"""Integration tests for CheckpointUX -> MemoryStore integration.

Phase 2C: Memory-Powered UX Implementation
Tests for displaying similar past decisions in CheckpointUX.

TDD: Tests written BEFORE implementation (RED phase).
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


class TestSimilarDecisionsDisplay:
    """Tests for displaying similar past decisions in CheckpointUX."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, temp_store_path):
        """Create a MemoryStore instance with temp path."""
        return MemoryStore(store_path=temp_store_path)

    @pytest.fixture
    def populated_memory_store(self, temp_store_path):
        """Create a MemoryStore with checkpoint decision entries."""
        store = MemoryStore(store_path=temp_store_path)

        # Add checkpoint decisions with different triggers and outcomes
        decisions = [
            ("HICCUP", "Proceed", "Import error in utils module", True, 2),
            ("HICCUP", "Skip", "Missing dependency in requirements", False, 5),
            ("HICCUP", "Proceed", "Test configuration issue", True, 7),
            ("COST_SINGLE", "Proceed", "Expensive operation approved", True, 1),
            ("UX_CHANGE", "Skip", "UI change rejected", False, 3),
        ]

        for trigger, decision, context, was_accepted, days_ago in decisions:
            created_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
            entry = MemoryEntry(
                id=str(uuid4()),
                category="checkpoint_decision",
                feature_id="test-feature",
                issue_number=None,
                content={
                    "trigger": trigger,
                    "decision": decision,
                    "context": context,
                },
                outcome="applied" if was_accepted else "rejected",
                created_at=created_at,
                tags=[trigger, decision],
            )
            store.add(entry)

        store.save()
        return store

    @pytest.fixture
    def sample_checkpoint(self):
        """Create a sample checkpoint for testing."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointTrigger,
        )

        return Checkpoint(
            checkpoint_id=f"chk-{uuid4().hex[:12]}",
            trigger=CheckpointTrigger.HICCUP,
            context="Goal failed after retries. Error: Import failed in test suite",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
                CheckpointOption(label="Skip", description="Skip goal", is_recommended=False),
                CheckpointOption(label="Pause", description="Pause for manual review", is_recommended=False),
            ],
            recommendation="Proceed - Similar errors resolved by continuing",
            created_at=datetime.now().isoformat(),
            goal_id="goal-test-123",
            status="pending",
        )

    @pytest.fixture
    def sample_goal(self):
        """Create a sample DailyGoal for testing."""
        from dataclasses import dataclass, field

        @dataclass
        class MockGoal:
            tags: list[str] = field(default_factory=list)

        return MockGoal(tags=["implementation", "testing"])

    def test_checkpoint_shows_similar_decisions_from_memory(
        self, populated_memory_store, sample_checkpoint, sample_goal
    ):
        """Checkpoint display should include similar past decisions."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        # PreferenceLearner should accept memory_store parameter
        learner = PreferenceLearner(memory_store=populated_memory_store)
        ux = CheckpointUX(preference_learner=learner)

        # Format checkpoint with goal for similar decisions lookup
        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Should contain similar decisions section
        assert "Similar Past Decisions:" in formatted

    def test_similar_decisions_limited_to_three(
        self, populated_memory_store, sample_checkpoint, sample_goal
    ):
        """At most 3 similar decisions should be shown."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        learner = PreferenceLearner(memory_store=populated_memory_store)
        ux = CheckpointUX(preference_learner=learner)

        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Count bullet points (similar decisions)
        bullet_count = formatted.count("  •")
        assert bullet_count <= 3

    def test_similar_decisions_show_trigger_type(
        self, populated_memory_store, sample_checkpoint, sample_goal
    ):
        """Each similar decision should show its trigger type."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        learner = PreferenceLearner(memory_store=populated_memory_store)
        ux = CheckpointUX(preference_learner=learner)

        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Similar decisions section should contain trigger type
        if "Similar Past Decisions:" in formatted:
            # At least one trigger type should be visible (HICCUP, COST_SINGLE, etc.)
            assert "HICCUP" in formatted or "COST" in formatted or "UX" in formatted

    def test_similar_decisions_show_outcome(
        self, populated_memory_store, sample_checkpoint, sample_goal
    ):
        """Each similar decision should show approved/rejected."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        learner = PreferenceLearner(memory_store=populated_memory_store)
        ux = CheckpointUX(preference_learner=learner)

        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Should contain approval/rejection indicators
        has_approved = "✓ Approved" in formatted
        has_rejected = "✗ Rejected" in formatted
        # At least one outcome type should be present
        assert has_approved or has_rejected or "first time" in formatted.lower()

    def test_similar_decisions_show_relative_age(
        self, populated_memory_store, sample_checkpoint, sample_goal
    ):
        """Each similar decision should show age like '2 days ago'."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        learner = PreferenceLearner(memory_store=populated_memory_store)
        ux = CheckpointUX(preference_learner=learner)

        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Should contain relative time in parentheses
        # Examples: "(2 days ago)", "(1 week ago)", "(5 days ago)"
        assert "ago)" in formatted or "first time" in formatted.lower()

    def test_no_similar_decisions_when_memory_empty(
        self, memory_store, sample_checkpoint, sample_goal
    ):
        """No similar decisions section when memory has no matches."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        # Empty memory store
        learner = PreferenceLearner(memory_store=memory_store)
        ux = CheckpointUX(preference_learner=learner)

        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Should indicate no similar decisions or first time
        assert "first time" in formatted.lower() or "None" in formatted

    def test_works_without_memory_store(self, sample_checkpoint, sample_goal):
        """Existing behavior preserved when memory_store=None."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        # No memory store
        learner = PreferenceLearner()  # No memory_store parameter
        ux = CheckpointUX(preference_learner=learner)

        # Should not raise
        formatted = ux.format_checkpoint(sample_checkpoint, goal=sample_goal)

        # Should still format checkpoint correctly
        assert "HICCUP" in formatted
        assert "Options:" in formatted


class TestPreferenceLearnerMemoryIntegration:
    """Tests for PreferenceLearner using MemoryStore."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store_with_decisions(self, temp_store_path):
        """Create a MemoryStore with checkpoint decisions."""
        store = MemoryStore(store_path=temp_store_path)

        # Add decisions with different triggers
        for i, (trigger, decision) in enumerate([
            ("HICCUP", "Proceed"),
            ("HICCUP", "Skip"),
            ("COST_SINGLE", "Proceed"),
        ]):
            entry = MemoryEntry(
                id=str(uuid4()),
                category="checkpoint_decision",
                feature_id="test-feature",
                issue_number=None,
                content={
                    "trigger": trigger,
                    "decision": decision,
                    "context": f"Test context {i}",
                },
                outcome="applied" if decision == "Proceed" else "rejected",
                created_at=datetime.now().isoformat(),
                tags=[trigger, decision],
            )
            store.add(entry)

        store.save()
        return store

    def test_preference_learner_accepts_memory_store(self, memory_store_with_decisions):
        """PreferenceLearner should accept memory_store parameter."""
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        # Should not raise
        learner = PreferenceLearner(memory_store=memory_store_with_decisions)
        assert learner is not None

    def test_preference_learner_queries_memory_for_similar(self, memory_store_with_decisions):
        """find_similar_decisions should query MemoryStore."""
        from dataclasses import dataclass, field

        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        @dataclass
        class MockGoal:
            tags: list[str] = field(default_factory=list)

        learner = PreferenceLearner(memory_store=memory_store_with_decisions)
        goal = MockGoal(tags=["testing"])

        # Should return decisions from memory store
        similar = learner.find_similar_decisions(goal, k=3)

        # Should have found decisions
        assert len(similar) >= 1
        # Each result should have expected keys
        for decision in similar:
            assert "trigger" in decision
            assert "was_accepted" in decision

    def test_preference_learner_falls_back_without_memory(self):
        """Without memory_store, should use existing behavior."""
        from dataclasses import dataclass, field

        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        @dataclass
        class MockGoal:
            tags: list[str] = field(default_factory=list)

        # No memory store
        learner = PreferenceLearner()

        # Add a signal manually (old behavior)
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointTrigger,
        )

        checkpoint = Checkpoint(
            checkpoint_id="test-chk",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context",
            options=[CheckpointOption(label="Proceed", description="Go", is_recommended=True)],
            recommendation="Proceed",
            created_at=datetime.now().isoformat(),
            goal_id="test-goal",
            status="approved",
            chosen_option="Proceed",
        )

        learner.extract_signal(checkpoint)

        goal = MockGoal(tags=["testing"])
        similar = learner.find_similar_decisions(goal, k=3)

        # Should find the manually added signal
        assert len(similar) >= 1


class TestFormatAgeHelper:
    """Tests for _format_age helper method in CheckpointUX."""

    def test_format_age_seconds_ago(self):
        """Should format recent timestamps as 'just now'."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

        ux = CheckpointUX()
        now = datetime.now()
        timestamp = now.isoformat()

        age = ux._format_age(timestamp)
        assert age in ["just now", "1 minute ago", "a few seconds ago"]

    def test_format_age_minutes_ago(self):
        """Should format minutes ago."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

        ux = CheckpointUX()
        timestamp = (datetime.now() - timedelta(minutes=30)).isoformat()

        age = ux._format_age(timestamp)
        assert "minute" in age or "min" in age

    def test_format_age_hours_ago(self):
        """Should format hours ago."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

        ux = CheckpointUX()
        timestamp = (datetime.now() - timedelta(hours=3)).isoformat()

        age = ux._format_age(timestamp)
        assert "hour" in age

    def test_format_age_days_ago(self):
        """Should format days ago."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

        ux = CheckpointUX()
        timestamp = (datetime.now() - timedelta(days=2)).isoformat()

        age = ux._format_age(timestamp)
        assert "day" in age

    def test_format_age_weeks_ago(self):
        """Should format weeks ago."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

        ux = CheckpointUX()
        timestamp = (datetime.now() - timedelta(days=10)).isoformat()

        age = ux._format_age(timestamp)
        assert "week" in age or "day" in age
