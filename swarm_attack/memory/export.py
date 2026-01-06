"""Export and import memory entries to various formats.

Supports JSON and YAML formats for sharing memory across sessions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import yaml

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryStore

from swarm_attack.memory.store import MemoryEntry


class MemoryExporter:
    """Export and import memory entries to various formats."""

    def _get_entries(
        self,
        store: "MemoryStore",
        categories: Optional[List[str]] = None
    ) -> List[MemoryEntry]:
        """Get entries from store, optionally filtered by categories.

        Args:
            store: The memory store to get entries from.
            categories: If provided, only return entries matching these categories.

        Returns:
            List of MemoryEntry objects.
        """
        # Access internal entries directly to avoid hit_count increment
        all_entries = list(store._entries.values())

        if categories is None:
            return all_entries

        # Filter by categories
        return [e for e in all_entries if e.category in categories]

    def _build_export_data(
        self,
        entries: List[MemoryEntry]
    ) -> dict:
        """Build the export data structure with metadata.

        Args:
            entries: List of entries to export.

        Returns:
            Dictionary with metadata and entries.
        """
        return {
            "metadata": {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "entry_count": len(entries),
            },
            "entries": [e.to_dict() for e in entries],
        }

    def export_json(
        self,
        store: "MemoryStore",
        path: Path,
        categories: Optional[List[str]] = None
    ) -> None:
        """Export memory store to JSON file.

        Args:
            store: The memory store to export from.
            path: Output file path.
            categories: If provided, only export these categories.
        """
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get entries (optionally filtered)
        entries = self._get_entries(store, categories)

        # Build export data
        data = self._build_export_data(entries)

        # Write JSON file
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def import_json(
        self,
        store: "MemoryStore",
        path: Path,
        merge: bool = True
    ) -> int:
        """Import memory entries from JSON file.

        Args:
            store: The memory store to import into.
            path: Input file path.
            merge: If True, add to existing entries. If False, clear first.

        Returns:
            Number of entries imported.
        """
        # Clear store if not merging
        if not merge:
            store.clear()

        # Read JSON file
        with open(path, "r") as f:
            data = json.load(f)

        # Import entries
        entries = data.get("entries", [])
        count = 0

        for entry_data in entries:
            entry = MemoryEntry.from_dict(entry_data)
            store.add(entry)
            count += 1

        return count

    def export_yaml(
        self,
        store: "MemoryStore",
        path: Path,
        categories: Optional[List[str]] = None
    ) -> None:
        """Export memory store to YAML file.

        Args:
            store: The memory store to export from.
            path: Output file path.
            categories: If provided, only export these categories.
        """
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get entries (optionally filtered)
        entries = self._get_entries(store, categories)

        # Build export data
        data = self._build_export_data(entries)

        # Write YAML file
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
