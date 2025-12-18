"""Autopilot session models for pause/resume functionality."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AutopilotState(Enum):
    """State of an autopilot session."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AutopilotSession:
    """Represents an autopilot session that can be paused and resumed."""
    
    session_id: str
    feature_id: str
    state: AutopilotState = AutopilotState.RUNNING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_persisted_at: Optional[datetime] = None
    current_issue: Optional[int] = None
    completed_issues: list[int] = field(default_factory=list)
    error_message: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Create AutopilotSession from dictionary."""
        state_str = data.get("state", "running")
        try:
            state = AutopilotState(state_str)
        except ValueError:
            state = AutopilotState.RUNNING
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)
        
        last_persisted_at = data.get("last_persisted_at")
        if isinstance(last_persisted_at, str):
            last_persisted_at = datetime.fromisoformat(last_persisted_at)
        
        return cls(
            session_id=data.get("session_id", ""),
            feature_id=data.get("feature_id", ""),
            state=state,
            created_at=created_at,
            last_persisted_at=last_persisted_at,
            current_issue=data.get("current_issue"),
            completed_issues=data.get("completed_issues", []),
            error_message=data.get("error_message"),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert AutopilotSession to dictionary."""
        return {
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_persisted_at": self.last_persisted_at.isoformat() if self.last_persisted_at else None,
            "current_issue": self.current_issue,
            "completed_issues": self.completed_issues,
            "error_message": self.error_message,
        }