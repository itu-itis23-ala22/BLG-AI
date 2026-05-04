"""
Text chunking utilities for Wikipedia articles.
Chunks use a fixed character window plus overlap so large pages remain usable.
"""

import logging
from config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks near the requested size.

    The splitter looks for a nearby sentence boundary before falling back to a
    hard character split.

    Args:
        text: Full document text.
        chunk_size: Target number of characters per chunk.
        chunk_overlap: Characters repeated between neighboring chunks.

    Returns:
        Chunk strings in article order.
    """
    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Prefer a sentence break near the end of the window.
        if end < text_len:
            # Search backward from the tentative end position.
            search_start = max(start + chunk_size // 2, start)
            best_break = -1
            for i in range(end, search_start, -1):
                if text[i - 1] in ".!?\n" and (i >= text_len or text[i] == " " or text[i] == "\n"):
                    best_break = i
                    break

            if best_break > start:
                end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward while keeping overlap for context continuity.
        start = end - chunk_overlap if end < text_len else text_len

    return chunks


def chunk_article(article: dict, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Chunk one fetched article and add metadata to each piece.

    Args:
        article: Dictionary with title, text, url, and type.

    Returns:
        Chunk dictionaries with text, id, and metadata.
    """
    raw_chunks = chunk_text(article["text"], chunk_size, chunk_overlap)

    result = []
    for i, chunk in enumerate(raw_chunks):
        result.append({
            "id": f"{article['title'].replace(' ', '_')}_{i}",
            "text": chunk,
            "metadata": {
                "entity_name": article["title"],
                "type": article["type"],
                "chunk_index": i,
                "source_url": article["url"],
            },
        })

    logger.info(
        f"Chunked '{article['title']}' into {len(result)} chunks "
        f"(avg {sum(len(c['text']) for c in result) // max(len(result), 1)} chars)"
    )
    return result
