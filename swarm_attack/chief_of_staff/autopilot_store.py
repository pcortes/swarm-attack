"""AutopilotSessionStore for persisting autopilot sessions for pause/resume."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .autopilot import AutopilotSession


class AutopilotSessionStore:
    """Persists autopilot sessions for pause/resume capability.
    
    Storage path: .swarm/chief-of-staff/autopilot/
    Session files: {session_id}.json
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize with storage path.
        
        Args:
            base_path: Base storage path (.swarm/chief-of-staff/)
        """
        self.base_path = base_path / "autopilot"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            Path to the session JSON file.
        """
        return self.base_path / f"{session_id}.json"

    def save(self, session: AutopilotSession) -> None:
        """Save autopilot session to disk atomically.
        
        Uses atomic write pattern:
        1. Write to temp file
        2. Validate by re-reading
        3. Backup existing file
        4. Atomic rename
        5. Set last_persisted_at
        
        Args:
            session: AutopilotSession to save.
            
        Raises:
            Exception: If validation fails or write fails.
        """
        # Set persistence timestamp
        session.last_persisted_at = datetime.now().isoformat()
        
        path = self._session_path(session.session_id)
        temp_path = path.with_suffix(".tmp")
        backup_path = path.with_suffix(".bak")
        
        try:
            # Write to temp file
            temp_path.write_text(json.dumps(session.to_dict(), indent=2))
            
            # Validate by re-reading
            validation_data = json.loads(temp_path.read_text())
            AutopilotSession.from_dict(validation_data)
            
            # Backup existing file if present
            if path.exists():
                shutil.copy2(path, backup_path)
            
            # Atomic rename
            temp_path.rename(path)
            
            # Remove backup after successful rename
            if backup_path.exists():
                backup_path.unlink()
                
        except Exception as e:
            # Restore from backup if available
            if backup_path.exists():
                shutil.copy2(backup_path, path)
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self, session_id: str) -> Optional[AutopilotSession]:
        """Load autopilot session from disk.
        
        Args:
            session_id: Session identifier to load.
            
        Returns:
            AutopilotSession if found and valid, None otherwise.
        """
        path = self._session_path(session_id)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text())
            return AutopilotSession.from_dict(data)
        except Exception:
            return None

    def list_paused(self) -> list[str]:
        """List all paused session IDs.
        
        Returns:
            List of session IDs with status "paused".
        """
        paused = []
        for path in self.base_path.glob("*.json"):
            session = self.load(path.stem)
            if session and session.status == "paused":
                paused.append(session.session_id)
        return paused

    def list_all(self) -> list[str]:
        """List all session IDs.
        
        Returns:
            List of all session IDs.
        """
        return [path.stem for path in self.base_path.glob("*.json")]

    def delete(self, session_id: str) -> None:
        """Delete a session file.
        
        Args:
            session_id: Session identifier to delete.
        """
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def get_latest_paused(self) -> Optional[AutopilotSession]:
        """Get the most recently paused session.
        
        Returns:
            Most recently paused AutopilotSession, or None if no paused sessions.
        """
        paused_sessions = []
        
        for session_id in self.list_paused():
            session = self.load(session_id)
            if session:
                paused_sessions.append(session)
        
        if not paused_sessions:
            return None
        
        # Sort by last_persisted_at (most recent first)
        def get_timestamp(s: AutopilotSession) -> str:
            return s.last_persisted_at or ""
        
        paused_sessions.sort(key=get_timestamp, reverse=True)
        return paused_sessions[0]