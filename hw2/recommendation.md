# Recommendations for Production Deployment

## Summary

The current implementation is a well-structured single-machine crawler that can comfortably index tens of thousands of pages per hour on commodity hardware.  Moving it to production requires three categories of work: **infrastructure hardening**, **horizontal scale-out**, and **operational excellence**.

---

## 1  Storage

Replace SQLite with durable, horizontally-scalable stores:

| Data | Recommended Store | Rationale |
|---|---|---|
| Crawl job state & logs | PostgreSQL (or DynamoDB) | ACID transactions, easy replication, supports many concurrent writers |
| Visited-URL dedup | Redis `SET` or Bloom filter (e.g., RedisBloom) | O(1) membership test at scale; millions of entries fit in RAM |
| Page content / FTS index | Elasticsearch or OpenSearch | Distributed full-text search, BM25 ranking, near-real-time indexing, horizontal sharding |
| Overflow / pending queue | Apache Kafka or AWS SQS | Durable, replayable message queue; decouples crawl workers from discovery |

A `visited_urls` Bloom filter (false-positive rate ~0.1 %) is strongly preferred at production scale – it fits billions of URLs in a few hundred MB of Redis memory versus gigabytes for an exact set.

---

## 2  Horizontal Scale-Out

**Crawl workers**  
Deploy worker processes as stateless containers (Docker / Kubernetes Pods).  Each worker subscribes to the URL queue (Kafka/SQS), fetches a page, and publishes discovered links back to the queue.  Autoscale horizontally based on queue depth – the same back-pressure signal the current code already tracks.

**Search API**  
Run behind a load balancer with multiple read replicas of the Elasticsearch cluster.  The crawler writes to Elasticsearch with `refresh=wait_for` (or asynchronously with a small lag); search nodes are always read-only.  This separation means a crawler surge never degrades search latency.

**Coordinator / scheduler**  
A lightweight scheduler service manages job creation, depth tracking, and dedup lookups against Redis. Workers are stateless – they receive `(url, depth, job_id)` tuples and return `(discovered_links, page_content)` results.

---

## 3  Operational Excellence

- **Observability**: Export Prometheus metrics (pages/s, queue depth, error rate, p95 fetch latency) and build Grafana dashboards. Set alerts on queue saturation and error-rate spikes.
- **Politeness**: Honour `robots.txt` (use `urllib.robotparser`). Add per-domain rate limiting (e.g., max 1 req/s to the same host). Implement exponential back-off on 429/503 responses.
- **Fault tolerance**: Workers should ack a queue message only after successful persistence, so a crash causes at-least-once re-delivery rather than data loss.
- **Security**: Store API credentials in a secrets manager (AWS Secrets Manager, Vault). Run workers in a network segment with egress filtering. Sanitise all URLs before fetching (SSRF prevention).
- **Compliance**: Respect `noindex` / `nofollow` meta tags. Implement a re-crawl TTL so stale pages are refreshed rather than cached indefinitely. Store crawl timestamps to support right-to-erasure requests.
- **CI/CD**: Dockerise the application. Add integration tests that crawl a local HTTP server (e.g., `http.server`) and assert expected index/search behaviour. Gate production deployments on these tests.

---

## Timeline Estimate (rough)

| Phase | Effort |
|---|---|
| Swap SQLite → PostgreSQL + Redis dedup | 1–2 days |
| Add Kafka/SQS queue integration | 1–2 days |
| Containerise + Kubernetes manifests | 1 day |
| Elasticsearch integration + search API update | 2–3 days |
| Observability (Prometheus + Grafana) | 1 day |
| Politeness, SSRF protection, compliance | 1–2 days |
| **Total** | **~2 weeks for a production-grade v1** |
