# P0 Context Optimization Fixes Specification

## Overview

This spec addresses two critical root causes of issue-to-issue context loss identified by the Expert Review Panel.

**Problem Statement:**
When implementing Issue N+1, the CoderAgent lacks sufficient context about what Issue N created, leading to:
1. Duplicate class definitions (schema drift)
2. Import errors
3. Wasted tokens on failed attempts

**Root Causes Identified:**
1. Rich context format exists in `ContextBuilder` but CoderAgent uses basic format
2. Classes added to modified files (not new files) are not tracked

---

## Fix #1: Use Rich Context Format in CoderAgent

### Current State

**File:** `swarm_attack/agents/coder.py:792-825`

```python
def _format_module_registry(self, registry: Optional[dict[str, Any]]) -> str:
    """Current implementation - shows ONLY class names."""
    if not registry or not registry.get("modules"):
        return "No prior modules created for this feature."

    modules = registry.get("modules", {})
    lines = ["**Files and classes created by prior issues:**", ""]
    for file_path, info in modules.items():
        classes = info.get("classes", [])
        issue_num = info.get("created_by_issue", "?")
        if classes:
            class_list = ", ".join(classes)
            lines.append(f"- `{file_path}` (issue #{issue_num}): {class_list}")
    # ...
```

**Output Example:**
```
- `swarm_attack/models/session.py` (issue #1): AutopilotSession, SessionState
```

**Problem:** Coder sees class EXISTS but not its fields, methods, or how to use it.

### Desired State

**Use existing method:** `ContextBuilder.format_module_registry_with_source()`

**File:** `swarm_attack/context_builder.py:374-464`

This method already exists and shows:
- Import statement
- Full class source code (with truncation for large classes)
- Schema evolution guidance

**Output Example:**
```markdown
## Existing Classes (MUST IMPORT - DO NOT RECREATE)

### From `swarm_attack/models/session.py` (Issue #1)
**Import:** `from swarm_attack.models.session import AutopilotSession, SessionState`

**Class `AutopilotSession`:**
```python
@dataclass
class AutopilotSession:
    session_id: str
    feature_id: str
    started_at: str
    goals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        ...
```
```

### Implementation

#### Changes Required

**File:** `swarm_attack/agents/coder.py`

1. Add import for ContextBuilder at top of file
2. Modify `_format_module_registry()` to use rich format OR
3. Modify `_build_prompt()` to call `ContextBuilder.format_module_registry_with_source()`

#### Option A: Modify `_format_module_registry()` (Preferred)

```python
def _format_module_registry(self, registry: Optional[dict[str, Any]]) -> str:
    """Format module registry with source code for LLM consumption.

    Uses ContextBuilder's rich format to show actual class definitions,
    enabling the coder to understand interfaces without guessing.
    """
    if not registry or not registry.get("modules"):
        return "No prior modules created for this feature."

    # Use rich format from ContextBuilder
    from swarm_attack.context_builder import ContextBuilder
    ctx_builder = ContextBuilder(self.config, self._state_store)
    return ctx_builder.format_module_registry_with_source(
        registry,
        max_chars_per_class=2000,  # Token budget ~500 tokens/class
    )
```

#### Token Budget Consideration

- Basic format: ~5 tokens per class
- Rich format: ~300-800 tokens per class (with 2000 char limit)
- For 5 classes: ~1500-4000 tokens
- Acceptable given context window of 200k tokens

### Test Cases

```python
# tests/unit/test_coder_rich_context.py

class TestCoderRichContextFormat:
    """Tests for CoderAgent using rich module registry format."""

    def test_format_module_registry_shows_source_code(self, tmp_path, mock_config):
        """Formatted registry should include class source code."""
        # Create a test file with a class
        test_file = tmp_path / "swarm_attack" / "models" / "test.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('''
@dataclass
class TestClass:
    field1: str
    field2: int = 0

    def to_dict(self) -> dict:
        return {"field1": self.field1}
''')

        registry = {
            "modules": {
                "swarm_attack/models/test.py": {
                    "created_by_issue": 1,
                    "classes": ["TestClass"],
                }
            }
        }

        coder = CoderAgent(mock_config)
        result = coder._format_module_registry(registry)

        # Should contain source code, not just class name
        assert "field1: str" in result
        assert "def to_dict" in result
        assert "MUST IMPORT" in result or "DO NOT RECREATE" in result

    def test_format_module_registry_shows_import_statement(self, tmp_path, mock_config):
        """Formatted registry should show how to import the class."""
        # ... setup ...
        result = coder._format_module_registry(registry)

        assert "from swarm_attack.models.test import TestClass" in result

    def test_format_module_registry_truncates_large_classes(self, tmp_path, mock_config):
        """Large classes should be truncated to stay within token budget."""
        # Create file with large class (> 2000 chars)
        large_class = "@dataclass\nclass LargeClass:\n" + "\n".join(
            f"    field{i}: str" for i in range(100)
        )
        # ...
        result = coder._format_module_registry(registry)

        assert len(result) < 5000  # Reasonable limit
        assert "truncated" in result.lower() or "..." in result

    def test_format_module_registry_empty_returns_message(self, mock_config):
        """Empty registry should return informative message."""
        coder = CoderAgent(mock_config)
        result = coder._format_module_registry({})

        assert "No prior modules" in result
```

---

## Fix #2: Track Classes in Modified Files

### Current State

**File:** `swarm_attack/agents/coder.py:1215-1255`

```python
def _extract_outputs(self, files: dict[str, str]) -> IssueOutput:
    """Current implementation - only tracks NEW files."""
    files_created = list(files.keys())  # <-- Only new files
    classes_defined: dict[str, list[str]] = {}

    for path, content in files.items():  # <-- Only iterates new files
        if path.endswith(".py"):
            matches = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
            if matches:
                classes_defined[path] = matches

    return IssueOutput(
        files_created=files_created,
        classes_defined=classes_defined,
    )
```

**Problem:** If coder modifies an existing file and adds classes, those classes are NOT tracked.

### Desired State

Track classes in BOTH:
1. Newly created files (existing behavior)
2. Modified existing files (new behavior)

### Implementation

#### Changes Required

**File:** `swarm_attack/agents/coder.py`

1. Modify `_extract_outputs()` signature to accept `files_modified` parameter
2. Read modified files from disk and extract classes
3. Update call sites in `run()` method

#### Updated Method

```python
def _extract_outputs(
    self,
    files: dict[str, str],
    files_modified: Optional[list[str]] = None,
) -> IssueOutput:
    """Extract output metadata from coder results.

    Extracts:
    - files_created: List of new file paths
    - classes_defined: Dict mapping file paths to class names

    Args:
        files: Dict of {path: content} for newly created files.
        files_modified: List of paths to files that were modified (not created).
                       Classes will be extracted from these files on disk.

    Returns:
        IssueOutput with files_created and classes_defined.
    """
    files_created = list(files.keys())
    classes_defined: dict[str, list[str]] = {}

    # Extract classes from NEW files (from content in memory)
    for path, content in files.items():
        classes = self._extract_classes_from_content(path, content)
        if classes:
            classes_defined[path] = classes

    # NEW: Extract classes from MODIFIED files (read from disk)
    if files_modified:
        for path in files_modified:
            full_path = Path(self.config.repo_root) / path
            if full_path.exists() and path.endswith(".py"):
                try:
                    content = full_path.read_text()
                    classes = self._extract_classes_from_content(path, content)
                    if classes:
                        # Merge with any existing (in case file was both created and modified)
                        existing = classes_defined.get(path, [])
                        classes_defined[path] = list(set(existing + classes))
                except (IOError, OSError):
                    pass  # Skip unreadable files

    return IssueOutput(
        files_created=files_created,
        classes_defined=classes_defined,
    )


def _extract_classes_from_content(self, path: str, content: str) -> list[str]:
    """Extract class names from file content.

    Supports Python, TypeScript, and Dart files.

    Args:
        path: File path (used to determine language).
        content: File content to parse.

    Returns:
        List of class names found.
    """
    classes: list[str] = []

    if path.endswith(".py"):
        # Python: class ClassName or class ClassName(Base)
        matches = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)
    elif path.endswith(".ts") or path.endswith(".tsx"):
        # TypeScript: class ClassName or export class ClassName
        matches = re.findall(r"(?:export\s+)?class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)
    elif path.endswith(".dart"):
        # Dart: class ClassName
        matches = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        classes.extend(matches)

    return classes
```

#### Update Call Site

**File:** `swarm_attack/agents/coder.py:1920` (approximate)

```python
# In run() method, after parsing files:
files = self._parse_file_outputs(result.text)
files_modified = self._parse_modified_files(result.text)  # NEW

issue_outputs = self._extract_outputs(
    files,
    files_modified=files_modified,  # NEW
)
```

#### Add Helper Method

```python
def _parse_modified_files(self, response_text: str) -> list[str]:
    """Parse LLM response for files that were modified (not created).

    Looks for patterns like:
    - "Modified: path/to/file.py"
    - "Updated: path/to/file.py"
    - "# MODIFIED FILE: path/to/file.py"

    Args:
        response_text: Raw LLM response text.

    Returns:
        List of file paths that were modified.
    """
    modified: list[str] = []

    # Pattern 1: # MODIFIED FILE: path
    pattern1 = re.findall(r"#\s*MODIFIED\s*FILE:\s*(.+\.py)", response_text)
    modified.extend(pattern1)

    # Pattern 2: Modified: path or Updated: path
    pattern2 = re.findall(r"(?:Modified|Updated):\s*[`']?(.+\.py)[`']?", response_text)
    modified.extend(pattern2)

    # Deduplicate and clean
    return list(set(p.strip() for p in modified))
```

### Test Cases

```python
# tests/unit/test_coder_modified_files.py

class TestCoderModifiedFileTracking:
    """Tests for tracking classes in modified files."""

    def test_extract_outputs_tracks_new_file_classes(self, mock_config):
        """Classes in new files should be tracked (existing behavior)."""
        coder = CoderAgent(mock_config)
        files = {
            "models/user.py": "class User:\n    pass\n\nclass UserFactory:\n    pass"
        }

        result = coder._extract_outputs(files)

        assert "models/user.py" in result.classes_defined
        assert "User" in result.classes_defined["models/user.py"]
        assert "UserFactory" in result.classes_defined["models/user.py"]

    def test_extract_outputs_tracks_modified_file_classes(self, tmp_path, mock_config):
        """Classes in modified files should be tracked (new behavior)."""
        # Create existing file on disk
        existing_file = tmp_path / "models" / "existing.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("class ExistingClass:\n    pass\n\nclass AddedClass:\n    pass")

        mock_config.repo_root = tmp_path
        coder = CoderAgent(mock_config)

        # No new files, but modified file
        files = {}
        files_modified = ["models/existing.py"]

        result = coder._extract_outputs(files, files_modified=files_modified)

        assert "models/existing.py" in result.classes_defined
        assert "ExistingClass" in result.classes_defined["models/existing.py"]
        assert "AddedClass" in result.classes_defined["models/existing.py"]

    def test_extract_outputs_merges_new_and_modified(self, tmp_path, mock_config):
        """Both new and modified files should be tracked together."""
        # Create existing file
        existing_file = tmp_path / "models" / "existing.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("class ExistingClass:\n    pass")

        mock_config.repo_root = tmp_path
        coder = CoderAgent(mock_config)

        # New file + modified file
        files = {"models/new.py": "class NewClass:\n    pass"}
        files_modified = ["models/existing.py"]

        result = coder._extract_outputs(files, files_modified=files_modified)

        assert "models/new.py" in result.classes_defined
        assert "models/existing.py" in result.classes_defined
        assert "NewClass" in result.classes_defined["models/new.py"]
        assert "ExistingClass" in result.classes_defined["models/existing.py"]

    def test_extract_outputs_handles_missing_modified_file(self, tmp_path, mock_config):
        """Missing modified files should be skipped gracefully."""
        mock_config.repo_root = tmp_path
        coder = CoderAgent(mock_config)

        files = {}
        files_modified = ["models/nonexistent.py"]  # Does not exist

        result = coder._extract_outputs(files, files_modified=files_modified)

        # Should not raise, should have empty classes_defined
        assert result.classes_defined == {}

    def test_parse_modified_files_extracts_patterns(self, mock_config):
        """Should parse various modified file patterns from LLM response."""
        coder = CoderAgent(mock_config)

        response = '''
I'll modify the existing file:
# MODIFIED FILE: models/session.py

And update another:
Modified: `utils/helpers.py`

Updated: config/settings.py
'''

        result = coder._parse_modified_files(response)

        assert "models/session.py" in result
        assert "utils/helpers.py" in result
        assert "config/settings.py" in result


class TestExtractClassesFromContent:
    """Tests for class extraction helper."""

    def test_extracts_python_classes(self, mock_config):
        """Should extract Python class definitions."""
        coder = CoderAgent(mock_config)
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

    def test_extracts_typescript_classes(self, mock_config):
        """Should extract TypeScript class definitions."""
        coder = CoderAgent(mock_config)
        content = '''
class SimpleClass {}

export class ExportedClass {}

abstract class AbstractClass {}
'''
        result = coder._extract_classes_from_content("test.ts", content)

        assert "SimpleClass" in result
        assert "ExportedClass" in result

    def test_returns_empty_for_unsupported_extension(self, mock_config):
        """Should return empty list for unsupported file types."""
        coder = CoderAgent(mock_config)
        result = coder._extract_classes_from_content("test.txt", "class Foo {}")

        assert result == []
```

---

## Integration Test

```python
# tests/integration/test_context_flow_fixes.py

class TestContextFlowFixes:
    """Integration tests for P0 context optimization fixes."""

    def test_issue_2_sees_issue_1_class_source(self, tmp_path, mock_orchestrator):
        """Issue #2 should see Issue #1's class source code in prompt."""
        # Setup: Issue #1 creates a class
        issue1_file = tmp_path / "swarm_attack" / "models" / "session.py"
        issue1_file.parent.mkdir(parents=True, exist_ok=True)
        issue1_file.write_text('''
@dataclass
class AutopilotSession:
    session_id: str
    started_at: str

    def to_dict(self) -> dict:
        return {"session_id": self.session_id}
''')

        # Simulate Issue #1 completion
        mock_orchestrator.state_store.save_issue_outputs("feature-1", 1, IssueOutput(
            files_created=["swarm_attack/models/session.py"],
            classes_defined={"swarm_attack/models/session.py": ["AutopilotSession"]},
        ))
        mock_orchestrator.state_store.mark_task_done("feature-1", 1)

        # Issue #2 starts - get its context
        context = mock_orchestrator._prepare_coder_context("feature-1", 2)

        # Build prompt for Issue #2
        coder = CoderAgent(mock_orchestrator.config)
        prompt = coder._build_prompt(
            issue={"title": "Add goal tracking", "body": "..."},
            module_registry=context["module_registry"],
            completed_summaries=context["completed_summaries"],
        )

        # VERIFY: Prompt contains class source code, not just name
        assert "session_id: str" in prompt
        assert "def to_dict" in prompt
        assert "from swarm_attack.models.session import AutopilotSession" in prompt

    def test_modified_file_classes_propagate_to_registry(self, tmp_path, mock_orchestrator):
        """Classes added to modified files should appear in module registry."""
        # Setup: Existing file with one class
        existing_file = tmp_path / "swarm_attack" / "models" / "base.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("class BaseModel:\n    pass")

        # Simulate Issue #1 modifying the file to add a class
        existing_file.write_text('''
class BaseModel:
    pass

class ExtendedModel(BaseModel):
    """Added by Issue #1"""
    pass
''')

        # Coder extracts outputs with modified file tracking
        coder = CoderAgent(mock_orchestrator.config)
        coder.config.repo_root = tmp_path

        issue_outputs = coder._extract_outputs(
            files={},  # No new files
            files_modified=["swarm_attack/models/base.py"],
        )

        # VERIFY: Both classes are tracked
        assert "swarm_attack/models/base.py" in issue_outputs.classes_defined
        assert "BaseModel" in issue_outputs.classes_defined["swarm_attack/models/base.py"]
        assert "ExtendedModel" in issue_outputs.classes_defined["swarm_attack/models/base.py"]
```

---

## Rollout Plan

### Phase 1: Write Tests (RED)
1. Create `tests/unit/test_coder_rich_context.py`
2. Create `tests/unit/test_coder_modified_files.py`
3. Create `tests/integration/test_context_flow_fixes.py`
4. Run tests - verify they FAIL

### Phase 2: Implement Fixes (GREEN)
1. Modify `CoderAgent._format_module_registry()` to use rich format
2. Add `CoderAgent._extract_classes_from_content()` helper
3. Modify `CoderAgent._extract_outputs()` to accept `files_modified`
4. Add `CoderAgent._parse_modified_files()` helper
5. Update call site in `CoderAgent.run()`
6. Run tests - verify they PASS

### Phase 3: Verify (REFACTOR)
1. Run full test suite: `pytest tests/ -v`
2. Verify no regressions
3. Manual verification with sample feature

---

## Success Metrics

| Metric | Before | After | How to Measure |
|--------|--------|-------|----------------|
| Class source in prompt | No | Yes | Grep prompt for "def " |
| Modified file classes tracked | No | Yes | Check IssueOutput.classes_defined |
| Schema drift on modified files | Possible | Detected | Run schema drift scenario |
| Existing tests pass | 100% | 100% | `pytest tests/` |

---

## Files Changed

**New Files:**
- `tests/unit/test_coder_rich_context.py`
- `tests/unit/test_coder_modified_files.py`
- `tests/integration/test_context_flow_fixes.py`

**Modified Files:**
- `swarm_attack/agents/coder.py` (~50 lines changed)
  - `_format_module_registry()` - use rich format
  - `_extract_outputs()` - add `files_modified` param
  - `_extract_classes_from_content()` - new helper
  - `_parse_modified_files()` - new helper
