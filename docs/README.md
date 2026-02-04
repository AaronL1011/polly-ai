# Demócrata — Documentation

Supporting documentation for the Demócrata project. The canonical product and scope spec is [SPEC.md](../SPEC.md).

---

## Documents

| Document | Description |
|----------|-------------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture, components, data flows (ingestion and query), scaling and statelessness. |
| **[SCHEMAS.md](SCHEMAS.md)** | API contracts (Ingestion, RAG, and Usage gRPC services), response schemas, component types. |
| **[DATA_MODELS.md](DATA_MODELS.md)** | Domain concepts, ingestion pipeline data, storage models (S3, vector store, Redis), usage entities. |
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Repository layout, domain-centred structure, tech stack, conventions, implementation notes. |
| **[SCALING.md](SCALING.md)** | Scaling challenges, patterns, and phased implementation roadmap (MVP → high-scale production). |
| **[COST_MODEL.md](COST_MODEL.md)** | Monetization strategy, pricing model (freemium + PAYG), usage tracking, revenue projections. |

---

## Quick reference

- **Mission and scope:** [SPEC.md](../SPEC.md) §§ 1–2  
- **Tech stack:** [SPEC.md](../SPEC.md) § 5 | [IMPLEMENTATION.md](IMPLEMENTATION.md) § 2  
- **Data flow:** [ARCHITECTURE.md](ARCHITECTURE.md) § 3  
- **API / RAG response types:** [SCHEMAS.md](SCHEMAS.md)  
- **Storage and cache:** [DATA_MODELS.md](DATA_MODELS.md) § 3  
- **Code layout and conventions:** [IMPLEMENTATION.md](IMPLEMENTATION.md)  
- **Scaling and roadmap:** [SCALING.md](SCALING.md)  
- **Pricing and monetization:** [COST_MODEL.md](COST_MODEL.md)
