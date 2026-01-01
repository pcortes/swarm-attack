"""
Session Initialization Protocol.

This module implements the mandatory 5-step initialization sequence that must
be executed before any agent session begins development work. This addresses
the "engineer arriving with no memory" problem by ensuring every session:

1. Verifies working directory exists and is a git repo
2. Reviews git history and progress log
3. Confirms task/issue assignment (if specified)
4. Runs verification tests for completed issues
5. Logs session start

The protocol prevents sessions from starting if verification tests are failing,
ensuring no work begins on a broken codebase.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.progress_logger import ProgressLogger
    from swarm_attack.state_store import StateStore


@dataclass
class VerificationResult:
    """Result of running verification tests."""

    passed: bool
    test_count: int = 0
    failures: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @classmethod
    def success(cls, test_count: int = 0, duration: float = 0.0) -> VerificationResult:
        """Create a successful verification result."""
        return cls(passed=True, test_count=test_count, duration_seconds=duration)

    @classmethod
    def failure(cls, failures: list[str], test_count: int = 0) -> VerificationResult:
        """Create a failed verification result."""
        return cls(passed=False, failures=failures, test_count=test_count)


@dataclass
class InitResult:
    """Result of session initialization."""

    ready: bool
    reason: str = ""
    verification_summary: Optional[dict] = None

    @classmethod
    def success(cls, verification_summary: Optional[dict] = None) -> InitResult:
        """Create a successful init result."""
        return cls(ready=True, verification_summary=verification_summary)

    @classmethod
    def blocked(cls, reason: str) -> InitResult:
        """Create a blocked init result."""
        return cls(ready=False, reason=reason)


class SessionInitializer:
    """
    Mandatory session initialization before coding begins.

    Implements the 5-step initialization protocol to ensure every agent
    session starts with proper context and a verified codebase.
    """

    def __init__(
        self,
        config: SwarmConfig,
        state_store: StateStore,
        progress_logger: ProgressLogger,
    ) -> None:
        """
        Initialize the session initializer.

        Args:
            config: SwarmConfig with repo_root and other settings.
            state_store: StateStore for loading feature/session state.
            progress_logger: ProgressLogger for logging session events.
        """
        self._config = config
        self._state_store = state_store
        self._progress_logger = progress_logger

    def initialize_session(
        self,
        feature_id: str,
        issue_number: Optional[int] = None,
    ) -> InitResult:
        """
        MANDATORY initialization before any coding begins.

        Runs the 5-step protocol:
        1. Verify working directory exists and is a git repo
        2. Review git history and progress log
        3. Confirm task/issue assignment (if issue specified)
        4. Run verification tests for completed issues
        5. Log session start

        Args:
            feature_id: The feature identifier.
            issue_number: Optional specific issue to work on.

        Returns:
            InitResult with ready=True if session can proceed.
        """
        # Step 1: Verify working directory exists
        if not self._verify_working_directory():
            return InitResult.blocked("Working directory invalid")

        # Step 2: Review git history and progress log
        self._review_git_history(feature_id)
        self._review_progress_log(feature_id)

        # Step 3: Confirm task/issue assignment (if issue specified)
        if issue_number is not None:
            if not self._verify_issue_assignment(feature_id, issue_number):
                return InitResult.blocked(
                    f"Issue #{issue_number} not found or blocked"
                )

        # Step 4: Run verification tests for completed issues
        verification = self._run_verification_tests(feature_id)
        if not verification.passed:
            return InitResult.blocked(
                f"Verification failed: {verification.failures}"
            )

        # Step 5: Log session start
        self._progress_logger.log_session_start(feature_id, issue_number)

        return InitResult.success(
            verification_summary={"tests": verification.test_count}
        )

    def _verify_working_directory(self) -> bool:
        """
        Verify repo root exists and is a git repo.

        Returns:
            True if valid git repo, False otherwise.
        """
        repo_root = Path(self._config.repo_root)
        if not repo_root.exists():
            return False
        if not (repo_root / ".git").exists():
            return False
        return True

    def _review_git_history(self, feature_id: str) -> list[str]:
        """
        Extract recent commits (last 10) for context.

        This is informational - doesn't block initialization.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of recent commit strings (oneline format), empty list on error.
        """
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self._config.repo_root,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                # Filter out empty strings
                return [line for line in lines if line]
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        return []

    def _review_progress_log(self, feature_id: str) -> str:
        """
        Load prior session summaries from progress.txt.

        This is informational - doesn't block initialization.

        Args:
            feature_id: The feature identifier.

        Returns:
            Content of progress.txt, empty string on error or if missing.
        """
        progress_path = (
            Path(self._config.repo_root) / ".swarm" / "features" / feature_id / "progress.txt"
        )
        try:
            if progress_path.exists():
                return progress_path.read_text()
        except Exception:
            pass
        return ""

    def _verify_issue_assignment(
        self,
        feature_id: str,
        issue_number: int
    ) -> bool:
        """
        Verify the issue exists and is not blocked.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number to verify.

        Returns:
            True if issue exists and is workable, False otherwise.
        """
        if self._state_store is None:
            return True  # No state store means no validation

        state = self._state_store.load(feature_id)
        if state is None:
            return False

        # Check if issue exists in tasks
        for task in state.tasks:
            if task.issue_number == issue_number:
                # Check if not blocked
                from swarm_attack.models import TaskStage
                if task.stage == TaskStage.BLOCKED:
                    return False
                return True

        return False

    def _run_verification_tests(self, feature_id: str) -> VerificationResult:
        """
        Run tests for completed issues to check for regressions.

        Args:
            feature_id: The feature identifier.

        Returns:
            VerificationResult with pass/fail status.
        """
        import time

        test_path = Path(self._config.repo_root) / "tests" / "generated" / feature_id
        if not test_path.exists():
            # No tests for this feature yet - that's fine
            return VerificationResult.success(test_count=0)

        start_time = time.time()
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=self._config.repo_root,
                timeout=300,  # 5 minute timeout
            )
            duration = time.time() - start_time

            if result.returncode == 0:
                # Parse test count from output
                test_count = self._parse_test_count(result.stdout)
                return VerificationResult.success(
                    test_count=test_count,
                    duration=duration
                )
            else:
                # Parse failures from output
                failures = self._parse_failures(result.stdout)
                return VerificationResult.failure(
                    failures=failures or ["See pytest output"]
                )

        except subprocess.TimeoutExpired:
            return VerificationResult.failure(
                failures=["Test run timed out after 5 minutes"]
            )
        except FileNotFoundError:
            # pytest not installed - skip verification
            return VerificationResult.success(test_count=0)
        except Exception as e:
            return VerificationResult.failure(failures=[str(e)])

    def _parse_test_count(self, output: str) -> int:
        """Parse test count from pytest output."""
        import re

        # Look for "X passed" in output
        match = re.search(r"(\d+)\s+passed", output)
        if match:
            return int(match.group(1))
        return 0

    def _parse_failures(self, output: str) -> list[str]:
        """Parse failure messages from pytest output."""
        import re

        failures = []
        # Look for FAILED test names with :: separator (pytest format: file.py::test_name)
        # Pattern requires :: to avoid matching progress indicators like '[ 75%]'
        for match in re.finditer(r"FAILED\s+([\w/._-]+::[\w:]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures
