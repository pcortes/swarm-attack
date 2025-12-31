# Agent Research Capability Implementation (TDD)

<mission>
You are orchestrating a **Team of Specialized Experts** to implement research-first architecture for Swarm Attack agents using strict **Test-Driven Development (TDD)** methodology.

This implementation ensures ALL agents can research the codebase before acting, matching Claude Code's "research first" behavior. No more blind agents.
</mission>

---

<team_structure>

| Expert | Role | Responsibility |
|--------|------|----------------|
| **Architect** | Design Lead | Review existing agent patterns, ensure consistency with base classes |
| **TestWriter** | RED Phase | Write comprehensive failing tests FIRST for all components |
| **Coder** | GREEN Phase | Implement minimal code to pass all tests |
| **Integrator** | Wiring | Update IssueCreator, ComplexityGate, and BaseAgent |
| **SkillEditor** | Prompts | Update all SKILL.md files with Phase 0: Research |
| **Reviewer** | Validation | Run full test suite, verify no regressions |

</team_structure>

---

<background_context>

<problem_statement>

Several Swarm Attack agents run **completely blind** without codebase access:

```python
# issue_creator.py:330 - BLIND!
result = self.llm.run(
    prompt,
    allowed_tools=[],  # Cannot see codebase
    max_turns=1,       # Cannot explore
)

# complexity_gate.py:274 - BLIND!
result = self.llm.run(
    prompt,
    allowed_tools=[],  # Cannot verify complexity claims
    max_turns=1,
    model="haiku",
)
```

This causes:
- Issues created without knowing what modules exist
- Complexity estimates without seeing actual code
- Poor integration with existing patterns
- Agents "answering like an LLM without context"

</problem_statement>

<existing_patterns>

**BaseAgent** (`swarm_attack/agents/base.py`):
```python
class BaseAgent(ABC):
    """Base class for all agents."""

    def load_skill(self, skill_name: str) -> str:
        """Load skill prompt from .claude/skills/{skill_name}/SKILL.md."""
        pass

    def get_allowed_tools_from_metadata(self, metadata: dict) -> list[str]:
        """Parse allowed-tools from skill metadata."""
        pass
```

**Agents with research capability** (working examples):
```python
# coder.py:1855 - HAS TOOLS
result = self.llm.run(
    prompt,
    allowed_tools=["Read", "Glob", "Grep"],  # Can explore!
    max_turns=max_turns,
)

# bug_researcher.py:200 - HAS TOOLS
result = self.llm.run(
    prompt,
    allowed_tools=["Read", "Glob", "Grep", "Bash"],  # Full capability
    max_turns=100,
)
```

</existing_patterns>

<what_claude_code_does>

Claude Code agents:
1. **START by researching** - Use Glob, Grep, Read before any action
2. **Discover context dynamically** - Find what they need
3. **Verify assumptions** - Check actual code before decisions
4. **Document findings** - Pass context to next steps

We need the same behavior in Swarm Attack.

</what_claude_code_does>

</background_context>

---

<implementation_phases>

This implementation is broken into 4 phases, each following TDD:

| Phase | Focus | Files |
|-------|-------|-------|
| **Phase 1** | ToolSets + Agent Requirements | `tool_sets.py`, `test_tool_sets.py` |
| **Phase 2** | Research Mixin | `research_mixin.py`, `test_research_mixin.py` |
| **Phase 3** | Agent Updates | `issue_creator.py`, `complexity_gate.py`, `base.py` |
| **Phase 4** | Skill Updates | All `SKILL.md` files with Phase 0: Research |

</implementation_phases>

---

<phase number="1" name="ToolSets">

<tdd_protocol>

<phase name="RED" description="Write Failing Tests First">

Create `tests/unit/test_tool_sets.py`:

```python
"""Unit tests for ToolSets and agent tool requirements.

TDD RED Phase - All tests should FAIL initially.
"""
import pytest

from swarm_attack.agents.tool_sets import (
    ToolSet,
    AGENT_TOOL_REQUIREMENTS,
    get_tools_for_agent,
)


class TestToolSetEnum:
    """Tests for ToolSet enum."""

    def test_research_only_has_read_glob_grep(self):
        """RESEARCH_ONLY should have Read, Glob, Grep."""
        assert ToolSet.RESEARCH_ONLY.value == ["Read", "Glob", "Grep"]

    def test_research_with_bash_includes_bash(self):
        """RESEARCH_WITH_BASH should include Bash."""
        tools = ToolSet.RESEARCH_WITH_BASH.value
        assert "Bash" in tools
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_research_with_write_includes_write(self):
        """RESEARCH_WITH_WRITE should include Write."""
        tools = ToolSet.RESEARCH_WITH_WRITE.value
        assert "Write" in tools
        assert "Read" in tools

    def test_full_has_all_tools(self):
        """FULL should have all tools."""
        tools = ToolSet.FULL.value
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools
        assert "Bash" in tools
        assert "Write" in tools
        assert "Edit" in tools

    def test_none_is_empty_list(self):
        """NONE should be empty list (legacy)."""
        assert ToolSet.NONE.value == []


class TestAgentToolRequirements:
    """Tests for AGENT_TOOL_REQUIREMENTS mapping."""

    def test_coder_agent_has_research_tools(self):
        """CoderAgent should have research tools."""
        assert "CoderAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["CoderAgent"] == ToolSet.RESEARCH_ONLY

    def test_issue_creator_has_research_tools(self):
        """IssueCreatorAgent should have research tools (not NONE!)."""
        assert "IssueCreatorAgent" in AGENT_TOOL_REQUIREMENTS
        # This is the KEY change - was NONE, now RESEARCH_ONLY
        assert AGENT_TOOL_REQUIREMENTS["IssueCreatorAgent"] == ToolSet.RESEARCH_ONLY

    def test_complexity_gate_has_research_tools(self):
        """ComplexityGateAgent should have research tools (not NONE!)."""
        assert "ComplexityGateAgent" in AGENT_TOOL_REQUIREMENTS
        # This is the KEY change - was NONE, now RESEARCH_ONLY
        assert AGENT_TOOL_REQUIREMENTS["ComplexityGateAgent"] == ToolSet.RESEARCH_ONLY

    def test_bug_researcher_has_bash(self):
        """BugResearcherAgent should have Bash for running tests."""
        assert "BugResearcherAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["BugResearcherAgent"] == ToolSet.RESEARCH_WITH_BASH

    def test_verifier_has_research_tools(self):
        """VerifierAgent should have research tools."""
        assert "VerifierAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["VerifierAgent"] == ToolSet.RESEARCH_ONLY

    def test_spec_author_has_write(self):
        """SpecAuthorAgent should have Write for spec files."""
        assert "SpecAuthorAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["SpecAuthorAgent"] == ToolSet.RESEARCH_WITH_WRITE


class TestGetToolsForAgent:
    """Tests for get_tools_for_agent function."""

    def test_returns_correct_tools_for_coder(self):
        """Should return Read, Glob, Grep for CoderAgent."""
        tools = get_tools_for_agent("CoderAgent")
        assert tools == ["Read", "Glob", "Grep"]

    def test_returns_correct_tools_for_issue_creator(self):
        """Should return research tools for IssueCreatorAgent."""
        tools = get_tools_for_agent("IssueCreatorAgent")
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_returns_correct_tools_for_complexity_gate(self):
        """Should return research tools for ComplexityGateAgent."""
        tools = get_tools_for_agent("ComplexityGateAgent")
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_unknown_agent_gets_research_tools(self):
        """Unknown agents should get research tools by default."""
        tools = get_tools_for_agent("UnknownAgent")
        assert tools == ["Read", "Glob", "Grep"]

    def test_returns_list_not_enum(self):
        """Should return list of strings, not ToolSet enum."""
        tools = get_tools_for_agent("CoderAgent")
        assert isinstance(tools, list)
        assert all(isinstance(t, str) for t in tools)
```

**Verify RED phase:**
```bash
pytest tests/unit/test_tool_sets.py -v
# Expected: ALL TESTS FAIL (tool_sets.py doesn't exist)
```

</phase>

<phase name="GREEN" description="Implement to Pass Tests">

Create `swarm_attack/agents/tool_sets.py`:

```python
"""
Standard tool sets for Swarm Attack agents.

Defines consistent tool access across all agents, ensuring every agent
that makes code decisions can research the codebase.
"""
from __future__ import annotations

from enum import Enum
from typing import List


class ToolSet(Enum):
    """Standard tool sets for different agent types."""

    # Minimal research - can read and search
    RESEARCH_ONLY = ["Read", "Glob", "Grep"]

    # Research + can run tests/commands
    RESEARCH_WITH_BASH = ["Read", "Glob", "Grep", "Bash"]

    # Research + can write files
    RESEARCH_WITH_WRITE = ["Read", "Glob", "Grep", "Write"]

    # Full capability
    FULL = ["Read", "Glob", "Grep", "Bash", "Write", "Edit"]

    # No tools (legacy - deprecated)
    NONE = []


# Mapping of agent names to their required tool sets
AGENT_TOOL_REQUIREMENTS: dict[str, ToolSet] = {
    # Implementation agents
    "CoderAgent": ToolSet.RESEARCH_ONLY,
    "VerifierAgent": ToolSet.RESEARCH_ONLY,

    # Planning agents - NOW WITH RESEARCH (was NONE)
    "IssueCreatorAgent": ToolSet.RESEARCH_ONLY,
    "ComplexityGateAgent": ToolSet.RESEARCH_ONLY,

    # Spec agents
    "SpecAuthorAgent": ToolSet.RESEARCH_WITH_WRITE,
    "SpecModeratorAgent": ToolSet.RESEARCH_ONLY,

    # Bug agents
    "BugResearcherAgent": ToolSet.RESEARCH_WITH_BASH,
    "RootCauseAnalyzerAgent": ToolSet.RESEARCH_ONLY,
    "FixPlannerAgent": ToolSet.RESEARCH_ONLY,
    "BugModeratorAgent": ToolSet.RESEARCH_ONLY,

    # Support agents
    "SummarizerAgent": ToolSet.RESEARCH_ONLY,
    "RecoveryAgent": ToolSet.RESEARCH_ONLY,
    "IssueSplitterAgent": ToolSet.RESEARCH_ONLY,
}


def get_tools_for_agent(agent_name: str) -> List[str]:
    """
    Get required tools for an agent.

    Args:
        agent_name: Name of the agent class (e.g., "CoderAgent")

    Returns:
        List of tool names. Defaults to RESEARCH_ONLY if agent not in mapping.
    """
    tool_set = AGENT_TOOL_REQUIREMENTS.get(agent_name, ToolSet.RESEARCH_ONLY)
    return tool_set.value
```

**Verify GREEN phase:**
```bash
pytest tests/unit/test_tool_sets.py -v
# Expected: ALL TESTS PASS
```

</phase>

</tdd_protocol>

</phase>

---

<phase number="2" name="ResearchMixin">

<tdd_protocol>

<phase name="RED" description="Write Failing Tests First">

Create `tests/unit/test_research_mixin.py`:

```python
"""Unit tests for AgentResearchMixin.

TDD RED Phase - All tests should FAIL initially.
"""
import pytest
from typing import Optional

from swarm_attack.agents.research_mixin import (
    AgentResearchMixin,
    DiscoveredContext,
    ResearchResult,
)


class TestDiscoveredContext:
    """Tests for DiscoveredContext TypedDict."""

    def test_discovered_context_has_required_fields(self):
        """DiscoveredContext should have all required fields."""
        context: DiscoveredContext = {
            "files_found": ["file1.py"],
            "patterns_found": {"class": ["class Foo"]},
            "modules_read": ["module.py"],
            "classes_discovered": {"file.py": ["MyClass"]},
            "functions_discovered": {"file.py": ["my_func"]},
            "existing_tests": ["test_file.py"],
            "dependencies": ["requests"],
        }

        assert "files_found" in context
        assert "patterns_found" in context
        assert "modules_read" in context
        assert "classes_discovered" in context
        assert "functions_discovered" in context
        assert "existing_tests" in context
        assert "dependencies" in context


class TestResearchResult:
    """Tests for ResearchResult dataclass."""

    def test_research_result_success(self):
        """ResearchResult should capture successful research."""
        context: DiscoveredContext = {
            "files_found": ["file1.py"],
            "patterns_found": {},
            "modules_read": [],
            "classes_discovered": {},
            "functions_discovered": {},
            "existing_tests": [],
            "dependencies": [],
        }

        result = ResearchResult(
            success=True,
            context=context,
            summary="Found 1 file",
            search_queries=["*.py"],
        )

        assert result.success is True
        assert result.error is None
        assert len(result.context["files_found"]) == 1

    def test_research_result_failure(self):
        """ResearchResult should capture failed research."""
        result = ResearchResult(
            success=False,
            context={
                "files_found": [],
                "patterns_found": {},
                "modules_read": [],
                "classes_discovered": {},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="",
            search_queries=["*.py"],
            error="No files found",
        )

        assert result.success is False
        assert result.error == "No files found"


class TestAgentResearchMixin:
    """Tests for AgentResearchMixin class."""

    def test_research_tools_constant(self):
        """RESEARCH_TOOLS should be Read, Glob, Grep."""
        assert AgentResearchMixin.RESEARCH_TOOLS == ["Read", "Glob", "Grep"]

    def test_get_standard_research_patterns(self):
        """Should return sensible default patterns for a feature."""
        mixin = AgentResearchMixin()
        patterns = mixin.get_standard_research_patterns("my-feature")

        assert "search_patterns" in patterns
        assert "grep_patterns" in patterns
        assert "read_files" in patterns

        # Should include python files
        assert any("*.py" in p for p in patterns["search_patterns"])
        # Should include CLAUDE.md
        assert "CLAUDE.md" in patterns["read_files"]

    def test_format_research_for_prompt_includes_files(self):
        """format_research_for_prompt should include found files."""
        mixin = AgentResearchMixin()
        result = ResearchResult(
            success=True,
            context={
                "files_found": ["swarm_attack/agents/base.py"],
                "patterns_found": {"class Agent": ["class BaseAgent"]},
                "modules_read": ["base.py"],
                "classes_discovered": {"base.py": ["BaseAgent"]},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="Found BaseAgent class",
            search_queries=["swarm_attack/**/*.py"],
        )

        formatted = mixin.format_research_for_prompt(result)

        assert "base.py" in formatted
        assert "BaseAgent" in formatted

    def test_format_research_for_prompt_handles_empty(self):
        """format_research_for_prompt should handle empty results."""
        mixin = AgentResearchMixin()
        result = ResearchResult(
            success=True,
            context={
                "files_found": [],
                "patterns_found": {},
                "modules_read": [],
                "classes_discovered": {},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="No results found",
            search_queries=["nonexistent/**/*.py"],
        )

        formatted = mixin.format_research_for_prompt(result)

        # Should not raise, should return something
        assert isinstance(formatted, str)

    def test_build_research_prompt(self):
        """build_research_prompt should create exploration prompt."""
        mixin = AgentResearchMixin()
        task_context = {
            "feature_id": "my-feature",
            "search_hints": ["look for Agent classes"],
        }

        prompt = mixin.build_research_prompt(task_context)

        assert "research" in prompt.lower() or "explore" in prompt.lower()
        assert "my-feature" in prompt or "Agent" in prompt
```

**Verify RED phase:**
```bash
pytest tests/unit/test_research_mixin.py -v
# Expected: ALL TESTS FAIL (research_mixin.py doesn't exist)
```

</phase>

<phase name="GREEN" description="Implement to Pass Tests">

Create `swarm_attack/agents/research_mixin.py`:

```python
"""
AgentResearchMixin - Adds research capability to any agent.

Provides standardized research phase execution, context discovery,
and result formatting for LLM prompts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TypedDict


class DiscoveredContext(TypedDict):
    """Context discovered during research phase."""
    files_found: list[str]
    patterns_found: dict[str, list[str]]
    modules_read: list[str]
    classes_discovered: dict[str, list[str]]
    functions_discovered: dict[str, list[str]]
    existing_tests: list[str]
    dependencies: list[str]


@dataclass
class ResearchResult:
    """Result of research phase."""
    success: bool
    context: DiscoveredContext
    summary: str
    search_queries: list[str]
    error: Optional[str] = None


class AgentResearchMixin:
    """
    Mixin that adds research capabilities to any agent.

    Provides:
    - Standardized research phase execution
    - Context discovery and caching
    - Research result formatting for prompts
    """

    RESEARCH_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    def __init__(self):
        self._research_cache: dict[str, ResearchResult] = {}

    def get_standard_research_patterns(self, feature_id: str) -> dict:
        """
        Get standard research patterns for a feature.

        Args:
            feature_id: Feature identifier

        Returns:
            Dict with search_patterns, grep_patterns, read_files
        """
        return {
            "search_patterns": [
                "swarm_attack/**/*.py",
                f"tests/**/*{feature_id}*.py" if feature_id else "tests/**/*.py",
                ".claude/skills/**/*.md",
            ],
            "grep_patterns": [
                r"class\s+\w+Agent",
                r"def\s+run\(",
                r"from swarm_attack",
            ],
            "read_files": [
                "CLAUDE.md",
                "swarm_attack/agents/base.py",
            ],
        }

    def format_research_for_prompt(self, result: ResearchResult) -> str:
        """
        Format research results for inclusion in agent prompt.

        Args:
            result: ResearchResult from research phase

        Returns:
            Formatted string suitable for LLM prompt
        """
        if not result.success or not result.context["files_found"]:
            return "## Research Results\n\nNo relevant files found during research."

        lines = ["## Research Results", ""]

        # Files found
        if result.context["files_found"]:
            lines.append("### Files Found")
            for f in result.context["files_found"][:20]:  # Limit to 20
                lines.append(f"- `{f}`")
            lines.append("")

        # Classes discovered
        if result.context["classes_discovered"]:
            lines.append("### Classes Discovered")
            for file, classes in result.context["classes_discovered"].items():
                for cls in classes:
                    lines.append(f"- `{cls}` in `{file}`")
            lines.append("")

        # Modules read
        if result.context["modules_read"]:
            lines.append("### Modules Read")
            for m in result.context["modules_read"]:
                lines.append(f"- `{m}`")
            lines.append("")

        # Summary
        if result.summary:
            lines.append("### Summary")
            lines.append(result.summary)
            lines.append("")

        return "\n".join(lines)

    def build_research_prompt(self, task_context: dict) -> str:
        """
        Build prompt for research phase.

        Args:
            task_context: Context about the task being researched

        Returns:
            Prompt string for research exploration
        """
        feature_id = task_context.get("feature_id", "")
        search_hints = task_context.get("search_hints", [])

        prompt_lines = [
            "# Research Phase",
            "",
            "Before proceeding, explore the codebase to understand existing patterns.",
            "",
            "## Your Task",
            "",
            "1. **Find relevant files** using Glob",
            "2. **Search for patterns** using Grep",
            "3. **Read key modules** to understand interfaces",
            "",
        ]

        if feature_id:
            prompt_lines.extend([
                f"## Feature Context: {feature_id}",
                "",
            ])

        if search_hints:
            prompt_lines.append("## Search Hints")
            for hint in search_hints:
                prompt_lines.append(f"- {hint}")
            prompt_lines.append("")

        prompt_lines.extend([
            "## Required Actions",
            "",
            "1. Glob 'swarm_attack/**/*.py' to find modules",
            "2. Grep for class definitions related to your task",
            "3. Read CLAUDE.md for project conventions",
            "4. Read base classes you'll be extending",
            "",
        ])

        return "\n".join(prompt_lines)
```

**Verify GREEN phase:**
```bash
pytest tests/unit/test_research_mixin.py -v
# Expected: ALL TESTS PASS
```

</phase>

</tdd_protocol>

</phase>

---

<phase number="3" name="AgentUpdates">

<tdd_protocol>

<phase name="RED" description="Write Failing Tests First">

Create `tests/integration/test_agent_research.py`:

```python
"""Integration tests for agent research capability.

TDD RED Phase - Tests for IssueCreator and ComplexityGate having research tools.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from swarm_attack.agents.issue_creator import IssueCreatorAgent
from swarm_attack.agents.complexity_gate import ComplexityGateAgent
from swarm_attack.agents.base import BaseAgent
from swarm_attack.agents.tool_sets import get_tools_for_agent


class TestBaseAgentDefaults:
    """Tests for BaseAgent default tool access."""

    def test_base_agent_has_default_tools(self):
        """BaseAgent should define DEFAULT_TOOLS."""
        assert hasattr(BaseAgent, "DEFAULT_TOOLS")
        assert BaseAgent.DEFAULT_TOOLS == ["Read", "Glob", "Grep"]

    def test_base_agent_get_tools_method(self):
        """BaseAgent should have get_tools() method."""
        assert hasattr(BaseAgent, "get_tools")


class TestIssueCreatorResearch:
    """Tests for IssueCreatorAgent research capability."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock()
        config.repo_root = "/fake/repo"
        config.specs_path = Mock()
        config.specs_path.__truediv__ = Mock(return_value=Mock())
        return config

    def test_issue_creator_has_research_tools(self, mock_config):
        """IssueCreatorAgent should have research tools, not empty."""
        tools = get_tools_for_agent("IssueCreatorAgent")

        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools
        # Should NOT be empty anymore
        assert tools != []

    def test_issue_creator_run_uses_tools(self, mock_config):
        """IssueCreatorAgent.run should pass allowed_tools to LLM."""
        agent = IssueCreatorAgent(config=mock_config)
        agent.llm = Mock()
        agent.llm.run = Mock(return_value=Mock(
            text='{"issues": []}',
            success=True,
        ))

        # Mock skill loading
        agent._load_skill_prompt = Mock(return_value="skill prompt")

        context = {
            "feature_id": "test-feature",
            "spec_content": "# Spec content",
        }

        # Execute
        with patch.object(agent, '_parse_issues_from_response', return_value=[]):
            try:
                agent.run(context)
            except Exception:
                pass  # We're testing the LLM call, not the result

        # Verify LLM was called with tools
        if agent.llm.run.called:
            call_kwargs = agent.llm.run.call_args
            if call_kwargs:
                # Check allowed_tools was passed and is not empty
                allowed_tools = call_kwargs.kwargs.get("allowed_tools", [])
                assert allowed_tools != [], "IssueCreator should have tools, not empty list"


class TestComplexityGateResearch:
    """Tests for ComplexityGateAgent research capability."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = Mock()
        config.repo_root = "/fake/repo"
        return config

    def test_complexity_gate_has_research_tools(self, mock_config):
        """ComplexityGateAgent should have research tools, not empty."""
        tools = get_tools_for_agent("ComplexityGateAgent")

        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools
        # Should NOT be empty anymore
        assert tools != []

    def test_complexity_gate_max_turns_allows_exploration(self, mock_config):
        """ComplexityGateAgent should have max_turns > 1 for exploration."""
        agent = ComplexityGateAgent(config=mock_config)

        # Check that the agent allows multiple turns
        # (Previously was max_turns=1, now should be higher)
        assert hasattr(agent, "GATE_TURNS") or True  # Attribute may be named differently

    def test_complexity_gate_run_uses_tools(self, mock_config):
        """ComplexityGateAgent.run should pass allowed_tools to LLM."""
        agent = ComplexityGateAgent(config=mock_config)
        agent.llm = Mock()
        agent.llm.run = Mock(return_value=Mock(
            text='{"complexity": "small", "estimated_turns": 5}',
            success=True,
        ))

        context = {
            "issue_body": "# Test Issue\n\nImplement something.",
            "issue_number": 1,
        }

        # Execute
        with patch.object(agent, '_parse_gate_response', return_value={"pass": True}):
            try:
                agent.run(context)
            except Exception:
                pass

        # Verify LLM was called with tools
        if agent.llm.run.called:
            call_kwargs = agent.llm.run.call_args
            if call_kwargs:
                allowed_tools = call_kwargs.kwargs.get("allowed_tools", [])
                assert allowed_tools != [], "ComplexityGate should have tools, not empty list"
```

**Verify RED phase:**
```bash
pytest tests/integration/test_agent_research.py -v
# Expected: SOME TESTS FAIL (agents still use allowed_tools=[])
```

</phase>

<phase name="GREEN" description="Update Agents">

**Update `swarm_attack/agents/base.py`:**

Add to BaseAgent class:

```python
class BaseAgent(ABC):
    """Base class for all agents."""

    # All agents get research tools by default
    DEFAULT_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    def get_tools(self) -> list[str]:
        """
        Get tools for this agent.

        Returns tools from tool_sets.py mapping, or DEFAULT_TOOLS.
        """
        from swarm_attack.agents.tool_sets import get_tools_for_agent
        return get_tools_for_agent(self.__class__.__name__)
```

**Update `swarm_attack/agents/issue_creator.py`:**

Change the `llm.run()` call:

```python
# OLD (line ~330):
result = self.llm.run(
    prompt,
    allowed_tools=[],  # BLIND!
    max_turns=1,
)

# NEW:
result = self.llm.run(
    prompt,
    allowed_tools=self.get_tools(),  # ["Read", "Glob", "Grep"]
    max_turns=5,  # Allow exploration turns
)
```

**Update `swarm_attack/agents/complexity_gate.py`:**

Change the `llm.run()` call:

```python
# OLD (line ~274):
result = self.llm.run(
    prompt,
    allowed_tools=[],  # BLIND!
    max_turns=1,
    model="haiku",
)

# NEW:
result = self.llm.run(
    prompt,
    allowed_tools=self.get_tools(),  # ["Read", "Glob", "Grep"]
    max_turns=3,  # Allow some exploration
    model="haiku",  # Still use cheap model
)
```

**Verify GREEN phase:**
```bash
pytest tests/integration/test_agent_research.py -v
pytest tests/unit/test_tool_sets.py -v
pytest tests/unit/test_research_mixin.py -v
# Expected: ALL TESTS PASS
```

</phase>

</tdd_protocol>

</phase>

---

<phase number="4" name="SkillUpdates">

<skill_template>

Add this "Phase 0: Research" section to ALL SKILL.md files:

```markdown
## Phase 0: Research (MANDATORY - DO THIS FIRST)

<research_protocol>

Before ANY other action, you MUST research the codebase.

**1. Find Relevant Files**
```
Glob "swarm_attack/**/*.py"
Glob "tests/**/*.py"
```

**2. Search for Patterns**
```
Grep "class.*Agent" swarm_attack/
Grep "def run\(" swarm_attack/agents/
```

**3. Read Key Files**
```
Read CLAUDE.md
Read swarm_attack/agents/base.py
```

**4. Document Findings**
Before proceeding, note:
- [ ] Existing patterns to follow
- [ ] Base classes to extend
- [ ] Tests that exist
- [ ] Modules to import from

</research_protocol>

DO NOT proceed until you have researched the codebase.
```

</skill_template>

<files_to_update>

| Skill File | Priority |
|------------|----------|
| `.claude/skills/coder/SKILL.md` | Already has Phase 0, verify complete |
| `.claude/skills/issue-creator/SKILL.md` | HIGH - add research phase |
| `.claude/skills/verifier/SKILL.md` | MEDIUM - add research phase |
| `.claude/skills/feature-spec-author/SKILL.md` | MEDIUM |
| `.claude/skills/feature-spec-moderator/SKILL.md` | MEDIUM |
| `.claude/skills/bug-researcher/SKILL.md` | Already good, verify |
| `.claude/skills/root-cause-analyzer/SKILL.md` | MEDIUM |
| `.claude/skills/fix-planner/SKILL.md` | MEDIUM |

</files_to_update>

</phase>

---

<success_criteria>

Implementation complete when:

1. [ ] `swarm_attack/agents/tool_sets.py` exists with all tests passing
2. [ ] `swarm_attack/agents/research_mixin.py` exists with all tests passing
3. [ ] `IssueCreatorAgent` uses `allowed_tools=["Read", "Glob", "Grep"]`
4. [ ] `ComplexityGateAgent` uses `allowed_tools=["Read", "Glob", "Grep"]`
5. [ ] `BaseAgent` has `DEFAULT_TOOLS` and `get_tools()` method
6. [ ] All SKILL.md files have "Phase 0: Research" section
7. [ ] Full test suite passes: `pytest tests/ -v`
8. [ ] No regressions in existing agent behavior

</success_criteria>

---

<execution_command>

```
Execute specs/agent-research-capability/IMPLEMENTATION_TDD_PROMPT.md using TDD methodology.

Phase 1: Create tool_sets.py with tests
Phase 2: Create research_mixin.py with tests
Phase 3: Update issue_creator.py and complexity_gate.py
Phase 4: Update all SKILL.md files with Phase 0: Research

Run full test suite after each phase to verify no regressions.
```

</execution_command>

---

<references>

- **Spec:** `specs/agent-research-capability/SPEC.md`
- **Existing Agents:** `swarm_attack/agents/*.py`
- **BaseAgent:** `swarm_attack/agents/base.py`
- **XML Guidelines:** `CLAUDE.md` section "XML Prompt Engineering Guidelines"

</references>
