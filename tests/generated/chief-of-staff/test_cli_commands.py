"""Integration tests for Chief of Staff CLI commands.

Tests the CLI commands exposed via `swarm-attack cos` subcommand.
These tests use Typer's CliRunner for isolated testing.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from swarm_attack.cli.chief_of_staff import app as cos_app
from swarm_attack.chief_of_staff.daily_log import DailyLog, DailyLogManager
from swarm_attack.chief_of_staff.goal_tracker import (
    DailyGoal,
    GoalPriority,
    GoalStatus,
)
from swarm_attack.chief_of_staff.state_gatherer import (
    RepoStateSnapshot,
    GitState,
    TestState,
    FeatureSummary,
    BugSummary,
    SpecSummary,
    PRDSummary,
)


runner = CliRunner()


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory with required structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create .swarm/chief-of-staff/daily-log structure
        daily_log_dir = project_dir / ".swarm" / "chief-of-staff" / "daily-log"
        daily_log_dir.mkdir(parents=True)

        # Create a sample daily log
        today = date.today()
        log_data = {
            "date": today.isoformat(),
            "goals": [
                {
                    "goal_id": "goal-test-1",
                    "description": "Test goal 1",
                    "priority": "high",
                    "estimated_minutes": 60,
                    "status": "pending",
                }
            ],
            "standups": [],
            "decisions": [],
            "summary": None,
        }
        log_file = daily_log_dir / f"{today.isoformat()}.json"
        log_file.write_text(json.dumps(log_data))

        yield project_dir


@pytest.fixture
def mock_state_snapshot() -> RepoStateSnapshot:
    """Create a mock RepoStateSnapshot for testing."""
    return RepoStateSnapshot(
        timestamp=datetime.now(),
        git=GitState(
            current_branch="main",
            status="clean",
            modified_files=[],
            recent_commits=["abc123 Initial commit"],
            ahead=0,
            behind=0,
        ),
        tests=TestState(
            total_tests=227,
            test_files=["test_example.py"],
        ),
        features=[
            FeatureSummary(
                feature_id="test-feature",
                phase="IMPLEMENTING",
                issue_count=5,
                completed_issues=3,
            ),
        ],
        bugs=[],
        prds=[],
        specs=[],
        github=None,
        interrupted_sessions=[],
        cost_today=2.50,
        cost_weekly=15.00,
    )


class TestCosHelp:
    """Test the --help flag for cos commands."""

    def test_cos_help_shows_commands(self):
        """Test that cos --help shows available commands."""
        result = runner.invoke(cos_app, ["--help"])
        assert result.exit_code == 0
        assert "standup" in result.output
        assert "checkin" in result.output
        assert "wrapup" in result.output
        assert "history" in result.output
        assert "next" in result.output

    def test_standup_help(self):
        """Test standup command help."""
        result = runner.invoke(cos_app, ["standup", "--help"])
        assert result.exit_code == 0
        assert "Morning standup" in result.output or "briefing" in result.output.lower()

    def test_checkin_help(self):
        """Test checkin command help."""
        result = runner.invoke(cos_app, ["checkin", "--help"])
        assert result.exit_code == 0
        assert "mid-day" in result.output.lower() or "status" in result.output.lower()

    def test_wrapup_help(self):
        """Test wrapup command help."""
        result = runner.invoke(cos_app, ["wrapup", "--help"])
        assert result.exit_code == 0
        assert "end" in result.output.lower() or "summary" in result.output.lower()

    def test_history_help(self):
        """Test history command help."""
        result = runner.invoke(cos_app, ["history", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output
        assert "--weekly" in result.output
        assert "--decisions" in result.output

    def test_next_help(self):
        """Test next command help."""
        result = runner.invoke(cos_app, ["next", "--help"])
        assert result.exit_code == 0
        assert "--all" in result.output


class TestCheckinCommand:
    """Test the checkin command."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_checkin_with_goals(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test checkin shows goal progress."""
        # Setup mocks
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Complete feature X",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.COMPLETE,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Fix bug Y",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
                status=GoalStatus.IN_PROGRESS,
            ),
        ]
        mock_dlm.get_today.return_value = mock_log
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["checkin"])

        assert result.exit_code == 0
        assert "Check-in" in result.output or "Goals" in result.output

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_checkin_no_goals(self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot):
        """Test checkin handles no goals gracefully."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = []
        mock_dlm.get_today.return_value = mock_log
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["checkin"])

        assert result.exit_code == 0
        assert "No goals" in result.output or "0" in result.output


class TestWrapupCommand:
    """Test the wrapup command."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_wrapup_shows_completion(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test wrapup shows completion rate."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Complete feature",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.COMPLETE,
                actual_minutes=45,
            ),
        ]
        mock_dlm.get_today.return_value = mock_log
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["wrapup"])

        assert result.exit_code == 0
        assert "Wrap-up" in result.output or "Completion" in result.output

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_wrapup_saves_summary(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test wrapup saves summary to daily log."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = []
        mock_dlm.get_today.return_value = mock_log
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["wrapup"])

        assert result.exit_code == 0
        mock_dlm.set_summary.assert_called_once()


class TestHistoryCommand:
    """Test the history command."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_history_default_days(self, mock_dlm_fn):
        """Test history shows last 7 days by default."""
        mock_dlm = MagicMock()
        mock_dlm.get_history.return_value = []
        mock_dlm_fn.return_value = mock_dlm

        result = runner.invoke(cos_app, ["history"])

        assert result.exit_code == 0
        mock_dlm.get_history.assert_called_once_with(7)

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_history_custom_days(self, mock_dlm_fn):
        """Test history with custom days."""
        mock_dlm = MagicMock()
        mock_dlm.get_history.return_value = []
        mock_dlm_fn.return_value = mock_dlm

        result = runner.invoke(cos_app, ["history", "--days", "14"])

        assert result.exit_code == 0
        mock_dlm.get_history.assert_called_once_with(14)

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_history_weekly_summary(self, mock_dlm_fn):
        """Test history with --weekly flag."""
        mock_dlm = MagicMock()
        mock_dlm.generate_weekly_summary.return_value = "# Weekly Summary\n\nNo data."
        mock_dlm_fn.return_value = mock_dlm

        result = runner.invoke(cos_app, ["history", "--weekly"])

        assert result.exit_code == 0
        mock_dlm.generate_weekly_summary.assert_called_once()

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_history_decisions(self, mock_dlm_fn):
        """Test history with --decisions flag."""
        mock_dlm = MagicMock()
        mock_dlm.get_decisions.return_value = []
        mock_dlm_fn.return_value = mock_dlm

        result = runner.invoke(cos_app, ["history", "--decisions"])

        assert result.exit_code == 0
        mock_dlm.get_decisions.assert_called_once()


class TestNextCommand:
    """Test the next command."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_next_shows_pending_goals(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test next shows pending goals."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Next task",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.PENDING,
            ),
        ]
        mock_dlm.get_today.return_value = mock_log
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["next"])

        assert result.exit_code == 0
        assert "Next" in result.output or "task" in result.output.lower()

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_next_all_shows_recommendations(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test next --all shows cross-feature recommendations."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = []
        mock_dlm.get_today.return_value = mock_log
        mock_dlm.get_yesterday.return_value = None
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["next", "--all"])

        assert result.exit_code == 0
        assert "Recommendation" in result.output or "P2" in result.output


class TestStandupCommand:
    """Test the standup command."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_standup_skip_goals(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test standup with goal selection skipped."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = []
        mock_dlm.get_today.return_value = mock_log
        mock_dlm.get_yesterday.return_value = None
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        # Input "0" to skip goal selection
        result = runner.invoke(cos_app, ["standup"], input="0\n")

        assert result.exit_code == 0
        assert "Standup" in result.output or "Morning" in result.output

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    @patch("swarm_attack.cli.chief_of_staff._get_state_gatherer")
    def test_standup_records_session(
        self, mock_gatherer_fn, mock_dlm_fn, mock_state_snapshot
    ):
        """Test standup records session in daily log."""
        mock_dlm = MagicMock()
        mock_log = DailyLog(date=date.today())
        mock_log.goals = []
        mock_dlm.get_today.return_value = mock_log
        mock_dlm.get_yesterday.return_value = None
        mock_dlm_fn.return_value = mock_dlm

        mock_gatherer = MagicMock()
        mock_gatherer.gather.return_value = mock_state_snapshot
        mock_gatherer_fn.return_value = mock_gatherer

        result = runner.invoke(cos_app, ["standup"], input="0\n")

        assert result.exit_code == 0
        mock_dlm.add_standup.assert_called_once()


class TestErrorHandling:
    """Test error handling in CLI commands."""

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_checkin_handles_exception(self, mock_dlm_fn):
        """Test checkin handles exceptions gracefully."""
        mock_dlm_fn.side_effect = Exception("Database error")

        result = runner.invoke(cos_app, ["checkin"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_wrapup_handles_exception(self, mock_dlm_fn):
        """Test wrapup handles exceptions gracefully."""
        mock_dlm_fn.side_effect = Exception("File not found")

        result = runner.invoke(cos_app, ["wrapup"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("swarm_attack.cli.chief_of_staff._get_daily_log_manager")
    def test_history_invalid_decision_type(self, mock_dlm_fn):
        """Test history handles invalid decision type."""
        mock_dlm = MagicMock()
        mock_dlm_fn.return_value = mock_dlm

        result = runner.invoke(cos_app, ["history", "--decisions", "--type", "invalid"])

        assert result.exit_code == 1
        assert "Invalid" in result.output or "type" in result.output.lower()
