"""Tests for blocking checkpoint UX.

TDD RED phase: These tests define the expected behavior of CheckpointUX.
They should FAIL until we implement the actual code.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from swarm_attack.chief_of_staff.checkpoints import (
    Checkpoint,
    CheckpointOption,
    CheckpointTrigger,
)


class TestCheckpointUX:
    """Tests for interactive checkpoint UX."""

    @pytest.fixture
    def sample_checkpoint(self):
        """Create a sample checkpoint for testing."""
        return Checkpoint(
            checkpoint_id="test-123",
            trigger=CheckpointTrigger.HICCUP,
            context="Goal failed after retries.\nGoal: Implement auth\nError: Import failed",
            options=[
                CheckpointOption(
                    label="Proceed",
                    description="Continue execution",
                    is_recommended=True,
                ),
                CheckpointOption(
                    label="Skip",
                    description="Skip this goal",
                    is_recommended=False,
                ),
                CheckpointOption(
                    label="Pause",
                    description="Pause for manual review",
                    is_recommended=False,
                ),
            ],
            recommendation="Proceed is recommended based on similar past decisions",
            created_at="2025-01-01T00:00:00Z",
            goal_id="goal-1",
        )

    def test_checkpoint_ux_import(self):
        """CheckpointUX module can be imported."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        assert CheckpointUX is not None

    def test_checkpoint_ux_init(self):
        """CheckpointUX can be instantiated."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()
        assert ux is not None

    def test_format_checkpoint_includes_context(self, sample_checkpoint):
        """Formatted checkpoint includes the context."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        output = ux.format_checkpoint(sample_checkpoint)

        assert "Goal failed after retries" in output
        assert "HICCUP" in output

    def test_format_checkpoint_shows_numbered_options(self, sample_checkpoint):
        """Formatted checkpoint shows options with numbers."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        output = ux.format_checkpoint(sample_checkpoint)

        assert "[1]" in output
        assert "[2]" in output
        assert "[3]" in output
        assert "Proceed" in output
        assert "Skip" in output
        assert "Pause" in output

    def test_format_checkpoint_marks_recommended(self, sample_checkpoint):
        """Recommended option is marked."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        output = ux.format_checkpoint(sample_checkpoint)

        # Recommended should be marked somehow (recommended) or *
        assert "recommended" in output.lower() or "Proceed" in output

    def test_get_decision_returns_selected_option(self, sample_checkpoint):
        """get_decision returns the option user selected."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        # Mock user input of "1" (Proceed)
        with patch('builtins.input', return_value="1"):
            decision = ux.get_decision(sample_checkpoint)

        assert decision.chosen_option == "Proceed"
        assert decision.checkpoint_id == "test-123"

    def test_get_decision_skip_option(self, sample_checkpoint):
        """get_decision with input 2 returns Skip."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        with patch('builtins.input', return_value="2"):
            decision = ux.get_decision(sample_checkpoint)

        assert decision.chosen_option == "Skip"

    def test_get_decision_pause_option(self, sample_checkpoint):
        """get_decision with input 3 returns Pause."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        with patch('builtins.input', return_value="3"):
            decision = ux.get_decision(sample_checkpoint)

        assert decision.chosen_option == "Pause"

    def test_get_decision_empty_input_selects_recommended(self, sample_checkpoint):
        """Empty input selects the recommended option."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        # Empty input should select recommended (Proceed)
        with patch('builtins.input', return_value=""):
            decision = ux.get_decision(sample_checkpoint)

        assert decision.chosen_option == "Proceed"

    def test_get_decision_invalid_reprompts(self, sample_checkpoint):
        """Invalid input prompts again."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        # First invalid, then valid
        inputs = iter(["invalid", "99", "1"])
        with patch('builtins.input', side_effect=lambda _="": next(inputs)):
            decision = ux.get_decision(sample_checkpoint)

        assert decision.chosen_option == "Proceed"

    def test_get_decision_allows_notes(self, sample_checkpoint):
        """User can add notes to decision."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        # Input: option then notes
        inputs = iter(["1", "This is my note"])
        with patch('builtins.input', side_effect=lambda prompt="": next(inputs)):
            decision = ux.get_decision(sample_checkpoint, allow_notes=True)

        assert decision.chosen_option == "Proceed"
        assert decision.notes == "This is my note"

    def test_decision_dataclass_fields(self, sample_checkpoint):
        """CheckpointDecision has required fields."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX, CheckpointDecision

        decision = CheckpointDecision(
            checkpoint_id="test-123",
            chosen_option="Proceed",
            notes="test note",
        )

        assert decision.checkpoint_id == "test-123"
        assert decision.chosen_option == "Proceed"
        assert decision.notes == "test note"


class TestCheckpointUXIntegration:
    """Integration tests for checkpoint UX with autopilot."""

    @pytest.fixture
    def sample_checkpoint(self):
        """Create a sample checkpoint for testing."""
        return Checkpoint(
            checkpoint_id="int-test-456",
            trigger=CheckpointTrigger.UX_CHANGE,
            context="UX change detected in frontend/",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
                CheckpointOption(label="Skip", description="Skip goal", is_recommended=False),
            ],
            recommendation="Review the changes",
            created_at="2025-01-01T00:00:00Z",
            goal_id="goal-2",
        )

    def test_prompt_and_wait_blocks_until_input(self, sample_checkpoint):
        """prompt_and_wait blocks execution until user responds."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        call_order = []

        def mock_input(prompt=""):
            call_order.append("input")
            return "1"

        with patch('builtins.input', side_effect=mock_input):
            call_order.append("before")
            decision = ux.prompt_and_wait(sample_checkpoint)
            call_order.append("after")

        # Input should happen between before and after
        assert call_order == ["before", "input", "after"]
        assert decision.chosen_option == "Proceed"

    def test_prompt_and_wait_displays_formatted(self, sample_checkpoint, capsys):
        """prompt_and_wait displays formatted checkpoint."""
        from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
        ux = CheckpointUX()

        with patch('builtins.input', return_value="1"):
            ux.prompt_and_wait(sample_checkpoint)

        captured = capsys.readouterr()
        assert "UX_CHANGE" in captured.out or "UX change" in captured.out
