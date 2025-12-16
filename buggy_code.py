"""A module with a deliberate bug for testing bug-bash."""


def divide(a: int, b: int) -> float:
    """Divide a by b.
    
    Args:
        a: The dividend.
        b: The divisor. Must not be zero.
    
    Returns:
        The result of a / b as a float.
    
    Raises:
        ValueError: If b is zero (division by zero is undefined).
    
    Note:
        As of this version, division by zero raises ValueError instead of
        ZeroDivisionError. Callers catching ZeroDivisionError should update
        their exception handlers.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def calculate_average(numbers: list) -> float:
    """Calculate the average of a list of numbers.

    Args:
        numbers: A list of numbers to average. Must not be empty.

    Returns:
        The arithmetic mean as a float.

    Raises:
        ValueError: If the list is empty.
    """
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)
