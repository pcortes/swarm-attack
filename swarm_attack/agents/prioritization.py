"""
Prioritization Agent for Feature Swarm.

This agent determines which issue to work on next based on:
- Dependencies (blocked issues are filtered out)
- Estimated size (smaller is preferred)
- Business value score (higher is preferred)
- Technical risk score (lower risk is preferred)

The agent does NOT use LLM - it applies a deterministic scoring algorithm.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent
from swarm_attack.models import RunState, TaskRef, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class PrioritizationAgent(BaseAgent):
    """
    Agent that determines which issue to work on next.

    Uses a scoring algorithm to rank READY tasks by:
    - Size (small > medium > large)
    - Business value (higher is better)
    - Technical risk (lower is better)

    Filters out blocked tasks (those with unmet dependencies).
    """

    name = "prioritization"

    # Scoring weights
    SIZE_SCORES = {
        "small": 0.5,
        "medium": 0.25,
        "large": 0.0,
    }
    DEFAULT_SIZE_SCORE = 0.25  # Default to medium if unknown

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the Prioritization agent.

        Note: llm_runner is accepted for interface compatibility but not used.
        """
        super().__init__(config, logger, llm_runner, state_store)

    def score(self, task: TaskRef) -> float:
        """
        Calculate a priority score for a task.

        Higher scores indicate higher priority.

        Scoring formula:
        - Size bonus: small=0.5, medium=0.25, large=0.0
        - Business value: 0.0 to 1.0
        - Risk penalty: (1.0 - risk) * 0.5

        Args:
            task: The task to score.

        Returns:
            Float score where higher is better.
        """
        score = 0.0

        # Size bonus (smaller is better)
        size_score = self.SIZE_SCORES.get(task.estimated_size, self.DEFAULT_SIZE_SCORE)
        score += size_score

        # Business value (direct addition)
        score += task.business_value_score

        # Technical risk (lower is better, so we add inverse)
        risk_bonus = (1.0 - task.technical_risk_score) * 0.5
        score += risk_bonus

        return score

    def filter_unblocked(
        self, tasks: list[TaskRef], state: RunState
    ) -> list[TaskRef]:
        """
        Filter out tasks that are blocked by incomplete dependencies.

        A task is blocked if any of its dependencies are not in DONE stage.

        Args:
            tasks: List of tasks to filter.
            state: Current run state containing all tasks.

        Returns:
            List of unblocked tasks.
        """
        # Build a map of task status by issue number
        task_stages = {t.issue_number: t.stage for t in state.tasks}

        unblocked = []
        for task in tasks:
            is_blocked = False

            for dep_issue_number in task.dependencies:
                # Check if dependency exists and is DONE
                dep_stage = task_stages.get(dep_issue_number)

                if dep_stage is None:
                    # Dependency doesn't exist - treat as blocked
                    is_blocked = True
                    break
                elif dep_stage != TaskStage.DONE:
                    # Dependency exists but is not done
                    is_blocked = True
                    break

            if not is_blocked:
                unblocked.append(task)

        return unblocked

    def get_next_issue(self, state: RunState) -> Optional[TaskRef]:
        """
        Get the next issue to work on.

        Filters to READY tasks, removes blocked ones, scores the rest,
        and returns the highest-scoring task.

        Args:
            state: Current run state with all tasks.

        Returns:
            Highest priority TaskRef, or None if no tasks are available.
        """
        # Get only READY tasks
        ready_tasks = [t for t in state.tasks if t.stage == TaskStage.READY]

        if not ready_tasks:
            return None

        # Filter out blocked tasks
        unblocked = self.filter_unblocked(ready_tasks, state)

        if not unblocked:
            return None

        # Score and sort
        scored = [(task, self.score(task)) for task in unblocked]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0]

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute prioritization to select the next issue.

        Args:
            context: Dictionary containing:
                - state: RunState with tasks to prioritize (required)

        Returns:
            AgentResult with:
                - success: True if prioritization completed
                - output: Dict with selected_issue and scored_candidates
                - errors: List of any errors
        """
        state = context.get("state")
        if state is None:
            return AgentResult.failure_result(
                "Missing required context: state (RunState)"
            )

        self._log("prioritization_start", {"feature_id": state.feature_id})
        self.checkpoint("started")

        # Get READY tasks
        ready_tasks = [t for t in state.tasks if t.stage == TaskStage.READY]

        # Filter unblocked
        unblocked = self.filter_unblocked(ready_tasks, state)

        # Score all unblocked tasks
        scored_candidates = []
        for task in unblocked:
            task_score = self.score(task)
            scored_candidates.append({
                "issue_number": task.issue_number,
                "title": task.title,
                "score": task_score,
                "size": task.estimated_size,
                "business_value": task.business_value_score,
                "technical_risk": task.technical_risk_score,
            })

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Select the top one (if any)
        selected_issue = None
        if scored_candidates:
            top = scored_candidates[0]
            # Find the actual TaskRef
            for task in unblocked:
                if task.issue_number == top["issue_number"]:
                    selected_issue = task
                    break

        self.checkpoint("complete")

        # Build output
        output = {
            "selected_issue": selected_issue,
            "scored_candidates": scored_candidates,
            "total_ready": len(ready_tasks),
            "total_unblocked": len(unblocked),
        }

        if selected_issue is None:
            output["message"] = "No tasks available for work"
            self._log(
                "prioritization_complete",
                {"feature_id": state.feature_id, "selected": None, "reason": "no_tasks"},
            )
        else:
            self._log(
                "prioritization_complete",
                {
                    "feature_id": state.feature_id,
                    "selected_issue": selected_issue.issue_number,
                    "score": scored_candidates[0]["score"],
                },
            )

        return AgentResult.success_result(output=output)
