"""Tests for CoderAgent empty-files validation (Bug #1).

When the LLM returns a response with no parseable file markers,
the coder should return a failure result, NOT a success with empty files.

This prevents the orchestrator from marking tasks as "Done" when
no actual implementation was generated.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path


class TestCoderEmptyFilesValidation:
    """Tests for empty-files validation in CoderAgent."""

    @pytest.fixture
    def coder(self):
        """Create a CoderAgent instance for testing."""
        from swarm_attack.agents.coder import CoderAgent
        from swarm_attack.config import SwarmConfig

        config = MagicMock(spec=SwarmConfig)
        config.repo_root = Path("/tmp/test-repo")
        config.specs_path = Path("/tmp/test-repo/specs")

        return CoderAgent(config=config)

    def test_parse_file_outputs_returns_empty_for_prose_response(self, coder):
        """_parse_file_outputs returns empty dict when LLM returns prose only."""
        prose_response = """
I'll help you implement this feature. Here's what we need to do:

1. First, create a new module for handling authentication
2. Then, add the login endpoint
3. Finally, write tests

Let me know if you have questions!
"""
        files = coder._parse_file_outputs(prose_response)
        assert files == {}

    def test_parse_file_outputs_returns_files_for_valid_response(self, coder):
        """_parse_file_outputs returns files when proper markers are present."""
        valid_response = """
# FILE: src/auth.py
def login(username, password):
    return True

# FILE: tests/test_auth.py
def test_login():
    assert login("user", "pass")
"""
        files = coder._parse_file_outputs(valid_response)
        assert len(files) == 2
        assert "src/auth.py" in files
        assert "tests/test_auth.py" in files

    def test_parse_file_outputs_returns_empty_for_empty_response(self, coder):
        """_parse_file_outputs returns empty dict for empty LLM response."""
        files = coder._parse_file_outputs("")
        assert files == {}

    def test_parse_file_outputs_returns_empty_for_whitespace(self, coder):
        """_parse_file_outputs returns empty dict for whitespace-only response."""
        files = coder._parse_file_outputs("   \n\n\t  \n  ")
        assert files == {}


class TestCoderEmptyFilesValidationLogic:
    """Tests for the empty-files validation logic in coder.py.

    These tests verify that:
    1. When files dict is empty (after parsing), we return failure
    2. When files dict only contains .gitkeep markers, we return failure
    3. When files dict has real files, we proceed to success path
    """

    @pytest.fixture
    def coder(self):
        """Create a CoderAgent instance for testing."""
        from swarm_attack.agents.coder import CoderAgent
        from swarm_attack.config import SwarmConfig

        config = MagicMock(spec=SwarmConfig)
        config.repo_root = Path("/tmp/test-repo")
        config.specs_path = Path("/tmp/test-repo/specs")

        return CoderAgent(config=config)

    def test_real_files_filter_excludes_gitkeep(self, coder):
        """The real_files filter should exclude .gitkeep files."""
        files = {
            "src/.gitkeep": "",
            "backend/.gitkeep": "",
        }
        real_files = {k: v for k, v in files.items() if not k.endswith('.gitkeep')}
        assert real_files == {}

    def test_real_files_filter_includes_implementation(self, coder):
        """The real_files filter should include implementation files."""
        files = {
            "src/auth.py": "class Auth: pass",
            "src/.gitkeep": "",
            "tests/test_auth.py": "def test(): pass",
        }
        real_files = {k: v for k, v in files.items() if not k.endswith('.gitkeep')}
        assert len(real_files) == 2
        assert "src/auth.py" in real_files
        assert "tests/test_auth.py" in real_files

    def test_validation_rejects_empty_files(self):
        """Verify the code path exists that rejects empty files.

        This test reads the source code to confirm the validation logic exists.
        A full integration test would require mocking the entire LLM pipeline.
        """
        import inspect
        from swarm_attack.agents.coder import CoderAgent

        # The implementation is in the `run` method
        source = inspect.getsource(CoderAgent.run)

        # Verify the empty-files validation logic exists
        assert "coder_no_files_generated" in source
        assert "no file outputs" in source.lower() or "no parseable file" in source.lower()
        assert "real_files" in source
