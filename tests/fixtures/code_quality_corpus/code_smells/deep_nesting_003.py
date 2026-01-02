"""Sample with deep nesting code smell - validation hell."""
from typing import Optional


def validate_user_input(data: dict) -> Optional[str]:
    """Validate input with absurd nesting."""
    if data is not None:
        if isinstance(data, dict):
            if "user" in data:
                user = data["user"]
                if user is not None:
                    if "email" in user:
                        email = user["email"]
                        if email:
                            if "@" in email:
                                if "." in email:
                                    parts = email.split("@")
                                    if len(parts) == 2:
                                        if len(parts[0]) > 0:
                                            if len(parts[1]) > 2:
                                                return email
    return None
