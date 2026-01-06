"""
Tests for orchestrator delay configuration and behavior.

These tests verify that the spec debate orchestrator properly implements
delays between rounds and between agents within rounds to prevent API
rate limiting issues.

The delay configuration is in SpecDebateConfig:
- inter_round_delay_seconds: float = 60.0 (delay between debate rounds)
- intra_round_delay_seconds: float = 10.0 (delay between critic and moderator)

Test Coverage:
1. test_spec_debate_config_has_delay_fields - SpecDebateConfig has delay fields with correct defaults
2. test_inter_round_delay_called_between_rounds - Mock time.sleep, verify called with correct delay
3. test_no_delay_after_final_round - Verify no delay after last round (would be wasteful)
4. test_intra_round_delay_called_between_critic_moderator - Verify delay between critic and moderator
5. test_delays_logged_correctly - Verify inter_round_delay and intra_round_delay log events
6. test_zero_delay_skips_sleep - If delay config is 0, time.sleep should NOT be called
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch, call

import pytest

from swarm_attack.config import SpecDebateConfig, SwarmConfig
from swarm_attack.models import FeaturePhase
from swarm_attack.orchestrator import Orchestrator


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create a mock config with all required attributes."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.swarm_path = tmp_path / ".swarm"
    config.tests = MagicMock()
    config.tests.timeout_seconds = 300
    config.retry = MagicMock()
    config.retry.max_retries = 3
    config.retry.backoff_seconds = 5
    config.spec_debate = MagicMock()
    config.spec_debate.max_rounds = 3
    config.spec_debate.rubric_thresholds = {
        "completeness": 0.8,
        "clarity": 0.8,
        "testability": 0.8,
    }
    # Stalemate/disagreement thresholds
    config.spec_debate.consecutive_stalemate_threshold = 2
    config.spec_debate.disagreement_threshold = 2
    # Delay fields (these exist in SpecDebateConfig)
    config.spec_debate.inter_round_delay_seconds = 60.0
    config.spec_debate.intra_round_delay_seconds = 10.0
    return config


@pytest.fixture
def mock_logger() -> MagicMock:
    """Create a mock logger to capture log calls."""
    logger = MagicMock()
    logger.log = MagicMock()
    return logger


@pytest.fixture
def mock_state_store(tmp_path: Path) -> MagicMock:
    """Create a mock state store."""
    store = MagicMock()
    mock_state = MagicMock()
    mock_state.phase = FeaturePhase.PRD_READY  # Use enum, not string
    mock_state.spec_path = str(tmp_path / "specs" / "test-feature" / "spec-draft.md")
    store.load.return_value = mock_state
    return store


@pytest.fixture
def mock_agents() -> dict[str, MagicMock]:
    """Create mock agents for critic and moderator."""
    critic = MagicMock()
    critic.run.return_value = MagicMock(
        success=True,
        output={
            "scores": {"clarity": 0.9, "coverage": 0.9, "architecture": 0.9, "risk": 0.9},
            "issues": [],
            "issue_counts": {},
            "disputed_issues": [],
        },
        cost_usd=0.05,
        errors=[],
    )

    moderator = MagicMock()
    moderator.run.return_value = MagicMock(
        success=True,
        output={
            "dispositions": [],
            "disposition_counts": {"accepted": 0, "rejected": 0, "deferred": 0, "partial": 0},
        },
        cost_usd=0.05,
        errors=[],
    )

    return {"critic": critic, "moderator": moderator}


# ==============================================================================
# Test 1: SpecDebateConfig has delay fields with correct defaults
# ==============================================================================


class TestSpecDebateConfigDelayFields:
    """Test that SpecDebateConfig has the new delay configuration fields."""

    def test_spec_debate_config_has_inter_round_delay_field(self):
        """SpecDebateConfig should have inter_round_delay_seconds field."""
        config = SpecDebateConfig()

        # This should fail - the field doesn't exist yet
        assert hasattr(config, "inter_round_delay_seconds"), (
            "SpecDebateConfig must have inter_round_delay_seconds field"
        )

    def test_spec_debate_config_has_intra_round_delay_field(self):
        """SpecDebateConfig should have intra_round_delay_seconds field."""
        config = SpecDebateConfig()

        # This should fail - the field doesn't exist yet
        assert hasattr(config, "intra_round_delay_seconds"), (
            "SpecDebateConfig must have intra_round_delay_seconds field"
        )

    def test_inter_round_delay_default_is_60_seconds(self):
        """Default inter_round_delay_seconds should be 60.0."""
        config = SpecDebateConfig()

        # This should fail - the field doesn't exist yet
        assert config.inter_round_delay_seconds == 60.0, (
            "inter_round_delay_seconds default should be 60.0"
        )

    def test_intra_round_delay_default_is_10_seconds(self):
        """Default intra_round_delay_seconds should be 10.0."""
        config = SpecDebateConfig()

        # This should fail - the field doesn't exist yet
        assert config.intra_round_delay_seconds == 10.0, (
            "intra_round_delay_seconds default should be 10.0"
        )

    def test_delay_fields_are_floats(self):
        """Delay fields should be floats to allow sub-second precision."""
        config = SpecDebateConfig()

        # This should fail - the fields don't exist yet
        assert isinstance(config.inter_round_delay_seconds, float), (
            "inter_round_delay_seconds should be a float"
        )
        assert isinstance(config.intra_round_delay_seconds, float), (
            "intra_round_delay_seconds should be a float"
        )

    def test_custom_delay_values_accepted(self):
        """Custom delay values should be accepted in constructor."""
        config = SpecDebateConfig(
            inter_round_delay_seconds=30.0,
            intra_round_delay_seconds=5.0,
        )

        # This should fail - the fields don't exist yet
        assert config.inter_round_delay_seconds == 30.0
        assert config.intra_round_delay_seconds == 5.0


# ==============================================================================
# Test 2: Inter-round delay called between rounds
# ==============================================================================


@patch("swarm_attack.orchestrator.get_event_bus")
class TestInterRoundDelayCalled:
    """Test that time.sleep is called with inter_round_delay between rounds."""

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_inter_round_delay_called_between_rounds(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """time.sleep should be called with inter_round_delay between debate rounds."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        # Use 2 rounds for cleaner test (1 inter-round delay expected)
        mock_config.spec_debate.max_rounds = 2

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        # Create orchestrator with mocks
        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        # Mock debate retry handler to pass through to agents
        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            # Round 1: critic
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            # Round 1: moderator
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            # Round 2: critic (final round, no moderator)
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        # Run the debate pipeline
        result = orchestrator.run_spec_debate_only("test-feature")

        # Verify inter_round_delay was called between rounds (round 1->2)
        # With 2 rounds, we should have 1 inter-round delay (only between rounds, not after last)
        inter_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(60.0)  # inter_round_delay_seconds
        ]
        assert len(inter_round_calls) >= 1, (
            f"Expected at least 1 inter-round delay between rounds, got {len(inter_round_calls)}"
        )

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_inter_round_delay_uses_config_value(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """time.sleep should use the configured inter_round_delay_seconds value."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        # Set custom delay
        mock_config.spec_debate.inter_round_delay_seconds = 45.0
        mock_config.spec_debate.max_rounds = 2  # Just 2 rounds for simpler test

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Verify the custom delay value was used
        inter_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(45.0)
        ]
        assert len(inter_round_calls) == 1, (
            "Expected 1 inter-round delay with custom value 45.0"
        )


# ==============================================================================
# Test 3: No delay after final round
# ==============================================================================


@patch("swarm_attack.orchestrator.get_event_bus")
class TestNoDelayAfterFinalRound:
    """Test that no inter-round delay is added after the final round."""

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_no_delay_after_final_round(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """No delay should be added after the last debate round - would be wasteful."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = 60.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            # Round 1: critic, moderator
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            # Round 2: critic only (final round)
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Count inter-round delays - should be exactly 1 (between round 1 and 2)
        inter_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(60.0)
        ]
        assert len(inter_round_calls) == 1, (
            f"Expected exactly 1 inter-round delay (not after final round), got {len(inter_round_calls)}"
        )

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_single_round_has_no_inter_round_delay(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """Single-round debate should have no inter-round delay."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 1
        mock_config.spec_debate.inter_round_delay_seconds = 60.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            # Round 1: critic only (single round debate)
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # No inter-round delays for single round
        inter_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(60.0)
        ]
        assert len(inter_round_calls) == 0, (
            "Single round debate should have no inter-round delays"
        )


# ==============================================================================
# Test 4: Intra-round delay called between critic and moderator
# ==============================================================================


@patch("swarm_attack.orchestrator.get_event_bus")
class TestIntraRoundDelayCalled:
    """Test that time.sleep is called between critic and moderator within a round."""

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_intra_round_delay_called_between_critic_and_moderator(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """time.sleep should be called between critic and moderator in each round."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.intra_round_delay_seconds = 10.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            # Round 1: critic, moderator
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            # Round 2: critic only (final round, no moderator)
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Intra-round delay should be called once per round that has moderator
        # With 2 rounds, only round 1 has moderator, so 1 intra-round delay
        intra_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(10.0)
        ]
        assert len(intra_round_calls) == 1, (
            f"Expected 1 intra-round delay (moderator only runs in non-final rounds), got {len(intra_round_calls)}"
        )

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_intra_round_delay_uses_config_value(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """time.sleep should use the configured intra_round_delay_seconds value."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.intra_round_delay_seconds = 15.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Verify custom delay value was used
        intra_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(15.0)
        ]
        assert len(intra_round_calls) == 1, (
            "Expected 1 intra-round delay with custom value 15.0"
        )


# ==============================================================================
# Test 5: Delays logged correctly
# ==============================================================================


@patch("swarm_attack.orchestrator.get_event_bus")
class TestDelaysLoggedCorrectly:
    """Test that delay events are properly logged."""

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_inter_round_delay_logged(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """inter_round_delay event should be logged with delay value."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = 60.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Find log calls for inter_round_delay
        log_calls = [call for call in mock_logger.log.call_args_list]
        inter_round_log_calls = [
            c for c in log_calls
            if c[0][0] == "inter_round_delay"
        ]

        assert len(inter_round_log_calls) >= 1, (
            "Expected at least one 'inter_round_delay' log event"
        )

        # Verify log data includes delay seconds
        log_data = inter_round_log_calls[0][0][1]
        assert "delay_seconds" in log_data, "Log should include delay_seconds"
        assert log_data["delay_seconds"] == 60.0

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_intra_round_delay_logged(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """intra_round_delay event should be logged with delay value."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.intra_round_delay_seconds = 10.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Find log calls for intra_round_delay
        log_calls = [call for call in mock_logger.log.call_args_list]
        intra_round_log_calls = [
            c for c in log_calls
            if c[0][0] == "intra_round_delay"
        ]

        assert len(intra_round_log_calls) >= 1, (
            "Expected at least one 'intra_round_delay' log event"
        )

        # Verify log data includes delay seconds
        log_data = intra_round_log_calls[0][0][1]
        assert "delay_seconds" in log_data, "Log should include delay_seconds"
        assert log_data["delay_seconds"] == 10.0

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_delay_logs_include_feature_id_and_round(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """Delay log events should include feature_id and round number."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = 60.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Find log calls for inter_round_delay
        log_calls = [call for call in mock_logger.log.call_args_list]
        inter_round_log_calls = [
            c for c in log_calls
            if c[0][0] == "inter_round_delay"
        ]

        assert len(inter_round_log_calls) >= 1, "Expected inter_round_delay log"

        log_data = inter_round_log_calls[0][0][1]
        assert "feature_id" in log_data, "Log should include feature_id"
        assert log_data["feature_id"] == "test-feature"
        assert "round" in log_data, "Log should include round number"


# ==============================================================================
# Test 6: Zero delay skips sleep
# ==============================================================================


@patch("swarm_attack.orchestrator.get_event_bus")
class TestZeroDelaySkipsSleep:
    """Test that zero-value delays skip the time.sleep call entirely."""

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_zero_inter_round_delay_skips_sleep(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """When inter_round_delay_seconds is 0, time.sleep should not be called."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = 0.0
        mock_config.spec_debate.intra_round_delay_seconds = 0.0

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # With delays set to 0, time.sleep should not be called for delays
        # (it might be called elsewhere in the code, so we check for no 0.0 calls)
        zero_delay_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(0.0) or (len(c[0]) > 0 and c[0][0] == 0.0)
        ]
        assert len(zero_delay_calls) == 0, (
            "time.sleep(0.0) should not be called - skip sleep for zero delay"
        )

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_zero_intra_round_delay_skips_sleep(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """When intra_round_delay_seconds is 0, time.sleep should not be called for it."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = 60.0  # Keep this for isolation
        mock_config.spec_debate.intra_round_delay_seconds = 0.0  # Test zero intra delay

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Verify no zero-value sleeps (intra-round should be skipped)
        zero_delay_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(0.0) or (len(c[0]) > 0 and c[0][0] == 0.0)
        ]
        assert len(zero_delay_calls) == 0, (
            "time.sleep should not be called with 0.0 for zero intra_round_delay"
        )

        # But inter-round delay should still work
        inter_round_calls = [
            c for c in mock_sleep.call_args_list
            if c == call(60.0)
        ]
        assert len(inter_round_calls) >= 1, (
            "Inter-round delay should still be called when non-zero"
        )

    @patch("swarm_attack.orchestrator.time.sleep")
    def test_negative_delay_treated_as_zero(
        self,
        mock_sleep: MagicMock,
        mock_event_bus: MagicMock,
        mock_config: SwarmConfig,
        mock_logger: MagicMock,
        mock_state_store: MagicMock,
        mock_agents: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """Negative delay values should be treated as zero (no sleep)."""
        # Setup mock event bus
        mock_bus_instance = MagicMock()
        mock_event_bus.return_value = mock_bus_instance

        mock_config.spec_debate.max_rounds = 2
        mock_config.spec_debate.inter_round_delay_seconds = -10.0  # Invalid negative
        mock_config.spec_debate.intra_round_delay_seconds = -5.0   # Invalid negative

        # Setup spec file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec-draft.md").write_text("# Test Spec")

        orchestrator = Orchestrator(
            config=mock_config,
            logger=mock_logger,
            critic=mock_agents["critic"],
            moderator=mock_agents["moderator"],
            state_store=mock_state_store,
        )

        orchestrator._debate_retry_handler = MagicMock()
        orchestrator._debate_retry_handler.run_with_retry.side_effect = [
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["moderator"].run.return_value.output, cost_usd=0.05, errors=[]),
            MagicMock(success=True, output=mock_agents["critic"].run.return_value.output, cost_usd=0.05, errors=[]),
        ]

        orchestrator.run_spec_debate_only("test-feature")

        # Negative delays should not result in any sleep calls
        negative_or_zero_calls = [
            c for c in mock_sleep.call_args_list
            if len(c[0]) > 0 and c[0][0] <= 0
        ]
        assert len(negative_or_zero_calls) == 0, (
            "Negative delays should skip sleep entirely"
        )
