# Fix Plan: divide-by-zero

## Summary
Add input validation to divide() to check if b=0 and raise ValueError with descriptive message before performing division. This is a backward-incompatible API change that intentionally replaces the implicit ZeroDivisionError with an explicit ValueError to provide clearer error semantics.

## Risk Assessment
- **Risk Level:** MEDIUM
- **Scope:** Single function in buggy_code.py - only the divide() function is modified. However, any callers of divide() that catch ZeroDivisionError are affected.

### Risk Explanation
This fix introduces a backward-incompatible change to the public API: divide(a, 0) now raises ValueError instead of ZeroDivisionError. Any existing code that catches ZeroDivisionError specifically will no longer handle this case and may propagate the ValueError unexpectedly. While the fix itself is minimal (2 lines of logic), the exception type change affects the public contract. Mitigation: The docstring includes a migration note, and callers should be notified of this change. The change is intentional and improves API clarity by using ValueError for invalid input rather than letting Python's implicit ZeroDivisionError bubble up.

## Proposed Changes

### Change 1: buggy_code.py
- **Type:** modify
- **Explanation:** Add a guard clause to check if the divisor b is zero before performing division. If b is 0, raise a ValueError with the expected message 'Cannot divide by zero'. The docstring is updated to document the Raises clause and includes a migration note warning callers about the exception type change from ZeroDivisionError to ValueError.

**Current Code:**
```python
def divide(a: int, b: int) -> float:
    """Divide a by b. Has a bug - doesn't handle division by zero."""
    return a / b
```

**Proposed Code:**
```python
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
```

## Test Cases

### Test 1: test_divide_by_zero_raises_value_error
- **Category:** regression
- **Description:** Regression test: divide(a, 0) should raise ValueError (not ZeroDivisionError) with correct message

```python
def test_divide_by_zero_raises_value_error():
    """Regression test for bug: division by zero should raise ValueError."""
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)
    # Also verify it's specifically ValueError, not ZeroDivisionError
    with pytest.raises(ValueError):
        divide(-5, 0)
```

### Test 2: test_divide_zero_dividend
- **Category:** edge_case
- **Description:** Edge case: zero as dividend (0/b) should work correctly and return 0.0

```python
def test_divide_zero_dividend():
    """Edge case: zero dividend should return 0.0."""
    assert divide(0, 5) == 0.0
    assert divide(0, -3) == 0.0
```

### Test 3: test_divide_negative_divisor
- **Category:** edge_case
- **Description:** Edge case: negative divisor should work correctly

```python
def test_divide_negative_divisor():
    """Edge case: negative divisor should work correctly."""
    assert divide(10, -2) == -5.0
    assert divide(-10, -2) == 5.0
```

### Test 4: test_divide_normal_cases_unchanged
- **Category:** regression
- **Description:** Verify normal division operations continue to work as expected after the fix

```python
def test_divide_normal_cases_unchanged():
    """Verify normal division behavior is unchanged."""
    assert divide(10, 2) == 5.0
    assert divide(7, 2) == 3.5
    assert divide(1, 3) == pytest.approx(0.333333, rel=1e-5)
```

## Potential Side Effects
- Code that previously caught ZeroDivisionError from divide() will need to catch ValueError instead - this is a breaking change for those callers
- All valid division operations (b != 0) continue working unchanged
- Error messages become more explicit and user-friendly
- Stack traces will show ValueError instead of ZeroDivisionError, which may affect logging/monitoring that filters by exception type

## Rollback Plan
Revert the single commit to restore original divide() behavior. Since this is a bug fix with an intentional API change, reverting restores the original ZeroDivisionError behavior. If partial rollback is needed, the docstring migration note can be kept while removing the guard clause, but this is not recommended as it would leave documentation inconsistent with behavior.

## Estimated Effort
small
