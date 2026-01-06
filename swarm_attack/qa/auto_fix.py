"""AutoFixOrchestrator - Automated detection and fixing loop.

This module provides the AutoFixOrchestrator that chains static bug detection
to the bug bash pipeline for automated remediation.

Flow:
    detection -> create bugs -> analyze -> approve -> fix -> repeat until clean
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.config import AutoFixConfig
    from swarm_attack.static_analysis.detector import StaticBugDetector
    from swarm_attack.static_analysis.models import StaticBugReport

logger = logging.getLogger(__name__)


@dataclass
class AutoFixResult:
    """Result from an auto-fix run.

    Attributes:
        bugs_found: Total number of bugs detected across all iterations.
        bugs_fixed: Number of bugs successfully fixed.
        iterations_run: Number of detection-fix iterations completed.
        success: True if no bugs remain (clean codebase).
        checkpoints_triggered: Number of critical bugs requiring human review.
        dry_run: Whether this was a dry-run (no fixes applied).
        errors: List of errors encountered during the run.
    """

    bugs_found: int = 0
    bugs_fixed: int = 0
    iterations_run: int = 0
    success: bool = False
    checkpoints_triggered: int = 0
    dry_run: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "bugs_found": self.bugs_found,
            "bugs_fixed": self.bugs_fixed,
            "iterations_run": self.iterations_run,
            "success": self.success,
            "checkpoints_triggered": self.checkpoints_triggered,
            "dry_run": self.dry_run,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AutoFixResult":
        """Create instance from dictionary."""
        return cls(
            bugs_found=data.get("bugs_found", 0),
            bugs_fixed=data.get("bugs_fixed", 0),
            iterations_run=data.get("iterations_run", 0),
            success=data.get("success", False),
            checkpoints_triggered=data.get("checkpoints_triggered", 0),
            dry_run=data.get("dry_run", False),
            errors=data.get("errors", []),
        )


class AutoFixOrchestrator:
    """Orchestrator for automatic bug detection and fixing.

    Chains the StaticBugDetector to BugOrchestrator for a complete
    detection-fix loop. Runs until all bugs are fixed or max_iterations
    is reached.

    Example:
        from swarm_attack.bug_orchestrator import BugOrchestrator
        from swarm_attack.static_analysis.detector import StaticBugDetector
        from swarm_attack.config import AutoFixConfig, SwarmConfig

        config = load_config()
        bug_orchestrator = BugOrchestrator(config)
        detector = StaticBugDetector()
        auto_fix_config = config.auto_fix

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=bug_orchestrator,
            detector=detector,
            config=auto_fix_config,
        )

        result = orchestrator.run(
            target="tests/",
            max_iterations=5,
            auto_approve=True,
        )
        print(f"Fixed {result.bugs_fixed} of {result.bugs_found} bugs")
    """

    def __init__(
        self,
        bug_orchestrator: BugOrchestrator,
        detector: StaticBugDetector,
        config: AutoFixConfig,
    ) -> None:
        """Initialize the AutoFixOrchestrator.

        Args:
            bug_orchestrator: BugOrchestrator instance for fix pipeline.
            detector: StaticBugDetector instance for bug detection.
            config: AutoFixConfig with settings.
        """
        self._bug_orchestrator = bug_orchestrator
        self._detector = detector
        self._config = config
        self._checkpoint_callback: Optional[Callable[[StaticBugReport], bool]] = None

    def set_checkpoint_callback(
        self, callback: Callable[[StaticBugReport], bool]
    ) -> None:
        """Set callback for critical bug checkpoints.

        The callback is invoked when a critical bug is found and auto_approve
        is False. It should return True to proceed with fixing, False to skip.

        Args:
            callback: Function that takes a StaticBugReport and returns bool.
        """
        self._checkpoint_callback = callback

    def _create_bug_from_finding(self, bug: StaticBugReport) -> Optional[str]:
        """Create a bug investigation from a static analysis finding.

        Converts a StaticBugReport into a BugOrchestrator bug investigation.

        Args:
            bug: The static analysis finding to convert.

        Returns:
            The bug_id if created successfully, None otherwise.
        """
        # Build description from the finding
        description = (
            f"[{bug.source.upper()}] {bug.error_code}: {bug.message} "
            f"at {bug.file_path}:{bug.line_number}"
        )

        # Determine test path if from pytest
        test_path = bug.file_path if bug.source == "pytest" else None

        # Create the bug via BugOrchestrator
        result = self._bug_orchestrator.init_bug(
            description=description,
            test_path=test_path,
            error_message=bug.message,
        )

        if result.success:
            logger.info(f"Created bug investigation: {result.bug_id}")
            return result.bug_id
        else:
            logger.warning(
                f"Failed to create bug investigation: {result.error}"
            )
            return None

    def run(
        self,
        target: Optional[str] = None,
        max_iterations: Optional[int] = None,
        auto_approve: Optional[bool] = None,
        dry_run: Optional[bool] = None,
    ) -> AutoFixResult:
        """Run the detection-fix loop.

        Detects bugs using static analysis, creates investigations, and
        attempts to fix them through the bug bash pipeline. Repeats until
        no bugs are found or max_iterations is reached.

        Args:
            target: Path to analyze (file or directory). None for current dir.
            max_iterations: Maximum fix iterations. Defaults to config value.
            auto_approve: Whether to auto-approve fixes. Defaults to config.
            dry_run: If True, detect but don't fix. Defaults to config.

        Returns:
            AutoFixResult with statistics and success status.
        """
        # Apply defaults from config
        if max_iterations is None:
            max_iterations = self._config.max_iterations
        if auto_approve is None:
            auto_approve = self._config.auto_approve
        if dry_run is None:
            dry_run = self._config.dry_run

        result = AutoFixResult(dry_run=dry_run)
        iteration = 0

        logger.info(
            f"Starting auto-fix loop: target={target}, max_iterations={max_iterations}, "
            f"auto_approve={auto_approve}, dry_run={dry_run}"
        )

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Auto-fix iteration {iteration}/{max_iterations}")

            # Step 1: Detect bugs
            detection_result = self._detector.detect_all(target)
            bugs = detection_result.bugs

            if not bugs:
                logger.info("No bugs detected - codebase is clean!")
                result.success = True
                result.iterations_run = iteration
                return result

            logger.info(
                f"Detected {len(bugs)} bugs from tools: {detection_result.tools_run}"
            )
            result.bugs_found += len(bugs)

            # Step 2: Process each bug
            for bug in bugs:
                logger.debug(
                    f"Processing bug: {bug.source}:{bug.error_code} "
                    f"at {bug.file_path}:{bug.line_number}"
                )

                # Critical bugs require human checkpoint when not auto_approve
                if bug.severity == "critical" and not auto_approve:
                    result.checkpoints_triggered += 1

                    if self._checkpoint_callback:
                        proceed = self._checkpoint_callback(bug)
                        if not proceed:
                            logger.info(
                                f"Human checkpoint: skipping critical bug "
                                f"{bug.error_code} at {bug.file_path}"
                            )
                            continue
                    else:
                        logger.warning(
                            f"Critical bug requires human review: {bug.error_code} "
                            f"at {bug.file_path}:{bug.line_number}. "
                            "Set checkpoint_callback or use auto_approve=True."
                        )
                        continue

                # Create bug investigation
                bug_id = self._create_bug_from_finding(bug)
                if not bug_id:
                    result.errors.append(
                        f"Failed to create bug for {bug.file_path}:{bug.line_number}"
                    )
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would fix: {bug_id}")
                    continue

                # Step 3: Analyze the bug
                try:
                    analyze_result = self._bug_orchestrator.analyze(bug_id)
                    if not analyze_result.success:
                        logger.warning(
                            f"Analysis failed for {bug_id}: {analyze_result.error}"
                        )
                        result.errors.append(
                            f"Analysis failed for {bug_id}: {analyze_result.error}"
                        )
                        continue
                except Exception as e:
                    logger.exception(f"Exception during analysis of {bug_id}")
                    result.errors.append(f"Analysis exception for {bug_id}: {e}")
                    continue

                # Step 4: Approve (if auto_approve)
                if auto_approve:
                    approve_result = self._bug_orchestrator.approve(bug_id)
                    if not approve_result.success:
                        logger.warning(
                            f"Approval failed for {bug_id}: {approve_result.error}"
                        )
                        result.errors.append(
                            f"Approval failed for {bug_id}: {approve_result.error}"
                        )
                        continue
                else:
                    # Without auto_approve, bugs stay in PLANNED state
                    logger.info(
                        f"Bug {bug_id} analyzed and planned - awaiting approval"
                    )
                    continue

                # Step 5: Fix the bug
                try:
                    fix_result = self._bug_orchestrator.fix(bug_id)
                    if fix_result.success:
                        logger.info(f"Successfully fixed bug: {bug_id}")
                        result.bugs_fixed += 1
                    else:
                        logger.warning(
                            f"Fix failed for {bug_id}: {fix_result.error}"
                        )
                        result.errors.append(
                            f"Fix failed for {bug_id}: {fix_result.error}"
                        )
                except Exception as e:
                    logger.exception(f"Exception during fix of {bug_id}")
                    result.errors.append(f"Fix exception for {bug_id}: {e}")

            result.iterations_run = iteration

        # Max iterations reached
        logger.warning(
            f"Max iterations ({max_iterations}) reached - some bugs may remain"
        )
        result.success = False
        return result

    def _get_file_mtimes(self, target: Optional[str]) -> dict[str, float]:
        """Get modification times for all Python files in target directory.

        Args:
            target: Path to scan. None for current directory.

        Returns:
            Dictionary mapping file paths to modification times.
        """
        mtimes: dict[str, float] = {}
        target_path = Path(target) if target else Path(".")

        if not target_path.exists():
            return mtimes

        if target_path.is_file():
            try:
                mtimes[str(target_path)] = target_path.stat().st_mtime
            except OSError:
                pass
            return mtimes

        # Scan directory for Python files
        for root, _dirs, files in os.walk(target_path):
            for filename in files:
                if filename.endswith(".py"):
                    file_path = Path(root) / filename
                    try:
                        mtimes[str(file_path)] = file_path.stat().st_mtime
                    except OSError:
                        pass

        return mtimes

    def _files_changed(
        self,
        old_mtimes: dict[str, float],
        new_mtimes: dict[str, float],
    ) -> bool:
        """Check if any files have changed between two mtime snapshots.

        Args:
            old_mtimes: Previous file modification times.
            new_mtimes: Current file modification times.

        Returns:
            True if any files were added, removed, or modified.
        """
        # Check for new or removed files
        if set(old_mtimes.keys()) != set(new_mtimes.keys()):
            return True

        # Check for modified files
        for path, mtime in new_mtimes.items():
            if path in old_mtimes and old_mtimes[path] != mtime:
                return True

        return False

    def watch(
        self,
        target: Optional[str] = None,
        max_iterations: Optional[int] = None,
        auto_approve: Optional[bool] = None,
    ) -> None:
        """Watch mode: run detection-fix loop on file changes.

        Uses simple polling (no external dependencies like watchdog).
        Ctrl+C to stop.

        Args:
            target: Path to watch (file or directory). None for current dir.
            max_iterations: Maximum fix iterations per detection cycle.
                Defaults to config value.
            auto_approve: Whether to auto-approve fixes. Defaults to config.
        """
        # Apply defaults from config
        if max_iterations is None:
            max_iterations = self._config.max_iterations
        if auto_approve is None:
            auto_approve = self._config.auto_approve

        poll_seconds = self._config.watch_poll_seconds

        logger.info(
            f"Starting watch mode: target={target}, poll_interval={poll_seconds}s, "
            f"max_iterations={max_iterations}, auto_approve={auto_approve}"
        )
        logger.info("Press Ctrl+C to stop watching.")

        # Initial file state
        last_mtimes = self._get_file_mtimes(target)

        # Run initial detection
        try:
            logger.info("Running initial detection...")
            self.run(
                target=target,
                max_iterations=max_iterations,
                auto_approve=auto_approve,
            )
        except KeyboardInterrupt:
            logger.info("Watch mode stopped by user (Ctrl+C).")
            return

        # Watch loop
        try:
            while True:
                time.sleep(poll_seconds)

                # Check for file changes
                current_mtimes = self._get_file_mtimes(target)
                if self._files_changed(last_mtimes, current_mtimes):
                    logger.info("File changes detected, running detection-fix loop...")
                    try:
                        self.run(
                            target=target,
                            max_iterations=max_iterations,
                            auto_approve=auto_approve,
                        )
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        logger.exception(f"Error during detection-fix loop: {e}")

                    # Update mtimes after run
                    last_mtimes = self._get_file_mtimes(target)
                else:
                    # No changes, update snapshot anyway in case
                    # files were modified during the run
                    last_mtimes = current_mtimes

        except KeyboardInterrupt:
            logger.info("Watch mode stopped by user (Ctrl+C).")
