"""
Small custom vector store backed by NumPy and JSON files.

It keeps the core retrieval logic explicit for the assignment while still
supporting metadata filters, upserts, and a basic keyword search.
"""

import os
import json
import logging
import numpy as np
from config import CHROMA_PERSIST_DIR, COLLECTION_NAME

logger = logging.getLogger(__name__)

# Store vectors beside the configured data directory.
STORE_DIR = os.path.join(os.path.dirname(CHROMA_PERSIST_DIR), "vector_store")


class VectorStore:
    """
    Persistent vector store with cosine similarity and metadata filtering.
    """

    def __init__(self, persist_dir: str = STORE_DIR):
        self._persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)

        self._data_file = os.path.join(persist_dir, "store.json")
        self._embeddings_file = os.path.join(persist_dir, "embeddings.npy")

        # Data is loaded into memory for fast local search.
        self._ids: list[str] = []
        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._embeddings: np.ndarray | None = None

        self._load()
        logger.info(
            f"VectorStore ready — {len(self._ids)} documents loaded"
        )

    def _load(self) -> None:
        """Load the saved store files when they are present."""
        if os.path.exists(self._data_file) and os.path.exists(self._embeddings_file):
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._ids = data["ids"]
            self._documents = data["documents"]
            self._metadatas = data["metadatas"]
            self._embeddings = np.load(self._embeddings_file)
            logger.info(f"Loaded {len(self._ids)} documents from disk")

    def _save(self) -> None:
        """Write metadata and embeddings back to disk."""
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump({
                "ids": self._ids,
                "documents": self._documents,
                "metadatas": self._metadatas,
            }, f, ensure_ascii=False)

        if self._embeddings is not None:
            np.save(self._embeddings_file, self._embeddings)
        logger.info(f"Saved {len(self._ids)} documents to disk")

    def add_chunks(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Add or replace chunks in the vector store.
        """
        new_embeddings = np.array(embeddings, dtype=np.float32)

        # Remove existing rows for incoming IDs before appending new versions.
        existing_ids = set(self._ids)
        incoming_ids = set(ids)
        overlap = existing_ids & incoming_ids

        if overlap:
            # Keep every stored chunk except the ones being replaced.
            keep_mask = [i for i, _id in enumerate(self._ids) if _id not in overlap]
            self._ids = [self._ids[i] for i in keep_mask]
            self._documents = [self._documents[i] for i in keep_mask]
            self._metadatas = [self._metadatas[i] for i in keep_mask]
            if self._embeddings is not None and len(keep_mask) > 0:
                self._embeddings = self._embeddings[keep_mask]
            elif len(keep_mask) == 0:
                self._embeddings = None

        # Append the new chunk batch.
        self._ids.extend(ids)
        self._documents.extend(texts)
        self._metadatas.extend(metadatas)

        if self._embeddings is not None and len(self._embeddings) > 0:
            self._embeddings = np.vstack([self._embeddings, new_embeddings])
        else:
            self._embeddings = new_embeddings

        self._save()
        logger.info(f"Upserted {len(ids)} chunks (total: {len(self._ids)})")

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """
        Query the vector store using cosine similarity.

        Args:
            query_embedding: the query vector.
            n_results: number of results to return.
            where: optional metadata filter, e.g. {"type": "person"}.

        Returns:
            Dict with keys: ids, documents, metadatas, distances (lists of lists).
        """
        if self._embeddings is None or len(self._ids) == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Narrow the candidate set with metadata when requested.
        if where:
            mask = []
            for i, meta in enumerate(self._metadatas):
                match = all(meta.get(k) == v for k, v in where.items())
                mask.append(match)
            indices = [i for i, m in enumerate(mask) if m]
        else:
            indices = list(range(len(self._ids)))

        if not indices:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Calculate cosine similarity manually with NumPy.
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        filtered_embeddings = self._embeddings[indices]
        norms = np.linalg.norm(filtered_embeddings, axis=1)

        # Ignore zero-length vectors to avoid invalid division.
        valid = norms > 0
        similarities = np.zeros(len(indices))
        if valid.any():
            similarities[valid] = (
                filtered_embeddings[valid] @ query_vec
            ) / (norms[valid] * query_norm)

        # The rest of the app expects distance, so use 1 - similarity.
        distances = 1.0 - similarities

        # Return the closest matches.
        k = min(n_results, len(indices))
        top_k_local = np.argsort(distances)[:k]

        result_ids = []
        result_docs = []
        result_metas = []
        result_dists = []

        for local_idx in top_k_local:
            global_idx = indices[local_idx]
            result_ids.append(self._ids[global_idx])
            result_docs.append(self._documents[global_idx])
            result_metas.append(self._metadatas[global_idx])
            result_dists.append(float(distances[local_idx]))

        return {
            "ids": [result_ids],
            "documents": [result_docs],
            "metadatas": [result_metas],
            "distances": [result_dists],
        }

    def count(self) -> int:
        """Return the number of stored chunks."""
        return len(self._ids)

    def get_stats(self) -> dict:
        """Return simple counts for the UI sidebar."""
        if not self._ids:
            return {"total_chunks": 0, "unique_entities": 0, "people_chunks": 0, "place_chunks": 0}

        entities = set()
        people_count = 0
        place_count = 0
        for m in self._metadatas:
            entities.add(m.get("entity_name", "unknown"))
            if m.get("type") == "person":
                people_count += 1
            else:
                place_count += 1

        return {
            "total_chunks": len(self._ids),
            "unique_entities": len(entities),
            "people_chunks": people_count,
            "place_chunks": place_count,
        }

    def get_intro_chunk(self, entity_name: str) -> dict | None:
        """Return the first chunk for an entity when it exists."""
        for doc, meta in zip(self._documents, self._metadatas):
            if meta.get("entity_name") == entity_name and meta.get("chunk_index") == 0:
                return {"text": doc, "metadata": meta, "distance": 0.0}
        return None

    def keyword_search(
        self,
        keywords: list[str],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """
        Find chunks containing at least one keyword, ranked by hit count.
        """
        if not keywords or not self._ids:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        kw_lower = [k.lower() for k in keywords]

        # Apply the same optional metadata filter as semantic search.
        if where:
            indices = [i for i, m in enumerate(self._metadatas) if all(m.get(k) == v for k, v in where.items())]
        else:
            indices = list(range(len(self._ids)))

        scored = []
        for i in indices:
            text_lower = self._documents[i].lower()
            hits = sum(kw in text_lower for kw in kw_lower)
            if hits > 0:
                scored.append((i, hits))

        # Higher keyword hit count means a better keyword match.
        scored.sort(key=lambda x: -x[1])
        top = scored[:n_results]

        if not top:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        result_ids, result_docs, result_metas, result_dists = [], [], [], []
        for idx, hits in top:
            result_ids.append(self._ids[idx])
            result_docs.append(self._documents[idx])
            result_metas.append(self._metadatas[idx])
            result_dists.append(1.0 - (hits / max(len(kw_lower), 1)))

        return {
            "ids": [result_ids],
            "documents": [result_docs],
            "metadatas": [result_metas],
            "distances": [result_dists],
        }

    def reset(self) -> None:
        """Clear memory and delete persisted store files."""
        self._ids = []
        self._documents = []
        self._metadatas = []
        self._embeddings = None

        # Remove persisted files if they already exist.
        for f in [self._data_file, self._embeddings_file]:
            if os.path.exists(f):
                os.remove(f)

        logger.info("Vector store reset")
