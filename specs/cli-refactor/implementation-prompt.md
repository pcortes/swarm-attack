# CLI Refactoring Implementation Prompt

Use this prompt with Claude, GPT-4, or any capable LLM to implement the CLI refactoring.

---

## PROMPT START

You are a **team of expert Python engineers** specializing in CLI architecture, Typer/Click frameworks, and large-scale refactoring. Your mission is to transform a monolithic 3,313-line CLI into a modular, maintainable architecture.

### Your Team Roles

1. **Lead Architect** - Oversees the overall structure, ensures no circular imports, validates the module boundaries
2. **CLI Specialist** - Expert in Typer, handles command routing, sub-apps, and backwards compatibility
3. **Python Expert** - Ensures clean imports, proper type hints, maintains lazy loading patterns
4. **QA Engineer** - Validates each phase, ensures no regressions, verifies exit codes and output

### The Mission

Transform `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/cli.py` (3,313 lines) into a modular CLI package following the specification at:

**SPEC LOCATION:** `/Users/philipjcortes/Desktop/swarm-attack/specs/cli-refactor/spec.md`

Read this spec file FIRST before doing any implementation.

### Repository Structure

```
/Users/philipjcortes/Desktop/swarm-attack/
├── swarm_attack/
│   ├── cli.py                 # SOURCE: 3,313 lines - THIS IS WHAT WE'RE REFACTORING
│   ├── cli_recovery.py        # DO NOT MODIFY (985 lines, already well-structured)
│   ├── config.py              # Config loading
│   ├── models.py              # Data models (FeaturePhase, TaskStage, RunState, etc.)
│   ├── state_store.py         # State persistence
│   ├── orchestrator.py        # Pipeline orchestration
│   ├── session_manager.py     # Session lifecycle
│   ├── recovery.py            # Recovery utilities (LockManager, HealthChecker)
│   ├── bug_orchestrator.py    # Bug pipeline
│   └── [other modules]
├── specs/
│   └── cli-refactor/
│       └── spec.md            # DETAILED SPECIFICATION - READ THIS
├── tests/
│   └── [existing tests]
└── pyproject.toml             # Entry point definition
```

### Implementation Instructions

**Execute the migration in 7 phases, completing each phase fully before moving to the next:**

---

#### PHASE 1: Create Package Structure

1. Create directory: `swarm_attack/cli/`
2. Create `cli/__init__.py`:
```python
"""CLI package for swarm-attack."""
from swarm_attack.cli.app import app, cli_main

__all__ = ["app", "cli_main"]
```

3. Create minimal `cli/app.py` that imports and re-exports from existing cli.py temporarily
4. Update `pyproject.toml`:
```toml
[project.scripts]
swarm-attack = "swarm_attack.cli:cli_main"
```

**Verify:** `swarm-attack --help` still works

---

#### PHASE 2: Extract display.py

1. Create `cli/display.py`
2. Move from cli.py:
   - `PHASE_DISPLAY` dict (lines 59-72)
   - `STAGE_DISPLAY` dict (lines 75-85)
   - `BUG_PHASE_DISPLAY` dict (lines 2219-2234)
   - `_format_phase()` function (lines 88-91) → rename to `format_phase()`
   - `_format_stage()` function (lines 94-97) → rename to `format_stage()`
   - `_format_bug_phase()` function (lines 2237-2240) → rename to `format_bug_phase()`
   - `_format_cost()` function (lines 100-104) → rename to `format_cost()`
   - `_get_task_summary()` function (lines 107-123) → rename to `get_task_summary()`
   - `_generate_completion_report()` function (lines 126-198) → rename to `generate_completion_report()`
   - `_show_all_features()` function → rename to `show_all_features()`
   - `_show_feature_detail()` function → rename to `show_feature_detail()`

3. Add proper imports at top of display.py
4. Update cli.py to import from cli.display instead of defining locally

**Verify:** `swarm-attack status` and `swarm-attack bug status` display correctly

---

#### PHASE 3: Extract common.py

1. Create `cli/common.py`
2. Move from cli.py:
   - `_project_dir` global (line 47)
   - `_get_project_dir()` (lines 50-52) → `get_project_dir()`
   - Create `set_project_dir(path: str)` function
   - Move console creation to `get_console()` function
   - Move `_get_config_or_default()` logic → `get_config_or_default()`
   - Move `_init_swarm_directory()` logic → `init_swarm_directory()`
   - Move `_get_prd_path()` (line 562-564) → `get_prd_path()`
   - Move `_get_spec_dir()` (line 567-569) → `get_spec_dir()`

3. Update cli.py to import from cli.common

**Verify:** All commands still work

---

#### PHASE 4: Extract bug.py

1. Create `cli/bug.py`
2. Move the entire bug command section from cli.py (lines 2206-2903):
   - bug_app Typer creation
   - All 8 bug commands: init, analyze, status, approve, fix, list, reject, unblock
3. Import formatters from cli.display
4. Import utilities from cli.common
5. Keep lazy imports inside command functions (e.g., `from swarm_attack.bug_orchestrator import BugOrchestrator`)
6. Update cli/app.py to import and register bug_app

**Verify:** `swarm-attack bug status`, `swarm-attack bug --help` work

---

#### PHASE 5: Extract admin.py

1. Create `cli/admin.py`
2. Move admin/recovery commands from cli.py:
   - `cleanup` (lines 2912-3007)
   - `unlock` (lines 3010-3077)
   - `reset_issue` (lines 3080-3165)
   - `diagnose` (lines 3167-3303)
   - `recover` (lines 1948-2068)
   - `unblock` (lines 2070-2204)
3. Create admin_app Typer sub-app
4. Import from cli.display and cli.common
5. Keep lazy imports for heavy modules
6. Update cli/app.py to register admin_app
7. Add backwards-compatible aliases in app.py for common commands:
   ```python
   @app.command("cleanup", hidden=True)
   def cleanup_alias(...):
       """Deprecated: Use 'swarm-attack admin cleanup'"""
       from swarm_attack.cli.admin import cleanup
       cleanup(...)
   ```

**Verify:**
- `swarm-attack admin cleanup --all` works
- `swarm-attack cleanup --all` still works (backwards compatible)
- `swarm-attack admin --help` shows all admin commands

---

#### PHASE 6: Extract feature.py

1. Create `cli/feature.py`
2. Move feature commands from cli.py:
   - `status` (lines 480-506)
   - `events` (lines 508-559)
   - `init` (lines 572-670)
   - `run` (lines 930-993)
   - `approve` (lines 1306-1388)
   - `reject` (lines 1390-1434)
   - `greenlight` (lines 1436-1546)
   - `issues` (lines 1548-1695)
   - `next` (lines 1697-1789)
   - `smart` (lines 1792-1946)
   - `import_spec` (find location)
3. Move pipeline functions:
   - `_run_spec_pipeline()` (lines 996-1185)
   - `_run_implementation()` (lines 1188-1303)
4. Create feature_app Typer sub-app
5. Update cli/app.py to:
   - Register feature_app
   - Add top-level shortcuts for status, run, init

**Verify:**
- `swarm-attack feature status` works
- `swarm-attack status` works (shortcut)
- `swarm-attack feature run my-feature` works
- `swarm-attack run my-feature` works (shortcut)

---

#### PHASE 7: Finalize app.py and Clean Up

1. Finalize `cli/app.py` with:
   - Clean imports of all sub-apps
   - Main callback with --project and --version
   - Top-level command shortcuts
   - Entry point cli_main()
2. Delete or rename old `cli.py` to `cli_legacy.py`
3. Verify all imports work
4. Run full test suite

**Final Verification:**
```bash
# All help commands
swarm-attack --help
swarm-attack feature --help
swarm-attack bug --help
swarm-attack admin --help

# Top-level shortcuts
swarm-attack status
swarm-attack run some-feature --issue 1
swarm-attack init new-feature

# Explicit grouped commands
swarm-attack feature status
swarm-attack bug status
swarm-attack admin diagnose some-feature

# Backwards compatibility
swarm-attack cleanup --all
swarm-attack unlock some-feature --issue 5

# Version
swarm-attack --version
```

---

### Critical Rules

1. **NO CIRCULAR IMPORTS**: common.py and display.py must NOT import from feature/bug/admin
2. **PRESERVE LAZY IMPORTS**: Keep heavy module imports inside functions, not at module level
3. **PRESERVE EXIT CODES**: Commands must exit with same codes (0=success, 1=error, 2=disagreement)
4. **PRESERVE OUTPUT**: Rich Panel/Table output must remain identical
5. **DO NOT MODIFY cli_recovery.py**: It's already well-structured
6. **TYPE HINTS**: Add proper type hints to all new functions
7. **DOCSTRINGS**: Preserve all existing docstrings, they appear in --help

### File Size Targets

| File | Target Lines |
|------|--------------|
| cli/__init__.py | ~20 |
| cli/app.py | ~150 |
| cli/common.py | ~100 |
| cli/display.py | ~250 |
| cli/feature.py | ~900 |
| cli/bug.py | ~550 |
| cli/admin.py | ~450 |

### Testing After Each Phase

After completing each phase:
1. Run `swarm-attack --help`
2. Run `swarm-attack status`
3. Run `pytest tests/ -v` (if tests exist)
4. Verify no import errors with `python -c "from swarm_attack.cli import cli_main"`

---

### Begin Implementation

Start with Phase 1. Read the spec at `/Users/philipjcortes/Desktop/swarm-attack/specs/cli-refactor/spec.md` first, then systematically work through each phase.

For each phase:
1. Announce which phase you're starting
2. Show the code changes
3. Explain what was moved and why
4. Show verification steps

**GO!**

---

## PROMPT END
