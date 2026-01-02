"""Sample with wrong signature - datetime with wrong method."""
from datetime import datetime


def get_formatted_date() -> str:
    """Get formatted date with wrong method."""
    now = datetime.now()
    # datetime doesn't have format method, should use strftime
    formatted = now.format("%Y-%m-%d")
    return formatted
