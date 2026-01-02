"""Sample with DIP violation - direct instantiation of dependencies."""
import json
import smtplib
from typing import Dict, List


class OrderService:
    """Order service that violates DIP - creates its own dependencies."""

    def __init__(self):
        # DIP violation: High-level module creates low-level dependencies
        self.db = JsonDatabase("orders.json")  # Direct instantiation
        self.email_client = SmtpEmailClient("smtp.example.com")  # Direct instantiation
        self.logger = FileLogger("orders.log")  # Direct instantiation

    def create_order(self, order_data: Dict) -> str:
        """Create order - tightly coupled to specific implementations."""
        order_id = self.db.insert(order_data)
        self.email_client.send(
            order_data["customer_email"],
            "Order Confirmation",
            f"Your order {order_id} has been created."
        )
        self.logger.log(f"Order created: {order_id}")
        return order_id

    def get_order(self, order_id: str) -> Dict:
        """Get order - coupled to JsonDatabase."""
        return self.db.find_by_id(order_id)


class JsonDatabase:
    """JSON file-based database."""

    def __init__(self, path: str):
        self.path = path

    def insert(self, data: Dict) -> str:
        return "order_123"

    def find_by_id(self, id: str) -> Dict:
        return {}


class SmtpEmailClient:
    """SMTP email client."""

    def __init__(self, host: str):
        self.host = host

    def send(self, to: str, subject: str, body: str) -> bool:
        return True


class FileLogger:
    """File-based logger."""

    def __init__(self, path: str):
        self.path = path

    def log(self, message: str) -> None:
        pass
