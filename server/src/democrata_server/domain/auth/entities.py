from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class User:
    """Represents an authenticated user in the system."""

    id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    email_verified: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Session:
    """Server-side representation of a Supabase auth session."""

    access_token: str
    refresh_token: str
    user: User
    expires_at: datetime
    created_at: datetime = field(default_factory=utc_now)

    @property
    def is_expired(self) -> bool:
        return utc_now() > self.expires_at
