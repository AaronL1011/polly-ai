"""PostgreSQL repository adapters for users, organizations, and billing."""

import logging
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from democrata_server.domain.auth.entities import User
from democrata_server.domain.billing.entities import (
    AccountType,
    BillingAccount,
    CreditTransaction,
    TransactionType,
)
from democrata_server.domain.orgs.entities import (
    Invitation,
    InvitationStatus,
    Membership,
    MemberRole,
    Organization,
    OrganizationPlan,
)

logger = logging.getLogger(__name__)


class PostgresConnectionPool:
    """Manages a PostgreSQL connection pool for the application."""

    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            logger.info("PostgreSQL connection pool initialized")

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool, raising if not initialized."""
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized. Call connect() first.")
        return self._pool


class PostgresUserRepository:
    """PostgreSQL implementation of UserRepository for profile data."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_user(self, row: asyncpg.Record) -> User:
        """Convert a database row to a User entity."""
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            avatar_url=row["avatar_url"],
            email_verified=row.get("email_verified", True),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by their unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT p.id, u.email, p.name, p.avatar_url, 
                       u.email_confirmed_at IS NOT NULL as email_verified,
                       p.created_at, p.updated_at
                FROM public.profiles p
                JOIN auth.users u ON p.id = u.id
                WHERE p.id = $1
                """,
                user_id,
            )
            return self._row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT p.id, u.email, p.name, p.avatar_url,
                       u.email_confirmed_at IS NOT NULL as email_verified,
                       p.created_at, p.updated_at
                FROM public.profiles p
                JOIN auth.users u ON p.id = u.id
                WHERE u.email = $1
                """,
                email.lower(),
            )
            return self._row_to_user(row) if row else None

    async def create(self, user: User) -> User:
        """Create a new user profile."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.profiles (id, name, avatar_url, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user.id,
                user.name,
                user.avatar_url,
                user.created_at,
                user.updated_at,
            )
            return user

    async def update(self, user: User) -> User:
        """Update an existing user profile."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.profiles
                SET name = $2, avatar_url = $3, updated_at = $4
                WHERE id = $1
                """,
                user.id,
                user.name,
                user.avatar_url,
                datetime.now(UTC),
            )
            return user


class PostgresOrganizationRepository:
    """PostgreSQL implementation of OrganizationRepository."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_organization(self, row: asyncpg.Record) -> Organization:
        """Convert a database row to an Organization entity."""
        return Organization(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            owner_id=row["owner_id"],
            billing_email=row["billing_email"],
            plan=OrganizationPlan(row["plan"]),
            max_seats=row["max_seats"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        """Get an organization by its unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.organizations WHERE id = $1",
                org_id,
            )
            return self._row_to_organization(row) if row else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get an organization by its URL-friendly slug."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.organizations WHERE slug = $1",
                slug.lower(),
            )
            return self._row_to_organization(row) if row else None

    async def create(self, organization: Organization) -> Organization:
        """Create a new organization."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.organizations 
                (id, name, slug, owner_id, billing_email, plan, max_seats, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                organization.id,
                organization.name,
                organization.slug.lower(),
                organization.owner_id,
                organization.billing_email,
                organization.plan.value,
                organization.max_seats,
                organization.created_at,
                organization.updated_at,
            )
            return organization

    async def update(self, organization: Organization) -> Organization:
        """Update an existing organization."""
        async with self._pool.pool.acquire() as conn:
            organization.updated_at = datetime.now(UTC)
            await conn.execute(
                """
                UPDATE public.organizations
                SET name = $2, billing_email = $3, plan = $4, max_seats = $5, updated_at = $6
                WHERE id = $1
                """,
                organization.id,
                organization.name,
                organization.billing_email,
                organization.plan.value,
                organization.max_seats,
                organization.updated_at,
            )
            return organization

    async def delete(self, org_id: UUID) -> None:
        """Delete an organization and all associated data."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM public.organizations WHERE id = $1",
                org_id,
            )

    async def slug_exists(self, slug: str) -> bool:
        """Check if a slug is already in use."""
        async with self._pool.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM public.organizations WHERE slug = $1)",
                slug.lower(),
            )
            return result


class PostgresMembershipRepository:
    """PostgreSQL implementation of MembershipRepository."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_membership(self, row: asyncpg.Record) -> Membership:
        """Convert a database row to a Membership entity."""
        return Membership(
            id=row["id"],
            user_id=row["user_id"],
            organization_id=row["organization_id"],
            role=MemberRole(row["role"]),
            invited_by=row["invited_by"],
            joined_at=row["joined_at"],
        )

    async def get_by_id(self, membership_id: UUID) -> Membership | None:
        """Get a membership by its unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.memberships WHERE id = $1",
                membership_id,
            )
            return self._row_to_membership(row) if row else None

    async def get_user_memberships(self, user_id: UUID) -> list[Membership]:
        """Get all memberships for a user."""
        async with self._pool.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM public.memberships WHERE user_id = $1 ORDER BY joined_at",
                user_id,
            )
            return [self._row_to_membership(row) for row in rows]

    async def get_organization_members(self, org_id: UUID) -> list[Membership]:
        """Get all memberships in an organization."""
        async with self._pool.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM public.memberships WHERE organization_id = $1 ORDER BY joined_at",
                org_id,
            )
            return [self._row_to_membership(row) for row in rows]

    async def get_membership(self, user_id: UUID, org_id: UUID) -> Membership | None:
        """Get a specific user's membership in an organization."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM public.memberships 
                WHERE user_id = $1 AND organization_id = $2
                """,
                user_id,
                org_id,
            )
            return self._row_to_membership(row) if row else None

    async def create(self, membership: Membership) -> Membership:
        """Create a new membership."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.memberships 
                (id, user_id, organization_id, role, invited_by, joined_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                membership.id,
                membership.user_id,
                membership.organization_id,
                membership.role.value,
                membership.invited_by,
                membership.joined_at,
            )
            return membership

    async def update(self, membership: Membership) -> Membership:
        """Update an existing membership (e.g., change role)."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.memberships SET role = $2 WHERE id = $1",
                membership.id,
                membership.role.value,
            )
            return membership

    async def delete(self, membership_id: UUID) -> None:
        """Remove a membership."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM public.memberships WHERE id = $1",
                membership_id,
            )

    async def count_members(self, org_id: UUID) -> int:
        """Count the number of members in an organization."""
        async with self._pool.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM public.memberships WHERE organization_id = $1",
                org_id,
            )
            return count or 0


class PostgresInvitationRepository:
    """PostgreSQL implementation of InvitationRepository."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_invitation(self, row: asyncpg.Record) -> Invitation:
        """Convert a database row to an Invitation entity."""
        return Invitation(
            id=row["id"],
            email=row["email"],
            organization_id=row["organization_id"],
            role=MemberRole(row["role"]),
            invited_by=row["invited_by"],
            token=row["token"],
            status=InvitationStatus(row["status"]),
            expires_at=row["expires_at"],
            created_at=row["created_at"],
        )

    async def get_by_id(self, invitation_id: UUID) -> Invitation | None:
        """Get an invitation by its unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.invitations WHERE id = $1",
                invitation_id,
            )
            return self._row_to_invitation(row) if row else None

    async def get_by_token(self, token: str) -> Invitation | None:
        """Get an invitation by its unique token."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.invitations WHERE token = $1",
                token,
            )
            return self._row_to_invitation(row) if row else None

    async def get_pending_for_email(self, email: str) -> list[Invitation]:
        """Get all pending invitations for an email address."""
        async with self._pool.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM public.invitations 
                WHERE email = $1 AND status = 'pending' AND expires_at > NOW()
                ORDER BY created_at DESC
                """,
                email.lower(),
            )
            return [self._row_to_invitation(row) for row in rows]

    async def get_organization_invitations(
        self, org_id: UUID, status: InvitationStatus | None = None
    ) -> list[Invitation]:
        """Get all invitations for an organization, optionally filtered by status."""
        async with self._pool.pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM public.invitations 
                    WHERE organization_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    org_id,
                    status.value,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM public.invitations 
                    WHERE organization_id = $1
                    ORDER BY created_at DESC
                    """,
                    org_id,
                )
            return [self._row_to_invitation(row) for row in rows]

    async def create(self, invitation: Invitation) -> Invitation:
        """Create a new invitation."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.invitations 
                (id, email, organization_id, role, invited_by, token, status, expires_at, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                invitation.id,
                invitation.email.lower(),
                invitation.organization_id,
                invitation.role.value,
                invitation.invited_by,
                invitation.token,
                invitation.status.value,
                invitation.expires_at,
                invitation.created_at,
            )
            return invitation

    async def update(self, invitation: Invitation) -> Invitation:
        """Update an invitation (e.g., change status)."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.invitations SET status = $2 WHERE id = $1",
                invitation.id,
                invitation.status.value,
            )
            return invitation

    async def delete(self, invitation_id: UUID) -> None:
        """Delete an invitation."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM public.invitations WHERE id = $1",
                invitation_id,
            )

    async def exists_for_email_and_org(self, email: str, org_id: UUID) -> bool:
        """Check if a pending invitation already exists for this email and org."""
        async with self._pool.pool.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM public.invitations 
                    WHERE email = $1 AND organization_id = $2 
                    AND status = 'pending' AND expires_at > NOW()
                )
                """,
                email.lower(),
                org_id,
            )
            return result


class PostgresBillingAccountRepository:
    """PostgreSQL implementation of BillingAccountRepository."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_billing_account(self, row: asyncpg.Record) -> BillingAccount:
        """Convert a database row to a BillingAccount entity."""
        return BillingAccount(
            id=row["id"],
            account_type=AccountType(row["account_type"]),
            user_id=row["user_id"],
            organization_id=row["organization_id"],
            credits=row["credits"],
            lifetime_credits=row["lifetime_credits"],
            lifetime_usage=row["lifetime_usage"],
            free_tier_remaining=row["free_tier_remaining"],
            free_tier_reset_at=row["free_tier_reset_at"],
            stripe_customer_id=row["stripe_customer_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_by_id(self, account_id: UUID) -> BillingAccount | None:
        """Get a billing account by its unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.billing_accounts WHERE id = $1",
                account_id,
            )
            return self._row_to_billing_account(row) if row else None

    async def get_by_user_id(self, user_id: UUID) -> BillingAccount | None:
        """Get the billing account for a user."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.billing_accounts WHERE user_id = $1",
                user_id,
            )
            return self._row_to_billing_account(row) if row else None

    async def get_by_organization_id(self, org_id: UUID) -> BillingAccount | None:
        """Get the billing account for an organization."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.billing_accounts WHERE organization_id = $1",
                org_id,
            )
            return self._row_to_billing_account(row) if row else None

    async def create(self, account: BillingAccount) -> BillingAccount:
        """Create a new billing account."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.billing_accounts 
                (id, account_type, user_id, organization_id, credits, lifetime_credits,
                 lifetime_usage, free_tier_remaining, free_tier_reset_at, 
                 stripe_customer_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                account.id,
                account.account_type.value,
                account.user_id,
                account.organization_id,
                account.credits,
                account.lifetime_credits,
                account.lifetime_usage,
                account.free_tier_remaining,
                account.free_tier_reset_at,
                account.stripe_customer_id,
                account.created_at,
                account.updated_at,
            )
            return account

    async def update(self, account: BillingAccount) -> BillingAccount:
        """Update an existing billing account."""
        account.updated_at = datetime.now(UTC)
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.billing_accounts
                SET credits = $2, lifetime_credits = $3, lifetime_usage = $4,
                    free_tier_remaining = $5, free_tier_reset_at = $6,
                    stripe_customer_id = $7, updated_at = $8
                WHERE id = $1
                """,
                account.id,
                account.credits,
                account.lifetime_credits,
                account.lifetime_usage,
                account.free_tier_remaining,
                account.free_tier_reset_at,
                account.stripe_customer_id,
                account.updated_at,
            )
            return account

    async def get_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> BillingAccount | None:
        """Get a billing account by its Stripe customer ID."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.billing_accounts WHERE stripe_customer_id = $1",
                stripe_customer_id,
            )
            return self._row_to_billing_account(row) if row else None


class PostgresTransactionRepository:
    """PostgreSQL implementation of TransactionRepository."""

    def __init__(self, pool: PostgresConnectionPool):
        self._pool = pool

    def _row_to_transaction(self, row: asyncpg.Record) -> CreditTransaction:
        """Convert a database row to a CreditTransaction entity."""
        return CreditTransaction(
            id=row["id"],
            billing_account_id=row["billing_account_id"],
            amount=row["amount"],
            transaction_type=TransactionType(row["transaction_type"]),
            balance_after=row["balance_after"],
            reference_id=row["reference_id"],
            description=row["description"],
            metadata=row["metadata"],
            created_at=row["created_at"],
        )

    async def get_by_id(self, transaction_id: UUID) -> CreditTransaction | None:
        """Get a transaction by its unique identifier."""
        async with self._pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.credit_transactions WHERE id = $1",
                transaction_id,
            )
            return self._row_to_transaction(row) if row else None

    async def get_by_billing_account(
        self,
        billing_account_id: UUID,
        limit: int = 50,
        offset: int = 0,
        transaction_type: TransactionType | None = None,
    ) -> list[CreditTransaction]:
        """Get transactions for a billing account with pagination."""
        async with self._pool.pool.acquire() as conn:
            if transaction_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM public.credit_transactions 
                    WHERE billing_account_id = $1 AND transaction_type = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    billing_account_id,
                    transaction_type.value,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM public.credit_transactions 
                    WHERE billing_account_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    billing_account_id,
                    limit,
                    offset,
                )
            return [self._row_to_transaction(row) for row in rows]

    async def get_by_date_range(
        self,
        billing_account_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CreditTransaction]:
        """Get transactions within a date range."""
        async with self._pool.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM public.credit_transactions 
                WHERE billing_account_id = $1 AND created_at >= $2 AND created_at <= $3
                ORDER BY created_at DESC
                """,
                billing_account_id,
                start_date,
                end_date,
            )
            return [self._row_to_transaction(row) for row in rows]

    async def create(self, transaction: CreditTransaction) -> CreditTransaction:
        """Create a new transaction record."""
        async with self._pool.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.credit_transactions 
                (id, billing_account_id, amount, transaction_type, balance_after,
                 reference_id, description, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                transaction.id,
                transaction.billing_account_id,
                transaction.amount,
                transaction.transaction_type.value,
                transaction.balance_after,
                transaction.reference_id,
                transaction.description,
                transaction.metadata,
                transaction.created_at,
            )
            return transaction

    async def get_total_by_type(
        self,
        billing_account_id: UUID,
        transaction_type: TransactionType,
        since: datetime | None = None,
    ) -> int:
        """Get the total amount for a transaction type, optionally since a date."""
        async with self._pool.pool.acquire() as conn:
            if since:
                total = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(amount), 0) FROM public.credit_transactions 
                    WHERE billing_account_id = $1 AND transaction_type = $2 AND created_at >= $3
                    """,
                    billing_account_id,
                    transaction_type.value,
                    since,
                )
            else:
                total = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(amount), 0) FROM public.credit_transactions 
                    WHERE billing_account_id = $1 AND transaction_type = $2
                    """,
                    billing_account_id,
                    transaction_type.value,
                )
            return total or 0
