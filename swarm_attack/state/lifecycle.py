"""State lifecycle management with TTL and cleanup.

Provides:
- LifecycleMetadata for tracking state age
- StateCleanupJob for removing expired state
- Staleness detection utilities
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json


@dataclass
class LifecycleMetadata:
    """Lifecycle tracking for persisted state.

    Attributes:
        created_at: When the state was first created (ISO format)
        updated_at: When the state was last modified (ISO format)
        expires_at: Optional expiration time (ISO format)
    """
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None

    @classmethod
    def now(cls, ttl_seconds: Optional[int] = None) -> "LifecycleMetadata":
        """Create metadata with current timestamp.

        Args:
            ttl_seconds: Optional TTL in seconds for expiration
        """
        now = datetime.now().isoformat()
        expires = None
        if ttl_seconds:
            expires = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
        return cls(created_at=now, updated_at=now, expires_at=expires)

    def touch(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.now().isoformat()

    def is_stale(self, max_age: timedelta) -> bool:
        """Check if state is stale (not updated within max_age).

        Args:
            max_age: Maximum age before considered stale

        Returns:
            True if updated_at is older than max_age ago
        """
        updated = datetime.fromisoformat(self.updated_at)
        return datetime.now() - updated > max_age

    def is_expired(self) -> bool:
        """Check if state has passed its expiration time.

        Returns:
            True if expires_at is set and has passed
        """
        if self.expires_at is None:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires

    def age_seconds(self) -> int:
        """Get age in seconds since last update."""
        updated = datetime.fromisoformat(self.updated_at)
        return int((datetime.now() - updated).total_seconds())

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LifecycleMetadata":
        """Deserialize from dictionary."""
        return cls(
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            expires_at=data.get("expires_at"),
        )


class StateCleanupJob:
    """Cleanup expired and stale state files.

    Scans a directory for JSON state files with lifecycle metadata
    and removes those that are expired or stale.
    """

    def __init__(
        self,
        state_dir: Path,
        max_age_days: int = 30,
        dry_run: bool = False,
    ):
        """Initialize cleanup job.

        Args:
            state_dir: Directory containing state files
            max_age_days: Remove state older than this many days
            dry_run: If True, report but don't delete
        """
        self.state_dir = state_dir
        self.max_age = timedelta(days=max_age_days)
        self.dry_run = dry_run

    def run(self) -> list[Path]:
        """Execute cleanup, removing expired state files.

        Returns:
            List of paths that were removed (or would be in dry_run)
        """
        removed = []

        if not self.state_dir.exists():
            return removed

        for state_file in self.state_dir.glob("**/*.json"):
            try:
                data = json.loads(state_file.read_text())

                # Check for lifecycle metadata
                if "lifecycle" not in data:
                    continue

                meta = LifecycleMetadata.from_dict(data["lifecycle"])

                should_remove = meta.is_expired() or meta.is_stale(self.max_age)

                if should_remove:
                    removed.append(state_file)
                    if not self.dry_run:
                        state_file.unlink()

            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip malformed files
                continue

        return removed


def get_staleness_indicator(updated_at: str, thresholds: dict[int, str] = None) -> Optional[str]:
    """Get human-readable staleness indicator.

    Args:
        updated_at: ISO format timestamp of last update
        thresholds: Dict of seconds -> label, defaults provided

    Returns:
        Staleness label if stale, None if fresh

    Example:
        >>> get_staleness_indicator("2025-12-20T10:00:00")
        "stale (5 min ago)"
    """
    if thresholds is None:
        thresholds = {
            300: "stale",       # 5 minutes
            3600: "very stale", # 1 hour
            86400: "outdated",  # 1 day
        }

    try:
        updated = datetime.fromisoformat(updated_at)
        age_seconds = (datetime.now() - updated).total_seconds()

        # Find the highest threshold that applies
        applicable_label = None
        for threshold in sorted(thresholds.keys()):
            if age_seconds >= threshold:
                applicable_label = thresholds[threshold]

        if applicable_label is None:
            return None  # Fresh

        # Format age string
        if age_seconds < 60:
            age_str = f"{int(age_seconds)}s ago"
        elif age_seconds < 3600:
            age_str = f"{int(age_seconds / 60)}m ago"
        elif age_seconds < 86400:
            age_str = f"{int(age_seconds / 3600)}h ago"
        else:
            age_str = f"{int(age_seconds / 86400)}d ago"

        return f"{applicable_label} ({age_str})"

    except ValueError:
        return "unknown"
