"""End-to-end ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .chunking import chunk_documents
from .config import PEOPLE, PLACES
from .ollama_client import OllamaClient
from .vector_store import WikiVectorStore
from .wikipedia import fetch_entities


@dataclass(frozen=True)
class IngestionResult:
    documents: int
    chunks: int
    collection_count: int


def ingest_default_dataset(
    store: WikiVectorStore,
    ollama: OllamaClient,
    reset: bool = False,
    batch_size: int = 32,
) -> IngestionResult:
    if reset:
        store.reset()

    documents = fetch_entities(PEOPLE, PLACES)
    chunks = chunk_documents(documents)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        embeddings = ollama.embed([chunk.text for chunk in batch])
        store.upsert_chunks(batch, embeddings)

    return IngestionResult(
        documents=len(documents),
        chunks=len(chunks),
        collection_count=store.count(),
    )

