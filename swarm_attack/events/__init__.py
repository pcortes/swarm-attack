"""
Event infrastructure for the swarm-attack autopilot system.

This module provides event-driven architecture to support:
- Detecting when spec debate scores reach approval threshold
- Detecting when complexity gate passes for all issues
- Detecting when bug fix plans are ready for approval
- Triggering automated actions based on state changes
"""

from swarm_attack.events.types import EventType, SwarmEvent
from swarm_attack.events.bus import EventBus, get_event_bus
from swarm_attack.events.persistence import EventPersistence

__all__ = [
    "EventType",
    "SwarmEvent",
    "EventBus",
    "get_event_bus",
    "EventPersistence",
]
