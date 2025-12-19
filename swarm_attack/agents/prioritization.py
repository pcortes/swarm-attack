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

    def check_dependencies(
        self, task: TaskRef, state: RunState
    ) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Check if a task's dependencies allow it to proceed.

        A task can proceed if all dependencies are DONE.
        A task is permanently blocked if any dependency is BLOCKED or SKIPPED.
        A task is temporarily blocked if dependencies are still in progress.

        Args:
            task: The task to check.
            state: Current run state containing all tasks.

        Returns:
            Tuple of (can_proceed, block_reason, blocking_issue_number)
            - can_proceed: True if all dependencies are satisfied
            - block_reason: None if can proceed, otherwise "blocked", "skipped", "incomplete", or "missing"
            - blocking_issue_number: The issue number causing the block (if any)
        """
        task_stages = {t.issue_number: t.stage for t in state.tasks}

        for dep_issue_number in task.dependencies:
            dep_stage = task_stages.get(dep_issue_number)

            if dep_stage is None:
                # Dependency doesn't exist
                return False, "missing", dep_issue_number
            elif dep_stage == TaskStage.BLOCKED:
                # Dependency is permanently blocked - this task can never succeed
                return False, "blocked", dep_issue_number
            elif dep_stage == TaskStage.SKIPPED:
                # Dependency was skipped - this task can never succeed
                return False, "skipped", dep_issue_number
            elif dep_stage == TaskStage.SPLIT:
                # Dependency was split - wait for children to complete
                # (Note: dependencies should be rewired to children, but handle edge case)
                return False, "split", dep_issue_number
            elif dep_stage != TaskStage.DONE:
                # Dependency exists but is not done yet (still in progress)
                return False, "incomplete", dep_issue_number

        return True, None, None

    def filter_unblocked(
        self, tasks: list[TaskRef], state: RunState
    ) -> tuple[list[TaskRef], list[tuple[TaskRef, str, int]]]:
        """
        Filter out tasks that are blocked by incomplete dependencies.

        Args:
            tasks: List of tasks to filter.
            state: Current run state containing all tasks.

        Returns:
            Tuple of (unblocked_tasks, permanently_blocked_tasks)
            - unblocked_tasks: Tasks ready to work on
            - permanently_blocked_tasks: List of (task, reason, blocking_issue) for tasks
              that can never succeed due to blocked/skipped dependencies
        """
        unblocked = []
        permanently_blocked = []

        for task in tasks:
            can_proceed, block_reason, blocking_issue = self.check_dependencies(task, state)

            if can_proceed:
                unblocked.append(task)
            elif block_reason in ("blocked", "skipped"):
                # This task can never succeed - its dependency failed
                permanently_blocked.append((task, block_reason, blocking_issue))
            # "incomplete" and "missing" are temporary - task stays in BACKLOG/READY

        return unblocked, permanently_blocked

    def get_next_issue(
        self, state: RunState
    ) -> tuple[Optional[TaskRef], list[tuple[TaskRef, str, int]]]:
        """
        Get the next issue to work on.

        Filters to READY/BACKLOG tasks, removes blocked ones, scores the rest,
        and returns the highest-scoring task. Also returns tasks that should
        be marked as SKIPPED due to permanently blocked dependencies.

        Args:
            state: Current run state with all tasks.

        Returns:
            Tuple of (selected_task, tasks_to_skip)
            - selected_task: Highest priority TaskRef, or None if no tasks available
            - tasks_to_skip: List of (task, reason, blocking_issue) for tasks that
              should be marked SKIPPED due to blocked/skipped dependencies
        """
        # Get READY and BACKLOG tasks (BACKLOG may become ready if deps are done)
        candidate_tasks = [
            t for t in state.tasks
            if t.stage in (TaskStage.READY, TaskStage.BACKLOG)
        ]

        if not candidate_tasks:
            return None, []

        # Filter out blocked tasks and identify permanently blocked ones
        unblocked, permanently_blocked = self.filter_unblocked(candidate_tasks, state)

        if not unblocked:
            return None, permanently_blocked

        # Score and sort
        scored = [(task, self.score(task)) for task in unblocked]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0], permanently_blocked

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute prioritization to select the next issue.

        Args:
            context: Dictionary containing:
                - state: RunState with tasks to prioritize (required)

        Returns:
            AgentResult with:
                - success: True if prioritization completed
                - output: Dict with selected_issue, scored_candidates, and tasks_to_skip
                - errors: List of any errors
        """
        state = context.get("state")
        if state is None:
            return AgentResult.failure_result(
                "Missing required context: state (RunState)"
            )

        self._log("prioritization_start", {"feature_id": state.feature_id})
        self.checkpoint("started")

        # Get candidate tasks (READY and BACKLOG)
        candidate_tasks = [
            t for t in state.tasks
            if t.stage in (TaskStage.READY, TaskStage.BACKLOG)
        ]

        # Filter unblocked and identify permanently blocked
        unblocked, permanently_blocked = self.filter_unblocked(candidate_tasks, state)

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

        # Build list of tasks to skip (due to blocked dependencies)
        tasks_to_skip = [
            {
                "issue_number": task.issue_number,
                "title": task.title,
                "reason": reason,
                "blocking_issue": blocking_issue,
            }
            for task, reason, blocking_issue in permanently_blocked
        ]

        self.checkpoint("complete")

        # Build output
        output = {
            "selected_issue": selected_issue,
            "scored_candidates": scored_candidates,
            "tasks_to_skip": tasks_to_skip,
            "total_candidates": len(candidate_tasks),
            "total_unblocked": len(unblocked),
            "total_permanently_blocked": len(permanently_blocked),
        }

        if selected_issue is None:
            output["message"] = "No tasks available for work"
            self._log(
                "prioritization_complete",
                {
                    "feature_id": state.feature_id,
                    "selected": None,
                    "reason": "no_tasks",
                    "tasks_to_skip": len(tasks_to_skip),
                },
            )
        else:
            self._log(
                "prioritization_complete",
                {
                    "feature_id": state.feature_id,
                    "selected_issue": selected_issue.issue_number,
                    "score": scored_candidates[0]["score"],
                    "tasks_to_skip": len(tasks_to_skip),
                },
            )

        # Log any tasks being skipped
        for skip_info in tasks_to_skip:
            self._log(
                "task_skipped_dependency_blocked",
                {
                    "feature_id": state.feature_id,
                    "issue_number": skip_info["issue_number"],
                    "reason": skip_info["reason"],
                    "blocking_issue": skip_info["blocking_issue"],
                },
                level="warning",
            )

        return AgentResult.success_result(output=output)
