"""TDD tests for PatternDetector pattern detection in memory entries.

Tests for PatternDetector class that will be in swarm_attack/memory/patterns.py:
- detect_recurring_schema_drift() - same class drifts multiple times
- detect_common_fix_patterns() - similar fixes applied repeatedly
- detect_failure_clusters() - related test failures
- pattern_confidence_score - confidence based on occurrences
- time window filtering - only detect patterns within time window
- single occurrence handling - single events aren't patterns

These tests are written in TDD RED phase - they should FAIL because
PatternDetector doesn't exist yet.

The PatternDetector works with MemoryStore to analyze entries and identify
patterns that can inform future agent decisions.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryStore, MemoryEntry

# This import should fail initially (RED phase) because the module doesn't exist
from swarm_attack.memory.patterns import PatternDetector


def _create_schema_drift_entry(
    class_name: str,
    feature_id: str = "test-feature",
    days_ago: int = 0,
    outcome: str = "detected",
    drift_type: str = "field_mismatch",
    content_extra: dict | None = None,
) -> MemoryEntry:
    """Create a schema_drift MemoryEntry for testing.

    Args:
        class_name: Name of the class that drifted.
        feature_id: Feature ID.
        days_ago: How many days ago the entry was created.
        outcome: Outcome of the drift detection.
        drift_type: Type of schema drift.
        content_extra: Additional content to merge.

    Returns:
        MemoryEntry with category="schema_drift".
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    content = {
        "class_name": class_name,
        "drift_type": drift_type,
        "file_path": f"swarm_attack/models/{class_name.lower()}.py",
    }
    if content_extra:
        content.update(content_extra)

    return MemoryEntry(
        id=str(uuid4()),
        category="schema_drift",
        feature_id=feature_id,
        issue_number=None,
        content=content,
        outcome=outcome,
        created_at=created_at.isoformat(),
        tags=["schema", class_name.lower()],
        hit_count=0,
    )


def _create_fix_entry(
    fix_type: str,
    target_file: str,
    feature_id: str = "test-feature",
    days_ago: int = 0,
    outcome: str = "applied",
    content_extra: dict | None = None,
) -> MemoryEntry:
    """Create a fix MemoryEntry for testing.

    Args:
        fix_type: Type of fix applied (e.g., "import_fix", "type_annotation").
        target_file: File that was fixed.
        feature_id: Feature ID.
        days_ago: How many days ago the entry was created.
        outcome: Outcome of the fix.
        content_extra: Additional content to merge.

    Returns:
        MemoryEntry with category="fix_applied".
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    content = {
        "fix_type": fix_type,
        "target_file": target_file,
        "description": f"Applied {fix_type} to {target_file}",
    }
    if content_extra:
        content.update(content_extra)

    return MemoryEntry(
        id=str(uuid4()),
        category="fix_applied",
        feature_id=feature_id,
        issue_number=None,
        content=content,
        outcome=outcome,
        created_at=created_at.isoformat(),
        tags=["fix", fix_type],
        hit_count=0,
    )


def _create_test_failure_entry(
    test_path: str,
    test_name: str,
    error_type: str = "AssertionError",
    feature_id: str = "test-feature",
    days_ago: int = 0,
    outcome: str = "failed",
    content_extra: dict | None = None,
) -> MemoryEntry:
    """Create a test_failure MemoryEntry for testing.

    Args:
        test_path: Path to the test file.
        test_name: Name of the failing test.
        error_type: Type of error (e.g., "AssertionError", "TypeError").
        feature_id: Feature ID.
        days_ago: How many days ago the entry was created.
        outcome: Outcome.
        content_extra: Additional content to merge.

    Returns:
        MemoryEntry with category="test_failure".
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    content = {
        "test_path": test_path,
        "test_name": test_name,
        "error_type": error_type,
        "error_message": f"{error_type}: test assertion failed",
    }
    if content_extra:
        content.update(content_extra)

    return MemoryEntry(
        id=str(uuid4()),
        category="test_failure",
        feature_id=feature_id,
        issue_number=None,
        content=content,
        outcome=outcome,
        created_at=created_at.isoformat(),
        tags=["test", "failure", error_type.lower()],
        hit_count=0,
    )


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Provide a temporary path for store persistence."""
    return tmp_path / "test_memories.json"


@pytest.fixture
def memory_store(temp_store_path: Path) -> MemoryStore:
    """Create a MemoryStore with temporary storage path."""
    return MemoryStore(store_path=temp_store_path)


@pytest.fixture
def pattern_detector(memory_store: MemoryStore) -> PatternDetector:
    """Create a PatternDetector with the memory store."""
    return PatternDetector(memory_store)


class TestDetectRecurringSchemaDrift:
    """Tests for detecting when the same class has schema drift multiple times."""

    def test_detect_recurring_schema_drift_finds_repeated_class_drift(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """detect_recurring_schema_drift identifies classes that drift repeatedly.

        When the same class appears in multiple schema_drift entries,
        it should be detected as a recurring pattern.
        """
        # Arrange - Same class drifts 3 times
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="UserConfig",
                feature_id=f"feature-{i}",
                days_ago=i,
            )
            memory_store.add(entry)

        # Add a different class that drifts once (not a pattern)
        single_drift = _create_schema_drift_entry(
            class_name="SingleDrift",
            feature_id="feature-single",
            days_ago=0,
        )
        memory_store.add(single_drift)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert
        assert len(patterns) >= 1
        # UserConfig should be identified as recurring
        class_names = [p.class_name for p in patterns]
        assert "UserConfig" in class_names
        # SingleDrift should NOT be in patterns (only occurred once)
        assert "SingleDrift" not in class_names

    def test_detect_recurring_schema_drift_returns_occurrence_count(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Pattern result includes how many times the class drifted."""
        # Arrange - Class drifts 5 times
        for i in range(5):
            entry = _create_schema_drift_entry(
                class_name="FrequentDrifter",
                feature_id=f"feature-{i}",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert
        assert len(patterns) == 1
        pattern = patterns[0]
        assert pattern.class_name == "FrequentDrifter"
        assert pattern.occurrence_count == 5

    def test_detect_recurring_schema_drift_groups_by_drift_type(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Recurring drift detection can group by drift type."""
        # Arrange - Same class with different drift types
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="MixedDrifter",
                drift_type="field_mismatch",
                days_ago=i,
            )
            memory_store.add(entry)

        for i in range(2):
            entry = _create_schema_drift_entry(
                class_name="MixedDrifter",
                drift_type="type_mismatch",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift(group_by_drift_type=True)

        # Assert - Should have separate patterns for each drift type
        field_patterns = [p for p in patterns if p.drift_type == "field_mismatch"]
        type_patterns = [p for p in patterns if p.drift_type == "type_mismatch"]

        assert len(field_patterns) == 1
        assert field_patterns[0].occurrence_count == 3

        assert len(type_patterns) == 1
        assert type_patterns[0].occurrence_count == 2

    def test_detect_recurring_schema_drift_minimum_occurrences(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Drift must occur min_occurrences times to be a pattern (default 2)."""
        # Arrange - Class drifts twice (exactly minimum)
        for i in range(2):
            entry = _create_schema_drift_entry(
                class_name="MinimalDrifter",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift(min_occurrences=2)

        # Assert - Should be detected (meets minimum)
        assert len(patterns) == 1
        assert patterns[0].class_name == "MinimalDrifter"

    def test_detect_recurring_schema_drift_custom_minimum_occurrences(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Custom min_occurrences threshold filters out less frequent drifts."""
        # Arrange - Class drifts 3 times
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="ThreeTimeDrifter",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act - Require at least 5 occurrences
        patterns = pattern_detector.detect_recurring_schema_drift(min_occurrences=5)

        # Assert - Should not be detected (below threshold)
        assert len(patterns) == 0


class TestDetectCommonFixPatterns:
    """Tests for detecting similar fixes applied repeatedly."""

    def test_detect_common_fix_patterns_finds_repeated_fix_types(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """detect_common_fix_patterns identifies fix types applied multiple times.

        When the same type of fix is applied to different files,
        it indicates a systemic issue that should be addressed.
        """
        # Arrange - Same fix type applied 4 times to different files
        for i in range(4):
            entry = _create_fix_entry(
                fix_type="missing_import",
                target_file=f"module_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        # Add a different fix type applied once
        single_fix = _create_fix_entry(
            fix_type="syntax_error",
            target_file="single.py",
            days_ago=0,
        )
        memory_store.add(single_fix)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns()

        # Assert
        assert len(patterns) >= 1
        fix_types = [p.fix_type for p in patterns]
        assert "missing_import" in fix_types
        assert "syntax_error" not in fix_types

    def test_detect_common_fix_patterns_returns_affected_files(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Pattern result includes list of files where fix was applied."""
        # Arrange
        files = ["auth.py", "config.py", "models.py"]
        for file in files:
            entry = _create_fix_entry(
                fix_type="type_annotation",
                target_file=file,
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns()

        # Assert
        assert len(patterns) == 1
        pattern = patterns[0]
        assert pattern.fix_type == "type_annotation"
        assert set(pattern.affected_files) == set(files)

    def test_detect_common_fix_patterns_counts_occurrences(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Pattern includes occurrence count."""
        # Arrange - Apply same fix 6 times
        for i in range(6):
            entry = _create_fix_entry(
                fix_type="docstring_addition",
                target_file=f"file_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns()

        # Assert
        assert len(patterns) == 1
        assert patterns[0].occurrence_count == 6

    def test_detect_common_fix_patterns_groups_by_module(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Can group fixes by target module/directory."""
        # Arrange - Fixes in different modules
        for i in range(3):
            entry = _create_fix_entry(
                fix_type="import_fix",
                target_file=f"swarm_attack/agents/agent_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        for i in range(2):
            entry = _create_fix_entry(
                fix_type="import_fix",
                target_file=f"swarm_attack/models/model_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns(group_by_module=True)

        # Assert - Should have patterns grouped by module
        agent_patterns = [p for p in patterns if "agents" in str(p.module_path)]
        model_patterns = [p for p in patterns if "models" in str(p.module_path)]

        assert len(agent_patterns) >= 1
        assert len(model_patterns) >= 1


class TestDetectFailureClusters:
    """Tests for detecting related test failures."""

    def test_detect_failure_clusters_finds_tests_failing_together(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """detect_failure_clusters identifies tests that fail together.

        When multiple tests in the same module fail around the same time,
        they likely share a root cause.
        """
        # Arrange - Multiple tests in same module fail
        test_names = ["test_create", "test_update", "test_delete"]
        for name in test_names:
            entry = _create_test_failure_entry(
                test_path="tests/unit/test_crud.py",
                test_name=name,
                error_type="AssertionError",
                days_ago=0,
            )
            memory_store.add(entry)

        # Add an unrelated failure in different module
        unrelated = _create_test_failure_entry(
            test_path="tests/integration/test_api.py",
            test_name="test_endpoint",
            days_ago=0,
        )
        memory_store.add(unrelated)

        # Act
        clusters = pattern_detector.detect_failure_clusters()

        # Assert - Should find cluster of CRUD tests
        assert len(clusters) >= 1
        crud_cluster = next(
            (c for c in clusters if "test_crud.py" in c.test_path),
            None
        )
        assert crud_cluster is not None
        assert len(crud_cluster.failing_tests) == 3

    def test_detect_failure_clusters_groups_by_error_type(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Clusters can be grouped by error type."""
        # Arrange - Different error types in same file
        for i in range(3):
            entry = _create_test_failure_entry(
                test_path="tests/test_module.py",
                test_name=f"test_assert_{i}",
                error_type="AssertionError",
                days_ago=0,
            )
            memory_store.add(entry)

        for i in range(2):
            entry = _create_test_failure_entry(
                test_path="tests/test_module.py",
                test_name=f"test_type_{i}",
                error_type="TypeError",
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        clusters = pattern_detector.detect_failure_clusters(group_by_error_type=True)

        # Assert - Should have separate clusters by error type
        assert_clusters = [c for c in clusters if c.error_type == "AssertionError"]
        type_clusters = [c for c in clusters if c.error_type == "TypeError"]

        assert len(assert_clusters) >= 1
        assert assert_clusters[0].failure_count == 3

        assert len(type_clusters) >= 1
        assert type_clusters[0].failure_count == 2

    def test_detect_failure_clusters_identifies_common_features(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Cluster includes feature IDs where failures occurred."""
        # Arrange - Same test fails across features
        features = ["feature-a", "feature-b", "feature-c"]
        for feature in features:
            entry = _create_test_failure_entry(
                test_path="tests/test_shared.py",
                test_name="test_common_case",
                feature_id=feature,
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        clusters = pattern_detector.detect_failure_clusters()

        # Assert
        assert len(clusters) >= 1
        cluster = clusters[0]
        assert set(cluster.affected_features) == set(features)

    def test_detect_failure_clusters_minimum_failures(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Cluster requires min_failures to be considered (default 2)."""
        # Arrange - Single failure (not a cluster)
        entry = _create_test_failure_entry(
            test_path="tests/test_isolated.py",
            test_name="test_single",
            days_ago=0,
        )
        memory_store.add(entry)

        # Two failures in another module (is a cluster)
        for i in range(2):
            entry = _create_test_failure_entry(
                test_path="tests/test_clustered.py",
                test_name=f"test_pair_{i}",
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        clusters = pattern_detector.detect_failure_clusters(min_failures=2)

        # Assert
        assert len(clusters) == 1
        assert "test_clustered.py" in clusters[0].test_path


class TestPatternConfidenceScore:
    """Tests for confidence scoring based on occurrences."""

    def test_pattern_confidence_score_increases_with_occurrences(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Confidence score increases with more occurrences.

        More occurrences = higher confidence the pattern is real.
        """
        # Arrange - Class drifts 10 times (high confidence)
        for i in range(10):
            entry = _create_schema_drift_entry(
                class_name="HighConfidenceDrifter",
                days_ago=i,
            )
            memory_store.add(entry)

        # Another class drifts 2 times (lower confidence)
        for i in range(2):
            entry = _create_schema_drift_entry(
                class_name="LowConfidenceDrifter",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert
        high_pattern = next(p for p in patterns if p.class_name == "HighConfidenceDrifter")
        low_pattern = next(p for p in patterns if p.class_name == "LowConfidenceDrifter")

        assert high_pattern.confidence_score > low_pattern.confidence_score

    def test_pattern_confidence_score_range(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Confidence score is normalized between 0.0 and 1.0."""
        # Arrange - Various occurrence counts
        for class_name, count in [("Low", 2), ("Medium", 5), ("High", 20)]:
            for i in range(count):
                entry = _create_schema_drift_entry(
                    class_name=class_name,
                    days_ago=i,
                )
                memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert - All confidence scores in valid range
        for pattern in patterns:
            assert 0.0 <= pattern.confidence_score <= 1.0

    def test_pattern_confidence_considers_recency(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """More recent patterns have higher confidence."""
        # Arrange - Same occurrence count, different recency
        # Recent pattern (all within last 7 days)
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="RecentPattern",
                days_ago=i,
            )
            memory_store.add(entry)

        # Old pattern (all more than 30 days ago)
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="OldPattern",
                days_ago=30 + i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert
        recent = next(p for p in patterns if p.class_name == "RecentPattern")
        old = next(p for p in patterns if p.class_name == "OldPattern")

        assert recent.confidence_score > old.confidence_score

    def test_pattern_confidence_for_fix_patterns(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Fix patterns also have confidence scores."""
        # Arrange
        for i in range(5):
            entry = _create_fix_entry(
                fix_type="null_check",
                target_file=f"file_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns()

        # Assert
        assert len(patterns) == 1
        assert 0.0 <= patterns[0].confidence_score <= 1.0


class TestPatternTimeWindow:
    """Tests for time window filtering in pattern detection."""

    def test_pattern_time_window_filters_old_entries(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Pattern detection only considers entries within time window.

        Default time window should be configurable (e.g., last 30 days).
        """
        # Arrange - Recent drifts (within window)
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="RecentClass",
                days_ago=i,
            )
            memory_store.add(entry)

        # Old drifts (outside window)
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="OldClass",
                days_ago=60 + i,  # More than 30 days ago
            )
            memory_store.add(entry)

        # Act - Use 30 day window
        patterns = pattern_detector.detect_recurring_schema_drift(
            time_window_days=30
        )

        # Assert - Only recent class should be detected
        class_names = [p.class_name for p in patterns]
        assert "RecentClass" in class_names
        assert "OldClass" not in class_names

    def test_pattern_time_window_custom_value(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Custom time window value filters appropriately."""
        # Arrange - Drifts at 5, 10, and 15 days ago
        for days in [5, 10, 15]:
            entry = _create_schema_drift_entry(
                class_name="TimedClass",
                days_ago=days,
            )
            memory_store.add(entry)

        # Act - Use 7 day window (should only get 1 entry, not enough for pattern)
        patterns_7_day = pattern_detector.detect_recurring_schema_drift(
            time_window_days=7
        )

        # Use 12 day window (should get 2 entries, enough for pattern)
        patterns_12_day = pattern_detector.detect_recurring_schema_drift(
            time_window_days=12
        )

        # Assert
        assert len(patterns_7_day) == 0  # Only 1 entry in window, not a pattern
        assert len(patterns_12_day) == 1  # 2 entries in window, is a pattern

    def test_pattern_time_window_none_includes_all(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """time_window_days=None includes all entries regardless of age."""
        # Arrange - Very old drifts
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="AncientClass",
                days_ago=365 + i,  # Over a year old
            )
            memory_store.add(entry)

        # Act - No time window limit
        patterns = pattern_detector.detect_recurring_schema_drift(
            time_window_days=None
        )

        # Assert - Old entries should still be detected
        class_names = [p.class_name for p in patterns]
        assert "AncientClass" in class_names

    def test_pattern_time_window_applies_to_fix_patterns(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Time window also applies to fix pattern detection."""
        # Arrange - Recent fixes
        for i in range(3):
            entry = _create_fix_entry(
                fix_type="recent_fix",
                target_file=f"recent_{i}.py",
                days_ago=i,
            )
            memory_store.add(entry)

        # Old fixes
        for i in range(3):
            entry = _create_fix_entry(
                fix_type="old_fix",
                target_file=f"old_{i}.py",
                days_ago=90 + i,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns(
            time_window_days=30
        )

        # Assert
        fix_types = [p.fix_type for p in patterns]
        assert "recent_fix" in fix_types
        assert "old_fix" not in fix_types

    def test_pattern_time_window_applies_to_failure_clusters(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Time window also applies to failure cluster detection."""
        # Arrange - Recent failures
        for i in range(3):
            entry = _create_test_failure_entry(
                test_path="tests/test_recent.py",
                test_name=f"test_recent_{i}",
                days_ago=i,
            )
            memory_store.add(entry)

        # Old failures
        for i in range(3):
            entry = _create_test_failure_entry(
                test_path="tests/test_old.py",
                test_name=f"test_old_{i}",
                days_ago=60 + i,
            )
            memory_store.add(entry)

        # Act
        clusters = pattern_detector.detect_failure_clusters(
            time_window_days=30
        )

        # Assert
        test_paths = [c.test_path for c in clusters]
        assert any("test_recent.py" in p for p in test_paths)
        assert not any("test_old.py" in p for p in test_paths)


class TestNoPatternForSingleOccurrence:
    """Tests for ensuring single occurrences aren't reported as patterns."""

    def test_single_schema_drift_is_not_a_pattern(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """A single schema drift occurrence should not be detected as a pattern.

        Patterns require repetition to be meaningful.
        """
        # Arrange - Single drift for each class
        classes = ["ClassA", "ClassB", "ClassC"]
        for class_name in classes:
            entry = _create_schema_drift_entry(
                class_name=class_name,
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert - No patterns (each class only drifted once)
        assert len(patterns) == 0

    def test_single_fix_type_is_not_a_pattern(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """A single fix application should not be detected as a pattern."""
        # Arrange - Single occurrence of each fix type
        fix_types = ["type_fix", "import_fix", "format_fix"]
        for fix_type in fix_types:
            entry = _create_fix_entry(
                fix_type=fix_type,
                target_file=f"{fix_type}.py",
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_common_fix_patterns()

        # Assert - No patterns
        assert len(patterns) == 0

    def test_single_test_failure_is_not_a_cluster(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """A single test failure should not be detected as a cluster."""
        # Arrange - Single failure in different modules
        modules = ["test_a.py", "test_b.py", "test_c.py"]
        for module in modules:
            entry = _create_test_failure_entry(
                test_path=f"tests/{module}",
                test_name="test_single",
                days_ago=0,
            )
            memory_store.add(entry)

        # Act
        clusters = pattern_detector.detect_failure_clusters()

        # Assert - No clusters (each module has only 1 failure)
        assert len(clusters) == 0

    def test_empty_store_returns_no_patterns(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Empty memory store should return empty pattern lists."""
        # Arrange - Store is empty

        # Act
        drift_patterns = pattern_detector.detect_recurring_schema_drift()
        fix_patterns = pattern_detector.detect_common_fix_patterns()
        failure_clusters = pattern_detector.detect_failure_clusters()

        # Assert - All empty
        assert drift_patterns == []
        assert fix_patterns == []
        assert failure_clusters == []

    def test_pattern_requires_minimum_two_occurrences_by_default(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Default minimum occurrence threshold is 2."""
        # Arrange - One class with exactly 2 drifts (should be pattern)
        for i in range(2):
            entry = _create_schema_drift_entry(
                class_name="TwoDrifts",
                days_ago=i,
            )
            memory_store.add(entry)

        # One class with exactly 1 drift (should not be pattern)
        entry = _create_schema_drift_entry(
            class_name="OneDrift",
            days_ago=0,
        )
        memory_store.add(entry)

        # Act
        patterns = pattern_detector.detect_recurring_schema_drift()

        # Assert
        assert len(patterns) == 1
        assert patterns[0].class_name == "TwoDrifts"
        assert patterns[0].occurrence_count == 2

    def test_mixed_categories_only_patterns_per_category(
        self, memory_store: MemoryStore, pattern_detector: PatternDetector
    ) -> None:
        """Different categories don't cross-contaminate pattern detection.

        Schema drifts and test failures are tracked separately.
        """
        # Arrange - 3 schema drifts for ClassX
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="ClassX",
                days_ago=i,
            )
            memory_store.add(entry)

        # 1 test failure (not enough for cluster)
        failure = _create_test_failure_entry(
            test_path="tests/test_x.py",
            test_name="test_class_x",
            days_ago=0,
        )
        memory_store.add(failure)

        # Act
        drift_patterns = pattern_detector.detect_recurring_schema_drift()
        failure_clusters = pattern_detector.detect_failure_clusters()

        # Assert
        assert len(drift_patterns) == 1  # ClassX schema drift is a pattern
        assert len(failure_clusters) == 0  # Single failure is not a cluster
