---
name: Auth Sessions Billing MVP
overview: Implement authentication, session management, organization support, and billing using Supabase (auth + PostgreSQL), with clean adapter patterns ensuring technology isolation for future migration flexibility.
todos:
  - id: domain-auth
    content: Create auth domain layer (entities, ports) for User, Organization, Membership
    status: pending
  - id: db-schema
    content: Design and create PostgreSQL schema with migrations (profiles, orgs, memberships, billing_accounts, usage_events, transactions)
    status: pending
  - id: supabase-adapter
    content: Implement SupabaseAuthProvider adapter with JWT validation
    status: pending
  - id: postgres-adapter
    content: Implement PostgreSQL repository adapters (UserRepository, OrganizationRepository, BalanceStore)
    status: pending
  - id: api-auth
    content: Add FastAPI auth routes (/auth/session, /auth/logout, /auth/refresh)
    status: pending
  - id: api-orgs
    content: Add organization management API routes (CRUD, members, invitations)
    status: pending
  - id: api-billing
    content: Add billing API routes (account, purchase, webhooks, usage history)
    status: pending
  - id: stripe-adapter
    content: Implement Stripe payment adapter for credit purchases
    status: pending
  - id: frontend-auth
    content: Create Svelte auth components (LoginForm, SignupForm, AuthGuard, UserMenu)
    status: pending
  - id: frontend-org
    content: Create Svelte org components (OrgSwitcher, MemberList, InviteModal)
    status: pending
  - id: frontend-billing
    content: Create Svelte billing components (CreditBalance, PurchaseCredits, UsageHistory)
    status: pending
  - id: infra
    content: Update docker-compose.yml and environment configuration
    status: pending
isProject: false
---

# Auth, Sessions, and Billing Implementation Plan

## Architecture Overview

The implementation follows the existing clean architecture pattern with domain entities, ports (protocols), and adapters. All Supabase-specific code will be isolated in adapters, with domain logic remaining technology-agnostic.

```mermaid
flowchart TB
    subgraph frontend [Frontend - Svelte]
        AuthUI[Auth Components]
        OrgUI[Org Management UI]
        BillingUI[Billing Dashboard]
    end
    
    subgraph api [API Layer - FastAPI]
        AuthRoutes["/auth/*"]
        OrgRoutes["/orgs/*"]
        BillingRoutes["/billing/*"]
    end
    
    subgraph domain [Domain Layer]
        AuthEntities[User, Session, Organization, Membership]
        AuthPorts[AuthProvider, SessionManager, OrgRepository]
        UsagePorts[BalanceStore, UsageLogger, TransactionStore]
    end
    
    subgraph adapters [Adapters Layer]
        SupabaseAuth[SupabaseAuthProvider]
        SupabaseDB[SupabaseRepository]
        StripeAdapter[StripePaymentAdapter]
    end
    
    subgraph infra [Infrastructure]
        Supabase[(Supabase Auth + PostgreSQL)]
        Stripe[Stripe API]
        Redis[(Redis Cache)]
    end
    
    frontend --> api
    api --> domain
    domain --> adapters
    SupabaseAuth --> Supabase
    SupabaseDB --> Supabase
    StripeAdapter --> Stripe
    adapters --> Redis
```



---

## 1. Domain Layer - New Entities

### 1.1 Auth Entities

Create `[server/src/democrata_server/domain/auth/entities.py](server/src/democrata_server/domain/auth/entities.py)`:

```python
@dataclass
class User:
    id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    email_verified: bool
    created_at: datetime
    updated_at: datetime

@dataclass
class Organization:
    id: UUID
    name: str
    slug: str  # URL-friendly identifier
    owner_id: UUID
    billing_email: str
    plan: OrganizationPlan  # free | pro | enterprise
    max_seats: int
    created_at: datetime

@dataclass
class Membership:
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MemberRole  # owner | admin | member | viewer
    invited_by: UUID | None
    joined_at: datetime
```

### 1.2 Auth Ports

Create `[server/src/democrata_server/domain/auth/ports.py](server/src/democrata_server/domain/auth/ports.py)`:

```python
class AuthProvider(Protocol):
    """Technology-agnostic auth interface."""
    async def get_user(self, token: str) -> User | None: ...
    async def verify_session(self, session_token: str) -> Session | None: ...
    async def refresh_session(self, refresh_token: str) -> Session | None: ...
    async def sign_out(self, session_token: str) -> None: ...

class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def update(self, user: User) -> None: ...

class OrganizationRepository(Protocol):
    async def get_by_id(self, org_id: UUID) -> Organization | None: ...
    async def get_by_slug(self, slug: str) -> Organization | None: ...
    async def get_user_organizations(self, user_id: UUID) -> list[Organization]: ...
    async def create(self, org: Organization) -> Organization: ...
    async def add_member(self, membership: Membership) -> None: ...
    async def remove_member(self, org_id: UUID, user_id: UUID) -> None: ...
    async def get_members(self, org_id: UUID) -> list[Membership]: ...
```

---

## 2. Data Model - PostgreSQL Schema

### 2.1 Users Table (managed by Supabase Auth)

Supabase creates `auth.users` automatically. We extend with a `public.profiles` table:

```sql
create table public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    name text,
    avatar_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
```

### 2.2 Organizations and Memberships

```sql
create type org_plan as enum ('free', 'pro', 'enterprise');
create type member_role as enum ('owner', 'admin', 'member', 'viewer');

create table public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text unique not null,
    owner_id uuid not null references auth.users(id),
    billing_email text not null,
    plan org_plan default 'free',
    max_seats int default 5,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.memberships (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    organization_id uuid not null references public.organizations(id) on delete cascade,
    role member_role not null default 'member',
    invited_by uuid references auth.users(id),
    joined_at timestamptz default now(),
    unique(user_id, organization_id)
);
```

### 2.3 Billing - Dual-Track Model

Support **both** individual user billing AND organization billing:

```sql
-- Account represents a billing entity (user OR org)
create type account_type as enum ('user', 'organization');

create table public.billing_accounts (
    id uuid primary key default gen_random_uuid(),
    account_type account_type not null,
    user_id uuid references auth.users(id),
    organization_id uuid references public.organizations(id),
    credits int default 0,
    lifetime_credits int default 0,
    lifetime_usage int default 0,
    free_tier_remaining int default 100,  -- Monthly for registered
    free_tier_reset_at timestamptz,
    stripe_customer_id text,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    constraint single_owner check (
        (user_id is not null and organization_id is null) or
        (user_id is null and organization_id is not null)
    )
);

create table public.usage_events (
    id uuid primary key default gen_random_uuid(),
    billing_account_id uuid not null references public.billing_accounts(id),
    user_id uuid references auth.users(id),  -- Who performed the action
    session_id text,
    event_type text not null,
    query_hash text,
    query_preview text,
    cached boolean default false,
    cost_breakdown jsonb not null,
    credits_charged int default 0,
    created_at timestamptz default now()
);

create table public.credit_transactions (
    id uuid primary key default gen_random_uuid(),
    billing_account_id uuid not null references public.billing_accounts(id),
    amount int not null,  -- Positive = added, negative = used
    transaction_type text not null,  -- purchase, usage, refund, grant
    reference_id text,
    balance_after int not null,
    metadata jsonb,
    created_at timestamptz default now()
);
```

### 2.4 Row Level Security (RLS)

```sql
-- Users can only see their own profile
alter table public.profiles enable row level security;
create policy "Users can view own profile" on public.profiles
    for select using (auth.uid() = id);

-- Users can see orgs they belong to
alter table public.organizations enable row level security;
create policy "Members can view organization" on public.organizations
    for select using (
        id in (select organization_id from public.memberships where user_id = auth.uid())
    );

-- Billing accounts visible to owner or org members
alter table public.billing_accounts enable row level security;
create policy "Owner can access billing" on public.billing_accounts
    for all using (
        user_id = auth.uid() or
        organization_id in (
            select organization_id from public.memberships 
            where user_id = auth.uid() and role in ('owner', 'admin')
        )
    );
```

### 2.5 Indexing Strategy

Indexes are critical for query performance, especially as data grows. The strategy below optimizes for the most common access patterns while considering future horizontal scaling.

#### Primary Access Pattern Indexes

```sql
-- Memberships: frequently queried by user_id (list user's orgs) and org_id (list org members)
create index idx_memberships_user_id on public.memberships(user_id);
create index idx_memberships_organization_id on public.memberships(organization_id);

-- Organizations: lookup by slug (URL routing)
create unique index idx_organizations_slug on public.organizations(slug);

-- Billing accounts: lookup by owner (user or org)
create unique index idx_billing_accounts_user_id on public.billing_accounts(user_id) 
    where user_id is not null;
create unique index idx_billing_accounts_organization_id on public.billing_accounts(organization_id) 
    where organization_id is not null;

-- Usage events: queried by billing account + time range (usage history, analytics)
create index idx_usage_events_billing_account_created 
    on public.usage_events(billing_account_id, created_at desc);

-- Usage events: queried by user (per-member breakdown in org context)
create index idx_usage_events_user_created 
    on public.usage_events(user_id, created_at desc) 
    where user_id is not null;

-- Credit transactions: audit log queries by billing account + time
create index idx_credit_transactions_billing_account_created 
    on public.credit_transactions(billing_account_id, created_at desc);
```

#### Analytics and Reporting Indexes

```sql
-- Usage aggregation by time period (monthly reports, dashboards)
create index idx_usage_events_created_at on public.usage_events(created_at);

-- Query cache hit analysis
create index idx_usage_events_query_hash on public.usage_events(query_hash) 
    where query_hash is not null;

-- Transaction type filtering (e.g., "show all purchases")
create index idx_credit_transactions_type_created 
    on public.credit_transactions(transaction_type, created_at desc);
```

#### Composite Indexes for Complex Queries

```sql
-- Org member role checks (permission verification)
create index idx_memberships_org_user_role 
    on public.memberships(organization_id, user_id, role);

-- Billing account balance checks with free tier status
create index idx_billing_accounts_credits_free_tier 
    on public.billing_accounts(credits, free_tier_remaining) 
    where credits > 0 or free_tier_remaining > 0;
```

### 2.6 Horizontal Scaling Considerations

The schema is designed to support future horizontal scaling via sharding if query volume or data size requires it.

#### Sharding Strategy

| Table | Shard Key | Rationale |
|-------|-----------|-----------|
| `profiles` | `id` (user_id) | User data accessed by user_id |
| `organizations` | `id` | Org data accessed by org_id |
| `memberships` | `organization_id` | Keep org's members co-located |
| `billing_accounts` | `id` | Referenced by usage_events |
| `usage_events` | `billing_account_id` | Keep account's usage co-located for queries |
| `credit_transactions` | `billing_account_id` | Keep account's transactions co-located |

#### Shard-Friendly Query Patterns

All common queries include the shard key:

```sql
-- Good: includes shard key (billing_account_id)
SELECT * FROM usage_events 
WHERE billing_account_id = $1 AND created_at > $2;

-- Good: includes shard key (organization_id)
SELECT * FROM memberships 
WHERE organization_id = $1;

-- Avoid: cross-shard aggregation (defer to analytics pipeline)
SELECT user_id, SUM(credits_charged) FROM usage_events 
GROUP BY user_id;  -- Would scatter-gather across shards
```

#### UUID Strategy for Distribution

All primary keys use UUIDv4 (`gen_random_uuid()`) which:
- Distributes evenly across shards (no hot spots)
- Allows client-side ID generation (reduces round trips)
- Enables cross-region ID uniqueness

#### Time-Series Partitioning for Usage Events

For high-volume tables, consider native PostgreSQL partitioning by time:

```sql
-- Future: partition usage_events by month
create table public.usage_events (
    id uuid not null default gen_random_uuid(),
    billing_account_id uuid not null,
    created_at timestamptz not null default now(),
    -- ... other columns
) partition by range (created_at);

-- Create monthly partitions
create table usage_events_2026_01 partition of usage_events
    for values from ('2026-01-01') to ('2026-02-01');
create table usage_events_2026_02 partition of usage_events
    for values from ('2026-02-01') to ('2026-03-01');
-- ... automated via pg_partman or cron job
```

Benefits:
- Fast pruning for time-range queries
- Easy archival of old partitions
- Parallel query execution across partitions
- Can drop old partitions without vacuum overhead

#### Connection Pooling

For horizontal scaling, use PgBouncer or Supabase's built-in pooler:

```
Application → PgBouncer (transaction mode) → PostgreSQL
```

Configuration considerations:
- Transaction pooling mode for stateless queries
- Pool size = (num_cores * 2) + effective_spindle_count
- Statement timeout to prevent long-running queries

#### Read Replicas

For read-heavy workloads (usage dashboards, analytics):

```mermaid
flowchart LR
    App[Application]
    Primary[(Primary DB)]
    Replica1[(Read Replica 1)]
    Replica2[(Read Replica 2)]
    
    App -->|writes| Primary
    App -->|reads| Replica1
    App -->|reads| Replica2
    Primary -->|replication| Replica1
    Primary -->|replication| Replica2
```

Adapter pattern enables transparent read/write splitting:

```python
class PostgresRepository:
    def __init__(self, write_pool: Pool, read_pool: Pool):
        self._write = write_pool  # Primary
        self._read = read_pool    # Replica(s)
    
    async def get_usage_history(self, account_id: UUID) -> list[UsageEvent]:
        # Route to read replica
        async with self._read.acquire() as conn:
            return await conn.fetch(...)
    
    async def log_usage(self, event: UsageEvent) -> None:
        # Route to primary
        async with self._write.acquire() as conn:
            await conn.execute(...)
```

---

## 3. Adapters Layer

### 3.1 Supabase Auth Adapter

Create `[server/src/democrata_server/adapters/auth/supabase.py](server/src/democrata_server/adapters/auth/supabase.py)`:

- Implement `AuthProvider` protocol using `supabase-py` client
- Validate JWTs from Supabase Auth
- Map Supabase user objects to domain `User` entities

### 3.2 PostgreSQL Repository Adapter

Create `[server/src/democrata_server/adapters/storage/postgres.py](server/src/democrata_server/adapters/storage/postgres.py)`:

- Implement `UserRepository`, `OrganizationRepository` protocols
- Implement `BalanceStore`, `UsageLogger` from existing usage ports
- Use `asyncpg` (already in dependencies) for async database access
- Can be swapped for any SQL database later

### 3.3 Payment Adapter (Stripe)

Create `[server/src/democrata_server/adapters/billing/stripe.py](server/src/democrata_server/adapters/billing/stripe.py)`:

- Implement `PaymentProvider` protocol
- Handle credit pack purchases ($5, $10, $20)
- Process webhooks for payment confirmation
- Isolated behind protocol for future provider swaps

---

## 4. API Layer

### 4.1 Auth Endpoints

Add to `[server/src/democrata_server/api/http/routes/](server/src/democrata_server/api/http/routes/)`:


| Endpoint        | Method | Description                         |
| --------------- | ------ | ----------------------------------- |
| `/auth/session` | GET    | Get current session/user from token |
| `/auth/logout`  | POST   | Invalidate session                  |
| `/auth/refresh` | POST   | Refresh access token                |


Note: Sign-up/sign-in handled by Supabase client in frontend.

### 4.2 Organization Endpoints


| Endpoint                    | Method | Description               |
| --------------------------- | ------ | ------------------------- |
| `/orgs`                     | GET    | List user's organizations |
| `/orgs`                     | POST   | Create organization       |
| `/orgs/{slug}`              | GET    | Get organization details  |
| `/orgs/{slug}/members`      | GET    | List members              |
| `/orgs/{slug}/members`      | POST   | Invite member             |
| `/orgs/{slug}/members/{id}` | DELETE | Remove member             |


### 4.3 Billing Endpoints


| Endpoint                    | Method | Description                              |
| --------------------------- | ------ | ---------------------------------------- |
| `/billing/account`          | GET    | Get billing account (user or active org) |
| `/billing/credits/purchase` | POST   | Create Stripe checkout session           |
| `/billing/credits/webhook`  | POST   | Handle Stripe webhooks                   |
| `/billing/usage`            | GET    | Get usage history                        |
| `/billing/transactions`     | GET    | Get transaction history                  |


---

## 5. Frontend Integration

### 5.1 Supabase Client Setup

Add to `[frontend/src/lib/](frontend/src/lib/)`:

```typescript
// supabase.ts
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
```

### 5.2 Auth Components

Create in `[frontend/src/lib/components/auth/](frontend/src/lib/components/auth/)`:

- `LoginForm.svelte` - Email/password + social login buttons
- `SignupForm.svelte` - Registration with email verification
- `AuthGuard.svelte` - Wrapper for protected routes
- `UserMenu.svelte` - User dropdown with logout, org switcher

### 5.3 Organization Components

Create in `[frontend/src/lib/components/org/](frontend/src/lib/components/org/)`:

- `OrgSwitcher.svelte` - Dropdown to switch active organization
- `OrgSettings.svelte` - Manage org name, billing email
- `MemberList.svelte` - View/manage members
- `InviteModal.svelte` - Invite new members by email

### 5.4 Billing Components

Create in `[frontend/src/lib/components/billing/](frontend/src/lib/components/billing/)`:

- `CreditBalance.svelte` - Display current balance + low balance warning
- `PurchaseCredits.svelte` - Credit pack selection + Stripe checkout
- `UsageHistory.svelte` - Table of recent usage with cost breakdown

---

## 6. Infrastructure Changes

### 6.1 Docker Compose

Add PostgreSQL service to `[docker-compose.yml](docker-compose.yml)`:

```yaml
postgres:
  image: postgres:16-alpine
  ports:
    - "5432:5432"
  environment:
    POSTGRES_USER: democrata
    POSTGRES_PASSWORD: democrata_dev
    POSTGRES_DB: democrata_pipeline
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

Note: For production, use Supabase hosted PostgreSQL.

### 6.2 Environment Variables

Add to `[.env.example](.env.example)`:

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Database (for local dev, production uses Supabase)
DATABASE_URL=postgresql://democrata:democrata_dev@localhost:5432/democrata_pipeline

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_500=price_...
STRIPE_PRICE_1000=price_...
STRIPE_PRICE_2000=price_...
```

---

## 7. Migration Path Considerations

The adapter pattern ensures easy migration:


| Component | Current             | Future Options              |
| --------- | ------------------- | --------------------------- |
| Auth      | Supabase Auth       | Clerk, Auth0, self-hosted   |
| Database  | Supabase PostgreSQL | Any PostgreSQL, CockroachDB |
| Payments  | Stripe              | Paddle, LemonSqueezy        |


To migrate auth providers:

1. Create new adapter implementing `AuthProvider` protocol
2. Update dependency injection in factory
3. Migrate user data (UUIDs remain stable)

---

## 8. User Flows

### 8.1 Individual User Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant Auth as SupabaseAuth
    participant DB as PostgreSQL

    Note over U,DB: 1. Anonymous Usage - No Signup
    U->>FE: Visit site, make query
    FE->>API: POST /rag/query - no auth token
    API->>API: Generate session_id from IP+UA hash
    API->>DB: Get/create session-based balance
    API->>API: Check free_tier_remaining - 10/day
    API-->>FE: Response + usage info
    
    Note over U,DB: 2. Signup - Convert Anonymous to Registered
    U->>FE: Click Sign Up
    FE->>Auth: supabase.auth.signUp
    Auth-->>FE: Session + user_id
    FE->>API: POST /auth/session with token
    API->>DB: Create profile + billing_account - user type
    API->>DB: Set free_tier_remaining = 100/month
    Note right of DB: User now has 100 free queries/month instead of 10/day

    Note over U,DB: 3. Registered User Query
    U->>FE: Make query - logged in
    FE->>API: POST /rag/query with Authorization Bearer token
    API->>Auth: Verify JWT to get user_id
    API->>DB: Get billing_account WHERE user_id = ?
    API->>DB: Check free_tier OR credits
    API->>API: Execute RAG pipeline
    API->>DB: Log usage_event, update balance
    API-->>FE: Response + cost breakdown

    Note over U,DB: 4. Purchase Credits - Exceeds Free Tier
    U->>FE: Click Buy Credits
    FE->>API: POST /billing/credits/purchase
    API->>Stripe: Create Checkout Session
    API-->>FE: Redirect URL
    FE->>Stripe: Complete payment
    Stripe->>API: Webhook payment_succeeded
    API->>DB: credit_transaction type purchase +1000
    API->>DB: Update billing_account.credits
```



### 8.2 Organization Flow

```mermaid
sequenceDiagram
    participant Owner as OrgOwner
    participant Member as TeamMember
    participant FE as Frontend
    participant API as FastAPI
    participant DB as PostgreSQL

    Note over Owner,DB: 1. Create Organization
    Owner->>FE: Click Create Organization
    FE->>API: POST /orgs with name and billing_email
    API->>DB: Create organization
    API->>DB: Create membership with role owner
    API->>DB: Create billing_account - org type, 100 free/month
    API-->>FE: Organization created

    Note over Owner,DB: 2. Invite Team Members
    Owner->>FE: Invite member@acme.com
    FE->>API: POST /orgs/acme-corp/members with email and role
    API->>DB: Create invitation record
    API->>API: Send invitation email
    
    Member->>FE: Click invite link, sign up/login
    FE->>API: POST /orgs/acme-corp/join with invite_token
    API->>DB: Create membership for user
    API-->>FE: Welcome to Acme Corp

    Note over Member,DB: 3. Member Makes Query - Org Context
    Member->>FE: Select Acme Corp in org switcher
    FE->>FE: Store active_org_id in context
    Member->>FE: Make query
    FE->>API: POST /rag/query with token + X-Organization-Id header
    API->>DB: Verify user is member of org
    API->>DB: Get billing_account WHERE organization_id = ?
    API->>DB: Check org free_tier OR credits
    API->>API: Execute RAG pipeline
    API->>DB: Log usage_event - billing_account=org, user_id=member
    API-->>FE: Response + cost charged to org

    Note over Owner,DB: 4. Owner Reviews Org Usage
    Owner->>FE: View Billing Dashboard
    FE->>API: GET /billing/usage?org=acme-corp
    API->>DB: SELECT usage_events WHERE billing_account = org
    API-->>FE: Usage breakdown by member
```



### 8.3 Billing Account Abstraction

The `billing_account` table handles both individual and org billing uniformly:


| Scenario        | billing_account.user_id | billing_account.organization_id |
| --------------- | ----------------------- | ------------------------------- |
| Individual user | `uuid`                  | `null`                          |
| Organization    | `null`                  | `uuid`                          |


This means the usage/billing logic operates on a billing account without needing to know if it represents a person or organization.

### 8.4 Context Switching

When a user belongs to multiple orgs (or has personal + org accounts), the frontend displays a context switcher:

```
Query as:
  - Personal Account (42 credits remaining)
  - Acme Corp (1,247 credits remaining)
  - Side Project LLC (89 credits remaining)
```

The frontend sends `X-Organization-Id` header (or omits it for personal), and the API routes billing accordingly.

### 8.5 Usage Attribution

Even when billing goes to an org, we track WHO made each query:

```sql
usage_events:
  billing_account_id  -- Acme Corp billing account (who pays)
  user_id             -- member@acme.com (who queried)
```

This enables:

- Org admins to see per-member usage breakdown
- Audit trails
- Future per-user quotas within orgs

### 8.6 Upgrade Paths

```
Anonymous (10/day)
    | sign up
    v
Individual Free (100/month)
    | purchase credits
    v
Individual Paid (credits)
    | create org
    v
Org Free (100/month shared)
    | purchase credits
    v
Org Paid (shared credit pool)
    | upgrade plan
    v
Org Pro (higher limits, priority)
```

### 8.7 Session to User Migration

When an anonymous user signs up, we can optionally migrate their session usage:

```python
async def on_user_signup(user_id: UUID, session_id: str):
    # Find any anonymous balance for this session
    anon_balance = await balance_store.get_by_session(session_id)
    if anon_balance and anon_balance.credits > 0:
        # Migrate credits to new user account
        user_balance = await balance_store.get_by_user(user_id)
        user_balance.credits += anon_balance.credits
        await balance_store.save(user_balance)
```

### 8.8 Summary Table


| User State        | Free Tier           | Billing Entity           | Can Create Org? |
| ----------------- | ------------------- | ------------------------ | --------------- |
| Anonymous         | 10 queries/day      | Session                  | No              |
| Registered (free) | 100 queries/month   | Personal billing_account | Yes             |
| Registered (paid) | + purchased credits | Personal billing_account | Yes             |
| Org member        | Uses org quota      | Org billing_account      | Depends on role |
| Org owner/admin   | Uses org quota      | Org billing_account      | Can manage org  |


---

## 9. Key Files to Create/Modify

### New Files

- `server/src/democrata_server/domain/auth/entities.py`
- `server/src/democrata_server/domain/auth/ports.py`
- `server/src/democrata_server/adapters/auth/supabase.py`
- `server/src/democrata_server/adapters/storage/postgres.py`
- `server/src/democrata_server/adapters/billing/stripe.py`
- `server/src/democrata_server/api/http/routes/auth.py`
- `server/src/democrata_server/api/http/routes/orgs.py`
- `server/src/democrata_server/api/http/routes/billing.py`
- `frontend/src/lib/supabase.ts`
- `frontend/src/lib/components/auth/*.svelte`
- `frontend/src/lib/components/org/*.svelte`
- `frontend/src/lib/components/billing/*.svelte`
- `supabase/migrations/*.sql`

### Modified Files

- `[docker-compose.yml](docker-compose.yml)` - Add PostgreSQL
- `[.env.example](.env.example)` - Add Supabase/Stripe config
- `[server/src/democrata_server/domain/usage/entities.py](server/src/democrata_server/domain/usage/entities.py)` - Add billing account reference
- `[server/src/democrata_server/domain/usage/ports.py](server/src/democrata_server/domain/usage/ports.py)` - Add transaction store port
- `server/pyproject.toml` - Add `supabase`, `stripe` dependencies
- `frontend/package.json` - Add `@supabase/supabase-js`

