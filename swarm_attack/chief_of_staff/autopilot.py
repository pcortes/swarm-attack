"""AutopilotRunner for autonomous execution with checkpoint enforcement."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import uuid


class AutopilotStatus(Enum):
    """Status of an autopilot session."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class StopTrigger:
    """Trigger conditions for stopping autopilot execution."""
    until_time: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StopTrigger":
        """Create StopTrigger from dictionary."""
        return cls(
            until_time=data.get("until_time"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "until_time": self.until_time,
        }


@dataclass
class GoalResult:
    """Result of executing a single goal."""
    success: bool
    cost_usd: float
    error: Optional[str] = None


@dataclass
class AutopilotSession:
    """Session state for autopilot execution."""
    session_id: str
    goals: list[str]
    budget_usd: float
    duration_seconds: int
    current_goal_index: int = 0
    status: AutopilotStatus = AutopilotStatus.RUNNING
    cost_usd: float = 0.0
    started_at: Optional[datetime] = None
    stop_trigger: Optional[StopTrigger] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Create AutopilotSession from dictionary."""
        status_str = data.get("status", "running")
        if isinstance(status_str, AutopilotStatus):
            status = status_str
        else:
            status = AutopilotStatus(status_str)

        started_at = data.get("started_at")
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)

        stop_trigger_data = data.get("stop_trigger")
        stop_trigger = None
        if stop_trigger_data:
            stop_trigger = StopTrigger.from_dict(stop_trigger_data)

        return cls(
            session_id=data.get("session_id", ""),
            goals=data.get("goals", []),
            budget_usd=data.get("budget_usd", 0.0),
            duration_seconds=data.get("duration_seconds", 0),
            current_goal_index=data.get("current_goal_index", 0),
            status=status,
            cost_usd=data.get("cost_usd", 0.0),
            started_at=started_at,
            stop_trigger=stop_trigger,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "session_id": self.session_id,
            "goals": self.goals,
            "budget_usd": self.budget_usd,
            "duration_seconds": self.duration_seconds,
            "current_goal_index": self.current_goal_index,
            "status": self.status.value if isinstance(self.status, AutopilotStatus) else self.status,
            "cost_usd": self.cost_usd,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }
        if self.stop_trigger:
            result["stop_trigger"] = self.stop_trigger.to_dict()
        return result


class AutopilotSessionStore:
    """Persistence store for autopilot sessions."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize session store."""
        if base_path is None:
            base_path = Path.cwd() / ".swarm" / "autopilot"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get path for session file."""
        return self.base_path / f"{session_id}.json"

    def save(self, session: AutopilotSession) -> None:
        """Save session to disk."""
        path = self._session_path(session.session_id)
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def load(self, session_id: str) -> Optional[AutopilotSession]:
        """Load session from disk."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return AutopilotSession.from_dict(data)

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        sessions = []
        for path in self.base_path.glob("*.json"):
            sessions.append(path.stem)
        return sessions


class AutopilotRunner:
    """Executes work autonomously with checkpoint enforcement."""

    def __init__(
        self,
        session_store: Optional[AutopilotSessionStore] = None,
        feature_orchestrator: Optional[Any] = None,
        bug_orchestrator: Optional[Any] = None,
    ):
        """Initialize autopilot runner."""
        self.session_store = session_store or AutopilotSessionStore()
        self.feature_orchestrator = feature_orchestrator
        self.bug_orchestrator = bug_orchestrator

    def start(
        self,
        goals: list[str],
        budget_usd: float,
        duration_seconds: int,
        stop_trigger: Optional[StopTrigger] = None,
    ) -> AutopilotSession:
        """Start a new autopilot session."""
        session_id = str(uuid.uuid4())
        session = AutopilotSession(
            session_id=session_id,
            goals=goals,
            budget_usd=budget_usd,
            duration_seconds=duration_seconds,
            status=AutopilotStatus.RUNNING,
            stop_trigger=stop_trigger,
        )
        self.session_store.save(session)
        self._run_session(session)
        return session

    def resume(self, session_id: str) -> AutopilotSession:
        """Resume a paused session."""
        session = self.session_store.load(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        
        if session.status not in [AutopilotStatus.PAUSED, AutopilotStatus.RUNNING]:
            raise ValueError(f"Session {session_id} is not resumable (status: {session.status.value})")
        
        session.status = AutopilotStatus.RUNNING
        self.session_store.save(session)
        self._run_session(session)
        return session

    def execute_goal(self, goal: str) -> GoalResult:
        """Execute a single goal, routing to appropriate orchestrator."""
        if goal.startswith("fix bug:"):
            if self.bug_orchestrator:
                result = self.bug_orchestrator.run(goal)
                return GoalResult(
                    success=result.success,
                    cost_usd=getattr(result, 'cost_usd', 0.0),
                    error=getattr(result, 'error', None),
                )
            return GoalResult(success=False, cost_usd=0.0, error="No bug orchestrator configured")
        elif goal.startswith("implement feature:"):
            if self.feature_orchestrator:
                result = self.feature_orchestrator.run(goal)
                return GoalResult(
                    success=result.success,
                    cost_usd=getattr(result, 'cost_usd', 0.0),
                    error=getattr(result, 'error', None),
                )
            return GoalResult(success=False, cost_usd=0.0, error="No feature orchestrator configured")
        else:
            # Default to feature orchestrator for unrecognized goals
            if self.feature_orchestrator:
                result = self.feature_orchestrator.run(goal)
                return GoalResult(
                    success=result.success,
                    cost_usd=getattr(result, 'cost_usd', 0.0),
                    error=getattr(result, 'error', None),
                )
            return GoalResult(success=False, cost_usd=0.0, error="No orchestrator configured")

    def handle_checkpoint(
        self,
        session: AutopilotSession,
        trigger: Optional[StopTrigger],
    ) -> str:
        """Handle checkpoint - returns 'continue', 'pause', or 'abort'."""
        # Always persist session state
        self.session_store.save(session)
        
        # Check budget
        if session.cost_usd >= session.budget_usd:
            return "pause"
        
        # Check time trigger
        if trigger and trigger.until_time:
            now = datetime.now()
            trigger_time = datetime.strptime(trigger.until_time, "%H:%M")
            trigger_datetime = now.replace(
                hour=trigger_time.hour,
                minute=trigger_time.minute,
                second=0,
                microsecond=0,
            )
            if now >= trigger_datetime:
                return "pause"
        
        return "continue"

    def get_status(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get status information for a session."""
        session = self.session_store.load(session_id)
        if session is None:
            return None
        
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "goals": session.goals,
            "current_goal_index": session.current_goal_index,
            "cost_usd": session.cost_usd,
            "budget_usd": session.budget_usd,
            "duration_seconds": session.duration_seconds,
        }

    def _run_session(self, session: AutopilotSession) -> None:
        """Run the session, executing goals until completion or pause."""
        while session.current_goal_index < len(session.goals):
            # Check triggers before each goal
            checkpoint_result = self.handle_checkpoint(session, session.stop_trigger)
            if checkpoint_result == "pause":
                session.status = AutopilotStatus.PAUSED
                self.session_store.save(session)
                return
            elif checkpoint_result == "abort":
                session.status = AutopilotStatus.ABORTED
                self.session_store.save(session)
                return
            
            # Execute current goal
            goal = session.goals[session.current_goal_index]
            result = self.execute_goal(goal)
            
            # Update session with result
            session.cost_usd += result.cost_usd
            session.current_goal_index += 1
            
            # Persist after each goal
            self.session_store.save(session)
            
            # Check triggers after goal execution
            checkpoint_result = self.handle_checkpoint(session, session.stop_trigger)
            if checkpoint_result == "pause":
                session.status = AutopilotStatus.PAUSED
                self.session_store.save(session)
                return
            elif checkpoint_result == "abort":
                session.status = AutopilotStatus.ABORTED
                self.session_store.save(session)
                return
        
        # All goals completed
        session.status = AutopilotStatus.COMPLETED
        self.session_store.save(session)