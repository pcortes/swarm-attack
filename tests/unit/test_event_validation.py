"""
Tests for event payload validation.

Issue 9: Add Event Payload Schema Validation (P0 Security)
Events accept arbitrary dict payloads without validation, creating injection risk.
Add schema validation per event type.

Acceptance Criteria:
- 9.1: ALLOWED_FIELDS defined per EventType
- 9.2: validate_payload() rejects unknown fields
- 9.3: EventBus.emit() validates before dispatch
- 9.4: Invalid payloads raise ValueError with field name
"""

import pytest

from swarm_attack.events.types import EventType, SwarmEvent
from swarm_attack.events.validation import ALLOWED_FIELDS, validate_payload


class TestAllowedFields:
    """Tests for ALLOWED_FIELDS schema (AC 9.1)."""

    def test_allowed_fields_is_dict(self):
        """ALLOWED_FIELDS should be a dict mapping EventType to set of fields."""
        assert isinstance(ALLOWED_FIELDS, dict)

    def test_all_event_types_have_schema(self):
        """Every EventType should have an entry in ALLOWED_FIELDS."""
        for event_type in EventType:
            assert event_type in ALLOWED_FIELDS, f"Missing schema for {event_type}"

    def test_allowed_fields_values_are_sets(self):
        """Each schema should be a set of field names."""
        for event_type, fields in ALLOWED_FIELDS.items():
            assert isinstance(fields, set), f"{event_type} schema is not a set"

    def test_issue_created_has_expected_fields(self):
        """ISSUE_CREATED should allow issue_count and output_path."""
        expected = {"issue_count", "output_path"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.ISSUE_CREATED])

    def test_impl_started_has_expected_fields(self):
        """IMPL_STARTED should allow issue_number."""
        expected = {"issue_number"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.IMPL_STARTED])

    def test_impl_verified_has_expected_fields(self):
        """IMPL_VERIFIED should allow issue_number and test_count."""
        expected = {"issue_number", "test_count"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.IMPL_VERIFIED])

    def test_impl_failed_has_expected_fields(self):
        """IMPL_FAILED should allow issue_number, error, and retry_count."""
        expected = {"issue_number", "error", "retry_count"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.IMPL_FAILED])

    def test_auto_approval_triggered_has_expected_fields(self):
        """AUTO_APPROVAL_TRIGGERED should allow approval_type, reason, threshold_used."""
        expected = {"approval_type", "reason", "threshold_used"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.AUTO_APPROVAL_TRIGGERED])

    def test_spec_approved_has_score_field(self):
        """SPEC_APPROVED should allow score field (used in bus.emit_spec_approved)."""
        assert "score" in ALLOWED_FIELDS[EventType.SPEC_APPROVED]

    def test_phase_transition_has_from_to_fields(self):
        """SYSTEM_PHASE_TRANSITION should allow from and to fields."""
        expected = {"from", "to"}
        assert expected.issubset(ALLOWED_FIELDS[EventType.SYSTEM_PHASE_TRANSITION])


class TestValidatePayload:
    """Tests for validate_payload() function (AC 9.2, 9.4)."""

    def test_valid_payload_returns_true(self):
        """Valid payload should return True."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"issue_count": 3, "output_path": "/tmp/issues.json"},
        )
        assert validate_payload(event) is True

    def test_empty_payload_returns_true(self):
        """Empty payload should be valid (all fields are optional)."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={},
        )
        assert validate_payload(event) is True

    def test_partial_payload_returns_true(self):
        """Partial payload with only some allowed fields should be valid."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"issue_count": 5},
        )
        assert validate_payload(event) is True

    def test_unknown_field_raises_value_error(self):
        """Unknown field in payload should raise ValueError (AC 9.4)."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"issue_count": 3, "malicious_code": "rm -rf /"},
        )
        with pytest.raises(ValueError) as exc_info:
            validate_payload(event)
        assert "malicious_code" in str(exc_info.value)

    def test_multiple_unknown_fields_lists_all(self):
        """Multiple unknown fields should all be mentioned in error."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={
                "issue_count": 3,
                "bad_field_1": "value1",
                "bad_field_2": "value2",
            },
        )
        with pytest.raises(ValueError) as exc_info:
            validate_payload(event)
        error_msg = str(exc_info.value)
        assert "bad_field_1" in error_msg or "bad_field_2" in error_msg

    def test_error_message_includes_invalid_prefix(self):
        """Error message should indicate invalid payload fields."""
        event = SwarmEvent(
            event_type=EventType.IMPL_STARTED,
            feature_id="test-feature",
            payload={"unknown_field": "value"},
        )
        with pytest.raises(ValueError) as exc_info:
            validate_payload(event)
        assert "Invalid payload field" in str(exc_info.value)

    def test_validation_for_each_event_type(self):
        """All event types should support empty payload validation."""
        for event_type in EventType:
            event = SwarmEvent(
                event_type=event_type,
                feature_id="test-feature",
                payload={},
            )
            # Should not raise - empty payloads are valid
            assert validate_payload(event) is True


class TestEventBusValidation:
    """Tests for EventBus.emit() payload validation integration (AC 9.3)."""

    def test_emit_validates_payload_before_dispatch(self):
        """EventBus.emit() should validate payload before calling handlers."""
        from swarm_attack.events.bus import EventBus

        bus = EventBus(persist=False)

        # Create event with invalid payload
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"issue_count": 3, "injected_field": "malicious"},
        )

        # emit() should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            bus.emit(event)
        assert "injected_field" in str(exc_info.value)

    def test_emit_allows_valid_payload(self):
        """EventBus.emit() should allow valid payloads through."""
        from swarm_attack.events.bus import EventBus

        bus = EventBus(persist=False)
        handler_called = []

        def handler(event):
            handler_called.append(event)

        bus.subscribe(EventType.ISSUE_CREATED, handler)

        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"issue_count": 3},
        )

        # Should not raise
        bus.emit(event)

        # Handler should have been called
        assert len(handler_called) == 1
        assert handler_called[0] == event

    def test_emit_spec_approved_with_valid_payload(self):
        """Convenience method emit_spec_approved should work with valid payload."""
        from swarm_attack.events.bus import EventBus

        bus = EventBus(persist=False)
        handler_called = []

        def handler(event):
            handler_called.append(event)

        bus.subscribe(EventType.SPEC_APPROVED, handler)

        # This should work - uses score which should be allowed
        event = bus.emit_spec_approved("test-feature", score=0.9)

        assert len(handler_called) == 1
        assert handler_called[0].payload == {"score": 0.9}

    def test_emit_phase_transition_with_valid_payload(self):
        """Convenience method emit_phase_transition should work with valid payload."""
        from swarm_attack.events.bus import EventBus

        bus = EventBus(persist=False)
        handler_called = []

        def handler(event):
            handler_called.append(event)

        bus.subscribe(EventType.SYSTEM_PHASE_TRANSITION, handler)

        # This should work - uses from/to which should be allowed
        event = bus.emit_phase_transition("test-feature", "READY", "COMPLETE")

        assert len(handler_called) == 1
        assert handler_called[0].payload == {"from": "READY", "to": "COMPLETE"}

    def test_validation_happens_before_persistence(self):
        """Invalid payload should not be persisted."""
        from unittest.mock import MagicMock

        from swarm_attack.events.bus import EventBus

        bus = EventBus(persist=False)
        bus._persistence = MagicMock()

        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"bad_field": "value"},
        )

        with pytest.raises(ValueError):
            bus.emit(event)

        # Persistence should NOT have been called
        bus._persistence.append.assert_not_called()


class TestSecurityScenarios:
    """Tests for security-related validation scenarios."""

    def test_injection_attempt_blocked(self):
        """Injection attempts in payload should be blocked."""
        event = SwarmEvent(
            event_type=EventType.SYSTEM_ERROR,
            feature_id="test-feature",
            payload={"__class__": "attack", "__dict__": {}},
        )
        with pytest.raises(ValueError):
            validate_payload(event)

    def test_deeply_nested_payload_not_allowed_if_not_in_schema(self):
        """Fields not in schema should be rejected even with nested values."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            payload={"nested": {"deeply": {"nested": "value"}}},
        )
        with pytest.raises(ValueError) as exc_info:
            validate_payload(event)
        assert "nested" in str(exc_info.value)

    def test_code_execution_attempt_blocked(self):
        """Attempts to inject executable code should be blocked."""
        event = SwarmEvent(
            event_type=EventType.IMPL_STARTED,
            feature_id="test-feature",
            payload={"exec": "import os; os.system('rm -rf /')"},
        )
        with pytest.raises(ValueError) as exc_info:
            validate_payload(event)
        assert "exec" in str(exc_info.value)
