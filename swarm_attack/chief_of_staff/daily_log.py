"""Daily log manager for persistence of daily logs and decisions."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import os
import tempfile


class DecisionType(Enum):
    """Types of decisions that can be logged."""
    
    PRIORITY = "priority"
    ESCALATION = "escalation"
    DEFERRAL = "deferral"
    ASSIGNMENT = "assignment"


@dataclass
class StandupSession:
    """A standup session entry."""
    
    timestamp: datetime
    completed_yesterday: list[str] = field(default_factory=list)
    planned_today: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupSession":
        """Create StandupSession from dictionary."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            timestamp=timestamp,
            completed_yesterday=data.get("completed_yesterday", []),
            planned_today=data.get("planned_today", []),
            blockers=data.get("blockers", []),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "completed_yesterday": self.completed_yesterday,
            "planned_today": self.planned_today,
            "blockers": self.blockers,
        }


@dataclass
class WorkLogEntry:
    """A work log entry."""
    
    timestamp: datetime
    description: str
    duration_minutes: int
    category: str
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkLogEntry":
        """Create WorkLogEntry from dictionary."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            timestamp=timestamp,
            description=data.get("description", ""),
            duration_minutes=data.get("duration_minutes", 0),
            category=data.get("category", ""),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "category": self.category,
        }


@dataclass
class DailySummary:
    """End-of-day summary."""
    
    highlights: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    tomorrow_priorities: list[str] = field(default_factory=list)
    notes: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySummary":
        """Create DailySummary from dictionary."""
        return cls(
            highlights=data.get("highlights", []),
            challenges=data.get("challenges", []),
            tomorrow_priorities=data.get("tomorrow_priorities", []),
            notes=data.get("notes", ""),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "highlights": self.highlights,
            "challenges": self.challenges,
            "tomorrow_priorities": self.tomorrow_priorities,
            "notes": self.notes,
        }


@dataclass
class Decision:
    """A decision record."""
    
    timestamp: datetime
    decision_type: DecisionType
    description: str
    reasoning: str
    context: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Create Decision from dictionary."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        decision_type_str = data.get("decision_type", "priority")
        decision_type = DecisionType(decision_type_str)
        return cls(
            timestamp=timestamp,
            decision_type=decision_type,
            description=data.get("description", ""),
            reasoning=data.get("reasoning", ""),
            context=data.get("context", {}),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "decision_type": self.decision_type.value,
            "description": self.description,
            "reasoning": self.reasoning,
            "context": self.context,
        }


@dataclass
class DailyGoal:
    """A daily goal tracked in the log.

    Note: This is a simplified version for DailyLog storage. The full DailyGoal
    with all fields is in goal_tracker.py.
    """

    goal_id: str
    description: str
    priority: str  # "high", "medium", "low"
    estimated_minutes: int
    status: str = "pending"  # "pending", "in_progress", "complete", "blocked", "deferred"
    actual_minutes: Optional[int] = None
    notes: str = ""
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyGoal":
        """Create DailyGoal from dictionary."""
        return cls(
            goal_id=data.get("goal_id", ""),
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            estimated_minutes=data.get("estimated_minutes", 0),
            status=data.get("status", "pending"),
            actual_minutes=data.get("actual_minutes"),
            notes=data.get("notes", ""),
            linked_feature=data.get("linked_feature"),
            linked_bug=data.get("linked_bug"),
            linked_spec=data.get("linked_spec"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status,
            "actual_minutes": self.actual_minutes,
            "notes": self.notes,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
        }


@dataclass
class DailyLog:
    """A daily log entry containing standups, work entries, goals, and summary."""

    date: date
    standups: list[StandupSession] = field(default_factory=list)
    work_entries: list[WorkLogEntry] = field(default_factory=list)
    goals: list[DailyGoal] = field(default_factory=list)
    summary: Optional[DailySummary] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyLog":
        """Create DailyLog from dictionary."""
        date_str = data.get("date", "")
        if isinstance(date_str, str):
            log_date = date.fromisoformat(date_str)
        else:
            log_date = date_str

        standups = [
            StandupSession.from_dict(s) for s in data.get("standups", [])
        ]
        work_entries = [
            WorkLogEntry.from_dict(w) for w in data.get("work_entries", [])
        ]
        goals = [
            DailyGoal.from_dict(g) for g in data.get("goals", [])
        ]
        summary_data = data.get("summary")
        summary = DailySummary.from_dict(summary_data) if summary_data else None

        return cls(
            date=log_date,
            standups=standups,
            work_entries=work_entries,
            goals=goals,
            summary=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date.isoformat(),
            "standups": [s.to_dict() for s in self.standups],
            "work_entries": [w.to_dict() for w in self.work_entries],
            "goals": [g if isinstance(g, dict) else g.to_dict() for g in self.goals],
            "summary": self.summary.to_dict() if self.summary else None,
        }


class DailyLogManager:
    """Manager for daily log persistence."""
    
    def __init__(self, base_path: Path) -> None:
        """Initialize DailyLogManager with storage path.
        
        Args:
            base_path: Path to store daily log files.
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_json_path(self, log_date: date) -> Path:
        """Get path to JSON file for a date."""
        return self.base_path / f"{log_date.isoformat()}.json"
    
    def _get_md_path(self, log_date: date) -> Path:
        """Get path to markdown file for a date."""
        return self.base_path / f"{log_date.isoformat()}.md"
    
    def _get_decisions_path(self) -> Path:
        """Get path to decisions JSONL file."""
        return self.base_path / "decisions.jsonl"
    
    def _save_atomic(self, path: Path, content: str) -> None:
        """Save file atomically using temp file + rename pattern."""
        # Create temp file in same directory for atomic rename
        fd, temp_path = tempfile.mkstemp(
            dir=self.base_path,
            prefix=".tmp_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            # Atomic rename
            os.rename(temp_path, path)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def _generate_markdown(self, log: DailyLog) -> str:
        """Generate markdown content for a daily log."""
        lines = [
            f"# Daily Log: {log.date.isoformat()}",
            "",
        ]
        
        # Standups section
        if log.standups:
            lines.append("## Standups")
            lines.append("")
            for i, standup in enumerate(log.standups, 1):
                lines.append(f"### Standup {i} ({standup.timestamp.strftime('%H:%M')})")
                lines.append("")
                if standup.completed_yesterday:
                    lines.append("**Completed Yesterday:**")
                    for item in standup.completed_yesterday:
                        lines.append(f"- {item}")
                    lines.append("")
                if standup.planned_today:
                    lines.append("**Planned Today:**")
                    for item in standup.planned_today:
                        lines.append(f"- {item}")
                    lines.append("")
                if standup.blockers:
                    lines.append("**Blockers:**")
                    for item in standup.blockers:
                        lines.append(f"- {item}")
                    lines.append("")
        
        # Work entries section
        if log.work_entries:
            lines.append("## Work Log")
            lines.append("")
            for entry in log.work_entries:
                time_str = entry.timestamp.strftime("%H:%M")
                duration = f"{entry.duration_minutes}min"
                lines.append(f"- **{time_str}** [{entry.category}] ({duration}): {entry.description}")
            lines.append("")

        # Goals section
        if log.goals:
            lines.append("## Goals")
            lines.append("")
            for goal in log.goals:
                # Handle both DailyGoal objects and dicts
                if isinstance(goal, dict):
                    status = goal.get("status", "pending")
                    estimated_minutes = goal.get("estimated_minutes", 0)
                    actual_minutes = goal.get("actual_minutes")
                    description = goal.get("description", "")
                    priority = goal.get("priority", "medium")
                    notes = goal.get("notes", "")
                else:
                    status = goal.status.value if hasattr(goal.status, 'value') else goal.status
                    estimated_minutes = goal.estimated_minutes
                    actual_minutes = goal.actual_minutes
                    description = goal.description
                    priority = goal.priority.value if hasattr(goal.priority, 'value') else goal.priority
                    notes = goal.notes

                status_emoji = {
                    "complete": "[x]",
                    "in_progress": "[-]",
                    "pending": "[ ]",
                    "blocked": "[!]",
                    "deferred": "[~]",
                }.get(status, "[ ]")
                time_info = f"~{estimated_minutes}min"
                if actual_minutes is not None:
                    time_info = f"{actual_minutes}/{estimated_minutes}min"
                lines.append(f"- {status_emoji} **{description}** ({time_info}) [{priority}]")
                if notes:
                    lines.append(f"  - {notes}")
            lines.append("")

        # Summary section
        if log.summary:
            lines.append("## End of Day Summary")
            lines.append("")
            if log.summary.highlights:
                lines.append("### Highlights")
                for item in log.summary.highlights:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.challenges:
                lines.append("### Challenges")
                for item in log.summary.challenges:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.tomorrow_priorities:
                lines.append("### Tomorrow's Priorities")
                for item in log.summary.tomorrow_priorities:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.notes:
                lines.append("### Notes")
                lines.append(log.summary.notes)
                lines.append("")
        
        return "\n".join(lines)
    
    def get_log(self, log_date: date) -> Optional[DailyLog]:
        """Retrieve log for a specific date.
        
        Args:
            log_date: The date to retrieve log for.
            
        Returns:
            DailyLog if exists, None otherwise.
        """
        json_path = self._get_json_path(log_date)
        if not json_path.exists():
            return None
        
        try:
            content = json_path.read_text()
            data = json.loads(content)
            return DailyLog.from_dict(data)
        except (json.JSONDecodeError, ValueError):
            return None
    
    def get_today(self) -> DailyLog:
        """Get or create today's log.
        
        Returns:
            DailyLog for today.
        """
        today = date.today()
        log = self.get_log(today)
        if log is None:
            log = DailyLog(date=today)
            self.save_log(log)
        return log
    
    def get_yesterday(self) -> Optional[DailyLog]:
        """Retrieve yesterday's log.
        
        Returns:
            DailyLog if exists, None otherwise.
        """
        yesterday = date.today() - timedelta(days=1)
        return self.get_log(yesterday)
    
    def save_log(self, log: DailyLog) -> None:
        """Save log to both JSON and markdown files atomically.
        
        Args:
            log: The DailyLog to save.
        """
        # Save JSON
        json_path = self._get_json_path(log.date)
        json_content = json.dumps(log.to_dict(), indent=2)
        self._save_atomic(json_path, json_content)
        
        # Save Markdown
        md_path = self._get_md_path(log.date)
        md_content = self._generate_markdown(log)
        self._save_atomic(md_path, md_content)
    
    def add_standup(self, standup: StandupSession) -> None:
        """Add standup session to today's log.
        
        Args:
            standup: The StandupSession to add.
        """
        log = self.get_today()
        log.standups.append(standup)
        self.save_log(log)
    
    def add_work_entry(self, entry: WorkLogEntry) -> None:
        """Add work entry to today's log.
        
        Args:
            entry: The WorkLogEntry to add.
        """
        log = self.get_today()
        log.work_entries.append(entry)
        self.save_log(log)
    
    def set_summary(self, summary: DailySummary) -> None:
        """Set end-of-day summary on today's log.
        
        Args:
            summary: The DailySummary to set.
        """
        log = self.get_today()
        log.summary = summary
        self.save_log(log)
    
    def append_decision(self, decision: Decision) -> None:
        """Append decision to decisions.jsonl.
        
        Args:
            decision: The Decision to append.
        """
        jsonl_path = self._get_decisions_path()
        line = json.dumps(decision.to_dict()) + "\n"
        
        # Append to file (create if not exists)
        with open(jsonl_path, "a") as f:
            f.write(line)
    
    def get_decisions(
        self,
        since: Optional[datetime] = None,
        decision_type: Optional[DecisionType] = None,
    ) -> list[Decision]:
        """Query decisions from JSONL file.
        
        Args:
            since: Only return decisions after this timestamp.
            decision_type: Only return decisions of this type.
            
        Returns:
            List of matching Decision objects.
        """
        jsonl_path = self._get_decisions_path()
        if not jsonl_path.exists():
            return []
        
        decisions = []
        content = jsonl_path.read_text()
        for line in content.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                decision = Decision.from_dict(data)
                
                # Filter by since
                if since and decision.timestamp < since:
                    continue
                
                # Filter by type
                if decision_type and decision.decision_type != decision_type:
                    continue
                
                decisions.append(decision)
            except (json.JSONDecodeError, ValueError):
                # Skip corrupted lines
                continue
        
        return decisions
    
    def get_history(self, days: int) -> list[DailyLog]:
        """Get logs for the last N days.
        
        Args:
            days: Number of days to look back.
            
        Returns:
            List of DailyLog objects sorted by date descending.
        """
        logs = []
        today = date.today()
        
        for i in range(days):
            log_date = today - timedelta(days=i)
            log = self.get_log(log_date)
            if log:
                logs.append(log)
        
        # Already sorted by date descending due to iteration order
        return logs
    
    def generate_weekly_summary(self, week: int, year: int) -> str:
        """Generate markdown summary for a specific week.
        
        Args:
            week: ISO week number (1-53).
            year: Year.
            
        Returns:
            Markdown string with weekly summary.
        """
        lines = [
            f"# Weekly Summary: Week {week}, {year}",
            "",
        ]
        
        # Find all logs for this week
        week_logs = []
        
        # Iterate through the year to find matching week
        check_date = date(year, 1, 1)
        while check_date.year <= year:
            if check_date.isocalendar()[1] == week and check_date.year == year:
                log = self.get_log(check_date)
                if log:
                    week_logs.append(log)
            check_date += timedelta(days=1)
            if check_date.year > year:
                break
        
        if not week_logs:
            lines.append("*No logs recorded for this week.*")
            lines.append("")
            return "\n".join(lines)
        
        # Sort by date
        week_logs.sort(key=lambda x: x.date)
        
        # Aggregate highlights
        all_highlights = []
        all_challenges = []
        
        for log in week_logs:
            lines.append(f"## {log.date.strftime('%A, %Y-%m-%d')}")
            lines.append("")
            
            if log.summary:
                if log.summary.highlights:
                    lines.append("**Highlights:**")
                    for h in log.summary.highlights:
                        lines.append(f"- {h}")
                        all_highlights.append(h)
                    lines.append("")
                
                if log.summary.challenges:
                    lines.append("**Challenges:**")
                    for c in log.summary.challenges:
                        lines.append(f"- {c}")
                        all_challenges.append(c)
                    lines.append("")
            else:
                lines.append("*No summary recorded.*")
                lines.append("")
        
        # Weekly aggregation
        lines.append("## Week Overview")
        lines.append("")
        
        if all_highlights:
            lines.append("### All Highlights")
            for h in all_highlights:
                lines.append(f"- {h}")
            lines.append("")
        
        if all_challenges:
            lines.append("### All Challenges")
            for c in all_challenges:
                lines.append(f"- {c}")
            lines.append("")
        
        return "\n".join(lines)