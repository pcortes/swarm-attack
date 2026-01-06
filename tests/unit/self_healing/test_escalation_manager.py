"""
Tests for EscalationManager - Human-in-loop escalation with context preservation.

Tests cover:
- Escalation trigger thresholds (when to escalate)
- Priority classification (P0-P3)
- Context handoff completeness
- Ticket creation with all required fields
- Resume functionality after human intervention
- Escalation history tracking
"""

import pytest
from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock, patch

from swarm_attack.self_healing.escalation_manager import (
    EscalationManager,
    FailureContext,
    EscalationContext,
    EscalationTicket,
    Priority,
    ResumeResult,
    EscalationTrigger,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def escalation_manager():
    """Create an EscalationManager instance for testing."""
    return EscalationManager()


@pytest.fixture
def simple_failure_context():
    """Create a simple failure context for testing."""
    return FailureContext(
        error_message="Connection timeout",
        error_type="TimeoutError",
        component="api_client",
        attempts=1,
        max_attempts=3,
        elapsed_seconds=30.0,
    )


@pytest.fixture
def critical_failure_context():
    """Create a critical failure context that should trigger escalation."""
    return FailureContext(
        error_message="Database corruption detected",
        error_type="DataIntegrityError",
        component="database",
        attempts=5,
        max_attempts=3,
        elapsed_seconds=600.0,
        is_data_loss_risk=True,
    )


@pytest.fixture
def escalation_context(simple_failure_context):
    """Create an escalation context for testing."""
    return EscalationContext(
        failure_context=simple_failure_context,
        attempted_fixes=["retry_connection", "reset_client"],
        failure_reason="All retry attempts exhausted",
        session_id="session-123",
        feature_id="feature-abc",
        issue_number=42,
    )


# =============================================================================
# Test FailureContext
# =============================================================================


class TestFailureContext:
    """Tests for FailureContext dataclass."""

    def test_create_failure_context_with_required_fields(self):
        """Test creating a FailureContext with required fields."""
        ctx = FailureContext(
            error_message="Something went wrong",
            error_type="RuntimeError",
            component="orchestrator",
        )
        assert ctx.error_message == "Something went wrong"
        assert ctx.error_type == "RuntimeError"
        assert ctx.component == "orchestrator"

    def test_failure_context_defaults(self):
        """Test FailureContext default values."""
        ctx = FailureContext(
            error_message="Error",
            error_type="Error",
            component="test",
        )
        assert ctx.attempts == 0
        assert ctx.max_attempts == 3
        assert ctx.elapsed_seconds == 0.0
        assert ctx.is_data_loss_risk is False
        assert ctx.related_files == []
        assert ctx.stack_trace is None

    def test_failure_context_with_all_fields(self):
        """Test FailureContext with all fields populated."""
        ctx = FailureContext(
            error_message="Full error",
            error_type="FullError",
            component="full_component",
            attempts=2,
            max_attempts=5,
            elapsed_seconds=120.5,
            is_data_loss_risk=True,
            related_files=["file1.py", "file2.py"],
            stack_trace="Traceback...",
        )
        assert ctx.attempts == 2
        assert ctx.max_attempts == 5
        assert ctx.elapsed_seconds == 120.5
        assert ctx.is_data_loss_risk is True
        assert ctx.related_files == ["file1.py", "file2.py"]
        assert ctx.stack_trace == "Traceback..."

    def test_failure_context_to_dict(self):
        """Test serializing FailureContext to dictionary."""
        ctx = FailureContext(
            error_message="Test error",
            error_type="TestError",
            component="test_comp",
            attempts=1,
        )
        d = ctx.to_dict()
        assert d["error_message"] == "Test error"
        assert d["error_type"] == "TestError"
        assert d["component"] == "test_comp"
        assert d["attempts"] == 1

    def test_failure_context_from_dict(self):
        """Test deserializing FailureContext from dictionary."""
        data = {
            "error_message": "Loaded error",
            "error_type": "LoadedError",
            "component": "loader",
            "attempts": 3,
            "max_attempts": 5,
        }
        ctx = FailureContext.from_dict(data)
        assert ctx.error_message == "Loaded error"
        assert ctx.error_type == "LoadedError"
        assert ctx.component == "loader"
        assert ctx.attempts == 3


# =============================================================================
# Test Priority Enum
# =============================================================================


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_values(self):
        """Test that all priority levels are defined."""
        assert Priority.P0.value == "P0"
        assert Priority.P1.value == "P1"
        assert Priority.P2.value == "P2"
        assert Priority.P3.value == "P3"

    def test_priority_ordering(self):
        """Test that priorities can be compared for ordering."""
        # P0 is highest priority (most urgent)
        assert Priority.P0.value < Priority.P1.value
        assert Priority.P1.value < Priority.P2.value
        assert Priority.P2.value < Priority.P3.value

    def test_priority_from_string(self):
        """Test creating Priority from string."""
        assert Priority("P0") == Priority.P0
        assert Priority("P1") == Priority.P1
        assert Priority("P2") == Priority.P2
        assert Priority("P3") == Priority.P3


# =============================================================================
# Test EscalationContext
# =============================================================================


class TestEscalationContext:
    """Tests for EscalationContext dataclass."""

    def test_create_escalation_context(self, simple_failure_context):
        """Test creating an EscalationContext."""
        ctx = EscalationContext(
            failure_context=simple_failure_context,
            attempted_fixes=["fix1", "fix2"],
            failure_reason="Could not recover",
        )
        assert ctx.failure_context == simple_failure_context
        assert ctx.attempted_fixes == ["fix1", "fix2"]
        assert ctx.failure_reason == "Could not recover"

    def test_escalation_context_optional_fields(self, simple_failure_context):
        """Test EscalationContext optional fields."""
        ctx = EscalationContext(
            failure_context=simple_failure_context,
            attempted_fixes=[],
            failure_reason="Unknown",
            session_id="sess-1",
            feature_id="feat-1",
            issue_number=10,
        )
        assert ctx.session_id == "sess-1"
        assert ctx.feature_id == "feat-1"
        assert ctx.issue_number == 10

    def test_escalation_context_to_dict(self, simple_failure_context):
        """Test serializing EscalationContext to dictionary."""
        ctx = EscalationContext(
            failure_context=simple_failure_context,
            attempted_fixes=["fix1"],
            failure_reason="Failed",
            session_id="s1",
        )
        d = ctx.to_dict()
        assert "failure_context" in d
        assert d["attempted_fixes"] == ["fix1"]
        assert d["failure_reason"] == "Failed"
        assert d["session_id"] == "s1"


# =============================================================================
# Test EscalationTicket
# =============================================================================


class TestEscalationTicket:
    """Tests for EscalationTicket dataclass."""

    def test_create_escalation_ticket(self):
        """Test creating an EscalationTicket."""
        ticket = EscalationTicket(
            ticket_id="ESC-001",
            priority=Priority.P1,
            title="API Connection Failure",
            description="Connection to API failed after 3 retries",
            context_summary="Session was processing feature X",
        )
        assert ticket.ticket_id == "ESC-001"
        assert ticket.priority == Priority.P1
        assert ticket.title == "API Connection Failure"

    def test_escalation_ticket_has_timestamp(self):
        """Test that EscalationTicket has a created_at timestamp."""
        ticket = EscalationTicket(
            ticket_id="ESC-002",
            priority=Priority.P2,
            title="Test",
            description="Desc",
            context_summary="Summary",
        )
        assert ticket.created_at is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(ticket.created_at)

    def test_escalation_ticket_status_default(self):
        """Test that EscalationTicket status defaults to 'open'."""
        ticket = EscalationTicket(
            ticket_id="ESC-003",
            priority=Priority.P3,
            title="Test",
            description="Desc",
            context_summary="Summary",
        )
        assert ticket.status == "open"

    def test_escalation_ticket_to_dict(self):
        """Test serializing EscalationTicket to dictionary."""
        ticket = EscalationTicket(
            ticket_id="ESC-004",
            priority=Priority.P0,
            title="Critical Issue",
            description="Full description",
            context_summary="Context",
            status="open",
        )
        d = ticket.to_dict()
        assert d["ticket_id"] == "ESC-004"
        assert d["priority"] == "P0"
        assert d["title"] == "Critical Issue"
        assert d["status"] == "open"

    def test_escalation_ticket_from_dict(self):
        """Test deserializing EscalationTicket from dictionary."""
        data = {
            "ticket_id": "ESC-005",
            "priority": "P1",
            "title": "Loaded Ticket",
            "description": "Loaded desc",
            "context_summary": "Loaded context",
            "created_at": "2025-01-01T12:00:00",
            "status": "in_progress",
        }
        ticket = EscalationTicket.from_dict(data)
        assert ticket.ticket_id == "ESC-005"
        assert ticket.priority == Priority.P1
        assert ticket.status == "in_progress"

    def test_escalation_ticket_has_session_state(self):
        """Test that ticket preserves session state for resumption."""
        ticket = EscalationTicket(
            ticket_id="ESC-006",
            priority=Priority.P1,
            title="Issue",
            description="Desc",
            context_summary="Context",
            session_state={"step": 3, "data": {"key": "value"}},
        )
        assert ticket.session_state == {"step": 3, "data": {"key": "value"}}


# =============================================================================
# Test ResumeResult
# =============================================================================


class TestResumeResult:
    """Tests for ResumeResult dataclass."""

    def test_create_resume_result_success(self):
        """Test creating a successful ResumeResult."""
        result = ResumeResult(
            success=True,
            ticket_id="ESC-001",
            human_guidance="Increase timeout to 60s",
            resume_context={"new_timeout": 60},
        )
        assert result.success is True
        assert result.ticket_id == "ESC-001"
        assert result.human_guidance == "Increase timeout to 60s"
        assert result.resume_context == {"new_timeout": 60}

    def test_create_resume_result_failure(self):
        """Test creating a failed ResumeResult."""
        result = ResumeResult(
            success=False,
            ticket_id="ESC-002",
            error="Ticket not found",
        )
        assert result.success is False
        assert result.error == "Ticket not found"

    def test_resume_result_to_dict(self):
        """Test serializing ResumeResult to dictionary."""
        result = ResumeResult(
            success=True,
            ticket_id="ESC-003",
            human_guidance="Retry with different params",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["ticket_id"] == "ESC-003"


# =============================================================================
# Test Escalation Triggers (should_escalate)
# =============================================================================


class TestEscalationTriggers:
    """Tests for escalation trigger thresholds."""

    def test_no_escalation_on_first_attempt(self, escalation_manager, simple_failure_context):
        """Test that first attempt doesn't trigger escalation."""
        simple_failure_context.attempts = 1
        simple_failure_context.max_attempts = 3
        result = escalation_manager.should_escalate(simple_failure_context)
        assert result is False

    def test_escalation_when_max_attempts_exceeded(self, escalation_manager, simple_failure_context):
        """Test escalation when max attempts are exceeded."""
        simple_failure_context.attempts = 4
        simple_failure_context.max_attempts = 3
        result = escalation_manager.should_escalate(simple_failure_context)
        assert result is True

    def test_escalation_on_data_loss_risk(self, escalation_manager, simple_failure_context):
        """Test immediate escalation on data loss risk."""
        simple_failure_context.is_data_loss_risk = True
        simple_failure_context.attempts = 1
        result = escalation_manager.should_escalate(simple_failure_context)
        assert result is True

    def test_escalation_on_timeout_threshold(self, escalation_manager, simple_failure_context):
        """Test escalation when elapsed time exceeds threshold."""
        simple_failure_context.elapsed_seconds = 400.0  # Over 5 min threshold
        result = escalation_manager.should_escalate(simple_failure_context)
        assert result is True

    def test_no_escalation_under_timeout_threshold(self, escalation_manager, simple_failure_context):
        """Test no escalation when elapsed time is under threshold."""
        simple_failure_context.elapsed_seconds = 100.0  # Under 5 min
        simple_failure_context.attempts = 1
        result = escalation_manager.should_escalate(simple_failure_context)
        assert result is False

    def test_escalation_on_critical_error_types(self, escalation_manager, simple_failure_context):
        """Test escalation on critical error types."""
        critical_types = [
            "DataIntegrityError",
            "SecurityViolation",
            "AuthenticationError",
            "SystemCrash",
        ]
        for error_type in critical_types:
            simple_failure_context.error_type = error_type
            simple_failure_context.attempts = 1
            result = escalation_manager.should_escalate(simple_failure_context)
            assert result is True, f"Expected escalation for {error_type}"

    def test_configurable_timeout_threshold(self):
        """Test that timeout threshold is configurable."""
        manager = EscalationManager(timeout_threshold_seconds=600.0)
        ctx = FailureContext(
            error_message="Error",
            error_type="Error",
            component="test",
            elapsed_seconds=400.0,  # Under 600s
        )
        assert manager.should_escalate(ctx) is False

        ctx.elapsed_seconds = 700.0  # Over 600s
        assert manager.should_escalate(ctx) is True

    def test_configurable_max_attempts_multiplier(self):
        """Test that max attempts multiplier is configurable."""
        manager = EscalationManager(max_attempts_multiplier=2.0)
        ctx = FailureContext(
            error_message="Error",
            error_type="Error",
            component="test",
            attempts=4,  # 4 > 3 but < 3 * 2
            max_attempts=3,
        )
        assert manager.should_escalate(ctx) is False

        ctx.attempts = 7  # 7 > 3 * 2
        assert manager.should_escalate(ctx) is True


# =============================================================================
# Test Priority Classification
# =============================================================================


class TestPriorityClassification:
    """Tests for priority classification (P0-P3)."""

    def test_p0_for_data_loss_risk(self, escalation_manager, escalation_context):
        """Test P0 priority for data loss risk."""
        escalation_context.failure_context.is_data_loss_risk = True
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P0

    def test_p0_for_security_violations(self, escalation_manager, escalation_context):
        """Test P0 priority for security violations."""
        escalation_context.failure_context.error_type = "SecurityViolation"
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P0

    def test_p1_for_system_errors(self, escalation_manager, escalation_context):
        """Test P1 priority for system-level errors."""
        escalation_context.failure_context.error_type = "SystemError"
        escalation_context.failure_context.is_data_loss_risk = False
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P1

    def test_p2_for_persistent_failures(self, escalation_manager, escalation_context):
        """Test P2 priority for persistent but non-critical failures."""
        escalation_context.failure_context.error_type = "ConnectionError"
        escalation_context.failure_context.attempts = 5
        escalation_context.failure_context.is_data_loss_risk = False
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P2

    def test_p3_for_minor_issues(self, escalation_manager, escalation_context):
        """Test P3 priority for minor/warning issues."""
        escalation_context.failure_context.error_type = "WarningError"
        escalation_context.failure_context.is_data_loss_risk = False
        escalation_context.failure_context.attempts = 1
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P3

    def test_priority_can_be_overridden(self, escalation_manager, escalation_context):
        """Test that priority can be explicitly overridden."""
        ticket = escalation_manager.escalate(
            escalation_context,
            override_priority=Priority.P0,
        )
        assert ticket.priority == Priority.P0


# =============================================================================
# Test Context Handoff
# =============================================================================


class TestContextHandoff:
    """Tests for context handoff completeness."""

    def test_ticket_includes_error_details(self, escalation_manager, escalation_context):
        """Test that ticket includes error details."""
        ticket = escalation_manager.escalate(escalation_context)
        assert escalation_context.failure_context.error_message in ticket.description
        assert escalation_context.failure_context.error_type in ticket.description

    def test_ticket_includes_attempted_fixes(self, escalation_manager, escalation_context):
        """Test that ticket includes attempted fixes."""
        escalation_context.attempted_fixes = ["fix1", "fix2", "fix3"]
        ticket = escalation_manager.escalate(escalation_context)
        assert "fix1" in ticket.description or "fix1" in ticket.context_summary
        assert "fix2" in ticket.description or "fix2" in ticket.context_summary

    def test_ticket_includes_session_context(self, escalation_manager, escalation_context):
        """Test that ticket includes session context."""
        escalation_context.session_id = "session-abc"
        escalation_context.feature_id = "feature-xyz"
        escalation_context.issue_number = 123
        ticket = escalation_manager.escalate(escalation_context)
        assert "session-abc" in ticket.context_summary or ticket.session_state.get("session_id") == "session-abc"
        assert "feature-xyz" in ticket.context_summary or ticket.session_state.get("feature_id") == "feature-xyz"

    def test_ticket_includes_stack_trace(self, escalation_manager, escalation_context):
        """Test that ticket includes stack trace when available."""
        escalation_context.failure_context.stack_trace = "Traceback (most recent call last):\n  File..."
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.session_state.get("stack_trace") or "Traceback" in ticket.description

    def test_ticket_includes_related_files(self, escalation_manager, escalation_context):
        """Test that ticket includes related files."""
        escalation_context.failure_context.related_files = ["src/module.py", "tests/test_module.py"]
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.session_state.get("related_files") or "module.py" in str(ticket)


# =============================================================================
# Test Ticket Creation
# =============================================================================


class TestTicketCreation:
    """Tests for ticket creation with all required fields."""

    def test_ticket_has_unique_id(self, escalation_manager, escalation_context):
        """Test that each ticket has a unique ID."""
        ticket1 = escalation_manager.escalate(escalation_context)
        ticket2 = escalation_manager.escalate(escalation_context)
        assert ticket1.ticket_id != ticket2.ticket_id

    def test_ticket_id_format(self, escalation_manager, escalation_context):
        """Test that ticket ID follows expected format."""
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.ticket_id.startswith("ESC-")

    def test_ticket_has_title(self, escalation_manager, escalation_context):
        """Test that ticket has a descriptive title."""
        ticket = escalation_manager.escalate(escalation_context)
        assert len(ticket.title) > 0
        assert escalation_context.failure_context.component in ticket.title or \
               escalation_context.failure_context.error_type in ticket.title

    def test_ticket_has_description(self, escalation_manager, escalation_context):
        """Test that ticket has a full description."""
        ticket = escalation_manager.escalate(escalation_context)
        assert len(ticket.description) > 0
        assert escalation_context.failure_reason in ticket.description

    def test_ticket_has_context_summary(self, escalation_manager, escalation_context):
        """Test that ticket has a context summary."""
        ticket = escalation_manager.escalate(escalation_context)
        assert len(ticket.context_summary) > 0

    def test_ticket_preserves_session_state(self, escalation_manager, escalation_context):
        """Test that ticket preserves session state for resumption."""
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.session_state is not None
        assert isinstance(ticket.session_state, dict)


# =============================================================================
# Test Resume Functionality
# =============================================================================


class TestResumeFunctionality:
    """Tests for resume functionality after human intervention."""

    def test_resume_with_valid_ticket(self, escalation_manager, escalation_context):
        """Test resuming with a valid ticket ID."""
        ticket = escalation_manager.escalate(escalation_context)
        result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Increase connection timeout",
        )
        assert result.success is True
        assert result.ticket_id == ticket.ticket_id
        assert result.human_guidance == "Increase connection timeout"

    def test_resume_with_invalid_ticket(self, escalation_manager):
        """Test resuming with an invalid ticket ID."""
        result = escalation_manager.resume(
            ticket_id="ESC-NONEXISTENT",
            human_guidance="Some guidance",
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_resume_updates_ticket_status(self, escalation_manager, escalation_context):
        """Test that resume updates ticket status."""
        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.status == "open"

        escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Fix applied",
        )

        updated_ticket = escalation_manager.get_ticket(ticket.ticket_id)
        assert updated_ticket.status == "resumed"

    def test_resume_preserves_context(self, escalation_manager, escalation_context):
        """Test that resume result includes original context."""
        escalation_context.session_id = "sess-preserve"
        ticket = escalation_manager.escalate(escalation_context)

        result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Continue with modified params",
        )

        assert result.resume_context is not None
        assert result.resume_context.get("session_id") == "sess-preserve" or \
               "sess-preserve" in str(result.resume_context)

    def test_resume_adds_guidance_to_context(self, escalation_manager, escalation_context):
        """Test that human guidance is added to resume context."""
        ticket = escalation_manager.escalate(escalation_context)
        result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Use backup server instead",
        )

        assert result.human_guidance == "Use backup server instead"
        assert "backup server" in result.human_guidance

    def test_resume_with_additional_context(self, escalation_manager, escalation_context):
        """Test resume with additional context from human."""
        ticket = escalation_manager.escalate(escalation_context)
        result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Apply fix X",
            additional_context={"new_config": {"timeout": 120}},
        )

        assert result.success is True
        assert result.resume_context.get("new_config") == {"timeout": 120}


# =============================================================================
# Test Escalation History
# =============================================================================


class TestEscalationHistory:
    """Tests for escalation history tracking."""

    def test_history_stores_all_escalations(self, escalation_manager, escalation_context):
        """Test that history stores all escalations."""
        ticket1 = escalation_manager.escalate(escalation_context)
        ticket2 = escalation_manager.escalate(escalation_context)
        ticket3 = escalation_manager.escalate(escalation_context)

        history = escalation_manager.get_history()
        assert len(history) == 3
        assert ticket1.ticket_id in [t.ticket_id for t in history]
        assert ticket2.ticket_id in [t.ticket_id for t in history]
        assert ticket3.ticket_id in [t.ticket_id for t in history]

    def test_history_filter_by_priority(self, escalation_manager, escalation_context):
        """Test filtering history by priority."""
        # Create P0 ticket
        escalation_context.failure_context.is_data_loss_risk = True
        ticket_p0 = escalation_manager.escalate(escalation_context)

        # Create P2 ticket
        escalation_context.failure_context.is_data_loss_risk = False
        escalation_context.failure_context.error_type = "ConnectionError"
        ticket_p2 = escalation_manager.escalate(escalation_context)

        p0_history = escalation_manager.get_history(priority=Priority.P0)
        assert ticket_p0.ticket_id in [t.ticket_id for t in p0_history]
        assert ticket_p2.ticket_id not in [t.ticket_id for t in p0_history]

    def test_history_filter_by_status(self, escalation_manager, escalation_context):
        """Test filtering history by status."""
        ticket1 = escalation_manager.escalate(escalation_context)
        ticket2 = escalation_manager.escalate(escalation_context)

        # Resume one ticket
        escalation_manager.resume(ticket1.ticket_id, "Fixed")

        open_tickets = escalation_manager.get_history(status="open")
        resumed_tickets = escalation_manager.get_history(status="resumed")

        assert ticket2.ticket_id in [t.ticket_id for t in open_tickets]
        assert ticket1.ticket_id in [t.ticket_id for t in resumed_tickets]

    def test_history_filter_by_feature(self, escalation_manager, escalation_context):
        """Test filtering history by feature ID."""
        escalation_context.feature_id = "feature-alpha"
        ticket1 = escalation_manager.escalate(escalation_context)

        escalation_context.feature_id = "feature-beta"
        ticket2 = escalation_manager.escalate(escalation_context)

        alpha_history = escalation_manager.get_history(feature_id="feature-alpha")
        assert ticket1.ticket_id in [t.ticket_id for t in alpha_history]
        assert ticket2.ticket_id not in [t.ticket_id for t in alpha_history]

    def test_get_ticket_by_id(self, escalation_manager, escalation_context):
        """Test retrieving a specific ticket by ID."""
        ticket = escalation_manager.escalate(escalation_context)
        retrieved = escalation_manager.get_ticket(ticket.ticket_id)
        assert retrieved is not None
        assert retrieved.ticket_id == ticket.ticket_id
        assert retrieved.priority == ticket.priority

    def test_get_nonexistent_ticket(self, escalation_manager):
        """Test retrieving a non-existent ticket."""
        retrieved = escalation_manager.get_ticket("ESC-NOTFOUND")
        assert retrieved is None

    def test_history_ordered_by_creation_time(self, escalation_manager, escalation_context):
        """Test that history is ordered by creation time."""
        import time

        tickets = []
        for _ in range(3):
            ticket = escalation_manager.escalate(escalation_context)
            tickets.append(ticket)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        history = escalation_manager.get_history()
        # Most recent first
        assert history[0].ticket_id == tickets[-1].ticket_id

    def test_history_persistence(self, tmp_path, escalation_context):
        """Test that history can be persisted and loaded."""
        storage_path = tmp_path / "escalations"
        manager1 = EscalationManager(storage_dir=storage_path)
        ticket = manager1.escalate(escalation_context)
        manager1.save()

        # Create new manager and load
        manager2 = EscalationManager(storage_dir=storage_path)
        manager2.load()

        history = manager2.get_history()
        assert len(history) >= 1
        assert ticket.ticket_id in [t.ticket_id for t in history]


# =============================================================================
# Test EscalationTrigger Enum
# =============================================================================


class TestEscalationTrigger:
    """Tests for EscalationTrigger enum."""

    def test_trigger_values(self):
        """Test that all trigger types are defined."""
        assert EscalationTrigger.MAX_ATTEMPTS_EXCEEDED is not None
        assert EscalationTrigger.TIMEOUT_EXCEEDED is not None
        assert EscalationTrigger.DATA_LOSS_RISK is not None
        assert EscalationTrigger.CRITICAL_ERROR is not None
        assert EscalationTrigger.MANUAL is not None

    def test_get_trigger_reason(self, escalation_manager, simple_failure_context):
        """Test getting the trigger reason for an escalation."""
        # Max attempts exceeded
        simple_failure_context.attempts = 5
        simple_failure_context.max_attempts = 3
        trigger = escalation_manager.get_trigger_reason(simple_failure_context)
        assert trigger == EscalationTrigger.MAX_ATTEMPTS_EXCEEDED

    def test_get_trigger_data_loss(self, escalation_manager, simple_failure_context):
        """Test trigger reason for data loss risk."""
        simple_failure_context.is_data_loss_risk = True
        trigger = escalation_manager.get_trigger_reason(simple_failure_context)
        assert trigger == EscalationTrigger.DATA_LOSS_RISK

    def test_get_trigger_timeout(self, escalation_manager, simple_failure_context):
        """Test trigger reason for timeout."""
        simple_failure_context.elapsed_seconds = 500.0
        trigger = escalation_manager.get_trigger_reason(simple_failure_context)
        assert trigger == EscalationTrigger.TIMEOUT_EXCEEDED

    def test_get_trigger_critical_error(self, escalation_manager, simple_failure_context):
        """Test trigger reason for critical error type."""
        simple_failure_context.error_type = "SecurityViolation"
        trigger = escalation_manager.get_trigger_reason(simple_failure_context)
        assert trigger == EscalationTrigger.CRITICAL_ERROR


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_escalate_with_empty_attempted_fixes(self, escalation_manager, simple_failure_context):
        """Test escalation with no attempted fixes."""
        ctx = EscalationContext(
            failure_context=simple_failure_context,
            attempted_fixes=[],
            failure_reason="No fixes attempted",
        )
        ticket = escalation_manager.escalate(ctx)
        assert ticket is not None
        assert "No fixes attempted" in ticket.description

    def test_escalate_with_long_error_message(self, escalation_manager, simple_failure_context):
        """Test escalation with very long error message."""
        simple_failure_context.error_message = "Error: " + "x" * 10000
        ctx = EscalationContext(
            failure_context=simple_failure_context,
            attempted_fixes=["fix"],
            failure_reason="Long error",
        )
        ticket = escalation_manager.escalate(ctx)
        assert ticket is not None
        # Title should be truncated appropriately
        assert len(ticket.title) <= 200

    def test_resume_already_resolved_ticket(self, escalation_manager, escalation_context):
        """Test resuming an already resolved ticket."""
        ticket = escalation_manager.escalate(escalation_context)
        escalation_manager.resume(ticket.ticket_id, "First resolution")
        escalation_manager.close_ticket(ticket.ticket_id)

        result = escalation_manager.resume(ticket.ticket_id, "Second attempt")
        assert result.success is False
        assert "closed" in result.error.lower() or "resolved" in result.error.lower()

    def test_close_ticket(self, escalation_manager, escalation_context):
        """Test closing a ticket."""
        ticket = escalation_manager.escalate(escalation_context)
        escalation_manager.close_ticket(ticket.ticket_id)

        updated = escalation_manager.get_ticket(ticket.ticket_id)
        assert updated.status == "closed"

    def test_thread_safety(self, escalation_manager, escalation_context):
        """Test thread safety of escalation manager."""
        import threading
        import time

        tickets = []
        errors = []

        def create_ticket():
            try:
                ticket = escalation_manager.escalate(escalation_context)
                tickets.append(ticket)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_ticket) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(tickets) == 10
        # All ticket IDs should be unique
        ticket_ids = [t.ticket_id for t in tickets]
        assert len(set(ticket_ids)) == 10
