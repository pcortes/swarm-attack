"""Tests for SubAgentRunner - spawns sub-agents using Claude CLI.

TDD tests for Issue #3: Create SubAgentRunner for Librarian spawning.
"""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sub_agent import SubAgentResult, SubAgentRunner


class TestSubAgentResult:
    """Tests for SubAgentResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = SubAgentResult(
            success=True,
            output="Task completed",
            cost_usd=0.05,
            error=None,
        )
        assert result.success is True
        assert result.output == "Task completed"
        assert result.cost_usd == 0.05
        assert result.error is None

    def test_create_failure_result(self):
        """Test creating a failure result."""
        result = SubAgentResult(
            success=False,
            output="",
            cost_usd=0.0,
            error="Timeout occurred",
        )
        assert result.success is False
        assert result.output == ""
        assert result.error == "Timeout occurred"

    def test_default_values(self):
        """Test default field values."""
        result = SubAgentResult(success=True, output="test")
        assert result.cost_usd == 0.0
        assert result.error is None

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = SubAgentResult(
            success=True,
            output="output text",
            cost_usd=0.10,
            error=None,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "output text"
        assert d["cost_usd"] == 0.10
        assert d["error"] is None

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "success": False,
            "output": "partial output",
            "cost_usd": 0.02,
            "error": "Connection lost",
        }
        result = SubAgentResult.from_dict(data)
        assert result.success is False
        assert result.output == "partial output"
        assert result.cost_usd == 0.02
        assert result.error == "Connection lost"

    def test_from_dict_defaults(self):
        """Test deserialization with missing optional fields."""
        data = {"success": True, "output": "minimal"}
        result = SubAgentResult.from_dict(data)
        assert result.cost_usd == 0.0
        assert result.error is None

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = SubAgentResult(
            success=True,
            output="roundtrip test",
            cost_usd=0.15,
            error=None,
        )
        roundtrip = SubAgentResult.from_dict(original.to_dict())
        assert roundtrip.success == original.success
        assert roundtrip.output == original.output
        assert roundtrip.cost_usd == original.cost_usd
        assert roundtrip.error == original.error


class TestSubAgentRunner:
    """Tests for SubAgentRunner class."""

    @pytest.fixture
    def mock_config(self):
        """Config fixture for tests."""
        return {
            "claude": {
                "binary": "claude",
                "timeout_seconds": 120,
                "max_turns": 5,
            }
        }

    @pytest.fixture
    def mock_skill_loader(self):
        """Mock skill loader fixture."""
        loader = MagicMock()
        loader.load_skill.return_value = MagicMock(
            content="You are a {role}. Do {task}.",
            metadata={"max_turns": 3},
        )
        return loader

    def test_init(self, mock_config, mock_skill_loader):
        """Test SubAgentRunner initialization."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        assert runner.config == mock_config
        assert runner.skill_loader == mock_skill_loader

    def test_inject_context_single_placeholder(self, mock_config, mock_skill_loader):
        """Test context injection with single placeholder."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        prompt = "Hello {name}!"
        context = {"name": "World"}
        result = runner._inject_context(prompt, context)
        assert result == "Hello World!"

    def test_inject_context_multiple_placeholders(self, mock_config, mock_skill_loader):
        """Test context injection with multiple placeholders."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        prompt = "Task: {task}, Role: {role}, Project: {project}"
        context = {"task": "analyze", "role": "engineer", "project": "swarm"}
        result = runner._inject_context(prompt, context)
        assert result == "Task: analyze, Role: engineer, Project: swarm"

    def test_inject_context_no_placeholders(self, mock_config, mock_skill_loader):
        """Test context injection with no placeholders."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        prompt = "Static prompt with no variables"
        context = {"unused": "value"}
        result = runner._inject_context(prompt, context)
        assert result == "Static prompt with no variables"

    def test_inject_context_missing_placeholder(self, mock_config, mock_skill_loader):
        """Test context injection leaves missing placeholders unchanged."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        prompt = "Hello {name}, your {role} is ready"
        context = {"name": "Alice"}  # missing "role"
        result = runner._inject_context(prompt, context)
        assert result == "Hello Alice, your {role} is ready"

    def test_inject_context_empty_context(self, mock_config, mock_skill_loader):
        """Test context injection with empty context dict."""
        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        prompt = "Hello {name}!"
        context = {}
        result = runner._inject_context(prompt, context)
        assert result == "Hello {name}!"

    @patch("subprocess.run")
    def test_spawn_success(self, mock_run, mock_config, mock_skill_loader):
        """Test successful spawn execution."""
        # Mock successful subprocess
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "Task completed successfully",
                "total_cost_usd": 0.05,
                "num_turns": 2,
            }),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(
            skill_name="librarian",
            context={"role": "researcher", "task": "find docs"},
        )

        assert result.success is True
        assert result.output == "Task completed successfully"
        assert result.cost_usd == 0.05
        assert result.error is None

    @patch("subprocess.run")
    def test_spawn_loads_skill(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn loads skill from skill_loader."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "done", "total_cost_usd": 0.01}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={})

        mock_skill_loader.load_skill.assert_called_once_with("librarian")

    @patch("subprocess.run")
    def test_spawn_injects_context(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn injects context into skill prompt."""
        mock_skill_loader.load_skill.return_value = MagicMock(
            content="Find {topic} in {source}",
            metadata={},
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "found", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(
            skill_name="librarian",
            context={"topic": "Python patterns", "source": "codebase"},
        )

        # Verify the command includes the interpolated prompt
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # The prompt should be the last argument after --
        prompt_arg = cmd[-1]
        assert "Python patterns" in prompt_arg
        assert "codebase" in prompt_arg

    @patch("subprocess.run")
    def test_spawn_uses_default_timeout(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn uses default timeout of 120 seconds."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "ok", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={})

        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 120

    @patch("subprocess.run")
    def test_spawn_custom_timeout(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn accepts custom timeout."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "ok", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={}, timeout=60)

        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 60

    @patch("subprocess.run")
    def test_spawn_handles_timeout(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn handles subprocess timeout gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(skill_name="librarian", context={})

        assert result.success is False
        assert result.output == ""
        assert "timeout" in result.error.lower()

    @patch("subprocess.run")
    def test_spawn_handles_nonzero_exit(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn handles non-zero exit code."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Claude CLI error: invalid arguments",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(skill_name="librarian", context={})

        assert result.success is False
        assert "invalid arguments" in result.error

    @patch("subprocess.run")
    def test_spawn_handles_invalid_json(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn handles non-JSON output gracefully."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Not valid JSON output",
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(skill_name="librarian", context={})

        # Should still succeed but output might be raw text
        assert result.success is True
        assert "Not valid JSON output" in result.output

    @patch("subprocess.run")
    def test_spawn_parses_json_output(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn parses JSON output from Claude CLI."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "Analyzed codebase",
                "total_cost_usd": 0.12,
                "num_turns": 4,
                "session_id": "test-session-123",
            }),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(skill_name="librarian", context={})

        assert result.success is True
        assert result.output == "Analyzed codebase"
        assert result.cost_usd == 0.12

    @patch("subprocess.run")
    def test_spawn_uses_max_turns_from_skill_metadata(
        self, mock_run, mock_config, mock_skill_loader
    ):
        """Test spawn uses max_turns from skill metadata if available."""
        mock_skill_loader.load_skill.return_value = MagicMock(
            content="Skill prompt",
            metadata={"max_turns": 8},
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "ok", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={})

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # Check --max-turns is in command
        assert "--max-turns" in cmd
        max_turns_idx = cmd.index("--max-turns")
        assert cmd[max_turns_idx + 1] == "8"

    @patch("subprocess.run")
    def test_spawn_uses_default_max_turns(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn uses config max_turns when not in skill metadata."""
        mock_skill_loader.load_skill.return_value = MagicMock(
            content="Skill prompt",
            metadata={},  # No max_turns in metadata
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "ok", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={})

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--max-turns" in cmd
        max_turns_idx = cmd.index("--max-turns")
        assert cmd[max_turns_idx + 1] == "5"  # from mock_config

    @patch("subprocess.run")
    def test_spawn_builds_correct_command(self, mock_run, mock_config, mock_skill_loader):
        """Test spawn builds correct Claude CLI command."""
        mock_skill_loader.load_skill.return_value = MagicMock(
            content="Test prompt",
            metadata={},
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"result": "ok", "total_cost_usd": 0.0}),
            stderr="",
        )

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        runner.spawn(skill_name="librarian", context={})

        call_args = mock_run.call_args
        cmd = call_args[0][0]

        # Verify command structure
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        output_fmt_idx = cmd.index("--output-format")
        assert cmd[output_fmt_idx + 1] == "json"
        assert "--max-turns" in cmd

    def test_spawn_handles_skill_not_found(self, mock_config, mock_skill_loader):
        """Test spawn handles skill not found error."""
        from src.sub_agent import SubAgentError

        mock_skill_loader.load_skill.side_effect = Exception("Skill 'invalid' not found")

        runner = SubAgentRunner(config=mock_config, skill_loader=mock_skill_loader)
        result = runner.spawn(skill_name="invalid", context={})

        assert result.success is False
        assert "not found" in result.error.lower() or "invalid" in result.error.lower()


class TestSubAgentRunnerIntegration:
    """Integration-style tests for SubAgentRunner (still mocked subprocess)."""

    @pytest.fixture
    def real_config(self):
        """More realistic config fixture."""
        return {
            "claude": {
                "binary": "/usr/local/bin/claude",
                "timeout_seconds": 300,
                "max_turns": 10,
            }
        }

    @patch("subprocess.run")
    def test_full_workflow(self, mock_run, real_config):
        """Test full workflow with skill loading and execution."""
        # Setup mock skill loader
        skill_loader = MagicMock()
        skill_loader.load_skill.return_value = MagicMock(
            content="Research {topic} and summarize findings for {audience}.",
            metadata={"max_turns": 5},
        )

        # Setup mock subprocess
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "Found 15 relevant documents on Python best practices.",
                "total_cost_usd": 0.08,
                "num_turns": 3,
            }),
            stderr="",
        )

        runner = SubAgentRunner(config=real_config, skill_loader=skill_loader)
        result = runner.spawn(
            skill_name="librarian",
            context={
                "topic": "Python best practices",
                "audience": "senior developers",
            },
            timeout=60,
        )

        # Verify result
        assert result.success is True
        assert "15 relevant documents" in result.output
        assert result.cost_usd == 0.08

        # Verify skill was loaded
        skill_loader.load_skill.assert_called_once_with("librarian")

        # Verify subprocess was called correctly
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        prompt = cmd[-1]  # Last argument after --
        assert "Python best practices" in prompt
        assert "senior developers" in prompt