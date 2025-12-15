# Engineering Spec: User Activity Dashboard

## 1. Overview

### 1.1 Purpose

The User Activity Dashboard provides users with visual insights into their activity patterns over time. It enables users to understand when they are most productive, track weekly and monthly trends, and export their data for personal analysis. The dashboard operates offline after initial load, respecting the 30-day data retention limit.

### 1.2 Scope

**In Scope:**
- Daily, weekly, and monthly activity visualization with interactive charts
- Peak productivity hours analysis and display
- CSV data export functionality
- Offline-first architecture with service worker caching
- Durable offline event collection with background sync
- Mobile-responsive design
- 30-day rolling data window with automatic cleanup across all storage layers
- Real-time activity data aggregation
- Local storage for offline access with 30-day retention enforcement
- Timezone-aware data presentation

**Out of Scope:**
- Historical data beyond 30 days
- Cross-device activity synchronization
- Machine learning-based productivity predictions
- Team/organization-level analytics
- Integration with external calendar services
- Activity data from third-party applications

### 1.3 Success Criteria

| Criterion | Metric | Target |
|-----------|--------|--------|
| Dashboard load time | Initial render (P95) | < 2 seconds |
| User engagement | Weekly active users viewing dashboard | > 30% |
| Export success | CSV export completion rate | > 99% |
| Offline reliability | Dashboard loads without network | 100% after initial visit |
| Event collection reliability | Events captured offline delivered | > 99.5% |
| Data freshness | Activity update delay | < 5 minutes |
| Mobile usability | Lighthouse mobile score | > 90 |

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         User Activity Dashboard                              │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────┐
                         │   User's Browser    │
                         └──────────┬──────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  Service Worker   │   │   React App       │   │   IndexedDB       │
│  (Offline Cache   │   │   (Dashboard UI)  │   │   (Local Storage  │
│   + Background    │   │                   │   │    + Event Queue) │
│   Sync)           │   │                   │   │                   │
└───────────────────┘   └─────────┬─────────┘   └───────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │    REST API Layer       │
                    │   /api/v1/activity/*    │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────────┐
        │                       │                           │
        ▼                       ▼                           ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  Activity         │   │  Aggregation      │   │  Export           │
│  Collector        │   │  Service          │   │  Service          │
└───────────────────┘   └───────────────────┘   └───────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │     PostgreSQL          │
                    │  (Activity Events)      │
                    │  (30-day retention)     │
                    └─────────────────────────┘
```

### 2.2 Components

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| Dashboard UI | Interactive charts and visualizations | React + D3.js/Chart.js |
| Service Worker | Cache dashboard assets for offline use, background sync for events | Workbox |
| IndexedDB Store | Store activity data locally for offline access (30-day max), durable event queue | idb library |
| Activity Collector | Capture user activity events with offline support | JavaScript SDK |
| Aggregation Service | Pre-compute hourly/daily/weekly/monthly rollups | Python background job |
| Export Service | Generate CSV files from activity data | Python + pandas |
| Activity Store | Persist raw and aggregated activity data | PostgreSQL with partitioning |
| Retention Worker | Purge data older than 30 days from all tables | PostgreSQL scheduled job |

### 2.3 Data Flow

1. **Activity Collection**
   - User actions trigger activity events in the application
   - Activity Collector queues events in IndexedDB (durable storage)
   - When online, batches sent to `/api/v1/activity/events` endpoint
   - When offline, events remain queued until connectivity restored
   - Background Sync API triggers delivery when online
   - Events stored in `activity_events` table with user_id, timestamp, event_type

2. **Aggregation Pipeline**
   - Hourly job runs every 5 minutes: aggregates raw events into hourly buckets
   - Daily job runs at 00:30 UTC: aggregates hourly data into daily rollups
   - Weekly job runs at 01:00 UTC: aggregates daily data into weekly rollups
   - Monthly job runs at 01:30 UTC: aggregates daily data into monthly rollups
   - All aggregations stored in UTC; converted to user timezone at read time

3. **Dashboard Loading**
   - Client requests aggregated data from `/api/v1/activity/summary`
   - Server converts UTC data to user's timezone preference
   - Server returns pre-computed aggregations (fast query via composite indexes)
   - Client caches response in IndexedDB with timestamp
   - Service Worker caches static assets
   - Subsequent loads use cached data if offline

4. **Data Export**
   - User requests export via `/api/v1/activity/export`
   - Server streams CSV data for the requested date range
   - Maximum export range: 30 days (entire retention window)
   - Export files deleted after 24 hours

5. **Retention Enforcement (All Storage Layers)**
   - Daily scheduled job at 02:00 UTC
   - Deletes partitions older than 30 days from activity_events
   - Deletes rows older than 30 days from activity_hourly, activity_daily
   - Deletes weekly rollups where period_end < cutoff_date
   - Deletes monthly rollups where period_end < cutoff_date
   - Deletes expired export files from storage
   - Updates `activity_retention_log` for audit trail
   - Client-side: IndexedDB cache entries expire after 30 days

---

## 3. Data Models

### 3.1 New Models

```python
from dataclasses import dataclass, field
from datetime import datetime, date, time
from enum import Enum
from typing import Optional
from decimal import Decimal
import uuid


class ActivityEventType(Enum):
    """Types of user activity events."""
    PAGE_VIEW = "page_view"
    FEATURE_USE = "feature_use"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    ACTION = "action"
    NAVIGATION = "navigation"


class TimeGranularity(Enum):
    """Time granularity for activity aggregations."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ExportStatus(Enum):
    """Status of an export job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class ActivityEvent:
    """Raw activity event from user action."""
    event_id: str                           # UUID
    user_id: str                            # User who performed action
    event_type: ActivityEventType           # Type of activity
    event_name: str                         # Specific event identifier
    timestamp: datetime                     # When event occurred (UTC)
    session_id: Optional[str] = None        # Browser session identifier
    page_path: Optional[str] = None         # URL path if applicable
    metadata: dict = field(default_factory=dict)  # Additional context
    duration_ms: Optional[int] = None       # Duration for timed events
    client_timestamp: Optional[datetime] = None  # Original client time for offline events

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "event_type": self.event_type.value,
            "event_name": self.event_name,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "page_path": self.page_path,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "client_timestamp": self.client_timestamp.isoformat() if self.client_timestamp else None,
        }


@dataclass
class HourlyActivityRollup:
    """Hourly aggregation of user activity."""
    user_id: str
    hour_start: datetime                    # Start of the hour (truncated, UTC)
    event_count: int                        # Total events in this hour
    session_count: int                      # Distinct sessions
    active_minutes: int                     # Minutes with at least one event
    page_views: int                         # Count of page_view events
    feature_uses: int                       # Count of feature_use events
    top_pages: list[str] = field(default_factory=list)  # Top 5 pages by views
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def productivity_score(self) -> float:
        """Calculate productivity score (0-100) for this hour."""
        if self.active_minutes == 0:
            return 0.0
        # Score based on activity density and feature engagement
        density = min(self.active_minutes / 60.0, 1.0) * 50
        engagement = min(self.feature_uses / 10.0, 1.0) * 50
        return round(density + engagement, 2)


@dataclass
class DailyActivityRollup:
    """Daily aggregation of user activity."""
    user_id: str
    date: date                              # Calendar date (UTC)
    total_events: int                       # Total events for the day
    total_sessions: int                     # Total distinct sessions
    active_hours: int                       # Hours with at least one event
    active_minutes: int                     # Total active minutes
    peak_hour: int                          # Hour (0-23) with most activity (UTC)
    peak_hour_events: int                   # Event count in peak hour
    page_views: int
    feature_uses: int
    first_activity: Optional[time] = None   # Time of first event (UTC)
    last_activity: Optional[time] = None    # Time of last event (UTC)
    hourly_breakdown: list[int] = field(default_factory=lambda: [0] * 24)  # Events per hour (UTC)

    @property
    def productivity_score(self) -> float:
        """Calculate daily productivity score (0-100)."""
        if self.active_hours == 0:
            return 0.0
        # Score based on active hours and engagement
        hours_score = min(self.active_hours / 8.0, 1.0) * 40
        engagement_score = min(self.feature_uses / 50.0, 1.0) * 40
        consistency_score = self._consistency_bonus() * 20
        return round(hours_score + engagement_score + consistency_score, 2)

    def _consistency_bonus(self) -> float:
        """Bonus for consistent activity throughout the day."""
        if sum(self.hourly_breakdown) == 0:
            return 0.0
        non_zero_hours = sum(1 for h in self.hourly_breakdown if h > 0)
        return min(non_zero_hours / 8.0, 1.0)


@dataclass
class WeeklyActivityRollup:
    """Weekly aggregation of user activity."""
    user_id: str
    week_start: date                        # Monday of the week
    week_end: date                          # Sunday of the week (inclusive)
    total_events: int
    total_sessions: int
    active_days: int                        # Days with at least one event
    total_active_hours: int
    total_active_minutes: int
    peak_day: int                           # Day of week (0=Mon) with most activity
    peak_day_events: int
    daily_breakdown: list[int] = field(default_factory=lambda: [0] * 7)  # Events per day
    hourly_heatmap: list[list[int]] = field(
        default_factory=lambda: [[0] * 24 for _ in range(7)]
    )  # 7 days x 24 hours (UTC)

    @property
    def average_daily_score(self) -> float:
        """Average productivity score across active days."""
        if self.active_days == 0:
            return 0.0
        return round(sum(self.daily_breakdown) / self.active_days / 100, 2)


@dataclass
class MonthlyActivityRollup:
    """Monthly aggregation of user activity."""
    user_id: str
    month_start: date                       # First day of the month
    month_end: date                         # Last day of the month (inclusive)
    total_events: int                       # Total events for the month
    total_sessions: int                     # Total distinct sessions
    active_days: int                        # Days with at least one event
    total_active_hours: int                 # Total hours with activity
    total_active_minutes: int               # Total active minutes
    peak_week: int                          # Week of month (1-5) with most activity
    peak_week_events: int                   # Event count in peak week
    peak_day_of_week: int                   # Day of week (0=Mon) with most activity overall
    page_views: int
    feature_uses: int
    weekly_breakdown: list[int] = field(default_factory=lambda: [0] * 5)  # Events per week (max 5 weeks)
    daily_breakdown: list[int] = field(default_factory=lambda: [0] * 31)  # Events per day of month
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def productivity_score(self) -> float:
        """Calculate monthly productivity score (0-100)."""
        if self.active_days == 0:
            return 0.0
        # Score based on active days, engagement, and consistency
        days_score = min(self.active_days / 20.0, 1.0) * 35  # ~20 working days ideal
        engagement_score = min(self.feature_uses / 200.0, 1.0) * 35
        consistency_score = self._consistency_bonus() * 30
        return round(days_score + engagement_score + consistency_score, 2)

    def _consistency_bonus(self) -> float:
        """Bonus for consistent activity throughout the month."""
        days_in_month = sum(1 for d in self.daily_breakdown if d >= 0)  # Actual days in month
        if days_in_month == 0:
            return 0.0
        active_ratio = self.active_days / min(days_in_month, 22)  # Compare to ~22 working days
        return min(active_ratio, 1.0)

    @property
    def average_daily_events(self) -> float:
        """Average events per active day."""
        if self.active_days == 0:
            return 0.0
        return round(self.total_events / self.active_days, 1)


@dataclass
class PeakHoursAnalysis:
    """Analysis of user's peak productivity hours."""
    user_id: str
    analysis_period_days: int               # Number of days analyzed
    timezone: str                           # User's timezone for this analysis
    peak_hours: list[int]                   # Top 3 most productive hours (0-23, local time)
    peak_hours_scores: list[float]          # Productivity scores for peak hours
    peak_days: list[int]                    # Top 3 most productive days (0=Mon)
    average_start_time: time                # Average first activity time (local)
    average_end_time: time                  # Average last activity time (local)
    most_active_period: str                 # "morning", "afternoon", "evening", "night"
    consistency_score: float                # How consistent the pattern is (0-100)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "user_id": self.user_id,
            "analysis_period_days": self.analysis_period_days,
            "timezone": self.timezone,
            "peak_hours": self.peak_hours,
            "peak_hours_scores": self.peak_hours_scores,
            "peak_days": self.peak_days,
            "average_start_time": self.average_start_time.isoformat() if self.average_start_time else None,
            "average_end_time": self.average_end_time.isoformat() if self.average_end_time else None,
            "most_active_period": self.most_active_period,
            "consistency_score": self.consistency_score,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ExportJob:
    """Represents a data export request."""
    export_id: str                          # UUID
    user_id: str
    status: ExportStatus
    start_date: date                        # Export range start
    end_date: date                          # Export range end
    file_format: str = "csv"                # Only CSV supported initially
    include_raw_events: bool = False        # Include raw events or just aggregates
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    file_path: Optional[str] = None         # Path to generated file
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    expires_at: Optional[datetime] = None   # When download link expires (24 hours)


@dataclass
class UserDashboardPreferences:
    """User preferences for dashboard display."""
    user_id: str
    default_view: TimeGranularity = TimeGranularity.WEEKLY
    timezone: str = "UTC"
    week_starts_on: int = 0                 # 0=Monday, 6=Sunday
    chart_type: str = "bar"                 # "bar", "line", "area"
    show_productivity_score: bool = True
    show_peak_hours: bool = True
    show_comparison: bool = True            # Compare to previous period
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

### 3.2 Schema Changes

**PostgreSQL Migrations:**

```sql
-- Migration: 001_create_activity_events
-- Using table partitioning for efficient retention management
CREATE TABLE activity_events (
    event_id UUID NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    session_id VARCHAR(64),
    page_path VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    duration_ms INT,
    client_timestamp TIMESTAMPTZ,  -- Original client time for offline events
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (event_id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create partitions for current and next 30 days
-- Additional partitions created by scheduled job
CREATE TABLE activity_events_default PARTITION OF activity_events DEFAULT;

-- Indexes for common queries (user_id first for efficient filtering)
CREATE INDEX idx_activity_events_user_ts ON activity_events(user_id, timestamp DESC);
CREATE INDEX idx_activity_events_type ON activity_events(event_type, timestamp DESC);
CREATE INDEX idx_activity_events_session ON activity_events(session_id, timestamp DESC);


-- Migration: 002_create_activity_hourly
CREATE TABLE activity_hourly (
    user_id VARCHAR(64) NOT NULL,
    hour_start TIMESTAMPTZ NOT NULL,
    event_count INT NOT NULL DEFAULT 0,
    session_count INT NOT NULL DEFAULT 0,
    active_minutes INT NOT NULL DEFAULT 0,
    page_views INT NOT NULL DEFAULT 0,
    feature_uses INT NOT NULL DEFAULT 0,
    top_pages JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, hour_start)
);

-- Primary access pattern: user's hourly data for a time range
CREATE INDEX idx_activity_hourly_user_ts ON activity_hourly(user_id, hour_start DESC);
-- Secondary: time-based queries for retention cleanup
CREATE INDEX idx_activity_hourly_ts ON activity_hourly(hour_start DESC);


-- Migration: 003_create_activity_daily
CREATE TABLE activity_daily (
    user_id VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    total_events INT NOT NULL DEFAULT 0,
    total_sessions INT NOT NULL DEFAULT 0,
    active_hours INT NOT NULL DEFAULT 0,
    active_minutes INT NOT NULL DEFAULT 0,
    peak_hour SMALLINT,
    peak_hour_events INT DEFAULT 0,
    page_views INT NOT NULL DEFAULT 0,
    feature_uses INT NOT NULL DEFAULT 0,
    first_activity TIME,
    last_activity TIME,
    hourly_breakdown INT[] DEFAULT ARRAY_FILL(0, ARRAY[24]),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, date)
);

-- Primary access pattern: user's daily data for a date range
CREATE INDEX idx_activity_daily_user_date ON activity_daily(user_id, date DESC);
-- Secondary: date-based queries for retention cleanup
CREATE INDEX idx_activity_daily_date ON activity_daily(date DESC);


-- Migration: 004_create_activity_weekly
CREATE TABLE activity_weekly (
    user_id VARCHAR(64) NOT NULL,
    week_start DATE NOT NULL,  -- Always a Monday
    week_end DATE NOT NULL,    -- Always a Sunday (inclusive)
    total_events INT NOT NULL DEFAULT 0,
    total_sessions INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    total_active_hours INT NOT NULL DEFAULT 0,
    total_active_minutes INT NOT NULL DEFAULT 0,
    peak_day SMALLINT,
    peak_day_events INT DEFAULT 0,
    daily_breakdown INT[] DEFAULT ARRAY_FILL(0, ARRAY[7]),
    hourly_heatmap INT[][] DEFAULT ARRAY_FILL(0, ARRAY[7, 24]),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, week_start),
    CONSTRAINT valid_week_start CHECK (EXTRACT(DOW FROM week_start) = 1),  -- Must be Monday
    CONSTRAINT valid_week_end CHECK (week_end = week_start + INTERVAL '6 days')
);

-- Primary access pattern: user's weekly data for a date range
CREATE INDEX idx_activity_weekly_user_date ON activity_weekly(user_id, week_start DESC);
-- Secondary: date-based queries for retention cleanup (uses week_end)
CREATE INDEX idx_activity_weekly_end ON activity_weekly(week_end DESC);


-- Migration: 004b_create_activity_monthly
CREATE TABLE activity_monthly (
    user_id VARCHAR(64) NOT NULL,
    month_start DATE NOT NULL,  -- Always first day of month
    month_end DATE NOT NULL,    -- Always last day of month (inclusive)
    total_events INT NOT NULL DEFAULT 0,
    total_sessions INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    total_active_hours INT NOT NULL DEFAULT 0,
    total_active_minutes INT NOT NULL DEFAULT 0,
    peak_week SMALLINT,                     -- Week of month (1-5)
    peak_week_events INT DEFAULT 0,
    peak_day_of_week SMALLINT,              -- Day of week (0=Mon) with most activity
    page_views INT NOT NULL DEFAULT 0,
    feature_uses INT NOT NULL DEFAULT 0,
    weekly_breakdown INT[] DEFAULT ARRAY_FILL(0, ARRAY[5]),  -- Up to 5 weeks per month
    daily_breakdown INT[] DEFAULT ARRAY_FILL(0, ARRAY[31]),  -- Up to 31 days
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, month_start),
    CONSTRAINT valid_month_start CHECK (EXTRACT(DAY FROM month_start) = 1),  -- Must be first of month
    CONSTRAINT valid_month_end CHECK (
        month_end = (month_start + INTERVAL '1 month' - INTERVAL '1 day')::DATE
    )
);

-- Primary access pattern: user's monthly data
CREATE INDEX idx_activity_monthly_user_date ON activity_monthly(user_id, month_start DESC);
-- Secondary: date-based queries for retention cleanup (uses month_end)
CREATE INDEX idx_activity_monthly_end ON activity_monthly(month_end DESC);


-- Migration: 005_create_export_jobs
CREATE TABLE export_jobs (
    export_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    file_format VARCHAR(10) NOT NULL DEFAULT 'csv',
    include_raw_events BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    file_path VARCHAR(500),
    file_size_bytes BIGINT,
    row_count INT,
    error_message TEXT,
    expires_at TIMESTAMPTZ,  -- 24 hours after completion

    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    CONSTRAINT valid_date_range CHECK (end_date >= start_date),
    CONSTRAINT max_date_range CHECK (end_date - start_date <= 30)
);

CREATE INDEX idx_export_jobs_user ON export_jobs(user_id, created_at DESC);
CREATE INDEX idx_export_jobs_status ON export_jobs(status) WHERE status IN ('pending', 'processing');
CREATE INDEX idx_export_jobs_expires ON export_jobs(expires_at) WHERE status = 'completed';


-- Migration: 006_create_user_dashboard_preferences
CREATE TABLE user_dashboard_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    default_view VARCHAR(20) NOT NULL DEFAULT 'weekly',
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    week_starts_on SMALLINT NOT NULL DEFAULT 0,
    chart_type VARCHAR(20) NOT NULL DEFAULT 'bar',
    show_productivity_score BOOLEAN NOT NULL DEFAULT true,
    show_peak_hours BOOLEAN NOT NULL DEFAULT true,
    show_comparison BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_default_view CHECK (default_view IN ('hourly', 'daily', 'weekly', 'monthly')),
    CONSTRAINT valid_week_starts CHECK (week_starts_on >= 0 AND week_starts_on <= 6),
    CONSTRAINT valid_chart_type CHECK (chart_type IN ('bar', 'line', 'area'))
);


-- Migration: 007_create_retention_log
CREATE TABLE activity_retention_log (
    id SERIAL PRIMARY KEY,
    execution_date DATE NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    partition_dropped VARCHAR(100),
    rows_deleted BIGINT,
    execution_time_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Migration: 008_create_partition_and_retention_function
CREATE OR REPLACE FUNCTION manage_activity_data_retention()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    old_partition_name TEXT;
    cutoff_date DATE;
    cutoff_timestamp TIMESTAMPTZ;
    deleted_count BIGINT;
    start_time TIMESTAMPTZ;
BEGIN
    cutoff_date := CURRENT_DATE - INTERVAL '30 days';
    cutoff_timestamp := cutoff_date::TIMESTAMPTZ;
    
    -- 1. Create partition for tomorrow (activity_events)
    partition_date := CURRENT_DATE + INTERVAL '1 day';
    partition_name := 'activity_events_' || TO_CHAR(partition_date, 'YYYYMMDD');

    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = partition_name) THEN
        EXECUTE FORMAT(
            'CREATE TABLE %I PARTITION OF activity_events FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_date,
            partition_date + INTERVAL '1 day'
        );
    END IF;

    -- 2. Drop old partitions from activity_events (>30 days)
    FOR old_partition_name IN
        SELECT tablename FROM pg_tables
        WHERE tablename LIKE 'activity_events_%'
        AND tablename ~ '^activity_events_[0-9]{8}$'
        AND TO_DATE(SUBSTRING(tablename FROM '[0-9]{8}$'), 'YYYYMMDD') < cutoff_date
    LOOP
        start_time := clock_timestamp();
        EXECUTE FORMAT('DROP TABLE IF EXISTS %I', old_partition_name);
        
        INSERT INTO activity_retention_log (execution_date, table_name, partition_dropped, execution_time_ms)
        VALUES (CURRENT_DATE, 'activity_events', old_partition_name, 
                EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INT);
    END LOOP;

    -- 3. Delete old rows from activity_hourly (>30 days)
    start_time := clock_timestamp();
    DELETE FROM activity_hourly WHERE hour_start < cutoff_timestamp;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        INSERT INTO activity_retention_log (execution_date, table_name, rows_deleted, execution_time_ms)
        VALUES (CURRENT_DATE, 'activity_hourly', deleted_count,
                EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INT);
    END IF;

    -- 4. Delete old rows from activity_daily (>30 days)
    start_time := clock_timestamp();
    DELETE FROM activity_daily WHERE date < cutoff_date;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        INSERT INTO activity_retention_log (execution_date, table_name, rows_deleted, execution_time_ms)
        VALUES (CURRENT_DATE, 'activity_daily', deleted_count,
                EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INT);
    END IF;

    -- 5. Delete old rows from activity_weekly (only when week_end < cutoff)
    -- This ensures we keep weekly rollups until ALL days in the week are >30 days old
    start_time := clock_timestamp();
    DELETE FROM activity_weekly WHERE week_end < cutoff_date;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        INSERT INTO activity_retention_log (execution_date, table_name, rows_deleted, execution_time_ms)
        VALUES (CURRENT_DATE, 'activity_weekly', deleted_count,
                EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INT);
    END IF;

    -- 6. Delete old rows from activity_monthly (only when month_end < cutoff)
    -- This ensures we keep monthly rollups until ALL days in the month are >30 days old
    start_time := clock_timestamp();
    DELETE FROM activity_monthly WHERE month_end < cutoff_date;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count > 0 THEN
        INSERT INTO activity_retention_log (execution_date, table_name, rows_deleted, execution_time_ms)
        VALUES (CURRENT_DATE, 'activity_monthly', deleted_count,
                EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time)::INT);
    END IF;

    -- 7. Mark expired exports and delete old export files
    UPDATE export_jobs 
    SET status = 'expired' 
    WHERE status = 'completed' AND expires_at < NOW();
    
    -- Note: Physical file deletion handled by separate cleanup job
    -- that reads expired export_jobs and deletes from storage
    
END;
$$ LANGUAGE plpgsql;

-- Schedule daily at 02:00 UTC (requires pg_cron extension)
-- SELECT cron.schedule('manage-activity-retention', '0 2 * * *', 'SELECT manage_activity_data_retention()');


-- Migration: 009_create_export_file_cleanup_function
CREATE OR REPLACE FUNCTION cleanup_expired_export_files()
RETURNS TABLE(file_path VARCHAR, deleted BOOLEAN) AS $$
BEGIN
    -- Returns list of expired export file paths for application to delete from storage
    -- Application should call this, delete files, then update records
    RETURN QUERY
    SELECT ej.file_path, false AS deleted
    FROM export_jobs ej
    WHERE ej.status = 'expired' 
    AND ej.file_path IS NOT NULL;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. API Design

### 4.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/activity/events | Batch submit activity events |
| GET | /api/v1/activity/summary | Get activity summary for dashboard |
| GET | /api/v1/activity/daily | Get daily activity breakdown |
| GET | /api/v1/activity/weekly | Get weekly activity with heatmap |
| GET | /api/v1/activity/monthly | Get monthly activity overview |
| GET | /api/v1/activity/peak-hours | Get peak productivity hours analysis |
| POST | /api/v1/activity/export | Request data export |
| GET | /api/v1/activity/export/{export_id} | Get export job status |
| GET | /api/v1/activity/export/{export_id}/download | Download exported file |
| GET | /api/v1/activity/preferences | Get dashboard preferences |
| PUT | /api/v1/activity/preferences | Update dashboard preferences |

### 4.2 Request/Response Schemas

**POST /api/v1/activity/events**

Request:
```json
{
  "events": [
    {
      "event_type": "page_view",
      "event_name": "dashboard_viewed",
      "timestamp": "2025-12-15T10:30:00Z",
      "client_timestamp": "2025-12-15T10:30:00Z",
      "session_id": "sess_abc123",
      "page_path": "/dashboard",
      "metadata": {
        "referrer": "/home"
      }
    },
    {
      "event_type": "feature_use",
      "event_name": "report_generated",
      "timestamp": "2025-12-15T10:32:00Z",
      "client_timestamp": "2025-12-15T10:32:00Z",
      "session_id": "sess_abc123",
      "duration_ms": 2500,
      "metadata": {
        "report_type": "weekly"
      }
    }
  ],
  "batch_id": "batch_xyz123",
  "queued_at": "2025-12-15T10:30:00Z"
}
```

Response:
```json
{
  "accepted": 2,
  "rejected": 0,
  "batch_id": "batch_xyz123",
  "errors": []
}
```

**GET /api/v1/activity/summary**

Query Parameters:
- `period` (string, optional): "day", "week", "month" (default: "week")
- `timezone` (string, optional): IANA timezone (default: user preference or "UTC")

Response:
```json
{
  "user_id": "usr_123456",
  "period": "week",
  "period_start": "2025-12-09",
  "period_end": "2025-12-15",
  "timezone": "America/New_York",
  "summary": {
    "total_events": 847,
    "total_sessions": 23,
    "active_days": 5,
    "active_hours": 42,
    "active_minutes": 1680,
    "productivity_score": 72.5
  },
  "comparison": {
    "previous_period_events": 792,
    "events_change_percent": 6.9,
    "previous_period_score": 68.2,
    "score_change_percent": 6.3
  },
  "peak_hours": {
    "top_hours": [10, 14, 11],
    "top_hours_local": ["10:00 AM", "2:00 PM", "11:00 AM"],
    "most_active_period": "morning"
  },
  "charts": {
    "daily_breakdown": [
      {"date": "2025-12-09", "events": 156, "score": 71.2},
      {"date": "2025-12-10", "events": 189, "score": 78.5},
      {"date": "2025-12-11", "events": 167, "score": 73.1},
      {"date": "2025-12-12", "events": 0, "score": 0},
      {"date": "2025-12-13", "events": 0, "score": 0},
      {"date": "2025-12-14", "events": 145, "score": 65.8},
      {"date": "2025-12-15", "events": 190, "score": 75.4}
    ]
  },
  "generated_at": "2025-12-15T11:00:00Z",
  "cache_ttl_seconds": 300
}
```

**GET /api/v1/activity/weekly**

Query Parameters:
- `week_start` (date, optional): Start of week (default: current week)
- `timezone` (string, optional): IANA timezone

Response:
```json
{
  "user_id": "usr_123456",
  "week_start": "2025-12-09",
  "week_end": "2025-12-15",
  "timezone": "America/New_York",
  "totals": {
    "events": 847,
    "sessions": 23,
    "active_days": 5,
    "active_hours": 42,
    "active_minutes": 1680
  },
  "peak_day": {
    "day_of_week": 1,
    "day_name": "Tuesday",
    "events": 189
  },
  "daily_breakdown": [
    {"day": 0, "name": "Monday", "events": 156, "hours": 8},
    {"day": 1, "name": "Tuesday", "events": 189, "hours": 9},
    {"day": 2, "name": "Wednesday", "events": 167, "hours": 8},
    {"day": 3, "name": "Thursday", "events": 0, "hours": 0},
    {"day": 4, "name": "Friday", "events": 0, "hours": 0},
    {"day": 5, "name": "Saturday", "events": 145, "hours": 7},
    {"day": 6, "name": "Sunday", "events": 190, "hours": 10}
  ],
  "hourly_heatmap": [
    [0, 0, 0, 0, 0, 0, 8, 12, 18, 25, 32, 28, 15, 22, 30, 28, 18, 12, 8, 5, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 10, 15, 22, 30, 35, 32, 18, 25, 35, 32, 20, 15, 10, 6, 0, 0, 0, 0]
  ],
  "hourly_heatmap_timezone": "America/New_York"
}
```

**GET /api/v1/activity/monthly**

Query Parameters:
- `month_start` (date, optional): First day of month (default: current month)
- `timezone` (string, optional): IANA timezone

Response:
```json
{
  "user_id": "usr_123456",
  "month_start": "2025-12-01",
  "month_end": "2025-12-31",
  "timezone": "America/New_York",
  "totals": {
    "events": 3420,
    "sessions": 89,
    "active_days": 18,
    "active_hours": 156,
    "active_minutes": 6240,
    "productivity_score": 74.2
  },
  "comparison": {
    "previous_month_events": 3180,
    "events_change_percent": 7.5,
    "previous_month_score": 71.8,
    "score_change_percent": 3.3
  },
  "peak_week": {
    "week_number": 2,
    "week_start": "2025-12-09",
    "events": 920
  },
  "peak_day_of_week": {
    "day_of_week": 1,
    "day_name": "Tuesday",
    "average_events": 210
  },
  "weekly_breakdown": [
    {"week": 1, "start": "2025-12-01", "events": 780, "active_days": 4},
    {"week": 2, "start": "2025-12-08", "events": 920, "active_days": 5},
    {"week": 3, "start": "2025-12-15", "events": 870, "active_days": 5},
    {"week": 4, "start": "2025-12-22", "events": 650, "active_days": 3},
    {"week": 5, "start": "2025-12-29", "events": 200, "active_days": 1}
  ],
  "daily_breakdown": [
    {"day": 1, "events": 145, "active": true},
    {"day": 2, "events": 178, "active": true},
    {"day": 3, "events": 0, "active": false}
  ],
  "trends": {
    "best_day": {"date": "2025-12-10", "events": 215, "score": 82.3},
    "average_daily_events": 190,
    "most_productive_time": "10:00 AM - 12:00 PM"
  },
  "generated_at": "2025-12-15T11:00:00Z",
  "cache_ttl_seconds": 600
}
```

**GET /api/v1/activity/peak-hours**

Query Parameters:
- `days` (int, optional): Number of days to analyze (default: 30, max: 30)
- `timezone` (string, optional): IANA timezone (default: user preference)

Response:
```json
{
  "user_id": "usr_123456",
  "analysis_period_days": 30,
  "timezone": "America/New_York",
  "peak_hours": [10, 14, 11],
  "peak_hours_labels": ["10:00 AM", "2:00 PM", "11:00 AM"],
  "peak_hours_scores": [85.2, 78.4, 76.1],
  "peak_days": [1, 2, 0],
  "peak_days_labels": ["Tuesday", "Wednesday", "Monday"],
  "patterns": {
    "most_active_period": "morning",
    "average_start_time": "08:30",
    "average_end_time": "17:45",
    "consistency_score": 72.3
  },
  "insights": [
    {
      "type": "peak_hour",
      "message": "You're most productive at 10:00 AM with 85% productivity score"
    },
    {
      "type": "consistency",
      "message": "Your activity pattern is fairly consistent (72% consistency)"
    },
    {
      "type": "suggestion",
      "message": "Consider scheduling important tasks between 10 AM and 2 PM"
    }
  ],
  "generated_at": "2025-12-15T11:00:00Z"
}
```

**POST /api/v1/activity/export**

Request:
```json
{
  "start_date": "2025-11-15",
  "end_date": "2025-12-15",
  "include_raw_events": false
}
```

Response:
```json
{
  "export_id": "exp_xyz789",
  "status": "pending",
  "start_date": "2025-11-15",
  "end_date": "2025-12-15",
  "include_raw_events": false,
  "estimated_rows": 4200,
  "created_at": "2025-12-15T11:00:00Z"
}
```

**GET /api/v1/activity/export/{export_id}**

Response:
```json
{
  "export_id": "exp_xyz789",
  "status": "completed",
  "start_date": "2025-11-15",
  "end_date": "2025-12-15",
  "include_raw_events": false,
  "created_at": "2025-12-15T11:00:00Z",
  "completed_at": "2025-12-15T11:00:15Z",
  "file_size_bytes": 125000,
  "row_count": 4156,
  "download_url": "/api/v1/activity/export/exp_xyz789/download",
  "expires_at": "2025-12-16T11:00:15Z"
}
```

**GET /api/v1/activity/preferences**

Response:
```json
{
  "user_id": "usr_123456",
  "default_view": "weekly",
  "timezone": "America/New_York",
  "week_starts_on": 0,
  "chart_type": "bar",
  "show_productivity_score": true,
  "show_peak_hours": true,
  "show_comparison": true
}
```

### 4.3 Error Responses

```json
{
  "error": {
    "code": "INVALID_DATE_RANGE",
    "message": "Export date range cannot exceed 30 days",
    "details": {
      "requested_days": 45,
      "max_days": 30
    }
  }
}
```

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| INVALID_REQUEST | 400 | Malformed request body |
| INVALID_DATE_RANGE | 400 | Date range exceeds 30 days or is invalid |
| INVALID_TIMEZONE | 400 | Unknown timezone identifier |
| EXPORT_NOT_FOUND | 404 | Export job does not exist |
| EXPORT_EXPIRED | 410 | Export download link has expired |
| EXPORT_IN_PROGRESS | 409 | Export is still being processed |
| RATE_LIMITED | 429 | Too many export requests (max 5/day) |
| INTERNAL_ERROR | 500 | Internal server error |

---

## 5. Implementation Plan

### 5.1 Tasks

| # | Task | Dependencies | Size | Description |
|---|------|--------------|------|-------------|
| 1 | Create data models | None | M | Implement all dataclasses in `models/activity_models.py` |
| 2 | Database migrations | None | M | Create PostgreSQL tables with partitioning |
| 3 | Activity event repository | 1, 2 | M | Batch insert and query for raw events |
| 4 | Hourly aggregation repository | 1, 2 | S | CRUD for hourly rollups |
| 5 | Daily aggregation repository | 1, 2 | S | CRUD for daily rollups |
| 6 | Weekly aggregation repository | 1, 2 | S | CRUD for weekly rollups |
| 6b | Monthly aggregation repository | 1, 2 | S | CRUD for monthly rollups |
| 7 | Activity collector SDK | 1 | M | JavaScript SDK for client-side event collection with offline support |
| 7b | Offline event queue | 7 | M | IndexedDB-backed durable queue with background sync |
| 8 | Event ingestion endpoint | 3 | S | POST /api/v1/activity/events |
| 9 | Hourly aggregation job | 3, 4 | M | Background job to compute hourly rollups |
| 10 | Daily aggregation job | 4, 5 | M | Background job to compute daily rollups |
| 11 | Weekly aggregation job | 5, 6 | M | Background job to compute weekly rollups |
| 11b | Monthly aggregation job | 5, 6b | M | Background job to compute monthly rollups from daily data |
| 12 | Summary API endpoint | 4, 5, 6, 6b | M | GET /api/v1/activity/summary |
| 12b | Timezone conversion utilities | 1 | S | Helper functions for UTC to local time conversion |
| 13 | Daily API endpoint | 5, 12b | S | GET /api/v1/activity/daily |
| 14 | Weekly API endpoint | 6, 12b | S | GET /api/v1/activity/weekly |
| 15 | Monthly API endpoint | 6b, 12b | S | GET /api/v1/activity/monthly |
| 16 | Peak hours analysis service | 4, 5, 12b | M | Compute peak hours from aggregated data (timezone-aware) |
| 17 | Peak hours API endpoint | 16 | S | GET /api/v1/activity/peak-hours |
| 18 | Export service | 3, 5, 6, 6b | M | Generate CSV exports |
| 19 | Export API endpoints | 18 | S | POST/GET export endpoints |
| 20 | Preferences repository | 1, 2 | S | CRUD for user preferences |
| 21 | Preferences API endpoints | 20 | S | GET/PUT preferences endpoints |
| 22 | Dashboard React component | None | L | Main dashboard UI with charts |
| 23 | Activity charts component | 22 | M | D3.js/Chart.js visualizations |
| 24 | Heatmap component | 22 | M | Weekly activity heatmap |
| 25 | Peak hours component | 22, 23 | S | Peak hours visualization |
| 26 | Export UI component | 22, 19 | S | Export request and download UI |
| 27 | Service worker setup | 22, 7b | M | Workbox configuration for offline + background sync |
| 28 | IndexedDB cache layer | 22 | M | Client-side data caching with 30-day expiration |
| 29 | Mobile responsive styles | 22-26 | M | Responsive CSS for all viewports |
| 30 | Retention management job | 2 | M | Daily job for partition rotation and aggregate cleanup |
| 30b | Export file cleanup job | 30 | S | Delete expired export files from storage |
| 31 | Unit tests | 1-21 | L | Backend unit tests |
| 32 | Frontend tests | 22-29 | L | React component tests |
| 33 | Integration tests | 31 | M | API integration tests |
| 34 | Performance tests | 33 | M | Load time and throughput testing |

### 5.2 File Changes

**New Files:**
```
src/
├── activity/
│   ├── __init__.py
│   ├── models.py                     # Task 1: Data models
│   ├── timezone_utils.py             # Task 12b: Timezone conversion utilities
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── events_repository.py      # Task 3: Raw events storage
│   │   ├── hourly_repository.py      # Task 4: Hourly aggregates
│   │   ├── daily_repository.py       # Task 5: Daily aggregates
│   │   ├── weekly_repository.py      # Task 6: Weekly aggregates
│   │   ├── monthly_repository.py     # Task 6b: Monthly aggregates
│   │   └── preferences_repository.py # Task 20: User preferences
│   ├── services/
│   │   ├── __init__.py
│   │   ├── aggregation_service.py    # Tasks 9-11, 11b: Aggregation logic
│   │   ├── peak_hours_service.py     # Task 16: Peak hours analysis
│   │   └── export_service.py         # Task 18: CSV export
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── hourly_aggregation.py     # Task 9: Hourly job
│   │   ├── daily_aggregation.py      # Task 10: Daily job
│   │   ├── weekly_aggregation.py     # Task 11: Weekly job
│   │   ├── monthly_aggregation.py    # Task 11b: Monthly job
│   │   ├── retention_manager.py      # Task 30: All-table retention
│   │   └── export_cleanup.py         # Task 30b: Export file cleanup
│   └── api/
│       ├── __init__.py
│       ├── routes.py                 # Tasks 8, 12-15, 17, 19, 21
│       ├── schemas.py                # Request/response schemas
│       └── handlers.py               # Request handlers
├── migrations/
│   ├── 001_create_activity_events.sql
│   ├── 002_create_activity_hourly.sql
│   ├── 003_create_activity_daily.sql
│   ├── 004_create_activity_weekly.sql
│   ├── 004b_create_activity_monthly.sql
│   ├── 005_create_export_jobs.sql
│   ├── 006_create_user_dashboard_preferences.sql
│   ├── 007_create_retention_log.sql
│   ├── 008_create_retention_function.sql
│   └── 009_create_export_cleanup_function.sql
frontend/
├── src/
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── ActivityDashboard.tsx     # Task 22: Main dashboard
│   │   │   ├── ActivityChart.tsx         # Task 23: Charts
│   │   │   ├── ActivityHeatmap.tsx       # Task 24: Heatmap
│   │   │   ├── PeakHoursCard.tsx         # Task 25: Peak hours
│   │   │   ├── MonthlyTrendsCard.tsx     # Task 22: Monthly view
│   │   │   └── ExportButton.tsx          # Task 26: Export UI
│   │   └── common/
│   │       └── OfflineIndicator.tsx      # Offline status
│   ├── hooks/
│   │   ├── useActivityData.ts            # Data fetching hook
│   │   └── useOfflineCache.ts            # IndexedDB hook with expiration
│   ├── services/
│   │   ├── activityCollector.ts          # Task 7: Event collection SDK
│   │   ├── eventQueue.ts                 # Task 7b: Durable offline queue
│   │   └── indexedDBCache.ts             # Task 28: IndexedDB with 30-day TTL
│   ├── styles/
│   │   └── dashboard.css                 # Task 29: Responsive styles
│   └── sw.ts                             # Task 27: Service worker with background sync
tests/
├── activity/
│   ├── test_models.py                    # Task 31
│   ├── test_repositories.py              # Task 31
│   ├── test_aggregation_service.py       # Task 31
│   ├── test_monthly_aggregation.py       # Task 31: Monthly-specific tests
│   ├── test_peak_hours_service.py        # Task 31
│   ├── test_export_service.py            # Task 31
│   ├── test_retention_manager.py         # Task 31: Retention tests
│   ├── test_timezone_utils.py            # Task 31: Timezone conversion tests
│   ├── test_api.py                       # Task 31
│   └── integration/
│       ├── test_full_pipeline.py         # Task 33
│       ├── test_retention_compliance.py  # Task 33: 30-day enforcement
│       ├── test_offline_sync.py          # Task 33: Offline event delivery
│       └── test_performance.py           # Task 34
frontend/
└── tests/
    ├── components/
    │   ├── ActivityDashboard.test.tsx    # Task 32
    │   ├── ActivityChart.test.tsx        # Task 32
    │   ├── ActivityHeatmap.test.tsx      # Task 32
    │   └── MonthlyTrendsCard.test.tsx    # Task 32
    └── hooks/
        ├── useActivityData.test.ts       # Task 32
        ├── useOfflineCache.test.ts       # Task 32: Cache expiration tests
        └── eventQueue.test.ts            # Task 32: Offline queue tests
```

**Modified Files:**
```
src/
├── config.py                         # Add activity dashboard configuration
├── main.py                           # Register activity API routes
└── jobs/scheduler.py                 # Add aggregation and retention job schedules
frontend/
├── src/App.tsx                       # Add dashboard route
└── public/manifest.json              # Add service worker registration
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Component | Test Cases | Coverage Target |
|-----------|------------|-----------------|
| Data models | Serialization, validation, productivity score calculation | 95% |
| Repositories | CRUD operations, batch inserts, queries | 85% |
| Aggregation service | Hourly/daily/weekly/monthly rollup accuracy | 90% |
| Peak hours service | Pattern detection, score calculation, timezone handling | 90% |
| Export service | CSV generation, date range validation | 85% |
| Retention manager | All-table cleanup, compliance verification, period_end logic | 95% |
| Timezone utilities | UTC conversion, DST handling, edge cases | 95% |
| API handlers | Request validation, error responses | 85% |
| React components | Rendering, user interactions | 80% |
| Service worker | Caching, offline behavior, background sync | 80% |
| IndexedDB cache | Storage, expiration, cleanup | 85% |
| Event queue | Persistence, retry logic, deduplication | 90% |

**Key Unit Tests:**

```python
# test_aggregation_service.py
def test_hourly_aggregation_counts_events():
    """Hourly rollup accurately counts events."""
    events = [
        ActivityEvent(event_type=ActivityEventType.PAGE_VIEW, timestamp=datetime(2025, 12, 15, 10, 15)),
        ActivityEvent(event_type=ActivityEventType.PAGE_VIEW, timestamp=datetime(2025, 12, 15, 10, 30)),
        ActivityEvent(event_type=ActivityEventType.FEATURE_USE, timestamp=datetime(2025, 12, 15, 10, 45)),
    ]

    rollup = aggregate_hourly(events, hour_start=datetime(2025, 12, 15, 10, 0))

    assert rollup.event_count == 3
    assert rollup.page_views == 2
    assert rollup.feature_uses == 1

def test_daily_aggregation_finds_peak_hour():
    """Daily rollup correctly identifies peak hour."""
    hourly_rollups = [
        HourlyActivityRollup(hour_start=datetime(2025, 12, 15, 9, 0), event_count=50),
        HourlyActivityRollup(hour_start=datetime(2025, 12, 15, 10, 0), event_count=100),
        HourlyActivityRollup(hour_start=datetime(2025, 12, 15, 11, 0), event_count=75),
    ]

    rollup = aggregate_daily(hourly_rollups, date=date(2025, 12, 15))

    assert rollup.peak_hour == 10
    assert rollup.peak_hour_events == 100

def test_productivity_score_calculation():
    """Productivity score correctly weights activity density and engagement."""
    rollup = HourlyActivityRollup(
        user_id="user_123",
        hour_start=datetime(2025, 12, 15, 10, 0),
        event_count=50,
        active_minutes=45,
        feature_uses=8
    )

    score = rollup.productivity_score

    # 45/60 * 50 = 37.5 (density) + 8/10 * 50 = 40 (engagement) = 77.5
    assert score == 77.5

def test_weekly_heatmap_structure():
    """Weekly rollup generates correct heatmap dimensions."""
    rollup = aggregate_weekly(daily_rollups, week_start=date(2025, 12, 9))

    assert len(rollup.hourly_heatmap) == 7  # 7 days
    assert all(len(day) == 24 for day in rollup.hourly_heatmap)  # 24 hours each


# test_monthly_aggregation.py
def test_monthly_aggregation_from_daily():
    """Monthly rollup correctly aggregates daily data."""
    daily_rollups = [
        DailyActivityRollup(user_id="user_123", date=date(2025, 12, 1), total_events=150),
        DailyActivityRollup(user_id="user_123", date=date(2025, 12, 2), total_events=180),
        DailyActivityRollup(user_id="user_123", date=date(2025, 12, 3), total_events=0),
        # ... more days
    ]

    rollup = aggregate_monthly(daily_rollups, month_start=date(2025, 12, 1))

    assert rollup.total_events == sum(d.total_events for d in daily_rollups)
    assert rollup.active_days == 2  # Days with events > 0
    assert rollup.month_end == date(2025, 12, 31)  # Correct month end

def test_monthly_weekly_breakdown():
    """Monthly rollup correctly splits events into weeks."""
    rollup = aggregate_monthly(daily_rollups, month_start=date(2025, 12, 1))

    assert len(rollup.weekly_breakdown) == 5  # Max 5 weeks
    assert sum(rollup.weekly_breakdown) == rollup.total_events

def test_monthly_peak_week_identification():
    """Monthly rollup correctly identifies peak week."""
    rollup = aggregate_monthly(daily_rollups_with_peak_in_week_2, month_start=date(2025, 12, 1))

    assert rollup.peak_week == 2
    assert rollup.peak_week_events > 0


# test_peak_hours_service.py
def test_peak_hours_identifies_top_three():
    """Peak hours analysis returns top 3 most productive hours."""
    analysis = analyze_peak_hours(user_id="user_123", days=30, timezone="UTC")

    assert len(analysis.peak_hours) == 3
    assert analysis.peak_hours[0] != analysis.peak_hours[1]
    assert analysis.peak_hours_scores[0] >= analysis.peak_hours_scores[1]

def test_peak_hours_respects_timezone():
    """Peak hours are computed in user's local timezone."""
    # UTC data has peak at 15:00 UTC
    analysis_utc = analyze_peak_hours(user_id="user_123", days=30, timezone="UTC")
    # For PST (UTC-8), same data peak should be at 07:00 local
    analysis_pst = analyze_peak_hours(user_id="user_123", days=30, timezone="America/Los_Angeles")

    # The peak hour shifts by timezone offset
    assert analysis_pst.peak_hours[0] != analysis_utc.peak_hours[0]
    assert analysis_pst.timezone == "America/Los_Angeles"

def test_most_active_period_classification():
    """Most active period correctly classified based on peak hours."""
    # Mock data with peak at 10 AM local
    analysis = analyze_peak_hours_with_mock(peak_hour=10)
    assert analysis.most_active_period == "morning"

    # Mock data with peak at 3 PM local
    analysis = analyze_peak_hours_with_mock(peak_hour=15)
    assert analysis.most_active_period == "afternoon"


# test_timezone_utils.py
def test_utc_to_local_conversion():
    """UTC timestamps correctly convert to local time."""
    utc_time = datetime(2025, 12, 15, 18, 0, tzinfo=timezone.utc)
    local_time = convert_to_timezone(utc_time, "America/New_York")
    
    # EST is UTC-5
    assert local_time.hour == 13

def test_hourly_breakdown_timezone_shift():
    """Hourly breakdown array shifts correctly for timezone."""
    utc_breakdown = [0]*6 + [10, 20, 30, 40, 50, 45, 35, 25, 20, 15, 10, 5] + [0]*6
    local_breakdown = shift_hourly_breakdown(utc_breakdown, "America/New_York")
    
    # EST is UTC-5, so hour 6 UTC becomes hour 1 local
    assert local_breakdown[1] == utc_breakdown[6]

def test_dst_transition_handling():
    """Correctly handles daylight saving time transitions."""
    # March 9, 2025: DST starts in US
    utc_time = datetime(2025, 3, 9, 10, 0, tzinfo=timezone.utc)
    local_time = convert_to_timezone(utc_time, "America/New_York")
    
    # After DST, EDT is UTC-4
    assert local_time.hour == 6  # 10 - 4 = 6


# test_export_service.py
def test_csv_export_includes_headers():
    """CSV export includes correct column headers."""
    csv_content = generate_export(user_id="user_123", start_date=date(2025, 12, 1), end_date=date(2025, 12, 15))

    lines = csv_content.split("\n")
    headers = lines[0].split(",")

    assert "date" in headers
    assert "total_events" in headers
    assert "productivity_score" in headers

def test_export_respects_30_day_limit():
    """Export rejects date ranges over 30 days."""
    with pytest.raises(InvalidDateRangeError):
        generate_export(
            user_id="user_123",
            start_date=date(2025, 11, 1),
            end_date=date(2025, 12, 15)
        )


# test_retention_manager.py
def test_retention_deletes_old_hourly_data():
    """Retention job removes hourly data older than 30 days."""
    # Insert data 31 days old
    old_timestamp = datetime.utcnow() - timedelta(days=31)
    insert_hourly_rollup(user_id="user_123", hour_start=old_timestamp)

    run_retention_job()

    # Verify deletion
    result = query_hourly_rollup(user_id="user_123", hour_start=old_timestamp)
    assert result is None

def test_retention_deletes_old_daily_data():
    """Retention job removes daily data older than 30 days."""
    old_date = date.today() - timedelta(days=31)
    insert_daily_rollup(user_id="user_123", date=old_date)

    run_retention_job()

    result = query_daily_rollup(user_id="user_123", date=old_date)
    assert result is None

def test_retention_uses_week_end_for_weekly():
    """Retention job uses week_end, not week_start, for weekly deletion."""
    # Week starting 35 days ago but ending 29 days ago should be kept
    old_week_start = date.today() - timedelta(days=35)
    week_end = old_week_start + timedelta(days=6)  # 29 days ago
    insert_weekly_rollup(user_id="user_123", week_start=old_week_start, week_end=week_end)

    run_retention_job()

    # Should still exist because week_end is within 30 days
    result = query_weekly_rollup(user_id="user_123", week_start=old_week_start)
    assert result is not None

def test_retention_deletes_weekly_when_week_end_old():
    """Retention job deletes weekly rollup when week_end is older than 30 days."""
    # Week ending 31 days ago
    old_week_start = date.today() - timedelta(days=37)
    week_end = old_week_start + timedelta(days=6)  # 31 days ago
    insert_weekly_rollup(user_id="user_123", week_start=old_week_start, week_end=week_end)

    run_retention_job()

    result = query_weekly_rollup(user_id="user_123", week_start=old_week_start)
    assert result is None

def test_retention_uses_month_end_for_monthly():
    """Retention job uses month_end, not month_start, for monthly deletion."""
    # Month starting Nov 1 (45 days ago) but ending Nov 30 (15 days ago) should be kept
    month_start = date(2025, 11, 1)
    month_end = date(2025, 11, 30)
    insert_monthly_rollup(user_id="user_123", month_start=month_start, month_end=month_end)

    run_retention_job()  # Assuming today is Dec 15

    # Should still exist because month_end is within 30 days
    result = query_monthly_rollup(user_id="user_123", month_start=month_start)
    assert result is not None

def test_retention_preserves_recent_data():
    """Retention job preserves data within 30-day window."""
    recent_date = date.today() - timedelta(days=15)
    insert_daily_rollup(user_id="user_123", date=recent_date)

    run_retention_job()

    result = query_daily_rollup(user_id="user_123", date=recent_date)
    assert result is not None

def test_export_file_cleanup():
    """Expired export files are deleted from storage."""
    # Create completed export with expired timestamp
    export = create_export_job(
        user_id="user_123",
        status="completed",
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    
    run_export_cleanup_job()
    
    # Verify file deleted and status updated
    result = get_export_job(export.export_id)
    assert result.status == "expired"
    assert not file_exists(result.file_path)


# test_offline_queue.py (frontend)
def test_events_queued_when_offline():
    """Events are stored in IndexedDB when offline."""
    set_network_status(offline=True)
    collector.track('page_view', 'test_page')
    
    queued = get_queued_events()
    assert len(queued) == 1
    assert queued[0].event_name == 'test_page'

def test_queued_events_sent_on_reconnect():
    """Queued events are sent when connection restored."""
    set_network_status(offline=True)
    collector.track('page_view', 'test_page')
    
    set_network_status(offline=False)
    trigger_background_sync()
    
    queued = get_queued_events()
    assert len(queued) == 0  # All sent

def test_retry_on_failed_delivery():
    """Failed deliveries are retried with backoff."""
    mock_api_failure()
    collector.track('page_view', 'test_page')
    
    # First attempt fails
    await_retry(attempt=1)
    
    mock_api_success()
    # Second attempt succeeds
    await_retry(attempt=2)
    
    queued = get_queued_events()
    assert len(queued) == 0

def test_event_deduplication():
    """Duplicate events are not redelivered."""
    collector.track('page_view', 'test_page', event_id='evt_123')
    
    # Simulate network failure after server received but before ack
    mock_api_failure_after_processing()
    trigger_background_sync()
    
    # Re-sending same event should be deduplicated server-side
    delivered = get_delivered_events()
    assert len([e for e in delivered if e.event_id == 'evt_123']) == 1
```

### 6.2 Integration Tests

| Scenario | Description | Validation |
|----------|-------------|------------|
| Event ingestion pipeline | Submit events → aggregation → query | Events reflected in hourly rollup within 5 mins |
| Dashboard load performance | Request summary with 30 days of data | Response time < 500ms |
| Monthly aggregation pipeline | Daily data → monthly rollup → API query | Monthly data accurate and queryable |
| Export full workflow | Request export → poll status → download | CSV downloaded successfully |
| Offline dashboard | Load dashboard → disconnect → reload | Dashboard renders from cache |
| Offline event collection | Track events offline → reconnect → verify delivery | All events delivered with correct timestamps |
| Retention enforcement (all tables) | Insert 31-day-old data in all tables → run retention | All old data deleted |
| Retention with period_end | Insert weekly/monthly with recent end dates | Rollups preserved until period_end exceeds 30 days |
| Client cache expiration | Cache data → wait 30 days → verify deletion | IndexedDB entries expired |
| Concurrent aggregation | Multiple users aggregating simultaneously | No data corruption |
| Mobile responsiveness | Load dashboard on mobile viewport | All elements visible and usable |
| Timezone consistency | Set timezone → check all endpoints | All times in correct timezone |
| Peak hours across timezones | Compare peak hours for UTC vs PST user | Hours correctly shifted |

### 6.3 Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| No activity data | Dashboard shows empty state with helpful message |
| Single day of activity | Weekly/monthly views show one data point, others empty |
| Activity at midnight | Correctly assigned to appropriate day |
| Timezone crossing midnight | Respects user's timezone for day boundaries |
| Export with no data in range | Returns CSV with headers only |
| Concurrent export requests | Queued and processed sequentially |
| 10,000 events in single batch | Batch split and processed in chunks |
| User changes timezone | Historical data re-rendered in new timezone |
| Exactly 30 days of data | All data included, none dropped |
| Activity on Feb 29 (leap year) | Correctly handled in aggregations |
| Service worker update | User notified, data refreshed |
| IndexedDB storage full | Graceful degradation, API-only mode |
| Month with 28/29/30/31 days | Monthly breakdown array handles variable length |
| Partial month of data | Monthly totals accurate for available days |
| Data exactly at retention boundary | 30-day-old data preserved, 31-day-old deleted |
| Weekly rollup spanning retention boundary | Preserved until week_end is >30 days old |
| Monthly rollup spanning retention boundary | Preserved until month_end is >30 days old |
| Offline for multiple days | All events queued and delivered on reconnect |
| Background sync fails repeatedly | Events retained, retried with exponential backoff |
| DST transition | Timezone conversions handle spring-forward/fall-back |
| User in half-hour timezone (e.g., IST) | Hourly buckets correctly shifted |

---

## 7. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Dashboard load time exceeds 2s | High | Medium | Pre-computed aggregations, CDN caching, lazy loading, composite indexes |
| Aggregation jobs fall behind | Medium | Low | Horizontal scaling, catchup mode, monitoring alerts |
| Large export files timeout | Medium | Medium | Streaming response, chunked downloads, progress API |
| IndexedDB storage limits | Low | Low | LRU eviction, configurable retention in client, 30-day max |
| Timezone handling errors | Medium | Medium | Consistent UTC storage, comprehensive timezone utils, DST tests |
| Service worker cache stale | Medium | Low | Version-based cache invalidation, manual refresh option |
| Peak hours inaccurate with sparse data | Low | Medium | Minimum data threshold, confidence intervals |
| Retention job deletes wrong data | High | Low | Dry-run mode, audit logging, comprehensive tests, period_end validation |
| Mobile chart performance | Medium | Medium | Canvas rendering, reduced data points on mobile |
| Event collection battery drain | Medium | Low | Batching, visibility API, configurable frequency |
| Compliance violation (>30 day data) | High | Low | All-table retention, client cache expiration, audit logging, period_end columns |
| Offline events lost | Medium | Low | Durable IndexedDB queue, background sync, retry with backoff |
| Duplicate events on retry | Low | Medium | Event ID deduplication on server, idempotent ingestion |

### 7.1 Performance Optimization Strategy

To meet the < 2 second load time requirement:

1. **Pre-computation**: All aggregations (hourly/daily/weekly/monthly) computed in background jobs, never on-demand
2. **Composite Indexes**: All aggregation tables indexed by (user_id, date/timestamp DESC) for fast user-specific queries
3. **Response caching**: 5-minute TTL on summary endpoints with ETag support
4. **CDN caching**: Static assets cached at edge locations
5. **Lazy loading**: Charts rendered progressively, heatmap loaded after initial render
6. **Data minimization**: API returns only data needed for current view
7. **Timezone conversion at read time**: Store UTC, convert on API response to avoid recomputation

**Performance Budget:**

| Asset/Operation | Target | Cumulative |
|-----------------|--------|------------|
| HTML + critical CSS | 50ms | 50ms |
| JavaScript bundle | 200ms | 250ms |
| API request (cached) | 50ms | 300ms |
| API request (uncached) | 300ms | 600ms |
| Chart rendering | 400ms | 1000ms |
| Full interactivity | 500ms | 1500ms |
| Buffer | 500ms | 2000ms |

### 7.2 Offline Strategy

The dashboard uses a "stale-while-revalidate" strategy:

1. **First Visit**: Fetch from API, cache in IndexedDB with timestamp, register service worker
2. **Subsequent Visits**:
   - Immediately render from IndexedDB cache
   - Fetch fresh data in background
   - Update UI when fresh data arrives
3. **Offline Visit**: Render entirely from IndexedDB, show "offline" indicator
4. **Cache Expiration**: IndexedDB data expires after 30 days (compliance) or 24 hours of no updates (freshness)

```typescript
// Service worker strategy
const CACHE_NAME = 'activity-dashboard-v1';
const API_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Cache static assets with cache-first strategy
workbox.routing.registerRoute(
  /\.(js|css|png|svg)$/,
  new workbox.strategies.CacheFirst({
    cacheName: CACHE_NAME,
  })
);

// Cache API responses with stale-while-revalidate
workbox.routing.registerRoute(
  /\/api\/v1\/activity\//,
  new workbox.strategies.StaleWhileRevalidate({
    cacheName: 'activity-api-cache',
    plugins: [
      new workbox.expiration.ExpirationPlugin({
        maxAgeSeconds: API_CACHE_TTL / 1000,
      }),
    ],
  })
);

// Register background sync for event delivery
workbox.routing.registerRoute(
  /\/api\/v1\/activity\/events/,
  new workbox.strategies.NetworkOnly({
    plugins: [
      new workbox.backgroundSync.BackgroundSyncPlugin('activity-events-queue', {
        maxRetentionTime: 24 * 60, // Retry for up to 24 hours (in minutes)
      }),
    ],
  }),
  'POST'
);
```

```typescript
// IndexedDB cache with 30-day retention compliance
const CACHE_MAX_AGE_DAYS = 30;

interface CachedData {
  data: any;
  cachedAt: number;  // Unix timestamp
  expiresAt: number; // Unix timestamp (cachedAt + 30 days)
}

async function getCachedData(key: string): Promise<any | null> {
  const cached = await db.get('activity-cache', key);
  if (!cached) return null;
  
  // Enforce 30-day retention
  if (Date.now() > cached.expiresAt) {
    await db.delete('activity-cache', key);
    return null;
  }
  
  return cached.data;
}

async function setCachedData(key: string, data: any): Promise<void> {
  const now = Date.now();
  await db.put('activity-cache', {
    data,
    cachedAt: now,
    expiresAt: now + (CACHE_MAX_AGE_DAYS * 24 * 60 * 60 * 1000),
  }, key);
}

// Cleanup job runs on app init
async function cleanupExpiredCache(): Promise<void> {
  const now = Date.now();
  const keys = await db.getAllKeys('activity-cache');
  for (const key of keys) {
    const cached = await db.get('activity-cache', key);
    if (cached && now > cached.expiresAt) {
      await db.delete('activity-cache', key);
    }
  }
}
```

### 7.3 Retention Compliance Strategy

To ensure compliance with the 30-day data retention constraint:

1. **Server-Side (PostgreSQL)**:
   - Raw events: Table partitioning with automatic partition drops
   - Hourly/Daily aggregation tables: Daily DELETE job for rows older than 30 days
   - Weekly aggregation tables: DELETE based on week_end < cutoff (not week_start)
   - Monthly aggregation tables: DELETE based on month_end < cutoff (not month_start)
   - Export files: 24-hour expiration with cleanup job
   - Audit logging: All deletions recorded in `activity_retention_log`

2. **Client-Side (IndexedDB)**:
   - All cached entries include `expiresAt` timestamp (30 days from cache time)
   - Cleanup runs on app initialization
   - Expired entries return null and are deleted

3. **Monitoring**:
   - Alert if retention job fails
   - Dashboard showing oldest data in each table
   - Compliance report generated weekly

### 7.4 Timezone Handling Strategy

All data is stored in UTC and converted to user's local timezone at read time:

1. **Storage (UTC)**:
   - All timestamps stored as TIMESTAMPTZ in PostgreSQL (UTC)
   - Aggregation jobs use UTC boundaries for bucketing
   - Hourly breakdowns stored as 24-element arrays (UTC hours 0-23)

2. **Read-Time Conversion**:
   - API endpoints accept `timezone` parameter (defaults to user preference)
   - Server converts all timestamps to requested timezone before response
   - Hourly breakdown arrays are rotated by timezone offset

3. **Peak Hours Analysis**:
   - Peak hours computed by converting UTC hourly data to local time
   - DST transitions handled using pytz/zoneinfo library
   - Analysis result includes `timezone` field indicating which timezone was used

4. **Client-Side**:
   - Charts display times in user's local timezone
   - Heatmaps shift hour columns based on timezone offset
   - All displayed times labeled with timezone indicator

**Timezone Conversion Utilities:**

```python
# timezone_utils.py
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import List

def convert_to_timezone(utc_dt: datetime, timezone: str) -> datetime:
    """Convert UTC datetime to specified timezone."""
    utc_tz = ZoneInfo("UTC")
    target_tz = ZoneInfo(timezone)
    
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=utc_tz)
    
    return utc_dt.astimezone(target_tz)

def get_timezone_offset_hours(timezone: str, reference_date: datetime = None) -> int:
    """Get timezone offset from UTC in hours (handles DST)."""
    if reference_date is None:
        reference_date = datetime.utcnow()
    
    utc_tz = ZoneInfo("UTC")
    target_tz = ZoneInfo(timezone)
    
    utc_dt = reference_date.replace(tzinfo=utc_tz)
    local_dt = utc_dt.astimezone(target_tz)
    
    offset = local_dt.utcoffset()
    return int(offset.total_seconds() // 3600)

def shift_hourly_breakdown(utc_breakdown: List[int], timezone: str, reference_date: datetime = None) -> List[int]:
    """Shift a 24-element hourly breakdown array to local timezone."""
    offset = get_timezone_offset_hours(timezone, reference_date)
    
    # Positive offset means local time is ahead of UTC
    # So hour 0 UTC becomes hour +offset local
    shifted = [0] * 24
    for utc_hour in range(24):
        local_hour = (utc_hour + offset) % 24
        shifted[local_hour] = utc_breakdown[utc_hour]
    
    return shifted

def compute_local_peak_hour(utc_hourly_scores: List[float], timezone: str) -> int:
    """Compute peak hour in local timezone from UTC scores."""
    local_scores = shift_hourly_breakdown(utc_hourly_scores, timezone)
    return local_scores.index(max(local_scores))

def classify_time_period(hour: int) -> str:
    """Classify hour into time period (morning/afternoon/evening/night)."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"
```

---

## 8. Open Questions

1. **Activity Tracking Opt-In**: Should activity tracking require explicit user consent? Are there GDPR/CCPA implications for storing activity data?

2. **Cross-Device Data**: Should activity from multiple devices be combined? If so, how do we handle device identification without compromising privacy?

3. **Productivity Score Formula**: Is the current productivity score calculation (activity density + feature engagement) appropriate, or should it be configurable per user?

4. **Export Frequency Limits**: What is the appropriate rate limit for exports (currently proposed: 5 per day)?

5. **Heatmap Color Scale**: Should the heatmap use absolute values or relative-to-user-max values for color intensity?

6. **Activity Event Granularity**: What level of detail should be captured in event metadata? More detail enables better insights but increases storage costs.

7. **Real-Time Updates**: Should the dashboard update in real-time (WebSocket) or on-demand (manual refresh)?

8. **Historical Comparison**: Should we support comparing current period to the same period last month/year, even though we only retain 30 days?

9. **Mobile App Activity**: If there's a mobile app, should mobile activity be included in the dashboard?

---

## 9. Appendix

### 9.1 Sample Dashboard UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Activity Dashboard                              [Weekly ▼] [Export]    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │ 847          │  │ 42           │  │ 72.5         │  │ +6.9%        ││
│  │ Total Events │  │ Active Hours │  │ Productivity │  │ vs Last Week ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Daily Activity                                                      │ │
│  │  200│                    ██                                         │ │
│  │     │        ██          ██                      ██      ██         │ │
│  │  100│  ██    ██    ██    ██                ██    ██      ██         │ │
│  │     │  ██    ██    ██    ██                ██    ██      ██         │ │
│  │    0│──Mon───Tue───Wed───Thu───Fri───Sat───Sun──────────────────── │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Peak Hours (EST)                │  │ Weekly Heatmap               │  │
│  │                                 │  │                               │  │
│  │  🏆 10:00 AM  (85.2)           │  │     0  4  8  12 16 20        │  │
│  │  🥈 2:00 PM   (78.4)           │  │ Mon ░░▓▓██████▓▓░░          │  │
│  │  🥉 11:00 AM  (76.1)           │  │ Tue ░░▓▓████████▓░░          │  │
│  │                                 │  │ Wed ░░▓▓██████▓▓░░          │  │
│  │  Most active: Morning           │  │ Thu ░░░░░░░░░░░░░░          │  │
│  │  Average: 8:30 AM - 5:45 PM     │  │ Fri ░░░░░░░░░░░░░░          │  │
│  └─────────────────────────────────┘  │ Sat ░░░░▓▓████▓░░░          │  │
│                                        │ Sun ░░░░▓▓██████▓░░          │  │
│                                        └─────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Monthly View Wireframe

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Activity Dashboard                             [Monthly ▼] [Export]    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │ 3,420        │  │ 18           │  │ 74.2         │  │ +7.5%        ││
│  │ Total Events │  │ Active Days  │  │ Productivity │  │ vs Last Month││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Weekly Breakdown - December 2025                                    │ │
│  │ 1000│                                                               │ │
│  │     │        ████                                                   │ │
│  │  500│  ████  ████  ████  ████                                       │ │
│  │     │  ████  ████  ████  ████  ██                                   │ │
│  │    0│──Wk1───Wk2───Wk3───Wk4───Wk5──────────────────────────────── │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Daily Activity - December 2025                                      │ │
│  │                                                                      │ │
│  │  S  M  T  W  T  F  S                                                │ │
│  │     1  2  3  4  5  6    ██ High (>150 events)                       │ │
│  │  7  8  9 10 11 12 13    ▓▓ Medium (50-150)                          │ │
│  │ 14 15 16 17 18 19 20    ░░ Low (<50)                                │ │
│  │ 21 22 23 24 25 26 27    ·· No activity                              │ │
│  │ 28 29 30 31                                                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Monthly Insights                │  │ Best Days                    │  │
│  │                                 │  │                               │  │
│  │ Peak Week: Week 2 (920 events) │  │ 1. Dec 10 - 215 events       │  │
│  │ Most Active: Tuesdays          │  │ 2. Dec 17 - 198 events       │  │
│  │ Avg Daily: 190 events          │  │ 3. Dec 9  - 189 events       │  │
│  └─────────────────────────────────┘  └─────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 CSV Export Format

```csv
date,day_of_week,total_events,total_sessions,active_hours,active_minutes,productivity_score,peak_hour,page_views,feature_uses
2025-12-15,Sunday,190,5,10,420,75.4,10,120,45
2025-12-14,Saturday,145,4,7,280,65.8,14,95,32
2025-12-11,Wednesday,167,5,8,360,73.1,11,110,38
2025-12-10,Tuesday,189,6,9,400,78.5,10,125,42
2025-12-09,Monday,156,4,8,340,71.2,10,100,35
```

### 9.4 Activity Collector SDK Usage

```typescript
import { ActivityCollector } from '@app/activity-collector';

// Initialize collector with offline support
const collector = new ActivityCollector({
  endpoint: '/api/v1/activity/events',
  batchSize: 100,
  flushInterval: 30000, // 30 seconds
  sessionTimeout: 1800000, // 30 minutes
  offlineStorage: {
    enabled: true,
    maxQueueSize: 10000, // Max events to queue offline
    retryStrategy: 'exponential', // 'exponential' | 'linear' | 'fixed'
    maxRetries: 10,
    baseRetryDelay: 1000, // 1 second initial delay
    maxRetryDelay: 300000, // 5 minutes max delay
  },
});

// Track page view
collector.track('page_view', 'dashboard_viewed', {
  page_path: '/dashboard',
  referrer: document.referrer,
});

// Track feature use with duration
collector.trackTimed('feature_use', 'report_generated', {
  report_type: 'weekly',
});
// ... later
collector.endTimed('report_generated');

// Manual flush (e.g., before page unload)
collector.flush();

// Check queue status
const queueStatus = await collector.getQueueStatus();
console.log(`${queueStatus.pendingEvents} events pending delivery`);

// Force retry of failed events
await collector.retryFailedEvents();
```

**Offline Event Queue Implementation:**

```typescript
// eventQueue.ts
import { openDB, DBSchema, IDBPDatabase } from 'idb';

interface EventQueueDB extends DBSchema {
  'pending-events': {
    key: string;
    value: {
      eventId: string;
      event: ActivityEvent;
      queuedAt: number;
      attempts: number;
      lastAttemptAt: number | null;
      nextRetryAt: number;
    };
    indexes: { 'by-next-retry': number };
  };
  'sent-events': {
    key: string;
    value: {
      eventId: string;
      sentAt: number;
    };
  };
}

class EventQueue {
  private db: IDBPDatabase<EventQueueDB> | null = null;
  private readonly MAX_QUEUE_SIZE = 10000;
  private readonly DEDUP_WINDOW_MS = 24 * 60 * 60 * 1000; // 24 hours

  async init(): Promise<void> {
    this.db = await openDB<EventQueueDB>('activity-event-queue', 1, {
      upgrade(db) {
        const pendingStore = db.createObjectStore('pending-events', {
          keyPath: 'eventId',
        });
        pendingStore.createIndex('by-next-retry', 'nextRetryAt');
        
        db.createObjectStore('sent-events', { keyPath: 'eventId' });
      },
    });
  }

  async enqueue(event: ActivityEvent): Promise<void> {
    if (!this.db) throw new Error('Queue not initialized');

    // Check for duplicate (already sent recently)
    const existing = await this.db.get('sent-events', event.event_id);
    if (existing && Date.now() - existing.sentAt < this.DEDUP_WINDOW_MS) {
      return; // Skip duplicate
    }

    // Check queue size limit
    const count = await this.db.count('pending-events');
    if (count >= this.MAX_QUEUE_SIZE) {
      // Remove oldest events to make room
      const oldest = await this.db.getAllFromIndex(
        'pending-events',
        'by-next-retry',
        IDBKeyRange.upperBound(Date.now()),
        count - this.MAX_QUEUE_SIZE + 1
      );
      for (const item of oldest) {
        await this.db.delete('pending-events', item.eventId);
      }
    }

    await this.db.put('pending-events', {
      eventId: event.event_id,
      event,
      queuedAt: Date.now(),
      attempts: 0,
      lastAttemptAt: null,
      nextRetryAt: Date.now(),
    });
  }

  async getEventsToSend(limit: number = 100): Promise<ActivityEvent[]> {
    if (!this.db) throw new Error('Queue not initialized');

    const now = Date.now();
    const items = await this.db.getAllFromIndex(
      'pending-events',
      'by-next-retry',
      IDBKeyRange.upperBound(now),
      limit
    );

    return items.map(item => item.event);
  }

  async markSent(eventIds: string[]): Promise<void> {
    if (!this.db) throw new Error('Queue not initialized');

    const tx = this.db.transaction(['pending-events', 'sent-events'], 'readwrite');
    const now = Date.now();

    for (const eventId of eventIds) {
      await tx.objectStore('pending-events').delete(eventId);
      await tx.objectStore('sent-events').put({ eventId, sentAt: now });
    }

    await tx.done;
  }

  async markFailed(eventId: string, config: RetryConfig): Promise<void> {
    if (!this.db) throw new Error('Queue not initialized');

    const item = await this.db.get('pending-events', eventId);
    if (!item) return;

    const newAttempts = item.attempts + 1;
    if (newAttempts >= config.maxRetries) {
      // Give up after max retries
      await this.db.delete('pending-events', eventId);
      return;
    }

    // Calculate next retry with exponential backoff
    const delay = Math.min(
      config.baseRetryDelay * Math.pow(2, newAttempts),
      config.maxRetryDelay
    );

    await this.db.put('pending-events', {
      ...item,
      attempts: newAttempts,
      lastAttemptAt: Date.now(),
      nextRetryAt: Date.now() + delay,
    });
  }

  async cleanupOldSentRecords(): Promise<void> {
    if (!this.db) throw new Error('Queue not initialized');

    const cutoff = Date.now() - this.DEDUP_WINDOW_MS;
    const allSent = await this.db.getAll('sent-events');
    
    for (const record of allSent) {
      if (record.sentAt < cutoff) {
        await this.db.delete('sent-events', record.eventId);
      }
    }
  }
}
```

### 9.5 Configuration Schema

```yaml
activity_dashboard:
  # Event collection
  collection:
    batch_size: 100
    flush_interval_seconds: 30
    max_events_per_batch: 500
    offline:
      enabled: true
      max_queue_size: 10000
      max_retries: 10
      base_retry_delay_ms: 1000
      max_retry_delay_ms: 300000

  # Aggregation jobs
  aggregation:
    hourly_interval_minutes: 5
    daily_run_time: "00:30"  # UTC
    weekly_run_time: "01:00"  # UTC
    monthly_run_time: "01:30"  # UTC

  # Data retention (PRD constraint: 30 days max)
  retention:
    max_days: 30
    cleanup_time: "02:00"  # UTC
    tables:
      - name: activity_events    # Partition-based
        retention_column: timestamp
      - name: activity_hourly    # Row deletion
        retention_column: hour_start
      - name: activity_daily     # Row deletion
        retention_column: date
      - name: activity_weekly    # Row deletion, uses period_end
        retention_column: week_end
      - name: activity_monthly   # Row deletion, uses period_end
        retention_column: month_end
    export_expiry_hours: 24
    client_cache_max_days: 30

  # Timezone handling
  timezone:
    default: "UTC"
    supported_timezones: "all"  # Or list specific ones
    convert_at: "read_time"  # "read_time" | "write_time"

  # Export settings
  export:
    max_range_days: 30
    max_exports_per_day: 5
    download_expiry_hours: 24

  # API caching
  caching:
    summary_ttl_seconds: 300
    peak_hours_ttl_seconds: 3600
    monthly_ttl_seconds: 600

  # Performance
  performance:
    max_heatmap_cells: 168  # 7 days * 24 hours
    chart_data_points_mobile: 7
    chart_data_points_desktop: 30
```

### 9.6 Monitoring Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `activity_events_ingested_total` | Counter | event_type | Total events ingested |
| `activity_events_batch_size` | Histogram | - | Size of ingested batches |
| `activity_events_offline_delivered_total` | Counter | - | Events delivered after being queued offline |
| `activity_events_queue_depth` | Gauge | - | Current offline event queue depth |
| `activity_aggregation_duration_seconds` | Histogram | granularity | Time to complete aggregation |
| `activity_aggregation_lag_seconds` | Gauge | granularity | Delay from event to aggregation |
| `activity_dashboard_load_duration_seconds` | Histogram | cache_status | Dashboard load time |
| `activity_api_request_duration_seconds` | Histogram | endpoint, timezone | API response time |
| `activity_export_requests_total` | Counter | status | Export requests by outcome |
| `activity_export_file_size_bytes` | Histogram | - | Size of generated exports |
| `activity_offline_loads_total` | Counter | - | Dashboard loads from offline cache |
| `activity_retention_rows_deleted_total` | Counter | table | Rows deleted by retention job per table |
| `activity_retention_job_duration_seconds` | Histogram | - | Time for retention job to complete |
| `activity_storage_bytes` | Gauge | table | Storage used per table |
| `activity_oldest_data_days` | Gauge | table | Age of oldest data in each table (compliance) |
| `activity_timezone_conversions_total` | Counter | timezone | API requests by timezone |