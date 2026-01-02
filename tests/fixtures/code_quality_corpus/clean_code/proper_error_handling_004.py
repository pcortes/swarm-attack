"""Clean module with context manager for resource handling."""
from typing import Optional, Iterator
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Database connection with proper resource management."""

    def __init__(self, connection_string: str):
        """Initialize connection."""
        self._connection_string = connection_string
        self._connected = False

    def connect(self) -> None:
        """Establish database connection."""
        logger.info(f"Connecting to database...")
        self._connected = True

    def disconnect(self) -> None:
        """Close database connection."""
        if self._connected:
            logger.info("Disconnecting from database...")
            self._connected = False

    def execute(self, query: str) -> list:
        """Execute a query."""
        if not self._connected:
            raise RuntimeError("Not connected to database")
        logger.debug(f"Executing: {query}")
        return []


@contextmanager
def database_connection(connection_string: str) -> Iterator[DatabaseConnection]:
    """Context manager for database connections.

    Ensures the connection is properly closed even if an error occurs.

    Args:
        connection_string: The database connection string.

    Yields:
        An active database connection.
    """
    conn = DatabaseConnection(connection_string)
    try:
        conn.connect()
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.disconnect()


def run_query(connection_string: str, query: str) -> list:
    """Run a query with automatic connection management.

    Args:
        connection_string: The database connection string.
        query: The SQL query to execute.

    Returns:
        Query results.
    """
    with database_connection(connection_string) as conn:
        return conn.execute(query)
