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
import os
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
from swarm_attack.agents.recovery import RecoveryAgent
from swarm_attack.agents.complexity_gate import ComplexityGateAgent
from swarm_attack.agents.gate import GateAgent, GateResult
from swarm_attack.agents.summarizer import SummarizerAgent
from swarm_attack.context_builder import ContextBuilder
from swarm_attack.event_logger import EventLogger
from swarm_attack.github.issue_context import IssueContextManager
from swarm_attack.github_sync import GitHubSync
from swarm_attack.models import FeaturePhase, TaskStage
from swarm_attack.planning.dependency_graph import DependencyGraph
from swarm_attack.progress_logger import ProgressLogger
from swarm_attack.session_initializer import SessionInitializer
from swarm_attack.session_finalizer import SessionFinalizer
from swarm_attack.verification_tracker import VerificationTracker

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.github_client import GitHubClient
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import StateStore


# Known external library imports for import error recovery
# Maps symbol name to correct import statement
KNOWN_EXTERNAL_IMPORTS: dict[str, str] = {
    # Testing libraries
    "CliRunner": "from typer.testing import CliRunner",
    "TestClient": "from fastapi.testclient import TestClient",
    "Mock": "from unittest.mock import Mock",
    "patch": "from unittest.mock import patch",
    "MagicMock": "from unittest.mock import MagicMock",
    "AsyncMock": "from unittest.mock import AsyncMock",
    "pytest": "import pytest",
    # Standard library
    "Path": "from pathlib import Path",
    "datetime": "from datetime import datetime",
    "timedelta": "from datetime import timedelta",
    "dataclass": "from dataclasses import dataclass",
    "field": "from dataclasses import field",
    "Optional": "from typing import Optional",
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Any": "from typing import Any",
    "Callable": "from typing import Callable",
    "Union": "from typing import Union",
    # Rich library
    "Console": "from rich.console import Console",
    "Table": "from rich.table import Table",
    "Panel": "from rich.panel import Panel",
    # Typer
    "typer": "import typer",
    "Typer": "import typer",
    # JSON
    "json": "import json",
    # OS
    "os": "import os",
    "subprocess": "import subprocess",
}


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


@dataclass
class BaselineResult:
    """
    Result from baseline test validation.

    Run before coder starts to detect pre-existing test failures.
    If tests are already broken, the coder shouldn't be blamed for regressions.
    """

    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    pre_existing_failures: list[dict[str, Any]]
    duration_seconds: float
    test_files_checked: list[str]
    skipped_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging and context."""
        return {
            "passed": self.passed,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "pre_existing_failures": self.pre_existing_failures,
            "duration_seconds": self.duration_seconds,
            "test_files_checked": self.test_files_checked,
            "skipped_reason": self.skipped_reason,
        }


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

        # Gate agent for pre-coder validation (lazy initialized)
        self._gate_agent: Optional[GateAgent] = None
        self._post_coder_gate_agent: Optional[GateAgent] = None

        # Complexity Gate for issue sizing validation (lazy initialized)
        self._complexity_gate: Optional[ComplexityGateAgent] = None

        # Coordination Layer v2 components
        self._context_builder = ContextBuilder(config, state_store)
        self._github_sync = GitHubSync(config, logger)
        self._event_logger = EventLogger(config)

        # Schema drift prevention components
        self._summarizer = SummarizerAgent(config, logger)
        self._issue_context = IssueContextManager(config, logger)

        # Recovery agent for self-healing on coder failures
        self._recovery_agent = RecoveryAgent(config, logger)

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

    def _is_already_implemented(self, feature_id: str, issue_number: int) -> bool:
        """
        Belt-and-suspenders check for existing implementation.

        Checks multiple sources to determine if an issue is already implemented:
        1. Git commit exists with implementation pattern
        2. Test file exists and all tests pass
        3. Task is marked DONE in state

        This is an idempotency guard to prevent re-implementing completed work
        even if state synchronization failed.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number to check.

        Returns:
            True if implementation already exists, False otherwise.
        """
        # Check 1: Git commit exists
        try:
            import re as regex
            result = subprocess.run(
                [
                    "git", "log",
                    "--oneline",
                    "--grep", f"feat({feature_id}): Implement issue #{issue_number}",
                    "-n", "1",
                ],
                cwd=str(self.config.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip():
                self._log("duplicate_detection_git", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "source": "git_commit",
                })
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # Git check failed, continue to other checks

        # Check 2: Test file exists and passes
        test_path = (
            Path(self.config.repo_root)
            / "tests"
            / "generated"
            / feature_id
            / f"test_issue_{issue_number}.py"
        )
        if test_path.exists():
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_path), "-v", "--tb=no", "-q"],
                    cwd=str(self.config.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PYTHONPATH": str(self.config.repo_root)},
                )
                if result.returncode == 0:
                    self._log("duplicate_detection_tests", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "source": "tests_pass",
                    })
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # Test check failed, continue

        # Check 3: Task is DONE in state (should be redundant if sync worked)
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                for task in state.tasks:
                    if task.issue_number == issue_number and task.stage == TaskStage.DONE:
                        self._log("duplicate_detection_state", {
                            "feature_id": feature_id,
                            "issue_number": issue_number,
                            "source": "state_done",
                        })
                        return True

        return False

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

    def _can_collect_test_file(self, test_file: Path) -> bool:
        """
        Check if a test file can be collected by pytest without import errors.

        This prevents cascade failures where DONE issues with broken imports
        block subsequent issues from being marked DONE.

        Args:
            test_file: Path to the test file.

        Returns:
            True if the test file can be collected, False otherwise.
        """
        try:
            result = subprocess.run(
                ["pytest", str(test_file), "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.config.repo_root,
                env={**os.environ, "PYTHONPATH": str(self.config.repo_root)},
            )
            # Collection succeeds if exit code is 0 or 5 (no tests collected but no errors)
            # Exit code 2 means collection errors (import failures, etc.)
            return result.returncode in (0, 5)
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _get_regression_test_files(self, feature_id: str) -> list[str]:
        """
        Get test files from DONE issues only for regression checking.

        This prevents cascading failures where BLOCKED issues cause
        subsequent issues to fail regression even when their own tests pass.

        Also validates that test files can be collected (no import errors).

        Args:
            feature_id: The feature identifier.

        Returns:
            List of test file paths from DONE issues that can be collected.
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
                    # Validate test file can be collected (no import errors)
                    if self._can_collect_test_file(test_file):
                        test_files.append(str(test_file))
                    else:
                        self._log(
                            "regression_skip_uncollectable",
                            {
                                "feature_id": feature_id,
                                "issue_number": task.issue_number,
                                "test_file": str(test_file),
                                "reason": "Test file has collection errors (likely import failures)",
                            },
                            level="warning",
                        )

        return test_files

    def _run_baseline_check(self, feature_id: str, issue_number: int) -> BaselineResult:
        """
        Run baseline test validation before coder starts.

        This detects pre-existing test failures so the coder isn't blamed
        for regressions it didn't cause.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue being implemented.

        Returns:
            BaselineResult with pass/fail status and any pre-existing failures.
        """
        import time

        self._log("baseline_check_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        start_time = time.time()

        # Collect test files from DONE issues
        test_files_to_run = self._get_regression_test_files(feature_id)

        if not test_files_to_run:
            return BaselineResult(
                passed=True,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                pre_existing_failures=[],
                duration_seconds=0.0,
                test_files_checked=[],
                skipped_reason="No test files to validate",
            )

        # Run pytest on collected files using verifier's method
        exit_code, output = self._verifier._run_pytest(
            test_files=[Path(f) for f in test_files_to_run]
        )

        duration = time.time() - start_time
        parsed = self._verifier._parse_pytest_output(output)
        baseline_passed = exit_code == 0

        pre_existing_failures: list[dict[str, Any]] = []
        if not baseline_passed:
            pre_existing_failures = self._verifier._parse_pytest_failures(output)

        result = BaselineResult(
            passed=baseline_passed,
            tests_run=parsed.get("tests_run", 0),
            tests_passed=parsed.get("tests_passed", 0),
            tests_failed=parsed.get("tests_failed", 0),
            pre_existing_failures=pre_existing_failures,
            duration_seconds=round(duration, 2),
            test_files_checked=test_files_to_run,
        )

        self._log("baseline_check_complete", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "passed": result.passed,
            "tests_run": result.tests_run,
            "tests_failed": result.tests_failed,
            "duration_seconds": result.duration_seconds,
        })

        return result

    def _load_issue_from_spec(
        self, feature_id: str, issue_number: int
    ) -> Optional[dict[str, Any]]:
        """
        Load issue data from issues.json for complexity gate.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue order number.

        Returns:
            Issue dict if found, None otherwise.
        """
        issues_path = self.config.specs_path / feature_id / "issues.json"
        if not issues_path.exists():
            return None
        try:
            with open(issues_path) as f:
                data = json.load(f)
            for issue in data.get("issues", []):
                if issue.get("order") == issue_number:
                    return issue
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _auto_split_issue(
        self,
        feature_id: str,
        issue_number: int,
        issue_data: dict[str, Any],
        gate_estimate: Any,  # ComplexityEstimate
    ) -> AgentResult:
        """
        Automatically split a complex issue into smaller sub-issues.

        Called when ComplexityGateAgent determines an issue needs splitting.
        Creates 2-4 smaller sub-issues and updates the state.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue order number being split.
            issue_data: The issue dict from issues.json.
            gate_estimate: ComplexityEstimate from the gate.

        Returns:
            AgentResult with sub_issues if successful.
        """
        from swarm_attack.agents.issue_splitter import IssueSplitterAgent

        # Initialize splitter agent
        splitter = IssueSplitterAgent(
            config=self.config,
            logger=self.logger,
            llm_runner=None,  # Agent will create its own via base class
            state_store=self._state_store,
        )

        # Run splitter
        result = splitter.run({
            "feature_id": feature_id,
            "issue_number": issue_number,
            "issue_title": issue_data.get("title", ""),
            "issue_body": issue_data.get("body", ""),
            "split_suggestions": gate_estimate.split_suggestions,
            "estimated_turns": gate_estimate.estimated_turns,
        })

        if result.success:
            # Apply split to state
            self._apply_split_to_state(
                feature_id=feature_id,
                parent_issue_number=issue_number,
                sub_issues=result.output.get("sub_issues", []),
            )

        return result

    def _apply_split_to_state(
        self,
        feature_id: str,
        parent_issue_number: int,
        sub_issues: list[dict[str, Any]],
    ) -> None:
        """
        Apply issue split to state: create child tasks, mark parent as SPLIT.

        Args:
            feature_id: The feature identifier.
            parent_issue_number: The issue number being split.
            sub_issues: List of sub-issue dicts with title, body, estimated_size.
        """
        from swarm_attack.models import TaskRef, TaskStage

        if not self._state_store:
            self._log("apply_split_no_store", {}, level="error")
            return

        state = self._state_store.load(feature_id)
        if not state:
            self._log("apply_split_no_state", {"feature_id": feature_id}, level="error")
            return

        # Find parent task
        parent_task = None
        for task in state.tasks:
            if task.issue_number == parent_issue_number:
                parent_task = task
                break

        if not parent_task:
            self._log("apply_split_parent_not_found", {
                "feature_id": feature_id,
                "issue_number": parent_issue_number,
            }, level="error")
            return

        # Get next available issue number
        max_num = max(t.issue_number for t in state.tasks) if state.tasks else 0

        # Create child tasks
        child_nums = []
        for i, sub in enumerate(sub_issues):
            new_num = max_num + 1 + i
            child_nums.append(new_num)

            # First child inherits parent's deps, others chain sequentially
            if i == 0:
                deps = parent_task.dependencies.copy()
            else:
                deps = [child_nums[i - 1]]

            # Determine initial stage
            initial_stage = TaskStage.READY if not deps else TaskStage.BACKLOG

            child_task = TaskRef(
                issue_number=new_num,
                stage=initial_stage,
                title=sub.get("title", f"Sub-issue {i + 1}"),
                dependencies=deps,
                estimated_size=sub.get("estimated_size", "small"),
                parent_issue=parent_issue_number,
            )
            state.tasks.append(child_task)

        # Update parent task
        parent_task.stage = TaskStage.SPLIT
        parent_task.child_issues = child_nums
        parent_task.blocked_reason = f"Split into {len(child_nums)} sub-issues: {child_nums}"

        # Rewire dependents: anything depending on parent now depends on last child
        if child_nums:
            last_child = child_nums[-1]
            for task in state.tasks:
                if parent_issue_number in task.dependencies and task.issue_number != parent_issue_number:
                    task.dependencies.remove(parent_issue_number)
                    if last_child not in task.dependencies:
                        task.dependencies.append(last_child)
                    # Update stage if now unblocked
                    if task.stage == TaskStage.BACKLOG and not task.dependencies:
                        task.stage = TaskStage.READY

        # Save state
        self._state_store.save(state)

        # CRITICAL: Also write sub-issues to issues.json so coder can find them
        self._write_sub_issues_to_spec(
            feature_id=feature_id,
            parent_issue_number=parent_issue_number,
            child_nums=child_nums,
            sub_issues=sub_issues,
        )

        self._log("split_applied", {
            "feature_id": feature_id,
            "parent_issue": parent_issue_number,
            "child_issues": child_nums,
            "child_titles": [s.get("title", "") for s in sub_issues],
        })

    def _write_sub_issues_to_spec(
        self,
        feature_id: str,
        parent_issue_number: int,
        child_nums: list[int],
        sub_issues: list[dict[str, Any]],
    ) -> None:
        """
        Write sub-issues to issues.json so coder can find them.

        Bug fix: When issues are split, the sub-issues were only added to state
        but not to issues.json. The coder agent loads issue bodies from issues.json,
        so it would fail with "Issue N not found in issues.json".
        """
        issues_path = self.config.specs_path / feature_id / "issues.json"
        if not issues_path.exists():
            self._log("write_sub_issues_no_spec", {
                "feature_id": feature_id,
                "issues_path": str(issues_path),
            }, level="error")
            return

        try:
            with open(issues_path) as f:
                issues_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self._log("write_sub_issues_load_error", {
                "feature_id": feature_id,
                "error": str(e),
            }, level="error")
            return

        if "issues" not in issues_data:
            issues_data["issues"] = []

        # Find parent issue for labels
        parent_labels = ["enhancement", "backend"]
        for issue in issues_data["issues"]:
            if issue.get("order") == parent_issue_number:
                parent_labels = issue.get("labels", parent_labels)
                break

        # Add sub-issues to issues array
        for i, (num, sub) in enumerate(zip(child_nums, sub_issues)):
            # First child inherits parent deps, others chain sequentially
            if i == 0:
                deps = []  # Will be resolved from state
                for issue in issues_data["issues"]:
                    if issue.get("order") == parent_issue_number:
                        deps = issue.get("dependencies", [])
                        break
            else:
                deps = [child_nums[i - 1]]

            new_issue = {
                "title": sub.get("title", f"Sub-issue {i + 1} of #{parent_issue_number}"),
                "body": sub.get("body", ""),
                "labels": parent_labels,
                "estimated_size": sub.get("estimated_size", "small"),
                "dependencies": deps,
                "order": num,
                "automation_type": "automated",
                "parent_issue": parent_issue_number,
            }
            issues_data["issues"].append(new_issue)

        # Write back
        try:
            with open(issues_path, "w") as f:
                json.dump(issues_data, f, indent=2)
            self._log("write_sub_issues_success", {
                "feature_id": feature_id,
                "parent_issue": parent_issue_number,
                "child_issues": child_nums,
            })
        except OSError as e:
            self._log("write_sub_issues_write_error", {
                "feature_id": feature_id,
                "error": str(e),
            }, level="error")

    def _should_auto_split_on_timeout(self, result: AgentResult) -> bool:
        """
        Check if a coder failure should trigger auto-split.

        Returns True if:
        - auto_split_on_timeout is enabled in config
        - The error indicates timeout OR max_turns exceeded (both = issue too complex)

        Args:
            result: The AgentResult from the coder.

        Returns:
            True if auto-split should be triggered due to complexity.
        """
        if not getattr(self.config, "auto_split_on_timeout", True):
            return False

        if not result.error:
            return False

        error_lower = result.error.lower()

        # Timeout patterns - issue took too long
        if "timed out" in error_lower:
            return True

        # Max turns patterns - issue required too many LLM turns
        if "error_max_turns" in error_lower or "max_turns" in error_lower:
            return True

        # Context exhausted - issue too large for context window
        if "context" in error_lower and "exhaust" in error_lower:
            return True

        return False

    def _classify_coder_error(self, error_msg: str) -> str:
        """
        Classify coder error type for routing to recovery.

        Args:
            error_msg: The error message from coder failure.

        Returns:
            Error type: "timeout", "import_error", "syntax_error", or "unknown".
        """
        error_lower = error_msg.lower()

        if "timed out" in error_lower:
            return "timeout"

        if any(x in error_lower for x in ["undefined name", "importerror", "modulenotfounderror"]):
            return "import_error"

        if any(x in error_lower for x in ["syntaxerror", "indentationerror"]):
            return "syntax_error"

        if "typeerror" in error_lower:
            return "type_error"

        return "unknown"

    def _extract_undefined_names(self, error_msg: str) -> list[str]:
        """
        Extract undefined names from import error message.

        Parses error messages like:
        "undefined name(s): __future__.py:annotations, typer/testing.py:CliRunner"

        Args:
            error_msg: The error message containing undefined names.

        Returns:
            List of undefined symbol names.
        """
        import re

        # Look for "undefined name(s): path:name, path:name" pattern
        match = re.search(r"undefined name\(s\):\s*(.+?)(?:\s*$|\s*\n)", error_msg, re.IGNORECASE)
        if not match:
            return []

        # Parse "path:name, path:name" format
        names = []
        parts = match.group(1).split(",")
        for part in parts:
            part = part.strip()
            if ":" in part:
                # Extract name after the colon
                name = part.split(":")[-1].strip()
                if name:
                    names.append(name)

        return names

    def _find_correct_import_paths(
        self,
        undefined_names: list[str],
    ) -> dict[str, str]:
        """
        Search for correct import paths for undefined names.

        First checks KNOWN_EXTERNAL_IMPORTS for common libraries,
        then searches the codebase for internal definitions.

        Args:
            undefined_names: List of undefined symbol names.

        Returns:
            Dict mapping name to suggested import statement.
        """
        correct_paths: dict[str, str] = {}

        for name in undefined_names:
            # Strategy 1: Check known external imports
            if name in KNOWN_EXTERNAL_IMPORTS:
                correct_paths[name] = KNOWN_EXTERNAL_IMPORTS[name]
                continue

            # Strategy 2: Search codebase for definition
            definition = self._search_codebase_for_definition(name)
            if definition:
                correct_paths[name] = definition
                continue

            # Strategy 3: Search for module with similar name
            module = self._search_for_module(name)
            if module:
                correct_paths[name] = module

        return correct_paths

    def _search_codebase_for_definition(self, name: str) -> Optional[str]:
        """
        Search codebase for class or function definition.

        Args:
            name: The symbol name to search for.

        Returns:
            Import statement if found, None otherwise.
        """
        try:
            # Search for class definition
            patterns = [
                f"^class {name}\\(",
                f"^class {name}:",
                f"^def {name}\\(",
            ]

            for pattern in patterns:
                result = subprocess.run(
                    ["rg", "-l", "-e", pattern, "--type", "py", "."],
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout.strip():
                    file_path = result.stdout.strip().split("\n")[0]
                    # Convert file path to import
                    module = self._file_path_to_module(file_path)
                    if module:
                        return f"from {module} import {name}"
        except (subprocess.TimeoutExpired, Exception):
            pass

        return None

    def _search_for_module(self, name: str) -> Optional[str]:
        """
        Search for a module with a name similar to the undefined name.

        Args:
            name: The symbol name to search for.

        Returns:
            Import statement if found, None otherwise.
        """
        try:
            # Convert CamelCase to snake_case for module search
            import re
            snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

            # Search for .py files with this name
            result = subprocess.run(
                ["find", ".", "-name", f"{snake_name}.py", "-type", "f"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                file_path = result.stdout.strip().split("\n")[0]
                module = self._file_path_to_module(file_path)
                if module:
                    return f"from {module} import {name}"
        except (subprocess.TimeoutExpired, Exception):
            pass

        return None

    def _file_path_to_module(self, file_path: str) -> Optional[str]:
        """
        Convert a file path to a Python module path.

        Args:
            file_path: File path like './swarm_attack/cli/chief_of_staff.py'

        Returns:
            Module path like 'swarm_attack.cli.chief_of_staff'
        """
        # Remove ./ prefix and .py suffix
        path = file_path.lstrip("./")
        if path.endswith(".py"):
            path = path[:-3]

        # Convert path separators to dots
        module = path.replace("/", ".").replace("\\", ".")

        # Skip __init__ files
        if module.endswith(".__init__"):
            module = module[:-9]

        return module if module else None

    def _build_import_recovery_hint(
        self,
        undefined_names: list[str],
        suggestions: dict[str, str],
    ) -> str:
        """
        Build a recovery hint message for the coder.

        Args:
            undefined_names: List of undefined symbol names.
            suggestions: Dict mapping names to suggested imports.

        Returns:
            Human-readable recovery hint string.
        """
        lines = [
            "The previous attempt failed due to import errors.",
            "Please use the following correct imports:",
            "",
        ]

        for name in undefined_names:
            if name in suggestions:
                lines.append(f"  {suggestions[name]}")
            else:
                lines.append(f"  # Could not find import for: {name}")

        lines.append("")
        lines.append("Make sure to add these imports at the top of your files.")

        return "\n".join(lines)

    def _handle_import_error_recovery(
        self,
        error_msg: str,
        issue: Any,
        attempt: int,
        max_retries: int,
        session: Any,
    ) -> Optional["IssueSessionResult"]:
        """
        Handle import errors by finding correct imports and retrying.

        Args:
            error_msg: The error message from coder failure.
            issue: The issue being worked on.
            attempt: Current retry attempt number.
            max_retries: Maximum number of retries allowed.
            session: The current session object.

        Returns:
            IssueSessionResult if terminal (blocked), None if should retry.
        """
        # Check if auto-fix is enabled
        if not getattr(self.config, "auto_fix_import_errors", True):
            return None

        # 1. Extract undefined names
        undefined_names = self._extract_undefined_names(error_msg)

        if not undefined_names:
            # Can't parse - fall through to normal failure
            return None

        # 2. Search for correct import paths
        correct_paths = self._find_correct_import_paths(undefined_names)

        # 3. Build recovery context
        recovery_hint = self._build_import_recovery_hint(undefined_names, correct_paths)

        # 4. Store recovery context in session for retry
        session.recovery_context = {
            "error_type": "import_error",
            "undefined_names": undefined_names,
            "suggested_imports": correct_paths,
            "recovery_hint": recovery_hint,
        }

        # 5. Check if we should retry
        if attempt < max_retries:
            self._log(
                "import_error_recovery",
                {
                    "issue": getattr(issue, "issue_number", issue),
                    "undefined_names": undefined_names,
                    "suggested_imports": correct_paths,
                    "attempt": attempt,
                },
                level="warning",
            )
            return None  # Signal: retry with recovery context

        # 6. Max retries exhausted - block with actionable message
        return IssueSessionResult(
            status="blocked",
            issue_number=getattr(issue, "issue_number", 0),
            session_id="",
            tests_written=0,
            tests_passed=0,
            tests_failed=0,
            commits=[],
            cost_usd=0.0,
            retries=attempt,
            error=f"Import errors after {attempt} attempts. Missing: {', '.join(undefined_names)}. Recovery hint: {recovery_hint}",
        )

    def _attempt_recovery_with_agent(
        self,
        feature_id: str,
        issue_number: int,
        error_msg: str,
        attempt: int,
    ) -> Optional[dict[str, Any]]:
        """
        Use RecoveryAgent to analyze coder failure and determine recovery strategy.

        This is the general-purpose self-healing mechanism that uses LLM to analyze
        ANY type of coder failure and generate a recovery plan.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number that failed.
            error_msg: The error message from the coder failure.
            attempt: Current retry attempt number.

        Returns:
            Dict with recovery analysis if agent succeeds:
                - recoverable: bool - whether retry is possible
                - recovery_plan: str - instructions for fixing the issue
                - root_cause: str - analysis of what went wrong
                - human_instructions: str - if not recoverable, what human should do
                - cost_usd: float - cost of the analysis
            None if RecoveryAgent itself fails.
        """
        try:
            # Build context for RecoveryAgent
            context = {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "failure_type": "coder_error",
                "error_output": error_msg,
                "retry_count": attempt,
            }

            self._log(
                "recovery_agent_invoked",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "attempt": attempt,
                },
            )

            # Invoke RecoveryAgent
            result = self._recovery_agent.run(context)

            if not result.success:
                self._log(
                    "recovery_agent_failed",
                    {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "error": result.error,
                    },
                    level="warning",
                )
                return None

            # Extract recovery analysis from result
            output = result.output or {}
            recovery_analysis = {
                "recoverable": output.get("recoverable", False),
                "recovery_plan": output.get("recovery_plan"),
                "root_cause": output.get("root_cause", "Unknown"),
                "human_instructions": output.get("human_instructions"),
                "suggested_actions": output.get("suggested_actions", []),
                "cost_usd": result.cost_usd,
            }

            self._log(
                "recovery_agent_complete",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "recoverable": recovery_analysis["recoverable"],
                    "root_cause": recovery_analysis["root_cause"][:100] if recovery_analysis["root_cause"] else None,
                },
            )

            return recovery_analysis

        except Exception as e:
            self._log(
                "recovery_agent_exception",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "error": str(e),
                },
                level="error",
            )
            return None

    def _handle_timeout_auto_split(
        self,
        feature_id: str,
        issue_number: int,
        issue_data: dict[str, Any],
    ) -> tuple[bool, Optional[str], AgentResult, float]:
        """
        Handle timeout by auto-splitting the issue.

        When coder times out, it indicates the issue is more complex than estimated.
        Trigger IssueSplitter to break it into smaller pieces.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number that timed out.
            issue_data: The issue dict from issues.json.

        Returns:
            Tuple of (success, commit_sha, result, cost).
        """
        from swarm_attack.agents.complexity_gate import ComplexityEstimate

        self._log("timeout_auto_split_started", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        # Create synthetic gate estimate with needs_split=True
        gate_estimate = ComplexityEstimate(
            estimated_turns=30,  # Clearly over limit
            complexity_score=0.9,
            needs_split=True,
            split_suggestions=[
                "Issue timed out - actual complexity exceeds estimate",
                "Split into smaller, focused sub-issues",
            ],
            confidence=0.95,
            reasoning="Coder timeout triggered auto-split",
        )

        # Use existing _auto_split_issue method
        split_result = self._auto_split_issue(
            feature_id=feature_id,
            issue_number=issue_number,
            issue_data=issue_data,
            gate_estimate=gate_estimate,
        )

        if split_result.success:
            self._log("timeout_auto_split_success", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "sub_issues_count": split_result.output.get("count", 0),
            })
            return (
                True,
                None,
                AgentResult.success_result(
                    output={
                        "action": "split",
                        "reason": "timeout_auto_split",
                        "sub_issues": split_result.output.get("sub_issues", []),
                        "count": split_result.output.get("count", 0),
                    },
                    cost_usd=split_result.cost_usd,
                ),
                split_result.cost_usd,
            )
        else:
            self._log("timeout_auto_split_failed", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": split_result.error,
            }, level="error")
            return (
                False,
                None,
                AgentResult.failure_result(
                    f"Issue timed out and auto-split failed: {split_result.error}. "
                    "Manual intervention required."
                ),
                split_result.cost_usd,
            )

    def _generate_completion_summary(
        self,
        feature_id: str,
        issue_number: int,
        coder_result: Optional[AgentResult],
    ) -> Optional[str]:
        """
        Generate 1-2 sentence summary of what was accomplished.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            coder_result: Result from coder agent with files/classes info.

        Returns:
            Semantic summary string, or None if no info available.
        """
        if not coder_result or not coder_result.output:
            return None

        issue_outputs = coder_result.output.get("issue_outputs")
        if not issue_outputs:
            return None

        # Extract info from IssueOutput (handle both object and dict)
        if hasattr(issue_outputs, 'files_created'):
            files_created = issue_outputs.files_created
            classes_defined = issue_outputs.classes_defined
        else:
            files_created = issue_outputs.get('files_created', [])
            classes_defined = issue_outputs.get('classes_defined', {})

        # Build simple summary
        parts = []
        if files_created:
            file_list = ', '.join(files_created[:3])
            parts.append(f"Created {len(files_created)} file(s): {file_list}")
            if len(files_created) > 3:
                parts[-1] = parts[-1].replace(file_list, f"{file_list} (+{len(files_created)-3} more)")

        if classes_defined:
            all_classes = []
            for file_classes in classes_defined.values():
                all_classes.extend(file_classes)
            if all_classes:
                class_list = ', '.join(all_classes[:5])
                parts.append(f"Defined: {class_list}")

        if parts:
            return "; ".join(parts)
        return f"Implemented issue #{issue_number}"

    def _generate_and_propagate_context(
        self,
        feature_id: str,
        issue_number: int,
        issue_title: str,
        coder_result: Optional[AgentResult],
        commit_hash: Optional[str] = None,
    ) -> None:
        """
        Generate rich implementation summary and propagate to dependent issues.

        This is the key method for schema drift prevention. After an issue completes:
        1. SummarizerAgent generates a structured summary (classes, imports, usage)
        2. Summary is added to the completed GitHub issue
        3. Summary is propagated to all transitive dependent issues

        This ensures that when a coder picks up a dependent issue, it sees
        context from ALL issues it depends on directly in the issue body.

        Args:
            feature_id: The feature identifier.
            issue_number: The completed issue number.
            issue_title: Title of the completed issue.
            coder_result: Result from coder agent with files/classes info.
            commit_hash: Optional commit hash for the implementation.
        """
        self._log("context_propagation_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        # Extract issue outputs
        files_created: list[str] = []
        classes_defined: dict[str, list[str]] = {}

        if coder_result and coder_result.output:
            issue_outputs = coder_result.output.get("issue_outputs")
            if issue_outputs:
                if hasattr(issue_outputs, 'files_created'):
                    files_created = issue_outputs.files_created
                    classes_defined = issue_outputs.classes_defined
                else:
                    files_created = issue_outputs.get('files_created', [])
                    classes_defined = issue_outputs.get('classes_defined', {})

        # Get issue body for context
        issue_body = ""
        if self._state_store:
            state = self._state_store.load(feature_id)
            if state:
                for task in state.tasks:
                    if task.issue_number == issue_number:
                        issue_body = task.title  # Use title as minimal context
                        break

        # Step 1: Generate rich summary using SummarizerAgent
        try:
            summarizer_context = {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "issue_title": issue_title,
                "issue_body": issue_body,
                "commit_hash": commit_hash,
                "files_created": files_created,
                "classes_defined": classes_defined,
            }

            summarizer_result = self._summarizer.run(summarizer_context)

            if not summarizer_result.success:
                self._log("summarizer_failed", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "errors": summarizer_result.errors,
                }, level="warning")
                return

            summary_output = summarizer_result.output
            github_markdown = summary_output.get("github_markdown", "")
            context_markdown = summary_output.get("context_markdown", "")

            self._log("summarizer_complete", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "cost_usd": summarizer_result.cost_usd,
            })

        except Exception as e:
            self._log("summarizer_error", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": str(e),
            }, level="error")
            return

        # Step 2: Add summary to completed issue
        try:
            if github_markdown:
                self._issue_context.add_summary_to_issue(issue_number, github_markdown)
        except Exception as e:
            self._log("add_summary_failed", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": str(e),
            }, level="warning")

        # Step 3: Propagate context to transitive dependents
        try:
            if not context_markdown or not self._state_store:
                return

            state = self._state_store.load(feature_id)
            if not state or not state.tasks:
                return

            # Build dependency graph
            graph = DependencyGraph(state.tasks)

            # Get all issues that depend on this one (transitively)
            dependents = graph.get_transitive_dependents(issue_number)

            if dependents:
                results = self._issue_context.propagate_context_to_dependents(
                    issue_number,
                    list(dependents),
                    context_markdown,
                )

                success_count = sum(1 for s in results.values() if s)
                self._log("context_propagated", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "dependent_count": len(dependents),
                    "success_count": success_count,
                })

        except Exception as e:
            self._log("context_propagation_error", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": str(e),
            }, level="warning")

    def _run_implementation_cycle(
        self,
        feature_id: str,
        issue_number: int,
        session_id: str,
        retry_number: int = 0,
        previous_failures: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[bool, Optional[AgentResult], AgentResult, float]:
        """
        Run one implementation cycle (coder → verifier).

        Args:
            feature_id: The feature identifier.
            issue_number: The issue to implement.
            session_id: Current session ID for checkpoints.
            retry_number: Current retry attempt (0 = first attempt).
            previous_failures: Failure details from previous verifier run.

        Returns:
            Tuple of (success, coder_result, verifier_result, total_cost).
        """
        # Get test files from DONE issues only for regression check
        # This prevents BLOCKED issues from causing cascading failures
        # Pass empty list if no DONE issues (disables regression) vs None (run all)
        regression_test_files = self._get_regression_test_files(feature_id)

        total_cost = 0.0

        # BASELINE CHECK (only on first attempt)
        # Detect pre-existing test failures BEFORE coder runs
        # If tests are already broken, don't blame coder for regressions
        baseline_result: Optional[BaselineResult] = None
        if retry_number == 0:
            baseline_result = self._run_baseline_check(feature_id, issue_number)

            if not baseline_result.passed and not baseline_result.skipped_reason:
                self._log("baseline_check_abort", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "pre_existing_failures": len(baseline_result.pre_existing_failures),
                    "failures": baseline_result.pre_existing_failures[:3],  # First 3 for logging
                }, level="error")

                return (
                    False,
                    None,
                    AgentResult.failure_result(
                        f"Baseline check failed: {len(baseline_result.pre_existing_failures)} "
                        f"pre-existing test failure(s). Fix these before implementing new issues."
                    ),
                    total_cost,
                )

        # Build module registry from completed issues for context handoff
        module_registry: dict[str, Any] = {}
        issue_dependencies: list[int] = []
        all_tasks: list = []
        completed_summaries: list[dict[str, Any]] = []
        if self._state_store:
            module_registry = self._state_store.get_module_registry(feature_id)
            # Get dependencies for schema drift prevention
            state = self._state_store.load(feature_id)
            if state and state.tasks:
                all_tasks = state.tasks
                for task in state.tasks:
                    if task.issue_number == issue_number:
                        issue_dependencies = task.dependencies
                        break

            # Build completed summaries for context handoff between issues
            # This is the PRIMARY mechanism for issue N+1 to know what issue N created
            context_builder = ContextBuilder(self.config, self._state_store)
            completed_summaries = context_builder.get_completed_summaries(feature_id)

        # Compute test_path for coder context handoff
        # This ensures orchestrator and coder use the same test file location
        test_path = str(
            Path(self.config.repo_root)
            / "tests"
            / "generated"
            / feature_id
            / f"test_issue_{issue_number}.py"
        )

        # Gate: On retries, verify test file exists before proceeding
        # In thick-agent TDD mode, coder creates tests on first run.
        # If test file is still missing on retry, something went wrong.
        if retry_number > 0 and not Path(test_path).exists():
            self._log(
                "test_file_missing_on_retry",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "expected_path": test_path,
                    "retry_number": retry_number,
                },
                level="error",
            )
            return (
                False,
                None,
                AgentResult.failure_result(
                    f"Test file not found on retry: {test_path}. "
                    "Coder should have created tests on first run."
                ),
                0.0,
            )

        context = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            # Pass test_path to ensure coder uses the same location as orchestrator
            "test_path": test_path,
            # Pass the list as-is (even if empty) to run targeted regression
            # Empty list means no regression tests, None would run all tests
            "regression_test_files": regression_test_files,
            # NEW: Pass retry context to coder
            "retry_number": retry_number,
            "test_failures": previous_failures or [],
            # NEW: Pass module registry for context handoff from prior issues
            "module_registry": module_registry,
            # NEW: Pass dependencies for schema drift prevention (compact schema filtering)
            "issue_dependencies": issue_dependencies,
            "all_tasks": all_tasks,
            # P0 FIX: Pass completed summaries for issue-to-issue context handoff
            # This enables issue N+1 to see what issue N actually created (classes, files, patterns)
            "completed_summaries": completed_summaries,
            # Pass baseline result for logging/debugging (if available)
            "baseline_result": baseline_result.to_dict() if baseline_result else None,
        }

        # Complexity Gate: Check if issue is too complex before burning tokens
        # Only run on first attempt (retry doesn't change issue complexity)
        if retry_number == 0:
            # Lazy initialize complexity gate
            if self._complexity_gate is None:
                self._complexity_gate = ComplexityGateAgent(self.config, self.logger)

            # Load issue data for gate estimation
            issue_data = self._load_issue_from_spec(feature_id, issue_number)
            if issue_data:
                gate_estimate = self._complexity_gate.estimate_complexity(issue_data)
                total_cost += self._complexity_gate.get_total_cost()

                if gate_estimate.needs_split:
                    self._log("complexity_gate_needs_split", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "estimated_turns": gate_estimate.estimated_turns,
                        "complexity_score": gate_estimate.complexity_score,
                        "suggestions": gate_estimate.split_suggestions,
                        "reasoning": gate_estimate.reasoning,
                    }, level="warning")

                    # Auto-split the issue into smaller sub-issues
                    split_result = self._auto_split_issue(
                        feature_id=feature_id,
                        issue_number=issue_number,
                        issue_data=issue_data,
                        gate_estimate=gate_estimate,
                    )
                    total_cost += split_result.cost_usd

                    if split_result.success:
                        # Split successful - return with split action
                        return (
                            True,  # Success - issue was handled (by splitting)
                            None,
                            AgentResult.success_result(
                                output={
                                    "action": "split",
                                    "sub_issues": split_result.output.get("sub_issues", []),
                                    "count": split_result.output.get("count", 0),
                                },
                                cost_usd=split_result.cost_usd,
                            ),
                            total_cost,
                        )
                    else:
                        # Split failed - fall back to blocking
                        self._log("auto_split_failed", {
                            "feature_id": feature_id,
                            "issue_number": issue_number,
                            "error": split_result.error,
                        }, level="error")
                        return (
                            False,
                            None,
                            AgentResult.failure_result(
                                f"Issue too complex and auto-split failed: {split_result.error}. "
                                f"Manual split needed. Suggestions: {'; '.join(gate_estimate.split_suggestions)}"
                            ),
                            total_cost,
                        )

                # Adjust max_turns based on gate estimate
                context["max_turns_override"] = min(gate_estimate.estimated_turns + 5, 30)
                self._log("complexity_gate_pass", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "estimated_turns": gate_estimate.estimated_turns,
                    "max_turns_override": context["max_turns_override"],
                    "confidence": gate_estimate.confidence,
                })

        # Run pre-coder gate validation (optional, only on retry_number == 0)
        # Gate validates test artifacts exist before coder runs
        if retry_number == 0:
            gate_result = self._run_pre_coder_gate(
                feature_id, issue_number, test_path, context
            )
            if gate_result is not None:
                total_cost += gate_result.get("cost_usd", 0.0)
                # Enrich context with gate findings
                if gate_result.get("passed"):
                    if gate_result.get("language"):
                        context["language"] = gate_result["language"]
                    if gate_result.get("test_count"):
                        context["test_count"] = gate_result["test_count"]
                # Note: We don't fail on gate failure in first iteration
                # since coder (TDD) creates tests as part of implementation. Gate is informational.

        # Run coder
        coder_result: Optional[AgentResult] = None
        if self._coder:
            self._coder.reset()
            coder_result = self._coder.run(context)
            total_cost += coder_result.cost_usd

            if self._session_manager:
                self._session_manager.checkpoint(
                    session_id, "coder", "complete", cost_usd=coder_result.cost_usd
                )

            if not coder_result.success:
                return False, coder_result, coder_result, total_cost

            # Run post-coder gate validation
            # Gate validates implementation artifacts before verifier runs
            post_gate_result = self._run_post_coder_gate(
                feature_id, issue_number, test_path, coder_result, context
            )
            if post_gate_result is not None:
                total_cost += post_gate_result.get("cost_usd", 0.0)
                # If post-coder gate fails, log warning but continue to verifier
                # Verifier will catch actual test failures
                if not post_gate_result.get("passed"):
                    self._log(
                        "post_coder_gate_warning",
                        {
                            "feature_id": feature_id,
                            "issue_number": issue_number,
                            "errors": post_gate_result.get("errors", []),
                        },
                        level="warning",
                    )

        # Run verifier
        if self._verifier:
            self._verifier.reset()

            # Pass schema drift detection context to verifier
            # Extract newly created classes from coder output for validation
            verifier_context = context.copy()
            if coder_result and coder_result.output:
                issue_outputs = coder_result.output.get("issue_outputs")
                if issue_outputs and hasattr(issue_outputs, "classes_defined"):
                    verifier_context["new_classes_defined"] = issue_outputs.classes_defined
                    # module_registry is already in context from _prepare_coder_context

            verifier_result = self._verifier.run(verifier_context)
            total_cost += verifier_result.cost_usd

            if self._session_manager:
                self._session_manager.checkpoint(
                    session_id, "verifier", "complete", cost_usd=verifier_result.cost_usd
                )

            # Save issue outputs to module registry if verifier succeeded
            if verifier_result.success and coder_result and coder_result.output:
                issue_outputs = coder_result.output.get("issue_outputs")
                if issue_outputs and self._state_store:
                    self._state_store.save_issue_outputs(
                        feature_id, issue_number, issue_outputs
                    )

            return verifier_result.success, coder_result, verifier_result, total_cost

        # No verifier - return failure
        return False, coder_result, AgentResult.failure_result("No verifier agent configured"), total_cost

    def _run_pre_coder_gate(
        self,
        feature_id: str,
        issue_number: int,
        test_path: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Run pre-coder gate validation to check test artifacts.

        This is an LLM-adaptive gate that validates test artifacts exist
        and are syntactically correct before the coder agent runs.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            test_path: Expected test file path.
            context: Full context dict.

        Returns:
            Dict with gate results (passed, language, test_count, cost_usd)
            or None if gate validation was skipped.
        """
        try:
            # Lazy initialize gate agent
            if self._gate_agent is None:
                self._gate_agent = GateAgent(
                    self.config,
                    logger=self.logger,
                    gate_name="pre_coder_gate",
                )

            # Build gate context
            gate_context = {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "previous_agent": "coder",
                "expected_artifacts": ["test file"],
                "project_root": str(self.config.repo_root),
                "test_path": test_path,
            }

            # Run gate validation
            gate_result = self._gate_agent.validate(gate_context)

            # Log gate result
            self._log(
                "pre_coder_gate_complete",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "passed": gate_result.passed,
                    "language": gate_result.language,
                    "test_count": gate_result.test_count,
                    "cost_usd": self._gate_agent.get_total_cost(),
                },
            )

            return {
                "passed": gate_result.passed,
                "language": gate_result.language,
                "test_count": gate_result.test_count,
                "errors": gate_result.errors,
                "cost_usd": self._gate_agent.get_total_cost(),
            }

        except Exception as e:
            # Gate failure should not block coder - log and continue
            self._log(
                "pre_coder_gate_error",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "error": str(e),
                },
                level="warning",
            )
            return None

    def _run_post_coder_gate(
        self,
        feature_id: str,
        issue_number: int,
        test_path: str,
        coder_result: AgentResult,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Run post-coder gate validation to check implementation artifacts.

        This is an LLM-adaptive gate that validates implementation artifacts
        exist and are syntactically correct after the coder agent runs.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            test_path: Expected test file path.
            coder_result: Result from the coder agent.
            context: Full context dict.

        Returns:
            Dict with gate results (passed, language, errors, cost_usd)
            or None if gate validation was skipped.
        """
        try:
            # Lazy initialize post-coder gate agent
            if self._post_coder_gate_agent is None:
                self._post_coder_gate_agent = GateAgent(
                    self.config,
                    logger=self.logger,
                    gate_name="post_coder_gate",
                )

            # Extract implementation files from coder result
            impl_files = []
            if coder_result.output:
                issue_outputs = coder_result.output.get("issue_outputs", {})
                impl_files = issue_outputs.get("modified_files", [])

            # Build gate context
            gate_context = {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "previous_agent": "coder",
                "expected_artifacts": ["implementation file", "passing tests"],
                "project_root": str(self.config.repo_root),
                "test_path": test_path,
                "impl_files": impl_files,
            }

            # Run gate validation
            gate_result = self._post_coder_gate_agent.validate(gate_context)

            # Log gate result
            self._log(
                "post_coder_gate_complete",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "passed": gate_result.passed,
                    "language": gate_result.language,
                    "test_count": gate_result.test_count,
                    "cost_usd": self._post_coder_gate_agent.get_total_cost(),
                },
            )

            return {
                "passed": gate_result.passed,
                "language": gate_result.language,
                "test_count": gate_result.test_count,
                "errors": gate_result.errors,
                "cost_usd": self._post_coder_gate_agent.get_total_cost(),
            }

        except Exception as e:
            # Gate failure should not block verifier - log and continue
            self._log(
                "post_coder_gate_error",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "error": str(e),
                },
                level="warning",
            )
            return None

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
        """Mark task as DONE in state with exclusive locking."""
        if self._state_store:
            with self._state_store.exclusive_lock(feature_id):
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
        """Mark task as BLOCKED in state with optional reason and exclusive locking.

        Also posts a comment to the GitHub issue explaining why it's blocked.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number to mark as blocked.
            reason: Optional error message explaining why the task is blocked.
        """
        if self._state_store:
            with self._state_store.exclusive_lock(feature_id):
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

            # Sync state from git to detect already-implemented issues
            synced = self._state_store.sync_state_from_git(feature_id)
            if synced:
                self._log("git_sync_completed", {
                    "feature_id": feature_id,
                    "synced_issues": synced,
                })

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

        # BELT-AND-SUSPENDERS: Check if issue is already implemented
        # This catches cases where sync_state_from_git missed the commit
        # (e.g., different commit message format, branch not merged yet)
        if self._is_already_implemented(feature_id, issue_number):
            self._log("duplicate_implementation_prevented", {
                "feature_id": feature_id,
                "issue_number": issue_number,
            })
            # Mark task as DONE in state if not already
            if self._state_store:
                with self._state_store.exclusive_lock(feature_id):
                    state = self._state_store.load(feature_id)
                    if state:
                        for task in state.tasks:
                            if task.issue_number == issue_number:
                                if task.stage != TaskStage.DONE:
                                    task.stage = TaskStage.DONE
                                    self._state_store.save(state)
                                break

            return IssueSessionResult(
                status="success",
                issue_number=issue_number,
                session_id="",
                tests_written=0,
                tests_passed=0,
                tests_failed=0,
                commits=[],
                cost_usd=0.0,
                retries=0,
                error=None,
            )

        # Session Initialization Protocol (5-step verification before coding)
        progress_logger = ProgressLogger(self.config.swarm_path)
        initializer = SessionInitializer(self.config, self._state_store, progress_logger)
        init_result = initializer.initialize_session(feature_id, issue_number)

        if not init_result.ready:
            self._log("session_init_blocked", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "reason": init_result.reason,
            })
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
                error=f"Session initialization failed: {init_result.reason}",
            )

        # Track whether we've claimed the lock (for finally block cleanup)
        lock_claimed = False
        session_ended = False
        session_id = ""  # Initialize before try block for guaranteed cleanup access

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

        try:
            # Step 3: Ensure feature branch (now inside try for guaranteed lock cleanup)
            if self._session_manager:
                self._session_manager.ensure_feature_branch(feature_id)

                # Start session
                session = self._session_manager.start_session(feature_id, issue_number)
                session_id = session.session_id

            # Log issue started event
            try:
                self._event_logger.log_issue_started(feature_id, issue_number, session_id)
            except Exception:
                pass  # Event logging failures must not block implementation

            # Step 4: Implementation cycle with retries
            # Thick-agent architecture: CoderAgent handles full TDD workflow
            # (test writing + implementation + verification iteration)
            max_retries = getattr(self.config.sessions, "max_implementation_retries", 3)
            success = False
            verifier_result: Optional[AgentResult] = None
            attempt = 0
            # Track failures from previous run to pass to coder on retry
            previous_failures: list[dict[str, Any]] = []
            # Track last coder result for summary generation
            last_coder_result: Optional[AgentResult] = None

            while attempt <= max_retries:
                cycle_success, coder_result, verifier_result, cycle_cost = self._run_implementation_cycle(
                    feature_id,
                    issue_number,
                    session_id,
                    retry_number=attempt,
                    previous_failures=previous_failures,
                )
                total_cost += cycle_cost
                # Track coder result for summary generation
                if coder_result:
                    last_coder_result = coder_result

                if cycle_success:
                    success = True
                    # retries = number of attempts after the first one
                    retries = attempt
                    break

                # Check if it was a coder failure (not verifier)
                if verifier_result and not verifier_result.output:
                    # Check if this is a timeout that should trigger auto-split
                    error_msg = verifier_result.errors[0] if verifier_result.errors else "Unknown error"
                    coder_fail_result = AgentResult.failure_result(f"Coder failed: {error_msg}")

                    if self._should_auto_split_on_timeout(coder_fail_result):
                        # Load issue data for splitting
                        issue_data = self._load_issue_from_spec(feature_id, issue_number)
                        if issue_data:
                            self._log("timeout_auto_split_triggered", {
                                "feature_id": feature_id,
                                "issue_number": issue_number,
                            })

                            split_success, _, split_result, split_cost = self._handle_timeout_auto_split(
                                feature_id=feature_id,
                                issue_number=issue_number,
                                issue_data=issue_data,
                            )
                            total_cost += split_cost

                            if split_success:
                                if self._session_manager:
                                    self._session_manager.end_session(session_id, "split")
                                    session_ended = True

                                return IssueSessionResult(
                                    status="split",
                                    issue_number=issue_number,
                                    session_id=session_id,
                                    tests_written=0,
                                    tests_passed=0,
                                    tests_failed=0,
                                    commits=[],
                                    cost_usd=total_cost,
                                    retries=attempt,
                                    error=None,
                                )

                    # Use RecoveryAgent to analyze ANY coder failure and determine recovery
                    if attempt < max_retries:
                        recovery_result = self._attempt_recovery_with_agent(
                            feature_id=feature_id,
                            issue_number=issue_number,
                            error_msg=error_msg,
                            attempt=attempt,
                        )

                        if recovery_result and recovery_result.get("recoverable"):
                            # RecoveryAgent says we can retry
                            recovery_plan = recovery_result.get("recovery_plan", "")
                            total_cost += recovery_result.get("cost_usd", 0.0)

                            # Store recovery plan for next coder attempt
                            previous_failures = previous_failures or []
                            if recovery_plan:
                                previous_failures.append({
                                    "type": "recovery_agent_plan",
                                    "message": recovery_plan,
                                    "root_cause": recovery_result.get("root_cause", ""),
                                })

                            # Continue to retry loop
                            attempt += 1
                            self._log("recovery_agent_retry", {
                                "feature_id": feature_id,
                                "issue_number": issue_number,
                                "retry": attempt,
                                "recovery_plan": recovery_plan[:200] if recovery_plan else None,
                                "root_cause": recovery_result.get("root_cause"),
                            }, level="warning")
                            continue  # Go to next iteration of while loop

                        # RecoveryAgent says not recoverable - fall through to failure
                        if recovery_result:
                            total_cost += recovery_result.get("cost_usd", 0.0)

                    # Coder failed - no retry (or recovery not possible)
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
                        error=f"Coder failed: {error_msg}",
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
                    # Log retry event
                    try:
                        self._event_logger.log_retry_started(feature_id, issue_number, attempt)
                    except Exception:
                        pass  # Event logging failures must not block implementation
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
                # Generate and save completion summary
                summary: Optional[str] = None
                try:
                    summary = self._generate_completion_summary(feature_id, issue_number, last_coder_result)
                    if summary and self._state_store:
                        self._state_store.save_completion_summary(feature_id, issue_number, summary)
                except Exception:
                    pass  # Summary generation failures should not block implementation

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

                # Session Finalization Protocol (verify all tests pass before marking complete)
                verification_tracker = VerificationTracker(self.config.swarm_path)
                finalizer = SessionFinalizer(
                    self.config, self._state_store, progress_logger, verification_tracker
                )
                finalize_result = finalizer.finalize_session(
                    feature_id, issue_number, commits=commits
                )

                if not finalize_result.can_complete:
                    self._log("session_finalize_blocked", {
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "reason": finalize_result.reason,
                    }, level="warning")
                    # Don't block completion - just log the warning
                    # The verifier already ran, so this is a secondary check

                # Update GitHub issue
                if self._github_client:
                    self._github_client.close_issue(issue_number)

                # Mark task done
                self._mark_task_done(feature_id, issue_number)

                # Schema drift prevention: Generate and propagate context
                try:
                    # Get issue title for context
                    issue_title = f"Issue #{issue_number}"
                    if self._state_store:
                        state = self._state_store.load(feature_id)
                        if state:
                            for task in state.tasks:
                                if task.issue_number == issue_number:
                                    issue_title = task.title
                                    break

                    self._generate_and_propagate_context(
                        feature_id,
                        issue_number,
                        issue_title,
                        last_coder_result,
                        commit_hash,
                    )
                except Exception:
                    pass  # Context propagation failures must not block implementation

                # Event logging and GitHub sync
                try:
                    self._event_logger.log_issue_done(feature_id, issue_number, commit_hash or "", total_cost)
                except Exception:
                    pass  # Event logging failures must not block implementation
                try:
                    self._github_sync.update_issue_state(issue_number, "done")
                    files_created = []
                    if last_coder_result and last_coder_result.output:
                        issue_outputs = last_coder_result.output.get("issue_outputs")
                        if issue_outputs:
                            if hasattr(issue_outputs, 'files_created'):
                                files_created = issue_outputs.files_created
                            else:
                                files_created = issue_outputs.get("files_created", [])
                    self._github_sync.post_done_comment(
                        issue_number,
                        commit_hash or "",
                        files_created=files_created,
                        test_count=tests_passed,
                        completion_summary=summary,
                    )
                except Exception:
                    pass  # GitHub sync failures must not block implementation

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

                # Event logging and GitHub sync
                try:
                    self._event_logger.log_issue_blocked(feature_id, issue_number, error_msg, retries)
                except Exception:
                    pass  # Event logging failures must not block implementation
                try:
                    self._github_sync.update_issue_state(issue_number, "blocked")
                    self._github_sync.post_blocked_comment(
                        issue_number,
                        error_msg,
                        retry_count=retries,
                        feature_id=feature_id,
                    )
                except Exception:
                    pass  # GitHub sync failures must not block implementation

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

    # =========================================================================
    # Safe Execution Methods - Production Error Handling
    # =========================================================================

    def run_preflight_checks(self, feature_id: str) -> tuple[bool, list[str]]:
        """
        Run pre-flight checks before starting any work.

        Validates:
        - Disk space (minimum 1GB free)
        - No stale sessions for this feature
        - Git worktree healthy (if using worktrees)
        - State file not corrupted

        Args:
            feature_id: The feature identifier.

        Returns:
            Tuple of (passed, list of error messages).
        """
        from swarm_attack.recovery import PreflightChecker, HealthChecker

        health_checker = HealthChecker(
            self.config,
            session_manager=self._session_manager,
            state_store=self._state_store,
        )
        preflight = PreflightChecker(self.config, health_checker)

        passed, errors = preflight.run_preflight_checks(feature_id)

        if not passed:
            self._log("preflight_checks_failed", {
                "feature_id": feature_id,
                "errors": errors,
            }, level="warning")

        return passed, errors

    def get_ready_issues_safe(self, feature_id: str) -> list[TaskRef]:
        """
        Get issues ready for work, respecting blocked dependencies.

        An issue is ready if:
        1. Its stage is READY
        2. All its dependencies are DONE (not BLOCKED or SKIPPED)

        Issues with blocked dependencies are marked as SKIPPED.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of TaskRef objects ready for work.
        """
        from swarm_attack.recovery import get_ready_issues_safe, should_skip_issue

        if not self._state_store:
            return []

        state = self._state_store.load(feature_id)
        if not state or not state.tasks:
            return []

        # Get done and blocked issue numbers
        done_issues = {t.issue_number for t in state.done_tasks}
        blocked_issues = {t.issue_number for t in state.blocked_tasks}
        skipped_issues = {t.issue_number for t in state.skipped_tasks}

        # Check for tasks that should be skipped due to blocked dependencies
        for task in state.tasks:
            if task.stage == TaskStage.READY:
                blocking_issue = should_skip_issue(task, blocked_issues, skipped_issues)
                if blocking_issue:
                    # Mark as SKIPPED with reason
                    task.stage = TaskStage.SKIPPED
                    task.failure_reason = f"Dependency #{blocking_issue} is blocked/skipped"
                    skipped_issues.add(task.issue_number)

                    self._log("issue_skipped_dependency", {
                        "feature_id": feature_id,
                        "issue_number": task.issue_number,
                        "blocking_issue": blocking_issue,
                    })

        # Save if any tasks were skipped
        if any(t.stage == TaskStage.SKIPPED for t in state.tasks):
            self._state_store.save(state)

        # Return ready issues
        return get_ready_issues_safe(state.tasks, done_issues, blocked_issues)

    def validate_no_circular_deps(self, feature_id: str) -> Optional[str]:
        """
        Detect circular dependencies in task graph.

        Uses Kahn's algorithm for topological sort.

        Args:
            feature_id: The feature identifier.

        Returns:
            Error message if cycle detected, None otherwise.
        """
        from swarm_attack.recovery import validate_no_circular_deps

        if not self._state_store:
            return None

        state = self._state_store.load(feature_id)
        if not state or not state.tasks:
            return None

        error = validate_no_circular_deps(state.tasks)

        if error:
            self._log("circular_dependency_detected", {
                "feature_id": feature_id,
                "error": error,
            }, level="error")

        return error
