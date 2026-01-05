"""
ContinuityLedger - Session continuity tracking for the autopilot system.

The ContinuityLedger records:
1. Goals - what the session is trying to achieve
2. Decisions - important choices made during the session
3. Blockers - obstacles encountered
4. Handoff notes - context for the next session
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


@dataclass
class GoalEntry:
    """A goal entry in the ledger."""

    id: str
    description: str
    priority: str = "normal"
    status: str = "pending"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionEntry:
    """A decision entry in the ledger."""

    id: str
    decision: str
    rationale: str
    alternatives: List[str] = field(default_factory=list)
    impact: str = "medium"
    context: Optional[Dict[str, Any]] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlockerEntry:
    """A blocker entry in the ledger."""

    id: str
    description: str
    severity: str = "medium"
    resolved: bool = False
    resolution: Optional[str] = None
    suggested_resolution: Optional[str] = None
    related_files: List[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HandoffNoteEntry:
    """A handoff note entry in the ledger."""

    id: str
    note: str
    category: str = "general"
    priority: str = "normal"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContinuityLedger:
    """
    Ledger for tracking session continuity.

    Records goals, decisions, blockers, and handoff notes for session continuity.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        feature_id: Optional[str] = None,
        issue_number: Optional[int] = None,
        parent_session_id: Optional[str] = None,
        storage_dir: Optional[Path] = None,
    ):
        """
        Initialize a ContinuityLedger.

        Args:
            session_id: Unique identifier for this session. Auto-generated if not provided.
            feature_id: Optional feature branch identifier.
            issue_number: Optional issue number this session relates to.
            parent_session_id: Optional parent session ID for continuation chains.
            storage_dir: Optional storage directory for persistence.
        """
        self.session_id = session_id or str(uuid4())
        self.feature_id = feature_id
        self.issue_number = issue_number
        self.parent_session_id = parent_session_id
        self.storage_dir = Path(storage_dir) if storage_dir else None

        self.created_at = datetime.now().isoformat()
        self.updated_at: Optional[str] = None

        self.goals: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []
        self.blockers: List[Dict[str, Any]] = []
        self.handoff_notes: List[Dict[str, Any]] = []

        # Prior session context (populated when continuing from another session)
        self.prior_handoff_notes: List[Dict[str, Any]] = []
        self._prior_context: Optional[str] = None
        self._prior_goals: List[str] = []

        # Compaction callbacks
        self._compaction_callbacks: List[Callable[[], None]] = []
        self._auto_save_path: Optional[Path] = None

        # Completed work tracking
        self._completed_work: List[str] = []

    # -------------------------------------------------------------------------
    # Goals
    # -------------------------------------------------------------------------

    def add_goal(
        self,
        description: str,
        priority: str = "normal",
        status: str = "pending",
    ) -> str:
        """Add a goal to the ledger."""
        goal_id = f"goal-{uuid4().hex[:8]}"
        self.goals.append(
            {
                "id": goal_id,
                "description": description,
                "priority": priority,
                "status": status,
                "created_at": datetime.now().isoformat(),
            }
        )
        return goal_id

    def update_goal(self, goal_id: str, **updates: Any) -> None:
        """Update a goal's properties."""
        for goal in self.goals:
            if goal["id"] == goal_id:
                goal.update(updates)
                break

    def mark_goal_complete(self, description: str) -> None:
        """Mark a goal as complete by description."""
        for goal in self.goals:
            if goal["description"] == description:
                goal["status"] = "completed"
                break

    def get_prior_goals(self) -> List[str]:
        """Get goals from prior session."""
        return self._prior_goals

    # -------------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------------

    def add_decision(
        self,
        decision: str = "",
        rationale: str = "",
        alternatives: Optional[List[str]] = None,
        impact: str = "medium",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a decision to the ledger."""
        decision_id = f"decision-{uuid4().hex[:8]}"
        entry: Dict[str, Any] = {
            "id": decision_id,
            "decision": decision,
            "rationale": rationale,
            "created_at": datetime.now().isoformat(),
        }
        if alternatives:
            entry["alternatives"] = alternatives
        if impact:
            entry["impact"] = impact
        if context:
            entry["context"] = context
        self.decisions.append(entry)
        return decision_id

    # -------------------------------------------------------------------------
    # Blockers
    # -------------------------------------------------------------------------

    def add_blocker(
        self,
        description: str = "",
        severity: str = "medium",
        suggested_resolution: Optional[str] = None,
        related_files: Optional[List[str]] = None,
    ) -> str:
        """Add a blocker to the ledger."""
        blocker_id = f"blocker-{uuid4().hex[:8]}"
        entry: Dict[str, Any] = {
            "id": blocker_id,
            "description": description,
            "severity": severity,
            "resolved": False,
            "created_at": datetime.now().isoformat(),
        }
        if suggested_resolution:
            entry["suggested_resolution"] = suggested_resolution
        if related_files:
            entry["related_files"] = related_files
        self.blockers.append(entry)
        return blocker_id

    def resolve_blocker(self, blocker_id: str, resolution: str) -> None:
        """Mark a blocker as resolved."""
        for blocker in self.blockers:
            if blocker["id"] == blocker_id:
                blocker["resolved"] = True
                blocker["resolution"] = resolution
                break

    # -------------------------------------------------------------------------
    # Handoff Notes
    # -------------------------------------------------------------------------

    def add_handoff_note(
        self,
        note: str,
        category: str = "general",
        priority: str = "normal",
    ) -> str:
        """Add a handoff note for the next session."""
        note_id = f"note-{uuid4().hex[:8]}"
        self.handoff_notes.append(
            {
                "id": note_id,
                "note": note,
                "category": category,
                "priority": priority,
                "created_at": datetime.now().isoformat(),
            }
        )
        return note_id

    # -------------------------------------------------------------------------
    # Completed Work
    # -------------------------------------------------------------------------

    def mark_complete(self, description: str) -> None:
        """Mark a work item as complete."""
        self._completed_work.append(description)

    def get_completed_work(self) -> List[str]:
        """Get list of completed work items."""
        return self._completed_work.copy()

    # -------------------------------------------------------------------------
    # Context
    # -------------------------------------------------------------------------

    def set_context(self, context: str) -> None:
        """Set the current context/summary."""
        self._prior_context = context

    def get_context(self) -> Optional[str]:
        """Get the current context."""
        return self._prior_context

    def get_prior_context(self) -> Optional[str]:
        """Get context from prior session."""
        return self._prior_context

    def set_prior_goals(self, goals: List[str]) -> None:
        """Set goals from prior session."""
        self._prior_goals = goals

    def set_prior_context(self, context: str) -> None:
        """Set context from prior session."""
        self._prior_context = context

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ledger to dictionary."""
        return {
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
            "parent_session_id": self.parent_session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "goals": self.goals,
            "decisions": self.decisions,
            "blockers": self.blockers,
            "handoff_notes": self.handoff_notes,
            "prior_handoff_notes": self.prior_handoff_notes,
            "completed_work": self._completed_work,
            "context": self._prior_context,
            "prior_goals": self._prior_goals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContinuityLedger":
        """Deserialize ledger from dictionary."""
        ledger = cls(
            session_id=data.get("session_id"),
            feature_id=data.get("feature_id"),
            issue_number=data.get("issue_number"),
            parent_session_id=data.get("parent_session_id"),
        )
        ledger.created_at = data.get("created_at", ledger.created_at)
        ledger.updated_at = data.get("updated_at")
        ledger.goals = data.get("goals", [])
        ledger.decisions = data.get("decisions", [])
        ledger.blockers = data.get("blockers", [])
        ledger.handoff_notes = data.get("handoff_notes", [])
        ledger.prior_handoff_notes = data.get("prior_handoff_notes", [])
        ledger._completed_work = data.get("completed_work", [])
        ledger._prior_context = data.get("context")
        ledger._prior_goals = data.get("prior_goals", [])
        return ledger

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Save ledger to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Optional["ContinuityLedger"]:
        """Load ledger from a JSON file."""
        path = Path(path)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    @classmethod
    def find_latest(
        cls,
        continuity_dir: Path,
        feature_id: Optional[str] = None,
        issue_number: Optional[int] = None,
    ) -> Optional["ContinuityLedger"]:
        """Find the most recent ledger matching the criteria."""
        continuity_dir = Path(continuity_dir)
        if not continuity_dir.exists():
            return None

        matching_ledgers: List[tuple] = []  # (mtime, ledger)

        for json_file in continuity_dir.glob("*.json"):
            ledger = cls.load(json_file)
            if ledger is None:
                continue

            # Check if it matches criteria
            if feature_id and ledger.feature_id != feature_id:
                continue
            if issue_number and ledger.issue_number != issue_number:
                continue

            mtime = json_file.stat().st_mtime
            matching_ledgers.append((mtime, ledger))

        if not matching_ledgers:
            return None

        # Return the most recent
        matching_ledgers.sort(key=lambda x: x[0], reverse=True)
        return matching_ledgers[0][1]

    # -------------------------------------------------------------------------
    # Session Continuation
    # -------------------------------------------------------------------------

    @classmethod
    def continue_from(
        cls, prior_ledger: "ContinuityLedger", new_session_id: Optional[str] = None
    ) -> "ContinuityLedger":
        """Create a new ledger that continues from a prior session."""
        new_ledger = cls(
            session_id=new_session_id,
            feature_id=prior_ledger.feature_id,
            issue_number=prior_ledger.issue_number,
            parent_session_id=prior_ledger.session_id,
        )

        # Carry over incomplete goals
        for goal in prior_ledger.goals:
            if goal.get("status") != "completed":
                new_ledger.goals.append(goal.copy())

        # Carry over unresolved blockers
        for blocker in prior_ledger.blockers:
            if not blocker.get("resolved"):
                new_ledger.blockers.append(blocker.copy())

        # Store prior handoff notes
        new_ledger.prior_handoff_notes = [n.copy() for n in prior_ledger.handoff_notes]

        return new_ledger

    # -------------------------------------------------------------------------
    # Context Injection
    # -------------------------------------------------------------------------

    def get_injection_context(self) -> str:
        """Get formatted context suitable for prompt injection."""
        parts = []

        if self.goals:
            goals_text = "\n".join(f"- {g['description']}" for g in self.goals)
            parts.append(f"**Goals:**\n{goals_text}")

        if self.decisions:
            decisions_text = "\n".join(
                f"- {d['decision']}: {d.get('rationale', '')}" for d in self.decisions
            )
            parts.append(f"**Decisions:**\n{decisions_text}")

        if self.blockers:
            blockers_text = "\n".join(f"- {b['description']}" for b in self.blockers)
            parts.append(f"**Blockers:**\n{blockers_text}")

        if self.handoff_notes:
            notes_text = "\n".join(f"- {n['note']}" for n in self.handoff_notes)
            parts.append(f"**Handoff Notes:**\n{notes_text}")

        return "\n\n".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the ledger state."""
        return {
            "goals": {
                "total": len(self.goals),
                "completed": sum(1 for g in self.goals if g.get("status") == "completed"),
                "in_progress": sum(
                    1 for g in self.goals if g.get("status") == "in_progress"
                ),
                "pending": sum(1 for g in self.goals if g.get("status") == "pending"),
            },
            "decisions": {"total": len(self.decisions)},
            "blockers": {
                "total": len(self.blockers),
                "resolved": sum(1 for b in self.blockers if b.get("resolved")),
                "unresolved": sum(1 for b in self.blockers if not b.get("resolved")),
            },
            "handoff_notes": {"total": len(self.handoff_notes)},
        }

    # -------------------------------------------------------------------------
    # Compaction Support
    # -------------------------------------------------------------------------

    def on_compaction(self, callback: Callable[[], None]) -> None:
        """Register a callback for compaction events."""
        self._compaction_callbacks.append(callback)

    def configure_auto_save(self, path: Path) -> None:
        """Configure automatic save path for compaction."""
        self._auto_save_path = Path(path)

    def trigger_compaction_save(self) -> None:
        """Trigger compaction callbacks and auto-save."""
        for callback in self._compaction_callbacks:
            callback()

        if self._auto_save_path:
            self.save(self._auto_save_path)

    def get_compacted_context(self, max_tokens: int = 500) -> str:
        """Get a compacted version of context prioritizing critical items."""
        parts = []

        # Prioritize critical items
        critical_goals = [g for g in self.goals if g.get("priority") == "critical"]
        critical_blockers = [b for b in self.blockers if b.get("severity") == "critical"]

        if critical_goals:
            goals_text = "\n".join(f"- {g['description']}" for g in critical_goals)
            parts.append(f"**Critical Goals:**\n{goals_text}")

        if critical_blockers:
            blockers_text = "\n".join(f"- {b['description']}" for b in critical_blockers)
            parts.append(f"**Critical Blockers:**\n{blockers_text}")

        # Add high priority items if space allows
        result = "\n\n".join(parts)

        # Simple token estimation (4 chars per token)
        estimated_tokens = len(result) // 4
        if estimated_tokens < max_tokens:
            # Add more context if there's room
            high_goals = [g for g in self.goals if g.get("priority") == "high"]
            if high_goals:
                high_text = "\n".join(f"- {g['description']}" for g in high_goals)
                result += f"\n\n**High Priority Goals:**\n{high_text}"

        return result
