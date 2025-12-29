"""Coverage tracking for QA sessions.

Tracks endpoint coverage across QA sessions and computes coverage percentages.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json


@dataclass
class CoverageBaseline:
    """Baseline coverage snapshot from a QA session."""
    session_id: str
    captured_at: str  # ISO timestamp
    endpoints_discovered: int
    endpoints_tested: int
    coverage_percentage: float
    endpoint_list: list[str]
    tested_endpoints: list[str]


@dataclass
class CoverageReport:
    """Coverage comparison report between sessions."""
    current_session_id: str
    baseline_session_id: Optional[str]
    endpoints_discovered: int
    endpoints_tested: int
    coverage_percentage: float
    coverage_delta: float  # vs baseline
    untested_endpoints: list[str]
    newly_tested: list[str]


class CoverageTracker:
    """Track QA endpoint coverage across sessions."""

    def __init__(self, swarm_dir: Path):
        """Initialize coverage tracker.

        Args:
            swarm_dir: Path to .swarm directory
        """
        self._coverage_dir = swarm_dir / "qa" / "coverage"
        self._coverage_dir.mkdir(parents=True, exist_ok=True)

    def capture_baseline(
        self,
        session_id: str,
        endpoints_discovered: list[str],
        endpoints_tested: list[str]
    ) -> CoverageBaseline:
        """Capture coverage baseline for a session.

        Args:
            session_id: Unique session identifier
            endpoints_discovered: All endpoints available for testing
            endpoints_tested: Endpoints that were actually tested

        Returns:
            CoverageBaseline with captured metrics
        """
        discovered_count = len(endpoints_discovered)
        tested_count = len(endpoints_tested)
        coverage_pct = (tested_count / max(discovered_count, 1)) * 100

        baseline = CoverageBaseline(
            session_id=session_id,
            captured_at=datetime.now().isoformat(),
            endpoints_discovered=discovered_count,
            endpoints_tested=tested_count,
            coverage_percentage=coverage_pct,
            endpoint_list=endpoints_discovered,
            tested_endpoints=endpoints_tested,
        )

        self._save_baseline(baseline)
        return baseline

    def get_latest_baseline(self, feature_id: Optional[str] = None) -> Optional[CoverageBaseline]:
        """Get most recent baseline for comparison.

        Args:
            feature_id: Optional feature filter (not yet implemented)

        Returns:
            Most recent CoverageBaseline or None if not found
        """
        path = self._coverage_dir / "latest-baseline.json"
        if not path.exists():
            return None
        with path.open() as f:
            data = json.load(f)
        return CoverageBaseline(**data)

    def compare_to_baseline(
        self,
        session_id: str,
        endpoints_discovered: list[str],
        endpoints_tested: list[str]
    ) -> CoverageReport:
        """Compare current session coverage to baseline.

        Args:
            session_id: Current session identifier
            endpoints_discovered: All endpoints available for testing
            endpoints_tested: Endpoints that were actually tested

        Returns:
            CoverageReport with comparison metrics
        """
        baseline = self.get_latest_baseline()
        discovered_count = len(endpoints_discovered)
        tested_count = len(endpoints_tested)
        current_pct = (tested_count / max(discovered_count, 1)) * 100

        if baseline:
            delta = current_pct - baseline.coverage_percentage
            newly_tested = [e for e in endpoints_tested if e not in baseline.tested_endpoints]
        else:
            delta = 0.0
            newly_tested = list(endpoints_tested)

        untested = [e for e in endpoints_discovered if e not in endpoints_tested]

        return CoverageReport(
            current_session_id=session_id,
            baseline_session_id=baseline.session_id if baseline else None,
            endpoints_discovered=discovered_count,
            endpoints_tested=tested_count,
            coverage_percentage=current_pct,
            coverage_delta=delta,
            untested_endpoints=untested,
            newly_tested=newly_tested,
        )

    def _save_baseline(self, baseline: CoverageBaseline) -> None:
        """Save baseline as latest and to history.

        Args:
            baseline: Baseline to save
        """
        baseline_dict = asdict(baseline)

        # Save as latest
        latest_path = self._coverage_dir / "latest-baseline.json"
        with latest_path.open("w") as f:
            json.dump(baseline_dict, f, indent=2)

        # Append to history
        history_path = self._coverage_dir / "coverage-history.json"
        history: list[dict] = []
        if history_path.exists():
            with history_path.open() as f:
                history = json.load(f)
        history.append(baseline_dict)
        with history_path.open("w") as f:
            json.dump(history[-100:], f, indent=2)  # Keep last 100
