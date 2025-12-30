# Swarm Attack Expert Team: Bug Investigation & Fix Spec

## Your Role

You are the **Swarm Attack Expert Engineering Team**. A PM evaluation tested your tool on 2025-12-20 and encountered several issues preventing successful end-to-end builds. Your job is to:

1. **Investigate** each reported bug in the current codebase
2. **Determine** if the bug is FIXED, PARTIALLY FIXED, or NOT FIXED
3. **Root cause** any remaining issues
4. **Write a fix spec** for issues that still need work

**IMPORTANT:** The team has been actively developing, so some of these may already be fixed. Don't assume anything - investigate the actual code.

---

## Reported Bugs from PM Evaluation

### Bug #1: Coder Agent Marks Tasks "Done" But Writes Zero Files

**Severity:** CRITICAL

**Observed Behavior:**
```
╭────────────────────────── Implementation Complete ───────────────────────────╮
│ Issue: #1                                                                    │
│ Tests Written: 0                                                             │
│ Tests Passed: 0                                                              │
│ Commits: None                                                                │
╰──────────────────────────────────────────────────────────────────────────────╯
```
Then: `ls backend/` → "No such file or directory"

**Reported Root Cause (from external analysis):**

Three locations in `swarm_attack/agents/coder.py` may allow success without output:

| Location | Lines | Reported Problem |
|----------|-------|------------------|
| Pre-check return | 1732-1742 | Missing `issue_outputs` field in early return |
| File parsing | 1870-1871 | `_parse_file_outputs()` can return empty `{}` |
| Success validation | 1999-2009 | No check that `files_created` is non-empty |

**Reported Execution Flow:**
1. LLM returns response without `# FILE:` markers
2. `_parse_file_outputs()` logs warning but returns `{}`
3. Loop `for file_path, content in files.items():` skips (empty dict)
4. `files_created = []` remains empty
5. `AgentResult.success_result()` returned with empty files
6. Orchestrator marks task DONE

**Your Investigation Tasks:**
1. Read `swarm_attack/agents/coder.py` around lines 1732-1742, 1870-1877, 1999-2009
2. Trace the execution path when LLM returns no file markers
3. Check if validation was added to prevent empty success
4. Check `_parse_file_outputs()` method for error handling
5. Look at orchestrator behavior when `files_created=[]`

**Answer:**
- [ ] Is this bug FIXED, PARTIALLY FIXED, or NOT FIXED?
- [ ] If not fixed, what is the exact root cause?
- [ ] What validation is needed?

---

### Bug #2: Codex Authentication Detection False Positive

**Severity:** HIGH

**Observed Behavior:**
```bash
$ codex exec "say ok"
ok  # Codex works fine!

$ swarm-attack run voice-coo
╔══════════════════════════════════════════════════════════════╗
║  CODEX CLI AUTHENTICATION REQUIRED                           ║
╚══════════════════════════════════════════════════════════════╝
```

**Reported Root Cause (from external analysis):**

Config option `check_codex_auth: false` exists but is never used:

| Component | File | Line | Status |
|-----------|------|------|--------|
| Config field | `swarm_attack/config.py` | 93 | Defined |
| Config parsing | `swarm_attack/config.py` | 327 | Parsed |
| CodexCliRunner usage | N/A | N/A | NOT PASSED |

`CodexCliRunner` has `skip_auth_classification` parameter but it's hardcoded to `False` in:
- `swarm_attack/agents/spec_critic.py` (lines 71-75)
- `swarm_attack/agents/issue_validator.py`
- `swarm_attack/agents/bug_critic.py`

**Your Investigation Tasks:**
1. Search for all `CodexCliRunner` instantiations in the codebase
2. Check if any pass `skip_auth_classification` parameter
3. Trace how `config.preflight.check_codex_auth` flows through the system
4. Verify if the config value reaches the CodexCliRunner

**Answer:**
- [ ] Is this bug FIXED, PARTIALLY FIXED, or NOT FIXED?
- [ ] If not fixed, list all files that need updating

---

### Bug #3: TDD Mode Test File Requirements

**Severity:** MEDIUM

**Observed Behavior:**
```
Error: Coder failed: Test file not found at
tests/generated/voice-coo/test_issue_1.py
```

**Reported Root Cause (from external analysis):**

The coder operates in TDD mode expecting test files, but:
- Test file is expected before coder runs
- When tests import classes, those classes must be in same LLM response
- `max_turns` limit can cause incomplete implementation

**Reported Partial Fix:**
- `_validate_test_imports_satisfied()` method added (lines 1084-1172)
- `_extract_imports_from_tests_ast()` method added (lines 986-1041)
- Validation now catches incomplete implementations

**Your Investigation Tasks:**
1. Verify the validation methods exist and work
2. Check if validation is called in the main execution path
3. Test what happens when LLM hits max_turns mid-implementation
4. Determine if the error message is clear enough

**Answer:**
- [ ] Is this bug FIXED, PARTIALLY FIXED, or NOT FIXED?
- [ ] What edge cases remain?

---

### Bug #4: Skills Not Bundled With Package

**Severity:** HIGH

**Observed Behavior:**
```
Error: Skill not found: feature-spec-author at
/path/to/project/.claude/skills/feature-spec-author/SKILL.md
```

Users must manually run:
```bash
cp -r /path/to/swarm-attack/default-skills .claude/skills
```

**Reported Root Cause (from external analysis):**

| Aspect | Status |
|--------|--------|
| `default-skills/` directory | Exists in repo root |
| `pyproject.toml` package-data | Only `*.md, *.yaml` - missing skills |
| `swarm-attack init` command | Doesn't copy skills |
| `skill_loader.py` line 69 | Raises `SkillNotFoundError` at runtime |

**Your Investigation Tasks:**
1. Check if skills are now included in package-data
2. Check if `init` command now copies skills
3. Look for any auto-setup mechanism
4. Check if there's validation on first run

**Answer:**
- [ ] Is this bug FIXED, PARTIALLY FIXED, or NOT FIXED?
- [ ] What is the intended setup flow?

---

### Bug #5: Smart Mode Single Action Exit

**Severity:** LOW (may be by design)

**Observed Behavior:**
```bash
$ swarm-attack smart voice-coo
[Shows one action]
[Exits immediately]
```

**Reported Analysis:**
- No `while True` loop in smart command
- Docstring says "On startup" suggesting one-time
- May be intentional Unix-style design

**Your Investigation Tasks:**
1. Confirm this is intentional design
2. If not, determine if looping should be added
3. Document the intended usage pattern

**Answer:**
- [ ] Is this BY DESIGN or a BUG?
- [ ] Should documentation be updated?

---

## Fix Spec Template

For each bug that is NOT FIXED or PARTIALLY FIXED, write a fix spec:

```markdown
## Fix Spec: [Bug Title]

### Problem Statement
[One paragraph describing the issue]

### Root Cause
[Technical explanation with file:line references]

### Proposed Solution

#### Changes Required
| File | Change | Reason |
|------|--------|--------|
| path/to/file.py | Add validation at line X | Prevent empty success |

#### Code Changes
```python
# Before (file.py:123)
[existing code]

# After
[fixed code]
```

### Testing Plan
1. [How to verify the fix works]
2. [Edge cases to test]

### Rollout Considerations
[Any backwards compatibility concerns]
```

---

## Investigation Instructions

1. **Use Read tool** to examine each file mentioned
2. **Use Grep tool** to search for patterns across codebase
3. **Trace execution paths** from CLI command to agent execution
4. **Check recent commits** with `git log --oneline -20` for related fixes
5. **Don't assume** - verify everything in the actual code

## Output Format

For each bug, provide:

```
### Bug #N: [Title]

**Status:** FIXED / PARTIALLY FIXED / NOT FIXED

**Evidence:**
[Specific code snippets or file:line references proving status]

**Root Cause (if not fixed):**
[Technical explanation]

**Fix Spec (if needed):**
[Use template above]
```

---

## Context: What Was Being Built

The PM was testing swarm-attack by building a "Voice COO" app:
- FastAPI backend with voice command processing
- Vanilla HTML/JS frontend with Web Speech API
- Mock workflow execution

The test used:
```bash
swarm-attack init voice-coo
swarm-attack run voice-coo  # Spec generation
swarm-attack approve voice-coo
swarm-attack greenlight voice-coo
swarm-attack run voice-coo  # Implementation
```

**Result:** Spec generated successfully, but implementation phase marked tasks "Done" without creating any files.

---

## Begin Investigation

Start by reading the coder agent to investigate Bug #1 (the most critical):

```
Read: swarm_attack/agents/coder.py
Focus: Lines 1700-2050 (implementation completion logic)
```

Then proceed through each bug systematically.

