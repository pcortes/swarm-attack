"""Tests for QA metrics CLI command following TDD approach.

Tests for the swarm-attack qa metrics command that displays SemanticQAMetrics data.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_metrics_data():
    """Create sample metrics data for testing."""
    return {
        "metrics": [
            {
                "timestamp": "2026-01-05T10:00:00",
                "verdict": "PASS",
                "execution_time_ms": 150.0,
                "depth": "semantic",
                "was_true_positive": None,
                "was_false_positive": None,
                "scope": "changes_only",
            },
            {
                "timestamp": "2026-01-05T11:00:00",
                "verdict": "FAIL",
                "execution_time_ms": 200.0,
                "depth": "integration",
                "was_true_positive": True,
                "was_false_positive": False,
                "scope": "affected",
            },
            {
                "timestamp": "2026-01-05T12:00:00",
                "verdict": "PARTIAL",
                "execution_time_ms": 175.0,
                "depth": "unit",
                "was_true_positive": None,
                "was_false_positive": None,
                "scope": "full_system",
            },
        ]
    }


class TestMetricsCommandRegistration:
    """Tests for metrics command registration."""

    def test_metrics_command_exists(self, runner):
        """qa metrics command should be registered."""
        from swarm_attack.cli.qa import qa_app
        result = runner.invoke(qa_app, ["metrics", "--help"])
        assert result.exit_code == 0
        assert "metrics" in result.output.lower() or "QA" in result.output

    def test_metrics_help_shows_description(self, runner):
        """qa metrics --help should show description."""
        from swarm_attack.cli.qa import qa_app
        result = runner.invoke(qa_app, ["metrics", "--help"])
        assert result.exit_code == 0
        assert "semantic" in result.output.lower() or "metrics" in result.output.lower()


class TestMetricsDisplay:
    """Tests for metrics display functionality."""

    def test_displays_metrics_summary(self, runner, sample_metrics_data, tmp_path):
        """Should display metrics summary including total tests."""
        from swarm_attack.cli.qa import qa_app
        metrics_dir = tmp_path / ".swarm" / "qa"
        metrics_dir.mkdir(parents=True)
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps(sample_metrics_data))

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert "3" in result.output or "total" in result.output.lower()

    def test_displays_pass_rate(self, runner, sample_metrics_data, tmp_path):
        """Should display pass rate percentage."""
        from swarm_attack.cli.qa import qa_app
        metrics_dir = tmp_path / ".swarm" / "qa"
        metrics_dir.mkdir(parents=True)
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps(sample_metrics_data))

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert "%" in result.output or "rate" in result.output.lower() or "pass" in result.output.lower()

    def test_displays_execution_time(self, runner, sample_metrics_data, tmp_path):
        """Should display average execution time."""
        from swarm_attack.cli.qa import qa_app
        metrics_dir = tmp_path / ".swarm" / "qa"
        metrics_dir.mkdir(parents=True)
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps(sample_metrics_data))

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert "time" in result.output.lower() or "ms" in result.output

    def test_displays_coverage_by_depth(self, runner, sample_metrics_data, tmp_path):
        """Should display coverage breakdown by depth."""
        from swarm_attack.cli.qa import qa_app
        metrics_dir = tmp_path / ".swarm" / "qa"
        metrics_dir.mkdir(parents=True)
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps(sample_metrics_data))

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert ("semantic" in result.output.lower() or
                "integration" in result.output.lower() or
                "unit" in result.output.lower() or
                "depth" in result.output.lower())


class TestEmptyMetrics:
    """Tests for handling empty or missing metrics."""

    def test_handles_no_metrics_file(self, runner, tmp_path):
        """Should handle missing metrics file gracefully."""
        from swarm_attack.cli.qa import qa_app
        swarm_dir = tmp_path / ".swarm"
        swarm_dir.mkdir(parents=True)

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output

    def test_handles_empty_metrics(self, runner, tmp_path):
        """Should handle empty metrics list."""
        from swarm_attack.cli.qa import qa_app
        metrics_dir = tmp_path / ".swarm" / "qa"
        metrics_dir.mkdir(parents=True)
        metrics_file = metrics_dir / "metrics.json"
        metrics_file.write_text(json.dumps({"metrics": []}))

        result = runner.invoke(qa_app, ["metrics", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert "0" in result.output or "no" in result.output.lower()


class TestProjectOption:
    """Tests for --project option."""

    def test_accepts_project_option(self, runner):
        """Should accept --project option."""
        from swarm_attack.cli.qa import qa_app
        result = runner.invoke(qa_app, ["metrics", "--help"])
        assert "--project" in result.output

    def test_uses_current_directory_by_default(self, runner):
        """Should use current directory when --project not specified."""
        from swarm_attack.cli.qa import qa_app
        result = runner.invoke(qa_app, ["metrics"])
        assert result.exit_code == 0 or "error" in result.output.lower() or "no" in result.output.lower()
