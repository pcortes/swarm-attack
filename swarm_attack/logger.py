"""
Structured JSONL logging for Feature Swarm.

This module provides:
- JSONL event logging for debugging and audit trails
- Log files organized by feature and date
- Log levels (debug, info, warn, error)
- Context manager for session-scoped logging
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from swarm_attack.config import get_config, SwarmConfig


class LogLevel:
    """Log level constants."""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class SwarmLogger:
    """
    JSONL event logger for Feature Swarm.

    Writes structured log entries to .swarm/logs/<feature>-YYYY-MM-DD.jsonl

    Each log entry is a JSON object with:
    - timestamp: ISO format timestamp
    - level: Log level (debug, info, warn, error)
    - event_type: Type of event being logged
    - feature_id: Feature identifier
    - data: Additional event data (dict)
    """

    def __init__(self, feature_id: str, config: Optional[SwarmConfig] = None) -> None:
        """
        Initialize logger for a feature.

        Args:
            feature_id: The feature identifier for organizing logs.
            config: Optional config to use. If not provided, loads from config.yaml.
        """
        self.feature_id = feature_id
        self._config = config
        self._current_session_id: Optional[str] = None
        self._file_handle: Optional[Any] = None

    @property
    def config(self) -> SwarmConfig:
        """Get configuration (lazy load)."""
        if self._config is None:
            self._config = get_config()
        return self._config

    def _get_log_path(self) -> Path:
        """Get the log file path for today."""
        logs_dir = self.config.logs_path
        logs_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return logs_dir / f"{self.feature_id}-{today}.jsonl"

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a log entry to the JSONL file."""
        log_path = self._get_log_path()

        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to log file
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log(
        self,
        event_type: str,
        data: Optional[dict[str, Any]] = None,
        level: str = LogLevel.INFO,
    ) -> None:
        """
        Log an event.

        Args:
            event_type: Type of event (e.g., "agent_start", "checkpoint", "error").
            data: Additional data to include in the log entry.
            level: Log level (debug, info, warn, error).
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "event_type": event_type,
            "feature_id": self.feature_id,
            "data": data or {},
        }

        if self._current_session_id:
            entry["session_id"] = self._current_session_id

        self._write_entry(entry)

    def debug(self, event_type: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log a debug event."""
        self.log(event_type, data, LogLevel.DEBUG)

    def info(self, event_type: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log an info event."""
        self.log(event_type, data, LogLevel.INFO)

    def warn(self, event_type: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log a warning event."""
        self.log(event_type, data, LogLevel.WARN)

    def error(self, event_type: str, data: Optional[dict[str, Any]] = None) -> None:
        """Log an error event."""
        self.log(event_type, data, LogLevel.ERROR)

    @contextmanager
    def session_context(self, session_id: str) -> Iterator[SwarmLogger]:
        """
        Context manager for session-scoped logging.

        All logs within this context will include the session_id.

        Args:
            session_id: The session identifier.

        Yields:
            Self for chaining.

        Example:
            with logger.session_context("sess_001") as log:
                log.info("checkpoint", {"agent": "test_writer"})
        """
        old_session_id = self._current_session_id
        self._current_session_id = session_id
        self.info("session_start", {"session_id": session_id})
        try:
            yield self
        finally:
            self.info("session_end", {"session_id": session_id})
            self._current_session_id = old_session_id

    def read_logs(
        self,
        date: Optional[str] = None,
        level: Optional[str] = None,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Read log entries with optional filtering.

        Args:
            date: Date string (YYYY-MM-DD) to read. If None, reads today's logs.
            level: Filter by log level.
            event_type: Filter by event type.
            session_id: Filter by session ID.
            limit: Maximum number of entries to return.

        Returns:
            List of log entries matching the filters.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        log_path = self.config.logs_path / f"{self.feature_id}-{date}.jsonl"
        if not log_path.exists():
            return []

        entries = []
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Apply filters
                if level and entry.get("level") != level:
                    continue
                if event_type and entry.get("event_type") != event_type:
                    continue
                if session_id and entry.get("session_id") != session_id:
                    continue

                entries.append(entry)

                if limit and len(entries) >= limit:
                    break

        return entries

    def get_log_files(self) -> list[Path]:
        """
        Get all log files for this feature.

        Returns:
            List of log file paths, sorted by date (newest first).
        """
        logs_dir = self.config.logs_path
        if not logs_dir.exists():
            return []

        pattern = f"{self.feature_id}-*.jsonl"
        files = list(logs_dir.glob(pattern))
        files.sort(reverse=True)
        return files


# Module-level logger cache
_logger_cache: dict[str, SwarmLogger] = {}


def get_logger(feature_id: str, config: Optional[SwarmConfig] = None) -> SwarmLogger:
    """
    Get or create a logger for a feature.

    Args:
        feature_id: The feature identifier.
        config: Optional config to use.

    Returns:
        SwarmLogger instance for the feature.
    """
    if feature_id not in _logger_cache:
        _logger_cache[feature_id] = SwarmLogger(feature_id, config)
    return _logger_cache[feature_id]


def clear_logger_cache() -> None:
    """Clear the logger cache. Useful for testing."""
    global _logger_cache
    _logger_cache = {}
