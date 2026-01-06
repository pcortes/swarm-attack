"""Unit tests for VerifierAgent memory recording functionality.

TDD tests to verify that the VerifierAgent correctly records schema drift
events to the memory store for cross-session learning.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from swarm_attack.agents.verifier import VerifierAgent
from swarm_attack.config import SwarmConfig
from swarm_attack.memory.store import MemoryStore, MemoryEntry


@pytest.fixture
def mock_config(tmp_path):
    """Create a minimal SwarmConfig for testing."""
    repo_root = tmp_path / "test-repo"
    repo_root.mkdir()

    # Create tests/generated directory for test file path checks
    tests_dir = repo_root / "tests" / "generated" / "test-feature"
    tests_dir.mkdir(parents=True)

    # Create test files for various issue numbers used in tests
    for issue_num in [1, 2, 3, 4, 5, 6, 10]:
        (tests_dir / f"test_issue_{issue_num}.py").write_text("# test file")

    # Also create feature-x directory for one test
    feature_x_dir = repo_root / "tests" / "generated" / "feature-x"
    feature_x_dir.mkdir(parents=True)
    (feature_x_dir / "test_issue_10.py").write_text("# test file")

    config = SwarmConfig(repo_root=str(repo_root))
    return config


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store for testing."""
    store = MagicMock(spec=MemoryStore)
    store.add = MagicMock()
    store.save = MagicMock()
    return store


class TestVerifierRecordsSchemaDriftToMemory:
    """Test that when schema drift is detected, it's recorded to memory."""

    def test_verifier_records_schema_drift_to_memory(self, mock_config, mock_memory_store):
        """Test that schema drift conflicts are recorded to memory store."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        # Context with schema drift (duplicate class definition)
        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "module_registry": {
                "modules": {
                    "models/session.py": {
                        "created_by_issue": 1,
                        "classes": ["AutopilotSession"],
                    }
                }
            },
            "new_classes_defined": {
                "autopilot/core.py": ["AutopilotSession"],  # Duplicate!
            },
        }

        # Act
        result = verifier.run(context)

        # Assert
        assert result.success is False
        assert mock_memory_store.add.called

        # Check that an entry was added with schema_drift category
        call_args = mock_memory_store.add.call_args
        entry = call_args[0][0]  # First positional argument
        assert isinstance(entry, MemoryEntry)
        assert entry.category == "schema_drift"
        assert entry.feature_id == "test-feature"
        assert entry.issue_number == 1
        assert entry.content["class_name"] == "AutopilotSession"
        assert entry.outcome == "blocked"


class TestVerifierSavesMemoryAfterRecording:
    """Test that memory.save() is called after recording drift."""

    def test_verifier_saves_memory_after_recording(self, mock_config, mock_memory_store):
        """Test that memory store save() is called after adding drift entry."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 2,
            "module_registry": {
                "modules": {
                    "models/base.py": {
                        "created_by_issue": 1,
                        "classes": ["BaseModel"],
                    }
                }
            },
            "new_classes_defined": {
                "utils/models.py": ["BaseModel"],  # Duplicate!
            },
        }

        # Act
        verifier.run(context)

        # Assert - both add and save should be called
        assert mock_memory_store.add.called, "add() should be called to record schema drift"
        assert mock_memory_store.save.called, "save() should be called to persist memory"

        # Verify at least one entry was added before save
        assert mock_memory_store.add.call_count >= 1


class TestVerifierIncludesClassNameInTags:
    """Test that the recorded entry includes the class name in tags."""

    def test_verifier_includes_class_name_in_tags(self, mock_config, mock_memory_store):
        """Test that schema drift entry has class name and 'schema_drift' in tags."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 3,
            "module_registry": {
                "modules": {
                    "services/auth.py": {
                        "created_by_issue": 2,
                        "classes": ["AuthService"],
                    }
                }
            },
            "new_classes_defined": {
                "handlers/auth.py": ["AuthService"],  # Duplicate!
            },
        }

        # Act
        verifier.run(context)

        # Assert
        assert mock_memory_store.add.called
        entry = mock_memory_store.add.call_args[0][0]

        # Check tags contain both schema_drift and the class name
        assert "schema_drift" in entry.tags
        assert "AuthService" in entry.tags


class TestVerifierHandlesNoMemoryStoreGracefully:
    """Test that when memory_store is None, no errors occur."""

    def test_verifier_handles_no_memory_store_gracefully(self, mock_config):
        """Test that verifier works without memory store (no exceptions)."""
        # Arrange - no memory store provided
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=None,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 4,
            "module_registry": {
                "modules": {
                    "models/user.py": {
                        "created_by_issue": 1,
                        "classes": ["User"],
                    }
                }
            },
            "new_classes_defined": {
                "entities/user.py": ["User"],  # Duplicate - but no memory store
            },
        }

        # Act - should not raise exception
        result = verifier.run(context)

        # Assert
        assert result.success is False  # Still detects schema drift
        assert len(result.output.get("schema_conflicts", [])) > 0
        # Most importantly: no exception was raised

    def test_verifier_without_memory_store_still_detects_drift(self, mock_config):
        """Test that drift detection works even without memory store."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=None,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 5,
            "module_registry": {
                "modules": {
                    "api/routes.py": {
                        "created_by_issue": 1,
                        "classes": ["Router"],
                    }
                }
            },
            "new_classes_defined": {
                "web/routes.py": ["Router"],
            },
        }

        # Act
        result = verifier.run(context)

        # Assert - schema drift is still detected and reported
        assert result.success is False
        assert "schema_conflicts" in result.output
        conflicts = result.output["schema_conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "Router"


class TestVerifierRecordsMultipleConflicts:
    """Test that multiple schema conflicts are all recorded."""

    def test_verifier_records_all_conflicts_to_memory(self, mock_config, mock_memory_store):
        """Test that when multiple classes conflict, all are recorded."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 6,
            "module_registry": {
                "modules": {
                    "models/entities.py": {
                        "created_by_issue": 1,
                        "classes": ["User", "Account"],
                    }
                }
            },
            "new_classes_defined": {
                "domain/models.py": ["User", "Account"],  # Both duplicate!
            },
        }

        # Act
        verifier.run(context)

        # Assert - add() should be called twice (once per conflict)
        assert mock_memory_store.add.call_count == 2

        # Get all recorded entries
        recorded_classes = set()
        for call in mock_memory_store.add.call_args_list:
            entry = call[0][0]
            recorded_classes.add(entry.content["class_name"])

        assert "User" in recorded_classes
        assert "Account" in recorded_classes


class TestVerifierRecordsConflictDetails:
    """Test that recorded entries contain full conflict details."""

    def test_verifier_records_existing_file_info(self, mock_config, mock_memory_store):
        """Test that memory entry contains existing file and issue info."""
        # Arrange
        verifier = VerifierAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        context = {
            "feature_id": "feature-x",
            "issue_number": 10,
            "module_registry": {
                "modules": {
                    "core/config.py": {
                        "created_by_issue": 3,
                        "classes": ["Settings"],
                    }
                }
            },
            "new_classes_defined": {
                "utils/settings.py": ["Settings"],
            },
        }

        # Act
        verifier.run(context)

        # Assert
        entry = mock_memory_store.add.call_args[0][0]
        assert entry.content["existing_file"] == "core/config.py"
        assert entry.content["new_file"] == "utils/settings.py"
        assert entry.content["existing_issue"] == 3
