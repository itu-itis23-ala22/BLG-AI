"""Wikipedia ingestion helpers built on the public MediaWiki API."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import RAW_DATA_DIR


API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "BLG483E-HW3-Local-Wikipedia-RAG/1.0"


@dataclass(frozen=True)
class WikiDocument:
    title: str
    entity_type: str
    url: str
    text: str


def _safe_filename(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")


def _request_json(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_wikipedia_page(title: str, entity_type: str, cache_dir: Path = RAW_DATA_DIR) -> WikiDocument:
    """Fetch a plain text Wikipedia page extract and cache it locally."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_safe_filename(title)}.json"

    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return WikiDocument(
            title=cached["title"],
            entity_type=cached["entity_type"],
            url=cached["url"],
            text=cached["text"],
        )

    payload = _request_json(
        {
            "action": "query",
            "format": "json",
            "prop": "extracts|info",
            "explaintext": "1",
            "redirects": "1",
            "inprop": "url",
            "titles": title,
        }
    )

    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        raise RuntimeError(f"Wikipedia returned no pages for {title!r}")

    page = next(iter(pages.values()))
    if "missing" in page:
        raise RuntimeError(f"Wikipedia page not found: {title!r}")

    document = WikiDocument(
        title=page.get("title", title),
        entity_type=entity_type,
        url=page.get("fullurl", f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"),
        text=_clean_extract(page.get("extract", "")),
    )
    if not document.text:
        raise RuntimeError(f"Wikipedia page had no extract text: {title!r}")

    cache_path.write_text(
        json.dumps(document.__dict__, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    time.sleep(0.2)
    return document


def fetch_entities(people: Iterable[str], places: Iterable[str]) -> list[WikiDocument]:
    documents: list[WikiDocument] = []
    for title in people:
        documents.append(fetch_wikipedia_page(title, "person"))
    for title in places:
        documents.append(fetch_wikipedia_page(title, "place"))
    return documents


def _clean_extract(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

