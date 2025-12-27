"""Coverage Validation Tests.

Verifies test coverage meets minimum thresholds.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


def _get_env_with_pythonpath():
    """Get environment dict with PYTHONPATH set."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    return env


class TestCoverageThresholds:
    """Tests for coverage thresholds."""

    @pytest.fixture
    def coverage_data(self, tmp_path):
        """Run coverage and return data."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/", "tests/integration/qa/",
                "--cov=swarm_attack.qa",
                "--cov-report=json",
                f"--cov-report=json:{tmp_path}/coverage.json",
                "--cov-fail-under=0",  # Don't fail on coverage threshold in nested run
                "-q",
                "--ignore=tests/integration/qa/test_coverage.py",  # Avoid recursive coverage tests
            ],
            capture_output=True,
            text=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
            timeout=300,  # 5 minute timeout
        )

        coverage_file = tmp_path / "coverage.json"
        if coverage_file.exists():
            return json.loads(coverage_file.read_text())
        return None

    def test_overall_coverage_above_threshold(self, coverage_data):
        """Overall coverage should be above 80%."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        total = coverage_data.get("totals", {})
        percent = total.get("percent_covered", 0)

        assert percent >= 80, f"Coverage {percent}% below 80% threshold"

    def test_orchestrator_coverage(self, coverage_data):
        """Orchestrator should have high coverage."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        files = coverage_data.get("files", {})
        orch_key = [k for k in files.keys() if "orchestrator.py" in k]

        if orch_key:
            percent = files[orch_key[0]].get("summary", {}).get("percent_covered", 0)
            assert percent >= 85, f"Orchestrator coverage {percent}% below 85%"

    def test_models_coverage(self, coverage_data):
        """Models should have high coverage."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        files = coverage_data.get("files", {})
        models_key = [k for k in files.keys() if "models.py" in k]

        if models_key:
            percent = files[models_key[0]].get("summary", {}).get("percent_covered", 0)
            assert percent >= 90, f"Models coverage {percent}% below 90%"


class TestCoverageReportGeneration:
    """Tests for coverage report generation."""

    def test_html_report_generates(self, tmp_path):
        """HTML coverage report should generate."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/test_models.py",
                "--cov=swarm_attack.qa.models",
                f"--cov-report=html:{tmp_path}/htmlcov",
                "--cov-fail-under=0",  # Don't fail on coverage threshold
                "-q"
            ],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )

        assert (tmp_path / "htmlcov" / "index.html").exists(), f"HTML report not generated. stderr: {result.stderr}"

    def test_xml_report_generates(self, tmp_path):
        """XML coverage report should generate (for CI)."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/test_models.py",
                "--cov=swarm_attack.qa.models",
                f"--cov-report=xml:{tmp_path}/coverage.xml",
                "--cov-fail-under=0",  # Don't fail on coverage threshold
                "-q"
            ],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )

        assert (tmp_path / "coverage.xml").exists(), f"XML report not generated. stderr: {result.stderr}"

    def test_json_report_generates(self, tmp_path):
        """JSON coverage report should generate."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/test_models.py",
                "--cov=swarm_attack.qa.models",
                f"--cov-report=json:{tmp_path}/coverage.json",
                "--cov-fail-under=0",  # Don't fail on coverage threshold
                "-q"
            ],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )

        assert (tmp_path / "coverage.json").exists(), f"JSON report not generated. stderr: {result.stderr}"

        # Verify JSON is valid
        coverage_data = json.loads((tmp_path / "coverage.json").read_text())
        assert "totals" in coverage_data
        assert "files" in coverage_data


class TestCoverageConfiguration:
    """Tests for coverage configuration."""

    def test_pyproject_has_coverage_config(self):
        """pyproject.toml should have coverage configuration."""
        pyproject_path = Path("/Users/philipjcortes/Desktop/swarm-attack-qa-agent/pyproject.toml")
        content = pyproject_path.read_text()

        assert "[tool.coverage.run]" in content, "Missing [tool.coverage.run] section"
        assert "[tool.coverage.report]" in content, "Missing [tool.coverage.report] section"

    def test_coverage_source_configured(self):
        """Coverage should be configured to measure swarm_attack/qa."""
        pyproject_path = Path("/Users/philipjcortes/Desktop/swarm-attack-qa-agent/pyproject.toml")
        content = pyproject_path.read_text()

        assert "swarm_attack/qa" in content or 'swarm_attack.qa' in content, \
            "Coverage source not configured for swarm_attack/qa"
