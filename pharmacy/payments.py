"""Explicit payment-provider boundary for locally configured gateways."""

from dataclasses import dataclass
from typing import Protocol


class PaymentConfigurationError(RuntimeError):
    """Raised when a gateway is selected without a configured integration."""


@dataclass(frozen=True)
class PaymentRequest:
    amount_bdt: str
    invoice_number: str
    customer_phone: str
    callback_url: str


@dataclass(frozen=True)
class PaymentSession:
    provider: str
    checkout_url: str
    reference: str


class PaymentAdapter(Protocol):
    """Contract implemented by bKash, Nagad, and Rocket merchant API clients."""

    def initiate(self, payment: PaymentRequest) -> PaymentSession:
        """Create a provider checkout session."""
        ...


def get_payment_adapter(provider: str) -> PaymentAdapter:
    """Fail explicitly until merchant credentials and provider-specific API are set."""
    if provider not in {"bkash", "nagad", "rocket"}:
        raise ValueError(f"Unsupported payment provider: {provider}")
    raise PaymentConfigurationError(
        f"{provider} merchant API is not configured. Add its credential-backed adapter "
        "before enabling hosted checkout."
    )
