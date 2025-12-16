"""DailyLogManager for persistence of daily logs and decisions.

This module handles reading/writing daily logs in both markdown and JSON formats,
plus the append-only decision log.
"""

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from swarm_attack.chief_of_staff.models import (
    DailyLog,
    DailySummary,
    Decision,
    StandupSession,
    WorkLogEntry,
)


class DailyLogManager:
    """Manages daily log persistence."""

    def __init__(self, base_path: Path) -> None:
        """Initialize with base storage path.
        
        Creates the directory structure:
        - {base_path}/daily-log/
        - {base_path}/weekly-summary/
        
        Args:
            base_path: Base directory for chief-of-staff storage.
        """
        self.base_path = Path(base_path)
        self.daily_log_dir = self.base_path / "daily-log"
        self.weekly_summary_dir = self.base_path / "weekly-summary"
        self.decisions_path = self.base_path / "decisions.jsonl"
        
        # Create directories
        self.daily_log_dir.mkdir(parents=True, exist_ok=True)
        self.weekly_summary_dir.mkdir(parents=True, exist_ok=True)

    def _json_path(self, log_date: str) -> Path:
        """Get JSON file path for a date."""
        return self.daily_log_dir / f"{log_date}.json"

    def _md_path(self, log_date: str) -> Path:
        """Get markdown file path for a date."""
        return self.daily_log_dir / f"{log_date}.md"

    def _save_atomic(self, path: Path, content: str) -> None:
        """Atomic write with temp file and rename."""
        temp_path = path.with_suffix(path.suffix + ".tmp")
        backup_path = path.with_suffix(path.suffix + ".bak")

        try:
            temp_path.write_text(content)

            if path.exists():
                shutil.copy2(path, backup_path)

            temp_path.rename(path)
            
            if backup_path.exists():
                backup_path.unlink()

        except Exception:
            if backup_path.exists():
                shutil.copy2(backup_path, path)
            if temp_path.exists():
                temp_path.unlink()
            raise
        finally:
            # Clean up any remaining temp files
            if temp_path.exists():
                temp_path.unlink()

    def get_log(self, log_date: date) -> Optional[DailyLog]:
        """Get daily log for a specific date.
        
        Args:
            log_date: The date to retrieve the log for.
            
        Returns:
            DailyLog if it exists, None otherwise.
        """
        date_str = log_date.isoformat()
        json_path = self._json_path(date_str)
        
        if not json_path.exists():
            return None
        
        try:
            data = json.loads(json_path.read_text())
            return DailyLog.from_dict(data)
        except (json.JSONDecodeError, Exception):
            # Handle corrupted JSON gracefully
            return None

    def get_today(self) -> DailyLog:
        """Get or create today's log.
        
        Returns:
            DailyLog for today, creating a new one if it doesn't exist.
        """
        today = date.today()
        log = self.get_log(today)
        
        if log is None:
            now = datetime.now().isoformat()
            log = DailyLog(
                date=today.isoformat(),
                created_at=now,
                updated_at=now,
            )
            self.save_log(log)
        
        return log

    def get_yesterday(self) -> Optional[DailyLog]:
        """Get yesterday's log if it exists.
        
        Returns:
            DailyLog for yesterday if it exists, None otherwise.
        """
        yesterday = date.today() - timedelta(days=1)
        return self.get_log(yesterday)

    def save_log(self, log: DailyLog) -> None:
        """Save daily log to disk (both .md and .json).
        
        Uses atomic file writes to prevent corruption.
        
        Args:
            log: The DailyLog to save.
        """
        # Update the updated_at timestamp
        log.updated_at = datetime.now().isoformat()
        
        # Save JSON
        json_content = json.dumps(log.to_dict(), indent=2)
        self._save_atomic(self._json_path(log.date), json_content)
        
        # Save Markdown
        md_content = self._generate_markdown(log)
        self._save_atomic(self._md_path(log.date), md_content)

    def _generate_markdown(self, log: DailyLog) -> str:
        """Generate markdown representation of a daily log."""
        lines = [f"# Daily Log: {log.date}", ""]
        
        # Standups section
        if log.standups:
            lines.append("## Standups")
            lines.append("")
            for standup in log.standups:
                lines.append(f"### Standup: {standup.session_id}")
                lines.append(f"- **Time:** {standup.time}")
                lines.append(f"- **Session ID:** {standup.session_id}")
                if standup.philip_notes:
                    lines.append(f"- **Notes:** {standup.philip_notes}")
                lines.append("")
                
                if standup.yesterday_goals:
                    lines.append("#### Yesterday's Goals")
                    for goal in standup.yesterday_goals:
                        lines.append(f"- [{goal.status.value}] {goal.content}")
                    lines.append("")
                
                if standup.today_goals:
                    lines.append("#### Today's Goals")
                    for goal in standup.today_goals:
                        lines.append(f"- [{goal.priority}] {goal.content}")
                    lines.append("")
        
        # Work Log section
        if log.work_log:
            lines.append("## Work Log")
            lines.append("")
            for entry in log.work_log:
                lines.append(f"### {entry.timestamp}")
                lines.append(f"- **Action:** {entry.action}")
                lines.append(f"- **Result:** {entry.result}")
                if entry.cost_usd > 0:
                    lines.append(f"- **Cost:** ${entry.cost_usd:.2f}")
                if entry.checkpoint:
                    lines.append(f"- **Checkpoint:** {entry.checkpoint}")
                lines.append("")
        
        # Summary section
        if log.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(f"- **Goals Completed:** {log.summary.goals_completed}/{log.summary.goals_total}")
            lines.append(f"- **Total Cost:** ${log.summary.total_cost_usd:.2f}")
            
            if log.summary.key_accomplishments:
                lines.append("")
                lines.append("### Key Accomplishments")
                for item in log.summary.key_accomplishments:
                    lines.append(f"- {item}")
            
            if log.summary.blockers_for_tomorrow:
                lines.append("")
                lines.append("### Blockers for Tomorrow")
                for item in log.summary.blockers_for_tomorrow:
                    lines.append(f"- {item}")
            
            if log.summary.carryover_goals:
                lines.append("")
                lines.append("### Carryover Goals")
                for goal in log.summary.carryover_goals:
                    lines.append(f"- [{goal.priority}] {goal.content}")
            lines.append("")
        
        return "\n".join(lines)

    def add_standup(self, standup: StandupSession) -> None:
        """Add a standup session to today's log.
        
        Args:
            standup: The StandupSession to add.
        """
        log = self.get_today()
        log.standups.append(standup)
        self.save_log(log)

    def add_work_entry(self, entry: WorkLogEntry) -> None:
        """Add a work log entry to today's log.
        
        Args:
            entry: The WorkLogEntry to add.
        """
        log = self.get_today()
        log.work_log.append(entry)
        self.save_log(log)

    def set_summary(self, summary: DailySummary) -> None:
        """Set end-of-day summary.
        
        Replaces any existing summary.
        
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
        line = json.dumps(decision.to_dict()) + "\n"
        
        with open(self.decisions_path, "a") as f:
            f.write(line)

    def get_decisions(
        self,
        since: Optional[datetime] = None,
        decision_type: Optional[str] = None,
    ) -> list[Decision]:
        """Query decisions from the JSONL log.
        
        Args:
            since: Only return decisions after this datetime.
            decision_type: Only return decisions of this type.
            
        Returns:
            List of matching Decision objects.
        """
        if not self.decisions_path.exists():
            return []
        
        decisions = []
        
        try:
            with open(self.decisions_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        decision = Decision.from_dict(data)
                        
                        # Apply filters
                        if decision_type and decision.type != decision_type:
                            continue
                        
                        if since:
                            # Parse the decision timestamp
                            decision_time = datetime.fromisoformat(
                                decision.timestamp.replace("Z", "+00:00")
                            )
                            # Make since timezone-aware if decision_time is
                            if decision_time.tzinfo is not None and since.tzinfo is None:
                                since_aware = since.replace(tzinfo=decision_time.tzinfo)
                            else:
                                since_aware = since
                            
                            # Compare naive datetimes if needed
                            if decision_time.tzinfo is not None:
                                decision_time_naive = decision_time.replace(tzinfo=None)
                            else:
                                decision_time_naive = decision_time
                            
                            if decision_time_naive < since.replace(tzinfo=None) if since.tzinfo else since:
                                continue
                        
                        decisions.append(decision)
                    except (json.JSONDecodeError, Exception):
                        # Skip corrupted lines
                        continue
        except Exception:
            return []
        
        return decisions

    def get_history(self, days: int = 7) -> list[DailyLog]:
        """Get logs for the last N days.
        
        Args:
            days: Number of days to look back (default 7).
            
        Returns:
            List of DailyLog objects, sorted newest first.
        """
        logs = []
        today = date.today()
        
        for i in range(days):
            log_date = today - timedelta(days=i)
            log = self.get_log(log_date)
            if log is not None:
                logs.append(log)
        
        return logs

    def generate_weekly_summary(self, week: int, year: int) -> str:
        """Generate weekly summary markdown.
        
        Args:
            week: ISO week number.
            year: Year.
            
        Returns:
            Markdown string with weekly summary.
        """
        lines = [f"# Weekly Summary: {year}-W{week:02d}", ""]
        
        # Find dates for this week
        # ISO week 1 is the week containing Jan 4
        jan_4 = date(year, 1, 4)
        week_1_start = jan_4 - timedelta(days=jan_4.weekday())
        week_start = week_1_start + timedelta(weeks=week - 1)
        
        # Collect logs for this week
        week_logs = []
        total_cost = 0.0
        total_entries = 0
        
        for i in range(7):
            log_date = week_start + timedelta(days=i)
            log = self.get_log(log_date)
            if log:
                week_logs.append(log)
                for entry in log.work_log:
                    total_cost += entry.cost_usd
                    total_entries += 1
        
        if not week_logs:
            lines.append("No logs found for this week.")
            return "\n".join(lines)
        
        lines.append(f"## Overview")
        lines.append("")
        lines.append(f"- **Days with logs:** {len(week_logs)}")
        lines.append(f"- **Total work entries:** {total_entries}")
        lines.append(f"- **Total cost:** ${total_cost:.2f}")
        lines.append("")
        
        # Daily summaries
        lines.append("## Daily Summaries")
        lines.append("")
        
        for log in week_logs:
            lines.append(f"### {log.date}")
            if log.summary:
                lines.append(f"- Goals: {log.summary.goals_completed}/{log.summary.goals_total}")
                lines.append(f"- Cost: ${log.summary.total_cost_usd:.2f}")
            else:
                work_cost = sum(e.cost_usd for e in log.work_log)
                lines.append(f"- Work entries: {len(log.work_log)}")
                lines.append(f"- Cost: ${work_cost:.2f}")
            lines.append("")
        
        return "\n".join(lines)