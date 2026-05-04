# Web Crawler

A depth-bounded web crawler with full-text search, built with Python, FastAPI, and SQLite.  
No third-party crawl/search libraries are used – everything is implemented with language-native primitives.

---

## Features

| Capability | Details |
|---|---|
| **Depth-bounded crawl** | Crawls from an origin URL to at most depth *k*; each discovered link is at most *k* hops from origin. |
| **Never visits the same page twice** | Per-job in-memory `set` (flushed to SQLite) provides O(1) dedup with full persistence for resume. |
| **Back pressure** | Bounded in-memory queue (`max_queue`). When full, overflow URLs are spilled to a SQLite `pending_urls` table. A feeder thread drains the DB back into the queue as space opens up. The UI shows queue depth and pending count in real time. |
| **Rate limiting** | Token-bucket limiter shared across all workers caps the aggregate HTTP request rate to `rate_limit` req/s. |
| **Concurrent search** | SQLite WAL journal mode lets search queries run at full speed while the crawler is writing – no coordination needed. Results reflect pages indexed up to the instant the query runs. |
| **Resumability** | On restart, jobs left in `running` state are automatically continued from the last known point (visited URLs + pending queue reloaded from SQLite). |
| **Full-text search** | SQLite FTS5 with the Porter stemmer indexes every page's visible text. Results are ranked by BM25 relevance score and returned as `(relevant_url, origin_url, depth)` triples. |

---

## Quick Start

```bash
# 1. Install dependencies (Python 3.10+)
cd /path/to/project
pip install -r requirements.txt

# 2. Start the server
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000

# 3. Open the UI
open http://localhost:8000
```

The SQLite database file (`crawler.db`) is created automatically on first run.

---

## Project Structure

```
.
├── main.py           # FastAPI app and API endpoints
├── crawler.py        # Core crawl engine (rate limiter, workers, back pressure)
├── storage.py        # SQLite storage layer (WAL mode, FTS5)
├── search.py         # Full-text search using FTS5
├── requirements.txt
├── static/
│   └── index.html    # Single-page UI (vanilla JS, no framework)
├── README.md
├── product_prd.md
└── recommendation.md
```

---

## API Reference

### `POST /api/index`
Start a new crawl job.

```json
{
  "origin": "https://example.com",
  "k": 2,
  "rate_limit": 5.0,
  "max_queue": 1000,
  "num_workers": 5,
  "max_pages": null
}
```

Response: `{ "job_id": "...", "status": "running" }`

### `POST /api/search`
Search all indexed pages.

```json
{ "query": "machine learning", "limit": 50, "job_id": "" }
```

Response:
```json
{
  "query": "machine learning",
  "total": 12,
  "results": [
    { "relevant_url": "...", "origin_url": "...", "depth": 1, "job_id": "...", "title": "...", "score": 3.14 }
  ]
}
```

### `GET /api/jobs`
List all crawl jobs (ordered newest-first).

### `GET /api/jobs/{job_id}`
Single job detail including queue depth, pending depth, and back-pressure status.

### `GET /api/jobs/{job_id}/logs?after=N`
Append-only log stream (use `?after=<last_id>` for incremental polling).

### `POST /api/jobs/{job_id}/stop`
Gracefully stop a running job.

### `GET /api/status`
System-wide snapshot: running jobs, total pages indexed, back-pressure indicators.

---

## Architecture

### Crawl Engine (`crawler.py`)

```
┌──────────────────────────────────────────────────────┐
│  CrawlJob                                            │
│                                                      │
│  ┌──────────┐   ┌──────────────────────────────┐    │
│  │ In-memory│   │  Worker Thread × N           │    │
│  │  Queue   │──▶│  1. acquire rate-limit token │    │
│  │(maxsize) │   │  2. HTTP GET                 │    │
│  └─────┬────┘   │  3. parse HTML               │    │
│        │        │  4. INSERT indexed_pages/FTS │    │
│  back  │        │  5. enqueue discovered links │    │
│  press.│        └──────────────────────────────┘    │
│        ▼                                             │
│  ┌──────────────────┐   ┌────────────────────┐      │
│  │ SQLite           │◀──│ Feeder Thread      │      │
│  │ pending_urls     │──▶│ (drains DB → queue)│      │
│  └──────────────────┘   └────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

### Back Pressure Detail

When `queue.qsize() >= max_queue`:
- Newly discovered URLs are written to `pending_urls` (SQLite) instead of the in-memory queue.
- The feeder thread wakes every 0.5 s and moves URLs from `pending_urls` back into the queue as space is available.
- The API exposes `queue_depth` and `pending_depth`; the UI shows both as progress bars with colour-coded warning/danger states.

### Search concurrency

SQLite WAL mode separates readers from writers at the page level. A search transaction opens a consistent snapshot and reads the FTS5 index without blocking – or being blocked by – the crawler's write transactions. No application-level locking is required.

---

## Configuration Reference

| Parameter | Default | Description |
|---|---|---|
| `k` | — | Maximum crawl depth from origin |
| `rate_limit` | 5.0 | HTTP requests per second (token-bucket) |
| `max_queue` | 1000 | In-memory queue capacity; back pressure activates above this |
| `num_workers` | 5 | Number of concurrent fetch threads per job |
| `max_pages` | unlimited | Hard cap on total pages crawled per job |
