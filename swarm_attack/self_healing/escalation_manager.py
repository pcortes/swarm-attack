"""
EscalationManager - Human-in-loop escalation with context preservation.

This module provides:
- Clear escalation triggers (defined thresholds)
- Context handoff (what was attempted, why it failed)
- Priority classification (P0-P3)
- Resumption support (continue after human intervention)
"""

import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Priority(Enum):
    """Priority levels for escalation tickets.

    P0 - Critical: Data loss risk, security violations (immediate attention)
    P1 - High: System errors, authentication failures (within 1 hour)
    P2 - Medium: Persistent failures, connection issues (within 4 hours)
    P3 - Low: Minor issues, warnings (within 24 hours)
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class EscalationTrigger(Enum):
    """Reasons for triggering an escalation."""

    MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    DATA_LOSS_RISK = "data_loss_risk"
    CRITICAL_ERROR = "critical_error"
    MANUAL = "manual"


# Critical error types that always trigger immediate escalation
CRITICAL_ERROR_TYPES = frozenset([
    "DataIntegrityError",
    "SecurityViolation",
    "AuthenticationError",
    "SystemCrash",
])

# Error types that map to P1 priority
SYSTEM_ERROR_TYPES = frozenset([
    "SystemError",
    "OSError",
    "IOError",
    "MemoryError",
])


@dataclass
class FailureContext:
    """Context information about a failure.

    Attributes:
        error_message: The error message from the failure.
        error_type: The type/class of the error.
        component: The component that failed.
        attempts: Number of retry attempts made.
        max_attempts: Maximum allowed retry attempts.
        elapsed_seconds: Time elapsed since first attempt.
        is_data_loss_risk: Whether this failure risks data loss.
        related_files: Files related to this failure.
        stack_trace: Full stack trace if available.
    """

    error_message: str
    error_type: str
    component: str
    attempts: int = 0
    max_attempts: int = 3
    elapsed_seconds: float = 0.0
    is_data_loss_risk: bool = False
    related_files: List[str] = field(default_factory=list)
    stack_trace: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureContext":
        """Deserialize from dictionary."""
        return cls(
            error_message=data.get("error_message", ""),
            error_type=data.get("error_type", ""),
            component=data.get("component", ""),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
            is_data_loss_risk=data.get("is_data_loss_risk", False),
            related_files=data.get("related_files", []),
            stack_trace=data.get("stack_trace"),
        )


@dataclass
class EscalationContext:
    """Context for creating an escalation ticket.

    Attributes:
        failure_context: The underlying failure context.
        attempted_fixes: List of fixes that were attempted.
        failure_reason: Why escalation is needed.
        session_id: Optional session identifier.
        feature_id: Optional feature identifier.
        issue_number: Optional issue number.
    """

    failure_context: FailureContext
    attempted_fixes: List[str]
    failure_reason: str
    session_id: Optional[str] = None
    feature_id: Optional[str] = None
    issue_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "failure_context": self.failure_context.to_dict(),
            "attempted_fixes": self.attempted_fixes,
            "failure_reason": self.failure_reason,
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
        }


@dataclass
class EscalationTicket:
    """A ticket representing an escalation to human operators.

    Attributes:
        ticket_id: Unique identifier for the ticket.
        priority: Priority level (P0-P3).
        title: Short descriptive title.
        description: Full description of the issue.
        context_summary: Summary of the context for handoff.
        created_at: ISO timestamp of creation.
        status: Current status (open, resumed, closed).
        session_state: Preserved session state for resumption.
    """

    ticket_id: str
    priority: Priority
    title: str
    description: str
    context_summary: str
    created_at: str = ""
    status: str = "open"
    session_state: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set creation timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "ticket_id": self.ticket_id,
            "priority": self.priority.value if isinstance(self.priority, Priority) else self.priority,
            "title": self.title,
            "description": self.description,
            "context_summary": self.context_summary,
            "created_at": self.created_at,
            "status": self.status,
            "session_state": self.session_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EscalationTicket":
        """Deserialize from dictionary."""
        priority_value = data.get("priority", "P3")
        priority = Priority(priority_value) if isinstance(priority_value, str) else priority_value

        return cls(
            ticket_id=data.get("ticket_id", ""),
            priority=priority,
            title=data.get("title", ""),
            description=data.get("description", ""),
            context_summary=data.get("context_summary", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", "open"),
            session_state=data.get("session_state", {}),
        )


@dataclass
class ResumeResult:
    """Result of resuming from an escalation.

    Attributes:
        success: Whether resume was successful.
        ticket_id: ID of the ticket that was resumed.
        human_guidance: Guidance provided by human operator.
        resume_context: Context for resuming execution.
        error: Error message if resume failed.
    """

    success: bool
    ticket_id: str
    human_guidance: str = ""
    resume_context: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


class EscalationManager:
    """Manager for human-in-loop escalations with context preservation.

    Provides:
    - Configurable escalation triggers
    - Priority classification (P0-P3)
    - Context handoff for human operators
    - Resume support after human intervention
    - Escalation history tracking
    """

    # Default configuration
    DEFAULT_TIMEOUT_THRESHOLD = 300.0  # 5 minutes
    DEFAULT_MAX_ATTEMPTS_MULTIPLIER = 1.0

    def __init__(
        self,
        timeout_threshold_seconds: float = DEFAULT_TIMEOUT_THRESHOLD,
        max_attempts_multiplier: float = DEFAULT_MAX_ATTEMPTS_MULTIPLIER,
        storage_dir: Optional[Path] = None,
    ):
        """Initialize EscalationManager.

        Args:
            timeout_threshold_seconds: Seconds after which to trigger escalation.
            max_attempts_multiplier: Multiplier for max_attempts before escalation.
            storage_dir: Optional directory for persisting escalation data.
        """
        self.timeout_threshold_seconds = timeout_threshold_seconds
        self.max_attempts_multiplier = max_attempts_multiplier
        self.storage_dir = Path(storage_dir) if storage_dir else None

        # Thread-safe ticket storage
        self._lock = threading.RLock()
        self._tickets: Dict[str, EscalationTicket] = {}
        self._ticket_counter = 0

    def should_escalate(self, failure_context: FailureContext) -> bool:
        """Determine if human escalation is needed.

        Escalation is triggered when:
        - Data loss risk is detected
        - Critical error types are encountered
        - Max attempts exceeded (with multiplier)
        - Timeout threshold exceeded

        Args:
            failure_context: Context about the failure.

        Returns:
            True if escalation should be triggered.
        """
        # Immediate escalation on data loss risk
        if failure_context.is_data_loss_risk:
            return True

        # Immediate escalation on critical error types
        if failure_context.error_type in CRITICAL_ERROR_TYPES:
            return True

        # Check if max attempts exceeded
        effective_max = failure_context.max_attempts * self.max_attempts_multiplier
        if failure_context.attempts > effective_max:
            return True

        # Check if timeout exceeded
        if failure_context.elapsed_seconds > self.timeout_threshold_seconds:
            return True

        return False

    def get_trigger_reason(self, failure_context: FailureContext) -> Optional[EscalationTrigger]:
        """Get the reason for triggering escalation.

        Args:
            failure_context: Context about the failure.

        Returns:
            The trigger reason, or None if no trigger applies.
        """
        if failure_context.is_data_loss_risk:
            return EscalationTrigger.DATA_LOSS_RISK

        if failure_context.error_type in CRITICAL_ERROR_TYPES:
            return EscalationTrigger.CRITICAL_ERROR

        effective_max = failure_context.max_attempts * self.max_attempts_multiplier
        if failure_context.attempts > effective_max:
            return EscalationTrigger.MAX_ATTEMPTS_EXCEEDED

        if failure_context.elapsed_seconds > self.timeout_threshold_seconds:
            return EscalationTrigger.TIMEOUT_EXCEEDED

        return None

    def _classify_priority(self, context: EscalationContext) -> Priority:
        """Classify the priority level for an escalation.

        Args:
            context: The escalation context.

        Returns:
            Priority level (P0-P3).
        """
        fc = context.failure_context

        # P0: Critical - data loss or security
        if fc.is_data_loss_risk:
            return Priority.P0
        if fc.error_type in ("SecurityViolation", "AuthenticationError"):
            return Priority.P0

        # P1: High - system errors
        if fc.error_type in SYSTEM_ERROR_TYPES:
            return Priority.P1
        if fc.error_type in CRITICAL_ERROR_TYPES:
            return Priority.P1

        # P2: Medium - persistent failures
        if fc.attempts >= 3:
            return Priority.P2
        if "Error" in fc.error_type and fc.attempts >= 2:
            return Priority.P2

        # P3: Low - minor issues
        return Priority.P3

    def _generate_ticket_id(self) -> str:
        """Generate a unique ticket ID."""
        with self._lock:
            self._ticket_counter += 1
            unique_part = uuid4().hex[:8]
            return f"ESC-{self._ticket_counter:04d}-{unique_part}"

    def _build_title(self, context: EscalationContext) -> str:
        """Build a descriptive title for the ticket."""
        fc = context.failure_context
        title = f"[{fc.error_type}] {fc.component}: {fc.error_message}"
        # Truncate to reasonable length
        if len(title) > 200:
            title = title[:197] + "..."
        return title

    def _build_description(self, context: EscalationContext) -> str:
        """Build full description for the ticket."""
        fc = context.failure_context
        parts = [
            f"## Error Details",
            f"- **Error Type:** {fc.error_type}",
            f"- **Component:** {fc.component}",
            f"- **Message:** {fc.error_message}",
            "",
            f"## Failure Reason",
            context.failure_reason,
            "",
            f"## Attempts",
            f"- Attempts made: {fc.attempts}",
            f"- Max attempts: {fc.max_attempts}",
            f"- Time elapsed: {fc.elapsed_seconds:.1f}s",
        ]

        if context.attempted_fixes:
            parts.extend([
                "",
                "## Attempted Fixes",
            ])
            for fix in context.attempted_fixes:
                parts.append(f"- {fix}")

        if fc.stack_trace:
            parts.extend([
                "",
                "## Stack Trace",
                "```",
                fc.stack_trace[:2000],  # Truncate very long traces
                "```",
            ])

        return "\n".join(parts)

    def _build_context_summary(self, context: EscalationContext) -> str:
        """Build a summary of context for handoff."""
        parts = []

        if context.session_id:
            parts.append(f"Session: {context.session_id}")
        if context.feature_id:
            parts.append(f"Feature: {context.feature_id}")
        if context.issue_number:
            parts.append(f"Issue: #{context.issue_number}")

        fc = context.failure_context
        parts.append(f"Component: {fc.component}")
        parts.append(f"Error: {fc.error_type}")

        if context.attempted_fixes:
            parts.append(f"Fixes tried: {', '.join(context.attempted_fixes)}")

        return " | ".join(parts) if parts else "No context available"

    def _build_session_state(self, context: EscalationContext) -> Dict[str, Any]:
        """Build session state for later resumption."""
        fc = context.failure_context
        return {
            "session_id": context.session_id,
            "feature_id": context.feature_id,
            "issue_number": context.issue_number,
            "error_type": fc.error_type,
            "component": fc.component,
            "attempts": fc.attempts,
            "related_files": fc.related_files,
            "stack_trace": fc.stack_trace,
            "attempted_fixes": context.attempted_fixes,
        }

    def escalate(
        self,
        context: EscalationContext,
        override_priority: Optional[Priority] = None,
    ) -> EscalationTicket:
        """Create escalation ticket with full context.

        Args:
            context: The escalation context.
            override_priority: Optional priority override.

        Returns:
            The created escalation ticket.
        """
        with self._lock:
            # Determine priority
            priority = override_priority or self._classify_priority(context)

            # Generate ticket
            ticket = EscalationTicket(
                ticket_id=self._generate_ticket_id(),
                priority=priority,
                title=self._build_title(context),
                description=self._build_description(context),
                context_summary=self._build_context_summary(context),
                session_state=self._build_session_state(context),
            )

            # Store ticket
            self._tickets[ticket.ticket_id] = ticket

            return ticket

    def resume(
        self,
        ticket_id: str,
        human_guidance: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> ResumeResult:
        """Resume execution after human intervention.

        Args:
            ticket_id: ID of the ticket to resume.
            human_guidance: Guidance provided by human operator.
            additional_context: Additional context from human.

        Returns:
            Result of the resume operation.
        """
        with self._lock:
            ticket = self._tickets.get(ticket_id)

            if ticket is None:
                return ResumeResult(
                    success=False,
                    ticket_id=ticket_id,
                    error="Ticket not found",
                )

            if ticket.status == "closed":
                return ResumeResult(
                    success=False,
                    ticket_id=ticket_id,
                    error="Cannot resume a closed ticket",
                )

            # Update ticket status
            ticket.status = "resumed"

            # Build resume context
            resume_context = dict(ticket.session_state)
            if additional_context:
                resume_context.update(additional_context)

            return ResumeResult(
                success=True,
                ticket_id=ticket_id,
                human_guidance=human_guidance,
                resume_context=resume_context,
            )

    def get_ticket(self, ticket_id: str) -> Optional[EscalationTicket]:
        """Get a ticket by ID.

        Args:
            ticket_id: The ticket ID.

        Returns:
            The ticket if found, None otherwise.
        """
        with self._lock:
            return self._tickets.get(ticket_id)

    def close_ticket(self, ticket_id: str) -> bool:
        """Close a ticket.

        Args:
            ticket_id: The ticket ID.

        Returns:
            True if ticket was closed, False if not found.
        """
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket:
                ticket.status = "closed"
                return True
            return False

    def get_history(
        self,
        priority: Optional[Priority] = None,
        status: Optional[str] = None,
        feature_id: Optional[str] = None,
    ) -> List[EscalationTicket]:
        """Get escalation history with optional filters.

        Args:
            priority: Filter by priority level.
            status: Filter by status.
            feature_id: Filter by feature ID.

        Returns:
            List of tickets matching filters, ordered by creation time (newest first).
        """
        with self._lock:
            tickets = list(self._tickets.values())

            # Apply filters
            if priority is not None:
                tickets = [t for t in tickets if t.priority == priority]

            if status is not None:
                tickets = [t for t in tickets if t.status == status]

            if feature_id is not None:
                tickets = [
                    t for t in tickets
                    if t.session_state.get("feature_id") == feature_id
                ]

            # Sort by creation time (newest first)
            tickets.sort(key=lambda t: t.created_at, reverse=True)

            return tickets

    def save(self) -> None:
        """Persist escalation data to storage.

        Raises:
            ValueError: If storage_dir is not configured.
        """
        if not self.storage_dir:
            return

        with self._lock:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "tickets": {
                    tid: ticket.to_dict()
                    for tid, ticket in self._tickets.items()
                },
                "ticket_counter": self._ticket_counter,
            }

            path = self.storage_dir / "escalations.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load escalation data from storage.

        Does nothing if storage_dir is not configured or file doesn't exist.
        """
        if not self.storage_dir:
            return

        path = self.storage_dir / "escalations.json"
        if not path.exists():
            return

        with self._lock:
            try:
                with open(path) as f:
                    data = json.load(f)

                self._tickets = {
                    tid: EscalationTicket.from_dict(tdata)
                    for tid, tdata in data.get("tickets", {}).items()
                }
                self._ticket_counter = data.get("ticket_counter", 0)
            except (json.JSONDecodeError, KeyError):
                # Handle corrupted files gracefully
                pass
