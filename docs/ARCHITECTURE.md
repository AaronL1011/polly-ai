# Demócrata — Architecture

This document describes the system architecture for Demócrata. It expands on [SPEC.md](../SPEC.md) Section 3 (High-level architecture) and Section 4 (Component specifications).

---

## 1. Overview

Demócrata is a **stateless**, **horizontally scalable** political data ingestion and RAG query system. It consists of:

- **Clients:** Web browser (users) and automated scrapers/jobs
- **Application:** Web frontend (Svelte, gRPC-Web), API server (FastAPI, gRPC), Ingestion Pipeline, RAG Service
- **Infrastructure:** S3 (blob storage), Redis (cache), Vector Store (embeddings), LLM/Embedding APIs

Correctness does **not** depend on in-process state; all shared state lives in S3, Redis, and the vector store. Multiple API server instances can run behind a load balancer with the same configuration.

---

## 2. High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│  ┌──────────────────┐                    ┌──────────────────┐               │
│  │ User (browser)   │                    │ Scraper / Jobs   │               │
│  └────────┬─────────┘                    └────────┬─────────┘               │
└───────────┼──────────────────────────────────────┼─────────────────────────┘
            │                                      │
            ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                  │
│  ┌──────────────────┐    gRPC-Web / HTTP    ┌──────────────────────────────┐│
│  │ Web Frontend     │◄─────────────────────►│ API Server (FastAPI, gRPC)   ││
│  │ (Svelte)         │                        │  • Ingestion endpoints        ││
│  └──────────────────┘                        │  • RAG query endpoints       ││
│                                              └──────────────┬───────────────┘│
│                                                             │                │
│                    ┌────────────────────────────────────────┼────────────┐   │
│                    ▼                                        ▼            │   │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐     │   │
│  │ Ingestion Pipeline          │    │ RAG Service                 │     │   │
│  │ • Clean, enrich, chunk      │    │ • Embed query, top-k search │     │   │
│  │ • Embed, index              │    │ • LLM reasoning             │     │   │
│  │ • Store blobs + vectors     │    │ • Structured layout output  │     │   │
│  └──────────────┬──────────────┘    └──────────────┬──────────────┘     │   │
└─────────────────┼─────────────────────────────────┼───────────────────────┘
                  │                                  │
                  ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INFRASTRUCTURE                                      │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ S3         │  │ Redis      │  │ Vector Store    │  │ LLM / Embedding  │  │
│  │ (blobs)    │  │ (cache)    │  │ (top-k search)  │  │ APIs             │  │
│  └────────────┘  └────────────┘  └─────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flows

### 3.1 Ingestion Flow

1. **Input:** Web-browser upload (via upload portal) or automated scraper job calling the API.
2. **Ingestion Pipeline:**
   - **Clean:** Normalise and validate input data (bills, Hansard, member data, etc.).
   - **Enrich:** Assign accurate metadata (source, date, type, entities).
   - **Chunk:** Split content into RAG-suitable chunks (e.g. by section, paragraph, or fixed size).
   - **Embed:** Run chunks through the embedding model.
   - **Store:** Write blobs to S3; write vectors and metadata to the vector store; use Redis where appropriate (e.g. repeated embeddings, job status).
3. **Output:** Data is RAG-ready (retrievable by embedding search).

### 3.2 Query Flow

1. **Input:** Natural-language query from the frontend (and optionally user/session for costing and caching).
2. **RAG Service:**
   - **Embed:** Encode the query with the same embedding model.
   - **Search:** Top-k retrieval from the vector store.
   - **Retrieve:** Fetch full document chunks (and blobs from S3 if needed).
   - **Reason:** LLM (via LangChain) reasons over retrieved context.
   - **Structure:** Produce a strongly typed response (layout + components) per proto/schema.
3. **Output:** Structured payload (e.g. `RAGResponse` with `Layout` and component list) sent to the frontend.
4. **Frontend:** Renders a dashboard from layout and components (text blocks, charts, timelines, tables, etc.).

---

## 4. Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Web Frontend** | Query UI; gRPC-Web client; render dashboards from server payloads; non-partisan presentation (factual accuracy without advocacy or false balance). |
| **API Server** | HTTP/gRPC entrypoint; routes to Ingestion Pipeline and RAG Service; auth and cost pass-through. |
| **Ingestion Pipeline** | Clean, enrich, chunk, embed, and store political data; no UI logic. |
| **RAG Service** | Embed query, top-k search, LLM reasoning, structured response generation; uses LangChain and proto-defined types. |
| **S3** | Blob and large artifact storage (original/source files, derived artifacts). |
| **Redis** | Query/result cache; optional embedding or session caches; TTL and key strategy to minimise overhead. |
| **Vector Store** | Vector index and metadata for top-k similarity search. |
| **LLM / Embedding APIs** | Embeddings and LLM calls; cost tracked and passed to user. |

---

## 5. Scaling and Statelessness

- **Application servers:** Stateless; any instance can serve any request. Horizontal scaling by adding instances behind a load balancer.
- **Shared resources:** All instances use the same S3 bucket(s), Redis instance/cluster, vector store, and LLM/embedding configuration.
- **No sticky sessions required:** Session or user context (if needed for costing/caching) is stored in Redis or derived from tokens, not in-process memory.

For detailed scaling patterns (async job queues, rate limiting, batch processing) and phased implementation roadmap, see [SCALING.md](SCALING.md).

---

## 6. References

- [SPEC.md](../SPEC.md) — Mission, scope, tech stack, non-functional requirements
- [SCHEMAS.md](SCHEMAS.md) — API and RAG response schemas
- [DATA_MODELS.md](DATA_MODELS.md) — Domain and storage models
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — Code layout and implementation conventions
- [SCALING.md](SCALING.md) — Scaling patterns and phased roadmap
