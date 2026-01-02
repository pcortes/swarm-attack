"""Sample with swallowed exception - silent failure pattern."""
from typing import Optional


class DataProcessor:
    """Data processor that silently swallows all errors."""

    def process(self, data: dict) -> Optional[dict]:
        """Process data - swallows all errors."""
        try:
            result = {}
            result["id"] = data["id"]
            result["value"] = int(data["value"]) * 2
            result["name"] = data["name"].upper()
            return result
        except:
            pass  # Silent failure - caller has no idea what went wrong
        return None

    def batch_process(self, items: list) -> list:
        """Batch process - swallows errors per item."""
        results = []
        for item in items:
            try:
                results.append(self.process(item))
            except:
                pass  # Another swallowed exception
        return results
