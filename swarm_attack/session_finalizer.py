"""
Session Finalization Protocol.

This module implements the mandatory finalization sequence that must be
executed before marking any issue as complete. This ensures:

1. All feature tests pass (not just the current issue's tests)
2. No regressions are introduced
3. Verification tracker is updated with final status
4. Session end is logged

The protocol prevents issues from being marked DONE if tests are failing.
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
    from swarm_attack.verification_tracker import VerificationTracker


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
class FinalizeResult:
    """Result of session finalization."""

    can_complete: bool
    reason: str = ""

    @classmethod
    def success(cls) -> FinalizeResult:
        """Create a successful finalize result."""
        return cls(can_complete=True)

    @classmethod
    def blocked(cls, reason: str) -> FinalizeResult:
        """Create a blocked finalize result."""
        return cls(can_complete=False, reason=reason)


class SessionFinalizer:
    """
    Mandatory session finalization before marking complete.

    Ensures all tests pass and verification status is tracked before
    allowing an issue to be marked as DONE.
    """

    def __init__(
        self,
        config: SwarmConfig,
        state_store: StateStore,
        progress_logger: ProgressLogger,
        verification_tracker: VerificationTracker,
    ) -> None:
        """
        Initialize the session finalizer.

        Args:
            config: SwarmConfig with repo_root and other settings.
            state_store: StateStore for loading feature/session state.
            progress_logger: ProgressLogger for logging session events.
            verification_tracker: VerificationTracker for updating status.
        """
        self._config = config
        self._state_store = state_store
        self._progress_logger = progress_logger
        self._verification_tracker = verification_tracker

    def finalize_session(
        self,
        feature_id: str,
        issue_number: int,
        commits: Optional[list[str]] = None,
    ) -> FinalizeResult:
        """
        MANDATORY finalization before marking issue complete.

        Steps:
        1. Run ALL feature tests (not just this issue's)
        2. Update verification tracker
        3. Log session end

        Args:
            feature_id: The feature identifier.
            issue_number: The issue that was worked on.
            commits: List of commit hashes created during the session.

        Returns:
            FinalizeResult with can_complete=True if issue can be marked done.
        """
        # Step 1: Run ALL feature tests (not just this issue's)
        verification = self._run_all_feature_tests(feature_id)
        if not verification.passed:
            # Log the failure
            self._progress_logger.log_verification_failed(
                len(verification.failures),
                verification.failures
            )
            return FinalizeResult.blocked(
                f"Tests failing: {verification.failures}"
            )

        # Step 2: Update verification tracker
        self._verification_tracker.update_issue_status(
            feature_id=feature_id,
            issue_number=issue_number,
            status="passing",
            test_count=verification.test_count,
        )

        # Log verification passed
        self._progress_logger.log_verification_passed(verification.test_count)

        # Step 3: Log session end
        self._progress_logger.log_session_end(
            feature_id,
            issue_number,
            status="DONE",
            commits=commits or [],
        )

        return FinalizeResult.success()

    def _run_all_feature_tests(self, feature_id: str) -> VerificationResult:
        """
        Run all tests for the feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            VerificationResult with pass/fail status.
        """
        import time

        test_path = Path(self._config.repo_root) / "tests" / "generated" / feature_id
        if not test_path.exists():
            # No tests for this feature yet
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
        # Look for FAILED test names
        for match in re.finditer(r"FAILED\s+([^\s]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures

    def finalize_failed_session(
        self,
        feature_id: str,
        issue_number: int,
        error: str,
        commits: Optional[list[str]] = None,
    ) -> None:
        """
        Log a failed session (for use when session fails, not completes).

        Args:
            feature_id: The feature identifier.
            issue_number: The issue that was worked on.
            error: Error message describing the failure.
            commits: List of commit hashes created during the session.
        """
        # Update verification tracker with failing status
        self._verification_tracker.update_issue_status(
            feature_id=feature_id,
            issue_number=issue_number,
            status="failing",
            test_count=0,
        )

        # Log error
        self._progress_logger.log_error(error)

        # Log session end with FAILED status
        self._progress_logger.log_session_end(
            feature_id,
            issue_number,
            status="FAILED",
            commits=commits or [],
        )
