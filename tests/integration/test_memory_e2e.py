"""End-to-end memory integration tests.

Tests the full learning cycle using real (temp) file I/O.
These tests are written in RED phase - Pattern/Recommendation modules
don't exist yet, so imports will fail.

TDD: Tests written BEFORE implementation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore
from swarm_attack.memory.analytics import MemoryAnalytics
from swarm_attack.memory.categories import (
    BUG_PATTERN,
    IMPLEMENTATION_SUCCESS,
    RECOVERY_PATTERN,
    SCHEMA_DRIFT,
    TEST_FAILURE,
)


# These imports will fail in RED phase (modules don't exist yet)
# Uncomment when implementing:
# from swarm_attack.memory.patterns import PatternDetector
# from swarm_attack.memory.recommendations import RecommendationEngine


class TestFullLearningCycle:
    """Test: record issue -> get rec -> apply fix -> verify.

    This tests the complete learning cycle where:
    1. An issue is recorded in memory
    2. A recommendation is retrieved based on past issues
    3. A fix is applied based on the recommendation
    4. The outcome is verified and recorded for future learning
    """

    @pytest.fixture
    def memory_path(self, tmp_path: Path) -> Path:
        """Create temporary memory store path."""
        return tmp_path / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, memory_path: Path) -> MemoryStore:
        """Create MemoryStore with temp path."""
        return MemoryStore(store_path=memory_path)

    def test_record_issue_creates_memory_entry(self, memory_store: MemoryStore):
        """Recording an issue should create a memory entry."""
        # Arrange
        issue_entry = MemoryEntry(
            id=str(uuid4()),
            category=TEST_FAILURE,
            feature_id="feature-auth",
            issue_number=42,
            content={
                "test_path": "tests/test_auth.py::test_login",
                "error_type": "AssertionError",
                "error_message": "Expected 200, got 401",
                "stack_trace": "File test_auth.py, line 15...",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["auth", "login", "401"],
        )

        # Act
        memory_store.add(issue_entry)
        memory_store.save()

        # Assert
        results = memory_store.query(category=TEST_FAILURE, feature_id="feature-auth")
        assert len(results) == 1
        assert results[0].content["error_type"] == "AssertionError"

    def test_get_recommendation_from_similar_issue(self, memory_store: MemoryStore):
        """Should get recommendation based on similar past issues.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        # Arrange: Add a past successful fix
        past_fix = MemoryEntry(
            id=str(uuid4()),
            category=IMPLEMENTATION_SUCCESS,
            feature_id="feature-auth",
            issue_number=41,
            content={
                "problem": "401 error on login",
                "solution": "Add Bearer token to Authorization header",
                "files_modified": ["src/auth/client.py"],
            },
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["auth", "401", "token"],
        )
        memory_store.add(past_fix)

        # RED PHASE: RecommendationEngine doesn't exist yet
        # This import will fail, making the test fail as expected
        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)

        # Act: Get recommendation for similar issue
        current_issue = {
            "error_type": "401 error",
            "context": "authentication failed",
            "tags": ["auth", "401"],
        }
        recommendations = engine.get_recommendations(current_issue, limit=3)

        # Assert
        assert len(recommendations) >= 1
        assert "Authorization header" in recommendations[0].suggestion

    def test_apply_fix_and_record_outcome(self, memory_store: MemoryStore):
        """Applying a fix should record the outcome for future learning.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)

        # Arrange: Record a fix attempt
        fix_entry = MemoryEntry(
            id=str(uuid4()),
            category=RECOVERY_PATTERN,
            feature_id="feature-auth",
            issue_number=42,
            content={
                "problem": "401 error on login",
                "attempted_fix": "Added Bearer token",
                "recommendation_id": "rec-123",
            },
            outcome=None,  # Not yet known
            created_at=datetime.now().isoformat(),
            tags=["auth", "fix-attempt"],
        )
        memory_store.add(fix_entry)

        # Act: Record outcome of the fix
        engine.record_outcome(
            entry_id=fix_entry.id,
            success=True,
            notes="Fix resolved the 401 error",
        )

        # Assert
        updated = memory_store.get_entry(fix_entry.id)
        assert updated.outcome == "success"

    def test_full_cycle_improves_future_recommendations(
        self, memory_store: MemoryStore
    ):
        """Complete learning cycle should improve future recommendations.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)

        # Cycle 1: Record initial issue and fix
        issue_1 = MemoryEntry(
            id=str(uuid4()),
            category=TEST_FAILURE,
            feature_id="feature-db",
            issue_number=100,
            content={
                "error_type": "ConnectionError",
                "error_message": "Database connection refused",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["database", "connection"],
        )
        memory_store.add(issue_1)

        fix_1 = MemoryEntry(
            id=str(uuid4()),
            category=IMPLEMENTATION_SUCCESS,
            feature_id="feature-db",
            issue_number=100,
            content={
                "problem": "Database connection refused",
                "solution": "Start database container",
                "confidence": 0.9,
            },
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["database", "docker"],
        )
        memory_store.add(fix_1)

        # Cycle 2: Similar issue should get better recommendation
        similar_issue = {
            "error_type": "ConnectionError",
            "context": "database connection failed",
            "tags": ["database", "connection"],
        }

        recommendations = engine.get_recommendations(similar_issue, limit=3)

        # Should recommend the successful fix from cycle 1
        assert len(recommendations) >= 1
        assert any("container" in r.suggestion.lower() for r in recommendations)


class TestPatternEmergesOverSessions:
    """Test: patterns detected across sessions.

    Patterns should emerge when similar issues occur across multiple sessions.
    """

    @pytest.fixture
    def memory_path(self, tmp_path: Path) -> Path:
        """Create temporary memory store path."""
        return tmp_path / "memory" / "memories.json"

    def test_pattern_detection_across_sessions(self, memory_path: Path):
        """Pattern detector should identify recurring issues across sessions.

        RED: This test will fail because PatternDetector doesn't exist.
        """
        # Session 1: Record first occurrence
        store_1 = MemoryStore(store_path=memory_path)
        entry_1 = MemoryEntry(
            id=str(uuid4()),
            category=TEST_FAILURE,
            feature_id="feature-api",
            issue_number=10,
            content={
                "test_path": "tests/test_api.py::test_timeout",
                "error_type": "TimeoutError",
                "error_message": "Request timed out after 30s",
            },
            outcome="failure",
            created_at=(datetime.now() - timedelta(days=7)).isoformat(),
            tags=["api", "timeout"],
        )
        store_1.add(entry_1)
        store_1.save()

        # Session 2: Record second occurrence (simulates new session)
        store_2 = MemoryStore.load(store_path=memory_path)
        entry_2 = MemoryEntry(
            id=str(uuid4()),
            category=TEST_FAILURE,
            feature_id="feature-api",
            issue_number=20,
            content={
                "test_path": "tests/test_api.py::test_slow_endpoint",
                "error_type": "TimeoutError",
                "error_message": "Request timed out after 30s",
            },
            outcome="failure",
            created_at=(datetime.now() - timedelta(days=3)).isoformat(),
            tags=["api", "timeout"],
        )
        store_2.add(entry_2)
        store_2.save()

        # Session 3: Detect pattern
        store_3 = MemoryStore.load(store_path=memory_path)

        # RED PHASE: PatternDetector doesn't exist yet
        from swarm_attack.memory.patterns import PatternDetector

        detector = PatternDetector(store_3)
        patterns = detector.detect_patterns(min_occurrences=2)

        # Assert pattern was detected
        assert len(patterns) >= 1
        timeout_pattern = next(
            (p for p in patterns if "timeout" in p.name.lower()), None
        )
        assert timeout_pattern is not None
        assert timeout_pattern.occurrence_count >= 2

    def test_pattern_includes_common_tags(self, memory_path: Path):
        """Detected patterns should include common tags.

        RED: This test will fail because PatternDetector doesn't exist.
        """
        store = MemoryStore(store_path=memory_path)

        # Add multiple entries with common tags
        for i in range(3):
            entry = MemoryEntry(
                id=str(uuid4()),
                category=SCHEMA_DRIFT,
                feature_id="feature-models",
                issue_number=30 + i,
                content={
                    "class_name": "UserModel",
                    "conflict_type": "duplicate_definition",
                },
                outcome="blocked",
                created_at=(datetime.now() - timedelta(days=i)).isoformat(),
                tags=["models", "schema", "duplicate"],
            )
            store.add(entry)
        store.save()

        from swarm_attack.memory.patterns import PatternDetector

        detector = PatternDetector(store)
        patterns = detector.detect_patterns(min_occurrences=2)

        # Pattern should include common tags
        assert len(patterns) >= 1
        assert "duplicate" in patterns[0].common_tags

    def test_pattern_detection_respects_time_window(self, memory_path: Path):
        """Pattern detection should consider time window.

        RED: This test will fail because PatternDetector doesn't exist.
        """
        store = MemoryStore(store_path=memory_path)

        # Add old entry (outside 30-day window)
        old_entry = MemoryEntry(
            id=str(uuid4()),
            category=BUG_PATTERN,
            feature_id="feature-old",
            issue_number=1,
            content={"bug_type": "memory_leak"},
            outcome="failure",
            created_at=(datetime.now() - timedelta(days=60)).isoformat(),
            tags=["memory", "leak"],
        )
        store.add(old_entry)

        # Add recent entries
        for i in range(2):
            entry = MemoryEntry(
                id=str(uuid4()),
                category=BUG_PATTERN,
                feature_id="feature-new",
                issue_number=100 + i,
                content={"bug_type": "null_pointer"},
                outcome="failure",
                created_at=(datetime.now() - timedelta(days=i)).isoformat(),
                tags=["null", "pointer"],
            )
            store.add(entry)
        store.save()

        from swarm_attack.memory.patterns import PatternDetector

        detector = PatternDetector(store)
        patterns = detector.detect_patterns(min_occurrences=2, days=30)

        # Old entry should not form a pattern (outside window)
        memory_leak_pattern = next(
            (p for p in patterns if "memory_leak" in str(p.content)), None
        )
        assert memory_leak_pattern is None

        # Recent entries should form a pattern
        null_pointer_pattern = next(
            (p for p in patterns if "null_pointer" in str(p.content)), None
        )
        assert null_pointer_pattern is not None


class TestRecommendationsImproveOverTime:
    """Test: recs get better with data.

    Recommendations should improve as more successful outcomes are recorded.
    """

    @pytest.fixture
    def memory_path(self, tmp_path: Path) -> Path:
        """Create temporary memory store path."""
        return tmp_path / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, memory_path: Path) -> MemoryStore:
        """Create MemoryStore with temp path."""
        return MemoryStore(store_path=memory_path)

    def test_recommendations_rank_by_success_rate(self, memory_store: MemoryStore):
        """Recommendations with higher success rates should rank higher.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        # Add fix with high success rate (5 successes, 1 failure)
        for i in range(5):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=IMPLEMENTATION_SUCCESS,
                feature_id="feature-cache",
                issue_number=200 + i,
                content={
                    "problem": "cache miss",
                    "solution": "Increase TTL to 3600",
                },
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=["cache", "ttl"],
            ))

        memory_store.add(MemoryEntry(
            id=str(uuid4()),
            category=RECOVERY_PATTERN,
            feature_id="feature-cache",
            issue_number=206,
            content={
                "problem": "cache miss",
                "solution": "Increase TTL to 3600",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["cache", "ttl"],
        ))

        # Add fix with low success rate (1 success, 3 failures)
        memory_store.add(MemoryEntry(
            id=str(uuid4()),
            category=IMPLEMENTATION_SUCCESS,
            feature_id="feature-cache",
            issue_number=300,
            content={
                "problem": "cache miss",
                "solution": "Clear cache on every request",
            },
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["cache", "clear"],
        ))

        for i in range(3):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=RECOVERY_PATTERN,
                feature_id="feature-cache",
                issue_number=301 + i,
                content={
                    "problem": "cache miss",
                    "solution": "Clear cache on every request",
                },
                outcome="failure",
                created_at=datetime.now().isoformat(),
                tags=["cache", "clear"],
            ))

        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)
        current_issue = {"error_type": "cache miss", "tags": ["cache"]}
        recommendations = engine.get_recommendations(current_issue, limit=2)

        # Higher success rate solution should rank first
        assert len(recommendations) >= 2
        assert "TTL" in recommendations[0].suggestion
        assert recommendations[0].confidence > recommendations[1].confidence

    def test_recommendation_confidence_increases_with_data(
        self, memory_store: MemoryStore
    ):
        """Confidence should increase as more successful outcomes are recorded.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)

        # Initial state: no data
        issue = {"error_type": "import_error", "tags": ["import"]}
        initial_recs = engine.get_recommendations(issue, limit=1)
        initial_confidence = initial_recs[0].confidence if initial_recs else 0.0

        # Add successful outcomes
        for i in range(5):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=IMPLEMENTATION_SUCCESS,
                feature_id="feature-imports",
                issue_number=400 + i,
                content={
                    "problem": "import_error",
                    "solution": "Add missing __init__.py",
                },
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=["import", "init"],
            ))

        # Get recommendations again
        updated_recs = engine.get_recommendations(issue, limit=1)
        updated_confidence = updated_recs[0].confidence if updated_recs else 0.0

        # Confidence should have increased
        assert updated_confidence > initial_confidence

    def test_recent_successes_weighted_higher(self, memory_store: MemoryStore):
        """Recent successful outcomes should have more weight.

        RED: This test will fail because RecommendationEngine doesn't exist.
        """
        # Add old success
        memory_store.add(MemoryEntry(
            id=str(uuid4()),
            category=IMPLEMENTATION_SUCCESS,
            feature_id="feature-retry",
            issue_number=500,
            content={
                "problem": "retry_exhausted",
                "solution": "Use exponential backoff",
            },
            outcome="success",
            created_at=(datetime.now() - timedelta(days=60)).isoformat(),
            tags=["retry", "backoff"],
        ))

        # Add recent success with different solution
        memory_store.add(MemoryEntry(
            id=str(uuid4()),
            category=IMPLEMENTATION_SUCCESS,
            feature_id="feature-retry",
            issue_number=501,
            content={
                "problem": "retry_exhausted",
                "solution": "Increase max_retries to 10",
            },
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["retry", "max_retries"],
        ))

        from swarm_attack.memory.recommendations import RecommendationEngine

        engine = RecommendationEngine(memory_store)
        issue = {"error_type": "retry_exhausted", "tags": ["retry"]}
        recommendations = engine.get_recommendations(issue, limit=2)

        # Recent solution should rank higher
        assert len(recommendations) >= 1
        assert "max_retries" in recommendations[0].suggestion


class TestMemoryPersistsAcrossRestarts:
    """Test: save/load cycle works.

    Memory should persist correctly across simulated restarts (save/load cycles).
    """

    @pytest.fixture
    def memory_path(self, tmp_path: Path) -> Path:
        """Create temporary memory store path."""
        return tmp_path / "memory" / "memories.json"

    def test_entries_persist_after_save_load(self, memory_path: Path):
        """Entries should be available after save/load cycle."""
        # Create and populate store
        store_1 = MemoryStore(store_path=memory_path)
        entry = MemoryEntry(
            id="test-persist-id",
            category=TEST_FAILURE,
            feature_id="feature-persist",
            issue_number=1,
            content={"test": "data"},
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["persist", "test"],
        )
        store_1.add(entry)
        store_1.save()

        # Simulate restart: create new store instance
        store_2 = MemoryStore.load(store_path=memory_path)

        # Assert entry persisted
        loaded = store_2.get_entry("test-persist-id")
        assert loaded is not None
        assert loaded.category == TEST_FAILURE
        assert loaded.content["test"] == "data"

    def test_query_count_persists(self, memory_path: Path):
        """Query count should persist across restarts."""
        store_1 = MemoryStore(store_path=memory_path)
        entry = MemoryEntry(
            id=str(uuid4()),
            category=SCHEMA_DRIFT,
            feature_id="feature-query",
            issue_number=None,
            content={},
            outcome=None,
            created_at=datetime.now().isoformat(),
            tags=[],
        )
        store_1.add(entry)

        # Perform queries
        store_1.query(category=SCHEMA_DRIFT)
        store_1.query(category=SCHEMA_DRIFT)
        store_1.query(category=SCHEMA_DRIFT)
        store_1.save()

        # Simulate restart
        store_2 = MemoryStore.load(store_path=memory_path)

        # Query count should be persisted
        stats = store_2.get_stats()
        assert stats["total_queries"] == 3

    def test_hit_counts_persist(self, memory_path: Path):
        """Hit counts should persist across restarts."""
        store_1 = MemoryStore(store_path=memory_path)
        entry = MemoryEntry(
            id="hit-count-test",
            category=BUG_PATTERN,
            feature_id="feature-hits",
            issue_number=5,
            content={"bug": "example"},
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["bug"],
        )
        store_1.add(entry)

        # Query to increment hit count
        store_1.query(category=BUG_PATTERN)  # hit_count = 1
        store_1.query(category=BUG_PATTERN)  # hit_count = 2
        store_1.save()

        # Simulate restart
        store_2 = MemoryStore.load(store_path=memory_path)

        # Hit count should be persisted
        loaded = store_2.get_entry("hit-count-test")
        assert loaded.hit_count == 2

    def test_multiple_save_load_cycles(self, memory_path: Path):
        """Memory should remain consistent through multiple cycles."""
        entry_ids = []

        # Cycle 1: Add entries
        store = MemoryStore(store_path=memory_path)
        for i in range(3):
            entry_id = f"cycle-test-{i}"
            entry_ids.append(entry_id)
            store.add(MemoryEntry(
                id=entry_id,
                category=RECOVERY_PATTERN,
                feature_id="feature-cycles",
                issue_number=i,
                content={"cycle": 1, "index": i},
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=["cycle"],
            ))
        store.save()

        # Cycle 2: Load, modify, save
        store = MemoryStore.load(store_path=memory_path)
        store.query(category=RECOVERY_PATTERN)  # Increment hits
        store.add(MemoryEntry(
            id="cycle-test-new",
            category=RECOVERY_PATTERN,
            feature_id="feature-cycles",
            issue_number=99,
            content={"cycle": 2},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["cycle"],
        ))
        entry_ids.append("cycle-test-new")
        store.save()

        # Cycle 3: Load and verify
        store = MemoryStore.load(store_path=memory_path)

        # All entries should be present
        for entry_id in entry_ids:
            assert store.get_entry(entry_id) is not None

        # Total should be 4
        stats = store.get_stats()
        assert stats["total_entries"] == 4

    def test_corrupted_file_handled_gracefully(self, memory_path: Path):
        """Loading corrupted file should not crash."""
        # Create corrupted JSON file
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text("{ corrupted json data [[[")

        # Should not raise, returns empty store
        store = MemoryStore.load(store_path=memory_path)

        # Store should be usable
        assert store.get_stats()["total_entries"] == 0


class TestAnalyticsReflectActivity:
    """Test: analytics accurate after operations.

    Analytics should accurately reflect all memory operations.
    """

    @pytest.fixture
    def memory_path(self, tmp_path: Path) -> Path:
        """Create temporary memory store path."""
        return tmp_path / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, memory_path: Path) -> MemoryStore:
        """Create MemoryStore with temp path."""
        return MemoryStore(store_path=memory_path)

    def test_category_counts_accurate_after_adds(self, memory_store: MemoryStore):
        """Category counts should reflect added entries."""
        # Add entries in different categories
        categories = [TEST_FAILURE, TEST_FAILURE, SCHEMA_DRIFT, BUG_PATTERN]
        for i, category in enumerate(categories):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=category,
                feature_id="feature-analytics",
                issue_number=i,
                content={},
                outcome=None,
                created_at=datetime.now().isoformat(),
                tags=[],
            ))

        analytics = MemoryAnalytics(memory_store)
        counts = analytics.category_counts()

        assert counts[TEST_FAILURE] == 2
        assert counts[SCHEMA_DRIFT] == 1
        assert counts[BUG_PATTERN] == 1

    def test_hit_rate_accurate_after_queries(self, memory_store: MemoryStore):
        """Hit rate should reflect query activity."""
        # Add 4 entries
        for i in range(4):
            memory_store.add(MemoryEntry(
                id=f"analytics-hit-{i}",
                category=TEST_FAILURE,
                feature_id="feature-hitrate",
                issue_number=i,
                content={"index": i},
                outcome=None,
                created_at=datetime.now().isoformat(),
                tags=[f"tag-{i}"],
            ))

        analytics = MemoryAnalytics(memory_store)

        # Initial hit rate should be 0
        assert analytics.hit_rate() == 0.0

        # Query to hit 2 of 4 entries
        memory_store.query(category=TEST_FAILURE, limit=2)

        # Hit rate should be 0.5 (2/4 entries hit)
        assert analytics.hit_rate() == 0.5

    def test_growth_timeline_accurate(self, memory_store: MemoryStore):
        """Growth timeline should reflect entry creation dates."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Add entries on different days
        dates = [today, today, yesterday, two_days_ago, two_days_ago]
        for i, date in enumerate(dates):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=RECOVERY_PATTERN,
                feature_id="feature-timeline",
                issue_number=i,
                content={},
                outcome=None,
                created_at=date.isoformat(),
                tags=[],
            ))

        analytics = MemoryAnalytics(memory_store)
        timeline = analytics.growth_timeline(days=7)

        today_key = today.strftime("%Y-%m-%d")
        yesterday_key = yesterday.strftime("%Y-%m-%d")
        two_days_key = two_days_ago.strftime("%Y-%m-%d")

        assert timeline[today_key] == 2
        assert timeline[yesterday_key] == 1
        assert timeline[two_days_key] == 2

    def test_analytics_after_delete(self, memory_store: MemoryStore):
        """Analytics should update after entry deletion."""
        # Add entries
        entry_id = "to-delete"
        memory_store.add(MemoryEntry(
            id=entry_id,
            category=SCHEMA_DRIFT,
            feature_id="feature-delete",
            issue_number=1,
            content={},
            outcome=None,
            created_at=datetime.now().isoformat(),
            tags=[],
        ))
        memory_store.add(MemoryEntry(
            id="keep-this",
            category=SCHEMA_DRIFT,
            feature_id="feature-delete",
            issue_number=2,
            content={},
            outcome=None,
            created_at=datetime.now().isoformat(),
            tags=[],
        ))

        analytics = MemoryAnalytics(memory_store)

        # Before delete
        assert analytics.category_counts()[SCHEMA_DRIFT] == 2

        # Delete one entry
        memory_store.delete(entry_id)

        # After delete
        assert analytics.category_counts()[SCHEMA_DRIFT] == 1

    def test_analytics_report_generation(self, memory_store: MemoryStore):
        """Generate report should include all key metrics."""
        # Add some test data
        for i in range(5):
            memory_store.add(MemoryEntry(
                id=str(uuid4()),
                category=TEST_FAILURE if i < 3 else BUG_PATTERN,
                feature_id="feature-report",
                issue_number=i,
                content={"test": "data"},
                outcome="failure",
                created_at=datetime.now().isoformat(),
                tags=["report"],
            ))

        # Perform some queries
        memory_store.query(category=TEST_FAILURE)

        analytics = MemoryAnalytics(memory_store)
        report = analytics.generate_report()

        # Report should contain key sections
        assert "Memory Store Analytics Report" in report
        assert "Total Entries: 5" in report
        assert TEST_FAILURE in report
        assert BUG_PATTERN in report
        assert "Hit Rate:" in report
        assert "Age Distribution:" in report

    def test_analytics_after_prune(self, memory_store: MemoryStore):
        """Analytics should update after pruning old entries."""
        now = datetime.now()
        old_date = (now - timedelta(days=40)).isoformat()
        recent_date = now.isoformat()

        # Add old and recent entries
        memory_store.add(MemoryEntry(
            id="old-entry",
            category=BUG_PATTERN,
            feature_id="feature-prune",
            issue_number=1,
            content={},
            outcome=None,
            created_at=old_date,
            tags=[],
        ))
        memory_store.add(MemoryEntry(
            id="recent-entry",
            category=BUG_PATTERN,
            feature_id="feature-prune",
            issue_number=2,
            content={},
            outcome=None,
            created_at=recent_date,
            tags=[],
        ))

        analytics = MemoryAnalytics(memory_store)

        # Before prune
        assert analytics.category_counts()[BUG_PATTERN] == 2

        # Prune entries older than 30 days
        memory_store.prune_old_entries(days=30)

        # After prune
        assert analytics.category_counts()[BUG_PATTERN] == 1
