"""Checkpoint and CheckpointStore for human-in-the-loop checkpoints.

This module provides data models and persistent storage for checkpoints
that require human approval before proceeding.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import aiofiles
import aiofiles.os


class CheckpointTrigger(Enum):
    """Triggers that cause a checkpoint to be created."""
    
    UX_CHANGE = "UX_CHANGE"
    COST_SINGLE = "COST_SINGLE"
    COST_CUMULATIVE = "COST_CUMULATIVE"
    ARCHITECTURE = "ARCHITECTURE"
    SCOPE_CHANGE = "SCOPE_CHANGE"
    HICCUP = "HICCUP"


@dataclass
class CheckpointOption:
    """An option presented to the human at a checkpoint."""
    
    label: str
    description: str
    is_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "label": self.label,
            "description": self.description,
            "is_recommended": self.is_recommended,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointOption":
        """Deserialize from dictionary."""
        return cls(
            label=data["label"],
            description=data["description"],
            is_recommended=data.get("is_recommended", False),
        )


@dataclass
class Checkpoint:
    """A human-in-the-loop checkpoint requiring approval.
    
    Checkpoints are created when the system encounters a situation
    that requires human decision-making before proceeding.
    """
    
    checkpoint_id: str
    trigger: CheckpointTrigger
    context: str
    options: list[CheckpointOption]
    recommendation: str
    created_at: str
    goal_id: str
    status: str = "pending"
    chosen_option: Optional[str] = None
    human_notes: Optional[str] = None
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "trigger": self.trigger.value,
            "context": self.context,
            "options": [opt.to_dict() for opt in self.options],
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "goal_id": self.goal_id,
            "status": self.status,
            "chosen_option": self.chosen_option,
            "human_notes": self.human_notes,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Deserialize from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            trigger=CheckpointTrigger(data["trigger"]),
            context=data["context"],
            options=[CheckpointOption.from_dict(opt) for opt in data.get("options", [])],
            recommendation=data["recommendation"],
            created_at=data["created_at"],
            goal_id=data["goal_id"],
            status=data.get("status", "pending"),
            chosen_option=data.get("chosen_option"),
            human_notes=data.get("human_notes"),
            resolved_at=data.get("resolved_at"),
        )


@dataclass
class CheckpointResult:
    """Result of checking if a checkpoint is needed."""
    
    requires_approval: bool
    approved: Optional[bool] = None
    checkpoint: Optional[Checkpoint] = None


class CheckpointStore:
    """Persistent storage for checkpoints.
    
    Stores checkpoints as individual JSON files in the checkpoints directory.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the checkpoint store.
        
        Args:
            base_path: Directory to store checkpoints. Defaults to
                      .swarm/chief-of-staff/checkpoints/
        """
        if base_path is None:
            base_path = Path.cwd() / ".swarm" / "chief-of-staff" / "checkpoints"
        self.base_path = base_path

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint to disk.
        
        Args:
            checkpoint: The checkpoint to save.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        file_path = self.base_path / f"{checkpoint.checkpoint_id}.json"
        content = json.dumps(checkpoint.to_dict(), indent=2)
        
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(content)

    async def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint by ID.
        
        Args:
            checkpoint_id: The ID of the checkpoint to load.
            
        Returns:
            The checkpoint if found, None otherwise.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"
        
        if not file_path.exists():
            return None
        
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
        
        data = json.loads(content)
        return Checkpoint.from_dict(data)

    async def get_pending_for_goal(self, goal_id: str) -> Optional[Checkpoint]:
        """Find a pending checkpoint for a specific goal.
        
        Args:
            goal_id: The goal ID to search for.
            
        Returns:
            The pending checkpoint if found, None otherwise.
        """
        if not self.base_path.exists():
            return None
        
        for file_path in self.base_path.glob("*.json"):
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            data = json.loads(content)
            if data.get("goal_id") == goal_id and data.get("status") == "pending":
                return Checkpoint.from_dict(data)
        
        return None

    async def list_pending(self) -> list[Checkpoint]:
        """List all pending checkpoints.
        
        Returns:
            List of all checkpoints with status "pending".
        """
        pending = []
        
        if not self.base_path.exists():
            return pending
        
        for file_path in self.base_path.glob("*.json"):
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
            
            data = json.loads(content)
            if data.get("status") == "pending":
                pending.append(Checkpoint.from_dict(data))

        return pending


class CheckpointSystem:
    """System for detecting checkpoint triggers.

    Stub implementation - full implementation in Issue #7.
    """

    def __init__(self, config: Any = None, store: Optional[CheckpointStore] = None):
        """Initialize the checkpoint system.

        Args:
            config: Configuration (optional).
            store: CheckpointStore for persistence (optional).
        """
        self.config = config
        self.store = store or CheckpointStore()
        self._error_count = 0

    def check_triggers(self, context: Any, action: str) -> Optional[CheckpointTrigger]:
        """Check if any checkpoint triggers are met.

        Stub - always returns None (no trigger).
        Full implementation in Issue #7.
        """
        return None

    def reset_error_count(self) -> None:
        """Reset the consecutive error counter."""
        self._error_count = 0

    def record_error(self) -> None:
        """Record an error for tracking consecutive failures."""
        self._error_count += 1