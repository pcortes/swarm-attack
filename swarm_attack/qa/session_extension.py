"""QA Session Extension for coverage and regression tracking.

Extends QA session lifecycle with coverage tracking and regression detection.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .coverage_tracker import CoverageTracker, CoverageReport
from .regression_detector import RegressionDetector, RegressionReport


@dataclass
class QASessionExtensionResult:
    """Result from session extension analysis."""
    coverage_report: Optional[CoverageReport]
    regression_report: Optional[RegressionReport]
    should_block: bool
    block_reason: Optional[str]


class QASessionExtension:
    """Extends QA session with coverage and regression tracking."""

    def __init__(self, swarm_dir: Path):
        """Initialize session extension.

        Args:
            swarm_dir: Path to .swarm directory
        """
        self._coverage_tracker = CoverageTracker(swarm_dir)
        self._regression_detector = RegressionDetector(swarm_dir)
        self._current_endpoints: list[str] = []

    def on_session_start(
        self,
        session_id: str,
        endpoints_discovered: list[str]
    ) -> None:
        """Called when QA session starts.

        Args:
            session_id: Unique session identifier
            endpoints_discovered: Endpoints available for testing
        """
        # Record what endpoints are available for testing
        self._current_endpoints = list(endpoints_discovered)

    def on_session_complete(
        self,
        session_id: str,
        endpoints_tested: list[str],
        findings: list
    ) -> QASessionExtensionResult:
        """Called when QA session completes.

        Args:
            session_id: Unique session identifier
            endpoints_tested: Endpoints that were actually tested
            findings: List of QAFinding objects or dicts

        Returns:
            QASessionExtensionResult with analysis and blocking decisions
        """
        # Capture coverage
        coverage_report = self._coverage_tracker.compare_to_baseline(
            session_id,
            self._current_endpoints,
            endpoints_tested
        )

        # Check for regressions
        regression_report = self._regression_detector.detect_regressions(
            session_id,
            findings
        )

        # Determine if should block
        should_block = False
        block_reason: Optional[str] = None

        if regression_report and regression_report.severity == "critical":
            should_block = True
            block_reason = f"Critical regressions detected: {regression_report.regression_count} new issues"

        if coverage_report.coverage_delta < -10:  # Coverage dropped by 10%+
            should_block = True
            block_reason = f"Coverage dropped significantly: {coverage_report.coverage_delta:.1f}%"

        return QASessionExtensionResult(
            coverage_report=coverage_report,
            regression_report=regression_report,
            should_block=should_block,
            block_reason=block_reason,
        )

    def set_as_baseline(
        self,
        session_id: str,
        endpoints_tested: list[str],
        findings: list
    ) -> None:
        """Mark current session as the baseline for future comparisons.

        Args:
            session_id: Session to use as baseline
            endpoints_tested: Endpoints that were tested
            findings: Findings from the session
        """
        self._coverage_tracker.capture_baseline(
            session_id,
            self._current_endpoints,
            endpoints_tested
        )
        self._regression_detector.establish_baseline(session_id, findings)
