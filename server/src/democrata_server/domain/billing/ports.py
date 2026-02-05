from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .entities import BillingAccount, CreditPack, CreditTransaction, TransactionType


class BillingAccountRepository(Protocol):
    """Repository for billing account data."""

    async def get_by_id(self, account_id: UUID) -> BillingAccount | None:
        """Get a billing account by its unique identifier."""
        ...

    async def get_by_user_id(self, user_id: UUID) -> BillingAccount | None:
        """Get the billing account for a user."""
        ...

    async def get_by_organization_id(self, org_id: UUID) -> BillingAccount | None:
        """Get the billing account for an organization."""
        ...

    async def create(self, account: BillingAccount) -> BillingAccount:
        """Create a new billing account."""
        ...

    async def update(self, account: BillingAccount) -> BillingAccount:
        """Update an existing billing account."""
        ...

    async def get_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> BillingAccount | None:
        """Get a billing account by its Stripe customer ID."""
        ...


class TransactionRepository(Protocol):
    """Repository for credit transaction history."""

    async def get_by_id(self, transaction_id: UUID) -> CreditTransaction | None:
        """Get a transaction by its unique identifier."""
        ...

    async def get_by_billing_account(
        self,
        billing_account_id: UUID,
        limit: int = 50,
        offset: int = 0,
        transaction_type: TransactionType | None = None,
    ) -> list[CreditTransaction]:
        """Get transactions for a billing account with pagination."""
        ...

    async def get_by_date_range(
        self,
        billing_account_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CreditTransaction]:
        """Get transactions within a date range."""
        ...

    async def create(self, transaction: CreditTransaction) -> CreditTransaction:
        """Create a new transaction record."""
        ...

    async def get_total_by_type(
        self,
        billing_account_id: UUID,
        transaction_type: TransactionType,
        since: datetime | None = None,
    ) -> int:
        """Get the total amount for a transaction type, optionally since a date."""
        ...


@dataclass
class CheckoutSession:
    """Represents a payment checkout session."""

    session_id: str
    url: str
    expires_at: datetime


@dataclass
class PaymentResult:
    """Result of a completed payment."""

    payment_id: str
    amount_cents: int
    credits: int
    customer_id: str
    metadata: dict | None = None


class PaymentProvider(Protocol):
    """Technology-agnostic payment interface (e.g., Stripe)."""

    async def create_checkout_session(
        self,
        billing_account: BillingAccount,
        credit_pack: CreditPack,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """Create a checkout session for purchasing credits."""
        ...

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> PaymentResult | None:
        """
        Verify a webhook payload and extract payment result.
        Returns None if the event is not a successful payment.
        """
        ...

    async def get_or_create_customer(
        self,
        billing_account: BillingAccount,
        email: str,
    ) -> str:
        """Get or create a customer ID for a billing account."""
        ...

    async def refund_payment(
        self,
        payment_id: str,
        amount_cents: int | None = None,
    ) -> str:
        """
        Refund a payment, optionally partially.
        Returns the refund ID.
        """
        ...
