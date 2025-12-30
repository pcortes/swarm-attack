# REFACTOR-001: Extract Pure Functions from Orchestrator

## Overview

**Status**: Ready for Implementation
**Risk Level**: Very Low
**Effort**: ~2-3 hours
**Lines Removed from orchestrator.py**: ~200
**Files Created**: 2 new modules

---

## Implementation Team & Workflow

### Required Subagents

The implementation MUST use the following specialist subagents:

| Subagent | Role | Responsibility |
|----------|------|----------------|
| **Plan** | Architect | Validate extraction boundaries before coding |
| **Explore** | Codebase Navigator | Find all call sites of methods being extracted |
| **general-purpose** | Implementer | Write tests, create modules, update orchestrator |

### Git Worktree Setup (MANDATORY)

**CRITICAL**: All implementation work MUST be done in an isolated worktree to prevent conflicts with other sessions.

```bash
# 1. Create the worktree from main repo
cd /Users/philipjcortes/Desktop/swarm-attack
git worktree add worktrees/refactor-001-pure-functions -b refactor/001-extract-pure-functions

# 2. Navigate to the worktree
cd worktrees/refactor-001-pure-functions

# 3. Verify you're on the correct branch
git branch  # Should show: * refactor/001-extract-pure-functions

# 4. All implementation happens here
# Never switch branches in main swarm-attack directory
```

### TDD Workflow (MANDATORY)

The implementation MUST follow strict TDD (Red-Green-Refactor):

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: RED - Write Failing Tests                            │
│  ─────────────────────────────────────────────────────────────  │
│  1. Create tests/unit/utils/test_text.py                        │
│  2. Create tests/unit/utils/test_imports.py                     │
│  3. Run tests - they MUST FAIL (module doesn't exist)           │
│     pytest tests/unit/utils/ -v  # Expected: ImportError        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: GREEN - Make Tests Pass                               │
│  ─────────────────────────────────────────────────────────────  │
│  1. Create swarm_attack/utils/text.py with functions            │
│  2. Create swarm_attack/utils/imports.py with constant          │
│  3. Run tests - they MUST PASS                                  │
│     pytest tests/unit/utils/ -v  # Expected: All pass           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: REFACTOR - Update Orchestrator                        │
│  ─────────────────────────────────────────────────────────────  │
│  1. Add imports to orchestrator.py                              │
│  2. Delete extracted methods from Orchestrator class            │
│  3. Update all internal calls (self._method -> function)        │
│  4. Run FULL test suite - ALL tests MUST PASS                   │
│     pytest tests/ -v --tb=short                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: COMMIT & MERGE                                        │
│  ─────────────────────────────────────────────────────────────  │
│  1. Commit with conventional commit message                     │
│     git add -A && git commit -m "refactor(orchestrator):        │
│       extract pure functions to utils/text.py and utils/imports │
│     "                                                           │
│  2. Push branch for review                                      │
│  3. After approval, merge to main                               │
│  4. Clean up worktree                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Commands

```bash
# In worktree: worktrees/refactor-001-pure-functions

# Phase 1: Write failing tests
# (Implementer creates test files per spec)
pytest tests/unit/utils/test_text.py -v  # Must fail with ImportError

# Phase 2: Create modules
# (Implementer creates swarm_attack/utils/text.py and imports.py)
pytest tests/unit/utils/ -v  # Must pass

# Phase 3: Update orchestrator
# (Implementer modifies orchestrator.py)
pytest tests/unit/test_error_classification_routing.py -v  # Must still pass
pytest tests/integration/test_debate_rejection_memory.py -v  # Must still pass
pytest tests/ -v --tb=short  # Full suite must pass

# Phase 4: Commit
git add -A
git commit -m "refactor(orchestrator): extract pure functions to utils modules

- Create swarm_attack/utils/text.py with 5 pure text processing functions
- Create swarm_attack/utils/imports.py with KNOWN_EXTERNAL_IMPORTS constant
- Update orchestrator.py to use new modules
- Add comprehensive unit tests for extracted functions
- Reduces orchestrator.py by ~200 lines

BREAKING CHANGE: None (internal refactor only)"

# Merge back to main
cd /Users/philipjcortes/Desktop/swarm-attack
git checkout main
git merge refactor/001-extract-pure-functions
git push origin main

# Cleanup
git worktree remove worktrees/refactor-001-pure-functions
git branch -d refactor/001-extract-pure-functions
```

---

## Problem Statement

`orchestrator.py` is 3,816 lines - too large for an LLM to process in a single context window. The file contains the `Orchestrator` class which violates the Single Responsibility Principle by handling:
- Spec debate pipeline
- Issue session orchestration
- Error recovery
- Import resolution
- Issue splitting
- Context propagation
- Git operations
- And more...

## Proposed Solution

Extract **pure functions** (functions with no side effects or `self` dependencies) to dedicated utility modules. This is the safest possible refactor because:

1. Pure functions have no hidden state dependencies
2. Tests can be trivially updated (just change import path)
3. No mocking required for testing
4. No interface changes for callers

## Functions to Extract

### Target 1: `swarm_attack/utils/text.py`

| Function | Current Location | Lines | Test Coverage |
|----------|-----------------|-------|---------------|
| `generate_semantic_key(issue_text: str) -> str` | Lines 288-338 | ~50 | test_debate_rejection_memory.py |
| `classify_coder_error(error_msg: str) -> str` | Lines 1886-1910 | ~25 | test_error_classification_routing.py |
| `extract_undefined_names(error_msg: str) -> list[str]` | Lines 1912-1943 | ~30 | test_error_classification_routing.py |
| `file_path_to_module(file_path: str) -> Optional[str]` | Lines 2054-2076 | ~25 | indirect |
| `build_import_recovery_hint(undefined_names, suggestions) -> str` | Lines 2078-2108 | ~30 | test_error_classification_routing.py |

**Total: ~160 lines**

### Target 2: `swarm_attack/utils/imports.py`

| Item | Current Location | Lines |
|------|-----------------|-------|
| `KNOWN_EXTERNAL_IMPORTS` dict | Lines 61-94 | ~35 |

**Total: ~35 lines**

## TDD Test Cases

### Phase 1: Write Failing Tests (RED)

Create `tests/unit/utils/test_text.py`:

```python
"""Unit tests for text utility functions extracted from orchestrator."""

import pytest
from swarm_attack.utils.text import (
    generate_semantic_key,
    classify_coder_error,
    extract_undefined_names,
    file_path_to_module,
    build_import_recovery_hint,
)


class TestGenerateSemanticKey:
    """Tests for semantic key generation from issue text."""

    def test_basic_extraction(self):
        """Should extract significant words and sort alphabetically."""
        result = generate_semantic_key("Should implement refresh token rotation")
        assert result == "refresh_rotation_token"

    def test_filters_stopwords(self):
        """Should filter out common stopwords."""
        result = generate_semantic_key("Need to add support for handling errors")
        # "need", "to", "add", "support", "for", "handling" are stopwords
        assert "need" not in result
        assert "support" not in result

    def test_filters_short_words(self):
        """Should filter words with 4 or fewer characters."""
        result = generate_semantic_key("Add new API key for auth")
        # "add", "new", "API", "key", "for" all <= 4 chars
        assert result == "generic_issue" or "auth" in result

    def test_empty_input(self):
        """Should return generic key for empty input."""
        result = generate_semantic_key("")
        assert result == "generic_issue"

    def test_punctuation_removed(self):
        """Should remove punctuation from input."""
        result = generate_semantic_key("Error: Can't parse JSON!!!")
        assert ":" not in result
        assert "!" not in result


class TestClassifyCoderError:
    """Tests for coder error classification."""

    def test_timeout_error(self):
        """Should classify timeout errors."""
        result = classify_coder_error("Process timed out after 60 seconds")
        assert result == "timeout"

    def test_import_error(self):
        """Should classify import errors."""
        result = classify_coder_error("undefined name: SomeClass")
        assert result == "import_error"

        result = classify_coder_error("ImportError: No module named 'foo'")
        assert result == "import_error"

        result = classify_coder_error("ModuleNotFoundError: No module named 'bar'")
        assert result == "import_error"

    def test_syntax_error(self):
        """Should classify syntax errors."""
        result = classify_coder_error("SyntaxError: invalid syntax")
        assert result == "syntax_error"

        result = classify_coder_error("IndentationError: unexpected indent")
        assert result == "syntax_error"

    def test_type_error(self):
        """Should classify type errors."""
        result = classify_coder_error("TypeError: 'NoneType' object is not iterable")
        assert result == "type_error"

    def test_unknown_error(self):
        """Should return 'unknown' for unrecognized errors."""
        result = classify_coder_error("Some random error happened")
        assert result == "unknown"


class TestExtractUndefinedNames:
    """Tests for extracting undefined names from error messages."""

    def test_single_undefined_name(self):
        """Should extract a single undefined name."""
        error = "undefined name(s): typing.py:Optional"
        result = extract_undefined_names(error)
        assert result == ["Optional"]

    def test_multiple_undefined_names(self):
        """Should extract multiple undefined names."""
        error = "undefined name(s): __future__.py:annotations, typer/testing.py:CliRunner"
        result = extract_undefined_names(error)
        assert "annotations" in result
        assert "CliRunner" in result

    def test_no_undefined_names(self):
        """Should return empty list when no undefined names found."""
        error = "Some other error message"
        result = extract_undefined_names(error)
        assert result == []


class TestFilePathToModule:
    """Tests for converting file paths to Python module paths."""

    def test_simple_path(self):
        """Should convert simple file path to module."""
        result = file_path_to_module("./swarm_attack/utils/text.py")
        assert result == "swarm_attack.utils.text"

    def test_path_without_prefix(self):
        """Should handle paths without ./ prefix."""
        result = file_path_to_module("swarm_attack/utils/text.py")
        assert result == "swarm_attack.utils.text"

    def test_init_file(self):
        """Should strip __init__ from module path."""
        result = file_path_to_module("./swarm_attack/utils/__init__.py")
        assert result == "swarm_attack.utils"

    def test_empty_path(self):
        """Should return None for empty path."""
        result = file_path_to_module("")
        assert result is None


class TestBuildImportRecoveryHint:
    """Tests for building recovery hints from import suggestions."""

    def test_with_suggestions(self):
        """Should include suggested imports in hint."""
        undefined = ["Optional", "List"]
        suggestions = {
            "Optional": "from typing import Optional",
            "List": "from typing import List",
        }
        result = build_import_recovery_hint(undefined, suggestions)

        assert "from typing import Optional" in result
        assert "from typing import List" in result

    def test_with_missing_suggestions(self):
        """Should indicate when import not found."""
        undefined = ["UnknownClass"]
        suggestions = {}
        result = build_import_recovery_hint(undefined, suggestions)

        assert "Could not find import for: UnknownClass" in result

    def test_includes_instructions(self):
        """Should include instructions to add imports."""
        result = build_import_recovery_hint(["X"], {"X": "import X"})
        assert "add these imports" in result.lower()
```

Create `tests/unit/utils/test_imports.py`:

```python
"""Unit tests for import utilities extracted from orchestrator."""

import pytest
from swarm_attack.utils.imports import KNOWN_EXTERNAL_IMPORTS


class TestKnownExternalImports:
    """Tests for the KNOWN_EXTERNAL_IMPORTS constant."""

    def test_contains_testing_libraries(self):
        """Should contain common testing library imports."""
        assert "CliRunner" in KNOWN_EXTERNAL_IMPORTS
        assert "TestClient" in KNOWN_EXTERNAL_IMPORTS
        assert "Mock" in KNOWN_EXTERNAL_IMPORTS
        assert "patch" in KNOWN_EXTERNAL_IMPORTS
        assert "pytest" in KNOWN_EXTERNAL_IMPORTS

    def test_contains_standard_library(self):
        """Should contain standard library imports."""
        assert "Path" in KNOWN_EXTERNAL_IMPORTS
        assert "datetime" in KNOWN_EXTERNAL_IMPORTS
        assert "Optional" in KNOWN_EXTERNAL_IMPORTS
        assert "json" in KNOWN_EXTERNAL_IMPORTS

    def test_import_statements_are_valid(self):
        """All import statements should be syntactically valid."""
        for name, import_stmt in KNOWN_EXTERNAL_IMPORTS.items():
            assert import_stmt.startswith("from ") or import_stmt.startswith("import ")
            assert name in import_stmt or import_stmt.endswith(name)
```

### Phase 2: Create Modules (GREEN)

Create `swarm_attack/utils/text.py`:

```python
"""Text processing utilities extracted from orchestrator.

These are pure functions with no side effects, making them easy to test
and reuse across the codebase.
"""

from __future__ import annotations

import re
import string
from typing import Optional


# Stopwords commonly found in spec issues - filtered during semantic key generation
_STOPWORDS = {
    "should", "would", "could", "must", "need", "needs", "implement",
    "implementing", "implementation", "add", "adding", "include",
    "including", "require", "requires", "required", "missing", "ensure",
    "consider", "provide", "provides", "support", "supports", "handle",
    "handling", "define", "defining", "specify", "specifying", "document",
    "documenting", "update", "updating", "create", "creating", "have",
    "having", "make", "making", "there", "that", "this", "with", "from",
    "into", "about", "also", "being", "been", "does", "done", "each",
    "more", "most", "other", "some", "such", "than", "then", "very",
    "what", "when", "where", "which", "while", "will", "your", "their",
}


def generate_semantic_key(issue_text: str) -> str:
    """
    Generate stable semantic key from issue text.

    Algorithm:
    1. Lowercase, remove punctuation
    2. Remove stopwords (should, would, implement, need, add, etc.)
    3. Take first 3 significant words (>4 chars)
    4. Sort and join with underscore

    Example: "Should implement refresh token rotation" -> "refresh_rotation_token"

    Args:
        issue_text: The issue description text.

    Returns:
        Stable semantic key string, or "generic_issue" if no significant words found.
    """
    # Lowercase and remove punctuation
    text = issue_text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))

    # Split into words and filter
    words = text.split()
    significant_words = [
        w for w in words
        if w not in _STOPWORDS and len(w) > 4
    ]

    # Take first 3 significant words and sort for stability
    key_words = sorted(significant_words[:3])

    # Join with underscore
    return "_".join(key_words) if key_words else "generic_issue"


def classify_coder_error(error_msg: str) -> str:
    """
    Classify coder error type for routing to recovery.

    Args:
        error_msg: The error message from coder failure.

    Returns:
        Error type: "timeout", "import_error", "syntax_error", "type_error", or "unknown".
    """
    error_lower = error_msg.lower()

    if "timed out" in error_lower:
        return "timeout"

    if any(x in error_lower for x in ["undefined name", "importerror", "modulenotfounderror"]):
        return "import_error"

    if any(x in error_lower for x in ["syntaxerror", "indentationerror"]):
        return "syntax_error"

    if "typeerror" in error_lower:
        return "type_error"

    return "unknown"


def extract_undefined_names(error_msg: str) -> list[str]:
    """
    Extract undefined names from import error message.

    Parses error messages like:
    "undefined name(s): __future__.py:annotations, typer/testing.py:CliRunner"

    Args:
        error_msg: The error message containing undefined names.

    Returns:
        List of undefined symbol names.
    """
    # Look for "undefined name(s): path:name, path:name" pattern
    match = re.search(r"undefined name\(s\):\s*(.+?)(?:\s*$|\s*\n)", error_msg, re.IGNORECASE)
    if not match:
        return []

    # Parse "path:name, path:name" format
    names = []
    parts = match.group(1).split(",")
    for part in parts:
        part = part.strip()
        if ":" in part:
            # Extract name after the colon
            name = part.split(":")[-1].strip()
            if name:
                names.append(name)

    return names


def file_path_to_module(file_path: str) -> Optional[str]:
    """
    Convert a file path to a Python module path.

    Args:
        file_path: File path like './swarm_attack/cli/chief_of_staff.py'

    Returns:
        Module path like 'swarm_attack.cli.chief_of_staff', or None if empty.
    """
    # Remove ./ prefix and .py suffix
    path = file_path.lstrip("./")
    if path.endswith(".py"):
        path = path[:-3]

    # Convert path separators to dots
    module = path.replace("/", ".").replace("\\", ".")

    # Skip __init__ files
    if module.endswith(".__init__"):
        module = module[:-9]

    return module if module else None


def build_import_recovery_hint(
    undefined_names: list[str],
    suggestions: dict[str, str],
) -> str:
    """
    Build a recovery hint message for the coder.

    Args:
        undefined_names: List of undefined symbol names.
        suggestions: Dict mapping names to suggested imports.

    Returns:
        Human-readable recovery hint string.
    """
    lines = [
        "The previous attempt failed due to import errors.",
        "Please use the following correct imports:",
        "",
    ]

    for name in undefined_names:
        if name in suggestions:
            lines.append(f"  {suggestions[name]}")
        else:
            lines.append(f"  # Could not find import for: {name}")

    lines.append("")
    lines.append("Make sure to add these imports at the top of your files.")

    return "\n".join(lines)
```

Create `swarm_attack/utils/imports.py`:

```python
"""Import utilities extracted from orchestrator.

Contains known external library imports for import error recovery.
"""

# Known external library imports for import error recovery
# Maps symbol name to correct import statement
KNOWN_EXTERNAL_IMPORTS: dict[str, str] = {
    # Testing libraries
    "CliRunner": "from typer.testing import CliRunner",
    "TestClient": "from fastapi.testclient import TestClient",
    "Mock": "from unittest.mock import Mock",
    "patch": "from unittest.mock import patch",
    "MagicMock": "from unittest.mock import MagicMock",
    "AsyncMock": "from unittest.mock import AsyncMock",
    "pytest": "import pytest",
    # Standard library
    "Path": "from pathlib import Path",
    "datetime": "from datetime import datetime",
    "timedelta": "from datetime import timedelta",
    "dataclass": "from dataclasses import dataclass",
    "field": "from dataclasses import field",
    "Optional": "from typing import Optional",
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Any": "from typing import Any",
    "Callable": "from typing import Callable",
    "Union": "from typing import Union",
    # Rich library
    "Console": "from rich.console import Console",
    "Table": "from rich.table import Table",
    "Panel": "from rich.panel import Panel",
    # Typer
    "typer": "import typer",
    "Typer": "import typer",
    # JSON
    "json": "import json",
    # OS
    "os": "import os",
    "subprocess": "import subprocess",
}
```

### Phase 3: Update Orchestrator (REFACTOR)

In `orchestrator.py`, replace the extracted code with imports:

```python
# At top of file, add:
from swarm_attack.utils.text import (
    generate_semantic_key,
    classify_coder_error,
    extract_undefined_names,
    file_path_to_module,
    build_import_recovery_hint,
)
from swarm_attack.utils.imports import KNOWN_EXTERNAL_IMPORTS

# Replace method calls:
# OLD: self._generate_semantic_key(issue_text)
# NEW: generate_semantic_key(issue_text)

# OLD: self._classify_coder_error(error_msg)
# NEW: classify_coder_error(error_msg)

# etc.
```

## Verification Checklist

- [ ] All new tests pass: `pytest tests/unit/utils/test_text.py tests/unit/utils/test_imports.py -v`
- [ ] Existing orchestrator tests still pass: `pytest tests/unit/test_error_classification_routing.py -v`
- [ ] Existing debate tests still pass: `pytest tests/integration/test_debate_rejection_memory.py -v`
- [ ] Full test suite passes: `pytest tests/ -v --tb=short`
- [ ] orchestrator.py is ~200 lines smaller

## Rollback Plan

If issues arise:
1. Revert the changes to orchestrator.py
2. Delete the new modules
3. No external interfaces change, so no downstream impact

## Future Work

This refactor enables future extractions:
1. Extract `ImportRecoveryHandler` class (uses these utilities)
2. Extract `SpecDebateHelper` class (uses `generate_semantic_key`)
3. Extract data classes to `swarm_attack/models/results.py`

## Appendix: Specialist Analysis Summary

### Architecture Analyst
- Identified Recovery/Error Handling as lowest-coupling group
- Confirmed pure functions are completely self-contained

### Complexity Analyst
- Found 6 pure functions suitable for extraction
- Identified duplication between `run_spec_pipeline` and `run_spec_debate_only`

### Dependency Analyst
- Found dead code (`_classify_coder_error` never called, `_handle_import_error_recovery` never called)
- Found bug: methods reference undefined `self.project_dir`
- Confirmed single call sites for most extraction candidates

### TDD Specialist
- Confirmed excellent test coverage for target functions
- Identified test files that can be reused/adapted
- Recommended Tier 1 (pure functions) as safest starting point

---

## Acceptance Criteria

The implementation is COMPLETE when ALL of the following are true:

### Code Changes
- [ ] `swarm_attack/utils/text.py` exists with 5 functions
- [ ] `swarm_attack/utils/imports.py` exists with `KNOWN_EXTERNAL_IMPORTS`
- [ ] `swarm_attack/utils/__init__.py` exports the new modules
- [ ] `orchestrator.py` imports from the new modules
- [ ] Extracted methods are DELETED from `Orchestrator` class
- [ ] All internal calls updated (`self._method()` → `function()`)
- [ ] `orchestrator.py` is ~200 lines smaller

### Test Coverage
- [ ] `tests/unit/utils/test_text.py` exists with all test cases from spec
- [ ] `tests/unit/utils/test_imports.py` exists with all test cases from spec
- [ ] New tests pass: `pytest tests/unit/utils/ -v`
- [ ] Existing tests pass: `pytest tests/unit/test_error_classification_routing.py -v`
- [ ] Full test suite passes: `pytest tests/ -v --tb=short`

### Git Hygiene
- [ ] Work done in worktree `worktrees/refactor-001-pure-functions`
- [ ] Branch named `refactor/001-extract-pure-functions`
- [ ] Commit message follows conventional commits format
- [ ] No changes to main branch until merge

---

## Instructions for Implementing Agent

When an agent picks up this spec for implementation:

### Step 1: Setup (Explore subagent)
```
1. Read this spec completely
2. Create the worktree:
   git worktree add worktrees/refactor-001-pure-functions -b refactor/001-extract-pure-functions
3. Navigate to worktree
4. Use Explore subagent to find ALL call sites of:
   - _generate_semantic_key
   - _classify_coder_error
   - _extract_undefined_names
   - _file_path_to_module
   - _build_import_recovery_hint
   - KNOWN_EXTERNAL_IMPORTS
```

### Step 2: RED Phase (general-purpose subagent)
```
1. Create tests/unit/utils/__init__.py (empty)
2. Create tests/unit/utils/test_text.py with exact test code from spec
3. Create tests/unit/utils/test_imports.py with exact test code from spec
4. Run: pytest tests/unit/utils/ -v
5. VERIFY tests FAIL with ImportError (this is expected!)
```

### Step 3: GREEN Phase (general-purpose subagent)
```
1. Create swarm_attack/utils/text.py with exact code from spec
2. Create swarm_attack/utils/imports.py with exact code from spec
3. Update swarm_attack/utils/__init__.py to export new modules
4. Run: pytest tests/unit/utils/ -v
5. VERIFY all tests PASS
```

### Step 4: REFACTOR Phase (general-purpose subagent)
```
1. In orchestrator.py, add imports at top:
   from swarm_attack.utils.text import (
       generate_semantic_key,
       classify_coder_error,
       extract_undefined_names,
       file_path_to_module,
       build_import_recovery_hint,
   )
   from swarm_attack.utils.imports import KNOWN_EXTERNAL_IMPORTS

2. Delete KNOWN_EXTERNAL_IMPORTS constant from orchestrator.py (lines 61-94)

3. Delete these methods from Orchestrator class:
   - _generate_semantic_key (lines 288-338)
   - _classify_coder_error (lines 1886-1910)
   - _extract_undefined_names (lines 1912-1943)
   - _file_path_to_module (lines 2054-2076)
   - _build_import_recovery_hint (lines 2078-2108)

4. Update all call sites:
   - self._generate_semantic_key(...) → generate_semantic_key(...)
   - etc.

5. Run: pytest tests/ -v --tb=short
6. VERIFY full test suite passes
```

### Step 5: COMMIT Phase
```
1. git add -A
2. git commit with message from spec
3. Report completion
```

---

## Related Specs (Future Work)

After this refactor is complete, the following specs can be created:

1. **REFACTOR-002**: Extract `ImportRecoveryHandler` class
2. **REFACTOR-003**: Extract `SpecDebateHelper` class
3. **REFACTOR-004**: Extract data classes to `models/results.py`
4. **REFACTOR-005**: Eliminate duplication between `run_spec_pipeline` and `run_spec_debate_only`
