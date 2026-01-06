"""QASessionStore for persisting QA sessions.

Provides storage and retrieval of QA session state for the CLI commands.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from swarm_attack.qa.models import QASession


class QASessionStore:
    """Persists QA session state to enable reporting and historical analysis."""

    def __init__(self, base_path: Path) -> None:
        """Initialize storage in .swarm/qa/sessions/.

        Args:
            base_path: Base path for the project (typically project root).
        """
        if isinstance(base_path, str):
            base_path = Path(base_path)
        self._storage_path = base_path / ".swarm" / "qa" / "sessions"
        self._storage_path.mkdir(parents=True, exist_ok=True)

    @property
    def storage_path(self) -> Path:
        """Return the storage directory path."""
        return self._storage_path

    def save(self, session: QASession) -> None:
        """Save session atomically with validation.

        Uses temp file -> validate -> rename pattern for atomic writes.

        Args:
            session: The QA session to save.
        """
        # Convert to JSON
        data = session.to_dict()
        json_content = json.dumps(data, indent=2)

        # Write to temp file first
        target_file = self._storage_path / f"{session.session_id}.json"
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            dir=self._storage_path,
        )

        try:
            # Write content
            with os.fdopen(fd, "w") as f:
                f.write(json_content)

            # Validate by re-parsing
            with open(temp_path, "r") as f:
                parsed = json.load(f)
                # Validate we can reconstruct the session
                QASession.from_dict(parsed)

            # Atomic rename
            os.replace(temp_path, target_file)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def load(self, session_id: str) -> Optional[QASession]:
        """Load session from disk.

        Args:
            session_id: The session ID to load.

        Returns:
            The loaded QASession, or None if not found or corrupted.
        """
        session_file = self._storage_path / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, "r") as f:
                data = json.load(f)

            # Validate required fields exist
            if "session_id" not in data:
                return None

            return QASession.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def list_sessions(self) -> list[str]:
        """Return all session IDs.

        Returns:
            List of all session IDs (file stems of JSON files).
        """
        return [f.stem for f in self._storage_path.glob("*.json")]

    def list_all(self) -> list[QASession]:
        """Return all sessions as QASession objects.

        Returns:
            List of all QASession objects.
        """
        sessions = []
        for session_id in self.list_sessions():
            session = self.load(session_id)
            if session is not None:
                sessions.append(session)
        return sessions

    def delete(self, session_id: str) -> None:
        """Remove session file.

        Args:
            session_id: The session ID to delete.
        """
        session_file = self._storage_path / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
