"""Tests for Episode dataclass retry_count and recovery_level fields.

Verifies that the Episode dataclass correctly handles the new fields
for tracking retry attempts and recovery levels.
"""

import pytest
from swarm_attack.chief_of_staff.episodes import Episode


class TestEpisodeNewFields:
    """Test that new fields exist and have correct defaults."""

    def test_episode_has_retry_count_field(self):
        """Episode should have retry_count field."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        assert hasattr(episode, "retry_count")

    def test_episode_has_recovery_level_field(self):
        """Episode should have recovery_level field."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        assert hasattr(episode, "recovery_level")

    def test_retry_count_default_is_zero(self):
        """retry_count should default to 0."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        assert episode.retry_count == 0

    def test_recovery_level_default_is_none(self):
        """recovery_level should default to None."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        assert episode.recovery_level is None


class TestEpisodeFieldTypes:
    """Test that new fields accept correct types."""

    def test_retry_count_accepts_int(self):
        """retry_count should accept integer values."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            retry_count=3,
        )
        assert episode.retry_count == 3

    def test_recovery_level_accepts_string(self):
        """recovery_level should accept string values."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="same",
        )
        assert episode.recovery_level == "same"

    def test_recovery_level_accepts_none(self):
        """recovery_level should accept None."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level=None,
        )
        assert episode.recovery_level is None


class TestEpisodeToDict:
    """Test that to_dict() correctly serializes new fields."""

    def test_to_dict_includes_retry_count(self):
        """to_dict() should include retry_count."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            retry_count=2,
        )
        data = episode.to_dict()
        assert "retry_count" in data
        assert data["retry_count"] == 2

    def test_to_dict_includes_recovery_level(self):
        """to_dict() should include recovery_level."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="escalate",
        )
        data = episode.to_dict()
        assert "recovery_level" in data
        assert data["recovery_level"] == "escalate"

    def test_to_dict_includes_none_recovery_level(self):
        """to_dict() should include recovery_level even when None."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        data = episode.to_dict()
        assert "recovery_level" in data
        assert data["recovery_level"] is None

    def test_to_dict_includes_zero_retry_count(self):
        """to_dict() should include retry_count even when 0."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=True,
            cost_usd=0.50,
            duration_seconds=60,
        )
        data = episode.to_dict()
        assert "retry_count" in data
        assert data["retry_count"] == 0


class TestEpisodeFromDict:
    """Test that from_dict() correctly deserializes new fields."""

    def test_from_dict_reads_retry_count(self):
        """from_dict() should read retry_count from dictionary."""
        data = {
            "episode_id": "test-1",
            "timestamp": "2024-01-01T00:00:00",
            "goal_id": "goal-1",
            "success": False,
            "cost_usd": 0.50,
            "duration_seconds": 60,
            "retry_count": 3,
        }
        episode = Episode.from_dict(data)
        assert episode.retry_count == 3

    def test_from_dict_reads_recovery_level(self):
        """from_dict() should read recovery_level from dictionary."""
        data = {
            "episode_id": "test-1",
            "timestamp": "2024-01-01T00:00:00",
            "goal_id": "goal-1",
            "success": False,
            "cost_usd": 0.50,
            "duration_seconds": 60,
            "recovery_level": "same",
        }
        episode = Episode.from_dict(data)
        assert episode.recovery_level == "same"

    def test_from_dict_defaults_missing_retry_count_to_zero(self):
        """from_dict() should default missing retry_count to 0."""
        data = {
            "episode_id": "test-1",
            "timestamp": "2024-01-01T00:00:00",
            "goal_id": "goal-1",
            "success": True,
            "cost_usd": 0.50,
            "duration_seconds": 60,
        }
        episode = Episode.from_dict(data)
        assert episode.retry_count == 0

    def test_from_dict_defaults_missing_recovery_level_to_none(self):
        """from_dict() should default missing recovery_level to None."""
        data = {
            "episode_id": "test-1",
            "timestamp": "2024-01-01T00:00:00",
            "goal_id": "goal-1",
            "success": True,
            "cost_usd": 0.50,
            "duration_seconds": 60,
        }
        episode = Episode.from_dict(data)
        assert episode.recovery_level is None


class TestEpisodeSerializationRoundtrip:
    """Test that serialization roundtrip works correctly."""

    def test_roundtrip_with_retry_count(self):
        """Episode with retry_count survives to_dict -> from_dict roundtrip."""
        original = Episode(
            episode_id="test-roundtrip",
            timestamp="2024-01-01T12:00:00",
            goal_id="goal-roundtrip",
            success=False,
            cost_usd=1.25,
            duration_seconds=120,
            retry_count=2,
        )
        data = original.to_dict()
        restored = Episode.from_dict(data)
        assert restored.retry_count == original.retry_count

    def test_roundtrip_with_recovery_level(self):
        """Episode with recovery_level survives to_dict -> from_dict roundtrip."""
        original = Episode(
            episode_id="test-roundtrip",
            timestamp="2024-01-01T12:00:00",
            goal_id="goal-roundtrip",
            success=False,
            cost_usd=1.25,
            duration_seconds=120,
            recovery_level="escalate",
        )
        data = original.to_dict()
        restored = Episode.from_dict(data)
        assert restored.recovery_level == original.recovery_level

    def test_roundtrip_with_both_fields(self):
        """Episode with both new fields survives roundtrip."""
        original = Episode(
            episode_id="test-roundtrip",
            timestamp="2024-01-01T12:00:00",
            goal_id="goal-roundtrip",
            success=False,
            cost_usd=1.25,
            duration_seconds=120,
            retry_count=3,
            recovery_level="same",
        )
        data = original.to_dict()
        restored = Episode.from_dict(data)
        assert restored.retry_count == original.retry_count
        assert restored.recovery_level == original.recovery_level

    def test_roundtrip_preserves_all_fields(self):
        """Full roundtrip preserves all Episode fields including new ones."""
        original = Episode(
            episode_id="test-full",
            timestamp="2024-01-01T12:00:00",
            goal_id="goal-full",
            success=False,
            cost_usd=2.50,
            duration_seconds=300,
            checkpoints_triggered=["cp-1", "cp-2"],
            error="Test error",
            notes="Test notes",
            retry_count=3,
            recovery_level="escalate",
        )
        data = original.to_dict()
        restored = Episode.from_dict(data)
        
        assert restored.episode_id == original.episode_id
        assert restored.timestamp == original.timestamp
        assert restored.goal_id == original.goal_id
        assert restored.success == original.success
        assert restored.cost_usd == original.cost_usd
        assert restored.duration_seconds == original.duration_seconds
        assert restored.checkpoints_triggered == original.checkpoints_triggered
        assert restored.error == original.error
        assert restored.notes == original.notes
        assert restored.retry_count == original.retry_count
        assert restored.recovery_level == original.recovery_level


class TestEpisodeBackwardCompatibility:
    """Test backward compatibility with existing data."""

    def test_existing_episode_without_new_fields_loads(self):
        """Existing JSONL entries without new fields should load successfully."""
        # Simulates an old JSONL entry without retry_count and recovery_level
        old_data = {
            "episode_id": "old-episode-1",
            "timestamp": "2024-01-01T00:00:00",
            "goal_id": "goal-old",
            "success": True,
            "cost_usd": 0.50,
            "duration_seconds": 60,
            "checkpoints_triggered": [],
            "error": None,
            "notes": None,
        }
        # Should not raise any errors
        episode = Episode.from_dict(old_data)
        assert episode.episode_id == "old-episode-1"
        assert episode.retry_count == 0
        assert episode.recovery_level is None

    def test_default_values_dont_break_existing_creation(self):
        """Creating Episode without new fields should work (backward compat)."""
        # This is the minimum required fields pattern from existing code
        episode = Episode(
            episode_id="min-fields",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-min",
            success=True,
            cost_usd=0.0,
            duration_seconds=0,
        )
        # Should have defaults for new fields
        assert episode.retry_count == 0
        assert episode.recovery_level is None


class TestEpisodeRecoveryLevelValues:
    """Test that recovery_level accepts RetryStrategy values."""

    def test_recovery_level_accepts_same_strategy(self):
        """recovery_level should accept 'same' (RetryStrategy.SAME.value)."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="same",
        )
        assert episode.recovery_level == "same"

    def test_recovery_level_accepts_alternative_strategy(self):
        """recovery_level should accept 'alternative' (RetryStrategy.ALTERNATIVE.value)."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="alternative",
        )
        assert episode.recovery_level == "alternative"

    def test_recovery_level_accepts_clarify_strategy(self):
        """recovery_level should accept 'clarify' (RetryStrategy.CLARIFY.value)."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="clarify",
        )
        assert episode.recovery_level == "clarify"

    def test_recovery_level_accepts_escalate_strategy(self):
        """recovery_level should accept 'escalate' (RetryStrategy.ESCALATE.value)."""
        episode = Episode(
            episode_id="test-1",
            timestamp="2024-01-01T00:00:00",
            goal_id="goal-1",
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            recovery_level="escalate",
        )
        assert episode.recovery_level == "escalate"