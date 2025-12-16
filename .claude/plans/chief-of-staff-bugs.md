# Chief of Staff Bug Report

Generated: 2025-12-16

## Summary

Investigation of the chief-of-staff feature revealed 4 bugs blocking progress:

1. IssueCreatorAgent YAML frontmatter not stripped (Critical)
2. Pytest module name collision in generated tests (High)
3. False regression detection due to test collection errors (High)
4. coder skill has YAML frontmatter but fix only partial (Low)

---

## Bug Report: IssueCreatorAgent YAML Frontmatter Not Stripped

**Severity:** Critical
**Component:** IssueCreatorAgent
**File(s):** `swarm_attack/agents/issue_creator.py:57-61`

### Symptoms
- `python -m swarm_attack issues chief-of-staff` fails with `error_max_turns`
- Error message: "Claude invocation failed: Claude CLI returned error: error_max_turns"

### Root Cause
The issue-creator skill file `.claude/skills/issue-creator/SKILL.md` has YAML frontmatter:

```yaml
---
name: issue-creator
description: >
  Generate GitHub issues from an approved engineering specification.
allowed-tools: Read,Glob
---
```

However, `IssueCreatorAgent.run()` calls `self.llm.run()` with `allowed_tools=[]` (line 260-264):

```python
result = self.llm.run(
    prompt,
    allowed_tools=[],  # <-- Explicitly disables all tools
    max_turns=1,
)
```

Claude sees `allowed-tools: Read,Glob` in the prompt, attempts to use these tools, but the CLI has `--allowedTools ""` set. This causes tool calls to fail and burns through `max_turns=1` immediately.

The same bug was already fixed in `CoderAgent` (lines 172-192) by stripping YAML frontmatter, but the fix was not applied to `IssueCreatorAgent`.

### Proposed Fix
Add the same frontmatter stripping logic to `IssueCreatorAgent._load_skill_prompt()`:

```python
def _load_skill_prompt(self) -> str:
    """Load and cache the skill prompt, stripping YAML frontmatter."""
    if self._skill_prompt is None:
        content = self.load_skill("issue-creator")
        # Strip YAML frontmatter if present (---...---)
        if content.startswith("---"):
            end_idx = content.find("---", 3)
            if end_idx != -1:
                content = content[end_idx + 3:].lstrip()
        self._skill_prompt = content
    return self._skill_prompt
```

Alternatively, create a shared utility method in `BaseAgent` that all agents can use.

### Test Plan
1. Run `python -m swarm_attack issues chief-of-staff` - should succeed without error_max_turns
2. Verify issues.json is created in `specs/chief-of-staff/`
3. Run integration test for issue creation

---

## Bug Report: Pytest Module Name Collision

**Severity:** High
**Component:** TestWriter / Test Infrastructure
**File(s):** `tests/generated/*/test_issue_*.py`

### Symptoms
- `pytest tests/` fails with collection error:
  ```
  imported module 'test_issue_2' has this __file__ attribute:
    /Users/.../tests/generated/chief-of-staff/test_issue_2.py
  which is not the same as the test file we want to collect:
    /Users/.../tests/generated/external-dashboard/test_issue_2.py
  ```
- Only 2 warnings, 1 error in 0.24s (test collection fails before running)

### Root Cause
Multiple features generate test files with identical names (e.g., `test_issue_2.py`):
- `tests/generated/chief-of-staff/test_issue_2.py`
- `tests/generated/external-dashboard/test_issue_2.py`

Python's import system caches module names. When pytest tries to import both files, it finds a collision because both have the same module name `test_issue_2`.

The `__pycache__` directories cache the first import, causing subsequent imports from different directories to fail.

### Proposed Fix
Option A: Use feature-prefixed test file names:
```
tests/generated/chief-of-staff/test_chief_of_staff_issue_2.py
tests/generated/external-dashboard/test_external_dashboard_issue_2.py
```

Option B: Add conftest.py with unique package path configuration.

Option C: Add `__init__.py` to each generated directory to make them proper packages.

Recommended: Option A - prefix test files with feature name to ensure unique module names.

### Test Plan
1. Clear pycache: `find tests/generated -name "__pycache__" -type d -exec rm -rf {} +`
2. Rename test files with feature prefix
3. Run `pytest tests/ -v` - should collect and run all tests without collision

---

## Bug Report: False Regression Detection

**Severity:** High
**Component:** Verifier / Test Runner
**File(s):** `swarm_attack/agents/verifier.py` (regression detection logic)

### Symptoms
- Issue #5 (GoalTracker) is blocked with:
  ```
  "blocked_reason": "Max retries exceeded: Regression detected: 3 tests failed in full suite"
  ```
- But when running `pytest tests/ --ignore=tests/generated/external-dashboard` manually, all 236 tests pass

### Root Cause
The test collection error (Bug #2: Pytest Module Name Collision) causes pytest to abort with an error exit code before running any tests. The verifier interprets this collection error as "test failures" and triggers regression detection.

The verifier likely:
1. Runs `pytest tests/`
2. Gets exit code != 0 (due to collection error)
3. Parses output for failures but misinterprets the collection error count
4. Reports "3 tests failed in full suite" (possibly counting the 2 warnings + 1 error)

### Proposed Fix
1. First fix Bug #2 (module name collision) to prevent collection errors
2. Improve verifier to distinguish between:
   - Test collection errors (import issues, syntax errors)
   - Actual test failures
   - Test passes
3. Don't count collection errors as test failures for regression detection

### Test Plan
1. Fix module name collision (Bug #2)
2. Unblock issue #5: `python -m swarm_attack unblock chief-of-staff`
3. Re-run issue #5: `python -m swarm_attack run chief-of-staff --issue 5`
4. Verify it passes without false regression detection

---

## Bug Report: Inconsistent Frontmatter Handling Across Agents

**Severity:** Low (fix exists but not consistently applied)
**Component:** BaseAgent, Multiple Agent Implementations
**File(s):**
- `swarm_attack/agents/base.py` (load_skill method)
- `swarm_attack/agents/coder.py` (has fix)
- `swarm_attack/agents/issue_creator.py` (missing fix)
- Potentially other agents using skills

### Symptoms
- CoderAgent works (has frontmatter stripping)
- IssueCreatorAgent fails (missing frontmatter stripping)
- Other agents may fail depending on skill file format

### Root Cause
The frontmatter stripping fix was applied only to `CoderAgent._load_skill_prompt()` but not:
1. `IssueCreatorAgent._load_skill_prompt()`
2. Other agents that load skills
3. `BaseAgent.load_skill()` itself (would fix all agents)

Skills with YAML frontmatter containing `allowed-tools`:
- `.claude/skills/issue-creator/SKILL.md`: `allowed-tools: Read,Glob`
- `.claude/skills/coder/SKILL.md`: `allowed-tools: Read,Glob,Bash,Write,Edit`

### Proposed Fix
Move the frontmatter stripping logic to `BaseAgent.load_skill()` so all agents benefit:

```python
# In swarm_attack/agents/base.py
def load_skill(self, skill_name: str) -> str:
    """Load skill prompt and strip YAML frontmatter."""
    skill_path = self.config.skills_path / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise SkillNotFoundError(f"Skill not found: {skill_name}")

    content = skill_path.read_text()

    # Strip YAML frontmatter if present (---...---)
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            content = content[end_idx + 3:].lstrip()

    return content
```

This ensures all agents get clean skill prompts without frontmatter.

### Test Plan
1. Move frontmatter stripping to `BaseAgent.load_skill()`
2. Remove duplicate stripping from `CoderAgent._load_skill_prompt()`
3. Test `python -m swarm_attack issues chief-of-staff` - should work
4. Test `python -m swarm_attack run chief-of-staff` - should work
5. Verify both agents load skills correctly without error_max_turns

---

## Next Steps

1. **Immediate**: Unblock issue #5 by clearing the false regression state
   ```bash
   python -m swarm_attack unblock chief-of-staff
   ```

2. **Fix Bug #4 first** (BaseAgent.load_skill frontmatter stripping) - fixes Bug #1 automatically

3. **Fix Bug #2** (module name collision) - prevents Bug #3

4. **Re-run chief-of-staff implementation**:
   ```bash
   python -m swarm_attack run chief-of-staff
   ```

---

## Related Files

- `swarm_attack/agents/base.py:load_skill()` - Core skill loading
- `swarm_attack/agents/coder.py:172-192` - Has frontmatter fix
- `swarm_attack/agents/issue_creator.py:57-61` - Missing frontmatter fix
- `swarm_attack/agents/verifier.py` - Regression detection logic
- `.claude/skills/*/SKILL.md` - Skill prompt files with frontmatter
- `tests/generated/*/test_issue_*.py` - Generated test files with collisions
