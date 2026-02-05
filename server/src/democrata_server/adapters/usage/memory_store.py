from datetime import UTC, datetime, timedelta
from uuid import UUID

from democrata_server.domain.billing.entities import BillingAccount
from democrata_server.domain.ingestion.entities import Job
from democrata_server.domain.usage.entities import AnonymousSession


class InMemoryJobStore:
    def __init__(self):
        self._jobs: dict[UUID, Job] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.id] = job

    async def get(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)


class InMemoryAnonymousSessionStore:
    """In-memory store for anonymous session tracking (rate limiting)."""

    def __init__(self, daily_limit: int = 10):
        self._sessions: dict[str, AnonymousSession] = {}
        self.daily_limit = daily_limit

    async def get(self, session_id: str) -> AnonymousSession | None:
        session = self._sessions.get(session_id)
        if session:
            session.check_and_reset()
        return session

    async def create(self, session: AnonymousSession) -> AnonymousSession:
        self._sessions[session.session_id] = session
        return session

    async def update(self, session: AnonymousSession) -> AnonymousSession:
        self._sessions[session.session_id] = session
        return session

    async def get_or_create(self, session_id: str) -> AnonymousSession:
        session = await self.get(session_id)
        if session is None:
            session = AnonymousSession.create(session_id, self.daily_limit)
            await self.create(session)
        return session


class InMemoryBillingAccountStore:
    """In-memory store for billing accounts (for development/testing)."""

    def __init__(self):
        self._accounts_by_id: dict[UUID, BillingAccount] = {}
        self._accounts_by_user: dict[UUID, BillingAccount] = {}
        self._accounts_by_org: dict[UUID, BillingAccount] = {}

    async def get_by_id(self, account_id: UUID) -> BillingAccount | None:
        return self._accounts_by_id.get(account_id)

    async def get_by_user_id(self, user_id: UUID) -> BillingAccount | None:
        return self._accounts_by_user.get(user_id)

    async def get_by_organization_id(self, org_id: UUID) -> BillingAccount | None:
        return self._accounts_by_org.get(org_id)

    async def create(self, account: BillingAccount) -> BillingAccount:
        self._accounts_by_id[account.id] = account
        if account.user_id:
            self._accounts_by_user[account.user_id] = account
        if account.organization_id:
            self._accounts_by_org[account.organization_id] = account
        return account

    async def update(self, account: BillingAccount) -> BillingAccount:
        return await self.create(account)  # Same operation for in-memory

    async def get_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> BillingAccount | None:
        for account in self._accounts_by_id.values():
            if account.stripe_customer_id == stripe_customer_id:
                return account
        return None

    async def get_or_create_for_user(self, user_id: UUID) -> BillingAccount:
        """Get or create a billing account for a user."""
        account = await self.get_by_user_id(user_id)
        if account is None:
            account = BillingAccount.create_for_user(user_id)
            await self.create(account)
        return account
