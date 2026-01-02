"""Well-structured module demonstrating clean code principles."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """A user entity with validated fields."""

    name: str
    email: str
    age: int

    def display_name(self) -> str:
        """Return the formatted display name."""
        return self.name.title()

    def is_adult(self) -> bool:
        """Check if user is 18 or older."""
        return self.age >= 18


def create_user(name: str, email: str, age: int) -> Optional[User]:
    """Create a user with validation.

    Args:
        name: The user's full name.
        email: The user's email address.
        age: The user's age in years.

    Returns:
        A User object if valid, None otherwise.
    """
    if not name or not email or age < 0:
        return None

    if "@" not in email or "." not in email:
        return None

    return User(name=name, email=email, age=age)
