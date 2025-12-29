"""
Event persistence for the swarm-attack event system.

Persists events to JSONL files for debugging and replay.
Supports querying by feature, time range, and event type.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from swarm_attack.events.types import EventType, SwarmEvent


class EventPersistence:
    """Persist events to JSONL files."""

    def __init__(self, swarm_dir: Path) -> None:
        """
        Initialize event persistence.

        Args:
            swarm_dir: Path to .swarm directory (will create events/ subdirectory).
        """
        self._events_dir = Path(swarm_dir) / "events"
        self._events_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_path(self) -> Path:
        """Get today's event log path."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._events_dir / f"events-{date_str}.jsonl"

    def append(self, event: SwarmEvent) -> None:
        """Append event to today's log."""
        log_path = self._get_log_path()
        with log_path.open("a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def query(
        self,
        feature_id: Optional[str] = None,
        event_types: Optional[list[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[SwarmEvent]:
        """
        Query events with filters.

        Args:
            feature_id: Filter by feature ID.
            event_types: Filter by event types.
            since: Only return events after this time.
            limit: Maximum number of events to return.

        Returns:
            List of matching SwarmEvent objects.
        """
        events: list[SwarmEvent] = []

        # Determine which log files to read
        log_files = sorted(self._events_dir.glob("events-*.jsonl"), reverse=True)

        for log_file in log_files:
            with log_file.open() as f:
                for line in f:
                    if not line.strip():
                        continue

                    data = json.loads(line)
                    event = SwarmEvent.from_dict(data)

                    # Apply filters
                    if feature_id and event.feature_id != feature_id:
                        continue
                    if event_types and event.event_type not in event_types:
                        continue
                    if since and datetime.fromisoformat(event.timestamp) < since:
                        continue

                    events.append(event)

                    if len(events) >= limit:
                        return events

        return events

    def get_recent(self, minutes: int = 60) -> list[SwarmEvent]:
        """Get events from the last N minutes."""
        since = datetime.now() - timedelta(minutes=minutes)
        return self.query(since=since)

    def get_by_feature(self, feature_id: str, limit: int = 50) -> list[SwarmEvent]:
        """Get events for a specific feature."""
        return self.query(feature_id=feature_id, limit=limit)
