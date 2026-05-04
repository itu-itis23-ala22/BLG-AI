# Production Deployment Notes
## WikiRAG - Local Wikipedia RAG Assistant

**Student:** Enis Ersan Ala  
**Student Number:** 150220084  
**Repository:** [BLG-AI / hw3](https://github.com/itu-itis23-ala22/BLG-AI/tree/main/hw3)  
**Demo:** [HW3 Demo Video Folder](https://drive.google.com/drive/folders/1DauYiSYeRHDYs3wtop5wPzfD68LHyNad?usp=drive_link)

This document describes how the current local demo could be prepared for a real production environment. The project is intentionally small right now, so the recommendations below focus on the areas that would matter first: packaging, serving, storage, monitoring, and security.

---

## 1. Containerization

### Current State
The current version runs as Python scripts and uses local files for persistence: JSON/NumPy files for the vector store and SQLite for ingestion records and chat history.

### Recommendation
Package the app and Ollama with Docker Compose so the environment is easier to reproduce:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  app:
    build: .
    ports:
      - "8501:8501"
    depends_on:
      - ollama
    volumes:
      - ./data:/app/data
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
```

This would make setup more consistent between machines, allow GPU passthrough when available, and create a cleaner path toward Kubernetes later.

---

## 2. Vector Database Upgrade

### Current State
A custom NumPy and JSON vector store is enough for about 40 entities and a few thousand chunks. It is simple, portable, and fits the assignment, but it is not meant for large-scale indexing.

### Recommendation
For larger datasets, the vector layer should be replaced gradually:

| Scale | Recommendation | Notes |
|---|---|---|
| Small (< 10K chunks) | Custom NumPy store (current) or ChromaDB | Sufficient, minimal operational overhead |
| Medium (10K–1M chunks) | **Qdrant** or **Weaviate** | Client-server mode, better indexing options |
| Large (> 1M chunks) | **Pinecone** or **Milvus** | Managed or distributed, horizontal scale-out |

Qdrant would be the most natural first migration because it supports cosine similarity, runs easily in Docker, and provides production-ready approximate nearest neighbor indexing.

---

## 3. Model Serving

### Current State
Ollama is practical for a single local user and keeps setup simple.

### Recommendation
For many users, model serving should move to an inference server designed for concurrency:

- **vLLM** or **TGI (Text Generation Inference)** for higher throughput
  - supports batching, quantization, and continuous batching
  - handles concurrent load better than the current local setup
- **GPU requirements:** Minimum NVIDIA T4 (16 GB) for llama3.2:3b; A10G for larger models
- Consider upgrading the model for better quality:
  - `llama3.1:8b` - stronger reasoning, still possible on many GPUs
  - `mistral:7b` - good instruction-following behavior
  - `phi3:14b` - higher quality if a larger GPU is available

---

## 4. Caching Layer

### Recommendation
Add Redis caching in three places:

1. **Embedding cache** - avoid recalculating repeated query embeddings
2. **Response cache** - reuse exact query answers for a limited time
3. **Semantic cache** - reuse answers for near-duplicate questions when similarity is high enough

For repeated workloads, this could remove many unnecessary Ollama calls and lower latency.

---

## 5. API Layer

### Current State
Streamlit currently owns both the interface and most backend orchestration. This is fine for a demo, but it becomes limiting for multiple clients.

### Recommendation
Introduce a FastAPI backend between the frontend and the RAG pipeline:

```
Frontend (Streamlit/React) ──▶ FastAPI ──▶ Retriever + Generator
                                  │
                                  ▼
                            Redis Cache
```

Useful endpoints would include:
- `POST /api/query` for streamed answers
- `POST /api/ingest` for adding entities
- `GET /api/stats` for system counts
- `GET /api/health` for monitoring

This separation would make it easier to support different clients, scale the API separately from the UI, and add rate limiting or authentication.

---

## 6. Observability

### Recommendation
Production should include monitoring for the main parts of the RAG pipeline:

| Component | Tool | Purpose |
|---|---|---|
| Metrics | Prometheus + Grafana | Latency, throughput, and error rates |
| Logging | ELK Stack or Loki | Centralized log aggregation and search |
| Tracing | LangSmith or Jaeger | End-to-end RAG pipeline tracing (retrieval quality, LLM latency) |

Important metrics to collect:
- Query-to-answer latency (p50, p95, p99)
- Retrieval score distribution
- LLM token throughput (tokens/second)
- Cache hit rates
- Per-component error rates

---

## 7. Security

### Production Security Checklist

- [ ] **Authentication** - protect the API with OAuth2 or JWT
- [ ] **Rate limiting** - prevent a single user from overloading the service
- [ ] **Input validation** - reduce prompt injection and malformed input risk
- [ ] **HTTPS** - terminate TLS at Nginx or a cloud load balancer
- [ ] **Data encryption** - encrypt stored vectors, metadata, and chat records
- [ ] **Network isolation** - keep model-serving endpoints private
- [ ] **Audit logging** - record important requests and failures for investigation

---

## 8. Scaling Strategy

### Horizontal Scaling

```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌─────────┐ ┌─────────┐ ┌─────────┐
         │ App Pod 1│ │ App Pod 2│ │ App Pod 3│
         └────┬────┘ └────┬────┘ └────┬────┘
              │            │            │
              ▼            ▼            ▼
         ┌─────────────────────────────────┐
         │    Shared Vector DB (Qdrant)     │
         └─────────────────────────────────┘
              │
              ▼
         ┌─────────────────────────────────┐
         │    GPU Pool (vLLM instances)     │
         └─────────────────────────────────┘
```

- **Kubernetes** can run multiple app replicas and scale them based on traffic
- **Dedicated GPU workers** should handle LLM inference separately from the web tier
- **Shared vector storage** should be available to every app instance

---

## 9. Data Pipeline

### Recommendation
For production-grade ingestion:

- **Scheduled ingestion** - refresh Wikipedia content on a weekly or monthly schedule
- **Incremental updates** - re-ingest only articles that changed
- **Data validation** - check chunk length and content before inserting
- **Backups** - snapshot vector data, metadata, and relational records regularly

---

## 10. Cost Estimates (Cloud Deployment)

| Component | Instance Type | Monthly Cost |
|---|---|---|
| App servers (3×) | AWS t3.medium | ~$90 |
| GPU (LLM serving) | AWS g4dn.xlarge (T4) | ~$380 |
| Vector DB | Qdrant Cloud (1M vectors) | ~$50 |
| Redis Cache | AWS ElastiCache t3.micro | ~$15 |
| Total | | **~$535/month** |

These numbers are only rough estimates and use US East pricing assumptions from 2024.

---

## Summary

The current architecture is appropriate for a local course project. A production version should improve five areas first:

1. **Containerization** with Docker Compose and later Kubernetes
2. **API separation** with FastAPI
3. **Caching** with Redis
4. **Vector database migration** to Qdrant or a similar service
5. **Model serving** with vLLM or TGI

These changes can be introduced step by step without throwing away the main RAG pipeline.
