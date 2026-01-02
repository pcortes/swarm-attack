"""Sample with deep nesting code smell - over 4 levels."""
from typing import Optional, Dict


def process_deeply_nested(data: Dict) -> Optional[str]:
    """Process data with way too much nesting."""
    if data:
        if "items" in data:
            items = data["items"]
            if isinstance(items, list):
                for item in items:
                    if item:
                        if "type" in item:
                            item_type = item["type"]
                            if item_type == "special":
                                if "value" in item:
                                    value = item["value"]
                                    if value > 0:
                                        if value < 100:
                                            return f"Valid: {value}"
    return None
