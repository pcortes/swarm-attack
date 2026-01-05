"""
Command History - Logging module for tracking executed commands.

This module provides:
- Command logging with timestamps, outcomes, and reasoning
- Git commit SHA linking
- Search by date, command type, or outcome
- Secret redaction in logged commands

Storage is in .swarm/history/ as JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


# Patterns for secret detection
SECRET_PATTERNS = [
    # API keys with prefixes
    (r"sk[_-]live[_-][A-Za-z0-9]{20,}", "[REDACTED]"),
    (r"sk[_-]test[_-][A-Za-z0-9]{20,}", "[REDACTED]"),
    (r"sk[_-][A-Za-z0-9]{30,}", "[REDACTED]"),
    # AWS keys
    (r"AKIA[A-Z0-9]{16}", "[REDACTED]"),
    (r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)['\"]?\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})", "[REDACTED]"),
    # GitHub tokens
    (r"ghp_[A-Za-z0-9]{36}", "[REDACTED]"),
    (r"gho_[A-Za-z0-9]{36}", "[REDACTED]"),
    (r"ghu_[A-Za-z0-9]{36}", "[REDACTED]"),
    (r"ghs_[A-Za-z0-9]{36}", "[REDACTED]"),
    # JWT tokens (three base64 sections separated by dots)
    (r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+", "[REDACTED]"),
    # Private keys
    (r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----", "[REDACTED]"),
    # Passwords in connection strings (postgres://user:password@host)
    (r"((?:postgres|mysql|mongodb|redis):\/\/[^:]+:)([^@]+)(@)", r"\1[REDACTED]\3"),
    # Password flags (-p'password' or -p"password")
    (r"-p['\"]([^'\"]+)['\"]", "-p'[REDACTED]'"),
    # Generic bearer tokens with long values
    (r"(Bearer\s+)[A-Za-z0-9._-]{30,}", r"\1[REDACTED]"),
    # Generic long secrets in --token= or similar
    (r"(--token[=\s]+)[A-Za-z0-9._-]{30,}", r"\1[REDACTED]"),
    # Environment variable assignments with secrets
    (r"((?:OPENAI_API_KEY|API_KEY|SECRET_KEY|ACCESS_KEY)['\"]?\s*[=:]\s*['\"]?)([A-Za-z0-9._/-]{20,})", r"\1[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """Redact secrets from a string using known patterns."""
    if not text:
        return text

    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result)

    return result


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact secrets from a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = redact_secrets(value)
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, list):
            result[key] = [
                redact_secrets(v) if isinstance(v, str)
                else redact_dict(v) if isinstance(v, dict)
                else v
                for v in value
            ]
        else:
            result[key] = value
    return result


@dataclass
class CommandEntry:
    """
    A single command entry in the history.

    Attributes:
        id: Unique identifier for this command entry
        command: The command that was executed (redacted)
        command_type: Category of command (git, test, build, etc.)
        timestamp: ISO format timestamp when command was logged
        outcome: Result of the command (success, failure, error)
        reasoning: Optional explanation of why this command was run
        git_sha: Optional git commit SHA this command is linked to
        feature_id: Optional feature ID this command is associated with
        metadata: Additional structured data about the command
    """
    id: str
    command: str
    command_type: str
    timestamp: str
    outcome: str
    reasoning: Optional[str] = None
    git_sha: Optional[str] = None
    feature_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandEntry:
        """Create from dictionary."""
        return cls(**data)


class CommandHistory:
    """
    Command history manager for logging and searching commands.

    Provides persistent storage of command history with secret redaction,
    search capabilities, and git commit linking.
    """

    def __init__(self, store_path: Optional[Path] = None):
        """
        Initialize a CommandHistory instance.

        Args:
            store_path: Path to the JSON store file. Defaults to .swarm/history/command_history.json
        """
        self._store_path = store_path or Path(".swarm/history/command_history.json")
        self._entries: dict[str, CommandEntry] = {}

    @classmethod
    def load(cls, store_path: Optional[Path] = None) -> CommandHistory:
        """
        Load command history from disk.

        Args:
            store_path: Path to the JSON store file.

        Returns:
            CommandHistory instance with loaded data.
        """
        history = cls(store_path=store_path)

        if history._store_path.exists():
            try:
                with open(history._store_path, "r") as f:
                    data = json.load(f)
                    for entry_data in data.get("entries", []):
                        entry = CommandEntry.from_dict(entry_data)
                        history._entries[entry.id] = entry
            except (json.JSONDecodeError, KeyError, TypeError):
                # Corrupted file - start fresh
                history._entries = {}

        return history

    def save(self) -> None:
        """Save command history to disk."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "entries": [entry.to_dict() for entry in self._entries.values()]
        }

        with open(self._store_path, "w") as f:
            json.dump(data, f, indent=2)

    def log(
        self,
        command: str,
        command_type: str,
        outcome: str,
        reasoning: Optional[str] = None,
        git_sha: Optional[str] = None,
        feature_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> str:
        """
        Log a command to history.

        Args:
            command: The command that was executed
            command_type: Category of command (git, test, build, etc.)
            outcome: Result of the command (success, failure, error)
            reasoning: Optional explanation of why this command was run
            git_sha: Optional git commit SHA this command is linked to
            feature_id: Optional feature ID this command is associated with
            metadata: Additional structured data about the command
            timestamp: Optional ISO timestamp (auto-generated if not provided)

        Returns:
            The unique ID of the logged entry.
        """
        entry_id = str(uuid4())

        # Generate timestamp if not provided
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        # Redact secrets
        redacted_command = redact_secrets(command)
        redacted_reasoning = redact_secrets(reasoning) if reasoning else None
        redacted_metadata = redact_dict(metadata) if metadata else {}

        entry = CommandEntry(
            id=entry_id,
            command=redacted_command,
            command_type=command_type,
            timestamp=timestamp,
            outcome=outcome,
            reasoning=redacted_reasoning,
            git_sha=git_sha,
            feature_id=feature_id,
            metadata=redacted_metadata,
        )

        self._entries[entry_id] = entry
        return entry_id

    def get(self, entry_id: str) -> Optional[CommandEntry]:
        """
        Get a command entry by ID.

        Args:
            entry_id: The unique ID of the entry.

        Returns:
            The CommandEntry if found, None otherwise.
        """
        return self._entries.get(entry_id)

    def link_to_commit(self, entry_id: str, git_sha: str) -> None:
        """
        Link a command entry to a git commit SHA.

        Args:
            entry_id: The unique ID of the entry.
            git_sha: The git commit SHA to link to.

        Raises:
            KeyError: If the entry ID is not found.
        """
        if entry_id not in self._entries:
            raise KeyError(f"Entry not found: {entry_id}")

        entry = self._entries[entry_id]
        # Create a new entry with updated git_sha
        self._entries[entry_id] = CommandEntry(
            id=entry.id,
            command=entry.command,
            command_type=entry.command_type,
            timestamp=entry.timestamp,
            outcome=entry.outcome,
            reasoning=entry.reasoning,
            git_sha=git_sha,
            feature_id=entry.feature_id,
            metadata=entry.metadata,
        )

    def search(
        self,
        command_type: Optional[str] = None,
        outcome: Optional[str] = None,
        git_sha: Optional[str] = None,
        git_sha_prefix: Optional[str] = None,
        feature_id: Optional[str] = None,
        command_contains: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[CommandEntry]:
        """
        Search command history with various filters.

        Args:
            command_type: Filter by command type.
            outcome: Filter by outcome (success, failure, error).
            git_sha: Filter by exact git SHA.
            git_sha_prefix: Filter by git SHA prefix.
            feature_id: Filter by feature ID.
            command_contains: Filter by command text substring.
            start_date: Filter by start date (ISO format).
            end_date: Filter by end date (ISO format).
            date: Filter by single date (YYYY-MM-DD format).
            limit: Maximum number of results to return.

        Returns:
            List of matching CommandEntry objects, newest first.
        """
        results = []

        for entry in self._entries.values():
            # Filter by command type
            if command_type is not None and entry.command_type != command_type:
                continue

            # Filter by outcome
            if outcome is not None and entry.outcome != outcome:
                continue

            # Filter by exact git SHA
            if git_sha is not None and entry.git_sha != git_sha:
                continue

            # Filter by git SHA prefix
            if git_sha_prefix is not None:
                if entry.git_sha is None or not entry.git_sha.startswith(git_sha_prefix):
                    continue

            # Filter by feature ID
            if feature_id is not None and entry.feature_id != feature_id:
                continue

            # Filter by command text
            if command_contains is not None and command_contains not in entry.command:
                continue

            # Filter by date range
            if start_date is not None or end_date is not None:
                entry_ts = self._parse_timestamp(entry.timestamp)
                if start_date is not None:
                    start_ts = self._parse_timestamp(start_date)
                    if entry_ts < start_ts:
                        continue
                if end_date is not None:
                    end_ts = self._parse_timestamp(end_date)
                    if entry_ts > end_ts:
                        continue

            # Filter by single date
            if date is not None:
                entry_date = self._parse_timestamp(entry.timestamp).date()
                filter_date = datetime.fromisoformat(date).date()
                if entry_date != filter_date:
                    continue

            results.append(entry)

        # Sort by timestamp, newest first
        results.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit is not None:
            results = results[:limit]

        return results

    def get_commands_for_commit(self, git_sha: str) -> list[CommandEntry]:
        """
        Get all commands associated with a specific commit.

        Args:
            git_sha: The git commit SHA.

        Returns:
            List of CommandEntry objects for that commit.
        """
        return self.search(git_sha=git_sha)

    def get_stats(self, by_feature: bool = False) -> dict[str, Any]:
        """
        Get statistics about command history.

        Args:
            by_feature: If True, include breakdown by feature ID.

        Returns:
            Dictionary with statistics.
        """
        stats: dict[str, Any] = {
            "total_commands": len(self._entries),
            "by_type": {},
            "by_outcome": {},
        }

        # Count by type and outcome
        for entry in self._entries.values():
            # By type
            if entry.command_type not in stats["by_type"]:
                stats["by_type"][entry.command_type] = 0
            stats["by_type"][entry.command_type] += 1

            # By outcome
            if entry.outcome not in stats["by_outcome"]:
                stats["by_outcome"][entry.outcome] = 0
            stats["by_outcome"][entry.outcome] += 1

        # Success rate
        total = len(self._entries)
        successes = stats["by_outcome"].get("success", 0)
        stats["success_rate"] = successes / total if total > 0 else 0.0

        # By feature breakdown
        if by_feature:
            stats["by_feature"] = {}
            for entry in self._entries.values():
                if entry.feature_id:
                    if entry.feature_id not in stats["by_feature"]:
                        stats["by_feature"][entry.feature_id] = {"total": 0}
                    stats["by_feature"][entry.feature_id]["total"] += 1

        return stats

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse an ISO format timestamp, handling timezone variations."""
        # Handle 'Z' suffix
        ts = ts.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            # Try parsing without timezone
            try:
                return datetime.fromisoformat(ts.split("+")[0].split("-")[0])
            except ValueError:
                return datetime.now(timezone.utc)
