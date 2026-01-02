"""Sample with OCP violation - isinstance checks instead of polymorphism."""
from dataclasses import dataclass


@dataclass
class Shape:
    """Base shape."""
    name: str


@dataclass
class Circle(Shape):
    """Circle shape."""
    radius: float


@dataclass
class Rectangle(Shape):
    """Rectangle shape."""
    width: float
    height: float


@dataclass
class Triangle(Shape):
    """Triangle shape."""
    base: float
    height: float


class AreaCalculator:
    """Area calculator that violates OCP - isinstance checks."""

    def calculate_area(self, shape: Shape) -> float:
        """Calculate area - OCP violation with isinstance checks."""
        # Adding new shape requires modifying this method
        if isinstance(shape, Circle):
            return 3.14159 * shape.radius ** 2
        elif isinstance(shape, Rectangle):
            return shape.width * shape.height
        elif isinstance(shape, Triangle):
            return 0.5 * shape.base * shape.height
        else:
            raise ValueError(f"Unknown shape: {type(shape)}")

    def calculate_perimeter(self, shape: Shape) -> float:
        """Calculate perimeter - another OCP violation."""
        if isinstance(shape, Circle):
            return 2 * 3.14159 * shape.radius
        elif isinstance(shape, Rectangle):
            return 2 * (shape.width + shape.height)
        elif isinstance(shape, Triangle):
            # Simplified - assuming equilateral
            return 3 * shape.base
        else:
            raise ValueError(f"Unknown shape: {type(shape)}")
