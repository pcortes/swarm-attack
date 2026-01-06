"""Unit tests for SemanticTesterAgent (TDD)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import will fail until implementation exists - that's TDD!
try:
    from swarm_attack.qa.agents.semantic_tester import (
        SemanticTesterAgent,
        SemanticTestResult,
        SemanticVerdict,
        SemanticScope,
        Evidence,
        SemanticIssue,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="SemanticTesterAgent not yet implemented"
)


class TestEnums:
    """Test enum definitions."""

    def test_semantic_scope_values(self):
        assert SemanticScope.CHANGES_ONLY.value == "changes_only"
        assert SemanticScope.AFFECTED.value == "affected"
        assert SemanticScope.FULL_SYSTEM.value == "full_system"

    def test_semantic_verdict_values(self):
        assert SemanticVerdict.PASS.value == "PASS"
        assert SemanticVerdict.FAIL.value == "FAIL"
        assert SemanticVerdict.PARTIAL.value == "PARTIAL"


class TestEvidence:
    """Test Evidence dataclass."""

    def test_evidence_creation(self):
        evidence = Evidence(
            description="Test passed",
            source="pytest output",
            confidence=0.95,
        )
        assert evidence.description == "Test passed"
        assert evidence.source == "pytest output"
        assert evidence.confidence == 0.95
        assert evidence.details == {}

    def test_evidence_with_details(self):
        evidence = Evidence(
            description="Test",
            source="source",
            confidence=0.8,
            details={"key": "value"},
        )
        assert evidence.details == {"key": "value"}


class TestSemanticIssue:
    """Test SemanticIssue dataclass."""

    def test_issue_creation(self):
        issue = SemanticIssue(
            severity="critical",
            description="Bug found",
            location="src/main.py:42",
            suggestion="Fix the bug",
        )
        assert issue.severity == "critical"
        assert issue.description == "Bug found"
        assert issue.location == "src/main.py:42"
        assert issue.suggestion == "Fix the bug"


class TestSemanticTestResult:
    """Test SemanticTestResult dataclass."""

    def test_result_creation_minimal(self):
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        assert result.verdict == SemanticVerdict.PASS
        assert result.evidence == []
        assert result.issues == []
        assert result.recommendations == []

    def test_result_to_dict(self):
        evidence = Evidence("desc", "src", 0.9)
        issue = SemanticIssue("minor", "desc", "loc", "sug")
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            evidence=[evidence],
            issues=[issue],
            recommendations=["Fix it"],
        )
        d = result.to_dict()
        assert d["verdict"] == "FAIL"
        assert len(d["evidence"]) == 1
        assert len(d["issues"]) == 1
        assert d["recommendations"] == ["Fix it"]


class TestSemanticTesterAgentInit:
    """Test SemanticTesterAgent initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return config

    def test_agent_name(self, mock_config):
        agent = SemanticTesterAgent(mock_config)
        assert agent.name == "semantic_tester"

    def test_skill_name(self, mock_config):
        agent = SemanticTesterAgent(mock_config)
        assert agent.skill_name == "semantic-test"

    def test_loads_skill_prompt(self, mock_config, tmp_path):
        # Create skill file
        skill_dir = tmp_path / ".claude" / "skills" / "semantic-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test\n---\nCustom prompt")

        agent = SemanticTesterAgent(mock_config)
        assert "Custom prompt" in agent.skill_prompt


class TestBuildTestPrompt:
    """Test _build_test_prompt method."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_includes_changes(self, agent):
        context = {"changes": "def foo(): pass"}
        prompt = agent._build_test_prompt(context)
        assert "def foo(): pass" in prompt

    def test_includes_expected_behavior(self, agent):
        context = {"changes": "x", "expected_behavior": "Should work"}
        prompt = agent._build_test_prompt(context)
        assert "Should work" in prompt

    def test_includes_json_format(self, agent):
        context = {"changes": "x"}
        prompt = agent._build_test_prompt(context)
        assert '"verdict"' in prompt
        assert "PASS" in prompt


class TestParseTestOutput:
    """Test _parse_test_output method."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_parses_json_block(self, agent):
        output = '''Some text
```json
{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}
```
More text'''
        result = agent._parse_test_output(output)
        assert result.verdict == SemanticVerdict.PASS

    def test_parses_raw_json(self, agent):
        output = '{"verdict": "FAIL", "evidence": [], "issues": [], "recommendations": []}'
        result = agent._parse_test_output(output)
        assert result.verdict == SemanticVerdict.FAIL

    def test_handles_invalid_json(self, agent):
        output = "Not valid JSON at all"
        result = agent._parse_test_output(output)
        assert result.verdict == SemanticVerdict.PARTIAL


class TestRunMethod:
    """Test run() method."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_requires_changes_field(self, agent):
        result = agent.run({})
        assert result.success is False
        assert "changes" in result.errors[0].lower()

    @patch("subprocess.run")
    def test_returns_agent_result_on_success(self, mock_run, agent):
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}',
            stderr="",
        )
        result = agent.run({"changes": "code", "expected_behavior": "works"})
        assert result.success is True
        assert result.cost_usd == 0.0

    @patch("subprocess.run")
    def test_handles_cli_failure(self, mock_run, agent):
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="CLI error")
        result = agent.run({"changes": "code"})
        assert result.success is False
