"""Clean module with proper separation of concerns."""
from dataclasses import dataclass
from typing import List
from abc import ABC, abstractmethod


@dataclass
class Product:
    """Represents a product in the catalog."""

    id: str
    name: str
    price: float


class ProductRepository(ABC):
    """Abstract repository for product persistence."""

    @abstractmethod
    def find_by_id(self, product_id: str) -> Product | None:
        """Find a product by its ID."""
        pass

    @abstractmethod
    def find_all(self) -> List[Product]:
        """Return all products."""
        pass


class ProductService:
    """Service layer for product operations."""

    def __init__(self, repository: ProductRepository):
        """Initialize with a repository dependency."""
        self._repository = repository

    def get_product(self, product_id: str) -> Product | None:
        """Get a product by ID."""
        return self._repository.find_by_id(product_id)

    def get_all_products(self) -> List[Product]:
        """Get all products."""
        return self._repository.find_all()

    def calculate_total(self, product_ids: List[str]) -> float:
        """Calculate total price for given product IDs."""
        total = 0.0
        for product_id in product_ids:
            product = self._repository.find_by_id(product_id)
            if product:
                total += product.price
        return total
