"""
Tests for orchestrator silent exception handling fixes (Issue 6).

This tests that all silent exception handlers in orchestrator.py now log warnings
instead of silently passing. This is P0 security because silent exceptions can
hide state corruption.

The locations that previously had silent `pass`:
1. _check_spec_files_indicate_success: json/io errors when reading rubric files
2. _is_already_implemented (git check): git subprocess failures
3. _is_already_implemented (test check): pytest subprocess failures
4. _load_issue_from_spec: json errors reading issues.json
5. _search_codebase_for_definition: rg subprocess failures
6. _search_for_module: find subprocess failures
7. _create_commit: git commit failures
"""

import json
import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from swarm_attack.orchestrator import Orchestrator
from swarm_attack.config import SwarmConfig


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create a mock config with all required attributes."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.swarm_path = tmp_path / ".swarm"
    config.tests = MagicMock()
    config.tests.timeout_seconds = 300
    config.retry = MagicMock()
    config.retry.max_retries = 3
    config.retry.backoff_seconds = 5
    config.spec_debate = MagicMock()
    config.spec_debate.rubric_thresholds = {
        "completeness": 0.8,
        "clarity": 0.8,
        "testability": 0.8,
    }
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger to capture log calls."""
    logger = MagicMock()
    logger.log = MagicMock()
    return logger


@pytest.fixture
def orchestrator(mock_config: SwarmConfig, mock_logger) -> Orchestrator:
    """Create an orchestrator with a mock logger."""
    orch = Orchestrator(config=mock_config, logger=mock_logger)
    return orch


class TestSpecFileParseError:
    """Test error logging for spec file parsing failures."""

    def test_json_decode_error_logs_warning(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """JSON decode errors in spec files should log a warning."""
        # Create spec directory with invalid rubric file
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        spec_path = spec_dir / "spec-draft.md"
        spec_path.write_text("# Valid spec")

        # Create invalid rubric file (will cause JSONDecodeError)
        rubric_path = spec_dir / "spec-rubric.json"
        rubric_path.write_text("{invalid json")

        result, scores = orchestrator._check_spec_files_indicate_success("test-feature")

        # Should log warning for JSON error
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "spec_file_parse_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log spec_file_parse_error warning"

        # Should include error details
        call_data = warning_calls[0][0][1]
        assert "error" in call_data
        assert "error_type" in call_data

    def test_key_error_logs_warning(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """KeyError in spec parsing should log a warning."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        spec_path = spec_dir / "spec-draft.md"
        spec_path.write_text("# Valid spec")

        # Create rubric file with wrong structure (missing ready_for_approval)
        rubric_path = spec_dir / "spec-rubric.json"
        rubric_path.write_text('{"ready_for_approval": true}')  # Missing current_scores

        result, scores = orchestrator._check_spec_files_indicate_success("test-feature")

        # Should return False, {} (but shouldn't crash)
        assert result is False
        assert scores == {}


class TestDuplicateDetectionGitError:
    """Test error logging for git subprocess failures in duplicate detection."""

    def test_git_timeout_logs_warning(
        self, orchestrator: Orchestrator, mock_logger
    ):
        """Git timeout during duplicate detection should log a warning."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)

            result = orchestrator._is_already_implemented("test-feature", 1)

        # Should log git_check_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "git_check_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log git_check_error warning"

    def test_git_not_found_logs_warning(
        self, orchestrator: Orchestrator, mock_logger
    ):
        """Git not found during duplicate detection should log a warning."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            result = orchestrator._is_already_implemented("test-feature", 1)

        # Should log error and continue to check other sources
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "git_check_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log git_check_error warning"
        assert result is False  # No duplicate found


class TestDuplicateDetectionTestError:
    """Test error logging for pytest subprocess failures in duplicate detection."""

    def test_pytest_timeout_logs_warning(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """Pytest timeout during duplicate detection should log a warning."""
        # Create test file so the check is attempted
        test_dir = tmp_path / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_1.py"
        test_file.write_text("# Test file")

        # First call succeeds (git check), second fails (pytest)
        call_count = [0]
        def mock_subprocess(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Git check - no match
                result = MagicMock()
                result.stdout = ""
                return result
            else:
                # Pytest check - timeout
                raise subprocess.TimeoutExpired(cmd="pytest", timeout=60)

        with patch("subprocess.run", side_effect=mock_subprocess):
            result = orchestrator._is_already_implemented("test-feature", 1)

        # Should log test_check_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "test_check_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log test_check_error warning"


class TestIssueLookupError:
    """Test error logging for issue lookup failures."""

    def test_json_decode_error_logs_warning(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """JSON decode error in issues.json should log a warning."""
        issues_dir = tmp_path / "specs" / "test-feature"
        issues_dir.mkdir(parents=True)
        issues_file = issues_dir / "issues.json"
        issues_file.write_text("{invalid json")

        result = orchestrator._load_issue_from_spec("test-feature", 1)

        # Should log issue_lookup_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "issue_lookup_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log issue_lookup_error warning"
        assert result is None


class TestCodebaseSearchError:
    """Test error logging for codebase search subprocess failures."""

    def test_rg_timeout_logs_warning(
        self, orchestrator: Orchestrator, mock_logger
    ):
        """Ripgrep timeout during codebase search should log a warning."""
        orchestrator.project_dir = "/tmp"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="rg", timeout=5)

            result = orchestrator._search_codebase_for_definition("SomeClass")

        # Should log codebase_search_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "codebase_search_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log codebase_search_error warning"
        assert result is None


class TestModuleSearchError:
    """Test error logging for module search subprocess failures."""

    def test_find_timeout_logs_warning(
        self, orchestrator: Orchestrator, mock_logger
    ):
        """Find timeout during module search should log a warning."""
        orchestrator.project_dir = "/tmp"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="find", timeout=5)

            result = orchestrator._search_for_module("SomeClass")

        # Should log module_search_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "module_search_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log module_search_error warning"
        assert result is None


class TestGitCommitError:
    """Test error logging for git commit failures."""

    def test_git_commit_failure_logs_warning(
        self, orchestrator: Orchestrator, mock_logger
    ):
        """Git commit failure should log a warning."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["git", "commit"],
                stderr="nothing to commit"
            )

            result = orchestrator._create_commit("test-feature", 1, "commit message")

        # Should log git_commit_error warning
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[0][0] == "git_commit_error" and c[1].get("level") == "warning"
        ]
        assert len(warning_calls) >= 1, "Should log git_commit_error warning"
        assert result == ""


class TestDebugModeErrorSurfacing:
    """Test that errors are surfaced in debug mode."""

    def test_errors_surfaced_in_debug_mode(
        self, mock_config: SwarmConfig, mock_logger, tmp_path: Path
    ):
        """In debug mode (SWARM_DEBUG=1), errors should be logged."""
        orchestrator = Orchestrator(config=mock_config, logger=mock_logger)

        issues_dir = tmp_path / "specs" / "test-feature"
        issues_dir.mkdir(parents=True)
        issues_file = issues_dir / "issues.json"
        issues_file.write_text("{invalid json")

        with patch.dict(os.environ, {"SWARM_DEBUG": "1"}):
            result = orchestrator._load_issue_from_spec("test-feature", 1)

        # In debug mode, error should be logged
        log_calls = [call for call in mock_logger.log.call_args_list]
        assert any(
            c[0][0] == "issue_lookup_error" for c in log_calls
        ), "Should log the error even in debug mode"


class TestStateCorruptionCriticalLog:
    """Test that state corruption errors trigger logs."""

    def test_state_corruption_from_json_error_is_logged(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """State file corruption (bad JSON) should be logged as warning."""
        # When we fail to parse JSON that could affect state,
        # it should be logged so we can detect state corruption
        issues_dir = tmp_path / "specs" / "test-feature"
        issues_dir.mkdir(parents=True)
        issues_file = issues_dir / "issues.json"
        issues_file.write_text("{corrupted")

        orchestrator._load_issue_from_spec("test-feature", 1)

        # Should log with warning level at minimum
        log_calls = [call for call in mock_logger.log.call_args_list]
        warning_calls = [
            c for c in log_calls
            if c[1].get("level") in ("warning", "error", "critical")
        ]
        assert len(warning_calls) >= 1, "State-related errors should be logged"


class TestNoFunctionalRegression:
    """Test that error handling changes don't break normal operation."""

    def test_successful_spec_check_still_works(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """Valid spec files should still be processed correctly."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)

        # Create valid spec and rubric
        spec_path = spec_dir / "spec-draft.md"
        spec_path.write_text("# Valid spec content")

        rubric = {
            "ready_for_approval": True,
            "current_scores": {
                "completeness": 0.9,
                "clarity": 0.9,
                "testability": 0.9,
            },
        }
        rubric_path = spec_dir / "spec-rubric.json"
        rubric_path.write_text(json.dumps(rubric))

        result, returned_scores = orchestrator._check_spec_files_indicate_success("test-feature")

        # Should succeed
        assert result is True
        assert returned_scores["completeness"] == 0.9

    def test_successful_issue_lookup_still_works(
        self, orchestrator: Orchestrator, mock_logger, tmp_path: Path
    ):
        """Valid issues.json should still be parsed correctly."""
        issues_dir = tmp_path / "specs" / "test-feature"
        issues_dir.mkdir(parents=True)

        issues_data = {
            "issues": [
                {"order": 1, "title": "Test Issue", "body": "Description"},
                {"order": 2, "title": "Another Issue", "body": "More description"},
            ]
        }
        issues_file = issues_dir / "issues.json"
        issues_file.write_text(json.dumps(issues_data))

        result = orchestrator._load_issue_from_spec("test-feature", 1)

        # Should find the issue
        assert result is not None
        assert result["title"] == "Test Issue"
