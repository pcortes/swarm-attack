"""
State persistence for Bug Bash.

This module handles:
- Saving and loading bug state to .swarm/bugs/{bug_id}/
- Atomic writes with file locking
- State versioning and migration
- Phase transition history logging
- Human-readable markdown reports
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from filelock import FileLock, Timeout
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from swarm_attack.bug_models import (
    BugNotFoundError,
    BugPhase,
    BugState,
    PhaseTransition,
    StateCorruptionError,
)

if TYPE_CHECKING:
    from swarm_attack.logger import SwarmLogger

# State file version for migrations
STATE_VERSION = 1


class BugStateStore:
    """
    Persistent state storage for Bug Bash.

    Handles saving and loading bug investigation state to the file system
    with atomic writes, file locking, and corruption recovery.

    Storage structure:
    .swarm/bugs/{bug_id}/
    ├── state.json              # BugState serialized (source of truth)
    ├── state.json.lock         # Lock file for concurrent access
    ├── report.md               # Human-readable bug report
    ├── reproduction.md         # Reproduction results (written after REPRODUCED)
    ├── root-cause-analysis.md  # Root cause analysis (written after ANALYZED)
    ├── fix-plan.md            # Proposed fix plan (written after PLANNED)
    ├── test-cases.py          # Generated test code (written after PLANNED)
    └── history/
        └── phase_transitions.jsonl  # Append-only transition log
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the bug state store.

        Args:
            base_path: Base path for bug storage. Defaults to .swarm/bugs.
            logger: Optional logger for recording operations.
        """
        self.base_path = base_path or Path(".swarm/bugs")
        self._logger = logger

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "bug_state_store"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _bug_dir(self, bug_id: str) -> Path:
        """Get the directory path for a bug."""
        return self.base_path / bug_id

    def _state_path(self, bug_id: str) -> Path:
        """Get the path to the state file."""
        return self._bug_dir(bug_id) / "state.json"

    def _lock_path(self, bug_id: str) -> Path:
        """Get the path to the lock file."""
        return self._bug_dir(bug_id) / "state.json.lock"

    def _history_dir(self, bug_id: str) -> Path:
        """Get the path to the history directory."""
        return self._bug_dir(bug_id) / "history"

    def _transitions_path(self, bug_id: str) -> Path:
        """Get the path to the phase transitions log."""
        return self._history_dir(bug_id) / "phase_transitions.jsonl"

    def _ensure_directories(self, bug_id: str) -> None:
        """Ensure all directories exist for a bug."""
        bug_dir = self._bug_dir(bug_id)
        bug_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir(bug_id).mkdir(exist_ok=True)

    def _migrate_state(self, data: dict) -> dict:
        """
        Migrate state from older versions.

        Args:
            data: Raw state data from file.

        Returns:
            Migrated state data.
        """
        version = data.get("version", 0)

        if version < 1:
            # Migration from v0 to v1
            if "costs" not in data:
                data["costs"] = []
            if "transitions" not in data:
                data["transitions"] = []
            data["version"] = 1

        return data

    def save(self, state: BugState) -> None:
        """
        Save state to disk atomically with file locking.

        Uses a temp file + rename pattern to prevent corruption.

        Args:
            state: The BugState to save.

        Raises:
            StateCorruptionError: If save fails.
        """
        self._ensure_directories(state.bug_id)

        state_path = self._state_path(state.bug_id)
        lock_path = self._lock_path(state.bug_id)
        temp_path = state_path.with_suffix(".tmp")
        backup_path = state_path.with_suffix(".bak")

        try:
            lock = FileLock(lock_path, timeout=10)
            with lock:
                # Write to temp file first
                data = state.to_dict()
                temp_path.write_text(json.dumps(data, indent=2))

                # Validate temp file by re-reading
                loaded = json.loads(temp_path.read_text())
                BugState.from_dict(loaded)  # Validate schema

                # Backup existing if present
                if state_path.exists():
                    shutil.copy2(state_path, backup_path)

                # Atomic rename
                temp_path.rename(state_path)

                # Remove backup on success
                if backup_path.exists():
                    backup_path.unlink()

                self._log("bug_state_saved", {
                    "bug_id": state.bug_id,
                    "phase": state.phase.value,
                })

        except Timeout:
            self._log("bug_state_save_timeout", {
                "bug_id": state.bug_id,
            }, level="error")
            raise StateCorruptionError(f"Timeout acquiring lock for bug {state.bug_id}")

        except Exception as e:
            # Restore from backup if available
            if backup_path.exists():
                try:
                    shutil.copy2(backup_path, state_path)
                except Exception:
                    pass  # Best effort

            # Clean up temp file
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            self._log("bug_state_save_error", {
                "bug_id": state.bug_id,
                "error": str(e),
            }, level="error")
            raise StateCorruptionError(f"Failed to save state for {state.bug_id}: {e}")

    def load(self, bug_id: str) -> BugState:
        """
        Load state from disk.

        Args:
            bug_id: The bug identifier.

        Returns:
            BugState if state exists and is valid.

        Raises:
            BugNotFoundError: If bug doesn't exist.
            StateCorruptionError: If state is corrupted.
        """
        state_path = self._state_path(bug_id)

        if not state_path.exists():
            raise BugNotFoundError(f"Bug '{bug_id}' not found")

        try:
            content = state_path.read_text()
            data = json.loads(content)

            # Migrate if needed
            data = self._migrate_state(data)

            state = BugState.from_dict(data)
            self._log("bug_state_loaded", {
                "bug_id": bug_id,
                "phase": state.phase.value,
            })
            return state

        except json.JSONDecodeError as e:
            self._log("bug_state_corrupted", {
                "bug_id": bug_id,
                "error": str(e),
            }, level="error")
            raise StateCorruptionError(f"Corrupted state for bug {bug_id}: {e}")

        except (KeyError, ValueError, TypeError) as e:
            self._log("bug_state_invalid", {
                "bug_id": bug_id,
                "error": str(e),
            }, level="error")
            raise StateCorruptionError(f"Invalid state for bug {bug_id}: {e}")

    def exists(self, bug_id: str) -> bool:
        """
        Check if bug exists.

        Args:
            bug_id: The bug identifier.

        Returns:
            True if state file exists.
        """
        return self._state_path(bug_id).exists()

    def list_all(self, phase: Optional[BugPhase] = None) -> list[str]:
        """
        List all bug IDs, optionally filtered by phase.

        Args:
            phase: Optional phase filter.

        Returns:
            List of bug ID strings.
        """
        if not self.base_path.exists():
            return []

        bug_ids = []
        for bug_dir in self.base_path.iterdir():
            if not bug_dir.is_dir():
                continue

            state_path = bug_dir / "state.json"
            if not state_path.exists():
                continue

            bug_id = bug_dir.name

            if phase is not None:
                try:
                    state = self.load(bug_id)
                    if state.phase != phase:
                        continue
                except (BugNotFoundError, StateCorruptionError):
                    continue

            bug_ids.append(bug_id)

        return sorted(bug_ids)

    def delete(self, bug_id: str) -> None:
        """
        Delete a bug investigation.

        Args:
            bug_id: The bug identifier.

        Raises:
            BugNotFoundError: If bug doesn't exist.
        """
        bug_dir = self._bug_dir(bug_id)
        if not bug_dir.exists():
            raise BugNotFoundError(f"Bug '{bug_id}' not found")

        shutil.rmtree(bug_dir)
        self._log("bug_deleted", {"bug_id": bug_id})

    def append_transition(self, bug_id: str, transition: PhaseTransition) -> None:
        """
        Append a phase transition to the history log.

        Args:
            bug_id: The bug identifier.
            transition: The transition to log.
        """
        self._ensure_directories(bug_id)
        transitions_path = self._transitions_path(bug_id)

        with open(transitions_path, "a") as f:
            f.write(json.dumps(transition.to_dict()) + "\n")

    def get_transitions(self, bug_id: str) -> list[PhaseTransition]:
        """
        Get all phase transitions for a bug.

        Args:
            bug_id: The bug identifier.

        Returns:
            List of PhaseTransition objects.
        """
        transitions_path = self._transitions_path(bug_id)
        if not transitions_path.exists():
            return []

        transitions = []
        with open(transitions_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    transitions.append(PhaseTransition.from_dict(data))

        return transitions

    # =========================================================================
    # Human-Readable Report Generation
    # =========================================================================

    def write_report(self, state: BugState) -> None:
        """
        Write human-readable bug report markdown.

        Args:
            state: The bug state to document.
        """
        self._ensure_directories(state.bug_id)
        report_path = self._bug_dir(state.bug_id) / "report.md"

        report = f"""# Bug Report: {state.bug_id}

## Status
- **Phase:** {state.phase.value}
- **Created:** {state.created_at}
- **Updated:** {state.updated_at}
- **Total Cost:** ${state.total_cost_usd:.2f}

## Description
{state.report.description}

"""

        if state.report.test_path:
            report += f"### Test Path\n`{state.report.test_path}`\n\n"

        if state.report.github_issue:
            report += f"### GitHub Issue\n#{state.report.github_issue}\n\n"

        if state.report.error_message:
            report += f"### Error Message\n```\n{state.report.error_message}\n```\n\n"

        if state.report.stack_trace:
            report += f"### Stack Trace\n```\n{state.report.stack_trace}\n```\n\n"

        if state.report.steps_to_reproduce:
            report += "### Steps to Reproduce\n"
            for i, step in enumerate(state.report.steps_to_reproduce, 1):
                report += f"{i}. {step}\n"
            report += "\n"

        report_path.write_text(report)

    def write_reproduction_report(self, state: BugState) -> None:
        """
        Write reproduction results markdown.

        Args:
            state: The bug state with reproduction results.
        """
        if not state.reproduction:
            return

        self._ensure_directories(state.bug_id)
        report_path = self._bug_dir(state.bug_id) / "reproduction.md"

        r = state.reproduction
        status = "CONFIRMED" if r.confirmed else "NOT REPRODUCIBLE"
        report = f"""# Reproduction Results: {state.bug_id}

## Status: {status}
- **Confidence:** {r.confidence}
- **Attempts:** {r.attempts}

## Reproduction Steps
"""
        for i, step in enumerate(r.reproduction_steps, 1):
            report += f"{i}. {step}\n"

        if r.affected_files:
            report += "\n## Affected Files\n"
            for f in r.affected_files:
                report += f"- `{f}`\n"

        if r.error_message:
            report += f"\n## Error Message\n```\n{r.error_message}\n```\n"

        if r.stack_trace:
            report += f"\n## Stack Trace\n```\n{r.stack_trace}\n```\n"

        if r.test_output:
            report += f"\n## Test Output\n```\n{r.test_output}\n```\n"

        if r.related_code_snippets:
            report += "\n## Related Code Snippets\n"
            for path, code in r.related_code_snippets.items():
                report += f"\n### {path}\n```python\n{code}\n```\n"

        if r.environment:
            report += "\n## Environment\n"
            for key, value in r.environment.items():
                report += f"- **{key}:** {value}\n"

        if r.notes:
            report += f"\n## Notes\n{r.notes}\n"

        report_path.write_text(report)

    def write_root_cause_report(self, state: BugState) -> None:
        """
        Write root cause analysis markdown.

        Args:
            state: The bug state with root cause analysis.
        """
        if not state.root_cause:
            return

        self._ensure_directories(state.bug_id)
        report_path = self._bug_dir(state.bug_id) / "root-cause-analysis.md"

        rc = state.root_cause
        report = f"""# Root Cause Analysis: {state.bug_id}

## Summary
{rc.summary}

## Confidence: {rc.confidence}

## Root Cause Location
- **File:** `{rc.root_cause_file}`
"""
        if rc.root_cause_line:
            report += f"- **Line:** {rc.root_cause_line}\n"

        report += f"""
## Root Cause Code
```python
{rc.root_cause_code}
```

## Explanation
{rc.root_cause_explanation}

## Why Tests Didn't Catch It
{rc.why_not_caught}

## Execution Trace
"""
        for i, step in enumerate(rc.execution_trace, 1):
            report += f"{i}. {step}\n"

        if rc.alternative_hypotheses:
            report += "\n## Alternative Hypotheses Considered\n"
            for hyp in rc.alternative_hypotheses:
                report += f"- {hyp}\n"

        report_path.write_text(report)

    def write_fix_plan_report(self, state: BugState) -> None:
        """
        Write fix plan markdown.

        Args:
            state: The bug state with fix plan.
        """
        if not state.fix_plan:
            return

        self._ensure_directories(state.bug_id)
        report_path = self._bug_dir(state.bug_id) / "fix-plan.md"

        fp = state.fix_plan
        report = f"""# Fix Plan: {state.bug_id}

## Summary
{fp.summary}

## Risk Assessment
- **Risk Level:** {fp.risk_level.upper()}
- **Scope:** {fp.scope}

### Risk Explanation
{fp.risk_explanation}

## Proposed Changes

"""
        for i, change in enumerate(fp.changes, 1):
            report += f"### Change {i}: {change.file_path}\n"
            report += f"- **Type:** {change.change_type}\n"
            report += f"- **Explanation:** {change.explanation}\n"

            if change.current_code:
                report += f"\n**Current Code:**\n```python\n{change.current_code}\n```\n"
            if change.proposed_code:
                report += f"\n**Proposed Code:**\n```python\n{change.proposed_code}\n```\n"
            report += "\n"

        report += "## Test Cases\n\n"
        for i, test in enumerate(fp.test_cases, 1):
            report += f"### Test {i}: {test.name}\n"
            report += f"- **Category:** {test.category}\n"
            report += f"- **Description:** {test.description}\n"
            report += f"\n```python\n{test.test_code}\n```\n\n"

        if fp.side_effects:
            report += "## Potential Side Effects\n"
            for effect in fp.side_effects:
                report += f"- {effect}\n"
            report += "\n"

        report += f"## Rollback Plan\n{fp.rollback_plan}\n\n"

        if fp.estimated_effort:
            report += f"## Estimated Effort\n{fp.estimated_effort}\n"

        report_path.write_text(report)

        # Also write test cases as Python file
        self._write_test_cases(state)

    def _write_test_cases(self, state: BugState) -> None:
        """Write generated test cases to a Python file."""
        if not state.fix_plan or not state.fix_plan.test_cases:
            return

        test_path = self._bug_dir(state.bug_id) / "test-cases.py"

        test_code = f'''"""
Generated test cases for bug: {state.bug_id}

These tests verify the fix for the identified bug.
"""

import pytest


'''
        for test in state.fix_plan.test_cases:
            test_code += f"# {test.description}\n"
            test_code += f"{test.test_code}\n\n"

        test_path.write_text(test_code)


# Module-level singleton for convenience
_store_cache: dict[str, BugStateStore] = {}


def get_bug_store(
    base_path: Optional[Path] = None,
    logger: Optional[SwarmLogger] = None,
) -> BugStateStore:
    """
    Get a BugStateStore instance.

    Uses a simple cache keyed by base_path.

    Args:
        base_path: Base path for bug storage.
        logger: Optional logger for recording operations.

    Returns:
        BugStateStore instance.
    """
    key = str(base_path or ".swarm/bugs")
    if key not in _store_cache:
        _store_cache[key] = BugStateStore(
            base_path=Path(base_path) if base_path else None,
            logger=logger,
        )
    return _store_cache[key]


def clear_bug_store_cache() -> None:
    """Clear the store cache. Useful for testing."""
    global _store_cache
    _store_cache = {}
