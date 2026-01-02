"""Sample with bare except - catches everything including KeyboardInterrupt."""


def dangerous_operation(data: dict) -> dict:
    """Dangerous bare except - catches everything."""
    try:
        result = data["key1"]["key2"]["key3"]
        return {"value": result}
    except:  # Bare except - catches KeyboardInterrupt, SystemExit, etc.
        return {"error": "Something went wrong"}
