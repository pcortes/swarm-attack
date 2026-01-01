"""
Event payload validation for the swarm-attack event system.

Provides schema-based validation for event payloads to prevent injection attacks
and ensure data integrity. Each EventType has a defined set of allowed fields.

Issue 9: Add Event Payload Schema Validation (P0 Security)
"""

from typing import Set

from swarm_attack.events.types import EventType, SwarmEvent


# Schema defining allowed payload fields per event type
# Any field not in this set will be rejected
ALLOWED_FIELDS: dict[EventType, Set[str]] = {
    # Spec lifecycle
    EventType.SPEC_DRAFT_CREATED: {"author", "path", "prd_path"},
    EventType.SPEC_REVIEW_COMPLETE: {"round", "score", "critic_feedback"},
    EventType.SPEC_APPROVED: {"score", "rounds_taken", "final_path"},
    EventType.SPEC_REJECTED: {"score", "reason", "rounds_taken"},

    # Issue lifecycle
    EventType.ISSUE_CREATED: {"issue_count", "output_path", "github_issue_id"},
    EventType.ISSUE_VALIDATED: {"issue_number", "validation_result", "errors"},
    EventType.ISSUE_COMPLEXITY_PASSED: {"issue_number", "complexity_score", "max_turns"},
    EventType.ISSUE_COMPLEXITY_FAILED: {"issue_number", "complexity_score", "split_suggestions"},
    EventType.ISSUE_READY: {"issue_number", "assigned_to"},
    EventType.ISSUE_COMPLETE: {"issue_number", "commit_sha", "files_changed"},

    # Implementation lifecycle
    EventType.IMPL_STARTED: {"issue_number", "agent_id"},
    EventType.IMPL_TESTS_WRITTEN: {"issue_number", "test_count", "test_path"},
    EventType.IMPL_CODE_COMPLETE: {"issue_number", "files_created", "files_modified"},
    EventType.IMPL_VERIFIED: {"issue_number", "test_count", "coverage_percent"},
    EventType.IMPL_FAILED: {"issue_number", "error", "retry_count", "phase"},

    # Bug lifecycle
    EventType.BUG_DETECTED: {"bug_id", "description", "test_path", "error_message"},
    EventType.BUG_REPRODUCED: {"bug_id", "reproduction_steps", "test_output"},
    EventType.BUG_ANALYZED: {"bug_id", "root_cause", "confidence", "affected_files"},
    EventType.BUG_PLANNED: {"bug_id", "fix_plan_path", "estimated_effort"},
    EventType.BUG_APPROVED: {"bug_id", "approver", "approval_mode"},
    EventType.BUG_FIXED: {"bug_id", "commit_sha", "files_changed"},
    EventType.BUG_BLOCKED: {"bug_id", "reason", "blocked_since"},

    # System events
    EventType.SYSTEM_PHASE_TRANSITION: {"from", "to", "trigger"},
    EventType.SYSTEM_ERROR: {"error_type", "message", "stacktrace", "recoverable"},
    EventType.SYSTEM_RECOVERY: {"recovery_type", "from_state", "to_state", "action_taken"},

    # Auto-approval events
    EventType.AUTO_APPROVAL_TRIGGERED: {"approval_type", "reason", "threshold_used", "score"},
    EventType.AUTO_APPROVAL_BLOCKED: {"approval_type", "reason", "blocking_condition"},
    EventType.MANUAL_OVERRIDE: {"override_type", "user", "reason", "previous_decision"},
}


def validate_payload(event: SwarmEvent) -> bool:
    """
    Validate event payload against schema.

    Checks that all fields in the event's payload are in the allowed set
    for that event type. This prevents injection of arbitrary data.

    Args:
        event: The SwarmEvent to validate.

    Returns:
        True if validation passes.

    Raises:
        ValueError: If payload contains disallowed fields, with the field names included.
    """
    allowed = ALLOWED_FIELDS.get(event.event_type, set())
    actual = set(event.payload.keys())
    invalid = actual - allowed

    if invalid:
        raise ValueError(f"Invalid payload field(s): {invalid}")

    return True
