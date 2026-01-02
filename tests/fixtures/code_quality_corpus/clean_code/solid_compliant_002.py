"""Clean module demonstrating SOLID - Open/Closed with polymorphism."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentResult:
    """Result of a payment operation."""

    success: bool
    transaction_id: str | None = None
    error: str | None = None


class PaymentMethod(ABC):
    """Abstract payment method - Open for extension, closed for modification."""

    @abstractmethod
    def process(self, amount: float) -> PaymentResult:
        """Process a payment."""
        pass

    @abstractmethod
    def refund(self, transaction_id: str) -> PaymentResult:
        """Refund a payment."""
        pass


class CreditCardPayment(PaymentMethod):
    """Credit card payment implementation."""

    def __init__(self, card_number: str, expiry: str, cvv: str):
        """Initialize with card details."""
        self._card_number = card_number
        self._expiry = expiry
        self._cvv = cvv

    def process(self, amount: float) -> PaymentResult:
        """Process credit card payment."""
        # Would integrate with payment gateway
        return PaymentResult(success=True, transaction_id="cc_123")

    def refund(self, transaction_id: str) -> PaymentResult:
        """Refund credit card payment."""
        return PaymentResult(success=True, transaction_id=transaction_id)


class PayPalPayment(PaymentMethod):
    """PayPal payment implementation."""

    def __init__(self, email: str):
        """Initialize with PayPal email."""
        self._email = email

    def process(self, amount: float) -> PaymentResult:
        """Process PayPal payment."""
        return PaymentResult(success=True, transaction_id="pp_456")

    def refund(self, transaction_id: str) -> PaymentResult:
        """Refund PayPal payment."""
        return PaymentResult(success=True, transaction_id=transaction_id)


class PaymentProcessor:
    """Payment processor that works with any PaymentMethod."""

    def checkout(self, payment_method: PaymentMethod, amount: float) -> PaymentResult:
        """Process checkout - works with any payment method."""
        return payment_method.process(amount)
