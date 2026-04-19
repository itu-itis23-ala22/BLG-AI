# Product Requirements Document (PRD)

## Overview
A single-machine web crawler and search engine designed to index web pages up to a specified depth and serve concurrent search queries. 

## Core Requirements
* **Indexing:** The `index(origin, k)` method crawls URLs starting from an origin up to `k` hops. It maintains a strictly unique `visited_urls` set to ensure no page is crawled twice.
* **Back Pressure:** The system uses a bounded queue (`maxsize=1000`). If the queue reaches capacity, the crawler threads block until space frees up, managing memory and network load in a controlled way.
* **Search:** The `search(query)` method returns a list of triples: `(relevant_url, origin_url, depth)`. Relevancy is defined as a simple case-insensitive substring match within the URL or the extracted page title.
* **Concurrency:** The system allows search to be invoked while the indexer is active, reflecting new results as they are discovered.

## Technology Stack
* Language: Python 3.10+
* Concurrency: Native `threading` module
* Data Structures: Native `queue.Queue`, `set`, and `dict`
* Networking: `urllib.request`