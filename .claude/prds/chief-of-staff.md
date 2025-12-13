# Chief of Staff Agent PRD

## Executive Summary

The Chief of Staff agent is a strategic orchestration layer for swarm-attack that acts as an autonomous "mini-CEO" for the repository. It conducts daily standups with the human operator (Philip), tracks work across all features and bugs, maintains persistent memory of goals and decisions, and autonomously executes work while respecting human checkpoint gates.

**Vision:** A development partner that starts each day by reviewing what was planned vs accomplished, presents the current state of all work, recommends priorities, gets human alignment, then autonomously executes until it hits a checkpoint requiring human input.

---

## Problem Statement

### Current Pain Points

1. **No Cross-Session Memory**: Each conversation starts fresh. The system doesn't remember what was discussed yesterday, what goals were set, or what was accomplished.

2. **Manual State Gathering**: To understand repo status, the human must manually run multiple commands (`status`, `bug list`, check git, etc.) and mentally synthesize the information.

3. **No Plan Tracking**: There's no record of what was planned vs what actually happened. No way to learn from patterns of success/failure.

4. **Reactive, Not Proactive**: The system waits for commands rather than proactively identifying what needs attention (blockers, approvals needed, regressions).

5. **No Priority Framework**: When multiple features/bugs exist, there's no systematic way to decide what to work on next.

6. **Human Must Context-Switch**: The human has to remember what state everything is in and what the next logical step is for each item.

### User Stories

1. **As Philip**, I want to start my day with a standup that shows me what happened since we last talked, so I can quickly get up to speed.

2. **As Philip**, I want the system to remember what we agreed to work on yesterday and tell me if we achieved those goals.

3. **As Philip**, I want recommended next actions based on priority, blockers, and current state, so I don't have to figure out what to do next.

4. **As Philip**, I want to say "go ahead and work on this for 2 hours" and have the system autonomously execute until it needs my input.

5. **As Philip**, I want the system to track all decisions we make together, so we can review patterns and improve over time.

6. **As Philip**, I want to see GitHub issue deltas (what changed since yesterday) without having to manually check.

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CHIEF OF STAFF AGENT                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │    MEMORY     │  │    PLANNER    │  │   EXECUTOR    │               │
│  │               │  │               │  │               │               │
│  │ • Daily logs  │  │ • Goal setting│  │ • Orchestrator│               │
│  │ • Decisions   │  │ • Priorities  │  │ • Bug Bash    │               │
│  │ • Preferences │  │ • Estimates   │  │ • Git ops     │               │
│  │ • Feedback    │  │ • Risk assess │  │ • GitHub API  │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│          │                 │                  │                         │
│          └─────────────────┼──────────────────┘                         │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      STATE GATHERER                              │   │
│  │                                                                  │   │
│  │  Sources:                                                        │   │
│  │  • Git: commits, branches, diffs, log                           │   │
│  │  • PRDs: .claude/prds/*.md (parse phase from frontmatter)       │   │
│  │  • Specs: .claude/specs/*.md                                    │   │
│  │  • Features: .swarm/features/*/state.json                       │   │
│  │  • Bugs: .swarm/bugs/*/state.json                               │   │
│  │  • Sessions: .swarm/sessions/*.json (interrupted/completed)     │   │
│  │  • GitHub: issues, PRs, comments (via gh CLI)                   │   │
│  │  • Tests: pytest results, collection count                      │   │
│  │  • Previous logs: .swarm/chief-of-staff/daily-log/*.md          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CHECKPOINT SYSTEM                             │   │
│  │                                                                  │   │
│  │  Triggers that pause autonomous execution:                       │   │
│  │  • cost_threshold_reached (configurable, e.g., $10)             │   │
│  │  • time_threshold_reached (configurable, e.g., 2 hours)         │   │
│  │  • blocker_detected (can't proceed without human input)         │   │
│  │  • approval_required (spec approval, fix approval)              │   │
│  │  • high_risk_action (architectural change, main branch push)    │   │
│  │  • error_rate_spike (3+ consecutive failures)                   │   │
│  │  • end_of_session (natural stopping point)                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Model

#### Daily Log Structure
```
.swarm/chief-of-staff/
├── config.yaml                    # Preferences, thresholds
├── daily-log/
│   ├── 2025-12-12.md             # Full day record
│   ├── 2025-12-13.md
│   └── ...
├── weekly-summary/
│   └── 2025-W50.md               # Auto-generated weekly rollup
├── decisions.jsonl                # Append-only decision log
├── preferences.yaml               # Learned preferences from interactions
└── metrics.json                   # Running totals, averages
```

#### Daily Log Format
```markdown
# Daily Log: 2025-12-12

## Morning Standup
- **Time:** 08:30
- **Session ID:** cos-20251212-001

### Yesterday's Goals (from 2025-12-11)
| Goal | Status | Notes |
|------|--------|-------|
| Fix RT blockers | Partial | #1 still blocked |
| Test bug-bash | Done | Full pipeline validated |
| Start new PRD | Skipped | Blockers took priority |

### Current State Snapshot
- **Features:** 1 (bug-bash @ SPEC_NEEDS_APPROVAL)
- **Bugs:** 1 fixed, 0 open
- **GitHub Issues:** 14 closed, 2 blocked
- **Tests:** 3/3 passing
- **Git:** agents-cutover branch, clean

### Today's Plan (agreed with Philip)
1. [P1] Approve bug-bash spec
2. [P2] Build Chief of Staff agent
3. [P3] Clean up test files

### Philip's Notes
> "Let's prioritize the Chief of Staff - it will pay dividends."

---

## Work Log

### 09:15 - Approved bug-bash spec
- Command: `swarm-attack approve bug-bash`
- Result: Success
- Cost: $0

### 09:20 - Started Chief of Staff implementation
- Created PRD
- Cost: $0

### 11:30 - CHECKPOINT: Spec ready for review
- Spec generated for chief-of-staff
- Awaiting Philip's approval
- Cost so far: $2.50

---

## End of Day Summary
- **Goals Completed:** 2/3
- **Total Cost:** $5.20
- **Key Accomplishments:**
  - Chief of Staff PRD approved
  - Spec generated and reviewed
- **Blockers for Tomorrow:**
  - None
- **Carryover:**
  - Clean up test files (low priority)
```

#### Decision Log Format (JSONL)
```json
{"timestamp": "2025-12-12T09:15:00Z", "type": "approval", "item": "bug-bash-spec", "decision": "approved", "rationale": "Spec meets quality thresholds", "human_override": false}
{"timestamp": "2025-12-12T09:30:00Z", "type": "priority", "item": "chief-of-staff", "decision": "P1", "rationale": "Philip requested prioritization", "human_override": true}
{"timestamp": "2025-12-12T11:30:00Z", "type": "checkpoint", "trigger": "approval_required", "action": "paused", "context": "Spec ready for review"}
```

---

## CLI Interface

### New Commands

```bash
# Morning standup - comprehensive daily briefing
swarm-attack standup [--since DATETIME]

# Quick check-in during the day
swarm-attack checkin

# End of day wrap-up
swarm-attack wrapup

# Autonomous execution mode
swarm-attack autopilot [OPTIONS]
  --budget FLOAT        Max spend before checkpoint (default: $10)
  --duration DURATION   Max time before checkpoint (default: 2h)
  --until TRIGGER       Stop at specific trigger (blocker|approval|budget|time)
  --dry-run             Show what would be done without executing

# Review history
swarm-attack history [OPTIONS]
  --days N              Show last N days (default: 7)
  --weekly              Show weekly summaries
  --decisions           Show decision log

# Show current plan
swarm-attack plan [SUBCOMMAND]
  show                  Display today's plan
  set GOAL...           Set goals for today
  status                Compare plan vs actual

# What should we work on?
swarm-attack next --all   # Across all features/bugs with recommendations
```

### Standup Output Format

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  DAILY STANDUP - December 13, 2025                                           ║
║  swarm-attack v0.2.0 | Chief of Staff Agent                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  📅 YESTERDAY'S PLAN vs ACTUAL                                               ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Goal                           │ Planned │ Actual  │ Status            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Approve bug-bash spec          │ 5 min   │ 5 min   │ ✅ Done            │  ║
║  │ Build Chief of Staff PRD       │ 30 min  │ 45 min  │ ✅ Done            │  ║
║  │ Clean up test files            │ 10 min  │ -       │ ⏭️ Skipped         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  📊 REPO HEALTH                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Branch: agents-cutover (clean)                                        │  ║
║  │ Tests: 3/3 passing (100%)                                             │  ║
║  │ Features: 2 total                                                     │  ║
║  │   • bug-bash: SPEC_NEEDS_APPROVAL                                     │  ║
║  │   • chief-of-staff: PRD_READY (new)                                   │  ║
║  │ Bugs: 1 fixed, 0 open                                                 │  ║
║  │ Spend: $0.37 yesterday | $5.20 this week                              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🔔 ITEMS NEEDING YOUR ATTENTION                                             ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ 1. [APPROVAL] bug-bash spec ready for review                          │  ║
║  │ 2. [NEW] chief-of-staff PRD created - ready for spec pipeline         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🔴 BLOCKERS                                                                 ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ None currently                                                         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🎯 RECOMMENDED TODAY                                                        ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Pri │ Task                                    │ Est Cost │ Est Time   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ P1  │ Approve bug-bash spec                   │ $0       │ 5 min      │  ║
║  │ P1  │ Run spec pipeline for chief-of-staff   │ ~$1      │ 15 min     │  ║
║  │ P2  │ Start bug-bash implementation          │ ~$5      │ 1 hr       │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  What would you like to focus on today?                                      ║
║                                                                              ║
║  [1] Accept recommendations and start                                        ║
║  [2] Modify priorities                                                       ║
║  [3] Autopilot: Execute P1 tasks, report back                                ║
║  [4] Something else                                                          ║
║                                                                              ║
║  > _                                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Implementation Requirements

### Phase 1: State Gatherer (Foundation)
**Goal:** Collect all repo state into a single comprehensive report.

Components:
- `StateGatherer` class that queries all data sources
- Git state: branch, status, recent commits, uncommitted changes
- Feature state: all `.swarm/features/*/state.json`
- Bug state: all `.swarm/bugs/*/state.json`
- PRD state: all `.claude/prds/*.md` with frontmatter parsing
- Spec state: all `.claude/specs/*.md`
- Session state: `.swarm/sessions/*.json`
- GitHub state: issues and PRs via `gh` CLI
- Test state: pytest collection and last run results

Output: `RepoStateSnapshot` dataclass with all information.

### Phase 2: Daily Log Persistence
**Goal:** Maintain persistent memory across sessions.

Components:
- `DailyLogManager` class for reading/writing daily logs
- Markdown format for human readability
- JSONL format for decision log (append-only, parseable)
- Auto-create new day's log on first standup
- Link to previous day for continuity

### Phase 3: Standup Command
**Goal:** Interactive morning briefing with recommendations.

Components:
- `StandupAgent` that generates the standup report
- Compare yesterday's plan vs actual (if log exists)
- Priority scoring algorithm for recommendations
- Interactive prompt for goal setting
- Save agreed plan to today's log

### Phase 4: Plan Tracking
**Goal:** Track goals and measure achievement.

Components:
- Goal data model with status tracking
- Auto-update goal status based on state changes
- End-of-day summary generation
- Carryover logic for incomplete goals

### Phase 5: Autopilot Mode
**Goal:** Autonomous execution with checkpoint enforcement.

Components:
- `AutopilotRunner` that executes work items
- Checkpoint trigger detection
- Budget and time tracking
- Progress reporting during execution
- Clean pause/resume capability

### Phase 6: Preference Learning (Future)
**Goal:** Learn from Philip's decisions to improve recommendations.

Components:
- Track human overrides of recommendations
- Pattern detection in successful vs failed approaches
- Preference model for priority weighting
- Personalized estimates based on history

---

## Configuration

```yaml
# .swarm/chief-of-staff/config.yaml

# Checkpoint thresholds
checkpoints:
  budget_usd: 10.0          # Pause after spending this much
  duration_minutes: 120      # Pause after this long
  error_streak: 3           # Pause after N consecutive errors

# Priority weights (0.0 - 1.0)
priorities:
  blocker_weight: 1.0       # Blockers are highest priority
  approval_weight: 0.9      # Human approvals needed
  regression_weight: 0.85   # Test regressions
  in_progress_weight: 0.7   # Continue started work
  new_feature_weight: 0.5   # Start new features

# Standup preferences
standup:
  auto_run_on_start: false  # Run standup automatically
  include_github: true      # Query GitHub for issues/PRs
  include_tests: true       # Run pytest collection
  history_days: 7           # How far back to look

# Autopilot preferences
autopilot:
  default_budget: 10.0
  default_duration: "2h"
  pause_on_approval: true   # Always pause for approvals
  pause_on_high_risk: true  # Always pause for risky ops
```

---

## Success Metrics

1. **Daily Continuity**: 100% of sessions should be able to recall yesterday's plan
2. **Goal Achievement**: Track % of daily goals completed over time
3. **Time to Context**: Standup should provide full context in <30 seconds
4. **Autonomous Efficiency**: % of work completed without human intervention
5. **Checkpoint Accuracy**: Checkpoints should trigger appropriately (not too often, not too rarely)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Log corruption | Loss of memory | Append-only JSONL, daily backups |
| Runaway spending | Cost overrun | Hard budget limits, mandatory checkpoints |
| Stale recommendations | Bad priorities | Always gather fresh state before standup |
| Over-automation | Loss of control | Conservative checkpoint defaults, easy override |

---

## Open Questions

1. Should the Chief of Staff have its own conversation/context window, or operate within the main Claude Code session?
2. How should it handle multiple repos? Per-repo config or global?
3. Should it integrate with calendar/scheduling for time-based planning?
4. How aggressive should auto-recovery be? (Currently requires human trigger)

---

## Timeline

| Phase | Deliverable | Estimated Effort |
|-------|-------------|------------------|
| 1 | State Gatherer | 1 day |
| 2 | Daily Log Persistence | 0.5 day |
| 3 | Standup Command | 1 day |
| 4 | Plan Tracking | 1 day |
| 5 | Autopilot Mode | 2 days |
| 6 | Preference Learning | 2 days (future) |

**Total MVP (Phases 1-5): ~5.5 days**

---

## Appendix: Example Interaction Flow

```
$ swarm-attack standup

[Chief of Staff gathers state...]

╔═══════════════════════════════════════════════════════════════════╗
║  DAILY STANDUP - December 13, 2025                                ║
╠═══════════════════════════════════════════════════════════════════╣
║  [... full standup display ...]                                   ║
║                                                                   ║
║  What would you like to focus on today?                           ║
║  > 3                                                              ║
╚═══════════════════════════════════════════════════════════════════╝

Philip selected: Autopilot mode

Setting goals for today:
1. [P1] Approve bug-bash spec
2. [P1] Run spec pipeline for chief-of-staff

Budget: $10 | Duration: 2h | Checkpoints: approval, blocker

Starting autopilot...

[09:15] Executing: Approve bug-bash spec
[09:15] ✅ Complete ($0)

[09:16] Executing: Run spec pipeline for chief-of-staff
[09:20] Spec author complete ($0.50)
[09:25] Spec critic reviewing...
[09:30] Spec debate round 1/5...

╔═══════════════════════════════════════════════════════════════════╗
║  CHECKPOINT: Approval Required                                    ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  chief-of-staff spec is ready for your review.                    ║
║                                                                   ║
║  Progress so far:                                                 ║
║  • bug-bash spec approved                                         ║
║  • chief-of-staff spec generated                                  ║
║  • Cost: $1.20 / $10 budget                                       ║
║  • Time: 15 min / 2h duration                                     ║
║                                                                   ║
║  [1] Review and approve spec                                      ║
║  [2] Review and request changes                                   ║
║  [3] Pause autopilot, I'll continue manually                      ║
║                                                                   ║
║  > _                                                              ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

*PRD Author: Claude (Chief of Staff Agent Design)*
*Created: 2025-12-12*
*Status: Draft - Awaiting Review*
