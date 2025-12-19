"""Weekly planning and summary generation for Chief of Staff."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .campaigns import CampaignState


@dataclass
class WeeklySummary:
    """Summary of weekly progress and metrics."""
    
    week_start: date
    week_end: date
    active_campaigns: int
    completed_campaigns: int
    milestones_completed: int
    milestones_remaining: int
    goals_completed: int
    goals_failed: int
    goals_skipped: int
    total_cost: float
    next_week_goals: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeeklySummary":
        """Create WeeklySummary from dictionary."""
        week_start = data.get("week_start", "")
        week_end = data.get("week_end", "")
        
        # Parse date strings
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start)
        if isinstance(week_end, str):
            week_end = date.fromisoformat(week_end)
        
        return cls(
            week_start=week_start,
            week_end=week_end,
            active_campaigns=data.get("active_campaigns", 0),
            completed_campaigns=data.get("completed_campaigns", 0),
            milestones_completed=data.get("milestones_completed", 0),
            milestones_remaining=data.get("milestones_remaining", 0),
            goals_completed=data.get("goals_completed", 0),
            goals_failed=data.get("goals_failed", 0),
            goals_skipped=data.get("goals_skipped", 0),
            total_cost=data.get("total_cost", 0.0),
            next_week_goals=data.get("next_week_goals", []),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert WeeklySummary to dictionary."""
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "active_campaigns": self.active_campaigns,
            "completed_campaigns": self.completed_campaigns,
            "milestones_completed": self.milestones_completed,
            "milestones_remaining": self.milestones_remaining,
            "goals_completed": self.goals_completed,
            "goals_failed": self.goals_failed,
            "goals_skipped": self.goals_skipped,
            "total_cost": self.total_cost,
            "next_week_goals": self.next_week_goals,
        }


class WeeklyPlanner:
    """Generates weekly planning summaries and reports."""
    
    def __init__(
        self,
        campaign_store: Any,
        episode_store: Any,
        llm: Any = None,
    ) -> None:
        """Initialize WeeklyPlanner.
        
        Args:
            campaign_store: Store for campaign data.
            episode_store: Store for episode/execution history.
            llm: Language model for generating insights (optional).
        """
        self.campaign_store = campaign_store
        self.episode_store = episode_store
        self.llm = llm
    
    def _get_milestone_completed(self, milestone: Any) -> bool:
        """Get whether a milestone is completed, handling both old and new interfaces."""
        # New interface: milestone.completed (bool)
        if hasattr(milestone, 'completed'):
            return milestone.completed
        # Old interface: milestone.status == "completed" or milestone.completed_at is not None
        if hasattr(milestone, 'status'):
            return milestone.status == "completed"
        if hasattr(milestone, 'completed_at'):
            return milestone.completed_at is not None
        return False
    
    def _get_day_plan_date(self, day_plan: Any) -> date:
        """Get the date from a day plan."""
        if hasattr(day_plan, 'date'):
            return day_plan.date
        return date.today()
    
    def _get_day_plan_goals(self, day_plan: Any) -> list[str]:
        """Get the goals from a day plan."""
        if hasattr(day_plan, 'goals'):
            return day_plan.goals
        return []
    
    def generate_weekly_summary(self) -> WeeklySummary:
        """Generate a summary of the current week's progress.
        
        Returns:
            WeeklySummary with metrics from the current week.
        """
        today = date.today()
        # Get Monday of the current week
        week_start = today - timedelta(days=today.weekday())
        # Get Friday of the current week
        week_end = week_start + timedelta(days=4)
        
        # Get all campaigns
        campaigns = self.campaign_store.list_all_sync()
        
        # Count active and completed campaigns
        active_campaigns = sum(1 for c in campaigns if c.state == CampaignState.ACTIVE)
        completed_campaigns = sum(1 for c in campaigns if c.state == CampaignState.COMPLETED)
        
        # Count milestones across all campaigns
        milestones_completed = 0
        milestones_remaining = 0
        for campaign in campaigns:
            for milestone in campaign.milestones:
                if self._get_milestone_completed(milestone):
                    milestones_completed += 1
                else:
                    milestones_remaining += 1
        
        # Get episodes from the current week
        episodes = self.episode_store.list_episodes_in_range(week_start, week_end)
        
        # Count goals by outcome
        goals_completed = sum(1 for e in episodes if e.outcome == "completed")
        goals_failed = sum(1 for e in episodes if e.outcome == "failed")
        goals_skipped = sum(1 for e in episodes if e.outcome == "skipped")
        
        # Calculate total cost
        total_cost = sum(e.cost for e in episodes if hasattr(e, 'cost') and e.cost)
        
        # Project next week's goals
        next_week_goals = self._project_next_week()
        
        return WeeklySummary(
            week_start=week_start,
            week_end=week_end,
            active_campaigns=active_campaigns,
            completed_campaigns=completed_campaigns,
            milestones_completed=milestones_completed,
            milestones_remaining=milestones_remaining,
            goals_completed=goals_completed,
            goals_failed=goals_failed,
            goals_skipped=goals_skipped,
            total_cost=total_cost,
            next_week_goals=next_week_goals,
        )
    
    def generate_weekly_report(self) -> str:
        """Generate a human-readable weekly report in markdown format.
        
        Returns:
            Markdown string with the weekly report.
        """
        summary = self.generate_weekly_summary()
        campaigns = self.campaign_store.list_all_sync()
        
        report_lines = [
            f"# Weekly Report",
            f"",
            f"**Week:** {summary.week_start.isoformat()} to {summary.week_end.isoformat()}",
            f"",
            f"## Campaign Summary",
            f"",
            f"- Active campaigns: {summary.active_campaigns}",
            f"- Completed campaigns: {summary.completed_campaigns}",
            f"",
            f"## Milestone Progress",
            f"",
            f"- Milestones completed: {summary.milestones_completed}",
            f"- Milestones remaining: {summary.milestones_remaining}",
            f"",
            f"## Goal Execution",
            f"",
            f"- Goals completed: {summary.goals_completed}",
            f"- Goals failed: {summary.goals_failed}",
            f"- Goals skipped: {summary.goals_skipped}",
            f"- Total cost: ${summary.total_cost:.2f}",
            f"",
        ]
        
        if summary.next_week_goals:
            report_lines.append("## Next Week Goals")
            report_lines.append("")
            for goal in summary.next_week_goals:
                report_lines.append(f"- {goal}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def _project_next_week(self) -> list[str]:
        """Project goals for the next 5 working days.
        
        Returns:
            List of goal descriptions for the upcoming days.
        """
        today = date.today()
        # Get next 5 days (not necessarily working days, just days)
        next_5_days = set()
        for i in range(1, 6):
            next_5_days.add(today + timedelta(days=i))
        
        # Get all campaigns
        campaigns = self.campaign_store.list_all_sync()
        
        # Collect goals from active campaigns' day plans that fall in next 5 days
        upcoming_goals: list[str] = []
        for campaign in campaigns:
            if campaign.state != CampaignState.ACTIVE:
                continue
            for day_plan in campaign.day_plans:
                plan_date = self._get_day_plan_date(day_plan)
                if plan_date in next_5_days:
                    upcoming_goals.extend(self._get_day_plan_goals(day_plan))
        
        return upcoming_goals