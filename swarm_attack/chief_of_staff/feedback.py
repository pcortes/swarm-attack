"""FeedbackIncorporator core data models and FeedbackStore for persistence."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class HumanFeedback:
    """Represents human feedback on a checkpoint decision.
    
    Attributes:
        checkpoint_id: Unique identifier for the checkpoint this feedback relates to.
        timestamp: When the feedback was provided.
        feedback_type: Type of feedback (e.g., 'approval', 'rejection', 'modification').
        content: The actual feedback content/message.
        applies_to: List of goal IDs or contexts this feedback applies to.
        expires_at: Optional expiration datetime for time-limited feedback.
    """
    
    checkpoint_id: str
    timestamp: datetime
    feedback_type: str
    content: str
    applies_to: list[str]
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize HumanFeedback to a dictionary.
        
        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp.isoformat(),
            "feedback_type": self.feedback_type,
            "content": self.content,
            "applies_to": self.applies_to,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanFeedback":
        """Deserialize HumanFeedback from a dictionary.
        
        Args:
            data: Dictionary containing HumanFeedback fields.
            
        Returns:
            HumanFeedback instance.
        """
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        
        return cls(
            checkpoint_id=data["checkpoint_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            feedback_type=data["feedback_type"],
            content=data["content"],
            applies_to=data.get("applies_to", []),
            expires_at=expires_at,
        )


class FeedbackStore:
    """Persistence layer for human feedback.
    
    Stores feedback entries in a JSON file within the .swarm/feedback/ directory.
    Provides CRUD operations for managing feedback.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize FeedbackStore.
        
        Args:
            base_path: Directory path for storing feedback. Defaults to .swarm/feedback/.
        """
        if base_path is None:
            self.base_path = Path.cwd() / ".swarm" / "feedback"
        else:
            self.base_path = Path(base_path)
        
        self._feedback: list[HumanFeedback] = []
    
    def _ensure_directory(self) -> None:
        """Ensure the feedback directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def _feedback_file(self) -> Path:
        """Path to the feedback JSON file."""
        return self.base_path / "feedback.json"
    
    def add_feedback(self, feedback: HumanFeedback) -> None:
        """Add a new feedback entry.
        
        Args:
            feedback: HumanFeedback instance to add.
        """
        self._feedback.append(feedback)
    
    def get_all(self) -> list[HumanFeedback]:
        """Get all feedback entries.
        
        Returns:
            List of all HumanFeedback entries.
        """
        self._ensure_directory()
        return list(self._feedback)
    
    def save(self) -> None:
        """Save all feedback to the JSON file."""
        self._ensure_directory()
        
        data = [fb.to_dict() for fb in self._feedback]
        
        with open(self._feedback_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def load(self) -> None:
        """Load feedback from the JSON file.
        
        If the file doesn't exist, initializes with empty list.
        """
        self._ensure_directory()
        
        if not self._feedback_file.exists():
            self._feedback = []
            return
        
        with open(self._feedback_file) as f:
            data = json.load(f)
        
        self._feedback = [HumanFeedback.from_dict(item) for item in data]