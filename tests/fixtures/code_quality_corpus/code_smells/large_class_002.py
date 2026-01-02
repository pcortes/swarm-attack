"""Sample with large class code smell - another oversized class."""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import hashlib
import time


@dataclass
class Item:
    id: str
    name: str
    value: int


class DatabaseManager:
    """Another class that is way too large - handles too many concerns."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = []
        self.active_connections = 0
        self.max_connections = 10
        self.queries_executed = 0
        self.cache = {}
        self.transactions = []
        self.schema = {}
        self.indexes = []
        self.triggers = []
        self.views = []
        self.procedures = []
        self.last_error = None
        self.last_query = None
        self.query_log = []

    def connect(self) -> bool:
        """Establish connection."""
        if self.active_connections >= self.max_connections:
            self.last_error = "Max connections reached"
            return False
        self.active_connections += 1
        return True

    def disconnect(self) -> bool:
        """Close connection."""
        if self.active_connections > 0:
            self.active_connections -= 1
            return True
        return False

    def execute_query(self, query: str) -> Optional[List[Dict]]:
        """Execute a query."""
        self.last_query = query
        self.queries_executed += 1
        self.query_log.append(query)
        return []

    def execute_many(self, queries: List[str]) -> List[Optional[List[Dict]]]:
        """Execute multiple queries."""
        return [self.execute_query(q) for q in queries]

    def begin_transaction(self) -> str:
        """Begin transaction."""
        tx_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.transactions.append(tx_id)
        return tx_id

    def commit_transaction(self, tx_id: str) -> bool:
        """Commit transaction."""
        if tx_id in self.transactions:
            self.transactions.remove(tx_id)
            return True
        return False

    def rollback_transaction(self, tx_id: str) -> bool:
        """Rollback transaction."""
        if tx_id in self.transactions:
            self.transactions.remove(tx_id)
            return True
        return False

    def create_table(self, name: str, columns: Dict[str, str]) -> bool:
        """Create table."""
        self.schema[name] = columns
        return True

    def drop_table(self, name: str) -> bool:
        """Drop table."""
        if name in self.schema:
            del self.schema[name]
            return True
        return False

    def alter_table(self, name: str, changes: Dict) -> bool:
        """Alter table."""
        if name in self.schema:
            self.schema[name].update(changes)
            return True
        return False

    def create_index(self, name: str, table: str, columns: List[str]) -> bool:
        """Create index."""
        self.indexes.append({"name": name, "table": table, "columns": columns})
        return True

    def drop_index(self, name: str) -> bool:
        """Drop index."""
        self.indexes = [i for i in self.indexes if i["name"] != name]
        return True

    def insert(self, table: str, data: Dict) -> bool:
        """Insert row."""
        return True

    def update(self, table: str, data: Dict, where: Dict) -> int:
        """Update rows."""
        return 0

    def delete(self, table: str, where: Dict) -> int:
        """Delete rows."""
        return 0

    def select(self, table: str, columns: List[str], where: Optional[Dict] = None) -> List[Dict]:
        """Select rows."""
        return []

    def cache_query(self, key: str, result: Any) -> None:
        """Cache query result."""
        self.cache[key] = result

    def get_cached_query(self, key: str) -> Optional[Any]:
        """Get cached query result."""
        return self.cache.get(key)

    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache."""
        if key:
            self.cache.pop(key, None)
        else:
            self.cache = {}

    def create_view(self, name: str, query: str) -> bool:
        """Create view."""
        self.views.append({"name": name, "query": query})
        return True

    def drop_view(self, name: str) -> bool:
        """Drop view."""
        self.views = [v for v in self.views if v["name"] != name]
        return True

    def create_procedure(self, name: str, body: str) -> bool:
        """Create stored procedure."""
        self.procedures.append({"name": name, "body": body})
        return True

    def call_procedure(self, name: str, params: List[Any]) -> Any:
        """Call stored procedure."""
        return None

    def create_trigger(self, name: str, table: str, event: str, body: str) -> bool:
        """Create trigger."""
        self.triggers.append({
            "name": name,
            "table": table,
            "event": event,
            "body": body
        })
        return True

    def get_table_info(self, name: str) -> Optional[Dict]:
        """Get table info."""
        return self.schema.get(name)

    def list_tables(self) -> List[str]:
        """List all tables."""
        return list(self.schema.keys())

    def list_indexes(self, table: Optional[str] = None) -> List[Dict]:
        """List indexes."""
        if table:
            return [i for i in self.indexes if i["table"] == table]
        return self.indexes.copy()

    def get_stats(self) -> Dict:
        """Get database stats."""
        return {
            "connections": self.active_connections,
            "queries": self.queries_executed,
            "tables": len(self.schema),
            "indexes": len(self.indexes),
            "views": len(self.views),
            "procedures": len(self.procedures),
            "triggers": len(self.triggers),
            "cache_size": len(self.cache),
        }

    def backup(self, path: str) -> bool:
        """Backup database."""
        return True

    def restore(self, path: str) -> bool:
        """Restore database."""
        return True

    def vacuum(self) -> bool:
        """Vacuum database."""
        return True

    def analyze(self) -> Dict:
        """Analyze database."""
        return {"status": "ok"}

    def get_last_error(self) -> Optional[str]:
        """Get last error."""
        return self.last_error

    def get_query_log(self) -> List[str]:
        """Get query log."""
        return self.query_log.copy()

    def clear_query_log(self) -> None:
        """Clear query log."""
        self.query_log = []
