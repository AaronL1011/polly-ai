"""Auth API routes for session management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from democrata_server.api.http.deps import get_auth_provider, get_current_user
from democrata_server.domain.auth.entities import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class UserResponse(BaseModel):
    """User information returned by auth endpoints."""

    id: str
    email: str
    name: str | None
    avatar_url: str | None
    email_verified: bool

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            email_verified=user.email_verified,
        )


class SessionResponse(BaseModel):
    """Session information response."""

    user: UserResponse
    expires_at: str | None = None


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response from token refresh."""

    access_token: str
    refresh_token: str
    user: UserResponse
    expires_at: str


@router.get("/session", response_model=SessionResponse)
async def get_session(
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionResponse:
    """
    Get the current session and user information.

    Validates the access token from the Authorization header and returns
    the associated user information.
    """
    return SessionResponse(user=UserResponse.from_entity(current_user))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_session(
    request: RefreshRequest,
    auth_provider=Depends(get_auth_provider),
) -> RefreshResponse:
    """
    Refresh an expired session using a refresh token.

    Returns new access and refresh tokens along with updated user info.
    """
    session = await auth_provider.refresh_session(request.refresh_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return RefreshResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user=UserResponse.from_entity(session.user),
        expires_at=session.expires_at.isoformat(),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: Annotated[str | None, Header()] = None,
    auth_provider=Depends(get_auth_provider),
) -> None:
    """
    Invalidate the current session.

    Signs out the user and revokes the session on the auth provider.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    await auth_provider.sign_out(token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Get the current authenticated user's profile.

    Alias for /session that returns just the user without session metadata.
    """
    return UserResponse.from_entity(current_user)
