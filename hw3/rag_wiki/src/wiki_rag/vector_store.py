"""Persistent Chroma vector store wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import chromadb

from .chunking import TextChunk
from .config import CHROMA_DIR, DEFAULT_COLLECTION


QueryScope = Literal["person", "place", "both"]


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: dict
    distance: float


class WikiVectorStore:
    """One collection with metadata filters for people and places."""

    def __init__(self, persist_dir: Path = CHROMA_DIR, collection_name: str = DEFAULT_COLLECTION):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection_name = collection_name
        self.collection: Any = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Wikipedia chunks for people and places"},
        )

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except ValueError:
            pass
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def count(self) -> int:
        return self.collection.count()

    def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        batch_size: int = 128,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        for start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[start : start + batch_size]
            batch_embeddings = embeddings[start : start + batch_size]
            self.collection.upsert(
                ids=[chunk.id for chunk in batch_chunks],
                documents=[chunk.text for chunk in batch_chunks],
                metadatas=[chunk.metadata for chunk in batch_chunks],
                embeddings=batch_embeddings,
            )

    def query(
        self,
        query_embedding: list[float],
        scope: QueryScope = "both",
        top_k: int = 6,
    ) -> list[RetrievedChunk]:
        where = None if scope == "both" else {"entity_type": scope}
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            RetrievedChunk(text=document, metadata=metadata, distance=float(distance))
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]

