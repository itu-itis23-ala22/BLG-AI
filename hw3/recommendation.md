# Production Deployment Recommendation

## Current Scope

This homework system is designed for a laptop and localhost execution. It uses local Ollama models, Chroma persistence, cached Wikipedia extracts, and a CLI interface. This is appropriate for demonstrating RAG concepts, but production use would need stronger reliability, observability, and governance.

## Recommended Production Architecture

- Package the app as a Docker service with pinned Python dependencies.
- Run Ollama or another model server on dedicated CPU/GPU infrastructure.
- Replace local Chroma files with a managed or replicated vector database for backups and scaling.
- Add a web API layer with authentication, rate limiting, and request logging.
- Move ingestion into a scheduled job with source versioning and retry handling.
- Store raw documents, chunks, embeddings, and ingestion metadata in durable storage.
- Add monitoring for latency, retrieval quality, model failures, and vector store health.

## Retrieval Improvements

- Add hybrid search with BM25 plus vector retrieval.
- Rerank retrieved chunks with a local reranker model.
- Tune chunk size and overlap with evaluation queries.
- Add entity aliases, disambiguation, and better query classification.
- Track citations more explicitly by section heading and source URL.

## Generation Improvements

- Use a stronger local model when hardware allows.
- Add streaming responses for a more natural chat experience.
- Add a stricter answer validator that checks whether claims are supported by retrieved text.
- Cache frequent answers and embeddings.
- Keep conversation history, but retrieve fresh context for each factual question.

## Reliability and Safety

- Add integration tests for ingestion, retrieval filters, failure cases, and answer formatting.
- Pin model names and document the expected hardware.
- Add structured logs and clear error messages for missing Ollama models.
- Keep external API usage limited to trusted ingestion sources.
- Add a review process before updating the production knowledge base.

## Tradeoffs

The current implementation favors clarity and local reproducibility over scale. It avoids external LLM APIs and complex orchestration, which makes the assignment easy to inspect and run. For production, the main tradeoff is that local models and local vector files are simpler but less scalable and less reliable than managed infrastructure.

