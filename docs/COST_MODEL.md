# Demócrata — Cost Model and Monetization

This document describes the cost model, pricing strategy, and usage tracking for Demócrata. It provides the foundation for sustainable operation while maintaining civic accessibility.

---

## 1. Monetization Philosophy

### 1.1 Core Values

- **Civic accessibility:** Basic access to political information should be free. Democracy benefits when citizens can easily understand their government.
- **Sustainability:** The system must generate enough revenue to cover operational costs plus a modest income for maintainers. This is not a venture-scale business—the goal is long-term sustainability, not aggressive growth.
- **Transparency:** Users see what they pay for and why. Cost breakdowns are visible, pricing is predictable, and there are no hidden fees.

### 1.2 Revenue Goal

Target: Cover infrastructure costs + provide livable income for system maintainers (e.g., $3–5K/month net after costs). This requires a modest user base with reasonable conversion rates, achievable for a useful civic tool.

---

## 2. Cost Drivers

All costs that contribute to per-query or per-ingestion pricing:

### 2.1 Variable Costs (Per-Request)

| Cost Type | Driver | Typical Rate | Notes |
|-----------|--------|--------------|-------|
| **LLM API (input)** | Input tokens | ~$0.01–0.03 per 1K tokens | Context + query sent to LLM |
| **LLM API (output)** | Output tokens | ~$0.03–0.06 per 1K tokens | LLM response generation |
| **Embedding API** | Input tokens | ~$0.0001 per 1K tokens | Query and document embedding |
| **Vector store queries** | Query count | ~$0.00001–0.0001 per query | Top-k similarity search |

### 2.2 Fixed/Operational Costs (Not Passed to Users)

| Cost Type | Driver | Typical Rate | Notes |
|-----------|--------|--------------|-------|
| **S3 storage** | GB stored | ~$0.023/GB/month | Document blobs |
| **S3 transfer** | GB transferred | ~$0.09/GB | Retrieval during queries |
| **Vector store storage** | Vectors stored | Varies by provider | Indexed embeddings |
| **Redis** | Memory hours | ~$0.05–0.10/GB-hour | Cache layer |
| **Compute** | Server hours | Variable | API servers, workers |

Fixed costs are covered by the margin on variable costs and are not itemized to users.

### 2.3 Ingestion Costs

| Operation | Cost Driver | Who Pays |
|-----------|-------------|----------|
| Bulk political data (bills, Hansard, votes) | Embedding tokens | Operator (service cost) |
| User-uploaded documents (future) | Embedding tokens | User (if implemented) |

Public political data ingestion is treated as a service cost—part of providing value to all users. This cost is amortized across all queries via the margin.

---

## 3. Pricing Model: Freemium + Pay-As-You-Go

```
┌─────────────────────────────────────────────────────────────────┐
│                         FREE TIER                                │
│                                                                  │
│  • Anonymous users: 10 queries per day                          │
│  • Registered users: 100 queries per month                      │
│  • Standard response quality                                     │
│  • Cached responses served when available                       │
│  • No credit card required                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (exceeds limits)
┌─────────────────────────────────────────────────────────────────┐
│                      PAY-AS-YOU-GO                               │
│                                                                  │
│  • Prepaid credits: 1 credit = $0.01                            │
│  • Credit packs: $5 (500), $10 (1000), $20 (2000)               │
│  • Per-query cost: ~3–8 credits depending on complexity         │
│  • Credits never expire                                          │
│  • Transparent cost breakdown shown per query                   │
│  • Low-balance warnings at 50 and 10 credits                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Free Tier Limits

| User Type | Limit | Reset |
|-----------|-------|-------|
| Anonymous (no account) | 10 queries/day | Daily at midnight UTC |
| Registered (free account) | 100 queries/month | Monthly on registration anniversary |

Anonymous limits are tracked by session/IP fingerprint (not foolproof, but sufficient for honest users). Registration is encouraged but not required for basic use.

### 3.2 Credit System

| Aspect | Value | Rationale |
|--------|-------|-----------|
| Credit value | 1 credit = $0.01 | Simple mental model |
| Minimum purchase | $5 (500 credits) | Covers payment processing fees (~3%) |
| Credit packs | $5, $10, $20 | Low barrier, flexible amounts |
| Expiration | Never | Builds trust, encourages prepayment |
| Refunds | Pro-rata for unused credits | Fair policy |

### 3.3 Cached Query Handling

- **Free tier:** Cached responses count against free tier limits (still consumes a "query" but costs nothing to serve)
- **Paid tier:** Cached responses cost 0 credits (user only pays for actual LLM/API usage)

This rewards common questions and reduces system costs while being fair to users.

---

## 4. Query Cost Calculation

### 4.1 Formula

```
query_cost = (
    embedding_cost           # embed the query text
  + vector_search_cost       # top-k retrieval
  + llm_input_cost           # context + query tokens to LLM
  + llm_output_cost          # LLM response tokens
) × (1 + margin)
```

### 4.2 Component Costs

| Component | Calculation | Typical Value |
|-----------|-------------|---------------|
| Embedding cost | query_tokens × embedding_rate | ~$0.00001 |
| Vector search cost | fixed per query | ~$0.0001 |
| LLM input cost | (context_tokens + query_tokens) × input_rate | ~$0.01–0.03 |
| LLM output cost | output_tokens × output_rate | ~$0.01–0.03 |

### 4.3 Margin

**Recommended margin: 40% on variable costs**

This covers:
- Fixed infrastructure costs (S3, Redis, compute)
- Ingestion costs (operator-funded)
- Maintainer income
- Payment processing fees
- Buffer for cost fluctuations

### 4.4 Example Calculations

**Simple query (cached context, short response):**
- Embedding: 30 tokens × $0.0001/1K = $0.000003
- Vector search: $0.0001
- LLM input: 1,500 tokens × $0.01/1K = $0.015
- LLM output: 200 tokens × $0.03/1K = $0.006
- Subtotal: $0.021
- With 40% margin: $0.029 → **3 credits**

**Complex query (large context, detailed response):**
- Embedding: 80 tokens × $0.0001/1K = $0.000008
- Vector search: $0.0001
- LLM input: 4,000 tokens × $0.01/1K = $0.04
- LLM output: 800 tokens × $0.03/1K = $0.024
- Subtotal: $0.064
- With 40% margin: $0.090 → **9 credits**

**Cached response:**
- Cost: $0 → **0 credits** (paid users) or 1 free tier query (free users)

---

## 5. Usage Tracking Schema

### 5.1 UsageEvent

Records every billable action for auditing, analytics, and billing.

```
UsageEvent:
  id: UUID                    # Unique event identifier
  user_id: UUID | null        # Null for anonymous users
  session_id: string          # Session identifier (for anonymous tracking)
  event_type: EventType       # query | ingestion
  timestamp: datetime         # When the event occurred
  cached: boolean             # Whether result was served from cache
  query_hash: string          # Hash of query (for cache attribution)
  
  # Cost breakdown
  costs:
    embedding_tokens: int
    embedding_cost: decimal
    llm_input_tokens: int
    llm_output_tokens: int
    llm_cost: decimal
    vector_queries: int
    vector_cost: decimal
    total_cost: decimal           # Raw cost before margin
    total_with_margin: decimal    # Final billable amount
    credits_charged: int          # Credits deducted (0 if free tier)
```

### 5.2 UserBalance

Tracks user credit balance and free tier status.

```
UserBalance:
  user_id: UUID               # User identifier
  credits: decimal            # Current credit balance (in credits, not dollars)
  lifetime_credits: decimal   # Total credits ever purchased
  lifetime_usage: decimal     # Total credits ever used
  free_tier_remaining: int    # Remaining free queries this period
  free_tier_reset_at: datetime # When free tier resets
  created_at: datetime
  updated_at: datetime
```

### 5.3 CreditTransaction

Audit log for all credit movements.

```
CreditTransaction:
  id: UUID                    # Transaction identifier
  user_id: UUID               # User identifier
  amount: decimal             # Positive for credits added, negative for usage
  type: TransactionType       # purchase | usage | refund | grant | adjustment
  reference_id: string        # Payment ID, UsageEvent ID, or admin note
  balance_after: decimal      # Balance after this transaction
  timestamp: datetime
  metadata: JSON              # Additional context (payment provider, admin, etc.)
```

### 5.4 Indexes and Queries

Key queries the schema must support efficiently:
- Get user's current balance and free tier status
- List user's recent usage events (for usage history UI)
- Sum costs by user over a time period (for analytics)
- List transactions by user (for billing history)
- Aggregate usage by query_hash (for cache analytics)

---

## 6. Cost Control Mechanisms

### 6.1 User-Facing Controls

| Mechanism | Description |
|-----------|-------------|
| **Cost estimation** | Before executing, show estimated cost in credits |
| **Balance display** | Always show current balance in UI |
| **Low-balance warning** | Alert at 50 credits and 10 credits remaining |
| **Insufficient funds** | Block query if balance would go negative; prompt to add credits |
| **Usage history** | Show recent queries with cost breakdown |

### 6.2 System-Level Controls

| Mechanism | Description |
|-----------|-------------|
| **Spending limits** | Optional per-user daily/monthly spending cap |
| **Rate limiting** | Prevent runaway usage from bugs or abuse |
| **Cost anomaly detection** | Alert operators if per-query costs spike unexpectedly |
| **Circuit breaker** | Pause billing if external API costs exceed thresholds |

### 6.3 Operator Controls

| Mechanism | Description |
|-----------|-------------|
| **Grant credits** | Admin can grant credits to users (for support, promotions) |
| **Adjust balance** | Admin can adjust balance with audit trail |
| **View usage** | Dashboard showing system-wide usage and revenue |
| **Cost configuration** | Update API rates and margin without code deploy |

---

## 7. Implementation Phases

Aligned with [SCALING.md](SCALING.md) phases:

| Phase | Cost/Usage Capabilities |
|-------|------------------------|
| **Phase 1: MVP** | Log costs per request (structured logs); manual margin calculation; no billing integration; all usage free during beta |
| **Phase 2: Async Ingestion** | Persist UsageEvent to database; basic usage API (`GET /usage`); cost breakdown in query response |
| **Phase 3: Resilience** | Free tier enforcement; UserBalance tracking; rate limiting by balance; low-balance warnings |
| **Phase 4: Batch Processing** | Payment integration (Stripe or similar); credit purchase flow; CreditTransaction audit log |
| **Phase 5: High Availability** | Usage dashboards; spending alerts; admin tools for credits/adjustments |
| **Phase 6: Multi-Tenancy** | Per-tenant billing; usage quotas; SLA tiers with different margins |

### 7.1 MVP Specifics

During MVP/beta:
- All queries are free (no enforcement)
- Costs are logged but not charged
- Focus on validating cost assumptions with real usage data
- Adjust margin and pricing before enabling billing

---

## 8. Payment Integration (Phase 4+)

### 8.1 Recommended Provider

**Stripe** (or similar):
- Low barrier for small transactions
- Good developer experience
- Supports one-time payments (credit packs)
- Handles tax compliance

### 8.2 Purchase Flow

```
User clicks "Buy Credits"
    → Select credit pack ($5, $10, $20)
    → Stripe Checkout / Payment Element
    → Webhook confirms payment
    → CreditTransaction (type: purchase) created
    → UserBalance.credits incremented
    → User sees updated balance
```

### 8.3 Fee Considerations

| Amount | Stripe Fee (~2.9% + $0.30) | Net Revenue | Effective Rate |
|--------|---------------------------|-------------|----------------|
| $5 | $0.45 | $4.55 | 91% |
| $10 | $0.59 | $9.41 | 94% |
| $20 | $0.88 | $19.12 | 96% |

$5 minimum balances accessibility with reasonable fee efficiency. Larger packs are more efficient but higher barrier.

---

## 9. Revenue Projections

### 9.1 Target

Modest sustainability: **$3,000–5,000/month net** (after infrastructure and payment fees)

### 9.2 Assumptions

- 10% of active users exceed free tier and become paying
- Average paying user: $3/month (300 credits, ~50–100 queries)
- Infrastructure costs: ~$500–1,000/month at scale
- Payment fees: ~5% of gross revenue

### 9.3 Required Scale

| Scenario | Paying Users | Total Active Users | Monthly Revenue |
|----------|--------------|-------------------|-----------------|
| Minimum viable | 1,000 | 10,000 | ~$3,000 |
| Comfortable | 2,000 | 20,000 | ~$6,000 |
| Strong | 5,000 | 50,000 | ~$15,000 |

These numbers are achievable for a useful niche tool with good SEO, word-of-mouth, and steady content updates around political events.

---

## 10. References

- [SPEC.md](../SPEC.md) — Mission, scope, cost principles
- [ARCHITECTURE.md](ARCHITECTURE.md) — System components, data flows
- [SCALING.md](SCALING.md) — Phased implementation roadmap
- [DATA_MODELS.md](DATA_MODELS.md) — Storage models for usage entities
- [SCHEMAS.md](SCHEMAS.md) — API schemas for cost/usage endpoints
