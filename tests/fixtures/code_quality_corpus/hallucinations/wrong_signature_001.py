"""Sample with wrong signature - json.loads with wrong parameters."""
import json


def parse_data(data: str) -> dict:
    """Parse JSON with wrong parameter name."""
    # json.loads uses 's' not 'json_string', and encoding param doesn't exist
    result = json.loads(json_string=data, encoding="utf-8")
    return result
