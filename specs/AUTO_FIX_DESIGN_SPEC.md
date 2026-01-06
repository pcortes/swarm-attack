# Auto-Fix Design Specification

## Executive Summary

This spec defines how to extend swarm-attack to **automatically detect bugs and fix them** without human intervention (where safe).

**Expert Team Findings Synthesized:**
- QA Architect: Identified gaps in QA→BugBash integration
- Pipeline Designer: Designed autonomous flow with safety controls
- Code Architect: Created implementation plan (~12-17 hours effort)
- Static Analyzer: Designed pytest/mypy/ruff integration

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────┐
                    │           AUTONOMOUS BUG FIX PIPELINE           │
                    └─────────────────────────────────────────────────┘
                                          │
          ┌───────────────────────────────┼───────────────────────────────┐
          │                               │                               │
          ▼                               ▼                               ▼
   ┌─────────────┐               ┌─────────────┐               ┌─────────────┐
   │   TRIGGER   │               │   TRIGGER   │               │   TRIGGER   │
   │ Post-Commit │               │  Scheduled  │               │   Manual    │
   └──────┬──────┘               └──────┬──────┘               └──────┬──────┘
          │                               │                               │
          └───────────────────────────────┼───────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │              DETECTION PHASE                     │
                    │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
                    │  │   pytest    │  │    mypy     │  │   ruff   │ │
                    │  │  failures   │  │   errors    │  │  issues  │ │
                    │  └──────┬──────┘  └──────┬──────┘  └────┬─────┘ │
                    │         └─────────────┬──┴──────────────┘       │
                    │                       ▼                         │
                    │            StaticBugDetector                    │
                    │            + QAOrchestrator                     │
                    └─────────────────────┬───────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │              TRIAGE PHASE                        │
                    │                                                  │
                    │  Severity: CRITICAL | MODERATE | MINOR          │
                    │  Confidence: 0.0 - 1.0                          │
                    │  Risk Level: LOW | MEDIUM | HIGH                │
                    │  Auto-fixable: true | false                     │
                    └─────────────────────┬───────────────────────────┘
                                          │
                    ┌─────────────────────┼───────────────────────────┐
                    │                     │                           │
                    ▼                     ▼                           ▼
          ┌─────────────────┐   ┌─────────────────┐         ┌─────────────────┐
          │  AUTO-FIX PATH  │   │  HUMAN REVIEW   │         │   SKIP/LOG      │
          │                 │   │                 │         │                 │
          │ severity≤MOD    │   │ severity=CRIT   │         │ severity=MINOR  │
          │ confidence≥0.85 │   │ OR risk=HIGH    │         │ (configurable)  │
          │ risk≤MEDIUM     │   │ OR security     │         │                 │
          └────────┬────────┘   └────────┬────────┘         └─────────────────┘
                   │                     │
                   ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐
          │  BugOrchestrator │   │  Checkpoint     │
          │  .analyze()     │   │  (wait human)   │
          │  .approve(auto) │   │                 │
          │  .fix()         │   │                 │
          └────────┬────────┘   └─────────────────┘
                   │
                   ▼
          ┌─────────────────────────────────────────────────┐
          │              VERIFICATION PHASE                  │
          │                                                  │
          │  Re-run detection on affected files              │
          │  Check: fewer bugs? Tests pass? No regressions?  │
          └─────────────────────┬───────────────────────────┘
                                │
                   ┌────────────┴────────────┐
                   │                         │
                   ▼                         ▼
          ┌─────────────────┐       ┌─────────────────┐
          │     COMMIT      │       │    ROLLBACK     │
          │                 │       │                 │
          │  git commit     │       │  git revert     │
          │  emit BUG_FIXED │       │  emit HICCUP    │
          └─────────────────┘       │  human review   │
                                    └─────────────────┘
```

---

## Key Components

### 1. StaticBugDetector (NEW)

Detects bugs via static analysis tools:

```python
class StaticBugDetector:
    def detect_all() -> StaticAnalysisResult
    def detect_from_tests(path) -> list[StaticBugReport]  # pytest
    def detect_from_types(path) -> list[StaticBugReport]  # mypy
    def detect_from_lint(path) -> list[StaticBugReport]   # ruff
```

**Output: `StaticBugReport`**
```python
@dataclass
class StaticBugReport:
    source: BugSource          # pytest, mypy, ruff
    file_path: str
    line_number: int
    error_code: str
    message: str
    severity: BugSeverity      # critical, moderate, minor
    auto_fixable: bool
```

### 2. AutoFixOrchestrator (NEW)

Chains detection → fix in a loop:

```python
class AutoFixOrchestrator:
    def run_detection_fix_loop(
        target: str,
        max_iterations: int = 3,
        auto_approve: bool = False,
        dry_run: bool = False,
    ) -> AutoFixResult
```

**Loop Logic:**
1. Run detection (static + QA)
2. Filter by severity threshold
3. Create bug investigations
4. For each bug: analyze → (auto-approve if safe) → fix
5. Verify with re-detection
6. Repeat until clean or max iterations

### 3. Safety Controls

**Auto-Fix Eligibility Criteria (ALL must pass):**

| Criterion | Threshold |
|-----------|-----------|
| Severity | ≤ MODERATE |
| Confidence | ≥ 0.85 |
| Risk Level | ≠ HIGH |
| Architectural Impact | FALSE |
| Files Affected | ≤ 3 |
| Est. Cost | < $5.00 |
| Security-Critical | FALSE |
| Previous Attempts | < 3 |

**Blocklist (always requires human review):**
- `*.env*`, `*secret*`, `*credential*`
- `migrations/*`, `database/*`
- Schema changes, API breaking changes

**Loop Prevention:**
- Max 3 fix attempts per bug
- Max 10 fixes per hour
- 30-minute cooldown after failure
- Circuit breaker after 5 consecutive failures

---

## CLI Commands

### New Commands

```bash
# Static analysis
swarm-attack analyze all              # Run pytest + mypy + ruff
swarm-attack analyze all --create-bugs # Auto-create bug bash entries
swarm-attack analyze tests             # pytest only
swarm-attack analyze types             # mypy only
swarm-attack analyze lint              # ruff only
swarm-attack analyze lint --fix        # Auto-fix lint issues

# Autonomous QA
swarm-attack qa auto-fix <target>     # Detection-fix loop
swarm-attack qa auto-fix /api/users --dry-run
swarm-attack qa auto-fix src/ --approve-all --max-iterations 5

# Autonomous watch mode
swarm-attack qa auto-watch            # Listen for triggers
swarm-attack qa auto-status           # Check pipeline status
swarm-attack qa auto-pause            # Pause autonomous mode
swarm-attack qa auto-stop             # Emergency stop
```

---

## Configuration

```yaml
# config.yaml

autonomous_qa:
  enabled: true

  triggers:
    post_commit:
      enabled: true
      depth: shallow
      branches: ["main", "develop"]
    scheduled:
      enabled: true
      cron: "0 */4 * * *"

  auto_fix:
    enabled: false              # Must be explicitly enabled
    max_severity: moderate
    min_confidence: 0.85
    max_files_affected: 3
    max_cost_per_fix: 5.0
    blocklist:
      - "*.env*"
      - "*secret*"
      - "migrations/*"

  loop_guard:
    max_fix_attempts: 3
    max_fixes_per_hour: 10
    cooldown_minutes: 30
    circuit_breaker_threshold: 5

  budget:
    max_daily_cost: 100.0
    max_session_cost: 20.0
```

---

## Implementation Plan

### Files to Create

| File | LOC | Complexity |
|------|-----|------------|
| `swarm_attack/static_analysis/detector.py` | ~400 | MEDIUM |
| `swarm_attack/qa/auto_fix.py` | ~400 | MEDIUM |
| `swarm_attack/cli/analyze.py` | ~200 | SMALL |
| `tests/unit/qa/test_auto_fix.py` | ~300 | MEDIUM |
| `tests/unit/static_analysis/test_detector.py` | ~200 | SMALL |

### Files to Modify

| File | Changes |
|------|---------|
| `swarm_attack/cli/qa_commands.py` | Add `auto-fix` command |
| `swarm_attack/cli/app.py` | Register `analyze` sub-app |
| `swarm_attack/qa/qa_config.py` | Add auto-fix config fields |
| `swarm_attack/config.py` | Add autonomous_qa section |

### Effort Estimate

| Phase | Hours |
|-------|-------|
| StaticBugDetector | 4-6 |
| AutoFixOrchestrator | 4-6 |
| CLI Commands | 2-3 |
| Tests | 3-4 |
| Documentation | 1-2 |
| **Total** | **14-21** |

---

## Critical Gap Identified

**The `qa create-bugs` command only writes markdown - it does NOT create actual `BugState` entries!**

The `AutoFixOrchestrator` must bridge this gap by calling `BugOrchestrator.init_bug()` directly instead of relying on `QAOrchestrator.create_bug_investigations()`.

```python
# Bridge function in AutoFixOrchestrator
def _create_bug_states_from_findings(self, findings: list[QAFinding]) -> list[str]:
    bug_ids = []
    for finding in findings:
        result = self.bug_orchestrator.init_bug(
            description=finding.title,
            error_message=finding.description,
        )
        if result.success:
            bug_ids.append(result.bug_id)
    return bug_ids
```

---

## Event Flow

```
TRIGGER (commit/schedule/manual)
    │
    ▼
[1] SYSTEM_PHASE_TRANSITION (qa_autonomous_start)
    │
    ▼
[2] Run detection
    │
    ▼
[3] For each finding:
    │   └─► BUG_DETECTED
    │
    ▼
[4] Triage assessment
    │
    ├─► AUTO_APPROVAL_TRIGGERED (if safe)
    │       │
    │       ▼
    │   [5] Bug Bash Pipeline (auto-approved)
    │       │
    │       ▼
    │   [6] Verification
    │       │
    │       ├─► BUG_FIXED (if pass)
    │       └─► SYSTEM_RECOVERY (if fail, rollback)
    │
    └─► AUTO_APPROVAL_BLOCKED (if needs human)
            │
            ▼
        Create checkpoint, wait for approval
```

---

## Success Criteria

1. `swarm-attack analyze all` finds bugs in test project
2. `swarm-attack analyze all --create-bugs` creates bug bash entries
3. `swarm-attack qa auto-fix` runs detection-fix loop
4. Auto-approval works for low-risk bugs
5. High-risk bugs route to human checkpoint
6. Rollback works when fix verification fails
7. Loop terminates cleanly (max iterations, cost limit, or clean)

---

## Next Steps

1. Implement `StaticBugDetector` with pytest JSON parsing
2. Implement `AutoFixOrchestrator` with loop logic
3. Add CLI commands
4. Add configuration schema
5. Write tests
6. Test on `/tmp/buggy-api` project
