"""
Smart CLI State Machine for Feature Swarm.

This module handles:
- Reading current state and determining next action
- Using PrioritizationAgent to select issues
- Using SessionManager for session lifecycle
- Phase transitions
- Interrupted session handling

The state machine maps FeaturePhases to Actions that the CLI should take:

┌─────────────────────┐     ┌─────────────────────────┐
│      NO_PRD         │ --> │     AWAIT_PRD           │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (PRD created)
┌─────────────────────┐     ┌─────────────────────────┐
│     PRD_READY       │ --> │   RUN_SPEC_PIPELINE     │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (spec generated)
┌─────────────────────┐     ┌─────────────────────────┐
│ SPEC_NEEDS_APPROVAL │ --> │  AWAIT_SPEC_APPROVAL    │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (spec approved)
┌─────────────────────┐     ┌─────────────────────────┐
│    SPEC_APPROVED    │ --> │  RUN_ISSUE_PIPELINE     │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (issues created)
┌─────────────────────┐     ┌─────────────────────────┐
│ ISSUES_NEED_REVIEW  │ --> │ AWAIT_ISSUE_GREENLIGHT  │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (issues approved)
┌─────────────────────┐     ┌─────────────────────────┐
│ READY_TO_IMPLEMENT  │ --> │    SELECT_ISSUE         │
└─────────────────────┘     └─────────────────────────┘
          │
          ▼ (issue selected)
┌─────────────────────┐     ┌─────────────────────────┐
│    IMPLEMENTING     │ --> │  RUN_IMPLEMENTATION     │
└─────────────────────┘     │   or RESUME_SESSION     │
                            └─────────────────────────┘
          │
          ▼ (all done)
┌─────────────────────┐     ┌─────────────────────────┐
│      COMPLETE       │ --> │       COMPLETE          │
└─────────────────────┘     └─────────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from swarm_attack.agents.prioritization import PrioritizationAgent
from swarm_attack.models import FeaturePhase, SessionState, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import StateStore


class StateMachineError(Exception):
    """Raised when the state machine encounters an error."""
    pass


class ActionType(Enum):
    """
    Types of actions the CLI can take.

    Each action corresponds to a specific CLI behavior or user prompt.
    """
    # PRD phase
    AWAIT_PRD = auto()              # Prompt user to create PRD

    # Spec phase
    RUN_SPEC_PIPELINE = auto()      # Run spec debate pipeline
    AWAIT_SPEC_APPROVAL = auto()    # Wait for human to review spec

    # Issue phase
    RUN_ISSUE_PIPELINE = auto()     # Run issue creation pipeline
    AWAIT_ISSUE_GREENLIGHT = auto() # Wait for human to greenlight issues

    # Implementation phase
    SELECT_ISSUE = auto()           # Select next issue to work on
    RESUME_SESSION = auto()         # Resume interrupted session
    RUN_IMPLEMENTATION = auto()     # Run implementation agents

    # Terminal states
    COMPLETE = auto()               # All work is done
    AWAIT_HUMAN_HELP = auto()       # Feature is blocked, needs help


@dataclass
class Action:
    """
    An action to be taken by the CLI.

    Contains all information needed for the CLI to execute the action
    and display appropriate messages to the user.
    """
    action_type: ActionType
    feature_id: str
    issue_number: Optional[int] = None
    session_id: Optional[str] = None
    message: Optional[str] = None
    suggested_phase: Optional[FeaturePhase] = None

    @property
    def description(self) -> str:
        """Get a human-readable description of the action."""
        descriptions = {
            ActionType.AWAIT_PRD: "Waiting for PRD to be created",
            ActionType.RUN_SPEC_PIPELINE: "Running spec debate pipeline",
            ActionType.AWAIT_SPEC_APPROVAL: "Waiting for spec approval",
            ActionType.RUN_ISSUE_PIPELINE: "Running issue creation pipeline",
            ActionType.AWAIT_ISSUE_GREENLIGHT: "Waiting for issue greenlight",
            ActionType.SELECT_ISSUE: f"Selecting issue #{self.issue_number}",
            ActionType.RESUME_SESSION: f"Resuming session {self.session_id}",
            ActionType.RUN_IMPLEMENTATION: f"Running implementation for issue #{self.issue_number}",
            ActionType.COMPLETE: "Feature is complete",
            ActionType.AWAIT_HUMAN_HELP: "Waiting for human intervention",
        }
        return descriptions.get(self.action_type, str(self.action_type))


class StateMachine:
    """
    Smart CLI State Machine for Feature Swarm.

    Determines the next action based on current feature state, active sessions,
    and task status. Uses PrioritizationAgent for issue selection.
    """

    def __init__(
        self,
        config: SwarmConfig,
        state_store: StateStore,
        session_manager: SessionManager,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the State Machine.

        Args:
            config: SwarmConfig with paths and settings.
            state_store: StateStore for loading feature state.
            session_manager: SessionManager for session lifecycle.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self.state_store = state_store
        self.session_manager = session_manager
        self.logger = logger

        # Create prioritization agent for issue selection
        self._prioritization_agent = PrioritizationAgent(config, logger)

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            log_data = {"component": "state_machine"}
            if data:
                log_data.update(data)
            self.logger.log(event_type, log_data, level=level)

    def has_active_session(self, feature_id: str) -> bool:
        """
        Check if a feature has an active session.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if an active session exists.
        """
        return self.session_manager.has_active_session(feature_id)

    def get_interrupted_session(self, feature_id: str) -> Optional[SessionState]:
        """
        Get an interrupted session for a feature.

        Checks for sessions with status="interrupted" (explicitly marked).

        Args:
            feature_id: The feature identifier.

        Returns:
            Interrupted SessionState or None.
        """
        # Check all sessions for interrupted status
        session_ids = self.session_manager.list_sessions(feature_id)
        for sid in session_ids:
            session = self.session_manager.get_session(feature_id, sid)
            if session is not None and session.status == "interrupted":
                return session
        return None

    def _get_next_issue(self, feature_id: str) -> Optional[int]:
        """
        Get the next issue to work on using PrioritizationAgent.

        Args:
            feature_id: The feature identifier.

        Returns:
            Issue number or None if no issues available.
        """
        state = self.state_store.load(feature_id)
        if state is None:
            return None

        result = self._prioritization_agent.run({"state": state})
        if not result.success:
            return None

        selected = result.output.get("selected_issue")
        if selected is None:
            return None

        return selected.issue_number

    def _are_all_tasks_done(self, feature_id: str) -> bool:
        """
        Check if all tasks for a feature are done.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if all tasks are DONE, False otherwise.
        """
        state = self.state_store.load(feature_id)
        if state is None or not state.tasks:
            return True  # No tasks = done

        return all(task.stage == TaskStage.DONE for task in state.tasks)

    def _has_ready_tasks(self, feature_id: str) -> bool:
        """
        Check if there are any READY tasks.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if there are READY tasks.
        """
        state = self.state_store.load(feature_id)
        if state is None:
            return False

        return any(task.stage == TaskStage.READY for task in state.tasks)

    def _has_any_tasks(self, feature_id: str) -> bool:
        """
        Check if the feature has any tasks at all.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if there are tasks.
        """
        state = self.state_store.load(feature_id)
        if state is None:
            return False
        return len(state.tasks) > 0

    def get_next_action(self, feature_id: str) -> Action:
        """
        Determine the next action for a feature.

        This is the main entry point for the state machine. It examines
        the current state and returns the appropriate action.

        Args:
            feature_id: The feature identifier.

        Returns:
            Action describing what the CLI should do next.

        Raises:
            StateMachineError: If feature not found or in invalid state.
        """
        # Load state
        state = self.state_store.load(feature_id)
        if state is None:
            raise StateMachineError(f"Feature '{feature_id}' not found")

        self._log(
            "state_machine_evaluate",
            {
                "feature_id": feature_id,
                "phase": state.phase.name,
                "current_session": state.current_session,
            },
        )

        # Map phase to action
        action = self._phase_to_action(feature_id, state.phase)

        self._log(
            "state_machine_action",
            {
                "feature_id": feature_id,
                "action_type": action.action_type.name,
                "issue_number": action.issue_number,
                "session_id": action.session_id,
            },
        )

        return action

    def _phase_to_action(self, feature_id: str, phase: FeaturePhase) -> Action:
        """
        Map a feature phase to an action.

        Args:
            feature_id: The feature identifier.
            phase: Current feature phase.

        Returns:
            Action to take.
        """
        # Phase-specific handlers
        handlers = {
            FeaturePhase.NO_PRD: self._handle_no_prd,
            FeaturePhase.PRD_READY: self._handle_prd_ready,
            FeaturePhase.SPEC_IN_PROGRESS: self._handle_spec_in_progress,
            FeaturePhase.SPEC_NEEDS_APPROVAL: self._handle_spec_needs_approval,
            FeaturePhase.SPEC_APPROVED: self._handle_spec_approved,
            FeaturePhase.ISSUES_CREATING: self._handle_issues_creating,
            FeaturePhase.ISSUES_VALIDATING: self._handle_issues_validating,
            FeaturePhase.ISSUES_NEED_REVIEW: self._handle_issues_need_review,
            FeaturePhase.READY_TO_IMPLEMENT: self._handle_ready_to_implement,
            FeaturePhase.IMPLEMENTING: self._handle_implementing,
            FeaturePhase.COMPLETE: self._handle_complete,
            FeaturePhase.BLOCKED: self._handle_blocked,
        }

        handler = handlers.get(phase)
        if handler is None:
            raise StateMachineError(f"Unknown phase: {phase}")

        return handler(feature_id)

    # =========================================================================
    # Phase Handlers
    # =========================================================================

    def _handle_no_prd(self, feature_id: str) -> Action:
        """Handle NO_PRD phase."""
        return Action(
            action_type=ActionType.AWAIT_PRD,
            feature_id=feature_id,
            message="Please create a PRD at .claude/prds/{feature_id}.md",
        )

    def _handle_prd_ready(self, feature_id: str) -> Action:
        """Handle PRD_READY phase."""
        return Action(
            action_type=ActionType.RUN_SPEC_PIPELINE,
            feature_id=feature_id,
            message="Running spec debate pipeline...",
        )

    def _handle_spec_in_progress(self, feature_id: str) -> Action:
        """Handle SPEC_IN_PROGRESS phase."""
        return Action(
            action_type=ActionType.RUN_SPEC_PIPELINE,
            feature_id=feature_id,
            message="Continuing spec debate pipeline...",
        )

    def _handle_spec_needs_approval(self, feature_id: str) -> Action:
        """Handle SPEC_NEEDS_APPROVAL phase."""
        return Action(
            action_type=ActionType.AWAIT_SPEC_APPROVAL,
            feature_id=feature_id,
            message="Spec is ready for review. Run 'feature-swarm approve {feature_id}' to approve.",
        )

    def _handle_spec_approved(self, feature_id: str) -> Action:
        """Handle SPEC_APPROVED phase."""
        return Action(
            action_type=ActionType.RUN_ISSUE_PIPELINE,
            feature_id=feature_id,
            message="Running issue creation pipeline...",
        )

    def _handle_issues_creating(self, feature_id: str) -> Action:
        """Handle ISSUES_CREATING phase."""
        return Action(
            action_type=ActionType.RUN_ISSUE_PIPELINE,
            feature_id=feature_id,
            message="Continuing issue creation...",
        )

    def _handle_issues_validating(self, feature_id: str) -> Action:
        """Handle ISSUES_VALIDATING phase."""
        return Action(
            action_type=ActionType.RUN_ISSUE_PIPELINE,
            feature_id=feature_id,
            message="Validating issues...",
        )

    def _handle_issues_need_review(self, feature_id: str) -> Action:
        """Handle ISSUES_NEED_REVIEW phase."""
        return Action(
            action_type=ActionType.AWAIT_ISSUE_GREENLIGHT,
            feature_id=feature_id,
            message="Issues are ready for review. Run 'feature-swarm greenlight {feature_id}' to approve.",
        )

    def _handle_ready_to_implement(self, feature_id: str) -> Action:
        """Handle READY_TO_IMPLEMENT phase."""
        # Check if all tasks are done
        if self._are_all_tasks_done(feature_id):
            return Action(
                action_type=ActionType.COMPLETE,
                feature_id=feature_id,
                message="All tasks completed!",
                suggested_phase=FeaturePhase.COMPLETE,
            )

        # Check if any tasks are available
        next_issue = self._get_next_issue(feature_id)
        if next_issue is None:
            # No unblocked tasks available
            if self._has_ready_tasks(feature_id):
                # Has ready tasks but all blocked by dependencies
                return Action(
                    action_type=ActionType.AWAIT_HUMAN_HELP,
                    feature_id=feature_id,
                    message="All ready tasks are blocked by circular dependencies",
                )
            elif not self._has_any_tasks(feature_id):
                # No tasks at all
                return Action(
                    action_type=ActionType.COMPLETE,
                    feature_id=feature_id,
                    message="No tasks to implement",
                    suggested_phase=FeaturePhase.COMPLETE,
                )
            else:
                # All tasks are done or in non-READY states
                return Action(
                    action_type=ActionType.COMPLETE,
                    feature_id=feature_id,
                    message="All tasks completed!",
                    suggested_phase=FeaturePhase.COMPLETE,
                )

        return Action(
            action_type=ActionType.SELECT_ISSUE,
            feature_id=feature_id,
            issue_number=next_issue,
            message=f"Selected issue #{next_issue} for implementation",
        )

    def _handle_implementing(self, feature_id: str) -> Action:
        """Handle IMPLEMENTING phase."""
        # First check for all done
        if self._are_all_tasks_done(feature_id):
            return Action(
                action_type=ActionType.COMPLETE,
                feature_id=feature_id,
                message="All tasks completed!",
                suggested_phase=FeaturePhase.COMPLETE,
            )

        # Check for explicitly interrupted sessions FIRST
        # These are sessions that were marked as interrupted (status="interrupted")
        interrupted = self.get_interrupted_session(feature_id)
        if interrupted is not None:
            return Action(
                action_type=ActionType.RESUME_SESSION,
                feature_id=feature_id,
                session_id=interrupted.session_id,
                issue_number=interrupted.issue_number,
                message=f"Resuming interrupted session for issue #{interrupted.issue_number}",
            )

        # Check for active session (status="active")
        # This means we're currently working on this session
        active = self.session_manager.get_active_session(feature_id)
        if active is not None:
            return Action(
                action_type=ActionType.RUN_IMPLEMENTATION,
                feature_id=feature_id,
                session_id=active.session_id,
                issue_number=active.issue_number,
                message=f"Continuing implementation of issue #{active.issue_number}",
            )

        # No active or interrupted session - select next issue
        next_issue = self._get_next_issue(feature_id)
        if next_issue is None:
            # Check if there are ready tasks
            if self._has_ready_tasks(feature_id):
                # Circular dependencies
                return Action(
                    action_type=ActionType.AWAIT_HUMAN_HELP,
                    feature_id=feature_id,
                    message="All ready tasks are blocked by circular dependencies",
                )
            else:
                # No more ready tasks - likely all done
                return Action(
                    action_type=ActionType.COMPLETE,
                    feature_id=feature_id,
                    message="All tasks completed!",
                    suggested_phase=FeaturePhase.COMPLETE,
                )

        return Action(
            action_type=ActionType.SELECT_ISSUE,
            feature_id=feature_id,
            issue_number=next_issue,
            message=f"Selected issue #{next_issue} for implementation",
        )

    def _handle_complete(self, feature_id: str) -> Action:
        """Handle COMPLETE phase."""
        return Action(
            action_type=ActionType.COMPLETE,
            feature_id=feature_id,
            message="Feature is complete!",
        )

    def _handle_blocked(self, feature_id: str) -> Action:
        """Handle BLOCKED phase."""
        return Action(
            action_type=ActionType.AWAIT_HUMAN_HELP,
            feature_id=feature_id,
            message="Feature is blocked and needs human intervention",
        )
