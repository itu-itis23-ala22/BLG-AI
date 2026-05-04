"""
Wikipedia article fetching utilities.
The wikipedia-api package is used only to retrieve clean article text.
"""

import wikipediaapi
import logging
from config import MAX_ARTICLE_LENGTH

logger = logging.getLogger(__name__)


def create_wiki_client() -> wikipediaapi.Wikipedia:
    """Create the Wikipedia client with the required user agent."""
    return wikipediaapi.Wikipedia(
        user_agent="WikiRAGAssistant/1.0 (university project)",
        language="en",
        extract_format=wikipediaapi.ExtractFormat.WIKI,
    )


def fetch_article(wiki: wikipediaapi.Wikipedia, title: str) -> dict | None:
    """
    Fetch one Wikipedia article by title.

    Returns:
        A dict with title, text, and url, or None when the page is unusable.
    """
    page = wiki.page(title)

    if not page.exists():
        logger.warning(f"Page not found: '{title}'")
        return None

    text = page.text
    if not text or len(text.strip()) < 100:
        logger.warning(f"Page too short or empty: '{title}'")
        return None

    # Keep the opening and early sections so article size stays manageable.
    if len(text) > MAX_ARTICLE_LENGTH:
        text = text[:MAX_ARTICLE_LENGTH]
        # Prefer ending on a sentence boundary after truncation.
        last_period = text.rfind(".")
        if last_period > MAX_ARTICLE_LENGTH * 0.8:
            text = text[: last_period + 1]

    logger.info(f"Fetched '{page.title}' — {len(text):,} chars")
    return {
        "title": page.title,
        "text": text,
        "url": page.fullurl,
    }


def fetch_all(
    titles: list[str], entity_type: str
) -> list[dict]:
    """
    Fetch a list of Wikipedia articles and attach the entity type.

    Args:
        titles: Article titles to fetch.
        entity_type: "person" or "place", stored as metadata.

    Returns:
        Article dictionaries with title, text, url, and type.
    """
    wiki = create_wiki_client()
    results = []

    for title in titles:
        article = fetch_article(wiki, title)
        if article:
            article["type"] = entity_type
            results.append(article)
        else:
            logger.error(f"FAILED to fetch '{title}' — skipping")

    logger.info(
        f"Fetched {len(results)}/{len(titles)} {entity_type} articles"
    )
    return results
