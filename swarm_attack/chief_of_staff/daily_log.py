"""DailyLogManager for reading/writing daily logs and decision log."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import json
import os
import tempfile

from swarm_attack.chief_of_staff.models import (
    DailyLog,
    DailyGoal,
    DailySummary,
    Decision,
    GoalStatus,
    StandupSession,
    WorkLogEntry,
)


class DailyLogManager:
    """Manages daily logs and the append-only decision log."""

    def __init__(self, base_path: Path) -> None:
        """Initialize storage at the given base path.
        
        Args:
            base_path: Base directory for storing logs
        """
        self.base_path = Path(base_path)
        self.daily_log_path = self.base_path / "daily-log"
        self.decisions_path = self.base_path / "decisions.jsonl"
        
        # Ensure directories exist
        self.daily_log_path.mkdir(parents=True, exist_ok=True)

    def _get_log_paths(self, log_date: date) -> tuple[Path, Path]:
        """Get the JSON and Markdown paths for a given date."""
        date_str = log_date.isoformat()
        json_path = self.daily_log_path / f"{date_str}.json"
        md_path = self.daily_log_path / f"{date_str}.md"
        return json_path, md_path

    def get_log(self, log_date: date) -> Optional[DailyLog]:
        """Retrieve log for a specific date.
        
        Args:
            log_date: The date to retrieve the log for
            
        Returns:
            DailyLog if exists, None otherwise
        """
        json_path, _ = self._get_log_paths(log_date)
        
        if not json_path.exists():
            return None
            
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            return DailyLog.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def get_today(self) -> DailyLog:
        """Get or create today's log.
        
        Returns:
            Today's DailyLog (created if doesn't exist)
        """
        today = date.today()
        log = self.get_log(today)
        
        if log is None:
            log = DailyLog(date=today.isoformat())
            self.save_log(log)
            
        return log

    def get_yesterday(self) -> Optional[DailyLog]:
        """Get yesterday's log.
        
        Returns:
            Yesterday's DailyLog if exists, None otherwise
        """
        yesterday = date.today() - timedelta(days=1)
        return self.get_log(yesterday)

    def save_log(self, log: DailyLog) -> None:
        """Save log as both .json and .md versions using atomic writes.
        
        Args:
            log: The DailyLog to save
        """
        log_date = date.fromisoformat(log.date)
        json_path, md_path = self._get_log_paths(log_date)
        
        # Atomic write for JSON
        self._atomic_write(json_path, json.dumps(log.to_dict(), indent=2))
        
        # Atomic write for Markdown
        self._atomic_write(md_path, self._generate_markdown(log))

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to file atomically using temp file pattern.
        
        Args:
            path: Target file path
            content: Content to write
        """
        # Create temp file in same directory for atomic rename
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            # Atomic rename
            os.replace(temp_path, path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _get_status_icon(self, status: GoalStatus) -> str:
        """Get markdown icon for goal status."""
        icons = {
            GoalStatus.PENDING: "⬜",
            GoalStatus.IN_PROGRESS: "🔄",
            GoalStatus.DONE: "✅",
            GoalStatus.BLOCKED: "🚫",
            GoalStatus.PARTIAL: "🔶",
            GoalStatus.CARRIED_OVER: "➡️",
        }
        return icons.get(status, "⬜")

    def _generate_markdown(self, log: DailyLog) -> str:
        """Generate markdown for a daily log per spec Section 10.3 format.
        
        Args:
            log: The DailyLog to render
            
        Returns:
            Markdown string
        """
        lines = [f"# Daily Log: {log.date}", ""]
        
        # Standups section
        if log.standups:
            lines.append("## Standups")
            lines.append("")
            for standup in log.standups:
                lines.append(f"### Standup at {standup.time}")
                lines.append("")
                if standup.yesterday_goals:
                    lines.append("**Yesterday's Goals:**")
                    for goal in standup.yesterday_goals:
                        icon = self._get_status_icon(goal.status)
                        lines.append(f"- {icon} [{goal.priority}] {goal.content}")
                    lines.append("")
                if standup.today_goals:
                    lines.append("**Today's Goals:**")
                    for goal in standup.today_goals:
                        icon = self._get_status_icon(goal.status)
                        time_str = f" ({goal.estimated_minutes}m)" if goal.estimated_minutes else ""
                        lines.append(f"- {icon} [{goal.priority}] {goal.content}{time_str}")
                    lines.append("")
                if standup.notes:
                    lines.append(f"**Notes:** {standup.notes}")
                    lines.append("")
        
        # Work log section
        if log.work_log:
            lines.append("## Work Log")
            lines.append("")
            for entry in log.work_log:
                duration = f" ({entry.duration_minutes}m)" if entry.duration_minutes else ""
                lines.append(f"- **{entry.time}**{duration}: {entry.description}")
                if entry.outcome:
                    lines.append(f"  - Outcome: {entry.outcome}")
            lines.append("")
        
        # Summary section
        if log.summary:
            lines.append("## Summary")
            lines.append("")
            if log.summary.accomplishments:
                lines.append("### Accomplishments")
                for item in log.summary.accomplishments:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.blockers:
                lines.append("### Blockers")
                for item in log.summary.blockers:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.learnings:
                lines.append("### Learnings")
                for item in log.summary.learnings:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.mood:
                lines.append(f"**Mood:** {log.summary.mood}")
            if log.summary.productivity_score is not None:
                lines.append(f"**Productivity Score:** {log.summary.productivity_score}/10")
        
        return "\n".join(lines)

    def add_standup(self, standup: StandupSession) -> None:
        """Add a standup session to today's log.
        
        Args:
            standup: The StandupSession to add
        """
        log = self.get_today()
        log.standups.append(standup)
        self.save_log(log)

    def add_work_entry(self, entry: WorkLogEntry) -> None:
        """Add a work log entry to today's log.
        
        Args:
            entry: The WorkLogEntry to add
        """
        log = self.get_today()
        log.work_log.append(entry)
        self.save_log(log)

    def set_summary(self, summary: DailySummary) -> None:
        """Set the end-of-day summary for today's log.
        
        Args:
            summary: The DailySummary to set
        """
        log = self.get_today()
        log.summary = summary
        self.save_log(log)

    def append_decision(self, decision: Decision) -> None:
        """Append a decision to the decisions.jsonl file.
        
        Args:
            decision: The Decision to append
        """
        with open(self.decisions_path, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    def get_decisions(
        self,
        since: Optional[datetime] = None,
        decision_type: Optional[str] = None,
    ) -> list[Decision]:
        """Query the decision log.
        
        Args:
            since: Only return decisions after this timestamp
            decision_type: Only return decisions of this type
            
        Returns:
            List of matching decisions
        """
        if not self.decisions_path.exists():
            return []
        
        decisions = []
        with open(self.decisions_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    decision = Decision.from_dict(data)
                    
                    # Filter by timestamp
                    if since is not None:
                        decision_time = datetime.fromisoformat(decision.timestamp)
                        if decision_time < since:
                            continue
                    
                    # Filter by type
                    if decision_type is not None:
                        if decision.decision_type != decision_type:
                            continue
                    
                    decisions.append(decision)
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return decisions

    def get_history(self, days: int) -> list[DailyLog]:
        """Get logs for the last N days.
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            List of DailyLog objects (most recent first)
        """
        logs = []
        today = date.today()
        
        for i in range(days):
            log_date = today - timedelta(days=i)
            log = self.get_log(log_date)
            if log is not None:
                logs.append(log)
        
        return logs