# Coordination Layer v2: Complete Specification

## Executive Summary

This spec addresses critical failures in the swarm coordination system and adds intelligent orchestration capabilities. The current system repeatedly re-implements completed issues, ignores project context (CLAUDE.md), and provides no visibility into swarm state via GitHub.

---

## Part 1: Critical Bug Fixes (P0)

### 1.1 State Synchronization Failure

**Bug:** `greenlight` command resets completed issues to READY

**Root Cause:** `sync_state_from_git()` is only called in `run_issue_session`, not in `greenlight`

**Evidence:**
```
State file: Issue #1 = READY
Git log: "feat(chief-of-staff): Implement issue #1" EXISTS
Result: Issue #1 gets re-implemented
```

**Fix Location:** `swarm_attack/cli.py` lines 1400-1468

**Fix:**
```python
# In greenlight command, BEFORE loading issues.json (line ~1410)
synced = store.sync_state_from_git(feature_id)
if synced:
    console.print(f"[dim]Synced {len(synced)} issues from git history[/dim]")
    state = store.load(feature_id)  # Reload after sync
```

### 1.2 Duplicate Implementation Detection

**Bug:** No safeguard against re-implementing already-implemented issues

**Fix Location:** `swarm_attack/orchestrator.py`

**Fix:** Add `_is_already_implemented()` check:
```python
def _is_already_implemented(self, feature_id: str, issue_number: int) -> bool:
    """Belt-and-suspenders check for existing implementation."""
    # Check 1: Git commit exists
    # Check 2: Test file exists and passes
    # Check 3: Implementation file exists
    return any([git_check, test_check, file_check])
```

---

## Part 2: Context Injection (P1)

### 2.1 CLAUDE.md Not Used

**Bug:** Coder agent has zero awareness of project context

**Evidence:** `grep -r "CLAUDE.md" swarm_attack/` returns no matches

**Impact:** Every implementation starts blind, doesn't follow project conventions

**Fix:** Create `ContextBuilder` class that reads:
- `CLAUDE.md` - Project instructions
- `README.md` - Fallback context
- Module registry - What previous issues created
- Completed issue summaries - Semantic understanding of prior work

### 2.2 Shallow Context Handoff

**Current State:** Module registry only contains file paths and class names
```python
# Current (shallow)
{"modules": {"auth/login.py": {"classes": ["User"]}}}
```

**Improved State:** Include semantic summaries
```python
# Improved (rich)
{
    "modules": {"auth/login.py": {"classes": ["User"], "purpose": "User authentication with JWT tokens"}},
    "completed_issues": [
        {"issue": 1, "summary": "Created User model with login/logout methods", "key_files": ["auth/login.py"]}
    ]
}
```

**Implementation:** Generate 1-2 sentence summary via LLM after each issue completes

---

## Part 3: GitHub State Synchronization (P1)

### 3.1 Issue State Labels

**Current:** GitHub issues don't reflect swarm state
**Improved:** Automatic label management

**Labels:**
- `swarm:ready` - Issue ready for implementation
- `swarm:in-progress` - Swarm actively working
- `swarm:blocked` - Implementation blocked (with comment explaining why)
- `swarm:done` - Implementation complete

**Transition Points:**
| Event | Action |
|-------|--------|
| `run_issue_session` starts | Add `swarm:in-progress` |
| `_mark_task_blocked` called | Add `swarm:blocked`, post comment with reason |
| `_mark_task_done` called | Add `swarm:done`, close issue |
| Retry starts | Update comment with retry count |

### 3.2 Rich Status Comments

**On Block:**
```markdown
## 🚫 Implementation Blocked

**Reason:** Test failures after 3 retries

**Test Output:**
```
FAILED test_user_login - AssertionError: expected 200, got 401
```

**Files Modified:**
- `auth/login.py` (created)
- `tests/generated/feature/test_issue_1.py` (created)

**Next Steps:**
1. Review test expectations
2. Check if dependency issue #0 was implemented correctly
3. Run `swarm-attack unblock feature --issue 1` to retry
```

**On Success:**
```markdown
## ✅ Implementation Complete

**Commit:** abc123

**Files Created:**
- `auth/login.py` - User authentication module
- `tests/generated/feature/test_issue_1.py` - 12 tests, all passing

**Test Results:** 12/12 passed

**Ready for Review:** This issue is complete. Dependent issues #2, #3 are now unblocked.
```

---

## Part 4: Intelligent Orchestration (P2)

### 4.1 LLM Coordinator Agent (Optional)

**Current:** PrioritizationAgent uses deterministic scoring algorithm
**Improved:** Optional LLM mode for complex decisions

**When to Use LLM Coordinator:**
- Multiple retries have failed
- Dependencies are partially blocked
- User requests "smart mode"

**CoordinatorAgent Responsibilities:**
```python
class CoordinatorAgent(BaseAgent):
    """LLM-based orchestration for complex decisions."""

    def analyze_failure(self, context: dict) -> FailureAnalysis:
        """Analyze WHY an implementation failed and recommend action."""
        # Returns: retry, skip, escalate, modify_approach

    def select_next_issue(self, context: dict) -> IssueSelection:
        """Intelligently select next issue considering full context."""
        # Considers: dependencies, risk, what was just completed

    def generate_handoff_context(self, completed_issue: int) -> str:
        """Generate semantic summary for next agent."""
        # 1-2 sentence summary of what was accomplished
```

### 4.2 Failure Analysis

**Current:** On retry, just pass test output to coder
**Improved:** LLM analyzes failure pattern and adjusts approach

```python
FAILURE_ANALYSIS_PROMPT = """
Analyze this implementation failure:

**Issue:** #{issue_number} - {title}
**Attempt:** {retry_number} of {max_retries}
**Test Output:** {test_output}
**Files Changed:** {files}

Previous attempts:
{previous_attempts}

Questions to answer:
1. Is this a test expectation problem or implementation problem?
2. Is there a missing dependency that should be implemented first?
3. Should we modify the approach or retry the same way?
4. Is this issue fundamentally blocked?

Return JSON:
{
    "diagnosis": "test_expectation|implementation_bug|missing_dependency|blocked",
    "recommendation": "retry|skip|escalate|modify",
    "modified_approach": "..." // if recommendation is modify
    "reason": "..."
}
"""
```

---

## Part 5: Event Logging & Observability (P3)

### 5.1 Event Log

**Location:** `.swarm/events/{feature_id}.jsonl`

**Events:**
```jsonl
{"ts": "2025-12-17T12:00:00Z", "event": "issue_started", "issue": 1, "session": "sess_123"}
{"ts": "2025-12-17T12:05:00Z", "event": "tests_written", "issue": 1, "count": 12}
{"ts": "2025-12-17T12:10:00Z", "event": "implementation_complete", "issue": 1}
{"ts": "2025-12-17T12:11:00Z", "event": "verification_failed", "issue": 1, "failures": 3}
{"ts": "2025-12-17T12:15:00Z", "event": "retry_started", "issue": 1, "attempt": 2}
{"ts": "2025-12-17T12:20:00Z", "event": "issue_done", "issue": 1, "commit": "abc123"}
```

**Benefits:**
- Debug failed runs after the fact
- Track progress over time
- Enable dashboard visualization
- Audit trail for costs

---

## Part 6: Architecture Changes

### 6.1 New Files

```
swarm_attack/
├── context_builder.py      # NEW: Build rich context for agents
├── github_sync.py          # NEW: GitHub label/comment management
├── event_logger.py         # NEW: Event logging to jsonl
├── agents/
│   └── coordinator.py      # NEW: LLM-based orchestration (optional)
```

### 6.2 Modified Files

| File | Changes |
|------|---------|
| `cli.py` | Add `sync_state_from_git` to greenlight |
| `orchestrator.py` | Add duplicate detection, GitHub sync calls, event logging |
| `agents/coder.py` | Inject CLAUDE.md and rich context into prompt |
| `state_store.py` | Add `save_issue_summary()` for semantic context |

### 6.3 Data Model Changes

**TaskRef (models.py):**
```python
@dataclass
class TaskRef:
    # Existing fields...

    # NEW: Semantic summary of what was accomplished
    completion_summary: Optional[str] = None
```

**IssueOutput (models.py):**
```python
@dataclass
class IssueOutput:
    files_created: list[str]
    classes_defined: dict[str, list[str]]

    # NEW: LLM-generated summary
    semantic_summary: Optional[str] = None
```

---

## Part 7: Configuration

### 7.1 New Config Options

```yaml
# config.yaml
coordination:
  # Sync state from git before operations
  auto_sync_from_git: true

  # Update GitHub issue labels
  github_sync_enabled: true

  # Use LLM for complex orchestration decisions
  llm_coordinator_enabled: false  # opt-in

  # Generate semantic summaries after each issue
  generate_summaries: true

  # Event logging
  event_logging_enabled: true
```

---

## Part 8: Test Plan

### 8.1 Unit Tests

```python
# tests/unit/test_greenlight_sync.py
def test_greenlight_preserves_done_from_git():
    """Greenlight should sync from git before merging issues.json."""
    # Setup: Issue #1 committed in git, state says READY
    # Action: Run greenlight
    # Assert: State now says DONE for issue #1

def test_duplicate_detection_via_git():
    """Should detect already-implemented issues via git log."""
    # Setup: Commit exists for issue #1
    # Action: Check _is_already_implemented(1)
    # Assert: Returns True

def test_duplicate_detection_via_tests():
    """Should detect already-implemented issues via passing tests."""
    # Setup: Test file exists and passes
    # Action: Check _is_already_implemented(1)
    # Assert: Returns True
```

### 8.2 Integration Tests

```python
# tests/integration/test_coordination_v2.py
def test_full_flow_no_duplicate_implementation():
    """Complete flow should not re-implement completed issues."""
    # 1. Init feature
    # 2. Run issue #1 to completion
    # 3. Run greenlight again
    # 4. Run - should pick issue #2, NOT #1

def test_claude_md_injected_into_coder():
    """Coder prompt should include CLAUDE.md content."""
    # Setup: Create CLAUDE.md with marker text
    # Action: Run implementation
    # Assert: Marker text appears in coder prompt

def test_github_labels_updated():
    """GitHub issues should have labels updated."""
    # Requires: GH_TOKEN, real repo
    # Action: Run issue to completion
    # Assert: Issue has swarm:done label
```

---

## Part 9: Migration

### 9.1 Existing Features

For features already in progress:
1. Run `swarm-attack status <feature>` - will auto-sync from git
2. Or manually: `python -c "from swarm_attack.state_store import ...; store.sync_state_from_git('feature')"`

### 9.2 Backward Compatibility

- All new features are opt-in via config
- Default behavior remains the same
- GitHub sync requires labels to exist (auto-created on first use)

---

## Part 10: Success Criteria

### Must Have (P0)
- [ ] `greenlight` calls `sync_state_from_git` before merge
- [ ] Duplicate implementation detection prevents re-work
- [ ] CLAUDE.md content injected into coder prompt

### Should Have (P1)
- [ ] GitHub labels updated at state transitions
- [ ] Rich status comments on blocked/done
- [ ] Semantic summaries saved after completion

### Nice to Have (P2)
- [ ] LLM Coordinator agent for smart decisions
- [ ] Failure analysis with modified approach suggestions
- [ ] Event logging to jsonl

---

## Appendix A: File Locations Reference

| Concept | File | Line |
|---------|------|------|
| Greenlight command | `cli.py` | 1380-1468 |
| sync_state_from_git | `state_store.py` | 605-704 |
| Module registry | `state_store.py` | 562-603 |
| Issue session | `orchestrator.py` | 1800-2100 |
| Coder prompt building | `agents/coder.py` | 700-900 |
| PrioritizationAgent | `agents/prioritization.py` | 1-323 |
| GateAgent | `agents/gate.py` | 1-313 |

## Appendix B: Command Reference

```bash
# Fix state for existing feature
swarm-attack status chief-of-staff  # Auto-syncs from git

# Force sync manually
python -c "
from pathlib import Path
from swarm_attack.config import SwarmConfig
from swarm_attack.state_store import StateStore
config = SwarmConfig(repo_root=Path('.'))
store = StateStore(config)
synced = store.sync_state_from_git('chief-of-staff')
print(f'Synced: {synced}')
"

# Check current state
cat .swarm/state/chief-of-staff.json | python -m json.tool
```
