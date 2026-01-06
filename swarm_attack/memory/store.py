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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, Union

from swarm_attack.memory.relevance import RelevanceScorer


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

    def __len__(self) -> int:
        """Return number of entries in the store."""
        return len(self._entries)

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

    def get_schema_drift_warnings(self, class_names: list[str]) -> list[MemoryEntry]:
        """Get schema drift entries for the given class names.

        Searches for schema_drift category entries that have a class_name
        or class in their content matching any of the provided class names.

        Args:
            class_names: List of class names to search for.

        Returns:
            List of MemoryEntry objects matching the class names.
        """
        if not class_names:
            return []

        results: list[MemoryEntry] = []
        class_names_set = set(class_names)

        for entry in self._entries.values():
            if entry.category != "schema_drift":
                continue

            # Check if the entry's class_name or class matches any in the list
            # Support both "class_name" and "class" keys (common variations)
            entry_class_name = entry.content.get("class_name") or entry.content.get("class")
            if entry_class_name and entry_class_name in class_names_set:
                entry.hit_count += 1
                results.append(entry)

        return results

    def get_test_failure_patterns(self, test_path: str) -> list[MemoryEntry]:
        """Get test failure entries matching the test path.

        Searches for test_failure category entries where the test_path
        in content matches the provided path.

        Args:
            test_path: The test file path to search for.

        Returns:
            List of MemoryEntry objects matching the test path.
        """
        results: list[MemoryEntry] = []

        for entry in self._entries.values():
            if entry.category != "test_failure":
                continue

            # Check if the entry's test_path matches
            entry_test_path = entry.content.get("test_path")
            if entry_test_path == test_path:
                entry.hit_count += 1
                results.append(entry)

        return results

    def get_recent_entries(self, category: str, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent entries for a category, sorted by timestamp desc.

        Args:
            category: The category to filter by.
            limit: Maximum number of entries to return. Defaults to 10.

        Returns:
            List of MemoryEntry objects sorted by created_at descending.
        """
        # Filter by category
        category_entries = [
            entry for entry in self._entries.values()
            if entry.category == category
        ]

        # Sort by created_at descending (most recent first)
        category_entries.sort(key=lambda e: e.created_at, reverse=True)

        # Apply limit and update hit counts
        results = category_entries[:limit]
        for entry in results:
            entry.hit_count += 1

        return results

    def prune_old_entries(self, days: int) -> int:
        """Remove entries older than N days.

        Args:
            days: Remove entries older than this many days.
                  If days=0, nothing is removed (edge case).

        Returns:
            Count of entries removed.
        """
        if days <= 0:
            return 0

        cutoff = datetime.now() - timedelta(days=days)
        to_remove: list[str] = []

        for entry_id, entry in self._entries.items():
            entry_date = datetime.fromisoformat(entry.created_at)
            if entry_date < cutoff:
                to_remove.append(entry_id)

        for entry_id in to_remove:
            del self._entries[entry_id]

        return len(to_remove)

    def prune_low_value_entries(self, min_hits: int = 1) -> int:
        """Remove entries with fewer than min_hits query hits.

        Args:
            min_hits: Minimum hit_count to keep an entry. Entries with
                      hit_count < min_hits will be removed. Defaults to 1.

        Returns:
            Count of entries removed.
        """
        to_remove: list[str] = []

        for entry_id, entry in self._entries.items():
            if entry.hit_count < min_hits:
                to_remove.append(entry_id)

        for entry_id in to_remove:
            del self._entries[entry_id]

        return len(to_remove)

    def clear(self) -> None:
        """Clear all entries from the store."""
        self._entries.clear()
        self._query_count = 0

    def prune_by_relevance(
        self,
        threshold: float = 0.3,
        min_entries: int = 10
    ) -> int:
        """Remove entries below relevance threshold.

        Uses RelevanceScorer to calculate scores. The threshold is compared
        against normalized scores (0-1 range based on min-max in the set).
        Keeps at least min_entries regardless of threshold.
        Returns count of removed entries.

        Args:
            threshold: Minimum normalized relevance score (0-1) to keep an entry.
                      Entries with normalized score < threshold are candidates for removal.
            min_entries: Minimum number of entries to keep regardless of threshold.
                        The highest scoring entries are kept.

        Returns:
            Count of entries removed.
        """
        if not self._entries:
            return 0

        scorer = RelevanceScorer()

        # Score all entries
        scored_entries: List[tuple[float, str]] = []
        for entry_id, entry in self._entries.items():
            score = scorer.score(entry)
            scored_entries.append((score, entry_id))

        # Sort by score descending (highest first)
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # Find min and max for normalization
        max_score = scored_entries[0][0]
        min_score = scored_entries[-1][0]
        score_range = max_score - min_score

        total_entries = len(self._entries)

        # Check if entries are tightly clustered (within 20% of each other)
        scores_are_similar = score_range < 0.2 * max_score if max_score > 0 else True

        # Separate entries by normalized threshold
        above_threshold: List[tuple[float, str]] = []
        below_threshold: List[tuple[float, str]] = []

        for score, entry_id in scored_entries:
            if score_range > 0 and not scores_are_similar:
                # Normalize to 0-1 range based on min-max
                normalized_score = (score - min_score) / score_range
                if normalized_score >= threshold:
                    above_threshold.append((score, entry_id))
                else:
                    below_threshold.append((score, entry_id))
            else:
                # All entries have similar scores - all go to above_threshold
                # (but we'll still apply min_entries logic below)
                above_threshold.append((score, entry_id))

        entries_to_keep: set[str] = set()

        if above_threshold and not below_threshold:
            # All entries are above threshold (or similar)
            # Apply min_entries pruning only for high thresholds on similar scores
            # High threshold (>= 0.5) with similar scores suggests pruning is intended
            # Low threshold (< 0.5) with similar scores suggests all entries are acceptable
            if scores_are_similar and total_entries > min_entries and threshold >= 0.5:
                # When scores are similar and threshold is high, prune to min_entries
                # Keep the top min_entries (they're all similar, so just keep first N)
                entries_to_keep = {entry_id for _, entry_id in scored_entries[:min_entries]}
            else:
                # Keep all above-threshold entries (low threshold or diverse scores)
                entries_to_keep = {entry_id for _, entry_id in above_threshold}
        elif above_threshold:
            # Case: Some entries are above threshold, some below
            # Always keep all above-threshold entries
            entries_to_keep = {entry_id for _, entry_id in above_threshold}

            # If we have enough total entries to meet min_entries,
            # also keep top below-threshold entries to reach min_entries
            if total_entries >= min_entries and len(above_threshold) < min_entries:
                needed_from_below = min_entries - len(above_threshold)
                for i, (_, entry_id) in enumerate(below_threshold):
                    if i < needed_from_below:
                        entries_to_keep.add(entry_id)
        else:
            # Case: ALL entries are below threshold
            # Apply min_entries constraint - keep at least min_entries of the highest scoring
            if total_entries <= min_entries:
                # Keep all since we have fewer than min_entries
                entries_to_keep = {entry_id for _, entry_id in below_threshold}
            else:
                # Keep top min_entries by score
                entries_to_keep = {entry_id for _, entry_id in below_threshold[:min_entries]}

        # Remove entries not in keep set
        to_remove = [eid for eid in self._entries if eid not in entries_to_keep]
        for entry_id in to_remove:
            del self._entries[entry_id]

        return len(to_remove)

    def get_by_relevance(
        self,
        category: str = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get entries sorted by relevance score.

        Optionally filter by category.
        Returns up to limit entries, highest relevance first.

        Args:
            category: Optional category to filter by.
            limit: Maximum number of entries to return.

        Returns:
            List of MemoryEntry objects sorted by relevance score (highest first).
        """
        scorer = RelevanceScorer()

        # Filter by category if specified
        candidates = []
        for entry in self._entries.values():
            if category is not None and entry.category != category:
                continue
            candidates.append(entry)

        if not candidates:
            return []

        # Score and sort by relevance (highest first)
        scored: List[tuple[float, MemoryEntry]] = []
        for entry in candidates:
            score = scorer.score(entry)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Get top N entries
        results = [entry for _, entry in scored[:limit]]

        # Update hit counts for returned entries
        for entry in results:
            entry.hit_count += 1

        return results

    def save_to_file(self, path: Union[str, Path]) -> None:
        """Save memory store to JSON file.

        Creates parent directories if they don't exist.
        Format matches existing save() method.

        Args:
            path: Path to save the JSON file to (str or Path object).
        """
        path = Path(path)  # Convert to Path if string
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "entries": [e.to_dict() for e in self._entries.values()],
            "stats": {
                "total_queries": self._query_count,
                "last_saved": datetime.now().isoformat(),
            },
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, path: Union[str, Path]) -> None:
        """Load memory store from JSON file.

        Adds entries to existing store (doesn't replace).
        Handles corrupted/missing files gracefully.

        Args:
            path: Path to the JSON file to load from (str or Path object).
        """
        path = Path(path)  # Convert to Path if string
        if not path.exists():
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Handle case where data is not a dict (e.g., JSON array)
            if not isinstance(data, dict):
                return

            for entry_data in data.get("entries", []):
                entry = MemoryEntry.from_dict(entry_data)
                self._entries[entry.id] = entry

            # Load stats if present
            stats = data.get("stats", {})
            if "total_queries" in stats:
                self._query_count = stats["total_queries"]

        except (json.JSONDecodeError, IOError, OSError, KeyError, TypeError):
            # Gracefully handle corrupted/empty/malformed files
            pass

    @classmethod
    def from_file(cls, path: Path) -> "MemoryStore":
        """Create new store from file.

        Returns empty store if file doesn't exist or is corrupted.

        Args:
            path: Path to the JSON file to load from.

        Returns:
            MemoryStore instance with loaded entries, or empty store on error.
        """
        store = cls()
        store.load_from_file(path)
        return store


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
