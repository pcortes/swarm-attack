"""Sample with primitive obsession code smell - coordinates as tuples."""
from typing import Tuple, List, Optional
import math


def calculate_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate distance between two points - should use Coordinate value object."""
    # Haversine formula
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_location(
    target_lat: float,
    target_lon: float,
    locations: List[Tuple[str, float, float]]
) -> Optional[Tuple[str, float, float, float]]:
    """Find nearest location - primitive obsession with lat/lon."""
    nearest = None
    min_distance = float('inf')

    for name, lat, lon in locations:
        dist = calculate_distance(target_lat, target_lon, lat, lon)
        if dist < min_distance:
            min_distance = dist
            nearest = (name, lat, lon, dist)

    return nearest


def is_within_bounds(
    lat: float,
    lon: float,
    north_lat: float,
    south_lat: float,
    east_lon: float,
    west_lon: float
) -> bool:
    """Check if point is within bounds - should use BoundingBox value object."""
    return (
        south_lat <= lat <= north_lat and
        west_lon <= lon <= east_lon
    )


def get_midpoint(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Tuple[float, float]:
    """Get midpoint between two coordinates."""
    return ((lat1 + lat2) / 2, (lon1 + lon2) / 2)
