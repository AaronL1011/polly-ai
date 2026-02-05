"""Organization management API routes."""

import logging
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from democrata_server.api.http.deps import (
    ensure_user_exists_in_local_db,
    get_billing_account_repository,
    get_current_user,
    get_invitation_repository,
    get_membership_repository,
    get_organization_repository,
)
from democrata_server.domain.auth.entities import User
from democrata_server.domain.billing.entities import BillingAccount
from democrata_server.domain.orgs.entities import (
    Invitation,
    InvitationStatus,
    Membership,
    MemberRole,
    Organization,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orgs", tags=["organizations"])


# --- Request/Response Models ---


class OrganizationResponse(BaseModel):
    """Organization information response."""

    id: str
    name: str
    slug: str
    owner_id: str
    billing_email: str
    plan: str
    max_seats: int
    member_count: int | None = None

    @classmethod
    def from_entity(
        cls, org: Organization, member_count: int | None = None
    ) -> "OrganizationResponse":
        return cls(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            owner_id=str(org.owner_id),
            billing_email=org.billing_email,
            plan=org.plan.value,
            max_seats=org.max_seats,
            member_count=member_count,
        )


class CreateOrganizationRequest(BaseModel):
    """Request to create a new organization."""

    name: str
    slug: str
    billing_email: EmailStr

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        slug = v.lower().strip()
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$", slug):
            raise ValueError(
                "Slug must be 3-40 characters, lowercase alphanumeric with hyphens, "
                "cannot start or end with a hyphen"
            )
        return slug


class UpdateOrganizationRequest(BaseModel):
    """Request to update an organization."""

    name: str | None = None
    billing_email: EmailStr | None = None


class MembershipResponse(BaseModel):
    """Membership information response."""

    id: str
    user_id: str
    organization_id: str
    role: str
    joined_at: str
    # User info may be populated for member lists
    user_email: str | None = None
    user_name: str | None = None

    @classmethod
    def from_entity(
        cls,
        membership: Membership,
        user_email: str | None = None,
        user_name: str | None = None,
    ) -> "MembershipResponse":
        return cls(
            id=str(membership.id),
            user_id=str(membership.user_id),
            organization_id=str(membership.organization_id),
            role=membership.role.value,
            joined_at=membership.joined_at.isoformat(),
            user_email=user_email,
            user_name=user_name,
        )


class InviteMemberRequest(BaseModel):
    """Request to invite a member to an organization."""

    email: EmailStr
    role: str = "member"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ["admin", "member", "viewer"]
        if v.lower() not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v.lower()


class InvitationResponse(BaseModel):
    """Invitation information response."""

    id: str
    email: str
    organization_id: str
    role: str
    status: str
    expires_at: str
    created_at: str

    @classmethod
    def from_entity(cls, invitation: Invitation) -> "InvitationResponse":
        return cls(
            id=str(invitation.id),
            email=invitation.email,
            organization_id=str(invitation.organization_id),
            role=invitation.role.value,
            status=invitation.status.value,
            expires_at=invitation.expires_at.isoformat(),
            created_at=invitation.created_at.isoformat(),
        )


class UpdateMemberRoleRequest(BaseModel):
    """Request to update a member's role."""

    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ["admin", "member", "viewer"]
        if v.lower() not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v.lower()


# --- Organization CRUD ---


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    membership_repo=Depends(get_membership_repository),
    org_repo=Depends(get_organization_repository),
) -> list[OrganizationResponse]:
    """
    List all organizations the current user belongs to.
    """
    memberships = await membership_repo.get_user_memberships(current_user.id)
    orgs = []
    for membership in memberships:
        org = await org_repo.get_by_id(membership.organization_id)
        if org:
            member_count = await membership_repo.count_members(org.id)
            orgs.append(OrganizationResponse.from_entity(org, member_count))
    return orgs


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
    billing_repo=Depends(get_billing_account_repository),
) -> OrganizationResponse:
    """
    Create a new organization.

    The current user becomes the owner and a billing account is created.
    """
    # Check slug availability
    if await org_repo.slug_exists(request.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already in use",
        )

    # Ensure user exists in local database (for local dev with Supabase auth)
    await ensure_user_exists_in_local_db(current_user)

    # Create organization
    org = Organization.create(
        name=request.name,
        slug=request.slug,
        owner_id=current_user.id,
        billing_email=request.billing_email,
    )
    await org_repo.create(org)

    # Create owner membership
    owner_membership = Membership.create_owner(
        user_id=current_user.id,
        organization_id=org.id,
    )
    await membership_repo.create(owner_membership)

    # Create billing account for the organization
    billing_account = BillingAccount.create_for_organization(org.id)
    await billing_repo.create(billing_account)

    return OrganizationResponse.from_entity(org, member_count=1)


@router.get("/{slug}", response_model=OrganizationResponse)
async def get_organization(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> OrganizationResponse:
    """
    Get organization details by slug.

    User must be a member of the organization.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Verify user is a member
    membership = await membership_repo.get_membership(current_user.id, org.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    member_count = await membership_repo.count_members(org.id)
    return OrganizationResponse.from_entity(org, member_count)


@router.patch("/{slug}", response_model=OrganizationResponse)
async def update_organization(
    slug: str,
    request: UpdateOrganizationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> OrganizationResponse:
    """
    Update organization details.

    Only owners and admins can update organization settings.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permissions
    membership = await membership_repo.get_membership(current_user.id, org.id)
    if not membership or not membership.role.can_manage_billing():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update organization",
        )

    # Apply updates
    if request.name:
        org.name = request.name
    if request.billing_email:
        org.billing_email = request.billing_email

    await org_repo.update(org)
    member_count = await membership_repo.count_members(org.id)
    return OrganizationResponse.from_entity(org, member_count)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> None:
    """
    Delete an organization.

    Only the owner can delete an organization.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only owner can delete
    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete an organization",
        )

    await org_repo.delete(org.id)


# --- Member Management ---


@router.get("/{slug}/members", response_model=list[MembershipResponse])
async def list_members(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> list[MembershipResponse]:
    """
    List all members of an organization.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Verify user is a member
    user_membership = await membership_repo.get_membership(current_user.id, org.id)
    if not user_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    memberships = await membership_repo.get_organization_members(org.id)
    return [MembershipResponse.from_entity(m) for m in memberships]


@router.post("/{slug}/members", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    slug: str,
    request: InviteMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
    invitation_repo=Depends(get_invitation_repository),
) -> InvitationResponse:
    """
    Invite a new member to the organization.

    Creates a pending invitation that the user can accept.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permissions
    user_membership = await membership_repo.get_membership(current_user.id, org.id)
    if not user_membership or not user_membership.role.can_invite():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to invite members",
        )

    # Check seat limit
    member_count = await membership_repo.count_members(org.id)
    if member_count >= org.max_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization has reached the maximum of {org.max_seats} members",
        )

    # Check for existing pending invitation
    if await invitation_repo.exists_for_email_and_org(request.email, org.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invitation has already been sent to this email",
        )

    # Create invitation
    invitation = Invitation.create(
        email=request.email,
        organization_id=org.id,
        role=MemberRole(request.role),
        invited_by=current_user.id,
    )
    await invitation_repo.create(invitation)

    # TODO: Send invitation email

    return InvitationResponse.from_entity(invitation)


@router.get("/{slug}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    slug: str,
    status_filter: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
    invitation_repo=Depends(get_invitation_repository),
) -> list[InvitationResponse]:
    """
    List all invitations for an organization.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permissions - only admins/owners can see invitations
    user_membership = await membership_repo.get_membership(current_user.id, org.id)
    if not user_membership or not user_membership.role.can_manage_members():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view invitations",
        )

    invitation_status = InvitationStatus(status_filter) if status_filter else None
    invitations = await invitation_repo.get_organization_invitations(
        org.id, invitation_status
    )
    return [InvitationResponse.from_entity(i) for i in invitations]


@router.patch("/{slug}/members/{member_id}", response_model=MembershipResponse)
async def update_member_role(
    slug: str,
    member_id: UUID,
    request: UpdateMemberRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> MembershipResponse:
    """
    Update a member's role.

    Only owners and admins can change member roles. Owners cannot be demoted.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permissions
    user_membership = await membership_repo.get_membership(current_user.id, org.id)
    if not user_membership or not user_membership.role.can_manage_members():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage members",
        )

    # Get target membership
    target_membership = await membership_repo.get_by_id(member_id)
    if not target_membership or target_membership.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Cannot change owner's role
    if target_membership.role == MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change the owner's role",
        )

    target_membership.role = MemberRole(request.role)
    await membership_repo.update(target_membership)
    return MembershipResponse.from_entity(target_membership)


@router.delete("/{slug}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    slug: str,
    member_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    org_repo=Depends(get_organization_repository),
    membership_repo=Depends(get_membership_repository),
) -> None:
    """
    Remove a member from the organization.

    Members can remove themselves. Admins and owners can remove other members.
    """
    org = await org_repo.get_by_slug(slug)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get target membership
    target_membership = await membership_repo.get_by_id(member_id)
    if not target_membership or target_membership.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Cannot remove owner
    if target_membership.role == MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the organization owner",
        )

    # Check permissions - allow self-removal or admin/owner
    is_self_removal = target_membership.user_id == current_user.id
    user_membership = await membership_repo.get_membership(current_user.id, org.id)

    if not is_self_removal:
        if not user_membership or not user_membership.role.can_manage_members():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to remove members",
            )

    await membership_repo.delete(target_membership.id)


# --- Invitation Accept/Decline ---


@router.post("/invitations/{token}/accept", response_model=MembershipResponse)
async def accept_invitation(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    invitation_repo=Depends(get_invitation_repository),
    membership_repo=Depends(get_membership_repository),
    org_repo=Depends(get_organization_repository),
) -> MembershipResponse:
    """
    Accept an invitation to join an organization.
    """
    invitation = await invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify invitation is valid
    if not invitation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired or been revoked",
        )

    # Verify email matches
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address",
        )

    # Check if already a member
    existing = await membership_repo.get_membership(
        current_user.id, invitation.organization_id
    )
    if existing:
        # Update invitation status and return existing membership
        invitation.status = InvitationStatus.ACCEPTED
        await invitation_repo.update(invitation)
        return MembershipResponse.from_entity(existing)

    # Check seat limit
    org = await org_repo.get_by_id(invitation.organization_id)
    if org:
        member_count = await membership_repo.count_members(org.id)
        if member_count >= org.max_seats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization has reached maximum capacity",
            )

    # Ensure user exists in local database (for local dev with Supabase auth)
    await ensure_user_exists_in_local_db(current_user)

    # Create membership
    membership = Membership.create(
        user_id=current_user.id,
        organization_id=invitation.organization_id,
        role=invitation.role,
        invited_by=invitation.invited_by,
    )
    await membership_repo.create(membership)

    # Update invitation status
    invitation.status = InvitationStatus.ACCEPTED
    await invitation_repo.update(invitation)

    return MembershipResponse.from_entity(membership)


@router.post("/invitations/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_invitation(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    invitation_repo=Depends(get_invitation_repository),
) -> None:
    """
    Decline an invitation to join an organization.
    """
    invitation = await invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify email matches
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address",
        )

    invitation.status = InvitationStatus.DECLINED
    await invitation_repo.update(invitation)
