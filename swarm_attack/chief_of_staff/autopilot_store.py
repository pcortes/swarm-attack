"""AutopilotSessionStore for persisting autopilot sessions."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState


class AutopilotSessionStore:
    """Persists autopilot session state to enable pause/resume functionality."""
    
    def __init__(self, base_path: Path) -> None:
        """Initialize storage in .swarm/chief-of-staff/autopilot/.
        
        Args:
            base_path: Base path for the project (typically project root).
        """
        self._storage_path = base_path / ".swarm" / "chief-of-staff" / "autopilot"
        self._storage_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def storage_path(self) -> Path:
        """Return the storage directory path."""
        return self._storage_path
    
    def save(self, session: AutopilotSession) -> None:
        """Save session atomically with validation.
        
        Uses temp file -> validate -> rename pattern for atomic writes.
        Sets last_persisted_at timestamp on the session.
        
        Args:
            session: The autopilot session to save.
        """
        # Set persistence timestamp
        session.last_persisted_at = datetime.now(timezone.utc)
        
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
                AutopilotSession.from_dict(parsed)
            
            # Atomic rename
            os.replace(temp_path, target_file)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def load(self, session_id: str) -> Optional[AutopilotSession]:
        """Load session from disk.
        
        Args:
            session_id: The session ID to load.
            
        Returns:
            The loaded AutopilotSession, or None if not found or corrupted.
        """
        session_file = self._storage_path / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            
            # Validate required fields exist
            if "session_id" not in data or "feature_id" not in data:
                return None
            
            return AutopilotSession.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
    
    def list_paused(self) -> list[str]:
        """Return IDs of all paused sessions.
        
        Returns:
            List of session IDs with state == PAUSED.
        """
        paused_ids = []
        
        for session_file in self._storage_path.glob("*.json"):
            session_id = session_file.stem
            session = self.load(session_id)
            
            if session is not None and session.state == AutopilotState.PAUSED:
                paused_ids.append(session_id)
        
        return paused_ids
    
    def list_all(self) -> list[str]:
        """Return all session IDs.

        Returns:
            List of all session IDs (file stems of JSON files).
        """
        return [f.stem for f in self._storage_path.glob("*.json")]

    def list_sessions(self) -> list[AutopilotSession]:
        """Return all sessions as AutopilotSession objects.

        Returns:
            List of all AutopilotSession objects.
        """
        sessions = []
        for session_id in self.list_all():
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
    
    def get_latest_paused(self) -> Optional[AutopilotSession]:
        """Return most recent paused session.
        
        Returns:
            The most recently persisted paused session, or None if none exist.
        """
        paused_sessions = []
        
        for session_id in self.list_paused():
            session = self.load(session_id)
            if session is not None:
                paused_sessions.append(session)
        
        if not paused_sessions:
            return None
        
        # Sort by last_persisted_at, most recent first
        paused_sessions.sort(
            key=lambda s: s.last_persisted_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        
        return paused_sessions[0]