# WikiRAG - Local Wikipedia RAG Assistant

WikiRAG is a small local RAG application that answers questions about famous people and places using Wikipedia articles. After the first setup and data ingestion steps, the retrieval store, chat interface, embedding model, and language model all run on the local machine.

## Project Info

- **Student:** Enis Ersan Ala
- **Student Number:** 150220084
- **GitHub Repository:** [BLG-AI / hw3](https://github.com/itu-itis23-ala22/BLG-AI/tree/main/hw3)
- **Demo Video Folder:** [HW3 Demo](https://drive.google.com/drive/folders/1DauYiSYeRHDYs3wtop5wPzfD68LHyNad?usp=drive_link)

## Architecture

```
User Question
     │
     ▼
┌─────────────┐
│  Streamlit   │  Streaming chat interface
│  Frontend    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────────────┐
│  Retriever   │────▶│  Custom Vector Store  │  Cosine similarity search
│  (classify   │     │  (NumPy + JSON)       │  with metadata-based filtering
│   + search)  │     └──────────────────────┘
└──────┬──────┘
       │ top-K chunks
       ▼
┌─────────────┐     ┌──────────────┐
│  Generator   │────▶│  Ollama       │  On-device LLM inference
│  (prompt +   │     │  llama3.2:3b  │
│   stream)    │     └──────────────┘
└─────────────┘
```

**Vector store design:** I used the assignment's Option B: one vector store with metadata instead of separate stores for people and places. This keeps mixed questions, such as "Which famous place is in Turkey?", easier to handle. When the query looks clearly like a person or place question, the `type` metadata field narrows the search.

**Why the vector store is custom:** The project specification asks us to use language-native functionality where possible instead of relying on a full library for the main work. For that reason, this implementation stores metadata in JSON and uses NumPy to compute cosine similarity. It is enough for this assignment size and avoids native dependency problems.

## Prerequisites

- **Python 3.11+**
- **Ollama** - download from [ollama.com](https://ollama.com)

## Quick Start

### 1. Install dependencies

```bash
cd aia_hw3
pip install -r requirements.txt
```

### 2. Download the required Ollama models

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Before ingestion or chat, make sure the Ollama server is active:
```bash
ollama serve
```

### 3. Load Wikipedia data

```bash
python ingest.py
```

During ingestion the script:
- downloads 20 people and 20 places from Wikipedia
- splits every article into overlapping text chunks
- embeds the chunks locally with `nomic-embed-text`
- saves the vectors and metadata under `data/vector_store/`

To delete the current local data and build the store again:
```bash
python ingest.py --reset
```

### 4. Launch the application

```bash
streamlit run app.py
```

After Streamlit starts, open `http://localhost:8501` in the browser.

## Example Queries

### People
- "Who was Albert Einstein and what is he known for?"
- "What did Marie Curie discover?"
- "Why is Nikola Tesla famous?"
- "Compare Lionel Messi and Cristiano Ronaldo"
- "What is Frida Kahlo known for?"

### Places
- "Where is the Eiffel Tower located?"
- "Why is the Great Wall of China important?"
- "What was the Colosseum used for?"
- "What is Machu Picchu?"
- "Where is Mount Everest?"

### Mixed
- "Which famous place is located in Turkey?"
- "Which person is associated with electricity?"
- "Compare Albert Einstein and Nikola Tesla"
- "Compare the Eiffel Tower and the Statue of Liberty"

### Out-of-scope questions
- "Who is the president of Mars?"
- "Tell me about John Doe"

For questions like these, the assistant should say that it does not have enough information.

## Project Structure

```
aia_hw3/
├── app.py                    # main Streamlit chat application
├── ingest.py                 # command line ingestion script
├── config.py                 # shared project settings
├── requirements.txt          # Python dependencies
├── README.md                 # setup and usage notes
├── product_prd.md            # product requirements document
├── recommendation.md         # production deployment discussion
├── project_description.txt   # assignment text
│
├── core/
│   ├── __init__.py
│   ├── wikipedia_fetcher.py  # gets article text from Wikipedia
│   ├── chunker.py            # creates overlapping article chunks
│   ├── embedder.py           # calls Ollama for local embeddings
│   ├── vector_store.py       # NumPy + JSON vector storage
│   ├── retriever.py          # query classification and retrieval
│   ├── generator.py          # Ollama answer generation
│   └── database.py           # SQLite records and chat history
│
└── data/                     # created automatically
    ├── vector_store/         # saved vectors and chunk metadata
    └── wiki_rag.db           # SQLite database file
```

## Configuration

The main parameters are collected in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `LLM_MODEL` | `llama3.2:3b` | Ollama model used for answer generation |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model used for embeddings |
| `CHUNK_SIZE` | 1500 | Characters per chunk |
| `CHUNK_OVERLAP` | 200 | Character overlap between adjacent chunks |
| `TOP_K` | 5 | Number of chunks fetched per query |

## Technical Details

### Chunking Strategy
Articles are split into character-based chunks of about 1500 characters, with 200 characters of overlap. The chunker also tries to finish chunks at sentence boundaries so the retrieved text is easier for the model to use.

### Query Classification
The query classifier is rule-based. First it checks whether a known entity name or token appears in the question. If that is not enough, it looks for person/place keywords such as "who", "born", "where", and "located". Ambiguous queries search both categories.

### Retrieval

The retriever uses a hybrid approach because pure semantic search was not reliable enough for every question.

When a named entity is present, the system first filters by that entity's metadata and then ranks matching chunks with cosine similarity. This works well for direct questions and comparisons like "Compare Messi and Ronaldo".

When no specific entity is found, the system combines keyword search and semantic search. Keyword hits are useful for facts like country names or landmark terms, while vector search still helps with broader wording. Results are merged and duplicates are removed before generation.

### Embedding
The embedding model is `nomic-embed-text`. Documents are embedded with the `search_document:` prefix during ingestion, and user questions are embedded with the `search_query:` prefix at runtime.

### Generation
The local LLM receives only the retrieved chunks plus the user question. The prompt tells it not to invent missing facts, and the Streamlit app streams the answer as tokens arrive.

## Demo Video

[HW3 Demo Video Folder](https://drive.google.com/drive/folders/1DauYiSYeRHDYs3wtop5wPzfD68LHyNad?usp=drive_link)

## Repository

[GitHub Repository](https://github.com/itu-itis23-ala22/BLG-AI/tree/main/hw3)

## License

Built for educational purposes as part of a university course assignment.
