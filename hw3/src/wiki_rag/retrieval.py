"""Simple query classification and retrieval helpers."""

from __future__ import annotations

import re

from .config import PEOPLE, PLACES
from .ollama_client import OllamaClient
from .vector_store import QueryScope, RetrievedChunk, WikiVectorStore


PERSON_KEYWORDS = {
    "person",
    "people",
    "who",
    "born",
    "discover",
    "invent",
    "known for",
    "artist",
    "scientist",
    "footballer",
    "singer",
    "writer",
    "electricity",
}

PLACE_KEYWORDS = {
    "place",
    "where",
    "located",
    "city",
    "country",
    "built",
    "tower",
    "mount",
    "monument",
    "landmark",
    "turkey",
    "used for",
}


def classify_query(query: str) -> QueryScope:
    normalized = query.lower()
    mentions_person = any(_contains_name(normalized, name) for name in PEOPLE)
    mentions_place = any(_contains_name(normalized, name) for name in PLACES)

    if mentions_person and mentions_place:
        return "both"
    if mentions_person:
        return "person"
    if mentions_place:
        return "place"

    person_score = sum(1 for keyword in PERSON_KEYWORDS if keyword in normalized)
    place_score = sum(1 for keyword in PLACE_KEYWORDS if keyword in normalized)

    if person_score and place_score:
        return "both"
    if person_score:
        return "person"
    if place_score:
        return "place"
    return "both"


def retrieve(
    query: str,
    store: WikiVectorStore,
    ollama: OllamaClient,
    top_k: int = 6,
) -> tuple[QueryScope, list[RetrievedChunk]]:
    scope = classify_query(query)
    query_embedding = ollama.embed([query])[0]
    return scope, store.query(query_embedding=query_embedding, scope=scope, top_k=top_k)


def _contains_name(text: str, name: str) -> bool:
    words = re.escape(name.lower()).replace(r"\ ", r"\s+")
    return re.search(rf"\b{words}\b", text) is not None

