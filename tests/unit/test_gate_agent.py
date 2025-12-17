"""Tests for LLM-adaptive gate agent."""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.agents.gate import (
    GateAgent,
    GateResult,
    GATE_SYSTEM_PROMPT,
)
from swarm_attack.config import SwarmConfig


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.claude = MagicMock()
    config.claude.binary = "claude"
    config.claude.max_turns = 10
    return config


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_passed_result(self):
        """Test creating a passed result."""
        result = GateResult(
            passed=True,
            language="python",
            test_count=5,
        )
        assert result.passed
        assert result.language == "python"
        assert result.test_count == 5
        assert result.errors == []
        assert result.commands_run == []

    def test_failed_result(self):
        """Test creating a failed result."""
        result = GateResult(
            passed=False,
            errors=["Test file not found"],
        )
        assert not result.passed
        assert "Test file not found" in result.errors

    def test_failure_factory(self):
        """Test the failure() factory method."""
        result = GateResult.failure("Something went wrong")
        assert not result.passed
        assert "Something went wrong" in result.errors

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = GateResult(
            passed=True,
            language="flutter",
            artifacts=[{"path": "test/widget_test.dart", "exists": True}],
            test_count=3,
            errors=[],
            commands_run=["flutter test --reporter expanded"],
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["language"] == "flutter"
        assert d["test_count"] == 3
        assert len(d["artifacts"]) == 1

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "passed": True,
            "language": "python",
            "artifacts": [{"path": "tests/test_foo.py", "exists": True}],
            "test_count": 10,
            "errors": [],
            "commands_run": ["pytest --collect-only"],
        }
        result = GateResult.from_dict(data)
        assert result.passed
        assert result.language == "python"
        assert result.test_count == 10

    def test_from_dict_missing_fields(self):
        """Test from_dict handles missing fields gracefully."""
        data = {"passed": False}
        result = GateResult.from_dict(data)
        assert not result.passed
        assert result.language is None
        assert result.test_count == 0
        assert result.errors == []


class TestGateSystemPrompt:
    """Tests for gate system prompt content."""

    def test_system_prompt_contains_language_detection(self):
        """System prompt should document language detection files."""
        assert "pubspec.yaml" in GATE_SYSTEM_PROMPT
        assert "package.json" in GATE_SYSTEM_PROMPT
        assert "pyproject.toml" in GATE_SYSTEM_PROMPT
        assert "go.mod" in GATE_SYSTEM_PROMPT
        assert "Cargo.toml" in GATE_SYSTEM_PROMPT

    def test_system_prompt_requires_json_output(self):
        """System prompt should specify JSON output format."""
        assert '"passed"' in GATE_SYSTEM_PROMPT
        assert '"language"' in GATE_SYSTEM_PROMPT
        assert '"test_count"' in GATE_SYSTEM_PROMPT
        assert '"artifacts"' in GATE_SYSTEM_PROMPT
        assert '"errors"' in GATE_SYSTEM_PROMPT

    def test_system_prompt_lists_tools(self):
        """System prompt should list available tools."""
        assert "Glob" in GATE_SYSTEM_PROMPT
        assert "Read" in GATE_SYSTEM_PROMPT
        assert "Bash" in GATE_SYSTEM_PROMPT

    def test_system_prompt_has_validation_rules(self):
        """System prompt should have validation rules."""
        assert "ALWAYS use tools to verify" in GATE_SYSTEM_PROMPT
        assert "never assume" in GATE_SYSTEM_PROMPT


class TestGateAgent:
    """Tests for GateAgent class."""

    def test_initialization(self, mock_config):
        """Test GateAgent initialization."""
        gate = GateAgent(mock_config, gate_name="test_gate")
        assert gate.name == "gate"
        assert gate.gate_name == "test_gate"
        assert gate.GATE_TOOLS == ["Glob", "Read", "Bash"]
        assert gate.MAX_GATE_TURNS == 5

    def test_build_validation_prompt(self, mock_config):
        """Test building validation prompt."""
        gate = GateAgent(mock_config)
        prompt = gate._build_validation_prompt({
            "feature_id": "my-feature",
            "issue_number": 42,
            "previous_agent": "test-writer",
            "project_root": "/repo",
            "expected_artifacts": ["test file"],
        })

        assert "my-feature" in prompt
        assert "42" in prompt
        assert "test-writer" in prompt
        assert "/repo" in prompt
        assert GATE_SYSTEM_PROMPT in prompt

    def test_build_validation_prompt_with_test_path(self, mock_config):
        """Test that explicit test_path is included in prompt."""
        gate = GateAgent(mock_config)
        prompt = gate._build_validation_prompt({
            "feature_id": "my-feature",
            "issue_number": 1,
            "previous_agent": "test-writer",
            "project_root": "/repo",
            "test_path": "/repo/tests/generated/my-feature/test_issue_1.py",
        })

        assert "/repo/tests/generated/my-feature/test_issue_1.py" in prompt

    def test_parse_llm_result_success(self, mock_config):
        """Test parsing successful LLM result."""
        gate = GateAgent(mock_config)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = '{"passed": true, "language": "flutter", "test_count": 3}'

        result = gate._parse_llm_result(mock_result)

        assert result.passed
        assert result.language == "flutter"
        assert result.test_count == 3

    def test_parse_llm_result_with_surrounding_text(self, mock_config):
        """Test parsing LLM result with JSON embedded in text."""
        gate = GateAgent(mock_config)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = '''I found the test file and validated it.

{"passed": true, "language": "python", "test_count": 5, "artifacts": [{"path": "tests/test_foo.py", "exists": true}]}

The validation is complete.'''

        result = gate._parse_llm_result(mock_result)

        assert result.passed
        assert result.language == "python"
        assert result.test_count == 5

    def test_parse_llm_result_failure(self, mock_config):
        """Test parsing failed LLM invocation."""
        gate = GateAgent(mock_config)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Agent timed out"

        result = gate._parse_llm_result(mock_result)

        assert not result.passed
        assert "Agent timed out" in result.errors

    def test_parse_llm_result_no_json(self, mock_config):
        """Test parsing result with no JSON."""
        gate = GateAgent(mock_config)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "I couldn't find any test files."

        result = gate._parse_llm_result(mock_result)

        assert not result.passed
        assert any("No JSON found" in e for e in result.errors)

    def test_parse_llm_result_malformed_json(self, mock_config):
        """Test parsing result with malformed JSON."""
        gate = GateAgent(mock_config)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = '{"passed": true, "language": python}'  # missing quotes

        result = gate._parse_llm_result(mock_result)

        assert not result.passed
        assert any("Failed to parse" in e for e in result.errors)

    def test_run_returns_agent_result(self, mock_config):
        """Test that run() returns AgentResult."""
        gate = GateAgent(mock_config)

        with patch.object(gate, 'validate') as mock_validate:
            mock_validate.return_value = GateResult(
                passed=True,
                language="python",
                test_count=5,
            )

            result = gate.run({
                "feature_id": "test",
                "issue_number": 1,
            })

            assert result.success
            assert result.output["passed"] is True
            assert result.output["language"] == "python"

    def test_run_handles_validation_failure(self, mock_config):
        """Test run() handles validation failure."""
        gate = GateAgent(mock_config)

        with patch.object(gate, 'validate') as mock_validate:
            mock_validate.return_value = GateResult(
                passed=False,
                errors=["Test file not found"],
            )

            result = gate.run({
                "feature_id": "test",
                "issue_number": 1,
            })

            assert not result.success
            assert "Test file not found" in result.errors


class TestGateAgentValidate:
    """Integration-style tests for validate() method."""

    def test_validate_calls_llm_with_correct_params(self, mock_config):
        """Test that validate() calls LLM with correct parameters."""
        mock_llm_runner = MagicMock()
        mock_llm_result = MagicMock()
        mock_llm_result.success = True
        mock_llm_result.output = '{"passed": true, "language": "python", "test_count": 3}'
        mock_llm_result.cost_usd = 0.001
        mock_llm_runner.run.return_value = mock_llm_result

        gate = GateAgent(mock_config, llm_runner=mock_llm_runner)

        result = gate.validate({
            "feature_id": "my-feature",
            "issue_number": 1,
            "previous_agent": "test-writer",
            "project_root": "/repo",
        })

        # Verify LLM was called with correct parameters
        mock_llm_runner.run.assert_called_once()
        call_kwargs = mock_llm_runner.run.call_args[1]
        assert call_kwargs["max_turns"] == 5
        assert call_kwargs["allowed_tools"] == ["Glob", "Read", "Bash"]
        assert call_kwargs["timeout"] == 60

        # Verify result
        assert result.passed
        assert result.language == "python"

    def test_validate_handles_exception(self, mock_config):
        """Test that validate() handles exceptions gracefully."""
        mock_llm_runner = MagicMock()
        mock_llm_runner.run.side_effect = Exception("Connection failed")

        gate = GateAgent(mock_config, llm_runner=mock_llm_runner)

        result = gate.validate({
            "feature_id": "my-feature",
            "issue_number": 1,
        })

        assert not result.passed
        assert any("Connection failed" in e for e in result.errors)

    def test_validate_tracks_cost(self, mock_config):
        """Test that validate() tracks LLM cost."""
        mock_llm_runner = MagicMock()
        mock_llm_result = MagicMock()
        mock_llm_result.success = True
        mock_llm_result.output = '{"passed": true, "language": "python", "test_count": 3}'
        mock_llm_result.cost_usd = 0.0005
        mock_llm_runner.run.return_value = mock_llm_result

        gate = GateAgent(mock_config, llm_runner=mock_llm_runner)

        gate.validate({
            "feature_id": "my-feature",
            "issue_number": 1,
        })

        assert gate.get_total_cost() == 0.0005


class TestGateAgentPostCoder:
    """Tests for post-coder gate validation context."""

    def test_gate_can_handle_coder_context(self, mock_config):
        """Test that gate can process context from coder output."""
        mock_llm_runner = MagicMock()
        mock_llm_result = MagicMock()
        mock_llm_result.success = True
        mock_llm_result.output = '{"passed": true, "language": "python", "test_count": 5}'
        mock_llm_result.cost_usd = 0.001
        mock_llm_runner.run.return_value = mock_llm_result

        gate = GateAgent(mock_config, llm_runner=mock_llm_runner, gate_name="post_coder_gate")

        # Simulate post-coder context with implementation files
        result = gate.validate({
            "feature_id": "my-feature",
            "issue_number": 1,
            "previous_agent": "coder",
            "expected_artifacts": ["implementation file", "passing tests"],
            "project_root": "/repo",
            "test_path": "/repo/tests/test_foo.py",
            "impl_files": ["/repo/src/foo.py"],
        })

        assert result.passed
        assert result.language == "python"
        assert result.test_count == 5

    def test_gate_builds_prompt_for_post_coder(self, mock_config):
        """Test that validation prompt includes coder context."""
        gate = GateAgent(mock_config, gate_name="post_coder_gate")

        prompt = gate._build_validation_prompt({
            "feature_id": "my-feature",
            "issue_number": 42,
            "previous_agent": "coder",
            "expected_artifacts": ["implementation file"],
            "project_root": "/repo",
            "impl_files": ["/repo/src/impl.py"],
        })

        assert "coder" in prompt
        assert "42" in prompt
        assert "my-feature" in prompt

    def test_post_coder_gate_different_name(self, mock_config):
        """Test that post_coder_gate has different name from pre_coder gate."""
        pre_gate = GateAgent(mock_config, gate_name="pre_coder_gate")
        post_gate = GateAgent(mock_config, gate_name="post_coder_gate")

        assert pre_gate.gate_name == "pre_coder_gate"
        assert post_gate.gate_name == "post_coder_gate"
        # Both should have same base name
        assert pre_gate.name == "gate"
        assert post_gate.name == "gate"
