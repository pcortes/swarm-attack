"""
Persistent Memory Store for Swarm Attack.

Phase A implementation provides:
- MemoryEntry dataclass for structured memory entries
- MemoryStore class for JSON-based persistence
- Query by category, feature_id, tags
- Simple keyword-based similarity search (no embeddings)

This module enables cross-session learning by persisting:
- Checkpoint decisions and their outcomes
- Schema drift detections
- Test failure patterns
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class MemoryEntry:
    """A single memory entry in the persistent store.

    Attributes:
        id: Unique identifier (UUID string).
        category: Entry type (e.g., "checkpoint_decision", "schema_drift", "test_failure").
        feature_id: The feature this memory relates to.
        issue_number: Optional issue number for issue-specific memories.
        content: Flexible payload with memory-specific data.
        outcome: Result of the action (e.g., "success", "failure", "blocked", "applied").
        created_at: ISO timestamp of when the memory was created.
        tags: Searchable tags for filtering.
        hit_count: Number of times this entry was returned in queries (for value tracking).
    """

    id: str
    category: str
    feature_id: str
    issue_number: Optional[int]
    content: dict[str, Any]
    outcome: Optional[str]
    created_at: str
    tags: list[str] = field(default_factory=list)
    hit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "category": self.category,
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
            "content": self.content,
            "outcome": self.outcome,
            "created_at": self.created_at,
            "tags": self.tags,
            "hit_count": self.hit_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            category=data["category"],
            feature_id=data["feature_id"],
            issue_number=data.get("issue_number"),
            content=data.get("content", {}),
            outcome=data.get("outcome"),
            created_at=data["created_at"],
            tags=data.get("tags", []),
            hit_count=data.get("hit_count", 0),
        )


class MemoryStore:
    """Persistent memory storage using JSON file.

    Provides:
    - add(): Add a memory entry
    - query(): Filter by category, feature_id, tags
    - find_similar(): Keyword-based similarity search
    - save(): Persist to disk
    - load(): Load from disk

    Storage location: .swarm/memory/memories.json (default)
    """

    def __init__(self, store_path: Optional[Path] = None):
        """Initialize the memory store.

        Args:
            store_path: Path to the JSON file. Defaults to .swarm/memory/memories.json
        """
        if store_path is None:
            store_path = Path.cwd() / ".swarm" / "memory" / "memories.json"
        self.store_path = store_path
        self._entries: dict[str, MemoryEntry] = {}
        self._query_count = 0

    def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry to the store.

        Args:
            entry: The MemoryEntry to add.
        """
        self._entries[entry.id] = entry

    def save(self) -> None:
        """Persist the store to disk.

        Creates parent directories if they don't exist.
        """
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "entries": [e.to_dict() for e in self._entries.values()],
            "stats": {
                "total_queries": self._query_count,
                "last_saved": datetime.now().isoformat(),
            },
        }

        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, store_path: Optional[Path] = None) -> "MemoryStore":
        """Load a memory store from disk.

        Args:
            store_path: Path to the JSON file. Defaults to .swarm/memory/memories.json

        Returns:
            MemoryStore instance with loaded entries.
        """
        store = cls(store_path=store_path)

        if not store.store_path.exists():
            return store

        try:
            with open(store.store_path, "r") as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = MemoryEntry.from_dict(entry_data)
                store._entries[entry.id] = entry

            store._query_count = data.get("stats", {}).get("total_queries", 0)

        except (json.JSONDecodeError, IOError, OSError):
            # Gracefully handle corrupted/empty files
            pass

        return store

    def query(
        self,
        category: Optional[str] = None,
        feature_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Query memories by filters.

        All filters are ANDed together. Entries matching all specified
        filters are returned.

        Args:
            category: Filter by entry category.
            feature_id: Filter by feature ID.
            tags: Filter by tags (entry must have ALL specified tags).
            limit: Maximum number of results to return.

        Returns:
            List of matching MemoryEntry objects.
        """
        self._query_count += 1
        results: list[MemoryEntry] = []

        for entry in self._entries.values():
            # Apply category filter
            if category is not None and entry.category != category:
                continue

            # Apply feature_id filter
            if feature_id is not None and entry.feature_id != feature_id:
                continue

            # Apply tags filter (must have ALL specified tags)
            if tags is not None:
                entry_tags_lower = {t.lower() for t in entry.tags}
                query_tags_lower = {t.lower() for t in tags}
                if not query_tags_lower.issubset(entry_tags_lower):
                    continue

            # Entry matches all filters
            entry.hit_count += 1
            results.append(entry)

            if len(results) >= limit:
                break

        return results

    def find_similar(
        self,
        content: dict[str, Any],
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Find similar memories using keyword matching.

        Phase A uses simple keyword matching on content values.
        Phase B will add embedding-based semantic similarity.

        Args:
            content: Dictionary with keys/values to match.
            category: Optional category filter.
            limit: Maximum number of results.

        Returns:
            List of matching MemoryEntry objects, sorted by relevance.
        """
        self._query_count += 1

        # Extract keywords from query content
        query_keywords = self._extract_keywords(content)
        if not query_keywords:
            return []

        # Score each entry by keyword overlap
        scored: list[tuple[float, MemoryEntry]] = []

        for entry in self._entries.values():
            # Apply category filter
            if category is not None and entry.category != category:
                continue

            # Extract keywords from entry content
            entry_keywords = self._extract_keywords(entry.content)

            # Calculate overlap score
            if not entry_keywords:
                continue

            overlap = len(query_keywords & entry_keywords)
            if overlap > 0:
                # Normalize by query keywords for relevance
                score = overlap / len(query_keywords)
                scored.append((score, entry))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top results
        results = [entry for _, entry in scored[:limit]]

        # Update hit counts
        for entry in results:
            entry.hit_count += 1

        return results

    def _extract_keywords(self, content: dict[str, Any]) -> set[str]:
        """Extract searchable keywords from content dictionary.

        Flattens nested dictionaries and extracts string values.

        Args:
            content: Dictionary to extract keywords from.

        Returns:
            Set of lowercase keyword strings.
        """
        keywords: set[str] = set()

        def extract(obj: Any) -> None:
            if isinstance(obj, str):
                # Add the string value as keyword
                keywords.add(obj.lower())
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    # Add dict keys as keywords
                    keywords.add(str(key).lower())
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(content)
        return keywords

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics for value measurement.

        Returns:
            Dictionary with:
            - total_entries: Number of entries in store
            - total_queries: Number of queries performed
            - entries_by_category: Count of entries per category
            - avg_hit_count: Average hit count per entry
        """
        entries_by_category: dict[str, int] = {}
        total_hits = 0

        for entry in self._entries.values():
            cat = entry.category
            entries_by_category[cat] = entries_by_category.get(cat, 0) + 1
            total_hits += entry.hit_count

        total_entries = len(self._entries)
        avg_hit_count = total_hits / total_entries if total_entries > 0 else 0.0

        return {
            "total_entries": total_entries,
            "total_queries": self._query_count,
            "entries_by_category": entries_by_category,
            "avg_hit_count": avg_hit_count,
        }

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID.

        Args:
            entry_id: The ID of the entry to retrieve.

        Returns:
            The MemoryEntry if found, None otherwise.
        """
        return self._entries.get(entry_id)

    def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID.

        Args:
            entry_id: The ID of the entry to delete.

        Returns:
            True if deleted, False if not found.
        """
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from the store."""
        self._entries.clear()
        self._query_count = 0


# Global memory store singleton for convenience
_global_store: Optional[MemoryStore] = None


def get_global_memory_store() -> MemoryStore:
    """Get the global memory store singleton.

    This provides a convenient way to access a shared MemoryStore instance
    without having to manage the lifecycle manually. Useful for production
    code while still supporting dependency injection in tests.

    Returns:
        The global MemoryStore instance, created on first call.
    """
    global _global_store
    if _global_store is None:
        _global_store = MemoryStore.load()
    return _global_store
