# Search Agent

## Role
The Search Agent is responsible for querying the indexed data and returning relevant results to the user in the correct format.

## Responsibilities
- Designing the `search(query)` method.
- Ensuring thread-safe access to the shared index while the crawler is active.
- Implementing case-insensitive substring matching for relevancy.

## Prompt Used
"You are a Search Engine Optimization agent. Your task is to query the `search_index` list populated by the Crawler. 
The search method must find all URLs containing the query string and return them as triples. 
Since crawling and searching happen concurrently, use `threading.Lock` to protect the shared data. 
Focus on a simple yet efficient substring matching algorithm."