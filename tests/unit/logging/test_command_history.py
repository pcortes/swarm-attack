"""
Unit tests for CommandHistory - Command Logging Module.

TDD Tests for the CommandHistory module that provides:
- Command logging with timestamps, outcomes, and reasoning
- Git commit SHA linking
- Search by date, command type, or outcome
- Secret redaction in logged commands

Tests written BEFORE implementation (RED phase).
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_history_path():
    """Create a temporary directory for test command history store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "logging" / "command_history.json"


@pytest.fixture
def command_history(temp_history_path):
    """Create a CommandHistory instance with temp path."""
    from swarm_attack.logging.command_history import CommandHistory

    return CommandHistory(store_path=temp_history_path)


@pytest.fixture
def sample_command():
    """Create a sample command entry for tests."""
    from swarm_attack.logging.command_history import CommandEntry

    return CommandEntry(
        id=str(uuid4()),
        command="git commit -m 'Add feature'",
        command_type="git",
        timestamp=datetime.now().isoformat(),
        outcome="success",
        reasoning="Committed changes after tests passed",
        git_sha=None,
        feature_id="test-feature",
        metadata={},
    )


# =============================================================================
# TestCommandLogging - Basic logging functionality
# =============================================================================


class TestCommandLogging:
    """Tests for basic command logging functionality."""

    def test_command_entry_creation(self):
        """Test creating a CommandEntry with all fields."""
        from swarm_attack.logging.command_history import CommandEntry

        entry = CommandEntry(
            id="cmd-123",
            command="pytest tests/ -v",
            command_type="test",
            timestamp="2026-01-05T10:00:00Z",
            outcome="success",
            reasoning="Running test suite to verify changes",
            git_sha="abc1234",
            feature_id="chief-of-staff-v3",
            metadata={"test_count": 42, "duration_seconds": 15.5},
        )

        assert entry.id == "cmd-123"
        assert entry.command == "pytest tests/ -v"
        assert entry.command_type == "test"
        assert entry.timestamp == "2026-01-05T10:00:00Z"
        assert entry.outcome == "success"
        assert entry.reasoning == "Running test suite to verify changes"
        assert entry.git_sha == "abc1234"
        assert entry.feature_id == "chief-of-staff-v3"
        assert entry.metadata == {"test_count": 42, "duration_seconds": 15.5}

    def test_command_entry_optional_fields(self):
        """Test creating a CommandEntry with optional fields as None."""
        from swarm_attack.logging.command_history import CommandEntry

        entry = CommandEntry(
            id="cmd-456",
            command="ls -la",
            command_type="shell",
            timestamp="2026-01-05T11:00:00Z",
            outcome="success",
            reasoning=None,  # Optional
            git_sha=None,  # Optional
            feature_id=None,  # Optional
            metadata={},
        )

        assert entry.reasoning is None
        assert entry.git_sha is None
        assert entry.feature_id is None
        assert entry.metadata == {}

    def test_command_entry_to_dict(self):
        """Test serializing CommandEntry to dictionary."""
        from swarm_attack.logging.command_history import CommandEntry

        entry = CommandEntry(
            id="cmd-789",
            command="python -m pytest",
            command_type="test",
            timestamp="2026-01-05T12:00:00Z",
            outcome="failure",
            reasoning="Tests failed due to import error",
            git_sha="def5678",
            feature_id="feature-x",
            metadata={"exit_code": 1},
        )

        data = entry.to_dict()

        assert data["id"] == "cmd-789"
        assert data["command"] == "python -m pytest"
        assert data["command_type"] == "test"
        assert data["timestamp"] == "2026-01-05T12:00:00Z"
        assert data["outcome"] == "failure"
        assert data["reasoning"] == "Tests failed due to import error"
        assert data["git_sha"] == "def5678"
        assert data["feature_id"] == "feature-x"
        assert data["metadata"] == {"exit_code": 1}

    def test_command_entry_from_dict(self):
        """Test deserializing CommandEntry from dictionary."""
        from swarm_attack.logging.command_history import CommandEntry

        data = {
            "id": "cmd-abc",
            "command": "git push origin main",
            "command_type": "git",
            "timestamp": "2026-01-05T14:00:00Z",
            "outcome": "success",
            "reasoning": "Pushing completed feature",
            "git_sha": "ghi9012",
            "feature_id": "feature-y",
            "metadata": {"remote": "origin"},
        }

        entry = CommandEntry.from_dict(data)

        assert entry.id == "cmd-abc"
        assert entry.command == "git push origin main"
        assert entry.command_type == "git"
        assert entry.outcome == "success"
        assert entry.git_sha == "ghi9012"

    def test_command_entry_roundtrip(self):
        """Test that to_dict/from_dict roundtrip preserves data."""
        from swarm_attack.logging.command_history import CommandEntry

        original = CommandEntry(
            id=str(uuid4()),
            command="make build",
            command_type="build",
            timestamp=datetime.now().isoformat(),
            outcome="success",
            reasoning="Building the project",
            git_sha="xyz7890",
            feature_id="roundtrip-test",
            metadata={"artifact": "app.tar.gz"},
        )

        data = original.to_dict()
        restored = CommandEntry.from_dict(data)

        assert restored.id == original.id
        assert restored.command == original.command
        assert restored.command_type == original.command_type
        assert restored.outcome == original.outcome
        assert restored.reasoning == original.reasoning
        assert restored.git_sha == original.git_sha
        assert restored.feature_id == original.feature_id
        assert restored.metadata == original.metadata

    def test_log_command_basic(self, command_history):
        """Test logging a basic command."""
        from swarm_attack.logging.command_history import CommandEntry

        entry_id = command_history.log(
            command="git status",
            command_type="git",
            outcome="success",
            reasoning="Checking working tree status",
        )

        assert entry_id is not None
        assert isinstance(entry_id, str)

        # Verify the entry was logged
        entry = command_history.get(entry_id)
        assert entry is not None
        assert entry.command == "git status"
        assert entry.command_type == "git"
        assert entry.outcome == "success"

    def test_log_command_with_all_fields(self, command_history):
        """Test logging a command with all optional fields."""
        entry_id = command_history.log(
            command="git commit -m 'Feature complete'",
            command_type="git",
            outcome="success",
            reasoning="Committing after all tests pass",
            git_sha="abc1234567890",
            feature_id="new-feature",
            metadata={"files_changed": 5},
        )

        entry = command_history.get(entry_id)

        assert entry.git_sha == "abc1234567890"
        assert entry.feature_id == "new-feature"
        assert entry.metadata == {"files_changed": 5}

    def test_log_command_generates_timestamp(self, command_history):
        """Test that logging a command automatically generates a timestamp."""
        before = datetime.now()
        entry_id = command_history.log(
            command="echo test",
            command_type="shell",
            outcome="success",
        )
        after = datetime.now()

        entry = command_history.get(entry_id)
        timestamp = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))

        # Timestamp should be between before and after (with some tolerance)
        assert timestamp >= before.replace(tzinfo=timestamp.tzinfo) - timedelta(seconds=1)
        assert timestamp <= after.replace(tzinfo=timestamp.tzinfo) + timedelta(seconds=1)

    def test_log_command_generates_unique_id(self, command_history):
        """Test that each logged command gets a unique ID."""
        id1 = command_history.log(command="cmd1", command_type="test", outcome="success")
        id2 = command_history.log(command="cmd2", command_type="test", outcome="success")
        id3 = command_history.log(command="cmd3", command_type="test", outcome="success")

        assert id1 != id2 != id3

    def test_log_command_with_failure_outcome(self, command_history):
        """Test logging a failed command."""
        entry_id = command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="failure",
            reasoning="3 tests failed due to missing fixtures",
            metadata={"failed_tests": 3, "exit_code": 1},
        )

        entry = command_history.get(entry_id)
        assert entry.outcome == "failure"
        assert entry.metadata["failed_tests"] == 3

    def test_log_command_with_error_outcome(self, command_history):
        """Test logging a command that errored."""
        entry_id = command_history.log(
            command="python script.py",
            command_type="script",
            outcome="error",
            reasoning="Script crashed with unhandled exception",
            metadata={"error_type": "RuntimeError"},
        )

        entry = command_history.get(entry_id)
        assert entry.outcome == "error"

    def test_persistence_save_and_load(self, temp_history_path):
        """Test that command history persists across instances."""
        from swarm_attack.logging.command_history import CommandHistory

        # Create first instance and log commands
        history1 = CommandHistory(store_path=temp_history_path)
        id1 = history1.log(
            command="git add .",
            command_type="git",
            outcome="success",
            reasoning="Staging all changes",
        )
        history1.save()

        # Create new instance and verify persistence
        history2 = CommandHistory.load(store_path=temp_history_path)
        entry = history2.get(id1)

        assert entry is not None
        assert entry.command == "git add ."
        assert entry.outcome == "success"

    def test_save_creates_directory(self, temp_history_path):
        """Test that save() creates parent directories if needed."""
        from swarm_attack.logging.command_history import CommandHistory

        # Path doesn't exist yet
        assert not temp_history_path.parent.exists()

        history = CommandHistory(store_path=temp_history_path)
        history.log(command="test", command_type="test", outcome="success")
        history.save()

        # Directory and file should now exist
        assert temp_history_path.parent.exists()
        assert temp_history_path.exists()

    def test_empty_history_graceful(self, temp_history_path):
        """Test that empty/new history handles queries gracefully."""
        from swarm_attack.logging.command_history import CommandHistory

        history = CommandHistory.load(store_path=temp_history_path)

        # Get should return None
        result = history.get("nonexistent-id")
        assert result is None

        # Search should return empty list
        results = history.search(command_type="git")
        assert results == []


# =============================================================================
# TestCommitLinking - Git SHA linking
# =============================================================================


class TestCommitLinking:
    """Tests for linking commands to git commit SHAs."""

    def test_log_command_with_git_sha(self, command_history):
        """Test logging a command with an explicit git SHA."""
        entry_id = command_history.log(
            command="git commit -m 'Fix bug'",
            command_type="git",
            outcome="success",
            reasoning="Bug fix committed",
            git_sha="abc123def456",
        )

        entry = command_history.get(entry_id)
        assert entry.git_sha == "abc123def456"

    def test_link_command_to_commit(self, command_history):
        """Test linking an existing command to a git commit after the fact."""
        # Log command without SHA
        entry_id = command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
        )

        # Link to commit later
        command_history.link_to_commit(entry_id, "deadbeef12345678")

        entry = command_history.get(entry_id)
        assert entry.git_sha == "deadbeef12345678"

    def test_link_command_to_commit_nonexistent_id(self, command_history):
        """Test that linking nonexistent command raises error."""
        with pytest.raises(KeyError):
            command_history.link_to_commit("nonexistent-id", "abc123")

    def test_search_by_git_sha(self, command_history):
        """Test searching for commands by git SHA."""
        sha = "abc123456789"

        # Log multiple commands with same SHA (e.g., commit + push)
        command_history.log(
            command="git commit -m 'Feature'",
            command_type="git",
            outcome="success",
            git_sha=sha,
        )
        command_history.log(
            command="git push origin main",
            command_type="git",
            outcome="success",
            git_sha=sha,
        )
        # Log command with different SHA
        command_history.log(
            command="git status",
            command_type="git",
            outcome="success",
            git_sha="different-sha",
        )

        results = command_history.search(git_sha=sha)

        assert len(results) == 2
        assert all(r.git_sha == sha for r in results)

    def test_get_commands_for_commit(self, command_history):
        """Test getting all commands associated with a specific commit."""
        sha = "feature-commit-sha"

        # Test command, then commit, then push
        command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
            git_sha=sha,
        )
        command_history.log(
            command="git commit -m 'Add feature'",
            command_type="git",
            outcome="success",
            git_sha=sha,
        )

        commands = command_history.get_commands_for_commit(sha)

        assert len(commands) == 2
        assert any(c.command_type == "test" for c in commands)
        assert any(c.command_type == "git" for c in commands)

    def test_link_overwrites_existing_sha(self, command_history):
        """Test that linking to a new SHA overwrites the existing one."""
        entry_id = command_history.log(
            command="git commit",
            command_type="git",
            outcome="success",
            git_sha="old-sha",
        )

        command_history.link_to_commit(entry_id, "new-sha")

        entry = command_history.get(entry_id)
        assert entry.git_sha == "new-sha"

    def test_partial_sha_search(self, command_history):
        """Test that search can find by partial SHA prefix."""
        full_sha = "abc123def456789012345678901234567890"

        command_history.log(
            command="git commit",
            command_type="git",
            outcome="success",
            git_sha=full_sha,
        )

        # Search by first 7 characters (common git short SHA)
        results = command_history.search(git_sha_prefix="abc123d")

        assert len(results) >= 1
        assert results[0].git_sha == full_sha


# =============================================================================
# TestHistorySearch - Search functionality
# =============================================================================


class TestHistorySearch:
    """Tests for searching command history by date, type, or outcome."""

    def test_search_by_command_type(self, command_history):
        """Test filtering search by command type."""
        # Log commands of different types
        command_history.log(command="git status", command_type="git", outcome="success")
        command_history.log(command="pytest tests/", command_type="test", outcome="success")
        command_history.log(command="git commit", command_type="git", outcome="success")
        command_history.log(command="python build.py", command_type="build", outcome="success")

        git_commands = command_history.search(command_type="git")
        test_commands = command_history.search(command_type="test")

        assert len(git_commands) == 2
        assert len(test_commands) == 1
        assert all(c.command_type == "git" for c in git_commands)

    def test_search_by_outcome(self, command_history):
        """Test filtering search by outcome."""
        command_history.log(command="pytest test1", command_type="test", outcome="success")
        command_history.log(command="pytest test2", command_type="test", outcome="failure")
        command_history.log(command="pytest test3", command_type="test", outcome="success")
        command_history.log(command="pytest test4", command_type="test", outcome="error")

        successful = command_history.search(outcome="success")
        failed = command_history.search(outcome="failure")
        errored = command_history.search(outcome="error")

        assert len(successful) == 2
        assert len(failed) == 1
        assert len(errored) == 1

    def test_search_by_date_range(self, command_history):
        """Test filtering search by date range."""
        from swarm_attack.logging.command_history import CommandEntry

        # Create entries with specific timestamps
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        week_ago = now - timedelta(days=7)

        # Log commands with backdated timestamps
        command_history.log(
            command="cmd today",
            command_type="test",
            outcome="success",
            timestamp=now.isoformat(),
        )
        command_history.log(
            command="cmd yesterday",
            command_type="test",
            outcome="success",
            timestamp=yesterday.isoformat(),
        )
        command_history.log(
            command="cmd two days ago",
            command_type="test",
            outcome="success",
            timestamp=two_days_ago.isoformat(),
        )
        command_history.log(
            command="cmd week ago",
            command_type="test",
            outcome="success",
            timestamp=week_ago.isoformat(),
        )

        # Search for last 2 days
        results = command_history.search(
            start_date=(now - timedelta(days=2)).isoformat(),
            end_date=now.isoformat(),
        )

        assert len(results) == 3  # today, yesterday, two_days_ago

    def test_search_by_single_date(self, command_history):
        """Test filtering search by a single date (start of day to end of day)."""
        today = datetime.now().date().isoformat()

        command_history.log(
            command="cmd today",
            command_type="test",
            outcome="success",
        )

        results = command_history.search(date=today)

        assert len(results) >= 1

    def test_search_by_feature_id(self, command_history):
        """Test filtering search by feature ID."""
        command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
            feature_id="feature-a",
        )
        command_history.log(
            command="git commit",
            command_type="git",
            outcome="success",
            feature_id="feature-a",
        )
        command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
            feature_id="feature-b",
        )

        feature_a_commands = command_history.search(feature_id="feature-a")

        assert len(feature_a_commands) == 2
        assert all(c.feature_id == "feature-a" for c in feature_a_commands)

    def test_search_combined_filters(self, command_history):
        """Test combining multiple search filters."""
        command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
            feature_id="feature-a",
        )
        command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="failure",
            feature_id="feature-a",
        )
        command_history.log(
            command="git commit",
            command_type="git",
            outcome="success",
            feature_id="feature-a",
        )

        # Search for successful tests in feature-a
        results = command_history.search(
            command_type="test",
            outcome="success",
            feature_id="feature-a",
        )

        assert len(results) == 1
        assert results[0].command == "pytest tests/"
        assert results[0].outcome == "success"

    def test_search_with_limit(self, command_history):
        """Test limiting search results."""
        # Log 10 commands
        for i in range(10):
            command_history.log(
                command=f"cmd-{i}",
                command_type="test",
                outcome="success",
            )

        results = command_history.search(limit=5)

        assert len(results) == 5

    def test_search_returns_newest_first(self, command_history):
        """Test that search results are ordered by timestamp, newest first."""
        now = datetime.now()

        command_history.log(
            command="oldest",
            command_type="test",
            outcome="success",
            timestamp=(now - timedelta(hours=2)).isoformat(),
        )
        command_history.log(
            command="middle",
            command_type="test",
            outcome="success",
            timestamp=(now - timedelta(hours=1)).isoformat(),
        )
        command_history.log(
            command="newest",
            command_type="test",
            outcome="success",
            timestamp=now.isoformat(),
        )

        results = command_history.search()

        assert results[0].command == "newest"
        assert results[1].command == "middle"
        assert results[2].command == "oldest"

    def test_search_by_command_text(self, command_history):
        """Test searching by command text substring."""
        command_history.log(command="git commit -m 'Fix bug'", command_type="git", outcome="success")
        command_history.log(command="git push origin main", command_type="git", outcome="success")
        command_history.log(command="pytest tests/unit/", command_type="test", outcome="success")

        results = command_history.search(command_contains="commit")

        assert len(results) == 1
        assert "commit" in results[0].command

    def test_search_no_results(self, command_history):
        """Test search with no matching results."""
        command_history.log(command="git status", command_type="git", outcome="success")

        results = command_history.search(command_type="nonexistent")

        assert results == []


# =============================================================================
# TestSecretRedaction - Secret redaction in logged commands
# =============================================================================


class TestSecretRedaction:
    """Tests for redacting secrets from logged commands."""

    def test_redacts_api_key_in_command(self, command_history):
        """Test that API keys are redacted from logged commands."""
        entry_id = command_history.log(
            command="curl -H 'Authorization: Bearer sk_test_FAKETESTKEYabc123def456ghi789'",
            command_type="api",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        # The actual API key should be redacted
        assert "sk_test_FAKETESTKEYabc123" not in entry.command
        assert "[REDACTED]" in entry.command or "***" in entry.command

    def test_redacts_password_in_command(self, command_history):
        """Test that passwords are redacted from logged commands."""
        entry_id = command_history.log(
            command="mysql -u admin -p'SuperSecret123!' database",
            command_type="database",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "SuperSecret123!" not in entry.command
        assert "[REDACTED]" in entry.command or "***" in entry.command

    def test_redacts_aws_access_key(self, command_history):
        """Test that AWS access keys are redacted."""
        entry_id = command_history.log(
            command="aws configure set aws_access_key_id AKIAIOSFODNN7EXAMPLE",
            command_type="aws",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "AKIAIOSFODNN7EXAMPLE" not in entry.command
        assert "[REDACTED]" in entry.command or "***" in entry.command

    def test_redacts_aws_secret_key(self, command_history):
        """Test that AWS secret keys are redacted."""
        entry_id = command_history.log(
            command="export AWS_SECRET_ACCESS_KEY='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
            command_type="shell",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in entry.command

    def test_redacts_github_token(self, command_history):
        """Test that GitHub tokens are redacted."""
        entry_id = command_history.log(
            command="git clone https://ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@github.com/user/repo",
            command_type="git",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" not in entry.command

    def test_redacts_jwt_token(self, command_history):
        """Test that JWT tokens are redacted."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        entry_id = command_history.log(
            command=f"curl -H 'Authorization: Bearer {jwt}' https://api.example.com",
            command_type="api",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert jwt not in entry.command

    def test_redacts_connection_string_password(self, command_history):
        """Test that passwords in connection strings are redacted."""
        entry_id = command_history.log(
            command="psql postgres://user:mysecretpassword@localhost:5432/db",
            command_type="database",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "mysecretpassword" not in entry.command

    def test_redacts_private_key_content(self, command_history):
        """Test that private key content is redacted."""
        entry_id = command_history.log(
            command="echo '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----'",
            command_type="shell",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "BEGIN RSA PRIVATE KEY" not in entry.command

    def test_redacts_env_var_secrets(self, command_history):
        """Test that secrets in environment variable assignments are redacted."""
        entry_id = command_history.log(
            command="export OPENAI_API_KEY='sk-abcdefghijklmnopqrstuvwxyz123456789012345678'",
            command_type="shell",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        assert "sk-abcdefghijklmnopqrstuvwxyz123456789012345678" not in entry.command

    def test_redacts_secrets_in_metadata(self, command_history):
        """Test that secrets in metadata are also redacted."""
        entry_id = command_history.log(
            command="test command",
            command_type="test",
            outcome="success",
            metadata={
                "api_key": "sk_test_FAKEKEYabc123def456ghi789jkl",
                "safe_data": "not a secret",
            },
        )

        entry = command_history.get(entry_id)

        # Metadata should have redacted value
        assert "sk_test_FAKEKEYabc123" not in str(entry.metadata)
        assert entry.metadata.get("safe_data") == "not a secret"

    def test_redacts_secrets_in_reasoning(self, command_history):
        """Test that secrets mentioned in reasoning are redacted."""
        entry_id = command_history.log(
            command="test",
            command_type="test",
            outcome="success",
            reasoning="Failed because API key sk_test_1234567890123456789012345678 was invalid",
        )

        entry = command_history.get(entry_id)

        assert "sk_test_1234567890123456789012345678" not in entry.reasoning

    def test_preserves_non_secret_data(self, command_history):
        """Test that non-secret parts of commands are preserved."""
        entry_id = command_history.log(
            command="git push origin feature-branch --force",
            command_type="git",
            outcome="success",
        )

        entry = command_history.get(entry_id)

        # Non-secret parts should be preserved
        assert "git push origin feature-branch --force" in entry.command

    def test_get_raw_command_requires_permission(self, command_history):
        """Test that getting the raw (unredacted) command requires explicit permission."""
        entry_id = command_history.log(
            command="curl -H 'Authorization: Bearer secret123456789012345678901234567890'",
            command_type="api",
            outcome="success",
        )

        # Normal get returns redacted
        entry = command_history.get(entry_id)
        assert "secret123456789012345678901234567890" not in entry.command

        # Raw access (if implemented) would be restricted or separate
        # This tests that the default behavior is safe

    def test_redaction_is_consistent(self, command_history):
        """Test that same secret gets same redaction across multiple logs."""
        secret = "my_super_secret_api_key_12345678901234567890"

        id1 = command_history.log(
            command=f"cmd1 --token={secret}",
            command_type="test",
            outcome="success",
        )
        id2 = command_history.log(
            command=f"cmd2 --token={secret}",
            command_type="test",
            outcome="success",
        )

        entry1 = command_history.get(id1)
        entry2 = command_history.get(id2)

        # Both should have the secret redacted
        assert secret not in entry1.command
        assert secret not in entry2.command


# =============================================================================
# TestCommandHistoryStats - Statistics and aggregation
# =============================================================================


class TestCommandHistoryStats:
    """Tests for command history statistics."""

    def test_get_stats_returns_summary(self, command_history):
        """Test that get_stats returns a summary of command history."""
        command_history.log(command="git status", command_type="git", outcome="success")
        command_history.log(command="pytest tests/", command_type="test", outcome="success")
        command_history.log(command="pytest tests/", command_type="test", outcome="failure")

        stats = command_history.get_stats()

        assert "total_commands" in stats
        assert stats["total_commands"] == 3
        assert "by_type" in stats
        assert stats["by_type"]["git"] == 1
        assert stats["by_type"]["test"] == 2
        assert "by_outcome" in stats
        assert stats["by_outcome"]["success"] == 2
        assert stats["by_outcome"]["failure"] == 1

    def test_get_success_rate(self, command_history):
        """Test calculating success rate."""
        # 3 successes, 1 failure = 75% success rate
        command_history.log(command="cmd1", command_type="test", outcome="success")
        command_history.log(command="cmd2", command_type="test", outcome="success")
        command_history.log(command="cmd3", command_type="test", outcome="success")
        command_history.log(command="cmd4", command_type="test", outcome="failure")

        stats = command_history.get_stats()

        assert stats["success_rate"] == 0.75

    def test_get_stats_by_feature(self, command_history):
        """Test getting stats broken down by feature."""
        command_history.log(
            command="cmd1", command_type="test", outcome="success", feature_id="feature-a"
        )
        command_history.log(
            command="cmd2", command_type="test", outcome="failure", feature_id="feature-a"
        )
        command_history.log(
            command="cmd3", command_type="test", outcome="success", feature_id="feature-b"
        )

        stats = command_history.get_stats(by_feature=True)

        assert "by_feature" in stats
        assert stats["by_feature"]["feature-a"]["total"] == 2
        assert stats["by_feature"]["feature-b"]["total"] == 1


# =============================================================================
# TestEdgeCases - Edge cases and error handling
# =============================================================================


class TestCommandHistoryEdgeCases:
    """Edge case and error handling tests for CommandHistory."""

    def test_log_empty_command(self, command_history):
        """Test logging an empty command."""
        entry_id = command_history.log(
            command="",
            command_type="unknown",
            outcome="success",
        )

        entry = command_history.get(entry_id)
        assert entry.command == ""

    def test_log_very_long_command(self, command_history):
        """Test logging a very long command."""
        long_command = "x" * 10000

        entry_id = command_history.log(
            command=long_command,
            command_type="test",
            outcome="success",
        )

        entry = command_history.get(entry_id)
        # Should either truncate or store full command
        assert len(entry.command) > 0

    def test_log_unicode_command(self, command_history):
        """Test logging a command with unicode characters."""
        entry_id = command_history.log(
            command="echo 'Hello, World!'",
            command_type="shell",
            outcome="success",
        )

        entry = command_history.get(entry_id)
        assert "Hello, World!" in entry.command

    def test_corrupted_store_file_handled(self, temp_history_path):
        """Test that corrupted store file is handled gracefully."""
        from swarm_attack.logging.command_history import CommandHistory

        # Create corrupted JSON file
        temp_history_path.parent.mkdir(parents=True, exist_ok=True)
        temp_history_path.write_text("{ invalid json }")

        # Should not crash, just return empty history
        history = CommandHistory.load(store_path=temp_history_path)
        results = history.search()
        assert results == []

    def test_concurrent_access_safety(self, temp_history_path):
        """Test basic thread safety hint - actual implementation may vary."""
        from swarm_attack.logging.command_history import CommandHistory

        # This test documents expected behavior for concurrent access
        # Implementation might use file locking or other mechanisms
        history = CommandHistory(store_path=temp_history_path)

        # Multiple rapid logs should all succeed
        ids = []
        for i in range(100):
            id = history.log(
                command=f"cmd-{i}",
                command_type="test",
                outcome="success",
            )
            ids.append(id)

        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_special_characters_in_command(self, command_history):
        """Test commands with special characters."""
        entry_id = command_history.log(
            command="echo 'test' | grep -E '^test$' && echo \"done\"",
            command_type="shell",
            outcome="success",
        )

        entry = command_history.get(entry_id)
        assert "grep -E '^test$'" in entry.command


# =============================================================================
# Integration Tests
# =============================================================================


class TestCommandHistoryIntegration:
    """Integration tests for CommandHistory."""

    def test_full_workflow(self, temp_history_path):
        """Test a complete workflow: log, search, link, save, load."""
        from swarm_attack.logging.command_history import CommandHistory

        # Create and use history
        history = CommandHistory(store_path=temp_history_path)

        # Log test command
        test_id = history.log(
            command="pytest tests/ -v",
            command_type="test",
            outcome="success",
            feature_id="new-feature",
        )

        # Log commit with link
        commit_id = history.log(
            command="git commit -m 'Add tests'",
            command_type="git",
            outcome="success",
            feature_id="new-feature",
            git_sha="abc123def",
        )

        # Link test to same commit
        history.link_to_commit(test_id, "abc123def")

        # Save
        history.save()

        # Load fresh
        history2 = CommandHistory.load(store_path=temp_history_path)

        # Verify search
        feature_commands = history2.search(feature_id="new-feature")
        assert len(feature_commands) == 2

        commit_commands = history2.search(git_sha="abc123def")
        assert len(commit_commands) == 2

        # Verify stats
        stats = history2.get_stats()
        assert stats["total_commands"] == 2
        assert stats["success_rate"] == 1.0

    def test_workflow_with_failures(self, command_history):
        """Test workflow including failure handling."""
        # First test fails
        fail_id = command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="failure",
            reasoning="ImportError in test_module",
            feature_id="buggy-feature",
        )

        # Fix applied
        fix_id = command_history.log(
            command="python fix_import.py",
            command_type="script",
            outcome="success",
            feature_id="buggy-feature",
        )

        # Re-test passes
        pass_id = command_history.log(
            command="pytest tests/",
            command_type="test",
            outcome="success",
            feature_id="buggy-feature",
        )

        # Search for feature history
        history = command_history.search(feature_id="buggy-feature")
        assert len(history) == 3

        # Verify outcome distribution
        outcomes = [h.outcome for h in history]
        assert outcomes.count("success") == 2
        assert outcomes.count("failure") == 1
