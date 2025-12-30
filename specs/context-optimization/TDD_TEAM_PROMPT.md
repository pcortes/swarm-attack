# TDD Implementation Prompt: P0 Context Optimization Fixes

You are orchestrating a **Team of Specialized Agents** to implement the P0 Context Optimization Fixes using strict **Test-Driven Development (TDD)** methodology.

---

## Spec Reference

Read the full specification at: `specs/context-optimization/P0_FIXES_SPEC.md`

**Summary of Fixes:**
1. **Fix #1:** Use rich context format in `CoderAgent._format_module_registry()`
2. **Fix #2:** Track classes in modified files via `_extract_outputs(files_modified=...)`

---

## Agent Team Composition

| Agent | Role | Responsibility |
|-------|------|----------------|
| **Test Architect** | Design test structure | Define test files, classes, fixtures |
| **Red Phase Agent** | Write failing tests | Create tests that define expected behavior |
| **Green Phase Agent** | Implement code | Write minimal code to pass tests |
| **Refactor Agent** | Clean up | Improve code quality without changing behavior |
| **Integration Agent** | End-to-end verification | Verify full system works together |

---

## TDD Workflow

Execute these phases IN ORDER. Do not skip phases.

### PHASE 1: Test Architecture (Test Architect Agent)

**Objective:** Design the test structure before writing any tests.

**Tasks:**
1. Create test file stubs:
   - `tests/unit/test_coder_rich_context.py`
   - `tests/unit/test_coder_modified_files.py`
   - `tests/integration/test_context_flow_fixes.py`

2. Define test class structure with docstrings (no implementations yet):
```python
"""Unit tests for CoderAgent rich context format (Fix #1)."""
import pytest
from pathlib import Path

class TestCoderRichContextFormat:
    """Tests for CoderAgent using rich module registry format."""

    def test_format_module_registry_shows_source_code(self):
        """Formatted registry should include class source code."""
        pass

    def test_format_module_registry_shows_import_statement(self):
        """Formatted registry should show how to import the class."""
        pass

    def test_format_module_registry_truncates_large_classes(self):
        """Large classes should be truncated to stay within token budget."""
        pass

    def test_format_module_registry_empty_returns_message(self):
        """Empty registry should return informative message."""
        pass
```

3. Define required fixtures:
```python
@pytest.fixture
def mock_config(tmp_path):
    """Create mock SwarmConfig with tmp_path as repo_root."""
    pass

@pytest.fixture
def sample_registry(tmp_path):
    """Create sample module registry with test files on disk."""
    pass
```

**Output:** Test file skeletons with `pass` implementations.

---

### PHASE 2: RED Phase (Red Phase Agent)

**Objective:** Write failing tests that define expected behavior.

**Rules:**
- Tests MUST fail initially (that's the point of RED phase)
- Tests define the CONTRACT - what the code SHOULD do
- Be specific about assertions
- Use descriptive test names

**Tasks for Fix #1 (Rich Context Format):**

```python
# tests/unit/test_coder_rich_context.py

class TestCoderRichContextFormat:

    def test_format_module_registry_shows_source_code(self, tmp_path):
        """Formatted registry should include class source code."""
        # Arrange: Create test file with a dataclass
        test_file = tmp_path / "swarm_attack" / "models" / "session.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('''
@dataclass
class AutopilotSession:
    session_id: str
    started_at: str

    def to_dict(self) -> dict:
        return {"session_id": self.session_id}
''')

        # Create config pointing to tmp_path
        config = create_mock_config(repo_root=tmp_path)

        # Create registry referencing the file
        registry = {
            "modules": {
                "swarm_attack/models/session.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession"],
                }
            }
        }

        # Act
        coder = CoderAgent(config)
        result = coder._format_module_registry(registry)

        # Assert: Should contain source code elements
        assert "session_id: str" in result, "Should show field definitions"
        assert "def to_dict" in result, "Should show method signatures"
        assert "DO NOT RECREATE" in result or "MUST IMPORT" in result, "Should warn against recreation"

    def test_format_module_registry_shows_import_statement(self, tmp_path):
        """Formatted registry should show how to import the class."""
        # Arrange
        test_file = tmp_path / "swarm_attack" / "models" / "user.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("class User:\n    pass")

        config = create_mock_config(repo_root=tmp_path)
        registry = {
            "modules": {
                "swarm_attack/models/user.py": {
                    "created_by_issue": 1,
                    "classes": ["User"],
                }
            }
        }

        # Act
        coder = CoderAgent(config)
        result = coder._format_module_registry(registry)

        # Assert
        assert "from swarm_attack.models.user import User" in result
```

**Tasks for Fix #2 (Modified File Tracking):**

```python
# tests/unit/test_coder_modified_files.py

class TestCoderModifiedFileTracking:

    def test_extract_outputs_tracks_modified_file_classes(self, tmp_path):
        """Classes in modified files should be tracked."""
        # Arrange: Create existing file on disk
        existing_file = tmp_path / "models" / "existing.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text('''
class ExistingClass:
    pass

class AddedClass:
    """Added by modification"""
    pass
''')

        config = create_mock_config(repo_root=tmp_path)
        coder = CoderAgent(config)

        # Act: Extract with modified file (no new files)
        result = coder._extract_outputs(
            files={},
            files_modified=["models/existing.py"],
        )

        # Assert
        assert "models/existing.py" in result.classes_defined
        assert "ExistingClass" in result.classes_defined["models/existing.py"]
        assert "AddedClass" in result.classes_defined["models/existing.py"]

    def test_extract_classes_from_content_python(self):
        """Should extract Python class definitions."""
        config = create_mock_config()
        coder = CoderAgent(config)

        content = '''
class SimpleClass:
    pass

class ClassWithBase(BaseClass):
    pass

@dataclass
class DataClass:
    field: str
'''
        result = coder._extract_classes_from_content("test.py", content)

        assert "SimpleClass" in result
        assert "ClassWithBase" in result
        assert "DataClass" in result

    def test_parse_modified_files_extracts_patterns(self):
        """Should parse modified file patterns from LLM response."""
        config = create_mock_config()
        coder = CoderAgent(config)

        response = '''
I modified the existing file:
# MODIFIED FILE: models/session.py

Updated: utils/helpers.py
'''
        result = coder._parse_modified_files(response)

        assert "models/session.py" in result
        assert "utils/helpers.py" in result
```

**Verify RED Phase:**
```bash
pytest tests/unit/test_coder_rich_context.py tests/unit/test_coder_modified_files.py -v
# Expected: ALL TESTS FAIL (methods don't exist yet or return wrong values)
```

---

### PHASE 3: GREEN Phase (Green Phase Agent)

**Objective:** Write MINIMAL code to make tests pass.

**Rules:**
- Write the SIMPLEST code that passes tests
- Don't add features not covered by tests
- Don't optimize prematurely
- One test at a time if needed

**Tasks for Fix #1:**

```python
# In swarm_attack/agents/coder.py

def _format_module_registry(self, registry: Optional[dict[str, Any]]) -> str:
    """Format module registry with source code for LLM consumption.

    Uses ContextBuilder's rich format to show actual class definitions,
    enabling the coder to understand interfaces without guessing.

    Args:
        registry: Module registry from StateStore.get_module_registry()

    Returns:
        Formatted markdown string with class source code.
    """
    if not registry or not registry.get("modules"):
        return "No prior modules created for this feature."

    # Use rich format from ContextBuilder
    from swarm_attack.context_builder import ContextBuilder
    ctx_builder = ContextBuilder(self.config, self._state_store)
    return ctx_builder.format_module_registry_with_source(
        registry,
        max_chars_per_class=2000,
    )
```

**Tasks for Fix #2:**

```python
# In swarm_attack/agents/coder.py

def _extract_classes_from_content(self, path: str, content: str) -> list[str]:
    """Extract class names from file content.

    Args:
        path: File path (determines language by extension).
        content: File content to parse.

    Returns:
        List of class names found.
    """
    classes: list[str] = []

    if path.endswith(".py"):
        matches = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)
    elif path.endswith(".ts") or path.endswith(".tsx"):
        matches = re.findall(r"(?:export\s+)?class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)
    elif path.endswith(".dart"):
        matches = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)

    return classes


def _parse_modified_files(self, response_text: str) -> list[str]:
    """Parse LLM response for files that were modified.

    Args:
        response_text: Raw LLM response text.

    Returns:
        List of file paths that were modified.
    """
    modified: list[str] = []

    # Pattern: # MODIFIED FILE: path
    pattern1 = re.findall(r"#\s*MODIFIED\s*FILE:\s*(.+\.py)", response_text)
    modified.extend(pattern1)

    # Pattern: Modified: path or Updated: path
    pattern2 = re.findall(r"(?:Modified|Updated):\s*[`']?([^\s`']+\.py)[`']?", response_text)
    modified.extend(pattern2)

    return list(set(p.strip() for p in modified))


def _extract_outputs(
    self,
    files: dict[str, str],
    files_modified: Optional[list[str]] = None,
) -> IssueOutput:
    """Extract output metadata from coder results.

    Args:
        files: Dict of {path: content} for newly created files.
        files_modified: List of paths to modified files.

    Returns:
        IssueOutput with files_created and classes_defined.
    """
    files_created = list(files.keys())
    classes_defined: dict[str, list[str]] = {}

    # Extract from NEW files
    for path, content in files.items():
        classes = self._extract_classes_from_content(path, content)
        if classes:
            classes_defined[path] = classes

    # Extract from MODIFIED files (read from disk)
    if files_modified:
        for path in files_modified:
            full_path = Path(self.config.repo_root) / path
            if full_path.exists() and path.endswith(".py"):
                try:
                    content = full_path.read_text()
                    classes = self._extract_classes_from_content(path, content)
                    if classes:
                        existing = classes_defined.get(path, [])
                        classes_defined[path] = list(set(existing + classes))
                except (IOError, OSError):
                    pass

    return IssueOutput(
        files_created=files_created,
        classes_defined=classes_defined,
    )
```

**Verify GREEN Phase:**
```bash
pytest tests/unit/test_coder_rich_context.py tests/unit/test_coder_modified_files.py -v
# Expected: ALL TESTS PASS
```

---

### PHASE 4: Integration Tests (Integration Agent)

**Objective:** Verify the fixes work together in realistic scenarios.

```python
# tests/integration/test_context_flow_fixes.py

class TestContextFlowFixes:
    """Integration tests for P0 context optimization fixes."""

    def test_issue_2_sees_issue_1_class_source_in_prompt(self, tmp_path):
        """Issue #2's prompt should contain Issue #1's class source code."""
        # Setup Issue #1 completion
        session_file = tmp_path / "swarm_attack" / "models" / "session.py"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text('''
@dataclass
class AutopilotSession:
    session_id: str
    feature_id: str

    def to_dict(self) -> dict:
        return {"session_id": self.session_id}
''')

        # Create state with Issue #1 completed
        config = create_mock_config(repo_root=tmp_path)
        state_store = StateStore(config)
        state_store.save_issue_outputs("test-feature", 1, IssueOutput(
            files_created=["swarm_attack/models/session.py"],
            classes_defined={"swarm_attack/models/session.py": ["AutopilotSession"]},
        ))

        # Get module registry for Issue #2
        registry = state_store.get_module_registry("test-feature")

        # Format for prompt
        coder = CoderAgent(config)
        formatted = coder._format_module_registry(registry)

        # Verify source code is included
        assert "session_id: str" in formatted
        assert "def to_dict" in formatted
        assert "from swarm_attack.models.session import AutopilotSession" in formatted

    def test_schema_drift_detected_for_modified_file_class(self, tmp_path):
        """Schema drift should be detected when class added to modified file."""
        # Issue #1 modifies existing file, adds ClassA
        existing_file = tmp_path / "models" / "base.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("class ClassA:\n    pass")

        config = create_mock_config(repo_root=tmp_path)
        coder = CoderAgent(config)

        # Extract outputs including modified file
        outputs = coder._extract_outputs(
            files={},
            files_modified=["models/base.py"],
        )

        # ClassA should be tracked
        assert "ClassA" in outputs.classes_defined.get("models/base.py", [])

        # Now Issue #2 tries to create ClassA in different file
        # Verifier should detect this as schema drift
        verifier = VerifierAgent(config)
        conflicts = verifier._check_duplicate_classes(
            new_classes={"models/new.py": ["ClassA"]},
            registry={"modules": {"models/base.py": {"classes": ["ClassA"], "created_by_issue": 1}}},
        )

        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "ClassA"
```

**Verify Integration:**
```bash
pytest tests/integration/test_context_flow_fixes.py -v
# Expected: ALL TESTS PASS
```

---

### PHASE 5: Full Suite Verification (Refactor Agent)

**Objective:** Ensure no regressions and clean up code.

**Tasks:**
1. Run full test suite:
```bash
pytest tests/ -v --tb=short
```

2. Check for any regressions in existing tests

3. Refactor if needed (improve code without changing behavior):
   - Add missing docstrings
   - Extract common patterns
   - Improve error messages

4. Final verification:
```bash
pytest tests/ -v
# Expected: ALL TESTS PASS, including existing tests
```

---

## Execution Instructions

### For Human Orchestrator

Run this prompt by launching agents in sequence:

```
1. Launch Test Architect Agent:
   "Create test file stubs per PHASE 1 in specs/context-optimization/TDD_TEAM_PROMPT.md"

2. Launch Red Phase Agent:
   "Implement failing tests per PHASE 2 in specs/context-optimization/TDD_TEAM_PROMPT.md"

3. Verify RED: Run pytest, confirm all tests FAIL

4. Launch Green Phase Agent:
   "Implement code to pass tests per PHASE 3 in specs/context-optimization/TDD_TEAM_PROMPT.md"

5. Verify GREEN: Run pytest, confirm all tests PASS

6. Launch Integration Agent:
   "Create integration tests per PHASE 4 in specs/context-optimization/TDD_TEAM_PROMPT.md"

7. Launch Refactor Agent:
   "Run full suite and refactor per PHASE 5 in specs/context-optimization/TDD_TEAM_PROMPT.md"
```

### For AI Orchestrator (Claude Code)

```python
# Launch all test-writing agents in parallel (RED phase)
agents = [
    Task(subagent_type="general-purpose", prompt="Read specs/context-optimization/TDD_TEAM_PROMPT.md PHASE 2. Write tests/unit/test_coder_rich_context.py with all test implementations. Tests should FAIL initially."),
    Task(subagent_type="general-purpose", prompt="Read specs/context-optimization/TDD_TEAM_PROMPT.md PHASE 2. Write tests/unit/test_coder_modified_files.py with all test implementations. Tests should FAIL initially."),
    Task(subagent_type="general-purpose", prompt="Read specs/context-optimization/TDD_TEAM_PROMPT.md PHASE 4. Write tests/integration/test_context_flow_fixes.py with all test implementations."),
]

# After tests written, launch implementation agent (GREEN phase)
Task(subagent_type="general-purpose", prompt="Read specs/context-optimization/TDD_TEAM_PROMPT.md PHASE 3. Implement the code changes in swarm_attack/agents/coder.py to make all tests pass.")

# Verify
Bash("pytest tests/unit/test_coder_rich_context.py tests/unit/test_coder_modified_files.py tests/integration/test_context_flow_fixes.py -v")
```

---

## Success Criteria

| Phase | Criteria |
|-------|----------|
| RED | All new tests exist and FAIL |
| GREEN | All new tests PASS |
| Integration | Integration tests PASS |
| Refactor | Full suite PASSES, no regressions |

---

## Files to Create/Modify

**Create:**
- `tests/unit/test_coder_rich_context.py`
- `tests/unit/test_coder_modified_files.py`
- `tests/integration/test_context_flow_fixes.py`

**Modify:**
- `swarm_attack/agents/coder.py`
  - `_format_module_registry()` - use rich format
  - `_extract_outputs()` - add `files_modified` param
  - `_extract_classes_from_content()` - new method
  - `_parse_modified_files()` - new method
