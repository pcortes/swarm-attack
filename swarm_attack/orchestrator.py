"""
Spec Debate Orchestrator for Feature Swarm.

This module orchestrates:
1. Spec debate pipeline:
   - SpecAuthor generates initial spec from PRD
   - SpecCritic reviews and scores the spec
   - SpecModerator applies feedback and improves spec
   - Loop continues until success, stalemate, or timeout

2. Issue session orchestration:
   - Claim issue and ensure feature branch
   - TestWriterAgent generates tests
   - CoderAgent implements code
   - VerifierAgent runs tests
   - Retry logic with max retries
   - Git commit and GitHub issue update
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents import (
    AgentResult,
    CoderAgent,
    PrioritizationAgent,
    SpecAuthorAgent,
    SpecCriticAgent,
    SpecModeratorAgent,
    TestWriterAgent,
    VerifierAgent,
)
from swarm_attack.models import FeaturePhase, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.github_client import GitHubClient
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import StateStore


@dataclass
class PipelineResult:
    """
    Result from a spec pipeline execution.

    Tracks the outcome of the debate process including success/failure,
    rounds completed, final scores, and total cost.
    """

    status: str  # "success", "stalemate", "timeout", "failure"
    feature_id: str
    rounds_completed: int
    final_scores: dict[str, float]
    total_cost_usd: float
    error: Optional[str] = None


@dataclass
class IssueSessionResult:
    """
    Result of an issue implementation session.

    Tracks the outcome of the full implementation workflow:
    claim → test → code → verify → commit → release
    """

    status: str  # "success", "failed", "blocked"
    issue_number: int
    session_id: str
    tests_written: int
    tests_passed: int
    tests_failed: int
    commits: list[str]
    cost_usd: float
    retries: int
    error: Optional[str] = None


class Orchestrator:
    """
    Orchestrates the Feature Swarm pipelines.

    Coordinates:
    1. Spec debate pipeline: SpecAuthor, SpecCritic, and SpecModerator agents
       to iteratively improve a spec until it meets quality thresholds.
    2. Issue session: PrioritizationAgent, TestWriterAgent, CoderAgent, and
       VerifierAgent to implement issues with TDD and retry logic.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        author: Optional[SpecAuthorAgent] = None,
        critic: Optional[SpecCriticAgent] = None,
        moderator: Optional[SpecModeratorAgent] = None,
        state_store: Optional[StateStore] = None,
        # Implementation agents (optional, auto-created if not provided)
        prioritization: Optional[PrioritizationAgent] = None,
        test_writer: Optional[TestWriterAgent] = None,
        coder: Optional[CoderAgent] = None,
        verifier: Optional[VerifierAgent] = None,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            author: Optional SpecAuthorAgent (created if not provided).
            critic: Optional SpecCriticAgent (created if not provided).
            moderator: Optional SpecModeratorAgent (created if not provided).
            state_store: Optional state store for persistence.
            prioritization: Optional PrioritizationAgent (created if not provided).
            test_writer: Optional TestWriterAgent (created if not provided).
            coder: Optional CoderAgent (created if not provided).
            verifier: Optional VerifierAgent (created if not provided).
        """
        self.config = config
        self.logger = logger
        self._state_store = state_store

        # Spec debate agents
        self._author = author or SpecAuthorAgent(config, logger)
        self._critic = critic or SpecCriticAgent(config, logger)
        self._moderator = moderator or SpecModeratorAgent(config, logger)

        # Issue session agents (auto-created if not provided)
        self._session_manager: Optional[SessionManager] = None
        self._prioritization = prioritization or PrioritizationAgent(config, logger)
        self._test_writer = test_writer or TestWriterAgent(config, logger)
        self._coder = coder or CoderAgent(config, logger)
        self._verifier = verifier or VerifierAgent(config, logger)
        self._github_client: Optional[GitHubClient] = None

    @property
    def author(self) -> SpecAuthorAgent:
        """Get the author agent."""
        return self._author

    @property
    def critic(self) -> SpecCriticAgent:
        """Get the critic agent."""
        return self._critic

    @property
    def moderator(self) -> SpecModeratorAgent:
        """Get the moderator agent."""
        return self._moderator

    @property
    def state_store(self) -> Optional[StateStore]:
        """Get the state store."""
        return self._state_store

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            log_data = {"orchestrator": "spec_pipeline"}
            if data:
                log_data.update(data)
            self.logger.log(event_type, log_data, level=level)

    def _check_stopping(
        self,
        scores: dict[str, float],
        issues: list[dict[str, Any]],
        prev_scores: Optional[dict[str, float]],
    ) -> str:
        """
        Check stopping conditions for the debate.

        Args:
            scores: Current rubric scores.
            issues: List of issues from the critic.
            prev_scores: Scores from the previous round (if any).

        Returns:
            "success" - All thresholds met, few/no issues
            "stalemate" - No improvement from previous round
            "continue" - Keep iterating
        """
        thresholds = self.config.spec_debate.rubric_thresholds

        # Count issues by severity
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        moderate_count = sum(1 for i in issues if i.get("severity") == "moderate")

        # Check if all scores meet thresholds
        all_pass = all(
            scores.get(dim, 0.0) >= threshold
            for dim, threshold in thresholds.items()
        )

        # SUCCESS: All scores pass AND no critical issues AND <3 moderate issues
        if all_pass and critical_count == 0 and moderate_count < 3:
            return "success"

        # Check for stalemate if we have previous scores
        if prev_scores is not None:
            # Calculate average improvement
            improvements = [
                scores.get(dim, 0.0) - prev_scores.get(dim, 0.0)
                for dim in thresholds.keys()
            ]
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0

            # STALEMATE: Improvement < 0.05
            if avg_improvement < 0.05:
                return "stalemate"

        # CONTINUE: Keep iterating
        return "continue"

    def _update_phase(self, feature_id: str, phase: FeaturePhase) -> None:
        """Update the feature phase in the state store."""
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                state.update_phase(phase)
                self._state_store.save(state)

    def _update_cost(self, feature_id: str, cost_usd: float, phase_name: str) -> None:
        """Update the cost tracking in the state store."""
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                state.add_cost(cost_usd, phase_name)
                self._state_store.save(state)

    def _check_spec_files_indicate_success(self, feature_id: str) -> tuple[bool, dict[str, float]]:
        """
        Check if spec files on disk indicate the debate actually succeeded.

        This handles the case where Claude times out AFTER completing work
        but before the response is returned. The files may already be written
        with successful results even though we got a timeout error.

        Args:
            feature_id: The feature identifier.

        Returns:
            Tuple of (success_indicated, scores_dict).
            success_indicated is True if rubric shows ready_for_approval=true
            and all scores meet thresholds.
        """
        spec_dir = Path(self.config.specs_path) / feature_id
        rubric_path = spec_dir / "spec-rubric.json"
        spec_path = spec_dir / "spec-draft.md"

        # Check if both files exist
        if not rubric_path.exists() or not spec_path.exists():
            return False, {}

        try:
            with open(rubric_path) as f:
                rubric = json.load(f)

            # Check for explicit ready_for_approval flag
            if rubric.get("ready_for_approval", False):
                scores = rubric.get("current_scores", {})
                thresholds = self.config.spec_debate.rubric_thresholds

                # Verify all scores meet thresholds
                all_pass = all(
                    scores.get(dim, 0.0) >= threshold
                    for dim, threshold in thresholds.items()
                )

                if all_pass:
                    self._log(
                        "spec_files_indicate_success",
                        {"feature_id": feature_id, "scores": scores},
                    )
                    return True, scores

        except (json.JSONDecodeError, IOError, KeyError):
            pass

        return False, {}

    def run_spec_pipeline(self, feature_id: str) -> PipelineResult:
        """
        Run the spec debate pipeline for a feature.

        The pipeline:
        1. Author generates spec from PRD
        2. Critic reviews and scores spec
        3. If not passing, Moderator improves spec
        4. Loop until success, stalemate, or max_rounds

        Args:
            feature_id: The feature identifier.

        Returns:
            PipelineResult with status, scores, and cost.
        """
        max_rounds = self.config.spec_debate.max_rounds
        total_cost = 0.0
        final_scores: dict[str, float] = {}
        prev_scores: Optional[dict[str, float]] = None

        # Check feature exists
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state is None:
                return PipelineResult(
                    status="failure",
                    feature_id=feature_id,
                    rounds_completed=0,
                    final_scores={},
                    total_cost_usd=0.0,
                    error=f"Feature '{feature_id}' not found in state store",
                )

        # Update phase to SPEC_IN_PROGRESS
        self._update_phase(feature_id, FeaturePhase.SPEC_IN_PROGRESS)

        self._log("pipeline_start", {"feature_id": feature_id, "max_rounds": max_rounds})

        for round_num in range(1, max_rounds + 1):
            self._log("round_start", {"feature_id": feature_id, "round": round_num})

            # Step 1: Author generates spec (only on first round)
            if round_num == 1:
                self._author.reset()
                author_result = self._author.run({"feature_id": feature_id})
                total_cost += author_result.cost_usd

                if not author_result.success:
                    self._log(
                        "author_failure",
                        {"feature_id": feature_id, "error": author_result.errors},
                        level="error",
                    )
                    self._update_phase(feature_id, FeaturePhase.BLOCKED)
                    return PipelineResult(
                        status="failure",
                        feature_id=feature_id,
                        rounds_completed=0,
                        final_scores={},
                        total_cost_usd=total_cost,
                        error=f"Spec author failed: {author_result.errors[0] if author_result.errors else 'Unknown error'}",
                    )

            # Step 2: Critic reviews spec
            self._critic.reset()
            critic_result = self._critic.run({"feature_id": feature_id})
            total_cost += critic_result.cost_usd

            if not critic_result.success:
                self._log(
                    "critic_failure",
                    {"feature_id": feature_id, "error": critic_result.errors},
                    level="error",
                )
                self._update_phase(feature_id, FeaturePhase.BLOCKED)
                return PipelineResult(
                    status="failure",
                    feature_id=feature_id,
                    rounds_completed=round_num - 1,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                    error=f"Spec critic failed to review: {critic_result.errors[0] if critic_result.errors else 'Unknown error'}",
                )

            # Extract scores and issues from critic result
            scores = critic_result.output.get("scores", {})
            issues = critic_result.output.get("issues", [])

            final_scores = scores
            self._log(
                "round_scores",
                {
                    "feature_id": feature_id,
                    "round": round_num,
                    "scores": scores,
                    "issue_counts": critic_result.output.get("issue_counts", {}),
                },
            )

            # Check stopping conditions
            stop_result = self._check_stopping(scores, issues, prev_scores)

            if stop_result == "success":
                self._log(
                    "pipeline_success",
                    {"feature_id": feature_id, "rounds": round_num, "scores": scores},
                )
                self._update_phase(feature_id, FeaturePhase.SPEC_NEEDS_APPROVAL)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="success",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                )

            if stop_result == "stalemate":
                self._log(
                    "pipeline_stalemate",
                    {"feature_id": feature_id, "rounds": round_num, "scores": scores},
                )
                self._update_phase(feature_id, FeaturePhase.BLOCKED)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="stalemate",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                )

            # Step 3: Moderator improves spec (if not last round)
            if round_num < max_rounds:
                self._moderator.reset()
                moderator_result = self._moderator.run(
                    {"feature_id": feature_id, "round": round_num}
                )
                total_cost += moderator_result.cost_usd

                if not moderator_result.success:
                    # Check if spec files indicate success despite the error
                    # This handles timeout after Claude completed work but before response
                    files_ok, file_scores = self._check_spec_files_indicate_success(feature_id)

                    if files_ok:
                        self._log(
                            "moderator_timeout_recovered",
                            {
                                "feature_id": feature_id,
                                "recovered_from": "file_check",
                                "scores": file_scores,
                            },
                        )
                        self._update_phase(feature_id, FeaturePhase.SPEC_NEEDS_APPROVAL)
                        self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                        return PipelineResult(
                            status="success",
                            feature_id=feature_id,
                            rounds_completed=round_num,
                            final_scores=file_scores,
                            total_cost_usd=total_cost,
                        )

                    # Genuine failure - no recovery possible
                    self._log(
                        "moderator_failure",
                        {"feature_id": feature_id, "error": moderator_result.errors},
                        level="error",
                    )
                    self._update_phase(feature_id, FeaturePhase.BLOCKED)
                    return PipelineResult(
                        status="failure",
                        feature_id=feature_id,
                        rounds_completed=round_num,
                        final_scores=final_scores,
                        total_cost_usd=total_cost,
                        error=f"Spec moderator failed: {moderator_result.errors[0] if moderator_result.errors else 'Unknown error'}",
                    )

                # Use moderator's current scores for next comparison
                prev_scores = moderator_result.output.get("current_scores", scores)
            else:
                prev_scores = scores

        # Reached max rounds - timeout
        self._log(
            "pipeline_timeout",
            {"feature_id": feature_id, "rounds": max_rounds, "scores": final_scores},
        )
        self._update_phase(feature_id, FeaturePhase.BLOCKED)
        self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
        return PipelineResult(
            status="timeout",
            feature_id=feature_id,
            rounds_completed=max_rounds,
            final_scores=final_scores,
            total_cost_usd=total_cost,
        )

    # =========================================================================
    # Issue Session Orchestration
    # =========================================================================

    def _mark_task_skipped(
        self, feature_id: str, issue_number: int, reason: str, blocking_issue: int
    ) -> None:
        """Mark task as SKIPPED in state with reason."""
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                for task in state.tasks:
                    if task.issue_number == issue_number:
                        task.stage = TaskStage.SKIPPED
                        break
                self._state_store.save(state)
                self._log(
                    "task_marked_skipped",
                    {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "reason": reason,
                        "blocking_issue": blocking_issue,
                    },
                    level="warning",
                )

    def _select_issue(self, feature_id: str) -> Optional[int]:
        """
        Select the next issue to work on using PrioritizationAgent.

        Also handles marking tasks as SKIPPED if their dependencies are
        permanently blocked.

        Args:
            feature_id: The feature identifier.

        Returns:
            Issue number if found, None otherwise.
        """
        if self._state_store is None:
            return None

        state = self._state_store.load(feature_id)
        if state is None:
            return None

        # Run prioritization agent
        if self._prioritization:
            self._prioritization.reset()
            result = self._prioritization.run({"state": state})
            if result.success and result.output:
                # First, mark any tasks that should be skipped
                tasks_to_skip = result.output.get("tasks_to_skip", [])
                for skip_info in tasks_to_skip:
                    self._mark_task_skipped(
                        feature_id,
                        skip_info["issue_number"],
                        skip_info["reason"],
                        skip_info["blocking_issue"],
                    )

                # Then return the selected issue
                selected = result.output.get("selected_issue")
                if selected:
                    return selected.issue_number
        return None

    def _get_regression_test_files(self, feature_id: str) -> list[str]:
        """
        Get test files from DONE issues only for regression checking.

        This prevents cascading failures where BLOCKED issues cause
        subsequent issues to fail regression even when their own tests pass.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of test file paths from DONE issues.
        """
        if self._state_store is None:
            return []

        state = self._state_store.load(feature_id)
        if state is None:
            return []

        test_files = []
        tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id

        for task in state.tasks:
            # Only include tests from DONE issues
            if task.stage == TaskStage.DONE:
                test_file = tests_dir / f"test_issue_{task.issue_number}.py"
                if test_file.exists():
                    test_files.append(str(test_file))

        return test_files

    def _run_implementation_cycle(
        self,
        feature_id: str,
        issue_number: int,
        session_id: str,
        retry_number: int = 0,
        previous_failures: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[bool, AgentResult, float]:
        """
        Run one test_writer → coder → verifier cycle.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue to implement.
            session_id: Current session ID for checkpoints.
            retry_number: Current retry attempt (0 = first attempt).
            previous_failures: Failure details from previous verifier run.

        Returns:
            Tuple of (success, verifier_result, total_cost).
        """
        # Get test files from DONE issues only for regression check
        # This prevents BLOCKED issues from causing cascading failures
        # Pass empty list if no DONE issues (disables regression) vs None (run all)
        regression_test_files = self._get_regression_test_files(feature_id)

        context = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            # Pass the list as-is (even if empty) to run targeted regression
            # Empty list means no regression tests, None would run all tests
            "regression_test_files": regression_test_files,
            # NEW: Pass retry context to coder
            "retry_number": retry_number,
            "test_failures": previous_failures or [],
        }
        total_cost = 0.0

        # Run coder
        if self._coder:
            self._coder.reset()
            coder_result = self._coder.run(context)
            total_cost += coder_result.cost_usd

            if self._session_manager:
                self._session_manager.checkpoint(
                    session_id, "coder", "complete", cost_usd=coder_result.cost_usd
                )

            if not coder_result.success:
                return False, coder_result, total_cost

        # Run verifier
        if self._verifier:
            self._verifier.reset()
            verifier_result = self._verifier.run(context)
            total_cost += verifier_result.cost_usd

            if self._session_manager:
                self._session_manager.checkpoint(
                    session_id, "verifier", "complete", cost_usd=verifier_result.cost_usd
                )

            return verifier_result.success, verifier_result, total_cost

        # No verifier - return failure
        return False, AgentResult.failure_result("No verifier agent configured"), total_cost

    def _create_commit(
        self,
        feature_id: str,
        issue_number: int,
        message: str,
    ) -> str:
        """
        Create a git commit with the proper message format.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            message: Commit message body.

        Returns:
            Commit hash string.
        """
        # Format: feat(feature_id): message (#issue_number)
        commit_msg = f"feat({feature_id}): {message} (#{issue_number})"

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.config.repo_root,
                capture_output=True,
                check=True,
            )

            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.config.repo_root,
                    capture_output=True,
                    text=True,
                )
                return hash_result.stdout.strip()

        except subprocess.CalledProcessError:
            pass

        return ""

    def _mark_task_done(self, feature_id: str, issue_number: int) -> None:
        """Mark task as DONE in state."""
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                for task in state.tasks:
                    if task.issue_number == issue_number:
                        task.stage = TaskStage.DONE
                        break
                self._state_store.save(state)

    def _post_github_comment(self, issue_number: int, comment: str) -> bool:
        """Post a comment to a GitHub issue.

        Args:
            issue_number: The GitHub issue number.
            comment: The comment body (markdown supported).

        Returns:
            True if comment was posted successfully, False otherwise.
        """
        try:
            result = subprocess.run(
                ["gh", "issue", "comment", str(issue_number), "--body", comment],
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            # gh CLI not available or failed - not critical
            return False

    def _mark_task_blocked(
        self, feature_id: str, issue_number: int, reason: Optional[str] = None
    ) -> None:
        """Mark task as BLOCKED in state with optional reason.

        Also posts a comment to the GitHub issue explaining why it's blocked.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number to mark as blocked.
            reason: Optional error message explaining why the task is blocked.
        """
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                for task in state.tasks:
                    if task.issue_number == issue_number:
                        task.stage = TaskStage.BLOCKED
                        task.blocked_reason = reason
                        break
                self._state_store.save(state)

        # Post comment to GitHub issue
        if reason:
            comment = f"""## 🚫 Implementation Blocked

**Reason:** {reason}

**Next Steps:**
1. Review the error above and fix the root cause
2. Run `swarm-attack run {feature_id} --issue {issue_number}` to retry

---
*🤖 Posted by swarm-attack*"""
            self._post_github_comment(issue_number, comment)

    def run_issue_session(
        self,
        feature_id: str,
        issue_number: Optional[int] = None,
    ) -> IssueSessionResult:
        """
        Run a complete issue implementation session.

        The session workflow:
        1. Select issue (if not specified) using PrioritizationAgent
        2. Claim issue lock
        3. Ensure feature branch
        4. Run TestWriterAgent to generate tests
        5. Run CoderAgent to implement code
        6. Run VerifierAgent to verify tests pass
        7. If tests fail, retry up to max_implementation_retries
        8. On success: commit, update GitHub issue, mark task done
        9. On blocked: mark task blocked
        10. Release issue lock

        Args:
            feature_id: The feature identifier.
            issue_number: Specific issue to work on. If None, uses PrioritizationAgent.

        Returns:
            IssueSessionResult with status and details.
        """
        total_cost = 0.0
        commits: list[str] = []
        tests_written = 0
        tests_passed = 0
        tests_failed = 0
        retries = 0
        session_id = ""

        # Check feature exists
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state is None:
                return IssueSessionResult(
                    status="failed",
                    issue_number=issue_number or 0,
                    session_id="",
                    tests_written=0,
                    tests_passed=0,
                    tests_failed=0,
                    commits=[],
                    cost_usd=0.0,
                    retries=0,
                    error=f"Feature '{feature_id}' not found",
                )

        # Step 1: Select issue if not specified
        if issue_number is None:
            issue_number = self._select_issue(feature_id)
            if issue_number is None:
                return IssueSessionResult(
                    status="failed",
                    issue_number=0,
                    session_id="",
                    tests_written=0,
                    tests_passed=0,
                    tests_failed=0,
                    commits=[],
                    cost_usd=0.0,
                    retries=0,
                    error="No issue available for work",
                )

        self._log("issue_session_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        # Step 2: Claim issue lock
        if self._session_manager:
            claimed = self._session_manager.claim_issue(feature_id, issue_number)
            if not claimed:
                return IssueSessionResult(
                    status="failed",
                    issue_number=issue_number,
                    session_id="",
                    tests_written=0,
                    tests_passed=0,
                    tests_failed=0,
                    commits=[],
                    cost_usd=0.0,
                    retries=0,
                    error=f"Issue {issue_number} is already claimed/locked",
                )

            # Step 3: Ensure feature branch
            self._session_manager.ensure_feature_branch(feature_id)

            # Start session
            session = self._session_manager.start_session(feature_id, issue_number)
            session_id = session.session_id

        try:
            # Step 4: Run TestWriterAgent
            if self._test_writer:
                context = {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                }
                self._test_writer.reset()
                test_writer_result = self._test_writer.run(context)
                total_cost += test_writer_result.cost_usd

                if self._session_manager:
                    self._session_manager.checkpoint(
                        session_id, "test_writer", "complete", cost_usd=test_writer_result.cost_usd
                    )

                if not test_writer_result.success:
                    self._log("test_writer_failure", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "error": test_writer_result.errors,
                    }, level="error")

                    if self._session_manager:
                        self._session_manager.end_session(session_id, "failed")
                        self._session_manager.release_issue(feature_id, issue_number)

                    return IssueSessionResult(
                        status="failed",
                        issue_number=issue_number,
                        session_id=session_id,
                        tests_written=0,
                        tests_passed=0,
                        tests_failed=0,
                        commits=[],
                        cost_usd=total_cost,
                        retries=0,
                        error=f"Test writer failed: {test_writer_result.errors[0] if test_writer_result.errors else 'Unknown error'}",
                    )

                tests_written = test_writer_result.output.get("tests_generated", 0)

            # Step 5-7: Implementation cycle with retries
            max_retries = getattr(self.config.sessions, "max_implementation_retries", 3)
            success = False
            verifier_result: Optional[AgentResult] = None
            attempt = 0
            # Track failures from previous run to pass to coder on retry
            previous_failures: list[dict[str, Any]] = []

            while attempt <= max_retries:
                cycle_success, verifier_result, cycle_cost = self._run_implementation_cycle(
                    feature_id,
                    issue_number,
                    session_id,
                    retry_number=attempt,
                    previous_failures=previous_failures,
                )
                total_cost += cycle_cost

                if cycle_success:
                    success = True
                    # retries = number of attempts after the first one
                    retries = attempt
                    break

                # Check if it was a coder failure (not verifier)
                if verifier_result and not verifier_result.output:
                    # Coder failed - no retry
                    self._log("coder_failure", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "error": verifier_result.errors,
                    }, level="error")

                    if self._session_manager:
                        self._session_manager.end_session(session_id, "failed")
                        self._session_manager.release_issue(feature_id, issue_number)

                    return IssueSessionResult(
                        status="failed",
                        issue_number=issue_number,
                        session_id=session_id,
                        tests_written=tests_written,
                        tests_passed=0,
                        tests_failed=0,
                        commits=[],
                        cost_usd=total_cost,
                        retries=attempt,
                        error=f"Coder failed: {verifier_result.errors[0] if verifier_result.errors else 'Unknown error'}",
                    )

                # Extract failures from verifier result for next retry
                if verifier_result and verifier_result.output:
                    previous_failures = verifier_result.output.get("failures", [])
                    # Also check regression failures if issue tests passed but regression failed
                    if not previous_failures:
                        regression_check = verifier_result.output.get("regression_check") or {}
                        previous_failures = regression_check.get("failures", [])

                # Verifier failed - retry if we haven't exceeded max_retries
                attempt += 1
                if attempt <= max_retries:
                    self._log("issue_session_retry", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "retry": attempt,
                        "failures_to_fix": len(previous_failures),
                    })
                else:
                    # We've exceeded max retries
                    retries = max_retries
                    break

            # Get test results from verifier
            if verifier_result and verifier_result.output:
                tests_passed = verifier_result.output.get("tests_passed", 0)
                tests_failed = verifier_result.output.get("tests_failed", 0)

            # Step 8-9: Handle success or blocked
            if success:
                # SAFETY CHECK: Verify tests actually pass before marking DONE
                # This prevents issues being marked DONE if verifier had a bug
                if tests_failed > 0:
                    self._log("issue_session_false_positive", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "tests_failed": tests_failed,
                        "tests_passed": tests_passed,
                        "warning": "Verifier reported success but tests_failed > 0",
                    }, level="warning")
                    success = False  # Override - don't mark DONE with failing tests

            if success:
                # Create commit
                commit_hash = self._create_commit(
                    feature_id,
                    issue_number,
                    f"Implement issue #{issue_number}",
                )
                if commit_hash:
                    commits.append(commit_hash)
                    if self._session_manager:
                        self._session_manager.add_commit(session_id, commit_hash)

                # Update GitHub issue
                if self._github_client:
                    self._github_client.close_issue(issue_number)

                # Mark task done
                self._mark_task_done(feature_id, issue_number)

                # Update cost in state
                self._update_cost(feature_id, total_cost, "IMPLEMENTATION")

                # End session
                if self._session_manager:
                    self._session_manager.end_session(session_id, "success")
                    self._session_manager.release_issue(feature_id, issue_number)

                self._log("issue_session_success", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "commits": commits,
                    "cost_usd": total_cost,
                })

                return IssueSessionResult(
                    status="success",
                    issue_number=issue_number,
                    session_id=session_id,
                    tests_written=tests_written,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    commits=commits,
                    cost_usd=total_cost,
                    retries=retries,
                )

            else:
                # Max retries exceeded - build error message first
                error_msg = "Max retries exceeded"
                if verifier_result and verifier_result.errors:
                    error_msg = f"{error_msg}: {verifier_result.errors[0]}"
                elif verifier_result and verifier_result.output:
                    regression = verifier_result.output.get("regression_check", {})
                    if regression and not regression.get("passed", True):
                        failed_count = regression.get("failed_count", 0)
                        error_msg = f"Regression detected: {failed_count} tests failed in full suite"

                # Mark blocked with reason
                self._mark_task_blocked(feature_id, issue_number, reason=error_msg)

                # Update cost in state
                self._update_cost(feature_id, total_cost, "IMPLEMENTATION")

                # End session
                if self._session_manager:
                    self._session_manager.end_session(session_id, "failed")
                    self._session_manager.release_issue(feature_id, issue_number)

                self._log("issue_session_blocked", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "retries": retries,
                    "error": error_msg,
                })

                return IssueSessionResult(
                    status="blocked",
                    issue_number=issue_number,
                    session_id=session_id,
                    tests_written=tests_written,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    commits=[],
                    cost_usd=total_cost,
                    retries=retries,
                    error=error_msg,
                )

        except Exception as e:
            # Handle unexpected errors
            if self._session_manager:
                self._session_manager.end_session(session_id, "failed")
                self._session_manager.release_issue(feature_id, issue_number)

            self._log("issue_session_error", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": str(e),
            }, level="error")

            return IssueSessionResult(
                status="failed",
                issue_number=issue_number,
                session_id=session_id,
                tests_written=tests_written,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                commits=[],
                cost_usd=total_cost,
                retries=retries,
                error=str(e),
            )
