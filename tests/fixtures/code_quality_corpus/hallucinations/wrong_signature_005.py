"""Sample with wrong signature - requests.get with wrong parameters."""
import requests


def fetch_url(url: str) -> str:
    """Fetch URL with wrong parameters."""
    # requests.get doesn't have 'follow_redirects' parameter
    # should be allow_redirects
    response = requests.get(url, follow_redirects=True, timeout_seconds=30)
    return response.text
