"""Checkpoint and CheckpointStore for human-in-the-loop checkpoints.

This module provides data models and persistent storage for checkpoints
that require human approval before proceeding.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import json
import uuid
import aiofiles
import aiofiles.os

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal
    from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class CheckpointTrigger(Enum):
    """Triggers that cause a checkpoint to be created."""

    UX_CHANGE = "UX_CHANGE"
    COST_SINGLE = "COST_SINGLE"
    COST_CUMULATIVE = "COST_CUMULATIVE"
    ARCHITECTURE = "ARCHITECTURE"
    SCOPE_CHANGE = "SCOPE_CHANGE"
    HICCUP = "HICCUP"


# Alias for backwards compatibility
CheckpointTriggerType = CheckpointTrigger
CheckpointTriggerEnum = CheckpointTrigger


@dataclass
class TriggerCheckResult:
    """Result of a checkpoint trigger check."""

    trigger_type: str
    reason: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trigger_type": self.trigger_type,
            "reason": self.reason,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerCheckResult":
        """Deserialize from dictionary."""
        return cls(
            trigger_type=data["trigger_type"],
            reason=data["reason"],
            action=data["action"],
        )


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
    trigger: CheckpointTriggerType
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
            trigger=CheckpointTriggerType(data["trigger"]),
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


# Tags that trigger UX_CHANGE (case-insensitive)
UX_CHANGE_TAGS = {"ui", "ux", "frontend"}

# Tags that trigger ARCHITECTURE (case-insensitive)
ARCHITECTURE_TAGS = {"architecture", "refactor", "core"}


# Context templates per trigger type
CONTEXT_TEMPLATES = {
    CheckpointTrigger.UX_CHANGE: (
        "This goal involves UI/UX changes that may affect user experience. "
        "Goal: {description}. Tags: {tags}. "
        "Review recommended before proceeding with user-facing changes."
    ),
    CheckpointTrigger.COST_SINGLE: (
        "This goal has a high estimated cost of ${cost:.2f} USD, which exceeds "
        "the single-task cost threshold. Goal: {description}. "
        "Consider whether the cost is justified for this task."
    ),
    CheckpointTrigger.COST_CUMULATIVE: (
        "Daily cumulative cost budget has been exceeded. "
        "Current daily spend: ${daily_cost:.2f} USD. Goal: {description}. "
        "Consider pausing to review overall spending before continuing."
    ),
    CheckpointTrigger.ARCHITECTURE: (
        "This goal involves architectural or structural changes to the codebase. "
        "Goal: {description}. Tags: {tags}. "
        "Architectural changes may have wide-reaching impacts and should be reviewed."
    ),
    CheckpointTrigger.SCOPE_CHANGE: (
        "This is an unplanned goal that was not in the original scope. "
        "Goal: {description}. "
        "Review whether this unplanned work should take priority over planned work."
    ),
    CheckpointTrigger.HICCUP: (
        "This goal has encountered issues or errors during execution. "
        "Goal: {description}. Error count: {error_count}. "
        "Review the errors before deciding how to proceed."
    ),
}

# Recommendation templates per trigger type
RECOMMENDATION_TEMPLATES = {
    CheckpointTrigger.UX_CHANGE: (
        "Recommend proceeding with caution. UI/UX changes should be validated "
        "against design specifications and user expectations."
    ),
    CheckpointTrigger.COST_SINGLE: (
        "Recommend proceeding if the task is critical. Consider breaking down "
        "into smaller tasks if cost can be reduced."
    ),
    CheckpointTrigger.COST_CUMULATIVE: (
        "Recommend reviewing daily progress before continuing. Consider whether "
        "remaining budget should be preserved for higher-priority work."
    ),
    CheckpointTrigger.ARCHITECTURE: (
        "Recommend careful review of architectural changes. Ensure changes align "
        "with overall system design and don't introduce technical debt."
    ),
    CheckpointTrigger.SCOPE_CHANGE: (
        "Recommend evaluating priority. Unplanned work may indicate emergent "
        "requirements or scope creep. Assess impact on planned goals."
    ),
    CheckpointTrigger.HICCUP: (
        "Recommend reviewing errors before proceeding. Determine if issues are "
        "transient or indicate a deeper problem requiring investigation."
    ),
}


class CheckpointSystem:
    """System for detecting checkpoint triggers.

    Implements trigger detection for autopilot sessions including:
    - Stop triggers (user-defined stop conditions)
    - Cost/budget triggers
    - Time/duration triggers
    - Approval-required action detection
    - High-risk action detection
    - Error streak detection
    - Blocker detection
    """

    # High-risk keywords for action detection
    HIGH_RISK_KEYWORDS = [
        "architecture", "architectural",
        "main", "master",  # branch names
        "delete", "drop", "rm -rf", "force push",
        "push to main", "push to master", "merge to main", "merge to master",
    ]

    # Keywords that require approval
    APPROVAL_KEYWORDS = ["approve", "approval", "confirm", "review"]

    def __init__(self, config: Any = None, store: Optional[CheckpointStore] = None):
        """Initialize the checkpoint system.

        Args:
            config: Configuration (optional).
            store: CheckpointStore for persistence (optional).
        """
        self.config = config
        self.store = store or CheckpointStore()
        self._error_count = 0
        self.daily_cost = 0.0

    def _detect_triggers(self, goal: "DailyGoal") -> list[CheckpointTrigger]:
        """Detect which checkpoint triggers apply to a goal.

        Checks the goal's properties against trigger conditions:
        - UX_CHANGE: tags contain ui, ux, frontend (case-insensitive)
        - COST_SINGLE: estimated_cost_usd > config.checkpoint_cost_single
        - COST_CUMULATIVE: daily_cost > config.checkpoint_cost_daily
        - ARCHITECTURE: tags contain architecture, refactor, core (case-insensitive)
        - SCOPE_CHANGE: is_unplanned == True
        - HICCUP: error_count > 0 or is_hiccup == True

        Args:
            goal: The DailyGoal to check for triggers.

        Returns:
            List of CheckpointTrigger enums that apply to this goal.
        """
        triggers: list[CheckpointTrigger] = []

        # Get tags as lowercase set for case-insensitive comparison
        goal_tags_lower = {tag.lower() for tag in goal.tags} if goal.tags else set()

        # UX_CHANGE: tags contain ui, ux, frontend
        if goal_tags_lower & UX_CHANGE_TAGS:
            triggers.append(CheckpointTrigger.UX_CHANGE)

        # COST_SINGLE: estimated_cost_usd > config.checkpoint_cost_single
        if goal.estimated_cost_usd is not None and self.config is not None:
            cost_single_threshold = getattr(self.config, "checkpoint_cost_single", 5.0)
            if goal.estimated_cost_usd > cost_single_threshold:
                triggers.append(CheckpointTrigger.COST_SINGLE)

        # COST_CUMULATIVE: daily_cost > config.checkpoint_cost_daily
        if self.config is not None:
            cost_daily_threshold = getattr(self.config, "checkpoint_cost_daily", 15.0)
            if self.daily_cost > cost_daily_threshold:
                triggers.append(CheckpointTrigger.COST_CUMULATIVE)

        # ARCHITECTURE: tags contain architecture, refactor, core
        if goal_tags_lower & ARCHITECTURE_TAGS:
            triggers.append(CheckpointTrigger.ARCHITECTURE)

        # SCOPE_CHANGE: is_unplanned == True
        if goal.is_unplanned:
            triggers.append(CheckpointTrigger.SCOPE_CHANGE)

        # HICCUP: error_count > 0 or is_hiccup == True
        if goal.error_count > 0 or goal.is_hiccup:
            triggers.append(CheckpointTrigger.HICCUP)

        return triggers

    def _create_checkpoint(self, goal: "DailyGoal", trigger: CheckpointTrigger) -> Checkpoint:
        """Create a checkpoint for a goal and trigger.

        Args:
            goal: The DailyGoal that triggered the checkpoint.
            trigger: The trigger type that caused this checkpoint.

        Returns:
            A new Checkpoint instance with context, options, and recommendation.
        """
        checkpoint_id = f"chk-{uuid.uuid4().hex[:12]}"
        context = self._build_context(goal, trigger)
        options = self._build_options(goal, trigger)
        recommendation = self._build_recommendation(goal, trigger)
        created_at = datetime.now().isoformat()

        return Checkpoint(
            checkpoint_id=checkpoint_id,
            trigger=trigger,
            context=context,
            options=options,
            recommendation=recommendation,
            created_at=created_at,
            goal_id=goal.goal_id,
            status="pending",
        )

    def _build_context(self, goal: "DailyGoal", trigger: CheckpointTrigger) -> str:
        """Build context string for a checkpoint.

        Args:
            goal: The DailyGoal for context.
            trigger: The trigger type.

        Returns:
            Context string describing the situation.
        """
        template = CONTEXT_TEMPLATES.get(trigger, "Goal: {description}")
        
        # Build format kwargs
        tags_str = ", ".join(goal.tags) if goal.tags else "none"
        cost = goal.estimated_cost_usd if goal.estimated_cost_usd is not None else 0.0
        
        return template.format(
            description=goal.description,
            tags=tags_str,
            cost=cost,
            daily_cost=self.daily_cost,
            error_count=goal.error_count,
        )

    def _build_options(self, goal: "DailyGoal", trigger: CheckpointTrigger) -> list[CheckpointOption]:
        """Build options for a checkpoint.

        Returns the standard four options: Proceed, Skip, Modify, Pause.
        Proceed is marked as is_recommended for most triggers.

        Args:
            goal: The DailyGoal (unused but kept for consistency).
            trigger: The trigger type (unused but kept for consistency).

        Returns:
            List of four CheckpointOption instances.
        """
        return [
            CheckpointOption(
                label="Proceed",
                description="Continue with the goal as planned.",
                is_recommended=True,
            ),
            CheckpointOption(
                label="Skip",
                description="Skip this goal and move to the next one.",
                is_recommended=False,
            ),
            CheckpointOption(
                label="Modify",
                description="Modify the goal before proceeding.",
                is_recommended=False,
            ),
            CheckpointOption(
                label="Pause",
                description="Pause the session for manual review.",
                is_recommended=False,
            ),
        ]

    def _build_recommendation(self, goal: "DailyGoal", trigger: CheckpointTrigger) -> str:
        """Build recommendation string for a checkpoint.

        Args:
            goal: The DailyGoal (unused but kept for consistency).
            trigger: The trigger type.

        Returns:
            Recommendation string.
        """
        return RECOMMENDATION_TEMPLATES.get(
            trigger,
            "Recommend reviewing the situation before proceeding."
        )

    def check_triggers(self, session: Any, action: str) -> Optional[TriggerCheckResult]:
        """Check if any checkpoint triggers are met.

        Checks triggers in priority order:
        1. Stop trigger (user-defined)
        2. Cost/budget exceeded
        3. Time/duration exceeded
        4. Approval required
        5. High-risk action
        6. Error streak exceeded
        7. Blocker detected

        Args:
            session: The autopilot session with cost/time/trigger info.
            action: The action about to be performed.

        Returns:
            CheckpointTrigger if a trigger is met, None otherwise.
        """
        # 1. Check stop trigger first (highest priority)
        if self.matches_stop_trigger(session, action):
            return TriggerCheckResult(
                trigger_type="stop_trigger",
                reason=f"Stop trigger matched: {getattr(session, 'stop_trigger', '')}",
                action="pause session",
            )

        # 2. Check cost/budget
        budget_usd = getattr(self.config, 'budget_usd', None) if self.config else None
        if budget_usd is not None:
            total_cost = getattr(session, 'total_cost_usd', 0)
            if total_cost > budget_usd:
                return TriggerCheckResult(
                    trigger_type="cost",
                    reason=f"Budget exceeded: ${total_cost:.2f} > ${budget_usd:.2f}",
                    action="pause session",
                )

        # 3. Check time/duration
        duration_minutes = getattr(self.config, 'duration_minutes', None) if self.config else None
        if duration_minutes is not None:
            elapsed = getattr(session, 'elapsed_minutes', 0)
            if elapsed > duration_minutes:
                return TriggerCheckResult(
                    trigger_type="time",
                    reason=f"Duration exceeded: {elapsed}m > {duration_minutes}m",
                    action="pause session",
                )

        # 4. Check approval required
        if self.should_pause_for_approval(action):
            return TriggerCheckResult(
                trigger_type="approval",
                reason=f"Action requires approval: {action}",
                action="request approval",
            )

        # 5. Check high-risk action
        if self.is_high_risk(action):
            return TriggerCheckResult(
                trigger_type="high_risk",
                reason=f"High-risk action detected: {action}",
                action="require approval",
            )

        # 6. Check error streak
        error_streak = getattr(self.config, 'error_streak', 3) if self.config else 3
        if self._error_count >= error_streak:
            return TriggerCheckResult(
                trigger_type="errors",
                reason=f"Error streak: {self._error_count} consecutive errors",
                action="pause session",
            )

        # 7. Check blocker
        is_blocked = getattr(session, 'is_blocked', False)
        if is_blocked:
            return TriggerCheckResult(
                trigger_type="blocker",
                reason="Session is blocked",
                action="pause session",
            )

        return None

    def matches_stop_trigger(self, session: Any, action: str) -> bool:
        """Check if the action matches the session's stop trigger.

        Args:
            session: The autopilot session with stop_trigger attribute.
            action: The action to check.

        Returns:
            True if the action matches the stop trigger.
        """
        stop_trigger = getattr(session, 'stop_trigger', None)
        if not stop_trigger:
            return False

        # Case-insensitive contains check
        return stop_trigger.lower() in action.lower()

    def is_high_risk(self, action: str) -> bool:
        """Check if an action is high-risk.

        High-risk actions include:
        - Architectural changes
        - Pushing to main/master branch
        - Destructive operations (delete, drop, rm -rf, force push)

        Args:
            action: The action to check.

        Returns:
            True if the action is high-risk.
        """
        action_lower = action.lower()
        return any(keyword in action_lower for keyword in self.HIGH_RISK_KEYWORDS)

    def should_pause_for_approval(self, action: str) -> bool:
        """Check if an action requires approval before proceeding.

        Args:
            action: The action to check.

        Returns:
            True if the action requires approval.
        """
        action_lower = action.lower()
        return any(keyword in action_lower for keyword in self.APPROVAL_KEYWORDS)

    def reset_error_count(self) -> None:
        """Reset the consecutive error counter."""
        self._error_count = 0

    def record_error(self) -> None:
        """Record an error for tracking consecutive failures."""
        self._error_count += 1