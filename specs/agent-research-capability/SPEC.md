# Agent Research Capability Overhaul

<mission>
Fix the fundamental weakness in Swarm Attack where agents operate without codebase awareness. Ensure ALL agents can research the codebase before acting, matching Claude Code's "research first" behavior.
</mission>

---

## Problem Statement

<problem_analysis>

### Previous State: Agents Operating Blind (NOW FIXED)

Several critical agents previously had **no codebase search capability**:

| Agent | Previous Tools | Problem | Current State |
|-------|----------------|---------|---------------|
| **IssueCreator** | `allowed_tools=[]` | Created issues without knowing what code exists | **FIXED**: Uses `get_tools_for_agent("IssueCreatorAgent")` |
| **ComplexityGate** | `allowed_tools=[]` | Estimated complexity without seeing actual code | **FIXED**: Uses `get_tools_for_agent("ComplexityGateAgent")` |
| **SpecCritic** | Codex CLI (no tools) | Reviews specs without verifying against codebase | Out of scope (Codex agent) |

**UPDATE (Implementation Complete):** The `tool_sets.py` module now provides centralized tool management. All agents use `get_tools_for_agent()` which returns `["Read", "Glob", "Grep"]` for research capability.

### Root Cause

The system follows a "thick-agent" model where context is **pre-loaded by the orchestrator** rather than **discovered by the agent**. This creates:

1. **Orchestrator bottleneck** - If orchestrator misses context, agent can't find it
2. **Stale context** - Pre-loaded context may not reflect current codebase state
3. **No verification** - Agents can't double-check assumptions against actual code
4. **Inconsistent behavior** - Some agents research, others don't

### What Claude Code Does Differently

Claude Code agents:
1. **START by researching** - Use Glob, Grep, Read before any action
2. **Discover context dynamically** - Find what they need, don't rely on injection
3. **Verify assumptions** - Check actual code before making decisions
4. **Iterate with feedback** - Research → Act → Verify → Repeat

</problem_analysis>

---

## Solution Design

<solution_overview>

### Core Principle: Research-First Architecture

Every agent that makes decisions about code should:
1. Have access to `Read`, `Glob`, `Grep` tools (minimum)
2. Execute a mandatory "Phase 0: Research" before acting
3. Be able to verify its assumptions against actual code
4. Document what it discovered for downstream agents

### Implementation Strategy

1. **AgentResearchMixin** - Shared research capabilities for all agents
2. **StandardToolSet** - Consistent tool access across agents
3. **ResearchPhase decorator** - Enforce research-first behavior
4. **ContextDiscovery** - Structured codebase discovery output

</solution_overview>

---

## Technical Specification

<interface_contract>

### 1. AgentResearchMixin

```python
# File: swarm_attack/agents/research_mixin.py

from typing import Protocol, TypedDict, Optional
from dataclasses import dataclass, field


class DiscoveredContext(TypedDict):
    """Context discovered during research phase."""
    files_found: list[str]           # Files matching search patterns
    patterns_found: dict[str, list[str]]  # pattern -> matching lines
    modules_read: list[str]          # Modules that were read
    classes_discovered: dict[str, list[str]]  # file -> [class names]
    functions_discovered: dict[str, list[str]]  # file -> [function names]
    existing_tests: list[str]        # Test files found
    dependencies: list[str]          # External dependencies detected


@dataclass
class ResearchResult:
    """Result of research phase."""
    success: bool
    context: DiscoveredContext
    summary: str  # Human-readable summary of findings
    search_queries: list[str]  # What searches were performed
    error: Optional[str] = None


class ResearchCapable(Protocol):
    """Protocol for agents with research capability."""

    def research_codebase(
        self,
        search_patterns: list[str],
        grep_patterns: list[str],
        read_files: list[str],
    ) -> ResearchResult:
        """Execute research phase to discover context."""
        ...

    def build_research_prompt(self, task_context: dict) -> str:
        """Build prompt for research phase."""
        ...


class AgentResearchMixin:
    """
    Mixin that adds research capabilities to any agent.

    Provides:
    - Standardized research phase execution
    - Context discovery and caching
    - Research result formatting for prompts
    """

    # Standard tools all research-capable agents should have
    RESEARCH_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    def __init__(self):
        self._research_cache: dict[str, ResearchResult] = {}

    def research_codebase(
        self,
        search_patterns: list[str],
        grep_patterns: list[str],
        read_files: list[str],
        cache_key: Optional[str] = None,
    ) -> ResearchResult:
        """
        Execute research phase to discover codebase context.

        Args:
            search_patterns: Glob patterns to find files (e.g., "swarm_attack/**/*.py")
            grep_patterns: Regex patterns to search content (e.g., "class.*Agent")
            read_files: Specific files to read
            cache_key: Optional key for caching results

        Returns:
            ResearchResult with discovered context
        """
        pass

    def format_research_for_prompt(self, result: ResearchResult) -> str:
        """Format research results for inclusion in agent prompt."""
        pass

    def get_standard_research_patterns(self, feature_id: str) -> dict:
        """Get standard research patterns for a feature."""
        return {
            "search_patterns": [
                f"swarm_attack/**/*.py",
                f"tests/**/*{feature_id}*.py",
                f".claude/skills/**/*.md",
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
```

### 2. StandardToolSet

```python
# File: swarm_attack/agents/tool_sets.py

from enum import Enum
from typing import List


class ToolSet(Enum):
    """Standard tool sets for different agent types."""

    # Minimal research - can read and search
    RESEARCH_ONLY = ["Read", "Glob", "Grep"]

    # Research + can run tests
    RESEARCH_WITH_BASH = ["Read", "Glob", "Grep", "Bash"]

    # Research + can write files
    RESEARCH_WITH_WRITE = ["Read", "Glob", "Grep", "Write"]

    # Full capability (for bug researchers, etc.)
    FULL = ["Read", "Glob", "Grep", "Bash", "Write", "Edit"]

    # No tools (legacy - should be deprecated)
    NONE = []


# Mapping of agent names to their required tool sets
AGENT_TOOL_REQUIREMENTS: dict[str, ToolSet] = {
    # Implementation agents - need research
    "CoderAgent": ToolSet.RESEARCH_ONLY,
    "VerifierAgent": ToolSet.RESEARCH_ONLY,

    # Planning agents - need research to understand codebase
    "IssueCreatorAgent": ToolSet.RESEARCH_ONLY,  # CHANGED from NONE
    "ComplexityGateAgent": ToolSet.RESEARCH_ONLY,  # CHANGED from NONE

    # Spec agents - need research to verify against code
    "SpecAuthorAgent": ToolSet.RESEARCH_WITH_WRITE,
    "SpecCriticAgent": ToolSet.RESEARCH_ONLY,  # CHANGED - was Codex
    "SpecModeratorAgent": ToolSet.RESEARCH_ONLY,

    # Bug agents - need full research
    "BugResearcherAgent": ToolSet.RESEARCH_WITH_BASH,
    "RootCauseAnalyzerAgent": ToolSet.RESEARCH_ONLY,
    "FixPlannerAgent": ToolSet.RESEARCH_ONLY,

    # Support agents
    "SummarizerAgent": ToolSet.RESEARCH_ONLY,
    "RecoveryAgent": ToolSet.RESEARCH_ONLY,
}


def get_tools_for_agent(agent_name: str) -> List[str]:
    """Get required tools for an agent."""
    tool_set = AGENT_TOOL_REQUIREMENTS.get(agent_name, ToolSet.RESEARCH_ONLY)
    return tool_set.value
```

### 3. Research Phase Decorator

```python
# File: swarm_attack/agents/research_decorator.py

from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


def requires_research(
    search_patterns: list[str] = None,
    grep_patterns: list[str] = None,
    min_files_to_read: int = 1,
):
    """
    Decorator that enforces research phase before agent execution.

    Usage:
        @requires_research(
            search_patterns=["swarm_attack/**/*.py"],
            grep_patterns=["class.*Agent"],
        )
        def run(self, context: dict) -> AgentResult:
            # Research results available in context["research"]
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, context: dict, *args, **kwargs) -> Any:
            # Execute research phase if not already done
            if "research" not in context:
                logger.info(f"{self.__class__.__name__}: Executing research phase")

                patterns = search_patterns or self.get_default_search_patterns(context)
                grep_pats = grep_patterns or self.get_default_grep_patterns(context)

                research_result = self.research_codebase(
                    search_patterns=patterns,
                    grep_patterns=grep_pats,
                    read_files=self.get_files_to_read(context),
                )

                if not research_result.success:
                    logger.warning(f"Research phase failed: {research_result.error}")

                context["research"] = research_result

            return func(self, context, *args, **kwargs)
        return wrapper
    return decorator
```

### 4. Updated Agent Base Class

```python
# Changes to swarm_attack/agents/base.py

class BaseAgent(ABC):
    """Base class for all agents with research capability."""

    # All agents get research tools by default
    DEFAULT_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    def get_tools(self) -> list[str]:
        """
        Get tools for this agent.

        Override in subclasses for different tool sets.
        Defaults to research tools (Read, Glob, Grep).
        """
        from swarm_attack.agents.tool_sets import get_tools_for_agent
        return get_tools_for_agent(self.__class__.__name__)

    def get_default_search_patterns(self, context: dict) -> list[str]:
        """Get default glob patterns for research phase."""
        feature_id = context.get("feature_id", "")
        return [
            "swarm_attack/**/*.py",
            f"tests/**/*{feature_id}*.py" if feature_id else "tests/**/*.py",
        ]

    def get_default_grep_patterns(self, context: dict) -> list[str]:
        """Get default grep patterns for research phase."""
        return [
            r"class\s+\w+",
            r"def\s+\w+\(",
        ]

    def get_files_to_read(self, context: dict) -> list[str]:
        """Get specific files that should always be read."""
        return ["CLAUDE.md"]
```

</interface_contract>

---

## Agent-Specific Changes

<agent_changes>

### 1. IssueCreatorAgent (IMPLEMENTED)

**Previous:** `allowed_tools=[]` - ran completely blind

**Current Implementation:** Uses `get_tools_for_agent("IssueCreatorAgent")` which returns `["Read", "Glob", "Grep"]`

```python
# issue_creator.py - NOW IMPLEMENTED via tool_sets.py

from swarm_attack.agents.tool_sets import get_tools_for_agent

class IssueCreatorAgent(BaseAgent):
    """Creates issues with codebase awareness."""

    def run(self, context: dict) -> AgentResult:
        # Uses tools for verification via get_tools_for_agent()
        result = self.llm.run(
            prompt,
            allowed_tools=get_tools_for_agent("IssueCreatorAgent"),  # ["Read", "Glob", "Grep"]
            max_turns=5,  # Allows exploration
        )
```

### 2. ComplexityGateAgent (IMPLEMENTED)

**Previous:** `allowed_tools=[]`, `max_turns=1` - instant judgment without looking

**Current Implementation:** Uses `get_tools_for_agent("ComplexityGateAgent")` which returns `["Read", "Glob", "Grep"]`

```python
# complexity_gate.py - NOW IMPLEMENTED via tool_sets.py

from swarm_attack.agents.tool_sets import get_tools_for_agent

class ComplexityGateAgent(BaseAgent):
    """Estimates complexity with codebase awareness."""

    def run(self, context: dict) -> AgentResult:
        result = self.llm.run(
            prompt,
            allowed_tools=get_tools_for_agent("ComplexityGateAgent"),  # ["Read", "Glob", "Grep"]
            max_turns=3,  # Allows exploration
            model="haiku",  # Still use cheap model
        )
```

### 3. SpecCriticAgent (OUT OF SCOPE)

**Current:** Uses Codex CLI without tool access

**Status:** Keep as-is for now. Codex-based agents will be addressed separately.

The SpecCritic uses Codex CLI intentionally for independent review (avoiding self-review bias). Context injection will be explored as a separate enhancement.

### 4. All Agent Skills (SKILL.md Updates)

Add mandatory research phase to all skill prompts:

```markdown
## Phase 0: Research (MANDATORY - DO THIS FIRST)

Before ANY other action, you MUST research the codebase:

<research_protocol>
1. **Find relevant files**
   - Glob for files mentioned in the task
   - Glob for similar/related modules

2. **Search for patterns**
   - Grep for class definitions
   - Grep for function signatures
   - Grep for imports and dependencies

3. **Read key files**
   - Read CLAUDE.md for project conventions
   - Read any files explicitly mentioned
   - Read base classes and interfaces

4. **Document findings**
   - Note existing patterns to follow
   - Note modules to import from
   - Note tests that exist
</research_protocol>

DO NOT proceed to implementation until you have:
- [ ] Found at least 3 relevant files
- [ ] Read the base class/interface you're extending
- [ ] Identified existing patterns to follow
```

</agent_changes>

---

## Acceptance Criteria

<acceptance_criteria>

### Core Functionality
- [x] `AgentResearchMixin` provides standard research interface
- [x] `ToolSet` enum defines consistent tool sets (in `swarm_attack/agents/tool_sets.py`)
- [x] `AGENT_TOOL_REQUIREMENTS` maps all agents to appropriate tools
- [x] `get_tools_for_agent()` returns correct tools for any agent
- [ ] `@requires_research` decorator enforces research phase (optional enhancement)

### Agent Changes
- [x] `IssueCreatorAgent` uses research tools via `get_tools_for_agent("IssueCreatorAgent")`
- [x] `ComplexityGateAgent` uses research tools via `get_tools_for_agent("ComplexityGateAgent")`
- [x] All agents get research tools by default via `BaseAgent.DEFAULT_TOOLS`
- [x] SpecCriticAgent unchanged (Codex agents out of scope)

### Skill Updates
- [ ] All SKILL.md files include "Phase 0: Research" section
- [ ] Research phase is documented as MANDATORY
- [ ] Verification checklist included in each skill

### Backward Compatibility
- [ ] Existing agent behavior unchanged when research disabled
- [ ] Research can be skipped with explicit flag
- [ ] No breaking changes to AgentResult interface

### Testing
- [ ] Unit tests for AgentResearchMixin
- [ ] Unit tests for ToolSet and requirements mapping
- [ ] Integration test: IssueCreator researches before creating issues
- [ ] Integration test: ComplexityGate reads code before estimating

</acceptance_criteria>

---

## Files to Create

| File | Purpose |
|------|---------|
| `swarm_attack/agents/research_mixin.py` | AgentResearchMixin implementation |
| `swarm_attack/agents/tool_sets.py` | ToolSet enum and agent mapping |
| `swarm_attack/agents/research_decorator.py` | @requires_research decorator |
| `tests/unit/test_research_mixin.py` | Unit tests for mixin |
| `tests/unit/test_tool_sets.py` | Unit tests for tool sets |
| `tests/integration/test_agent_research.py` | Integration tests |

## Files to Modify

| File | Change |
|------|--------|
| `swarm_attack/agents/base.py` | Add DEFAULT_TOOLS, get_tools() method |
| `swarm_attack/agents/issue_creator.py` | Enable research tools, add research phase |
| `swarm_attack/agents/complexity_gate.py` | Enable research tools, add research phase |
| `.claude/skills/*/SKILL.md` | Add Phase 0: Research section to all |

**Out of Scope:** `swarm_attack/agents/spec_critic.py` (Codex agents handled separately)

---

## Success Metrics

After implementation:

1. **No blind agents** - Every agent that makes code decisions can search the codebase
2. **Research-first behavior** - Agents research before acting, like Claude Code
3. **Consistent tools** - All agents use standardized tool sets
4. **Verified outputs** - Agents can verify their assumptions against actual code
5. **Better issue quality** - IssueCreator knows what modules exist before creating issues
6. **Better estimates** - ComplexityGate sees actual code complexity before estimating

