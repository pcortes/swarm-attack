"""
Spec Debate Orchestrator for Feature Swarm.

This module orchestrates:
1. Spec debate pipeline:
   - SpecAuthor generates initial spec from PRD
   - SpecCritic reviews and scores the spec
   - SpecModerator applies feedback and improves spec
   - Loop continues until success, stalemate, or timeout

2. Issue session orchestration (thick-agent architecture):
   - Claim issue and ensure feature branch
   - CoderAgent (Implementation Agent) handles full TDD workflow:
     - Writes tests first (RED phase)
     - Implements code (GREEN phase)
     - Iterates until tests pass
   - VerifierAgent runs full test suite
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

    status: str  # "success", "stalemate", "disagreement", "timeout", "failure"
    feature_id: str
    rounds_completed: int
    final_scores: dict[str, float]
    total_cost_usd: float
    error: Optional[str] = None
    message: Optional[str] = None  # Human-readable summary
    rejected_issues: Optional[list[dict]] = None  # For disagreement status


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
    2. Issue session: PrioritizationAgent and CoderAgent (Implementation Agent)
       to implement issues with full TDD workflow in a single context window.
       The CoderAgent handles test writing + implementation + verification iteration.
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
        coder: Optional[CoderAgent] = None,
        verifier: Optional[VerifierAgent] = None,
        # Progress callback for CLI output
        progress_callback: Optional[Any] = None,
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
            coder: Optional CoderAgent - Implementation Agent with full TDD workflow.
            verifier: Optional VerifierAgent (created if not provided).
            progress_callback: Optional callback function(event: str, data: dict) for progress.
        """
        self.config = config
        self.logger = logger
        self._state_store = state_store
        self._progress_callback = progress_callback

        # Spec debate agents
        self._author = author or SpecAuthorAgent(config, logger)
        self._critic = critic or SpecCriticAgent(config, logger)
        self._moderator = moderator or SpecModeratorAgent(config, logger)

        # Issue session agents (auto-created if not provided)
        # Note: Thick-agent architecture - CoderAgent handles full TDD workflow
        # (test writing + implementation + verification iteration)
        self._session_manager: Optional[SessionManager] = None
        self._prioritization = prioritization or PrioritizationAgent(config, logger)
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

    def _emit_progress(self, event: str, data: Optional[dict] = None) -> None:
        """Emit progress event to callback if configured."""
        if self._progress_callback:
            self._progress_callback(event, data or {})

    # =========================================================================
    # Rejection Memory Methods (Debate Loop Enhancement)
    # =========================================================================

    def _generate_semantic_key(self, issue_text: str) -> str:
        """
        Generate stable semantic key from issue text.

        Algorithm:
        1. Lowercase, remove punctuation
        2. Remove stopwords (should, would, implement, need, add, etc.)
        3. Take first 3 significant words (>4 chars)
        4. Sort and join with underscore

        Example: "Should implement refresh token rotation" -> "refresh_rotation_token"

        Args:
            issue_text: The issue description text.

        Returns:
            Stable semantic key string.
        """
        import re
        import string

        # Stopwords to filter out (common in spec issues)
        stopwords = {
            "should", "would", "could", "must", "need", "needs", "implement",
            "implementing", "implementation", "add", "adding", "include",
            "including", "require", "requires", "required", "missing", "ensure",
            "consider", "provide", "provides", "support", "supports", "handle",
            "handling", "define", "defining", "specify", "specifying", "document",
            "documenting", "update", "updating", "create", "creating", "have",
            "having", "make", "making", "there", "that", "this", "with", "from",
            "into", "about", "also", "being", "been", "does", "done", "each",
            "more", "most", "other", "some", "such", "than", "then", "very",
            "what", "when", "where", "which", "while", "will", "your", "their",
        }

        # Lowercase and remove punctuation
        text = issue_text.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))

        # Split into words and filter
        words = text.split()
        significant_words = [
            w for w in words
            if w not in stopwords and len(w) > 4
        ]

        # Take first 3 significant words and sort for stability
        key_words = sorted(significant_words[:3])

        # Join with underscore
        return "_".join(key_words) if key_words else "generic_issue"

    def _build_rejection_context_for_critic(self, feature_id: str) -> str:
        """
        Build rejection history context to inject into Critic prompt.

        Returns formatted markdown block with:
        - REJECTED issues (with PRD citations)
        - DEFERRED issues
        - Instructions for dispute mechanism

        Args:
            feature_id: The feature identifier.

        Returns:
            Formatted rejection context string, or empty string if no history.
        """
        if self._state_store is None:
            return ""

        state = self._state_store.load(feature_id)
        if state is None:
            return ""

        # Get disposition history from state
        disposition_history = getattr(state, "disposition_history", [])
        if not disposition_history:
            return ""

        # Separate rejected and deferred issues
        rejected_issues: list[dict] = []
        deferred_issues: list[dict] = []

        for disp in disposition_history:
            classification = disp.get("classification", "").upper()
            if classification == "REJECT":
                rejected_issues.append(disp)
            elif classification == "DEFER":
                deferred_issues.append(disp)

        # Limit to 8-10 most recent to stay token-efficient
        rejected_issues = rejected_issues[-8:]
        deferred_issues = deferred_issues[-2:]

        if not rejected_issues and not deferred_issues:
            return ""

        # Build the context block
        lines = [
            "## Prior Round Context (READ CAREFULLY)",
            "",
        ]

        if rejected_issues:
            lines.extend([
                "### REJECTED ISSUES (Do Not Re-raise)",
                "",
                "The following issues were previously raised and **REJECTED** by the architect.",
                "They are out of scope or based on a misunderstanding. Do NOT re-raise these:",
                "",
            ])
            for i, rej in enumerate(rejected_issues, 1):
                issue_id = rej.get("issue_id", f"R?-{i}")
                original = rej.get("original_issue", "Unknown issue")
                reasoning = rej.get("reasoning", "No reasoning provided")
                semantic_key = rej.get("semantic_key", self._generate_semantic_key(original))
                lines.extend([
                    f"**{issue_id}** (key: `{semantic_key}`)",
                    f"- Issue: {original}",
                    f"- Rejection reason: {reasoning}",
                    "",
                ])

        if deferred_issues:
            lines.extend([
                "### DEFERRED ISSUES (Valid but Out of Scope)",
                "",
                "These were acknowledged as valid but deferred to future iterations:",
                "",
            ])
            for i, def_issue in enumerate(deferred_issues, 1):
                issue_id = def_issue.get("issue_id", f"D?-{i}")
                original = def_issue.get("original_issue", "Unknown issue")
                lines.extend([
                    f"**{issue_id}**: {original}",
                    "",
                ])

        # Add dispute instructions
        lines.extend([
            "### If You Disagree With a Rejection",
            "",
            "If you believe a rejected issue is **genuinely critical** (security, compliance,",
            "or correctness), you may escalate it via the `disputed_issues` array.",
            "",
            "Add to `\"disputed_issues\"` (NOT `\"issues\"`):",
            "```json",
            "{",
            '  "original_issue_id": "R1-4",',
            '  "dispute_category": "security|compliance|correctness",',
            '  "evidence": "Specific technical evidence why this matters",',
            '  "risk_if_ignored": "Concrete impact of not addressing",',
            '  "recommendation": "Suggested action for human review"',
            "}",
            "```",
            "",
            "**Note:** Frivolous disputes waste human review time. Only dispute if genuinely critical.",
            "",
        ])

        return "\n".join(lines)

    def _detect_semantic_disagreement(
        self,
        current_dispositions: list[dict[str, Any]],
        previous_dispositions: list[dict[str, Any]],
        feature_id: str,
    ) -> dict[str, Any]:
        """
        Detect if same issues are being repeatedly rejected.

        Strategy 1 (preferred): Use Moderator's `repeat_of` tags
        Strategy 2 (fallback): Use semantic key matching
        Strategy 3 (fallback): Use SequenceMatcher similarity >= 0.7

        Args:
            current_dispositions: Dispositions from current round.
            previous_dispositions: Dispositions from previous round.
            feature_id: The feature identifier for logging.

        Returns:
            {"deadlock": bool, "reason": str, "repeated_issues": list}
        """
        from difflib import SequenceMatcher

        if not current_dispositions or not previous_dispositions:
            return {"deadlock": False, "reason": "insufficient_data", "repeated_issues": []}

        # Get current rejected issues
        current_rejected = [
            d for d in current_dispositions
            if d.get("classification", "").upper() == "REJECT"
        ]

        # Get previous rejected issues
        previous_rejected = [
            d for d in previous_dispositions
            if d.get("classification", "").upper() == "REJECT"
        ]

        if not current_rejected or not previous_rejected:
            return {"deadlock": False, "reason": "no_rejections", "repeated_issues": []}

        repeated_issues: list[dict] = []

        for curr_rej in current_rejected:
            curr_issue = curr_rej.get("original_issue", "")
            curr_semantic_key = curr_rej.get("semantic_key", "")
            curr_repeat_of = curr_rej.get("repeat_of", "")
            curr_consecutive = curr_rej.get("consecutive_rejections", 1)

            # Strategy 1: Check explicit repeat_of tag
            if curr_repeat_of:
                for prev_rej in previous_rejected:
                    prev_id = prev_rej.get("issue_id", "")
                    if prev_id == curr_repeat_of:
                        repeated_issues.append({
                            "current_issue_id": curr_rej.get("issue_id", ""),
                            "previous_issue_id": prev_id,
                            "match_strategy": "repeat_of_tag",
                            "consecutive_count": curr_consecutive,
                            "issue_text": curr_issue,
                        })
                        break
                continue

            # Strategy 2: Semantic key matching
            if curr_semantic_key:
                for prev_rej in previous_rejected:
                    prev_semantic_key = prev_rej.get("semantic_key", "")
                    if prev_semantic_key and curr_semantic_key == prev_semantic_key:
                        repeated_issues.append({
                            "current_issue_id": curr_rej.get("issue_id", ""),
                            "previous_issue_id": prev_rej.get("issue_id", ""),
                            "match_strategy": "semantic_key",
                            "semantic_key": curr_semantic_key,
                            "issue_text": curr_issue,
                        })
                        break
                else:
                    # Strategy 3: Fuzzy string matching as fallback
                    prev_issue = ""
                    for prev_rej in previous_rejected:
                        prev_issue = prev_rej.get("original_issue", "")
                        if prev_issue:
                            ratio = SequenceMatcher(None, curr_issue.lower(), prev_issue.lower()).ratio()
                            if ratio >= 0.7:
                                repeated_issues.append({
                                    "current_issue_id": curr_rej.get("issue_id", ""),
                                    "previous_issue_id": prev_rej.get("issue_id", ""),
                                    "match_strategy": "fuzzy_match",
                                    "similarity_ratio": ratio,
                                    "issue_text": curr_issue,
                                })
                                break
            else:
                # No semantic key, use Strategy 3 only
                for prev_rej in previous_rejected:
                    prev_issue = prev_rej.get("original_issue", "")
                    if prev_issue:
                        ratio = SequenceMatcher(None, curr_issue.lower(), prev_issue.lower()).ratio()
                        if ratio >= 0.7:
                            repeated_issues.append({
                                "current_issue_id": curr_rej.get("issue_id", ""),
                                "previous_issue_id": prev_rej.get("issue_id", ""),
                                "match_strategy": "fuzzy_match",
                                "similarity_ratio": ratio,
                                "issue_text": curr_issue,
                            })
                            break

        # Determine if we have a deadlock
        disagreement_threshold = self.config.spec_debate.disagreement_threshold
        is_deadlock = len(repeated_issues) >= disagreement_threshold

        if is_deadlock:
            self._log(
                "semantic_disagreement_detected",
                {
                    "feature_id": feature_id,
                    "repeated_count": len(repeated_issues),
                    "threshold": disagreement_threshold,
                    "repeated_issues": repeated_issues,
                },
            )

        return {
            "deadlock": is_deadlock,
            "reason": "repeated_rejections" if is_deadlock else "below_threshold",
            "repeated_issues": repeated_issues,
        }

    def _check_stopping(
        self,
        scores: dict[str, float],
        issues: list[dict[str, Any]],
        prev_scores: Optional[dict[str, float]],
        dispositions: Optional[list[dict[str, Any]]] = None,
        prev_dispositions: Optional[list[dict[str, Any]]] = None,
        consecutive_no_improvement: int = 0,
        feature_id: str = "",
    ) -> tuple[str, int]:
        """
        Check stopping conditions for the debate.

        Args:
            scores: Current rubric scores.
            issues: List of issues from the critic.
            prev_scores: Scores from the previous round (if any).
            dispositions: Current round dispositions from moderator.
            prev_dispositions: Previous round dispositions.
            consecutive_no_improvement: Count of rounds with no score improvement.
            feature_id: Feature identifier for semantic disagreement detection.

        Returns:
            Tuple of (status, consecutive_no_improvement):
            - "success" - All thresholds met, few/no issues
            - "stalemate" - N consecutive rounds of no improvement
            - "disagreement" - Moderator rejected same issues multiple rounds
            - "continue" - Keep iterating
        """
        thresholds = self.config.spec_debate.rubric_thresholds
        stalemate_threshold = self.config.spec_debate.consecutive_stalemate_threshold

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
            return "success", 0

        # Check for disagreement using semantic matching if we have both dispositions
        if dispositions and prev_dispositions:
            disagreement_result = self._detect_semantic_disagreement(
                dispositions,
                prev_dispositions,
                feature_id,
            )
            if disagreement_result["deadlock"]:
                return "disagreement", consecutive_no_improvement

        # Check for stalemate if we have previous scores
        if prev_scores is not None:
            # Calculate average improvement
            improvements = [
                scores.get(dim, 0.0) - prev_scores.get(dim, 0.0)
                for dim in thresholds.keys()
            ]
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0

            # Track consecutive no-improvement rounds
            if avg_improvement < 0.05:
                consecutive_no_improvement += 1
                # STALEMATE: N consecutive rounds of no improvement
                if consecutive_no_improvement >= stalemate_threshold:
                    return "stalemate", consecutive_no_improvement
            else:
                consecutive_no_improvement = 0

        # CONTINUE: Keep iterating
        return "continue", consecutive_no_improvement

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
        4. Loop until success, stalemate, disagreement, or max_rounds

        Args:
            feature_id: The feature identifier.

        Returns:
            PipelineResult with status, scores, and cost.
        """
        max_rounds = self.config.spec_debate.max_rounds
        total_cost = 0.0
        final_scores: dict[str, float] = {}
        prev_scores: Optional[dict[str, float]] = None

        # Track dispositions across rounds for disagreement detection
        issue_history: list[dict[str, Any]] = []
        prev_dispositions: Optional[list[dict[str, Any]]] = None
        consecutive_no_improvement = 0

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
                self._emit_progress("author_start", {"feature_id": feature_id})
                self._author.reset()
                author_result = self._author.run({"feature_id": feature_id})
                total_cost += author_result.cost_usd

                if author_result.success:
                    spec_path = author_result.output.get("spec_path", "")
                    self._emit_progress("author_complete", {
                        "feature_id": feature_id,
                        "spec_path": spec_path,
                        "cost_usd": author_result.cost_usd,
                    })

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

            # Step 2: Critic reviews spec (with rejection context for round 2+)
            self._emit_progress("critic_start", {"feature_id": feature_id, "round": round_num})
            self._critic.reset()
            # Build rejection context from prior dispositions
            rejection_context = self._build_rejection_context_for_critic(feature_id) if round_num > 1 else ""
            critic_result = self._critic.run({
                "feature_id": feature_id,
                "rejection_context": rejection_context,
            })
            total_cost += critic_result.cost_usd

            if critic_result.success:
                self._emit_progress("critic_complete", {
                    "feature_id": feature_id,
                    "round": round_num,
                    "scores": critic_result.output.get("scores", {}),
                    "recommendation": critic_result.output.get("recommendation", ""),
                    "issue_counts": critic_result.output.get("issue_counts", {}),
                    "cost_usd": critic_result.cost_usd,
                })

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

            # Step 3: Moderator improves spec (if not last round)
            current_dispositions: Optional[list[dict[str, Any]]] = None
            # Extract disputed_issues from critic result for escalation
            disputed_issues = critic_result.output.get("disputed_issues", [])
            if round_num < max_rounds:
                self._emit_progress("moderator_start", {"feature_id": feature_id, "round": round_num})
                self._moderator.reset()
                moderator_result = self._moderator.run({
                    "feature_id": feature_id,
                    "round": round_num,
                    "prior_dispositions": issue_history,
                    "disputed_issues": disputed_issues,  # Pass for escalation handling
                })
                total_cost += moderator_result.cost_usd

                if moderator_result.success:
                    disposition_counts = moderator_result.output.get("disposition_counts", {})
                    self._emit_progress("moderator_complete", {
                        "feature_id": feature_id,
                        "round": round_num,
                        "accepted": disposition_counts.get("accepted", 0),
                        "rejected": disposition_counts.get("rejected", 0),
                        "deferred": disposition_counts.get("deferred", 0),
                        "partial": disposition_counts.get("partial", 0),
                        "cost_usd": moderator_result.cost_usd,
                    })

                if not moderator_result.success:
                    # Check if spec files indicate success despite the error
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

                # Extract dispositions from moderator result
                current_dispositions = moderator_result.output.get("dispositions", [])
                if current_dispositions:
                    issue_history.extend(current_dispositions)

                # Use moderator's current scores for next comparison
                prev_scores = moderator_result.output.get("current_scores", scores)
            else:
                prev_scores = scores

            # Check stopping conditions (after moderator for disposition tracking)
            stop_result, consecutive_no_improvement = self._check_stopping(
                scores,
                issues,
                prev_scores,
                current_dispositions,
                prev_dispositions,
                consecutive_no_improvement,
                feature_id,
            )

            # Store current dispositions for next round comparison
            prev_dispositions = current_dispositions

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
                    {
                        "feature_id": feature_id,
                        "rounds": round_num,
                        "scores": scores,
                        "consecutive_no_improvement": consecutive_no_improvement,
                    },
                )
                self._update_phase(feature_id, FeaturePhase.BLOCKED)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="stalemate",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                    message=f"No improvement for {consecutive_no_improvement} consecutive rounds.",
                )

            if stop_result == "disagreement":
                rejected_issues = [
                    d for d in (current_dispositions or [])
                    if d.get("classification") == "REJECT"
                ]
                self._log(
                    "pipeline_disagreement",
                    {
                        "feature_id": feature_id,
                        "rounds": round_num,
                        "rejected_issues": rejected_issues,
                    },
                )
                self._update_phase(feature_id, FeaturePhase.SPEC_NEEDS_APPROVAL)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="disagreement",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                    message="Architect and reviewer disagree on issues. Human review required.",
                    rejected_issues=rejected_issues,
                )

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

    def run_spec_debate_only(self, feature_id: str) -> PipelineResult:
        """
        Run the spec debate pipeline without the author step.

        This is used for imported specs that already exist - it skips the
        SpecAuthor and runs only Critic → Moderator debate.

        Args:
            feature_id: The feature identifier.

        Returns:
            PipelineResult with status, scores, and cost.
        """
        max_rounds = self.config.spec_debate.max_rounds
        total_cost = 0.0
        final_scores: dict[str, float] = {}
        prev_scores: Optional[dict[str, float]] = None

        # NEW: Track dispositions across rounds for disagreement detection
        issue_history: list[dict[str, Any]] = []
        prev_dispositions: Optional[list[dict[str, Any]]] = None
        consecutive_no_improvement = 0

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

        # Verify spec-draft.md exists
        spec_path = self.config.specs_path / feature_id / "spec-draft.md"
        if not spec_path.exists():
            return PipelineResult(
                status="failure",
                feature_id=feature_id,
                rounds_completed=0,
                final_scores={},
                total_cost_usd=0.0,
                error=f"Spec not found at {spec_path} - import the spec first",
            )

        # Update phase to SPEC_IN_PROGRESS
        self._update_phase(feature_id, FeaturePhase.SPEC_IN_PROGRESS)

        self._log(
            "debate_only_start",
            {"feature_id": feature_id, "max_rounds": max_rounds, "spec_path": str(spec_path)},
        )

        for round_num in range(1, max_rounds + 1):
            self._log("round_start", {"feature_id": feature_id, "round": round_num})

            # Step 1: Critic reviews spec (with rejection context for round 2+)
            self._critic.reset()
            # Build rejection context from prior dispositions
            rejection_context = self._build_rejection_context_for_critic(feature_id) if round_num > 1 else ""
            critic_result = self._critic.run({
                "feature_id": feature_id,
                "rejection_context": rejection_context,
            })
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

            # Step 2: Moderator improves spec (if not last round)
            current_dispositions: Optional[list[dict[str, Any]]] = None
            # Extract disputed_issues from critic result for escalation
            disputed_issues = critic_result.output.get("disputed_issues", [])
            if round_num < max_rounds:
                self._moderator.reset()
                moderator_result = self._moderator.run({
                    "feature_id": feature_id,
                    "round": round_num,
                    "prior_dispositions": issue_history,  # Pass full history
                    "disputed_issues": disputed_issues,  # Pass for escalation handling
                })
                total_cost += moderator_result.cost_usd

                if not moderator_result.success:
                    # Check if spec files indicate success despite the error
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

                # Extract dispositions from moderator result
                current_dispositions = moderator_result.output.get("dispositions", [])
                if current_dispositions:
                    issue_history.extend(current_dispositions)

                # Log disposition summary
                disp_counts = moderator_result.output.get("disposition_counts", {})
                self._log(
                    "round_dispositions",
                    {
                        "feature_id": feature_id,
                        "round": round_num,
                        "accepted": disp_counts.get("accepted", 0),
                        "rejected": disp_counts.get("rejected", 0),
                        "deferred": disp_counts.get("deferred", 0),
                        "partial": disp_counts.get("partial", 0),
                    },
                )

                prev_scores = moderator_result.output.get("current_scores", scores)
            else:
                prev_scores = scores

            # Check stopping conditions (now after moderator runs so we have dispositions)
            stop_result, consecutive_no_improvement = self._check_stopping(
                scores,
                issues,
                prev_scores,
                current_dispositions,
                prev_dispositions,
                consecutive_no_improvement,
                feature_id,
            )

            # Store current dispositions for next round comparison
            prev_dispositions = current_dispositions

            if stop_result == "success":
                self._log(
                    "debate_success",
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
                    "debate_stalemate",
                    {
                        "feature_id": feature_id,
                        "rounds": round_num,
                        "scores": scores,
                        "consecutive_no_improvement": consecutive_no_improvement,
                    },
                )
                self._update_phase(feature_id, FeaturePhase.BLOCKED)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="stalemate",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                    message=f"No improvement for {consecutive_no_improvement} consecutive rounds.",
                )

            if stop_result == "disagreement":
                # Get the rejected issues for human review
                rejected_issues = [
                    d for d in (current_dispositions or [])
                    if d.get("classification") == "REJECT"
                ]
                self._log(
                    "debate_disagreement",
                    {
                        "feature_id": feature_id,
                        "rounds": round_num,
                        "rejected_issues": rejected_issues,
                    },
                )
                # Don't mark as BLOCKED - this needs human review
                self._update_phase(feature_id, FeaturePhase.SPEC_NEEDS_APPROVAL)
                self._update_cost(feature_id, total_cost, "SPEC_IN_PROGRESS")
                return PipelineResult(
                    status="disagreement",
                    feature_id=feature_id,
                    rounds_completed=round_num,
                    final_scores=final_scores,
                    total_cost_usd=total_cost,
                    message="Architect and reviewer disagree on issues. Human review required.",
                    rejected_issues=rejected_issues,
                )

        # Reached max rounds - timeout
        self._log(
            "debate_timeout",
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
        Run one implementation cycle (coder → verifier).

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

        The session workflow (thick-agent architecture):
        1. Select issue (if not specified) using PrioritizationAgent
        2. Claim issue lock
        3. Ensure feature branch
        4. Run CoderAgent (Implementation Agent) with full TDD workflow:
           - Reads context (issue, spec, integration points)
           - Writes tests first (RED phase)
           - Implements code (GREEN phase)
           - Iterates until all tests pass
        5. Run VerifierAgent to verify full test suite passes
        6. If tests fail, retry up to max_implementation_retries
        7. On success: commit, update GitHub issue, mark task done
        8. On blocked: mark task blocked
        9. Release issue lock

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

        # Track whether we've claimed the lock (for finally block cleanup)
        lock_claimed = False
        session_ended = False

        # Step 2: Claim issue lock
        if self._session_manager:
            # Clean stale locks before attempting to claim (self-healing)
            cleaned = self._session_manager.clean_stale_locks(feature_id)
            if cleaned:
                self._log("stale_locks_cleaned_on_startup", {
                    "feature_id": feature_id,
                    "cleaned_issues": cleaned,
                })

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

            lock_claimed = True

            # Step 3: Ensure feature branch
            self._session_manager.ensure_feature_branch(feature_id)

            # Start session
            session = self._session_manager.start_session(feature_id, issue_number)
            session_id = session.session_id

        try:
            # Step 4: Implementation cycle with retries
            # Thick-agent architecture: CoderAgent handles full TDD workflow
            # (test writing + implementation + verification iteration)
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
                        session_ended = True
                        # Lock release handled by finally block

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
                    session_ended = True
                    # Lock release handled by finally block

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
                    session_ended = True
                    # Lock release handled by finally block

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
            if self._session_manager and not session_ended:
                try:
                    self._session_manager.end_session(session_id, "failed")
                    session_ended = True
                except Exception:
                    pass  # Best effort - don't mask original error

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

        finally:
            # GUARANTEED LOCK CLEANUP: Always release the lock if we claimed it
            # This handles KeyboardInterrupt, SystemExit, and any other uncaught exceptions
            if lock_claimed and self._session_manager:
                try:
                    self._session_manager.release_issue(feature_id, issue_number)
                    self._log("lock_released_finally", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                    })
                except Exception as cleanup_error:
                    # Log but don't raise - we're in cleanup
                    self._log("lock_release_error", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "error": str(cleanup_error),
                    }, level="warning")
