# Expert Team Implementation Prompt: Coordination Layer v2

## Mission

You are a team of 5 expert engineers tasked with implementing the Coordination Layer v2 specification. This is a critical fix for a production system that is wasting resources by repeatedly re-implementing completed work.

**Spec Location:** `/Users/philipjcortes/Desktop/swarm-attack/specs/coordination-layer-v2/spec-final.md`

**Repository:** `/Users/philipjcortes/Desktop/swarm-attack`

---

## Team Roles

### Expert 1: State Management Engineer
**Responsibility:** Fix the critical greenlight sync bug and duplicate detection

**Your Tasks:**
1. Modify `swarm_attack/cli.py` greenlight command (lines ~1400-1468)
   - Add `sync_state_from_git()` call BEFORE loading issues.json
   - Reload state after sync
   - Add console output showing synced issues

2. Add `_is_already_implemented()` to `swarm_attack/orchestrator.py`
   - Check git log for existing commit
   - Check if test file exists and passes
   - Call this before `claim_issue()` in `run_issue_session()`

3. Add `sync_state_from_git()` to `status` command in cli.py
   - Auto-sync when displaying status for accuracy

**Test Requirements:**
- `tests/unit/test_greenlight_sync.py` - Test sync before merge
- `tests/unit/test_duplicate_detection.py` - Test git/test checks

---

### Expert 2: Context Injection Engineer
**Responsibility:** Make CLAUDE.md and rich context available to coder

**Your Tasks:**
1. Create `swarm_attack/context_builder.py`
   ```python
   class ContextBuilder:
       def __init__(self, config: SwarmConfig):
           self.config = config

       def get_project_instructions(self) -> str:
           """Read CLAUDE.md from repo root."""
           candidates = ["CLAUDE.md", "claude.md", ".claude/CLAUDE.md"]
           for name in candidates:
               path = self.config.repo_root / name
               if path.exists():
                   return path.read_text()
           return ""

       def build_coder_context(
           self,
           feature_id: str,
           issue_number: int,
           module_registry: dict,
           issue_body: str,
           completed_summaries: list[dict],
       ) -> dict:
           """Build comprehensive context for coder agent."""
           return {
               "project_instructions": self.get_project_instructions(),
               "module_registry": module_registry,
               "completed_summaries": completed_summaries,
               "feature_id": feature_id,
               "issue_number": issue_number,
               "issue_body": issue_body,
           }

       def get_completed_summaries(self, feature_id: str) -> list[dict]:
           """Get summaries of completed issues."""
           # Read from state, return list of {issue, summary, files}
   ```

2. Modify `swarm_attack/orchestrator.py` `_run_implementation_cycle()`
   - Import and use ContextBuilder
   - Pass rich context to coder agent

3. Modify `swarm_attack/agents/coder.py` `_build_implementation_prompt()`
   - Add "Project Context" section with CLAUDE.md content
   - Add "Completed Work" section with summaries
   - Ensure module registry is formatted readably

**Test Requirements:**
- `tests/unit/test_context_builder.py` - Test CLAUDE.md reading
- Integration test that CLAUDE.md content appears in prompt

---

### Expert 3: GitHub Integration Engineer
**Responsibility:** Sync swarm state to GitHub issue labels and comments

**Your Tasks:**
1. Create `swarm_attack/github_sync.py`
   ```python
   class GitHubSync:
       """Synchronize swarm state to GitHub issues."""

       LABELS = {
           "in_progress": "swarm:in-progress",
           "blocked": "swarm:blocked",
           "done": "swarm:done",
       }

       def __init__(self, config: SwarmConfig, logger: Optional[SwarmLogger] = None):
           self.config = config
           self.logger = logger

       def update_issue_state(self, issue_number: int, state: str) -> bool:
           """Update GitHub issue label."""
           # Remove old swarm:* labels
           # Add new label
           # Return success/failure

       def post_blocked_comment(
           self, issue_number: int, reason: str, test_output: str, files: list[str]
       ) -> bool:
           """Post detailed blocked comment."""
           # Format markdown comment
           # Use gh issue comment

       def post_done_comment(
           self, issue_number: int, commit: str, files: list[str], test_count: int
       ) -> bool:
           """Post success comment and close issue."""
           # Format markdown comment
           # Use gh issue comment
           # Use gh issue close

       def ensure_labels_exist(self) -> None:
           """Create swarm:* labels if they don't exist."""
           # Use gh label create
   ```

2. Modify `swarm_attack/orchestrator.py`
   - Add `_github_sync: Optional[GitHubSync]` field
   - Call `update_issue_state("in_progress")` at session start
   - Call `post_blocked_comment()` in `_mark_task_blocked()`
   - Call `post_done_comment()` in `_mark_task_done()`

3. Add config option `github_sync_enabled` to `swarm_attack/config.py`

**Test Requirements:**
- `tests/unit/test_github_sync.py` - Mock subprocess, test label logic
- Manual test with real GitHub repo

---

### Expert 4: Semantic Summary Engineer
**Responsibility:** Generate and store meaningful summaries of completed work

**Your Tasks:**
1. Modify `swarm_attack/models.py`
   - Add `completion_summary: Optional[str] = None` to `TaskRef`
   - Add `semantic_summary: Optional[str] = None` to `IssueOutput`

2. Modify `swarm_attack/state_store.py`
   - Add `save_completion_summary(feature_id, issue_number, summary)` method
   - Modify `get_module_registry()` to include summaries

3. Create summary generation in `swarm_attack/orchestrator.py`
   ```python
   def _generate_completion_summary(
       self, feature_id: str, issue_number: int, result: AgentResult
   ) -> str:
       """Generate 1-2 sentence summary of what was accomplished."""
       # Use Haiku for fast, cheap summary generation
       prompt = f"""
       Summarize in 1-2 sentences what was accomplished:

       Issue: #{issue_number}
       Files created: {result.output.get('files_created', [])}
       Classes defined: {result.output.get('classes_defined', {})}

       Example: "Created User authentication module with login/logout methods and JWT token validation."
       """
       # Call LLM, return summary
   ```

4. Call summary generation after successful verification in `run_issue_session()`

**Test Requirements:**
- `tests/unit/test_summary_generation.py` - Test prompt building
- Verify summaries are saved and retrieved

---

### Expert 5: Event Logging & Testing Engineer
**Responsibility:** Add observability and ensure comprehensive test coverage

**Your Tasks:**
1. Create `swarm_attack/event_logger.py`
   ```python
   class EventLogger:
       """Log swarm events to jsonl file."""

       def __init__(self, config: SwarmConfig):
           self.events_dir = config.swarm_path / "events"

       def log(self, feature_id: str, event: str, data: dict) -> None:
           """Append event to feature's event log."""
           path = self.events_dir / f"{feature_id}.jsonl"
           entry = {
               "ts": datetime.now(timezone.utc).isoformat(),
               "event": event,
               **data,
           }
           with open(path, "a") as f:
               f.write(json.dumps(entry) + "\n")

       def get_events(self, feature_id: str) -> list[dict]:
           """Read all events for a feature."""
   ```

2. Add event logging calls throughout orchestrator:
   - `issue_started` - When session begins
   - `tests_written` - After test-writer (with count)
   - `implementation_complete` - After coder
   - `verification_passed` / `verification_failed`
   - `retry_started` - When retry begins
   - `issue_done` / `issue_blocked`

3. Create comprehensive integration test:
   ```python
   # tests/integration/test_coordination_v2.py
   def test_full_flow_no_duplicate():
       """End-to-end test that issues aren't re-implemented."""
       # 1. Create test feature with mock PRD
       # 2. Run spec pipeline (mock)
       # 3. Run issue creation (mock)
       # 4. Run greenlight
       # 5. Run implementation for issue #1
       # 6. Verify commit exists
       # 7. Run greenlight again
       # 8. Run implementation - should pick issue #2
       # 9. Verify issue #1 was NOT re-implemented
   ```

4. Add CLI command `swarm-attack events <feature>` to view event log

**Test Requirements:**
- `tests/unit/test_event_logger.py`
- `tests/integration/test_coordination_v2.py`

---

## Implementation Order

Execute in this order to minimize conflicts:

```
Phase 1: Critical Fixes (Expert 1)
├── 1.1 greenlight sync fix
├── 1.2 duplicate detection
└── 1.3 status command sync

Phase 2: Context (Expert 2)
├── 2.1 context_builder.py
├── 2.2 orchestrator integration
└── 2.3 coder prompt injection

Phase 3: GitHub (Expert 3) [parallel with Phase 2]
├── 3.1 github_sync.py
├── 3.2 orchestrator integration
└── 3.3 config option

Phase 4: Summaries (Expert 4) [after Phase 2]
├── 4.1 model changes
├── 4.2 state_store changes
└── 4.3 summary generation

Phase 5: Observability (Expert 5) [parallel with Phase 4]
├── 5.1 event_logger.py
├── 5.2 orchestrator integration
├── 5.3 CLI command
└── 5.4 integration tests
```

---

## Code Quality Requirements

1. **Type Hints:** All new code must have complete type hints
2. **Docstrings:** All public methods must have docstrings
3. **Logging:** Use existing `self._log()` pattern for consistency
4. **Error Handling:** Graceful degradation - GitHub sync failure shouldn't block implementation
5. **Tests:** Minimum 80% coverage on new code

---

## File Checklist

### New Files to Create
- [ ] `swarm_attack/context_builder.py`
- [ ] `swarm_attack/github_sync.py`
- [ ] `swarm_attack/event_logger.py`
- [ ] `tests/unit/test_greenlight_sync.py`
- [ ] `tests/unit/test_duplicate_detection.py`
- [ ] `tests/unit/test_context_builder.py`
- [ ] `tests/unit/test_github_sync.py`
- [ ] `tests/unit/test_event_logger.py`
- [ ] `tests/integration/test_coordination_v2.py`

### Files to Modify
- [ ] `swarm_attack/cli.py` - greenlight sync, status sync, events command
- [ ] `swarm_attack/orchestrator.py` - duplicate detection, github sync, events, context
- [ ] `swarm_attack/agents/coder.py` - context injection in prompt
- [ ] `swarm_attack/models.py` - completion_summary, semantic_summary fields
- [ ] `swarm_attack/state_store.py` - save_completion_summary, get_module_registry update
- [ ] `swarm_attack/config.py` - github_sync_enabled, event_logging_enabled options

---

## Validation

After implementation, run these commands to verify:

```bash
# 1. Run all tests
pytest tests/ -v

# 2. Manual test of critical fix
cd /Users/philipjcortes/Desktop/swarm-attack

# Reset chief-of-staff issue #1 to READY (simulating the bug)
python3 -c "
import json
from pathlib import Path
state_path = Path('.swarm/state/chief-of-staff.json')
state = json.loads(state_path.read_text())
state['tasks'][0]['stage'] = 'READY'
state_path.write_text(json.dumps(state, indent=2))
print('Reset issue #1 to READY')
"

# Run greenlight - should sync from git and preserve DONE
swarm-attack greenlight chief-of-staff

# Verify issue #1 is DONE
python3 -c "
import json
from pathlib import Path
state = json.loads(Path('.swarm/state/chief-of-staff.json').read_text())
print(f\"Issue #1 stage: {state['tasks'][0]['stage']}\")
assert state['tasks'][0]['stage'] == 'DONE', 'BUG NOT FIXED!'
print('SUCCESS: greenlight preserved DONE status from git')
"

# 3. Check CLAUDE.md injection (requires running implementation)
SWARM_DEBUG=1 swarm-attack run chief-of-staff --issue 3 2>&1 | grep -i "project context"
```

---

## Success Criteria

### P0 (Must Pass)
- [ ] `greenlight` syncs from git before merge - issue #1 stays DONE
- [ ] Duplicate detection prevents re-implementation
- [ ] All existing tests still pass

### P1 (Should Pass)
- [ ] CLAUDE.md content appears in coder prompt
- [ ] GitHub labels updated on state changes
- [ ] Completion summaries saved after success

### P2 (Nice to Have)
- [ ] Event log captures all state transitions
- [ ] `swarm-attack events` command works
- [ ] Rich blocked/done comments on GitHub

---

## Notes for Implementation

1. **Read the spec first:** The full specification at `specs/coordination-layer-v2/spec-final.md` has detailed context and rationale.

2. **Don't break existing functionality:** The system currently works (albeit with bugs). Ensure backward compatibility.

3. **GitHub sync is optional:** Make it configurable and fail gracefully. Not everyone has `gh` CLI installed.

4. **Test with chief-of-staff feature:** This feature has the bug - use it as your test case.

5. **Coordinate on shared files:** `orchestrator.py` will be modified by multiple experts. Communicate to avoid conflicts.

---

## Reference: Current State of chief-of-staff

```bash
# Git commits that exist:
git log --oneline --grep="feat(chief-of-staff)"
# 8f97660 feat(chief-of-staff): Implement issue #2 (#2)
# 8caef0a feat(chief-of-staff): Implement issue #1 (#1)
# ...

# State file shows (BUG - should be DONE):
cat .swarm/state/chief-of-staff.json | jq '.tasks[0]'
# {"issue_number": 1, "stage": "READY", ...}  # WRONG!

# After your fix, should show:
# {"issue_number": 1, "stage": "DONE", ...}   # CORRECT!
```

---

## Begin Implementation

Start with Expert 1's tasks (critical fix). Once the greenlight sync is working, proceed in parallel with other experts.

Good luck! The swarm is counting on you.
