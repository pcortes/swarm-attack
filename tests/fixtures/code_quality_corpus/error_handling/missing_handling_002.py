"""Sample with missing error handling - network operations."""
import requests


def fetch_api_data(endpoint: str) -> dict:
    """Fetch API data - no error handling for network operations."""
    response = requests.get(endpoint)  # No timeout, no try/except
    data = response.json()  # Could fail if not JSON
    return data


def post_data(endpoint: str, payload: dict) -> bool:
    """Post data - no error handling."""
    response = requests.post(endpoint, json=payload)  # No try/except
    return response.status_code == 200
