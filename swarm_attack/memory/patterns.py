"""
Pattern Detection for Memory Entries.

Analyzes MemoryStore entries to detect:
- Recurring schema drift patterns
- Common fix patterns
- Test failure clusters
- Verification patterns (success/failure)

Uses time window filtering and confidence scoring based on occurrences and recency.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional
from uuid import uuid4

from swarm_attack.memory.store import MemoryEntry, MemoryStore


@dataclass
class SchemaDriftPattern:
    """A detected pattern of recurring schema drift for a class.

    Attributes:
        class_name: Name of the class that has recurring drift.
        occurrence_count: Number of times drift was detected.
        drift_type: Optional specific drift type if grouped.
        confidence_score: Confidence score (0.0-1.0) based on occurrences and recency.
        entry_ids: IDs of the memory entries that form this pattern.
    """
    class_name: str
    occurrence_count: int
    drift_type: Optional[str] = None
    confidence_score: float = 0.0
    entry_ids: List[str] = field(default_factory=list)


@dataclass
class FixPattern:
    """A detected pattern of commonly applied fixes.

    Attributes:
        fix_type: The type of fix that was repeatedly applied.
        affected_files: List of files where this fix was applied.
        occurrence_count: Number of times this fix was applied.
        module_path: Optional module path if grouped by module.
        confidence_score: Confidence score (0.0-1.0) based on occurrences and recency.
        entry_ids: IDs of the memory entries that form this pattern.
    """
    fix_type: str
    affected_files: List[str]
    occurrence_count: int
    module_path: Optional[str] = None
    confidence_score: float = 0.0
    entry_ids: List[str] = field(default_factory=list)


@dataclass
class FailureCluster:
    """A cluster of related test failures.

    Attributes:
        test_path: Path to the test file with failures.
        failing_tests: List of failing test names.
        failure_count: Number of failures in this cluster.
        error_type: Optional error type if grouped.
        affected_features: Feature IDs where failures occurred.
        entry_ids: IDs of the memory entries that form this cluster.
    """
    test_path: str
    failing_tests: List[str]
    failure_count: int
    error_type: Optional[str] = None
    affected_features: List[str] = field(default_factory=list)
    entry_ids: List[str] = field(default_factory=list)


@dataclass
class DetectedPattern:
    """A generic detected pattern for the unified detect_patterns API.

    Used by E2E tests which expect a common pattern format across
    all pattern types.

    Attributes:
        name: Name/identifier of the pattern.
        occurrence_count: Number of times the pattern occurred.
        confidence_score: Confidence score (0.0-1.0).
        common_tags: Tags common to entries forming this pattern.
        content: Additional pattern-specific content.
        entry_ids: IDs of entries forming this pattern.
    """
    name: str
    occurrence_count: int
    confidence_score: float = 0.5
    common_tags: List[str] = field(default_factory=list)
    content: dict = field(default_factory=dict)
    entry_ids: List[str] = field(default_factory=list)


@dataclass
class VerificationPattern:
    """A verification pattern entry.

    Attributes:
        test_path: Path to the test file that was verified.
        result: Either "success" or "failure".
        error_message: Error message for failures (None for successes).
        fix_applied: Description of what fixed the issue (for successes).
        related_entries: List of related memory entry IDs.
    """

    test_path: str
    result: str
    error_message: Optional[str] = None
    fix_applied: Optional[str] = None
    related_entries: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "test_path": self.test_path,
            "result": self.result,
            "error_message": self.error_message,
            "fix_applied": self.fix_applied,
            "related_entries": self.related_entries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationPattern":
        """Create from dictionary."""
        return cls(
            test_path=data["test_path"],
            result=data["result"],
            error_message=data.get("error_message"),
            fix_applied=data.get("fix_applied"),
            related_entries=data.get("related_entries", []),
        )


class PatternDetector:
    """Detects patterns in memory entries.

    Analyzes MemoryStore entries to identify:
    - Recurring schema drift (same class drifts multiple times)
    - Common fix patterns (same fix type applied repeatedly)
    - Failure clusters (related test failures)

    Supports time window filtering and confidence scoring.
    """

    def __init__(self, store: MemoryStore, time_window_days: int = 30):
        """Initialize the pattern detector.

        Args:
            store: The MemoryStore to analyze.
            time_window_days: Default time window for pattern detection.
        """
        self.store = store
        self.time_window_days = time_window_days

    def _parse_datetime_with_tz(self, created_at: str) -> datetime:
        """Parse datetime string ensuring timezone awareness.

        Args:
            created_at: ISO format datetime string.

        Returns:
            Timezone-aware datetime object.
        """
        entry_date = datetime.fromisoformat(created_at)
        if entry_date.tzinfo is None:
            entry_date = entry_date.replace(tzinfo=timezone.utc)
        return entry_date

    def _is_within_time_window(
        self,
        entry: MemoryEntry,
        time_window_days: Optional[int]
    ) -> bool:
        """Check if an entry is within the time window.

        Args:
            entry: The entry to check.
            time_window_days: Number of days in the window, or None for no limit.

        Returns:
            True if entry is within the time window.
        """
        if time_window_days is None:
            return True

        cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        entry_date = datetime.fromisoformat(entry.created_at)
        # Ensure both datetimes are timezone-aware for comparison
        if entry_date.tzinfo is None:
            entry_date = entry_date.replace(tzinfo=timezone.utc)
        return entry_date >= cutoff

    def _calculate_confidence_score(
        self,
        entries: List[MemoryEntry],
        max_occurrences: int = 10
    ) -> float:
        """Calculate confidence score based on occurrences and recency.

        Score is influenced by:
        - Number of occurrences (more = higher confidence)
        - Recency of occurrences (more recent = higher confidence)

        Args:
            entries: List of entries forming the pattern.
            max_occurrences: Number of occurrences that gives max score.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not entries:
            return 0.0

        # Occurrence-based score (capped at max_occurrences)
        occurrence_score = min(len(entries) / max_occurrences, 1.0)

        # Recency-based score (average age in days, inverted)
        now = datetime.now(timezone.utc)
        ages = []
        for entry in entries:
            entry_date = datetime.fromisoformat(entry.created_at)
            # Ensure both datetimes are timezone-aware for comparison
            if entry_date.tzinfo is None:
                entry_date = entry_date.replace(tzinfo=timezone.utc)
            age_days = (now - entry_date).days
            ages.append(age_days)

        avg_age = sum(ages) / len(ages)
        # Score decreases as average age increases (30 days = ~0.5, 60 days = ~0.25)
        recency_score = 1.0 / (1.0 + avg_age / 30.0)

        # Combine scores (70% occurrence, 30% recency)
        return min(0.7 * occurrence_score + 0.3 * recency_score, 1.0)

    def detect_recurring_schema_drift(
        self,
        min_occurrences: int = 2,
        group_by_drift_type: bool = False,
        time_window_days: Optional[int] = None,
    ) -> List[SchemaDriftPattern]:
        """Find recurring schema drift patterns.

        Identifies classes that have schema drift multiple times,
        indicating a systemic issue.

        Args:
            min_occurrences: Minimum number of drifts to be considered a pattern.
            group_by_drift_type: If True, group patterns by drift type too.
            time_window_days: Time window for entries, None for no limit.

        Returns:
            List of SchemaDriftPattern objects.
        """
        # Use provided time window or default
        window = time_window_days if time_window_days is not None else None

        # Get all schema_drift entries within time window
        entries = self.store.query(category="schema_drift", limit=1000)
        filtered_entries = [
            e for e in entries
            if self._is_within_time_window(e, window)
        ]

        # Group by class_name (and optionally drift_type)
        groups: dict[tuple, List[MemoryEntry]] = defaultdict(list)

        for entry in filtered_entries:
            # Support both "class_name" and "class" keys (common variations)
            class_name = entry.content.get("class_name") or entry.content.get("class")
            if not class_name:
                continue

            if group_by_drift_type:
                drift_type = entry.content.get("drift_type")
                key = (class_name, drift_type)
            else:
                key = (class_name, None)

            groups[key].append(entry)

        # Create patterns for groups meeting min_occurrences
        patterns: List[SchemaDriftPattern] = []

        for (class_name, drift_type), group_entries in groups.items():
            if len(group_entries) >= min_occurrences:
                pattern = SchemaDriftPattern(
                    class_name=class_name,
                    occurrence_count=len(group_entries),
                    drift_type=drift_type,
                    confidence_score=self._calculate_confidence_score(group_entries),
                    entry_ids=[e.id for e in group_entries],
                )
                patterns.append(pattern)

        return patterns

    def detect_common_fix_patterns(
        self,
        min_occurrences: int = 2,
        group_by_module: bool = False,
        time_window_days: Optional[int] = None,
    ) -> List[FixPattern]:
        """Find common fix patterns.

        Identifies fix types that are applied repeatedly,
        indicating systemic issues that need addressing.

        Args:
            min_occurrences: Minimum number of fixes to be considered a pattern.
            group_by_module: If True, group patterns by module/directory too.
            time_window_days: Time window for entries, None for no limit.

        Returns:
            List of FixPattern objects.
        """
        # Use provided time window or default
        window = time_window_days if time_window_days is not None else None

        # Get all fix_applied entries within time window
        entries = self.store.query(category="fix_applied", limit=1000)
        filtered_entries = [
            e for e in entries
            if self._is_within_time_window(e, window)
        ]

        # Group by fix_type (and optionally module)
        groups: dict[tuple, List[MemoryEntry]] = defaultdict(list)

        for entry in filtered_entries:
            fix_type = entry.content.get("fix_type")
            if not fix_type:
                continue

            if group_by_module:
                target_file = entry.content.get("target_file", "")
                # Extract module path (parent directory)
                module_path = str(Path(target_file).parent) if target_file else ""
                key = (fix_type, module_path)
            else:
                key = (fix_type, None)

            groups[key].append(entry)

        # Create patterns for groups meeting min_occurrences
        patterns: List[FixPattern] = []

        for (fix_type, module_path), group_entries in groups.items():
            if len(group_entries) >= min_occurrences:
                # Collect affected files
                affected_files = [
                    e.content.get("target_file", "")
                    for e in group_entries
                    if e.content.get("target_file")
                ]

                pattern = FixPattern(
                    fix_type=fix_type,
                    affected_files=affected_files,
                    occurrence_count=len(group_entries),
                    module_path=module_path,
                    confidence_score=self._calculate_confidence_score(group_entries),
                    entry_ids=[e.id for e in group_entries],
                )
                patterns.append(pattern)

        return patterns

    def detect_failure_clusters(
        self,
        min_failures: int = 2,
        group_by_error_type: bool = False,
        time_window_days: Optional[int] = None,
    ) -> List[FailureCluster]:
        """Find clusters of related test failures.

        Identifies test files with multiple failures,
        indicating related issues that likely share a root cause.

        Args:
            min_failures: Minimum number of failures to form a cluster.
            group_by_error_type: If True, group clusters by error type too.
            time_window_days: Time window for entries, None for no limit.

        Returns:
            List of FailureCluster objects.
        """
        # Use provided time window or default
        window = time_window_days if time_window_days is not None else None

        # Get all test_failure entries within time window
        entries = self.store.query(category="test_failure", limit=1000)
        filtered_entries = [
            e for e in entries
            if self._is_within_time_window(e, window)
        ]

        # Group by test_path (and optionally error_type)
        groups: dict[tuple, List[MemoryEntry]] = defaultdict(list)

        for entry in filtered_entries:
            test_path = entry.content.get("test_path")
            if not test_path:
                continue

            if group_by_error_type:
                error_type = entry.content.get("error_type")
                key = (test_path, error_type)
            else:
                key = (test_path, None)

            groups[key].append(entry)

        # Create clusters for groups meeting min_failures
        clusters: List[FailureCluster] = []

        for (test_path, error_type), group_entries in groups.items():
            if len(group_entries) >= min_failures:
                # Collect failing test names
                failing_tests = [
                    e.content.get("test_name", "")
                    for e in group_entries
                    if e.content.get("test_name")
                ]

                # Collect affected feature IDs
                affected_features = list(set(
                    e.feature_id
                    for e in group_entries
                    if e.feature_id
                ))

                cluster = FailureCluster(
                    test_path=test_path,
                    failing_tests=failing_tests,
                    failure_count=len(group_entries),
                    error_type=error_type,
                    affected_features=affected_features,
                    entry_ids=[e.id for e in group_entries],
                )
                clusters.append(cluster)

        return clusters

    # =========================================================================
    # Verification Pattern Methods
    # =========================================================================

    VERIFICATION_CATEGORY = "verification_pattern"

    def record_success_pattern(
        self,
        test_path: str,
        feature_id: str,
        issue_number: Optional[int] = None,
        fix_applied: Optional[str] = None,
        related_entries: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Record a successful verification pattern.

        Args:
            test_path: Path to the test file.
            feature_id: The feature being verified.
            issue_number: Optional issue number.
            fix_applied: What fixed the previously failing test.
            related_entries: Related memory entry IDs.
            tags: Additional tags for the entry.

        Returns:
            The ID of the created memory entry.
        """
        pattern = VerificationPattern(
            test_path=test_path,
            result="success",
            fix_applied=fix_applied,
            related_entries=related_entries or [],
        )

        entry_id = str(uuid4())
        entry = MemoryEntry(
            id=entry_id,
            category=self.VERIFICATION_CATEGORY,
            feature_id=feature_id,
            issue_number=issue_number,
            content=pattern.to_dict(),
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )

        self.store.add(entry)
        return entry_id

    def record_failure_pattern(
        self,
        test_path: str,
        feature_id: str,
        error_message: str,
        issue_number: Optional[int] = None,
        related_entries: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Record a failed verification pattern.

        Args:
            test_path: Path to the test file.
            feature_id: The feature being verified.
            error_message: The error message from the failure.
            issue_number: Optional issue number.
            related_entries: Related memory entry IDs.
            tags: Additional tags for the entry.

        Returns:
            The ID of the created memory entry.
        """
        pattern = VerificationPattern(
            test_path=test_path,
            result="failure",
            error_message=error_message,
            related_entries=related_entries or [],
        )

        entry_id = str(uuid4())
        entry = MemoryEntry(
            id=entry_id,
            category=self.VERIFICATION_CATEGORY,
            feature_id=feature_id,
            issue_number=issue_number,
            content=pattern.to_dict(),
            outcome="failure",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )

        self.store.add(entry)
        return entry_id

    def link_fix_to_failure(
        self,
        failure_entry_id: str,
        fix_description: str,
    ) -> bool:
        """Link a fix description to a previous failure entry.

        Args:
            failure_entry_id: The ID of the failure entry to update.
            fix_description: Description of what fixed the issue.

        Returns:
            True if the entry was found and updated, False otherwise.
        """
        entry = self.store.get_entry(failure_entry_id)
        if entry is None:
            return False

        if entry.category != self.VERIFICATION_CATEGORY:
            return False

        # Update the content with the fix
        entry.content["fix_applied"] = fix_description
        return True

    def get_verification_patterns(
        self,
        test_path: Optional[str] = None,
        feature_id: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryEntry]:
        """Get verification patterns with optional filters.

        Args:
            test_path: Filter by test file path.
            feature_id: Filter by feature ID.
            result: Filter by result ("success" or "failure").
            limit: Maximum number of entries to return.

        Returns:
            List of MemoryEntry objects matching the filters.
        """
        entries = self.store.query(
            category=self.VERIFICATION_CATEGORY,
            feature_id=feature_id,
            limit=limit,
        )

        results = []
        for entry in entries:
            # Apply test_path filter
            if test_path is not None:
                if entry.content.get("test_path") != test_path:
                    continue

            # Apply result filter
            if result is not None:
                if entry.content.get("result") != result:
                    continue

            results.append(entry)

        return results

    def detect_patterns(
        self,
        min_occurrences: int = 2,
        days: Optional[int] = 30,
    ) -> List[DetectedPattern]:
        """Detect patterns across all categories.

        This is a unified API that returns all detected patterns in a
        common format. Used by E2E tests.

        Args:
            min_occurrences: Minimum occurrences to consider a pattern.
            days: Time window in days. None for all time.

        Returns:
            List of DetectedPattern objects.
        """
        patterns: List[DetectedPattern] = []

        # Get all entries and filter by time window
        all_entries = list(self.store._entries.values())

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            all_entries = [
                e for e in all_entries
                if self._parse_datetime_with_tz(e.created_at) >= cutoff
            ]

        if not all_entries:
            return []

        # Group entries by category
        category_groups: dict[str, List[MemoryEntry]] = defaultdict(list)
        for entry in all_entries:
            category_groups[entry.category].append(entry)

        # Process test_failure entries - group by error_type
        test_failures = category_groups.get("test_failure", [])
        if test_failures:
            error_type_groups: dict[str, List[MemoryEntry]] = defaultdict(list)
            for entry in test_failures:
                error_type = entry.content.get("error_type", "unknown")
                error_type_groups[error_type].append(entry)

            for error_type, group_entries in error_type_groups.items():
                if len(group_entries) >= min_occurrences:
                    # Find common tags
                    tag_sets = [set(e.tags) for e in group_entries]
                    common_tags = list(set.intersection(*tag_sets)) if tag_sets else []

                    # Generate pattern name from error type
                    name = "timeout" if "timeout" in error_type.lower() else error_type.lower()

                    patterns.append(DetectedPattern(
                        name=name,
                        occurrence_count=len(group_entries),
                        confidence_score=self._calculate_confidence_score(group_entries),
                        common_tags=common_tags,
                        content={"error_type": error_type},
                        entry_ids=[e.id for e in group_entries],
                    ))

        # Process schema_drift entries - group by conflict_type
        schema_drifts = category_groups.get("schema_drift", [])
        if schema_drifts:
            conflict_groups: dict[str, List[MemoryEntry]] = defaultdict(list)
            for entry in schema_drifts:
                conflict_type = entry.content.get("conflict_type", "unknown")
                conflict_groups[conflict_type].append(entry)

            for conflict_type, group_entries in conflict_groups.items():
                if len(group_entries) >= min_occurrences:
                    tag_sets = [set(e.tags) for e in group_entries]
                    common_tags = list(set.intersection(*tag_sets)) if tag_sets else []

                    patterns.append(DetectedPattern(
                        name=f"schema_drift_{conflict_type}",
                        occurrence_count=len(group_entries),
                        confidence_score=self._calculate_confidence_score(group_entries),
                        common_tags=common_tags,
                        content={"conflict_type": conflict_type},
                        entry_ids=[e.id for e in group_entries],
                    ))

        # Process bug_pattern entries - group by bug_type
        bug_patterns = category_groups.get("bug_pattern", [])
        if bug_patterns:
            bug_type_groups: dict[str, List[MemoryEntry]] = defaultdict(list)
            for entry in bug_patterns:
                bug_type = entry.content.get("bug_type", "unknown")
                bug_type_groups[bug_type].append(entry)

            for bug_type, group_entries in bug_type_groups.items():
                if len(group_entries) >= min_occurrences:
                    tag_sets = [set(e.tags) for e in group_entries]
                    common_tags = list(set.intersection(*tag_sets)) if tag_sets else []

                    patterns.append(DetectedPattern(
                        name=f"bug_{bug_type}",
                        occurrence_count=len(group_entries),
                        confidence_score=self._calculate_confidence_score(group_entries),
                        common_tags=common_tags,
                        content={"bug_type": bug_type},
                        entry_ids=[e.id for e in group_entries],
                    ))

        # Sort by occurrence count descending
        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        return patterns
