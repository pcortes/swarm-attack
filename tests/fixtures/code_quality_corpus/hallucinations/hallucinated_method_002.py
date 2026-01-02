"""Sample with hallucinated method - dict method that doesn't exist."""


def process_config(config: dict) -> dict:
    """Process config using non-existent dict method."""
    # dict has no deep_merge method
    result = config.deep_merge({"default": True})
    return result
