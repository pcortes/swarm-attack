"""
MemoryIndex - Inverted index for fast memory search.

Provides:
- Inverted index built on MemoryStore load
- Index updates on entry add/delete
- Fast keyword-based lookup via index
- Persistence alongside the MemoryStore
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from swarm_attack.memory.store import MemoryEntry, MemoryStore


# Current index version - increment when format changes
INDEX_VERSION = "1.0"


class MemoryIndex:
    """Inverted index for fast memory search.

    Provides O(1) lookup by keyword instead of O(n) scanning through all entries.
    Supports indexing of:
    - Content values (recursively extracted from nested dicts)
    - Tags
    - Category
    - Feature ID

    The index is persisted alongside the MemoryStore for fast startup.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        index_path: Optional[Path] = None,
    ):
        """Initialize the memory index.

        Args:
            store: The MemoryStore to build index from. If None, creates empty index.
            index_path: Path to persist the index. If None, defaults to index.json
                       in the same directory as the store file.
        """
        self.store = store
        self._inverted_index: Dict[str, Set[str]] = {}

        # Determine index path
        if index_path is not None:
            self._index_path = index_path
        elif store is not None and store.store_path is not None:
            self._index_path = store.store_path.parent / "index.json"
        else:
            self._index_path = Path.cwd() / ".swarm" / "memory" / "index.json"

        # Try to load existing index, otherwise build from store
        if not self._load_index():
            self._build_index()

    def _load_index(self) -> bool:
        """Load index from file if it exists and is valid.

        Returns:
            True if index was loaded successfully, False otherwise.
        """
        if not self._index_path.exists():
            return False

        try:
            with open(self._index_path, "r") as f:
                data = json.load(f)

            # Check version - rebuild if version mismatch
            if data.get("version") != INDEX_VERSION:
                return False

            # Load inverted index
            inverted = data.get("inverted_index", {})
            self._inverted_index = {
                keyword: set(entry_ids)
                for keyword, entry_ids in inverted.items()
            }
            return True

        except (json.JSONDecodeError, IOError, OSError, KeyError, TypeError):
            # Corrupted file - rebuild from store
            return False

    def _build_index(self) -> None:
        """Build index from existing store entries."""
        self._inverted_index.clear()

        if self.store is None:
            return

        # Index all entries from store
        for entry_id in list(self.store._entries.keys()):
            entry = self.store.get_entry(entry_id)
            if entry:
                self._index_entry(entry)

    def _index_entry(self, entry: MemoryEntry) -> None:
        """Add an entry's keywords to the index.

        Args:
            entry: The MemoryEntry to index.
        """
        keywords = self._extract_keywords(entry)
        for keyword in keywords:
            if keyword not in self._inverted_index:
                self._inverted_index[keyword] = set()
            self._inverted_index[keyword].add(entry.id)

    def _extract_keywords(self, entry: MemoryEntry) -> Set[str]:
        """Extract all searchable keywords from an entry.

        Extracts from:
        - Content values (recursively)
        - Tags
        - Category
        - Feature ID

        Args:
            entry: The MemoryEntry to extract keywords from.

        Returns:
            Set of lowercase keyword strings.
        """
        keywords: Set[str] = set()

        # Add category and feature_id
        if entry.category:
            keywords.add(entry.category.lower())
        if entry.feature_id:
            keywords.add(entry.feature_id.lower())

        # Add tags
        for tag in entry.tags:
            keywords.add(tag.lower())

        # Extract keywords from content
        content_keywords = self._extract_content_keywords(entry.content)
        keywords.update(content_keywords)

        return keywords

    def _extract_content_keywords(self, content: Any) -> Set[str]:
        """Extract keywords from content dictionary recursively.

        Splits string values into individual words and handles nested structures.

        Args:
            content: The content to extract keywords from.

        Returns:
            Set of lowercase keyword strings.
        """
        keywords: Set[str] = set()

        def extract(obj: Any) -> None:
            if isinstance(obj, str):
                # Split into words and add each as a keyword
                words = re.split(r'[^a-zA-Z0-9_]+', obj)
                for word in words:
                    word = word.strip()
                    if word:
                        keywords.add(word.lower())
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(content)
        return keywords

    def _remove_entry_from_index(self, entry: MemoryEntry) -> None:
        """Remove an entry's keywords from the index.

        Args:
            entry: The MemoryEntry to remove from index.
        """
        keywords = self._extract_keywords(entry)
        orphaned_keywords = []

        for keyword in keywords:
            if keyword in self._inverted_index:
                self._inverted_index[keyword].discard(entry.id)
                # Track orphaned keywords (no entries left)
                if not self._inverted_index[keyword]:
                    orphaned_keywords.append(keyword)

        # Remove orphaned keywords from index
        for keyword in orphaned_keywords:
            del self._inverted_index[keyword]

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add entry to both the index and the underlying store.

        Args:
            entry: The MemoryEntry to add.
        """
        # Add to store first
        if self.store is not None:
            self.store.add(entry)

        # Then add to index
        self._index_entry(entry)

    def delete_entry(self, entry_id: str) -> bool:
        """Delete entry from both the index and the underlying store.

        Args:
            entry_id: The ID of the entry to delete.

        Returns:
            True if entry was deleted, False if not found.
        """
        # Get entry before deleting from store
        entry = None
        if self.store is not None:
            entry = self.store.get_entry(entry_id)

        if entry is None:
            return False

        # Remove from index
        self._remove_entry_from_index(entry)

        # Remove from store
        if self.store is not None:
            self.store.delete(entry_id)

        return True

    def get_entries_for_keyword(self, keyword: str) -> Set[str]:
        """Get entry IDs that contain the given keyword.

        Args:
            keyword: The keyword to search for (case-insensitive).

        Returns:
            Set of entry IDs containing the keyword.
        """
        return self._inverted_index.get(keyword.lower(), set()).copy()

    def keyword_count(self) -> int:
        """Get the number of unique keywords in the index.

        Returns:
            Count of unique keywords.
        """
        return len(self._inverted_index)

    def search(
        self,
        keywords: List[str],
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        """Search for entries matching all keywords (AND logic).

        Uses the inverted index for fast O(1) lookups.

        Args:
            keywords: List of keywords to search for (all must match).
            category: Optional category filter.
            limit: Optional maximum number of results.

        Returns:
            List of matching MemoryEntry objects.
        """
        if not keywords:
            return []

        # Normalize keywords to lowercase
        normalized_keywords = [k.lower() for k in keywords]

        # Get entry IDs for first keyword
        if normalized_keywords[0] not in self._inverted_index:
            return []

        result_ids = self._inverted_index[normalized_keywords[0]].copy()

        # Intersect with other keywords (AND logic)
        for keyword in normalized_keywords[1:]:
            if keyword not in self._inverted_index:
                return []
            result_ids &= self._inverted_index[keyword]

        if not result_ids:
            return []

        # Filter by category if specified
        results: List[MemoryEntry] = []
        for entry_id in result_ids:
            if self.store is None:
                continue

            entry = self.store.get_entry(entry_id)
            if entry is None:
                continue

            # Apply category filter
            if category is not None and entry.category != category:
                continue

            results.append(entry)

            # Apply limit
            if limit is not None and len(results) >= limit:
                break

        return results

    def save(self) -> None:
        """Persist the index to disk.

        Creates parent directories if they don't exist.
        """
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": INDEX_VERSION,
            "inverted_index": {
                keyword: list(entry_ids)
                for keyword, entry_ids in self._inverted_index.items()
            },
        }

        with open(self._index_path, "w") as f:
            json.dump(data, f, indent=2)

    def to_dict(self) -> dict:
        """Serialize index for persistence.

        Returns:
            Dictionary representation of the index.
        """
        return {
            "version": INDEX_VERSION,
            "inverted_index": {
                keyword: list(entry_ids)
                for keyword, entry_ids in self._inverted_index.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, store: Optional[MemoryStore] = None) -> "MemoryIndex":
        """Deserialize index from dictionary.

        Args:
            data: Dictionary representation of the index.
            store: Optional MemoryStore to associate with the index.

        Returns:
            MemoryIndex instance.
        """
        index = cls.__new__(cls)
        index.store = store
        index._index_path = Path.cwd() / ".swarm" / "memory" / "index.json"

        inverted = data.get("inverted_index", {})
        index._inverted_index = {
            keyword: set(entry_ids)
            for keyword, entry_ids in inverted.items()
        }

        return index
