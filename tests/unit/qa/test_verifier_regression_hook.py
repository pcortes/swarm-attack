"""Tests for VerifierAgent regression scheduler hook.

Tests the integration between VerifierAgent and RegressionScheduler:
- record_issue_committed() is called after successful verification
- When should_run_regression() returns True, regression is triggered
- When should_run_regression() returns False, no regression is triggered
- Graceful degradation when regression scheduler fails
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.agents.verifier import VerifierAgent


@pytest.fixture
def temp_repo():
    """Create a temporary repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_repo):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = temp_repo
    config.tests = MagicMock()
    config.tests.timeout_seconds = 60
    return config


@pytest.fixture
def verifier(mock_config):
    """Create a VerifierAgent instance."""
    return VerifierAgent(mock_config)


class TestRegressionSchedulerHookIntegration:
    """Tests for RegressionScheduler integration in VerifierAgent."""

    def test_record_issue_committed_called_on_success(self, verifier, temp_repo):
        """RegressionScheduler.record_issue_committed() should be called after successful verification."""
        # Create a passing test file
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_1.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "check_regressions": False,  # Disable inline regression check
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler.record_issue_committed.return_value = False
                mock_scheduler_class.return_value = mock_scheduler

                result = verifier.run(context)

        assert result.success is True
        mock_scheduler.record_issue_committed.assert_called_once_with("test-feature_1")

    def test_regression_triggered_when_should_run_returns_true(
        self, verifier, temp_repo
    ):
        """When record_issue_committed returns True, regression_triggered should be logged."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_5.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 5,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                # Simulate threshold reached - regression needed
                mock_scheduler.record_issue_committed.return_value = True
                mock_scheduler_class.return_value = mock_scheduler

                with patch.object(verifier, "_log") as mock_log:
                    result = verifier.run(context)

        assert result.success is True
        # Verify regression_triggered was logged
        log_calls = [call[0] for call in mock_log.call_args_list]
        assert any("regression_triggered" in str(call) for call in log_calls)

    def test_no_regression_triggered_when_should_run_returns_false(
        self, verifier, temp_repo
    ):
        """When record_issue_committed returns False, no regression_triggered log."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_3.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 3,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                # Threshold not reached - no regression needed
                mock_scheduler.record_issue_committed.return_value = False
                mock_scheduler_class.return_value = mock_scheduler

                with patch.object(verifier, "_log") as mock_log:
                    result = verifier.run(context)

        assert result.success is True
        # Verify regression_triggered was NOT logged
        log_calls = [call[0] for call in mock_log.call_args_list]
        assert not any("regression_triggered" in str(call) for call in log_calls)

    def test_regression_hook_does_not_run_on_failure(self, verifier, temp_repo):
        """RegressionScheduler should NOT be called when verification fails."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_2.py"
        test_file.write_text("def test_fails(): assert False")

        context = {
            "feature_id": "test-feature",
            "issue_number": 2,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            # Simulate test failure
            mock_pytest.return_value = (1, "1 failed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler

                result = verifier.run(context)

        assert result.success is False
        # RegressionScheduler should not have been called
        mock_scheduler_class.assert_not_called()

    def test_regression_hook_does_not_block_verification(self, verifier, temp_repo):
        """Regression scheduler failures should not block verification success."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_4.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 4,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                # Simulate scheduler throwing an exception
                mock_scheduler_class.side_effect = Exception("Scheduler init failed")

                result = verifier.run(context)

        # Verification should still succeed despite scheduler failure
        assert result.success is True

    def test_scheduler_config_defaults_used(self, verifier, temp_repo):
        """RegressionSchedulerConfig should be created with defaults."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_6.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 6,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionSchedulerConfig"
            ) as mock_config_class:
                mock_config = MagicMock()
                mock_config_class.return_value = mock_config

                with patch(
                    "swarm_attack.agents.verifier.RegressionScheduler"
                ) as mock_scheduler_class:
                    mock_scheduler = MagicMock()
                    mock_scheduler.record_issue_committed.return_value = False
                    mock_scheduler_class.return_value = mock_scheduler

                    result = verifier.run(context)

        assert result.success is True
        mock_config_class.assert_called_once()  # Config created with defaults


class TestRegressionSchedulerHookIssueIdFormat:
    """Tests for the issue_id format passed to RegressionScheduler."""

    def test_issue_id_format_is_feature_underscore_issue(self, verifier, temp_repo):
        """Issue ID should be formatted as {feature_id}_{issue_number}."""
        test_dir = temp_repo / "tests" / "generated" / "my-cool-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_42.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "my-cool-feature",
            "issue_number": 42,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler.record_issue_committed.return_value = False
                mock_scheduler_class.return_value = mock_scheduler

                verifier.run(context)

        mock_scheduler.record_issue_committed.assert_called_once_with(
            "my-cool-feature_42"
        )

    def test_issue_id_handles_special_characters_in_feature_id(
        self, verifier, temp_repo
    ):
        """Issue ID format should work with special characters in feature_id."""
        test_dir = temp_repo / "tests" / "generated" / "feature-with-dashes"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_99.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "feature-with-dashes",
            "issue_number": 99,
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")

            with patch(
                "swarm_attack.agents.verifier.RegressionScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler.record_issue_committed.return_value = False
                mock_scheduler_class.return_value = mock_scheduler

                verifier.run(context)

        mock_scheduler.record_issue_committed.assert_called_once_with(
            "feature-with-dashes_99"
        )
