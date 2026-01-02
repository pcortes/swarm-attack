"""Sample with primitive obsession code smell - using primitives instead of objects."""
from typing import Dict, Optional


def create_order(
    customer_first_name: str,
    customer_last_name: str,
    customer_email: str,
    customer_phone: str,
    customer_street: str,
    customer_city: str,
    customer_state: str,
    customer_zip: str,
    customer_country: str,
    item_name: str,
    item_sku: str,
    item_quantity: int,
    item_price_cents: int,
    item_weight_grams: int,
    shipping_method: str,
    shipping_cost_cents: int,
    tax_rate_percent: float,
    discount_percent: float,
) -> Dict:
    """Create order using primitive obsession - should use value objects."""
    return {
        "customer": {
            "first_name": customer_first_name,
            "last_name": customer_last_name,
            "email": customer_email,
            "phone": customer_phone,
            "address": {
                "street": customer_street,
                "city": customer_city,
                "state": customer_state,
                "zip": customer_zip,
                "country": customer_country,
            }
        },
        "item": {
            "name": item_name,
            "sku": item_sku,
            "quantity": item_quantity,
            "price_cents": item_price_cents,
            "weight_grams": item_weight_grams,
        },
        "shipping": {
            "method": shipping_method,
            "cost_cents": shipping_cost_cents,
        },
        "tax_rate_percent": tax_rate_percent,
        "discount_percent": discount_percent,
    }
