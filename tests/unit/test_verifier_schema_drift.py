"""
Tests for VerifierAgent schema drift detection functionality.

These tests validate the duplicate class detection mechanism that
prevents schema drift between issues.
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


class TestCheckDuplicateClasses:
    """Tests for _check_duplicate_classes method."""

    def test_no_conflicts_empty_registry(self, verifier):
        """Test with empty registry - no conflicts possible."""
        new_classes = {
            "autopilot.py": ["AutopilotSession", "Runner"],
        }
        conflicts = verifier._check_duplicate_classes(new_classes, {})
        assert conflicts == []

    def test_no_conflicts_different_classes(self, verifier):
        """Test when new classes don't conflict with existing ones."""
        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["Session", "User"],
                }
            }
        }
        new_classes = {
            "autopilot.py": ["Runner", "Controller"],
        }
        conflicts = verifier._check_duplicate_classes(new_classes, registry)
        assert conflicts == []

    def test_no_conflict_same_file(self, verifier):
        """Test that updating the SAME file doesn't trigger conflict."""
        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["Session"],
                }
            }
        }
        # Re-defining in the same file is OK (modification, not duplication)
        new_classes = {
            "models.py": ["Session"],
        }
        conflicts = verifier._check_duplicate_classes(new_classes, registry)
        assert conflicts == []

    def test_detects_duplicate_class(self, verifier):
        """Test detection of a duplicate class in a different file."""
        registry = {
            "modules": {
                "swarm_attack/chief_of_staff/models.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession", "DailyGoal"],
                }
            }
        }
        # Issue #9 recreates AutopilotSession in a different file
        new_classes = {
            "swarm_attack/chief_of_staff/autopilot.py": ["AutopilotSession", "Runner"],
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "AutopilotSession"
        assert conflicts[0]["existing_file"] == "swarm_attack/chief_of_staff/models.py"
        assert conflicts[0]["new_file"] == "swarm_attack/chief_of_staff/autopilot.py"
        assert conflicts[0]["existing_issue"] == 1
        assert conflicts[0]["severity"] == "critical"
        assert "SCHEMA DRIFT DETECTED" in conflicts[0]["message"]

    def test_detects_multiple_duplicates(self, verifier):
        """Test detection of multiple duplicate classes."""
        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["Session", "User", "Token"],
                }
            }
        }
        # New code recreates multiple classes
        new_classes = {
            "new_models.py": ["Session", "Token"],  # Both are duplicates
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        assert len(conflicts) == 2
        conflict_names = {c["class_name"] for c in conflicts}
        assert conflict_names == {"Session", "Token"}

    def test_detects_duplicates_across_files(self, verifier):
        """Test detection when duplicates span multiple new files."""
        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["Session"],
                },
                "auth.py": {
                    "created_by_issue": 2,
                    "classes": ["Token"],
                },
            }
        }
        # New code creates files that conflict with different existing files
        new_classes = {
            "new_session.py": ["Session"],  # Conflicts with models.py
            "new_auth.py": ["Token"],  # Conflicts with auth.py
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        assert len(conflicts) == 2

        session_conflict = next(c for c in conflicts if c["class_name"] == "Session")
        assert session_conflict["existing_file"] == "models.py"
        assert session_conflict["existing_issue"] == 1

        token_conflict = next(c for c in conflicts if c["class_name"] == "Token")
        assert token_conflict["existing_file"] == "auth.py"
        assert token_conflict["existing_issue"] == 2


class TestVerifierRunWithSchemaDrift:
    """Tests for verifier.run() with schema drift detection."""

    def test_fails_on_schema_drift(self, verifier, temp_repo):
        """Test that verifier fails when schema drift is detected."""
        # Create a test file so the verifier doesn't fail on missing test
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_9.py"
        test_file.write_text("def test_dummy(): pass")

        context = {
            "feature_id": "test-feature",
            "issue_number": 9,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["AutopilotSession"],
                    }
                }
            },
            "new_classes_defined": {
                "autopilot.py": ["AutopilotSession"],  # Duplicate!
            },
            "check_regressions": False,
        }

        result = verifier.run(context)

        assert result.success is False
        assert len(result.errors) == 1
        assert "SCHEMA DRIFT DETECTED" in result.errors[0]
        assert "AutopilotSession" in result.errors[0]
        assert "schema_conflicts" in result.output
        assert result.output["tests_run"] == 0  # Tests never ran

    def test_passes_without_schema_drift(self, verifier, temp_repo):
        """Test that verifier proceeds when no schema drift detected."""
        # Create a passing test file
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_9.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 9,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["Session"],
                    }
                }
            },
            "new_classes_defined": {
                "runner.py": ["Runner"],  # No conflict
            },
            "check_regressions": False,
        }

        # Mock pytest to avoid actually running tests
        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")
            result = verifier.run(context)

        # Should proceed to run tests (no schema drift)
        assert mock_pytest.called
        # Result depends on test outcome, but schema check passed

    def test_skips_check_without_registry(self, verifier, temp_repo):
        """Test that schema check is skipped when no registry provided."""
        test_dir = temp_repo / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_9.py"
        test_file.write_text("def test_passes(): assert True")

        context = {
            "feature_id": "test-feature",
            "issue_number": 9,
            # No module_registry or new_classes_defined
            "check_regressions": False,
        }

        with patch.object(verifier, "_run_pytest") as mock_pytest:
            mock_pytest.return_value = (0, "1 passed in 0.1s")
            result = verifier.run(context)

        # Should proceed without schema drift check
        assert mock_pytest.called

    def test_conflict_message_format(self, verifier):
        """Test that conflict messages are informative."""
        registry = {
            "modules": {
                "swarm_attack/models.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession"],
                }
            }
        }
        new_classes = {
            "swarm_attack/autopilot.py": ["AutopilotSession"],
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        message = conflicts[0]["message"]
        # Should contain all relevant information
        assert "AutopilotSession" in message
        assert "swarm_attack/models.py" in message
        assert "swarm_attack/autopilot.py" in message
        assert "issue #1" in message
        assert "runtime errors" in message.lower()


class TestRealWorldScenario:
    """Tests simulating the actual chief-of-staff schema drift scenario."""

    def test_chief_of_staff_scenario(self, verifier):
        """
        Test the exact scenario from the root cause analysis:
        Issue #1 creates AutopilotSession in models.py
        Issue #9 recreates AutopilotSession in autopilot.py
        """
        # Registry reflects Issue #1's implementation
        registry = {
            "modules": {
                "swarm_attack/chief_of_staff/models.py": {
                    "created_by_issue": 1,
                    "classes": [
                        "AutopilotSession",
                        "DailyGoal",
                        "CheckpointEvent",
                        "WorkLogEntry",
                    ],
                }
            }
        }

        # Issue #9's coder creates a duplicate AutopilotSession
        new_classes = {
            "swarm_attack/chief_of_staff/autopilot.py": [
                "AutopilotSession",  # DUPLICATE - should be caught!
                "AutopilotRunner",   # OK - new class
                "AutopilotStatus",   # OK - new class
            ],
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        # Should detect exactly one conflict
        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "AutopilotSession"
        assert "models.py" in conflicts[0]["existing_file"]
        assert "autopilot.py" in conflicts[0]["new_file"]
        assert conflicts[0]["existing_issue"] == 1

    def test_correct_implementation_scenario(self, verifier):
        """
        Test the correct implementation where Issue #9 imports
        AutopilotSession instead of recreating it.
        """
        registry = {
            "modules": {
                "swarm_attack/chief_of_staff/models.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession", "DailyGoal"],
                }
            }
        }

        # Issue #9's correct implementation - no duplicate classes
        new_classes = {
            "swarm_attack/chief_of_staff/autopilot.py": [
                "AutopilotRunner",   # New class that USES AutopilotSession
                "AutopilotStatus",   # New enum
            ],
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        # No conflicts - correct implementation
        assert conflicts == []
