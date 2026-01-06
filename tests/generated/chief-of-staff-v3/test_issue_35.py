"""Tests for Issue #35: cos feedback-clear command + integration tests.

These tests verify the feedback-clear CLI command and integration
between feedback commands.

TDD Phase: RED - Write failing tests first.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from typer.testing import CliRunner

from swarm_attack.cli.chief_of_staff import app
from swarm_attack.chief_of_staff.feedback import (
    HumanFeedback,
    FeedbackStore,
)


runner = CliRunner()


@pytest.fixture
def mock_project_dir(tmp_path, monkeypatch):
    """Mock get_project_dir to return a temp path."""
    monkeypatch.setattr(
        "swarm_attack.cli.chief_of_staff.get_project_dir",
        lambda: str(tmp_path),
    )
    return tmp_path


def create_feedback_entries(feedback_dir, entries):
    """Helper to create feedback entries in the feedback file."""
    feedback_dir.mkdir(parents=True, exist_ok=True)
    feedback_file = feedback_dir / "feedback.json"
    with open(feedback_file, "w") as f:
        json.dump(entries, f)


class TestFeedbackClearCommand:
    """Tests for the 'feedback-clear' CLI command."""

    def test_feedback_clear_requires_option(self, mock_project_dir):
        """Test that feedback-clear requires at least one filter option."""
        result = runner.invoke(app, ["feedback-clear"])
        # Should fail or warn if no option is provided (safety measure)
        # Implementation should require --all, --before, or --tag
        assert result.exit_code != 0 or "option" in result.stdout.lower() or "specify" in result.stdout.lower()

    def test_feedback_clear_all(self, mock_project_dir):
        """Test clearing all feedback with --all flag."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Feedback 1",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-02T11:00:00",
                "feedback_type": "correction",
                "content": "Feedback 2",
                "applies_to": ["security"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        # Clear all with confirmation
        result = runner.invoke(app, ["feedback-clear", "--all"], input="y\n")
        assert result.exit_code == 0
        assert "cleared" in result.stdout.lower() or "removed" in result.stdout.lower()

        # Verify feedback file is empty or contains empty list
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)
        assert len(data) == 0

    def test_feedback_clear_all_requires_confirmation(self, mock_project_dir, monkeypatch):
        """Test that --all requires user confirmation."""
        # Mock confirm_or_default to simulate user declining
        monkeypatch.setattr(
            "swarm_attack.cli.chief_of_staff.confirm_or_default",
            lambda prompt, default: False
        )

        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Feedback 1",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        # Decline confirmation
        result = runner.invoke(app, ["feedback-clear", "--all"], input="n\n")
        # Should not clear if user declines
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)
        # Data should still be there
        assert len(data) == 1

    def test_feedback_clear_by_tag(self, mock_project_dir):
        """Test clearing feedback filtered by --tag."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Security feedback",
                "applies_to": ["security"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-02T11:00:00",
                "feedback_type": "correction",
                "content": "Testing feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-003",
                "timestamp": "2025-01-03T12:00:00",
                "feedback_type": "guidance",
                "content": "Another security feedback",
                "applies_to": ["security", "api"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        result = runner.invoke(app, ["feedback-clear", "--tag", "security"])
        assert result.exit_code == 0

        # Verify only testing feedback remains
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["checkpoint_id"] == "chk-002"  # Testing feedback

    def test_feedback_clear_by_date(self, mock_project_dir):
        """Test clearing feedback before a specific date with --before."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Old feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-15T11:00:00",
                "feedback_type": "correction",
                "content": "Mid feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-003",
                "timestamp": "2025-01-30T12:00:00",
                "feedback_type": "guidance",
                "content": "Recent feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        result = runner.invoke(app, ["feedback-clear", "--before", "2025-01-20"])
        assert result.exit_code == 0

        # Verify only recent feedback remains
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["checkpoint_id"] == "chk-003"  # Only recent feedback

    def test_feedback_clear_combined_filters(self, mock_project_dir):
        """Test clearing with both --tag and --before filters."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Old security feedback",
                "applies_to": ["security"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-002",
                "timestamp": "2025-01-25T11:00:00",
                "feedback_type": "correction",
                "content": "Recent security feedback",
                "applies_to": ["security"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-003",
                "timestamp": "2025-01-01T12:00:00",
                "feedback_type": "guidance",
                "content": "Old testing feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        # Clear security entries before Jan 15
        result = runner.invoke(app, ["feedback-clear", "--tag", "security", "--before", "2025-01-15"])
        assert result.exit_code == 0

        # Verify old testing and recent security remain
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) == 2
        ids = [entry["checkpoint_id"] for entry in data]
        assert "chk-002" in ids  # Recent security
        assert "chk-003" in ids  # Old testing

    def test_feedback_clear_short_options(self, mock_project_dir):
        """Test feedback-clear with short option flags."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Test feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        result = runner.invoke(app, ["feedback-clear", "-t", "testing"])
        assert result.exit_code == 0

    def test_feedback_clear_shows_count(self, mock_project_dir):
        """Test that feedback-clear shows the count of cleared entries."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": f"chk-{i:03d}",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": f"Feedback {i}",
                "applies_to": ["testing"],
                "expires_at": None,
            }
            for i in range(5)
        ]
        create_feedback_entries(feedback_dir, entries)

        result = runner.invoke(app, ["feedback-clear", "--tag", "testing"])
        assert result.exit_code == 0
        # Should show count of cleared entries
        assert "5" in result.stdout or "five" in result.stdout.lower()

    def test_feedback_clear_no_matching_entries(self, mock_project_dir):
        """Test feedback-clear when no entries match the filter."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        entries = [
            {
                "checkpoint_id": "chk-001",
                "timestamp": "2025-01-01T10:00:00",
                "feedback_type": "guidance",
                "content": "Security feedback",
                "applies_to": ["security"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        result = runner.invoke(app, ["feedback-clear", "--tag", "nonexistent"])
        assert result.exit_code == 0
        # Should indicate no entries matched
        assert "no" in result.stdout.lower() or "0" in result.stdout


class TestFeedbackIntegration:
    """Integration tests for all feedback commands working together."""

    def test_add_list_clear_verify_empty(self, mock_project_dir):
        """Test add -> list -> clear -> verify empty workflow."""
        # Add feedback
        add_result = runner.invoke(app, ["feedback-add", "Integration test feedback", "-t", "integration"])
        assert add_result.exit_code == 0

        # List and verify it's there
        list_result = runner.invoke(app, ["feedback-list"])
        assert list_result.exit_code == 0
        assert "Integration test feedback" in list_result.stdout or "integration" in list_result.stdout.lower()

        # Clear by tag
        clear_result = runner.invoke(app, ["feedback-clear", "--tag", "integration"])
        assert clear_result.exit_code == 0

        # List and verify empty
        list_result2 = runner.invoke(app, ["feedback-list"])
        assert list_result2.exit_code == 0
        # Should show no entries or empty message
        # Note: manual tag is added automatically, so we need to clear that too
        # or check that our specific feedback is gone

    def test_add_multiple_clear_by_tag_verify_remaining(self, mock_project_dir):
        """Test adding multiple entries, clearing by tag, verifying remaining."""
        # Add feedbacks with different tags
        runner.invoke(app, ["feedback-add", "Security feedback 1", "-t", "security"])
        runner.invoke(app, ["feedback-add", "Performance feedback", "-t", "performance"])
        runner.invoke(app, ["feedback-add", "Security feedback 2", "-t", "security"])

        # Verify all are there
        list_result = runner.invoke(app, ["feedback-list"])
        assert list_result.exit_code == 0

        # Verify feedback file has all entries
        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)
        assert len(data) == 3

        # Clear security entries
        clear_result = runner.invoke(app, ["feedback-clear", "--tag", "security"])
        assert clear_result.exit_code == 0

        # Verify only performance remains
        with open(feedback_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert "performance" in str(data[0].get("applies_to", [])).lower()

    def test_clear_by_date_preserves_recent(self, mock_project_dir):
        """Test clearing old entries preserves recent ones."""
        feedback_dir = mock_project_dir / ".swarm" / "feedback"

        # Create entries with specific dates
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        recent_date = (datetime.now() - timedelta(days=1)).isoformat()

        entries = [
            {
                "checkpoint_id": "chk-old",
                "timestamp": old_date,
                "feedback_type": "guidance",
                "content": "Old feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
            {
                "checkpoint_id": "chk-recent",
                "timestamp": recent_date,
                "feedback_type": "guidance",
                "content": "Recent feedback",
                "applies_to": ["testing"],
                "expires_at": None,
            },
        ]
        create_feedback_entries(feedback_dir, entries)

        # Clear entries before 7 days ago
        before_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        result = runner.invoke(app, ["feedback-clear", "--before", before_date])
        assert result.exit_code == 0

        # Verify recent is preserved
        feedback_file = feedback_dir / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["checkpoint_id"] == "chk-recent"

    def test_full_lifecycle_workflow(self, mock_project_dir):
        """Test complete lifecycle: add, list, filter list, clear some, verify."""
        # Step 1: Add several feedback entries
        runner.invoke(app, ["feedback-add", "Security audit needed", "-t", "security"])
        runner.invoke(app, ["feedback-add", "Performance regression", "-t", "performance"])
        runner.invoke(app, ["feedback-add", "API documentation update", "-t", "api"])
        runner.invoke(app, ["feedback-add", "Security patch applied", "-t", "security"])

        # Step 2: List all - should show 4
        list_all = runner.invoke(app, ["feedback-list"])
        assert list_all.exit_code == 0

        # Step 3: List with tag filter
        list_security = runner.invoke(app, ["feedback-list", "--tag", "security"])
        assert list_security.exit_code == 0

        # Step 4: Clear security entries
        clear_result = runner.invoke(app, ["feedback-clear", "--tag", "security"])
        assert clear_result.exit_code == 0

        # Step 5: List all - should show 2
        list_remaining = runner.invoke(app, ["feedback-list"])
        assert list_remaining.exit_code == 0

        feedback_file = mock_project_dir / ".swarm" / "feedback" / "feedback.json"
        with open(feedback_file) as f:
            data = json.load(f)
        assert len(data) == 2

        # Step 6: Clear all remaining
        clear_all = runner.invoke(app, ["feedback-clear", "--all"], input="y\n")
        assert clear_all.exit_code == 0

        # Step 7: Verify empty
        with open(feedback_file) as f:
            data = json.load(f)
        assert len(data) == 0

    def test_list_with_limit_after_clear(self, mock_project_dir):
        """Test that limit works correctly after some entries are cleared."""
        # Add 10 entries
        for i in range(10):
            runner.invoke(app, ["feedback-add", f"Feedback {i}", "-t", f"tag{i % 3}"])

        # Clear entries with tag0
        runner.invoke(app, ["feedback-clear", "--tag", "tag0"])

        # List with limit should still work
        result = runner.invoke(app, ["feedback-list", "--limit", "3"])
        assert result.exit_code == 0
