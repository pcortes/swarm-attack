# Swarm Attack Context Problem: Investigation & Fix Plan

**Date:** 2024-12-18
**Status:** Ready for Engineering Review
**Priority:** P0 - Blocking Feature Development

---

## Executive Summary

Swarm Attack agents operate in isolation with **40-50% context loss** between pipeline stages. The coordination layer we built is **architecturally incomplete** - it saves context but never passes it to the coder.

**The Fatal Gap:** Coder reads from static `issues.json` instead of live state, so all the context propagation we built is bypassed.

---

## Problem Statement

### What We Observed
When implementing chief-of-staff-v2, Issue #1 failed because:
1. Coder generated correct code in worktree
2. Tests ran against main codebase (not worktree)
3. Issue #2 wouldn't see what Issue #1 created

### Root Causes Identified

| Problem | Evidence |
|---------|----------|
| **Coder reads static `issues.json`** | `coder.py:1016` - reads from file, not GitHub/state |
| **Completion summaries not passed** | Saved to state but never injected into coder prompt |
| **Project instructions ignored** | `ContextBuilder.get_project_instructions()` exists but never called |
| **Worktree path not propagated** | `SessionState.worktree_path` stored but never used |
| **Issue creator has no tools** | `allowed_tools=[]` despite skill saying "search existing code" |

---

## What Coordination Layer Exists

We built infrastructure that **should** solve this but has gaps:

| Component | Location | Status |
|-----------|----------|--------|
| `StateStore.get_module_registry()` | `state_store.py:562` | **Works** - builds registry from DONE tasks |
| `StateStore.save_completion_summary()` | `state_store.py:626` | **Saved but unused** |
| `SummarizerAgent` | `agents/summarizer.py` | **Works** - generates rich summaries |
| `IssueContextManager.propagate_context()` | `issue_context.py` | **Works** - updates GitHub issues |
| `ContextBuilder.get_completed_summaries()` | `context_builder.py:116` | **Exists but never called** |

### The Flow Gap

**INTENDED:**
```
Issue 1 completes
  → SummarizerAgent generates summary
  → Summary added to GitHub issue #1
  → Context propagated to GitHub issue #2
  → Coder fetches GitHub issue #2  ← ASSUMED
  → Coder sees dependency context
```

**ACTUAL:**
```
Issue 1 completes
  → SummarizerAgent generates summary
  → Summary added to GitHub issue #1  ✓
  → Context propagated to GitHub issue #2  ✓
  → Coder reads static issues.json  ✗ BYPASSES EVERYTHING
  → Coder sees original issue body only
```

---

## The Fix Plan

### Phase 1: Critical Fixes (2-3 hours) - P0

These fixes use existing infrastructure that's built but not wired up.

#### 1.1 Pass Completion Summaries to Coder

**File:** `swarm_attack/orchestrator.py`
**Location:** Before calling coder (~line 1665)

```python
# BEFORE calling coder, get completed summaries for dependencies
from swarm_attack.context_builder import ContextBuilder

context_builder = ContextBuilder(self.config, self._state_store)
completed_summaries = context_builder.get_completed_summaries(feature_id)

# Add to context dict (line 1709)
context = {
    # ... existing context ...
    "completed_summaries": completed_summaries,  # ADD THIS
}
```

**File:** `swarm_attack/agents/coder.py`
**Location:** `_build_prompt()` method (~line 731)

```python
# Inject completed summaries into prompt
completed_summaries = context.get("completed_summaries", [])
if completed_summaries:
    summaries_text = self._format_completed_summaries(completed_summaries)
    # Add to prompt before issue section
```

#### 1.2 Pass Project Instructions to Coder

**File:** `swarm_attack/agents/coder.py`
**Location:** `_build_prompt()` method

```python
# At start of _build_prompt()
context_builder = ContextBuilder(self.config)
project_instructions = context_builder.get_project_instructions()

# Inject at top of prompt
if project_instructions:
    prompt = f"## Project Guidelines\n\n{project_instructions}\n\n---\n\n{prompt}"
```

#### 1.3 Pass Issue Dependencies to Coder

**File:** `swarm_attack/orchestrator.py`
**Location:** Context dict (~line 1709)

```python
# Get dependencies from the issue
issue_data = self._get_issue_data(feature_id, issue_number)
issue_dependencies = issue_data.get("dependencies", [])

context = {
    # ... existing ...
    "issue_dependencies": issue_dependencies,  # ADD THIS
}
```

**File:** `swarm_attack/agents/coder.py`
**Location:** `_build_prompt()`

```python
issue_deps = context.get("issue_dependencies", [])
if issue_deps:
    deps_text = f"**This issue depends on:** #{', #'.join(map(str, issue_deps))}\n"
    deps_text += "Make sure to import from modules created by those issues.\n"
```

#### 1.4 Fix Worktree Path Propagation

**File:** `swarm_attack/orchestrator.py`
**Location:** Context dict (~line 1709)

```python
context = {
    # ... existing ...
    "worktree_path": session.worktree_path if self._session_manager else None,
}
```

**File:** `swarm_attack/agents/coder.py`
**Location:** File writing (~line 1119)

```python
# Determine base path - use worktree if available
worktree_path = context.get("worktree_path")
if worktree_path and Path(worktree_path).exists():
    base_path = Path(worktree_path)
else:
    base_path = Path(self.config.repo_root)

full_path = base_path / file_path
```

---

### Phase 2: Enable Agent Capabilities (2-3 hours) - P1

#### 2.1 Enable Tools for Issue Creator

**File:** `swarm_attack/agents/issue_creator.py`
**Location:** Line 330

```python
# BEFORE (broken):
result = self.llm.run(
    prompt,
    allowed_tools=[],
    max_turns=1,
)

# AFTER (fixed):
result = self.llm.run(
    prompt,
    allowed_tools=["Read", "Glob"],  # Allow codebase exploration
    max_turns=5,  # Allow tool use iterations
)
```

#### 2.2 Add Codebase Context to Spec Author

**File:** `swarm_attack/orchestrator.py`
**Location:** Spec author call (~line 697)

```python
# Build codebase context for spec author
context_builder = ContextBuilder(self.config, self._state_store)
codebase_context = {
    "project_instructions": context_builder.get_project_instructions(),
    "file_structure": self._get_file_structure_summary(),
    "existing_modules": self._get_existing_modules_summary(),
}

author_result = self._author.run({
    "feature_id": feature_id,
    "codebase_context": codebase_context,  # ADD THIS
})
```

#### 2.3 Enhance Module Registry with Source Snippets

**File:** `swarm_attack/state_store.py`
**Location:** `get_module_registry()` method

```python
def get_module_registry(self, feature_id: str) -> dict[str, Any]:
    # ... existing code ...

    for file_path, classes in outputs.classes_defined.items():
        # ADD: Include source snippet
        source_snippet = self._read_source_snippet(feature_id, file_path)

        registry["modules"][file_path] = {
            "created_by_issue": task.issue_number,
            "classes": classes,
            "source_snippet": source_snippet,  # ADD THIS
        }
```

---

### Phase 3: Architectural Fix (4-6 hours) - P2

The fundamental issue is coder reads static `issues.json` instead of live state.

#### Option A: Update issues.json Dynamically (Recommended)

After each issue completes, update `issues.json` with dependency context:

**File:** `swarm_attack/orchestrator.py`
**Location:** After `_generate_and_propagate_context()`

```python
def _update_issues_json_with_context(self, feature_id: str, completed_issue: int):
    """Update issues.json with context from completed issue."""
    issues_path = self.config.specs_dir / feature_id / "issues.json"
    issues_data = json.loads(read_file(issues_path))

    # Get completion summary
    summary = self._state_store.get_completion_summary(feature_id, completed_issue)

    # Add to dependent issues
    for issue in issues_data["issues"]:
        if completed_issue in issue.get("dependencies", []):
            # Append context to issue body
            context_section = f"\n\n---\n## Context from Issue #{completed_issue}\n{summary}"
            issue["body"] += context_section

    safe_write(issues_path, json.dumps(issues_data, indent=2))
```

#### Option B: Fetch from GitHub (Alternative)

Make coder fetch live issue from GitHub instead of static file:

```python
# In coder.py, instead of reading issues.json
issue_body = github_client.get_issue(issue_number).body
```

**Tradeoff:** Requires GitHub API calls, but gets live context.

---

### Phase 4: Structured Context Object (Future)

Create a unified `ExecutionContext` that flows through all stages:

```python
@dataclass
class ExecutionContext:
    feature_id: str
    prd_content: str           # Preserved from start
    spec_content: str
    project_instructions: str
    file_structure: str
    module_registry: dict
    completed_summaries: list  # Rich context from prior issues
    issue_dependencies: list
    worktree_path: Optional[str]
```

This replaces the ad-hoc context dict with a typed object.

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `orchestrator.py` | P1 | Pass context_builder results, worktree_path, dependencies |
| `agents/coder.py` | P1 | Inject project instructions, summaries, handle worktree |
| `agents/issue_creator.py` | P1 | Enable Read/Glob tools |
| `state_store.py` | P1 | Add source snippets to module registry |
| `context_builder.py` | P1 | Add file structure helper |
| `orchestrator.py` | P2 | Update issues.json after completion |

---

## Testing the Fixes

### Test 1: Completion Summary Handoff
```bash
# Complete issue 1, verify summary appears in issue 2's coder prompt
swarm-attack run feature --issue 1
# Check .swarm/sessions/feature/sess_*.json for prompt content
```

### Test 2: Module Registry
```bash
# After issue 1, verify registry shows classes
python -c "
from swarm_attack.state_store import get_store
store = get_store()
print(store.get_module_registry('feature'))
"
```

### Test 3: Worktree Integration
```bash
# Run issue, verify files written to correct location
swarm-attack run feature --issue 1
git status  # Should show changes in main, not orphaned in worktree
```

---

## Success Criteria

After implementing these fixes:

- [ ] Coder prompt includes project instructions from CLAUDE.md
- [ ] Coder prompt shows completion summaries from prior issues
- [ ] Coder prompt shows issue dependencies
- [ ] Module registry includes source snippets (not just class names)
- [ ] Files written to correct location (main or worktree integrated)
- [ ] Issue creator can explore codebase with Read/Glob
- [ ] Spec author receives codebase context

---

## Priority Summary

| Priority | Fixes | Effort | Impact |
|----------|-------|--------|--------|
| **P0** | 1.1-1.4 (completion summaries, instructions, deps, worktree) | 2-3 hrs | Unblocks issue handoff |
| **P1** | 2.1-2.3 (enable tools, codebase context, source snippets) | 2-3 hrs | Better quality specs/issues |
| **P2** | 3.x (dynamic issues.json or GitHub fetch) | 4-6 hrs | Architectural fix |
| **Future** | 4.x (ExecutionContext) | 1-2 days | Clean architecture |

---

## Next Steps

1. **Immediate:** Review this plan with team
2. **This Sprint:** Implement P0 fixes (1.1-1.4)
3. **Next Sprint:** Implement P1 fixes (2.1-2.3)
4. **Backlog:** P2 architectural fix

---

## Appendix: Investigation Evidence

### A. Completion Summary Exists But Unused

```python
# state_store.py:626 - Summary IS saved
task.completion_summary = summary

# context_builder.py:222 - Code EXISTS to format it
completion = summary.get("completion_summary", "")
if completion:
    lines.append(f"**Summary:** {completion}")

# coder.py - NEVER calls get_completed_summaries()
# The summary sits in state, never reaching the prompt
```

### B. Module Registry Works But Is Minimal

```python
# What coder sees:
"- src/auth/user.py (issue #1): User, UserFactory"

# What coder SHOULD see:
"- src/auth/user.py (issue #1): User, UserFactory
   class User:
       def __init__(self, id: str, email: str): ...
       def validate_email(self) -> bool: ...
   Usage: from src.auth.user import User"
```

### C. GitHub Propagation Works But Is Bypassed

```bash
# GitHub issue #2 DOES get context added
# But coder reads issues.json which has original body only
```
