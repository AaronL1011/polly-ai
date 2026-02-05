"""Billing adapters for payment processing."""

from .stripe import StripePaymentProvider

__all__ = ["StripePaymentProvider"]
