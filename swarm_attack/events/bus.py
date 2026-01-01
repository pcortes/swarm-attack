"""
Event bus for the swarm-attack event system.

Lightweight event bus for routing events to subscribers.
Supports sync handlers (for Phase 1) with async-ready design.
"""

from pathlib import Path
from typing import Callable, Optional

from swarm_attack.events.persistence import EventPersistence
from swarm_attack.events.types import EventType, SwarmEvent
from swarm_attack.events.validation import validate_payload

EventHandler = Callable[[SwarmEvent], None]


class EventBus:
    """Lightweight event bus for routing swarm events."""

    def __init__(
        self,
        swarm_dir: Optional[Path] = None,
        persist: bool = True,
    ) -> None:
        """
        Initialize the event bus.

        Args:
            swarm_dir: Path to .swarm directory for persistence.
            persist: Whether to persist events to disk.
        """
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._persist = persist
        if persist and swarm_dir:
            self._persistence: Optional[EventPersistence] = EventPersistence(swarm_dir)
        else:
            self._persistence = None

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events (for logging, metrics)."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def emit(self, event: SwarmEvent) -> None:
        """Emit an event to all subscribers.

        Validates the event payload before dispatch. Invalid payloads
        raise ValueError and are not persisted or dispatched.

        Raises:
            ValueError: If the event payload contains disallowed fields.
        """
        # Validate payload before any dispatch or persistence (P0 Security)
        validate_payload(event)

        # Persist after validation (for debugging and replay)
        if self._persistence:
            self._persistence.append(event)

        # Global handlers (logging, metrics)
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                # Log but don't fail - handlers shouldn't break the bus
                pass

        # Type-specific handlers
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    handler(event)
                except Exception:
                    # Log but don't fail - handlers shouldn't break the bus
                    pass

    def emit_spec_approved(
        self,
        feature_id: str,
        score: float,
        source_agent: str = "SpecModerator",
    ) -> SwarmEvent:
        """Convenience method to emit spec approval event."""
        event = SwarmEvent(
            event_type=EventType.SPEC_APPROVED,
            feature_id=feature_id,
            source_agent=source_agent,
            confidence=score,
            payload={"score": score},
        )
        self.emit(event)
        return event

    def emit_phase_transition(
        self,
        feature_id: str,
        from_phase: str,
        to_phase: str,
    ) -> SwarmEvent:
        """Convenience method to emit phase transition."""
        event = SwarmEvent(
            event_type=EventType.SYSTEM_PHASE_TRANSITION,
            feature_id=feature_id,
            payload={"from": from_phase, "to": to_phase},
        )
        self.emit(event)
        return event


# Global singleton for convenience
_default_bus: Optional[EventBus] = None


def get_event_bus(swarm_dir: Optional[Path] = None) -> EventBus:
    """Get or create the default event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus(swarm_dir, persist=True)
    return _default_bus
