"""Memory analytics and reporting.

Provides analytics and reports on memory store usage patterns.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryStore

from swarm_attack.memory.relevance import RelevanceScorer


class MemoryAnalytics:
    """Analytics and reporting for memory store."""

    def __init__(self, store: "MemoryStore"):
        self.store = store

    def category_counts(self) -> Dict[str, int]:
        """Get entry count per category.

        Returns dict like {"schema_drift": 5, "bug_fix": 3}
        """
        counts: Dict[str, int] = {}
        for entry in self.store._entries.values():
            category = entry.category
            counts[category] = counts.get(category, 0) + 1
        return counts

    def hit_rate(self) -> float:
        """Calculate hit rate (entries with hit_count > 0 / total).

        Returns 0.0 if no entries.
        """
        entries = list(self.store._entries.values())
        if not entries:
            return 0.0

        hit_count = sum(1 for entry in entries if entry.hit_count > 0)
        return hit_count / len(entries)

    def age_distribution(self, buckets: int = 5) -> Dict[str, int]:
        """Get age distribution as histogram.

        Buckets entries by age in days.
        Keys are labels like "0-7 days", "8-14 days", etc.
        Returns empty buckets for empty store.
        """
        # Each bucket spans 7 days
        # Bucket 0: 0-7 days (days 0-7 inclusive means 8 days, but ages 0-6 map here)
        # Bucket 1: 8-14 days
        # Bucket 2: 15-21 days
        # etc.

        # Create bucket labels
        result: Dict[str, int] = {}
        bucket_ranges = []
        for i in range(buckets):
            if i == 0:
                start = 0
                end = 7
            else:
                start = i * 7 + 1
                end = (i + 1) * 7
            label = f"{start}-{end} days"
            result[label] = 0
            bucket_ranges.append((start, end, label))

        now = datetime.now()

        # Distribute entries into buckets
        for entry in self.store._entries.values():
            created_at = datetime.fromisoformat(entry.created_at)
            age_days = (now - created_at).days

            # Find which bucket this entry belongs to
            bucket_found = False
            for start, end, label in bucket_ranges:
                if start <= age_days <= end:
                    result[label] += 1
                    bucket_found = True
                    break

            # If older than all buckets, put in last bucket
            if not bucket_found and bucket_ranges:
                result[bucket_ranges[-1][2]] += 1

        return result

    def relevance_distribution(self, buckets: int = 5) -> Dict[str, int]:
        """Get relevance score distribution as histogram.

        Uses RelevanceScorer to calculate scores.
        Keys are labels like "0.0-0.2", "0.2-0.4", etc.
        """
        # Create bucket labels for 0.0 to 1.0 range
        bucket_size = 1.0 / buckets
        result: Dict[str, int] = {}

        for i in range(buckets):
            start = i * bucket_size
            end = (i + 1) * bucket_size
            label = f"{start:.1f}-{end:.1f}"
            result[label] = 0

        entries = list(self.store._entries.values())
        if not entries:
            return result

        scorer = RelevanceScorer()

        # Calculate scores for all entries
        scores = [scorer.score(entry) for entry in entries]

        # Normalize scores to 0-1 range
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score

        # If score range is very small relative to the max score, treat all as equal
        # This handles cases where scores differ only due to microsecond timing differences
        scores_essentially_equal = score_range < (max_score * 0.001) if max_score > 0 else True

        for score in scores:
            if scores_essentially_equal:
                # All scores are essentially the same - place in highest bucket
                normalized = 0.9999
            elif score_range > 0:
                normalized = (score - min_score) / score_range
            else:
                normalized = 0.9999

            # Handle edge case where normalized == 1.0
            if normalized >= 1.0:
                normalized = 0.9999

            # Find bucket index
            bucket_index = int(normalized / bucket_size)
            if bucket_index >= buckets:
                bucket_index = buckets - 1

            start = bucket_index * bucket_size
            end = (bucket_index + 1) * bucket_size
            label = f"{start:.1f}-{end:.1f}"
            result[label] += 1

        return result

    def growth_timeline(self, days: int = 7) -> Dict[str, int]:
        """Get entries created per day over last N days.

        Returns dict with YYYY-MM-DD keys.
        Includes all days in range even if count is 0.
        """
        now = datetime.now()
        result: Dict[str, int] = {}

        # Initialize all days in range with 0
        for i in range(days):
            date = now - timedelta(days=days - 1 - i)
            key = date.strftime("%Y-%m-%d")
            result[key] = 0

        # Count entries per day
        for entry in self.store._entries.values():
            created_at = datetime.fromisoformat(entry.created_at)
            key = created_at.strftime("%Y-%m-%d")

            # Only count if within the range
            if key in result:
                result[key] += 1

        return result

    def generate_report(self) -> str:
        """Generate a text report with all analytics.

        Returns formatted string with category counts, hit rate, totals.
        """
        lines = []
        lines.append("=" * 50)
        lines.append("Memory Store Analytics Report")
        lines.append("=" * 50)
        lines.append("")

        # Total entries
        total_entries = len(self.store._entries)
        lines.append(f"Total Entries: {total_entries}")
        lines.append("")

        # Category counts
        lines.append("Category Counts:")
        counts = self.category_counts()
        if counts:
            for category, count in sorted(counts.items()):
                lines.append(f"  - {category}: {count}")
        else:
            lines.append("  (no entries)")
        lines.append("")

        # Hit rate
        rate = self.hit_rate()
        lines.append(f"Hit Rate: {rate:.1%}")
        lines.append("")

        # Age distribution
        lines.append("Age Distribution:")
        age_dist = self.age_distribution()
        for label, count in age_dist.items():
            lines.append(f"  - {label}: {count}")
        lines.append("")

        # Growth timeline (last 7 days)
        lines.append("Growth Timeline (Last 7 Days):")
        timeline = self.growth_timeline(days=7)
        for date, count in timeline.items():
            lines.append(f"  - {date}: {count}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)
