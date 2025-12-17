"""
State persistence for Feature Swarm.

This module handles:
- Saving and loading feature state to .swarm/state/<feature>.json
- Atomic writes to prevent corruption
- Graceful handling of missing or corrupted state files
- Session state persistence to .swarm/sessions/<feature>/<session_id>.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from swarm_attack.models import (
    FeaturePhase,
    IssueOutput,
    RunState,
    SessionState,
    TaskStage,
    model_to_json,
)
from swarm_attack.utils.fs import (
    FileSystemError,
    ensure_dir,
    file_exists,
    list_files,
    read_file,
    safe_write,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class StateStoreError(Exception):
    """Raised when state store operations fail."""
    pass


class StateStore:
    """
    Persistent state storage for Feature Swarm.

    Handles saving and loading feature state to the file system with
    atomic writes and corruption handling.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None
    ) -> None:
        """
        Initialize the state store.

        Args:
            config: SwarmConfig with paths configured.
            logger: Optional logger for recording operations.
        """
        self._config = config
        self._logger = logger
        self._state_dir = config.state_path
        self._sessions_dir = config.sessions_path

    def _ensure_directories(self) -> None:
        """Ensure state and session directories exist."""
        ensure_dir(self._state_dir)
        ensure_dir(self._sessions_dir)

    def _get_state_path(self, feature_id: str) -> Path:
        """Get path to feature state file."""
        return self._state_dir / f"{feature_id}.json"

    def _get_session_dir(self, feature_id: str) -> Path:
        """Get path to feature session directory."""
        return self._sessions_dir / feature_id

    def _get_session_path(self, feature_id: str, session_id: str) -> Path:
        """Get path to session state file."""
        return self._get_session_dir(feature_id) / f"{session_id}.json"

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            self._logger.log(event_type, data, level=level)

    # Feature State Operations

    def load(self, feature_id: str) -> Optional[RunState]:
        """
        Load feature state from disk.

        Args:
            feature_id: The feature identifier.

        Returns:
            RunState if state exists and is valid, None otherwise.
        """
        state_path = self._get_state_path(feature_id)

        if not file_exists(state_path):
            self._log("state_load_miss", {"feature_id": feature_id}, level="debug")
            return None

        try:
            content = read_file(state_path)
            data = json.loads(content)
            state = RunState.from_dict(data)
            self._log("state_loaded", {
                "feature_id": feature_id,
                "phase": state.phase.name
            })
            return state

        except json.JSONDecodeError as e:
            self._log("state_corrupted", {
                "feature_id": feature_id,
                "error": str(e),
                "path": str(state_path)
            }, level="error")
            return None

        except (KeyError, ValueError, TypeError) as e:
            self._log("state_invalid", {
                "feature_id": feature_id,
                "error": str(e),
                "path": str(state_path)
            }, level="error")
            return None

        except FileSystemError as e:
            self._log("state_read_error", {
                "feature_id": feature_id,
                "error": str(e)
            }, level="error")
            return None

    def save(self, state: RunState) -> None:
        """
        Save feature state to disk atomically.

        Args:
            state: The RunState to save.

        Raises:
            StateStoreError: If save fails.
        """
        self._ensure_directories()
        state_path = self._get_state_path(state.feature_id)

        try:
            content = model_to_json(state.to_dict(), indent=2)
            safe_write(state_path, content)
            self._log("state_saved", {
                "feature_id": state.feature_id,
                "phase": state.phase.name
            })

        except FileSystemError as e:
            self._log("state_save_error", {
                "feature_id": state.feature_id,
                "error": str(e)
            }, level="error")
            raise StateStoreError(f"Failed to save state for {state.feature_id}: {e}")

    def delete(self, feature_id: str) -> bool:
        """
        Delete feature state from disk.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if state was deleted, False if it didn't exist.
        """
        state_path = self._get_state_path(feature_id)

        if not file_exists(state_path):
            return False

        try:
            state_path.unlink()
            self._log("state_deleted", {"feature_id": feature_id})
            return True
        except OSError as e:
            self._log("state_delete_error", {
                "feature_id": feature_id,
                "error": str(e)
            }, level="error")
            raise StateStoreError(f"Failed to delete state for {feature_id}: {e}")

    def list_features(self) -> list[str]:
        """
        List all feature IDs with saved state.

        Returns:
            List of feature ID strings.
        """
        self._ensure_directories()

        try:
            state_files = list_files(self._state_dir, "*.json")
            return [f.stem for f in state_files]
        except FileSystemError:
            return []

    def create_feature(
        self,
        feature_id: str,
        phase: FeaturePhase = FeaturePhase.NO_PRD
    ) -> RunState:
        """
        Create a new feature with initial state.

        Args:
            feature_id: The feature identifier (slug).
            phase: Initial phase. Defaults to NO_PRD.

        Returns:
            The created RunState.

        Raises:
            StateStoreError: If feature already exists or creation fails.
        """
        if self.load(feature_id) is not None:
            raise StateStoreError(f"Feature '{feature_id}' already exists")

        state = RunState(
            feature_id=feature_id,
            phase=phase
        )

        self.save(state)
        self._log("feature_created", {
            "feature_id": feature_id,
            "phase": phase.name
        })

        return state

    def update_phase(
        self,
        feature_id: str,
        new_phase: FeaturePhase
    ) -> RunState:
        """
        Update the phase of a feature.

        Args:
            feature_id: The feature identifier.
            new_phase: The new phase.

        Returns:
            The updated RunState.

        Raises:
            StateStoreError: If feature doesn't exist.
        """
        state = self.load(feature_id)
        if state is None:
            raise StateStoreError(f"Feature '{feature_id}' not found")

        old_phase = state.phase
        state.update_phase(new_phase)
        self.save(state)

        self._log("phase_updated", {
            "feature_id": feature_id,
            "old_phase": old_phase.name,
            "new_phase": new_phase.name
        })

        return state

    def exists(self, feature_id: str) -> bool:
        """
        Check if a feature state exists.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if state file exists.
        """
        return file_exists(self._get_state_path(feature_id))

    # Session State Operations

    def load_session(
        self,
        feature_id: str,
        session_id: str
    ) -> Optional[SessionState]:
        """
        Load session state from disk.

        Args:
            feature_id: The feature identifier.
            session_id: The session identifier.

        Returns:
            SessionState if exists and valid, None otherwise.
        """
        session_path = self._get_session_path(feature_id, session_id)

        if not file_exists(session_path):
            return None

        try:
            content = read_file(session_path)
            data = json.loads(content)
            return SessionState.from_dict(data)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            self._log("session_load_error", {
                "feature_id": feature_id,
                "session_id": session_id,
                "error": str(e)
            }, level="error")
            return None

        except FileSystemError as e:
            self._log("session_read_error", {
                "feature_id": feature_id,
                "session_id": session_id,
                "error": str(e)
            }, level="error")
            return None

    def save_session(self, session: SessionState) -> None:
        """
        Save session state to disk atomically.

        Args:
            session: The SessionState to save.

        Raises:
            StateStoreError: If save fails.
        """
        session_dir = self._get_session_dir(session.feature_id)
        ensure_dir(session_dir)

        session_path = self._get_session_path(
            session.feature_id,
            session.session_id
        )

        try:
            content = model_to_json(session.to_dict(), indent=2)
            safe_write(session_path, content)
            self._log("session_saved", {
                "feature_id": session.feature_id,
                "session_id": session.session_id,
                "status": session.status
            })

        except FileSystemError as e:
            self._log("session_save_error", {
                "feature_id": session.feature_id,
                "session_id": session.session_id,
                "error": str(e)
            }, level="error")
            raise StateStoreError(
                f"Failed to save session {session.session_id}: {e}"
            )

    def list_sessions(self, feature_id: str) -> list[str]:
        """
        List all session IDs for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of session ID strings.
        """
        session_dir = self._get_session_dir(feature_id)

        if not session_dir.exists():
            return []

        try:
            session_files = list_files(session_dir, "*.json")
            return [f.stem for f in session_files]
        except FileSystemError:
            return []

    def get_latest_session(
        self,
        feature_id: str
    ) -> Optional[SessionState]:
        """
        Get the most recent session for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            Most recent SessionState or None if no sessions exist.
        """
        session_ids = self.list_sessions(feature_id)
        if not session_ids:
            return None

        # Load all sessions and find the one with latest started_at
        latest: Optional[SessionState] = None
        for sid in session_ids:
            session = self.load_session(feature_id, sid)
            if session is None:
                continue
            if latest is None or session.started_at > latest.started_at:
                latest = session

        return latest

    def get_active_session(
        self,
        feature_id: str
    ) -> Optional[SessionState]:
        """
        Get the active (non-ended) session for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            Active SessionState or None if no active session.
        """
        session_ids = self.list_sessions(feature_id)

        for sid in session_ids:
            session = self.load_session(feature_id, sid)
            if session is not None and session.status == "active":
                return session

        return None

    # Issue Output and Module Registry Operations

    def save_issue_outputs(
        self,
        feature_id: str,
        issue_number: int,
        outputs: IssueOutput
    ) -> None:
        """
        Save outputs from a completed issue to state.

        Updates the task's outputs field with files/classes created.
        This enables context handoff to subsequent issues.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue that created these outputs.
            outputs: IssueOutput with files_created and classes_defined.

        Raises:
            StateStoreError: If feature doesn't exist.
        """
        state = self.load(feature_id)
        if state is None:
            raise StateStoreError(f"Feature '{feature_id}' not found")

        # Find the task and update its outputs
        for task in state.tasks:
            if task.issue_number == issue_number:
                task.outputs = outputs
                break

        self.save(state)
        self._log("issue_outputs_saved", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "files_created": len(outputs.files_created),
            "classes_defined": sum(len(v) for v in outputs.classes_defined.values()),
        })

    def get_module_registry(self, feature_id: str) -> dict[str, any]:
        """
        Build module registry from all completed issues.

        Creates a map of files and classes created by prior issues,
        enabling context handoff to subsequent issues.

        Args:
            feature_id: The feature identifier.

        Returns:
            Dict with structure:
            {
                "feature_id": "...",
                "modules": {
                    "path/to/file.py": {
                        "created_by_issue": 1,
                        "classes": ["ClassName", ...]
                    },
                    ...
                }
            }
        """
        state = self.load(feature_id)
        if state is None:
            return {"feature_id": feature_id, "modules": {}}

        registry: dict[str, any] = {
            "feature_id": feature_id,
            "modules": {}
        }

        for task in state.tasks:
            # Only include outputs from DONE tasks
            if task.stage == TaskStage.DONE and task.outputs:
                for file_path in task.outputs.files_created:
                    registry["modules"][file_path] = {
                        "created_by_issue": task.issue_number,
                        "classes": task.outputs.classes_defined.get(file_path, []),
                    }

        return registry


# Module-level singleton for convenience
_store_cache: dict[str, StateStore] = {}


def get_store(
    config: SwarmConfig,
    logger: Optional[SwarmLogger] = None
) -> StateStore:
    """
    Get a StateStore instance for the given config.

    Uses a simple cache keyed by repo_root.

    Args:
        config: SwarmConfig with paths configured.
        logger: Optional logger for recording operations.

    Returns:
        StateStore instance.
    """
    key = config.repo_root
    if key not in _store_cache:
        _store_cache[key] = StateStore(config, logger)
    return _store_cache[key]


def clear_store_cache() -> None:
    """Clear the store cache. Useful for testing."""
    global _store_cache
    _store_cache = {}
