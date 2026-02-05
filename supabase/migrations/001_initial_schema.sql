-- Demócrata Initial Database Schema
-- This migration sets up the core tables for auth, organizations, and billing.
-- For Supabase, this extends the built-in auth.users table.
-- For local development with plain PostgreSQL, we create a minimal auth schema.

-- =============================================================================
-- Auth Schema (for local development without Supabase)
-- =============================================================================
-- Create auth schema if it doesn't exist (Supabase provides this automatically)
CREATE SCHEMA IF NOT EXISTS auth;

-- Minimal auth.users table for local development
-- In production with Supabase, this table is managed by Supabase Auth
CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE NOT NULL,
    email_confirmed_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- Enum Types
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE org_plan AS ENUM ('free', 'pro', 'enterprise');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member', 'viewer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'declined', 'expired', 'revoked');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE account_type AS ENUM ('user', 'organization');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transaction_type AS ENUM ('purchase', 'usage', 'refund', 'grant', 'adjustment');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- =============================================================================
-- User Profiles
-- =============================================================================
-- Extends auth.users with additional profile information
CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name text,
    avatar_url text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Organizations
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.organizations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text UNIQUE NOT NULL,
    owner_id uuid NOT NULL REFERENCES auth.users(id),
    billing_email text NOT NULL,
    plan org_plan DEFAULT 'free',
    max_seats int DEFAULT 5,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

DROP TRIGGER IF EXISTS update_organizations_updated_at ON public.organizations;
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON public.organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Index for slug lookups (URL routing)
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_slug ON public.organizations(slug);

-- =============================================================================
-- Memberships
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    role member_role NOT NULL DEFAULT 'member',
    invited_by uuid REFERENCES auth.users(id),
    joined_at timestamptz DEFAULT now(),
    UNIQUE(user_id, organization_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON public.memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_organization_id ON public.memberships(organization_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org_user_role ON public.memberships(organization_id, user_id, role);

-- =============================================================================
-- Invitations
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    role member_role NOT NULL DEFAULT 'member',
    invited_by uuid NOT NULL REFERENCES auth.users(id),
    token text UNIQUE NOT NULL,
    status invitation_status DEFAULT 'pending',
    expires_at timestamptz NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Index for token lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_invitations_token ON public.invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_email_org ON public.invitations(email, organization_id);

-- =============================================================================
-- Billing Accounts
-- =============================================================================
-- Supports both individual user billing AND organization billing
CREATE TABLE IF NOT EXISTS public.billing_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_type account_type NOT NULL,
    user_id uuid REFERENCES auth.users(id),
    organization_id uuid REFERENCES public.organizations(id),
    credits int DEFAULT 0,
    lifetime_credits int DEFAULT 0,
    lifetime_usage int DEFAULT 0,
    free_tier_remaining int DEFAULT 100,  -- Monthly for registered users/orgs
    free_tier_reset_at timestamptz,
    stripe_customer_id text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    -- Ensure exactly one owner type is set
    CONSTRAINT single_owner CHECK (
        (user_id IS NOT NULL AND organization_id IS NULL) OR
        (user_id IS NULL AND organization_id IS NOT NULL)
    )
);

DROP TRIGGER IF EXISTS update_billing_accounts_updated_at ON public.billing_accounts;
CREATE TRIGGER update_billing_accounts_updated_at
    BEFORE UPDATE ON public.billing_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes for billing account lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_accounts_user_id 
    ON public.billing_accounts(user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_accounts_organization_id 
    ON public.billing_accounts(organization_id) WHERE organization_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_billing_accounts_stripe_customer 
    ON public.billing_accounts(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- =============================================================================
-- Credit Transactions
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.credit_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    amount int NOT NULL,  -- Positive = added, negative = used
    transaction_type transaction_type NOT NULL,
    balance_after int NOT NULL,
    reference_id text,  -- External reference (e.g., Stripe payment ID)
    description text,
    metadata jsonb,
    created_at timestamptz DEFAULT now()
);

-- Indexes for transaction queries
CREATE INDEX IF NOT EXISTS idx_credit_transactions_billing_account_created 
    ON public.credit_transactions(billing_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type_created 
    ON public.credit_transactions(transaction_type, created_at DESC);

-- =============================================================================
-- Usage Events (for detailed query tracking)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.usage_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    user_id uuid REFERENCES auth.users(id),  -- Who performed the action (for org context)
    session_id text,
    event_type text NOT NULL,
    query_hash text,
    query_preview text,
    cached boolean DEFAULT false,
    cost_breakdown jsonb NOT NULL,
    credits_charged int DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

-- Indexes for usage queries
CREATE INDEX IF NOT EXISTS idx_usage_events_billing_account_created 
    ON public.usage_events(billing_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_user_created 
    ON public.usage_events(user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usage_events_query_hash 
    ON public.usage_events(query_hash) WHERE query_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usage_events_created_at 
    ON public.usage_events(created_at);

-- =============================================================================
-- Row Level Security (RLS) Policies
-- =============================================================================
-- Note: These policies work with Supabase Auth. For local development without
-- Supabase, you may need to disable RLS or create a custom auth.uid() function.

-- For local development, create a mock auth.uid() function
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claim.sub', true)::uuid,
        '00000000-0000-0000-0000-000000000000'::uuid
    );
$$ LANGUAGE sql STABLE;

-- Enable RLS on tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can only see their own profile
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Organizations: Members can view their organizations
DROP POLICY IF EXISTS "Members can view organization" ON public.organizations;
CREATE POLICY "Members can view organization" ON public.organizations
    FOR SELECT USING (
        id IN (SELECT organization_id FROM public.memberships WHERE user_id = auth.uid())
    );

-- Memberships: Users can view memberships for orgs they belong to
DROP POLICY IF EXISTS "Members can view memberships" ON public.memberships;
CREATE POLICY "Members can view memberships" ON public.memberships
    FOR SELECT USING (
        organization_id IN (SELECT organization_id FROM public.memberships WHERE user_id = auth.uid())
    );

-- Billing accounts: Owner or org admin can access
DROP POLICY IF EXISTS "Owner can access billing" ON public.billing_accounts;
CREATE POLICY "Owner can access billing" ON public.billing_accounts
    FOR ALL USING (
        user_id = auth.uid() OR
        organization_id IN (
            SELECT organization_id FROM public.memberships 
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Transactions: Same as billing accounts
DROP POLICY IF EXISTS "Owner can view transactions" ON public.credit_transactions;
CREATE POLICY "Owner can view transactions" ON public.credit_transactions
    FOR SELECT USING (
        billing_account_id IN (
            SELECT id FROM public.billing_accounts
            WHERE user_id = auth.uid() OR
            organization_id IN (
                SELECT organization_id FROM public.memberships 
                WHERE user_id = auth.uid()
            )
        )
    );

-- Usage events: Same as billing accounts
DROP POLICY IF EXISTS "Owner can view usage" ON public.usage_events;
CREATE POLICY "Owner can view usage" ON public.usage_events
    FOR SELECT USING (
        billing_account_id IN (
            SELECT id FROM public.billing_accounts
            WHERE user_id = auth.uid() OR
            organization_id IN (
                SELECT organization_id FROM public.memberships 
                WHERE user_id = auth.uid()
            )
        )
    );

-- Invitations: Org admins can manage, users can view their own
DROP POLICY IF EXISTS "Admins can manage invitations" ON public.invitations;
CREATE POLICY "Admins can manage invitations" ON public.invitations
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM public.memberships 
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

DROP POLICY IF EXISTS "Users can view own invitations" ON public.invitations;
CREATE POLICY "Users can view own invitations" ON public.invitations
    FOR SELECT USING (
        email = (SELECT email FROM auth.users WHERE id = auth.uid())
    );
