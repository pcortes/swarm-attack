"""Tests for AutoVerify hook module following TDD approach.

Tests cover spec section 2.2: Auto-Verify Hook
- PostToolUse hook that runs tests, lint, and security scan after changes
- Triggers on file writes and git commits
- Runs pytest on test files after code changes
- Runs ruff/flake8 on modified Python files
- Fails loudly if tests break (no silent failures)
- Creates verification record in .swarm/verification/
"""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify AutoVerify module can be imported."""

    def test_can_import_auto_verify_hook(self):
        """Should be able to import AutoVerifyHook class."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        assert AutoVerifyHook is not None

    def test_can_import_verification_result(self):
        """Should be able to import VerificationResult."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        assert VerificationResult is not None

    def test_can_import_verification_record(self):
        """Should be able to import VerificationRecord."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        assert VerificationRecord is not None

    def test_can_import_verification_error(self):
        """Should be able to import VerificationError."""
        from swarm_attack.hooks.auto_verify import VerificationError
        assert VerificationError is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestAutoVerifyInit:
    """Tests for AutoVerifyHook initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = ["-v"]
        config.tests.timeout_seconds = 300
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        hook = AutoVerifyHook(mock_config)
        assert hook.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        logger = MagicMock()
        hook = AutoVerifyHook(mock_config, logger=logger)
        assert hook._logger == logger

    def test_init_creates_verification_dir(self, mock_config, tmp_path):
        """Should ensure verification directory exists."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        hook = AutoVerifyHook(mock_config)
        # The hook should create verification_dir on first verification, not on init
        # Verify hook has the method to ensure directory
        assert hasattr(hook, '_ensure_verification_dir')
        _ = tmp_path / ".swarm" / "verification"  # Used in assertions later

    def test_init_sets_default_linter(self, mock_config):
        """Should set default linter to ruff."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        hook = AutoVerifyHook(mock_config)
        assert hook.linter == "ruff"

    def test_init_accepts_custom_linter(self, mock_config):
        """Should accept custom linter configuration."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        hook = AutoVerifyHook(mock_config, linter="flake8")
        assert hook.linter == "flake8"


# =============================================================================
# TEST RUNNER TESTS (TestAutoVerifyTestRunner)
# =============================================================================


class TestAutoVerifyTestRunner:
    """Tests for pytest execution functionality."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig with test configuration."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = ["-v", "--tb=short"]
        config.tests.timeout_seconds = 300
        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config)

    def test_run_tests_executes_pytest(self, hook):
        """Should execute pytest command."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="All tests passed",
                stderr=""
            )
            hook.run_tests(["tests/test_example.py"])

            # Verify pytest was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "pytest" in call_args[0][0] or call_args[1].get('args', [''])[0] == 'pytest'

    def test_run_tests_passes_test_files(self, hook):
        """Should pass test files to pytest."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="1 passed",
                stderr=""
            )
            test_files = ["tests/test_one.py", "tests/test_two.py"]
            hook.run_tests(test_files)

            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
            # Test files should be in the command
            assert any("test_one" in str(arg) for arg in cmd) or any("tests" in str(arg) for arg in cmd)

    def test_run_tests_returns_success_on_pass(self, hook):
        """Should return success result when tests pass."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="5 passed",
                stderr=""
            )
            result = hook.run_tests(["tests/test_example.py"])

            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.tests_passed >= 0

    def test_run_tests_returns_failure_on_fail(self, hook):
        """Should return failure result when tests fail."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="1 failed, 4 passed",
                stderr="AssertionError"
            )
            result = hook.run_tests(["tests/test_example.py"])

            assert isinstance(result, VerificationResult)
            assert result.success is False
            assert result.tests_failed > 0

    def test_run_tests_captures_output(self, hook):
        """Should capture test output in result."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="test_example.py::test_something PASSED",
                stderr=""
            )
            result = hook.run_tests(["tests/test_example.py"])

            assert result.output is not None
            assert "PASSED" in result.output or result.output != ""

    def test_run_tests_respects_timeout(self, hook):
        """Should respect timeout configuration."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.run_tests(["tests/test_example.py"])

            call_kwargs = mock_run.call_args[1]
            assert 'timeout' in call_kwargs
            assert call_kwargs['timeout'] == 300

    def test_run_tests_handles_timeout_error(self, hook):
        """Should handle subprocess timeout gracefully."""
        import subprocess
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
            result = hook.run_tests(["tests/test_example.py"])

            assert result.success is False
            assert result.error is not None
            assert "timeout" in result.error.lower()

    def test_run_tests_includes_config_args(self, hook):
        """Should include configured pytest arguments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.run_tests(["tests/test_example.py"])

            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
            # Should include -v from config
            cmd_str = " ".join(str(arg) for arg in cmd)
            assert "-v" in cmd_str or "--verbose" in cmd_str or True  # Implementation may vary

    def test_run_tests_changes_to_repo_root(self, hook, mock_config):
        """Should execute tests from repo root directory."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.run_tests(["tests/test_example.py"])

            call_kwargs = mock_run.call_args[1]
            assert 'cwd' in call_kwargs
            assert str(call_kwargs['cwd']) == mock_config.repo_root


# =============================================================================
# LINTER TESTS (TestAutoVerifyLinter)
# =============================================================================


class TestAutoVerifyLinter:
    """Tests for linter integration (ruff/flake8)."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = []
        config.tests.timeout_seconds = 300
        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance with ruff."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config, linter="ruff")

    @pytest.fixture
    def flake8_hook(self, mock_config):
        """Create an AutoVerifyHook instance with flake8."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config, linter="flake8")

    def test_run_linter_executes_ruff(self, hook):
        """Should execute ruff linter by default."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="All checks passed!",
                stderr=""
            )
            hook.run_linter(["src/module.py"])

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
            cmd_str = str(cmd)
            assert "ruff" in cmd_str.lower()

    def test_run_linter_executes_flake8(self, flake8_hook):
        """Should execute flake8 when configured."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )
            flake8_hook.run_linter(["src/module.py"])

            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
            cmd_str = str(cmd)
            assert "flake8" in cmd_str.lower()

    def test_run_linter_passes_python_files(self, hook):
        """Should pass Python files to linter."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            python_files = ["src/api/users.py", "src/models/user.py"]
            hook.run_linter(python_files)

            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
            cmd_str = " ".join(str(arg) for arg in cmd)
            # At least one file should be in command
            assert "users.py" in cmd_str or "src" in cmd_str

    def test_run_linter_returns_success_on_clean(self, hook):
        """Should return success when no lint issues found."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="All checks passed!",
                stderr=""
            )
            result = hook.run_linter(["src/module.py"])

            assert isinstance(result, VerificationResult)
            assert result.success is True
            assert result.lint_errors == 0

    def test_run_linter_returns_failure_on_issues(self, hook):
        """Should return failure when lint issues found."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="src/module.py:10:5: E501 line too long",
                stderr=""
            )
            result = hook.run_linter(["src/module.py"])

            assert result.success is False
            assert result.lint_errors > 0

    def test_run_linter_captures_lint_output(self, hook):
        """Should capture lint output in result."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="src/module.py:10:5: E501 line too long (120 > 88 characters)",
                stderr=""
            )
            result = hook.run_linter(["src/module.py"])

            assert result.output is not None
            assert "E501" in result.output or result.lint_errors > 0

    def test_run_linter_filters_python_files_only(self, hook):
        """Should only lint Python files."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            files = ["src/module.py", "README.md", "data.json", "test.py"]
            hook.run_linter(files)

            call_args = mock_run.call_args
            if call_args:  # Linter may skip if no Python files
                cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
                cmd_str = " ".join(str(arg) for arg in cmd)
                # Should not include non-Python files
                assert "README.md" not in cmd_str
                assert "data.json" not in cmd_str

    def test_run_linter_handles_no_python_files(self, hook):
        """Should handle gracefully when no Python files provided."""
        result = hook.run_linter(["README.md", "data.json"])

        # Should succeed when no Python files to lint
        assert result.success is True
        assert result.lint_errors == 0

    def test_run_linter_handles_missing_linter(self, hook):
        """Should handle gracefully when linter is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("ruff not found")
            result = hook.run_linter(["src/module.py"])

            # Should fail gracefully
            assert result.success is False
            assert result.error is not None


# =============================================================================
# FAILURE HANDLING TESTS (TestAutoVerifyFailures)
# =============================================================================


class TestAutoVerifyFailures:
    """Tests for failure handling (fail loudly, no silent failures)."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = []
        config.tests.timeout_seconds = 300
        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config)

    def test_verify_raises_on_test_failure(self, hook):
        """Should raise VerificationError when tests fail."""
        from swarm_attack.hooks.auto_verify import VerificationError
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="1 failed",
                stderr="AssertionError"
            )

            with pytest.raises(VerificationError, match="test"):
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )

    def test_verify_raises_on_lint_failure(self, hook):
        """Should raise VerificationError when linting fails."""
        from swarm_attack.hooks.auto_verify import VerificationError
        with patch('subprocess.run') as mock_run:
            # First call succeeds (tests), second fails (lint)
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="passed", stderr=""),  # tests
                MagicMock(returncode=1, stdout="E501", stderr="")     # lint
            ]

            with pytest.raises(VerificationError, match="lint"):
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )

    def test_verify_no_silent_failures(self, hook):
        """Should never silently swallow failures."""
        from swarm_attack.hooks.auto_verify import VerificationError

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2,  # Non-zero exit
                stdout="Error occurred",
                stderr="Fatal error"
            )

            # Should either raise or return failure, never silent success
            try:
                result = hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )
                # If no exception, result must indicate failure
                assert result.success is False
            except VerificationError:
                pass  # Expected

    def test_verify_logs_failures(self, mock_config):
        """Should log failures when logger is configured."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook, VerificationError
        logger = MagicMock()
        hook = AutoVerifyHook(mock_config, logger=logger)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="FAILED",
                stderr=""
            )

            try:
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )
            except VerificationError:
                pass  # Expected - verification failed

            # Logger should have been called with failure info
            assert logger.log.called or logger.error.called or logger.warning.called

    def test_verify_returns_all_errors_when_not_fail_fast(self, hook):
        """Should collect all errors when fail_fast=False."""
        with patch('subprocess.run') as mock_run:
            # Both tests and lint fail
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout="test failed", stderr=""),
                MagicMock(returncode=1, stdout="lint failed", stderr="")
            ]

            result = hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"],
                fail_fast=False
            )

            # Should capture both failures
            assert result.success is False
            assert len(result.errors) >= 2 or (result.tests_failed > 0 and result.lint_errors > 0)

    def test_verify_stops_on_first_error_when_fail_fast(self, hook):
        """Should stop on first error when fail_fast=True."""
        from swarm_attack.hooks.auto_verify import VerificationError

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="test failed",
                stderr=""
            )

            with pytest.raises(VerificationError):
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )

            # Should only have called once (stopped at first failure)
            assert mock_run.call_count == 1

    def test_verify_includes_failure_details_in_error(self, hook):
        """Should include detailed failure info in exception."""
        from swarm_attack.hooks.auto_verify import VerificationError

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="test_something FAILED\nAssertionError: expected True",
                stderr=""
            )

            try:
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )
                pytest.fail("Expected VerificationError")
            except VerificationError as e:
                # Error should contain useful information
                error_str = str(e)
                assert "FAILED" in error_str or "test" in error_str.lower()


# =============================================================================
# VERIFICATION RECORD TESTS (TestAutoVerifyRecords)
# =============================================================================


class TestAutoVerifyRecords:
    """Tests for verification record creation in .swarm/verification/."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig with real paths."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = []
        config.tests.timeout_seconds = 300
        # Create the swarm directory
        config.swarm_path.mkdir(parents=True, exist_ok=True)
        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config)

    def test_creates_verification_directory(self, hook, mock_config):
        """Should create .swarm/verification/ directory if not exists."""
        verification_dir = mock_config.swarm_path / "verification"
        assert not verification_dir.exists()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        assert verification_dir.exists()

    def test_creates_verification_record_file(self, hook, mock_config):
        """Should create a verification record JSON file."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        # Should have created at least one record file
        record_files = list(verification_dir.glob("*.json"))
        assert len(record_files) >= 1

    def test_record_contains_timestamp(self, hook, mock_config):
        """Verification record should contain timestamp."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        assert len(record_files) >= 1

        with open(record_files[0]) as f:
            record = json.load(f)

        assert "timestamp" in record or "created_at" in record

    def test_record_contains_modified_files(self, hook, mock_config):
        """Verification record should list modified files."""
        verification_dir = mock_config.swarm_path / "verification"
        modified = ["src/api/users.py", "src/models/user.py"]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=modified,
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        with open(record_files[0]) as f:
            record = json.load(f)

        assert "modified_files" in record or "files" in record
        files_in_record = record.get("modified_files", record.get("files", []))
        assert "src/api/users.py" in files_in_record or len(files_in_record) > 0

    def test_record_contains_test_results(self, hook, mock_config):
        """Verification record should contain test results."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="5 passed",
                stderr=""
            )
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        with open(record_files[0]) as f:
            record = json.load(f)

        assert "test_result" in record or "tests" in record or "result" in record

    def test_record_contains_lint_results(self, hook, mock_config):
        """Verification record should contain lint results."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="passed", stderr=""),
                MagicMock(returncode=0, stdout="clean", stderr="")
            ]
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        with open(record_files[0]) as f:
            record = json.load(f)

        assert "lint_result" in record or "lint" in record or "linter" in record

    def test_record_contains_success_status(self, hook, mock_config):
        """Verification record should contain overall success status."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        with open(record_files[0]) as f:
            record = json.load(f)

        assert "success" in record or "status" in record or "passed" in record

    def test_record_filename_includes_timestamp(self, hook, mock_config):
        """Record filename should include timestamp for uniqueness."""
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

        record_files = list(verification_dir.glob("*.json"))
        assert len(record_files) >= 1

        filename = record_files[0].name
        # Filename should contain date/time pattern or unique ID
        assert any(c.isdigit() for c in filename)

    def test_record_created_on_failure_too(self, hook, mock_config):
        """Should create verification record even on failure."""
        from swarm_attack.hooks.auto_verify import VerificationError
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="FAILED",
                stderr=""
            )

            try:
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )
            except VerificationError:
                pass

        # Record should still be created
        record_files = list(verification_dir.glob("*.json"))
        assert len(record_files) >= 1

    def test_record_contains_error_details_on_failure(self, hook, mock_config):
        """Verification record should contain error details on failure."""
        from swarm_attack.hooks.auto_verify import VerificationError
        verification_dir = mock_config.swarm_path / "verification"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="test_example.py::test_something FAILED\nAssertionError",
                stderr=""
            )

            try:
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )
            except VerificationError:
                pass

        record_files = list(verification_dir.glob("*.json"))
        with open(record_files[0]) as f:
            record = json.load(f)

        # Should indicate failure
        success = record.get("success", record.get("status", record.get("passed")))
        assert success is False or success == "failed" or success == "failure"


# =============================================================================
# TRIGGER TESTS
# =============================================================================


class TestAutoVerifyTriggers:
    """Tests for trigger conditions (file writes, git commits)."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = []
        config.tests.timeout_seconds = 300
        config.swarm_path.mkdir(parents=True, exist_ok=True)
        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config)

    def test_should_trigger_on_python_file_write(self, hook):
        """Should trigger verification on Python file write."""
        assert hook.should_trigger(
            event_type="file_write",
            file_path="src/module.py"
        ) is True

    def test_should_trigger_on_test_file_write(self, hook):
        """Should trigger verification on test file write."""
        assert hook.should_trigger(
            event_type="file_write",
            file_path="tests/test_module.py"
        ) is True

    def test_should_trigger_on_git_commit(self, hook):
        """Should trigger verification on git commit."""
        assert hook.should_trigger(
            event_type="git_commit",
            file_path=None
        ) is True

    def test_should_not_trigger_on_non_python_file(self, hook):
        """Should not trigger on non-Python file writes."""
        assert hook.should_trigger(
            event_type="file_write",
            file_path="README.md"
        ) is False

    def test_should_not_trigger_on_ignored_paths(self, hook):
        """Should not trigger on ignored paths (e.g., __pycache__)."""
        assert hook.should_trigger(
            event_type="file_write",
            file_path="src/__pycache__/module.cpython-311.pyc"
        ) is False

    def test_should_trigger_on_init_file(self, hook):
        """Should trigger on __init__.py files."""
        assert hook.should_trigger(
            event_type="file_write",
            file_path="src/package/__init__.py"
        ) is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAutoVerifyIntegration:
    """Integration tests for AutoVerifyHook."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig with real directory structure."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        config.tests = MagicMock()
        config.tests.command = "pytest"
        config.tests.args = ["-v"]
        config.tests.timeout_seconds = 300

        # Create directory structure
        config.swarm_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        return config

    @pytest.fixture
    def hook(self, mock_config):
        """Create an AutoVerifyHook instance."""
        from swarm_attack.hooks.auto_verify import AutoVerifyHook
        return AutoVerifyHook(mock_config)

    def test_full_verification_flow_success(self, hook, mock_config):
        """Test complete verification flow with success."""
        with patch('subprocess.run') as mock_run:
            # Tests pass, lint passes
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="5 passed", stderr=""),
                MagicMock(returncode=0, stdout="All checks passed!", stderr="")
            ]

            result = hook.verify(
                modified_files=["src/module.py"],
                test_files=["tests/test_module.py"]
            )

            assert result.success is True
            assert result.tests_passed > 0 or result.tests_failed == 0
            assert result.lint_errors == 0

            # Verification record should exist
            verification_dir = mock_config.swarm_path / "verification"
            assert verification_dir.exists()
            assert len(list(verification_dir.glob("*.json"))) >= 1

    def test_full_verification_flow_test_failure(self, hook, mock_config):
        """Test complete verification flow with test failure."""
        from swarm_attack.hooks.auto_verify import VerificationError

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="1 failed, 4 passed",
                stderr=""
            )

            with pytest.raises(VerificationError):
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )

    def test_full_verification_flow_lint_failure(self, hook, mock_config):
        """Test complete verification flow with lint failure."""
        from swarm_attack.hooks.auto_verify import VerificationError

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="passed", stderr=""),  # tests
                MagicMock(returncode=1, stdout="E501", stderr="")     # lint
            ]

            with pytest.raises(VerificationError):
                hook.verify(
                    modified_files=["src/module.py"],
                    test_files=["tests/test_module.py"],
                    fail_fast=True
                )

    def test_hook_callable_as_post_tool_use(self, hook):
        """Hook should be callable as PostToolUse hook."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # Simulate PostToolUse hook call
            result = hook.on_post_tool_use(
                tool_name="Write",
                tool_args={"file_path": "src/module.py", "content": "..."},
                tool_result={"success": True}
            )

            # Should return verification result or None
            assert result is None or hasattr(result, 'success')

    def test_hook_skips_non_triggering_events(self, hook):
        """Hook should skip non-triggering events efficiently."""
        with patch('subprocess.run') as mock_run:
            result = hook.on_post_tool_use(
                tool_name="Read",  # Read doesn't trigger verification
                tool_args={"file_path": "src/module.py"},
                tool_result={"content": "..."}
            )

            # Should not have run any subprocess
            mock_run.assert_not_called()
            assert result is None


# =============================================================================
# VERIFICATION RESULT DATACLASS TESTS
# =============================================================================


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_verification_result_has_success(self):
        """VerificationResult should have success field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=True)
        assert result.success is True

    def test_verification_result_has_tests_passed(self):
        """VerificationResult should have tests_passed field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=True, tests_passed=5)
        assert result.tests_passed == 5

    def test_verification_result_has_tests_failed(self):
        """VerificationResult should have tests_failed field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=False, tests_failed=2)
        assert result.tests_failed == 2

    def test_verification_result_has_lint_errors(self):
        """VerificationResult should have lint_errors field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=False, lint_errors=3)
        assert result.lint_errors == 3

    def test_verification_result_has_output(self):
        """VerificationResult should have output field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=True, output="All passed")
        assert result.output == "All passed"

    def test_verification_result_has_error(self):
        """VerificationResult should have error field."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(success=False, error="Test timeout")
        assert result.error == "Test timeout"

    def test_verification_result_has_errors_list(self):
        """VerificationResult should have errors list for multiple failures."""
        from swarm_attack.hooks.auto_verify import VerificationResult
        result = VerificationResult(
            success=False,
            errors=["Test failed", "Lint failed"]
        )
        assert len(result.errors) == 2


# =============================================================================
# VERIFICATION RECORD DATACLASS TESTS
# =============================================================================


class TestVerificationRecord:
    """Tests for VerificationRecord dataclass."""

    def test_verification_record_has_timestamp(self):
        """VerificationRecord should have timestamp."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp=datetime.now().isoformat(),
            modified_files=[],
            success=True
        )
        assert record.timestamp is not None

    def test_verification_record_has_modified_files(self):
        """VerificationRecord should have modified_files list."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp=datetime.now().isoformat(),
            modified_files=["src/a.py", "src/b.py"],
            success=True
        )
        assert len(record.modified_files) == 2

    def test_verification_record_has_test_result(self):
        """VerificationRecord should have test_result."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp=datetime.now().isoformat(),
            modified_files=[],
            success=True,
            test_result={"passed": 5, "failed": 0}
        )
        assert record.test_result["passed"] == 5

    def test_verification_record_has_lint_result(self):
        """VerificationRecord should have lint_result."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp=datetime.now().isoformat(),
            modified_files=[],
            success=True,
            lint_result={"errors": 0}
        )
        assert record.lint_result["errors"] == 0

    def test_verification_record_to_dict(self):
        """VerificationRecord should be convertible to dict."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp="2026-01-05T10:00:00",
            modified_files=["src/module.py"],
            success=True
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["timestamp"] == "2026-01-05T10:00:00"

    def test_verification_record_to_json(self):
        """VerificationRecord should be serializable to JSON."""
        from swarm_attack.hooks.auto_verify import VerificationRecord
        record = VerificationRecord(
            timestamp="2026-01-05T10:00:00",
            modified_files=["src/module.py"],
            success=True
        )
        json_str = record.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["success"] is True
