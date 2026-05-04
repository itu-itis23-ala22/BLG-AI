# Product PRD: Local Wikipedia RAG Assistant

## Objective

Build a ChatGPT-style local assistant that answers questions about famous people and famous places using retrieved Wikipedia context. The system must run on localhost with local embeddings, local vector storage, and a local language model.

## Target Users

- Course instructor evaluating the homework.
- Student demonstrating local RAG architecture.
- Users who want quick factual answers about the ingested people and places.

## Core User Stories

- As a user, I can ingest Wikipedia pages for famous people and places.
- As a user, I can ask questions in a chat-style CLI.
- As a user, I can see which retrieved chunks were used.
- As a user, I can reset local data and rebuild the index.
- As a user, I can run a local readiness check before recording the demo.
- As an evaluator, I can run the system by following only the README.

## Functional Requirements

- Ingest at least 20 people and 20 places from Wikipedia.
- Include all assignment-required entities.
- Split source documents into chunks with overlap.
- Generate embeddings locally.
- Store vectors locally in a persistent vector database.
- Determine whether a query concerns a person, place, or both.
- Retrieve from the correct metadata scope.
- Generate answers using a local LLM.
- Return `I don't know.` when retrieved context is insufficient.
- Provide a CLI for one-shot questions and interactive chat.
- Provide a `doctor` command that checks Ollama model availability and vector store status.

## Non-Functional Requirements

- No external LLM APIs.
- Localhost runnable.
- Clear setup and run instructions.
- Simple, readable Python implementation.
- Persistent data between runs.
- Easy reset for repeatable demos.

## Technical Design

The system uses Python, Ollama, and Chroma.

- Data source: Wikipedia MediaWiki API during ingestion.
- Embedding model: `nomic-embed-text` through local Ollama.
- Generation model: `llama3.2:3b` through local Ollama.
- Vector store: one persistent Chroma collection.
- Metadata: each chunk includes title, entity type, source URL, and chunk index.
- Retrieval: rule-based query classification plus Chroma similarity search.
- Interface: CLI commands in `main.py`.

## Vector Store Choice

The implementation uses Option B from the assignment: one vector store with metadata. This design avoids duplicating retrieval logic and supports comparison questions across people and places. Metadata filtering still gives precise person-only or place-only retrieval.

## Success Criteria

- `python main.py ingest --reset` builds the index.
- `python main.py ask "What did Marie Curie discover?" --show-sources` returns a grounded answer and sources.
- `python main.py doctor` reports the required local Ollama models and whether the vector store has data.
- Person questions retrieve person chunks.
- Place questions retrieve place chunks.
- Mixed comparison questions can retrieve both types.
- Failure questions are constrained by the prompt to answer `I don't know.`

## Demo Plan

1. Show the repository layout and README.
2. Start Ollama and verify the local models.
3. Run ingestion with reset.
4. Ask one people question, one places question, one comparison question, and one failure case.
5. Show retrieved sources.
6. Explain metadata filtering, local models, tradeoffs, and future improvements.

