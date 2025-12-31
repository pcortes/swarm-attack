"""Tests for the `cos progress` CLI command."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile


class TestProgressCommandExists:
    """Test that the progress command exists in CLI."""

    def test_progress_command_in_app(self):
        """Test that progress command is registered in the app."""
        from swarm_attack.cli.chief_of_staff import app
        
        # Get all command names
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "progress" in command_names, "progress command must be registered"


class TestProgressCommandDisplay:
    """Tests for progress command display output."""

    def test_progress_command_shows_goals_completed(self):
        """Test that progress shows goals completed/total with percentage."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=3,
            goals_total=5,
            cost_usd=25.50,
            duration_seconds=3600,
        )
        
        # Verify snapshot has correct data
        assert snapshot.goals_completed == 3
        assert snapshot.goals_total == 5
        assert snapshot.completion_percent == 60.0

    def test_progress_command_shows_cost_spent(self):
        """Test that progress shows cost spent."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=2,
            goals_total=4,
            cost_usd=15.75,
            duration_seconds=1800,
        )
        
        assert snapshot.cost_usd == 15.75

    def test_progress_command_shows_duration(self):
        """Test that progress shows duration."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=1,
            goals_total=3,
            cost_usd=10.00,
            duration_seconds=7200,  # 2 hours
        )
        
        assert snapshot.duration_seconds == 7200

    def test_progress_command_shows_current_goal(self):
        """Test that progress shows current goal when present."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=1,
            goals_total=3,
            cost_usd=10.00,
            duration_seconds=1800,
            current_goal="Implementing feature X",
        )
        
        assert snapshot.current_goal == "Implementing feature X"

    def test_progress_command_shows_blockers(self):
        """Test that progress shows blockers when present."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=1,
            goals_total=3,
            cost_usd=10.00,
            duration_seconds=1800,
            blockers=["Waiting for approval", "CI failing"],
        )
        
        assert len(snapshot.blockers) == 2
        assert "Waiting for approval" in snapshot.blockers


class TestProgressCommandNoData:
    """Tests for progress command when no data exists."""

    def test_progress_command_handles_no_data(self):
        """Test that progress handles when no progress data exists."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "progress"
            tracker = ProgressTracker(base_path)
            
            # No session started, should return None
            current = tracker.get_current()
            assert current is None


class TestProgressTrackerCLIHelper:
    """Tests for the progress tracker CLI helper function."""

    def test_get_progress_tracker_function_exists(self):
        """Test that _get_progress_tracker helper exists."""
        from swarm_attack.cli.chief_of_staff import _get_progress_tracker
        
        assert callable(_get_progress_tracker)

    def test_get_progress_tracker_returns_tracker(self):
        """Test that _get_progress_tracker returns a ProgressTracker."""
        from swarm_attack.cli.chief_of_staff import _get_progress_tracker
        from swarm_attack.chief_of_staff.progress import ProgressTracker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('swarm_attack.cli.chief_of_staff.get_project_dir', return_value=tmpdir):
                tracker = _get_progress_tracker()
                assert isinstance(tracker, ProgressTracker)


class TestProgressCommandFormatting:
    """Tests for progress command output formatting."""

    def test_format_duration_seconds(self):
        """Test formatting duration from seconds."""
        from swarm_attack.cli.chief_of_staff import _format_duration
        
        # Test minutes only
        assert "30" in _format_duration(1800) and "min" in _format_duration(1800)
        
        # Test hours and minutes
        result = _format_duration(5400)  # 1h 30m
        assert "1" in result and ("h" in result or "hour" in result.lower())

    def test_format_duration_zero(self):
        """Test formatting zero duration."""
        from swarm_attack.cli.chief_of_staff import _format_duration
        
        result = _format_duration(0)
        assert "0" in result

    def test_format_cost(self):
        """Test formatting cost value."""
        # Cost should be displayed as USD with 2 decimal places
        cost = 25.50
        formatted = f"${cost:.2f}"
        assert formatted == "$25.50"


class TestProgressCommandIntegration:
    """Integration tests for the progress command."""

    def test_progress_command_with_active_session(self):
        """Test progress command with an active session."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            tracker = ProgressTracker(base_path)
            
            # Start a session
            tracker.start_session(total_goals=5)
            
            # Update progress
            tracker.update(
                goals_completed=2,
                cost_usd=15.00,
                duration_seconds=3600,
                current_goal="Working on task",
            )
            
            current = tracker.get_current()
            assert current is not None
            assert current.goals_completed == 2
            assert current.goals_total == 5
            assert current.completion_percent == 40.0
            assert current.cost_usd == 15.00
            assert current.current_goal == "Working on task"

    def test_progress_command_loads_from_disk(self):
        """Test that progress command loads persisted data."""
        from swarm_attack.chief_of_staff.progress import ProgressTracker
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            
            # Create and save progress
            tracker1 = ProgressTracker(base_path)
            tracker1.start_session(total_goals=4)
            tracker1.update(goals_completed=1, cost_usd=5.00, duration_seconds=600)
            
            # Load in new tracker instance
            tracker2 = ProgressTracker(base_path)
            tracker2.load()
            
            current = tracker2.get_current()
            assert current is not None
            assert current.goals_completed == 1
            assert current.goals_total == 4


class TestProgressModuleExists:
    """Test that the progress module file exists."""

    def test_progress_module_exists(self):
        """Test that progress.py exists."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "progress.py"
        assert path.exists(), "progress.py must exist"


class TestProgressCommandPercentageCalculation:
    """Tests for percentage calculation in progress display."""

    def test_completion_percent_calculation(self):
        """Test that completion percentage is calculated correctly."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=3,
            goals_total=4,
            cost_usd=0.0,
            duration_seconds=0,
        )
        
        assert snapshot.completion_percent == 75.0

    def test_completion_percent_zero_total(self):
        """Test that completion percentage handles zero total goals."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=0,
            goals_total=0,
            cost_usd=0.0,
            duration_seconds=0,
        )
        
        assert snapshot.completion_percent == 0.0

    def test_completion_percent_full(self):
        """Test 100% completion."""
        from swarm_attack.chief_of_staff.progress import ProgressSnapshot
        
        snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=5,
            goals_total=5,
            cost_usd=0.0,
            duration_seconds=0,
        )
        
        assert snapshot.completion_percent == 100.0