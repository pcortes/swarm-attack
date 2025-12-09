# Feature Swarm Bug Bashing Log

> **Purpose**: Track debugging iterations, root causes, and fixes so future teams don't reinvent the wheel.

## Quick Status

| Issue | Status | Root Cause | Fix Applied |
|-------|--------|------------|-------------|
| Missing `feature-spec-moderator` skill | ✅ FIXED | Fixture drift - skill not in all fixtures | Added to conftest.py setup_skills |
| Empty spec content | ✅ FIXED | Agent overwrites Claude's Write tool output | Check file before using result.text |
| Skill prompts missing Write instruction | ✅ FIXED | Test fixtures lacked explicit tool instructions | Added "Use the Write tool" to all skills |
| SpecModeratorAgent extraction failure | ✅ FIXED | Same as empty spec - didn't check if Claude wrote file | Added file-first check before parsing result.text |
| LLM client tests failing (`-p` flag) | ✅ FIXED | Tests expect `-p` flag, impl uses `--` separator | Updated tests to use `--` separator pattern |

---

## Iteration Log

### 2025-11-27 Session 1: Initial Investigation

**Starting State:**
- 3 test issues reported: 2 SKIPPED, 1 FAILED
- Tests created: `test_fixture_consistency.py`, `test_spec_author_edge_cases.py`

**Investigation:**
```
tests/unit/test_fixture_consistency.py - 9 tests
tests/unit/test_spec_author_edge_cases.py - 9 tests
```

**Root Causes Identified:**

1. **Fixture Drift**: Multiple test files maintain their own skill fixtures independently:
   - `conftest.py::setup_skills`
   - `test_e2e_critical.py::_setup_e2e_skills`
   - `test_pipeline_integration.py::_setup_test_skills`

   When `feature-spec-moderator` was added to the system, it was added to some fixtures but not all.

2. **Mock-Reality Divergence**: The original agent code assumed `result.text` always contains the spec:
   ```python
   # BEFORE (broken)
   spec_content = result.text  # Gets "I've written the spec..." if Claude used Write tool
   safe_write(spec_path, spec_content)  # Overwrites Claude's file!
   ```

3. **Prompt Engineering Gap**: Test fixture skill prompts didn't include explicit Write tool instructions:
   ```
   # Before: "Generate a spec with Overview, Architecture..."
   # After: "Use the Write tool to save the spec file. Do not just return content."
   ```

---

### 2025-11-27 Session 2: Fixes Applied

**Fix 1: feature-spec-moderator skill in conftest.py**
- File: `tests/integration/conftest.py`
- Change: Added explicit Write tool instruction
- Lines changed: 650-653
```python
# Added:
5. **Use the Write tool** to save the updated spec to spec-draft.md (overwrite)
6. **Use the Write tool** to save the new rubric assessment to spec-rubric.json

IMPORTANT: You MUST use the Write tool to save both files.
```

**Fix 2: Created test-writer skill in source**
- File: `.claude/skills/test-writer/SKILL.md`
- Created new skill file with explicit Write tool instructions

**Fix 3: test-writer and coder skills in conftest.py**
- File: `tests/integration/conftest.py`
- Added explicit Write tool instructions to both skills

**Fix 4: SpecModeratorAgent extraction logic**
- File: `swarm_attack/agents/spec_moderator.py`
- Lines 290-370: Rewrote to check file-first before parsing result.text
- Key logic:
```python
# Check if Claude already wrote the spec file via Write tool
if file_exists(spec_path):
    file_content = read_file(spec_path)
    if file_content != original_spec and len(file_content) > 50:
        # Claude updated the file, use it
        updated_spec = file_content

# Only fall back to result.text if file wasn't updated
if not updated_spec:
    updated_spec, rubric = self._parse_response(result.text)
```

**Fix 5: Updated test assertions in test_spec_agents.py**
- Tests now use spec content > 50 chars to pass validation
- File: `tests/unit/test_spec_agents.py`
- Multiple test methods updated

---

### 2025-11-27 Session 3: LLM Client Tests Fix

**Problem:**
- 5 tests failing in `tests/unit/test_llm_clients.py`
- Tests expected `-p` flag for prompts
- Implementation uses `--` separator instead (to prevent prompts starting with `---` from being interpreted as CLI options)

**Root Cause:**
The implementation was updated to use `--` separator (line 90 in `llm_clients.py`) for safety reasons, but tests were never updated to match.

**Fix Applied:**
- File: `tests/unit/test_llm_clients.py`
- Changes:
  1. Updated `test_builds_basic_command` to check for `--` instead of `-p`
  2. Added helper function `_get_prompt_from_cmd()` to extract prompt after `--` separator
  3. Updated all 4 `TestRunWithContext` tests to use the helper function

**Tests After Fix:**
```
tests/unit/test_llm_clients.py - 33 passed ✅
tests/unit/ (all tests) - 1032 passed ✅
```

---

## Test Results After Fixes

```
tests/unit/test_fixture_consistency.py - 9 passed ✅
tests/unit/test_spec_author_edge_cases.py - 9 passed ✅
tests/unit/test_spec_agents.py - 27 passed ✅
tests/unit/test_llm_clients.py - 33 passed ✅
tests/unit/ (all tests) - 1032 passed ✅
```

---

## Files Modified

| File | Type | Changes |
|------|------|---------|
| `tests/integration/conftest.py` | Test | Added Write instructions to feature-spec-moderator, test-writer, coder skills |
| `.claude/skills/test-writer/SKILL.md` | Source | Created new skill file |
| `swarm_attack/agents/spec_moderator.py` | Source | Fixed extraction logic to check file-first |
| `tests/unit/test_spec_agents.py` | Test | Updated mock content to be > 50 chars |
| `tests/unit/test_llm_clients.py` | Test | Updated to use `--` separator instead of `-p` flag |

---

## Lessons Learned

1. **Fixture Centralization**: All skills should be defined in ONE place and imported/copied to tests. Never maintain parallel lists.

2. **File-First Pattern**: When allowing LLMs to use Write tool, always check if they wrote a file before using result.text.

3. **Explicit Tool Instructions**: LLMs may not use tools unless explicitly instructed. Always include "Use the Write tool to..." in prompts.

4. **Mock-Reality Parity**: Mocks should simulate what the LLM actually returns, not what we wish it returned. When Claude uses Write tool, result.text is conversational.

5. **Minimum Content Validation**: The 50-char threshold catches empty/conversational responses. Consider pattern-based detection for better accuracy.

---

### 2025-11-27 Session 4: Verification Run

**Time**: 2025-11-27 (verification session)

**Action**: Ran full unit test suite to verify all fixes are holding.

**Results**:
```
python -m pytest tests/unit/ -v --tb=short
====================== 1032 passed, 21 warnings in 2.14s =======================
```

**All tests passing** ✅

**Warnings Note**: 21 PytestCollectionWarnings about `TestRunnerConfig` and `TestWriterAgent` classes. These are false positives - pytest sees classes starting with "Test" but they're config dataclasses and agent classes, not test classes. Not a bug, just a naming convention issue.

---

## Known Issues Still Open

1. ~~**LLM Client Tests**: `test_llm_clients.py` has 5 failing tests expecting `-p` flag~~ ✅ FIXED
2. **Integration Tests with Real Claude**: Not yet run to verify fixes work end-to-end
3. **PytestCollectionWarnings**: `TestRunnerConfig` and `TestWriterAgent` trigger false positive warnings (cosmetic, not blocking)

---

## How to Continue Debugging

1. Read this file first to understand context
2. Check the test files mentioned above for current state
3. Run tests incrementally:
   ```bash
   python -m pytest tests/unit/test_fixture_consistency.py -v
   python -m pytest tests/unit/test_spec_author_edge_cases.py -v
   python -m pytest tests/unit/test_spec_agents.py -v
   ```
4. Update this log with timestamps when making changes
5. Document root causes, not just fixes
