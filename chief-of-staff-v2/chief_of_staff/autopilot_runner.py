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

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Optional

from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointTrigger
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus

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
        orchestrator: Optional["Orchestrator"] = None,
        bug_orchestrator: Optional["BugOrchestrator"] = None,
        checkpoint_system: Optional[CheckpointSystem] = None,
        config: Optional[ChiefOfStaffConfig] = None,
        session_store: Optional[AutopilotSessionStore] = None,
        on_goal_start: Optional[Callable[[DailyGoal], None]] = None,
        on_goal_complete: Optional[Callable[[DailyGoal, GoalExecutionResult], None]] = None,
        on_checkpoint: Optional[Callable[[CheckpointTrigger], None]] = None,
    ) -> None:
        """Initialize AutopilotRunner.

        Args:
            orchestrator: Optional Orchestrator for feature execution
            bug_orchestrator: Optional BugOrchestrator for bug execution
            checkpoint_system: CheckpointSystem for trigger detection
            config: ChiefOfStaffConfig with autopilot settings
            session_store: AutopilotSessionStore for persistence
            on_goal_start: Optional callback when goal execution starts
            on_goal_complete: Optional callback when goal completes
            on_checkpoint: Optional callback when checkpoint triggers
        """
        self.orchestrator = orchestrator
        self.bug_orchestrator = bug_orchestrator
        self.checkpoint_system = checkpoint_system
        self.config = config if config is not None else ChiefOfStaffConfig()
        self.session_store = session_store
        self.on_goal_start = on_goal_start
        self.on_goal_complete = on_goal_complete
        self.on_checkpoint = on_checkpoint

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
            goals: List of goals to execute
            budget_usd: Optional budget limit in USD
            duration_minutes: Optional time limit in minutes
            stop_trigger: Optional trigger condition to stop at
            dry_run: If True, don't actually execute goals

        Returns:
            AutopilotRunResult with session info and execution results
        """
        session_id = str(uuid.uuid4())
        feature_id = goals[0].linked_feature if goals and goals[0].linked_feature else "autopilot"

        session = AutopilotSession(
            session_id=session_id,
            feature_id=feature_id,
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            started_at=datetime.now(timezone.utc),
        )

        return self._run_session(session, goals, stop_trigger, dry_run)

    def resume(self, session_id: str) -> AutopilotRunResult:
        """Resume a paused session.

        Args:
            session_id: ID of the session to resume

        Returns:
            AutopilotRunResult with session info and execution results
        """
        if self.session_store is None:
            raise ValueError("No session store configured")

        session = self.session_store.load(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        goals = [DailyGoal.from_dict(g) for g in session.goals]
        return self._run_session(session, goals, None, False)

    def _run_session(
        self,
        session: AutopilotSession,
        goals: list[DailyGoal],
        stop_trigger: Optional[str],
        dry_run: bool,
    ) -> AutopilotRunResult:
        """Run the session, executing goals until complete or triggered.

        Args:
            session: The autopilot session
            goals: List of goals to execute
            stop_trigger: Optional trigger condition
            dry_run: If True, don't actually execute

        Returns:
            AutopilotRunResult with execution results
        """
        start_time = datetime.now(timezone.utc)
        goals_completed = 0

        context = SessionContext(
            total_cost_usd=session.total_cost_usd,
            elapsed_minutes=0.0,
            stop_trigger=stop_trigger,
        )

        for i, goal in enumerate(goals[session.current_goal_index:], start=session.current_goal_index):
            # Check for triggers before each goal
            if self.checkpoint_system is not None:
                trigger = self.checkpoint_system.check_triggers(context, goal.description)
                if trigger is not None:
                    session.state = AutopilotState.PAUSED
                    session.current_goal_index = i
                    if self.session_store is not None:
                        self.session_store.save(session)
                    if self.on_checkpoint is not None:
                        self.on_checkpoint(trigger)

                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    return AutopilotRunResult(
                        session=session,
                        goals_completed=goals_completed,
                        goals_total=len(goals),
                        total_cost_usd=context.total_cost_usd,
                        duration_seconds=int(elapsed),
                        trigger=trigger,
                    )

            # Execute goal (stub implementation)
            if self.on_goal_start is not None:
                self.on_goal_start(goal)

            result = self._execute_goal(goal, dry_run)

            if self.on_goal_complete is not None:
                self.on_goal_complete(goal, result)

            context.total_cost_usd += result.cost_usd
            goals_completed += 1
            session.current_goal_index = i + 1
            session.total_cost_usd = context.total_cost_usd

            # Update elapsed time
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            context.elapsed_minutes = elapsed / 60.0

        # All goals completed
        session.state = AutopilotState.COMPLETE
        if self.session_store is not None:
            self.session_store.save(session)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        return AutopilotRunResult(
            session=session,
            goals_completed=goals_completed,
            goals_total=len(goals),
            total_cost_usd=context.total_cost_usd,
            duration_seconds=int(elapsed),
        )

    def _execute_goal(self, goal: DailyGoal, dry_run: bool) -> GoalExecutionResult:
        """Execute a single goal (stub implementation).

        Args:
            goal: The goal to execute
            dry_run: If True, don't actually execute

        Returns:
            GoalExecutionResult with execution details
        """
        # Stub implementation - just mark as successful
        return GoalExecutionResult(
            success=True,
            cost_usd=0.01,  # Nominal cost for tracking
            duration_seconds=1,
            output=f"Executed goal: {goal.description}" if not dry_run else f"Dry run: {goal.description}",
        )