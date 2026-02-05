from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class OrganizationPlan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

    def can_manage_members(self) -> bool:
        return self in (MemberRole.OWNER, MemberRole.ADMIN)

    def can_manage_billing(self) -> bool:
        return self in (MemberRole.OWNER, MemberRole.ADMIN)

    def can_invite(self) -> bool:
        return self in (MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER)


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class Organization:
    """Represents an organization that groups users and manages shared billing."""

    id: UUID
    name: str
    slug: str  # URL-friendly identifier
    owner_id: UUID
    billing_email: str
    plan: OrganizationPlan = OrganizationPlan.FREE
    max_seats: int = 5
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        name: str,
        slug: str,
        owner_id: UUID,
        billing_email: str,
        plan: OrganizationPlan = OrganizationPlan.FREE,
        max_seats: int = 5,
    ) -> "Organization":
        now = utc_now()
        return cls(
            id=uuid4(),
            name=name,
            slug=slug,
            owner_id=owner_id,
            billing_email=billing_email,
            plan=plan,
            max_seats=max_seats,
            created_at=now,
            updated_at=now,
        )


@dataclass
class Membership:
    """Represents a user's membership in an organization."""

    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MemberRole
    invited_by: UUID | None = None
    joined_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create_owner(cls, user_id: UUID, organization_id: UUID) -> "Membership":
        return cls(
            id=uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            role=MemberRole.OWNER,
            invited_by=None,
            joined_at=utc_now(),
        )

    @classmethod
    def create(
        cls,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        invited_by: UUID | None = None,
    ) -> "Membership":
        return cls(
            id=uuid4(),
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
            joined_at=utc_now(),
        )


@dataclass
class Invitation:
    """Represents a pending invitation to join an organization."""

    id: UUID
    email: str
    organization_id: UUID
    role: MemberRole
    invited_by: UUID
    token: str
    status: InvitationStatus = InvitationStatus.PENDING
    expires_at: datetime = field(
        default_factory=lambda: utc_now() + timedelta(days=7)
    )
    created_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        email: str,
        organization_id: UUID,
        role: MemberRole,
        invited_by: UUID,
        token: str | None = None,
        expires_in_days: int = 7,
    ) -> "Invitation":
        now = utc_now()
        return cls(
            id=uuid4(),
            email=email.lower(),
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
            token=token or str(uuid4()),
            status=InvitationStatus.PENDING,
            expires_at=now + timedelta(days=expires_in_days),
            created_at=now,
        )

    @property
    def is_expired(self) -> bool:
        return utc_now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.status == InvitationStatus.PENDING and not self.is_expired
