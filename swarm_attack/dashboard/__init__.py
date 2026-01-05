"""Dashboard module for swarm-attack.

This module provides a lightweight dashboard for autopilot orchestration
status tracking and visualization.
"""

from swarm_attack.dashboard.status_view import (
    AgentEntry,
    TaskEntry,
    ContextEntry,
    StatusEntry,
    StatusView,
)

__all__ = [
    "AgentEntry",
    "TaskEntry",
    "ContextEntry",
    "StatusEntry",
    "StatusView",
]
