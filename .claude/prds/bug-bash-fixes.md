# Bug Bash Fixes PRD

## Expert Review Prompt

<mission>
You are the **Swarm Attack Expert Engineering Review Board** - a team of specialized experts assembled to review bug investigations and proposed fixes. Your job is to:

1. **Validate** each root cause analysis for technical accuracy
2. **Review** each proposed fix for correctness and completeness
3. **Identify** any edge cases, regressions, or gaps in the solutions
4. **Sign off** or **improve** each fix spec before implementation
</mission>

<team_structure>
| Expert | Role | Focus Area |
|--------|------|------------|
| **Systems Architect** | Design Lead | Validates root cause traces, ensures fixes don't introduce architectural debt |
| **Python Engineer** | Implementation | Reviews code changes for correctness, Pythonic patterns, edge cases |
| **QA Engineer** | Testing | Validates test plans, identifies missing test scenarios |
| **DevOps Engineer** | Packaging | Reviews packaging/bundling solutions, pip/setuptools concerns |
| **UX Engineer** | User Impact | Ensures error messages are clear, user flows are intuitive |
</team_structure>

<review_protocol>
For each bug fix spec, the team must:

1. **Read the root cause** - Is the analysis technically accurate? Are there other contributing factors?
2. **Trace the execution path** - Use Read/Grep tools to verify the code paths described
3. **Review the proposed fix** - Is it minimal? Does it introduce new bugs? Are there better approaches?
4. **Validate the test plan** - Are all edge cases covered? What about regression tests?
5. **Provide a verdict**:
   - `APPROVED` - Fix is correct and complete, ready for implementation
   - `APPROVED WITH CHANGES` - Fix is mostly correct but needs specific modifications
   - `NEEDS REWORK` - Significant issues found, provide alternative approach

Output your review in this format for each bug:

```markdown
### Bug #N Review

**Verdict:** APPROVED / APPROVED WITH CHANGES / NEEDS REWORK

**Root Cause Validation:**
[Confirm or correct the root cause analysis]

**Fix Review:**
[Assessment of the proposed solution]

**Recommended Changes (if any):**
[Specific code changes or improvements]

**Additional Test Cases:**
[Any missing test scenarios]

**Sign-off:**
- [ ] Systems Architect
- [ ] Python Engineer
- [ ] QA Engineer
- [ ] DevOps Engineer (if applicable)
- [ ] UX Engineer (if applicable)
```
</review_protocol>

<investigation_instructions>
Before signing off, verify each claim by reading the actual code:

1. **Bug #1**: Read `swarm_attack/agents/coder.py` lines 1871-2009 to confirm no empty-files validation exists
2. **Bug #2**: Read the `codex` property in `spec_critic.py`, `issue_validator.py`, `bug_critic.py` to confirm `skip_auth_classification` is not passed
3. **Bug #3**: Read lines 1879-1919 to confirm validation exists but doesn't cover zero-files case
4. **Bug #4**: Read `pyproject.toml` to confirm skills are not in package-data

Do NOT approve without reading the code. Assumptions lead to incorrect fixes.
</investigation_instructions>

---

## Background

### Context

A PM evaluation on 2025-12-20 tested swarm-attack by building a "Voice COO" app. The test used:

```bash
swarm-attack init voice-coo
swarm-attack run voice-coo  # Spec generation
swarm-attack approve voice-coo
swarm-attack greenlight voice-coo
swarm-attack run voice-coo  # Implementation
```

**Result:** Spec generated successfully, but implementation phase marked tasks "Done" without creating any files.

### Investigation Summary

| Bug | Title | Status | Priority |
|-----|-------|--------|----------|
| #1 | Coder Agent Marks Tasks Done But Writes Zero Files | **NOT FIXED** | CRITICAL |
| #2 | Codex Authentication Detection False Positive | **NOT FIXED** | HIGH |
| #3 | TDD Mode Test File Requirements | **PARTIALLY FIXED** | MEDIUM |
| #4 | Skills Not Bundled With Package | **NOT FIXED** | HIGH |
| #5 | Smart Mode Single Action Exit | **BY DESIGN** | LOW |

---

## Bug #1: Coder Agent Marks Tasks "Done" But Writes Zero Files

### Severity: CRITICAL

### Observed Behavior

```
╭────────────────────────── Implementation Complete ───────────────────────────╮
│ Issue: #1                                                                    │
│ Tests Written: 0                                                             │
│ Tests Passed: 0                                                              │
│ Commits: None                                                                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Then: `ls backend/` → "No such file or directory"

### Root Cause Analysis

**File:** `swarm_attack/agents/coder.py`

**Execution Flow:**
1. LLM returns response without `# FILE:` markers
2. `_parse_file_outputs()` (line 423-503) logs warning but returns empty `{}`
3. Line 1871: `files = self._parse_file_outputs(result.text)` receives empty dict
4. Line 1926: Loop `for file_path, content in files.items():` skips (empty dict)
5. `files_created = []` remains empty
6. Line 1999-2009: `AgentResult.success_result()` returned with empty files
7. Orchestrator marks task DONE

**Evidence:**

```python
# coder.py:495-503
if not files:
    self._log("coder_parse_warning", {
        "warning": "No files parsed from LLM response",
        ...
    }, level="warning")
return files  # Returns empty dict - NO FAILURE RAISED
```

**Gap:** No validation between `_parse_file_outputs()` returning and success being returned. The warning log is not actionable.

### Proposed Fix

#### Changes Required

| File | Location | Change | Reason |
|------|----------|--------|--------|
| `swarm_attack/agents/coder.py` | After line 1877 | Add empty-files validation | Prevent success with zero output |

#### Code Changes

```python
# BEFORE (coder.py, after line 1877, before import validation)
# (no validation - proceeds directly to import validation)

# AFTER - Add this block after line 1877:

# CRITICAL: Reject if no files were generated
# This catches the case where LLM response contains no parseable file markers
if not files:
    self._log("coder_no_files_generated", {
        "error": "LLM response contained no parseable file outputs",
        "response_length": len(result.text),
        "response_preview": result.text[:500] if result.text else "",
    }, level="error")
    return AgentResult.failure_result(
        "Implementation failed: LLM response contained no file outputs. "
        "Expected files marked with '# FILE: path/to/file.ext' format. "
        "The LLM may have provided explanations instead of code.",
        cost_usd=cost,
    )
```

### Testing Plan

1. **Unit Test - Empty Response:**
   ```python
   def test_coder_rejects_empty_file_output():
       """Coder should fail when LLM returns no file markers."""
       mock_response = "I'll help you implement this feature..."  # No # FILE: markers
       result = coder.implement_issue(...)
       assert result.success is False
       assert "no file outputs" in result.output.lower()
   ```

2. **Unit Test - Valid Response:**
   ```python
   def test_coder_accepts_valid_file_output():
       """Coder should succeed when LLM returns proper file markers."""
       mock_response = "# FILE: src/app.py\nprint('hello')"
       result = coder.implement_issue(...)
       assert result.success is True
       assert "src/app.py" in result.output["files_created"]
   ```

3. **Integration Test:**
   - Mock LLM to return response without file markers
   - Verify orchestrator receives failure, not success
   - Verify task is NOT marked as DONE

### Rollout Considerations

- **Backwards Compatible:** Yes - this only adds a failure case where success was incorrect
- **Risk:** Low - failing early is better than false success
- **Monitoring:** Log `coder_no_files_generated` events to track frequency

---

## Bug #2: Codex Authentication Detection False Positive

### Severity: HIGH

### Observed Behavior

```bash
$ codex exec "say ok"
ok  # Codex works fine!

$ swarm-attack run voice-coo
╔══════════════════════════════════════════════════════════════╗
║  CODEX CLI AUTHENTICATION REQUIRED                           ║
╚══════════════════════════════════════════════════════════════╝
```

### Root Cause Analysis

**Config Field Exists But Is Never Used:**

| Component | File | Line | Status |
|-----------|------|------|--------|
| Config field | `swarm_attack/config.py` | 93 | `check_codex_auth: bool = True` |
| Config parsing | `swarm_attack/config.py` | 327 | Parsed from YAML |
| Agent usage | N/A | N/A | **NOT PASSED TO CodexCliRunner** |

**Evidence - All agents instantiate CodexCliRunner WITHOUT the parameter:**

```python
# spec_critic.py:71-75
self._codex = CodexCliRunner(
    config=self.config,
    logger=self.logger,
    checkpoint_callback=lambda: self.checkpoint("pre_codex_call"),
)  # Missing: skip_auth_classification parameter

# Same pattern in:
# - issue_validator.py:76-80
# - bug_critic.py:76-80
```

**Gap:** The `CodexCliRunner` has a `skip_auth_classification` parameter (codex_client.py:95) but agents never pass it. The config value is parsed but never flows through.

### Proposed Fix

#### Changes Required

| File | Location | Change | Reason |
|------|----------|--------|--------|
| `swarm_attack/agents/spec_critic.py` | Lines 71-75 | Pass `skip_auth_classification` | Honor config |
| `swarm_attack/agents/issue_validator.py` | Lines 76-80 | Pass `skip_auth_classification` | Honor config |
| `swarm_attack/agents/bug_critic.py` | Lines 76-80 | Pass `skip_auth_classification` | Honor config |

#### Code Changes

```python
# BEFORE (spec_critic.py:71-75)
self._codex = CodexCliRunner(
    config=self.config,
    logger=self.logger,
    checkpoint_callback=lambda: self.checkpoint("pre_codex_call"),
)

# AFTER
self._codex = CodexCliRunner(
    config=self.config,
    logger=self.logger,
    checkpoint_callback=lambda: self.checkpoint("pre_codex_call"),
    skip_auth_classification=not self.config.preflight.check_codex_auth,
)
```

Apply the same change to `issue_validator.py` and `bug_critic.py`.

### Testing Plan

1. **Unit Test - Config Passthrough:**
   ```python
   def test_skip_auth_classification_passed_from_config():
       """Verify config.preflight.check_codex_auth flows to CodexCliRunner."""
       config = SwarmConfig(preflight=PreflightConfig(check_codex_auth=False))
       agent = SpecCriticAgent(config)
       assert agent.codex.skip_auth_classification is True
   ```

2. **Unit Test - Default Behavior:**
   ```python
   def test_default_auth_classification_enabled():
       """Default config should enable auth classification."""
       config = SwarmConfig()  # Default config
       agent = SpecCriticAgent(config)
       assert agent.codex.skip_auth_classification is False
   ```

3. **Integration Test:**
   - Set `preflight.check_codex_auth: false` in config.yaml
   - Run spec critic against a feature
   - Verify no AUTH_REQUIRED error when codex is functional

### Rollout Considerations

- **Backwards Compatible:** Yes - default behavior unchanged (`check_codex_auth=True`)
- **Risk:** Low - only affects users who explicitly set config
- **Documentation:** Update README to document the config option

---

## Bug #3: TDD Mode Test File Requirements

### Severity: MEDIUM

### Status: PARTIALLY FIXED

### Observed Behavior

```
Error: Coder failed: Test file not found at
tests/generated/voice-coo/test_issue_1.py
```

### Root Cause Analysis

**What Was Fixed:**

The following validation methods were added and ARE called in the main execution path:

| Method | Lines | Purpose |
|--------|-------|---------|
| `_validate_test_imports_satisfied()` | 1084-1172 | Validates test imports are satisfied by implementation |
| `_extract_imports_from_tests_ast()` | 986-1041 | Parses imports using AST |
| `_extract_test_files_from_generated()` | 1174+ | Extracts test files from generated output |

**What Remains Unfixed:**

The validation only catches cases where tests reference undefined names. It does NOT catch the case where LLM generates **zero files** (no tests AND no implementation).

**Execution Flow for Zero Files:**
1. `_parse_file_outputs()` returns empty `{}`
2. `generated_test_files = self._extract_test_files_from_generated(files)` → empty
3. `all_test_content_to_validate` is empty (no disk tests + no generated tests)
4. Validation loop (lines 1897-1906) skips entirely
5. `all_missing` stays empty → no failure raised
6. Code proceeds to success with empty files

**This ties directly to Bug #1.** Fixing Bug #1 (empty-files validation) also addresses this remaining gap.

### Proposed Fix

**No additional fix required** - Bug #1's fix addresses this gap.

The empty-files check added after line 1877 will reject before the import validation even runs, catching the zero-files case.

### Testing Plan

Same as Bug #1 - the zero-files test case covers this scenario.

---

## Bug #4: Skills Not Bundled With Package

### Severity: HIGH

### Observed Behavior

```
Error: Skill not found: feature-spec-author at
/path/to/project/.claude/skills/feature-spec-author/SKILL.md
```

Users must manually run:
```bash
cp -r /path/to/swarm-attack/default-skills .claude/skills
```

### Root Cause Analysis

| Aspect | Status |
|--------|--------|
| `default-skills/` directory | Exists in repo root |
| `pyproject.toml` package-data | Only `*.md, *.yaml` in `swarm_attack/` - missing skills |
| `swarm-attack init` command | Doesn't copy skills |
| `skill_loader.py` line 69+ | Raises `SkillNotFoundError` at runtime |

**Evidence:**

```toml
# pyproject.toml:50-51
[tool.setuptools.package-data]
swarm_attack = ["*.md", "*.yaml", "*.yml"]
# NOTE: default-skills/ is NOT included
```

### Proposed Fix

#### Option A: Auto-Copy on First Run (Recommended)

**Changes Required:**

| File | Change | Reason |
|------|--------|--------|
| `pyproject.toml` | Include `default-skills/**/*` in package-data | Bundle skills with pip package |
| `swarm_attack/skill_loader.py` | Add `ensure_default_skills()` function | Auto-copy if missing |
| `swarm_attack/agents/base.py` | Call `ensure_default_skills()` before raising error | Graceful fallback |

#### Code Changes

**pyproject.toml:**
```toml
[tool.setuptools.package-data]
swarm_attack = ["*.md", "*.yaml", "*.yml", "default-skills/**/*"]
```

**skill_loader.py (new function):**
```python
import shutil
from pathlib import Path

def ensure_default_skills(repo_root: Path) -> bool:
    """
    Copy default skills to project if missing.

    Returns True if skills were copied, False if they already exist.
    """
    target = repo_root / ".claude" / "skills"

    # Check if skills already exist
    if target.exists():
        required_skills = ["coder", "verifier", "feature-spec-author"]
        if all((target / skill / "SKILL.md").exists() for skill in required_skills):
            return False  # Skills already exist

    # Find package's default-skills directory
    package_dir = Path(__file__).parent
    source = package_dir / "default-skills"

    if not source.exists():
        # Try alternative location (development mode)
        source = package_dir.parent / "default-skills"

    if not source.exists():
        return False  # Can't find source skills

    # Copy skills
    target.mkdir(parents=True, exist_ok=True)
    for skill_dir in source.iterdir():
        if skill_dir.is_dir():
            dest = target / skill_dir.name
            if not dest.exists():
                shutil.copytree(skill_dir, dest)

    return True
```

**base.py (modify load_skill method):**
```python
def load_skill(self, skill_name: str) -> str:
    """Load a skill prompt from the skills directory."""
    skill_path = self._get_skill_path(skill_name)

    if not skill_path.exists():
        # Try to auto-copy default skills before failing
        from swarm_attack.skill_loader import ensure_default_skills
        if ensure_default_skills(Path(self.config.repo_root)):
            # Retry after copying
            if skill_path.exists():
                return self._read_skill_file(skill_path)

        raise SkillNotFoundError(f"Skill not found: {skill_name} at {skill_path}")

    return self._read_skill_file(skill_path)
```

### Testing Plan

1. **Unit Test - Auto-Copy:**
   ```python
   def test_skills_auto_copied_when_missing(tmp_path):
       """Skills should be auto-copied on first agent run."""
       # Create empty project directory
       config = SwarmConfig(repo_root=str(tmp_path))
       agent = CoderAgent(config)

       # Skills should now exist
       assert (tmp_path / ".claude" / "skills" / "coder" / "SKILL.md").exists()
   ```

2. **Unit Test - No Overwrite:**
   ```python
   def test_existing_skills_not_overwritten(tmp_path):
       """Existing skills should not be overwritten."""
       skills_dir = tmp_path / ".claude" / "skills" / "coder"
       skills_dir.mkdir(parents=True)
       (skills_dir / "SKILL.md").write_text("custom content")

       config = SwarmConfig(repo_root=str(tmp_path))
       agent = CoderAgent(config)

       # Custom content should be preserved
       assert (skills_dir / "SKILL.md").read_text() == "custom content"
   ```

3. **Integration Test:**
   - Fresh pip install of swarm-attack
   - Run `swarm-attack init test-feature`
   - Run `swarm-attack run test-feature`
   - Verify no SkillNotFoundError
   - Verify `.claude/skills/` was auto-populated

### Rollout Considerations

- **Backwards Compatible:** Yes - existing projects with skills are unaffected
- **Risk:** Medium - file system operations, need to handle permissions
- **Alternative:** Document manual copy more prominently in pip install output

---

## Bug #5: Smart Mode Single Action Exit

### Severity: LOW

### Status: BY DESIGN

### Observed Behavior

```bash
$ swarm-attack smart voice-coo
[Shows one action]
[Exits immediately]
```

### Analysis

The `smart` command is intentionally a **single-shot diagnostic** command, similar to `git status`. It:

1. Checks for interrupted sessions
2. Checks for blocked issues
3. Determines next action via state machine
4. Displays the recommended action
5. Exits

The docstring confirms this: "On startup: 1. Detects interrupted sessions..."

### Proposed Fix

No code changes needed. Documentation should be clarified.

**Documentation Update (README.md):**
```markdown
### Smart Mode

The `smart` command is a diagnostic tool that shows the next recommended action:

```bash
swarm-attack smart my-feature
```

This is a status command (like `git status`), not a continuous loop. Run the suggested
command to proceed, then run `smart` again to see the next action.

For continuous execution, use:
```bash
swarm-attack run my-feature  # Runs until completion or checkpoint
```
```

---

## Implementation Priority

| Priority | Bug | Effort | Impact |
|----------|-----|--------|--------|
| 1 | #1 - Zero-file validation | Small (5 lines) | CRITICAL - root cause of PM failure |
| 2 | #2 - Codex auth passthrough | Small (3 files, 1 line each) | HIGH - unblocks codex users |
| 3 | #4 - Skills auto-setup | Medium (new function + package config) | HIGH - improves onboarding |
| 4 | #5 - Documentation | Small (README update) | LOW - clarity |

**Note:** Bug #3 is automatically fixed by Bug #1's fix.

---

## Acceptance Criteria

- [ ] Bug #1: Coder returns failure when LLM response contains no file markers
- [ ] Bug #2: `config.preflight.check_codex_auth=false` prevents auth false positives
- [ ] Bug #3: (Covered by Bug #1)
- [ ] Bug #4: Fresh pip install + first run auto-populates skills
- [ ] Bug #5: README clarifies smart mode is single-shot diagnostic
- [ ] All existing tests pass
- [ ] New tests cover each fix
- [ ] PM can successfully build Voice COO app end-to-end
