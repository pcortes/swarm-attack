"""Sample with SRP violation - validator class doing validation and notification."""
from typing import Dict, List, Optional
import re


class OrderValidator:
    """Order validator that violates SRP - validation + notification + logging."""

    def __init__(self):
        self.errors: List[str] = []
        self.notifications_sent: List[str] = []
        self.log_entries: List[str] = []

    # Validation (responsibility 1)
    def validate_order(self, order: Dict) -> bool:
        self.errors = []

        if not order.get("customer_id"):
            self.errors.append("Missing customer ID")

        if not order.get("items"):
            self.errors.append("No items in order")

        email = order.get("email", "")
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            self.errors.append("Invalid email format")

        total = order.get("total", 0)
        if total <= 0:
            self.errors.append("Total must be positive")

        is_valid = len(self.errors) == 0

        # Notification (responsibility 2)
        if is_valid:
            self._send_confirmation(order)
        else:
            self._send_validation_failure(order)

        # Logging (responsibility 3)
        self._log_validation(order, is_valid)

        return is_valid

    def _send_confirmation(self, order: Dict) -> None:
        """Send order confirmation."""
        self.notifications_sent.append(f"Confirmation sent for order {order.get('id')}")

    def _send_validation_failure(self, order: Dict) -> None:
        """Send validation failure notification."""
        self.notifications_sent.append(f"Validation failed for order {order.get('id')}")

    def _log_validation(self, order: Dict, is_valid: bool) -> None:
        """Log validation result."""
        status = "PASSED" if is_valid else "FAILED"
        self.log_entries.append(f"Order {order.get('id')} validation {status}")
