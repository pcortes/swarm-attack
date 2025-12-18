"""
Event Logger for Feature Swarm.

This module provides structured event logging to JSONL files:
- Logs events with timestamps for debugging and auditing
- Stores events per-feature in .swarm/events/<feature>.jsonl
- Enables timeline reconstruction and dashboard visualization
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.utils.fs import ensure_dir

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class EventLogger:
    """
    Logs swarm events to JSONL files.

    Events are appended to per-feature log files for debugging,
    auditing, and progress tracking.
    """

    # Standard event types
    EVENT_TYPES = {
        "issue_started": "Implementation session started",
        "tests_written": "Test file created",
        "implementation_complete": "Code implementation finished",
        "verification_passed": "All tests pass",
        "verification_failed": "Tests failed",
        "retry_started": "Retry attempt initiated",
        "issue_done": "Issue successfully completed",
        "issue_blocked": "Issue blocked due to failures",
        "issue_skipped": "Issue skipped due to dependency",
        "git_sync": "State synced from git history",
        "context_injected": "CLAUDE.md context loaded",
        "github_sync": "GitHub labels/comments updated",
    }

    def __init__(self, config: SwarmConfig) -> None:
        """
        Initialize the event logger.

        Args:
            config: SwarmConfig with swarm_path.
        """
        self.config = config
        self.events_dir = config.swarm_path / "events"

    def _ensure_events_dir(self) -> None:
        """Ensure the events directory exists."""
        ensure_dir(self.events_dir)

    def _get_events_path(self, feature_id: str) -> Path:
        """Get path to feature's event log file."""
        return self.events_dir / f"{feature_id}.jsonl"

    def log(
        self,
        feature_id: str,
        event: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Append an event to the feature's event log.

        Args:
            feature_id: The feature identifier.
            event: Event type (e.g., "issue_started", "verification_failed").
            data: Optional additional data to include in the event.
        """
        self._ensure_events_dir()

        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
        }

        if data:
            entry.update(data)

        events_path = self._get_events_path(feature_id)

        try:
            with open(events_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except (IOError, OSError):
            # Best effort - don't fail if we can't log
            pass

    def get_events(
        self,
        feature_id: str,
        event_type: Optional[str] = None,
        issue_number: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Read events from a feature's event log.

        Args:
            feature_id: The feature identifier.
            event_type: Optional filter by event type.
            issue_number: Optional filter by issue number.
            limit: Optional maximum number of events to return (most recent).

        Returns:
            List of event dictionaries, newest last.
        """
        events_path = self._get_events_path(feature_id)

        if not events_path.exists():
            return []

        events: list[dict[str, Any]] = []

        try:
            with open(events_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)

                        # Apply filters
                        if event_type and entry.get("event") != event_type:
                            continue
                        if issue_number is not None and entry.get("issue") != issue_number:
                            continue

                        events.append(entry)
                    except json.JSONDecodeError:
                        continue
        except (IOError, OSError):
            return []

        # Apply limit (return most recent)
        if limit and len(events) > limit:
            events = events[-limit:]

        return events

    def get_issue_timeline(
        self,
        feature_id: str,
        issue_number: int,
    ) -> list[dict[str, Any]]:
        """
        Get timeline of events for a specific issue.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.

        Returns:
            List of events for this issue, oldest first.
        """
        return self.get_events(feature_id, issue_number=issue_number)

    def get_recent_events(
        self,
        feature_id: str,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get the most recent events for a feature.

        Args:
            feature_id: The feature identifier.
            count: Number of recent events to return.

        Returns:
            List of recent events, newest last.
        """
        return self.get_events(feature_id, limit=count)

    def log_issue_started(
        self,
        feature_id: str,
        issue_number: int,
        session_id: str = "",
    ) -> None:
        """Log that an issue implementation session started."""
        self.log(feature_id, "issue_started", {
            "issue": issue_number,
            "session": session_id,
        })

    def log_tests_written(
        self,
        feature_id: str,
        issue_number: int,
        test_count: int,
        test_path: str = "",
    ) -> None:
        """Log that tests were written."""
        self.log(feature_id, "tests_written", {
            "issue": issue_number,
            "count": test_count,
            "path": test_path,
        })

    def log_implementation_complete(
        self,
        feature_id: str,
        issue_number: int,
        files_created: Optional[list[str]] = None,
        files_modified: Optional[list[str]] = None,
    ) -> None:
        """Log that implementation code was generated."""
        data: dict[str, Any] = {"issue": issue_number}
        if files_created:
            data["files_created"] = files_created
        if files_modified:
            data["files_modified"] = files_modified
        self.log(feature_id, "implementation_complete", data)

    def log_verification_passed(
        self,
        feature_id: str,
        issue_number: int,
        tests_passed: int,
    ) -> None:
        """Log that verification passed."""
        self.log(feature_id, "verification_passed", {
            "issue": issue_number,
            "tests_passed": tests_passed,
        })

    def log_verification_failed(
        self,
        feature_id: str,
        issue_number: int,
        tests_failed: int,
        failures: Optional[list[str]] = None,
    ) -> None:
        """Log that verification failed."""
        data: dict[str, Any] = {
            "issue": issue_number,
            "tests_failed": tests_failed,
        }
        if failures:
            # Truncate failure messages
            data["failures"] = [f[:200] for f in failures[:5]]
        self.log(feature_id, "verification_failed", data)

    def log_retry_started(
        self,
        feature_id: str,
        issue_number: int,
        attempt: int,
    ) -> None:
        """Log that a retry attempt started."""
        self.log(feature_id, "retry_started", {
            "issue": issue_number,
            "attempt": attempt,
        })

    def log_issue_done(
        self,
        feature_id: str,
        issue_number: int,
        commit_hash: str = "",
        cost_usd: float = 0.0,
    ) -> None:
        """Log that an issue was completed successfully."""
        self.log(feature_id, "issue_done", {
            "issue": issue_number,
            "commit": commit_hash,
            "cost_usd": cost_usd,
        })

    def log_issue_blocked(
        self,
        feature_id: str,
        issue_number: int,
        reason: str,
        retries: int = 0,
    ) -> None:
        """Log that an issue was blocked."""
        self.log(feature_id, "issue_blocked", {
            "issue": issue_number,
            "reason": reason[:200],  # Truncate long reasons
            "retries": retries,
        })

    def log_issue_skipped(
        self,
        feature_id: str,
        issue_number: int,
        blocking_issue: int,
    ) -> None:
        """Log that an issue was skipped due to dependency."""
        self.log(feature_id, "issue_skipped", {
            "issue": issue_number,
            "blocking_issue": blocking_issue,
        })

    def log_git_sync(
        self,
        feature_id: str,
        synced_issues: list[int],
    ) -> None:
        """Log that state was synced from git."""
        self.log(feature_id, "git_sync", {
            "synced_issues": synced_issues,
        })

    def log_context_injected(
        self,
        feature_id: str,
        has_claude_md: bool,
        summaries_count: int = 0,
    ) -> None:
        """Log that context was injected into coder."""
        self.log(feature_id, "context_injected", {
            "has_claude_md": has_claude_md,
            "summaries_count": summaries_count,
        })

    def log_github_sync(
        self,
        feature_id: str,
        issue_number: int,
        action: str,  # "label_updated", "comment_posted", "issue_closed"
        success: bool,
    ) -> None:
        """Log GitHub sync action."""
        self.log(feature_id, "github_sync", {
            "issue": issue_number,
            "action": action,
            "success": success,
        })


# Module-level singleton for convenience
_logger_cache: dict[str, EventLogger] = {}


def get_event_logger(config: SwarmConfig) -> EventLogger:
    """
    Get an EventLogger instance for the given config.

    Uses a simple cache keyed by repo_root.

    Args:
        config: SwarmConfig with paths configured.

    Returns:
        EventLogger instance.
    """
    key = str(config.repo_root)
    if key not in _logger_cache:
        _logger_cache[key] = EventLogger(config)
    return _logger_cache[key]


def clear_logger_cache() -> None:
    """Clear the logger cache. Useful for testing."""
    global _logger_cache
    _logger_cache = {}
