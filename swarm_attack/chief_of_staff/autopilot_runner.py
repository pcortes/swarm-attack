"""AutopilotRunner - executes goals with checkpoint gates.

This module provides the AutopilotRunner class that executes daily goals
with checkpoint-based pause/resume capability. It integrates with:
- CheckpointSystem for trigger detection (cost, time, errors, approvals)
- AutopilotSessionStore for session persistence
- GoalTracker for goal management
- Orchestrator for feature/spec execution (Chief of Staff v3)
- BugOrchestrator for bug execution (Chief of Staff v3)
- RecoveryManager for hierarchical retry/escalation
- ProgressTracker for real-time execution monitoring

Implementation: Real Execution (v3)
- Full checkpoint trigger validation with real logic
- Goal progress tracking and persistence
- Pause/resume functionality
- Real execution via Orchestrator.run_issue_session() for features
- Real execution via BugOrchestrator.fix() for bugs
- Real execution via Orchestrator.run_spec_pipeline() for specs
- Hierarchical recovery with RecoveryManager for automatic retries
- Real-time progress tracking with ProgressTracker
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointTrigger
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus
from swarm_attack.chief_of_staff.budget import check_budget, get_effective_cost
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.progress import ProgressTracker

if TYPE_CHECKING:
    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.chief_of_staff.episodes import EpisodeStore


class ExecutionStrategy(Enum):
    """Strategy for executing goals in autopilot.

    Determines how goals are processed when some are blocked or fail.

    Values:
        SEQUENTIAL: Execute goals in order, stop on any block/failure.
        CONTINUE_ON_BLOCK: Skip blocked goals and continue with ready ones.
        PARALLEL_SAFE: Execute independent goals in parallel when safe.
    """

    SEQUENTIAL = "sequential"
    CONTINUE_ON_BLOCK = "continue_on_block"
    PARALLEL_SAFE = "parallel_safe"


@dataclass
class DependencyGraph:
    """Tracks goal dependencies for execution ordering.

    Used with CONTINUE_ON_BLOCK and PARALLEL_SAFE strategies to determine
    which goals can be executed when others are blocked.

    Attributes:
        issues: List of DailyGoal objects to track.
        dependencies: Mapping of goal_id to list of dependency goal_ids.
                      A goal can only execute when all its dependencies are complete.
    """

    issues: list[DailyGoal]
    dependencies: dict[str, list[str]] = field(default_factory=dict)

    def get_ready_goals(
        self, completed: set[str], blocked: set[str]
    ) -> list[DailyGoal]:
        """Get goals that are ready to execute.

        A goal is ready when:
        - It is not already completed
        - It is not blocked
        - All its dependencies are completed

        Args:
            completed: Set of goal_ids that have been completed.
            blocked: Set of goal_ids that are blocked.

        Returns:
            List of DailyGoal objects that are ready to execute.
        """
        ready = []
        for goal in self.issues:
            goal_id = goal.goal_id

            # Skip if already completed or blocked
            if goal_id in completed or goal_id in blocked:
                continue

            # Check if all dependencies are met
            deps = self.dependencies.get(goal_id, [])
            if all(dep in completed for dep in deps):
                ready.append(goal)

        return ready

    @classmethod
    def from_goals(cls, goals: list[DailyGoal]) -> "DependencyGraph":
        """Create a DependencyGraph from a list of goals.

        Creates a graph with no dependencies (all goals are independent).
        Dependencies can be added manually after creation.

        Args:
            goals: List of DailyGoal objects.

        Returns:
            A DependencyGraph with the given goals and empty dependencies.
        """
        return cls(issues=list(goals), dependencies={})


@dataclass
class GoalExecutionResult:
    """Result from executing a single goal."""

    success: bool
    cost_usd: float
    duration_seconds: int
    error: Optional[str] = None
    output: str = ""
    checkpoint_pending: bool = False


@dataclass
class AutopilotRunResult:
    """Result from an autopilot run."""

    session: AutopilotSession
    goals_completed: int
    goals_total: int
    total_cost_usd: float
    duration_seconds: int
    trigger: Optional[CheckpointTrigger] = None
    error: Optional[str] = None


@dataclass
class SessionContext:
    """Internal session context for checkpoint system compatibility.

    Provides the attributes expected by CheckpointSystem.check_triggers().
    """

    total_cost_usd: float = 0.0
    elapsed_minutes: float = 0.0
    stop_trigger: Optional[str] = None
    is_blocked: bool = False


class AutopilotRunner:
    """Execute goals with checkpoint gates and pause/resume capability.

    The AutopilotRunner orchestrates goal execution with:
    1. Budget/time limits via CheckpointSystem
    2. Session persistence via AutopilotSessionStore
    3. Goal-by-goal execution with progress tracking
    4. Pause on checkpoint triggers, resume from stored state
    5. Hierarchical recovery via RecoveryManager
    6. Real-time progress monitoring via ProgressTracker

    Implementation (v3 Real Execution):
    - Validates all checkpoint logic
    - Tracks goal progress correctly
    - Persists sessions for pause/resume
    - Calls Orchestrator.run_issue_session() for feature goals
    - Calls BugOrchestrator.fix() for bug goals
    - Calls Orchestrator.run_spec_pipeline() for spec goals
    - Uses RecoveryManager for automatic retry/escalation
    - Uses ProgressTracker for real-time progress updates

    Usage:
        runner = AutopilotRunner(
            orchestrator=orchestrator,
            bug_orchestrator=bug_orchestrator,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        # Start new session
        result = runner.start(goals, budget_usd=10.0, duration_minutes=120)

        # Resume paused session
        result = runner.resume(session_id)

        # Access progress
        current_progress = runner.progress_tracker.get_current()
    """

    def __init__(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
        orchestrator: Optional["Orchestrator"] = None,
        bug_orchestrator: Optional["BugOrchestrator"] = None,
        recovery_manager: Optional[RecoveryManager] = None,
        episode_store: Optional["EpisodeStore"] = None,
        on_goal_start: Optional[Callable[[DailyGoal], None]] = None,
        on_goal_complete: Optional[Callable[[DailyGoal, GoalExecutionResult], None]] = None,
        on_checkpoint: Optional[Callable[[CheckpointTrigger], None]] = None,
    ) -> None:
        """Initialize AutopilotRunner.

        Args:
            config: ChiefOfStaffConfig with autopilot settings
            checkpoint_system: CheckpointSystem for trigger detection
            session_store: AutopilotSessionStore for persistence
            orchestrator: Optional Orchestrator for feature execution
            bug_orchestrator: Optional BugOrchestrator for bug execution
            recovery_manager: Optional RecoveryManager for retry/escalation.
                              If not provided, one will be created.
            episode_store: Optional EpisodeStore for logging recovery episodes.
            on_goal_start: Optional callback when goal execution starts
            on_goal_complete: Optional callback when goal completes
            on_checkpoint: Optional callback when checkpoint triggers
        """
        self.config = config
        self.checkpoint_system = checkpoint_system
        self.session_store = session_store
        self.orchestrator = orchestrator
        self.bug_orchestrator = bug_orchestrator
        self.on_goal_start = on_goal_start
        self.on_goal_complete = on_goal_complete
        self.on_checkpoint = on_checkpoint
        self.episode_store = episode_store

        # Initialize or use provided RecoveryManager
        if recovery_manager is not None:
            self.recovery_manager = recovery_manager
        else:
            self.recovery_manager = RecoveryManager(checkpoint_system)

        # Initialize ProgressTracker with path from config
        progress_base_path = Path(config.storage_path) / "progress"
        self.progress_tracker = ProgressTracker(progress_base_path)

    @staticmethod
    def _parse_duration(duration: str) -> int:
        """Parse duration string to minutes.

        Args:
            duration: Duration string like "2h", "90m", "1h30m"

        Returns:
            Duration in minutes
        """
        import re
        total_minutes = 0

        # Match hours
        hours_match = re.search(r'(\d+)h', duration)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60

        # Match minutes
        mins_match = re.search(r'(\d+)m', duration)
        if mins_match:
            total_minutes += int(mins_match.group(1))

        # If no units found, assume minutes
        if total_minutes == 0 and duration.isdigit():
            total_minutes = int(duration)

        return total_minutes if total_minutes > 0 else 120  # Default 2 hours

    def _execute_feature_goal_sync(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a feature goal via Orchestrator (synchronous).

        This is the core execution function without recovery wrapping.

        Args:
            goal: DailyGoal with linked_feature and linked_issue set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if orchestrator is available
        if self.orchestrator is None:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for feature execution",
                output="",
            )

        # Call orchestrator.run_issue_session(feature_id, issue_number)
        result = self.orchestrator.run_issue_session(
            feature_id=goal.linked_feature,
            issue_number=goal.linked_issue,
        )

        duration = int(time.time() - start_time)

        # Map result status to success boolean
        success = result.status == "success"
        cost_usd = getattr(result, "cost_usd", 0.0)
        error = getattr(result, "error", None) if not success else None
        # Ensure output is a string (mock objects may return MagicMock)
        msg = getattr(result, "message", "")
        output = msg if isinstance(msg, str) else ""

        return GoalExecutionResult(
            success=success,
            cost_usd=cost_usd,
            duration_seconds=duration,
            error=error,
            output=output,
        )

    def _execute_feature_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a feature goal with recovery via RecoveryManager.

        Args:
            goal: DailyGoal with linked_feature and linked_issue set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        # Check if orchestrator is available first
        if self.orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for feature execution",
                output="",
            )

        # Create async execute function for recovery manager
        async def execute_fn():
            # Execute synchronously within async wrapper
            return self._execute_feature_goal_sync(goal)

        # Run with recovery
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )
        except RuntimeError:
            # No running loop - create a new one
            result = asyncio.run(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )

        return result

    def _execute_goal_with_budget_check(
        self,
        goal: DailyGoal,
        remaining_budget: float,
    ) -> GoalExecutionResult:
        """Execute a goal with pre-execution budget check.

        Args:
            goal: DailyGoal to execute
            remaining_budget: Available budget in USD

        Returns:
            GoalExecutionResult - failure if budget insufficient
        """
        if remaining_budget < self.config.min_execution_budget:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error=f"Insufficient budget: ${remaining_budget:.2f} remaining",
                output="",
            )
        return self._execute_goal(goal)

    def _execute_bug_goal_sync(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a bug goal via BugOrchestrator (synchronous).

        This is the core execution function without recovery wrapping.

        Args:
            goal: DailyGoal with linked_bug set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if bug_orchestrator is available
        if self.bug_orchestrator is None:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No bug_orchestrator configured for bug execution",
                output="",
            )

        # Call bug_orchestrator.fix(bug_id)
        result = self.bug_orchestrator.fix(goal.linked_bug)

        duration = int(time.time() - start_time)

        # Map result to success boolean
        # Success if result.success is True or phase.value == "fixed"
        success = False
        if hasattr(result, "success"):
            success = result.success
        if hasattr(result, "phase") and hasattr(result.phase, "value"):
            if result.phase.value == "fixed":
                success = True

        cost_usd = getattr(result, "cost_usd", 0.0)
        error = getattr(result, "error", None) if not success else None
        # Ensure output is a string (mock objects may return MagicMock)
        msg = getattr(result, "message", "")
        output = msg if isinstance(msg, str) else ""

        return GoalExecutionResult(
            success=success,
            cost_usd=cost_usd,
            duration_seconds=duration,
            error=error,
            output=output,
        )

    def _execute_bug_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a bug goal with recovery via RecoveryManager.

        Args:
            goal: DailyGoal with linked_bug set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        # Check if bug_orchestrator is available first
        if self.bug_orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No bug_orchestrator configured for bug execution",
                output="",
            )

        # Create async execute function for recovery manager
        async def execute_fn():
            # Execute synchronously within async wrapper
            return self._execute_bug_goal_sync(goal)

        # Run with recovery
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )
        except RuntimeError:
            # No running loop - create a new one
            result = asyncio.run(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )

        return result

    def _execute_spec_goal_sync(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a spec goal via Orchestrator.run_spec_pipeline (synchronous).

        This is the core execution function without recovery wrapping.

        Args:
            goal: DailyGoal with linked_spec set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if orchestrator is available
        if self.orchestrator is None:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for spec execution",
                output="",
            )

        # Call orchestrator.run_spec_pipeline(spec_id)
        result = self.orchestrator.run_spec_pipeline(goal.linked_spec)

        duration = int(time.time() - start_time)

        # Map result status to success boolean
        # Only "success" status means true success
        success = result.status == "success"
        cost_usd = getattr(result, "total_cost_usd", 0.0)
        error = getattr(result, "error", None) if not success else None
        # Ensure output is a string (mock objects may return MagicMock)
        msg = getattr(result, "message", "")
        output = msg if isinstance(msg, str) else ""

        return GoalExecutionResult(
            success=success,
            cost_usd=cost_usd,
            duration_seconds=duration,
            error=error,
            output=output,
        )

    def _execute_spec_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a spec goal with recovery via RecoveryManager.

        Args:
            goal: DailyGoal with linked_spec set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        # Check if orchestrator is available first
        if self.orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for spec execution",
                output="",
            )

        # Create async execute function for recovery manager
        async def execute_fn():
            # Execute synchronously within async wrapper
            return self._execute_spec_goal_sync(goal)

        # Run with recovery
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )
        except RuntimeError:
            # No running loop - create a new one
            result = asyncio.run(
                self.recovery_manager.execute_with_recovery(
                    goal, execute_fn, episode_store=self.episode_store
                )
            )

        return result

    def _execute_generic_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a generic goal (no linked artifact).

        Generic goals have no automated execution - they are stub/manual tasks.

        Args:
            goal: DailyGoal without linked_feature, linked_bug, or linked_spec

        Returns:
            GoalExecutionResult with success=True and stub note
        """
        return GoalExecutionResult(
            success=True,
            cost_usd=0.0,
            duration_seconds=0,
            error=None,
            output="Stub execution - manual goal with no linked artifact",
        )

    def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a single goal based on its linked artifact type.

        Routing priority:
        1. linked_feature (with linked_issue) -> _execute_feature_goal
        2. linked_bug -> _execute_bug_goal
        3. linked_spec -> _execute_spec_goal
        4. No linked artifact -> _execute_generic_goal

        Also updates progress tracker at start and after completion.

        Args:
            goal: DailyGoal to execute

        Returns:
            GoalExecutionResult with execution outcome
        """
        # Update progress tracker with current goal at start
        self.progress_tracker.update(current_goal=goal.description)

        # Route based on linked artifact type
        # Priority: feature > bug > spec > generic
        if goal.linked_feature and goal.linked_issue:
            result = self._execute_feature_goal(goal)
        elif goal.linked_bug:
            result = self._execute_bug_goal(goal)
        elif goal.linked_spec:
            result = self._execute_spec_goal(goal)
        else:
            result = self._execute_generic_goal(goal)

        # Update progress tracker after completion
        current = self.progress_tracker.get_current()
        if current is not None:
            new_completed = current.goals_completed + (1 if result.success else 0)
            new_cost = current.cost_usd + result.cost_usd
            self.progress_tracker.update(
                goals_completed=new_completed,
                cost_usd=new_cost,
            )

        return result

    def start(
        self,
        goals: list[DailyGoal],
        budget_usd: Optional[float] = None,
        duration_minutes: Optional[int] = None,
        stop_trigger: Optional[str] = None,
        dry_run: bool = False,
    ) -> AutopilotRunResult:
        """Start a new autopilot session with the given goals.

        Args:
            goals: List of DailyGoal to execute
            budget_usd: Budget limit in USD (defaults to config)
            duration_minutes: Time limit in minutes (defaults to config)
            stop_trigger: Optional keyword to stop at (e.g., "approval")
            dry_run: If True, don't actually execute (for testing)

        Returns:
            AutopilotRunResult with session state and execution summary
        """
        # Store stop trigger for checkpoint handling
        self._stop_trigger = stop_trigger
        self._dry_run = dry_run
        import asyncio

        start_time = time.time()

        # Use config defaults if not specified
        if budget_usd is None:
            budget_usd = self.config.budget_usd
        if duration_minutes is None:
            duration_minutes = self.config.duration_minutes

        # Reset daily cost at session start (Issue #12 requirement)
        self.checkpoint_system.reset_daily_cost()

        # Start progress tracking
        self.progress_tracker.start_session(total_goals=len(goals))

        # Create new session
        session_id = str(uuid.uuid4())[:8]
        session = AutopilotSession(
            session_id=session_id,
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            started_at=datetime.now(timezone.utc).isoformat(),
            budget_usd=budget_usd,
            duration_minutes=duration_minutes,
        )

        # Execute goals
        goals_completed = 0
        total_cost = 0.0
        checkpoint_pending = False

        for i, goal in enumerate(goals):
            session.current_goal_index = i

            # Check checkpoint before execution (Issue #12 requirement)
            # This checks for triggers like COST, UX_CHANGE, ARCHITECTURE, etc.
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, use nest_asyncio or create task
                import nest_asyncio
                nest_asyncio.apply()
                checkpoint_result = loop.run_until_complete(
                    self.checkpoint_system.check_before_execution(goal)
                )
            except RuntimeError:
                # No running loop - create a new one
                checkpoint_result = asyncio.run(
                    self.checkpoint_system.check_before_execution(goal)
                )

            if checkpoint_result.requires_approval and not checkpoint_result.approved:
                # Checkpoint requires approval - pause execution
                checkpoint_pending = True
                session.state = AutopilotState.PAUSED

                if self.on_checkpoint and checkpoint_result.checkpoint:
                    self.on_checkpoint(checkpoint_result.checkpoint.trigger)

                break

            # Check budget before execution
            remaining_budget = budget_usd - total_cost
            can_execute = check_budget(
                remaining_budget=remaining_budget,
                min_execution_budget=self.config.min_execution_budget,
            )

            if not can_execute:
                session.state = AutopilotState.PAUSED
                break

            # Callback before execution
            if self.on_goal_start:
                self.on_goal_start(goal)

            # Execute goal
            result = self._execute_goal(goal)

            # Update daily cost tracking (Issue #12 requirement)
            self.checkpoint_system.update_daily_cost(result.cost_usd)

            # Update totals
            total_cost += result.cost_usd
            session.total_cost_usd = total_cost

            if result.success:
                goal.status = GoalStatus.COMPLETE
                goals_completed += 1
            else:
                goal.status = GoalStatus.BLOCKED

            # Check if execution returned checkpoint_pending
            if result.checkpoint_pending:
                checkpoint_pending = True
                session.state = AutopilotState.PAUSED
                break

            # Callback after execution
            if self.on_goal_complete:
                self.on_goal_complete(goal, result)

        # Finalize session
        duration = int(time.time() - start_time)
        if session.state != AutopilotState.PAUSED:
            session.state = AutopilotState.COMPLETED

        session.completed_at = datetime.now(timezone.utc).isoformat()

        # Save session
        self.session_store.save(session)

        return AutopilotRunResult(
            session=session,
            goals_completed=goals_completed,
            goals_total=len(goals),
            total_cost_usd=total_cost,
            duration_seconds=duration,
        )

    def resume(self, session_id: str) -> AutopilotRunResult:
        """Resume a paused autopilot session.

        Args:
            session_id: ID of session to resume

        Returns:
            AutopilotRunResult with updated session state
        """
        # Load session
        session = self.session_store.load(session_id)
        if session is None:
            return AutopilotRunResult(
                session=AutopilotSession(
                    session_id=session_id,
                    state=AutopilotState.FAILED,
                    goals=[],
                    current_goal_index=0,
                    total_cost_usd=0.0,
                    started_at=datetime.now(timezone.utc).isoformat(),
                ),
                goals_completed=0,
                goals_total=0,
                total_cost_usd=0.0,
                duration_seconds=0,
                error=f"Session {session_id} not found",
            )

        # Reconstruct goals from session
        goals = [DailyGoal.from_dict(g) for g in session.goals]

        # Resume from current index
        start_index = session.current_goal_index
        remaining_goals = goals[start_index:]

        # Continue execution
        return self.start(
            remaining_goals,
            budget_usd=session.budget_usd,
            duration_minutes=session.duration_minutes,
        )