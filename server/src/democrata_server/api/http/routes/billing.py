"""Billing API routes for credit management and payments."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from democrata_server.api.http.deps import (
    ensure_user_exists_in_local_db,
    get_billing_account_repository,
    get_current_user,
    get_current_user_optional,
    get_membership_repository,
    get_organization_repository,
    get_payment_provider,
    get_transaction_repository,
)
from democrata_server.domain.auth.entities import User
from democrata_server.domain.billing.entities import (
    CREDIT_PACKS,
    BillingAccount,
    CreditPack,
    CreditTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# --- Request/Response Models ---


class CreditPackResponse(BaseModel):
    """Available credit pack for purchase."""

    credits: int
    price_cents: int
    price_dollars: float


class BillingAccountResponse(BaseModel):
    """Billing account information."""

    id: str
    account_type: str
    credits: int
    free_tier_remaining: int
    free_tier_reset_at: str | None
    lifetime_credits: int
    lifetime_usage: int
    has_stripe_customer: bool

    @classmethod
    def from_entity(cls, account: BillingAccount) -> "BillingAccountResponse":
        return cls(
            id=str(account.id),
            account_type=account.account_type.value,
            credits=account.credits,
            free_tier_remaining=account.free_tier_remaining,
            free_tier_reset_at=(
                account.free_tier_reset_at.isoformat()
                if account.free_tier_reset_at
                else None
            ),
            lifetime_credits=account.lifetime_credits,
            lifetime_usage=account.lifetime_usage,
            has_stripe_customer=account.stripe_customer_id is not None,
        )


class TransactionResponse(BaseModel):
    """Credit transaction record."""

    id: str
    amount: int
    transaction_type: str
    balance_after: int
    description: str | None
    reference_id: str | None
    created_at: str

    @classmethod
    def from_entity(cls, tx: CreditTransaction) -> "TransactionResponse":
        return cls(
            id=str(tx.id),
            amount=tx.amount,
            transaction_type=tx.transaction_type.value,
            balance_after=tx.balance_after,
            description=tx.description,
            reference_id=tx.reference_id,
            created_at=tx.created_at.isoformat(),
        )


class PurchaseRequest(BaseModel):
    """Request to purchase credits."""

    credit_pack_index: int
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    session_id: str
    checkout_url: str
    expires_at: str


class UsageSummaryResponse(BaseModel):
    """Summary of credit usage."""

    total_usage: int
    total_purchases: int
    period_start: str
    period_end: str


# --- Account & Balance ---


@router.get("/packs", response_model=list[CreditPackResponse])
async def list_credit_packs() -> list[CreditPackResponse]:
    """
    List available credit packs for purchase.
    """
    return [
        CreditPackResponse(
            credits=pack.credits,
            price_cents=pack.price_cents,
            price_dollars=pack.price_dollars,
        )
        for pack in CREDIT_PACKS
    ]


@router.get("/account", response_model=BillingAccountResponse)
async def get_billing_account(
    current_user: Annotated[User, Depends(get_current_user)],
    x_organization_id: Annotated[str | None, Header()] = None,
    billing_repo=Depends(get_billing_account_repository),
    membership_repo=Depends(get_membership_repository),
) -> BillingAccountResponse:
    """
    Get the current billing account.

    If X-Organization-Id header is provided, returns the org's billing account
    (user must be a member). Otherwise returns the user's personal billing account.
    """
    if x_organization_id:
        # Verify user is a member of the org
        org_id = UUID(x_organization_id)
        membership = await membership_repo.get_membership(current_user.id, org_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

        account = await billing_repo.get_by_organization_id(org_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization billing account not found",
            )
    else:
        # Get or create user's personal billing account
        account = await billing_repo.get_by_user_id(current_user.id)
        if not account:
            # Ensure user exists in local database (for local dev with Supabase auth)
            await ensure_user_exists_in_local_db(current_user)
            # Auto-create billing account for new users
            account = BillingAccount.create_for_user(current_user.id)
            await billing_repo.create(account)

    # Check and reset free tier if needed
    if account.check_and_reset_free_tier():
        await billing_repo.update(account)

    return BillingAccountResponse.from_entity(account)


# --- Purchases ---


@router.post("/credits/purchase", response_model=CheckoutResponse)
async def purchase_credits(
    request: PurchaseRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    x_organization_id: Annotated[str | None, Header()] = None,
    billing_repo=Depends(get_billing_account_repository),
    membership_repo=Depends(get_membership_repository),
    org_repo=Depends(get_organization_repository),
    payment_provider=Depends(get_payment_provider),
) -> CheckoutResponse:
    """
    Create a checkout session for purchasing credits.

    Returns a URL to redirect the user to Stripe Checkout.
    """
    # Validate credit pack selection
    if request.credit_pack_index < 0 or request.credit_pack_index >= len(CREDIT_PACKS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credit pack selection",
        )

    credit_pack = CREDIT_PACKS[request.credit_pack_index]

    # Get billing account
    if x_organization_id:
        org_id = UUID(x_organization_id)
        membership = await membership_repo.get_membership(current_user.id, org_id)
        if not membership or not membership.role.can_manage_billing():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to purchase credits for this organization",
            )
        account = await billing_repo.get_by_organization_id(org_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization billing account not found",
            )
        # Get org email for Stripe
        org = await org_repo.get_by_id(org_id)
        billing_email = org.billing_email if org else current_user.email
    else:
        account = await billing_repo.get_by_user_id(current_user.id)
        if not account:
            # Ensure user exists in local database (for local dev with Supabase auth)
            await ensure_user_exists_in_local_db(current_user)
            account = BillingAccount.create_for_user(current_user.id)
            await billing_repo.create(account)
        billing_email = current_user.email

    # Ensure we have a Stripe customer
    if not account.stripe_customer_id:
        customer_id = await payment_provider.get_or_create_customer(
            account, billing_email
        )
        account.stripe_customer_id = customer_id
        await billing_repo.update(account)

    # Create checkout session
    checkout = await payment_provider.create_checkout_session(
        billing_account=account,
        credit_pack=credit_pack,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )

    return CheckoutResponse(
        session_id=checkout.session_id,
        checkout_url=checkout.url,
        expires_at=checkout.expires_at.isoformat(),
    )


@router.post("/credits/webhook", status_code=status.HTTP_200_OK)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str, Header(alias="stripe-signature")],
    billing_repo=Depends(get_billing_account_repository),
    transaction_repo=Depends(get_transaction_repository),
    payment_provider=Depends(get_payment_provider),
) -> dict:
    """
    Handle Stripe webhook events.

    Processes successful payments and credits the appropriate billing account.
    """
    payload = await request.body()

    result = await payment_provider.verify_webhook(payload, stripe_signature)
    if not result:
        # Not a payment completion event or invalid - return 200 to acknowledge
        return {"status": "ignored"}

    # Get billing account from metadata
    billing_account_id = result.metadata.get("billing_account_id") if result.metadata else None
    if not billing_account_id:
        logger.error("Webhook missing billing_account_id in metadata")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing billing account identifier",
        )

    account = await billing_repo.get_by_id(UUID(billing_account_id))
    if not account:
        logger.error(f"Billing account not found: {billing_account_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing account not found",
        )

    # Update Stripe customer ID if needed
    if result.customer_id and not account.stripe_customer_id:
        account.stripe_customer_id = result.customer_id

    # Add credits
    account.add_credits(result.credits)
    await billing_repo.update(account)

    # Record transaction
    transaction = CreditTransaction.create_purchase(
        billing_account_id=account.id,
        amount=result.credits,
        balance_after=account.credits,
        stripe_payment_id=result.payment_id,
        credit_pack=CreditPack(
            credits=result.credits,
            price_cents=result.amount_cents,
        ),
    )
    await transaction_repo.create(transaction)

    logger.info(
        f"Credited {result.credits} to account {account.id}, "
        f"new balance: {account.credits}"
    )

    return {"status": "success", "credits_added": result.credits}


# --- Usage & Transaction History ---


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
    transaction_type: str | None = None,
    x_organization_id: Annotated[str | None, Header()] = None,
    billing_repo=Depends(get_billing_account_repository),
    transaction_repo=Depends(get_transaction_repository),
    membership_repo=Depends(get_membership_repository),
) -> list[TransactionResponse]:
    """
    List credit transactions for the billing account.
    """
    # Get billing account
    if x_organization_id:
        org_id = UUID(x_organization_id)
        membership = await membership_repo.get_membership(current_user.id, org_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )
        account = await billing_repo.get_by_organization_id(org_id)
    else:
        account = await billing_repo.get_by_user_id(current_user.id)

    if not account:
        return []

    # Parse transaction type filter
    tx_type = TransactionType(transaction_type) if transaction_type else None

    transactions = await transaction_repo.get_by_billing_account(
        billing_account_id=account.id,
        limit=limit,
        offset=offset,
        transaction_type=tx_type,
    )

    return [TransactionResponse.from_entity(tx) for tx in transactions]


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = 30,
    x_organization_id: Annotated[str | None, Header()] = None,
    billing_repo=Depends(get_billing_account_repository),
    transaction_repo=Depends(get_transaction_repository),
    membership_repo=Depends(get_membership_repository),
) -> UsageSummaryResponse:
    """
    Get a summary of credit usage over a time period.
    """
    # Get billing account
    if x_organization_id:
        org_id = UUID(x_organization_id)
        membership = await membership_repo.get_membership(current_user.id, org_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )
        account = await billing_repo.get_by_organization_id(org_id)
    else:
        account = await billing_repo.get_by_user_id(current_user.id)

    if not account:
        now = datetime.now(UTC)
        return UsageSummaryResponse(
            total_usage=0,
            total_purchases=0,
            period_start=(now - timedelta(days=days)).isoformat(),
            period_end=now.isoformat(),
        )

    # Calculate period
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    # Get totals
    total_usage = await transaction_repo.get_total_by_type(
        billing_account_id=account.id,
        transaction_type=TransactionType.USAGE,
        since=start_date,
    )
    # Usage is negative, so negate for display
    total_usage = abs(total_usage)

    total_purchases = await transaction_repo.get_total_by_type(
        billing_account_id=account.id,
        transaction_type=TransactionType.PURCHASE,
        since=start_date,
    )

    return UsageSummaryResponse(
        total_usage=total_usage,
        total_purchases=total_purchases,
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
    )
