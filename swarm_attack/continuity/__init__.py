"""
Continuity module for session state persistence and handoff.

This module provides tools for maintaining context and state across
Claude sessions, including:
- ContinuityLedger: Records goals, decisions, blockers, and handoff notes
- Handoff/HandoffManager: Auto-generates and injects session handoffs
"""

from .ledger import (
    ContinuityLedger,
    GoalEntry,
    DecisionEntry,
    BlockerEntry,
    HandoffNoteEntry,
)
from .handoff import Handoff, HandoffManager

__all__ = [
    "ContinuityLedger",
    "GoalEntry",
    "DecisionEntry",
    "BlockerEntry",
    "HandoffNoteEntry",
    "Handoff",
    "HandoffManager",
]
