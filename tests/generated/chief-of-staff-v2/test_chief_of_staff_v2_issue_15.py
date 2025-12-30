"""Tests for Issue #15: Implement Episode logging and PreferenceLearner.

Tests for:
- Episode dataclass with required fields
- EpisodeStore with JSONL storage
- EpisodeStore.save(episode) appends to JSONL
- EpisodeStore.load_recent(limit=100) loads recent episodes
- PreferenceLearner.record_decision(checkpoint) extracts signals
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from swarm_attack.chief_of_staff.episodes import (
    Episode,
    EpisodeStore,
    PreferenceLearner,
    PreferenceSignal,
)
from swarm_attack.chief_of_staff.checkpoints import (
    Checkpoint,
    CheckpointTrigger,
)


class TestEpisodeDataclass:
    """Tests for Episode dataclass."""

    def test_episode_has_required_fields(self):
        """Episode has all required fields."""
        episode = Episode(
            episode_id="ep-001",
            timestamp="2025-01-01T12:00:00",
            goal_id="goal-001",
            success=True,
            cost_usd=2.50,
            duration_seconds=120,
        )

        assert episode.episode_id == "ep-001"
        assert episode.timestamp == "2025-01-01T12:00:00"
        assert episode.goal_id == "goal-001"
        assert episode.success is True
        assert episode.cost_usd == 2.50
        assert episode.duration_seconds == 120

    def test_episode_to_dict(self):
        """Episode.to_dict() returns dictionary."""
        episode = Episode(
            episode_id="ep-001",
            timestamp="2025-01-01T12:00:00",
            goal_id="goal-001",
            success=True,
            cost_usd=2.50,
            duration_seconds=120,
        )

        result = episode.to_dict()

        assert isinstance(result, dict)
        assert result["episode_id"] == "ep-001"
        assert result["success"] is True

    def test_episode_from_dict(self):
        """Episode.from_dict() creates Episode."""
        data = {
            "episode_id": "ep-002",
            "timestamp": "2025-01-01T13:00:00",
            "goal_id": "goal-002",
            "success": False,
            "cost_usd": 1.00,
            "duration_seconds": 60,
            "error": "Connection timeout",
        }

        episode = Episode.from_dict(data)

        assert episode.episode_id == "ep-002"
        assert episode.success is False
        assert episode.error == "Connection timeout"


class TestEpisodeStore:
    """Tests for EpisodeStore."""

    def test_store_creates_directory(self):
        """EpisodeStore creates storage directory."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            assert base_path.exists()

    def test_save_appends_to_jsonl(self):
        """save() appends episode to JSONL file."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            episode = Episode(
                episode_id="ep-001",
                timestamp="2025-01-01T12:00:00",
                goal_id="goal-001",
                success=True,
                cost_usd=2.50,
                duration_seconds=120,
            )

            store.save(episode)

            # Verify file exists and contains content
            assert store.episodes_file.exists()
            content = store.episodes_file.read_text()
            assert "ep-001" in content

    def test_save_multiple_episodes(self):
        """save() appends multiple episodes."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            for i in range(3):
                episode = Episode(
                    episode_id=f"ep-{i:03d}",
                    timestamp=f"2025-01-01T{12+i}:00:00",
                    goal_id=f"goal-{i:03d}",
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
                store.save(episode)

            # Verify 3 lines in JSONL
            lines = store.episodes_file.read_text().strip().split("\n")
            assert len(lines) == 3

    def test_load_recent_returns_recent_first(self):
        """load_recent() returns most recent episodes first."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            for i in range(5):
                episode = Episode(
                    episode_id=f"ep-{i:03d}",
                    timestamp=f"2025-01-01T{12+i}:00:00",
                    goal_id=f"goal-{i:03d}",
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
                store.save(episode)

            episodes = store.load_recent(limit=3)

            assert len(episodes) == 3
            assert episodes[0].episode_id == "ep-004"  # Most recent first
            assert episodes[1].episode_id == "ep-003"
            assert episodes[2].episode_id == "ep-002"

    def test_load_recent_default_limit(self):
        """load_recent() defaults to limit=100."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            # Save 5 episodes
            for i in range(5):
                episode = Episode(
                    episode_id=f"ep-{i:03d}",
                    timestamp=f"2025-01-01T{12+i}:00:00",
                    goal_id=f"goal-{i:03d}",
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
                store.save(episode)

            episodes = store.load_recent()

            # All 5 returned (less than 100)
            assert len(episodes) == 5

    def test_load_recent_empty_file(self):
        """load_recent() returns empty list if file doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "episodes"
            store = EpisodeStore(base_path=base_path)

            episodes = store.load_recent()

            assert episodes == []


class TestPreferenceLearner:
    """Tests for PreferenceLearner."""

    def test_record_decision_extracts_signal(self):
        """record_decision() extracts PreferenceSignal."""
        learner = PreferenceLearner()

        checkpoint = Checkpoint(
            checkpoint_id="chk-001",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="High cost operation",
            options=[],
            recommendation="Proceed with caution",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-001",
            status="resolved",
            chosen_option="Proceed",
            resolved_at="2025-01-01T12:05:00",
        )

        signal = learner.record_decision(checkpoint)

        assert isinstance(signal, PreferenceSignal)
        assert signal.trigger == "COST_SINGLE"
        assert signal.chosen_option == "Proceed"

    def test_record_decision_classifies_approval(self):
        """record_decision() classifies approval signals."""
        learner = PreferenceLearner()

        checkpoint = Checkpoint(
            checkpoint_id="chk-001",
            trigger=CheckpointTrigger.ARCHITECTURE,
            context="Architecture change",
            options=[],
            recommendation="Review carefully",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-001",
            status="resolved",
            chosen_option="Approve",
            resolved_at="2025-01-01T12:05:00",
        )

        signal = learner.record_decision(checkpoint)

        assert signal.signal_type == "approved_architecture"

    def test_record_decision_classifies_rejection(self):
        """record_decision() classifies rejection signals."""
        learner = PreferenceLearner()

        checkpoint = Checkpoint(
            checkpoint_id="chk-001",
            trigger=CheckpointTrigger.UX_CHANGE,
            context="UI change",
            options=[],
            recommendation="Consider impact",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-001",
            status="resolved",
            chosen_option="Skip",
            resolved_at="2025-01-01T12:05:00",
        )

        signal = learner.record_decision(checkpoint)

        assert signal.signal_type == "rejected_ux_change"

    def test_get_signals_by_trigger(self):
        """get_signals_by_trigger() filters by trigger type."""
        learner = PreferenceLearner()

        # Record multiple decisions
        for trigger in [CheckpointTrigger.COST_SINGLE, CheckpointTrigger.UX_CHANGE, CheckpointTrigger.COST_SINGLE]:
            checkpoint = Checkpoint(
                checkpoint_id=f"chk-{trigger.value}",
                trigger=trigger,
                context="Context",
                options=[],
                recommendation="Rec",
                created_at="2025-01-01T12:00:00",
                goal_id="goal-001",
                status="resolved",
                chosen_option="Proceed",
            )
            learner.record_decision(checkpoint)

        cost_signals = learner.get_signals_by_trigger("COST_SINGLE")

        assert len(cost_signals) == 2

    def test_get_approval_rate(self):
        """get_approval_rate() calculates approval percentage."""
        learner = PreferenceLearner()

        # Record 3 approvals, 1 rejection
        for i, option in enumerate(["Approve", "Proceed", "Approve", "Skip"]):
            checkpoint = Checkpoint(
                checkpoint_id=f"chk-{i}",
                trigger=CheckpointTrigger.COST_SINGLE,
                context="Context",
                options=[],
                recommendation="Rec",
                created_at="2025-01-01T12:00:00",
                goal_id="goal-001",
                status="resolved",
                chosen_option=option,
            )
            learner.record_decision(checkpoint)

        rate = learner.get_approval_rate("COST_SINGLE")

        # 3/4 = 0.75
        assert rate == 0.75

    def test_get_approval_rate_no_data(self):
        """get_approval_rate() returns 0.0 with no data."""
        learner = PreferenceLearner()

        rate = learner.get_approval_rate("NONEXISTENT")

        assert rate == 0.0
