"""Clean module with Result pattern for error handling."""
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


@dataclass
class Result(Generic[T]):
    """A result type that can hold either a value or an error."""

    _value: Optional[T] = None
    _error: Optional[str] = None

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        """Create a successful result."""
        return cls(_value=value)

    @classmethod
    def err(cls, error: str) -> "Result[T]":
        """Create an error result."""
        return cls(_error=error)

    @property
    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self._error is None

    @property
    def is_err(self) -> bool:
        """Check if result is an error."""
        return self._error is not None

    def unwrap(self) -> T:
        """Get the value, raise if error."""
        if self._error is not None:
            raise ValueError(f"Cannot unwrap error result: {self._error}")
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        """Get the value or return default."""
        if self._error is not None:
            return default
        return self._value  # type: ignore

    @property
    def error(self) -> Optional[str]:
        """Get the error message if any."""
        return self._error


def divide(a: float, b: float) -> Result[float]:
    """Divide two numbers safely.

    Args:
        a: The numerator.
        b: The denominator.

    Returns:
        Result containing the quotient or an error.
    """
    if b == 0:
        return Result.err("Division by zero")
    return Result.ok(a / b)


def parse_int(s: str) -> Result[int]:
    """Parse a string to integer safely.

    Args:
        s: The string to parse.

    Returns:
        Result containing the integer or an error.
    """
    try:
        return Result.ok(int(s))
    except ValueError:
        return Result.err(f"Cannot parse '{s}' as integer")
