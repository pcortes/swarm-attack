"""Sample with swallowed exception - exception in loop."""
from typing import List, Dict


def process_records(records: List[Dict]) -> List[Dict]:
    """Process records - swallows exceptions silently."""
    results = []
    for record in records:
        try:
            processed = {
                "id": record["id"],
                "value": record["value"] / record["divisor"],
                "status": "processed"
            }
            results.append(processed)
        except Exception:
            pass  # ZeroDivisionError, KeyError - all swallowed
    return results
