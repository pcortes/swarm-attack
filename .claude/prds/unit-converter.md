# PRD: Unit Converter

## Problem
The existing TemperatureConverter class only handles temperature conversions. Users need a way to also convert between common length and weight units.

## Goals
1. Add length conversions: meters ↔ feet, kilometers ↔ miles
2. Add weight conversions: kilograms ↔ pounds
3. Extend the existing TemperatureConverter pattern for consistency

## Functional Requirements
1. **Length Conversions**
   - meters_to_feet(meters: float) -> float
   - feet_to_meters(feet: float) -> float
   - km_to_miles(km: float) -> float
   - miles_to_km(miles: float) -> float

2. **Weight Conversions**
   - kg_to_pounds(kg: float) -> float
   - pounds_to_kg(pounds: float) -> float

## Conversion Formulas
- 1 meter = 3.28084 feet
- 1 kilometer = 0.621371 miles
- 1 kilogram = 2.20462 pounds

## Constraints
- Pure Python, no external dependencies
- Return float results
- Follow existing code patterns from TemperatureConverter
- All functions should handle negative values gracefully
