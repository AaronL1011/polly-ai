from datetime import datetime
from typing import Protocol
from uuid import UUID

from .entities import AnonymousSession, UsageEvent, UsageEventType


class UsageEventRepository(Protocol):
    """Repository for usage event data."""

    async def create(self, event: UsageEvent) -> UsageEvent:
        """Log a usage event."""
        ...

    async def get_by_id(self, event_id: UUID) -> UsageEvent | None:
        """Get a usage event by its unique identifier."""
        ...

    async def get_by_billing_account(
        self,
        billing_account_id: UUID,
        limit: int = 50,
        offset: int = 0,
        event_type: UsageEventType | None = None,
    ) -> list[UsageEvent]:
        """Get usage events for a billing account with pagination."""
        ...

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UsageEvent]:
        """Get usage events performed by a specific user (for org member breakdown)."""
        ...

    async def get_by_date_range(
        self,
        billing_account_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[UsageEvent]:
        """Get usage events within a date range."""
        ...

    async def get_total_credits_charged(
        self,
        billing_account_id: UUID,
        since: datetime | None = None,
    ) -> int:
        """Get total credits charged for a billing account."""
        ...

    async def get_by_query_hash(
        self,
        query_hash: str,
        billing_account_id: UUID | None = None,
    ) -> UsageEvent | None:
        """Find a cached query event by its hash."""
        ...


class AnonymousSessionStore(Protocol):
    """Store for anonymous session tracking (rate limiting)."""

    async def get(self, session_id: str) -> AnonymousSession | None:
        """Get an anonymous session by its ID."""
        ...

    async def create(self, session: AnonymousSession) -> AnonymousSession:
        """Create a new anonymous session."""
        ...

    async def update(self, session: AnonymousSession) -> AnonymousSession:
        """Update an anonymous session."""
        ...

    async def get_or_create(self, session_id: str) -> AnonymousSession:
        """Get an existing session or create a new one."""
        ...


# Backwards compatibility alias
UsageLogger = UsageEventRepository
