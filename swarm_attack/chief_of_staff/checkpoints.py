"""Checkpoint and CheckpointStore for human-in-the-loop checkpoints.

This module provides data models and persistent storage for checkpoints
that require human approval before proceeding.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    from swarm_attack.memory.store import MemoryStore


class CheckpointTriggerKind(Enum):
    """Triggers that cause a checkpoint to be created."""

    UX_CHANGE = "UX_CHANGE"
    COST_SINGLE = "COST_SINGLE"
    COST_CUMULATIVE = "COST_CUMULATIVE"
    ARCHITECTURE = "ARCHITECTURE"
    SCOPE_CHANGE = "SCOPE_CHANGE"
    HICCUP = "HICCUP"


# Alias for backwards compatibility (internal code uses these)
CheckpointTriggerType = CheckpointTriggerKind
CheckpointTriggerEnum = CheckpointTriggerKind


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


# Alias: tests expect CheckpointTrigger to be the dataclass with trigger_type, reason, action
CheckpointTrigger = TriggerCheckResult

# Also expose enum values on CheckpointTrigger for backward compatibility
# (some tests use CheckpointTrigger.COST_SINGLE as if it's an enum)
CheckpointTrigger.UX_CHANGE = CheckpointTriggerKind.UX_CHANGE
CheckpointTrigger.COST_SINGLE = CheckpointTriggerKind.COST_SINGLE
CheckpointTrigger.COST_CUMULATIVE = CheckpointTriggerKind.COST_CUMULATIVE
CheckpointTrigger.ARCHITECTURE = CheckpointTriggerKind.ARCHITECTURE
CheckpointTrigger.SCOPE_CHANGE = CheckpointTriggerKind.SCOPE_CHANGE
CheckpointTrigger.HICCUP = CheckpointTriggerKind.HICCUP


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

    async def _load_all(self) -> list[Checkpoint]:
        """Load all checkpoints from disk.

        Returns:
            List of all checkpoints.
        """
        checkpoints = []

        if not self.base_path.exists():
            return checkpoints

        for file_path in self.base_path.glob("*.json"):
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()

            try:
                data = json.loads(content)
                checkpoints.append(Checkpoint.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                # Skip corrupted files
                continue

        return checkpoints

    async def _delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint from disk.

        Args:
            checkpoint_id: The ID of the checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"

        if not file_path.exists():
            return False

        try:
            await aiofiles.os.remove(file_path)
            return True
        except OSError:
            return False

    async def cleanup_stale_checkpoints(self, max_age_hours: int = 24) -> int:
        """Remove checkpoints older than max_age_hours (async).

        Args:
            max_age_hours: Maximum age in hours before a pending checkpoint is stale.

        Returns:
            Number of checkpoints removed.
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = 0

        for checkpoint in await self._load_all():
            try:
                created_at = datetime.fromisoformat(checkpoint.created_at.replace("Z", "+00:00"))
                # Make it naive for comparison if needed
                if created_at.tzinfo is not None:
                    created_at = created_at.replace(tzinfo=None)
            except ValueError:
                # Skip checkpoints with invalid timestamps
                continue

            if created_at < cutoff and checkpoint.status == "pending":
                if await self._delete(checkpoint.checkpoint_id):
                    removed += 1

        return removed

    def cleanup_stale_checkpoints_sync(self, max_age_days: int = 7) -> list[str]:
        """Remove checkpoints older than max_age_days (sync version using StateCleanupJob).

        This method uses the StateCleanupJob for cleanup. Note: StateCleanupJob
        only removes files that have 'lifecycle' metadata. Checkpoints without
        lifecycle metadata are removed by checking created_at directly.

        Args:
            max_age_days: Maximum age in days before removal.

        Returns:
            List of checkpoint IDs that were removed.
        """
        from swarm_attack.state.lifecycle import StateCleanupJob

        removed_ids: list[str] = []

        if not self.base_path.exists():
            return removed_ids

        # First, try StateCleanupJob for files with lifecycle metadata
        cleanup = StateCleanupJob(self.base_path, max_age_days=max_age_days)
        removed_files = cleanup.run()
        removed_ids.extend([f.stem for f in removed_files])

        # Also cleanup checkpoints without lifecycle metadata by checking created_at
        cutoff = datetime.now() - timedelta(days=max_age_days)
        for state_file in self.base_path.glob("*.json"):
            if state_file.stem in removed_ids:
                continue  # Already removed by StateCleanupJob

            try:
                data = json.loads(state_file.read_text())

                # Skip if has lifecycle (handled by StateCleanupJob)
                if "lifecycle" in data:
                    continue

                # Check created_at directly
                created_at_str = data.get("created_at", "")
                if not created_at_str:
                    continue

                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if created_at.tzinfo is not None:
                    created_at = created_at.replace(tzinfo=None)

                if created_at < cutoff:
                    state_file.unlink()
                    removed_ids.append(state_file.stem)

            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                continue

        return removed_ids

    async def deduplicate_pending(self) -> int:
        """Remove duplicate pending checkpoints, keeping newest.

        Groups checkpoints by trigger type + goal_id and removes older duplicates.

        Returns:
            Number of duplicates removed.
        """
        pending = [cp for cp in await self._load_all() if cp.status == "pending"]

        # Group by (trigger type, goal_id)
        groups: dict[tuple[str, str], list[Checkpoint]] = {}
        for cp in pending:
            key = (cp.trigger.value, cp.goal_id)
            if key not in groups:
                groups[key] = []
            groups[key].append(cp)

        removed = 0
        for key, cps in groups.items():
            if len(cps) > 1:
                # Sort by created_at descending (newest first)
                cps.sort(key=lambda x: x.created_at, reverse=True)
                # Keep newest, remove rest
                for old_cp in cps[1:]:
                    if await self._delete(old_cp.checkpoint_id):
                        removed += 1

        return removed


# Tags that trigger UX_CHANGE (case-insensitive)
UX_CHANGE_TAGS = {"ui", "ux", "frontend"}

# Tags that trigger ARCHITECTURE (case-insensitive)
ARCHITECTURE_TAGS = {"architecture", "refactor", "core"}


# Context templates per trigger type
CONTEXT_TEMPLATES = {
    CheckpointTriggerKind.UX_CHANGE: (
        "This goal involves UI/UX changes that may affect user experience. "
        "Goal: {description}. Tags: {tags}. "
        "Review recommended before proceeding with user-facing changes."
    ),
    CheckpointTriggerKind.COST_SINGLE: (
        "This goal has a high estimated cost of ${cost:.2f} USD, which exceeds "
        "the single-task cost threshold. Goal: {description}. "
        "Consider whether the cost is justified for this task."
    ),
    CheckpointTriggerKind.COST_CUMULATIVE: (
        "Daily cumulative cost budget has been exceeded. "
        "Current daily spend: ${daily_cost:.2f} USD. Goal: {description}. "
        "Consider pausing to review overall spending before continuing."
    ),
    CheckpointTriggerKind.ARCHITECTURE: (
        "This goal involves architectural or structural changes to the codebase. "
        "Goal: {description}. Tags: {tags}. "
        "Architectural changes may have wide-reaching impacts and should be reviewed."
    ),
    CheckpointTriggerKind.SCOPE_CHANGE: (
        "This is an unplanned goal that was not in the original scope. "
        "Goal: {description}. "
        "Review whether this unplanned work should take priority over planned work."
    ),
    CheckpointTriggerKind.HICCUP: (
        "This goal has encountered issues or errors during execution. "
        "Goal: {description}. Error count: {error_count}. "
        "Review the errors before deciding how to proceed."
    ),
}

# Recommendation templates per trigger type
RECOMMENDATION_TEMPLATES = {
    CheckpointTriggerKind.UX_CHANGE: (
        "Recommend proceeding with caution. UI/UX changes should be validated "
        "against design specifications and user expectations."
    ),
    CheckpointTriggerKind.COST_SINGLE: (
        "Recommend proceeding if the task is critical. Consider breaking down "
        "into smaller tasks if cost can be reduced."
    ),
    CheckpointTriggerKind.COST_CUMULATIVE: (
        "Recommend reviewing daily progress before continuing. Consider whether "
        "remaining budget should be preserved for higher-priority work."
    ),
    CheckpointTriggerKind.ARCHITECTURE: (
        "Recommend careful review of architectural changes. Ensure changes align "
        "with overall system design and don't introduce technical debt."
    ),
    CheckpointTriggerKind.SCOPE_CHANGE: (
        "Recommend evaluating priority. Unplanned work may indicate emergent "
        "requirements or scope creep. Assess impact on planned goals."
    ),
    CheckpointTriggerKind.HICCUP: (
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

    def __init__(
        self,
        config: Any = None,
        store: Optional[CheckpointStore] = None,
        memory_store: Optional["MemoryStore"] = None,
    ):
        """Initialize the checkpoint system.

        Args:
            config: Configuration (optional).
            store: CheckpointStore for persistence (optional).
            memory_store: MemoryStore for cross-session learning (optional).
        """
        self.config = config
        self.store = store or CheckpointStore()
        self._memory = memory_store
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
            triggers.append(CheckpointTriggerKind.UX_CHANGE)

        # COST_SINGLE: estimated_cost_usd > config.checkpoint_cost_single
        if goal.estimated_cost_usd is not None and self.config is not None:
            cost_single_threshold = getattr(self.config, "checkpoint_cost_single", 5.0)
            if goal.estimated_cost_usd > cost_single_threshold:
                triggers.append(CheckpointTriggerKind.COST_SINGLE)

        # COST_CUMULATIVE: daily_cost > config.checkpoint_cost_daily
        if self.config is not None:
            cost_daily_threshold = getattr(self.config, "checkpoint_cost_daily", 15.0)
            if self.daily_cost > cost_daily_threshold:
                triggers.append(CheckpointTriggerKind.COST_CUMULATIVE)

        # ARCHITECTURE: tags contain architecture, refactor, core
        if goal_tags_lower & ARCHITECTURE_TAGS:
            triggers.append(CheckpointTriggerKind.ARCHITECTURE)

        # SCOPE_CHANGE: is_unplanned == True
        if goal.is_unplanned:
            triggers.append(CheckpointTriggerKind.SCOPE_CHANGE)

        # HICCUP: error_count > 0 or is_hiccup == True
        if goal.error_count > 0 or goal.is_hiccup:
            triggers.append(CheckpointTriggerKind.HICCUP)

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

    async def check_before_execution(self, goal: "DailyGoal") -> CheckpointResult:
        """Check if a goal requires approval before execution.

        This method:
        1. Returns an existing pending checkpoint if one exists for the goal
        2. Creates a new checkpoint if triggers are detected and none is pending
        3. Returns CheckpointResult(requires_approval=False) if no triggers

        Args:
            goal: The DailyGoal to check before execution.

        Returns:
            CheckpointResult indicating whether approval is required.
        """
        # Check for existing pending checkpoint for this goal
        pending_checkpoint = await self.store.get_pending_for_goal(goal.goal_id)
        if pending_checkpoint is not None:
            return CheckpointResult(
                requires_approval=True,
                approved=False,
                checkpoint=pending_checkpoint,
            )

        # Detect triggers for this goal
        triggers = self._detect_triggers(goal)
        if not triggers:
            return CheckpointResult(
                requires_approval=False,
                approved=True,
                checkpoint=None,
            )

        # Create new checkpoint for the most significant trigger (first in list)
        checkpoint = self._create_checkpoint(goal, triggers[0])
        await self.store.save(checkpoint)

        return CheckpointResult(
            requires_approval=True,
            approved=False,
            checkpoint=checkpoint,
        )

    def update_daily_cost(self, cost: float) -> None:
        """Increment daily cost tracking.

        Args:
            cost: The cost to add to daily total.
        """
        self.daily_cost += cost

    def reset_daily_cost(self) -> None:
        """Reset daily cost tracking to zero."""
        self.daily_cost = 0.0

    async def resolve_checkpoint(
        self,
        checkpoint_id: str,
        chosen_option: str,
        notes: str,
    ) -> Checkpoint:
        """Resolve a checkpoint with user's choice.

        Args:
            checkpoint_id: The ID of the checkpoint to resolve.
            chosen_option: The option chosen by the user.
            notes: Human notes/feedback about the decision.

        Returns:
            The resolved Checkpoint.

        Raises:
            KeyError: If checkpoint_id is not found.
        """
        from datetime import datetime

        checkpoint = await self.store.get(checkpoint_id)
        if checkpoint is None:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        # Set status based on chosen option
        if chosen_option == "Proceed":
            checkpoint.status = "approved"
        else:
            # Skip, Modify, Pause all set status to rejected
            checkpoint.status = "rejected"

        # Store the chosen option and notes
        checkpoint.chosen_option = chosen_option
        checkpoint.human_notes = notes
        checkpoint.resolved_at = datetime.now().isoformat()

        # Save the updated checkpoint
        await self.store.save(checkpoint)

        # Record decision in memory layer for cross-session learning
        if self._memory is not None:
            from uuid import uuid4
            from swarm_attack.memory.store import MemoryEntry

            self._memory.add(MemoryEntry(
                id=str(uuid4()),
                category="checkpoint_decision",
                feature_id=checkpoint.goal_id,
                issue_number=None,
                content={
                    "trigger": checkpoint.trigger.value,
                    "context": checkpoint.context[:500],  # Truncate for storage
                    "decision": chosen_option,
                    "notes": notes[:200] if notes else None,
                },
                outcome="applied",
                created_at=datetime.now().isoformat(),
                tags=[checkpoint.trigger.value, chosen_option],
            ))
            self._memory.save()

        return checkpoint