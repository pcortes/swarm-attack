"""FeedbackIncorporator core data models and FeedbackStore for persistence."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from swarm_attack.chief_of_staff.checkpoints import Checkpoint


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


class FeedbackIncorporator:
    """Records and classifies human feedback from checkpoints.
    
    The FeedbackIncorporator processes human feedback given at checkpoints,
    classifying it as guidance, correction, or preference, and extracting
    relevant tags for future reference.
    
    Attributes:
        feedback_store: The FeedbackStore used for persistence.
    """
    
    # Keywords for classification (case-insensitive)
    GUIDANCE_KEYWORDS = ["suggest", "recommend", "consider", "try", "might", "could", "should"]
    CORRECTION_KEYWORDS = ["wrong", "incorrect", "fix", "error", "bug", "mistake", "broken"]
    PREFERENCE_KEYWORDS = ["prefer", "like", "always", "never", "want", "love", "hate"]
    
    # Tags to extract from notes (case-insensitive)
    NOTE_TAGS = ["testing", "performance", "security", "ui", "ux", "api", "database", "cost"]
    
    # Expiry durations by feedback type
    EXPIRY_DAYS = {
        "guidance": 30,  # Guidance expires in 30 days
        "correction": 7,  # Corrections expire in 7 days (more immediate)
        "preference": None,  # Preferences never expire
    }
    
    def __init__(self, feedback_store: FeedbackStore) -> None:
        """Initialize FeedbackIncorporator.
        
        Args:
            feedback_store: FeedbackStore instance for persisting feedback.
        """
        self.feedback_store = feedback_store
    
    def record_feedback(self, checkpoint: Checkpoint, notes: str) -> HumanFeedback:
        """Record human feedback from a checkpoint with classification.
        
        Creates a HumanFeedback instance with automatic classification,
        tag extraction, and expiry calculation based on the feedback type.
        
        Args:
            checkpoint: The Checkpoint that was reviewed.
            notes: Human notes/feedback about the checkpoint decision.
            
        Returns:
            The created HumanFeedback instance.
        """
        # Classify the feedback type
        feedback_type = self._classify_feedback(notes)
        
        # Extract relevant tags
        tags = self._extract_tags(checkpoint, notes)
        
        # Calculate expiry based on feedback type
        expiry_str = self._calculate_expiry(feedback_type)
        expires_at = datetime.fromisoformat(expiry_str) if expiry_str else None
        
        # Create the feedback instance
        feedback = HumanFeedback(
            checkpoint_id=checkpoint.checkpoint_id,
            timestamp=datetime.now(),
            feedback_type=feedback_type,
            content=notes,
            applies_to=tags,
            expires_at=expires_at,
        )
        
        # Add to store
        self.feedback_store.add_feedback(feedback)
        
        return feedback
    
    def _classify_feedback(self, notes: str) -> str:
        """Classify feedback as guidance, correction, or preference.
        
        Uses simple keyword matching (case-insensitive) to determine
        the feedback type. Priority: correction > preference > guidance.
        
        Args:
            notes: The feedback notes to classify.
            
        Returns:
            One of 'guidance', 'correction', or 'preference'.
        """
        notes_lower = notes.lower()
        
        # Check for correction keywords first (highest priority)
        for keyword in self.CORRECTION_KEYWORDS:
            if keyword in notes_lower:
                return "correction"
        
        # Check for preference keywords
        for keyword in self.PREFERENCE_KEYWORDS:
            if keyword in notes_lower:
                return "preference"
        
        # Check for guidance keywords
        for keyword in self.GUIDANCE_KEYWORDS:
            if keyword in notes_lower:
                return "guidance"
        
        # Default to guidance
        return "guidance"
    
    def _extract_tags(self, checkpoint: Checkpoint, notes: str) -> list[str]:
        """Extract relevant tags from checkpoint and notes.
        
        Extracts tags based on:
        1. The checkpoint trigger type
        2. Keywords found in the notes
        3. Goal ID prefix if available
        
        Args:
            checkpoint: The Checkpoint being reviewed.
            notes: The feedback notes.
            
        Returns:
            List of extracted tags.
        """
        tags: list[str] = []
        
        # Add checkpoint trigger type as a tag
        trigger_tag = checkpoint.trigger.value.lower()
        tags.append(trigger_tag)
        
        # Extract tags from notes based on keywords
        notes_lower = notes.lower()
        for tag in self.NOTE_TAGS:
            if tag in notes_lower:
                tags.append(tag)
        
        # Extract goal type from goal_id if present
        goal_id = checkpoint.goal_id
        if goal_id:
            # Common prefixes: feature_, bug_, spec_
            if goal_id.startswith("feature"):
                tags.append("feature")
            elif goal_id.startswith("bug"):
                tags.append("bug")
            elif goal_id.startswith("spec"):
                tags.append("spec")
        
        return tags
    
    def _calculate_expiry(self, feedback_type: str) -> Optional[str]:
        """Calculate expiry datetime based on feedback type.
        
        - Preference feedback: Never expires (returns None)
        - Guidance feedback: Expires in 30 days
        - Correction feedback: Expires in 7 days
        
        Args:
            feedback_type: The classified feedback type.
            
        Returns:
            ISO format datetime string for expiry, or None if never expires.
        """
        expiry_days = self.EXPIRY_DAYS.get(feedback_type)
        
        if expiry_days is None:
            return None
        
        expiry_dt = datetime.now() + timedelta(days=expiry_days)
        return expiry_dt.isoformat()