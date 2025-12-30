# SkillLoader Implementation Prompt (TDD)

## Mission

You are orchestrating a **Team of Specialized Experts** to implement the SkillLoader feature using strict **Test-Driven Development (TDD)** methodology.

This is the **only remaining Phase 1 feature** from the Context Optimization spec. Features 2-3 (ModuleRegistry, CompletionTracker) were implemented via alternative design integrated into existing components.

---

## Team Structure

| Expert | Role | Responsibility |
|--------|------|----------------|
| **Architect** | Design Lead | Review existing code, finalize interface contracts, identify integration points |
| **TestWriter** | RED Phase | Write comprehensive failing tests FIRST |
| **Coder** | GREEN Phase | Implement minimal code to pass all tests |
| **Integrator** | Wiring | Update BaseAgent to use new SkillLoader, ensure backward compatibility |
| **Reviewer** | Validation | Run full test suite, verify no regressions |

---

## Background Context

### What Already Exists

**Current Skill Loading** in `swarm_attack/agents/base.py` (lines 210-299):

```python
def load_skill(self, skill_name: str) -> str:
    """Load skill content from .claude/skills/{skill_name}/SKILL.md"""
    # Returns raw content with frontmatter stripped

def load_skill_with_metadata(self, skill_name: str) -> tuple[str, dict]:
    """Load skill and parse YAML frontmatter."""
    # Returns (content, metadata_dict)

def get_allowed_tools_from_metadata(self, metadata: dict) -> list[str]:
    """Extract tool permissions from metadata."""
```

**Current Limitations:**
1. No dedicated SkillLoader class (logic embedded in BaseAgent)
2. No SkillDefinition dataclass with structured metadata
3. No nested subagent discovery (`{skill}/agents/{subagent}/SKILL.md`)
4. No `list_subagents()` or `has_subagents()` methods

### Directory Structure for Skills

```
.claude/skills/
├── coder/
│   └── SKILL.md
├── verifier/
│   └── SKILL.md
├── feature-spec-author/
│   ├── SKILL.md
│   └── agents/              # NEW: Nested agents directory
│       ├── research/
│       │   └── SKILL.md
│       └── drafting/
│           └── SKILL.md
└── issue-creator/
    └── SKILL.md
```

---

## Feature Specification

### Interface Contract

```python
# File: swarm_attack/skill_loader.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SkillDefinition:
    """Parsed skill with metadata and nested agent info."""
    name: str                          # Skill name (e.g., "coder")
    content: str                       # SKILL.md content (frontmatter stripped)
    metadata: dict                     # Parsed YAML frontmatter
    subagents: list[str] = field(default_factory=list)  # Available nested agents
    path: Path = None                  # Source file path


class SkillLoader:
    """Loads skills and their nested subagents from .claude/skills/."""

    def __init__(self, skills_dir: Path = None):
        """
        Initialize SkillLoader.

        Args:
            skills_dir: Path to skills directory. Defaults to .claude/skills/
        """
        pass

    def load_skill(self, skill_name: str) -> SkillDefinition:
        """
        Load main skill from .claude/skills/{skill_name}/SKILL.md.

        Args:
            skill_name: Name of the skill directory.

        Returns:
            SkillDefinition with parsed content, metadata, and subagent list.

        Raises:
            SkillNotFoundError: If skill directory or SKILL.md doesn't exist.
        """
        pass

    def load_subagent(self, skill_name: str, agent_name: str) -> SkillDefinition:
        """
        Load nested agent from .claude/skills/{skill_name}/agents/{agent_name}/SKILL.md.

        Args:
            skill_name: Parent skill name.
            agent_name: Nested agent name.

        Returns:
            SkillDefinition for the subagent.

        Raises:
            SkillNotFoundError: If subagent doesn't exist.
        """
        pass

    def list_subagents(self, skill_name: str) -> list[str]:
        """
        List available subagents for a skill.

        Args:
            skill_name: Name of the parent skill.

        Returns:
            List of subagent names. Empty list if no agents/ directory.
        """
        pass

    def has_subagents(self, skill_name: str) -> bool:
        """
        Check if skill has nested agents directory.

        Args:
            skill_name: Name of the skill.

        Returns:
            True if {skill}/agents/ exists and contains subagents.
        """
        pass

    def _parse_frontmatter(self, content: str) -> tuple[str, dict]:
        """
        Parse YAML frontmatter from skill content.

        Args:
            content: Raw SKILL.md content.

        Returns:
            Tuple of (content_without_frontmatter, metadata_dict).
        """
        pass

    def _get_skill_path(self, skill_name: str) -> Path:
        """Get path to skill's SKILL.md file."""
        pass

    def _get_subagent_path(self, skill_name: str, agent_name: str) -> Path:
        """Get path to subagent's SKILL.md file."""
        pass
```

### Exception Class

```python
# In swarm_attack/skill_loader.py or swarm_attack/errors.py

class SkillNotFoundError(Exception):
    """Raised when a skill or subagent cannot be found."""

    def __init__(self, skill_name: str, path: Path = None, is_subagent: bool = False):
        self.skill_name = skill_name
        self.path = path
        self.is_subagent = is_subagent

        if is_subagent:
            msg = f"Subagent '{skill_name}' not found"
        else:
            msg = f"Skill '{skill_name}' not found"
        if path:
            msg += f" at {path}"

        super().__init__(msg)
```

---

## Acceptance Criteria

### Core Functionality
- [ ] `SkillLoader.__init__()` accepts optional `skills_dir` parameter
- [ ] `SkillLoader.load_skill()` returns `SkillDefinition` with parsed metadata
- [ ] `SkillLoader.load_subagent()` loads from `{skill}/agents/{agent}/SKILL.md`
- [ ] `SkillLoader.list_subagents()` returns agent names from `{skill}/agents/` directory
- [ ] `SkillLoader.has_subagents()` returns True/False correctly
- [ ] `SkillDefinition.subagents` populated when skill has nested agents

### Error Handling
- [ ] `SkillNotFoundError` raised when skill directory doesn't exist
- [ ] `SkillNotFoundError` raised when SKILL.md file doesn't exist
- [ ] `SkillNotFoundError` raised when subagent doesn't exist
- [ ] Graceful handling when `agents/` directory doesn't exist (empty list)
- [ ] Graceful handling of malformed YAML frontmatter

### Metadata Parsing
- [ ] YAML frontmatter between `---` markers is parsed correctly
- [ ] `allowed-tools` metadata extracted (e.g., "Read,Glob,Bash")
- [ ] Missing frontmatter returns empty metadata dict
- [ ] Content returned without frontmatter markers

### Backward Compatibility
- [ ] Existing `BaseAgent.load_skill()` behavior preserved
- [ ] `BaseAgent` updated to use `SkillLoader` internally (optional)
- [ ] All existing agent tests continue to pass

---

## TDD Execution Protocol

### Phase 1: RED (Write Failing Tests)

Create `tests/unit/test_skill_loader.py`:

```python
"""Unit tests for SkillLoader.

Tests follow TDD RED phase - all tests should FAIL initially.
"""
import pytest
from pathlib import Path

from swarm_attack.skill_loader import SkillLoader, SkillDefinition, SkillNotFoundError


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create temporary skills directory structure."""
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    return skills


@pytest.fixture
def skill_with_subagents(skills_dir: Path) -> Path:
    """Create skill with nested agents."""
    skill_dir = skills_dir / "feature-builder"
    skill_dir.mkdir()

    # Main skill
    (skill_dir / "SKILL.md").write_text('''---
allowed-tools: Read,Glob,Bash
description: Feature builder skill
---
# Feature Builder

You build features.
''')

    # Nested agents
    agents_dir = skill_dir / "agents"
    agents_dir.mkdir()

    research_dir = agents_dir / "research"
    research_dir.mkdir()
    (research_dir / "SKILL.md").write_text('''---
allowed-tools: Read,Glob
---
# Research Agent
''')

    design_dir = agents_dir / "design"
    design_dir.mkdir()
    (design_dir / "SKILL.md").write_text('''---
allowed-tools: Read
---
# Design Agent
''')

    return skill_dir


@pytest.fixture
def skill_without_subagents(skills_dir: Path) -> Path:
    """Create skill without nested agents."""
    skill_dir = skills_dir / "simple-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('''---
allowed-tools: Read
---
# Simple Skill

No nested agents here.
''')
    return skill_dir


class TestSkillLoaderInit:
    """Tests for SkillLoader initialization."""

    def test_init_with_default_path(self):
        """Should use .claude/skills/ as default."""
        loader = SkillLoader()
        assert loader.skills_dir.name == "skills"

    def test_init_with_custom_path(self, skills_dir):
        """Should accept custom skills directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.skills_dir == skills_dir


class TestLoadSkill:
    """Tests for SkillLoader.load_skill()."""

    def test_load_skill_returns_skill_definition(self, skills_dir, skill_without_subagents):
        """Should return SkillDefinition instance."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert isinstance(result, SkillDefinition)
        assert result.name == "simple-skill"

    def test_load_skill_parses_content(self, skills_dir, skill_without_subagents):
        """Should return content without frontmatter."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert "# Simple Skill" in result.content
        assert "---" not in result.content
        assert "allowed-tools" not in result.content

    def test_load_skill_parses_metadata(self, skills_dir, skill_without_subagents):
        """Should parse YAML frontmatter into metadata dict."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.metadata.get("allowed-tools") == "Read"

    def test_load_skill_populates_subagents(self, skills_dir, skill_with_subagents):
        """Should populate subagents list when agents/ exists."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("feature-builder")

        assert "research" in result.subagents
        assert "design" in result.subagents

    def test_load_skill_empty_subagents_when_no_agents_dir(self, skills_dir, skill_without_subagents):
        """Should have empty subagents when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.subagents == []

    def test_load_skill_sets_path(self, skills_dir, skill_without_subagents):
        """Should set path to SKILL.md location."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.path == skills_dir / "simple-skill" / "SKILL.md"

    def test_load_skill_raises_for_missing_skill(self, skills_dir):
        """Should raise SkillNotFoundError for missing skill."""
        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_skill("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_load_skill_handles_missing_frontmatter(self, skills_dir):
        """Should handle skill without frontmatter."""
        skill_dir = skills_dir / "no-frontmatter"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just Content\n\nNo metadata here.")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("no-frontmatter")

        assert result.metadata == {}
        assert "# Just Content" in result.content


class TestLoadSubagent:
    """Tests for SkillLoader.load_subagent()."""

    def test_load_subagent_returns_definition(self, skills_dir, skill_with_subagents):
        """Should return SkillDefinition for subagent."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        assert isinstance(result, SkillDefinition)
        assert result.name == "research"

    def test_load_subagent_parses_content(self, skills_dir, skill_with_subagents):
        """Should parse subagent content and metadata."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        assert "# Research Agent" in result.content
        assert result.metadata.get("allowed-tools") == "Read,Glob"

    def test_load_subagent_correct_path(self, skills_dir, skill_with_subagents):
        """Should set correct path for subagent."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        expected = skills_dir / "feature-builder" / "agents" / "research" / "SKILL.md"
        assert result.path == expected

    def test_load_subagent_raises_for_missing(self, skills_dir, skill_with_subagents):
        """Should raise SkillNotFoundError for missing subagent."""
        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_subagent("feature-builder", "nonexistent")

        assert exc_info.value.is_subagent is True


class TestListSubagents:
    """Tests for SkillLoader.list_subagents()."""

    def test_list_subagents_returns_names(self, skills_dir, skill_with_subagents):
        """Should return list of subagent names."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("feature-builder")

        assert set(result) == {"research", "design"}

    def test_list_subagents_empty_when_no_agents(self, skills_dir, skill_without_subagents):
        """Should return empty list when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("simple-skill")

        assert result == []

    def test_list_subagents_ignores_files(self, skills_dir, skill_with_subagents):
        """Should only return directories, not files."""
        # Add a file in agents/ directory
        agents_dir = skills_dir / "feature-builder" / "agents"
        (agents_dir / "README.md").write_text("# Agents")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("feature-builder")

        assert "README" not in result
        assert "README.md" not in result


class TestHasSubagents:
    """Tests for SkillLoader.has_subagents()."""

    def test_has_subagents_true(self, skills_dir, skill_with_subagents):
        """Should return True when agents/ exists with subagents."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("feature-builder") is True

    def test_has_subagents_false_no_dir(self, skills_dir, skill_without_subagents):
        """Should return False when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("simple-skill") is False

    def test_has_subagents_false_empty_dir(self, skills_dir):
        """Should return False when agents/ is empty."""
        skill_dir = skills_dir / "empty-agents"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        (skill_dir / "agents").mkdir()  # Empty agents dir

        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("empty-agents") is False


class TestParseFrontmatter:
    """Tests for frontmatter parsing."""

    def test_parses_yaml_frontmatter(self, skills_dir):
        """Should parse YAML between --- markers."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = '''---
allowed-tools: Read,Glob
description: Test skill
version: 1.0
---
# Content here
'''
        text, metadata = loader._parse_frontmatter(content)

        assert metadata["allowed-tools"] == "Read,Glob"
        assert metadata["description"] == "Test skill"
        assert "# Content here" in text
        assert "---" not in text

    def test_handles_no_frontmatter(self, skills_dir):
        """Should return empty metadata when no frontmatter."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = "# Just content\n\nNo frontmatter here."
        text, metadata = loader._parse_frontmatter(content)

        assert metadata == {}
        assert text == content

    def test_handles_malformed_yaml(self, skills_dir):
        """Should handle malformed YAML gracefully."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = '''---
this is: not: valid: yaml
---
# Content
'''
        # Should not raise, return empty or partial metadata
        text, metadata = loader._parse_frontmatter(content)
        assert "# Content" in text
```

**Run to verify RED phase:**
```bash
pytest tests/unit/test_skill_loader.py -v
# Expected: ALL TESTS FAIL (SkillLoader doesn't exist yet)
```

---

### Phase 2: GREEN (Implement to Pass Tests)

Create `swarm_attack/skill_loader.py`:

1. Implement `SkillDefinition` dataclass
2. Implement `SkillNotFoundError` exception
3. Implement `SkillLoader` class with all methods
4. Use existing frontmatter parsing pattern from `BaseAgent`

**Run to verify GREEN phase:**
```bash
pytest tests/unit/test_skill_loader.py -v
# Expected: ALL TESTS PASS
```

---

### Phase 3: REFACTOR (Clean Up + Integration)

1. **Update BaseAgent** (optional) to use SkillLoader internally
2. **Run full test suite** to verify no regressions:
   ```bash
   pytest tests/ -v --tb=short
   ```
3. **Update any imports** if SkillNotFoundError moved to new location

---

## Pattern References

### Existing Frontmatter Parsing
From `swarm_attack/agents/base.py` lines 247-275:

```python
def load_skill_with_metadata(self, skill_name: str) -> tuple[str, dict]:
    """Load skill file and parse YAML frontmatter."""
    content = self.load_skill(skill_name)

    # Check for YAML frontmatter
    if not content.startswith("---"):
        return content, {}

    # Find end of frontmatter
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return content, {}

    # Parse YAML
    try:
        import yaml
        frontmatter = "\n".join(lines[1:end_idx])
        metadata = yaml.safe_load(frontmatter) or {}
    except Exception:
        metadata = {}

    # Return content without frontmatter
    body = "\n".join(lines[end_idx + 1:]).strip()
    return body, metadata
```

### Skill Discovery Pattern
From `swarm_attack/agents/base.py` lines 210-245:

```python
def load_skill(self, skill_name: str) -> str:
    """Load skill prompt from .claude/skills/{skill_name}/SKILL.md."""
    # Try multiple locations
    possible_paths = [
        Path(self.config.repo_root) / ".claude" / "skills" / skill_name / "SKILL.md",
        Path.cwd() / ".claude" / "skills" / skill_name / "SKILL.md",
    ]

    for path in possible_paths:
        if path.exists():
            return path.read_text()

    raise SkillNotFoundError(f"Skill '{skill_name}' not found")
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `swarm_attack/skill_loader.py` | Main implementation |
| `tests/unit/test_skill_loader.py` | Unit tests (TDD) |

## Files to Modify (Optional Integration)

| File | Change |
|------|--------|
| `swarm_attack/agents/base.py` | Use SkillLoader internally |
| `swarm_attack/errors.py` | Add SkillNotFoundError (if centralizing) |

---

## Success Criteria

Phase complete when:
1. [ ] All unit tests in `test_skill_loader.py` pass
2. [ ] `SkillLoader` class fully implemented with all methods
3. [ ] `SkillDefinition` dataclass with all fields
4. [ ] Nested agent discovery works (`list_subagents`, `has_subagents`)
5. [ ] Error handling robust (missing skills, malformed YAML)
6. [ ] Full test suite passes (no regressions)
7. [ ] Code reviewed for patterns consistency

---

## Execution Command

To run this implementation:

```
Execute specs/context-optimization/SKILLLOADER_TDD_PROMPT.md using TDD methodology.

Phase 1 (RED): Create tests/unit/test_skill_loader.py with all tests - verify they FAIL
Phase 2 (GREEN): Create swarm_attack/skill_loader.py - verify all tests PASS
Phase 3 (REFACTOR): Run full test suite, clean up code
```

---

## Reference Specifications

- **Parent Spec:** `specs/context-optimization/IMPLEMENTATION_PROMPT.md` (Feature 1, lines 34-92)
- **TDD Protocol:** Same file, lines 628-680
- **Existing Code:** `swarm_attack/agents/base.py` lines 210-299
