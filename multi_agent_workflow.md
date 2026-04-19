# Multi-Agent Workflow

## Agent Roles and Responsibilities
To design this concurrent web crawler, I established a multi-agent workflow focusing on dividing architectural concerns from specific implementation details.

1. **The Architect Agent:** Responsible for the overall system design. This agent decided to use Python's native `threading` and `queue.Queue` modules to implement the shared state, ensuring the system runs on a single machine while supporting concurrent reads and writes.
2. **The Crawler (Indexer) Agent:** Tasked with building the `index(origin, k)` method. This agent utilized `urllib` and `html.parser` to traverse links up to depth `k` without visiting the same page twice. 
3. **The Search Agent:** Tasked with the `search(query)` method, ensuring it could read from the shared index while the Crawler Agent was actively writing to it.
4. **The UI/CLI Agent:** Built the interactive command-line interface to monitor queue depths and system status.

## Interactions and Decisions
The Architect established the ground rules: all agents must avoid heavy external libraries (like Scrapy or Celery) and use native language features. 
The core interaction challenge was concurrency. Because search and indexing run concurrently, we had to prevent race conditions when accessing the shared index dictionary, relying on fundamental system-level logic like mutex locks to separate read/write access. 
Furthermore, the Crawler Agent implemented a strict URL tracking system. If a server takes too long to respond, the request is caught by a timeout exception so that a "hanged" request or "failed" connection doesn't block the entire queue. Back pressure was naturally managed by setting a `maxsize` on the threading queue.