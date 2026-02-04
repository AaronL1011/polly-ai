# Demócrata — Schemas and API Contracts

This document outlines the API contracts and structured response schemas for Demócrata. Full field-level definitions will live in protobuf (`.proto`) files; this document serves as the schema reference and design guide.

**Reference:** [SPEC.md](../SPEC.md) Section 7 (Key interfaces).

---

## 1. Transport and RPC

- **Frontend ↔ Server:** gRPC-Web over HTTP/1.1 or HTTP/2.
- **Scraper / Jobs ↔ Server:** gRPC or REST (e.g. FastAPI) for ingestion triggers and status.
- **Contract:** All RPCs and message types are defined in `.proto` files; the server implements gRPC and may expose REST where needed.

---

## 2. Ingestion Service (gRPC)

### 2.1 Purpose

- Trigger uploads (browser-initiated or job-initiated).
- Trigger scraping jobs.
- Report job/upload status.

### 2.2 RPCs (Summary)

| RPC | Request | Response | Description |
|-----|---------|----------|-------------|
| `Upload` | Upload request (e.g. file ref, metadata) | Upload result (job_id, status) | Submit a file for ingestion. |
| `GetUploadStatus` | job_id | Upload status (state, progress, errors) | Poll status of an upload/job. |
| `TriggerScrape` | Scrape config (source, options) | Scrape result (job_id, status) | Start an automated scrape job. |
| `GetScrapeStatus` | job_id | Scrape status (state, progress, errors) | Poll status of a scrape job. |

Exact method names and request/response types are defined in the `.proto` files (e.g. `ingestion.proto`).

### 2.3 Message Types (Conceptual)

- **UploadRequest:** Identifier or reference to uploaded file; optional metadata (source, type).
- **UploadResult / JobResult:** `job_id`, initial `status` (e.g. PENDING, ACCEPTED).
- **StatusResponse:** `state` (PENDING, RUNNING, SUCCESS, FAILED), optional `progress`, optional `error_message`, optional `artifact_refs`.

---

## 3. RAG Query Service (gRPC)

### 3.1 Purpose

- Accept a natural-language query.
- Optionally accept user/session identifiers for costing and caching.
- Return a strongly typed structure describing the UI: **layout** and **components**.

### 3.2 RPCs (Summary)

| RPC | Request | Response | Description |
|-----|---------|----------|-------------|
| `Query` | Natural-language query, optional user/session | RAGResponse (layout + components) | Run RAG and return structured insight/analysis. |

### 3.3 Main Message Types

- **RAGQueryRequest:** `query` (string), optional `user_id`, optional `session_id`.
- **RAGResponse:** Top-level response; contains `Layout` and repeated **components** (one of the component types below).

### 3.4 Layout

- **Layout:** Describes how components are arranged (e.g. sections, order, grouping).
- Fields (conceptual): `sections` (ordered list of section descriptors), optional `title`, optional `subtitle`. Each section may reference component IDs or define inline ordering.

Full field-level definitions live in the protobuf schema (e.g. `rag.proto`).

---

## 4. Component Types (RAG Response)

The RAG service outputs, and the frontend must support, at least the following component types. Each component is a oneof (or equivalent) in the proto schema.

| Component Type | Description | Typical Use |
|----------------|-------------|-------------|
| **text_block** | Rich or plain text (summary, explanation, paragraph). | Explanations, summaries, narrative. |
| **chart** | Data visualization (e.g. bar, line, pie). | Trends, proportions, comparisons. |
| **timeline** | Ordered events or milestones. | Legislative or political timelines. |
| **comparison** | Side-by-side or structured comparison. | Bill versions, party positions, before/after. |
| **data_table** | Tabular data with headers and rows. | Votes, members, statistics. |
| **notice** / **alert** | Notice or alert (informational, warning, neutral). | Caveats, data quality, disclaimers. |
| **member_profiles** | One or more member profile cards. | MPs, representatives, roles. |
| **voting_breakdowns** | Voting results (for/against/abstain, by party, etc.). | Division results, roll calls. |

### 4.1 Component Schema Conventions (Conceptual)

- Each component has a **type** discriminator and **id** (for layout reference).
- Common optional fields: `title`, `caption`, `source_ref` (attribution).
- Component-specific payloads:
  - **text_block:** `content` (string), optional `format` (plain/markdown).
  - **chart:** `chart_type`, `series` / `data`, optional `labels`, `options`.
  - **timeline:** `events` (list of { date, label, description }).
  - **comparison:** `items` (list of comparable entities with attributes).
  - **data_table:** `headers`, `rows`, optional `pagination`.
  - **notice/alert:** `level` (info, warning), `message`, optional `title`.
  - **member_profiles:** List of profile objects (name, role, party, constituency, optional bio/photo ref).
  - **voting_breakdowns:** Division identifier, totals (for/against/abstain), optional breakdown by party or member.

Full field-level definitions live in the protobuf/schema definitions (e.g. `components.proto` or inline in `rag.proto`).

---

## 5. Proto File Layout (Recommended)

- **`api/ingestion.proto`** — Ingestion service and upload/scrape messages.
- **`api/rag.proto`** — RAG query service, `RAGQueryRequest`, `RAGResponse`, `Layout`.
- **`api/components.proto`** — All RAG component types (or embed in `rag.proto`).
- **`api/usage.proto`** — Usage and billing service, `CostEstimate`, `UserBalance`, `CreditPurchase`.

Shared types (e.g. common status enums, pagination) can live in a **`api/common.proto`**.

---

## 6. Usage and Billing Service (gRPC)

### 6.1 Purpose

- Query user balance and usage statistics.
- Estimate query cost before execution.
- Purchase credits.
- List usage history and transactions.

### 6.2 RPCs (Summary)

| RPC | Request | Response | Description |
|-----|---------|----------|-------------|
| `GetBalance` | user_id | UserBalance | Get current credit balance and free tier status. |
| `EstimateQueryCost` | query text | CostEstimate | Estimate cost before executing a query. |
| `PurchaseCredits` | user_id, amount, payment_token | PurchaseResult | Add credits via payment. |
| `GetUsageHistory` | user_id, pagination | UsageEvents list | List recent usage events. |
| `GetTransactions` | user_id, pagination | Transactions list | List credit transactions. |

### 6.3 Message Types

#### CostEstimate

Returned before or alongside query execution to show estimated/actual cost.

| Field | Type | Description |
|-------|------|-------------|
| estimated_credits | int | Estimated credits for this query |
| breakdown | CostBreakdown | Itemized cost components |
| cached | boolean | Whether result would be served from cache |
| free_tier_available | boolean | Whether free tier covers this query |

#### CostBreakdown

Itemized cost components for transparency.

| Field | Type | Description |
|-------|------|-------------|
| embedding_tokens | int | Tokens for query embedding |
| embedding_cost_cents | int | Cost in cents (before margin) |
| llm_input_tokens | int | Context tokens to LLM |
| llm_output_tokens | int | Response tokens from LLM |
| llm_cost_cents | int | LLM cost in cents (before margin) |
| margin_cents | int | Margin added |
| total_cents | int | Total cost in cents |
| total_credits | int | Total in credits (1 credit = 1 cent) |

#### UserBalance

Current balance and free tier status.

| Field | Type | Description |
|-------|------|-------------|
| user_id | string | User identifier |
| credits | int | Current credit balance |
| free_tier_remaining | int | Free queries remaining this period |
| free_tier_reset_at | timestamp | When free tier resets |

#### CreditPurchase

Request to purchase credits.

| Field | Type | Description |
|-------|------|-------------|
| user_id | string | User identifier |
| credits | int | Credits to purchase (500, 1000, 2000) |
| payment_method_token | string | Payment provider token (e.g., Stripe) |

#### PurchaseResult

Result of credit purchase.

| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Whether purchase succeeded |
| transaction_id | string | Transaction identifier |
| new_balance | int | Updated credit balance |
| error_message | string | Error details if failed |

### 6.4 RAG Query Response Extension

The `RAGResponse` message should include cost information:

| Field | Type | Description |
|-------|------|-------------|
| layout | Layout | UI layout (existing) |
| components | Component[] | UI components (existing) |
| cost | CostBreakdown | Actual cost of this query |
| cached | boolean | Whether served from cache |
| credits_charged | int | Credits deducted (0 if free tier or cached) |
| balance_remaining | int | User's remaining balance |

---

## 7. REST / OpenAPI (Optional)

If FastAPI exposes REST in addition to gRPC:

- Ingestion: e.g. `POST /ingestion/upload`, `GET /ingestion/jobs/{job_id}`.
- RAG: e.g. `POST /rag/query` with JSON body `{ "query": "..." }` and response matching the RAGResponse schema (or a JSON mapping of the proto).
- Usage: e.g. `GET /usage/balance`, `POST /usage/estimate`, `POST /usage/purchase`, `GET /usage/history`.

OpenAPI schema should stay aligned with the proto definitions so that both gRPC and REST clients see a consistent contract.

---

## 8. References

- [SPEC.md](../SPEC.md) — Key interfaces (Section 7)
- [ARCHITECTURE.md](ARCHITECTURE.md) — Data flows and component roles
- [DATA_MODELS.md](DATA_MODELS.md) — Domain and storage models
- [COST_MODEL.md](COST_MODEL.md) — Pricing model, margins, and revenue projections
