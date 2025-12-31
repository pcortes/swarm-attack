# Bug: Stale Session Not Marked as Completed After Successful Run

**Date:** 2025-12-31
**Reporter:** COO Priority Board Implementation Team
**Severity:** Medium

## Description

When swarm-attack completes an implementation run with the message "Implementation Complete", the session JSON file is left in `status: "active"` with `ended_at: null` and `end_status: null`. This causes subsequent runs to fail with:

```
Error: Session 'sess_YYYYMMDD_HHMMSS_XXXXXX' is already active for feature 'X' (working on issue #N)
```

## Steps to Reproduce

1. Run `python -m swarm_attack run coo-priority-board`
2. Wait for successful completion (shows "Implementation Complete" banner)
3. Run `python -m swarm_attack run coo-priority-board` again
4. **Expected:** Next available issue starts implementing
5. **Actual:** Error about session already active

## Root Cause Analysis

The session file at `.swarm/sessions/{feature_id}/{session_id}.json` is not updated when:
- All checkpoints complete successfully
- The "Implementation Complete" message is displayed

Session file shows:
- `status: "active"` (should be `"completed"`)
- `ended_at: null` (should be timestamp)
- `end_status: null` (should be `"success"`)

Both `coder` and `verifier` checkpoints show `status: "complete"`, but the parent session record is not finalized.

## Workaround

Manually edit the session JSON file:
```bash
# Find the session file
find .swarm/sessions -name "*.json" | xargs grep -l '"status": "active"'

# Edit to set:
# - "status": "completed"
# - "ended_at": "YYYY-MM-DDTHH:MM:SS.000000Z"
# - "end_status": "success"
```

Or delete the session file entirely.

## Expected Behavior

When `Implementation Complete` is shown:
1. Session `status` should be set to `"completed"`
2. `ended_at` should have the completion timestamp
3. `end_status` should be `"success"`

## Files Involved

- `swarm_attack/impl_orchestrator.py` (likely - session management)
- `swarm_attack/session.py` or similar session handling module
- `.swarm/sessions/{feature_id}/` - where session state is stored

## Additional Context

This happened during COO Priority Board implementation (issue #2). The `cleanup --stale-sessions` command did not detect this as stale (possibly because checkpoints are complete?).
