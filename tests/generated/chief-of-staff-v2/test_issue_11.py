"""Tests for Issue #11: Add checkpoint CLI commands.

This module tests the CLI commands for managing checkpoints:
- swarm-attack cos checkpoints: List all pending checkpoints
- swarm-attack cos approve <id>: Approve a checkpoint
- swarm-attack cos reject <id>: Reject a checkpoint
"""

import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock, patch

from swarm_attack.cli.chief_of_staff import app


runner = CliRunner()


class TestCheckpointsCommand:
    """Tests for the 'cos checkpoints' command."""

    def test_checkpoints_command_exists(self):
        """Test that checkpoints command is registered."""
        # Check the command exists in the app
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "checkpoints" in command_names

    def test_checkpoints_command_no_pending(self):
        """Test checkpoints command with no pending checkpoints."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_store") as mock_store:
            mock_instance = MagicMock()
            mock_instance.list_pending = AsyncMock(return_value=[])
            mock_store.return_value = mock_instance

            result = runner.invoke(app, ["checkpoints"])

            assert result.exit_code == 0
            assert "No pending checkpoints" in result.stdout

    def test_checkpoints_command_with_pending(self):
        """Test checkpoints command with pending checkpoints."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointTrigger,
        )

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test123",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context for checkpoint",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
                CheckpointOption(label="Skip", description="Skip this task", is_recommended=False),
            ],
            recommendation="Recommend proceeding",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-123",
            status="pending",
        )

        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_store") as mock_store:
            mock_instance = MagicMock()
            mock_instance.list_pending = AsyncMock(return_value=[mock_checkpoint])
            mock_store.return_value = mock_instance

            result = runner.invoke(app, ["checkpoints"])

            assert result.exit_code == 0
            assert "chk-test123" in result.stdout
            assert "COST_SINGLE" in result.stdout
            assert "goal-123" in result.stdout
            assert "Test context" in result.stdout


class TestApproveCommand:
    """Tests for the 'cos approve' command."""

    def test_approve_command_exists(self):
        """Test that approve command is registered."""
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "approve" in command_names

    def test_approve_command_success(self):
        """Test approving a checkpoint successfully."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointTrigger,
        )

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test123",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context",
            options=[],
            recommendation="Proceed",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-123",
            status="approved",
        )

        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(return_value=mock_checkpoint)
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["approve", "chk-test123"])

            assert result.exit_code == 0
            assert "Approved checkpoint: chk-test123" in result.stdout
            mock_instance.resolve_checkpoint.assert_called_once()

    def test_approve_command_with_notes(self):
        """Test approving a checkpoint with notes."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointTrigger,
        )

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test123",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context",
            options=[],
            recommendation="Proceed",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-123",
            status="approved",
        )

        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(return_value=mock_checkpoint)
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["approve", "chk-test123", "--notes", "Approved after review"])

            assert result.exit_code == 0
            assert "Approved checkpoint: chk-test123" in result.stdout
            assert "Approved after review" in result.stdout

            # Verify notes were passed
            call_kwargs = mock_instance.resolve_checkpoint.call_args
            assert call_kwargs.kwargs["notes"] == "Approved after review"

    def test_approve_command_not_found(self):
        """Test approving a non-existent checkpoint."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(side_effect=KeyError("Checkpoint not found"))
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["approve", "chk-nonexistent"])

            assert result.exit_code == 1
            assert "Checkpoint not found" in result.stdout


class TestRejectCommand:
    """Tests for the 'cos reject' command."""

    def test_reject_command_exists(self):
        """Test that reject command is registered."""
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "reject" in command_names

    def test_reject_command_success(self):
        """Test rejecting a checkpoint successfully."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointTrigger,
        )

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test123",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context",
            options=[],
            recommendation="Proceed",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-123",
            status="rejected",
        )

        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(return_value=mock_checkpoint)
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["reject", "chk-test123"])

            assert result.exit_code == 0
            assert "Rejected checkpoint: chk-test123" in result.stdout

            # Verify chosen_option is "Skip" for rejection
            call_kwargs = mock_instance.resolve_checkpoint.call_args
            assert call_kwargs.kwargs["chosen_option"] == "Skip"

    def test_reject_command_with_notes(self):
        """Test rejecting a checkpoint with notes."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointTrigger,
        )

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test123",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="Test context",
            options=[],
            recommendation="Proceed",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-123",
            status="rejected",
        )

        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(return_value=mock_checkpoint)
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["reject", "chk-test123", "--notes", "Too risky"])

            assert result.exit_code == 0
            assert "Rejected checkpoint: chk-test123" in result.stdout
            assert "Too risky" in result.stdout

            # Verify notes were passed
            call_kwargs = mock_instance.resolve_checkpoint.call_args
            assert call_kwargs.kwargs["notes"] == "Too risky"

    def test_reject_command_not_found(self):
        """Test rejecting a non-existent checkpoint."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_instance = MagicMock()
            mock_instance.resolve_checkpoint = AsyncMock(side_effect=KeyError("Checkpoint not found"))
            mock_system.return_value = mock_instance

            result = runner.invoke(app, ["reject", "chk-nonexistent"])

            assert result.exit_code == 1
            assert "Checkpoint not found" in result.stdout


class TestHelperFunctions:
    """Tests for CLI helper functions."""

    def test_get_checkpoint_store(self):
        """Test _get_checkpoint_store returns CheckpointStore."""
        from swarm_attack.cli.chief_of_staff import _get_checkpoint_store
        from swarm_attack.chief_of_staff.checkpoints import CheckpointStore

        store = _get_checkpoint_store()
        assert isinstance(store, CheckpointStore)

    def test_get_checkpoint_system(self):
        """Test _get_checkpoint_system returns CheckpointSystem."""
        from swarm_attack.cli.chief_of_staff import _get_checkpoint_system
        from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem

        system = _get_checkpoint_system()
        assert isinstance(system, CheckpointSystem)


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_checkpoints_command_handles_exception(self):
        """Test that checkpoints command handles exceptions gracefully."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_store") as mock_store:
            mock_store.side_effect = Exception("Connection error")

            result = runner.invoke(app, ["checkpoints"])

            assert result.exit_code == 1
            assert "Error listing checkpoints" in result.stdout

    def test_approve_command_handles_exception(self):
        """Test that approve command handles exceptions gracefully."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_system.side_effect = Exception("Connection error")

            result = runner.invoke(app, ["approve", "chk-test"])

            assert result.exit_code == 1
            assert "Error approving checkpoint" in result.stdout

    def test_reject_command_handles_exception(self):
        """Test that reject command handles exceptions gracefully."""
        with patch("swarm_attack.cli.chief_of_staff._get_checkpoint_system") as mock_system:
            mock_system.side_effect = Exception("Connection error")

            result = runner.invoke(app, ["reject", "chk-test"])

            assert result.exit_code == 1
            assert "Error rejecting checkpoint" in result.stdout
