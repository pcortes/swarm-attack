"""Sample with copy-paste code smell - duplicate code blocks."""
from typing import Dict, List


def process_orders(orders: List[Dict]) -> List[Dict]:
    """Process orders with duplicated validation logic."""
    results = []

    for order in orders:
        # Duplicated validation block 1
        if not order:
            continue
        if "id" not in order:
            continue
        if "customer_id" not in order:
            continue
        if "items" not in order:
            continue
        if not order["items"]:
            continue

        order["status"] = "validated"
        results.append(order)

    return results


def process_invoices(invoices: List[Dict]) -> List[Dict]:
    """Process invoices with the same duplicated validation logic."""
    results = []

    for invoice in invoices:
        # Duplicated validation block 2 (copy of block 1)
        if not invoice:
            continue
        if "id" not in invoice:
            continue
        if "customer_id" not in invoice:
            continue
        if "items" not in invoice:
            continue
        if not invoice["items"]:
            continue

        invoice["status"] = "validated"
        results.append(invoice)

    return results


def process_shipments(shipments: List[Dict]) -> List[Dict]:
    """Process shipments with yet another copy of validation logic."""
    results = []

    for shipment in shipments:
        # Duplicated validation block 3 (same logic again)
        if not shipment:
            continue
        if "id" not in shipment:
            continue
        if "customer_id" not in shipment:
            continue
        if "items" not in shipment:
            continue
        if not shipment["items"]:
            continue

        shipment["status"] = "validated"
        results.append(shipment)

    return results
