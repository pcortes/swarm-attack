# Schema Drift Prevention: Implementation Plan

## Overview

Prevent schema drift between issues by:
1. **GitHub Issue Context Propagation**: LLM-generated summaries added to completed issues and propagated to dependents
2. **Compact Schema Injection**: Structured schema for exact import paths (backup/validation)
3. **Detection Gate**: Hard fail on duplicate class creation (safety net)

## Phase 1: GitHub Issue Context Propagation (P0)

### 1.1 LLM Summarizer

**File**: `swarm_attack/agents/summarizer.py` (new)

```python
class IssueSummarizer:
    """Generates implementation summaries after issue completion."""

    SUMMARY_PROMPT = '''
    Analyze the completed issue implementation and generate a structured summary.

    ## Issue
    {issue_body}

    ## Files Changed
    {diff}

    ## Generate Summary

    Output a markdown summary with:
    1. **Files Created/Modified**: List with brief purpose
    2. **Classes Defined**: Table with Class | Purpose | Key Fields
    3. **Usage Patterns**: How to instantiate and use the classes
    4. **Import Statement**: Ready-to-copy import block

    Keep it concise (<300 tokens). Focus on what other issues need to know.
    '''

    async def summarize(self, issue: Issue, diff: str) -> str:
        """Generate implementation summary for completed issue."""

    def format_summary_section(self, summary: str) -> str:
        """Wrap summary in collapsible markdown section."""
        return f'''
<details>
<summary>📋 Implementation Summary (Auto-generated)</summary>

{summary}

</details>
'''
```

### 1.2 GitHub Issue Updater

**File**: `swarm_attack/github/issue_context.py` (new)

```python
class IssueContextManager:
    """Manages context propagation between issues."""

    async def add_summary_to_issue(self, issue_number: int, summary: str):
        """Append implementation summary to completed issue."""

    async def propagate_to_dependents(
        self,
        completed_issue: int,
        dependent_issues: list[int],
        summary: str
    ):
        """Add context section to all dependent issues."""

    def format_dependency_context(self, source_issue: int, summary: str) -> str:
        """Format context for injection into dependent issue."""
        return f'''
<details>
<summary>📦 Context from Issue #{source_issue} (Auto-generated)</summary>

{summary}

**⚠️ DO NOT recreate classes defined above. Import and use them.**

</details>
'''
```

### 1.3 Integration Point

**File**: `swarm_attack/orchestrator.py`

```python
# After issue verification passes:
async def _on_issue_completed(self, issue: Issue, result: VerificationResult):
    # Generate summary
    summarizer = IssueSummarizer()
    summary = await summarizer.summarize(issue, result.diff)

    # Update GitHub issues
    context_mgr = IssueContextManager(self.github_client)
    await context_mgr.add_summary_to_issue(issue.number, summary)

    # Propagate to dependents
    dependents = self._get_dependent_issues(issue.number)
    await context_mgr.propagate_to_dependents(issue.number, dependents, summary)
```

## Phase 2: Transitive Dependency Computation (P0)

### 2.1 Dependency Graph

**File**: `swarm_attack/planning/dependency_graph.py`

```python
class DependencyGraph:
    """Computes transitive closure of issue dependencies."""

    def __init__(self, issues: list[Issue]):
        self.graph = self._build_graph(issues)

    def get_transitive_dependencies(self, issue_number: int) -> set[int]:
        """Return all issues this issue transitively depends on."""
        visited = set()
        self._dfs(issue_number, visited)
        visited.discard(issue_number)  # Don't include self
        return visited

    def _dfs(self, node: int, visited: set[int]):
        if node in visited:
            return
        visited.add(node)
        for dep in self.graph.get(node, []):
            self._dfs(dep, visited)
```

### 2.2 Update Context Builder

**File**: `swarm_attack/context/context_builder.py`

```python
def build_coder_context(self, issue: Issue, all_issues: list[Issue]) -> str:
    # Compute transitive deps
    graph = DependencyGraph(all_issues)
    all_deps = graph.get_transitive_dependencies(issue.number)

    # Schema injection uses transitive deps
    schema_context = self.format_module_registry_compact(
        self.module_registry,
        dependencies=all_deps  # Was: issue.dependencies (direct only)
    )
```

## Phase 3: Detection Gate Improvements (P1)

### 3.1 Subclass Detection

**File**: `swarm_attack/agents/verifier.py`

```python
def _check_duplicate_classes(
    self,
    new_classes_defined: dict[str, list[str]],
    module_registry: dict,
) -> list[str]:
    errors = []

    existing = self._build_existing_class_map(module_registry)

    for new_file, classes in new_classes_defined.items():
        for cls in classes:
            if cls in existing and existing[cls][0] != new_file:
                # Check if it's a subclass (allowed)
                if self._is_subclass_of_existing(new_file, cls, existing[cls][0]):
                    continue  # Subclassing is fine

                orig_file, orig_issue = existing[cls]
                errors.append(
                    f"SCHEMA DRIFT: Class '{cls}' already exists in "
                    f"'{orig_file}' (Issue #{orig_issue}). "
                    f"Import it instead of recreating in '{new_file}'."
                )

    return errors

def _is_subclass_of_existing(
    self,
    new_file: str,
    class_name: str,
    existing_file: str
) -> bool:
    """Check if new class inherits from the existing class."""
    try:
        tree = ast.parse(Path(new_file).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for base in node.bases:
                    base_name = self._get_base_name(base)
                    if base_name and base_name in self._get_classes_in_file(existing_file):
                        return True
        return False
    except Exception:
        return False  # Can't parse, assume not subclass
```

## Phase 4: Compact Schema (Backup/Validation)

### 4.1 Compact Format

**File**: `swarm_attack/context/context_builder.py`

```python
def format_module_registry_compact(
    self,
    registry: dict,
    dependencies: set[int],
) -> str:
    """
    Compact schema injection as validation layer.

    This supplements GitHub issue context by providing exact:
    - Import paths
    - Field types
    - Method signatures

    Token budget: ~50 tokens per class × ~10 relevant classes = ~500 tokens
    """
    lines = [
        "## Existing Classes Reference",
        "",
        "Classes from dependency issues (import these, do not recreate):",
        ""
    ]

    for file_path, info in registry.get("modules", {}).items():
        issue_num = info.get("created_by_issue")

        # Filter to transitive dependencies
        if issue_num not in dependencies:
            continue

        import_path = self._path_to_module(file_path)

        for class_name in info.get("classes", []):
            schema = self._extract_class_schema_safe(file_path, class_name)

            # Compact format
            fields = ", ".join(
                f"{f['name']}: {f['type']}"
                for f in schema.get("fields", [])[:8]
            )
            methods = ", ".join(schema.get("methods", [])[:5])

            lines.append(f"**{class_name}** (`{file_path}`)")
            lines.append(f"  Import: `from {import_path} import {class_name}`")
            if fields:
                lines.append(f"  Fields: {fields}")
            if methods:
                lines.append(f"  Methods: {methods}")
            lines.append("")

    if len(lines) > 5:  # Has actual content
        lines.append("**⚠️ DO NOT recreate these classes. Import and use them.**")

    return "\n".join(lines)

def _extract_class_schema_safe(self, file_path: str, class_name: str) -> dict:
    """Extract schema with fallback for unparseable files."""
    try:
        return self._extract_class_schema(file_path, class_name)
    except Exception:
        return {"fields": [], "methods": [], "fallback": True}
```

## Phase 5: Testing

### 5.1 Unit Tests

**File**: `tests/unit/test_schema_drift_prevention.py`

```python
class TestDependencyGraph:
    def test_direct_dependencies(self):
        issues = [
            Issue(number=1, dependencies=[]),
            Issue(number=2, dependencies=[1]),
        ]
        graph = DependencyGraph(issues)
        assert graph.get_transitive_dependencies(2) == {1}

    def test_transitive_dependencies(self):
        issues = [
            Issue(number=1, dependencies=[]),
            Issue(number=2, dependencies=[1]),
            Issue(number=3, dependencies=[2]),
        ]
        graph = DependencyGraph(issues)
        assert graph.get_transitive_dependencies(3) == {1, 2}

    def test_diamond_dependencies(self):
        issues = [
            Issue(number=1, dependencies=[]),
            Issue(number=2, dependencies=[1]),
            Issue(number=3, dependencies=[1]),
            Issue(number=4, dependencies=[2, 3]),
        ]
        graph = DependencyGraph(issues)
        assert graph.get_transitive_dependencies(4) == {1, 2, 3}


class TestDuplicateDetection:
    def test_exact_duplicate_detected(self):
        ...

    def test_subclass_allowed(self):
        ...

    def test_same_name_different_module_allowed(self):
        ...


class TestIssueSummarizer:
    def test_generates_structured_summary(self):
        ...

    def test_summary_under_token_limit(self):
        ...

    def test_includes_import_statement(self):
        ...
```

### 5.2 Integration Test

**File**: `tests/integration/test_schema_drift_chief_of_staff.py`

```python
async def test_chief_of_staff_no_schema_drift():
    """
    Reproduce the original bug scenario:
    - Issue #1 creates AutopilotSession in models.py
    - Issue #9 should import it, not recreate it
    """
    # Setup: Run Issue #1
    result_1 = await run_issue(issue_1_core_models)
    assert result_1.success

    # Verify summary was added
    issue_1_body = await github.get_issue(1)
    assert "Implementation Summary" in issue_1_body
    assert "AutopilotSession" in issue_1_body

    # Verify context was propagated to Issue #9
    issue_9_body = await github.get_issue(9)
    assert "Context from Issue #1" in issue_9_body

    # Run Issue #9
    result_9 = await run_issue(issue_9_autopilot_runner)

    # Should succeed without creating duplicate
    assert result_9.success
    assert "AutopilotSession" not in result_9.new_classes_defined

    # Verify code imports rather than recreates
    autopilot_code = Path("autopilot.py").read_text()
    assert "from swarm_attack.chief_of_staff.models import AutopilotSession" in autopilot_code
```

## File Summary

| File | Status | Purpose |
|------|--------|---------|
| `swarm_attack/agents/summarizer.py` | New | LLM-powered implementation summarizer |
| `swarm_attack/github/issue_context.py` | New | GitHub issue context propagation |
| `swarm_attack/planning/dependency_graph.py` | New | Transitive dependency computation |
| `swarm_attack/context/context_builder.py` | Modify | Add compact schema with transitive deps |
| `swarm_attack/agents/verifier.py` | Modify | Add subclass detection to duplicate gate |
| `swarm_attack/orchestrator.py` | Modify | Integration point for summarizer |
| `tests/unit/test_schema_drift_prevention.py` | New | Unit tests |
| `tests/integration/test_schema_drift_chief_of_staff.py` | New | Integration test |

## Execution Order

```
Phase 1.1 ──┬──► Phase 1.2 ──► Phase 1.3 (GitHub context propagation)
            │
Phase 2.1 ──┴──► Phase 2.2 (Transitive dependencies)
            │
Phase 3.1 ─────► (Subclass detection)
            │
Phase 4.1 ─────► (Compact schema backup)
            │
Phase 5.1 ──┬──► Phase 5.2 (Testing)
            │
            ▼
        COMPLETE
```

## Success Criteria

1. ✅ Completed issues have auto-generated implementation summaries
2. ✅ Dependent issues receive context from their dependencies (transitively)
3. ✅ Subclassing is allowed, exact duplication is blocked
4. ✅ Chief-of-staff integration test passes
5. ✅ Total token overhead < 1,000 tokens per issue
