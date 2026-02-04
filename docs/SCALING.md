# Demócrata — Scaling Strategy

This document describes the scaling considerations, challenges, and phased implementation roadmap for Demócrata. It complements [ARCHITECTURE.md](ARCHITECTURE.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md).

---

## 1. Overview

Demócrata must handle variable traffic patterns, including significant bursts during election cycles, policy announcements, and major political events. The system must also support bulk ingestion of historical parliamentary data (years of bills, Hansard transcripts, voting records) while maintaining responsive query performance.

This document outlines:
- Key scaling challenges specific to political data RAG systems
- Architectural patterns to address these challenges
- A phased roadmap from MVP to high-scale production

---

## 2. Scaling Challenges

### 2.1 Long-Running Ingestion Jobs

Embedding large documents (e.g., comprehensive bills, lengthy Hansard transcripts) is CPU/API-intensive and can take minutes to hours for bulk imports.

| Challenge | Impact |
|-----------|--------|
| Synchronous processing blocks API servers | Reduced capacity for user queries during ingestion |
| No job persistence | Crashed jobs lose progress; no resume capability |
| No prioritisation | Bulk imports can starve interactive requests |

### 2.2 External API Rate Limits

LLM and embedding APIs (OpenAI, Anthropic, etc.) impose rate limits and quotas.

| Challenge | Impact |
|-----------|--------|
| Quota exhaustion | Cascading failures across all requests |
| No backpressure | Burst traffic exceeds limits without graceful degradation |
| Cost unpredictability | Uncontrolled bursts can exhaust budgets |

### 2.3 Traffic Bursts (Election Cycles)

Political events drive unpredictable traffic spikes—potentially 10–100× normal volume.

| Challenge | Impact |
|-----------|--------|
| Query volume exceeds capacity | Timeouts, failed requests |
| Cache misses on new topics | Higher LLM load for novel queries |
| Concurrent ingestion of new data | Competition for resources |

### 2.4 Vector Store Scaling

Different vector stores have different scaling characteristics:

| Vector Store | Characteristics |
|--------------|-----------------|
| **pgvector** | Simple; limited to Postgres capacity; struggles beyond ~1M vectors |
| **Pinecone** | Managed, auto-scales; cost scales with query volume |
| **Weaviate** | Horizontal scaling possible; operationally complex |
| **Qdrant** | Good horizontal scaling; requires cluster configuration |

The choice affects both capacity limits and operational complexity.

### 2.5 Cache Pressure

Redis handles multiple responsibilities: query cache, embedding cache, job status. Under high load:

| Challenge | Impact |
|-----------|--------|
| Memory exhaustion | Evictions, cache misses, increased LLM calls |
| Single instance limits | Throughput ceiling, single point of failure |

---

## 3. Scaling Patterns

### 3.1 Async Job Queue

Decouple long-running work from request handling:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ API Server  │─────►│  Job Queue  │─────►│   Workers   │
│ (enqueue)   │      │ (Redis/RMQ) │      │ (process)   │
└─────────────┘      └─────────────┘      └─────────────┘
```

- API servers accept ingestion requests, enqueue jobs, return job IDs immediately
- Dedicated worker processes consume queue and perform embedding/storage
- Workers scale independently from API servers
- Job status persisted for recovery

**Recommended tools:** Celery, Dramatiq, Arq (async), or cloud-native (AWS SQS + Lambda, Cloud Tasks)

### 3.2 Rate Limiting and Backpressure

Protect external APIs and ensure graceful degradation:

- **Token bucket / semaphore** for LLM calls with configurable concurrency
- **Circuit breaker** pattern for external API failures
- **Retry with exponential backoff** for transient failures
- **Request queue with depth limits** to shed load gracefully

### 3.3 Batch Processing

Reduce API call overhead for bulk operations:

- **Batch embedding:** Most embedding APIs accept multiple texts per request (e.g., OpenAI allows up to 2048)
- **Batch writes:** Aggregate vector store inserts into batches
- **Chunked uploads:** Process large files in streaming chunks

### 3.4 Cache Tiers

Optimise cache for different access patterns:

| Tier | Use Case | TTL |
|------|----------|-----|
| **Hot cache (Redis)** | Recent queries, active sessions | Short (minutes–hours) |
| **Warm cache (Redis/disk)** | Popular queries, common topics | Medium (hours–days) |
| **Cold storage (S3)** | Archived responses for analytics | Long-term |

### 3.5 Worker Pools and Priority Queues

Separate queues for different workload types:

| Queue | Purpose | Priority |
|-------|---------|----------|
| **query** | User-facing RAG queries | High |
| **ingestion-interactive** | Single document uploads | Medium |
| **ingestion-bulk** | Batch imports, scrapers | Low |

Workers can be allocated per queue or shared with priority weighting.

---

## 4. Implementation Roadmap

The roadmap is organised into phases. Each phase builds on the previous, delivering incremental value while progressively improving scale and resilience.

### Phase 1: MVP Foundation

**Goal:** Prove the concept with a working end-to-end system for low-to-moderate usage.

#### Scope

- **Synchronous ingestion:** Acceptable for single-document uploads and small batches
- **Direct LLM/embedding calls:** No queue, basic error handling
- **Single Redis instance:** Query cache with TTL
- **Simple vector store:** pgvector or single-node Weaviate/Qdrant
- **Stateless API servers:** Can run multiple instances behind load balancer

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Ingestion pipeline | Synchronous; clean → chunk → embed → store |
| RAG service | Direct embedding + vector search + LLM call |
| Cache | Redis query cache (hash of query → response) |
| Job status | In-memory or simple Redis key (no persistence) |
| Deployment | Single API server instance (or 2–3 for availability) |

#### Limitations Accepted

- Long ingestion jobs block API capacity
- No job recovery on failure
- Limited to moderate query volume
- No rate limiting on LLM APIs

---

### Phase 2: Async Ingestion

**Goal:** Decouple ingestion from request handling; enable bulk imports without degrading query performance.

#### Scope

- **Job queue:** Celery/Dramatiq/Arq with Redis or RabbitMQ backend
- **Dedicated workers:** Separate processes for ingestion work
- **Job persistence:** Durable job records in Postgres (not just Redis)
- **Job status API:** Query job progress, errors, completion

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Job queue | Celery with Redis broker (or Arq for async) |
| Worker pool | 1–N workers, configurable concurrency |
| Job model | Postgres table: job_id, status, progress, errors, created_at, updated_at |
| Status endpoint | `GET /jobs/{job_id}` returns current state |
| Dead-letter handling | Failed jobs logged with error details for retry/investigation |

#### New Capabilities

- Bulk ingestion (thousands of documents) without blocking queries
- Job resume after worker restart
- Visibility into ingestion progress

---

### Phase 3: Resilience and Rate Limiting

**Goal:** Protect against external API failures and traffic spikes; ensure graceful degradation.

#### Scope

- **Rate limiting:** Token bucket for LLM/embedding APIs
- **Circuit breakers:** Fail fast when external services are degraded
- **Retry policies:** Exponential backoff with jitter
- **Request queuing:** Bounded queue with load shedding

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Rate limiter | Semaphore or token bucket (e.g., `aiolimiter`, `limits`) per API |
| Circuit breaker | Library (e.g., `circuitbreaker`, `tenacity`) wrapping LLM clients |
| Retry policy | Configurable max retries, backoff multiplier, jitter |
| Queue depth | Configurable max pending requests; return 503 when exceeded |
| Metrics | Track rate limit hits, circuit breaker trips, retry counts |

#### New Capabilities

- Predictable behaviour under load
- Protection against cost overruns
- Graceful degradation instead of cascading failures

---

### Phase 4: Batch Processing and Optimisation

**Goal:** Improve throughput and reduce costs for high-volume operations.

#### Scope

- **Batch embedding:** Group texts into batches for API efficiency
- **Batch vector writes:** Aggregate inserts to vector store
- **Embedding cache:** Cache embeddings for duplicate/similar text
- **Query deduplication:** Coalesce identical concurrent queries

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Batch embedder | Accumulate texts up to API limit (e.g., 2048), embed in single call |
| Batch inserter | Buffer vector writes, flush at size/time threshold |
| Embedding cache | Redis: `embed:{hash(text)}` → vector; check before API call |
| Query coalescing | Track in-flight queries; return same future for duplicates |

#### New Capabilities

- 10–50× reduction in embedding API calls for bulk ingestion
- Lower latency for cached embeddings
- Reduced vector store write load

---

### Phase 5: High Availability and Horizontal Scale

**Goal:** Production-ready deployment capable of handling election-cycle traffic.

#### Scope

- **Redis cluster:** High availability, increased throughput
- **Vector store scaling:** Cluster mode or managed service with auto-scaling
- **Worker auto-scaling:** Scale workers based on queue depth
- **Multi-region (optional):** Geographic distribution for latency/resilience

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Redis | Cluster mode (3+ nodes) or managed service (ElastiCache, Upstash) |
| Vector store | Pinecone (managed) or Qdrant/Weaviate cluster |
| Worker scaling | Kubernetes HPA or cloud auto-scaling based on queue metrics |
| Load balancer | Health checks, connection draining, auto-scaling triggers |
| Monitoring | Dashboards for queue depth, cache hit rate, API latency, error rates |

#### New Capabilities

- Handle 10–100× traffic bursts
- No single points of failure
- Automatic scaling based on demand

---

### Phase 6: Priority Queues and Multi-Tenancy (Future)

**Goal:** Support differentiated workloads and potential multi-tenant operation.

#### Scope

- **Priority queues:** Separate queues for query vs. bulk ingestion
- **Tenant isolation:** Namespace separation in vector store and cache
- **Usage quotas:** Per-tenant rate limits and cost tracking
- **SLA tiers:** Different priority/capacity for different user tiers

#### Deliverables

| Component | Implementation |
|-----------|----------------|
| Queue routing | Priority-based worker allocation |
| Tenant context | Tenant ID in all requests; namespaced storage |
| Quota service | Track usage per tenant; enforce limits |
| Billing integration | Detailed cost attribution per tenant |

---

## 5. Decision Log

Significant architectural decisions should be recorded here as they are made.

| Date | Decision | Rationale | Phase |
|------|----------|-----------|-------|
| TBD | Vector store choice | Performance, cost, operational complexity trade-offs | 1 |
| TBD | Job queue technology | Team familiarity, async support, monitoring | 2 |
| TBD | Rate limiting strategy | API provider limits, cost constraints | 3 |

---

## 6. References

- [SPEC.md](../SPEC.md) — Mission, scope, non-functional requirements
- [ARCHITECTURE.md](ARCHITECTURE.md) — System components and data flows
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — Code structure and conventions
- [DATA_MODELS.md](DATA_MODELS.md) — Storage models (S3, Redis, vector store)
