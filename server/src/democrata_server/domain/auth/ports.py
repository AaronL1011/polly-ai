from typing import Protocol
from uuid import UUID

from .entities import Session, User


class AuthProvider(Protocol):
    """Technology-agnostic auth interface for session and token management."""

    async def get_user(self, token: str) -> User | None:
        """Extract and validate user from an access token."""
        ...

    async def verify_session(self, session_token: str) -> Session | None:
        """Verify a session token and return the full session if valid."""
        ...

    async def refresh_session(self, refresh_token: str) -> Session | None:
        """Refresh an expired session using a refresh token."""
        ...

    async def sign_out(self, session_token: str) -> None:
        """Invalidate a session, signing the user out."""
        ...


class UserRepository(Protocol):
    """Repository for user profile data (extends Supabase auth.users)."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by their unique identifier."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        ...

    async def create(self, user: User) -> User:
        """Create a new user profile."""
        ...

    async def update(self, user: User) -> User:
        """Update an existing user profile."""
        ...
