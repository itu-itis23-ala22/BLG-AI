"""
Build the local Wikipedia knowledge base.

Usage:
    python ingest.py            # add configured entities that are not stored yet
    python ingest.py --reset    # clear local data and rebuild it
"""

import sys
import argparse
import logging
import time

# Basic console logging for the ingestion run.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")

from config import PEOPLE, PLACES
from core.wikipedia_fetcher import fetch_all
from core.chunker import chunk_article
from core.embedder import embed_batch
from core.vector_store import VectorStore
from core.database import init_db, record_ingestion, is_ingested, clear_ingestion_records, get_ingestion_stats


def ingest_entities(entities: list[str], entity_type: str, store: VectorStore) -> int:
    """
    Fetch, chunk, embed, and store one group of entities.

    Returns:
        Number of entities added during this run.
    """
    # Avoid duplicating entities that were already ingested.
    to_ingest = [e for e in entities if not is_ingested(e)]

    if not to_ingest:
        logger.info(f"All {entity_type} entities already ingested — skipping")
        return 0

    logger.info(f"Fetching {len(to_ingest)} {entity_type} articles from Wikipedia...")
    articles = fetch_all(to_ingest, entity_type)

    ingested = 0
    for article in articles:
        try:
            # Split the article before embedding.
            chunks = chunk_article(article)
            if not chunks:
                logger.warning(f"No chunks produced for '{article['title']}'")
                continue

            # Include the title so chunks remain tied to their entity.
            texts = [c["text"] for c in chunks]
            embed_inputs = [f"{article['title']}: {t}" for t in texts]
            logger.info(f"Embedding {len(texts)} chunks for '{article['title']}'...")
            embeddings = embed_batch(embed_inputs)

            # Save text, vectors, and metadata together.
            ids = [c["id"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            store.add_chunks(ids, texts, embeddings, metadatas)

            # Record ingestion after vectors have been written.
            record_ingestion(
                name=article["title"],
                entity_type=entity_type,
                url=article["url"],
                chunk_count=len(chunks),
            )
            ingested += 1
            logger.info(f"✅ Ingested '{article['title']}' ({len(chunks)} chunks)")

        except Exception as e:
            logger.error(f"❌ Failed to ingest '{article['title']}': {e}")

    return ingested


def main():
    parser = argparse.ArgumentParser(description="Ingest Wikipedia articles into the RAG system")
    parser.add_argument("--reset", action="store_true", help="Clear all data and re-ingest")
    args = parser.parse_args()

    start_time = time.time()

    # Prepare the SQLite tables.
    init_db()

    # Load or create the local vector store.
    store = VectorStore()

    # Optional clean rebuild.
    if args.reset:
        logger.info("🔄 Resetting all data...")
        store.reset()
        clear_ingestion_records()
        logger.info("All data cleared.")

    # First ingest the person articles.
    logger.info("=" * 60)
    logger.info("INGESTING PEOPLE")
    logger.info("=" * 60)
    people_count = ingest_entities(PEOPLE, "person", store)

    # Then ingest the place articles.
    logger.info("=" * 60)
    logger.info("INGESTING PLACES")
    logger.info("=" * 60)
    places_count = ingest_entities(PLACES, "place", store)

    # Final run summary.
    elapsed = time.time() - start_time
    stats = get_ingestion_stats()

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"New entities ingested this run: {people_count + places_count}")
    logger.info(f"Total entities in database: {stats['total_entities']}")
    logger.info(f"  People: {stats['people']}")
    logger.info(f"  Places: {stats['places']}")
    logger.info(f"Total chunks: {stats['total_chunks']}")
    logger.info(f"Vector store count: {store.count()}")
    logger.info(f"Time elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
