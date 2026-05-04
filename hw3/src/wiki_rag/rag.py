"""RAG orchestration for answering questions from retrieved Wikipedia context."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ollama_client import OllamaClient
from .retrieval import retrieve
from .vector_store import RetrievedChunk, WikiVectorStore


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    scope: str
    sources: list[RetrievedChunk]


class LocalWikipediaRag:
    def __init__(self, store: WikiVectorStore, ollama: OllamaClient):
        self.store = store
        self.ollama = ollama

    def answer(self, query: str, top_k: int = 6) -> RagAnswer:
        if self.store.count() == 0:
            return RagAnswer(answer="I don't know. The local vector store is empty; run ingestion first.", scope="both", sources=[])

        scope, sources = retrieve(query=query, store=self.store, ollama=self.ollama, top_k=top_k)
        if not sources:
            return RagAnswer(answer="I don't know.", scope=scope, sources=[])

        prompt = _build_prompt(query, sources)
        answer = self.ollama.generate(prompt)
        if not answer:
            answer = "I don't know."
        return RagAnswer(answer=answer, scope=scope, sources=sources)


def _build_prompt(query: str, sources: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[Source {index}] {source.metadata.get('title')} "
        f"({source.metadata.get('entity_type')}, chunk {source.metadata.get('chunk_index')})\n"
        f"{_trim(source.text, 1400)}"
        for index, source in enumerate(sources, start=1)
    )
    return f"""You are a local Wikipedia retrieval-augmented assistant.

Answer the user's question using only the context below.
If the context does not contain enough information, answer exactly: I don't know.
Do not use outside knowledge.
For comparison questions, compare the entities using separate facts from the provided context; the context does not need to contain a pre-written comparison.
When useful, mention source titles in plain text.

Context:
{context}

Question: {query}
Answer:"""


def _trim(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."

