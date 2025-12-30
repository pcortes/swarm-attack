"""Tests for QA Session Extension - coverage tracking and regression detection."""

import pytest
from pathlib import Path
from swarm_attack.qa.coverage_tracker import CoverageTracker, CoverageBaseline
from swarm_attack.qa.regression_detector import RegressionDetector, RegressionReport
from swarm_attack.qa.session_extension import QASessionExtension


class TestCoverageTracker:
    def test_captures_baseline(self, tmp_path):
        """Tracker captures coverage baseline."""
        tracker = CoverageTracker(tmp_path / ".swarm")

        baseline = tracker.capture_baseline(
            session_id="sess-001",
            endpoints_discovered=["/api/users", "/api/items", "/api/orders"],
            endpoints_tested=["/api/users", "/api/items"]
        )

        assert baseline.endpoints_discovered == 3
        assert baseline.endpoints_tested == 2
        assert baseline.coverage_percentage == pytest.approx(66.67, rel=0.1)

    def test_compares_to_baseline(self, tmp_path):
        """Tracker compares current to baseline."""
        tracker = CoverageTracker(tmp_path / ".swarm")

        # Create baseline
        tracker.capture_baseline(
            session_id="sess-001",
            endpoints_discovered=["/api/users", "/api/items"],
            endpoints_tested=["/api/users"]
        )

        # Compare new session
        report = tracker.compare_to_baseline(
            session_id="sess-002",
            endpoints_discovered=["/api/users", "/api/items", "/api/orders"],
            endpoints_tested=["/api/users", "/api/items", "/api/orders"]
        )

        assert report.coverage_percentage == 100.0
        assert report.coverage_delta > 0  # Improved
        assert "/api/items" in report.newly_tested

    def test_tracks_untested_endpoints(self, tmp_path):
        """Report shows untested endpoints."""
        tracker = CoverageTracker(tmp_path / ".swarm")

        report = tracker.compare_to_baseline(
            session_id="sess-001",
            endpoints_discovered=["/api/users", "/api/items", "/api/orders"],
            endpoints_tested=["/api/users"]
        )

        assert "/api/items" in report.untested_endpoints
        assert "/api/orders" in report.untested_endpoints

    def test_saves_coverage_history(self, tmp_path):
        """Tracker saves coverage history for trending."""
        tracker = CoverageTracker(tmp_path / ".swarm")

        # Create multiple baselines
        tracker.capture_baseline("sess-001", ["/api/a"], ["/api/a"])
        tracker.capture_baseline("sess-002", ["/api/a", "/api/b"], ["/api/a", "/api/b"])

        # Check history file exists
        history_path = tmp_path / ".swarm" / "qa" / "coverage" / "coverage-history.json"
        assert history_path.exists()

    def test_handles_empty_endpoints(self, tmp_path):
        """Tracker handles empty endpoint lists gracefully."""
        tracker = CoverageTracker(tmp_path / ".swarm")

        baseline = tracker.capture_baseline(
            session_id="sess-001",
            endpoints_discovered=[],
            endpoints_tested=[]
        )

        assert baseline.endpoints_discovered == 0
        assert baseline.endpoints_tested == 0
        assert baseline.coverage_percentage == 0.0


class TestRegressionDetector:
    def test_detects_new_findings(self, tmp_path):
        """Detector finds new issues not in baseline."""
        detector = RegressionDetector(tmp_path / ".swarm")

        # Establish baseline with no issues
        detector.establish_baseline("sess-001", [])

        # Current session has issues
        current_findings = [
            {"endpoint": "/api/users", "category": "error", "test_type": "behavioral", "severity": "moderate"}
        ]
        report = detector.detect_regressions("sess-002", current_findings)

        assert report.regression_count == 1
        assert report.severity == "moderate"

    def test_detects_fixed_issues(self, tmp_path):
        """Detector finds issues that were fixed."""
        detector = RegressionDetector(tmp_path / ".swarm")

        # Baseline had issues
        baseline_findings = [
            {"endpoint": "/api/users", "category": "error", "test_type": "behavioral", "severity": "critical"}
        ]
        detector.establish_baseline("sess-001", baseline_findings)

        # Current has no issues
        report = detector.detect_regressions("sess-002", [])

        assert report.improvement_count == 1
        assert report.regression_count == 0
        assert report.severity == "none"

    def test_critical_regression_severity(self, tmp_path):
        """Critical findings result in critical severity."""
        detector = RegressionDetector(tmp_path / ".swarm")
        detector.establish_baseline("sess-001", [])

        current = [{"endpoint": "/api/auth", "category": "security", "test_type": "contract", "severity": "critical"}]
        report = detector.detect_regressions("sess-002", current)

        assert report.severity == "critical"

    def test_returns_none_without_baseline(self, tmp_path):
        """Detector returns None if no baseline exists."""
        detector = RegressionDetector(tmp_path / ".swarm")

        report = detector.detect_regressions("sess-001", [])
        assert report is None

    def test_finding_key_differentiates_issues(self, tmp_path):
        """Different findings have different keys."""
        detector = RegressionDetector(tmp_path / ".swarm")

        # Baseline has one type of issue
        baseline = [
            {"endpoint": "/api/users", "category": "error", "test_type": "behavioral", "severity": "moderate"}
        ]
        detector.establish_baseline("sess-001", baseline)

        # Current has different issue on same endpoint
        current = [
            {"endpoint": "/api/users", "category": "schema", "test_type": "contract", "severity": "moderate"}
        ]
        report = detector.detect_regressions("sess-002", current)

        # Should detect as new issue (different category/test_type)
        assert report.regression_count == 1
        assert report.improvement_count == 1  # Original was "fixed"


class TestQASessionExtension:
    def test_blocks_on_critical_regression(self, tmp_path):
        """Extension blocks session on critical regression."""
        ext = QASessionExtension(tmp_path / ".swarm")

        ext.on_session_start("sess-001", ["/api/users"])

        # First session establishes baseline
        ext.set_as_baseline("sess-001", ["/api/users"], [])

        # Second session with critical finding
        ext.on_session_start("sess-002", ["/api/users"])
        result = ext.on_session_complete(
            "sess-002",
            ["/api/users"],
            [{"endpoint": "/api/users", "severity": "critical", "category": "error", "test_type": "behavioral"}]
        )

        assert result.should_block is True
        assert "Critical regressions" in result.block_reason

    def test_blocks_on_coverage_drop(self, tmp_path):
        """Extension blocks on significant coverage drop."""
        ext = QASessionExtension(tmp_path / ".swarm")

        # Baseline with high coverage
        endpoints = [f"/api/endpoint{i}" for i in range(10)]
        ext.on_session_start("sess-001", endpoints)
        ext.set_as_baseline("sess-001", endpoints, [])  # 100% coverage

        # New session with low coverage
        ext.on_session_start("sess-002", endpoints)
        result = ext.on_session_complete("sess-002", endpoints[:2], [])  # 20% coverage

        assert result.should_block is True
        assert "Coverage dropped" in result.block_reason

    def test_does_not_block_on_improvement(self, tmp_path):
        """Extension does not block when things improve."""
        ext = QASessionExtension(tmp_path / ".swarm")

        # Baseline with low coverage and issues
        endpoints = [f"/api/endpoint{i}" for i in range(10)]
        ext.on_session_start("sess-001", endpoints)
        ext.set_as_baseline("sess-001", endpoints[:3], [
            {"endpoint": "/api/endpoint0", "severity": "moderate", "category": "error", "test_type": "behavioral"}
        ])

        # New session with better coverage and no issues
        ext.on_session_start("sess-002", endpoints)
        result = ext.on_session_complete("sess-002", endpoints, [])

        assert result.should_block is False
        assert result.block_reason is None

    def test_provides_coverage_report(self, tmp_path):
        """Extension provides coverage report in result."""
        ext = QASessionExtension(tmp_path / ".swarm")

        ext.on_session_start("sess-001", ["/api/a", "/api/b", "/api/c"])
        result = ext.on_session_complete("sess-001", ["/api/a", "/api/b"], [])

        assert result.coverage_report is not None
        assert result.coverage_report.endpoints_discovered == 3
        assert result.coverage_report.endpoints_tested == 2

    def test_provides_regression_report_when_baseline_exists(self, tmp_path):
        """Extension provides regression report when baseline exists."""
        ext = QASessionExtension(tmp_path / ".swarm")

        # Set up baseline
        ext.on_session_start("sess-001", ["/api/a"])
        ext.set_as_baseline("sess-001", ["/api/a"], [])

        # New session
        ext.on_session_start("sess-002", ["/api/a"])
        result = ext.on_session_complete("sess-002", ["/api/a"], [])

        assert result.regression_report is not None
        assert result.regression_report.baseline_session_id == "sess-001"
