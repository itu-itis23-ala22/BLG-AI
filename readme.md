# AI Web Crawler & Search Engine

A concurrent web crawler and search engine built using Python's native libraries.

## Features
- Concurrent crawling using daemon threads.
- Back pressure management via bounded queues.
- Real-time search that works while indexing is active.
- CLI interface to monitor system state.

## How to Run
1. Ensure you have Python 3 installed. No external dependencies (`pip install`) are required.
2. Run the main script: `python main.py`
3. Follow the CLI prompts to:
   - Type `index <URL> <depth>` to start crawling (e.g., `index https://example.com 2`)
   - Type `search <keyword>` to search the active index.
   - Type `status` to see queue depth and visited page counts.
   - Type `exit` to stop the system.