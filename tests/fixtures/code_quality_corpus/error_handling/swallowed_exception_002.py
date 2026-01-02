"""Sample with swallowed exception - exception caught but not used."""
import requests


def fetch_data(url: str) -> dict:
    """Fetch data - catches exception but ignores it completely."""
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except requests.RequestException as e:
        pass  # Swallowed - no logging, no re-raise, no default return
    return {}
