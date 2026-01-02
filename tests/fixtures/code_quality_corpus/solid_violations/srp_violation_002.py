"""Sample with SRP violation - report class doing formatting and data retrieval."""
from typing import Dict, List
from datetime import datetime
import csv
import json


class SalesReport:
    """Sales report class that violates SRP - data retrieval + multiple formats."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data: List[Dict] = []

    # Data retrieval (responsibility 1)
    def fetch_sales_data(self, start_date: datetime, end_date: datetime) -> None:
        """Fetch sales data from database."""
        # Simulated - would query database
        self.data = []

    def filter_by_region(self, region: str) -> None:
        """Filter data by region."""
        self.data = [d for d in self.data if d.get("region") == region]

    def filter_by_product(self, product: str) -> None:
        """Filter data by product."""
        self.data = [d for d in self.data if d.get("product") == product]

    # CSV formatting (responsibility 2)
    def to_csv(self, path: str) -> None:
        """Export to CSV."""
        with open(path, "w", newline="") as f:
            if self.data:
                writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
                writer.writeheader()
                writer.writerows(self.data)

    # JSON formatting (responsibility 3)
    def to_json(self, path: str) -> None:
        """Export to JSON."""
        with open(path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    # HTML formatting (responsibility 4)
    def to_html(self, path: str) -> None:
        """Export to HTML."""
        html = "<html><body><table>"
        if self.data:
            html += "<tr>" + "".join(f"<th>{k}</th>" for k in self.data[0].keys()) + "</tr>"
            for row in self.data:
                html += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"
        html += "</table></body></html>"
        with open(path, "w") as f:
            f.write(html)

    # Statistics (responsibility 5)
    def calculate_total(self) -> float:
        """Calculate total sales."""
        return sum(d.get("amount", 0) for d in self.data)

    def calculate_average(self) -> float:
        """Calculate average sale."""
        return self.calculate_total() / len(self.data) if self.data else 0
