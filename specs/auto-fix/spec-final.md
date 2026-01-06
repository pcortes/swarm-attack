# Auto-Fix Specification (Revised)

## Executive Summary

Autonomous bug detection and fixing pipeline. Detects bugs via static analysis, creates bug bash entries, and fixes them in a loop until clean.

**Design Philosophy:** Full autopilot capability with simple guards. No enterprise paranoia—just max_iterations and done.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 AUTO-FIX PIPELINE                           │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
  ┌───────────┐         ┌───────────┐         ┌───────────┐
  │  Manual   │         │  Watch    │         │ Post-Test │
  │   CLI     │         │  Mode     │         │  Hook     │
  └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │              DETECTION PHASE                         │
        │                                                      │
        │   ┌─────────┐   ┌─────────┐   ┌─────────┐           │
        │   │ pytest  │   │  mypy   │   │  ruff   │           │
        │   │ --json  │   │ --json  │   │ --json  │           │
        │   └────┬────┘   └────┬────┘   └────┬────┘           │
        │        └──────────┬──┴────────────┘                 │
        │                   ▼                                 │
        │          StaticBugDetector                          │
        │          (graceful if tool missing)                 │
        └─────────────────────┬───────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │              TRIAGE PHASE                            │
        │                                                      │
        │   Severity: CRITICAL | MODERATE | MINOR             │
        │   Auto-fixable: severity ≤ MODERATE                 │
        │                                                      │
        │   ├── CRITICAL → Human checkpoint                   │
        │   ├── MODERATE → Auto-fix (if auto_approve=true)    │
        │   └── MINOR    → Auto-fix (if auto_approve=true)    │
        └─────────────────────┬───────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │              FIX PHASE                               │
        │                                                      │
        │   BugOrchestrator.init_bug()                        │
        │   BugOrchestrator.analyze()                         │
        │   BugOrchestrator.approve() ← auto if enabled       │
        │   BugOrchestrator.fix()                             │
        └─────────────────────┬───────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │              VERIFY & LOOP                           │
        │                                                      │
        │   Re-run detection on affected files                │
        │   Still bugs? → Loop (up to max_iterations)         │
        │   Clean? → Done                                     │
        │   Max iterations hit? → Stop, report remaining      │
        └─────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. StaticBugDetector (~150 LOC)

Wraps static analysis tools and parses their JSON output.

```python
class StaticBugDetector:
    """Detect bugs via pytest, mypy, and ruff."""

    def detect_all(self, path: str | None = None) -> StaticAnalysisResult:
        """Run all available detectors and combine results."""

    def detect_from_tests(self, path: str | None = None) -> list[StaticBugReport]:
        """Run pytest with --json-report, parse failures."""

    def detect_from_types(self, path: str | None = None) -> list[StaticBugReport]:
        """Run mypy with --output=json, parse errors."""

    def detect_from_lint(self, path: str | None = None) -> list[StaticBugReport]:
        """Run ruff with --output-format=json, parse issues."""

    def _tool_available(self, tool: str) -> bool:
        """Check if tool is installed. Skip gracefully if not."""
```

**Graceful Degradation:** If pytest/mypy/ruff isn't installed, skip that detector and continue. Log a warning, don't fail.

**Output Model:**
```python
@dataclass
class StaticBugReport:
    source: Literal["pytest", "mypy", "ruff"]
    file_path: str
    line_number: int
    error_code: str
    message: str
    severity: Literal["critical", "moderate", "minor"]

@dataclass
class StaticAnalysisResult:
    bugs: list[StaticBugReport]
    tools_run: list[str]       # Which tools actually ran
    tools_skipped: list[str]   # Which tools were missing
```

### 2. AutoFixOrchestrator (~250 LOC)

The main loop that chains detection → fix.

```python
class AutoFixOrchestrator:
    """Autonomous detection-fix loop."""

    def __init__(
        self,
        bug_orchestrator: BugOrchestrator,
        detector: StaticBugDetector,
        config: AutoFixConfig,
    ):
        pass

    def run(
        self,
        target: str | None = None,
        max_iterations: int = 3,
        auto_approve: bool = False,
        dry_run: bool = False,
    ) -> AutoFixResult:
        """
        Run the detection-fix loop.

        1. Detect bugs
        2. Create bug bash entries
        3. For each bug: analyze → approve → fix
        4. Re-detect
        5. Loop until clean or max_iterations
        """

    def watch(
        self,
        target: str | None = None,
        max_iterations: int = 3,
        auto_approve: bool = False,
    ) -> None:
        """
        Watch mode: run detection-fix loop on file changes.
        Uses simple polling (no external dependencies).
        Ctrl+C to stop.
        """

    def _create_bug_from_finding(self, bug: StaticBugReport) -> str | None:
        """Bridge: StaticBugReport → BugOrchestrator.init_bug()"""
```

**Loop Logic:**
```
iteration = 0
while iteration < max_iterations:
    bugs = detector.detect_all(target)
    if not bugs:
        return SUCCESS  # Clean!

    for bug in bugs:
        if bug.severity == "critical" and not auto_approve:
            checkpoint(bug)  # Human review
            continue

        bug_id = create_bug_from_finding(bug)
        if dry_run:
            log(f"Would fix: {bug_id}")
            continue

        bug_orchestrator.analyze(bug_id)
        if auto_approve:
            bug_orchestrator.approve(bug_id)
        bug_orchestrator.fix(bug_id)

    iteration += 1

return PARTIAL  # Max iterations, some bugs remain
```

### 3. Simple Safety (3 criteria only)

| Criterion | Check |
|-----------|-------|
| Severity | ≤ MODERATE for auto-approve |
| Iteration | < max_iterations |
| Tool available | Skip missing tools gracefully |

**No blocklists, no rate limiting, no circuit breakers.** Just run until clean or max iterations.

---

## CLI Commands

### Detection Commands
```bash
swarm-attack analyze all                    # Run pytest + mypy + ruff
swarm-attack analyze all --create-bugs      # Also create bug bash entries
swarm-attack analyze tests                  # pytest only
swarm-attack analyze types                  # mypy only
swarm-attack analyze lint                   # ruff only
swarm-attack analyze lint --fix             # ruff --fix (auto-fix lint issues)
```

### Auto-Fix Commands
```bash
# One-shot: detect and fix bugs
swarm-attack qa auto-fix                    # Detection-fix loop
swarm-attack qa auto-fix --max-iterations 5 # Up to 5 iterations
swarm-attack qa auto-fix --approve-all      # Auto-approve all severities
swarm-attack qa auto-fix --dry-run          # Show what would be fixed

# Target specific paths
swarm-attack qa auto-fix src/api/
swarm-attack qa auto-fix tests/

# Watch mode: continuous monitoring
swarm-attack qa auto-watch                  # Watch for changes, auto-fix
swarm-attack qa auto-watch --approve-all    # Full autopilot
```

---

## Configuration (5 options)

```yaml
# config.yaml

auto_fix:
  enabled: false              # Must be explicitly enabled
  max_iterations: 3           # Max fix attempts per run
  auto_approve: false         # Auto-approve non-critical bugs
  dry_run: false              # Log actions without executing
  watch_poll_seconds: 5       # Poll interval for watch mode
```

That's it. No 20+ config options. Sensible defaults.

---

## Implementation Plan

### Files to Create

| File | LOC | Purpose |
|------|-----|---------|
| `swarm_attack/static_analysis/detector.py` | ~150 | StaticBugDetector |
| `swarm_attack/qa/auto_fix.py` | ~250 | AutoFixOrchestrator |
| `swarm_attack/cli/analyze.py` | ~100 | `analyze` CLI commands |
| `tests/unit/static_analysis/test_detector.py` | ~150 | Unit tests |
| `tests/unit/qa/test_auto_fix.py` | ~200 | Unit tests |

### Files to Modify

| File | Changes |
|------|---------|
| `swarm_attack/cli/qa_commands.py` | Add `auto-fix`, `auto-watch` |
| `swarm_attack/cli/app.py` | Register `analyze` sub-app |
| `swarm_attack/config.py` | Add `auto_fix` config section |

### Effort Estimate

| Phase | Hours |
|-------|-------|
| StaticBugDetector | 2-3 |
| AutoFixOrchestrator | 3-4 |
| Watch mode | 1-2 |
| CLI Commands | 1-2 |
| Tests | 2-3 |
| **Total** | **9-14** |

---

## Critical Gap: qa create-bugs

**Problem:** `swarm-attack qa create-bugs` writes markdown but does NOT create `BugState` entries.

**Solution:** AutoFixOrchestrator calls `BugOrchestrator.init_bug()` directly:

```python
def _create_bug_from_finding(self, bug: StaticBugReport) -> str | None:
    """Create a real BugState entry from a static analysis finding."""
    result = self.bug_orchestrator.init_bug(
        description=f"[{bug.source}] {bug.error_code}: {bug.message}",
        error_message=bug.message,
        test_file=bug.file_path,
    )
    return result.bug_id if result.success else None
```

---

## Success Criteria

1. `swarm-attack analyze all` runs pytest/mypy/ruff and reports bugs
2. `swarm-attack analyze all --create-bugs` creates actual BugState entries
3. `swarm-attack qa auto-fix` runs detection-fix loop until clean
4. `swarm-attack qa auto-fix --approve-all` fixes bugs without human intervention
5. `swarm-attack qa auto-watch` runs continuously until Ctrl+C
6. Missing tools (e.g., mypy not installed) are skipped gracefully
7. Max iterations prevents infinite loops

---

## Manual Testing Instructions

```bash
# Test on buggy-api project
cd /tmp/buggy-api

# 1. Run detection
swarm-attack analyze all
# Expected: Shows bugs from pytest/mypy/ruff

# 2. Create bug entries
swarm-attack analyze all --create-bugs
# Expected: Creates .swarm/bugs/*/state.json files

# 3. Dry run auto-fix
swarm-attack qa auto-fix --dry-run
# Expected: Shows what would be fixed

# 4. Full auto-fix
swarm-attack qa auto-fix --approve-all
# Expected: Bugs get fixed, tests pass

# 5. Watch mode
swarm-attack qa auto-watch --approve-all
# Expected: Watches for changes, auto-fixes
# Ctrl+C to stop
```

---

## What's NOT in This Spec

- ❌ Rate limiting (10 fixes/hour)
- ❌ Circuit breaker pattern
- ❌ Security blocklists
- ❌ Cooldown periods
- ❌ Cost tracking/budgets
- ❌ 20+ config options
- ❌ Cron/scheduled triggers (use actual cron)

These can be added later if users actually need them. Ship simple first.
