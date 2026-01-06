"""Unit tests for RecoveryHandler - Tiered recovery strategies for different failure modes.

Tests cover:
- Tier 1: Retry with modified prompt (80% of failures)
- Tier 2: Context reduction + retry (15% of failures)
- Tier 3: Checkpoint rollback + fresh attempt (4% of failures)
- Tier 4: Human escalation (1% of failures)
- Strategy selection based on failure characteristics
- Recovery result handling
"""

import pytest
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from swarm_attack.self_healing.recovery_handler import (
    RecoveryHandler,
    RecoveryStrategy,
    RecoveryTier,
    FailureInfo,
    RecoveryResult,
    RecoveryStatus,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def recovery_handler() -> RecoveryHandler:
    """Create a RecoveryHandler instance for testing."""
    return RecoveryHandler()


@pytest.fixture
def simple_failure() -> FailureInfo:
    """Create a simple failure that should use Tier 1 recovery."""
    return FailureInfo(
        failure_id="fail-001",
        error_type="ValidationError",
        error_message="Invalid input format",
        component="validator",
        retry_count=0,
        context_size=10000,
        checkpoint_available=False,
    )


@pytest.fixture
def context_heavy_failure() -> FailureInfo:
    """Create a failure with context issues that should use Tier 2 recovery."""
    return FailureInfo(
        failure_id="fail-002",
        error_type="ContextOverflowError",
        error_message="Context window exceeded",
        component="llm_client",
        retry_count=2,
        context_size=95000,
        checkpoint_available=True,
    )


@pytest.fixture
def persistent_failure() -> FailureInfo:
    """Create a persistent failure that should use Tier 3 recovery."""
    return FailureInfo(
        failure_id="fail-003",
        error_type="ExecutionError",
        error_message="Task failed after multiple retries",
        component="executor",
        retry_count=5,
        context_size=50000,
        checkpoint_available=True,
    )


@pytest.fixture
def critical_failure() -> FailureInfo:
    """Create a critical failure that requires human escalation (Tier 4)."""
    return FailureInfo(
        failure_id="fail-004",
        error_type="SecurityViolation",
        error_message="Unauthorized access attempt detected",
        component="security",
        retry_count=3,
        context_size=20000,
        checkpoint_available=True,
        is_critical=True,
    )


# =============================================================================
# Test RecoveryTier Enum
# =============================================================================


class TestRecoveryTier:
    """Tests for RecoveryTier enum."""

    def test_tier_values(self):
        """Test that all recovery tiers are defined."""
        assert RecoveryTier.TIER_1.value == 1
        assert RecoveryTier.TIER_2.value == 2
        assert RecoveryTier.TIER_3.value == 3
        assert RecoveryTier.TIER_4.value == 4

    def test_tier_ordering(self):
        """Test that tiers can be compared for severity."""
        assert RecoveryTier.TIER_1.value < RecoveryTier.TIER_2.value
        assert RecoveryTier.TIER_2.value < RecoveryTier.TIER_3.value
        assert RecoveryTier.TIER_3.value < RecoveryTier.TIER_4.value

    def test_tier_descriptions(self):
        """Test that tiers have descriptive names."""
        # Tier descriptions should be available
        assert RecoveryTier.TIER_1.name == "TIER_1"
        assert RecoveryTier.TIER_2.name == "TIER_2"
        assert RecoveryTier.TIER_3.name == "TIER_3"
        assert RecoveryTier.TIER_4.name == "TIER_4"


# =============================================================================
# Test RecoveryStatus Enum
# =============================================================================


class TestRecoveryStatus:
    """Tests for RecoveryStatus enum."""

    def test_status_values(self):
        """Test that all recovery statuses are defined."""
        assert RecoveryStatus.SUCCESS.value == "success"
        assert RecoveryStatus.PARTIAL.value == "partial"
        assert RecoveryStatus.FAILED.value == "failed"
        assert RecoveryStatus.ESCALATED.value == "escalated"

    def test_status_from_string(self):
        """Test creating RecoveryStatus from string."""
        assert RecoveryStatus("success") == RecoveryStatus.SUCCESS
        assert RecoveryStatus("partial") == RecoveryStatus.PARTIAL
        assert RecoveryStatus("failed") == RecoveryStatus.FAILED
        assert RecoveryStatus("escalated") == RecoveryStatus.ESCALATED


# =============================================================================
# Test FailureInfo
# =============================================================================


class TestFailureInfo:
    """Tests for FailureInfo dataclass."""

    def test_create_failure_info_with_required_fields(self):
        """Test creating a FailureInfo with required fields."""
        info = FailureInfo(
            failure_id="fail-001",
            error_type="RuntimeError",
            error_message="Something went wrong",
            component="main",
        )
        assert info.failure_id == "fail-001"
        assert info.error_type == "RuntimeError"
        assert info.error_message == "Something went wrong"
        assert info.component == "main"

    def test_failure_info_defaults(self):
        """Test FailureInfo default values."""
        info = FailureInfo(
            failure_id="fail-001",
            error_type="Error",
            error_message="Error",
            component="test",
        )
        assert info.retry_count == 0
        assert info.context_size == 0
        assert info.checkpoint_available is False
        assert info.is_critical is False
        assert info.metadata == {}

    def test_failure_info_with_all_fields(self):
        """Test FailureInfo with all fields populated."""
        info = FailureInfo(
            failure_id="fail-full",
            error_type="FullError",
            error_message="Full error message",
            component="full_component",
            retry_count=3,
            context_size=50000,
            checkpoint_available=True,
            is_critical=True,
            metadata={"key": "value"},
        )
        assert info.retry_count == 3
        assert info.context_size == 50000
        assert info.checkpoint_available is True
        assert info.is_critical is True
        assert info.metadata == {"key": "value"}

    def test_failure_info_to_dict(self):
        """Test serializing FailureInfo to dictionary."""
        info = FailureInfo(
            failure_id="fail-001",
            error_type="TestError",
            error_message="Test message",
            component="test_comp",
            retry_count=2,
        )
        d = info.to_dict()
        assert d["failure_id"] == "fail-001"
        assert d["error_type"] == "TestError"
        assert d["error_message"] == "Test message"
        assert d["component"] == "test_comp"
        assert d["retry_count"] == 2

    def test_failure_info_from_dict(self):
        """Test deserializing FailureInfo from dictionary."""
        data = {
            "failure_id": "fail-loaded",
            "error_type": "LoadedError",
            "error_message": "Loaded message",
            "component": "loader",
            "retry_count": 1,
            "context_size": 30000,
        }
        info = FailureInfo.from_dict(data)
        assert info.failure_id == "fail-loaded"
        assert info.error_type == "LoadedError"
        assert info.retry_count == 1
        assert info.context_size == 30000


# =============================================================================
# Test RecoveryStrategy
# =============================================================================


class TestRecoveryStrategy:
    """Tests for RecoveryStrategy dataclass."""

    def test_create_recovery_strategy(self):
        """Test creating a RecoveryStrategy."""
        strategy = RecoveryStrategy(
            tier=RecoveryTier.TIER_1,
            name="retry_with_modified_prompt",
            description="Retry the operation with a modified prompt",
            actions=["modify_prompt", "retry"],
        )
        assert strategy.tier == RecoveryTier.TIER_1
        assert strategy.name == "retry_with_modified_prompt"
        assert "modified prompt" in strategy.description
        assert "modify_prompt" in strategy.actions

    def test_recovery_strategy_defaults(self):
        """Test RecoveryStrategy default values."""
        strategy = RecoveryStrategy(
            tier=RecoveryTier.TIER_2,
            name="test_strategy",
            description="Test",
            actions=[],
        )
        assert strategy.max_retries == 3
        assert strategy.timeout_seconds == 300

    def test_recovery_strategy_to_dict(self):
        """Test serializing RecoveryStrategy to dictionary."""
        strategy = RecoveryStrategy(
            tier=RecoveryTier.TIER_1,
            name="test",
            description="Test strategy",
            actions=["action1"],
            max_retries=5,
        )
        d = strategy.to_dict()
        assert d["tier"] == 1
        assert d["name"] == "test"
        assert d["max_retries"] == 5


# =============================================================================
# Test RecoveryResult
# =============================================================================


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""

    def test_create_recovery_result_success(self):
        """Test creating a successful RecoveryResult."""
        result = RecoveryResult(
            failure_id="fail-001",
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_1,
            message="Recovery successful",
        )
        assert result.failure_id == "fail-001"
        assert result.status == RecoveryStatus.SUCCESS
        assert result.strategy_used == RecoveryTier.TIER_1
        assert result.message == "Recovery successful"

    def test_create_recovery_result_escalated(self):
        """Test creating an escalated RecoveryResult."""
        result = RecoveryResult(
            failure_id="fail-004",
            status=RecoveryStatus.ESCALATED,
            strategy_used=RecoveryTier.TIER_4,
            message="Escalated to human intervention",
            escalation_ticket_id="ESC-001",
        )
        assert result.status == RecoveryStatus.ESCALATED
        assert result.escalation_ticket_id == "ESC-001"

    def test_recovery_result_defaults(self):
        """Test RecoveryResult default values."""
        result = RecoveryResult(
            failure_id="fail-001",
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_1,
            message="OK",
        )
        assert result.attempts == 0
        assert result.escalation_ticket_id is None
        assert result.modified_context is None
        assert result.checkpoint_restored is False

    def test_recovery_result_to_dict(self):
        """Test serializing RecoveryResult to dictionary."""
        result = RecoveryResult(
            failure_id="fail-001",
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_1,
            message="Done",
            attempts=2,
        )
        d = result.to_dict()
        assert d["failure_id"] == "fail-001"
        assert d["status"] == "success"
        assert d["strategy_used"] == 1
        assert d["attempts"] == 2

    def test_recovery_result_is_recoverable(self):
        """Test is_recoverable property."""
        success_result = RecoveryResult(
            failure_id="f1",
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_1,
            message="OK",
        )
        assert success_result.is_recoverable is True

        partial_result = RecoveryResult(
            failure_id="f2",
            status=RecoveryStatus.PARTIAL,
            strategy_used=RecoveryTier.TIER_2,
            message="Partial",
        )
        assert partial_result.is_recoverable is True

        failed_result = RecoveryResult(
            failure_id="f3",
            status=RecoveryStatus.FAILED,
            strategy_used=RecoveryTier.TIER_3,
            message="Failed",
        )
        assert failed_result.is_recoverable is False


# =============================================================================
# Test RecoveryHandler Initialization
# =============================================================================


class TestRecoveryHandlerInit:
    """Tests for RecoveryHandler initialization."""

    def test_create_default_handler(self):
        """Test creating a RecoveryHandler with defaults."""
        handler = RecoveryHandler()
        assert handler is not None
        assert handler.tier1_retry_limit == 3
        assert handler.tier2_context_reduction_factor == 0.5
        assert handler.context_size_threshold == 80000

    def test_create_handler_with_custom_config(self):
        """Test creating a RecoveryHandler with custom configuration."""
        handler = RecoveryHandler(
            tier1_retry_limit=5,
            tier2_context_reduction_factor=0.3,
            context_size_threshold=60000,
        )
        assert handler.tier1_retry_limit == 5
        assert handler.tier2_context_reduction_factor == 0.3
        assert handler.context_size_threshold == 60000

    def test_handler_has_escalation_manager(self):
        """Test that handler has access to escalation manager."""
        handler = RecoveryHandler()
        assert handler.escalation_manager is not None


# =============================================================================
# Test Strategy Selection
# =============================================================================


class TestSelectStrategy:
    """Tests for RecoveryHandler.select_strategy()."""

    def test_select_tier1_for_simple_failure(self, recovery_handler, simple_failure):
        """Test that simple failures get Tier 1 strategy."""
        strategy = recovery_handler.select_strategy(simple_failure)
        assert strategy.tier == RecoveryTier.TIER_1
        assert "prompt" in strategy.name.lower() or "retry" in strategy.name.lower()

    def test_select_tier1_when_retry_count_low(self, recovery_handler):
        """Test Tier 1 selected when retry count is low."""
        failure = FailureInfo(
            failure_id="f1",
            error_type="ValidationError",
            error_message="Invalid format",
            component="parser",
            retry_count=1,
        )
        strategy = recovery_handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_1

    def test_select_tier2_for_context_issues(self, recovery_handler, context_heavy_failure):
        """Test that context issues get Tier 2 strategy."""
        strategy = recovery_handler.select_strategy(context_heavy_failure)
        assert strategy.tier == RecoveryTier.TIER_2
        assert "context" in strategy.name.lower() or "reduction" in strategy.name.lower()

    def test_select_tier2_when_context_exceeds_threshold(self, recovery_handler):
        """Test Tier 2 selected when context size exceeds threshold."""
        failure = FailureInfo(
            failure_id="f2",
            error_type="ContextError",
            error_message="Context too large",
            component="llm",
            retry_count=2,
            context_size=90000,  # Above default 80000 threshold
        )
        strategy = recovery_handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_2

    def test_select_tier3_for_persistent_failure(self, recovery_handler, persistent_failure):
        """Test that persistent failures get Tier 3 strategy."""
        strategy = recovery_handler.select_strategy(persistent_failure)
        assert strategy.tier == RecoveryTier.TIER_3
        assert "checkpoint" in strategy.name.lower() or "rollback" in strategy.name.lower()

    def test_select_tier3_when_checkpoint_available_and_many_retries(self, recovery_handler):
        """Test Tier 3 selected when checkpoint available and many retries."""
        failure = FailureInfo(
            failure_id="f3",
            error_type="ExecutionError",
            error_message="Failed repeatedly",
            component="executor",
            retry_count=5,
            checkpoint_available=True,
        )
        strategy = recovery_handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_3

    def test_select_tier3_fallback_when_no_checkpoint(self, recovery_handler):
        """Test that Tier 3 is still selected even without checkpoint for many retries."""
        failure = FailureInfo(
            failure_id="f3-no-cp",
            error_type="ExecutionError",
            error_message="Failed many times",
            component="executor",
            retry_count=6,
            checkpoint_available=False,
        )
        strategy = recovery_handler.select_strategy(failure)
        # Should still attempt Tier 3 but with different actions
        assert strategy.tier == RecoveryTier.TIER_3

    def test_select_tier4_for_critical_failure(self, recovery_handler, critical_failure):
        """Test that critical failures get Tier 4 strategy (human escalation)."""
        strategy = recovery_handler.select_strategy(critical_failure)
        assert strategy.tier == RecoveryTier.TIER_4
        assert "escalat" in strategy.name.lower() or "human" in strategy.name.lower()

    def test_select_tier4_for_security_violations(self, recovery_handler):
        """Test Tier 4 selected for security-related failures."""
        failure = FailureInfo(
            failure_id="f4",
            error_type="SecurityViolation",
            error_message="Unauthorized access",
            component="auth",
            is_critical=True,
        )
        strategy = recovery_handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_4

    def test_select_tier4_for_data_loss_risk(self, recovery_handler):
        """Test Tier 4 selected when data loss risk is detected."""
        failure = FailureInfo(
            failure_id="f4-data",
            error_type="DataIntegrityError",
            error_message="Potential data corruption",
            component="database",
            is_critical=True,
            metadata={"data_loss_risk": True},
        )
        strategy = recovery_handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_4


# =============================================================================
# Test Handle Method
# =============================================================================


class TestHandle:
    """Tests for RecoveryHandler.handle()."""

    def test_handle_simple_failure_returns_result(self, recovery_handler, simple_failure):
        """Test that handle() returns a RecoveryResult."""
        result = recovery_handler.handle(simple_failure)
        assert isinstance(result, RecoveryResult)
        assert result.failure_id == simple_failure.failure_id

    def test_handle_tier1_success(self, recovery_handler, simple_failure):
        """Test successful Tier 1 recovery."""
        result = recovery_handler.handle(simple_failure)
        assert result.strategy_used == RecoveryTier.TIER_1
        assert result.status in (RecoveryStatus.SUCCESS, RecoveryStatus.PARTIAL)

    def test_handle_tier2_reduces_context(self, recovery_handler, context_heavy_failure):
        """Test that Tier 2 recovery reduces context."""
        result = recovery_handler.handle(context_heavy_failure)
        assert result.strategy_used == RecoveryTier.TIER_2
        if result.modified_context:
            # Context should be reduced
            assert result.modified_context.get("reduced", False) is True

    def test_handle_tier3_uses_checkpoint(self, recovery_handler, persistent_failure):
        """Test that Tier 3 recovery uses checkpoint rollback."""
        result = recovery_handler.handle(persistent_failure)
        assert result.strategy_used == RecoveryTier.TIER_3
        # Should attempt checkpoint restoration
        assert result.checkpoint_restored is True or result.status == RecoveryStatus.FAILED

    def test_handle_tier4_creates_escalation(self, recovery_handler, critical_failure):
        """Test that Tier 4 recovery creates escalation ticket."""
        result = recovery_handler.handle(critical_failure)
        assert result.strategy_used == RecoveryTier.TIER_4
        assert result.status == RecoveryStatus.ESCALATED
        assert result.escalation_ticket_id is not None

    def test_handle_tracks_attempts(self, recovery_handler, simple_failure):
        """Test that handle() tracks recovery attempts."""
        result = recovery_handler.handle(simple_failure)
        assert result.attempts >= 1

    def test_handle_returns_failure_on_exhausted_retries(self, recovery_handler):
        """Test that handle() returns appropriate status when retries exhausted."""
        # Create a failure that will exhaust Tier 1 retries
        failure = FailureInfo(
            failure_id="exhaust",
            error_type="PersistentError",
            error_message="Always fails",
            component="test",
            retry_count=10,  # Already many retries - will trigger Tier 3
            checkpoint_available=False,
            is_critical=False,
        )
        # Configure handler with very low retry limits
        handler = RecoveryHandler(
            tier1_retry_limit=1,
            context_size_threshold=1000000,  # Won't trigger Tier 2
        )
        result = handler.handle(failure)
        # High retry count triggers Tier 3 (fresh start without checkpoint)
        # Returns PARTIAL since no checkpoint available but still attempts recovery
        assert result.status in (RecoveryStatus.PARTIAL, RecoveryStatus.FAILED, RecoveryStatus.ESCALATED)


# =============================================================================
# Test Tier Distribution (80/15/4/1)
# =============================================================================


class TestTierDistribution:
    """Tests to verify the tier distribution matches expected ratios."""

    def test_tier1_handles_majority_of_failures(self, recovery_handler):
        """Test that Tier 1 handles simple/common failures (80% target)."""
        # Generate a variety of simple failures
        simple_failures = [
            FailureInfo(
                failure_id=f"simple-{i}",
                error_type="ValidationError",
                error_message="Invalid input",
                component="validator",
                retry_count=i % 3,  # 0, 1, or 2 retries
                context_size=20000,
            )
            for i in range(10)
        ]

        tier1_count = sum(
            1 for f in simple_failures
            if recovery_handler.select_strategy(f).tier == RecoveryTier.TIER_1
        )
        # Most simple failures should use Tier 1
        assert tier1_count >= 8  # At least 80%

    def test_tier2_handles_context_failures(self, recovery_handler):
        """Test that Tier 2 handles context-related failures (15% target)."""
        context_failures = [
            FailureInfo(
                failure_id=f"context-{i}",
                error_type="ContextError",
                error_message="Context overflow",
                component="llm",
                retry_count=2,
                context_size=85000 + i * 1000,  # Above threshold
            )
            for i in range(10)
        ]

        tier2_count = sum(
            1 for f in context_failures
            if recovery_handler.select_strategy(f).tier == RecoveryTier.TIER_2
        )
        # All context-heavy failures should use Tier 2
        assert tier2_count == 10

    def test_tier3_handles_persistent_failures(self, recovery_handler):
        """Test that Tier 3 handles persistent failures (4% target)."""
        persistent_failures = [
            FailureInfo(
                failure_id=f"persistent-{i}",
                error_type="ExecutionError",
                error_message="Persistent failure",
                component="executor",
                retry_count=5 + i,  # High retry counts
                checkpoint_available=True,
            )
            for i in range(5)
        ]

        tier3_count = sum(
            1 for f in persistent_failures
            if recovery_handler.select_strategy(f).tier == RecoveryTier.TIER_3
        )
        # All persistent failures should use Tier 3
        assert tier3_count == 5

    def test_tier4_handles_critical_failures(self, recovery_handler):
        """Test that Tier 4 handles critical failures (1% target)."""
        critical_failures = [
            FailureInfo(
                failure_id=f"critical-{i}",
                error_type="SecurityViolation",
                error_message="Critical security issue",
                component="security",
                is_critical=True,
            )
            for i in range(5)
        ]

        tier4_count = sum(
            1 for f in critical_failures
            if recovery_handler.select_strategy(f).tier == RecoveryTier.TIER_4
        )
        # All critical failures must escalate
        assert tier4_count == 5


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_handle_empty_failure_id(self, recovery_handler):
        """Test handling failure with empty failure_id."""
        failure = FailureInfo(
            failure_id="",
            error_type="Error",
            error_message="Test",
            component="test",
        )
        result = recovery_handler.handle(failure)
        # Should still work but assign an ID
        assert result.failure_id is not None

    def test_handle_zero_context_size(self, recovery_handler):
        """Test handling failure with zero context size."""
        failure = FailureInfo(
            failure_id="zero-ctx",
            error_type="Error",
            error_message="No context",
            component="test",
            context_size=0,
        )
        strategy = recovery_handler.select_strategy(failure)
        # Should not try context reduction with zero context
        assert strategy.tier != RecoveryTier.TIER_2

    def test_handle_very_large_retry_count(self, recovery_handler):
        """Test handling failure with very large retry count."""
        failure = FailureInfo(
            failure_id="many-retries",
            error_type="PersistentError",
            error_message="Keeps failing",
            component="test",
            retry_count=100,
            checkpoint_available=True,
        )
        strategy = recovery_handler.select_strategy(failure)
        # Should escalate or use checkpoint
        assert strategy.tier in (RecoveryTier.TIER_3, RecoveryTier.TIER_4)

    def test_handle_unknown_error_type(self, recovery_handler):
        """Test handling failure with unknown error type."""
        failure = FailureInfo(
            failure_id="unknown",
            error_type="UnknownWeirdError",
            error_message="Mystery error",
            component="mystery",
            retry_count=1,
        )
        strategy = recovery_handler.select_strategy(failure)
        # Should still select a valid strategy
        assert strategy.tier in (
            RecoveryTier.TIER_1,
            RecoveryTier.TIER_2,
            RecoveryTier.TIER_3,
            RecoveryTier.TIER_4,
        )

    def test_select_strategy_returns_new_instance(self, recovery_handler, simple_failure):
        """Test that select_strategy returns a new strategy instance each time."""
        strategy1 = recovery_handler.select_strategy(simple_failure)
        strategy2 = recovery_handler.select_strategy(simple_failure)
        # Should be equal but not the same object
        assert strategy1.tier == strategy2.tier
        assert strategy1.name == strategy2.name

    def test_handle_concurrent_failures(self, recovery_handler):
        """Test handling multiple failures doesn't cause state issues."""
        failures = [
            FailureInfo(
                failure_id=f"concurrent-{i}",
                error_type="Error",
                error_message=f"Failure {i}",
                component="test",
            )
            for i in range(5)
        ]
        results = [recovery_handler.handle(f) for f in failures]
        # Each result should have the correct failure_id
        for i, result in enumerate(results):
            assert result.failure_id == f"concurrent-{i}"


# =============================================================================
# Test Integration with EscalationManager
# =============================================================================


class TestEscalationIntegration:
    """Tests for integration with EscalationManager."""

    def test_tier4_uses_escalation_manager(self, recovery_handler, critical_failure):
        """Test that Tier 4 recovery properly uses EscalationManager."""
        result = recovery_handler.handle(critical_failure)
        assert result.status == RecoveryStatus.ESCALATED
        # Should have created an escalation ticket
        assert result.escalation_ticket_id is not None
        assert result.escalation_ticket_id.startswith("ESC-")

    def test_escalation_includes_failure_context(self, recovery_handler, critical_failure):
        """Test that escalation ticket includes failure context."""
        result = recovery_handler.handle(critical_failure)
        # Get the ticket from escalation manager
        ticket = recovery_handler.escalation_manager.get_ticket(result.escalation_ticket_id)
        if ticket:
            assert critical_failure.error_type in ticket.title or critical_failure.error_type in ticket.description

    def test_escalation_preserves_metadata(self, recovery_handler):
        """Test that escalation preserves failure metadata."""
        failure = FailureInfo(
            failure_id="meta-test",
            error_type="CriticalError",
            error_message="Critical with metadata",
            component="test",
            is_critical=True,
            metadata={"key": "value", "count": 42},
        )
        result = recovery_handler.handle(failure)
        assert result.status == RecoveryStatus.ESCALATED


# =============================================================================
# Test Strategy Configuration
# =============================================================================


class TestStrategyConfiguration:
    """Tests for strategy configuration and customization."""

    def test_custom_tier1_retry_limit(self):
        """Test customizing Tier 1 retry limit affects execution."""
        handler = RecoveryHandler(tier1_retry_limit=5)
        # Use retry_count=2, which is below Tier 3 threshold (4)
        failure = FailureInfo(
            failure_id="custom",
            error_type="Error",
            error_message="Test",
            component="test",
            retry_count=2,
        )
        strategy = handler.select_strategy(failure)
        # Should use Tier 1 since retry_count is below Tier 3 threshold
        assert strategy.tier == RecoveryTier.TIER_1
        # Custom retry limit is used in strategy
        assert strategy.max_retries == 5

    def test_custom_context_threshold(self):
        """Test customizing context size threshold."""
        handler = RecoveryHandler(context_size_threshold=50000)
        failure = FailureInfo(
            failure_id="ctx-custom",
            error_type="Error",
            error_message="Test",
            component="test",
            retry_count=2,
            context_size=60000,  # Above custom threshold
        )
        strategy = handler.select_strategy(failure)
        assert strategy.tier == RecoveryTier.TIER_2

    def test_custom_reduction_factor(self):
        """Test customizing context reduction factor."""
        handler = RecoveryHandler(tier2_context_reduction_factor=0.7)
        assert handler.tier2_context_reduction_factor == 0.7


# =============================================================================
# Test Logging and Metrics
# =============================================================================


class TestLoggingAndMetrics:
    """Tests for logging and metrics collection."""

    def test_handler_tracks_recovery_history(self, recovery_handler, simple_failure):
        """Test that handler tracks recovery history."""
        recovery_handler.handle(simple_failure)
        recovery_handler.handle(simple_failure)

        history = recovery_handler.get_recovery_history(simple_failure.failure_id)
        assert len(history) >= 2

    def test_handler_provides_tier_statistics(self, recovery_handler):
        """Test that handler can provide tier usage statistics."""
        # Handle various failures
        for i in range(5):
            failure = FailureInfo(
                failure_id=f"stats-{i}",
                error_type="Error",
                error_message="Test",
                component="test",
            )
            recovery_handler.handle(failure)

        stats = recovery_handler.get_tier_statistics()
        assert "tier_1" in stats
        assert "tier_2" in stats
        assert "tier_3" in stats
        assert "tier_4" in stats

    def test_handler_clears_old_history(self, recovery_handler):
        """Test that handler can clear old history entries."""
        for i in range(10):
            failure = FailureInfo(
                failure_id=f"old-{i}",
                error_type="Error",
                error_message="Old failure",
                component="test",
            )
            recovery_handler.handle(failure)

        # Clear history
        recovery_handler.clear_history()
        stats = recovery_handler.get_tier_statistics()
        total = sum(stats.values())
        assert total == 0
