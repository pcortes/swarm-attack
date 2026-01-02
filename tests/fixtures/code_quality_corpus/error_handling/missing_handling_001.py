"""Sample with missing error handling - file operations without try/except."""
import json


def load_user_data(path: str) -> dict:
    """Load user data - no error handling for file operations."""
    with open(path) as f:  # No try/except - FileNotFoundError will crash
        data = json.load(f)  # No try/except - JSONDecodeError will crash
    return data


def save_user_data(path: str, data: dict) -> None:
    """Save user data - no error handling."""
    with open(path, "w") as f:  # No try/except - PermissionError will crash
        json.dump(data, f)
