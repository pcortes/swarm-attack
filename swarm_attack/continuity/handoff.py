"""
HandoffManager - Auto-Handoff System for session continuity.

This module provides automatic handoff generation and injection for maintaining
context across Claude sessions. Handoffs are generated on PreCompact hooks and
injected on SessionStart hooks.

Acceptance Criteria:
1. Generate handoff on PreCompact hook
2. Include: completed work, pending goals, blockers, context
3. Inject handoff automatically on SessionStart
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ledger import ContinuityLedger


@dataclass
class Handoff:
    """
    Represents a handoff document for session continuity.

    Contains all the context needed to resume work in a new session:
    - Goals from the previous session
    - Decisions made
    - Completed work
    - Blockers encountered
    - General context/summary
    """

    session_id: str
    goals: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    completed: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    context: str = ""
    generated_at: str = ""
    pending_goals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize handoff to dictionary."""
        return {
            "session_id": self.session_id,
            "goals": self.goals,
            "decisions": self.decisions,
            "completed": self.completed,
            "blockers": self.blockers,
            "context": self.context,
            "generated_at": self.generated_at,
            "pending_goals": self.pending_goals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Handoff":
        """Deserialize handoff from dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            goals=data.get("goals", []),
            decisions=data.get("decisions", []),
            completed=data.get("completed", []),
            blockers=data.get("blockers", []),
            context=data.get("context", ""),
            generated_at=data.get("generated_at", ""),
            pending_goals=data.get("pending_goals", []),
        )


class HandoffManager:
    """
    Manages handoff generation, persistence, and injection.

    Handoffs are:
    - Generated when PreCompact hook fires (before context compaction)
    - Saved to {storage_dir}/handoffs/handoff-{session_id}.json
    - Loaded and injected when SessionStart hook fires
    """

    def __init__(self, storage_dir: Path):
        """
        Initialize HandoffManager.

        Args:
            storage_dir: Base directory for storing handoff files.
        """
        self.storage_dir = Path(storage_dir)
        self.handoffs_dir = self.storage_dir / "handoffs"

    def _ensure_handoffs_dir(self) -> None:
        """Ensure the handoffs directory exists."""
        self.handoffs_dir.mkdir(parents=True, exist_ok=True)

    def _get_handoff_path(self, session_id: str) -> Path:
        """Get the file path for a handoff by session ID."""
        return self.handoffs_dir / f"handoff-{session_id}.json"

    # -------------------------------------------------------------------------
    # Handoff Generation
    # -------------------------------------------------------------------------

    def generate_handoff(self, ledger: ContinuityLedger) -> Handoff:
        """
        Generate a handoff from a ContinuityLedger.

        Extracts all relevant information from the ledger and creates
        a Handoff object ready for persistence and later injection.

        Args:
            ledger: The ContinuityLedger to generate a handoff from.

        Returns:
            A Handoff object containing the ledger's state.
        """
        # Extract goals (descriptions only)
        goals = [g.get("description", "") for g in ledger.goals]

        # Extract decisions
        decisions = [d.get("decision", "") for d in ledger.decisions]

        # Extract completed work
        completed = ledger.get_completed_work()

        # Extract blockers (unresolved only for blockers list, all for context)
        blockers = [b.get("description", "") for b in ledger.blockers if not b.get("resolved")]

        # Extract pending goals (not completed)
        pending_goals = [
            g.get("description", "")
            for g in ledger.goals
            if g.get("status") != "completed"
        ]

        # Get context
        context = ledger.get_context() or ""

        return Handoff(
            session_id=ledger.session_id,
            goals=goals,
            decisions=decisions,
            completed=completed,
            blockers=blockers,
            context=context,
            generated_at=datetime.now(timezone.utc).isoformat(),
            pending_goals=pending_goals,
        )

    def on_precompact(self, ledger: ContinuityLedger) -> Handoff:
        """
        Hook handler for PreCompact events.

        Generates and saves a handoff before context compaction.

        Args:
            ledger: The ContinuityLedger to generate a handoff from.

        Returns:
            The generated Handoff object.
        """
        handoff = self.generate_handoff(ledger)
        self.save_handoff(handoff)
        return handoff

    # -------------------------------------------------------------------------
    # Handoff Persistence
    # -------------------------------------------------------------------------

    def save_handoff(self, handoff: Handoff) -> None:
        """
        Save a handoff to disk.

        Saves to {storage_dir}/handoffs/handoff-{session_id}.json

        Args:
            handoff: The Handoff to save.
        """
        self._ensure_handoffs_dir()
        path = self._get_handoff_path(handoff.session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(handoff.to_dict(), f, indent=2, ensure_ascii=False)

    def load_handoff(self, session_id: str) -> Optional[Handoff]:
        """
        Load a handoff by session ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The Handoff if found, None otherwise.
        """
        path = self._get_handoff_path(session_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Handoff.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def load_latest_handoff(self) -> Optional[Handoff]:
        """
        Load the most recent handoff.

        Returns the handoff with the most recent file modification time.

        Returns:
            The most recent Handoff if any exist, None otherwise.
        """
        if not self.handoffs_dir.exists():
            return None

        handoff_files = list(self.handoffs_dir.glob("handoff-*.json"))
        if not handoff_files:
            return None

        # Sort by modification time (most recent first)
        handoff_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Load the most recent one
        for path in handoff_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Handoff.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return None

    def list_handoffs(self) -> List[Handoff]:
        """
        List all available handoffs.

        Returns:
            List of all Handoff objects stored.
        """
        if not self.handoffs_dir.exists():
            return []

        handoffs = []
        for path in self.handoffs_dir.glob("handoff-*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                handoffs.append(Handoff.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return handoffs

    # -------------------------------------------------------------------------
    # Handoff Injection
    # -------------------------------------------------------------------------

    def on_session_start(self, new_session_id: str) -> Optional[Handoff]:
        """
        Hook handler for SessionStart events.

        Returns the most recent handoff for injection into the new session.

        Args:
            new_session_id: The ID of the new session starting.

        Returns:
            The most recent Handoff if available, None otherwise.
        """
        return self.load_latest_handoff()

    def inject_into_ledger(self, ledger: ContinuityLedger) -> bool:
        """
        Inject handoff data into a new session's ledger.

        Loads the most recent handoff and populates the ledger's
        prior context fields.

        Args:
            ledger: The new session's ContinuityLedger to inject into.

        Returns:
            True if injection succeeded, False if no handoff available.
        """
        handoff = self.load_latest_handoff()
        if handoff is None:
            return False

        # Set prior goals
        ledger.set_prior_goals(handoff.goals)

        # Set prior context
        formatted_context = self.format_for_injection(handoff)
        ledger.set_prior_context(formatted_context)

        return True

    def format_for_injection(self, handoff: Handoff) -> str:
        """
        Format a handoff as readable context for LLM consumption.

        Creates a human-readable summary of the handoff suitable for
        injection into a prompt.

        Args:
            handoff: The Handoff to format.

        Returns:
            A formatted string representation of the handoff.
        """
        parts = []

        parts.append(f"## Handoff from Session: {handoff.session_id}")
        parts.append(f"Generated: {handoff.generated_at}")

        if handoff.context:
            parts.append(f"\n### Context\n{handoff.context}")

        if handoff.goals:
            goals_text = "\n".join(f"- {goal}" for goal in handoff.goals)
            parts.append(f"\n### Goals\n{goals_text}")

        if handoff.completed:
            completed_text = "\n".join(f"- {item}" for item in handoff.completed)
            parts.append(f"\n### Completed Work\n{completed_text}")

        if handoff.decisions:
            decisions_text = "\n".join(f"- {decision}" for decision in handoff.decisions)
            parts.append(f"\n### Decisions Made\n{decisions_text}")

        if handoff.blockers:
            blockers_text = "\n".join(f"- {blocker}" for blocker in handoff.blockers)
            parts.append(f"\n### Active Blockers\n{blockers_text}")

        return "\n".join(parts)
