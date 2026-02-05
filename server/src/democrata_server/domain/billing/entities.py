from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class AccountType(str, Enum):
    USER = "user"
    ORGANIZATION = "organization"


class TransactionType(str, Enum):
    PURCHASE = "purchase"
    USAGE = "usage"
    REFUND = "refund"
    GRANT = "grant"  # Admin-granted credits
    ADJUSTMENT = "adjustment"  # Manual correction


# Standard credit packs available for purchase
@dataclass(frozen=True)
class CreditPack:
    credits: int
    price_cents: int
    stripe_price_id: str | None = None

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100


# Default credit packs (can be configured via environment)
CREDIT_PACKS = [
    CreditPack(credits=500, price_cents=500),   # $5 for 500 credits
    CreditPack(credits=1000, price_cents=1000), # $10 for 1000 credits
    CreditPack(credits=2000, price_cents=2000), # $20 for 2000 credits
]

# Free tier limits
ANONYMOUS_FREE_TIER_DAILY = 10
REGISTERED_FREE_TIER_MONTHLY = 100


@dataclass
class BillingAccount:
    """
    Represents a billing entity that can be either a user or an organization.
    
    This abstraction allows the same billing/usage logic to work for both
    individual users and organizations without needing special cases.
    """

    id: UUID
    account_type: AccountType
    user_id: UUID | None = None  # Set if account_type == USER
    organization_id: UUID | None = None  # Set if account_type == ORGANIZATION
    credits: int = 0
    lifetime_credits: int = 0  # Total credits ever purchased
    lifetime_usage: int = 0  # Total credits ever consumed
    free_tier_remaining: int = REGISTERED_FREE_TIER_MONTHLY
    free_tier_reset_at: datetime | None = None
    stripe_customer_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.account_type == AccountType.USER and self.user_id is None:
            raise ValueError("user_id is required for user accounts")
        if self.account_type == AccountType.ORGANIZATION and self.organization_id is None:
            raise ValueError("organization_id is required for organization accounts")
        if self.user_id is not None and self.organization_id is not None:
            raise ValueError("Account cannot have both user_id and organization_id")

    @classmethod
    def create_for_user(
        cls,
        user_id: UUID,
        free_tier: int = REGISTERED_FREE_TIER_MONTHLY,
    ) -> "BillingAccount":
        now = utc_now()
        return cls(
            id=uuid4(),
            account_type=AccountType.USER,
            user_id=user_id,
            organization_id=None,
            credits=0,
            free_tier_remaining=free_tier,
            free_tier_reset_at=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def create_for_organization(
        cls,
        organization_id: UUID,
        free_tier: int = REGISTERED_FREE_TIER_MONTHLY,
    ) -> "BillingAccount":
        now = utc_now()
        return cls(
            id=uuid4(),
            account_type=AccountType.ORGANIZATION,
            user_id=None,
            organization_id=organization_id,
            credits=0,
            free_tier_remaining=free_tier,
            free_tier_reset_at=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )

    @property
    def owner_id(self) -> UUID:
        """Returns the owning entity ID (user_id or organization_id)."""
        if self.user_id is not None:
            return self.user_id
        if self.organization_id is not None:
            return self.organization_id
        raise ValueError("BillingAccount has no owner")

    @property
    def is_free_tier(self) -> bool:
        return self.credits == 0 and self.lifetime_credits == 0

    def can_consume(self, credits_needed: int = 1) -> bool:
        """Check if the account has sufficient credits or free tier quota."""
        if self.free_tier_remaining >= credits_needed:
            return True
        return self.credits >= credits_needed

    def check_and_reset_free_tier(self) -> bool:
        """
        Check if free tier should be reset (monthly for registered users).
        Returns True if reset was performed.
        """
        if self.free_tier_reset_at is None:
            return False
        
        now = utc_now()
        if now >= self.free_tier_reset_at:
            self.free_tier_remaining = REGISTERED_FREE_TIER_MONTHLY
            self.free_tier_reset_at = now + timedelta(days=30)
            self.updated_at = now
            return True
        return False

    def consume(self, credits_needed: int, use_free_tier_first: bool = True) -> int:
        """
        Consume credits from the account.
        
        Returns the number of paid credits consumed (0 if free tier was used).
        Raises ValueError if insufficient credits.
        """
        if not self.can_consume(credits_needed):
            raise ValueError(
                f"Insufficient credits: need {credits_needed}, "
                f"have {self.credits} credits + {self.free_tier_remaining} free tier"
            )

        self.updated_at = utc_now()
        paid_credits_used = 0

        if use_free_tier_first and self.free_tier_remaining > 0:
            free_to_use = min(self.free_tier_remaining, credits_needed)
            self.free_tier_remaining -= free_to_use
            credits_needed -= free_to_use

        if credits_needed > 0:
            self.credits -= credits_needed
            paid_credits_used = credits_needed

        self.lifetime_usage += paid_credits_used
        return paid_credits_used

    def add_credits(self, amount: int) -> None:
        """Add purchased or granted credits to the account."""
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        self.credits += amount
        self.lifetime_credits += amount
        self.updated_at = utc_now()


@dataclass
class CreditTransaction:
    """
    Records a credit transaction for audit and history purposes.
    
    Each transaction represents a change to a billing account's credit balance,
    whether from purchases, usage, refunds, or administrative adjustments.
    """

    id: UUID
    billing_account_id: UUID
    amount: int  # Positive = added, negative = consumed
    transaction_type: TransactionType
    balance_after: int
    reference_id: str | None = None  # External reference (e.g., Stripe payment ID)
    description: str | None = None
    metadata: dict | None = None
    created_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create_purchase(
        cls,
        billing_account_id: UUID,
        amount: int,
        balance_after: int,
        stripe_payment_id: str,
        credit_pack: CreditPack | None = None,
    ) -> "CreditTransaction":
        metadata = None
        if credit_pack:
            metadata = {
                "credits": credit_pack.credits,
                "price_cents": credit_pack.price_cents,
            }
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            amount=amount,
            transaction_type=TransactionType.PURCHASE,
            balance_after=balance_after,
            reference_id=stripe_payment_id,
            description=f"Purchased {amount} credits",
            metadata=metadata,
        )

    @classmethod
    def create_usage(
        cls,
        billing_account_id: UUID,
        amount: int,
        balance_after: int,
        usage_event_id: UUID | None = None,
        query_preview: str | None = None,
    ) -> "CreditTransaction":
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            amount=-abs(amount),  # Usage is always negative
            transaction_type=TransactionType.USAGE,
            balance_after=balance_after,
            reference_id=str(usage_event_id) if usage_event_id else None,
            description=query_preview[:50] if query_preview else "Query usage",
            metadata={"usage_event_id": str(usage_event_id)} if usage_event_id else None,
        )

    @classmethod
    def create_refund(
        cls,
        billing_account_id: UUID,
        amount: int,
        balance_after: int,
        reason: str,
        original_transaction_id: UUID | None = None,
    ) -> "CreditTransaction":
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            amount=abs(amount),  # Refunds are always positive
            transaction_type=TransactionType.REFUND,
            balance_after=balance_after,
            reference_id=str(original_transaction_id) if original_transaction_id else None,
            description=reason,
        )

    @classmethod
    def create_grant(
        cls,
        billing_account_id: UUID,
        amount: int,
        balance_after: int,
        reason: str,
        granted_by: UUID | None = None,
    ) -> "CreditTransaction":
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            amount=abs(amount),
            transaction_type=TransactionType.GRANT,
            balance_after=balance_after,
            description=reason,
            metadata={"granted_by": str(granted_by)} if granted_by else None,
        )
