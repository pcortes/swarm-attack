"""Tests for VerifierAgent pattern recording functionality.

This test module verifies that VerifierAgent correctly records verification
patterns (success/failure) to the memory system for cross-session learning.

TDD approach: Tests define expected behavior before implementation.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.agents.verifier import VerifierAgent
from swarm_attack.memory.store import MemoryStore
from swarm_attack.memory.patterns import PatternDetector


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig for testing."""
    config = MagicMock()
    config.repo_root = tmp_path
    config.tests = MagicMock()
    config.tests.timeout_seconds = 30
    return config


@pytest.fixture
def memory_store():
    """Create a fresh MemoryStore for testing."""
    return MemoryStore()


@pytest.fixture
def pattern_detector(memory_store):
    """Create a PatternDetector with a fresh store."""
    return PatternDetector(store=memory_store)


@pytest.fixture
def verifier_agent(mock_config, pattern_detector):
    """Create a VerifierAgent with pattern detection enabled."""
    return VerifierAgent(
        config=mock_config,
        pattern_detector=pattern_detector,
    )


@pytest.fixture
def test_file(tmp_path):
    """Create a simple passing test file."""
    test_path = tmp_path / "tests" / "generated" / "test-feature" / "test_issue_1.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("""
def test_simple():
    assert True
""")
    return test_path


# =============================================================================
# TestVerifierRecordsSuccessPattern
# =============================================================================


class TestVerifierRecordsSuccessPattern:
    """Test that VerifierAgent records success patterns."""

    def test_verifier_records_success_pattern(
        self, mock_config, memory_store, pattern_detector, test_file
    ):
        """Successful verification recorded for learning."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        # Mock _run_pytest to return success
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.01s")

            result = verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
            })

        assert result.success is True

        # Verify pattern was recorded
        patterns = pattern_detector.get_verification_patterns(
            feature_id="test-feature",
            result="success",
        )
        assert len(patterns) == 1
        assert patterns[0].content["result"] == "success"
        assert patterns[0].content["test_path"] == str(test_file)


# =============================================================================
# TestVerifierRecordsFailurePattern
# =============================================================================


class TestVerifierRecordsFailurePattern:
    """Test that VerifierAgent records failure patterns."""

    def test_verifier_records_failure_pattern(
        self, mock_config, memory_store, pattern_detector, test_file
    ):
        """Failed verification recorded with error details."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        # Mock _run_pytest to return failure
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (
                1,
                "FAILED test_issue_1.py::test_simple - AssertionError: assert False"
            )

            result = verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
            })

        assert result.success is False

        # Verify failure pattern was recorded
        patterns = pattern_detector.get_verification_patterns(
            feature_id="test-feature",
            result="failure",
        )
        assert len(patterns) == 1
        assert patterns[0].content["result"] == "failure"
        assert patterns[0].content["error_message"] is not None


# =============================================================================
# TestPatternIncludesContext
# =============================================================================


class TestPatternIncludesContext:
    """Test that pattern entries include proper context."""

    def test_pattern_includes_test_path(
        self, mock_config, memory_store, pattern_detector, test_file
    ):
        """Pattern entry includes test path."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.01s")

            verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
            })

        patterns = pattern_detector.get_verification_patterns(feature_id="test-feature")
        assert len(patterns) == 1
        assert patterns[0].content["test_path"] == str(test_file)

    def test_pattern_includes_error_message(
        self, mock_config, memory_store, pattern_detector, test_file
    ):
        """Pattern entry includes error message for failures."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        error_output = "FAILED test_issue_1.py::TestClass::test_name - AssertionError: Expected 5, got 3"

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (1, error_output)

            verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
            })

        patterns = pattern_detector.get_verification_patterns(
            feature_id="test-feature",
            result="failure",
        )
        assert len(patterns) == 1
        assert "AssertionError" in patterns[0].content["error_message"]


# =============================================================================
# TestPatternLinksToFix
# =============================================================================


class TestPatternLinksToFix:
    """Test that success patterns can link to what fixed the issue."""

    def test_success_pattern_links_to_fix(
        self, mock_config, memory_store, pattern_detector, test_file
    ):
        """Success pattern links to what fixed the issue."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        # First run fails
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (
                1,
                "FAILED test_issue_1.py::TestClass::test_name - AssertionError"
            )

            verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
            })

        # Get the failure entry ID
        failure_patterns = pattern_detector.get_verification_patterns(
            feature_id="test-feature",
            result="failure",
        )
        assert len(failure_patterns) == 1
        failure_entry_id = failure_patterns[0].id

        # Second run succeeds with fix info
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.01s")

            verifier.run({
                "feature_id": "test-feature",
                "issue_number": 1,
                "test_path": str(test_file),
                "check_regressions": False,
                "fix_applied": "Added missing return statement",
                "related_failure_id": failure_entry_id,
            })

        # Verify success pattern links to fix
        success_patterns = pattern_detector.get_verification_patterns(
            feature_id="test-feature",
            result="success",
        )
        assert len(success_patterns) == 1
        assert success_patterns[0].content["fix_applied"] == "Added missing return statement"
        assert failure_entry_id in success_patterns[0].content["related_entries"]


# =============================================================================
# TestMultiplePatternsFromSession
# =============================================================================


class TestMultiplePatternsFromSession:
    """Test that a session can record multiple patterns."""

    def test_session_can_have_multiple_patterns(
        self, mock_config, memory_store, pattern_detector, tmp_path
    ):
        """A session can record multiple patterns."""
        verifier = VerifierAgent(
            config=mock_config,
            pattern_detector=pattern_detector,
        )

        # Create multiple test files
        test_files = []
        for i in range(3):
            test_path = tmp_path / "tests" / "generated" / f"feature-{i}" / f"test_issue_{i}.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(f"""
def test_example_{i}():
    assert True
""")
            test_files.append(test_path)

        # Run verifier multiple times
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            # First two pass, last one fails
            mock_pytest.side_effect = [
                (0, "1 passed in 0.01s"),
                (0, "1 passed in 0.01s"),
                (1, "FAILED - AssertionError"),
            ]

            for i, test_path in enumerate(test_files):
                verifier.run({
                    "feature_id": f"feature-{i}",
                    "issue_number": i,
                    "test_path": str(test_path),
                    "check_regressions": False,
                })

        # Verify all patterns were recorded
        all_patterns = pattern_detector.get_verification_patterns()
        assert len(all_patterns) == 3

        success_patterns = pattern_detector.get_verification_patterns(result="success")
        assert len(success_patterns) == 2

        failure_patterns = pattern_detector.get_verification_patterns(result="failure")
        assert len(failure_patterns) == 1
