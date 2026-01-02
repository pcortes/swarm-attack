"""Clean module demonstrating SOLID principles - Single Responsibility."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class Order:
    """An order with items."""

    id: str
    customer_id: str
    items: List[str]
    total: float


class OrderRepository(ABC):
    """Repository for order persistence (Single Responsibility)."""

    @abstractmethod
    def save(self, order: Order) -> None:
        """Save an order."""
        pass

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order | None:
        """Find an order by ID."""
        pass


class OrderValidator:
    """Validator for orders (Single Responsibility)."""

    def validate(self, order: Order) -> List[str]:
        """Validate an order and return list of errors."""
        errors = []
        if not order.customer_id:
            errors.append("Customer ID is required")
        if not order.items:
            errors.append("Order must have at least one item")
        if order.total <= 0:
            errors.append("Total must be positive")
        return errors


class OrderNotifier(ABC):
    """Notification sender for orders (Single Responsibility)."""

    @abstractmethod
    def notify_created(self, order: Order) -> None:
        """Notify about order creation."""
        pass


class OrderService:
    """Service that coordinates order operations."""

    def __init__(
        self,
        repository: OrderRepository,
        validator: OrderValidator,
        notifier: OrderNotifier,
    ):
        """Initialize with injected dependencies."""
        self._repository = repository
        self._validator = validator
        self._notifier = notifier

    def create_order(self, order: Order) -> List[str]:
        """Create an order with validation and notification."""
        errors = self._validator.validate(order)
        if errors:
            return errors

        self._repository.save(order)
        self._notifier.notify_created(order)
        return []
