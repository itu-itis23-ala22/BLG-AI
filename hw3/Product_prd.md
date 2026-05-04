# Product Requirements Document
## WikiRAG - Local Wikipedia RAG Assistant

### 1. Overview

WikiRAG is a local Retrieval-Augmented Generation system for answering questions about well-known people and places. It collects Wikipedia text, retrieves the most relevant passages, and asks a local language model to answer from that context. The goal is to keep the full pipeline on the user's own machine.

### 2. Problem Statement

Many AI assistants depend on cloud services and external APIs. For this assignment, the system needs to demonstrate the same basic idea while staying local: data storage, retrieval, embeddings, and answer generation should all run on localhost. WikiRAG solves this by building a small Wikipedia knowledge base and grounding answers in retrieved article chunks.

### 3. Target Users

- Students looking up historical figures, artists, athletes, and landmarks
- Instructors who want a simple demo of a local RAG workflow
- Users who prefer not to send questions or context to a cloud API
- Developers learning the moving parts of retrieval-based AI systems

### 4. User Stories

| # | As a... | I want to... | So that... |
|---|---|---|---|
| 1 | User | Ask a question about a person | I can get a grounded short answer |
| 2 | User | Ask a question about a place | I can learn the important facts quickly |
| 3 | User | Compare two entities | I can see the main similarities and differences |
| 4 | User | Ask something outside the dataset | I am told when the answer is not available |
| 5 | User | View the retrieved sources | I can check where the answer came from |
| 6 | User | Clear or restart the chat | I can begin a new conversation cleanly |
| 7 | Admin | Add more entities later | The knowledge base can be expanded |
| 8 | Admin | Reset the local data | I can rebuild the store from scratch |

### 5. Functional Requirements

#### 5.1 Data Ingestion
- **FR-1**: Fetch Wikipedia articles for at least 20 people and 20 places
- **FR-2**: Split article text into configurable overlapping chunks
- **FR-3**: Generate embeddings locally for every chunk
- **FR-4**: Store chunk text, vectors, and metadata in a persistent local vector store
- **FR-5**: Track ingested entities so repeated runs do not duplicate them
- **FR-6**: Provide a reset mode that clears local data before re-ingesting

#### 5.2 Query Processing
- **FR-7**: Classify each question as person, place, or both
- **FR-8**: Embed the user question with the local embedding model
- **FR-9**: Retrieve the top-K useful chunks from the vector store
- **FR-10**: Use metadata filters when the query category is clear

#### 5.3 Answer Generation
- **FR-11**: Generate answers with a locally running LLM
- **FR-12**: Keep answers limited to retrieved context
- **FR-13**: Return an "I don't have enough information" style answer when context is missing
- **FR-14**: Stream generated text in the chat interface
- **FR-15**: Include a short chat history for basic multi-turn context

#### 5.4 User Interface
- **FR-16**: Provide a Streamlit chat UI
- **FR-17**: Show entity counts and vector store chunk totals
- **FR-18**: Display retrieved source passages for each answer
- **FR-19**: Show response latency for each query
- **FR-20**: Include example questions in the sidebar
- **FR-21**: Let the user clear the chat or start a new session

### 6. Non-Functional Requirements

- **NFR-1**: The system should run on localhost after setup
- **NFR-2**: Normal answers should complete within about 30 seconds on consumer hardware
- **NFR-3**: Local data should persist across app restarts
- **NFR-4**: Main components should stay separated and understandable
- **NFR-5**: Documentation should be enough to run the project from a fresh clone

### 7. Technical Architecture

#### Components
1. **Wikipedia Fetcher** - downloads article text using `wikipedia-api`
2. **Chunker** - splits articles with fixed-size windows and overlap
3. **Embedder** - creates embeddings through Ollama and `nomic-embed-text`
4. **Vector Store** - saves vectors with NumPy and metadata with JSON, using cosine similarity for search
5. **Retriever** - combines entity filters, keyword matching, and semantic search
6. **Generator** - streams answers from Ollama with `llama3.2:3b`
7. **Database** - uses SQLite for ingestion records and chat history
8. **UI** - provides the Streamlit chat screen

#### Data Flow
```
Wikipedia → Fetch → Chunk → Embed (search_document:) → Vector Store (NumPy + JSON)
                                                                ↑
User Query → Classify → Embed (search_query:) → Hybrid Search ─┘
                                                      │
                                               Top-K Chunks → LLM → Streamed Answer
```

### 8. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Vector store | Custom NumPy + JSON, single collection | Matches the assignment's language-native direction and supports metadata filtering |
| Retrieval strategy | Hybrid entity, keyword, and semantic search | Direct entity matching improves precision, while semantic search handles broader wording |
| Embedding prefixes | `search_document:` / `search_query:` | Keeps document and query embeddings aligned with `nomic-embed-text` usage |
| Chunking approach | Fixed-size chunks with overlap | Simple, predictable, and avoids losing context at chunk borders |
| Query classification | Rule-based keywords and entity matching | Transparent and enough for this controlled entity set |
| LLM model | llama3.2:3b | Good balance between local speed and answer quality |
| Embedding model | nomic-embed-text | Easy to run through Ollama and suitable for local retrieval |
| UI framework | Streamlit | Provides a quick browser chat UI with streaming support |

### 9. Success Criteria

- [ ] All 10 required people are ingested and queryable
- [ ] All 10 required places are ingested and queryable
- [ ] At least 10 additional entities (5 people, 5 places) are present in the knowledge base
- [ ] All example queries from the spec return relevant, grounded answers
- [ ] Out-of-scope queries consistently produce "I don't know" style responses
- [ ] Source passages are visible for every assistant response
- [ ] The system can be set up from scratch using only the README

### 10. Future Enhancements

- Better multi-turn memory over longer conversations
- Re-ranking after initial retrieval for stronger source selection
- More entity categories such as events, organizations, and concepts
- Query and embedding caching for repeated questions
- A model comparison screen for testing different local LLMs
