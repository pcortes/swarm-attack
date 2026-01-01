"""
Unit tests for BugFixerAgent.

Tests the intelligent fix application agent that uses Claude CLI
to apply fix plans instead of dumb string replacement.
"""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.agents.bug_fixer import BugFixerAgent, BugFixerResult
from swarm_attack.bug_models import FileChange, FixPlan, TestCase
from swarm_attack.config import (
    ClaudeConfig,
    GitConfig,
    GitHubConfig,
    SessionConfig,
    SpecDebateConfig,
    SwarmConfig,
    TestRunnerConfig,
)


@pytest.fixture
def config(tmp_path: Path) -> SwarmConfig:
    """Create a test config with temporary repo root."""
    return SwarmConfig(
        repo_root=str(tmp_path),
        specs_dir="specs",
        swarm_dir=".swarm",
        github=GitHubConfig(repo="test/repo"),
        claude=ClaudeConfig(),
        spec_debate=SpecDebateConfig(),
        sessions=SessionConfig(),
        tests=TestRunnerConfig(command="pytest"),
        git=GitConfig(),
    )


@pytest.fixture
def sample_fix_plan() -> FixPlan:
    """Create a sample fix plan for testing."""
    return FixPlan(
        summary="Fix missing blank line between function and class",
        changes=[
            FileChange(
                file_path="swarm_attack/cli.py",
                change_type="modify",
                current_code="""def helper():
    pass
app = typer.Typer()""",
                proposed_code="""def helper():
    pass


app = typer.Typer()""",
                explanation="Add blank line between function and module-level code",
            )
        ],
        test_cases=[
            TestCase(
                name="test_import_succeeds",
                description="Verify module imports without syntax errors",
                test_code="import swarm_attack.cli; print('OK')",
            )
        ],
        risk_level="low",
        risk_explanation="Simple formatting fix",
    )


@pytest.fixture
def skill_file(config: SwarmConfig) -> Path:
    """Create the bug-fixer skill file in the test config's repo root."""
    skill_dir = Path(config.repo_root) / ".claude" / "skills" / "bug-fixer"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("""# Bug Fixer Agent

You are a Bug Fixer Agent. Your job is to apply a fix plan to the codebase.

## CRITICAL INSTRUCTIONS

### 1. READ FILES FIRST
Before making ANY changes, use the Read tool to read each file.

### 2. USE THE EDIT TOOL (NOT STRING REPLACE)
The Edit tool is smarter than string replacement.
Do NOT attempt to manually replace strings.

### 3. ENSURE PROPER FORMATTING
Ensure your changes add blank lines between definitions.

### 4. VALIDATE SYNTAX
After applying changes, verify syntax.

## Fix Plan

{fix_plan_markdown}

## Instructions

Apply the fix plan above.
""")
    return skill_path


@pytest.fixture
def agent(config: SwarmConfig, skill_file: Path) -> BugFixerAgent:
    """Create a BugFixerAgent instance with skill file available."""
    return BugFixerAgent(config)


class TestBugFixerAgentInit:
    """Tests for BugFixerAgent initialization."""

    def test_agent_has_name(self, agent: BugFixerAgent) -> None:
        """Agent should have name 'bug_fixer'."""
        assert agent.name == "bug_fixer"

    def test_agent_inherits_from_base(self, agent: BugFixerAgent) -> None:
        """Agent should inherit from BaseAgent."""
        from swarm_attack.agents.base import BaseAgent
        assert isinstance(agent, BaseAgent)


class TestBugFixerRun:
    """Tests for the main run() method."""

    def test_run_requires_fix_plan(self, agent: BugFixerAgent) -> None:
        """Run should fail if fix_plan is not provided."""
        result = agent.run({})
        assert not result.success
        assert "fix_plan" in result.errors[0].lower()

    def test_run_requires_bug_id(
        self, agent: BugFixerAgent, sample_fix_plan: FixPlan
    ) -> None:
        """Run should fail if bug_id is not provided."""
        result = agent.run({"fix_plan": sample_fix_plan})
        assert not result.success
        assert "bug_id" in result.errors[0].lower()

    @patch.object(BugFixerAgent, "_call_claude_cli")
    def test_run_calls_claude_cli(
        self,
        mock_cli: MagicMock,
        agent: BugFixerAgent,
        sample_fix_plan: FixPlan,
        config: SwarmConfig,
    ) -> None:
        """Run should invoke Claude CLI with the fix plan context."""
        # Setup mock
        mock_cli.return_value = {
            "result": json.dumps({
                "success": True,
                "files_changed": ["swarm_attack/cli.py"],
                "syntax_verified": True,
            })
        }

        # Create the file to modify
        target_file = Path(config.repo_root) / "swarm_attack" / "cli.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("""def helper():
    pass
app = typer.Typer()""")

        result = agent.run({
            "fix_plan": sample_fix_plan,
            "bug_id": "test-bug-001",
        })

        # Verify CLI was called
        assert mock_cli.called
        prompt = mock_cli.call_args[0][0]
        assert "swarm_attack/cli.py" in prompt
        assert "blank line" in prompt.lower() or "formatting" in prompt.lower()

    @patch.object(BugFixerAgent, "_call_claude_cli")
    def test_run_returns_files_changed(
        self,
        mock_cli: MagicMock,
        agent: BugFixerAgent,
        sample_fix_plan: FixPlan,
        config: SwarmConfig,
    ) -> None:
        """Run should return list of files changed."""
        mock_cli.return_value = {
            "result": json.dumps({
                "success": True,
                "files_changed": ["swarm_attack/cli.py"],
                "syntax_verified": True,
            })
        }

        target_file = Path(config.repo_root) / "swarm_attack" / "cli.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("original content")

        result = agent.run({
            "fix_plan": sample_fix_plan,
            "bug_id": "test-bug-001",
        })

        assert result.success
        assert "files_changed" in result.output
        assert "swarm_attack/cli.py" in result.output["files_changed"]

    @patch.object(BugFixerAgent, "_call_claude_cli")
    def test_run_validates_syntax(
        self,
        mock_cli: MagicMock,
        agent: BugFixerAgent,
        sample_fix_plan: FixPlan,
        config: SwarmConfig,
    ) -> None:
        """Run should verify syntax after changes."""
        mock_cli.return_value = {
            "result": json.dumps({
                "success": True,
                "files_changed": ["swarm_attack/cli.py"],
                "syntax_verified": True,
            })
        }

        target_file = Path(config.repo_root) / "swarm_attack" / "cli.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("original content")

        result = agent.run({
            "fix_plan": sample_fix_plan,
            "bug_id": "test-bug-001",
        })

        assert result.success
        assert result.output.get("syntax_verified") is True


class TestBugFixerPromptBuilding:
    """Tests for prompt building."""

    def test_build_prompt_includes_fix_plan(
        self, agent: BugFixerAgent, sample_fix_plan: FixPlan
    ) -> None:
        """Prompt should include the fix plan details."""
        prompt = agent._build_prompt(sample_fix_plan, "test-bug-001")

        # Should include file path
        assert "swarm_attack/cli.py" in prompt

        # Should include change type
        assert "modify" in prompt.lower()

        # Should include current and proposed code
        assert "def helper():" in prompt
        assert "pass" in prompt

    def test_build_prompt_includes_instructions(
        self, agent: BugFixerAgent, sample_fix_plan: FixPlan
    ) -> None:
        """Prompt should include instructions to read files first."""
        prompt = agent._build_prompt(sample_fix_plan, "test-bug-001")

        # Should instruct to read files
        assert "read" in prompt.lower()

        # Should instruct about formatting
        assert "formatting" in prompt.lower() or "blank line" in prompt.lower()

        # Should instruct about syntax validation
        assert "syntax" in prompt.lower() or "validate" in prompt.lower()

    def test_build_prompt_warns_against_string_replace(
        self, agent: BugFixerAgent, sample_fix_plan: FixPlan
    ) -> None:
        """Prompt should warn against blind string replacement."""
        prompt = agent._build_prompt(sample_fix_plan, "test-bug-001")

        # Should contain warning about string replace
        assert "string" in prompt.lower() or "replace" in prompt.lower()


class TestClaudeCLIIntegration:
    """Tests for Claude CLI integration."""

    def test_call_claude_cli_subprocess(
        self, agent: BugFixerAgent, config: SwarmConfig
    ) -> None:
        """_call_claude_cli should invoke Claude CLI via subprocess."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"result": '{"success": true}'}),
                stderr="",
            )

            result = agent._call_claude_cli("test prompt")

            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Should call 'claude' binary
            assert call_args[0][0][0] == "claude"

            # Should include prompt
            assert "test prompt" in call_args[0][0]

            # Should have timeout
            assert "timeout" in call_args[1]

    def test_call_claude_cli_returns_parsed_json(
        self, agent: BugFixerAgent
    ) -> None:
        """_call_claude_cli should return parsed JSON response."""
        with patch("subprocess.run") as mock_run:
            expected_result = {"result": '{"success": true, "files_changed": []}'}
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(expected_result),
                stderr="",
            )

            result = agent._call_claude_cli("test prompt")

            assert result == expected_result

    def test_call_claude_cli_raises_on_failure(
        self, agent: BugFixerAgent
    ) -> None:
        """_call_claude_cli should raise on non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: authentication failed",
            )

            with pytest.raises(RuntimeError, match="Claude CLI failed"):
                agent._call_claude_cli("test prompt")

    def test_call_claude_cli_handles_timeout(
        self, agent: BugFixerAgent
    ) -> None:
        """_call_claude_cli should propagate timeout errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

            with pytest.raises(subprocess.TimeoutExpired):
                agent._call_claude_cli("test prompt")


class TestParseResult:
    """Tests for parsing Claude CLI response."""

    def test_parse_result_extracts_files_changed(
        self, agent: BugFixerAgent
    ) -> None:
        """Should extract files_changed from response."""
        response = {
            "result": json.dumps({
                "success": True,
                "files_changed": ["file1.py", "file2.py"],
                "syntax_verified": True,
            })
        }

        result = agent._parse_result(response)

        assert result.success is True
        assert result.files_changed == ["file1.py", "file2.py"]
        assert result.syntax_verified is True

    def test_parse_result_handles_failure(
        self, agent: BugFixerAgent
    ) -> None:
        """Should handle failure responses."""
        response = {
            "result": json.dumps({
                "success": False,
                "files_changed": [],
                "error": "Could not apply fix",
            })
        }

        result = agent._parse_result(response)

        assert result.success is False
        assert result.error == "Could not apply fix"

    def test_parse_result_handles_malformed_json(
        self, agent: BugFixerAgent
    ) -> None:
        """Should handle malformed JSON gracefully."""
        response = {"result": "not valid json"}

        result = agent._parse_result(response)

        assert result.success is False
        assert "parse" in result.error.lower() or "json" in result.error.lower()


class TestBugFixerResult:
    """Tests for BugFixerResult dataclass."""

    def test_result_has_required_fields(self) -> None:
        """Result should have all required fields."""
        result = BugFixerResult(
            success=True,
            files_changed=["file.py"],
            syntax_verified=True,
        )

        assert result.success is True
        assert result.files_changed == ["file.py"]
        assert result.syntax_verified is True
        assert result.error == ""

    def test_result_to_dict(self) -> None:
        """Result should be serializable to dict."""
        result = BugFixerResult(
            success=True,
            files_changed=["file.py"],
            syntax_verified=True,
            error="",
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["files_changed"] == ["file.py"]


class TestSkillPrompt:
    """Tests for skill prompt loading."""

    def test_load_skill_prompt(
        self, agent: BugFixerAgent, config: SwarmConfig
    ) -> None:
        """Should load skill prompt from SKILL.md."""
        skill_dir = Path(config.repo_root) / ".claude" / "skills" / "bug-fixer"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# Bug Fixer Skill\n\nTest content")

        prompt = agent._load_skill_prompt()

        assert "Bug Fixer" in prompt

    def test_skill_prompt_not_found_raises(
        self, config: SwarmConfig
    ) -> None:
        """Should raise if skill prompt not found."""
        from swarm_attack.agents.base import SkillNotFoundError

        # Create agent WITHOUT the skill_file fixture to test missing file case
        agent_without_skill = BugFixerAgent(config)

        with pytest.raises(SkillNotFoundError):
            agent_without_skill._load_skill_prompt()
