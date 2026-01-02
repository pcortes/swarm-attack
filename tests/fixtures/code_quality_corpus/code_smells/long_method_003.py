"""Sample with long method code smell - data transformation."""
from typing import List, Dict


def transform_user_data(users: List[Dict]) -> List[Dict]:
    """Transform user data - extremely long method."""
    result = []

    for user in users:
        # Validate user
        if not user:
            continue
        if "id" not in user:
            continue
        if "email" not in user:
            continue

        # Extract basic info
        user_id = user.get("id")
        email = user.get("email", "").lower()
        name = user.get("name", "")
        age = user.get("age", 0)
        active = user.get("active", True)

        # Validate email
        if "@" not in email:
            continue
        if "." not in email:
            continue
        if len(email) < 5:
            continue

        # Process name
        if name:
            name = name.strip()
            name = name.title()
            parts = name.split()
            first_name = parts[0] if parts else ""
            last_name = parts[-1] if len(parts) > 1 else ""
        else:
            first_name = ""
            last_name = ""

        # Process age
        if age < 0:
            age = 0
        if age > 150:
            age = 150
        age_group = "child" if age < 18 else "adult" if age < 65 else "senior"

        # Build transformed user
        transformed = {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": name,
            "age": age,
            "age_group": age_group,
            "active": active,
            "processed": True,
        }

        result.append(transformed)

    return result
