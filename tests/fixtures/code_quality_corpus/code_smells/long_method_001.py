"""Sample with long method code smell - 60+ lines method."""


def process_data(data: dict) -> dict:
    """Process data with way too many lines."""
    # Step 1: Validate
    if not data:
        return {}
    if "id" not in data:
        return {}
    if "name" not in data:
        return {}
    if "type" not in data:
        return {}

    # Step 2: Extract fields
    data_id = data.get("id")
    name = data.get("name")
    data_type = data.get("type")
    value = data.get("value", 0)
    tags = data.get("tags", [])
    metadata = data.get("metadata", {})

    # Step 3: Transform
    processed_name = name.upper()
    processed_type = data_type.lower()
    processed_value = value * 2
    processed_tags = [t.strip() for t in tags]
    processed_meta = {k: v for k, v in metadata.items()}

    # Step 4: More validation
    if len(processed_name) < 1:
        return {}
    if processed_value < 0:
        return {}
    if len(processed_tags) > 100:
        return {}

    # Step 5: Build result
    result = {}
    result["id"] = data_id
    result["name"] = processed_name
    result["type"] = processed_type
    result["value"] = processed_value
    result["tags"] = processed_tags
    result["metadata"] = processed_meta

    # Step 6: Add computed fields
    result["name_length"] = len(processed_name)
    result["tag_count"] = len(processed_tags)
    result["has_metadata"] = bool(processed_meta)
    result["value_category"] = "high" if processed_value > 100 else "low"

    # Step 7: Finalize
    result["processed"] = True
    result["version"] = 1
    result["timestamp"] = "2024-01-01"

    # Step 8: More processing
    if result["value_category"] == "high":
        result["priority"] = 1
    else:
        result["priority"] = 2

    # Step 9: Final adjustments
    if result["has_metadata"]:
        result["enriched"] = True
    else:
        result["enriched"] = False

    return result
