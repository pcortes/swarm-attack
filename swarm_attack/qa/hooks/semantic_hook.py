# swarm_attack/qa/hooks/semantic_hook.py
"""SemanticTestHook for post-implementation semantic QA testing.

Integrates SemanticTesterAgent into the feature pipeline orchestrator,
running after verifier passes and before commit creation.

Verdicts:
- FAIL: Block commit, create bug investigation
- PARTIAL: Log warning, allow commit to proceed
- PASS: Allow commit normally
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.qa.agents.semantic_tester import (
    SemanticTesterAgent,
    SemanticScope,
)
from swarm_attack.qa.regression_scheduler import (
    RegressionScheduler,
    RegressionSchedulerConfig,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class SemanticHookResult:
    """Result of running the SemanticTestHook."""

    verdict: str = "PASS"
    should_block: bool = False
    block_reason: Optional[str] = None

    # Bug tracking
    created_bug_id: Optional[str] = None

    # Warnings and recommendations
    warning: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)

    # Evidence from testing
    evidence: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)

    # Error handling
    error: Optional[str] = None
    skipped: bool = False


class SemanticTestHook:
    """
    Hook that runs semantic testing after verifier passes.

    Uses SemanticTesterAgent (Claude Code CLI) to perform human-like
    semantic validation of code changes before commit.

    Integrates with RegressionScheduler to track commits for periodic
    full regression testing.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the SemanticTestHook.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.enabled = True

        # Create semantic tester
        self.semantic_tester = SemanticTesterAgent(config, logger)

        # Create regression scheduler
        project_root = Path(config.repo_root)
        scheduler_config = RegressionSchedulerConfig()
        self.regression_scheduler = RegressionScheduler(scheduler_config, project_root)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "semantic_test_hook"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def should_run(
        self,
        verifier_passed: bool,
        feature_id: str,
        issue_number: int,
    ) -> bool:
        """
        Determine if semantic testing should run.

        Args:
            verifier_passed: Whether unit test verification passed.
            feature_id: Feature identifier.
            issue_number: Issue number.

        Returns:
            True if hook should run, False otherwise.
        """
        # Skip if disabled
        if not self.enabled:
            self._log("semantic_hook_skip", {"reason": "disabled"})
            return False

        # Skip if verifier failed
        if not verifier_passed:
            self._log("semantic_hook_skip", {"reason": "verifier_failed"})
            return False

        return True

    def run(
        self,
        feature_id: str,
        issue_number: int,
        commit_message: Optional[str] = None,
    ) -> SemanticHookResult:
        """
        Run semantic testing on staged changes.

        Args:
            feature_id: Feature identifier.
            issue_number: Issue number.
            commit_message: Optional commit message for context.

        Returns:
            SemanticHookResult with testing outcomes.
        """
        self._log("semantic_hook_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        try:
            # Get staged diff
            diff_result = self._get_staged_diff()
            if diff_result is None:
                return SemanticHookResult(
                    error="Failed to get staged changes",
                    should_block=False,  # Fail open
                )

            if not diff_result.strip():
                self._log("semantic_hook_skip", {"reason": "no_staged_changes"})
                return SemanticHookResult(
                    skipped=True,
                    warning="No staged changes to test",
                )

            # Build context for semantic testing
            context = {
                "changes": diff_result,
                "expected_behavior": f"Issue #{issue_number} implementation for {feature_id}",
                "test_scope": SemanticScope.CHANGES_ONLY.value,
            }

            # Run semantic test
            agent_result = self.semantic_tester.run(context)

            # Parse result
            output = agent_result.output or {}
            verdict = output.get("verdict", "PARTIAL")
            evidence = output.get("evidence", [])
            issues = output.get("issues", [])
            recommendations = output.get("recommendations", [])

            result = SemanticHookResult(
                verdict=verdict,
                evidence=evidence,
                issues=issues,
                recommendations=recommendations,
            )

            # Handle verdict
            if verdict == "FAIL":
                result.should_block = True
                result.block_reason = self._build_block_reason(issues)

                # Create bug for critical issues
                if issues:
                    result.created_bug_id = self.create_bug(
                        feature_id=feature_id,
                        issue_number=issue_number,
                        issues=issues,
                    )

                self._log("semantic_hook_fail", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "issues": len(issues),
                    "created_bug": result.created_bug_id,
                }, level="error")

            elif verdict == "PARTIAL":
                result.should_block = False
                result.warning = self._build_warning(issues, recommendations)

                self._log("semantic_hook_partial", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "issues": len(issues),
                    "recommendations": len(recommendations),
                }, level="warning")

            else:  # PASS
                result.should_block = False

                # Record for regression tracking
                self.regression_scheduler.record_issue_committed(
                    f"{feature_id}-{issue_number}"
                )

                self._log("semantic_hook_pass", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "evidence": len(evidence),
                })

            return result

        except subprocess.TimeoutExpired as e:
            self._log("semantic_hook_timeout", {"error": str(e)}, level="warning")
            return SemanticHookResult(
                error=f"Semantic test timed out: {e}",
                should_block=False,  # Fail open
            )

        except Exception as e:
            self._log("semantic_hook_error", {"error": str(e)}, level="error")
            return SemanticHookResult(
                error=f"Semantic test failed: {e}",
                should_block=False,  # Fail open - graceful degradation
            )

    def _get_staged_diff(self) -> Optional[str]:
        """
        Get staged changes from git.

        Returns:
            Diff string or None on error.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                self._log("git_diff_error", {"stderr": result.stderr}, level="error")
                return None
            return result.stdout
        except subprocess.TimeoutExpired:
            self._log("git_diff_timeout", {}, level="error")
            return None
        except Exception as e:
            self._log("git_diff_error", {"error": str(e)}, level="error")
            return None

    def _build_block_reason(self, issues: list[dict]) -> str:
        """Build human-readable block reason from issues."""
        if not issues:
            return "Semantic test failed"

        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        if critical_issues:
            first = critical_issues[0]
            return f"Semantic test failed: {first.get('description', 'Critical issue found')}"

        return f"Semantic test failed: {len(issues)} issue(s) found"

    def _build_warning(
        self, issues: list[dict], recommendations: list[str]
    ) -> str:
        """Build warning message from issues and recommendations."""
        parts = []

        if issues:
            parts.append(f"{len(issues)} issue(s) found")

        if recommendations:
            parts.append(f"{len(recommendations)} recommendation(s)")

        return "Semantic test partial: " + ", ".join(parts) if parts else "Semantic test completed with warnings"

    def create_bug(
        self,
        feature_id: str,
        issue_number: int,
        issues: list[dict],
    ) -> Optional[str]:
        """
        Create a bug investigation for semantic test failures.

        Args:
            feature_id: Feature identifier.
            issue_number: Original issue number.
            issues: List of issues found.

        Returns:
            Bug ID if created, None otherwise.
        """
        # For now, generate a local bug ID
        # In full implementation, this would create a GitHub issue
        bug_id = f"BUG-semantic-{feature_id}-{issue_number}"

        self._log("semantic_bug_created", {
            "bug_id": bug_id,
            "feature_id": feature_id,
            "issue_number": issue_number,
            "issue_count": len(issues),
        })

        return bug_id
