# Engineering Spec: User Notifications

## 1. Overview

### 1.1 Purpose
Enable users to receive and manage in-app notifications for important events. Users will be able to see a list of notifications, view notification history, and mark notifications as read. This is an MVP for our 100 beta users, focused on in-app notifications only.

### 1.2 Existing Infrastructure
This builds on the existing swarm-attack patterns:

- **State storage**: JSON file persistence via `StateStore` pattern in `swarm_attack/state_store.py`
- **Data models**: Dataclass pattern with `to_dict()`/`from_dict()` serialization in `swarm_attack/models.py`
- **Logging**: JSONL logging via `SwarmLogger` in `swarm_attack/logger.py`
- **File utilities**: Safe atomic writes via `swarm_attack/utils/fs.py`
- **User auth**: PRD states "use existing user auth system" - notifications will use a simple user_id string

### 1.3 Scope
**In Scope:**
- Notification data model with read/unread status
- Store notifications in JSON files (per-user)
- List recent notifications
- Mark notification as read
- Simple notification creation API
- CLI commands for users to view and manage notifications

**Out of Scope:**
- Push notifications (v1 is in-app only per PRD)
- Email notifications (explicitly excluded per PRD)
- Real-time updates (polling or manual refresh is fine for MVP)
- Notification preferences/settings
- Notification grouping or batching
- Rich media in notifications
- **Event trigger integration**: This spec provides the notification infrastructure. Which features/events call `NotificationStore.create()` is defined per-feature, not here. The API is ready; features plug in as needed.

## 2. Implementation

### 2.1 Approach
Follow the existing `StateStore` pattern for persistence. Create a `NotificationStore` class that mirrors `StateStore` but for notifications. Store notifications as JSON files at `.swarm/notifications/{user_id}.json`. Each file contains the user's notification list.

The pattern is intentionally simple: load JSON, modify in memory, write back atomically. This works well for 100 beta users.

### 2.2 Changes Required
| File | Change | Why |
|------|--------|-----|
| `swarm_attack/notification_models.py` | Create new file | Define Notification dataclass |
| `swarm_attack/notification_store.py` | Create new file | Persistence layer for notifications |
| `swarm_attack/cli.py` | Add commands | User-facing notification commands |

### 2.3 Data Model

```python
# New file: swarm_attack/notification_models.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Notification:
    """A single notification for a user."""
    id: str                              # Unique ID (e.g., "notif_001")
    user_id: str                         # User this notification belongs to
    title: str                           # Short title
    message: str                         # Full message
    notification_type: NotificationType  # Type for styling
    created_at: str                      # ISO timestamp
    read: bool = False                   # Has user seen this?
    read_at: Optional[str] = None        # When marked read

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notification_type"] = self.notification_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Notification":
        data = data.copy()
        data["notification_type"] = NotificationType(data["notification_type"])
        return cls(**data)

    def mark_read(self) -> None:
        self.read = True
        self.read_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class UserNotifications:
    """All notifications for a user."""
    user_id: str
    notifications: list[Notification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "notifications": [n.to_dict() for n in self.notifications],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserNotifications":
        return cls(
            user_id=data["user_id"],
            notifications=[Notification.from_dict(n) for n in data.get("notifications", [])],
        )

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self.notifications if not n.read)

    def get_recent(self, limit: int = 20) -> list[Notification]:
        """Get most recent notifications, newest first."""
        sorted_notifs = sorted(self.notifications, key=lambda n: n.created_at, reverse=True)
        return sorted_notifs[:limit]
```

## 3. API

### 3.1 Storage API (Python)

This is a CLI tool, not a web service. The API is Python functions in the `NotificationStore` class:

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `create(user_id: str, title: str, message: str, notification_type: NotificationType) -> Notification` | Create a notification |
| `list_notifications` | `list_notifications(user_id: str, limit: int = 20, unread_only: bool = False) -> list[Notification]` | Get user's notifications |
| `mark_read` | `mark_read(user_id: str, notification_id: str) -> bool` | Mark one notification as read |
| `mark_all_read` | `mark_all_read(user_id: str) -> int` | Mark all as read, return count |
| `get_unread_count` | `get_unread_count(user_id: str) -> int` | Get count of unread notifications |

### 3.2 CLI Commands

Users interact with notifications through CLI commands added to `swarm_attack/cli.py`:

| Command | Description | Example |
|---------|-------------|---------|
| `swarm notifications` | List recent notifications (shows unread count, last 20) | `swarm notifications` |
| `swarm notifications --unread` | List unread notifications only | `swarm notifications --unread` |
| `swarm notifications read <id>` | Mark a specific notification as read | `swarm notifications read notif_001` |
| `swarm notifications read-all` | Mark all notifications as read | `swarm notifications read-all` |

**Output format** (simple text, not JSON):
```
Notifications (3 unread)
────────────────────────
[!] notif_003 - Mission completed (2 min ago)
    Your mission "Fix login bug" was completed successfully.

[ ] notif_002 - New assignment (1 hour ago)
    You were assigned to project "Dashboard redesign".

[✓] notif_001 - Welcome (2 days ago)
    Welcome to the platform!
```

Legend: `[!]` = unread, `[✓]` = read

## 4. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Create notification data models | `swarm_attack/notification_models.py` | S |
| 2 | Create notification store with CRUD operations | `swarm_attack/notification_store.py` | M |
| 3 | Add CLI commands for notifications | `swarm_attack/cli.py` | S |
| 4 | Add unit tests for models | `tests/test_notification_models.py` | S |
| 5 | Add unit tests for store | `tests/test_notification_store.py` | M |

## 5. Testing

### 5.1 Manual Test Plan
1. Create a notification for user "test_user"
2. Run `swarm notifications` and verify it appears with `[!]` marker
3. Verify unread count shows in header
4. Run `swarm notifications read notif_001`
5. Run `swarm notifications` and verify it shows `[✓]` marker
6. Create 25 notifications, verify only 20 shown
7. Restart the application and verify notifications persist

### 5.2 Automated Tests

**Model tests** (`test_notification_models.py`):
- `test_notification_to_dict_from_dict_roundtrip`
- `test_notification_mark_read_sets_timestamp`
- `test_user_notifications_unread_count`
- `test_user_notifications_get_recent_ordering`

**Store tests** (`test_notification_store.py`):
- `test_create_notification_persists_to_file`
- `test_list_notifications_returns_recent_first`
- `test_mark_read_updates_notification`
- `test_mark_all_read_returns_count`
- `test_unread_only_filter`

**CLI tests** (`tests/test_cli.py` - add to existing):
- `test_notifications_command_shows_unread_count`
- `test_notifications_read_command_marks_notification`

## 6. Open Questions

1. **User ID source**: The PRD mentions "use existing user auth system" - what is the user_id format? Assuming simple string for now.
2. **Notification retention**: How long should notifications be kept? Defaulting to unlimited for MVP - can add cleanup later if needed.