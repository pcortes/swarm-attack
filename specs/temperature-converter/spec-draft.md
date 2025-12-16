# Engineering Spec: Temperature Converter

## 1. Overview

### 1.1 Purpose
Provide two pure Python functions to convert temperatures between Celsius and Fahrenheit. This is a simple utility with no external dependencies, designed for quick temperature calculations.

### 1.2 Existing Infrastructure
- **Utils module**: `swarm_attack/utils/` contains existing utility functions with type hints and docstrings following project conventions
- **No database or API needed**: This is pure computation
- **Pattern to follow**: Simple functions with type hints, similar to utilities in `swarm_attack/utils/fs.py`

### 1.3 Scope
**In Scope:**
- `celsius_to_fahrenheit(celsius: float) -> float` function
- `fahrenheit_to_celsius(fahrenheit: float) -> float` function
- Accept both int and float inputs (Python handles this naturally)

**Out of Scope:**
- Kelvin or other temperature scales
- CLI interface
- API endpoints
- Input validation beyond Python's native type handling
- Rounding or formatting of results

## 2. Implementation

### 2.1 Approach
Create a new module `temperature_converter.py` inside the existing `swarm_attack/utils/` package. This follows established project conventions and keeps utilities organized in one place.

Formulas:
- Celsius to Fahrenheit: `F = (C × 9/5) + 32`
- Fahrenheit to Celsius: `C = (F - 32) × 5/9`

### 2.2 Changes Required
| File | Change | Why |
|------|--------|-----|
| `swarm_attack/utils/temperature_converter.py` | Create new file with two functions | Implement the converter in the existing utils package |

### 2.3 Data Model
No data models needed. Pure functions operating on numeric inputs.

```python
# No models required - just function signatures:
def celsius_to_fahrenheit(celsius: float) -> float: ...
def fahrenheit_to_celsius(fahrenheit: float) -> float: ...
```

## 3. API (if applicable)

Not applicable. This is a pure Python utility module with no API endpoints.

## 4. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Create temperature_converter.py with both functions | swarm_attack/utils/temperature_converter.py | S |
| 2 | Add basic unit tests | tests/test_temperature_converter.py | S |

## 5. Testing

### 5.1 Manual Test Plan
```python
# In Python REPL:
from swarm_attack.utils.temperature_converter import celsius_to_fahrenheit, fahrenheit_to_celsius

# Test freezing point
celsius_to_fahrenheit(0)    # Should return 32.0
fahrenheit_to_celsius(32)   # Should return 0.0

# Test boiling point
celsius_to_fahrenheit(100)  # Should return 212.0
fahrenheit_to_celsius(212)  # Should return 100.0

# Test negative values
celsius_to_fahrenheit(-40)  # Should return -40.0 (they're equal at -40)
fahrenheit_to_celsius(-40)  # Should return -40.0
```

### 5.2 Automated Tests
Key test cases:
- Freezing point: 0°C = 32°F
- Boiling point: 100°C = 212°F
- Negative values: -40°C = -40°F (intersection point)
- Float inputs: 37.5°C (body temperature)
- Round-trip conversion: C → F → C should return original value

## 6. Open Questions

None. The requirements are clear and the implementation is straightforward.