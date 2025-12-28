"""Chief of Staff Autopilot QA Runner.

Implements spec section 5.2.4:
- Execute QA validation goals in autopilot
- Execute health check goals (shallow depth)
- Track QA sessions linked to goals
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from swarm_attack.qa.models import QADepth, QARecommendation
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class GoalExecutionResult:
    """Result of executing a QA goal.

    Attributes:
        success: Whether the goal execution succeeded.
        session_id: ID of the QA session that was run.
        cost_usd: Cost of the QA execution in USD.
        duration_seconds: Duration of execution in seconds.
        findings_count: Number of QA findings discovered.
        error: Error message if execution failed.
    """

    success: bool = False
    session_id: Optional[str] = None
    cost_usd: float = 0.0
    duration_seconds: int = 0
    findings_count: int = 0
    error: Optional[str] = None


class QAAutopilotRunner:
    """Runs QA goals as part of Chief of Staff autopilot.

    Supports two goal types:
    - QA_VALIDATION: Run QA validation for a feature/issue
    - QA_HEALTH: Run system health check (shallow depth)
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the QAAutopilotRunner.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.orchestrator = QAOrchestrator(config, logger)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "qa_autopilot_runner"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _calculate_duration(
        self, started_at: Optional[str], completed_at: Optional[str]
    ) -> int:
        """Calculate duration in seconds from timestamps.

        Args:
            started_at: ISO format start timestamp.
            completed_at: ISO format completion timestamp.

        Returns:
            Duration in seconds, or 0 if timestamps are invalid.
        """
        if not started_at or not completed_at:
            return 0

        try:
            # Parse ISO format timestamps
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            return int((end - start).total_seconds())
        except (ValueError, TypeError):
            return 0

    def execute_qa_validation_goal(self, goal: QAGoal) -> GoalExecutionResult:
        """Execute a QA validation goal.

        If the goal has linked_feature and linked_issue, uses validate_issue().
        Otherwise, falls back to test() with the goal description as target.

        Args:
            goal: The QA goal to execute.

        Returns:
            GoalExecutionResult with execution details.
        """
        self._log("qa_validation_goal_start", {
            "goal_type": goal.goal_type.value,
            "linked_feature": goal.linked_feature,
            "linked_issue": goal.linked_issue,
        })

        try:
            # Determine which method to call
            if goal.linked_feature and goal.linked_issue:
                # Use validate_issue for feature/issue pairs
                session = self.orchestrator.validate_issue(
                    feature_id=goal.linked_feature,
                    issue_number=goal.linked_issue,
                    depth=QADepth.STANDARD,
                )
            else:
                # Fall back to test() with description as target
                target = goal.description or "QA validation"
                session = self.orchestrator.test(
                    target=target,
                    depth=QADepth.STANDARD,
                )

            # Build result
            result = GoalExecutionResult(
                session_id=session.session_id,
                cost_usd=session.cost_usd,
                duration_seconds=self._calculate_duration(
                    session.started_at, session.completed_at
                ),
            )

            # Determine success based on recommendation
            if session.result:
                result.success = session.result.recommendation != QARecommendation.BLOCK
                result.findings_count = len(session.result.findings)
            else:
                # No result means session may have failed
                result.success = False

            self._log("qa_validation_goal_complete", {
                "session_id": session.session_id,
                "success": result.success,
                "findings_count": result.findings_count,
            })

            return result

        except Exception as e:
            self._log("qa_validation_goal_error", {"error": str(e)}, level="error")
            return GoalExecutionResult(
                success=False,
                error=str(e),
            )

    def execute_qa_health_goal(self, goal: QAGoal) -> GoalExecutionResult:
        """Execute a QA health check goal.

        Runs a shallow health check on all endpoints.

        Args:
            goal: The QA health goal to execute.

        Returns:
            GoalExecutionResult with execution details.
        """
        self._log("qa_health_goal_start", {
            "goal_type": goal.goal_type.value,
            "description": goal.description,
        })

        try:
            # Run health check
            session = self.orchestrator.health_check()

            # Build result
            result = GoalExecutionResult(
                session_id=session.session_id,
                cost_usd=session.cost_usd,
                duration_seconds=self._calculate_duration(
                    session.started_at, session.completed_at
                ),
            )

            # Determine success based on test failures
            if session.result:
                result.success = session.result.tests_failed == 0
                result.findings_count = len(session.result.findings)
            else:
                result.success = False

            self._log("qa_health_goal_complete", {
                "session_id": session.session_id,
                "success": result.success,
                "tests_failed": session.result.tests_failed if session.result else 0,
            })

            return result

        except Exception as e:
            self._log("qa_health_goal_error", {"error": str(e)}, level="error")
            return GoalExecutionResult(
                success=False,
                error=str(e),
            )
