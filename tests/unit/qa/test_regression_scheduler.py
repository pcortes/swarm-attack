"""Unit tests for RegressionScheduler (TDD)."""
import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

try:
    from swarm_attack.qa.regression_scheduler import (
        RegressionScheduler,
        RegressionSchedulerConfig,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="RegressionScheduler not yet implemented"
)


class TestRegressionSchedulerConfig:
    """Test config defaults."""

    def test_default_issues(self):
        config = RegressionSchedulerConfig()
        assert config.issues_between_regressions == 10

    def test_default_commits(self):
        config = RegressionSchedulerConfig()
        assert config.commits_between_regressions == 25

    def test_default_time(self):
        config = RegressionSchedulerConfig()
        assert config.time_between_regressions_hours == 24

    def test_default_state_file(self):
        config = RegressionSchedulerConfig()
        assert config.state_file == ".swarm/regression_state.json"

    def test_custom_config(self):
        config = RegressionSchedulerConfig(
            issues_between_regressions=5,
            commits_between_regressions=10,
        )
        assert config.issues_between_regressions == 5
        assert config.commits_between_regressions == 10


class TestRegressionSchedulerInit:
    """Test scheduler initialization."""

    def test_creates_fresh_state(self, tmp_path):
        config = RegressionSchedulerConfig()
        scheduler = RegressionScheduler(config, tmp_path)
        assert scheduler.state["issues_since_last_regression"] == 0
        assert scheduler.state["commits_since_last_regression"] == 0

    def test_loads_existing_state(self, tmp_path):
        state_file = tmp_path / ".swarm" / "regression_state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text(json.dumps({
            "issues_since_last_regression": 5,
            "commits_since_last_regression": 10,
            "last_regression_timestamp": None,
            "last_regression_result": None,
        }))

        config = RegressionSchedulerConfig()
        scheduler = RegressionScheduler(config, tmp_path)
        assert scheduler.state["issues_since_last_regression"] == 5


class TestRecordIssueCommitted:
    """Test issue recording."""

    def test_increments_counter(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.record_issue_committed("issue-1")
        assert scheduler.state["issues_since_last_regression"] == 1

    def test_returns_true_at_threshold(self, tmp_path):
        config = RegressionSchedulerConfig(issues_between_regressions=2)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.record_issue_committed("issue-1")
        result = scheduler.record_issue_committed("issue-2")
        assert result is True

    def test_persists_state(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.record_issue_committed("issue-1")

        state_file = tmp_path / ".swarm" / "regression_state.json"
        assert state_file.exists()


class TestRecordCommit:
    """Test commit recording."""

    def test_increments_counter(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.record_commit("abc123")
        assert scheduler.state["commits_since_last_regression"] == 1

    def test_returns_true_at_threshold(self, tmp_path):
        config = RegressionSchedulerConfig(commits_between_regressions=2)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.record_commit("abc")
        result = scheduler.record_commit("def")
        assert result is True


class TestShouldRunRegression:
    """Test regression trigger logic."""

    def test_triggers_on_issue_threshold(self, tmp_path):
        config = RegressionSchedulerConfig(issues_between_regressions=2)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.state["issues_since_last_regression"] = 2
        assert scheduler.should_run_regression() is True

    def test_triggers_on_commit_threshold(self, tmp_path):
        config = RegressionSchedulerConfig(commits_between_regressions=2)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.state["commits_since_last_regression"] = 2
        assert scheduler.should_run_regression() is True

    def test_triggers_on_time_threshold(self, tmp_path):
        config = RegressionSchedulerConfig(time_between_regressions_hours=1)
        scheduler = RegressionScheduler(config, tmp_path)
        past = (datetime.now() - timedelta(hours=2)).isoformat()
        scheduler.state["last_regression_timestamp"] = past
        assert scheduler.should_run_regression() is True

    def test_no_trigger_below_thresholds(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        assert scheduler.should_run_regression() is False


class TestRecordRegressionCompleted:
    """Test regression completion."""

    def test_resets_counters(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.state["issues_since_last_regression"] = 10
        scheduler.state["commits_since_last_regression"] = 25

        scheduler.record_regression_completed({"verdict": "PASS"})

        assert scheduler.state["issues_since_last_regression"] == 0
        assert scheduler.state["commits_since_last_regression"] == 0

    def test_records_timestamp(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.record_regression_completed({"verdict": "PASS"})
        assert scheduler.state["last_regression_timestamp"] is not None

    def test_records_result(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.record_regression_completed({"verdict": "FAIL"})
        assert scheduler.state["last_regression_result"] == "FAIL"


class TestGetStatus:
    """Test status reporting."""

    def test_returns_issues_until(self, tmp_path):
        config = RegressionSchedulerConfig(issues_between_regressions=10)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.state["issues_since_last_regression"] = 3

        status = scheduler.get_status()
        assert status["issues_until_regression"] == 7

    def test_returns_commits_until(self, tmp_path):
        config = RegressionSchedulerConfig(commits_between_regressions=25)
        scheduler = RegressionScheduler(config, tmp_path)
        scheduler.state["commits_since_last_regression"] = 10

        status = scheduler.get_status()
        assert status["commits_until_regression"] == 15

    def test_returns_last_regression_info(self, tmp_path):
        scheduler = RegressionScheduler(RegressionSchedulerConfig(), tmp_path)
        scheduler.state["last_regression_timestamp"] = "2025-01-01T00:00:00"
        scheduler.state["last_regression_result"] = "PASS"

        status = scheduler.get_status()
        assert status["last_regression"] == "2025-01-01T00:00:00"
        assert status["last_result"] == "PASS"
