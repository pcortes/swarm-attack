"""Tests for the `cos progress --history` flag."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile


class TestProgressHistoryFlagExists:
    """Test that the --history flag exists on progress command."""

    def test_progress_command_has_history_parameter(self):
        """Test that progress command accepts --history flag."""
        from swarm_attack.cli.chief_of_staff import progress_command
        import inspect

        sig = inspect.signature(progress_command)
        param_names = list(sig.parameters.keys())
        assert "history" in param_names, "progress command must have history parameter"

    def test_progress_command_history_default_false(self):
        """Test that --history flag defaults to False."""
        from swarm_attack.cli.chief_of_staff import progress_command
        import inspect

        sig = inspect.signature(progress_command)
        history_param = sig.parameters.get("history")
        assert history_param is not None
        assert history_param.default is False or (
            hasattr(history_param.default, "default") and history_param.default.default is False
        )


class TestProgressHistoryDisplay:
    """Tests for progress history display output."""

    def test_progress_tracker_get_history_returns_list(self):
        """Test that ProgressTracker.get_history() returns a list."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "progress"
            tracker = ProgressTracker(base_path)

            history = tracker.get_history()
            assert isinstance(history, list)

    def test_progress_history_shows_timestamps(self):
        """Test that progress history entries have timestamps."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker, ProgressSnapshot

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)

            # Start session and make updates
            tracker.start_session(total_goals=3)
            tracker.update(goals_completed=1, cost_usd=5.0, duration_seconds=600)
            tracker.update(goals_completed=2, cost_usd=10.0, duration_seconds=1200)

            history = tracker.get_history()

            # Should have 3 entries (initial + 2 updates)
            assert len(history) >= 3

            # Each entry should have a timestamp
            for snapshot in history:
                assert snapshot.timestamp is not None
                assert len(snapshot.timestamp) > 0

    def test_progress_history_chronological_order(self):
        """Test that progress history is in chronological order."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)

            tracker.start_session(total_goals=5)
            tracker.update(goals_completed=1)
            tracker.update(goals_completed=2)
            tracker.update(goals_completed=3)

            history = tracker.get_history()

            # Verify chronological order by parsing timestamps
            for i in range(len(history) - 1):
                ts1 = history[i].timestamp
                ts2 = history[i + 1].timestamp
                # Later entries should have same or later timestamps
                assert ts1 <= ts2

    def test_progress_history_includes_goals_data(self):
        """Test that each history entry includes goals data."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)

            tracker.start_session(total_goals=4)
            tracker.update(goals_completed=2, cost_usd=15.0, duration_seconds=900)

            history = tracker.get_history()

            # Last entry should have updated goals
            last = history[-1]
            assert last.goals_completed == 2
            assert last.goals_total == 4
            assert last.cost_usd == 15.0
            assert last.duration_seconds == 900


class TestProgressHistoryNoData:
    """Tests for progress --history when no data exists."""

    def test_progress_history_empty_when_no_session(self):
        """Test that progress history is empty when no session started."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)

            history = tracker.get_history()
            assert history == []

    def test_progress_history_handles_missing_file(self):
        """Test that progress history handles missing progress file."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "nonexistent"
            tracker = ProgressTracker(base_path)

            # Should not raise, just return empty list
            tracker.load()
            history = tracker.get_history()
            assert history == []


class TestProgressHistoryPersistence:
    """Tests for progress history persistence."""

    def test_progress_history_persists_across_loads(self):
        """Test that progress history is persisted and can be loaded."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create and save history
            tracker1 = ProgressTracker(base_path)
            tracker1.start_session(total_goals=5)
            tracker1.update(goals_completed=1, cost_usd=5.0)
            tracker1.update(goals_completed=2, cost_usd=10.0)

            original_len = len(tracker1.get_history())

            # Load in new tracker
            tracker2 = ProgressTracker(base_path)
            tracker2.load()

            history = tracker2.get_history()
            assert len(history) == original_len

    def test_progress_history_snapshot_roundtrip(self):
        """Test that progress snapshots survive serialization roundtrip."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot

        original = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=3,
            goals_total=5,
            cost_usd=25.50,
            duration_seconds=3600,
            current_goal="Test goal",
            blockers=["Blocker 1", "Blocker 2"],
        )

        # Roundtrip through dict
        restored = ProgressSnapshot.from_dict(original.to_dict())

        assert restored.timestamp == original.timestamp
        assert restored.goals_completed == original.goals_completed
        assert restored.goals_total == original.goals_total
        assert restored.cost_usd == original.cost_usd
        assert restored.duration_seconds == original.duration_seconds
        assert restored.current_goal == original.current_goal
        assert restored.blockers == original.blockers


class TestProgressHistoryFormatting:
    """Tests for progress history output formatting."""

    def test_format_history_entry_timestamp(self):
        """Test that history entries can be formatted with timestamp."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot

        snapshot = ProgressSnapshot(
            timestamp="2024-01-15T10:30:00+00:00",
            goals_completed=2,
            goals_total=5,
            cost_usd=10.0,
            duration_seconds=1800,
        )

        # Should be able to display timestamp
        assert "2024-01-15" in snapshot.timestamp

    def test_format_history_entry_progress(self):
        """Test that history entries show progress."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot

        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=3,
            goals_total=5,
            cost_usd=15.0,
            duration_seconds=2400,
        )

        # Should calculate percentage correctly
        assert snapshot.completion_percent == 60.0


class TestProgressHistoryFileExists:
    """Test that the CLI module exists with history flag."""

    def test_cli_module_has_progress_command(self):
        """Test that chief_of_staff CLI module has progress command."""
        from swarm_attack.cli.chief_of_staff import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "progress" in command_names


class TestProgressHistoryIntegration:
    """Integration tests for progress --history command."""

    def test_progress_history_full_workflow(self):
        """Test full workflow of creating and retrieving history."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)

            # Simulate a session with multiple updates
            tracker.start_session(total_goals=4)
            tracker.update(goals_completed=1, cost_usd=5.0, duration_seconds=300, current_goal="Goal 1")
            tracker.update(goals_completed=2, cost_usd=12.0, duration_seconds=720, current_goal="Goal 2")
            tracker.update(goals_completed=3, cost_usd=18.0, duration_seconds=1200, blocker="Waiting for review")
            tracker.update(goals_completed=4, cost_usd=25.0, duration_seconds=1800)

            history = tracker.get_history()

            # Should have 5 entries (initial + 4 updates)
            assert len(history) == 5

            # First entry should be initial state
            assert history[0].goals_completed == 0
            assert history[0].goals_total == 4

            # Last entry should be final state
            assert history[-1].goals_completed == 4
            assert history[-1].cost_usd == 25.0
            assert history[-1].duration_seconds == 1800

            # One entry should have a blocker
            blockers_found = [s for s in history if s.blockers]
            assert len(blockers_found) >= 1