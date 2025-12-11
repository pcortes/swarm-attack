# Swarm-Attack Fix Plan

## Executive Summary

The swarm-attack CLI has a significant **wiring gap**: the backend implementation for the issue creation and implementation phases is ~90% complete, but the CLI commands to access this functionality are missing. The agents, orchestrator logic, and state machine are all implemented, but users cannot access them because:

1. The `issues` command doesn't exist (documented in HOW_TO_USE.md line 218)
2. The `greenlight` command doesn't exist (documented in HOW_TO_USE.md line 243)
3. The `run` command only handles spec pipeline, not implementation
4. The `next` command shows "(not yet implemented)" for valid backend functionality

**Total Scope:** 1 bug with 4 sub-issues, all related to incomplete CLI wiring.

---

## Bug Analysis

### Bug 1: CLI Commands Missing - Backend Implemented but Not Wired Up

**Severity:** High (Blocks progression from spec approval to implementation)

**Root Cause:**
The development appears to have followed a pattern of implementing the backend first (agents, orchestrator, state machine) and then wiring up the CLI. However, the CLI wiring was only completed for the spec pipeline phase. The issue/implementation pipeline CLI commands were never added, despite the backend being fully functional.

**Evidence:**

| Component | File | Status | Line Reference |
|-----------|------|--------|----------------|
| IssueCreatorAgent | `/swarm_attack/agents/issue_creator.py` | ✅ Fully implemented | Lines 1-276 |
| IssueValidatorAgent | `/swarm_attack/agents/issue_validator.py` | ✅ Fully implemented | Lines 1-505 |
| CoderAgent | `/swarm_attack/agents/coder.py` | ✅ Implemented | Exported in `__init__.py:19` |
| TestWriterAgent | `/swarm_attack/agents/test_writer.py` | ✅ Implemented | Exported in `__init__.py:27` |
| VerifierAgent | `/swarm_attack/agents/verifier.py` | ✅ Implemented | Exported in `__init__.py:28` |
| `run_issue_session()` | `/swarm_attack/orchestrator.py` | ✅ Fully implemented | Lines 564-877 |
| StateMachine issue handling | `/swarm_attack/state_machine.py` | ✅ Fully implemented | Lines 397-535 |
| `issues` CLI command | `/swarm_attack/cli.py` | ❌ Missing | N/A - does not exist |
| `greenlight` CLI command | `/swarm_attack/cli.py` | ❌ Missing | N/A - does not exist |
| Implementation wiring in `run` | `/swarm_attack/cli.py` | ❌ Missing | Only handles spec at lines 444-547 |
| Next command suggestions | `/swarm_attack/cli.py` | ❌ Hardcoded "(not yet implemented)" | Lines 722-726 |

**Detailed Gap Analysis:**

#### 1.1 Missing `issues` Command

**What exists:**
- `IssueCreatorAgent.run()` in `/swarm_attack/agents/issue_creator.py:155-275` - Fully functional
- `IssueValidatorAgent.run()` in `/swarm_attack/agents/issue_validator.py:318-504` - Fully functional
- Orchestrator method would need to be added to coordinate both agents

**What's missing:**
- No `@app.command() def issues(...)` in `/swarm_attack/cli.py`
- Documentation in `HOW_TO_USE.md:217-229` says command should exist

**Fix Required:**
- [ ] Add `@app.command() def issues(feature_id: str)` to cli.py
- [ ] Wire to IssueCreatorAgent and IssueValidatorAgent
- [ ] Update feature phase from SPEC_APPROVED → ISSUES_CREATING → ISSUES_VALIDATING → ISSUES_NEED_REVIEW
- [ ] Add cost tracking for issue creation phase

**Complexity:** Medium

---

#### 1.2 Missing `greenlight` Command

**What exists:**
- Phase `READY_TO_IMPLEMENT` defined in `/swarm_attack/models.py:39`
- Phase `ISSUES_NEED_REVIEW` defined in `/swarm_attack/models.py:38`
- State machine handler `_handle_issues_need_review()` in `/swarm_attack/state_machine.py:421-427`

**What's missing:**
- No `@app.command() def greenlight(...)` in `/swarm_attack/cli.py`
- Documentation in `HOW_TO_USE.md:241-243` says command should exist

**Fix Required:**
- [ ] Add `@app.command() def greenlight(feature_id: str)` to cli.py
- [ ] Update phase from ISSUES_NEED_REVIEW → READY_TO_IMPLEMENT
- [ ] Optionally validate that issues.json exists and passed validation

**Complexity:** Small

---

#### 1.3 `run` Command Doesn't Handle Implementation Phase

**What exists:**
- `run` command in `/swarm_attack/cli.py:444-547` - Only calls `run_spec_pipeline()`
- `orchestrator.run_issue_session()` in `/swarm_attack/orchestrator.py:564-877` - Fully functional
- Issue selection via PrioritizationAgent in `/swarm_attack/agents/prioritization.py`

**What's missing:**
- `run` command doesn't detect current phase and route to implementation
- No option to pass `--issue <number>` for specific issue implementation

**Fix Required:**
- [ ] Modify `run` command to detect feature phase
- [ ] If phase is READY_TO_IMPLEMENT or IMPLEMENTING, call `run_issue_session()`
- [ ] Add `--issue` optional parameter to run specific issue
- [ ] Display implementation results similar to spec pipeline results

**Complexity:** Medium

---

#### 1.4 `next` Command Shows Hardcoded "(not yet implemented)" Messages

**What exists:**
- Working state machine in `/swarm_attack/state_machine.py`
- ActionType enum with all actions defined in `/swarm_attack/state_machine.py:75-99`

**What's missing:**
- Actual command suggestions in `/swarm_attack/cli.py:722-726` are hardcoded to say:
  ```python
  ActionType.RUN_ISSUE_PIPELINE: "(Issue pipeline not yet implemented)",
  ActionType.SELECT_ISSUE: "(Implementation agents not yet implemented)",
  ActionType.RESUME_SESSION: "(Implementation agents not yet implemented)",
  ActionType.RUN_IMPLEMENTATION: "(Implementation agents not yet implemented)",
  ```

**Fix Required:**
- [ ] Update command_suggestions dict at `/swarm_attack/cli.py:718-729`:
  - `RUN_ISSUE_PIPELINE` → `swarm-attack issues {feature_id}`
  - `SELECT_ISSUE` → `swarm-attack run {feature_id}` or `swarm-attack run {feature_id} --issue {n}`
  - `RESUME_SESSION` → `swarm-attack run {feature_id}` (auto-resumes)
  - `RUN_IMPLEMENTATION` → `swarm-attack run {feature_id}`

**Complexity:** Small

---

## Implementation Order

1. **Add `greenlight` command** (Small, no dependencies)
   - This is the simplest fix - just a phase transition
   - Unblocks the other commands from progressing

2. **Add `issues` command** (Medium, depends on nothing)
   - Wire IssueCreatorAgent and IssueValidatorAgent
   - Enables creation of issues from specs
   - Can be tested independently

3. **Enhance `run` command** (Medium, depends on greenlight + issues)
   - Add phase detection logic
   - Add --issue parameter
   - Wire to run_issue_session()
   - Can only be fully tested after issues/greenlight work

4. **Update `next` command suggestions** (Small, depends on all above)
   - Should be done last once commands actually exist
   - Simple string replacement

---

## Files to Modify

| File | Changes |
|------|---------|
| `/swarm_attack/cli.py` | Add `issues()` command (new function), Add `greenlight()` command (new function), Modify `run()` to detect phase and call issue session, Update command_suggestions dict at line 718-729 |
| `/swarm_attack/orchestrator.py` | Possibly add `run_issue_pipeline()` method to coordinate IssueCreatorAgent + IssueValidatorAgent (or call agents directly from CLI) |

---

## Additional Notes

### Testing Strategy
After implementing fixes, test the complete workflow:
```bash
# 1. Create feature with PRD
swarm-attack init test-feature

# 2. Run spec pipeline
swarm-attack run test-feature

# 3. Approve spec
swarm-attack approve test-feature

# 4. Create issues (NEW)
swarm-attack issues test-feature

# 5. Greenlight issues (NEW)
swarm-attack greenlight test-feature

# 6. Run implementation (ENHANCED)
swarm-attack run test-feature

# 7. Check status
swarm-attack status test-feature
```

### Backward Compatibility
All changes are additive - no existing functionality will break:
- `run` command will continue to work for spec pipeline when phase is PRD_READY/SPEC_IN_PROGRESS
- Existing state files remain compatible

### Documentation Alignment
The `HOW_TO_USE.md` documentation already describes the correct behavior. Once CLI is wired, documentation will be accurate. No documentation changes needed.
