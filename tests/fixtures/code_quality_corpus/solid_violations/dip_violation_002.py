"""Sample with DIP violation - new operator in business logic."""
from typing import List, Dict
from datetime import datetime


class ReportGenerator:
    """Report generator that violates DIP - instantiates dependencies inline."""

    def generate_sales_report(self, start_date: datetime, end_date: datetime) -> str:
        # DIP violation: Creating concrete implementations inline
        data_source = MySqlDataSource(
            host="localhost",
            port=3306,
            database="sales"
        )

        formatter = PdfFormatter(page_size="A4", orientation="landscape")

        exporter = S3Exporter(
            bucket="reports",
            region="us-east-1"
        )

        # Business logic tightly coupled to concrete implementations
        raw_data = data_source.query(
            f"SELECT * FROM sales WHERE date BETWEEN '{start_date}' AND '{end_date}'"
        )

        formatted = formatter.format(raw_data)
        path = exporter.upload(formatted)

        return path


class MySqlDataSource:
    """MySQL data source."""

    def __init__(self, host: str, port: int, database: str):
        self.host = host
        self.port = port
        self.database = database

    def query(self, sql: str) -> List[Dict]:
        return []


class PdfFormatter:
    """PDF formatter."""

    def __init__(self, page_size: str, orientation: str):
        self.page_size = page_size
        self.orientation = orientation

    def format(self, data: List[Dict]) -> bytes:
        return b""


class S3Exporter:
    """S3 exporter."""

    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.region = region

    def upload(self, data: bytes) -> str:
        return "s3://reports/report.pdf"
