"""DailyLogManager: Manages daily log persistence."""

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

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
        """Initialize with base storage path."""
        self._base_path = Path(base_path)
        self._daily_log_path = self._base_path / "daily-log"
        self._daily_log_path.mkdir(parents=True, exist_ok=True)
        self._weekly_summary_path = self._base_path / "weekly-summary"
        self._weekly_summary_path.mkdir(parents=True, exist_ok=True)
        self._decisions_path = self._base_path / "decisions.jsonl"

    def _log_path_json(self, log_date: date) -> Path:
        """Get JSON log path for a date."""
        return self._daily_log_path / f"{log_date.isoformat()}.json"

    def _log_path_md(self, log_date: date) -> Path:
        """Get markdown log path for a date."""
        return self._daily_log_path / f"{log_date.isoformat()}.md"

    def get_log(self, log_date: date) -> Optional[DailyLog]:
        """Get daily log for a specific date."""
        json_path = self._log_path_json(log_date)
        if not json_path.exists():
            return None
        
        try:
            data = json.loads(json_path.read_text())
            return DailyLog.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def get_today(self) -> DailyLog:
        """Get or create today's log."""
        today = date.today()
        log = self.get_log(today)
        if log is None:
            log = DailyLog(date=today.isoformat())
            self.save_log(log)
        return log

    def get_yesterday(self) -> Optional[DailyLog]:
        """Get yesterday's log if it exists."""
        yesterday = date.today() - timedelta(days=1)
        return self.get_log(yesterday)

    def save_log(self, log: DailyLog) -> None:
        """Save daily log to disk (both .md and .json)."""
        log.updated_at = datetime.now().isoformat()
        log_date = date.fromisoformat(log.date)
        
        json_path = self._log_path_json(log_date)
        md_path = self._log_path_md(log_date)
        
        # Atomic write for JSON
        self._save_atomic(json_path, json.dumps(log.to_dict(), indent=2))
        
        # Generate and save markdown
        md_content = self._generate_markdown(log)
        self._save_atomic(md_path, md_content)

    def _save_atomic(self, path: Path, content: str) -> None:
        """Atomic write with temp file and rename."""
        temp_path = path.with_suffix(".tmp")
        backup_path = path.with_suffix(".bak")
        
        try:
            temp_path.write_text(content)
            
            if path.exists():
                shutil.copy2(path, backup_path)
            
            temp_path.rename(path)
            backup_path.unlink(missing_ok=True)
        except Exception:
            if backup_path.exists():
                backup_path.rename(path)
            raise

    def _generate_markdown(self, log: DailyLog) -> str:
        """Generate markdown representation of log."""
        lines = [f"# Daily Log: {log.date}", ""]
        
        for standup in log.standups:
            lines.append(f"## Standup - {standup.time}")
            lines.append(f"- **Session ID:** {standup.session_id}")
            lines.append("")
            
            if standup.yesterday_goals:
                lines.append("### Yesterday's Goals")
                lines.append("| Goal | Status |")
                lines.append("|------|--------|")
                for goal in standup.yesterday_goals:
                    lines.append(f"| {goal.content} | {goal.status.value} |")
                lines.append("")
            
            if standup.today_goals:
                lines.append("### Today's Goals")
                lines.append("| Priority | Goal | Status |")
                lines.append("|----------|------|--------|")
                for goal in standup.today_goals:
                    lines.append(f"| {goal.priority} | {goal.content} | {goal.status.value} |")
                lines.append("")
            
            if standup.philip_notes:
                lines.append("### Notes")
                lines.append(f"> {standup.philip_notes}")
                lines.append("")
        
        if log.work_log:
            lines.append("## Work Log")
            lines.append("")
            for entry in log.work_log:
                lines.append(f"### {entry.timestamp}")
                lines.append(f"- **Action:** {entry.action}")
                lines.append(f"- **Result:** {entry.result}")
                if entry.cost_usd > 0:
                    lines.append(f"- **Cost:** ${entry.cost_usd:.2f}")
                lines.append("")
        
        if log.summary:
            lines.append("## Summary")
            lines.append(f"- **Goals Completed:** {log.summary.goals_completed}/{log.summary.goals_total}")
            lines.append(f"- **Total Cost:** ${log.summary.total_cost_usd:.2f}")
            lines.append("")
            if log.summary.key_accomplishments:
                lines.append("### Key Accomplishments")
                for item in log.summary.key_accomplishments:
                    lines.append(f"- {item}")
                lines.append("")
            if log.summary.blockers_for_tomorrow:
                lines.append("### Blockers for Tomorrow")
                for item in log.summary.blockers_for_tomorrow:
                    lines.append(f"- {item}")
                lines.append("")
        
        return "\n".join(lines)

    def add_standup(self, standup: StandupSession) -> None:
        """Add a standup session to today's log."""
        log = self.get_today()
        log.standups.append(standup)
        self.save_log(log)

    def add_work_entry(self, entry: WorkLogEntry) -> None:
        """Add a work log entry to today's log."""
        log = self.get_today()
        log.work_log.append(entry)
        self.save_log(log)

    def set_summary(self, summary: DailySummary) -> None:
        """Set end-of-day summary."""
        log = self.get_today()
        log.summary = summary
        self.save_log(log)

    def append_decision(self, decision: Decision) -> None:
        """Append decision to decisions.jsonl."""
        with open(self._decisions_path, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    def get_decisions(
        self,
        since: Optional[datetime] = None,
        decision_type: Optional[str] = None,
    ) -> list[Decision]:
        """Query decisions from the JSONL log."""
        if not self._decisions_path.exists():
            return []
        
        decisions = []
        with open(self._decisions_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    decision = Decision.from_dict(data)
                    
                    if since is not None:
                        decision_time = datetime.fromisoformat(decision.timestamp)
                        # Normalize: strip timezone for comparison (handle TZ-aware vs naive)
                        decision_time_naive = decision_time.replace(tzinfo=None)
                        if decision_time_naive < since:
                            continue
                    
                    if decision_type is not None and decision.type != decision_type:
                        continue
                    
                    decisions.append(decision)
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return decisions

    def get_history(self, days: int = 7) -> list[DailyLog]:
        """Get logs for the last N days."""
        logs = []
        today = date.today()
        for i in range(days):
            log_date = today - timedelta(days=i)
            log = self.get_log(log_date)
            if log is not None:
                logs.append(log)
        return logs

    def generate_weekly_summary(self, week: int, year: int) -> str:
        """Generate weekly summary markdown."""
        lines = [f"# Weekly Summary: {year}-W{week:02d}", ""]
        
        # Get logs for this week
        from datetime import date as date_cls
        week_start = date_cls.fromisocalendar(year, week, 1)
        
        total_goals_completed = 0
        total_goals = 0
        total_cost = 0.0
        
        for i in range(7):
            log_date = week_start + timedelta(days=i)
            log = self.get_log(log_date)
            if log is not None and log.summary is not None:
                total_goals_completed += log.summary.goals_completed
                total_goals += log.summary.goals_total
                total_cost += log.summary.total_cost_usd
        
        lines.append(f"- **Goals Completed:** {total_goals_completed}/{total_goals}")
        if total_goals > 0:
            rate = total_goals_completed / total_goals * 100
            lines.append(f"- **Completion Rate:** {rate:.1f}%")
        lines.append(f"- **Total Cost:** ${total_cost:.2f}")
        
        return "\n".join(lines)