"""Sample with primitive obsession code smell - money as integers."""
from typing import Dict


class OrderProcessor:
    """Order processor using primitives for money instead of Money value object."""

    def calculate_subtotal(self, items: list) -> int:
        """Calculate subtotal in cents."""
        total_cents = 0
        for item in items:
            price_cents = item["price_cents"]
            quantity = item["quantity"]
            total_cents += price_cents * quantity
        return total_cents

    def apply_discount(self, amount_cents: int, discount_percent: float) -> int:
        """Apply percentage discount."""
        discount_cents = int(amount_cents * discount_percent / 100)
        return amount_cents - discount_cents

    def calculate_tax(self, amount_cents: int, tax_rate_percent: float) -> int:
        """Calculate tax amount in cents."""
        return int(amount_cents * tax_rate_percent / 100)

    def calculate_total(
        self,
        subtotal_cents: int,
        discount_percent: float,
        tax_rate_percent: float,
        shipping_cents: int,
    ) -> Dict[str, int]:
        """Calculate order total - all in cents to avoid floating point."""
        after_discount = self.apply_discount(subtotal_cents, discount_percent)
        tax_cents = self.calculate_tax(after_discount, tax_rate_percent)
        total_cents = after_discount + tax_cents + shipping_cents

        return {
            "subtotal_cents": subtotal_cents,
            "discount_cents": subtotal_cents - after_discount,
            "tax_cents": tax_cents,
            "shipping_cents": shipping_cents,
            "total_cents": total_cents,
        }

    def format_cents_as_dollars(self, cents: int) -> str:
        """Format cents as dollar string."""
        dollars = cents // 100
        remaining_cents = cents % 100
        return f"${dollars}.{remaining_cents:02d}"
