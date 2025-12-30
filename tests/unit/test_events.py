"""
Tests for the event infrastructure (swarm_attack/events/).

TDD RED phase: These tests define the expected behavior before implementation.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from swarm_attack.events.types import SwarmEvent, EventType
from swarm_attack.events.bus import EventBus
from swarm_attack.events.persistence import EventPersistence


class TestSwarmEvent:
    """Tests for SwarmEvent dataclass."""

    def test_event_creation(self):
        """Events can be created with required fields."""
        event = SwarmEvent(
            event_type=EventType.SPEC_APPROVED,
            feature_id="my-feature",
            confidence=0.85
        )

        assert event.event_type == EventType.SPEC_APPROVED
        assert event.feature_id == "my-feature"
        assert event.confidence == 0.85
        assert event.event_id  # Auto-generated

    def test_event_creation_with_defaults(self):
        """Events use sensible defaults for optional fields."""
        event = SwarmEvent(event_type=EventType.SPEC_APPROVED)

        assert event.feature_id == ""
        assert event.issue_number is None
        assert event.bug_id is None
        assert event.source_agent == ""
        assert event.payload == {}
        assert event.confidence == 0.0
        assert event.timestamp  # Auto-generated

    def test_event_serialization(self):
        """Events serialize to/from dict."""
        event = SwarmEvent(
            event_type=EventType.ISSUE_COMPLETE,
            feature_id="test",
            issue_number=3,
            source_agent="Coder",
            payload={"result": "success"},
            confidence=0.95
        )

        data = event.to_dict()
        restored = SwarmEvent.from_dict(data)

        assert restored.event_type == event.event_type
        assert restored.feature_id == event.feature_id
        assert restored.issue_number == event.issue_number
        assert restored.source_agent == event.source_agent
        assert restored.payload == event.payload
        assert restored.confidence == event.confidence

    def test_event_str_representation(self):
        """Events have readable string representation."""
        event = SwarmEvent(
            event_type=EventType.SPEC_APPROVED,
            feature_id="my-feature"
        )

        str_repr = str(event)
        assert "spec.approved" in str_repr
        assert "my-feature" in str_repr

    def test_event_type_values(self):
        """EventType enum has expected values."""
        # Spec lifecycle
        assert EventType.SPEC_DRAFT_CREATED.value == "spec.draft_created"
        assert EventType.SPEC_APPROVED.value == "spec.approved"

        # Issue lifecycle
        assert EventType.ISSUE_CREATED.value == "issue.created"
        assert EventType.ISSUE_COMPLETE.value == "issue.complete"

        # Bug lifecycle
        assert EventType.BUG_DETECTED.value == "bug.detected"
        assert EventType.BUG_FIXED.value == "bug.fixed"

        # System events
        assert EventType.SYSTEM_PHASE_TRANSITION.value == "system.phase_transition"


class TestEventBus:
    """Tests for EventBus class."""

    def test_subscribe_and_emit(self, tmp_path):
        """Subscribers receive emitted events."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.SPEC_APPROVED, handler)

        event = SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="test")
        bus.emit(event)

        assert len(received) == 1
        assert received[0].feature_id == "test"

    def test_subscribe_multiple_handlers(self, tmp_path):
        """Multiple handlers for same event type all receive events."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received1 = []
        received2 = []

        bus.subscribe(EventType.SPEC_APPROVED, lambda e: received1.append(e))
        bus.subscribe(EventType.SPEC_APPROVED, lambda e: received2.append(e))

        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED))

        assert len(received1) == 1
        assert len(received2) == 1

    def test_subscribers_only_receive_matching_events(self, tmp_path):
        """Subscribers only receive events of their subscribed type."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        bus.subscribe(EventType.SPEC_APPROVED, lambda e: received.append(e))

        # Emit different event type
        bus.emit(SwarmEvent(event_type=EventType.ISSUE_COMPLETE))

        assert len(received) == 0

    def test_global_subscriber(self, tmp_path):
        """Global subscribers receive all events."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        bus.subscribe_all(lambda e: received.append(e))

        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="a"))
        bus.emit(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="b"))

        assert len(received) == 2

    def test_unsubscribe(self, tmp_path):
        """Can unsubscribe handlers."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        def handler(e):
            received.append(e)

        bus.subscribe(EventType.SPEC_APPROVED, handler)
        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED))
        assert len(received) == 1

        bus.unsubscribe(EventType.SPEC_APPROVED, handler)
        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED))
        assert len(received) == 1  # Still 1, handler was unsubscribed

    def test_convenience_method_emit_spec_approved(self, tmp_path):
        """Convenience method emit_spec_approved works correctly."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        bus.subscribe(EventType.SPEC_APPROVED, lambda e: received.append(e))

        event = bus.emit_spec_approved("my-feature", score=0.9)

        assert len(received) == 1
        assert received[0].confidence == 0.9
        assert received[0].payload == {"score": 0.9}
        assert event.feature_id == "my-feature"

    def test_convenience_method_emit_phase_transition(self, tmp_path):
        """Convenience method emit_phase_transition works correctly."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        bus.subscribe(EventType.SYSTEM_PHASE_TRANSITION, lambda e: received.append(e))

        event = bus.emit_phase_transition("my-feature", "SPEC_IN_PROGRESS", "SPEC_APPROVED")

        assert len(received) == 1
        assert received[0].payload == {"from": "SPEC_IN_PROGRESS", "to": "SPEC_APPROVED"}

    def test_handler_error_doesnt_break_bus(self, tmp_path):
        """Handler errors don't prevent other handlers from running."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        def bad_handler(e):
            raise ValueError("Oops")

        def good_handler(e):
            received.append(e)

        bus.subscribe(EventType.SPEC_APPROVED, bad_handler)
        bus.subscribe(EventType.SPEC_APPROVED, good_handler)

        # Should not raise
        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED))

        assert len(received) == 1

    def test_global_handler_error_doesnt_break_bus(self, tmp_path):
        """Global handler errors don't prevent type-specific handlers."""
        bus = EventBus(tmp_path / ".swarm", persist=False)
        received = []

        def bad_global_handler(e):
            raise ValueError("Global error")

        def good_handler(e):
            received.append(e)

        bus.subscribe_all(bad_global_handler)
        bus.subscribe(EventType.SPEC_APPROVED, good_handler)

        bus.emit(SwarmEvent(event_type=EventType.SPEC_APPROVED))

        assert len(received) == 1


class TestEventPersistence:
    """Tests for EventPersistence class."""

    def test_creates_events_directory(self, tmp_path):
        """Persistence creates .swarm/events/ directory."""
        persistence = EventPersistence(tmp_path / ".swarm")

        events_dir = tmp_path / ".swarm" / "events"
        assert events_dir.exists()
        assert events_dir.is_dir()

    def test_persist_and_query(self, tmp_path):
        """Events persist to disk and can be queried."""
        persistence = EventPersistence(tmp_path / ".swarm")

        event = SwarmEvent(
            event_type=EventType.ISSUE_COMPLETE,
            feature_id="test-feature",
            issue_number=1
        )
        persistence.append(event)

        results = persistence.query(feature_id="test-feature")

        assert len(results) == 1
        assert results[0].issue_number == 1

    def test_persist_multiple_events(self, tmp_path):
        """Multiple events persist and can be queried."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="a"))
        persistence.append(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="b"))
        persistence.append(SwarmEvent(event_type=EventType.BUG_FIXED, feature_id="c"))

        results = persistence.query()

        assert len(results) == 3

    def test_query_by_feature_id(self, tmp_path):
        """Can filter events by feature_id."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="a"))
        persistence.append(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="b"))
        persistence.append(SwarmEvent(event_type=EventType.BUG_FIXED, feature_id="a"))

        results = persistence.query(feature_id="a")

        assert len(results) == 2
        assert all(e.feature_id == "a" for e in results)

    def test_query_by_type(self, tmp_path):
        """Can query events by type."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="a"))
        persistence.append(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="b"))
        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="c"))

        results = persistence.query(event_types=[EventType.SPEC_APPROVED])

        assert len(results) == 2
        assert all(e.event_type == EventType.SPEC_APPROVED for e in results)

    def test_query_by_multiple_types(self, tmp_path):
        """Can query events by multiple types."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="a"))
        persistence.append(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="b"))
        persistence.append(SwarmEvent(event_type=EventType.BUG_FIXED, feature_id="c"))

        results = persistence.query(event_types=[EventType.SPEC_APPROVED, EventType.BUG_FIXED])

        assert len(results) == 2

    def test_query_with_limit(self, tmp_path):
        """Can limit query results."""
        persistence = EventPersistence(tmp_path / ".swarm")

        for i in range(10):
            persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id=f"f{i}"))

        results = persistence.query(limit=5)

        assert len(results) == 5

    def test_get_recent(self, tmp_path):
        """Can get recent events."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED))

        results = persistence.get_recent(minutes=5)

        assert len(results) == 1

    def test_get_by_feature(self, tmp_path):
        """get_by_feature is a convenience method for query with feature_id."""
        persistence = EventPersistence(tmp_path / ".swarm")

        persistence.append(SwarmEvent(event_type=EventType.SPEC_APPROVED, feature_id="target"))
        persistence.append(SwarmEvent(event_type=EventType.ISSUE_COMPLETE, feature_id="other"))

        results = persistence.get_by_feature("target")

        assert len(results) == 1
        assert results[0].feature_id == "target"


class TestEventIntegration:
    """Integration tests for EventBus with EventPersistence."""

    def test_bus_with_persistence(self, tmp_path):
        """Bus persists events automatically when persist=True."""
        bus = EventBus(tmp_path / ".swarm", persist=True)

        bus.emit(SwarmEvent(event_type=EventType.BUG_FIXED, feature_id="test"))

        # Check persistence
        persistence = EventPersistence(tmp_path / ".swarm")
        results = persistence.query()

        assert len(results) == 1
        assert results[0].event_type == EventType.BUG_FIXED

    def test_bus_without_persistence(self, tmp_path):
        """Bus does not persist when persist=False."""
        bus = EventBus(tmp_path / ".swarm", persist=False)

        bus.emit(SwarmEvent(event_type=EventType.BUG_FIXED, feature_id="test"))

        # Check no persistence
        events_dir = tmp_path / ".swarm" / "events"
        # Directory may not exist or should be empty
        if events_dir.exists():
            files = list(events_dir.glob("*.jsonl"))
            assert len(files) == 0

    def test_global_bus_singleton(self, tmp_path):
        """get_event_bus returns a singleton."""
        from swarm_attack.events.bus import get_event_bus, _default_bus
        import swarm_attack.events.bus as bus_module

        # Reset the singleton for testing
        bus_module._default_bus = None

        bus1 = get_event_bus(tmp_path / ".swarm")
        bus2 = get_event_bus()

        assert bus1 is bus2
