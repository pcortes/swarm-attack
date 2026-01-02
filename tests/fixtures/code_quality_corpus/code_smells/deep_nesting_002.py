"""Sample with deep nesting code smell - nested loops and conditions."""
from typing import List, Dict


def find_matching_items(data: List[Dict], criteria: Dict) -> List[Dict]:
    """Find items with excessive nesting."""
    results = []
    if data:
        for group in data:
            if group:
                if "children" in group:
                    for child in group["children"]:
                        if child:
                            if "items" in child:
                                for item in child["items"]:
                                    if item:
                                        matches = True
                                        for key, value in criteria.items():
                                            if key in item:
                                                if item[key] != value:
                                                    matches = False
                                        if matches:
                                            results.append(item)
    return results
