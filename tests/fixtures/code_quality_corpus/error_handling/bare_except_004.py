"""Sample with bare except - nested try blocks."""


def complex_operation(a: int, b: int, c: int) -> int:
    """Complex operation with nested bare excepts."""
    try:
        result = a / b
        try:
            result = result / c
        except:  # Nested bare except
            result = 0
        return int(result)
    except:  # Outer bare except
        return -1
