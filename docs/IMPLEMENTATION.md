# Demócrata — Implementation Details

This document outlines implementation conventions, code layout, and technical details for Demócrata. It expands on [SPEC.md](../SPEC.md) Section 6 (Architecture principles) and aligns with the monorepo structure.

---

## 1. Repository and Layout

### 1.1 Monorepo

- **Root:** Monorepo root; shared tooling (e.g. Makefile, pnpm workspace).
- **frontend/** — Svelte app; gRPC-Web client; consumes RAG and (optionally) ingestion APIs.
- **server/** — Python API server (FastAPI, gRPC); Ingestion Pipeline; RAG Service.
- **docs/** — Supporting documentation (this folder).

### 1.2 Domain-Centred Structure (Server)

The server follows **domain-centred** structure with **inversion of dependencies**:

- **Domain core** has no FastAPI, gRPC, or infrastructure imports. It defines use cases, entities, and interfaces (ports).
- **Adapters** depend on the domain: HTTP/gRPC handlers, S3 client, Redis client, vector store client, LLM/embedding clients. They implement ports defined by the domain.

Recommended layout under `server/src/democrata_server/`:

```
democrata_server/
├── __init__.py
├── main.py                 # FastAPI app, gRPC registration (adapters)
├── api/                    # HTTP/gRPC adapters (depend on domain)
│   ├── http/
│   │   └── routes/
│   ├── grpc/
│   └── ...
├── domain/                 # Core domain (no FastAPI/gRPC/infra imports)
│   ├── ingestion/
│   │   ├── ports.py        # Interfaces for storage, embedding
│   │   ├── use_cases.py
│   │   └── entities.py
│   ├── rag/
│   │   ├── ports.py
│   │   ├── use_cases.py
│   │   └── entities.py
│   ├── usage/              # Cost tracking and billing
│   │   ├── ports.py        # Interfaces for balance store, payment
│   │   ├── use_cases.py    # Check balance, record usage, purchase
│   │   └── entities.py     # UsageEvent, UserBalance, CreditTransaction
│   └── ...
├── adapters/               # Infrastructure and external services
│   ├── storage/
│   │   ├── s3.py
│   │   └── vector_store.py
│   ├── cache/
│   │   └── redis.py
│   └── llm/
│       └── langchain_client.py
└── proto/                  # Generated and/or hand-written proto stubs (optional under server)
    └── ...
```

- **Domain** modules contain business logic and define **ports** (abstract interfaces).
- **Adapters** implement those ports (e.g. `VectorStorePort` implemented by `VectorStoreAdapter` using the real vector DB).
- **API** layer (FastAPI routes, gRPC servicers) calls domain use cases and maps DTOs to/from proto or JSON.

### 1.3 Proto and Generated Code

- **Proto files:** Recommended under `server/proto/` or a shared `proto/` at repo root (see [SCHEMAS.md](SCHEMAS.md)).
- **Generated code:** Python (grpcio-tools) and TypeScript/JavaScript (e.g. grpc-web) generated from `.proto`; generated files can live in `server/src/.../gen/` and `frontend/src/gen/` or similar, and be excluded from hand-editing.

---

## 2. Tech Stack (Implementation)

| Layer | Technology | Notes |
|-------|------------|-------|
| Server | Python, FastAPI, gRPC (grpcio) | Async where beneficial; workers stateless. |
| Frontend | Svelte, gRPC-Web | Typed client from proto. |
| Agent / LLM | LangChain | Used inside RAG service for agent/LLM and tools. |
| Blob storage | S3 | AWS S3 or S3-compatible API. |
| Cache | Redis | Query/result cache; optional embedding/session cache. |
| Vector store | TBD | e.g. Pinecone, Weaviate, pgvector, or dedicated vector DB; interface behind a port. |

---

## 3. Key Conventions

### 3.1 Statelessness

- No in-process state required for correctness. Session or user context (for costing/caching) in Redis or derived from auth tokens.
- Shared config (S3 bucket, Redis URL, vector store config, LLM API keys) via environment or config service; same across instances.
- See [SCALING.md](SCALING.md) for phased roadmap from MVP (synchronous processing) to production-scale (async queues, rate limiting, clustering).

### 3.2 Cost and Caching

For full pricing model and monetization strategy, see [COST_MODEL.md](COST_MODEL.md).

- **LLM token cost:** Tracked per request; forwarded to user plus 40% margin.
- **Cache:** Similar queries served from cache where feasible. Cache design: stable key from query (and optional user/session), TTL to limit staleness, key strategy to avoid excessive overhead (see [DATA_MODELS.md](DATA_MODELS.md) Redis section).
- **Free tier:** Anonymous users get 10 queries/day; registered users get 100 queries/month (enforced via UserBalance in Redis/PostgreSQL).
- **Paid tier:** Prepaid credits (1 credit = $0.01); credits deducted per query based on actual API usage.

#### Cost Tracking Implementation

**Middleware approach:** Wrap LLM and embedding calls to capture token counts:

```python
# Pseudocode for cost tracking middleware
class CostTracker:
    def __init__(self):
        self.embedding_tokens = 0
        self.llm_input_tokens = 0
        self.llm_output_tokens = 0
    
    def track_embedding(self, text: str, tokens: int):
        self.embedding_tokens += tokens
    
    def track_llm(self, input_tokens: int, output_tokens: int):
        self.llm_input_tokens += input_tokens
        self.llm_output_tokens += output_tokens
    
    def calculate_cost(self, config: CostConfig) -> CostBreakdown:
        # Apply rates and margin from config
        ...
```

**Token counting:**
- Use `tiktoken` (for OpenAI models) or provider-specific tokenizers
- Count tokens before API calls for estimation; use response metadata for actual counts
- LangChain callbacks can intercept token usage from LLM responses

**Cache hit attribution:**
- Check cache before LLM call; if hit, skip cost tracking (query is free for paid users)
- For free tier, cached responses still count against daily/monthly limit

**Balance enforcement:**
- Before executing query, check UserBalance in Redis (fast path)
- If free tier exhausted and insufficient credits, return 402 Payment Required
- After query, atomically decrement balance and log UsageEvent

**Cost configuration:**
- Store API rates (per 1K tokens) and margin in config/environment
- Update without redeploy when provider prices change

### 3.3 Non-Partisanship

- Content and UI framing must remain strictly neutral. No advocacy or partisan framing in explanations, summaries, or layout choices.
- **Non-partisan ≠ false balance.** Present facts accurately even when asymmetric. If one party voted 90% for and another 10%, say so—do not artificially frame this as "mixed."
- **Non-partisan = no advocacy.** Do not tell users what to think or how to vote. Present information; let users draw conclusions.
- **Transparency:** Always cite sources and show methodology so users can evaluate the presentation.
- Implemented via: prompt design (LLM instructions emphasising factual accuracy over balance), content guidelines, source attribution, and frontend presentation rules (clarity and neutrality as first-order requirements).

### 3.4 Code Quality

- **Modular, loosely coupled:** Clear boundaries between ingestion, RAG, and API.
- **KISS and YAGNI:** Avoid speculative features; implement what the SPEC requires.
- **Testing:** Domain logic unit-tested; adapters tested with mocks or test containers; API tests for critical paths.

---

## 4. Ingestion Pipeline (Implementation Notes)

- **Input validation:** Validate file type and size at API layer; pass validated payload to domain.
- **Chunking:** Strategy configurable (e.g. by section, paragraph, or fixed token/size); same strategy used for embedding and retrieval.
- **Embedding:** One model, one dimension; configurable via env/config. Optional caching of embeddings (e.g. Redis) for identical text.
- **Idempotency:** Job IDs and document IDs allow idempotent retries; overwrite or skip based on policy (e.g. same job_id + document_id).
- **Async processing:** MVP uses synchronous ingestion; later phases introduce job queues and dedicated workers (see [SCALING.md](SCALING.md) Phase 2).

---

## 5. RAG Service (Implementation Notes)

- **LangChain:** Used for orchestration: embed query, run top-k retrieval (tool or custom step), build context, call LLM, parse/validate structured output (layout + components).
- **Structured output:** LLM output mapped to proto-defined types (RAGResponse, Layout, components); validation before returning to client.
- **Caching:** Before calling LLM, check Redis for cached result by query key; store result in cache after successful response (with TTL).

---

## 6. Frontend (Implementation Notes)

- **gRPC-Web:** Client generated from same protos as server; calls RAG query (and ingestion if needed).
- **Rendering:** Layout and component types from [SCHEMAS.md](SCHEMAS.md); each component type has a Svelte (or shared) component: e.g. `TextBlock.svelte`, `Chart.svelte`, `Timeline.svelte`, `DataTable.svelte`, `Notice.svelte`, `MemberProfiles.svelte`, `VotingBreakdowns.svelte`.
- **Accessibility and clarity:** First-order requirements; neutral presentation (no partisan advocacy, but accurate presentation of asymmetric facts).

---

## 7. Configuration and Environment

- **Server:** Environment variables or config file for: S3 bucket/region, Redis URL, vector store connection, LLM/embedding API keys, cache TTLs, profit margin / cost config.
- **Frontend:** API base URL (gRPC-Web endpoint) via env or build-time config.

Exact variable names and defaults to be defined when implementing each adapter.

---

## 8. References

- [SPEC.md](../SPEC.md) — Mission, scope, tech stack, architecture principles
- [ARCHITECTURE.md](ARCHITECTURE.md) — Components and data flows
- [SCHEMAS.md](SCHEMAS.md) — API and RAG response schemas
- [DATA_MODELS.md](DATA_MODELS.md) — Domain and storage models
- [SCALING.md](SCALING.md) — Scaling patterns and phased implementation roadmap
- [COST_MODEL.md](COST_MODEL.md) — Pricing model, margins, and revenue projections
