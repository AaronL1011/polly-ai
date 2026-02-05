from typing import Protocol
from uuid import UUID

from .entities import Invitation, InvitationStatus, Membership, Organization


class OrganizationRepository(Protocol):
    """Repository for organization data."""

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        """Get an organization by its unique identifier."""
        ...

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get an organization by its URL-friendly slug."""
        ...

    async def create(self, organization: Organization) -> Organization:
        """Create a new organization."""
        ...

    async def update(self, organization: Organization) -> Organization:
        """Update an existing organization."""
        ...

    async def delete(self, org_id: UUID) -> None:
        """Delete an organization and all associated data."""
        ...

    async def slug_exists(self, slug: str) -> bool:
        """Check if a slug is already in use."""
        ...


class MembershipRepository(Protocol):
    """Repository for organization membership data."""

    async def get_by_id(self, membership_id: UUID) -> Membership | None:
        """Get a membership by its unique identifier."""
        ...

    async def get_user_memberships(self, user_id: UUID) -> list[Membership]:
        """Get all memberships for a user."""
        ...

    async def get_organization_members(self, org_id: UUID) -> list[Membership]:
        """Get all memberships in an organization."""
        ...

    async def get_membership(
        self, user_id: UUID, org_id: UUID
    ) -> Membership | None:
        """Get a specific user's membership in an organization."""
        ...

    async def create(self, membership: Membership) -> Membership:
        """Create a new membership."""
        ...

    async def update(self, membership: Membership) -> Membership:
        """Update an existing membership (e.g., change role)."""
        ...

    async def delete(self, membership_id: UUID) -> None:
        """Remove a membership."""
        ...

    async def count_members(self, org_id: UUID) -> int:
        """Count the number of members in an organization."""
        ...


class InvitationRepository(Protocol):
    """Repository for organization invitations."""

    async def get_by_id(self, invitation_id: UUID) -> Invitation | None:
        """Get an invitation by its unique identifier."""
        ...

    async def get_by_token(self, token: str) -> Invitation | None:
        """Get an invitation by its unique token."""
        ...

    async def get_pending_for_email(self, email: str) -> list[Invitation]:
        """Get all pending invitations for an email address."""
        ...

    async def get_organization_invitations(
        self, org_id: UUID, status: InvitationStatus | None = None
    ) -> list[Invitation]:
        """Get all invitations for an organization, optionally filtered by status."""
        ...

    async def create(self, invitation: Invitation) -> Invitation:
        """Create a new invitation."""
        ...

    async def update(self, invitation: Invitation) -> Invitation:
        """Update an invitation (e.g., change status)."""
        ...

    async def delete(self, invitation_id: UUID) -> None:
        """Delete an invitation."""
        ...

    async def exists_for_email_and_org(self, email: str, org_id: UUID) -> bool:
        """Check if a pending invitation already exists for this email and org."""
        ...
