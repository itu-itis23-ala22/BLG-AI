"""
SQLite storage layer.

Uses WAL journal mode so readers never block writers and concurrent search
queries can run at full speed while the crawler is active.  Each thread gets
its own connection (thread-local) to avoid sharing connection state.

FTS5 with the Porter stemmer is used for full-text search.
"""

import sqlite3
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

DB_PATH = "crawler.db"

_local = threading.local()

# A process-wide lock serialises the rare case where two threads try to
# write to the FTS5 virtual table at exactly the same instant.  Regular
# row tables are handled by SQLite's WAL concurrency mechanism.
_fts_write_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    """Return (and lazily create) a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA cache_size=-32000")  # 32 MB page cache
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """Create all tables and indexes (idempotent)."""
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS crawl_jobs (
            id            TEXT PRIMARY KEY,
            origin_url    TEXT    NOT NULL,
            max_depth     INTEGER NOT NULL,
            max_pages     INTEGER,
            rate_limit    REAL    DEFAULT 5.0,
            max_queue     INTEGER DEFAULT 1000,
            num_workers   INTEGER DEFAULT 5,
            status        TEXT    DEFAULT 'pending',
            pages_crawled INTEGER DEFAULT 0,
            pages_failed  INTEGER DEFAULT 0,
            queue_depth   INTEGER DEFAULT 0,
            pending_depth INTEGER DEFAULT 0,
            created_at    REAL,
            updated_at    REAL,
            completed_at  REAL
        );

        /* ------------------------------------------------------------------ *
         * visited_urls – written once per URL, read on every discovery.       *
         * Kept per-job so separate crawls can re-visit the same page.         *
         * ------------------------------------------------------------------ */
        CREATE TABLE IF NOT EXISTS visited_urls (
            url    TEXT NOT NULL,
            job_id TEXT NOT NULL,
            PRIMARY KEY (url, job_id)
        );

        /* ------------------------------------------------------------------ *
         * indexed_pages – lightweight metadata row for each crawled page.     *
         * Full text lives in the FTS5 virtual table below.                    *
         * ------------------------------------------------------------------ */
        CREATE TABLE IF NOT EXISTS indexed_pages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT    NOT NULL,
            origin_url TEXT    NOT NULL,
            job_id     TEXT    NOT NULL,
            depth      INTEGER NOT NULL,
            title      TEXT    DEFAULT '',
            crawled_at REAL,
            UNIQUE(url, job_id)
        );
        CREATE INDEX IF NOT EXISTS ix_indexed_job
            ON indexed_pages(job_id);

        /* ------------------------------------------------------------------ *
         * pending_urls – overflow queue.                                      *
         * URLs that could not fit in the in-memory queue due to back          *
         * pressure are persisted here and fed back in when space is           *
         * available.  Also used for crash-resume.                             *
         * ------------------------------------------------------------------ */
        CREATE TABLE IF NOT EXISTS pending_urls (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT    NOT NULL,
            url    TEXT    NOT NULL,
            depth  INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_pending_job
            ON pending_urls(job_id, id);

        /* ------------------------------------------------------------------ *
         * page_fts – FTS5 full-text index with Porter stemmer.               *
         * UNINDEXED columns are stored but not tokenised; rank is via bm25.  *
         * ------------------------------------------------------------------ */
        CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
            content,
            url        UNINDEXED,
            origin_url UNINDEXED,
            job_id     UNINDEXED,
            depth      UNINDEXED,
            title      UNINDEXED,
            tokenize = 'porter ascii'
        );

        /* ------------------------------------------------------------------ *
         * job_logs – append-only event log for each job.                     *
         * ------------------------------------------------------------------ */
        CREATE TABLE IF NOT EXISTS job_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id     TEXT NOT NULL,
            level      TEXT DEFAULT 'INFO',
            message    TEXT NOT NULL,
            created_at REAL DEFAULT (unixepoch())
        );
        CREATE INDEX IF NOT EXISTS ix_logs_job
            ON job_logs(job_id, created_at);
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def create_job(
    job_id: str,
    origin_url: str,
    max_depth: int,
    max_pages: Optional[int],
    rate_limit: float,
    max_queue: int,
    num_workers: int,
) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO crawl_jobs
               (id, origin_url, max_depth, max_pages, rate_limit, max_queue,
                num_workers, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""",
        (job_id, origin_url, max_depth, max_pages, rate_limit, max_queue,
         num_workers, time.time(), time.time()),
    )
    conn.commit()


def update_job_stats(
    job_id: str,
    pages_crawled: int,
    pages_failed: int,
    queue_depth: int,
    pending_depth: int,
    status: Optional[str] = None,
) -> None:
    conn = get_conn()
    if status:
        conn.execute(
            """UPDATE crawl_jobs
               SET pages_crawled=?, pages_failed=?, queue_depth=?,
                   pending_depth=?, status=?, updated_at=?
               WHERE id=?""",
            (pages_crawled, pages_failed, queue_depth, pending_depth,
             status, time.time(), job_id),
        )
    else:
        conn.execute(
            """UPDATE crawl_jobs
               SET pages_crawled=?, pages_failed=?, queue_depth=?,
                   pending_depth=?, updated_at=?
               WHERE id=?""",
            (pages_crawled, pages_failed, queue_depth, pending_depth,
             time.time(), job_id),
        )
    conn.commit()


def finish_job(job_id: str, status: str = "completed") -> None:
    conn = get_conn()
    conn.execute(
        """UPDATE crawl_jobs
           SET status=?, completed_at=?, updated_at=?, queue_depth=0, pending_depth=0
           WHERE id=?""",
        (status, time.time(), time.time(), job_id),
    )
    conn.commit()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM crawl_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return dict(row) if row else None


def list_jobs() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM crawl_jobs ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Visited-URL helpers
# ---------------------------------------------------------------------------

def mark_visited_batch(job_id: str, urls: List[str]) -> None:
    """Persist a batch of visited URLs so they survive a restart."""
    if not urls:
        return
    conn = get_conn()
    conn.executemany(
        "INSERT OR IGNORE INTO visited_urls (url, job_id) VALUES (?, ?)",
        [(u, job_id) for u in urls],
    )
    conn.commit()


def load_visited(job_id: str) -> set:
    conn = get_conn()
    rows = conn.execute(
        "SELECT url FROM visited_urls WHERE job_id=?", (job_id,)
    ).fetchall()
    return {r["url"] for r in rows}


# ---------------------------------------------------------------------------
# Pending-URL (overflow queue) helpers
# ---------------------------------------------------------------------------

def push_pending(job_id: str, url: str, depth: int) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO pending_urls (job_id, url, depth) VALUES (?, ?, ?)",
        (job_id, url, depth),
    )
    conn.commit()


def pop_pending_batch(job_id: str, limit: int) -> List[Tuple[str, int]]:
    """Atomically remove and return up to *limit* pending URLs."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, url, depth FROM pending_urls WHERE job_id=? ORDER BY id LIMIT ?",
        (job_id, limit),
    ).fetchall()
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    conn.execute(
        f"DELETE FROM pending_urls WHERE id IN ({','.join('?'*len(ids))})",
        ids,
    )
    conn.commit()
    return [(r["url"], r["depth"]) for r in rows]


def count_pending(job_id: str) -> int:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) AS n FROM pending_urls WHERE job_id=?", (job_id,)
    ).fetchone()["n"]


# ---------------------------------------------------------------------------
# Indexed-page helpers
# ---------------------------------------------------------------------------

def insert_page(
    url: str,
    origin_url: str,
    job_id: str,
    depth: int,
    title: str,
    content: str,
) -> bool:
    """Insert a page into indexed_pages and page_fts.

    Returns True if the row was newly inserted, False if it already existed.
    """
    conn = get_conn()
    cursor = conn.execute(
        """INSERT OR IGNORE INTO indexed_pages
               (url, origin_url, job_id, depth, title, crawled_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (url, origin_url, job_id, depth, title[:500], time.time()),
    )
    if cursor.rowcount == 0:
        conn.commit()
        return False  # Already indexed

    # Write to FTS table under a lock to avoid WAL write conflicts
    with _fts_write_lock:
        conn.execute(
            """INSERT INTO page_fts
                   (content, url, origin_url, job_id, depth, title)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content[:65536], url, origin_url, job_id, depth, title[:500]),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def log(job_id: str, message: str, level: str = "INFO") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO job_logs (job_id, level, message) VALUES (?, ?, ?)",
        (job_id, level, message),
    )
    conn.commit()


def get_logs(
    job_id: str, after_id: int = 0, limit: int = 200
) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, level, message, created_at
           FROM job_logs
           WHERE job_id=? AND id>?
           ORDER BY id
           LIMIT ?""",
        (job_id, after_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]
