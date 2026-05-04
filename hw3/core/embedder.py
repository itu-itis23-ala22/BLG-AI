"""
Embedding helpers that call Ollama locally.
The default model is nomic-embed-text.
"""

import requests
import logging
from config import OLLAMA_BASE_URL, EMBED_MODEL

logger = logging.getLogger(__name__)


def embed_text(text: str, model: str = EMBED_MODEL) -> list[float]:
    """
    Create an embedding for a user query.

    The `search_query:` prefix is used because nomic-embed-text separates query
    and document embedding tasks.
    """
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": model, "prompt": f"search_query: {text}"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running (ollama serve)."
        )
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}")


def embed_batch(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """
    Create document embeddings for multiple chunks.

    Each prompt uses the `search_document:` prefix expected by nomic-embed-text.
    """
    embeddings = []
    total = len(texts)

    for i, text in enumerate(texts):
        if (i + 1) % 25 == 0 or i == 0:
            logger.info(f"Embedding {i + 1}/{total}...")
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": f"search_document: {text}"},
                timeout=60,
            )
            response.raise_for_status()
            emb = response.json()["embedding"]
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
                "Make sure Ollama is running (ollama serve)."
            )
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")
        embeddings.append(emb)

    logger.info(f"Embedded {total} texts (dim={len(embeddings[0]) if embeddings else '?'})")
    return embeddings
