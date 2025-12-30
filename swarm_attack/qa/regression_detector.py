"""Regression detection for QA sessions.

Detects regressions by comparing QA findings between sessions.
Tracks which bugs have regressed (were fixed, now failing again).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class RegressionReport:
    """Report comparing findings between baseline and current session."""
    baseline_session_id: str
    current_session_id: str
    new_findings: list[dict]  # Findings in current but not baseline
    fixed_findings: list[dict]  # Findings in baseline but not current
    regression_count: int
    improvement_count: int
    severity: str  # "critical", "moderate", "none"


class RegressionDetector:
    """Detect regressions by comparing QA sessions."""

    def __init__(self, swarm_dir: Path):
        """Initialize regression detector.

        Args:
            swarm_dir: Path to .swarm directory
        """
        self._baselines_dir = swarm_dir / "qa" / "baselines"
        self._baselines_dir.mkdir(parents=True, exist_ok=True)

    def establish_baseline(self, session_id: str, findings: list) -> None:
        """Save session as baseline for future comparison.

        Args:
            session_id: Unique session identifier
            findings: List of QAFinding objects or dicts
        """
        baseline_path = self._baselines_dir / f"{session_id}.json"
        findings_data = [self._finding_to_dict(f) for f in findings]
        with baseline_path.open("w") as f:
            json.dump({
                "session_id": session_id,
                "findings": findings_data,
            }, f, indent=2)

        # Also set as latest
        latest_path = self._baselines_dir / "latest.json"
        with latest_path.open("w") as f:
            json.dump({
                "session_id": session_id,
                "findings": findings_data,
            }, f, indent=2)

    def detect_regressions(
        self,
        current_session_id: str,
        current_findings: list
    ) -> Optional[RegressionReport]:
        """Compare current findings to baseline.

        Args:
            current_session_id: Current session identifier
            current_findings: List of QAFinding objects or dicts

        Returns:
            RegressionReport or None if no baseline exists
        """
        baseline = self._load_latest_baseline()
        if not baseline:
            return None

        # Convert current findings to dicts
        current_findings_dicts = [self._finding_to_dict(f) for f in current_findings]

        # Create keys for comparison
        baseline_keys = {self._finding_key(f) for f in baseline["findings"]}
        current_keys = {self._finding_key(f) for f in current_findings_dicts}

        # Find new and fixed
        new_keys = current_keys - baseline_keys
        fixed_keys = baseline_keys - current_keys

        new_findings = [f for f in current_findings_dicts if self._finding_key(f) in new_keys]
        fixed_findings = [f for f in baseline["findings"] if self._finding_key(f) in fixed_keys]

        # Determine severity based on new findings
        has_critical = any(
            self._get_severity(f) == "critical"
            for f in current_findings_dicts
            if self._finding_key(f) in new_keys
        )
        severity = "critical" if has_critical else ("moderate" if new_findings else "none")

        return RegressionReport(
            baseline_session_id=baseline["session_id"],
            current_session_id=current_session_id,
            new_findings=new_findings,
            fixed_findings=fixed_findings,
            regression_count=len(new_findings),
            improvement_count=len(fixed_findings),
            severity=severity,
        )

    def _finding_key(self, finding: dict) -> str:
        """Create unique key for finding comparison.

        Args:
            finding: Finding dict

        Returns:
            Unique string key for comparison
        """
        return f"{finding.get('endpoint', '')}:{finding.get('category', '')}:{finding.get('test_type', '')}"

    def _get_severity(self, finding: Any) -> str:
        """Get severity from finding dict or object.

        Args:
            finding: Finding dict or object

        Returns:
            Severity string
        """
        if isinstance(finding, dict):
            return finding.get("severity", "moderate")
        return getattr(finding, "severity", "moderate")

    def _finding_to_dict(self, finding: Any) -> dict:
        """Convert QAFinding to dict.

        Args:
            finding: QAFinding object or dict

        Returns:
            Dict representation
        """
        if isinstance(finding, dict):
            return finding
        if hasattr(finding, "to_dict"):
            return finding.to_dict()
        if hasattr(finding, "__dict__"):
            return {k: v for k, v in finding.__dict__.items() if not k.startswith("_")}
        return dict(finding)

    def _load_latest_baseline(self) -> Optional[dict]:
        """Load latest baseline.

        Returns:
            Baseline dict or None if not found
        """
        path = self._baselines_dir / "latest.json"
        if not path.exists():
            return None
        with path.open() as f:
            return json.load(f)
