# Swarm Attack Issues Analysis & Fix Requirements

**Date:** 2025-12-14
**Source:** Live walkthrough session with `user-preferences` feature
**Status:** Ready for engineering review and fixes

---

## Executive Summary

A live end-to-end walkthrough of Swarm Attack revealed **4 bugs** and **4 UX issues** that significantly impact usability. The core functionality works (specs are generated, reviews happen, debates run), but users have no visibility into what's happening and the state management has gaps.

---

## Issues Inventory

### BUGS

#### BUG-001: Status doesn't detect PRD file changes
| Field | Value |
|-------|-------|
| **Severity** | High |
| **Symptom** | After creating `.claude/prds/user-preferences.md`, running `python -m swarm_attack status` still shows "No PRD" |
| **Root Cause** | The `status` command reads phase from the state JSON file (`.swarm/state/{feature}.json`) but doesn't check if the PRD file actually exists on disk. The state file is only updated when `run` is called, not when files change externally. |
| **Expected Behavior** | Status should detect PRD file on disk and show "PRD Ready" or transition appropriately |
| **Reproduction** | 1. `swarm_attack init foo` 2. Create `.claude/prds/foo.md` with content 3. `swarm_attack status` → Shows "No PRD" |

#### BUG-002: Inconsistent command naming in help text
| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Symptom** | `init` output says `Run: feature-swarm run user-preferences` but the actual command is `python -m swarm_attack run` |
| **Root Cause** | Hardcoded string in init command output references old/wrong command name |
| **Expected Behavior** | Should say `swarm_attack run` or `python -m swarm_attack run` |
| **Reproduction** | Run `swarm_attack init anything` and read the "Next steps" output |

#### BUG-003: Cost not tracked during execution
| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Symptom** | Status shows `-` for cost even while LLM calls are being made. State JSON shows `cost_total_usd: 0.0` after spec generation. |
| **Root Cause** | Cost is likely only persisted at the end of a run, or cost tracking is broken entirely |
| **Expected Behavior** | Cost should increment and be visible during/after LLM operations |
| **Reproduction** | 1. Run a feature through spec generation 2. Check `swarm_attack status` during/after → Cost shows `-` or `0.0` |

#### BUG-004: State file updated_at not real-time
| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Symptom** | `updated_at` timestamp in state JSON shows old time despite active work |
| **Root Cause** | State is loaded at start, modified in memory, and only written at certain checkpoints (not after each phase transition) |
| **Expected Behavior** | `updated_at` should reflect the most recent state change |
| **Reproduction** | 1. Start a run 2. Check state JSON mid-execution → `updated_at` is stale |

---

### UX ISSUES

#### UX-001: No progress output during run (CRITICAL)
| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Symptom** | Only 2 lines of output for 4+ minutes of execution |
| **Current Output** | `Starting spec pipeline for: user-preferences` and `PRD: /path/to/prd.md` |
| **Expected Output** | Progress messages like: "Generating spec draft...", "Running critic review...", "Starting author/critic debate round 1...", "Debate complete, recommendation: REVISE" |
| **Impact** | Users think the system is frozen; no visibility into what's happening |

#### UX-002: Silent artifact creation
| Field | Value |
|-------|-------|
| **Severity** | High |
| **Symptom** | `spec-draft.md` (33KB, 967 lines) and `spec-review.json` were created with no terminal output |
| **Expected Behavior** | Print messages when files are created: "Wrote spec-draft.md (967 lines)", "Wrote spec-review.json (recommendation: REVISE)" |
| **Impact** | Users don't know files were created until they manually check the specs directory |

#### UX-003: No sub-phase indication in status
| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Symptom** | Status shows "Spec In Progress" but doesn't indicate if it's drafting, reviewing, or debating |
| **Expected Behavior** | Show sub-phase like "Spec In Progress (reviewing)" or "Spec In Progress (debate round 2)" |
| **Impact** | Users can't tell how far along the process is |

#### UX-004: No ETA or duration information
| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Symptom** | No indication of elapsed time or expected duration |
| **Expected Behavior** | Show elapsed time at minimum, optionally show typical duration |
| **Impact** | Users don't know if something is stuck or just slow |

---

## Evidence from Live Session

### Artifacts Generated (silently)
```
specs/user-preferences/
├── spec-draft.md      # 33KB, 967 lines - full technical spec
└── spec-review.json   # Review with scores and issues
```

### spec-review.json Content
```json
{
  "scores": {
    "clarity": 0.8,
    "coverage": 0.75,
    "architecture": 0.75,
    "risk": 0.6
  },
  "issues": [
    {"severity": "moderate", "dimension": "coverage", ...},
    {"severity": "moderate", "dimension": "risk", ...},
    {"severity": "minor", "dimension": "clarity", ...}
  ],
  "recommendation": "REVISE",
  "pass_threshold_met": false
}
```

### State File During Execution
```json
{
  "feature_id": "user-preferences",
  "phase": "SPEC_IN_PROGRESS",
  "tasks": [],
  "current_session": null,
  "created_at": "2025-12-13T18:10:53.380466Z",
  "updated_at": "2025-12-14T19:04:03.674021Z",  // STALE
  "cost_total_usd": 0.0,  // NOT TRACKED
  "cost_by_phase": {}
}
```

### Terminal Output (entire 4+ minute run)
```
Starting spec pipeline for: user-preferences
PRD: /Users/philipjcortes/Desktop/swarm-attack/.claude/prds/user-preferences.md
```
That's it. Nothing else for 4+ minutes while it generated 33KB of content.

---

## Likely Code Locations

Based on typical Python CLI patterns, these are the probable locations to investigate:

| Component | Likely Location | What to Look For |
|-----------|-----------------|------------------|
| CLI commands | `swarm_attack/cli.py` | `status`, `init`, `run` command definitions |
| State management | `swarm_attack/state.py` | `FeatureState` class, `save()`, `load()` methods |
| Pipeline orchestration | `swarm_attack/pipeline.py` | Main run loop, phase transitions |
| Spec author agent | `swarm_attack/agents/author.py` | Spec generation, file writing |
| Spec critic agent | `swarm_attack/agents/critic.py` | Review generation, scoring |
| Debate/moderation | `swarm_attack/agents/moderator.py` | Debate loop orchestration |
| Cost tracking | `swarm_attack/cost.py` or in agents | LLM call cost accumulation |
| Console output | `swarm_attack/console.py` or `rich` usage | Print/logging utilities |

---

## Fix Requirements

### Priority 1: Progress Output (UX-001, UX-002)
**Goal:** Users should see what's happening in real-time

Required output points:
1. Starting spec generation
2. Spec draft complete (with file path and size)
3. Starting critic review
4. Review complete (with recommendation and score summary)
5. Starting debate (if needed)
6. Each debate round
7. Final outcome

### Priority 2: Status PRD Detection (BUG-001)
**Goal:** Status should reflect actual file system state

Required changes:
1. When displaying status, check if PRD file exists on disk
2. If state says NO_PRD but file exists, show "PRD Ready" or auto-update state
3. Consider: should we auto-transition state, or just show accurate status?

### Priority 3: Command Naming (BUG-002)
**Goal:** Help text should show correct commands

Required changes:
1. Find hardcoded "feature-swarm" string
2. Replace with correct command name

### Priority 4: Cost Tracking (BUG-003)
**Goal:** Cost should be tracked and visible

Required changes:
1. Identify where LLM calls are made
2. Ensure cost is captured from API response
3. Accumulate cost in state
4. Persist state after each LLM call (or at phase boundaries)
5. Display cost in status

### Priority 5: State Persistence (BUG-004)
**Goal:** State should be current

Required changes:
1. Update `updated_at` whenever state changes
2. Persist state at key checkpoints (phase changes, after LLM calls)

---

## Testing Plan

After fixes, verify with this sequence:

```bash
# 1. Init a new feature
python -m swarm_attack init test-fix

# 2. Create PRD manually
echo "# Test PRD\n\n## Overview\nTest feature" > .claude/prds/test-fix.md

# 3. Check status - should show PRD detected
python -m swarm_attack status

# 4. Run and watch for progress output
python -m swarm_attack run test-fix

# 5. Check status during run - should show sub-phase and cost
python -m swarm_attack status

# 6. After completion, verify cost is tracked
python -m swarm_attack status

# 7. Cleanup
rm -rf .claude/prds/test-fix.md .swarm/state/test-fix.json specs/test-fix/
```

---

## Appendix: Full Session Log

See: `.swarm/bugs/live-session-user-preferences.md`
