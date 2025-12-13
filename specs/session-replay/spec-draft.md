# Engineering Spec: Session Replay

## 1. Overview

### 1.1 Purpose

The Session Replay feature enables users to replay their past coaching sessions as audio with interactive bookmarking capabilities. This allows users to revisit valuable coaching moments, save key insights for future reference, and navigate through session history efficiently.

### 1.2 Scope

**In Scope:**
- Viewing a chronological list of past coaching sessions with metadata
- Audio playback of any past session with standard controls (play/pause/seek/speed)
- Bookmarking specific timestamps during playback
- Persistent bookmark storage with retrieval
- Timeline view showing bookmarks within a session
- Audio streaming/progressive loading for large files

**Out of Scope:**
- Video replay (audio only for v1)
- Sharing sessions with other users
- Transcript generation (future feature)
- Offline playback
- Multi-session playlist or queue functionality
- Bookmark categories or tagging
- Audio editing or clipping
- Session creation or audio ingestion (handled by upstream systems)

### 1.3 Success Criteria

| Criterion | Metric | Target |
|-----------|--------|--------|
| Session list load time | Time to display session list | < 1 second |
| Audio playback start | Time from play to first audio | < 500ms for cached, < 2s for streaming |
| Bookmark creation | Time to save bookmark | < 200ms |
| Bookmark retrieval | Time to load session bookmarks | < 300ms |
| Playback controls responsiveness | Seek/speed change latency | < 100ms |
| Session list accuracy | All user sessions displayed | 100% |

See Section 11.4 for how these metrics will be instrumented and monitored.

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SESSION REPLAY FEATURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Frontend Layer                               │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ SessionListView │  │ AudioPlayer     │  │ BookmarkTimeline    │  │   │
│  │  │                 │  │                 │  │                     │  │   │
│  │  │ • List sessions │  │ • Play/pause    │  │ • Visual bookmarks  │  │   │
│  │  │ • Filter/sort   │  │ • Seek bar      │  │ • Click to seek     │  │   │
│  │  │ • Select to play│  │ • Speed control │  │ • Add/remove marks  │  │   │
│  │  │ • Show metadata │  │ • Time display  │  │ • Bookmark labels   │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          API Layer                                   │   │
│  │                                                                      │   │
│  │  GET /sessions              - List user's coaching sessions          │   │
│  │  GET /sessions/:id          - Get session details (includes audio_url)│   │
│  │  GET /sessions/:id/bookmarks - Get session bookmarks                 │   │
│  │  POST /sessions/:id/bookmarks - Create bookmark                      │   │
│  │  DELETE /sessions/:id/bookmarks/:bid - Delete bookmark               │   │
│  │  PATCH /sessions/:id/bookmarks/:bid - Update bookmark                │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Service Layer                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ SessionService  │  │ AudioService    │  │ BookmarkService     │  │   │
│  │  │                 │  │                 │  │                     │  │   │
│  │  │ • List sessions │  │ • Generate URL  │  │ • CRUD bookmarks    │  │   │
│  │  │ • Get details   │  │ • Sign URLs     │  │ • Validate times    │  │   │
│  │  │ • Authorization │  │ • Set expiry    │  │ • Ownership check   │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Storage Layer                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ SessionStore    │  │ AudioStore      │  │ BookmarkStore       │  │   │
│  │  │                 │  │                 │  │                     │  │   │
│  │  │ PostgreSQL      │  │ S3/Object Store │  │ PostgreSQL          │  │   │
│  │  │ session table   │  │ audio files     │  │ bookmark table      │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `SessionListView` | `frontend/components/SessionListView.tsx` | Display paginated list of past sessions |
| `AudioPlayer` | `frontend/components/AudioPlayer.tsx` | Audio playback with standard controls |
| `BookmarkTimeline` | `frontend/components/BookmarkTimeline.tsx` | Visual bookmark display and interaction |
| `SessionService` | `backend/services/session_service.py` | Session CRUD, authorization, and audio_url generation |
| `AudioService` | `backend/services/audio_service.py` | Pre-signed URL generation for S3 audio files |
| `BookmarkService` | `backend/services/bookmark_service.py` | Bookmark CRUD operations |
| `SessionRepository` | `backend/repositories/session_repository.py` | Session database operations |
| `BookmarkRepository` | `backend/repositories/bookmark_repository.py` | Bookmark database operations |

### 2.3 Data Flow

```
User Action: Select session from list
     │
     ▼
┌────────────────┐     ┌────────────────┐
│ SessionListView│────▶│ GET /sessions  │
└────────────────┘     └────────────────┘
                              │
                              ▼
                       ┌────────────────┐
                       │SessionService  │
                       │ - Auth check   │
                       │ - Query DB     │
                       └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│  AudioPlayer   │◀────│ Session Data   │
│                │     │ + Audio URL    │
└────────────────┘     └────────────────┘
        │
        ▼
User Action: Play audio
        │
        ▼
┌────────────────┐     ┌────────────────┐
│ HTML5 Audio    │────▶│ S3 Pre-signed  │
│ Element        │     │ URL (direct)   │
└────────────────┘     └────────────────┘

User Action: Add bookmark at 5:30
     │
     ▼
┌────────────────┐     ┌────────────────┐
│BookmarkTimeline│────▶│ POST /bookmarks│
└────────────────┘     └────────────────┘
                              │
                              ▼
                       ┌────────────────┐
                       │BookmarkService │
                       │ - Validate     │
                       │ - Persist      │
                       └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│BookmarkTimeline│◀────│ Bookmark Data  │
│ (updated)      │     └────────────────┘
└────────────────┘
```

---

## 3. Data Models

### 3.1 New Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid


class SessionStatus(Enum):
    """Status of a coaching session."""
    COMPLETED = "completed"      # Session finished normally
    INTERRUPTED = "interrupted"  # Session ended unexpectedly
    PROCESSING = "processing"    # Audio still being processed


@dataclass
class CoachingSession:
    """
    Represents a coaching session available for replay.

    Stored in the sessions table.
    Note: audio_file_key is internal only and never exposed in API responses.
    """
    id: str                              # UUID primary key
    user_id: str                         # Owner of the session
    title: str                           # Session title/topic
    started_at: datetime                 # When session began
    ended_at: Optional[datetime]         # When session ended
    duration_seconds: int                # Total duration in seconds
    audio_file_key: str                  # S3 key for audio file (internal only)
    audio_format: str                    # "mp3", "wav", "aac"
    audio_size_bytes: int                # File size for progress display
    status: SessionStatus                # Current status
    coach_name: Optional[str] = None     # Name of the coach if applicable
    summary: Optional[str] = None        # Brief summary of session
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self, audio_url: Optional[str] = None) -> dict:
        """
        Convert to dictionary for JSON serialization.
        
        Args:
            audio_url: Pre-signed URL generated by AudioService (injected by SessionService)
        
        Note: audio_file_key is intentionally excluded from public serialization.
        """
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "audio_format": self.audio_format,
            "audio_size_bytes": self.audio_size_bytes,
            "status": self.status.value,
            "coach_name": self.coach_name,
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if audio_url:
            result["audio_url"] = audio_url
        return result

    @classmethod
    def from_db_row(cls, row: dict) -> "CoachingSession":
        """Create from database row (includes audio_file_key)."""
        data = row.copy()
        data["status"] = SessionStatus(data["status"])
        data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("ended_at"):
            data["ended_at"] = datetime.fromisoformat(data["ended_at"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class Bookmark:
    """
    A bookmark at a specific timestamp in a session.

    Stored in the bookmarks table.
    """
    id: str                              # UUID primary key
    session_id: str                      # Foreign key to sessions
    user_id: str                         # Owner of the bookmark
    timestamp_seconds: float             # Position in audio (supports fractions)
    label: str                           # User-provided label/note
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp_seconds": self.timestamp_seconds,
            "label": self.label,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bookmark":
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class SessionListItem:
    """
    Lightweight session info for list display.

    Used to avoid loading full session data for list views.
    """
    id: str
    title: str
    started_at: datetime
    duration_seconds: int
    status: SessionStatus
    bookmark_count: int                  # Number of bookmarks for quick display
    coach_name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "duration_formatted": self._format_duration(),
            "status": self.status.value,
            "bookmark_count": self.bookmark_count,
            "coach_name": self.coach_name,
        }

    def _format_duration(self) -> str:
        """Format duration as HH:MM:SS or MM:SS."""
        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass
class PlaybackState:
    """
    Client-side playback state for resuming playback.

    Not persisted server-side, but defines the contract.
    """
    session_id: str
    current_time_seconds: float          # Current playback position
    playback_speed: float                # 0.5, 0.75, 1.0, 1.25, 1.5, 2.0
    is_playing: bool
    volume: float                        # 0.0 to 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for localStorage."""
        return {
            "session_id": self.session_id,
            "current_time_seconds": self.current_time_seconds,
            "playback_speed": self.playback_speed,
            "is_playing": self.is_playing,
            "volume": self.volume,
        }
```

### 3.2 Schema Changes

**Table Creation Strategy:**

The migration uses `CREATE TABLE IF NOT EXISTS` to handle both scenarios:
1. **Table does not exist**: Creates the table with all required columns
2. **Table already exists**: No-op; assumes existing table is compatible

Before running this migration in production, coordinate with the upstream session owner (identified in Open Questions #2) to determine:
- Whether to extend an existing table or use this new one
- Required data migration/backfill steps if extending
- Column compatibility if an existing table has different schema

**New Tables:**

```sql
-- Sessions table (may already exist, add missing columns)
CREATE TABLE IF NOT EXISTS coaching_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER NOT NULL,
    audio_file_key VARCHAR(512) NOT NULL,
    audio_format VARCHAR(10) NOT NULL DEFAULT 'mp3',
    audio_size_bytes BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    coach_name VARCHAR(100),
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('completed', 'interrupted', 'processing'))
);

-- Index for user session lookup (most common query)
CREATE INDEX IF NOT EXISTS idx_sessions_user_started ON coaching_sessions(user_id, started_at DESC);

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_sessions_status ON coaching_sessions(status);


-- Bookmarks table
CREATE TABLE IF NOT EXISTS session_bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES coaching_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp_seconds DECIMAL(10, 3) NOT NULL,
    label VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate bookmarks at same timestamp
    CONSTRAINT unique_bookmark_position UNIQUE (session_id, user_id, timestamp_seconds)
);

-- Index for session bookmark lookup
CREATE INDEX IF NOT EXISTS idx_bookmarks_session ON session_bookmarks(session_id, timestamp_seconds);

-- Index for user's bookmarks across all sessions
CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON session_bookmarks(user_id, created_at DESC);
```

**Migration File:**

```python
# migrations/versions/20251213_add_session_replay.py

"""Add session replay tables

Revision ID: 20251213_session_replay
Create Date: 2025-12-13

Note: This migration creates tables only if they don't exist. If coaching_sessions
already exists in your environment, coordinate with the upstream owner before
running this migration. See Open Questions #2 in the spec.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # Create coaching_sessions table if not exists
    # If table exists, this is a no-op
    op.execute("""
        CREATE TABLE IF NOT EXISTS coaching_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            duration_seconds INTEGER NOT NULL,
            audio_file_key VARCHAR(512) NOT NULL,
            audio_format VARCHAR(10) NOT NULL DEFAULT 'mp3',
            audio_size_bytes BIGINT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'completed',
            coach_name VARCHAR(100),
            summary TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT valid_session_status CHECK (status IN ('completed', 'interrupted', 'processing'))
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_started ON coaching_sessions(user_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON coaching_sessions(status)")

    # Create bookmarks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS session_bookmarks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES coaching_sessions(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp_seconds DECIMAL(10, 3) NOT NULL,
            label VARCHAR(500) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT unique_bookmark_position UNIQUE (session_id, user_id, timestamp_seconds)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_session ON session_bookmarks(session_id, timestamp_seconds)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON session_bookmarks(user_id, created_at DESC)")


def downgrade():
    op.drop_table('session_bookmarks')
    op.drop_table('coaching_sessions')
```

---

## 4. API Design

### 4.1 Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/sessions` | List user's coaching sessions | Required |
| GET | `/api/v1/sessions/:id` | Get session details with pre-signed audio_url | Required |
| GET | `/api/v1/sessions/:id/bookmarks` | Get session bookmarks | Required |
| POST | `/api/v1/sessions/:id/bookmarks` | Create bookmark | Required |
| PATCH | `/api/v1/sessions/:id/bookmarks/:bid` | Update bookmark | Required |
| DELETE | `/api/v1/sessions/:id/bookmarks/:bid` | Delete bookmark | Required |

**Note:** Audio is delivered via pre-signed S3 URLs returned in the session detail response, not through a streaming proxy endpoint. See Section 10.4 for rationale.

### 4.2 Request/Response Schemas

**GET /api/v1/sessions**

List user's coaching sessions with pagination and filtering.

Query Parameters:
```
page: int = 1              # Page number (1-indexed)
limit: int = 20            # Items per page (max 100)
status: string?            # Filter by status: completed, interrupted, processing
sort: string = "started_at" # Sort field: started_at, duration_seconds, title
order: string = "desc"     # Sort order: asc, desc
```

Response (200 OK):
```json
{
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Career Transition Coaching",
      "started_at": "2025-12-10T14:30:00Z",
      "duration_seconds": 3600,
      "duration_formatted": "1:00:00",
      "status": "completed",
      "bookmark_count": 5,
      "coach_name": "Sarah Johnson"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_count": 45,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

**GET /api/v1/sessions/:id**

Get full session details including pre-signed audio URL.

Response (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Career Transition Coaching",
  "started_at": "2025-12-10T14:30:00Z",
  "ended_at": "2025-12-10T15:30:00Z",
  "duration_seconds": 3600,
  "duration_formatted": "1:00:00",
  "audio_url": "https://bucket.s3.region.amazonaws.com/sessions/abc123.mp3?X-Amz-Algorithm=...",
  "audio_format": "mp3",
  "audio_size_bytes": 45678912,
  "status": "completed",
  "coach_name": "Sarah Johnson",
  "summary": "Discussed career goals and developed action plan for Q1.",
  "created_at": "2025-12-10T15:35:00Z",
  "bookmarks": [
    {
      "id": "bookmark-uuid-1",
      "timestamp_seconds": 330.5,
      "timestamp_formatted": "5:30",
      "label": "Key insight about networking"
    }
  ]
}
```

**Note:** The `audio_url` is a pre-signed S3 URL with 24-hour expiry. The frontend should use this URL directly with the HTML5 audio element. If a 403 error occurs during playback (expired URL), the frontend should re-fetch the session detail to obtain a fresh URL.

Response (404 Not Found):
```json
{
  "error": "session_not_found",
  "message": "Session not found or access denied"
}
```

**GET /api/v1/sessions/:id/bookmarks**

Get all bookmarks for a session.

Response (200 OK):
```json
{
  "bookmarks": [
    {
      "id": "bookmark-uuid-1",
      "timestamp_seconds": 330.5,
      "timestamp_formatted": "5:30",
      "label": "Key insight about networking",
      "created_at": "2025-12-10T15:45:00Z",
      "updated_at": "2025-12-10T15:45:00Z"
    },
    {
      "id": "bookmark-uuid-2",
      "timestamp_seconds": 1245.0,
      "timestamp_formatted": "20:45",
      "label": "Action item: Update resume",
      "created_at": "2025-12-10T16:00:00Z",
      "updated_at": "2025-12-10T16:00:00Z"
    }
  ]
}
```

**POST /api/v1/sessions/:id/bookmarks**

Create a new bookmark.

Request:
```json
{
  "timestamp_seconds": 330.5,
  "label": "Key insight about networking"
}
```

Validation Rules:
- `timestamp_seconds`: Required, >= 0, <= session duration
- `label`: Required, 1-500 characters, trimmed
- Cannot create duplicate bookmark at same timestamp

Response (201 Created):
```json
{
  "id": "bookmark-uuid-new",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp_seconds": 330.5,
  "timestamp_formatted": "5:30",
  "label": "Key insight about networking",
  "created_at": "2025-12-13T10:30:00Z",
  "updated_at": "2025-12-13T10:30:00Z"
}
```

Response (400 Bad Request):
```json
{
  "error": "validation_error",
  "message": "Invalid bookmark data",
  "details": {
    "timestamp_seconds": "Timestamp exceeds session duration (3600s)"
  }
}
```

Response (409 Conflict):
```json
{
  "error": "duplicate_bookmark",
  "message": "A bookmark already exists at this timestamp"
}
```

**PATCH /api/v1/sessions/:id/bookmarks/:bid**

Update bookmark label.

Request:
```json
{
  "label": "Updated insight about networking strategies"
}
```

Response (200 OK):
```json
{
  "id": "bookmark-uuid-1",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp_seconds": 330.5,
  "timestamp_formatted": "5:30",
  "label": "Updated insight about networking strategies",
  "created_at": "2025-12-10T15:45:00Z",
  "updated_at": "2025-12-13T10:35:00Z"
}
```

**DELETE /api/v1/sessions/:id/bookmarks/:bid**

Delete a bookmark.

Response (204 No Content)

Response (404 Not Found):
```json
{
  "error": "bookmark_not_found",
  "message": "Bookmark not found or access denied"
}
```

---

## 5. Implementation Plan

### 5.1 Tasks

| # | Task | Dependencies | Size | Description |
|---|------|--------------|------|-------------|
| 1 | Create data models | None | S | Define CoachingSession, Bookmark, SessionListItem dataclasses |
| 2 | Create database migration | 1 | S | Add coaching_sessions and session_bookmarks tables |
| 3 | Implement SessionRepository | 2 | M | Database operations for sessions |
| 4 | Implement BookmarkRepository | 2 | M | Database operations for bookmarks |
| 5 | Implement SessionService | 3 | M | Business logic for session operations, including audio_url generation |
| 6 | Implement AudioService | 3 | M | Pre-signed URL generation for S3 audio files |
| 7 | Implement BookmarkService | 4, 5 | M | Bookmark CRUD with validation |
| 8 | Create API endpoints | 5, 6, 7 | M | REST endpoints for all operations |
| 9 | Create SessionListView component | 8 | M | Frontend session list with pagination |
| 10 | Create AudioPlayer component | 8 | L | HTML5 audio player with custom controls |
| 11 | Create BookmarkTimeline component | 8 | M | Visual bookmark display and interaction |
| 12 | Integrate components | 9, 10, 11 | M | Wire up components into cohesive UI |
| 13 | Add playback state persistence | 12 | S | localStorage for resume playback |
| 14 | Add unit tests | 3, 4, 5, 6, 7 | L | Backend service and repository tests |
| 15 | Add integration tests | 8 | M | API endpoint tests |
| 16 | Add frontend tests | 9, 10, 11 | M | Component and interaction tests |
| 17 | Add observability instrumentation | 8, 12 | S | Metrics, logging, and tracing per Section 11.4 |

### 5.2 Service Layer Responsibilities

**SessionService** is responsible for:
1. Querying SessionRepository for session data (includes audio_file_key)
2. Verifying user ownership/authorization
3. Calling AudioService.get_audio_url(audio_file_key) to generate pre-signed URL
4. Injecting audio_url into the response DTO via CoachingSession.to_dict(audio_url=url)
5. Returning the complete response (audio_file_key never leaves the service layer)

```python
# session_service.py (key method)

class SessionService:
    def get_session_detail(self, user_id: str, session_id: str) -> dict:
        """Get session with audio URL for API response."""
        session = self.session_repo.get_by_id(session_id)
        if not session or session.user_id != user_id:
            raise NotFoundError("Session not found")
        
        # Generate pre-signed URL from internal key
        audio_url = self.audio_service.get_audio_url(session.audio_file_key)
        
        # Get bookmarks for this session
        bookmarks = self.bookmark_repo.get_by_session(session_id)
        
        # Return DTO with audio_url injected (audio_file_key excluded)
        result = session.to_dict(audio_url=audio_url)
        result["bookmarks"] = [b.to_dict() for b in bookmarks]
        return result
```

### 5.3 File Changes

**New Files:**

Backend:
- `backend/models/session_replay.py` - Data models
- `backend/repositories/session_repository.py` - Session DB operations
- `backend/repositories/bookmark_repository.py` - Bookmark DB operations
- `backend/services/session_service.py` - Session business logic with audio_url generation
- `backend/services/audio_service.py` - Pre-signed URL generation
- `backend/services/bookmark_service.py` - Bookmark business logic
- `backend/api/v1/sessions.py` - API endpoints
- `migrations/versions/20251213_add_session_replay.py` - DB migration

Frontend:
- `frontend/components/SessionListView.tsx` - Session list component
- `frontend/components/AudioPlayer.tsx` - Audio player component
- `frontend/components/BookmarkTimeline.tsx` - Bookmark timeline component
- `frontend/components/SessionReplayPage.tsx` - Main page component
- `frontend/hooks/useAudioPlayer.ts` - Audio playback hook
- `frontend/hooks/useBookmarks.ts` - Bookmark management hook
- `frontend/api/sessions.ts` - API client for sessions

Tests:
- `tests/unit/test_session_service.py`
- `tests/unit/test_audio_service.py`
- `tests/unit/test_bookmark_service.py`
- `tests/integration/test_session_api.py`
- `frontend/tests/SessionListView.test.tsx`
- `frontend/tests/AudioPlayer.test.tsx`
- `frontend/tests/BookmarkTimeline.test.tsx`

**Modified Files:**
- `backend/api/v1/__init__.py` - Register new routes
- `frontend/routes.tsx` - Add session replay route

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Component | Test Cases | Coverage Target |
|-----------|------------|-----------------|
| SessionRepository | CRUD operations, pagination, filtering | 90% |
| BookmarkRepository | CRUD, duplicate detection, cascade delete | 90% |
| SessionService | Authorization, list/get operations, audio_url generation | 85% |
| AudioService | URL generation, expiry settings | 85% |
| BookmarkService | Validation, ownership checks, timestamp bounds | 90% |

**Key Unit Tests:**

```python
# test_session_service.py

def test_list_sessions_returns_only_user_sessions():
    """User cannot see other users' sessions."""

def test_list_sessions_pagination():
    """Pagination returns correct page and counts."""

def test_list_sessions_filter_by_status():
    """Status filter works correctly."""

def test_get_session_not_found():
    """Returns None for non-existent session."""

def test_get_session_wrong_user():
    """Returns None when user doesn't own session."""

def test_get_session_includes_audio_url():
    """Session detail includes generated audio_url."""

def test_get_session_excludes_audio_file_key():
    """audio_file_key is not present in response."""


# test_bookmark_service.py

def test_create_bookmark_success():
    """Bookmark created with valid data."""

def test_create_bookmark_timestamp_exceeds_duration():
    """Rejects bookmark beyond session duration."""

def test_create_bookmark_negative_timestamp():
    """Rejects negative timestamp."""

def test_create_bookmark_duplicate_timestamp():
    """Rejects duplicate bookmark at same timestamp."""

def test_update_bookmark_wrong_user():
    """Cannot update another user's bookmark."""

def test_delete_bookmark_cascades_with_session():
    """Bookmarks deleted when session deleted."""
```

### 6.2 Integration Tests

| Scenario | Description | Validation |
|----------|-------------|------------|
| Session list flow | List -> Details -> Audio URL | All data correct, audio_url is valid signed URL |
| Bookmark CRUD flow | Create -> Read -> Update -> Delete | All operations succeed |
| Audio URL validity | Fetch session, use audio_url | URL returns audio data from S3 |
| Authorization | Access denied for other users | 404 responses |
| Pagination | Multi-page session list | Correct counts and data |

**Key Integration Tests:**

```python
# test_session_api.py

async def test_list_sessions_empty():
    """New user has no sessions."""

async def test_list_sessions_with_data():
    """Returns correct session list."""

async def test_get_session_includes_bookmarks():
    """Session detail includes bookmark list."""

async def test_get_session_audio_url_is_valid():
    """audio_url is a properly signed S3 URL."""

async def test_audio_url_allows_range_requests():
    """S3 URL supports HTTP Range headers for seeking."""

async def test_create_bookmark_updates_list():
    """New bookmark appears in session detail."""

async def test_concurrent_bookmark_creation():
    """Duplicate prevention under concurrency."""
```

### 6.3 Edge Cases

| Case | Test |
|------|------|
| Empty session list | Handles user with no sessions gracefully |
| Very long session (3+ hours) | Audio streaming handles large files |
| Many bookmarks (100+) | Timeline renders efficiently |
| Rapid bookmark creation | No duplicate creation race conditions |
| Session deleted while playing | Handles 404 gracefully in player |
| Invalid audio file | Handles corrupted/missing audio |
| Unicode in labels | Bookmark labels support unicode |
| Timestamp at exact duration | Edge case for end-of-session bookmark |
| Zero-duration session | Handles edge case gracefully |
| Session in "processing" status | Shows appropriate UI state |
| Expired audio URL during playback | Frontend refreshes URL on 403 |

---

## 7. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Large audio files cause slow loading | High | Medium | Use streaming with range requests via S3, show loading progress |
| S3 signed URLs expire during playback | Medium | Low | Generate URLs with 24h expiry, frontend re-fetches session detail on 403 to get fresh URL |
| Too many bookmarks slow timeline | Low | Low | Virtualize bookmark list if > 50 items |
| Audio format compatibility | Medium | Low | Transcode to MP3 on upload (universal support) |
| Race condition on bookmark creation | Low | Medium | Use database unique constraint, handle 409 gracefully |
| User loses place on page refresh | Medium | Medium | Persist playback state in localStorage |
| Mobile audio autoplay restrictions | Medium | High | Require explicit user interaction to start playback |
| Network interruption during playback | Medium | Medium | Browser handles buffering for S3 URLs, show reconnection UI |
| Audio URL confidentiality (leaked URLs) | Medium | Low | 24h URL expiry limits exposure window; HTTPS-only delivery prevents interception; recommend adding audit logging for URL generation in future iteration |
| Upstream session data unavailable | High | Medium | Open Questions 1, 2, 5 must be resolved before implementation; feature depends on existing session/audio data |

---

## 8. Open Questions (Blocking Dependencies)

The following questions must be resolved with stakeholders before implementation can begin:

1. **Audio Storage Location** (BLOCKING): Where are audio files currently stored? Need to confirm S3 bucket name, region, and IAM access patterns for generating pre-signed URLs.

2. **Existing Session Model** (BLOCKING): Does a `coaching_sessions` table already exist? If so, what columns exist vs. need to be added? If not, what upstream system will populate session records?

3. **Authentication System**: What is the current auth mechanism? Need to integrate with existing user identity for authorization checks.

4. **Audio Format**: Are sessions recorded in MP3 or another format? May need transcoding pipeline for browser compatibility.

5. **Session Creation Pipeline** (BLOCKING): How are sessions created and audio files uploaded? This spec assumes sessions already exist with valid audio_file_key values. The upstream system or migration strategy must be documented separately.

6. **Maximum Session Length**: Is there a maximum session duration? Affects bookmark timestamp validation upper bound.

7. **Bookmark Limit**: Should there be a maximum number of bookmarks per session? (Recommend: no limit for v1, monitor usage)

8. **Mobile App**: Is this web-only or also needed for mobile apps? Affects whether React Native audio considerations are needed.

---

## 9. Frontend Component Specifications

### 9.1 SessionListView

```typescript
interface SessionListViewProps {
  onSessionSelect: (sessionId: string) => void;
}

interface SessionListState {
  sessions: SessionListItem[];
  loading: boolean;
  error: string | null;
  pagination: {
    page: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
  filters: {
    status: SessionStatus | null;
    sortBy: 'started_at' | 'duration_seconds' | 'title';
    sortOrder: 'asc' | 'desc';
  };
}

// Display format:
// ┌─────────────────────────────────────────────────────────────┐
// │ Your Coaching Sessions                          [Filter ▼] │
// ├─────────────────────────────────────────────────────────────┤
// │ ┌─────────────────────────────────────────────────────────┐ │
// │ │ Career Transition Coaching                              │ │
// │ │ Dec 10, 2025 • 1:00:00 • 🔖 5 bookmarks                 │ │
// │ │ Coach: Sarah Johnson                                    │ │
// │ └─────────────────────────────────────────────────────────┘ │
// │ ┌─────────────────────────────────────────────────────────┐ │
// │ │ Leadership Development                                   │ │
// │ │ Dec 8, 2025 • 45:30 • 🔖 2 bookmarks                    │ │
// │ │ Coach: Michael Chen                                     │ │
// │ └─────────────────────────────────────────────────────────┘ │
// │                                                             │
// │ ◀ 1 2 3 ... 5 ▶                                            │
// └─────────────────────────────────────────────────────────────┘
```

### 9.2 AudioPlayer

```typescript
interface AudioPlayerProps {
  sessionId: string;
  audioUrl: string;  // Pre-signed S3 URL from session detail
  duration: number;
  bookmarks: Bookmark[];
  onTimeUpdate: (time: number) => void;
  onBookmarkClick: (bookmark: Bookmark) => void;
  onAudioError: (error: Error) => void;  // For handling expired URLs
}

interface AudioPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffered: number;
  volume: number;
  playbackSpeed: number;
  isLoading: boolean;
  error: string | null;
}

// Supported playback speeds
const PLAYBACK_SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

// Display format:
// ┌─────────────────────────────────────────────────────────────┐
// │                    Career Transition Coaching               │
// │                                                             │
// │  ●────────────────────────○──────────────────────────────  │
// │  ^                        ^                                 │
// │  0:00                   5:30                          1:00:00
// │                          ↑                                  │
// │                    Current Position                         │
// │                                                             │
// │       ⏮️    ⏪    ▶️/⏸️    ⏩    ⏭️       🔊 ▬▬▬▬○▬  1.0x │
// │                                                             │
// └─────────────────────────────────────────────────────────────┘
```

### 9.3 BookmarkTimeline

```typescript
interface BookmarkTimelineProps {
  sessionId: string;
  duration: number;
  bookmarks: Bookmark[];
  currentTime: number;
  onBookmarkClick: (timestamp: number) => void;
  onBookmarkAdd: (timestamp: number, label: string) => void;
  onBookmarkEdit: (bookmarkId: string, label: string) => void;
  onBookmarkDelete: (bookmarkId: string) => void;
}

// Display format:
// ┌─────────────────────────────────────────────────────────────┐
// │ Bookmarks (5)                                    [+ Add]    │
// ├─────────────────────────────────────────────────────────────┤
// │                                                             │
// │  ├──●────────●─────────────●──────────●────────────●──────┤ │
// │     ↑        ↑             ↑          ↑            ↑        │
// │   0:45     5:30         15:00      28:45        52:30       │
// │                                                             │
// │ ┌─────────────────────────────────────────────────────────┐ │
// │ │ 🔖 5:30  Key insight about networking              [✏️❌] │ │
// │ │ 🔖 15:00 Action item: Update resume               [✏️❌] │ │
// │ │ 🔖 28:45 Follow-up question for next session      [✏️❌] │ │
// │ └─────────────────────────────────────────────────────────┘ │
// └─────────────────────────────────────────────────────────────┘
```

**Add Bookmark UX Flow:**

1. **Trigger**: User clicks the "[+ Add]" button in the BookmarkTimeline header
2. **Timestamp capture**: The component captures `currentTime` from the AudioPlayer at the moment of click (playback continues unless user pauses)
3. **Label entry**: A modal dialog appears with:
   - Pre-filled timestamp display (e.g., "Bookmark at 5:30")
   - Text input for label (placeholder: "What's important here?")
   - "Cancel" and "Save" buttons
4. **Validation**: Label must be 1-500 characters; empty labels show inline error
5. **Save**: On "Save", calls `onBookmarkAdd(capturedTimestamp, label.trim())`
6. **Feedback**: 
   - Optimistic UI: Bookmark appears immediately in timeline
   - On API success: Bookmark persists with server-assigned ID
   - On API error (e.g., 409 duplicate): Show toast "A bookmark already exists at this time" and remove optimistic entry
7. **Keyboard support**: Enter to save, Escape to cancel

**Alternative quick-add**: Double-clicking the timeline bar at any position creates a bookmark at that timestamp with label "Bookmark at {time}", which can be edited immediately.

---

## 10. Implementation Notes

### 10.1 Audio Service Implementation

```python
# audio_service.py

from datetime import timedelta
import boto3
from botocore.config import Config

class AudioService:
    """
    Service for generating pre-signed URLs for audio file access.
    
    This service is called by SessionService to generate audio_url values.
    The audio_file_key is never exposed outside the service layer.
    """

    def __init__(self, s3_bucket: str, region: str):
        self.s3_client = boto3.client(
            's3',
            region_name=region,
            config=Config(signature_version='s3v4')
        )
        self.bucket = s3_bucket

    def get_audio_url(self, audio_file_key: str, expires_in: int = 86400) -> str:
        """
        Generate pre-signed URL for audio streaming.

        Args:
            audio_file_key: S3 object key (internal, from CoachingSession)
            expires_in: URL expiry in seconds (default 24 hours)

        Returns:
            Pre-signed URL for direct S3 audio access
            
        Note:
            The returned URL supports HTTP Range requests for seeking,
            handled natively by S3. No proxy endpoint is needed.
        """
        return self.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket,
                'Key': audio_file_key,
            },
            ExpiresIn=expires_in,
        )
```

### 10.2 Bookmark Validation

```python
# bookmark_service.py

class BookmarkService:
    """Service for bookmark operations."""

    def __init__(
        self,
        bookmark_repo: BookmarkRepository,
        session_repo: SessionRepository,
    ):
        self.bookmark_repo = bookmark_repo
        self.session_repo = session_repo

    def create_bookmark(
        self,
        user_id: str,
        session_id: str,
        timestamp_seconds: float,
        label: str,
    ) -> Bookmark:
        """
        Create a bookmark with validation.

        Args:
            user_id: User creating the bookmark
            session_id: Session to bookmark
            timestamp_seconds: Position in audio
            label: Bookmark label

        Returns:
            Created Bookmark

        Raises:
            ValidationError: If validation fails
            NotFoundError: If session not found
            DuplicateError: If bookmark exists at timestamp
        """
        # Validate label
        label = label.strip()
        if not label:
            raise ValidationError("label", "Label cannot be empty")
        if len(label) > 500:
            raise ValidationError("label", "Label must be 500 characters or less")

        # Validate timestamp
        if timestamp_seconds < 0:
            raise ValidationError("timestamp_seconds", "Timestamp cannot be negative")

        # Get session and validate ownership
        session = self.session_repo.get_by_id(session_id)
        if not session or session.user_id != user_id:
            raise NotFoundError("Session not found")

        # Validate timestamp is within session duration
        if timestamp_seconds > session.duration_seconds:
            raise ValidationError(
                "timestamp_seconds",
                f"Timestamp exceeds session duration ({session.duration_seconds}s)"
            )

        # Check for duplicate
        existing = self.bookmark_repo.get_by_timestamp(
            session_id=session_id,
            user_id=user_id,
            timestamp_seconds=timestamp_seconds,
        )
        if existing:
            raise DuplicateError("A bookmark already exists at this timestamp")

        # Create bookmark
        bookmark = Bookmark(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            timestamp_seconds=timestamp_seconds,
            label=label,
        )

        return self.bookmark_repo.create(bookmark)
```

### 10.3 Frontend Audio Hook

```typescript
// useAudioPlayer.ts

import { useState, useRef, useEffect, useCallback } from 'react';

interface UseAudioPlayerOptions {
  audioUrl: string;  // Pre-signed S3 URL
  onTimeUpdate?: (time: number) => void;
  onEnded?: () => void;
  onError?: (error: Error) => void;
}

interface UseAudioPlayerReturn {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffered: number;
  volume: number;
  playbackSpeed: number;
  isLoading: boolean;
  error: string | null;
  play: () => Promise<void>;
  pause: () => void;
  seek: (time: number) => void;
  setVolume: (volume: number) => void;
  setPlaybackSpeed: (speed: number) => void;
}

export function useAudioPlayer(options: UseAudioPlayerOptions): UseAudioPlayerReturn {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [volume, setVolumeState] = useState(1);
  const [playbackSpeed, setPlaybackSpeedState] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const audio = new Audio(options.audioUrl);
    audioRef.current = audio;

    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration);
      setIsLoading(false);
    });

    audio.addEventListener('timeupdate', () => {
      setCurrentTime(audio.currentTime);
      options.onTimeUpdate?.(audio.currentTime);
    });

    audio.addEventListener('progress', () => {
      if (audio.buffered.length > 0) {
        setBuffered(audio.buffered.end(audio.buffered.length - 1));
      }
    });

    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      options.onEnded?.();
    });

    audio.addEventListener('error', () => {
      // Check if it's a 403 (expired URL)
      const errorMsg = audio.error?.code === MediaError.MEDIA_ERR_NETWORK
        ? 'Audio URL may have expired. Please refresh.'
        : 'Failed to load audio';
      setError(errorMsg);
      setIsLoading(false);
      options.onError?.(new Error(errorMsg));
    });

    // Restore previous playback state from localStorage
    const savedState = localStorage.getItem(`playback_${options.audioUrl}`);
    if (savedState) {
      const { time, volume: savedVolume, speed } = JSON.parse(savedState);
      audio.currentTime = time;
      audio.volume = savedVolume;
      audio.playbackRate = speed;
      setVolumeState(savedVolume);
      setPlaybackSpeedState(speed);
    }

    return () => {
      // Save playback state
      localStorage.setItem(`playback_${options.audioUrl}`, JSON.stringify({
        time: audio.currentTime,
        volume: audio.volume,
        speed: audio.playbackRate,
      }));
      audio.pause();
    };
  }, [options.audioUrl]);

  const play = useCallback(async () => {
    if (audioRef.current) {
      try {
        await audioRef.current.play();
        setIsPlaying(true);
      } catch (err) {
        setError('Playback failed. Please try again.');
      }
    }
  }, []);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, Math.min(time, duration));
    }
  }, [duration]);

  const setVolume = useCallback((vol: number) => {
    if (audioRef.current) {
      audioRef.current.volume = Math.max(0, Math.min(1, vol));
      setVolumeState(vol);
    }
  }, []);

  const setPlaybackSpeed = useCallback((speed: number) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
      setPlaybackSpeedState(speed);
    }
  }, []);

  return {
    isPlaying,
    currentTime,
    duration,
    buffered,
    volume,
    playbackSpeed,
    isLoading,
    error,
    play,
    pause,
    seek,
    setVolume,
    setPlaybackSpeed,
  };
}
```

### 10.4 Audio Delivery Strategy

**Decision: Pre-signed S3 URLs (not proxy streaming)**

The frontend receives a pre-signed S3 URL in the session detail response and uses it directly with the HTML5 audio element. There is no backend proxy endpoint for streaming audio bytes.

**Rationale:**
1. **Performance**: Direct S3/CDN access is faster than proxying through the backend
2. **Scalability**: No backend compute required for audio delivery; S3 handles all streaming
3. **Range requests**: S3 natively supports HTTP Range headers for seeking without custom code
4. **Caching**: CloudFront/S3 caching is more efficient than backend caching
5. **Cost**: Reduces backend bandwidth and compute costs

**URL Refresh Strategy:**
- URLs have 24-hour expiry (sufficient for typical session playback)
- If the audio element receives a 403 error during playback, the frontend should:
  1. Pause playback
  2. Re-fetch the session detail to get a fresh audio_url
  3. Update the audio element source
  4. Resume from the previous timestamp

---

## 11. Performance Considerations

### 11.1 Audio Loading Strategy

1. **Progressive Loading**: S3 pre-signed URLs support streaming; browser buffers automatically
2. **Preload Metadata**: Set audio preload to "metadata" to get duration without full download
3. **Range Requests**: S3 handles byte-range requests natively for seeking
4. **CDN Caching**: Optional CloudFront distribution for frequently accessed sessions

### 11.2 Session List Optimization

1. **Pagination**: Load 20 sessions at a time, not all at once
2. **Virtual Scrolling**: For users with 100+ sessions, implement virtual list
3. **Bookmark Count**: Include in list query to avoid N+1 queries
4. **Index Usage**: Ensure `user_id, started_at DESC` index is used

### 11.3 Bookmark Performance

1. **Batch Loading**: Load all bookmarks for a session in one query
2. **Optimistic Updates**: Update UI before server confirmation
3. **Debounce Edits**: Debounce label edit saves to reduce API calls

### 11.4 Observability & Metrics

Each success criterion from Section 1.3 will be instrumented as follows:

| Metric | Instrumentation Method | Alert Threshold |
|--------|----------------------|-----------------|
| Session list load time | Frontend Performance API: `performance.measure()` from component mount to data rendered; emit via analytics beacon | p95 > 2s |
| Audio playback start | Frontend: measure from `play()` call to `canplay` event; log to analytics | p95 > 3s |
| Bookmark creation latency | Backend: structured log with request duration; emit StatsD/Prometheus histogram | p95 > 500ms |
| Bookmark retrieval latency | Backend: structured log with request duration; emit StatsD/Prometheus histogram | p95 > 500ms |
| Playback controls responsiveness | Frontend: measure from user action to audio element state change | p95 > 200ms |
| Session list accuracy | Backend: periodic audit job comparing user sessions count vs. displayed count | Any mismatch |

**Implementation:**

1. **Frontend metrics**: Use existing analytics library (or add lightweight beacon) to report timing data on:
   - Page load performance (`PerformanceObserver` for LCP, FCP)
   - Audio player events (load, play, seek, error)
   - User interactions (bookmark add/edit/delete)

2. **Backend metrics**: Add structured logging with timing data to each endpoint:
   ```python
   # Example: session_service.py
   import time
   import structlog
   
   logger = structlog.get_logger()
   
   def list_sessions(self, user_id: str, ...):
       start = time.perf_counter()
       result = self._do_list_sessions(user_id, ...)
       duration_ms = (time.perf_counter() - start) * 1000
       logger.info("list_sessions", user_id=user_id, duration_ms=duration_ms, count=len(result))
       return result
   ```

3. **Dashboard**: Create Grafana/Datadog dashboard with:
   - p50, p95, p99 latency for each endpoint
   - Error rate by endpoint
   - Audio playback success/failure rate
   - Bookmark operations per user (detect anomalies)

4. **Alerts**: Configure alerts for:
   - Latency thresholds exceeded (see table above)
   - Error rate > 1% for any endpoint
   - Audio 403 errors spike (indicates URL generation issues)

---

## 12. Security Considerations

### 12.1 Authorization

- All endpoints require authenticated user
- Users can only access their own sessions and bookmarks
- Return 404 (not 403) for unauthorized access to prevent enumeration
- Audio URLs use pre-signed tokens with 24h expiry

### 12.2 Input Validation

- Sanitize bookmark labels to prevent XSS
- Validate UUIDs are properly formatted
- Limit label length to 500 characters
- Validate timestamp is within session bounds

### 12.3 Rate Limiting

- Bookmark creation: 60 per minute per user
- Session list: 30 per minute per user
- Session detail (includes URL generation): 60 per minute per user

### 12.4 Audio URL Security

- Pre-signed URLs expire after 24 hours, limiting exposure window
- HTTPS-only delivery prevents URL interception
- URLs are user-specific (tied to session ownership verification at generation time)
- Future consideration: Add audit logging for URL generation to detect anomalous access patterns