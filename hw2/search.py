"""
Search module.

Uses SQLite FTS5 (with the Porter stemmer) to find pages whose crawled
text matches a user query.  Results are ranked by BM25 relevance score
and returned as (relevant_url, origin_url, depth) triples, augmented
with the job_id, page title, and BM25 score.

Concurrency note
----------------
Because the underlying SQLite database runs in WAL mode, search queries
can execute *while* the crawler is actively writing new pages.  SQLite
guarantees that each read transaction sees a consistent snapshot of all
data that has been committed up to the moment the transaction opens – so
results always reflect the most recently indexed content without any
locking or coordination required on the Python side.

Query sanitisation
------------------
Raw user input is tokenised and each token is double-quoted before being
handed to FTS5.  This prevents accidental FTS5 operator injection while
still enabling the Porter stemmer to match inflected forms (e.g.
"running" matches "run", "runs", "ran").
"""

import re
from typing import Any, Dict, List

import storage

_TOKEN_RE = re.compile(r'[^\w]+', re.UNICODE)


def _make_fts_query(raw: str) -> str:
    """Convert free-form user text into a safe FTS5 MATCH expression.

    Each whitespace-delimited token is wrapped in double quotes so that
    FTS5 treats it as a phrase prefix rather than interpreting special
    operator characters.  Tokens are joined with OR so that any word
    match produces a result, ranked by BM25 score.
    """
    tokens = [t for t in _TOKEN_RE.split(raw.strip()) if t and len(t) >= 2]
    if not tokens:
        return '""'
    # Use phrase-prefix syntax: "token"* matches the token and any
    # stemmed/prefixed variant.
    return " OR ".join(f'"{t}"' for t in tokens)


def search(query: str, limit: int = 50, job_id: str = "") -> List[Dict[str, Any]]:
    """Search the FTS index and return a ranked list of result dicts.

    Each dict contains:
        relevant_url – URL of the matching page
        origin_url   – seed URL of the crawl that discovered it
        depth        – crawl depth at which the page was found
        job_id       – crawl job identifier
        title        – page <title> text
        score        – BM25 relevance score (higher = more relevant)

    Parameters
    ----------
    query   : free-form search string
    limit   : maximum number of results to return
    job_id  : if non-empty, restrict results to a single crawl job
    """
    if not query.strip():
        return []

    fts_query = _make_fts_query(query)
    conn = storage.get_conn()

    if job_id:
        rows = conn.execute(
            """SELECT url        AS relevant_url,
                      origin_url,
                      depth,
                      job_id,
                      title,
                      bm25(page_fts) AS score
               FROM page_fts
               WHERE content MATCH ?
                 AND job_id  = ?
               ORDER BY bm25(page_fts)
               LIMIT ?""",
            (fts_query, job_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT url        AS relevant_url,
                      origin_url,
                      depth,
                      job_id,
                      title,
                      bm25(page_fts) AS score
               FROM page_fts
               WHERE content MATCH ?
               ORDER BY bm25(page_fts)
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()

    return [dict(r) for r in rows]
