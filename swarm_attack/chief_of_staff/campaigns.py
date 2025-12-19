"""Campaign, Milestone, DayPlan dataclasses and CampaignState enum for multi-day campaign management."""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any


class CampaignState(Enum):
    """State of a campaign."""
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Milestone:
    """A milestone within a campaign."""
    milestone_id: str
    name: str
    description: str
    target_day: int
    success_criteria: list[str]
    status: str = "pending"
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize milestone to dictionary."""
        return {
            "milestone_id": self.milestone_id,
            "name": self.name,
            "description": self.description,
            "target_day": self.target_day,
            "success_criteria": self.success_criteria,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Milestone":
        """Deserialize milestone from dictionary."""
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])
        return cls(
            milestone_id=data["milestone_id"],
            name=data["name"],
            description=data["description"],
            target_day=data["target_day"],
            success_criteria=data["success_criteria"],
            status=data.get("status", "pending"),
            completed_at=completed_at,
        )


@dataclass
class DayPlan:
    """A plan for a single day within a campaign."""
    day_number: int
    date: date
    goals: list[str]
    budget_usd: float
    status: str = "pending"
    actual_cost_usd: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize day plan to dictionary."""
        return {
            "day_number": self.day_number,
            "date": self.date.isoformat(),
            "goals": self.goals,
            "budget_usd": self.budget_usd,
            "status": self.status,
            "actual_cost_usd": self.actual_cost_usd,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DayPlan":
        """Deserialize day plan from dictionary."""
        plan_date = data["date"]
        if isinstance(plan_date, str):
            plan_date = date.fromisoformat(plan_date)
        return cls(
            day_number=data["day_number"],
            date=plan_date,
            goals=data["goals"],
            budget_usd=data["budget_usd"],
            status=data.get("status", "pending"),
            actual_cost_usd=data.get("actual_cost_usd", 0.0),
            notes=data.get("notes", ""),
        )


@dataclass
class Campaign:
    """A multi-day campaign for feature development or bug fixing."""
    campaign_id: str
    name: str
    description: str
    start_date: date
    planned_days: int
    total_budget_usd: float
    state: CampaignState = CampaignState.PLANNING
    current_day: int = 0
    milestones: list[Milestone] = field(default_factory=list)
    day_plans: list[DayPlan] = field(default_factory=list)
    spent_usd: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def days_behind(self) -> int:
        """Calculate how many days behind schedule the campaign is.
        
        Returns 0 for campaigns in PLANNING, COMPLETED, or FAILED states.
        For ACTIVE or PAUSED campaigns, calculates based on elapsed time vs current_day.
        """
        if self.state in (CampaignState.PLANNING, CampaignState.COMPLETED, CampaignState.FAILED):
            return 0
        
        today = date.today()
        elapsed_days = (today - self.start_date).days
        
        # Expected day is the minimum of elapsed days and planned days
        expected_day = min(elapsed_days, self.planned_days)
        
        # Days behind is how much current_day lags behind expected
        behind = expected_day - self.current_day
        return max(0, behind)

    def needs_replan(self) -> bool:
        """Check if campaign needs replanning (>30% behind schedule).
        
        Returns False for campaigns not in ACTIVE or PAUSED states.
        """
        if self.state not in (CampaignState.ACTIVE, CampaignState.PAUSED):
            return False
        
        if self.planned_days == 0:
            return False
        
        today = date.today()
        elapsed_days = (today - self.start_date).days
        expected_day = min(elapsed_days, self.planned_days)
        
        if expected_day == 0:
            return False
        
        # Calculate percentage behind
        behind = expected_day - self.current_day
        percent_behind = behind / expected_day
        
        # Need replan if MORE than 30% behind
        return percent_behind > 0.30

    def to_dict(self) -> dict[str, Any]:
        """Serialize campaign to dictionary."""
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "start_date": self.start_date.isoformat(),
            "planned_days": self.planned_days,
            "total_budget_usd": self.total_budget_usd,
            "state": self.state.value,
            "current_day": self.current_day,
            "milestones": [m.to_dict() for m in self.milestones],
            "day_plans": [dp.to_dict() for dp in self.day_plans],
            "spent_usd": self.spent_usd,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Campaign":
        """Deserialize campaign from dictionary."""
        start_date = data["start_date"]
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        
        state_value = data.get("state", "planning")
        state = CampaignState(state_value)
        
        milestones = [Milestone.from_dict(m) for m in data.get("milestones", [])]
        day_plans = [DayPlan.from_dict(dp) for dp in data.get("day_plans", [])]
        
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now()
        
        updated_at = data.get("updated_at")
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        else:
            updated_at = datetime.now()
        
        return cls(
            campaign_id=data["campaign_id"],
            name=data["name"],
            description=data["description"],
            start_date=start_date,
            planned_days=data["planned_days"],
            total_budget_usd=data["total_budget_usd"],
            state=state,
            current_day=data.get("current_day", 0),
            milestones=milestones,
            day_plans=day_plans,
            spent_usd=data.get("spent_usd", 0.0),
            created_at=created_at,
            updated_at=updated_at,
        )