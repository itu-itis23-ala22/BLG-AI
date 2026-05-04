"""
FastAPI application entry-point.

Endpoints
---------
POST  /api/index             – Start (or re-use) a crawl job
GET   /api/jobs              – List all jobs
GET   /api/jobs/{id}         – Single job detail
GET   /api/jobs/{id}/logs    – Append-only log stream (poll with ?after=N)
POST  /api/jobs/{id}/stop    – Gracefully stop a running job
POST  /api/search            – Full-text search across indexed pages
GET   /api/status            – System-wide health / back-pressure overview

The UI is served as a single static HTML file from ./static/index.html.
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import crawler as crawler_module
import search as search_module
import storage

# ─── Application setup ───────────────────────────────────────────────────────

app = FastAPI(title="Web Crawler", version="1.0.0")

# Serve static assets (index.html + any CSS/JS files)
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Process-global crawl manager
_manager = crawler_module.CrawlManager()


@app.on_event("startup")
def _on_startup() -> None:
    storage.init_db()
    _manager.resume_interrupted_jobs()


# ─── Serve the SPA ───────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


# ─── Request / response models ───────────────────────────────────────────────

class IndexRequest(BaseModel):
    origin: str
    k: int
    max_pages:   Optional[int]   = None
    rate_limit:  float            = 5.0
    max_queue:   int              = 1000
    num_workers: int              = 5

    @field_validator("k")
    @classmethod
    def k_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("k must be >= 0")
        return v

    @field_validator("rate_limit")
    @classmethod
    def rate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("rate_limit must be > 0")
        return v

    @field_validator("num_workers")
    @classmethod
    def workers_range(cls, v: int) -> int:
        if not 1 <= v <= 50:
            raise ValueError("num_workers must be between 1 and 50")
        return v

    @field_validator("max_queue")
    @classmethod
    def queue_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_queue must be >= 1")
        return v


class SearchRequest(BaseModel):
    query:  str
    limit:  int   = 50
    job_id: str   = ""


# ─── Index endpoints ─────────────────────────────────────────────────────────

@app.post("/api/index", status_code=201)
def start_index(req: IndexRequest) -> dict:
    """Initiate a web crawl from *origin* to at most depth *k*."""
    job_id = _manager.create_job(
        origin_url  = req.origin,
        max_depth   = req.k,
        max_pages   = req.max_pages,
        rate_limit  = req.rate_limit,
        max_queue   = req.max_queue,
        num_workers = req.num_workers,
    )
    return {"job_id": job_id, "status": "running"}


# ─── Job management endpoints ─────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs() -> list:
    return storage.list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Enrich with back-pressure flag
    job["back_pressure_active"] = (
        job.get("pending_depth", 0) > 0
        or job.get("queue_depth", 0) >= job.get("max_queue", 1)
    )
    return job


@app.get("/api/jobs/{job_id}/logs")
def get_logs(job_id: str, after: int = 0, limit: int = 200) -> list:
    """Return log entries for *job_id* with id > *after* (for long-polling)."""
    return storage.get_logs(job_id, after_id=after, limit=limit)


@app.post("/api/jobs/{job_id}/stop")
def stop_job(job_id: str) -> dict:
    found = _manager.stop_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Active job not found")
    return {"status": "stopping"}


# ─── Search endpoint ─────────────────────────────────────────────────────────

@app.post("/api/search")
def search(req: SearchRequest) -> dict:
    """
    Full-text search across all indexed pages.

    Returns a list of triples (relevant_url, origin_url, depth) enriched
    with job_id, title, and BM25 relevance score.

    Search runs concurrently with active crawls because SQLite WAL mode
    allows readers and a single writer to operate simultaneously without
    blocking each other.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    results = search_module.search(
        query  = req.query,
        limit  = min(req.limit, 500),
        job_id = req.job_id,
    )
    return {"query": req.query, "total": len(results), "results": results}


# ─── System status endpoint ───────────────────────────────────────────────────

@app.get("/api/status")
def system_status() -> dict:
    """
    Return a snapshot of the entire system:
      • running jobs with queue depth and back-pressure status
      • aggregate totals (pages indexed, jobs run)
    """
    all_jobs     = storage.list_jobs()
    running      = [j for j in all_jobs if j["status"] == "running"]
    total_pages  = sum(j["pages_crawled"] for j in all_jobs)
    total_failed = sum(j["pages_failed"]  for j in all_jobs)

    enriched_running = []
    for j in running:
        j = dict(j)
        j["back_pressure_active"] = (
            j.get("pending_depth", 0) > 0
            or j.get("queue_depth", 0) >= j.get("max_queue", 1)
        )
        enriched_running.append(j)

    return {
        "running_jobs":        enriched_running,
        "total_jobs":          len(all_jobs),
        "total_pages_indexed": total_pages,
        "total_pages_failed":  total_failed,
    }


# ─── Dev runner ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
