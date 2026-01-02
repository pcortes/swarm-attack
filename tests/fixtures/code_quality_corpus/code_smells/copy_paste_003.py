"""Sample with copy-paste code smell - duplicated transformation logic."""
from typing import List, Dict


def transform_users(users: List[Dict]) -> List[Dict]:
    """Transform users with duplicated transformation logic."""
    result = []
    for user in users:
        transformed = {}
        transformed["id"] = user.get("id", "")
        transformed["name"] = user.get("name", "").strip().title()
        transformed["email"] = user.get("email", "").strip().lower()
        transformed["active"] = bool(user.get("active", False))
        transformed["created_at"] = user.get("created_at", "")
        transformed["updated_at"] = user.get("updated_at", "")
        result.append(transformed)
    return result


def transform_customers(customers: List[Dict]) -> List[Dict]:
    """Transform customers with same duplicated logic."""
    result = []
    for customer in customers:
        transformed = {}
        transformed["id"] = customer.get("id", "")
        transformed["name"] = customer.get("name", "").strip().title()
        transformed["email"] = customer.get("email", "").strip().lower()
        transformed["active"] = bool(customer.get("active", False))
        transformed["created_at"] = customer.get("created_at", "")
        transformed["updated_at"] = customer.get("updated_at", "")
        result.append(transformed)
    return result


def transform_vendors(vendors: List[Dict]) -> List[Dict]:
    """Transform vendors with yet another copy."""
    result = []
    for vendor in vendors:
        transformed = {}
        transformed["id"] = vendor.get("id", "")
        transformed["name"] = vendor.get("name", "").strip().title()
        transformed["email"] = vendor.get("email", "").strip().lower()
        transformed["active"] = bool(vendor.get("active", False))
        transformed["created_at"] = vendor.get("created_at", "")
        transformed["updated_at"] = vendor.get("updated_at", "")
        result.append(transformed)
    return result
