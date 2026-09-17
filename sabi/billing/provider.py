"""The payment boundary. Deliberately unimplemented.

There is no checkout, no pricing page and no subscription logic in v1, and that
is a product decision rather than an unfinished one: naira pricing should come
from what real students say they would pay, not from a number guessed before
anyone has used the thing.

What exists is the seam. Three things make dropping Paystack in later a
contained change rather than a restructure:

* every user already carries a `plan`, and every limit is read from the plans
  table rather than from a constant;
* every question already writes a `usage_events` row with a cost, priced at
  zero on the free plan, in a shape that could drive an invoice;
* this interface, which the rest of the application does not import.

**Paystack, not Stripe.** Stripe does not properly serve Nigerian merchants:
onboarding a Nigerian entity is the exception rather than the path, and
settlement in naira to a Nigerian bank account is the normal case here, not an
edge case. Paystack is the default payment processor for Nigerian businesses,
takes bank transfer and USSD alongside cards, and handles the recurring-charge
authorisation flow that Nigerian cards actually use. Reasoning recorded in
DECISIONS.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """Minor units, always. Kobo for NGN. Never a float."""

    amount_minor: int
    currency: str = "NGN"

    def __str__(self) -> str:
        return f"{self.currency} {self.amount_minor / 100:,.2f}"


@dataclass(frozen=True)
class CheckoutSession:
    reference: str
    redirect_url: str
    plan: str


@dataclass(frozen=True)
class SubscriptionState:
    plan: str
    active: bool
    renews_at: str | None = None


class PaymentProvider(ABC):
    """What a processor has to do for Sabi. Nothing more.

    Kept this small on purpose: the smaller the surface, the less of the
    application has to change when it is filled in.
    """

    name: str

    @abstractmethod
    def start_checkout(self, anon_id: str, plan: str, price: Money) -> CheckoutSession:
        """Begin a payment and return somewhere to send the student."""

    @abstractmethod
    def verify(self, reference: str) -> SubscriptionState:
        """Confirm a completed payment. Called on return and by webhook."""

    @abstractmethod
    def cancel(self, anon_id: str) -> None:
        """Stop a recurring charge. Must be as easy as starting one."""


class UnimplementedPaymentProvider(PaymentProvider):
    """The only implementation. It refuses, loudly and on purpose."""

    name = "none"

    def start_checkout(self, anon_id: str, plan: str, price: Money) -> CheckoutSession:
        raise NotImplementedError(
            "Sabi has no payment flow. The free plan is the only plan, by design. "
            "See sabi/billing/provider.py and DECISIONS.md."
        )

    def verify(self, reference: str) -> SubscriptionState:
        raise NotImplementedError("no payment provider is configured")

    def cancel(self, anon_id: str) -> None:
        raise NotImplementedError("no payment provider is configured")


def get_payment_provider() -> PaymentProvider:
    return UnimplementedPaymentProvider()
