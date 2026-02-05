"""Supabase auth adapter implementing the AuthProvider protocol."""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx

from democrata_server.domain.auth.entities import Session, User

logger = logging.getLogger(__name__)


class SupabaseAuthProvider:
    """
    Supabase-based implementation of the AuthProvider protocol.

    Validates JWTs and manages sessions through Supabase's GoTrue API.
    Isolated behind the AuthProvider protocol for future provider swaps.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_anon_key: str,
        supabase_service_key: str | None = None,
    ):
        self._supabase_url = supabase_url.rstrip("/")
        self._anon_key = supabase_anon_key
        self._service_key = supabase_service_key
        self._auth_url = f"{self._supabase_url}/auth/v1"

    def _get_headers(self, access_token: str | None = None) -> dict[str, str]:
        """Build headers for Supabase API requests."""
        headers = {
            "apikey": self._anon_key,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _get_admin_headers(self) -> dict[str, str]:
        """Build headers for admin operations using service key."""
        if not self._service_key:
            raise ValueError("Service key required for admin operations")
        return {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }

    def _parse_user(self, user_data: dict) -> User:
        """Parse Supabase user response into domain User entity."""
        user_meta = user_data.get("user_metadata", {})
        return User(
            id=UUID(user_data["id"]),
            email=user_data["email"],
            name=user_meta.get("full_name") or user_meta.get("name"),
            avatar_url=user_meta.get("avatar_url"),
            email_verified=user_data.get("email_confirmed_at") is not None,
            created_at=datetime.fromisoformat(
                user_data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                user_data.get("updated_at", user_data["created_at"]).replace(
                    "Z", "+00:00"
                )
            ),
        )

    def _parse_session(self, session_data: dict, user: User) -> Session:
        """Parse Supabase session response into domain Session entity."""
        expires_at_ts = session_data.get("expires_at", 0)
        return Session(
            access_token=session_data["access_token"],
            refresh_token=session_data["refresh_token"],
            user=user,
            expires_at=datetime.fromtimestamp(expires_at_ts, tz=UTC),
        )

    async def get_user(self, token: str) -> User | None:
        """
        Extract and validate user from an access token.

        Makes a request to Supabase's /user endpoint to validate the token
        and retrieve the current user data.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._auth_url}/user",
                    headers=self._get_headers(token),
                )
                if response.status_code == 401:
                    logger.debug("Invalid or expired token")
                    return None
                response.raise_for_status()
                return self._parse_user(response.json())
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to get user: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error getting user: {e}")
                return None

    async def verify_session(self, session_token: str) -> Session | None:
        """
        Verify a session token and return the full session if valid.

        The session_token here is the access_token. We validate it and
        return the session info if valid.
        """
        user = await self.get_user(session_token)
        if not user:
            return None

        # For session verification, we create a minimal session
        # The refresh_token would come from the client in a real flow
        return Session(
            access_token=session_token,
            refresh_token="",  # Client manages refresh token
            user=user,
            expires_at=datetime.now(UTC),  # Expiry checked by Supabase
        )

    async def refresh_session(self, refresh_token: str) -> Session | None:
        """
        Refresh an expired session using a refresh token.

        Returns a new Session with fresh access_token and refresh_token.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._auth_url}/token?grant_type=refresh_token",
                    headers=self._get_headers(),
                    json={"refresh_token": refresh_token},
                )
                if response.status_code == 401:
                    logger.debug("Invalid refresh token")
                    return None
                response.raise_for_status()

                data = response.json()
                user = self._parse_user(data["user"])
                return self._parse_session(data, user)
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to refresh session: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error refreshing session: {e}")
                return None

    async def sign_out(self, session_token: str) -> None:
        """
        Invalidate a session, signing the user out.

        This revokes the session on Supabase's side.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._auth_url}/logout",
                    headers=self._get_headers(session_token),
                )
                response.raise_for_status()
                logger.debug("Session signed out successfully")
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to sign out: {e}")
            except Exception as e:
                logger.error(f"Unexpected error signing out: {e}")

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """
        Get a user by ID using admin privileges.

        Requires service_key to be configured.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._auth_url}/admin/users/{user_id}",
                    headers=self._get_admin_headers(),
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return self._parse_user(response.json())
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to get user by ID: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error getting user by ID: {e}")
                return None
