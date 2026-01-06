"""Tests for SemanticQAMetrics - Track semantic testing performance metrics."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from swarm_attack.qa.metrics import SemanticQAMetrics, SemanticTestMetric


class TestSemanticTestMetric:
    """Test SemanticTestMetric dataclass."""

    def test_creates_metric_with_required_fields(self):
        """Test creating a metric with required fields."""
        metric = SemanticTestMetric(
            timestamp="2026-01-05T10:00:00",
            verdict="PASS",
            execution_time_ms=150.5,
            depth="semantic",
        )
        assert metric.timestamp == "2026-01-05T10:00:00"
        assert metric.verdict == "PASS"
        assert metric.execution_time_ms == 150.5
        assert metric.depth == "semantic"
        assert metric.was_true_positive is None
        assert metric.was_false_positive is None
        assert metric.scope == "changes_only"

    def test_creates_metric_with_all_fields(self):
        """Test creating a metric with all fields."""
        metric = SemanticTestMetric(
            timestamp="2026-01-05T10:00:00",
            verdict="FAIL",
            execution_time_ms=200.0,
            depth="integration",
            was_true_positive=True,
            was_false_positive=False,
            scope="full",
        )
        assert metric.was_true_positive is True
        assert metric.was_false_positive is False
        assert metric.scope == "full"


class TestSemanticQAMetricsRecording:
    """Test recording metrics."""

    def test_record_test_creates_metric(self, tmp_path):
        """Test that record_test creates and saves a metric."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(
            verdict="PASS",
            execution_time_ms=100.0,
            depth="unit",
        )

        assert len(metrics.metrics) == 1
        assert metrics.metrics[0].verdict == "PASS"
        assert metrics.metrics[0].execution_time_ms == 100.0
        assert metrics.metrics[0].depth == "unit"

        # Verify persisted to disk
        assert metrics_file.exists()
        data = json.loads(metrics_file.read_text())
        assert len(data["metrics"]) == 1

    def test_record_bug_caught_true_positive(self, tmp_path):
        """Test recording a bug caught (true positive)."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        # Record a FAIL verdict
        metrics.record_test(verdict="FAIL", execution_time_ms=200.0)
        timestamp = metrics.metrics[0].timestamp

        # Mark it as a true positive (real bug found)
        metrics.record_true_positive(timestamp)

        assert metrics.metrics[0].was_true_positive is True
        assert metrics.metrics[0].was_false_positive is False

    def test_record_false_positive(self, tmp_path):
        """Test recording a false positive (FAIL but code was correct)."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        # Record a FAIL verdict
        metrics.record_test(verdict="FAIL", execution_time_ms=150.0)
        timestamp = metrics.metrics[0].timestamp

        # Mark it as a false positive (code was actually correct)
        metrics.record_false_positive(timestamp)

        assert metrics.metrics[0].was_true_positive is False
        assert metrics.metrics[0].was_false_positive is True

    def test_record_multiple_tests(self, tmp_path):
        """Test recording multiple test runs."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="unit")
        metrics.record_test(verdict="FAIL", execution_time_ms=200.0, depth="integration")
        metrics.record_test(verdict="PARTIAL", execution_time_ms=150.0, depth="semantic")

        assert len(metrics.metrics) == 3

        # Verify all persisted
        data = json.loads(metrics_file.read_text())
        assert len(data["metrics"]) == 3


class TestSemanticQAMetricsExecutionTime:
    """Test execution time tracking."""

    def test_records_execution_time(self, tmp_path):
        """Test that execution time is recorded correctly."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(verdict="PASS", execution_time_ms=123.456)

        assert metrics.metrics[0].execution_time_ms == 123.456

    def test_average_execution_time_in_summary(self, tmp_path):
        """Test that get_summary calculates average execution time."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(verdict="PASS", execution_time_ms=100.0)
        metrics.record_test(verdict="PASS", execution_time_ms=200.0)
        metrics.record_test(verdict="PASS", execution_time_ms=300.0)

        summary = metrics.get_summary()

        assert summary["avg_execution_time_ms"] == 200.0


class TestSemanticQAMetricsSummary:
    """Test get_summary() aggregations."""

    def test_empty_metrics_returns_zeros(self, tmp_path):
        """Test that empty metrics returns zero values."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        summary = metrics.get_summary()

        assert summary["total_tests"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["fail_rate"] == 0.0
        assert summary["partial_rate"] == 0.0
        assert summary["avg_execution_time_ms"] == 0.0
        assert summary["true_positive_rate"] == 0.0
        assert summary["false_positive_rate"] == 0.0
        assert summary["coverage_by_depth"] == {}

    def test_summary_calculates_pass_rate(self, tmp_path):
        """Test that summary calculates pass rate correctly."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        # 3 PASS, 1 FAIL, 1 PARTIAL = 60% pass rate
        metrics.record_test(verdict="PASS", execution_time_ms=100.0)
        metrics.record_test(verdict="PASS", execution_time_ms=100.0)
        metrics.record_test(verdict="PASS", execution_time_ms=100.0)
        metrics.record_test(verdict="FAIL", execution_time_ms=100.0)
        metrics.record_test(verdict="PARTIAL", execution_time_ms=100.0)

        summary = metrics.get_summary()

        assert summary["total_tests"] == 5
        assert summary["pass_rate"] == 0.6
        assert summary["fail_rate"] == 0.2
        assert summary["partial_rate"] == 0.2

    def test_summary_calculates_true_positive_rate(self, tmp_path):
        """Test that summary calculates true positive rate correctly."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        # 2 FAIL verdicts, 1 true positive, 1 false positive
        metrics.record_test(verdict="FAIL", execution_time_ms=100.0)
        ts1 = metrics.metrics[0].timestamp
        metrics.record_test(verdict="FAIL", execution_time_ms=100.0)
        ts2 = metrics.metrics[1].timestamp

        metrics.record_true_positive(ts1)
        metrics.record_false_positive(ts2)

        summary = metrics.get_summary()

        assert summary["true_positive_rate"] == 0.5
        assert summary["false_positive_rate"] == 0.5

    def test_summary_calculates_coverage_by_depth(self, tmp_path):
        """Test that summary calculates coverage by depth."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="unit")
        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="unit")
        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="integration")
        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="semantic")
        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="semantic")
        metrics.record_test(verdict="PASS", execution_time_ms=100.0, depth="semantic")

        summary = metrics.get_summary()

        assert summary["coverage_by_depth"] == {
            "unit": 2,
            "integration": 1,
            "semantic": 3,
        }


class TestSemanticQAMetricsPersistence:
    """Test persistence to disk."""

    def test_creates_directories_if_missing(self, tmp_path):
        """Test that parent directories are created if missing."""
        metrics_file = tmp_path / "deep/nested/path/metrics.json"
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        metrics.record_test(verdict="PASS", execution_time_ms=100.0)

        assert metrics_file.exists()

    def test_loads_existing_metrics(self, tmp_path):
        """Test that existing metrics are loaded from disk."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics_file.parent.mkdir(parents=True)

        # Pre-populate with existing data
        existing_data = {
            "metrics": [
                {
                    "timestamp": "2026-01-04T10:00:00",
                    "verdict": "PASS",
                    "execution_time_ms": 50.0,
                    "depth": "unit",
                    "was_true_positive": None,
                    "was_false_positive": None,
                    "scope": "changes_only",
                }
            ]
        }
        metrics_file.write_text(json.dumps(existing_data))

        # Load metrics
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        assert len(metrics.metrics) == 1
        assert metrics.metrics[0].verdict == "PASS"
        assert metrics.metrics[0].execution_time_ms == 50.0

    def test_handles_corrupted_metrics_file(self, tmp_path):
        """Test that corrupted metrics file is handled gracefully."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics_file.parent.mkdir(parents=True)

        # Write corrupted JSON
        metrics_file.write_text("not valid json {{{")

        # Should not raise, starts with empty metrics
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        assert len(metrics.metrics) == 0

    def test_handles_missing_keys_in_metrics_file(self, tmp_path):
        """Test that missing keys in metrics file is handled."""
        metrics_file = tmp_path / ".swarm/qa/metrics.json"
        metrics_file.parent.mkdir(parents=True)

        # Write JSON missing 'metrics' key
        metrics_file.write_text(json.dumps({"other_key": "value"}))

        # Should not raise, starts with empty metrics
        metrics = SemanticQAMetrics(metrics_file=metrics_file)

        assert len(metrics.metrics) == 0


class TestSemanticQAMetricsDefaultPath:
    """Test default metrics file path."""

    def test_default_metrics_path(self):
        """Test that default path is .swarm/qa/metrics.json."""
        # Use patch to avoid actual file creation
        with patch.object(SemanticQAMetrics, '_load'):
            metrics = SemanticQAMetrics()
            assert metrics.metrics_file == Path(".swarm/qa/metrics.json")
