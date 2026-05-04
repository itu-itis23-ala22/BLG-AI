GITHUB REPO Link: https://github.com/itu-itis23-ala22/BLG-AI/edit/main/hw3
DEMO VIDEO link:


# Local Wikipedia RAG Assistant

This project is a fully local retrieval augmented generation system for BLG483E HW3. It ingests Wikipedia pages for famous people and famous places, chunks the articles, creates local embeddings with Ollama, stores vectors in a persistent Chroma collection, retrieves relevant chunks, and answers questions with a local Ollama language model.

No external LLM API is used. Wikipedia is contacted only during ingestion to download source articles.

## Features

- Ingests 20 famous people and 20 famous places, including every minimum entity listed in the assignment.
- Uses overlapping chunks so long Wikipedia articles can be searched reliably.
- Uses `nomic-embed-text` through local Ollama for embeddings.
- Uses one Chroma vector store with metadata field `entity_type` equal to `person` or `place`.
- Classifies each query as person, place, or both, then filters retrieval when appropriate.
- Generates grounded answers with a local model such as `llama3.2:3b`.
- Provides CLI commands for ingestion, one-shot questions, interactive chat, source display, status, and reset.

## Architecture

The project uses one vector store with metadata instead of two separate stores. This keeps comparisons simple because mixed questions can search the full collection, while person-only and place-only questions still use Chroma metadata filters.

Pipeline:

1. `wiki_rag.wikipedia` fetches plain text Wikipedia extracts and caches them in `data/raw`.
2. `wiki_rag.chunking` splits each article into 220-word chunks with 45-word overlap.
3. `wiki_rag.ollama_client` calls local Ollama for embeddings and answer generation.
4. `wiki_rag.vector_store` persists chunks, metadata, and embeddings in Chroma.
5. `wiki_rag.retrieval` classifies the query and retrieves relevant chunks.
6. `wiki_rag.rag` prompts the local model to answer only from retrieved context.
7. `main.py` exposes the CLI.

## Requirements

- Python 3.10, 3.11, or 3.12. Chroma's `onnxruntime` dependency may not yet support newer Python releases.
- Ollama installed and running locally
- Local Ollama models:
  - `nomic-embed-text` for embeddings
  - `llama3.2:3b` for answer generation

## Installation

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and start Ollama, then pull the local models:

```bash
ollama serve
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

If `ollama serve` is already running, keep it open and run the other commands in a second terminal.

## Ingest Wikipedia Data

Build the local vector store:

```bash
python main.py ingest --reset
```

This downloads and caches Wikipedia pages, chunks them, embeds them locally, and stores vectors under `data/chroma`.

Check the store:

```bash
python main.py status
```

## Ask Questions

One-shot question:

```bash
python main.py ask "Who was Albert Einstein and what is he known for?" --show-sources
```

Interactive chat:

```bash
python main.py chat --show-sources
```

Chat commands:

- `:sources on` shows retrieved chunks after each answer.
- `:sources off` hides sources.
- `:clear` clears the terminal screen.
- `:reset` clears the Chroma collection.
- `:quit` exits chat.

Reset stored vectors:

```bash
python main.py reset
```

## Example Queries

People:

- Who was Albert Einstein and what is he known for?
- What did Marie Curie discover?
- Why is Nikola Tesla famous?
- Compare Lionel Messi and Cristiano Ronaldo.
- What is Frida Kahlo known for?

Places:

- Where is the Eiffel Tower located?
- Why is the Great Wall of China important?
- What is Machu Picchu?
- What was the Colosseum used for?
- Where is Mount Everest?

Mixed and failure cases:

- Which famous place is located in Turkey?
- Which person is associated with electricity?
- Compare Albert Einstein and Nikola Tesla.
- Compare the Eiffel Tower and the Statue of Liberty.
- Who is the president of Mars?
- Tell me about a random unknown person John Doe.

## Local Model Configuration

Defaults:

- Ollama host: `http://localhost:11434`
- LLM model: `llama3.2:3b`
- Embedding model: `nomic-embed-text`

Override with command-line flags:

```bash
python main.py ask "Where is Hagia Sophia?" \
  --ollama-host http://localhost:11434 \
  --llm-model mistral \
  --embed-model nomic-embed-text
```

Or environment variables:

```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_LLM_MODEL=llama3.2:3b
export OLLAMA_EMBED_MODEL=nomic-embed-text
```


## Notes and Limitations

- First ingestion can take several minutes because every chunk is embedded locally.
- Answer quality depends on the local Ollama model and retrieved context.
- The query classifier is intentionally simple and rule based, as allowed by the assignment.
- If the retrieved context is insufficient, the prompt instructs the model to answer `I don't know.`

