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
        orchestrator: Optional["Orchestrator"],
        bug_orchestrator: Optional["BugOrchestrator"],
        checkpoint_system: CheckpointSystem,
        config: ChiefOfStaffConfig,
        session_store: AutopilotSessionStore,
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
        self.config = config
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
        """Start a new autopilot session.

        Args:
            goals: List of DailyGoal objects to execute
            budget_usd: Budget limit (defaults to config)
            duration_minutes: Duration limit (defaults to config)
            stop_trigger: Optional --until trigger string
            dry_run: If True, don't execute, just validate

        Returns:
            AutopilotRunResult with session and execution details
        """
        # Create new session
        session = AutopilotSession(
            session_id=f"auto-{uuid.uuid4().hex[:8]}",
            feature_id="autopilot",
            state=AutopilotState.RUNNING,
            created_at=datetime.now(timezone.utc),
            current_issue=0,
            completed_issues=[],
        )

        # Resolve limits from config if not specified
        budget = budget_usd if budget_usd is not None else self.config.autopilot.default_budget
        duration = duration_minutes if duration_minutes is not None else self._parse_duration(
            self.config.autopilot.default_duration
        )

        # Store goals in session metadata
        self._goals_map[session.session_id] = goals

        # Save initial session state
        self.session_store.save(session)

        if dry_run:
            return AutopilotRunResult(
                session=session,
                goals_completed=0,
                goals_total=len(goals),
                total_cost_usd=0.0,
                duration_seconds=0,
                error=None,
            )

        return self._run_session(
            session=session,
            goals=goals,
            budget_usd=budget,
            duration_minutes=duration,
            stop_trigger=stop_trigger,
            start_index=0,
        )

    def resume(self, session_id: str) -> AutopilotRunResult:
        """Resume a paused session.

        Args:
            session_id: ID of the session to resume

        Returns:
            AutopilotRunResult with session and execution details

        Raises:
            ValueError: If session not found
        """
        session = self.session_store.load(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        if session.state != AutopilotState.PAUSED:
            raise ValueError(f"Session {session_id} is not paused (state: {session.state})")

        # Get stored goals
        goals = self._goals_map.get(session_id, [])
        if not goals:
            # Try to reconstruct from session
            return AutopilotRunResult(
                session=session,
                goals_completed=len(session.completed_issues),
                goals_total=len(session.completed_issues),
                total_cost_usd=0.0,
                duration_seconds=0,
                error="Could not restore goals for session",
            )

        session.state = AutopilotState.RUNNING

        return self._run_session(
            session=session,
            goals=goals,
            budget_usd=self.config.autopilot.default_budget,
            duration_minutes=self._parse_duration(self.config.autopilot.default_duration),
            stop_trigger=None,
            start_index=session.current_issue or 0,
        )

    def _run_session(
        self,
        session: AutopilotSession,
        goals: list[DailyGoal],
        budget_usd: float,
        duration_minutes: int,
        stop_trigger: Optional[str],
        start_index: int,
    ) -> AutopilotRunResult:
        """Execute goals with checkpoint checks.

        Args:
            session: The autopilot session
            goals: List of goals to execute
            budget_usd: Budget limit in USD
            duration_minutes: Duration limit in minutes
            stop_trigger: Optional --until trigger
            start_index: Index to start from (for resume)

        Returns:
            AutopilotRunResult with execution details
        """
        start_time = datetime.now(timezone.utc)
        total_cost = 0.0
        completed_count = len(session.completed_issues)
        trigger: Optional[CheckpointTrigger] = None

        for i in range(start_index, len(goals)):
            goal = goals[i]
            session.current_issue = i

            # Calculate elapsed time
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            elapsed_minutes = elapsed / 60.0

            # Build session context for checkpoint system
            context = SessionContext(
                total_cost_usd=total_cost,
                elapsed_minutes=elapsed_minutes,
                stop_trigger=stop_trigger,
                is_blocked=False,
            )

            # Build action description for checkpoint check
            action = self._describe_goal(goal)

            # Check checkpoint triggers
            trigger = self.checkpoint_system.check_triggers(context, action)

            if trigger:
                # Checkpoint triggered - pause session
                session.state = AutopilotState.PAUSED
                self.session_store.save(session)

                if self.on_checkpoint:
                    self.on_checkpoint(trigger)

                return AutopilotRunResult(
                    session=session,
                    goals_completed=completed_count,
                    goals_total=len(goals),
                    total_cost_usd=total_cost,
                    duration_seconds=int(elapsed),
                    trigger=trigger,
                )

            # Execute goal
            if self.on_goal_start:
                self.on_goal_start(goal)

            result = self._execute_goal(goal)
            total_cost += result.cost_usd

            if self.on_goal_complete:
                self.on_goal_complete(goal, result)

            if result.success:
                session.completed_issues.append(i)
                completed_count += 1
                self.checkpoint_system.reset_error_count()
            else:
                session.error_message = result.error
                self.checkpoint_system.record_error()

            # Save progress after each goal
            self.session_store.save(session)

        # All goals completed
        session.state = AutopilotState.COMPLETED
        self.session_store.save(session)

        return AutopilotRunResult(
            session=session,
            goals_completed=completed_count,
            goals_total=len(goals),
            total_cost_usd=total_cost,
            duration_seconds=int((datetime.now(timezone.utc) - start_time).total_seconds()),
        )

    def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a single goal.

        Current Implementation (Stub):
        - Marks goal as complete without real execution
        - Returns zero cost
        - Logs what WOULD be executed

        Future Implementation:
        - Dispatch to Orchestrator for feature goals
        - Dispatch to BugOrchestrator for bug goals
        - Return actual cost from execution

        Args:
            goal: The goal to execute

        Returns:
            GoalExecutionResult with success/cost/duration
        """
        # Log what would be executed (for debugging)
        execution_log = f"[STUB] Would execute: {goal.description}"

        if goal.linked_feature:
            execution_log += f" (via Orchestrator.run_feature({goal.linked_feature}))"
            # Future: return self._execute_feature_goal(goal)

        elif goal.linked_bug:
            execution_log += f" (via BugOrchestrator.fix({goal.linked_bug}))"
            # Future: return self._execute_bug_goal(goal)

        else:
            execution_log += " (manual goal - mark complete)"

        # Stub implementation: Mark as success with zero cost
        return GoalExecutionResult(
            success=True,
            cost_usd=0.0,
            duration_seconds=0,
            output=execution_log,
        )

    def _execute_feature_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a feature-linked goal via Orchestrator.

        NOT IMPLEMENTED - placeholder for future integration.
        """
        if self.orchestrator is None:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="Orchestrator not configured",
            )

        # Future implementation:
        # result = self.orchestrator.run_feature(goal.linked_feature)
        # return GoalExecutionResult(
        #     success=result.status == "success",
        #     cost_usd=result.total_cost_usd,
        #     duration_seconds=result.duration_seconds,
        #     error=result.error,
        # )

        return GoalExecutionResult(
            success=True,
            cost_usd=0.0,
            duration_seconds=0,
            output=f"Feature goal stub: {goal.linked_feature}",
        )

    def _execute_bug_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a bug-linked goal via BugOrchestrator.

        NOT IMPLEMENTED - placeholder for future integration.
        """
        if self.bug_orchestrator is None:
            return GoalExecutionResult(
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                error="BugOrchestrator not configured",
            )

        # Future implementation:
        # result = self.bug_orchestrator.fix(goal.linked_bug)
        # return GoalExecutionResult(
        #     success=result.success,
        #     cost_usd=result.cost_usd,
        #     duration_seconds=result.duration_seconds,
        #     error=result.error,
        # )

        return GoalExecutionResult(
            success=True,
            cost_usd=0.0,
            duration_seconds=0,
            output=f"Bug goal stub: {goal.linked_bug}",
        )

    def _describe_goal(self, goal: DailyGoal) -> str:
        """Generate action description for checkpoint checking.

        Args:
            goal: The goal to describe

        Returns:
            Human-readable action description
        """
        if goal.linked_feature:
            return f"Execute feature: {goal.linked_feature} - {goal.description}"
        elif goal.linked_bug:
            return f"Fix bug: {goal.linked_bug} - {goal.description}"
        else:
            return f"Complete goal: {goal.description}"

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to minutes.

        Supports formats: "2h", "120m", "1h30m"

        Args:
            duration_str: Duration string

        Returns:
            Duration in minutes
        """
        duration_str = duration_str.lower().strip()
        total_minutes = 0

        # Handle hours
        if "h" in duration_str:
            parts = duration_str.split("h")
            hours = int(parts[0]) if parts[0] else 0
            total_minutes += hours * 60
            duration_str = parts[1] if len(parts) > 1 else ""

        # Handle minutes
        if "m" in duration_str:
            minutes_str = duration_str.replace("m", "")
            if minutes_str:
                total_minutes += int(minutes_str)
        elif duration_str.isdigit():
            # Assume minutes if no unit
            total_minutes += int(duration_str)

        return total_minutes if total_minutes > 0 else 120  # Default 2 hours

    # In-memory storage for goals (session_id -> goals mapping)
    # In production, this should be persisted with the session
    _goals_map: dict[str, list[DailyGoal]] = {}

    def list_paused_sessions(self) -> list[AutopilotSession]:
        """List all paused sessions.

        Returns:
            List of paused AutopilotSession objects
        """
        paused_ids = self.session_store.list_paused()
        sessions = []

        for session_id in paused_ids:
            session = self.session_store.load(session_id)
            if session:
                sessions.append(session)

        return sessions

    def cancel(self, session_id: str) -> bool:
        """Cancel/delete a session.

        Args:
            session_id: ID of session to cancel

        Returns:
            True if deleted, False if not found
        """
        session = self.session_store.load(session_id)
        if session is None:
            return False

        session.state = AutopilotState.FAILED
        session.error_message = "Cancelled by user"
        self.session_store.save(session)

        # Clean up goals map
        if session_id in self._goals_map:
            del self._goals_map[session_id]

        return True