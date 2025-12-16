"""Tests for Chief of Staff configuration."""

import pytest

from swarm_attack.chief_of_staff.config import (
    AutopilotConfig,
    CheckpointConfig,
    ChiefOfStaffConfig,
    PriorityConfig,
    StandupConfig,
)


class TestCheckpointConfig:
    """Tests for CheckpointConfig."""

    def test_defaults(self):
        """Test default values."""
        config = CheckpointConfig()
        assert config.budget_usd == 10.0
        assert config.duration_minutes == 120
        assert config.error_streak == 3

    def test_to_dict(self):
        """Test serialization to dict."""
        config = CheckpointConfig(budget_usd=5.0, duration_minutes=60, error_streak=2)
        d = config.to_dict()
        assert d["budget_usd"] == 5.0
        assert d["duration_minutes"] == 60
        assert d["error_streak"] == 2

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {"budget_usd": 15.0, "duration_minutes": 180, "error_streak": 5}
        config = CheckpointConfig.from_dict(d)
        assert config.budget_usd == 15.0
        assert config.duration_minutes == 180
        assert config.error_streak == 5

    def test_from_dict_with_defaults(self):
        """Test deserialization with missing keys uses defaults."""
        config = CheckpointConfig.from_dict({})
        assert config.budget_usd == 10.0
        assert config.duration_minutes == 120
        assert config.error_streak == 3

    def test_round_trip(self):
        """Test serialization round-trip."""
        original = CheckpointConfig(budget_usd=7.5, duration_minutes=90, error_streak=4)
        restored = CheckpointConfig.from_dict(original.to_dict())
        assert original == restored


class TestPriorityConfig:
    """Tests for PriorityConfig."""

    def test_defaults(self):
        """Test default values."""
        config = PriorityConfig()
        assert config.blocker_weight == 1.0
        assert config.approval_weight == 0.9
        assert config.regression_weight == 0.85
        assert config.spec_review_weight == 0.88
        assert config.in_progress_weight == 0.7
        assert config.new_feature_weight == 0.5

    def test_round_trip(self):
        """Test serialization round-trip."""
        original = PriorityConfig(blocker_weight=0.95, new_feature_weight=0.6)
        restored = PriorityConfig.from_dict(original.to_dict())
        assert original == restored


class TestStandupConfig:
    """Tests for StandupConfig."""

    def test_defaults(self):
        """Test default values."""
        config = StandupConfig()
        assert config.auto_run_on_start is False
        assert config.include_github is True
        assert config.include_tests is True
        assert config.include_specs is True
        assert config.history_days == 7

    def test_round_trip(self):
        """Test serialization round-trip."""
        original = StandupConfig(auto_run_on_start=True, history_days=14)
        restored = StandupConfig.from_dict(original.to_dict())
        assert original == restored


class TestAutopilotConfig:
    """Tests for AutopilotConfig."""

    def test_defaults(self):
        """Test default values."""
        config = AutopilotConfig()
        assert config.default_budget == 10.0
        assert config.default_duration == "2h"
        assert config.pause_on_approval is True
        assert config.pause_on_high_risk is True
        assert config.persist_on_checkpoint is True

    def test_round_trip(self):
        """Test serialization round-trip."""
        original = AutopilotConfig(default_budget=20.0, default_duration="4h")
        restored = AutopilotConfig.from_dict(original.to_dict())
        assert original == restored


class TestChiefOfStaffConfig:
    """Tests for ChiefOfStaffConfig."""

    def test_defaults(self):
        """Test default values."""
        config = ChiefOfStaffConfig()
        assert config.storage_path == ".swarm/chief-of-staff"
        assert isinstance(config.checkpoints, CheckpointConfig)
        assert isinstance(config.priorities, PriorityConfig)
        assert isinstance(config.standup, StandupConfig)
        assert isinstance(config.autopilot, AutopilotConfig)

    def test_to_dict(self):
        """Test serialization to dict."""
        config = ChiefOfStaffConfig()
        d = config.to_dict()
        assert "checkpoints" in d
        assert "priorities" in d
        assert "standup" in d
        assert "autopilot" in d
        assert d["storage_path"] == ".swarm/chief-of-staff"

    def test_from_dict_empty(self):
        """Test deserialization from empty dict uses defaults."""
        config = ChiefOfStaffConfig.from_dict({})
        assert config.storage_path == ".swarm/chief-of-staff"
        assert config.checkpoints.budget_usd == 10.0

    def test_from_dict_nested(self):
        """Test deserialization with nested config."""
        d = {
            "checkpoints": {"budget_usd": 25.0},
            "standup": {"history_days": 30},
            "storage_path": "/custom/path",
        }
        config = ChiefOfStaffConfig.from_dict(d)
        assert config.checkpoints.budget_usd == 25.0
        assert config.standup.history_days == 30
        assert config.storage_path == "/custom/path"
        # Other nested configs should have defaults
        assert config.priorities.blocker_weight == 1.0

    def test_round_trip(self):
        """Test serialization round-trip."""
        original = ChiefOfStaffConfig(
            checkpoints=CheckpointConfig(budget_usd=15.0),
            standup=StandupConfig(auto_run_on_start=True),
            storage_path="/test/path",
        )
        restored = ChiefOfStaffConfig.from_dict(original.to_dict())
        assert original.checkpoints == restored.checkpoints
        assert original.standup == restored.standup
        assert original.storage_path == restored.storage_path
