# Crawler (Indexer) Agent

## Role
The Crawler Agent acts as a data collector that traverses the web and transforms raw HTML into the specific "triple" format required by the search engine.

## Responsibilities
- Implementing the `index(origin, k)` method.
- Fetching pages using `urllib` and parsing links with `html.parser`.
- Managing a `visited_urls` set to prevent redundant crawls and infinite loops.
- Handling network errors and "hanged" connections using timeout mechanisms.

## Prompt Used
"You are a Web Crawling specialist. Your goal is to write an indexer that follows links from an origin URL up to depth 'k'. 
Use `urllib.request` and store each discovered page as a triple: (relevant_url, origin_url, depth). 
Maintain a set of visited URLs to avoid duplicates. 
Apply a 3-second timeout to every request to prevent 'hanged' connections from blocking the queue, and handle exceptions gracefully."