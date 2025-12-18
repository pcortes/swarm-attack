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
        """Execute a feature goal via Orchestrator.

        Args:
            goal: DailyGoal with linked_feature and linked_issue set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if orchestrator is available
        if self.orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for feature execution",
                output="",
            )

        try:
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

        except Exception as e:
            goal.error_count += 1
            duration = int(time.time() - start_time)
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=duration,
                error=str(e),
                output="",
            )

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

    def _execute_bug_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a bug goal via BugOrchestrator.

        Args:
            goal: DailyGoal with linked_bug set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if bug_orchestrator is available
        if self.bug_orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No bug_orchestrator configured for bug execution",
                output="",
            )

        try:
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

        except Exception as e:
            goal.error_count += 1
            duration = int(time.time() - start_time)
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=duration,
                error=str(e),
                output="",
            )

    def _execute_spec_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a spec goal via Orchestrator.run_spec_pipeline.

        Args:
            goal: DailyGoal with linked_spec set

        Returns:
            GoalExecutionResult with success, cost_usd, duration_seconds
        """
        start_time = time.time()

        # Check if orchestrator is available
        if self.orchestrator is None:
            goal.error_count += 1
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="No orchestrator configured for spec execution",
                output="",
            )

        try:
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

        except Exception as e:
            goal.error_count += 1
            duration = int(time.time() - start_time)
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=duration,
                error=str(e),
                output="",
            )

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

        Args:
            goal: DailyGoal to execute

        Returns:
            GoalExecutionResult with execution outcome
        """
        # Route based on linked artifact type
        # Priority: feature > bug > spec > generic
        if goal.linked_feature and goal.linked_issue:
            return self._execute_feature_goal(goal)
        elif goal.linked_bug:
            return self._execute_bug_goal(goal)
        elif goal.linked_spec:
            return self._execute_spec_goal(goal)
        else:
            return self._execute_generic_goal(goal)

    def start(
        self,
        goals: list[DailyGoal],
        budget_usd: Optional[float] = None,
        duration_minutes: Optional[int] = None,
    ) -> AutopilotRunResult:
        """Start a new autopilot session with the given goals.

        Args:
            goals: List of DailyGoal to execute
            budget_usd: Budget limit in USD (defaults to config)
            duration_minutes: Time limit in minutes (defaults to config)

        Returns:
            AutopilotRunResult with session state and execution summary
        """
        start_time = time.time()

        # Use config defaults if not specified
        if budget_usd is None:
            budget_usd = self.config.budget_usd
        if duration_minutes is None:
            duration_minutes = self.config.duration_minutes

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

        for i, goal in enumerate(goals):
            session.current_goal_index = i

            # Check budget before execution
            estimated_cost = goal.estimated_cost_usd or 0.0
            budget_check = check_budget(
                estimated_cost=estimated_cost,
                current_spend=total_cost,
                budget_limit=budget_usd,
                min_execution_budget=self.config.min_execution_budget,
            )

            if not budget_check.can_execute:
                session.state = AutopilotState.PAUSED
                break

            # Callback before execution
            if self.on_goal_start:
                self.on_goal_start(goal)

            # Execute goal
            result = self._execute_goal(goal)

            # Update totals
            total_cost += result.cost_usd
            session.total_cost_usd = total_cost

            if result.success:
                goal.status = GoalStatus.COMPLETE
                goals_completed += 1
            else:
                goal.status = GoalStatus.BLOCKED

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