"""Sample with bare except - in a loop."""
from typing import List


def process_items(items: List[dict]) -> List[dict]:
    """Process with bare except in loop."""
    results = []
    for item in items:
        try:
            value = item["value"] * 2
            results.append({"id": item["id"], "value": value})
        except:  # Bare except catches everything
            results.append({"id": None, "error": True})
    return results
