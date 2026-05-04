# Product Requirements Document – Web Crawler

## Overview

A single-machine, depth-bounded web crawler that exposes two core capabilities:

1. **`index`** – Given a seed URL and depth *k*, crawl the web graph BFS-style to at most *k* hops from the origin, storing page content for later search.
2. **`search`** – Given a query string, return ranked `(relevant_url, origin_url, depth)` triples from all indexed pages, usable while indexing is still active.

---

## Goals

- Implement using language-native primitives (Python `threading`, `queue`, `urllib`, `html.parser`, `sqlite3`) rather than full-featured crawl/search libraries.
- Scale to large single-machine crawls through controlled concurrency, rate limiting, and back pressure.
- Provide a simple UI for launching jobs, monitoring progress, and running searches.
- Support crash-resume so a restarted server continues interrupted crawls.

---

## Non-Goals (v1)

- Multi-machine distributed crawling.
- JavaScript rendering (only static HTML is parsed).
- robots.txt compliance (out of scope for this exercise).
- Authentication on the API.

---

## Functional Requirements

### Index

| ID | Requirement |
|---|---|
| F1 | Accept `origin` (URL) and `k` (integer ≥ 0) as required parameters. |
| F2 | Never crawl the same URL twice within a job (deduplication via in-memory set + SQLite persistence). |
| F3 | Respect the depth budget: a page discovered *n* hops from origin is only crawled if *n ≤ k*. |
| F4 | Extract visible text and `<title>` from each page and store in an FTS5 full-text index. |
| F5 | Expose `rate_limit` (req/s), `max_queue` (back-pressure threshold), `num_workers`, and optional `max_pages` as tunable parameters. |
| F6 | Apply a token-bucket rate limiter shared across all worker threads. |
| F7 | When the in-memory queue reaches `max_queue`, overflow new URLs to a `pending_urls` DB table (back-pressure). A feeder thread drains the DB back into the queue as capacity is available. |
| F8 | Persist crawl state (visited URLs, pending queue, counters) to SQLite so a restarted server can resume. |

### Search

| ID | Requirement |
|---|---|
| S1 | Accept a free-form `query` string and return up to `limit` results. |
| S2 | Return results as `(relevant_url, origin_url, depth)` triples, enriched with `job_id`, `title`, and BM25 relevance score. |
| S3 | Search can be invoked while any crawl job is active; results reflect all pages indexed at query time. |
| S4 | Optionally filter results to a specific `job_id`. |

### UI

| ID | Requirement |
|---|---|
| U1 | **Crawl tab**: form to start a job; list of past/active jobs with status badges. |
| U2 | **Status tab**: system-wide statistics; running jobs with live queue-depth progress bars and back-pressure indicators. |
| U3 | **Search tab**: full-text query input; paginated result list with URL, origin, depth, title, and score. |
| U4 | **Job detail modal**: live-updating log stream (long-poll), counters, configuration summary, stop button. |

---

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| Concurrency | Each crawl job runs N worker threads (default 5, max 50) sharing a single rate limiter and dedup set. |
| Back pressure | Queue depth and DB pending count are exposed in the API and UI; the system degrades gracefully under load (no OOM) by spilling to SQLite. |
| Search latency | FTS5 with WAL mode should return results in < 100 ms for indexes up to ~1 M pages on commodity hardware. |
| Persistence | All state lives in a single `crawler.db` SQLite file. WAL mode ensures read queries never block writers. |
| Resumability | Jobs interrupted by process restart are automatically resumed on next startup. |

---

## Data Model

### `crawl_jobs`
Stores job configuration and live progress counters.

### `visited_urls`
One row per (url, job_id) pair, written in batches every 100 URLs.

### `indexed_pages`
Lightweight metadata row (url, origin_url, job_id, depth, title, crawled_at).

### `page_fts`
SQLite FTS5 virtual table. Stores page text with Porter stemming for full-text search.  
`content`, `url`, `origin_url`, `job_id`, `depth`, `title`.

### `pending_urls`
Overflow queue persisted to SQLite when in-memory queue is at capacity.

### `job_logs`
Append-only event log for each job (INFO/WARN/ERROR).

---

## Search While Indexing – Design Discussion

SQLite WAL (Write-Ahead Log) mode is the key mechanism:

- Writers append new frames to the WAL file without touching the main database file.
- Reader transactions open a snapshot at their start time and read committed frames from the WAL.
- **Result**: A search query and a crawler write can run simultaneously without any application-level locking or blocking.

At the application level, each thread uses its own SQLite connection (`threading.local`). A process-wide lock serialises writes to the FTS5 virtual table only (FTS5 internal structures are not concurrent-safe in the same process), but this lock is released in microseconds and does not affect reader throughput.

**If we were to scale beyond a single process**, the recommended approach is:

1. Promote SQLite to PostgreSQL (with GIN/tsvector full-text index) or Elasticsearch.
2. Run the search API behind a separate pool of read replicas or a dedicated search service that consumes an event stream (Kafka/SQS) from the crawler.
3. Use a consistent hashing ring or streaming replication to ensure search nodes see newly indexed documents within an acceptable SLA (e.g., < 5 s lag).

---

## Configuration Defaults

| Parameter | Default | Rationale |
|---|---|---|
| `rate_limit` | 5 req/s | Polite crawling; avoids triggering rate-limit responses on most public sites. |
| `max_queue` | 1000 | Keeps ~1 MB of URL strings in memory; back pressure activates before RAM pressure is felt. |
| `num_workers` | 5 | Saturates a typical home/office internet connection without overwhelming target servers. |
| `max_pages` | unlimited | The caller controls scope via `k` and `max_pages` together. |
