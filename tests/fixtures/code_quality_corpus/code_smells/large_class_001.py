"""Sample with large class code smell - class over 300 lines."""
from typing import List, Dict, Optional
import json
import os


class MegaProcessor:
    """A class that does way too many things - over 300 lines."""

    def __init__(self, config: dict):
        self.config = config
        self.data = []
        self.cache = {}
        self.errors = []
        self.warnings = []
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.start_time = None
        self.end_time = None

    def load_data(self, path: str) -> bool:
        """Load data from file."""
        if not os.path.exists(path):
            self.errors.append(f"File not found: {path}")
            return False
        try:
            with open(path) as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            self.errors.append(f"Failed to load: {e}")
            return False

    def save_data(self, path: str) -> bool:
        """Save data to file."""
        try:
            with open(path, "w") as f:
                json.dump(self.data, f)
            return True
        except Exception as e:
            self.errors.append(f"Failed to save: {e}")
            return False

    def validate_item(self, item: dict) -> bool:
        """Validate a single item."""
        if not item:
            return False
        if "id" not in item:
            return False
        if "name" not in item:
            return False
        return True

    def validate_all(self) -> int:
        """Validate all items."""
        valid = 0
        for item in self.data:
            if self.validate_item(item):
                valid += 1
        return valid

    def transform_item(self, item: dict) -> dict:
        """Transform a single item."""
        return {
            "id": item.get("id"),
            "name": item.get("name", "").upper(),
            "value": item.get("value", 0) * 2,
        }

    def transform_all(self) -> List[dict]:
        """Transform all items."""
        return [self.transform_item(i) for i in self.data]

    def filter_by_name(self, pattern: str) -> List[dict]:
        """Filter items by name pattern."""
        return [i for i in self.data if pattern in i.get("name", "")]

    def filter_by_value(self, min_val: int, max_val: int) -> List[dict]:
        """Filter items by value range."""
        return [
            i for i in self.data
            if min_val <= i.get("value", 0) <= max_val
        ]

    def sort_by_name(self) -> List[dict]:
        """Sort items by name."""
        return sorted(self.data, key=lambda x: x.get("name", ""))

    def sort_by_value(self, reverse: bool = False) -> List[dict]:
        """Sort items by value."""
        return sorted(self.data, key=lambda x: x.get("value", 0), reverse=reverse)

    def group_by_type(self) -> Dict[str, List[dict]]:
        """Group items by type."""
        groups = {}
        for item in self.data:
            t = item.get("type", "unknown")
            if t not in groups:
                groups[t] = []
            groups[t].append(item)
        return groups

    def calculate_sum(self) -> int:
        """Calculate sum of all values."""
        return sum(i.get("value", 0) for i in self.data)

    def calculate_average(self) -> float:
        """Calculate average value."""
        if not self.data:
            return 0.0
        return self.calculate_sum() / len(self.data)

    def calculate_min(self) -> int:
        """Calculate minimum value."""
        if not self.data:
            return 0
        return min(i.get("value", 0) for i in self.data)

    def calculate_max(self) -> int:
        """Calculate maximum value."""
        if not self.data:
            return 0
        return max(i.get("value", 0) for i in self.data)

    def get_by_id(self, item_id: str) -> Optional[dict]:
        """Get item by ID."""
        for item in self.data:
            if item.get("id") == item_id:
                return item
        return None

    def update_by_id(self, item_id: str, updates: dict) -> bool:
        """Update item by ID."""
        item = self.get_by_id(item_id)
        if item:
            item.update(updates)
            return True
        return False

    def delete_by_id(self, item_id: str) -> bool:
        """Delete item by ID."""
        for i, item in enumerate(self.data):
            if item.get("id") == item_id:
                del self.data[i]
                return True
        return False

    def add_item(self, item: dict) -> bool:
        """Add new item."""
        if self.validate_item(item):
            self.data.append(item)
            return True
        return False

    def clear_all(self) -> None:
        """Clear all data."""
        self.data = []
        self.cache = {}

    def get_count(self) -> int:
        """Get item count."""
        return len(self.data)

    def is_empty(self) -> bool:
        """Check if empty."""
        return len(self.data) == 0

    def export_csv(self, path: str) -> bool:
        """Export data to CSV."""
        try:
            with open(path, "w") as f:
                if self.data:
                    headers = list(self.data[0].keys())
                    f.write(",".join(headers) + "\n")
                    for item in self.data:
                        row = [str(item.get(h, "")) for h in headers]
                        f.write(",".join(row) + "\n")
            return True
        except Exception as e:
            self.errors.append(f"CSV export failed: {e}")
            return False

    def import_csv(self, path: str) -> bool:
        """Import data from CSV."""
        try:
            with open(path) as f:
                lines = f.readlines()
                if not lines:
                    return False
                headers = lines[0].strip().split(",")
                for line in lines[1:]:
                    values = line.strip().split(",")
                    item = dict(zip(headers, values))
                    self.data.append(item)
            return True
        except Exception as e:
            self.errors.append(f"CSV import failed: {e}")
            return False

    def cache_item(self, key: str, item: dict) -> None:
        """Cache an item."""
        self.cache[key] = item

    def get_cached(self, key: str) -> Optional[dict]:
        """Get cached item."""
        return self.cache.get(key)

    def clear_cache(self) -> None:
        """Clear cache."""
        self.cache = {}

    def log_error(self, message: str) -> None:
        """Log an error."""
        self.errors.append(message)

    def log_warning(self, message: str) -> None:
        """Log a warning."""
        self.warnings.append(message)

    def get_errors(self) -> List[str]:
        """Get all errors."""
        return self.errors.copy()

    def get_warnings(self) -> List[str]:
        """Get all warnings."""
        return self.warnings.copy()

    def clear_logs(self) -> None:
        """Clear all logs."""
        self.errors = []
        self.warnings = []

    def get_stats(self) -> dict:
        """Get processing stats."""
        return {
            "total": len(self.data),
            "processed": self.processed_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }

    def reset_stats(self) -> None:
        """Reset stats."""
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0

    def merge_data(self, other_data: List[dict]) -> None:
        """Merge other data into this dataset."""
        self.data.extend(other_data)

    def deduplicate(self) -> int:
        """Remove duplicate items."""
        seen = set()
        unique = []
        for item in self.data:
            item_id = item.get("id")
            if item_id not in seen:
                seen.add(item_id)
                unique.append(item)
        removed = len(self.data) - len(unique)
        self.data = unique
        return removed

    def batch_process(self, batch_size: int = 100) -> int:
        """Process data in batches."""
        processed = 0
        for i in range(0, len(self.data), batch_size):
            batch = self.data[i:i + batch_size]
            for item in batch:
                if self.validate_item(item):
                    self.transform_item(item)
                    processed += 1
        return processed
