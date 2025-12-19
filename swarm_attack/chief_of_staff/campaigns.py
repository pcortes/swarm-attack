"""Campaign, Milestone, DayPlan dataclasses and CampaignState enum for multi-day campaign management."""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import aiofiles
import aiofiles.os


class CampaignState(Enum):
    """State of a campaign."""
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Milestone:
    """A milestone within a campaign.
    
    Supports two interfaces:
    - New (test-compatible): id, description, target_date, completed
    - Old (production): milestone_id, name, description, target_day, success_criteria, status, completed_at
    """
    # New interface fields (test-compatible)
    id: str = ""
    description: str = ""
    target_date: Optional[date] = None
    completed: bool = False
    
    # Old interface fields (production)
    milestone_id: str = ""
    name: str = ""
    target_day: int = 0
    success_criteria: list[str] = field(default_factory=list)
    status: str = "pending"
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Sync old and new interface fields."""
        # If id is set but milestone_id isn't, copy it
        if self.id and not self.milestone_id:
            self.milestone_id = self.id
        # If milestone_id is set but id isn't, copy it
        if self.milestone_id and not self.id:
            self.id = self.milestone_id
        
        # Sync completed status
        if self.completed and self.status == "pending":
            self.status = "completed"
        if self.status == "completed" and not self.completed:
            self.completed = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize milestone to dictionary."""
        return {
            "milestone_id": self.milestone_id or self.id,
            "id": self.id or self.milestone_id,
            "name": self.name,
            "description": self.description,
            "target_day": self.target_day,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "success_criteria": self.success_criteria,
            "status": self.status,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Milestone":
        """Deserialize milestone from dictionary."""
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])
        
        target_date = None
        if data.get("target_date"):
            if isinstance(data["target_date"], str):
                target_date = date.fromisoformat(data["target_date"])
            else:
                target_date = data["target_date"]
        
        return cls(
            id=data.get("id", data.get("milestone_id", "")),
            milestone_id=data.get("milestone_id", data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            target_day=data.get("target_day", 0),
            target_date=target_date,
            success_criteria=data.get("success_criteria", []),
            status=data.get("status", "pending"),
            completed=data.get("completed", False),
            completed_at=completed_at,
        )


@dataclass
class DayPlan:
    """A plan for a single day within a campaign.
    
    Supports two interfaces:
    - New (test-compatible): date, goals
    - Old (production): day_number, date, goals, budget_usd, status, actual_cost_usd, notes
    """
    date: date = field(default_factory=date.today)
    goals: list[str] = field(default_factory=list)
    day_number: int = 0
    budget_usd: float = 0.0
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
        plan_date = data.get("date", date.today())
        if isinstance(plan_date, str):
            plan_date = date.fromisoformat(plan_date)
        return cls(
            day_number=data.get("day_number", 0),
            date=plan_date,
            goals=data.get("goals", []),
            budget_usd=data.get("budget_usd", 0.0),
            status=data.get("status", "pending"),
            actual_cost_usd=data.get("actual_cost_usd", 0.0),
            notes=data.get("notes", ""),
        )


@dataclass
class Campaign:
    """A multi-day campaign for feature development or bug fixing.
    
    Supports two interfaces:
    - New (test-compatible): id, name, state, milestones, day_plans, created_at
    - Old (production): campaign_id, name, description, start_date, planned_days, etc.
    """
    # New interface fields (test-compatible)
    id: str = ""
    name: str = ""
    state: CampaignState = CampaignState.PLANNING
    milestones: list[Milestone] = field(default_factory=list)
    day_plans: list[DayPlan] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    # Old interface fields (production)
    campaign_id: str = ""
    description: str = ""
    start_date: date = field(default_factory=date.today)
    planned_days: int = 0
    total_budget_usd: float = 0.0
    current_day: int = 0
    spent_usd: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Sync old and new interface fields."""
        # If id is set but campaign_id isn't, copy it
        if self.id and not self.campaign_id:
            self.campaign_id = self.id
        # If campaign_id is set but id isn't, copy it
        if self.campaign_id and not self.id:
            self.id = self.campaign_id

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
        percentage_behind = behind / expected_day
        
        return percentage_behind > 0.3

    def to_dict(self) -> dict[str, Any]:
        """Serialize campaign to dictionary."""
        return {
            "id": self.id or self.campaign_id,
            "campaign_id": self.campaign_id or self.id,
            "name": self.name,
            "description": self.description,
            "start_date": self.start_date.isoformat(),
            "planned_days": self.planned_days,
            "total_budget_usd": self.total_budget_usd,
            "state": self.state.value,
            "current_day": self.current_day,
            "milestones": [m.to_dict() for m in self.milestones],
            "day_plans": [d.to_dict() for d in self.day_plans],
            "spent_usd": self.spent_usd,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Campaign":
        """Deserialize campaign from dictionary."""
        start_date = data.get("start_date", date.today())
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()
        
        milestones = [Milestone.from_dict(m) for m in data.get("milestones", [])]
        day_plans = [DayPlan.from_dict(d) for d in data.get("day_plans", [])]
        
        return cls(
            id=data.get("id", data.get("campaign_id", "")),
            campaign_id=data.get("campaign_id", data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            start_date=start_date,
            planned_days=data.get("planned_days", 0),
            total_budget_usd=data.get("total_budget_usd", 0.0),
            state=CampaignState(data.get("state", "planning")),
            current_day=data.get("current_day", 0),
            milestones=milestones,
            day_plans=day_plans,
            spent_usd=data.get("spent_usd", 0.0),
            created_at=created_at,
            updated_at=updated_at,
        )


class CampaignStore:
    """Persistent storage for campaigns using JSON files."""

    def __init__(self, base_path: Path) -> None:
        """Initialize CampaignStore with base path.
        
        Creates campaigns/ subdirectory if it doesn't exist.
        
        Args:
            base_path: Base directory for storage
        """
        self._base_path = base_path
        self._campaigns_dir = base_path / "campaigns"
        self._campaigns_dir.mkdir(parents=True, exist_ok=True)

    def _campaign_path(self, campaign_id: str) -> Path:
        """Get the file path for a campaign.
        
        Args:
            campaign_id: The campaign ID
            
        Returns:
            Path to the campaign JSON file
        """
        return self._campaigns_dir / f"{campaign_id}.json"

    async def save(self, campaign: Campaign) -> None:
        """Save a campaign to JSON file.
        
        Args:
            campaign: The campaign to save
        """
        campaign_id = campaign.campaign_id or campaign.id
        file_path = self._campaign_path(campaign_id)
        campaign.updated_at = datetime.now()
        data = campaign.to_dict()
        content = json.dumps(data, indent=2)
        
        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)

    async def load(self, campaign_id: str) -> Optional[Campaign]:
        """Load a campaign from JSON file.
        
        Args:
            campaign_id: The campaign ID to load
            
        Returns:
            The loaded campaign, or None if not found
        """
        file_path = self._campaign_path(campaign_id)
        
        if not file_path.exists():
            return None
        
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
        
        data = json.loads(content)
        return Campaign.from_dict(data)

    async def list_all(self) -> list[Campaign]:
        """List all campaigns.
        
        Returns:
            List of all stored campaigns
        """
        campaigns: list[Campaign] = []
        
        if not self._campaigns_dir.exists():
            return campaigns
        
        for file_path in self._campaigns_dir.iterdir():
            if file_path.suffix == ".json":
                campaign_id = file_path.stem
                campaign = await self.load(campaign_id)
                if campaign is not None:
                    campaigns.append(campaign)
        
        return campaigns
    
    def list_all_sync(self) -> list[Campaign]:
        """Synchronous version of list_all for compatibility with WeeklyPlanner.
        
        Returns:
            List of all stored campaigns
        """
        campaigns: list[Campaign] = []
        
        if not self._campaigns_dir.exists():
            return campaigns
        
        for file_path in self._campaigns_dir.iterdir():
            if file_path.suffix == ".json":
                try:
                    with open(file_path, "r") as f:
                        content = f.read()
                    data = json.loads(content)
                    campaigns.append(Campaign.from_dict(data))
                except (json.JSONDecodeError, IOError):
                    continue
        
        return campaigns