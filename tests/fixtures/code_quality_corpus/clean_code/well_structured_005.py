"""Clean module demonstrating the Strategy pattern."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class Item:
    """An item with a price."""

    name: str
    price: float


class DiscountStrategy(ABC):
    """Abstract discount strategy."""

    @abstractmethod
    def apply(self, items: List[Item]) -> float:
        """Apply discount and return final total."""
        pass


class NoDiscount(DiscountStrategy):
    """No discount applied."""

    def apply(self, items: List[Item]) -> float:
        """Return sum of all item prices."""
        return sum(item.price for item in items)


class PercentageDiscount(DiscountStrategy):
    """Percentage-based discount."""

    def __init__(self, percentage: float):
        """Initialize with discount percentage (0-100)."""
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        self._percentage = percentage

    def apply(self, items: List[Item]) -> float:
        """Apply percentage discount to total."""
        total = sum(item.price for item in items)
        discount = total * (self._percentage / 100)
        return total - discount


class Cart:
    """Shopping cart with configurable discount strategy."""

    def __init__(self, discount_strategy: DiscountStrategy | None = None):
        """Initialize cart with optional discount strategy."""
        self._items: List[Item] = []
        self._discount = discount_strategy or NoDiscount()

    def add_item(self, item: Item) -> None:
        """Add an item to the cart."""
        self._items.append(item)

    def get_total(self) -> float:
        """Calculate total with discount applied."""
        return self._discount.apply(self._items)
