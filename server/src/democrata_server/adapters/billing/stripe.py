"""Stripe payment adapter implementing the PaymentProvider protocol."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx

from democrata_server.domain.billing.entities import BillingAccount, CreditPack
from democrata_server.domain.billing.ports import CheckoutSession, PaymentResult

logger = logging.getLogger(__name__)


class StripePaymentProvider:
    """
    Stripe-based implementation of the PaymentProvider protocol.

    Handles credit pack purchases via Stripe Checkout and processes webhooks.
    Isolated behind the PaymentProvider protocol for future provider swaps.
    """

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        api_version: str = "2024-12-18.acacia",
    ):
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._api_version = api_version
        self._base_url = "https://api.stripe.com/v1"

    def _get_headers(self) -> dict[str, str]:
        """Build headers for Stripe API requests."""
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Stripe-Version": self._api_version,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def create_checkout_session(
        self,
        billing_account: BillingAccount,
        credit_pack: CreditPack,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """
        Create a Stripe Checkout session for purchasing credits.

        Returns a CheckoutSession with the URL to redirect the user to.
        """
        async with httpx.AsyncClient() as client:
            # Build line items for the credit pack
            data = {
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata[billing_account_id]": str(billing_account.id),
                "metadata[credits]": str(credit_pack.credits),
                "line_items[0][quantity]": "1",
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][unit_amount]": str(credit_pack.price_cents),
                "line_items[0][price_data][product_data][name]": f"{credit_pack.credits} Credits",
                "line_items[0][price_data][product_data][description]": (
                    f"Purchase {credit_pack.credits} query credits for Demócrata"
                ),
            }

            # Attach customer if we have a Stripe customer ID
            if billing_account.stripe_customer_id:
                data["customer"] = billing_account.stripe_customer_id
            else:
                # Create or retrieve customer email from metadata
                owner_email = billing_account.user_id or billing_account.organization_id
                data["customer_creation"] = "always"
                data["metadata[owner_id]"] = str(owner_email)

            response = await client.post(
                f"{self._base_url}/checkout/sessions",
                headers=self._get_headers(),
                data=data,
            )
            response.raise_for_status()
            session_data = response.json()

            return CheckoutSession(
                session_id=session_data["id"],
                url=session_data["url"],
                expires_at=datetime.fromtimestamp(session_data["expires_at"], tz=UTC),
            )

    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify the Stripe webhook signature."""
        # Parse the signature header
        elements = dict(item.split("=") for item in signature.split(","))
        timestamp = elements.get("t")
        v1_signature = elements.get("v1")

        if not timestamp or not v1_signature:
            return False

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            self._webhook_secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Constant time comparison
        return hmac.compare_digest(expected_sig, v1_signature)

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> PaymentResult | None:
        """
        Verify a webhook payload and extract payment result.

        Returns None if the event is not a successful payment completion.
        """
        if not self._verify_signature(payload, signature):
            logger.warning("Invalid webhook signature")
            return None

        event = json.loads(payload)
        event_type = event.get("type")

        # We only process successful checkout completions
        if event_type != "checkout.session.completed":
            logger.debug(f"Ignoring webhook event type: {event_type}")
            return None

        session = event.get("data", {}).get("object", {})

        # Verify payment was successful
        if session.get("payment_status") != "paid":
            logger.debug(f"Session not paid: {session.get('payment_status')}")
            return None

        metadata = session.get("metadata", {})
        billing_account_id = metadata.get("billing_account_id")
        credits = metadata.get("credits")

        if not billing_account_id or not credits:
            logger.warning("Missing metadata in webhook: billing_account_id or credits")
            return None

        return PaymentResult(
            payment_id=session.get("payment_intent") or session.get("id"),
            amount_cents=session.get("amount_total", 0),
            credits=int(credits),
            customer_id=session.get("customer", ""),
            metadata={
                "billing_account_id": billing_account_id,
                "checkout_session_id": session.get("id"),
            },
        )

    async def get_or_create_customer(
        self,
        billing_account: BillingAccount,
        email: str,
    ) -> str:
        """
        Get or create a Stripe customer for a billing account.

        Returns the Stripe customer ID.
        """
        # If we already have a customer ID, verify it exists
        if billing_account.stripe_customer_id:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/customers/{billing_account.stripe_customer_id}",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return billing_account.stripe_customer_id
                # Customer was deleted, create a new one

        # Create a new customer
        async with httpx.AsyncClient() as client:
            data = {
                "email": email,
                "metadata[billing_account_id]": str(billing_account.id),
                "metadata[account_type]": billing_account.account_type.value,
            }

            response = await client.post(
                f"{self._base_url}/customers",
                headers=self._get_headers(),
                data=data,
            )
            response.raise_for_status()
            customer = response.json()
            return customer["id"]

    async def refund_payment(
        self,
        payment_id: str,
        amount_cents: int | None = None,
    ) -> str:
        """
        Refund a payment, optionally partially.

        Returns the refund ID.
        """
        async with httpx.AsyncClient() as client:
            data = {"payment_intent": payment_id}
            if amount_cents is not None:
                data["amount"] = str(amount_cents)

            response = await client.post(
                f"{self._base_url}/refunds",
                headers=self._get_headers(),
                data=data,
            )
            response.raise_for_status()
            refund = response.json()
            return refund["id"]

    async def get_checkout_session(self, session_id: str) -> dict | None:
        """
        Retrieve a checkout session by ID.

        Useful for verification after redirect or webhook processing.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/checkout/sessions/{session_id}",
                headers=self._get_headers(),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
