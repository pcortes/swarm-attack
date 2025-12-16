# Engineering Spec: Unit Converter

## 1. Overview

### 1.1 Purpose
Extend the existing temperature conversion utilities with length and weight conversion functions. This provides a consistent set of pure Python utility functions for common unit conversions, following the established pattern from the temperature converter.

### 1.2 Existing Infrastructure
- **Utils module**: `swarm_attack/utils/` contains utility functions following project conventions (type hints, docstrings)
- **Temperature converter spec**: `specs/temperature-converter/spec-final.md` defines the pattern - simple functions in a dedicated module
- **No database or API needed**: This is pure computation
- **Pattern to follow**: Simple functions with type hints matching the temperature converter approach

### 1.3 Scope
**In Scope:**
- Length conversions: `meters_to_feet`, `feet_to_meters`, `km_to_miles`, `miles_to_km`
- Weight conversions: `kg_to_pounds`, `pounds_to_kg`
- Accept float inputs, return float results
- Handle negative values (no special validation needed)

**Out of Scope:**
- Other unit types (volume, area, etc.)
- CLI interface
- API endpoints
- Input validation beyond Python's native type handling
- Rounding or formatting of results
- Class-based design (use simple functions like temperature converter)

## 2. Implementation

### 2.1 Approach
Create a new module `unit_converter.py` inside the existing `swarm_attack/utils/` package. This follows the same pattern established by the temperature converter spec and keeps utilities organized in one place.

**Conversion Constants (from PRD):**
- 1 meter = 3.28084 feet
- 1 kilometer = 0.621371 miles
- 1 kilogram = 2.20462 pounds

### 2.2 Changes Required
| File | Change | Why |
|------|--------|-----|
| `swarm_attack/utils/unit_converter.py` | Create new file with 6 conversion functions | Implement converters in existing utils package |
| `swarm_attack/utils/__init__.py` | Export new functions | Make functions accessible via `swarm_attack.utils` |

### 2.3 Data Model
No data models needed. Pure functions operating on numeric inputs.

```python
# Function signatures:
def meters_to_feet(meters: float) -> float: ...
def feet_to_meters(feet: float) -> float: ...
def km_to_miles(km: float) -> float: ...
def miles_to_km(miles: float) -> float: ...
def kg_to_pounds(kg: float) -> float: ...
def pounds_to_kg(pounds: float) -> float: ...
```

## 3. API (if applicable)

Not applicable. This is a pure Python utility module with no API endpoints.

## 4. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Create unit_converter.py with all 6 conversion functions | `swarm_attack/utils/unit_converter.py` | S |
| 2 | Export functions from utils __init__.py | `swarm_attack/utils/__init__.py` | S |
| 3 | Add unit tests for all conversions | `tests/test_unit_converter.py` | S |

## 5. Testing

### 5.1 Manual Test Plan
```python
# In Python REPL:
from swarm_attack.utils.unit_converter import (
    meters_to_feet, feet_to_meters,
    km_to_miles, miles_to_km,
    kg_to_pounds, pounds_to_kg
)

# Test length - meters/feet
meters_to_feet(1)       # Should return 3.28084
feet_to_meters(3.28084) # Should return ~1.0
meters_to_feet(0)       # Should return 0.0

# Test length - km/miles
km_to_miles(1)          # Should return 0.621371
miles_to_km(1)          # Should return ~1.60934
km_to_miles(0)          # Should return 0.0

# Test weight
kg_to_pounds(1)         # Should return 2.20462
pounds_to_kg(2.20462)   # Should return ~1.0
kg_to_pounds(0)         # Should return 0.0

# Test negative values
meters_to_feet(-1)      # Should return -3.28084
kg_to_pounds(-1)        # Should return -2.20462

# Round-trip conversions
meters_to_feet(feet_to_meters(10))  # Should return ~10.0
km_to_miles(miles_to_km(5))         # Should return ~5.0
kg_to_pounds(pounds_to_kg(100))     # Should return ~100.0
```

### 5.2 Automated Tests
Key test cases:
- **Length (meters/feet):**
  - 1 meter = 3.28084 feet
  - 0 meters = 0 feet
  - Negative: -1 meter = -3.28084 feet
  - Round-trip: m → ft → m returns original

- **Length (km/miles):**
  - 1 km = 0.621371 miles
  - 0 km = 0 miles
  - Negative: -1 km = -0.621371 miles
  - Round-trip: km → mi → km returns original

- **Weight (kg/pounds):**
  - 1 kg = 2.20462 pounds
  - 0 kg = 0 pounds
  - Negative: -1 kg = -2.20462 pounds
  - Round-trip: kg → lb → kg returns original

## 6. Open Questions

None. The requirements are clear and the implementation is straightforward, following the established temperature converter pattern.
