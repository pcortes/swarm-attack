"""Tests for schema validation."""
import pytest
from swarm_attack.state.schemas import (
    SwarmEvent,
    SchemaValidationError,
    validate_event,
)


class TestSwarmEvent:
    """Tests for SwarmEvent schema validation."""

    def test_valid_event_minimal(self):
        """Accept event with required fields only."""
        event = SwarmEvent(
            ts="2025-12-20T10:00:00",
            event="implementation_started",
            feature_id="my-feature",
        )
        assert event.ts == "2025-12-20T10:00:00"
        assert event.event == "implementation_started"
        assert event.feature_id == "my-feature"
        assert event.issue is None

    def test_valid_event_full(self):
        """Accept event with all fields."""
        event = SwarmEvent(
            ts="2025-12-20T10:00:00",
            event="implementation_completed",
            feature_id="my-feature",
            issue=5,
            agent="coder",
            cost_usd=1.50,
            success=True,
        )
        assert event.issue == 5
        assert event.agent == "coder"
        assert event.cost_usd == 1.50
        assert event.success is True

    def test_reject_empty_ts(self):
        """Reject event with empty timestamp."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(ts="", event="test", feature_id="test")
        assert exc_info.value.field == "ts"
        assert "required" in exc_info.value.message

    def test_reject_empty_event(self):
        """Reject event with empty event type."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(ts="2025-12-20T10:00:00", event="", feature_id="test")
        assert exc_info.value.field == "event"

    def test_reject_empty_feature_id(self):
        """Reject event with empty feature_id."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(ts="2025-12-20T10:00:00", event="test", feature_id="")
        assert exc_info.value.field == "feature_id"

    def test_reject_negative_issue(self):
        """Reject event with negative issue number."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(
                ts="2025-12-20T10:00:00",
                event="test",
                feature_id="test",
                issue=-1,
            )
        assert exc_info.value.field == "issue"
        assert ">= 1" in exc_info.value.message
        assert exc_info.value.value == -1

    def test_reject_zero_issue(self):
        """Reject event with zero issue number."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(
                ts="2025-12-20T10:00:00",
                event="test",
                feature_id="test",
                issue=0,
            )
        assert exc_info.value.field == "issue"

    def test_reject_negative_cost(self):
        """Reject event with negative cost."""
        with pytest.raises(SchemaValidationError) as exc_info:
            SwarmEvent(
                ts="2025-12-20T10:00:00",
                event="test",
                feature_id="test",
                cost_usd=-5.0,
            )
        assert exc_info.value.field == "cost_usd"
        assert "negative" in exc_info.value.message

    def test_accept_zero_cost(self):
        """Accept event with zero cost (free operations)."""
        event = SwarmEvent(
            ts="2025-12-20T10:00:00",
            event="test",
            feature_id="test",
            cost_usd=0.0,
        )
        assert event.cost_usd == 0.0

    def test_to_dict_minimal(self):
        """to_dict includes only required fields when optional not set."""
        event = SwarmEvent(
            ts="2025-12-20T10:00:00",
            event="test",
            feature_id="test",
        )
        d = event.to_dict()
        assert d == {
            "ts": "2025-12-20T10:00:00",
            "event": "test",
            "feature_id": "test",
        }

    def test_to_dict_full(self):
        """to_dict includes all set fields."""
        event = SwarmEvent(
            ts="2025-12-20T10:00:00",
            event="test",
            feature_id="test",
            issue=5,
            agent="coder",
            cost_usd=1.50,
            success=True,
            error="some error",
        )
        d = event.to_dict()
        assert d["issue"] == 5
        assert d["agent"] == "coder"
        assert d["cost_usd"] == 1.50
        assert d["success"] is True
        assert d["error"] == "some error"

    def test_from_dict_valid(self):
        """from_dict creates valid event."""
        data = {
            "ts": "2025-12-20T10:00:00",
            "event": "test",
            "feature_id": "test",
            "issue": 5,
        }
        event = SwarmEvent.from_dict(data)
        assert event.ts == "2025-12-20T10:00:00"
        assert event.issue == 5

    def test_from_dict_invalid_raises(self):
        """from_dict raises on invalid data."""
        with pytest.raises(SchemaValidationError):
            SwarmEvent.from_dict({"ts": "", "event": "test", "feature_id": "test"})


class TestValidateEvent:
    """Tests for validate_event helper."""

    def test_validates_and_returns_event(self):
        """validate_event returns SwarmEvent on valid data."""
        data = {
            "ts": "2025-12-20T10:00:00",
            "event": "test",
            "feature_id": "test",
        }
        event = validate_event(data)
        assert isinstance(event, SwarmEvent)
        assert event.ts == "2025-12-20T10:00:00"

    def test_raises_on_invalid(self):
        """validate_event raises on invalid data."""
        with pytest.raises(SchemaValidationError):
            validate_event({"ts": "", "event": "", "feature_id": ""})


class TestSchemaValidationError:
    """Tests for SchemaValidationError."""

    def test_error_message_includes_field(self):
        """Error message includes field name."""
        error = SchemaValidationError("my_field", "is invalid")
        assert "my_field" in str(error)

    def test_error_stores_value(self):
        """Error stores the invalid value."""
        error = SchemaValidationError("count", "must be positive", -5)
        assert error.value == -5
        assert error.field == "count"
        assert error.message == "must be positive"
