# Semantic QA System

Comprehensive guide to the Semantic QA testing system powered by Claude Code CLI with Opus 4.5.

## Overview

The Semantic QA System provides human-like testing capabilities for Swarm Attack pipelines. Unlike traditional unit/integration tests that verify code paths, semantic testing validates that code **does what it claims** from a user's perspective.

**Key Benefits:**
- **Zero API Cost** - Uses Claude Max subscription for unlimited testing via Claude Code CLI
- **Human-like Testing** - Runs real commands, examines real outputs, validates semantically
- **Pipeline Integration** - Automatic testing before commits in feature and bug pipelines
- **Intelligent Regression** - Scheduled regression testing based on commits, issues, or time

## Architecture

```
                                 +------------------+
                                 | SemanticTester   |
                                 |     Agent        |
                                 +--------+---------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
    +---------v---------+       +---------v---------+       +---------v---------+
    | SemanticTestHook  |       | RegressionScheduler|       | SemanticQAMetrics |
    | (Pipeline Gate)   |       | (Trigger Logic)    |       | (Performance)     |
    +-------------------+       +-------------------+       +-------------------+
              |                           |
    +---------v---------+       +---------v---------+
    | Feature Pipeline  |       | RegressionReporter |
    | Bug Pipeline      |       | (Markdown Reports) |
    +-------------------+       +-------------------+
```

### Components

| Component | Purpose |
|-----------|---------|
| **SemanticTesterAgent** | Claude Code CLI-powered agent that performs human-like semantic testing |
| **SemanticTestHook** | Pipeline integration hook that runs after verifier, before commit |
| **RegressionScheduler** | Tracks commits/issues and triggers periodic regression testing |
| **RegressionReporter** | Generates markdown reports for regression test runs |
| **SemanticQAMetrics** | Tracks test performance: true/false positives, execution times |

## SemanticTesterAgent

The core agent that executes semantic tests via the Claude Code CLI.

### SemanticVerdict Enum

Test results use a three-level verdict system:

| Verdict | Description | Pipeline Action |
|---------|-------------|-----------------|
| **PASS** | Feature works as expected, no issues found | Allow commit, record for regression |
| **FAIL** | Critical issues that block the feature | Block commit, create bug investigation |
| **PARTIAL** | Works but with caveats or minor issues | Log warning, allow commit to proceed |

### SemanticScope Enum

Controls the breadth of testing:

| Scope | Description |
|-------|-------------|
| `CHANGES_ONLY` | Test only the changed code (default) |
| `AFFECTED` | Test changed code plus affected integration points |
| `FULL_SYSTEM` | Full system regression testing |

### SemanticIssue Dataclass

Issues found during testing are captured with full context:

```python
@dataclass
class SemanticIssue:
    severity: str      # "critical", "major", or "minor"
    description: str   # What's wrong
    location: str      # Where in code/output (e.g., "src/main.py:42")
    suggestion: str    # How to fix it
```

## Pipeline Integration

### Feature Pipeline

The semantic hook integrates at the verification stage (orchestrator.py lines 3640-3660):

```
Coder (Implementation) --> Verifier (pytest) --> SemanticTestHook --> Commit
                                                        |
                                                        v
                                              [FAIL] --> Create Bug
                                              [PARTIAL] --> Log Warning
                                              [PASS] --> Proceed
```

### Bug Pipeline

The semantic tester runs before pytest verification (bug_orchestrator.py lines 1137-1185):

```
Fix Applied --> SemanticTesterAgent --> pytest Verification --> Fixed
                       |
                       v
              [FAIL] --> Block, Re-analyze
              [PASS/PARTIAL] --> Proceed
```

## RegressionScheduler

Tracks activity and triggers periodic regression testing.

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `issues_between_regressions` | 10 | Trigger regression after this many issues committed |
| `commits_between_regressions` | 25 | Trigger regression after this many commits |
| `time_between_regressions_hours` | 24 | Trigger regression if this many hours since last run |
| `state_file` | `.swarm/regression_state.json` | Location of state persistence file |

## RegressionReporter

Generates markdown reports for regression test runs. Reports are saved to `.swarm/qa/regression-reports/YYYY-MM-DD-HHMMSS.md`.

## CLI Commands

### semantic-test

Run semantic testing on code changes.

```bash
# Basic usage - tests git diff HEAD~1
swarm-attack qa semantic-test

# With expected behavior description
swarm-attack qa semantic-test --expected "User login should work correctly"

# With specific scope
swarm-attack qa semantic-test --scope affected
```

### regression-status

Check the regression scheduler status.

```bash
swarm-attack qa regression-status
swarm-attack qa regression-status --project /path/to/project
```

### regression

Force or check regression testing.

```bash
# Check if regression is needed (doesn't run tests)
swarm-attack qa regression --check

# Force a regression run regardless of thresholds
swarm-attack qa regression --force
```

## Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/qa/agents/semantic_tester.py` | SemanticTesterAgent with Claude CLI |
| `swarm_attack/qa/regression_scheduler.py` | RegressionScheduler trigger logic |
| `swarm_attack/qa/regression_reporter.py` | RegressionReporter markdown generation |
| `swarm_attack/qa/metrics.py` | SemanticQAMetrics tracking |
| `swarm_attack/qa/hooks/semantic_hook.py` | SemanticTestHook for pipeline integration |
| `swarm_attack/cli/qa.py` | CLI commands for semantic testing |

## Testing

### Running Semantic-Specific Tests

```bash
# Run all semantic tester tests
python -m pytest tests/unit/qa/test_semantic*.py -v

# Run integration tests
python -m pytest tests/integration/test_semantic*.py -v
```
