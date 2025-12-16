"""
Tests for skill loading with YAML frontmatter parsing.

This tests the fix for Bug 1: YAML Frontmatter Tool Mismatch.
The issue was that IssueCreatorAgent ran with allowed_tools=[] but the
skill frontmatter declared 'allowed-tools: Read,Glob'. Claude would try
to use tools, burn through max_turns=1, and fail.

The fix moves frontmatter parsing to BaseAgent.load_skill_with_metadata()
so all agents can access tool permissions from frontmatter.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.agents.base import BaseAgent, AgentResult, SkillNotFoundError
from swarm_attack.config import SwarmConfig


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing abstract BaseAgent."""

    name = "test_agent"

    def run(self, context: dict) -> AgentResult:
        return AgentResult.success_result()


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create a mock config with temporary skills path."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = tmp_path
    config.skills_path = tmp_path / ".claude" / "skills"
    return config


@pytest.fixture
def agent(mock_config: SwarmConfig) -> ConcreteAgent:
    """Create a test agent with mock config."""
    return ConcreteAgent(config=mock_config)


class TestLoadSkillWithMetadata:
    """Tests for BaseAgent.load_skill_with_metadata()."""

    def test_method_exists(self, agent: ConcreteAgent):
        """BaseAgent must have load_skill_with_metadata method."""
        assert hasattr(agent, "load_skill_with_metadata")
        assert callable(agent.load_skill_with_metadata)

    def test_returns_tuple_of_content_and_metadata(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Method must return (content, metadata) tuple."""
        # Setup skill file
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
allowed-tools: Read,Glob
---

# Test Skill

Content here.
""")

        result = agent.load_skill_with_metadata("test-skill")

        assert isinstance(result, tuple)
        assert len(result) == 2
        content, metadata = result
        assert isinstance(content, str)
        assert isinstance(metadata, dict)

    def test_strips_frontmatter_from_content(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Content returned should not include frontmatter."""
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
allowed-tools: Read,Glob
---

# Test Skill

Content here.
""")

        content, _ = agent.load_skill_with_metadata("test-skill")

        # Content should NOT start with --- or contain frontmatter
        assert not content.startswith("---")
        assert "allowed-tools:" not in content
        assert "# Test Skill" in content
        assert "Content here." in content

    def test_parses_allowed_tools_from_frontmatter(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Metadata should include parsed allowed-tools."""
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
allowed-tools: Read,Glob,Bash
---

# Test Skill
""")

        _, metadata = agent.load_skill_with_metadata("test-skill")

        assert "allowed-tools" in metadata
        assert metadata["allowed-tools"] == "Read,Glob,Bash"

    def test_handles_missing_frontmatter(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Files without frontmatter should return empty metadata."""
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""# Test Skill

No frontmatter here.
""")

        content, metadata = agent.load_skill_with_metadata("test-skill")

        assert metadata == {}
        assert "# Test Skill" in content
        assert "No frontmatter here." in content

    def test_handles_empty_frontmatter(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Files with empty frontmatter should return empty metadata."""
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
---

# Test Skill
""")

        content, metadata = agent.load_skill_with_metadata("test-skill")

        assert metadata == {}
        assert "# Test Skill" in content

    def test_handles_invalid_yaml_frontmatter(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Invalid YAML should return empty metadata, not crash."""
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
invalid: yaml: syntax: [[[
---

# Test Skill
""")

        content, metadata = agent.load_skill_with_metadata("test-skill")

        # Should not crash, just return empty metadata
        assert metadata == {}
        assert "# Test Skill" in content

    def test_raises_skill_not_found_for_missing_skill(
        self, agent: ConcreteAgent, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Should raise SkillNotFoundError for non-existent skills."""
        with pytest.raises(SkillNotFoundError):
            agent.load_skill_with_metadata("nonexistent-skill")


class TestGetAllowedToolsFromMetadata:
    """Tests for BaseAgent.get_allowed_tools_from_metadata()."""

    def test_method_exists(self, agent: ConcreteAgent):
        """BaseAgent must have get_allowed_tools_from_metadata method."""
        assert hasattr(agent, "get_allowed_tools_from_metadata")
        assert callable(agent.get_allowed_tools_from_metadata)

    def test_parses_comma_separated_tools(self, agent: ConcreteAgent):
        """Should parse 'Read,Glob,Bash' into ['Read', 'Glob', 'Bash']."""
        metadata = {"allowed-tools": "Read,Glob,Bash"}

        tools = agent.get_allowed_tools_from_metadata(metadata)

        assert tools == ["Read", "Glob", "Bash"]

    def test_strips_whitespace_from_tools(self, agent: ConcreteAgent):
        """Should strip whitespace from tool names."""
        metadata = {"allowed-tools": "Read, Glob , Bash"}

        tools = agent.get_allowed_tools_from_metadata(metadata)

        assert tools == ["Read", "Glob", "Bash"]

    def test_returns_empty_list_for_missing_key(self, agent: ConcreteAgent):
        """Should return empty list if allowed-tools not in metadata."""
        metadata = {"name": "test-skill"}

        tools = agent.get_allowed_tools_from_metadata(metadata)

        assert tools == []

    def test_returns_empty_list_for_empty_metadata(self, agent: ConcreteAgent):
        """Should return empty list for empty metadata dict."""
        tools = agent.get_allowed_tools_from_metadata({})

        assert tools == []

    def test_handles_single_tool(self, agent: ConcreteAgent):
        """Should handle single tool without comma."""
        metadata = {"allowed-tools": "Read"}

        tools = agent.get_allowed_tools_from_metadata(metadata)

        assert tools == ["Read"]


class TestVerifierCollectionErrorDetection:
    """Tests for Verifier distinguishing collection errors from test failures.

    This tests the fix for Bug 3: False Regression Detection.
    The Verifier was misinterpreting collection errors (import failures)
    as test failures, causing false regression reports.
    """

    def test_parse_pytest_output_detects_collection_error(self):
        """Verifier must detect collection errors separately from test failures."""
        from swarm_attack.agents.verifier import VerifierAgent

        config = MagicMock(spec=SwarmConfig)
        config.repo_root = Path("/tmp")
        config.tests = MagicMock()
        config.tests.timeout_seconds = 60

        verifier = VerifierAgent(config=config)

        # Pytest output with collection error
        output = """
============================= test session starts =============================
platform darwin -- Python 3.11.0
collected 0 items / 1 error

================================== ERRORS =====================================
_____________ ERROR collecting tests/generated/foo/test_issue_2.py ____________
ImportError while importing test module '/tests/generated/foo/test_issue_2.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback (most recent call last):
ModuleNotFoundError: No module named 'foo'
=========================== short test summary info ===========================
ERROR tests/generated/foo/test_issue_2.py
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 error !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.05s ==============================
"""

        result = verifier._parse_pytest_output(output)

        # Must have errors field > 0 for collection errors
        assert result["errors"] > 0, "Collection errors must be tracked separately"
        # Tests failed should be 0 (no tests ran)
        assert result["tests_failed"] == 0, "Collection error != test failure"
        assert result["tests_run"] == 0, "No tests should have run"

    def test_distinguishes_collection_error_from_test_failure(self):
        """Collection error != test failure - they are different failure modes."""
        from swarm_attack.agents.verifier import VerifierAgent

        config = MagicMock(spec=SwarmConfig)
        config.repo_root = Path("/tmp")
        config.tests = MagicMock()
        config.tests.timeout_seconds = 60

        verifier = VerifierAgent(config=config)

        # Actual test failure output
        test_failure_output = """
============================= test session starts =============================
collected 3 items

tests/test_foo.py::test_one PASSED
tests/test_foo.py::test_two FAILED
tests/test_foo.py::test_three PASSED

================================= FAILURES ====================================
______________________________ test_two _______________________________________
    def test_two():
>       assert 1 == 2
E       assert 1 == 2
================================== short test summary info ====================
FAILED tests/test_foo.py::test_two - assert 1 == 2
============================= 1 failed, 2 passed in 0.10s =====================
"""

        result = verifier._parse_pytest_output(test_failure_output)

        assert result["tests_failed"] == 1, "Should have 1 test failure"
        assert result["tests_passed"] == 2, "Should have 2 passed tests"
        assert result["errors"] == 0, "Should have no collection errors"
        assert result["tests_run"] == 3, "Should have run 3 tests"
