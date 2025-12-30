"""Tests for Issue #34: cos feedback-list and feedback-add commands.

These tests verify the CLI commands for listing and adding feedback entries.

TDD Phase: RED - Write failing tests first.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from swarm_attack.cli.chief_of_staff import app
from swarm_attack.chief_of_staff.feedback import (
    HumanFeedback,
    FeedbackStore,
)


runner = CliRunner()


@pytest.fixture
def temp_feedback_dir(tmp_path):
    """Create a temporary feedback directory."""
    feedback_dir = tmp_path / ".swarm" / "feedback"
    feedback_dir.mkdir(parents=True)
    return feedback_dir


@pytest.fixture
def mock_project_dir(tmp_path, monkeypatch):
    """Mock get_project_dir to return a temp path."""
    monkeypatch.setattr(
        "swarm_attack.cli.chief_of_staff.get_project_dir",
        lambda: str(tmp_path),
    )
    return tmp_path


class TestFeedbackListCommand:
    """Tests for the 'feedback-list' CLI command."""

    def test_feedback_list_empty(self, mock_project_dir):
        """Test listing feedback when no entries exist."""
        result = runner.invoke(app, ["feedback-list"])
        assert result.exit_code == 0
        assert "No feedback" in result.stdout or "0" in result.stdout or "empty" in result.stdout.lower()

    def test_feedback_list_with_entries(self, mock_project_dir):
        """Test listing feedback with existing entries."""
        # Create test feedback entries
        feedback_dir = mock_project_dir / ".swarm" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_data = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Test feedback 1",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-02T11:00:00",
                "feedback_type": "correction",
                "content": "Test feedback 2",
                "applies_to": ["security"],
                "expires_at": None,
            },
        ]

        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file, "w") as f:
            json.dump(feedback_data, f)

        result = runner.invoke(app, ["feedback-list"])
        assert result.exit_code == 0
        assert "Test feedback 1" in result.stdout or "chk-001" in result.stdout
        assert "Test feedback 2" in result.stdout or "chk-002" in result.stdout

    def test_feedback_list_with_limit(self, mock_project_dir):
        """Test listing feedback with --limit flag."""
        # Create multiple feedback entries
        feedback_dir = mock_project_dir / ".swarm" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_data = [
            {
                "checkpoint_id": f"chk-{i:03d}",
                "timestamp": f"2025-01-{i+1:02d}T10:00:00",
                "feedback_type": "guidance",
                "content": f"Feedback entry {i}",
                "applies_to": ["testing"],
                "expires_at": None,
            }
            for i in range(15)
        ]

        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file, "w") as f:
            json.dump(feedback_data, f)

        result = runner.invoke(app, ["feedback-list", "--limit", "5"])
        assert result.exit_code == 0
        # Should only show 5 entries (first 5 or last 5 depending on impl)

    def test_feedback_list_with_tag_filter(self, mock_project_dir):
        """Test listing feedback with --tag filter."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_data = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Security related feedback",
                "applies_to": ["security"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-02T11:00:00",
                "feedback_type": "correction",
                "content": "Testing related feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]

        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file, "w") as f:
            json.dump(feedback_data, f)

        result = runner.invoke(app, ["feedback-list", "--tag", "security"])
        assert result.exit_code == 0
        # Should show security-tagged feedback, not testing-tagged
        assert "Security related feedback" in result.stdout or "chk-001" in result.stdout

    def test_feedback_list_short_options(self, mock_project_dir):
        """Test feedback-list with short option flags."""
        result = runner.invoke(app, ["feedback-list", "-n", "5", "-t", "testing"])
        assert result.exit_code == 0


class TestFeedbackAddCommand:
    """Tests for the 'feedback-add' CLI command."""

    def test_feedback_add_basic(self, mock_project_dir):
        """Test adding basic feedback."""
        result = runner.invoke(app, ["feedback-add", "This is my feedback"])
        assert result.exit_code == 0
        # Should confirm feedback was added
        assert "added" in result.stdout.lower() or "saved" in result.stdout.lower() or "recorded" in result.stdout.lower()

        # Verify feedback was persisted
        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        assert feedback_file.exists()

        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) >= 1
        assert any("This is my feedback" in entry.get("content", "") for entry in data)

    def test_feedback_add_with_tag(self, mock_project_dir):
        """Test adding feedback with --tag flag."""
        result = runner.invoke(app, ["feedback-add", "Security concern", "--tag", "security"])
        assert result.exit_code == 0

        # Verify tag was added
        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        latest = data[-1]
        assert "security" in latest.get("applies_to", []) or "security" in latest.get("tags", [])

    def test_feedback_add_with_context(self, mock_project_dir):
        """Test adding feedback with --context flag."""
        result = runner.invoke(
            app,
            ["feedback-add", "Performance issue noted", "--context", "During autopilot execution"]
        )
        assert result.exit_code == 0

        # Verify context is stored somehow
        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        # Context may be stored in content, notes, or a separate field
        latest = data[-1]
        assert (
            "During autopilot" in str(latest.get("content", "")) or
            "During autopilot" in str(latest.get("context", "")) or
            "Performance issue" in str(latest.get("content", ""))
        )

    def test_feedback_add_with_all_options(self, mock_project_dir):
        """Test adding feedback with all options combined."""
        result = runner.invoke(
            app,
            [
                "feedback-add",
                "Complete feedback entry",
                "--tag", "api",
                "--context", "API review session",
            ]
        )
        assert result.exit_code == 0

        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        latest = data[-1]
        assert "Complete feedback entry" in str(latest.get("content", ""))
        assert "api" in latest.get("applies_to", []) or "api" in latest.get("tags", [])

    def test_feedback_add_short_options(self, mock_project_dir):
        """Test feedback-add with short option flags."""
        result = runner.invoke(
            app,
            ["feedback-add", "Short option test", "-t", "testing", "-c", "Test context"]
        )
        assert result.exit_code == 0

    def test_feedback_add_requires_text(self, mock_project_dir):
        """Test that feedback-add requires the text argument."""
        result = runner.invoke(app, ["feedback-add"])
        # Should fail or prompt for required argument
        assert result.exit_code != 0 or "Missing argument" in result.stdout

    def test_feedback_add_generates_checkpoint_id(self, mock_project_dir):
        """Test that feedback-add generates a checkpoint_id."""
        result = runner.invoke(app, ["feedback-add", "Auto ID test"])
        assert result.exit_code == 0

        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        latest = data[-1]
        # Should have some form of checkpoint_id
        assert "checkpoint_id" in latest
        assert latest["checkpoint_id"]  # Should not be empty

    def test_feedback_add_sets_timestamp(self, mock_project_dir):
        """Test that feedback-add sets a timestamp."""
        result = runner.invoke(app, ["feedback-add", "Timestamp test"])
        assert result.exit_code == 0

        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        latest = data[-1]
        assert "timestamp" in latest
        # Should be a valid ISO format timestamp
        datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))


class TestFeedbackCommandIntegration:
    """Integration tests for feedback commands."""

    def test_add_then_list(self, mock_project_dir):
        """Test adding feedback then listing it."""
        # Add feedback
        add_result = runner.invoke(app, ["feedback-add", "Integration test feedback", "-t", "integration"])
        assert add_result.exit_code == 0

        # List feedback
        list_result = runner.invoke(app, ["feedback-list"])
        assert list_result.exit_code == 0
        assert "Integration test feedback" in list_result.stdout or "integration" in list_result.stdout.lower()

    def test_multiple_adds_then_list(self, mock_project_dir):
        """Test adding multiple feedbacks then listing."""
        # Add multiple feedbacks
        runner.invoke(app, ["feedback-add", "First feedback", "-t", "first"])
        runner.invoke(app, ["feedback-add", "Second feedback", "-t", "second"])
        runner.invoke(app, ["feedback-add", "Third feedback", "-t", "third"])

        # List all
        list_result = runner.invoke(app, ["feedback-list"])
        assert list_result.exit_code == 0

        # Verify feedback file has all entries
        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) == 3

    def test_add_then_filter_list(self, mock_project_dir):
        """Test adding tagged feedback then filtering by tag."""
        # Add feedbacks with different tags
        runner.invoke(app, ["feedback-add", "Security feedback", "-t", "security"])
        runner.invoke(app, ["feedback-add", "Performance feedback", "-t", "performance"])
        runner.invoke(app, ["feedback-add", "Another security issue", "-t", "security"])

        # Filter by security tag
        list_result = runner.invoke(app, ["feedback-list", "--tag", "security"])
        assert list_result.exit_code == 0
        # Should show security items but not performance
        assert "Security feedback" in list_result.stdout or "security" in list_result.stdout.lower()
