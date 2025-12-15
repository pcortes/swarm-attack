# Swarm Attack Live Session - user-preferences

**Date:** 2025-12-14
**Feature:** user-preferences
**Duration:** ~3+ minutes (still running)

## Session Log

### Step 1: Check Status
**Command:** `python -m swarm_attack status`
**Output:**
```
Swarm Attack Status
Feature             Phase               Tasks  Cost  Updated
bug-bash            Spec Needs Approval   -      -   2025-12-11
chief-of-staff      Blocked               -   $1.19 2025-12-12
session-replay      Blocked               -   $2.38 2025-12-13
test-import-feature Spec Needs Approval   -      -   2025-12-12
```
**Notes:** Status works well. Nice table format. Shows cost tracking.

### Step 2: Init Feature
**Command:** `python -m swarm_attack init user-preferences`
**Output:**
```
Created feature: user-preferences
Created PRD template at: .claude/prds/user-preferences.md
Phase: No PRD

Next steps:
  1. Edit the PRD at .claude/prds/user-preferences.md
  2. Run: feature-swarm run user-preferences
```
**Notes:** Init worked. Shows helpful next steps.

### Step 3: Create PRD
**Action:** Wrote PRD content to `.claude/prds/user-preferences.md`
**Notes:** Successfully created PRD file

### Step 4: Check Status After PRD Creation
**Command:** `python -m swarm_attack status`
**Output:** Shows `user-preferences` with phase `No PRD`
**Notes:** BUG - Status still shows "No PRD" even though PRD file exists!

### Step 5: Run Swarm
**Command:** `python -m swarm_attack run user-preferences 2>&1`
**Output:**
```
Starting spec pipeline for: user-preferences
PRD: /Users/philipjcortes/Desktop/swarm-attack/.claude/prds/user-preferences.md
```
**Notes:**
- Running detected the PRD (unlike status)
- Only 2 lines of output for 3+ minutes of execution
- Process runs but gives no progress indicators

### Step 6: Monitor Progress
**Observations:**
- Files created silently in `specs/user-preferences/`:
  - `spec-draft.md` (33KB, 967 lines)
  - `spec-review.json` (review with REVISE recommendation)
- Status changed to "Spec In Progress"
- No CLI output for any of this - had to check files manually
- State file `updated_at` timestamp not updating in real-time

### Step 7: Review Content
**spec-review.json shows:**
- Scores: clarity=0.8, coverage=0.75, architecture=0.75, risk=0.6
- 3 issues found (2 moderate, 1 minor)
- Recommendation: REVISE
- pass_threshold_met: false

## Bugs Found

### BUG-001: Status doesn't detect PRD file changes
**Where:** Step 4
**Command:** `python -m swarm_attack status` (after creating PRD)
**Error:** Shows "No PRD" even though PRD file exists
**Expected:** Status should detect PRD file on disk and show "PRD Ready" or similar

### BUG-002: Inconsistent command naming in help text
**Where:** Step 2 (init output)
**Output:** Says `Run: feature-swarm run user-preferences`
**Expected:** Should say `swarm_attack run` or `python -m swarm_attack run` (actual command)

### BUG-003: Cost not tracked during execution
**Where:** Step 5-6
**Command:** `python -m swarm_attack status` while running
**Error:** Cost shows `-` even though LLM calls are being made
**Expected:** Cost should increment during/after spec generation

### BUG-004: State file updated_at not real-time
**Where:** Step 6
**Error:** `updated_at` in state JSON shows old timestamp despite active work
**Expected:** Should update as phases progress

## UX Issues

### UX-001: No progress output during run
**Where:** Step 5
**Problem:** After "Starting spec pipeline..." there's no output for minutes while LLM generates spec, reviews it, and runs debate. User has no idea what's happening.
**Suggestion:** Add progress messages like:
- "Generating spec draft..."
- "Running critic review..."
- "Starting author/critic debate..."
- "Round 1 of debate complete..."

### UX-002: No indication of generated artifacts
**Where:** Step 5-6
**Problem:** spec-draft.md and spec-review.json were created silently. User has to manually check the specs directory.
**Suggestion:** Print messages when files are created:
- "Wrote spec-draft.md (967 lines)"
- "Wrote spec-review.json (recommendation: REVISE)"

### UX-003: Status doesn't show current activity
**Where:** Step 6
**Problem:** When running `status` during execution, it shows "Spec In Progress" but no indication of which sub-step (draft/review/debate)
**Suggestion:** Show sub-phase like "Spec In Progress (debating round 2)"

### UX-004: No ETA or duration information
**Where:** Throughout
**Problem:** Process runs for 3+ minutes with no indication of how long it will take
**Suggestion:** Show elapsed time and/or typical duration

## What Works Well

1. **init command** - Creates feature and template cleanly
2. **Status table** - Nice formatting with cost tracking
3. **Spec generation** - Actually produced a 33KB detailed spec
4. **Review system** - Generated detailed review with scores and issues
5. **PRD detection on run** - Even though status didn't detect it, `run` found the PRD

## Summary

- **Got to phase:** Spec In Progress (review complete, debating)
- **Feature completed:** No (still running after 3+ minutes)
- **Artifacts generated:**
  - spec-draft.md (33KB)
  - spec-review.json (REVISE recommendation)
- **Major blockers:** None - system is working but UX is poor
- **Biggest issues:**
  1. No progress feedback during execution
  2. Status doesn't detect PRD file changes
  3. Cost not tracked

## Recommendations

1. **HIGH**: Add progress output during long-running operations
2. **HIGH**: Fix status to detect PRD file on disk
3. **MEDIUM**: Fix command name in help text (feature-swarm vs swarm_attack)
4. **MEDIUM**: Track and display cost during execution
5. **LOW**: Show sub-phase in status during execution
