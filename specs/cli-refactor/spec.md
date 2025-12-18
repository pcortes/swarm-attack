# CLI Refactoring Specification

## Overview

Transform the monolithic `swarm_attack/cli.py` (3,313 lines) into a modular, domain-based CLI architecture following industry best practices (gh, kubectl, gcloud patterns).

**Spec Location:** `/Users/philipjcortes/Desktop/swarm-attack/specs/cli-refactor/spec.md`
**Source File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/cli.py`
**Related File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/cli_recovery.py` (985 lines, keep unchanged)

---

## Goals

1. **LLM-friendly file sizes**: ~300-600 lines per module
2. **Logical command grouping**: `feature`, `bug`, `admin` domains
3. **Backwards compatibility**: Existing commands continue working
4. **Testability**: Module-level unit testing
5. **Discoverability**: `--help` shows command hierarchy

---

## Target Architecture

```
swarm_attack/
├── cli/
│   ├── __init__.py           # Package init, exports cli_main (~20 lines)
│   ├── app.py                # Main Typer app + callback + shortcuts (~150 lines)
│   ├── feature.py            # Feature commands + pipelines (~800 lines)
│   ├── bug.py                # Bug commands (~500 lines)
│   ├── admin.py              # Admin/recovery commands (~400 lines)
│   ├── display.py            # Rich formatters + display helpers (~200 lines)
│   └── common.py             # Shared config/init patterns (~100 lines)
├── cli_recovery.py           # UNCHANGED (985 lines)
└── [other modules unchanged]
```

---

## Command Mapping

### Current → Target

| Current Command | Target Location | Group |
|----------------|-----------------|-------|
| `swarm-attack init` | `cli/feature.py` | `feature init` + top-level alias |
| `swarm-attack run` | `cli/feature.py` | `feature run` + top-level alias |
| `swarm-attack status` | `cli/feature.py` | `feature status` + top-level alias |
| `swarm-attack approve` | `cli/feature.py` | `feature approve` |
| `swarm-attack reject` | `cli/feature.py` | `feature reject` |
| `swarm-attack greenlight` | `cli/feature.py` | `feature greenlight` |
| `swarm-attack events` | `cli/feature.py` | `feature events` |
| `swarm-attack issues` | `cli/feature.py` | `feature issues` |
| `swarm-attack next` | `cli/feature.py` | `feature next` |
| `swarm-attack smart` | `cli/feature.py` | `feature smart` |
| `swarm-attack import-spec` | `cli/feature.py` | `feature import-spec` |
| `swarm-attack bug *` | `cli/bug.py` | `bug *` (unchanged) |
| `swarm-attack cleanup` | `cli/admin.py` | `admin cleanup` + alias |
| `swarm-attack unlock` | `cli/admin.py` | `admin unlock` + alias |
| `swarm-attack reset` | `cli/admin.py` | `admin reset` + alias |
| `swarm-attack diagnose` | `cli/admin.py` | `admin diagnose` + alias |
| `swarm-attack recover` | `cli/admin.py` | `admin recover` + alias |
| `swarm-attack unblock` | `cli/admin.py` | `admin unblock` + alias |

---

## File Specifications

### 1. `cli/__init__.py`

```python
"""CLI package for swarm-attack."""
from swarm_attack.cli.app import app, cli_main

__all__ = ["app", "cli_main"]
```

### 2. `cli/common.py`

**Move from cli.py:**
- `_project_dir` global variable (line 47)
- `_get_project_dir()` function (line 50-52)
- Config loading pattern used by all commands
- `_init_swarm_directory()` logic
- `_get_prd_path()` (line 562-564)
- `_get_spec_dir()` (line 567-569)

**Exports:**
```python
# Global state management
_project_dir: Optional[str] = None

def get_project_dir() -> Optional[str]: ...
def set_project_dir(path: str) -> None: ...

# Console singleton
_console: Optional[Console] = None
def get_console() -> Console: ...

# Config helpers
def get_config_or_default() -> SwarmConfig: ...
def init_swarm_directory(config: SwarmConfig) -> None: ...
def get_prd_path(config: SwarmConfig, feature_id: str) -> Path: ...
def get_spec_dir(config: SwarmConfig, feature_id: str) -> Path: ...
```

### 3. `cli/display.py`

**Move from cli.py:**
- `PHASE_DISPLAY` dict (lines 59-72)
- `STAGE_DISPLAY` dict (lines 75-85)
- `BUG_PHASE_DISPLAY` dict (lines 2219-2234)
- `_format_phase()` (lines 88-91)
- `_format_stage()` (lines 94-97)
- `_format_bug_phase()` (lines 2237-2240)
- `_format_cost()` (lines 100-104)
- `_get_task_summary()` (lines 107-123)
- `_generate_completion_report()` (lines 126-198)
- `_show_all_features()` (find in file)
- `_show_feature_detail()` (find in file, lines ~300-430)

**Exports:**
```python
from rich.text import Text
from swarm_attack.models import FeaturePhase, TaskStage, RunState

PHASE_DISPLAY: dict[FeaturePhase, tuple[str, str]]
STAGE_DISPLAY: dict[TaskStage, tuple[str, str]]
BUG_PHASE_DISPLAY: dict[str, tuple[str, str]]

def format_phase(phase: FeaturePhase) -> Text: ...
def format_stage(stage: TaskStage) -> Text: ...
def format_bug_phase(phase_value: str) -> Text: ...
def format_cost(cost_usd: float) -> str: ...
def get_task_summary(state: RunState) -> str: ...
def generate_completion_report(state: RunState, feature_id: str) -> str: ...
def show_all_features(store: StateStore, config: SwarmConfig) -> None: ...
def show_feature_detail(store: StateStore, feature_id: str, config: SwarmConfig) -> None: ...
```

### 4. `cli/app.py`

**Contains:**
- Main Typer app creation
- `@app.callback` for `--project` and `--version`
- `version_callback()` function
- Import and wire up sub-apps: `feature_app`, `bug_app`, `admin_app`
- Top-level command shortcuts (status, run, init)

**Structure:**
```python
"""Main Typer app definition and routing."""
from typing import Optional
from pathlib import Path

import typer

from swarm_attack import __version__
from swarm_attack.cli.common import get_console, set_project_dir

# Create main app
app = typer.Typer(
    name="swarm-attack",
    help="Autonomous AI-powered feature development",
    add_completion=False,
)

# Import and register sub-apps
from swarm_attack.cli.feature import app as feature_app
from swarm_attack.cli.bug import app as bug_app
from swarm_attack.cli.admin import app as admin_app

app.add_typer(feature_app, name="feature", help="Feature development workflow")
app.add_typer(bug_app, name="bug", help="Bug investigation workflow")
app.add_typer(admin_app, name="admin", help="Recovery and admin commands")

console = get_console()

def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"swarm-attack version {__version__}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Project directory to operate on (default: current directory)",
    ),
    version: bool = typer.Option(
        False, "--version", "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Swarm Attack - Autonomous feature development orchestrator."""
    if project:
        project_path = Path(project)
        if not project_path.is_dir():
            console.print(f"[red]Error: Project directory not found: {project}[/red]")
            raise typer.Exit(1)
        set_project_dir(str(project_path.absolute()))

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

# ============================================================================
# Top-level shortcuts for common commands
# ============================================================================

@app.command()
def status(
    feature_id: Optional[str] = typer.Argument(None, help="Feature ID"),
) -> None:
    """Show feature status (shortcut for: feature status)."""
    from swarm_attack.cli.feature import status as feature_status
    feature_status(feature_id)

@app.command()
def run(
    feature_id: str = typer.Argument(..., help="Feature ID"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i"),
) -> None:
    """Run pipeline (shortcut for: feature run)."""
    from swarm_attack.cli.feature import run as feature_run
    feature_run(feature_id, issue)

@app.command()
def init(
    feature_id: str = typer.Argument(..., help="Feature ID"),
) -> None:
    """Initialize feature (shortcut for: feature init)."""
    from swarm_attack.cli.feature import init as feature_init
    feature_init(feature_id)

# ============================================================================
# Entry point
# ============================================================================

def cli_main() -> None:
    """Entry point for the CLI."""
    app()
```

### 5. `cli/feature.py`

**Move from cli.py:**
- `init` command (lines 573-670)
- `import_spec` command (lines 649-928) - NOTE: overlaps, find actual location
- `run` command (lines 930-993)
- `_run_spec_pipeline()` function (lines 996-1185)
- `_run_implementation()` function (lines 1188-1303)
- `approve` command (lines 1306-1388)
- `reject` command (lines 1390-1434)
- `greenlight` command (lines 1436-1546)
- `issues` command (lines 1548-1695)
- `next` command (lines 1697-1789)
- `smart` command (lines 1792-1946)
- `status` command (lines 481-506)
- `events` command (lines 509-559)

**Structure:**
```python
"""Feature workflow commands."""
from typing import Optional
import typer

from swarm_attack.cli.common import get_console, get_config_or_default, init_swarm_directory
from swarm_attack.cli.display import format_phase, format_stage, format_cost
from swarm_attack.state_store import get_store

app = typer.Typer(
    name="feature",
    help="Feature development workflow",
)

console = get_console()

# ============================================================================
# Pipeline Functions (private)
# ============================================================================

def _run_spec_pipeline(config, store, state, feature_id) -> None:
    """Run the spec debate pipeline."""
    # Move implementation from cli.py lines 996-1185
    ...

def _run_implementation(config, store, state, feature_id, issue_number=None) -> None:
    """Run the implementation pipeline."""
    # Move implementation from cli.py lines 1188-1303
    ...

# ============================================================================
# Commands
# ============================================================================

@app.command()
def init(feature_id: str = typer.Argument(...)) -> None:
    """Initialize a new feature."""
    ...

@app.command()
def run(feature_id: str = typer.Argument(...), issue: Optional[int] = typer.Option(None)) -> None:
    """Run the appropriate pipeline for a feature."""
    ...

@app.command()
def status(feature_id: Optional[str] = typer.Argument(None)) -> None:
    """Show feature status dashboard."""
    ...

@app.command()
def events(feature_id: str = typer.Argument(...), limit: int = typer.Option(20)) -> None:
    """Show event log for a feature."""
    ...

@app.command()
def approve(feature_id: str = typer.Argument(...)) -> None:
    """Approve a spec and transition phase."""
    ...

@app.command()
def reject(feature_id: str = typer.Argument(...), reason: str = typer.Option(...)) -> None:
    """Reject a spec with reason."""
    ...

@app.command()
def greenlight(feature_id: str = typer.Argument(...), issues: Optional[str] = typer.Option(None)) -> None:
    """Approve issues for implementation."""
    ...

@app.command()
def issues(feature_id: str = typer.Argument(...)) -> None:
    """Create and validate issues from spec."""
    ...

@app.command()
def next(feature_id: str = typer.Argument(...)) -> None:
    """Show next action using state machine."""
    ...

@app.command()
def smart(feature_id: str = typer.Argument(...)) -> None:
    """Smart CLI with recovery flow."""
    ...

@app.command("import-spec")
def import_spec(feature_id: str = typer.Argument(...), spec_path: str = typer.Argument(...)) -> None:
    """Import external spec and run debate pipeline."""
    ...
```

### 6. `cli/bug.py`

**Move from cli.py:**
- `bug_app` creation (lines 2211-2216)
- `BUG_PHASE_DISPLAY` already moved to display.py
- `_format_bug_phase()` already moved to display.py
- `bug_init` command (lines 2244-2311)
- `bug_analyze` command (lines 2314-2443)
- `bug_status` command (lines 2446-2592)
- `bug_approve` command (lines 2594-2673)
- `bug_fix` command (lines 2675-2741)
- `bug_list` command (lines 2743-2815)
- `bug_reject` command (lines 2817-2865)
- `bug_unblock` command (lines 2867-2903)

**Structure:**
```python
"""Bug investigation workflow commands."""
from typing import Optional
import typer

from swarm_attack.cli.common import get_console, get_config_or_default, init_swarm_directory
from swarm_attack.cli.display import format_bug_phase, format_cost

app = typer.Typer(
    name="bug",
    help="Bug investigation commands for Bug Bash pipeline",
    no_args_is_help=True,
)

console = get_console()

@app.command("init")
def bug_init(description: str = typer.Argument(...), ...) -> None:
    """Initialize a new bug investigation."""
    from swarm_attack.bug_orchestrator import BugOrchestrator
    ...

@app.command("analyze")
def bug_analyze(bug_id: str = typer.Argument(...), ...) -> None:
    """Run the full analysis pipeline."""
    ...

@app.command("status")
def bug_status(bug_id: Optional[str] = typer.Argument(None)) -> None:
    """Show bug investigation status."""
    ...

@app.command("approve")
def bug_approve(bug_id: str = typer.Argument(...)) -> None:
    """Approve fix plan."""
    ...

@app.command("fix")
def bug_fix(bug_id: str = typer.Argument(...)) -> None:
    """Execute approved fix."""
    ...

@app.command("list")
def bug_list() -> None:
    """List all bugs."""
    ...

@app.command("reject")
def bug_reject(bug_id: str = typer.Argument(...), reason: str = typer.Option(...)) -> None:
    """Reject/close bug."""
    ...

@app.command("unblock")
def bug_unblock(bug_id: str = typer.Argument(...)) -> None:
    """Unblock bug from stuck state."""
    ...
```

### 7. `cli/admin.py`

**Move from cli.py:**
- `cleanup` command (lines 2912-3007)
- `unlock` command (lines 3010-3077)
- `reset_issue` command (lines 3080-3165)
- `diagnose` command (lines 3167-3303)
- `recover` command (lines 1948-2068)
- `unblock` command (lines 2070-2204)

**Structure:**
```python
"""Admin and recovery commands."""
from typing import Optional
import typer

from swarm_attack.cli.common import get_console, get_config_or_default, init_swarm_directory
from swarm_attack.cli.display import format_stage, format_phase
from swarm_attack.state_store import get_store

app = typer.Typer(
    name="admin",
    help="Recovery and admin commands",
    no_args_is_help=True,
)

console = get_console()

@app.command()
def cleanup(
    feature_id: Optional[str] = typer.Argument(None),
    stale_sessions: bool = typer.Option(False, "--stale-sessions", "-s"),
    orphan_locks: bool = typer.Option(False, "--orphan-locks", "-l"),
    all_cleanup: bool = typer.Option(False, "--all", "-a"),
) -> None:
    """Clean up stale sessions and orphan locks."""
    from swarm_attack.recovery import LockManager, HealthChecker
    from swarm_attack.session_manager import SessionManager
    ...

@app.command()
def unlock(
    feature_id: str = typer.Argument(...),
    issue: int = typer.Option(..., "--issue", "-i"),
    force: bool = typer.Option(False, "--force", "-f"),
) -> None:
    """Force-unlock a stuck issue."""
    from swarm_attack.recovery import LockManager
    ...

@app.command("reset")
def reset_issue(
    feature_id: str = typer.Argument(...),
    issue: int = typer.Option(..., "--issue", "-i"),
    hard: bool = typer.Option(False, "--hard"),
) -> None:
    """Reset an issue to READY state."""
    from swarm_attack.recovery import LockManager
    ...

@app.command()
def diagnose(feature_id: str = typer.Argument(...)) -> None:
    """Show diagnostics and recovery suggestions."""
    from swarm_attack.recovery import LockManager, HealthChecker
    from swarm_attack.session_manager import SessionManager
    ...

@app.command()
def recover(feature_id: str = typer.Argument(...)) -> None:
    """Recovery flow for interrupted/blocked features."""
    from swarm_attack.cli_recovery import (
        check_interrupted_sessions,
        display_recovery_options,
        handle_resume,
        handle_backup_restart,
        handle_skip,
    )
    from swarm_attack.session_manager import SessionManager
    ...

@app.command()
def unblock(
    feature_id: str = typer.Argument(...),
    phase: Optional[str] = typer.Option(None, "--phase"),
) -> None:
    """Unblock features from BLOCKED phase."""
    from swarm_attack.cli_recovery import check_spec_pipeline_blocked, run_recovery_flow
    from swarm_attack.session_manager import SessionManager
    ...
```

---

## pyproject.toml Update

```toml
[project.scripts]
swarm-attack = "swarm_attack.cli:cli_main"
```

---

## Migration Phases

### Phase 1: Create Package Structure
1. Create `swarm_attack/cli/` directory
2. Create `cli/__init__.py` with exports
3. Update `pyproject.toml` entry point
4. Verify: `swarm-attack --help` works

### Phase 2: Extract display.py
1. Create `cli/display.py`
2. Move all formatting functions and constants
3. Update imports in cli.py to use new module
4. Verify: `swarm-attack status` displays correctly

### Phase 3: Extract common.py
1. Create `cli/common.py`
2. Move config/init utilities
3. Update imports
4. Verify: All commands work

### Phase 4: Extract bug.py
1. Create `cli/bug.py`
2. Move bug_app and all bug commands
3. Wire up in app.py
4. Verify: `swarm-attack bug status` works

### Phase 5: Extract admin.py
1. Create `cli/admin.py`
2. Move recovery/admin commands
3. Wire up in app.py
4. Add backwards-compatible aliases
5. Verify: `swarm-attack cleanup` and `swarm-attack admin cleanup` both work

### Phase 6: Extract feature.py
1. Create `cli/feature.py`
2. Move feature commands and pipeline functions
3. Wire up in app.py
4. Add top-level shortcuts
5. Verify: Full workflow works

### Phase 7: Create app.py
1. Consolidate main app logic
2. Add all sub-app imports
3. Remove old cli.py
4. Final verification

---

## Verification Checklist

After each phase, run:

```bash
# Basic functionality
swarm-attack --help
swarm-attack --version
swarm-attack status

# Feature workflow
swarm-attack feature --help
swarm-attack init test-feature  # Should work (alias)
swarm-attack feature init test-feature  # Should work (explicit)

# Bug workflow
swarm-attack bug --help
swarm-attack bug status

# Admin workflow
swarm-attack admin --help
swarm-attack cleanup --all  # Alias
swarm-attack admin cleanup --all  # Explicit

# Run tests
pytest tests/ -v
```

---

## Critical Implementation Notes

1. **Lazy imports**: Keep lazy import pattern for heavy modules (SessionManager, Orchestrator, etc.)
2. **Console singleton**: Use `get_console()` from common.py, not direct Console()
3. **Global state**: `_project_dir` must be accessible across modules via get/set functions
4. **No circular imports**: common.py and display.py must not import from feature/bug/admin
5. **Preserve exit codes**: Commands must preserve their exit codes (0, 1, 2)
6. **Rich output**: All Rich Panel/Table output must remain identical
7. **cli_recovery.py**: Do NOT modify this file - it's already well-structured

---

## Source Line References

Key locations in current `cli.py` (3,313 lines):

| Content | Lines |
|---------|-------|
| Imports | 1-35 |
| Typer app creation | 37-47 |
| Phase/Stage display dicts | 59-85 |
| Format functions | 88-198 |
| _show_feature_detail | ~300-430 |
| version_callback, main callback | 434-477 |
| status command | 480-506 |
| events command | 508-559 |
| init command | 572-670 |
| import-spec command | Find exact location |
| run command | 930-993 |
| _run_spec_pipeline | 996-1185 |
| _run_implementation | 1188-1303 |
| approve command | 1306-1388 |
| reject command | 1390-1434 |
| greenlight command | 1436-1546 |
| issues command | 1548-1695 |
| next command | 1697-1789 |
| smart command | 1792-1946 |
| recover command | 1948-2068 |
| unblock command | 2070-2204 |
| Bug section header | 2206-2208 |
| bug_app creation | 2211-2216 |
| Bug phase display | 2219-2240 |
| bug commands | 2243-2903 |
| Recovery section header | 2906-2908 |
| cleanup command | 2912-3007 |
| unlock command | 3010-3077 |
| reset command | 3080-3165 |
| diagnose command | 3167-3303 |
| cli_main entry | 3307-3313 |
