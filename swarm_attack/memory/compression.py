"""Memory compression for reducing store size.

Merges similar entries to reduce memory footprint during long sessions.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List
from uuid import uuid4

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryEntry


class MemoryCompressor:
    """Compress similar memory entries to reduce store size."""

    def compress(
        self,
        entries: List["MemoryEntry"],
        similarity_threshold: float = 0.8
    ) -> List["MemoryEntry"]:
        """Compress similar entries into fewer entries.

        Entries are similar if:
        - Same category
        - Same feature_id
        - Content keywords overlap >= similarity_threshold

        When merging:
        - Generate new ID (uuid4)
        - Keep the most recent timestamp
        - Sum hit_counts
        - Merge tags (union)
        - Keep most recent content
        - Keep most recent outcome

        Returns list of compressed entries.
        """
        if not entries:
            return []

        if len(entries) == 1:
            return entries.copy()

        # Track which entries have been merged
        merged_indices: set[int] = set()
        result: List["MemoryEntry"] = []

        for i, entry_a in enumerate(entries):
            if i in merged_indices:
                continue

            # Find all entries similar to entry_a
            group = [entry_a]
            group_indices = [i]

            for j, entry_b in enumerate(entries):
                if j <= i or j in merged_indices:
                    continue

                sim = self.similarity(entry_a, entry_b)
                if sim >= similarity_threshold:
                    group.append(entry_b)
                    group_indices.append(j)

            # Mark all in group as merged
            for idx in group_indices:
                merged_indices.add(idx)

            # Merge the group into one entry
            if len(group) == 1:
                result.append(group[0])
            else:
                merged = self._merge_entries(group)
                result.append(merged)

        return result

    def similarity(self, a: "MemoryEntry", b: "MemoryEntry") -> float:
        """Calculate similarity between two entries.

        Returns 0.0 if different category or feature_id.
        Otherwise returns keyword overlap ratio (0.0 to 1.0).

        Keyword extraction: extract words from content dict values.

        The overlap ratio is calculated as intersection / min(len(A), len(B)),
        which measures how much of the smaller keyword set is covered by the
        intersection. This handles cases where one entry has more content than
        the other (subset/superset relationship).
        """
        # Different category or feature_id means no similarity
        if a.category != b.category:
            return 0.0

        if a.feature_id != b.feature_id:
            return 0.0

        # Extract keywords from both entries
        keywords_a = self._extract_keywords(a.content)
        keywords_b = self._extract_keywords(b.content)

        # Handle edge case of empty keyword sets
        if not keywords_a and not keywords_b:
            return 1.0  # Both empty, consider identical

        if not keywords_a or not keywords_b:
            return 0.0  # One empty, one not

        # Calculate overlap ratio: intersection / min(sizes)
        # This handles subset/superset relationships well
        intersection = keywords_a & keywords_b
        min_size = min(len(keywords_a), len(keywords_b))

        return len(intersection) / min_size

    def _extract_keywords(self, content: dict) -> set[str]:
        """Extract keywords from content dictionary.

        Recursively finds all strings in the content dict values and keys,
        splitting strings into individual words for better similarity matching.
        """
        keywords: set[str] = set()

        def extract(obj: Any) -> None:
            if isinstance(obj, str):
                # Split string into words and add each as keyword (lowercased)
                for word in obj.lower().split():
                    keywords.add(word)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    # Add dict keys as keywords too
                    keywords.add(str(key).lower())
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(content)
        return keywords

    def _merge_entries(self, entries: List["MemoryEntry"]) -> "MemoryEntry":
        """Merge multiple entries into one.

        - Generate new ID (uuid4)
        - Keep the most recent timestamp
        - Sum hit_counts
        - Merge tags (union)
        - Keep most recent content
        - Keep most recent outcome
        """
        from swarm_attack.memory.store import MemoryEntry

        # Sort by timestamp to find most recent
        sorted_entries = sorted(
            entries,
            key=lambda e: datetime.fromisoformat(e.created_at),
            reverse=True
        )
        most_recent = sorted_entries[0]

        # Sum hit_counts
        total_hit_count = sum(e.hit_count for e in entries)

        # Merge tags (union), deduplicated
        all_tags: set[str] = set()
        for entry in entries:
            all_tags.update(entry.tags)

        # Create merged entry
        return MemoryEntry(
            id=str(uuid4()),
            category=most_recent.category,
            feature_id=most_recent.feature_id,
            issue_number=most_recent.issue_number,
            content=most_recent.content,
            outcome=most_recent.outcome,
            created_at=most_recent.created_at,
            tags=list(all_tags),
            hit_count=total_hit_count,
        )
