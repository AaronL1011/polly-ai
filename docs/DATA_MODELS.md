# Demócrata — Data Models

This document describes the domain and storage data models used by Demócrata. It complements [SPEC.md](../SPEC.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Domain Concepts

### 1.1 Political Data Types (In Scope)

| Type | Description | Example Sources |
|------|-------------|-----------------|
| **Bills** | Legislative bills (draft or enacted). | Parliament, legislative bodies. |
| **Hansard** | Parliamentary debate transcripts. | Parliament, committees. |
| **Members** | Politicians, representatives, roles. | Member registers, parliament sites. |
| **Votes / Divisions** | Voting results (for/against/abstain, by party). | Parliament, roll calls. |
| **Other documents** | Reports, white papers, press releases (as ingested). | Uploads, scrapers. |

### 1.2 Core Domain Entities (Conceptual)

- **Document:** A unit of ingested content (e.g. one bill, one Hansard sitting, one member record). Has source, type, metadata, and content (or blob reference).
- **Chunk:** A segment of a document used for RAG (embedding + retrieval). Belongs to one document; has position, text, and optional metadata.
- **Job:** An ingestion job (upload or scrape). Has ID, status, progress, optional errors, and references to produced artifacts.
- **Query / Session:** A user query (and optional session) for costing and caching; not stored long-term except in cache.

---

## 2. Ingestion Pipeline Data

### 2.1 Input

- **Upload:** File(s) from browser (e.g. PDF, HTML, CSV). Metadata may include source name, type (bill, Hansard, member, etc.), date.
- **Scrape:** Configuration (source URL or source type, options). Job produces raw data then runs through the same pipeline as uploads.

### 2.2 Processing Stages (Internal)

- **Raw input** → Cleaned/normalised text and structure.
- **Enriched metadata:** source, date, type, entities (e.g. member IDs, bill IDs).
- **Chunks:** Text segments with boundaries (e.g. by section, paragraph, or fixed size).
- **Embeddings:** One vector per chunk (dimension and model defined by config).

### 2.3 Output (Stored)

- **Blobs (S3):** Original or derived files (e.g. original PDF, cleaned JSON/text). Key structure: e.g. `{tenant?}/{job_id}/{artifact_type}/{filename}` (exact key design in implementation).
- **Vector store:** Per-chunk records: `chunk_id`, `document_id`, `vector`, metadata (source, type, date, title, etc.) for filtering and display.
- **Metadata / index:** Enough to map chunk_id → document, document → blob refs; may live in vector store metadata or a separate index (implementation-specific).

---

## 3. Storage Models

### 3.1 S3 (Blob Storage)

| Concept | Description |
|---------|-------------|
| **Bucket(s)** | One or more buckets; structure TBD (e.g. by environment, tenant). |
| **Object keys** | Hierarchical: e.g. `ingestion/{job_id}/raw/{filename}`, `ingestion/{job_id}/derived/{document_id}.json`. |
| **Content** | Raw uploads (PDF, HTML, etc.); optional derived artifacts (cleaned text, extracted metadata JSON). |
| **Metadata (object tags/attributes)** | Optional: source, type, job_id, document_id for listing and lifecycle. |

### 3.2 Vector Store

| Concept | Description |
|---------|-------------|
| **Record** | One row/item per chunk: unique ID, embedding vector, metadata. |
| **Metadata fields** | At least: document_id, source, type, date (or date range), title (or snippet). Optional: member_ids, bill_ids, etc., for filtering. |
| **Index** | Vector index for top-k similarity search; metadata used for optional filtering (e.g. by type, date). |
| **Consistency** | Same embedding model and dimension across all chunks; namespace or tenant if multi-tenant. |

### 3.3 Redis (Cache)

| Use Case | Key Pattern (Conceptual) | Value | TTL / Notes |
|----------|--------------------------|-------|-------------|
| **Query/result cache** | e.g. `rag:query:{hash(query)}` | Serialised RAGResponse or component payload | TTL to limit staleness; key from query hash (and optional user/session if needed). |
| **Embedding cache** | e.g. `embed:text:{hash(text)}` | Vector (binary or serialised) | Optional; avoid re-embedding identical text. |
| **Session / job status** | e.g. `job:status:{job_id}` | Status payload (state, progress, errors) | Short TTL or explicit invalidation when job completes. |

Cache key strategy and TTL must minimise overhead while allowing similar queries to be served from cache where feasible (see SPEC non-functional requirements). For cache tiers and scaling patterns, see [SCALING.md](SCALING.md) § 3.4.

---

## 4. RAG Service Data (Runtime)

### 4.1 Query Input

- Natural-language string.
- user_id, session_id (for costing and cache keying).

### 4.2 Retrieval

- Query → embedding → top-k search in vector store.
- Retrieved chunks → document refs → optional blob fetch from S3 if full content needed.
- Metadata on chunks used for attribution and filtering.

### 4.3 LLM and Output

- Retrieved context + query → LLM (via LangChain); output is structured (layout + components) per [SCHEMAS.md](SCHEMAS.md).
- No persistent storage of LLM output except as part of query/result cache (Redis).

---

## 5. Cost and Usage

For full monetization philosophy, pricing model, and implementation roadmap, see [COST_MODEL.md](COST_MODEL.md).

### 5.1 Pricing Model Summary

- **Free tier:** Anonymous users get 10 queries/day; registered users get 100 queries/month
- **Pay-as-you-go:** Prepaid credits (1 credit = $0.01); per-query cost based on actual API usage + 40% margin
- **Cached queries:** Free for paid users; count against limit for free tier

### 5.2 Usage Tracking Entities

#### UsageEvent

Records every billable action for auditing, analytics, and billing.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique event identifier |
| user_id | UUID / null | Null for anonymous users |
| session_id | string | Session identifier (for anonymous tracking) |
| event_type | enum | `query` or `ingestion` |
| timestamp | datetime | When the event occurred |
| cached | boolean | Whether result was served from cache |
| query_hash | string | Hash of query (for cache attribution) |
| costs | JSON | Cost breakdown (see below) |

**Costs object:**

| Field | Type | Description |
|-------|------|-------------|
| embedding_tokens | int | Tokens used for embedding |
| embedding_cost | decimal | Cost of embedding API call |
| llm_input_tokens | int | Context + query tokens to LLM |
| llm_output_tokens | int | LLM response tokens |
| llm_cost | decimal | Cost of LLM API call |
| vector_queries | int | Number of vector search queries |
| vector_cost | decimal | Cost of vector search |
| total_cost | decimal | Raw cost before margin |
| total_with_margin | decimal | Final billable amount |
| credits_charged | int | Credits deducted (0 if free tier) |

#### UserBalance

Tracks user credit balance and free tier status.

| Field | Type | Description |
|-------|------|-------------|
| user_id | UUID | User identifier |
| credits | decimal | Current credit balance |
| lifetime_credits | decimal | Total credits ever purchased |
| lifetime_usage | decimal | Total credits ever used |
| free_tier_remaining | int | Remaining free queries this period |
| free_tier_reset_at | datetime | When free tier resets |
| created_at | datetime | Record creation time |
| updated_at | datetime | Last update time |

#### CreditTransaction

Audit log for all credit movements.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Transaction identifier |
| user_id | UUID | User identifier |
| amount | decimal | Positive for credits added, negative for usage |
| type | enum | `purchase`, `usage`, `refund`, `grant`, `adjustment` |
| reference_id | string | Payment ID, UsageEvent ID, or admin note |
| balance_after | decimal | Balance after this transaction |
| timestamp | datetime | When the transaction occurred |
| metadata | JSON | Additional context (payment provider, admin, etc.) |

### 5.3 Storage Location

| Entity | Storage | Notes |
|--------|---------|-------|
| UsageEvent | PostgreSQL | Long-term persistence for auditing and analytics |
| UserBalance | PostgreSQL + Redis | PostgreSQL for durability; Redis for fast reads |
| CreditTransaction | PostgreSQL | Immutable audit log |

### 5.4 Key Queries

The schema must support:
- Get user's current balance and free tier status (fast, cached)
- List user's recent usage events (paginated)
- Sum costs by user over a time period (for analytics)
- List transactions by user (for billing history)
- Aggregate usage by query_hash (for cache analytics)

---

## 6. References

- [SPEC.md](../SPEC.md) — Scope, storage (S3, Redis, vector store), cost
- [ARCHITECTURE.md](ARCHITECTURE.md) — Data flows, ingestion and query
- [SCHEMAS.md](SCHEMAS.md) — API and RAG response schemas
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — Code layout and conventions
- [SCALING.md](SCALING.md) — Scaling patterns, cache tiers, job persistence
- [COST_MODEL.md](COST_MODEL.md) — Full pricing model, margins, and revenue projections
