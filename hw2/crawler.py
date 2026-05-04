"""
Core crawl engine.

Design overview
---------------
Each CrawlJob runs a configurable pool of worker threads that share:
  • An in-memory bounded Queue  (hard back-pressure limit)
  • A token-bucket RateLimiter  (max HTTP requests / second)
  • A thread-safe in-memory visited set  (fast O(1) dedup)

Back-pressure behaviour
-----------------------
When the in-memory queue is at capacity (queue.qsize() >= max_queue),
newly discovered URLs are written to the SQLite `pending_urls` table
instead.  A lightweight feeder thread wakes every 0.5 s and drains
pending_urls back into the queue as space becomes available.
This decouples discovery from consumption and provides:
  1. A clear "back-pressure active" signal (pending_depth > 0).
  2. Full crash-resume capability – the pending table survives restarts.

Concurrent search
-----------------
All writes go to SQLite with WAL journal mode enabled, which means
readers (search queries) never block and always see the latest committed
data.  The FTS5 virtual table is updated atomically with each page
insertion via a process-level write lock so no partial rows appear.

Resumability
------------
On restart the CrawlManager calls start(resume=True).  The worker loads:
  • visited_urls   – to rebuild the in-memory dedup set
  • pending_urls   – to re-seed the in-memory queue
Pages that were already inserted into indexed_pages / page_fts are not
re-fetched.
"""

import queue
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple

import storage

# ─── SSL context ────────────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PyCrawler/1.0; +localhost)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}

_MAX_BODY_BYTES = 512 * 1024   # 512 KB – large enough for most pages
_FETCH_TIMEOUT  = 12           # seconds


# ─── Rate limiter ────────────────────────────────────────────────────────────

class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Calling ``acquire()`` blocks (sleeps) until a request token is available,
    ensuring the aggregate request rate across all workers never exceeds
    *rate* requests per second.
    """

    def __init__(self, rate: float) -> None:
        self._rate   = max(rate, 0.01)
        self._tokens = self._rate
        self._last   = time.monotonic()
        self._lock   = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now     = time.monotonic()
                elapsed = now - self._last
                self._last   = now
                self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)


# ─── HTML parser ─────────────────────────────────────────────────────────────

class _PageParser(HTMLParser):
    """Extract visible text, page title, and outbound links from HTML."""

    _SKIP = frozenset({"script", "style", "noscript", "head", "meta", "link",
                        "svg", "canvas"})

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url  = base_url
        self.title     = ""
        self.links:    List[str] = []
        self._text:    List[str] = []
        self._in_title = False
        self._skip_n   = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag in self._SKIP:
            self._skip_n += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            href = href.strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:")):
                abs_url = urllib.parse.urljoin(self.base_url, href)
                parsed  = urllib.parse.urlparse(abs_url)
                if parsed.scheme in ("http", "https"):
                    clean = parsed._replace(fragment="").geturl()
                    self.links.append(clean)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP:
            self._skip_n = max(0, self._skip_n - 1)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        if self._skip_n == 0:
            self._text.append(text)

    @property
    def text(self) -> str:
        return " ".join(self._text)


# ─── HTTP fetch ──────────────────────────────────────────────────────────────

def _fetch(url: str) -> Tuple[Optional[str], int]:
    """Return (html, http_status).  html is None on any error."""
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(
            req, timeout=_FETCH_TIMEOUT, context=_SSL_CTX
        ) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" not in ct and "application/xhtml" not in ct:
                return None, resp.status
            raw     = resp.read(_MAX_BODY_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace"), resp.status
    except urllib.error.HTTPError as exc:
        return None, exc.code
    except Exception:
        return None, 0


# ─── Crawl job ───────────────────────────────────────────────────────────────

_VISITED_FLUSH_EVERY = 100   # persist visited set to DB every N new URLs


class CrawlJob:
    """Manages a single depth-bounded web crawl.

    Parameters
    ----------
    job_id       : unique identifier (stored in DB)
    origin_url   : seed URL
    max_depth    : maximum hops from origin (depth=0 means origin only)
    max_pages    : optional hard cap on total pages crawled
    rate_limit   : maximum HTTP requests per second (shared across workers)
    max_queue    : in-memory queue capacity; triggers back-pressure when full
    num_workers  : number of concurrent fetch threads
    """

    def __init__(
        self,
        job_id:      str,
        origin_url:  str,
        max_depth:   int,
        max_pages:   Optional[int] = None,
        rate_limit:  float = 5.0,
        max_queue:   int   = 1000,
        num_workers: int   = 5,
    ) -> None:
        self.job_id      = job_id
        self.origin_url  = origin_url
        self.max_depth   = max_depth
        self.max_pages   = max_pages
        self.max_queue   = max_queue
        self.num_workers = num_workers

        self._queue        = queue.Queue()          # unbounded in Python; we enforce max_queue manually
        self._rate         = RateLimiter(rate_limit)
        self._stop         = threading.Event()

        # Visited set – in-memory for O(1) lookup; periodically flushed to DB
        self._visited:     Set[str] = set()
        self._visited_buf: List[str] = []           # unflushed batch
        self._vis_lock     = threading.Lock()

        # Counters (protected by _cnt_lock)
        self._crawled = 0
        self._failed  = 0
        self._cnt_lock = threading.Lock()

        self._workers: List[threading.Thread] = []

    # ── public ────────────────────────────────────────────────────────────

    def start(self, resume: bool = False) -> None:
        """Spawn worker threads and begin crawling."""
        conn_thread = threading.Thread(
            target=self._bootstrap,
            args=(resume,),
            daemon=True,
            name=f"boot-{self.job_id[:8]}",
        )
        conn_thread.start()

    def stop(self) -> None:
        """Request a graceful shutdown."""
        self._stop.set()

    # ── bootstrap (runs in its own thread to not block the API) ───────────

    def _bootstrap(self, resume: bool) -> None:
        storage.log(self.job_id, f"Job started  origin={self.origin_url}  "
                                  f"depth={self.max_depth}  resume={resume}")

        if resume:
            # Reload visited set from DB
            visited = storage.load_visited(self.job_id)
            with self._vis_lock:
                self._visited = visited
            storage.log(self.job_id, f"Resumed with {len(visited)} visited URLs")

            # Reload counters
            job = storage.get_job(self.job_id)
            if job:
                with self._cnt_lock:
                    self._crawled = job["pages_crawled"]
                    self._failed  = job["pages_failed"]

            # Drain DB pending queue into memory
            batch = storage.pop_pending_batch(self.job_id, self.max_queue)
            for url, depth in batch:
                self._queue.put((url, depth))
        else:
            # Fresh start: seed with origin
            if self._mark_visited(self.origin_url):
                self._queue.put((self.origin_url, 0))

        if self._queue.empty() and storage.count_pending(self.job_id) == 0:
            storage.log(self.job_id, "Nothing to crawl – job complete")
            storage.finish_job(self.job_id, "completed")
            return

        # Feeder thread
        feeder = threading.Thread(
            target=self._feeder_loop,
            daemon=True,
            name=f"feeder-{self.job_id[:8]}",
        )
        feeder.start()

        # Worker threads
        for i in range(self.num_workers):
            t = threading.Thread(
                target=self._worker,
                daemon=True,
                name=f"worker-{self.job_id[:8]}-{i}",
            )
            t.start()
            self._workers.append(t)

        # Wait for all workers to finish
        for t in self._workers:
            t.join()

        feeder.join(timeout=3)

        self._flush_visited(force=True)

        with self._cnt_lock:
            c, f = self._crawled, self._failed

        final_status = "stopped" if self._stop.is_set() else "completed"
        storage.finish_job(self.job_id, final_status)
        storage.log(
            self.job_id,
            f"Job {final_status}: {c} pages crawled, {f} failed",
        )

    # ── feeder thread ──────────────────────────────────────────────────────

    def _feeder_loop(self) -> None:
        """Move URLs from the SQLite pending table back into memory."""
        while not self._stop.is_set():
            time.sleep(0.5)
            available = max(0, self.max_queue - self._queue.qsize())
            if available == 0:
                continue
            batch = storage.pop_pending_batch(self.job_id, available)
            for url, depth in batch:
                self._queue.put((url, depth))

    # ── worker thread ──────────────────────────────────────────────────────

    def _worker(self) -> None:
        idle_rounds = 0
        while not self._stop.is_set():
            try:
                url, depth = self._queue.get(timeout=2.0)
                idle_rounds = 0
            except queue.Empty:
                idle_rounds += 1
                # If the queue and the pending table are both empty for
                # several consecutive rounds, this worker is done.
                if idle_rounds >= 4 and storage.count_pending(self.job_id) == 0:
                    break
                continue

            try:
                self._process(url, depth)
            finally:
                self._queue.task_done()

    # ── core processing ────────────────────────────────────────────────────

    def _process(self, url: str, depth: int) -> None:
        # Hard page cap
        if self.max_pages is not None:
            with self._cnt_lock:
                if self._crawled >= self.max_pages:
                    self._stop.set()
                    return

        # Rate-limit token acquisition (sleeps when needed)
        self._rate.acquire()

        if self._stop.is_set():
            return

        html, status = _fetch(url)

        if html is None:
            with self._cnt_lock:
                self._failed += 1
            storage.log(self.job_id, f"FAIL [{status:3d}] {url}", "WARN")
            self._push_stats()
            return

        # Parse HTML
        parser = _PageParser(url)
        try:
            parser.feed(html)
        except Exception:
            pass  # Partial parse results are still useful

        # Persist
        inserted = storage.insert_page(
            url        = url,
            origin_url = self.origin_url,
            job_id     = self.job_id,
            depth      = depth,
            title      = parser.title.strip(),
            content    = parser.text,
        )

        if inserted:
            with self._cnt_lock:
                self._crawled += 1
            storage.log(self.job_id, f"OK  [{depth}] {url[:120]}")

        self._push_stats()

        # Enqueue discovered links (if within depth budget)
        if depth < self.max_depth:
            for link in set(parser.links):
                if self._mark_visited(link):
                    self._enqueue(link, depth + 1)

    # ── helpers ────────────────────────────────────────────────────────────

    def _mark_visited(self, url: str) -> bool:
        """Mark *url* as visited.  Returns True if it was new."""
        with self._vis_lock:
            if url in self._visited:
                return False
            self._visited.add(url)
            self._visited_buf.append(url)

        self._flush_visited()
        return True

    def _flush_visited(self, force: bool = False) -> None:
        with self._vis_lock:
            if not force and len(self._visited_buf) < _VISITED_FLUSH_EVERY:
                return
            batch = self._visited_buf[:]
            self._visited_buf.clear()
        storage.mark_visited_batch(self.job_id, batch)

    def _enqueue(self, url: str, depth: int) -> None:
        """Put URL in memory queue or spill to DB if at back-pressure limit."""
        if self._queue.qsize() < self.max_queue:
            self._queue.put((url, depth))
        else:
            # Back-pressure: overflow to persistent pending table
            storage.push_pending(self.job_id, url, depth)

    def _push_stats(self) -> None:
        with self._cnt_lock:
            c, f = self._crawled, self._failed
        storage.update_job_stats(
            job_id       = self.job_id,
            pages_crawled= c,
            pages_failed = f,
            queue_depth  = self._queue.qsize(),
            pending_depth= storage.count_pending(self.job_id),
        )


# ─── Crawl manager ───────────────────────────────────────────────────────────

class CrawlManager:
    """Singleton that creates, tracks, and resumes CrawlJob instances."""

    def __init__(self) -> None:
        self._jobs: Dict[str, CrawlJob] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        origin_url:  str,
        max_depth:   int,
        max_pages:   Optional[int] = None,
        rate_limit:  float = 5.0,
        max_queue:   int   = 1000,
        num_workers: int   = 5,
    ) -> str:
        job_id = uuid.uuid4().hex[:16]
        storage.create_job(
            job_id      = job_id,
            origin_url  = origin_url,
            max_depth   = max_depth,
            max_pages   = max_pages,
            rate_limit  = rate_limit,
            max_queue   = max_queue,
            num_workers = num_workers,
        )
        job = CrawlJob(
            job_id      = job_id,
            origin_url  = origin_url,
            max_depth   = max_depth,
            max_pages   = max_pages,
            rate_limit  = rate_limit,
            max_queue   = max_queue,
            num_workers = num_workers,
        )
        with self._lock:
            self._jobs[job_id] = job
        job.start(resume=False)
        return job_id

    def stop_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if job:
            job.stop()
            return True
        return False

    def resume_interrupted_jobs(self) -> None:
        """Called at startup to restart any jobs left in 'running' state."""
        rows = storage.list_jobs()
        for row in rows:
            if row["status"] == "running":
                job_id = row["id"]
                job = CrawlJob(
                    job_id      = job_id,
                    origin_url  = row["origin_url"],
                    max_depth   = row["max_depth"],
                    max_pages   = row["max_pages"],
                    rate_limit  = row["rate_limit"],
                    max_queue   = row["max_queue"],
                    num_workers = row["num_workers"],
                )
                with self._lock:
                    self._jobs[job_id] = job
                job.start(resume=True)
