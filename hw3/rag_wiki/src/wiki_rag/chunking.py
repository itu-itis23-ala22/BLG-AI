"""Document chunking with overlap for long Wikipedia articles."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .config import CHUNK_OVERLAP, CHUNK_WORDS
from .wikipedia import WikiDocument


@dataclass(frozen=True)
class TextChunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def chunk_document(
    document: WikiDocument,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    if chunk_words <= 0:
        raise ValueError("chunk_words must be positive")
    if overlap_words < 0 or overlap_words >= chunk_words:
        raise ValueError("overlap_words must be smaller than chunk_words")

    words = _tokenize_words(document.text)
    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            stable_id = _chunk_id(document.title, index, chunk_text)
            chunks.append(
                TextChunk(
                    id=stable_id,
                    text=chunk_text,
                    metadata={
                        "title": document.title,
                        "entity_type": document.entity_type,
                        "source_url": document.url,
                        "chunk_index": index,
                    },
                )
            )
        if end == len(words):
            break
        start = end - overlap_words
        index += 1

    return chunks


def chunk_documents(documents: list[WikiDocument]) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in documents:
        chunks.extend(chunk_document(document))
    return chunks


def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"\S+", text.replace("\n", " "))


def _chunk_id(title: str, index: int, text: str) -> str:
    digest = hashlib.sha1(f"{title}:{index}:{text}".encode("utf-8")).hexdigest()[:16]
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", title.lower()).strip("-")
    return f"{normalized}-{index}-{digest}"

