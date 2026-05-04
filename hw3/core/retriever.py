"""
Query classification and retrieval helpers.
The module decides which entity type a question targets and then finds useful
chunks from the local vector store.
"""

import logging
from core.embedder import embed_text
from core.vector_store import VectorStore
from config import TOP_K, PEOPLE, PLACES

logger = logging.getLogger(__name__)

# Map full names and meaningful name tokens back to the canonical entity name.
# For example, "Lionel Messi" can also be matched by "messi" or "lionel".
def _build_map(names: list[str]) -> dict[str, str]:
    m = {}
    for name in names:
        m[name.lower()] = name          # exact full-name match
        for token in name.lower().split():
            if len(token) > 3 and token not in m:  # skip very short or noisy tokens
                m[token] = name
    return m

_PEOPLE_MAP = _build_map(PEOPLE)
_PLACES_MAP = _build_map(PLACES)

# Simple keyword signals used when no entity name is found.
_PERSON_KEYWORDS = {
    "who", "born", "person", "people", "he", "she", "his", "her",
    "scientist", "artist", "player", "singer", "inventor", "writer",
    "discover", "discovered", "famous for", "known for", "life",
    "biography", "career", "achievement",
}

_PLACE_KEYWORDS = {
    "where", "located", "location", "place", "building", "monument",
    "landmark", "country", "city", "built", "tall", "height",
    "visit", "tourism", "site", "architecture", "structure",
}


def _find_named_entities(query: str) -> tuple[list[str], list[str]]:
    """Return canonical people and place names that appear in the query."""
    q = query.lower()
    matched_people = [orig for lower, orig in _PEOPLE_MAP.items() if lower in q]
    matched_places = [orig for lower, orig in _PLACES_MAP.items() if lower in q]
    return matched_people, matched_places


def classify_query(query: str) -> str:
    """
    Label a query as 'person', 'place', or 'both'.

    The classifier first trusts explicit entity names, then uses keyword
    signals, and finally searches both categories if the query is unclear.

    Returns:
        "person", "place", or "both".
    """
    matched_people, matched_places = _find_named_entities(query)

    if matched_people and matched_places:
        return "both"
    if matched_people:
        return "person"
    if matched_places:
        return "place"

    # Use keyword counts when there is no direct entity match.
    words = set(query.lower().split())
    person_score = len(words & _PERSON_KEYWORDS)
    place_score = len(words & _PLACE_KEYWORDS)

    if person_score > place_score:
        return "person"
    elif place_score > person_score:
        return "place"

    return "both"


def _flatten(results: dict) -> list[dict]:
    chunks = []
    if results and results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({"text": doc, "metadata": meta, "distance": dist})
    return chunks


def retrieve(
    query: str,
    store: VectorStore,
    top_k: int = TOP_K,
) -> dict:
    """
    Run the full retrieval path: classify, embed, and search.

    Direct entity matches are handled with metadata filters. General questions
    use a mix of semantic and keyword search.

    Returns:
        dict with keys:
            query_type: "person" | "place" | "both"
            chunks: list of {text, metadata, distance}
    """
    query_type = classify_query(query)
    logger.info(f"Query classified as: {query_type}")

    query_embedding = embed_text(query)

    matched_people, matched_places = _find_named_entities(query)
    named_entities = matched_people + matched_places

    if named_entities:
        # With named entities, search inside each matched entity first.
        chunks_per_entity = max(2, top_k // len(named_entities))
        all_chunks = []
        seen_ids = set()

        for entity in named_entities:
            # Include the first chunk because it usually contains the summary.
            intro = store.get_intro_chunk(entity)
            if intro:
                cid = entity + "0"
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_chunks.append(intro)

            # Add the most similar chunks for this specific entity.
            results = store.query(
                query_embedding=query_embedding,
                n_results=chunks_per_entity,
                where={"entity_name": entity},
            )
            for chunk in _flatten(results):
                cid = chunk["metadata"].get("entity_name", "") + str(chunk["metadata"].get("chunk_index", ""))
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_chunks.append(chunk)

        # Fill any remaining slots with a broader semantic search.
        if len(all_chunks) < top_k:
            type_filter = {"type": query_type} if query_type in ("person", "place") else None
            fallback = store.query(
                query_embedding=query_embedding,
                n_results=top_k,
                where=type_filter,
            )
            for chunk in _flatten(fallback):
                cid = chunk["metadata"].get("entity_name", "") + str(chunk["metadata"].get("chunk_index", ""))
                if cid not in seen_ids and len(all_chunks) < top_k:
                    seen_ids.add(cid)
                    all_chunks.append(chunk)

        chunks = all_chunks[:top_k]
    else:
        # Without entity names, combine semantic and keyword search.
        import re as _re
        # Remove generic words and classifier terms, leaving useful content words.
        _STOP = (
            {"a","an","the","is","are","was","were","be","been","what","who",
             "why","how","where","which","that","this","and","or","for","to",
             "of","in","on","at","by","with","about","from","do","did","tell",
             "me","us","it","its","can","could","would","should","famous","known"}
            | _PERSON_KEYWORDS | _PLACE_KEYWORDS
        )
        raw_words = _re.sub(r"[^\w\s]", "", query.lower()).split()
        keywords = [w for w in raw_words if w not in _STOP and len(w) > 2]

        where = {"type": query_type} if query_type in ("person", "place") else None

        semantic_chunks = _flatten(store.query(
            query_embedding=query_embedding,
            n_results=top_k,
            where=where,
        ))
        keyword_chunks = _flatten(store.keyword_search(
            keywords=keywords,
            n_results=top_k,
            where=where,
        ))

        # Prefer keyword hits, then add semantic results without duplicates.
        seen_ids = set()
        merged = []
        for chunk in keyword_chunks + semantic_chunks:
            cid = chunk["metadata"].get("entity_name", "") + str(chunk["metadata"].get("chunk_index", ""))
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged.append(chunk)

        chunks = merged[:top_k]

    logger.info(f"Retrieved {len(chunks)} chunks for query: '{query[:60]}'")
    return {"query_type": query_type, "chunks": chunks}
