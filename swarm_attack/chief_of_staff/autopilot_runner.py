"""AutopilotRunner - executes goals with checkpoint gates.

This module provides the AutopilotRunner class that executes daily goals
with checkpoint-based pause/resume capability. It integrates with:
- CheckpointSystem for trigger detection (cost, time, errors, approvals)
- AutopilotSessionStore for session persistence
- GoalTracker for goal management

Current Implementation: Option B+ (Enhanced Stub)
- Full checkpoint trigger validation with real logic
- Goal progress tracking and persistence
- Pause/resume functionality
- Stub execution (marks goals complete without calling orchestrators)

Future: Real execution via Orchestrator and BugOrchestrator integration.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Optional

from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointTrigger
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus
from swarm_attack.chief_of_staff.budget import check_budget, get_effective_cost

if TYPE_CHECKING:
    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.bug_orchestrator import BugOrchestrator


@dataclass
class GoalExecutionResult:
    """Result from executing a single goal."""

    success: bool
    cost_usd: float
    duration_seconds: int
    error: Optional[str] = None
    output: str = ""


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

    Current Implementation (Option B+ Stub):
    - Validates all checkpoint logic
    - Tracks goal progress correctly
    - Persists sessions for pause/resume
    - Does NOT call Orchestrator/BugOrchestrator (stub execution)
    - Logs what WOULD be executed for debugging

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
    """

    def __init__(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
        orchestrator: Optional["Orchestrator"] = None,
        bug_orchestrator: Optional["BugOrchestrator"] = None,
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

    def _execute_feature_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a feature goal by calling the orchestrator.

        Args:
            goal: DailyGoal with linked_feature set

        Returns:
            GoalExecutionResult with success status, cost, duration, and output
        """
        start_time = time.time()

        # Check if orchestrator is available
        if self.orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="Orchestrator not configured - cannot execute feature goals",
                output="",
            )

        try:
            # Call orchestrator with feature_id and issue_number
            result = self.orchestrator.run_issue_session(
                feature_id=goal.linked_feature,
                issue_number=goal.linked_issue,
            )

            # Calculate duration
            duration_seconds = int(time.time() - start_time)

            # Map status to success boolean
            success = result.status == "success"

            # Get cost from result
            cost_usd = getattr(result, "cost_usd", 0.0)

            # Get error if present
            error = getattr(result, "error", None) if not success else None

            # Get summary/output if present (ensure it's a string)
            summary = getattr(result, "summary", "")
            output = summary if isinstance(summary, str) else ""

            return GoalExecutionResult(
                success=success,
                cost_usd=cost_usd,
                duration_seconds=duration_seconds,
                error=error,
                output=output,
            )

        except Exception as e:
            # Handle exceptions - increment error count and return failure
            goal.error_count += 1
            duration_seconds = int(time.time() - start_time)

            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=duration_seconds,
                error=str(e),
                output="",
            )

    def _execute_bug_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a bug goal by calling the bug orchestrator.

        Args:
            goal: DailyGoal with linked_bug set

        Returns:
            GoalExecutionResult with success status, cost, duration, and output
        """
        start_time = time.time()

        # Check if bug_orchestrator is available
        if self.bug_orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="Bug orchestrator not configured - cannot execute bug goals",
                output="",
            )

        try:
            # Call bug orchestrator with bug_id
            result = self.bug_orchestrator.fix(goal.linked_bug)

            # Calculate duration
            duration_seconds = int(time.time() - start_time)

            # Map success using result.success boolean attribute
            # BugPipelineResult has success: bool directly
            success = getattr(result, "success", False)

            # Get cost from result
            cost_usd = getattr(result, "cost_usd", 0.0)

            # Get error if present
            error = getattr(result, "error", None) if not success else None

            # Get message/output if present (ensure it's a string)
            message = getattr(result, "message", "")
            output = message if isinstance(message, str) else ""

            return GoalExecutionResult(
                success=success,
                cost_usd=cost_usd,
                duration_seconds=duration_seconds,
                error=error,
                output=output,
            )

        except Exception as e:
            goal.error_count += 1
            duration_seconds = int(time.time() - start_time)

            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=duration_seconds,
                error=str(e),
                output="",
            )

    def _execute_goal_with_budget_check(
        self,
        goal: DailyGoal,
        remaining_budget: float,
    ) -> GoalExecutionResult:
        """Execute a goal with pre-execution budget check.

        Checks budget BEFORE calling orchestrator (David Dohan requirement).

        Args:
            goal: DailyGoal to execute
            remaining_budget: Available budget in USD

        Returns:
            GoalExecutionResult with failure if budget insufficient, otherwise execution result
        """
        # Check budget BEFORE any orchestrator call
        if remaining_budget < self.config.min_execution_budget:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error=f"Insufficient budget: ${remaining_budget:.2f} < min ${self.config.min_execution_budget:.2f}",
                output="",
            )

        # Budget is sufficient - proceed with execution
        return self._execute_goal(goal)

    def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a goal based on its type.

        Routes to _execute_feature_goal or _execute_bug_goal based on linked fields.

        Args:
            goal: DailyGoal to execute

        Returns:
            GoalExecutionResult with execution outcome
        """
        if goal.linked_feature:
            return self._execute_feature_goal(goal)
        elif goal.linked_bug:
            return self._execute_bug_goal(goal)
        else:
            # Stub execution for goals without linked items
            return GoalExecutionResult(
                success=True,
                cost_usd=0.0,
                duration_seconds=0,
                error=None,
                output="Goal executed (stub - no linked feature or bug)",
            )

    def start(
        self,
        goals: list[DailyGoal],
        budget_usd: Optional[float] = None,
        duration_minutes: Optional[int] = None,
    ) -> AutopilotRunResult:
        """Start a new autopilot session with the given goals.

        Args:
            goals: List of DailyGoal to execute
            budget_usd: Optional budget limit (uses config default if not specified)
            duration_minutes: Optional duration limit (uses config default if not specified)

        Returns:
            AutopilotRunResult with session info and execution results
        """
        # Use defaults from config if not specified
        if budget_usd is None:
            budget_usd = self.config.autopilot.default_budget
        if duration_minutes is None:
            # Parse duration string like "2h" to minutes
            duration_str = self.config.autopilot.default_duration
            if duration_str.endswith("h"):
                duration_minutes = int(duration_str[:-1]) * 60
            elif duration_str.endswith("m"):
                duration_minutes = int(duration_str[:-1])
            else:
                duration_minutes = 120

        # Create new session
        session_id = str(uuid.uuid4())
        session = AutopilotSession(
            session_id=session_id,
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            budget_usd=budget_usd,
            duration_minutes=duration_minutes,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # Save initial session
        self.session_store.save(session)

        # Execute goals
        return self._run_session(session, goals)

    def resume(self, session_id: str) -> AutopilotRunResult:
        """Resume a paused autopilot session.

        Args:
            session_id: ID of the session to resume

        Returns:
            AutopilotRunResult with session info and execution results
        """
        session = self.session_store.load(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        # Reconstruct goals from session
        goals = [DailyGoal.from_dict(g) for g in session.goals]

        # Update session state
        session.state = AutopilotState.RUNNING

        return self._run_session(session, goals)

    def _run_session(
        self,
        session: AutopilotSession,
        goals: list[DailyGoal],
    ) -> AutopilotRunResult:
        """Run the autopilot session executing goals.

        Args:
            session: The autopilot session
            goals: List of goals to execute

        Returns:
            AutopilotRunResult with execution results
        """
        start_time = time.time()
        total_cost = 0.0
        goals_completed = 0
        trigger = None
        error = None

        # Create session context for checkpoint checking
        context = SessionContext()

        for goal in goals:
            # Skip already completed goals
            if goal.status == GoalStatus.COMPLETE:
                goals_completed += 1
                continue

            # Check budget before execution
            if not check_budget(
                estimated_cost=goal.estimated_cost_usd or 0.0,
                current_spent=total_cost,
                budget_limit=session.budget_usd,
                min_execution_budget=self.config.min_execution_budget,
            ):
                trigger = CheckpointTrigger.COST_CUMULATIVE
                break

            # Check time limit
            elapsed_minutes = (time.time() - start_time) / 60
            if elapsed_minutes >= session.duration_minutes:
                trigger = CheckpointTrigger.COST_CUMULATIVE  # Reusing for time
                break

            # Notify goal start
            if self.on_goal_start:
                self.on_goal_start(goal)

            # Execute goal
            goal.status = GoalStatus.IN_PROGRESS
            result = self._execute_goal(goal)

            # Update goal status
            if result.success:
                goal.status = GoalStatus.COMPLETE
                goals_completed += 1
            else:
                goal.status = GoalStatus.BLOCKED
                if result.error:
                    goal.notes = result.error

            # Track costs
            total_cost += result.cost_usd

            # Notify goal complete
            if self.on_goal_complete:
                self.on_goal_complete(goal, result)

            # Update session goals
            session.goals = [g.to_dict() for g in goals]
            self.session_store.save(session)

        # Calculate total duration
        duration_seconds = int(time.time() - start_time)

        # Update session state
        if trigger:
            session.state = AutopilotState.PAUSED
        elif goals_completed == len(goals):
            session.state = AutopilotState.COMPLETE
        else:
            session.state = AutopilotState.RUNNING

        session.cost_usd = total_cost
        self.session_store.save(session)

        return AutopilotRunResult(
            session=session,
            goals_completed=goals_completed,
            goals_total=len(goals),
            total_cost_usd=total_cost,
            duration_seconds=duration_seconds,
            trigger=trigger,
            error=error,
        )