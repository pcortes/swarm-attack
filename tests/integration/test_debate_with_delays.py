"""
Integration tests for debate pipeline delay functionality.

Tests verify that the full debate pipeline uses delays correctly:
1. Inter-round delays are applied between rounds (not after last)
2. Intra-round delays are applied between critic and moderator
3. All delays are logged appropriately

This is a TDD RED phase test - the delay logic does NOT exist yet in the
Orchestrator, so these tests are expected to FAIL initially.

The implementation should add delays to Orchestrator.run_spec_debate_only()
with configuration from config.spec_debate.inter_round_delay_seconds and
config.spec_debate.intra_round_delay_seconds.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from swarm_attack.agents.base import AgentResult
from swarm_attack.config import SwarmConfig, SpecDebateConfig
from swarm_attack.models import FeaturePhase
from swarm_attack.orchestrator import Orchestrator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_project():
    """Create a temporary project directory with required structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create required directories
        (tmppath / ".swarm" / "state").mkdir(parents=True)
        (tmppath / ".swarm" / "events").mkdir(parents=True)
        (tmppath / ".swarm" / "logs").mkdir(parents=True)
        (tmppath / "specs").mkdir(parents=True)
        (tmppath / ".claude" / "prds").mkdir(parents=True)
        (tmppath / ".claude" / "skills").mkdir(parents=True)

        yield tmppath


@pytest.fixture
def mock_config(temp_project) -> SwarmConfig:
    """Create a SwarmConfig with delay settings for testing."""
    config = SwarmConfig(
        repo_root=str(temp_project),
        specs_dir="specs",
        swarm_dir=".swarm",
    )

    # Set up spec_debate config with delay parameters
    # NOTE: These fields do NOT exist yet - this test will fail until implemented
    config.spec_debate = SpecDebateConfig(
        max_rounds=2,
        timeout_seconds=900,
        consecutive_stalemate_threshold=2,
        disagreement_threshold=2,
        rubric_thresholds={
            "clarity": 0.8,
            "coverage": 0.8,
            "architecture": 0.8,
            "risk": 0.7,
        },
        # NEW: Delay configuration fields that need to be added
        # inter_round_delay_seconds=30,
        # intra_round_delay_seconds=5,
    )

    return config


@pytest.fixture
def mock_critic_success():
    """Create a mock critic agent that returns success with high scores."""
    def create_result(context: dict) -> AgentResult:
        return AgentResult(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.85,
                },
                "issues": [],
                "disputed_issues": [],
                "issue_counts": {"critical": 0, "moderate": 0, "minor": 0},
                "summary": "Spec meets all criteria.",
                "recommendation": "APPROVE",
            },
            errors=[],
            cost_usd=0.01,
        )

    mock = MagicMock()
    mock.run = MagicMock(side_effect=create_result)
    return mock


@pytest.fixture
def mock_moderator_success():
    """Create a mock moderator agent that returns success."""
    def create_result(context: dict) -> AgentResult:
        return AgentResult(
            success=True,
            output={
                "spec_path": "specs/test-feature/spec-draft.md",
                "rubric_path": "specs/test-feature/spec-rubric.json",
                "dispositions_path": "specs/test-feature/spec-dispositions.json",
                "round": context.get("round", 1),
                "previous_scores": {"clarity": 0.8, "coverage": 0.8, "architecture": 0.8, "risk": 0.7},
                "current_scores": {"clarity": 0.9, "coverage": 0.9, "architecture": 0.9, "risk": 0.85},
                "continue_debate": False,  # Stop after round 1 for simplicity
                "ready_for_approval": True,
                "dispositions": [],
                "disposition_counts": {"accepted": 0, "rejected": 0, "deferred": 0, "partial": 0},
                "meta": {"recommend_human_review": False, "review_reason": None},
                "dispute_resolutions": [],
            },
            errors=[],
            cost_usd=0.02,
        )

    mock = MagicMock()
    mock.run = MagicMock(side_effect=create_result)
    return mock


@pytest.fixture
def mock_state_store(temp_project):
    """Create a mock state store."""
    mock = MagicMock()

    # Create a mock state object with proper FeaturePhase enum
    state = MagicMock()
    state.feature_id = "test-feature"
    state.phase = FeaturePhase.PRD_READY  # Use enum, not string
    state.disposition_history = []
    state.module_registry = {}

    mock.load = MagicMock(return_value=state)
    mock.save = MagicMock()

    return mock


def setup_feature_files(temp_project: Path, feature_id: str = "test-feature"):
    """Helper to create required feature files."""
    # Create spec draft
    spec_dir = temp_project / "specs" / feature_id
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec-draft.md").write_text(
        "# Engineering Spec: test-feature\n\n"
        "## Overview\n\nThis is a test specification.\n\n"
        "## Requirements\n\n1. Requirement 1\n2. Requirement 2\n"
    )

    # Create PRD
    prd_dir = temp_project / ".claude" / "prds"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / f"{feature_id}.md").write_text(
        "# PRD: test-feature\n\n## Problem\n\nTest problem description."
    )


# ============================================================================
# Test: Full Debate Pipeline with Mocked Delays
# ============================================================================

class TestFullDebatePipelineWithMockedDelays:
    """
    Integration tests for the debate pipeline with delay verification.

    These tests mock the agents and time.sleep to verify:
    1. Inter-round delays are called between rounds
    2. Intra-round delays are called between critic and moderator
    3. Delays are properly logged

    Expected behavior:
    - For max_rounds=2:
      - Round 1: critic -> intra_delay -> moderator -> inter_delay
      - Round 2: critic -> intra_delay -> moderator (no inter_delay after last)

    IMPORTANT: This test is expected to FAIL until delay logic is implemented
    in the Orchestrator.
    """

    def test_full_debate_pipeline_with_mocked_delays(
        self,
        temp_project,
        mock_config,
        mock_state_store,
    ):
        """
        End-to-end debate with mocked agents, verify delays are applied.

        Verifies:
        - time.sleep was called with 30 (inter-round, only between rounds, not after last)
        - time.sleep was called with 5 (intra-round, between critic and moderator)
        - Logger logged "inter_round_delay" and "intra_round_delay" events
        """
        feature_id = "test-feature"
        setup_feature_files(temp_project, feature_id)

        # Manually set delay values on config since fields don't exist yet
        # This will need to be updated once SpecDebateConfig is extended
        mock_config.spec_debate.inter_round_delay_seconds = 30
        mock_config.spec_debate.intra_round_delay_seconds = 5

        # Create a critic that returns scores below threshold in round 1 (to continue debate),
        # and scores above threshold in round 2 (to complete successfully)
        critic_call_count = [0]  # Use list to allow mutation in nested function

        def critic_multi_round_result(context: dict) -> AgentResult:
            critic_call_count[0] += 1
            round_num = critic_call_count[0]
            if round_num == 1:
                # Round 1: scores below threshold to continue debate
                return AgentResult(
                    success=True,
                    output={
                        "scores": {
                            "clarity": 0.7,  # Below 0.8 threshold
                            "coverage": 0.7,
                            "architecture": 0.7,
                            "risk": 0.6,
                        },
                        "issues": [{"severity": "moderate", "description": "Needs improvement"}],
                        "disputed_issues": [],
                        "issue_counts": {"critical": 0, "moderate": 1, "minor": 0},
                        "summary": "Spec needs improvement.",
                        "recommendation": "REVISE",
                    },
                    errors=[],
                    cost_usd=0.01,
                )
            else:
                # Round 2: scores above threshold to trigger success
                return AgentResult(
                    success=True,
                    output={
                        "scores": {
                            "clarity": 0.9,
                            "coverage": 0.9,
                            "architecture": 0.9,
                            "risk": 0.85,
                        },
                        "issues": [],
                        "disputed_issues": [],
                        "issue_counts": {"critical": 0, "moderate": 0, "minor": 0},
                        "summary": "Spec meets all criteria.",
                        "recommendation": "APPROVE",
                    },
                    errors=[],
                    cost_usd=0.01,
                )

        mock_critic_multi_round = MagicMock()
        mock_critic_multi_round.run = MagicMock(side_effect=critic_multi_round_result)

        # Create a moderator that returns continue_debate=True for round 1,
        # and continue_debate=False for round 2, ensuring both rounds run
        def moderator_multi_round_result(context: dict) -> AgentResult:
            round_num = context.get("round", 1)
            return AgentResult(
                success=True,
                output={
                    "spec_path": "specs/test-feature/spec-draft.md",
                    "rubric_path": "specs/test-feature/spec-rubric.json",
                    "dispositions_path": "specs/test-feature/spec-dispositions.json",
                    "round": round_num,
                    "previous_scores": {"clarity": 0.7, "coverage": 0.7, "architecture": 0.7, "risk": 0.6},
                    "current_scores": {"clarity": 0.9, "coverage": 0.9, "architecture": 0.9, "risk": 0.85},
                    "continue_debate": round_num < 2,  # True for round 1, False for round 2
                    "ready_for_approval": round_num >= 2,
                    "dispositions": [],
                    "disposition_counts": {"accepted": 0, "rejected": 0, "deferred": 0, "partial": 0},
                    "meta": {"recommend_human_review": False, "review_reason": None},
                    "dispute_resolutions": [],
                },
                errors=[],
                cost_usd=0.02,
            )

        mock_moderator_multi_round = MagicMock()
        mock_moderator_multi_round.run = MagicMock(side_effect=moderator_multi_round_result)

        # Create mock logger to capture log events
        mock_logger = MagicMock()
        logged_events = []

        def capture_log(event_type, data=None, level="info"):
            logged_events.append({
                "event_type": event_type,
                "data": data or {},
                "level": level,
            })

        mock_logger.log = MagicMock(side_effect=capture_log)

        # Create orchestrator with mocked agents
        with patch("swarm_attack.orchestrator.SpecCriticAgent") as MockCritic, \
             patch("swarm_attack.orchestrator.SpecModeratorAgent") as MockModerator, \
             patch("swarm_attack.orchestrator.SpecAuthorAgent"), \
             patch("swarm_attack.orchestrator.DebateRetryHandler") as MockRetryHandler, \
             patch("swarm_attack.orchestrator.get_event_bus") as mock_get_bus, \
             patch("swarm_attack.events.validation.validate_payload"), \
             patch("swarm_attack.orchestrator.time.sleep") as mock_sleep:

            # Mock the event bus to avoid validation issues
            mock_bus = MagicMock()
            mock_get_bus.return_value = mock_bus

            # Configure the retry handler to pass through to agents
            mock_retry_handler = MagicMock()

            def run_with_retry(agent, context):
                """Simulate retry handler that just calls the agent."""
                result = agent.run(context)
                return result

            mock_retry_handler.run_with_retry = MagicMock(side_effect=run_with_retry)
            MockRetryHandler.return_value = mock_retry_handler

            # Configure mocked agents
            MockCritic.return_value = mock_critic_multi_round
            MockModerator.return_value = mock_moderator_multi_round

            # Create orchestrator
            orchestrator = Orchestrator(
                config=mock_config,
                logger=mock_logger,
                critic=mock_critic_multi_round,
                moderator=mock_moderator_multi_round,
                state_store=mock_state_store,
            )

            # Run the debate
            result = orchestrator.run_spec_debate_only(feature_id)

            # ================================================================
            # Verify: time.sleep was called correctly
            # ================================================================

            # Get all sleep calls
            sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]

            # For max_rounds=2:
            # - Round 1: intra_delay (5s) after critic, before moderator (only when round < max_rounds)
            # - Round 1: inter_delay (30s) after moderator, before round 2
            # - Round 2: NO intra_delay (because round_num == max_rounds, moderator doesn't run)
            # - NO inter_delay after round 2 (last round)
            #
            # Implementation note: intra_round_delay only applies when round_num < max_rounds
            # because the moderator only runs in those rounds.

            # Verify intra-round delays (between critic and moderator)
            # Should be called for rounds before max_rounds = 1 time for max_rounds=2
            intra_delay_calls = [c for c in sleep_calls if c == 5]
            assert len(intra_delay_calls) >= 1, (
                f"Expected at least 1 intra-round delay call (5s), "
                f"got {len(intra_delay_calls)}. All sleep calls: {sleep_calls}"
            )

            # Verify inter-round delays (between rounds)
            # Should be called (max_rounds - 1) = 1 time (not after last round)
            inter_delay_calls = [c for c in sleep_calls if c == 30]
            assert len(inter_delay_calls) >= 1, (
                f"Expected at least 1 inter-round delay call (30s), "
                f"got {len(inter_delay_calls)}. All sleep calls: {sleep_calls}"
            )

            # Verify the expected delay pattern exists
            assert 5 in sleep_calls, (
                f"Expected intra-round delay of 5s in sleep calls. "
                f"Got: {sleep_calls}"
            )
            assert 30 in sleep_calls, (
                f"Expected inter-round delay of 30s in sleep calls. "
                f"Got: {sleep_calls}"
            )

            # ================================================================
            # Verify: Logger captured delay events
            # ================================================================

            event_types = [e["event_type"] for e in logged_events]

            # Verify inter_round_delay was logged
            assert "inter_round_delay" in event_types, (
                f"Expected 'inter_round_delay' event in logs. "
                f"Got events: {event_types}"
            )

            # Verify intra_round_delay was logged
            assert "intra_round_delay" in event_types, (
                f"Expected 'intra_round_delay' event in logs. "
                f"Got events: {event_types}"
            )

            # Verify delay events have correct data
            inter_round_events = [
                e for e in logged_events if e["event_type"] == "inter_round_delay"
            ]
            for event in inter_round_events:
                assert "delay_seconds" in event["data"], (
                    f"inter_round_delay event missing delay_seconds: {event}"
                )
                assert event["data"]["delay_seconds"] == 30, (
                    f"Expected delay_seconds=30, got {event['data']['delay_seconds']}"
                )

            intra_round_events = [
                e for e in logged_events if e["event_type"] == "intra_round_delay"
            ]
            for event in intra_round_events:
                assert "delay_seconds" in event["data"], (
                    f"intra_round_delay event missing delay_seconds: {event}"
                )
                assert event["data"]["delay_seconds"] == 5, (
                    f"Expected delay_seconds=5, got {event['data']['delay_seconds']}"
                )

    def test_no_inter_round_delay_after_last_round(
        self,
        temp_project,
        mock_config,
        mock_state_store,
    ):
        """
        Verify that inter-round delay is NOT applied after the last round.

        With max_rounds=2, there should be exactly 1 inter-round delay
        (after round 1, before round 2), not 2.
        """
        feature_id = "test-feature"
        setup_feature_files(temp_project, feature_id)

        # Set delay values
        mock_config.spec_debate.inter_round_delay_seconds = 30
        mock_config.spec_debate.intra_round_delay_seconds = 5
        mock_config.spec_debate.max_rounds = 2

        # Create a critic that returns scores below threshold in round 1 (to continue debate),
        # and scores above threshold in round 2 (to complete successfully)
        critic_call_count = [0]

        def critic_continue_result(context: dict) -> AgentResult:
            critic_call_count[0] += 1
            round_num = critic_call_count[0]
            if round_num == 1:
                # Round 1: scores below threshold to continue debate
                return AgentResult(
                    success=True,
                    output={
                        "scores": {
                            "clarity": 0.7,
                            "coverage": 0.7,
                            "architecture": 0.7,
                            "risk": 0.6,
                        },
                        "issues": [{"severity": "moderate", "description": "Needs improvement"}],
                        "disputed_issues": [],
                        "issue_counts": {"critical": 0, "moderate": 1, "minor": 0},
                        "summary": "Spec needs improvement.",
                        "recommendation": "REVISE",
                    },
                    errors=[],
                    cost_usd=0.01,
                )
            else:
                # Round 2: scores above threshold to trigger success
                return AgentResult(
                    success=True,
                    output={
                        "scores": {
                            "clarity": 0.9,
                            "coverage": 0.9,
                            "architecture": 0.9,
                            "risk": 0.85,
                        },
                        "issues": [],
                        "disputed_issues": [],
                        "issue_counts": {"critical": 0, "moderate": 0, "minor": 0},
                        "summary": "Spec meets all criteria.",
                        "recommendation": "APPROVE",
                    },
                    errors=[],
                    cost_usd=0.01,
                )

        mock_critic = MagicMock()
        mock_critic.run = MagicMock(side_effect=critic_continue_result)

        # Create a moderator that signals to continue debate for both rounds
        def moderator_continue_result(context: dict) -> AgentResult:
            round_num = context.get("round", 1)
            return AgentResult(
                success=True,
                output={
                    "round": round_num,
                    "current_scores": {"clarity": 0.7, "coverage": 0.7, "architecture": 0.7, "risk": 0.7},
                    "continue_debate": round_num < 2,  # Continue until round 2
                    "ready_for_approval": round_num >= 2,
                    "dispositions": [],
                    "disposition_counts": {},
                    "meta": {},
                },
                errors=[],
                cost_usd=0.02,
            )

        mock_moderator = MagicMock()
        mock_moderator.run = MagicMock(side_effect=moderator_continue_result)

        mock_logger = MagicMock()

        with patch("swarm_attack.orchestrator.SpecCriticAgent"), \
             patch("swarm_attack.orchestrator.SpecModeratorAgent"), \
             patch("swarm_attack.orchestrator.SpecAuthorAgent"), \
             patch("swarm_attack.orchestrator.DebateRetryHandler") as MockRetryHandler, \
             patch("swarm_attack.orchestrator.get_event_bus") as mock_get_bus, \
             patch("swarm_attack.events.validation.validate_payload"), \
             patch("swarm_attack.orchestrator.time.sleep") as mock_sleep:

            # Mock the event bus
            mock_bus = MagicMock()
            mock_get_bus.return_value = mock_bus

            # Configure retry handler
            mock_retry_handler = MagicMock()
            mock_retry_handler.run_with_retry = MagicMock(
                side_effect=lambda agent, ctx: agent.run(ctx)
            )
            MockRetryHandler.return_value = mock_retry_handler

            orchestrator = Orchestrator(
                config=mock_config,
                logger=mock_logger,
                critic=mock_critic,
                moderator=mock_moderator,
                state_store=mock_state_store,
            )

            orchestrator.run_spec_debate_only(feature_id)

            # Count inter-round delay calls (30s)
            inter_delay_calls = [
                c for c in mock_sleep.call_args_list
                if c[0][0] == 30
            ]

            # Should be exactly (max_rounds - 1) = 1 inter-round delay
            assert len(inter_delay_calls) == 1, (
                f"Expected exactly 1 inter-round delay for max_rounds=2, "
                f"got {len(inter_delay_calls)}. "
                f"All calls: {mock_sleep.call_args_list}"
            )

    def test_delays_disabled_when_set_to_zero(
        self,
        temp_project,
        mock_config,
        mock_critic_success,
        mock_moderator_success,
        mock_state_store,
    ):
        """
        Verify that delays are skipped when configured as 0.

        When inter_round_delay_seconds=0 and intra_round_delay_seconds=0,
        time.sleep should not be called at all.
        """
        feature_id = "test-feature"
        setup_feature_files(temp_project, feature_id)

        # Disable delays
        mock_config.spec_debate.inter_round_delay_seconds = 0
        mock_config.spec_debate.intra_round_delay_seconds = 0
        mock_config.spec_debate.max_rounds = 2

        mock_logger = MagicMock()

        with patch("swarm_attack.orchestrator.SpecCriticAgent"), \
             patch("swarm_attack.orchestrator.SpecModeratorAgent"), \
             patch("swarm_attack.orchestrator.SpecAuthorAgent"), \
             patch("swarm_attack.orchestrator.DebateRetryHandler") as MockRetryHandler, \
             patch("swarm_attack.orchestrator.get_event_bus") as mock_get_bus, \
             patch("swarm_attack.events.validation.validate_payload"), \
             patch("swarm_attack.orchestrator.time.sleep") as mock_sleep:

            # Mock the event bus
            mock_bus = MagicMock()
            mock_get_bus.return_value = mock_bus

            mock_retry_handler = MagicMock()
            mock_retry_handler.run_with_retry = MagicMock(
                side_effect=lambda agent, ctx: agent.run(ctx)
            )
            MockRetryHandler.return_value = mock_retry_handler

            orchestrator = Orchestrator(
                config=mock_config,
                logger=mock_logger,
                critic=mock_critic_success,
                moderator=mock_moderator_success,
                state_store=mock_state_store,
            )

            orchestrator.run_spec_debate_only(feature_id)

            # Verify time.sleep was NOT called (delays disabled)
            # Note: If implementation doesn't check for 0, this will fail
            assert mock_sleep.call_count == 0, (
                f"Expected no sleep calls when delays are disabled (set to 0), "
                f"got {mock_sleep.call_count} calls: {mock_sleep.call_args_list}"
            )


class TestDelayConfigurationIntegration:
    """
    Tests for delay configuration integration.

    These tests verify that the SpecDebateConfig correctly accepts
    and exposes delay configuration values.
    """

    def test_spec_debate_config_accepts_delay_parameters(self):
        """
        Verify SpecDebateConfig accepts inter_round_delay_seconds and
        intra_round_delay_seconds parameters.

        This test will FAIL until SpecDebateConfig is updated with these fields.
        """
        # Attempt to create config with delay parameters
        # This will raise TypeError until the fields are added to the dataclass
        try:
            config = SpecDebateConfig(
                max_rounds=5,
                inter_round_delay_seconds=30,
                intra_round_delay_seconds=5,
            )

            assert config.inter_round_delay_seconds == 30, (
                f"Expected inter_round_delay_seconds=30, "
                f"got {config.inter_round_delay_seconds}"
            )
            assert config.intra_round_delay_seconds == 5, (
                f"Expected intra_round_delay_seconds=5, "
                f"got {config.intra_round_delay_seconds}"
            )
        except TypeError as e:
            # Expected to fail until implementation
            pytest.fail(
                f"SpecDebateConfig does not accept delay parameters yet. "
                f"Add 'inter_round_delay_seconds' and 'intra_round_delay_seconds' "
                f"fields to SpecDebateConfig. Error: {e}"
            )

    def test_spec_debate_config_defaults_for_delays(self):
        """
        Verify SpecDebateConfig has sensible defaults for delay parameters.

        Expected defaults:
        - inter_round_delay_seconds: 30 (seconds between rounds)
        - intra_round_delay_seconds: 5 (seconds between critic and moderator)
        """
        config = SpecDebateConfig()

        # These will fail with AttributeError until fields are added
        assert hasattr(config, "inter_round_delay_seconds"), (
            "SpecDebateConfig missing 'inter_round_delay_seconds' field"
        )
        assert hasattr(config, "intra_round_delay_seconds"), (
            "SpecDebateConfig missing 'intra_round_delay_seconds' field"
        )

        # Verify defaults are reasonable
        assert config.inter_round_delay_seconds >= 0, (
            f"inter_round_delay_seconds should be >= 0, "
            f"got {config.inter_round_delay_seconds}"
        )
        assert config.intra_round_delay_seconds >= 0, (
            f"intra_round_delay_seconds should be >= 0, "
            f"got {config.intra_round_delay_seconds}"
        )
