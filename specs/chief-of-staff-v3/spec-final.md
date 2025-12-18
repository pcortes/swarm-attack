# Chief of Staff v3: Strategic Capability

## Expert Panel Consensus Document

**Panel Members:**
- Harrison Chase (LangChain) - Agent frameworks, state machines
- Jerry Liu (LlamaIndex) - Data agents, retrieval systems
- Kanjun Qiu (Imbue) - Reasoning agents, self-improvement
- David Dohan (Anthropic) - Tool safety, bounded autonomy
- Shunyu Yao (Princeton) - ReAct, Tree-of-Thought planning

**Date:** December 2025
**Status:** FINAL - Ready for Implementation
**Version:** v3 Strategic (20 issues)

---

## Prerequisites

**⚠️ IMPORTANT: v3 requires v2 completion**

This spec builds on the foundation established in v2 (24 issues):
- Real execution (Phase 7)
- Hierarchical recovery (Phase 8)
- Episode memory + Reflexion + Preferences (Phase 9)
- Early enhancements: Discovery, Interval Checkpoints, Progress Tracking

v3 adds strategic capability on top of v2's autonomous foundation.

---

## 1. Executive Summary

### What v2 Delivered
Chief of Staff v2 provides the **autonomous foundation**:
- Real orchestrator integration (no more stubs)
- 4-level automatic recovery
- Episode memory + Reflexion + Preference Learning
- Human-in-the-loop checkpoint system (P0)
- Discovery phase, interval checkpoints, progress tracking

### What v3 Adds
v3 adds **strategic capability** for multi-day planning and reduced human oversight:

| Capability | v2 State | v3 Target |
|------------|----------|-----------|
| Planning | Single-day horizon | **Multi-day campaigns + Weekly summaries** |
| Validation | Human reviews everything | **Internal critics pre-filter (~70% auto-approve)** |
| Risk Assessment | Basic triggers | **Multi-factor risk scoring engine** |
| Execution | Stop on failure | **Continue-on-block strategy** |
| Q&A Format | Simple options | **Enhanced format with tradeoffs + recommendations** |

### v3 Scope (20 Issues)

| Phase | Issues | Description |
|-------|--------|-------------|
| Phase 10 | 10.1-10.8 (8) | Multi-Day Campaigns + Weekly Planning |
| Phase 11 | 11.1-11.6 (6) | Internal Validation Critics |
| Phase 12 (Remaining) | 12.1, 12.2, 12.5, 12.7, 12.8, 12.9 (6) | Advanced World-Class Enhancements |


---

## 5. Phase 10: Multi-Day Campaigns + Weekly Planning (P4)

### Consensus Decision

**Shunyu Yao:** "Backward planning from goal state. Define milestones, then decompose into daily goals. Re-plan only when >30% off track."

**Harrison Chase:** "Add state machine for campaign lifecycle. PLANNING → ACTIVE → PAUSED → COMPLETED/FAILED. Persist everything."

**Jerry Liu:** "Campaign context needs to persist across days. Store in a campaign.json with all state."

**David Dohan:** "Budget caps must be per-campaign AND per-day. Daily cap prevents single-day runaway."

**PRD Requirement (User Story #6):** "I want a weekly planning session that projects forward, not just daily standups that look backward."

### 5.1 Campaign Data Model

```python
class CampaignState(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Milestone:
    """A major deliverable within a campaign."""
    milestone_id: str
    name: str
    description: str
    target_day: int           # Day 1, 2, 3, etc.
    success_criteria: list[str]
    status: str = "pending"   # pending, in_progress, done, blocked
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Milestone":
        return cls(**data)

@dataclass
class DayPlan:
    """Goals planned for a specific day of the campaign."""
    day_number: int
    date: str                 # YYYY-MM-DD
    goals: list[DailyGoal]
    budget_usd: float
    status: str = "pending"   # pending, in_progress, done
    actual_cost_usd: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "day_number": self.day_number,
            "date": self.date,
            "goals": [g.to_dict() for g in self.goals],
            "budget_usd": self.budget_usd,
            "status": self.status,
            "actual_cost_usd": self.actual_cost_usd,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DayPlan":
        return cls(
            day_number=data["day_number"],
            date=data["date"],
            goals=[DailyGoal.from_dict(g) for g in data["goals"]],
            budget_usd=data["budget_usd"],
            status=data["status"],
            actual_cost_usd=data.get("actual_cost_usd", 0.0),
            notes=data.get("notes", ""),
        )

@dataclass
class Campaign:
    """Multi-day development campaign."""
    campaign_id: str
    name: str
    goal: str                 # High-level goal
    milestones: list[Milestone]
    day_plans: list[DayPlan]

    # Tracking
    state: CampaignState = CampaignState.PLANNING
    current_day: int = 1
    started_at: Optional[str] = None
    ended_at: Optional[str] = None

    # Budgets (David's requirement)
    total_budget_usd: float = 50.0
    daily_budget_usd: float = 15.0
    spent_usd: float = 0.0

    # Replanning
    original_duration_days: int = 0
    replanning_threshold: float = 0.3  # 30% behind triggers replan
    replan_count: int = 0

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "goal": self.goal,
            "milestones": [m.to_dict() for m in self.milestones],
            "day_plans": [d.to_dict() for d in self.day_plans],
            "state": self.state.value,
            "current_day": self.current_day,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_budget_usd": self.total_budget_usd,
            "daily_budget_usd": self.daily_budget_usd,
            "spent_usd": self.spent_usd,
            "original_duration_days": self.original_duration_days,
            "replanning_threshold": self.replanning_threshold,
            "replan_count": self.replan_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        return cls(
            campaign_id=data["campaign_id"],
            name=data["name"],
            goal=data["goal"],
            milestones=[Milestone.from_dict(m) for m in data["milestones"]],
            day_plans=[DayPlan.from_dict(d) for d in data["day_plans"]],
            state=CampaignState(data["state"]),
            current_day=data["current_day"],
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            total_budget_usd=data.get("total_budget_usd", 50.0),
            daily_budget_usd=data.get("daily_budget_usd", 15.0),
            spent_usd=data.get("spent_usd", 0.0),
            original_duration_days=data.get("original_duration_days", 0),
            replanning_threshold=data.get("replanning_threshold", 0.3),
            replan_count=data.get("replan_count", 0),
        )

    def days_behind(self) -> int:
        """Calculate how many days behind schedule."""
        if self.state != CampaignState.ACTIVE:
            return 0

        if self.original_duration_days == 0:
            return 0

        planned_progress = self.current_day / self.original_duration_days
        completed_milestones = len([m for m in self.milestones if m.status == "done"])
        actual_progress = completed_milestones / len(self.milestones) if self.milestones else 0

        if actual_progress < planned_progress:
            return int((planned_progress - actual_progress) * self.original_duration_days)
        return 0

    def needs_replan(self) -> bool:
        """Check if campaign is far enough behind to trigger replan."""
        if len(self.milestones) == 0 or self.original_duration_days == 0:
            return False

        progress_gap = self.days_behind() / self.original_duration_days
        return progress_gap > self.replanning_threshold
```

### 5.2 Campaign Planner

```python
class CampaignPlanner:
    """Plans multi-day campaigns using backward planning."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def plan(
        self,
        goal: str,
        deadline_days: Optional[int] = None,
        budget_usd: Optional[float] = None,
    ) -> Campaign:
        """Create campaign plan using backward planning."""

        prompt = f"""
        Goal: {goal}
        {"Deadline: " + str(deadline_days) + " days" if deadline_days else "No fixed deadline"}
        {"Budget: $" + str(budget_usd) if budget_usd else "No fixed budget"}

        Using backward planning from the goal state:

        1. Define the END STATE (what does success look like?)
        2. Identify MILESTONES needed to reach end state
        3. Sequence milestones with dependencies
        4. Estimate days needed for each milestone
        5. Decompose each milestone into daily goals

        Return structured JSON with:
        - milestones: [{{name, description, target_day, success_criteria}}]
        - day_plans: [{{day_number, goals: [{{content, priority, estimated_minutes, linked_feature/bug/spec}}]}}]
        - total_estimated_days
        - total_estimated_cost_usd
        """

        plan_response = await self.llm.complete(prompt, max_tokens=2000)
        plan_data = json.loads(plan_response)

        campaign_id = f"camp-{uuid.uuid4().hex[:8]}"

        milestones = [
            Milestone(
                milestone_id=f"ms-{i+1}",
                name=m["name"],
                description=m["description"],
                target_day=m["target_day"],
                success_criteria=m.get("success_criteria", []),
            )
            for i, m in enumerate(plan_data["milestones"])
        ]

        day_plans = [
            DayPlan(
                day_number=d["day_number"],
                date="",  # Set when campaign starts
                goals=[DailyGoal.from_dict(g) for g in d["goals"]],
                budget_usd=budget_usd / len(plan_data["day_plans"]) if budget_usd else 15.0,
            )
            for d in plan_data["day_plans"]
        ]

        return Campaign(
            campaign_id=campaign_id,
            name=goal[:50],
            goal=goal,
            milestones=milestones,
            day_plans=day_plans,
            total_budget_usd=budget_usd or 50.0,
            daily_budget_usd=budget_usd / len(day_plans) if budget_usd else 15.0,
            original_duration_days=len(day_plans),
        )

    async def replan(self, campaign: Campaign) -> Campaign:
        """Replan remaining days of campaign."""

        completed = [m for m in campaign.milestones if m.status == "done"]
        remaining = [m for m in campaign.milestones if m.status != "done"]

        prompt = f"""
        Campaign: {campaign.name}
        Original goal: {campaign.goal}

        Completed milestones: {[m.name for m in completed]}
        Remaining milestones: {[m.name for m in remaining]}

        Days elapsed: {campaign.current_day}
        Budget spent: ${campaign.spent_usd:.2f}
        Budget remaining: ${campaign.total_budget_usd - campaign.spent_usd:.2f}

        Create revised plan for remaining milestones.
        Adjust estimates based on actual pace so far.

        Return JSON with updated day_plans for remaining work.
        """

        revised = await self.llm.complete(prompt, max_tokens=1500)
        revised_data = json.loads(revised)

        # Update remaining day plans
        new_day_plans = campaign.day_plans[:campaign.current_day]
        for d in revised_data["day_plans"]:
            new_day_plans.append(DayPlan(
                day_number=len(new_day_plans) + 1,
                date="",
                goals=[DailyGoal.from_dict(g) for g in d["goals"]],
                budget_usd=campaign.daily_budget_usd,
            ))

        campaign.day_plans = new_day_plans
        campaign.replan_count += 1

        return campaign
```

### 5.3 Campaign Executor

```python
class CampaignExecutor:
    """Executes campaign day by day."""

    def __init__(
        self,
        autopilot: AutopilotRunner,
        planner: CampaignPlanner,
        store: "CampaignStore",
        checkpoint_system: CheckpointSystem,
    ):
        self.autopilot = autopilot
        self.planner = planner
        self.store = store
        self.checkpoint_system = checkpoint_system

    async def execute_day(self, campaign: Campaign) -> "DayResult":
        """Execute one day of the campaign."""

        if campaign.state != CampaignState.ACTIVE:
            raise ValueError(f"Campaign not active: {campaign.state}")

        if campaign.current_day > len(campaign.day_plans):
            raise ValueError("No more days planned")

        # Check for milestone boundary checkpoint
        if self._at_milestone_boundary(campaign):
            checkpoint = await self._create_milestone_checkpoint(campaign)
            pending = await self.checkpoint_system.store.get_pending_for_goal(
                f"milestone-{campaign.campaign_id}"
            )
            if pending and pending.status != "approved":
                campaign.state = CampaignState.PAUSED
                await self.store.save(campaign)
                return DayResult(
                    campaign_id=campaign.campaign_id,
                    day=campaign.current_day,
                    goals_completed=0,
                    cost_usd=0,
                    campaign_progress=self._calculate_progress(campaign),
                    paused_for_checkpoint=True,
                )

        day_plan = campaign.day_plans[campaign.current_day - 1]

        # Run autopilot for today's goals
        result = await self.autopilot.start(
            goals=day_plan.goals,
            budget_usd=min(campaign.daily_budget_usd,
                          campaign.total_budget_usd - campaign.spent_usd),
        )

        # Update campaign state
        day_plan.actual_cost_usd = result.total_cost_usd
        day_plan.status = "done"
        campaign.spent_usd += result.total_cost_usd

        # Check if replan needed
        if campaign.needs_replan():
            campaign = await self.planner.replan(campaign)

        # Advance to next day
        campaign.current_day += 1

        # Check completion
        if campaign.current_day > len(campaign.day_plans):
            all_done = all(m.status == "done" for m in campaign.milestones)
            campaign.state = CampaignState.COMPLETED if all_done else CampaignState.FAILED
            campaign.ended_at = datetime.now().isoformat()

        # Persist
        await self.store.save(campaign)

        return DayResult(
            campaign_id=campaign.campaign_id,
            day=campaign.current_day - 1,
            goals_completed=result.goals_completed,
            cost_usd=result.total_cost_usd,
            campaign_progress=self._calculate_progress(campaign),
        )

    def _at_milestone_boundary(self, campaign: Campaign) -> bool:
        """Check if we're about to start a new milestone."""
        for milestone in campaign.milestones:
            if milestone.target_day == campaign.current_day and milestone.status == "pending":
                return True
        return False

    async def _create_milestone_checkpoint(self, campaign: Campaign) -> Checkpoint:
        """Create checkpoint at milestone boundary."""
        milestone = next(
            m for m in campaign.milestones
            if m.target_day == campaign.current_day and m.status == "pending"
        )
        checkpoint = Checkpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            trigger=CheckpointTrigger.SCOPE_CHANGE,
            context=f"Starting milestone '{milestone.name}': {milestone.description}",
            options=[
                CheckpointOption(label="Proceed", description="Start this milestone", is_recommended=True),
                CheckpointOption(label="Adjust", description="Modify milestone scope"),
                CheckpointOption(label="Pause", description="Pause campaign for review"),
            ],
            recommendation=f"Proceed with milestone: {milestone.name}",
            created_at=datetime.now().isoformat(),
            goal_id=f"milestone-{campaign.campaign_id}",
            campaign_id=campaign.campaign_id,
        )
        await self.checkpoint_system.store.save(checkpoint)
        return checkpoint

    def _calculate_progress(self, campaign: Campaign) -> float:
        """Calculate overall campaign progress 0-1."""
        if not campaign.milestones:
            return 0.0
        done = len([m for m in campaign.milestones if m.status == "done"])
        return done / len(campaign.milestones)

    async def resume(self, campaign_id: str) -> Campaign:
        """Resume a paused or next-day campaign."""
        campaign = await self.store.load(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")

        if campaign.state == CampaignState.PAUSED:
            campaign.state = CampaignState.ACTIVE

        return campaign

@dataclass
class DayResult:
    """Result of executing one day of a campaign."""
    campaign_id: str
    day: int
    goals_completed: int
    cost_usd: float
    campaign_progress: float
    paused_for_checkpoint: bool = False

class CampaignStore:
    """Persistent storage for campaigns."""

    def __init__(self, base_path: Path):
        self.base_path = base_path / "campaigns"
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, campaign: Campaign) -> None:
        """Save campaign to JSON file."""
        path = self.base_path / f"{campaign.campaign_id}.json"
        with open(path, "w") as f:
            json.dump(campaign.to_dict(), f, indent=2)

    async def load(self, campaign_id: str) -> Optional[Campaign]:
        """Load campaign from JSON file."""
        path = self.base_path / f"{campaign_id}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return Campaign.from_dict(json.load(f))

    async def list_all(self) -> list[Campaign]:
        """List all campaigns."""
        campaigns = []
        for path in self.base_path.glob("*.json"):
            with open(path, "r") as f:
                campaigns.append(Campaign.from_dict(json.load(f)))
        return campaigns
```

### 5.4 Weekly Planning (Minimal - PRD User Story #6)

```python
@dataclass
class WeeklySummary:
    """Weekly planning summary."""
    week_start: str
    week_end: str
    campaigns_active: list[str]
    campaigns_completed: list[str]
    milestones_completed: int
    milestones_remaining: int
    total_cost_usd: float
    goals_completed: int
    goals_failed: int
    next_week_projection: list[str]  # Projected goals for next week

    def to_dict(self) -> dict:
        return asdict(self)

class WeeklyPlanner:
    """Lightweight weekly planning using campaign data."""

    def __init__(
        self,
        campaign_store: CampaignStore,
        episode_store: EpisodeStore,
        llm: LLMClient,
    ):
        self.campaign_store = campaign_store
        self.episode_store = episode_store
        self.llm = llm

    async def generate_weekly_summary(self) -> WeeklySummary:
        """Generate weekly summary from campaign and episode data."""

        # Get this week's date range
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Load campaigns
        campaigns = await self.campaign_store.list_all()
        active = [c for c in campaigns if c.state == CampaignState.ACTIVE]
        completed = [c for c in campaigns if c.state == CampaignState.COMPLETED
                     and c.ended_at and c.ended_at >= week_start.isoformat()]

        # Load episodes from this week
        episodes = self.episode_store.load_recent(limit=500)
        week_episodes = [
            e for e in episodes
            if e.timestamp >= week_start.isoformat()
        ]

        # Calculate metrics
        milestones_completed = sum(
            len([m for m in c.milestones if m.status == "done"
                 and m.completed_at and m.completed_at >= week_start.isoformat()])
            for c in campaigns
        )
        milestones_remaining = sum(
            len([m for m in c.milestones if m.status != "done"])
            for c in active
        )

        goals_completed = len([e for e in week_episodes if e.outcome.success])
        goals_failed = len([e for e in week_episodes if not e.outcome.success])
        total_cost = sum(e.cost_usd for e in week_episodes)

        # Project next week
        next_week_projection = await self._project_next_week(active)

        return WeeklySummary(
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=week_end.strftime("%Y-%m-%d"),
            campaigns_active=[c.name for c in active],
            campaigns_completed=[c.name for c in completed],
            milestones_completed=milestones_completed,
            milestones_remaining=milestones_remaining,
            total_cost_usd=total_cost,
            goals_completed=goals_completed,
            goals_failed=goals_failed,
            next_week_projection=next_week_projection,
        )

    async def _project_next_week(self, active_campaigns: list[Campaign]) -> list[str]:
        """Project goals for next week based on active campaigns."""
        projections = []

        for campaign in active_campaigns:
            remaining_days = len(campaign.day_plans) - campaign.current_day + 1
            if remaining_days <= 0:
                continue

            # Get next 5 days of goals
            for i in range(min(5, remaining_days)):
                day_idx = campaign.current_day - 1 + i
                if day_idx < len(campaign.day_plans):
                    day_plan = campaign.day_plans[day_idx]
                    for goal in day_plan.goals[:2]:  # Top 2 goals per day
                        projections.append(f"[{campaign.name}] {goal.content}")

        return projections[:10]  # Top 10 projections

    async def generate_weekly_report(self) -> str:
        """Generate human-readable weekly report."""
        summary = await self.generate_weekly_summary()

        report = f"""
# Weekly Summary: {summary.week_start} to {summary.week_end}

## Campaigns
- Active: {', '.join(summary.campaigns_active) or 'None'}
- Completed this week: {', '.join(summary.campaigns_completed) or 'None'}

## Progress
- Milestones completed: {summary.milestones_completed}
- Milestones remaining: {summary.milestones_remaining}
- Goals completed: {summary.goals_completed}
- Goals failed: {summary.goals_failed}
- Total cost: ${summary.total_cost_usd:.2f}

## Next Week Projection
"""
        for proj in summary.next_week_projection:
            report += f"- {proj}\n"

        return report
```

### CLI Extensions

```bash
# Campaign management
swarm-attack cos campaign create "Implement auth system" --days 5 --budget 50
swarm-attack cos campaign status [CAMPAIGN_ID]
swarm-attack cos campaign list
swarm-attack cos campaign run [CAMPAIGN_ID]      # Execute today's goals
swarm-attack cos campaign resume [CAMPAIGN_ID]   # Resume paused campaign
swarm-attack cos campaign pause [CAMPAIGN_ID]
swarm-attack cos campaign replan [CAMPAIGN_ID]   # Force replan

# Weekly planning (PRD User Story #6)
swarm-attack cos weekly                          # Generate weekly summary
swarm-attack cos weekly --report                 # Full weekly report
```

### Implementation Tasks (8 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 10.1 | Create Campaign, Milestone, DayPlan dataclasses | M | - |
| 10.2 | Implement CampaignStore persistence | M | 10.1 |
| 10.3 | Implement CampaignPlanner.plan() | L | 10.1 |
| 10.4 | Implement CampaignPlanner.replan() | M | 10.3 |
| 10.5 | Implement CampaignExecutor.execute_day() | L | 10.1, Phase 7 |
| 10.6 | Add campaign CLI commands | M | 10.2, 10.5 |
| 10.7 | Add campaign progress to standup | S | 10.2 |
| 10.8 | Implement WeeklyPlanner and weekly CLI command | M | 10.2, 9.2 |

---

## 6. Phase 11: Internal Validation Critics (P5)

### Consensus Decision

**Kanjun Qiu:** "Use diverse critics - one for each quality dimension. They should disagree with each other to surface real issues."

**Harrison Chase:** "Majority voting for approval, but ANY security critic veto blocks. Safety is not a democracy."

**David Dohan:** "Track critic accuracy over time. If a critic is consistently wrong, reduce its weight. But never zero - preserve voice."

### 6.1 Critic Data Model

```python
class CriticFocus(Enum):
    COMPLETENESS = "completeness"
    FEASIBILITY = "feasibility"
    SECURITY = "security"         # Veto power
    STYLE = "style"
    COVERAGE = "coverage"
    EDGE_CASES = "edge_cases"

@dataclass
class CriticScore:
    critic_name: str
    focus: CriticFocus
    score: float              # 0-1
    approved: bool
    issues: list[str]
    suggestions: list[str]
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "critic_name": self.critic_name,
            "focus": self.focus.value,
            "score": self.score,
            "approved": self.approved,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CriticScore":
        return cls(
            critic_name=data["critic_name"],
            focus=CriticFocus(data["focus"]),
            score=data["score"],
            approved=data["approved"],
            issues=data["issues"],
            suggestions=data["suggestions"],
            reasoning=data["reasoning"],
        )

@dataclass
class ValidationResult:
    artifact_type: str        # "spec", "code", "test"
    artifact_id: str
    approved: bool
    scores: list[CriticScore]
    blocking_issues: list[str]
    consensus_summary: str
    human_review_required: bool

    def to_dict(self) -> dict:
        return {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "approved": self.approved,
            "scores": [s.to_dict() for s in self.scores],
            "blocking_issues": self.blocking_issues,
            "consensus_summary": self.consensus_summary,
            "human_review_required": self.human_review_required,
        }
```

### 6.2 Critic Implementations

```python
class Critic:
    """Base class for validation critics."""

    def __init__(self, focus: CriticFocus, llm: LLMClient, weight: float = 1.0):
        self.focus = focus
        self.llm = llm
        self.weight = weight
        self.has_veto = focus == CriticFocus.SECURITY

    async def evaluate(self, artifact: str) -> CriticScore:
        raise NotImplementedError

class SpecCritic(Critic):
    """Evaluates engineering specs."""

    async def evaluate(self, spec_content: str) -> CriticScore:
        focus_prompts = {
            CriticFocus.COMPLETENESS: "How complete is the spec? Missing sections? Gaps in requirements?",
            CriticFocus.FEASIBILITY: "Can this be implemented as written? Unclear requirements? Impossible constraints?",
            CriticFocus.SECURITY: "Security issues? Injection risks? Auth gaps? Data exposure?",
        }

        prompt = f"""
        Evaluate this engineering spec for {self.focus.value}:

        {spec_content[:4000]}

        {focus_prompts.get(self.focus, "")}

        Rate 0-1 and identify specific issues.
        Return JSON: {{"score": 0.0-1.0, "approved": true/false, "issues": [], "suggestions": [], "reasoning": ""}}
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)

        return CriticScore(
            critic_name=f"SpecCritic-{self.focus.value}",
            focus=self.focus,
            score=data["score"],
            approved=data["approved"],
            issues=data["issues"],
            suggestions=data["suggestions"],
            reasoning=data["reasoning"],
        )

class CodeCritic(Critic):
    """Evaluates code changes."""

    async def evaluate(self, code_diff: str) -> CriticScore:
        focus_prompts = {
            CriticFocus.STYLE: "Code style issues? Naming? Structure? Readability?",
            CriticFocus.SECURITY: "Security vulnerabilities? Injection? Unsafe operations? Secrets exposed?",
        }

        prompt = f"""
        Evaluate this code change for {self.focus.value}:

        {code_diff[:4000]}

        {focus_prompts.get(self.focus, "")}

        Rate 0-1 and identify specific issues.
        Return JSON: {{"score": 0.0-1.0, "approved": true/false, "issues": [], "suggestions": [], "reasoning": ""}}
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)

        return CriticScore(
            critic_name=f"CodeCritic-{self.focus.value}",
            focus=self.focus,
            score=data["score"],
            approved=data["approved"],
            issues=data["issues"],
            suggestions=data["suggestions"],
            reasoning=data["reasoning"],
        )

class TestCritic(Critic):
    """Evaluates test coverage and quality."""

    async def evaluate(self, test_content: str) -> CriticScore:
        focus_prompts = {
            CriticFocus.COVERAGE: "Test coverage adequate? Missing scenarios? Key paths untested?",
            CriticFocus.EDGE_CASES: "Edge cases covered? Boundary conditions? Error scenarios?",
        }

        prompt = f"""
        Evaluate these tests for {self.focus.value}:

        {test_content[:4000]}

        {focus_prompts.get(self.focus, "")}

        Rate 0-1 and identify specific issues.
        Return JSON: {{"score": 0.0-1.0, "approved": true/false, "issues": [], "suggestions": [], "reasoning": ""}}
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)

        return CriticScore(
            critic_name=f"TestCritic-{self.focus.value}",
            focus=self.focus,
            score=data["score"],
            approved=data["approved"],
            issues=data["issues"],
            suggestions=data["suggestions"],
            reasoning=data["reasoning"],
        )
```

### 6.3 Validation Layer

```python
class ValidationLayer:
    """Orchestrates multiple critics for consensus building."""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.critics = {
            "spec": [
                SpecCritic(CriticFocus.COMPLETENESS, llm),
                SpecCritic(CriticFocus.FEASIBILITY, llm),
                SpecCritic(CriticFocus.SECURITY, llm),
            ],
            "code": [
                CodeCritic(CriticFocus.STYLE, llm),
                CodeCritic(CriticFocus.SECURITY, llm),
            ],
            "test": [
                TestCritic(CriticFocus.COVERAGE, llm),
                TestCritic(CriticFocus.EDGE_CASES, llm),
            ],
        }

    async def validate(
        self,
        artifact: str,
        artifact_type: str,
        artifact_id: str = "",
    ) -> ValidationResult:
        """Run all relevant critics and build consensus."""

        relevant_critics = self.critics.get(artifact_type, [])
        if not relevant_critics:
            return ValidationResult(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                approved=True,
                scores=[],
                blocking_issues=[],
                consensus_summary="No critics configured for this artifact type",
                human_review_required=False,
            )

        # Run critics in parallel
        scores = await asyncio.gather(*[
            c.evaluate(artifact) for c in relevant_critics
        ])

        # Check for security veto
        security_scores = [s for s in scores if s.focus == CriticFocus.SECURITY]
        if any(not s.approved for s in security_scores):
            return ValidationResult(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                approved=False,
                scores=list(scores),
                blocking_issues=[
                    issue for s in security_scores if not s.approved for issue in s.issues
                ],
                consensus_summary="BLOCKED: Security concerns require human review",
                human_review_required=True,
            )

        # Majority vote (weighted)
        total_weight = sum(c.weight for c in relevant_critics)
        approval_weight = sum(
            c.weight for c, s in zip(relevant_critics, scores) if s.approved
        )

        approved = (approval_weight / total_weight) >= 0.6  # 60% threshold

        return ValidationResult(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            approved=approved,
            scores=list(scores),
            blocking_issues=[
                issue for s in scores if not s.approved for issue in s.issues
            ],
            consensus_summary=self._build_summary(list(scores), approved),
            human_review_required=not approved,
        )

    def _build_summary(self, scores: list[CriticScore], approved: bool) -> str:
        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0

        if approved:
            return f"APPROVED by consensus (avg score: {avg_score:.2f})"
        else:
            concerns = [s.focus.value for s in scores if not s.approved]
            return f"NEEDS REVIEW: concerns in {', '.join(concerns)} (avg: {avg_score:.2f})"
```

### 6.4 Integration Flow

The ValidationLayer integrates at three key points in the pipeline:

#### Spec Pipeline Integration

```python
# In Orchestrator.run_spec_pipeline()
class Orchestrator:
    async def run_spec_pipeline(self, feature_id: str) -> SpecResult:
        spec = await self._generate_spec(feature_id)

        # GATE: Validate before human approval
        validation = await self.validation_layer.validate(
            artifact=spec.content,
            artifact_type="spec",
            artifact_id=feature_id,
        )

        if validation.approved:
            # Auto-advance to approval (human still sees it)
            return SpecResult(
                status="ready_for_approval",
                validation=validation,
                auto_approved=True,
            )
        else:
            # Block and surface issues
            return SpecResult(
                status="needs_revision",
                validation=validation,
                blocking_issues=validation.blocking_issues,
            )
```

#### Code Execution Integration

```python
# In AutopilotRunner._execute_goal()
class AutopilotRunner:
    async def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        # ... existing execution logic ...

        if goal.linked_feature and result.success:
            # GATE: Validate code before marking complete
            code_diff = await self._get_code_diff(goal.linked_feature)
            validation = await self.validation_layer.validate(
                artifact=code_diff,
                artifact_type="code",
                artifact_id=f"{goal.linked_feature}-{goal.linked_issue}",
            )

            if not validation.approved:
                # Don't mark complete - needs fixes
                return GoalExecutionResult(
                    success=False,
                    error="Validation failed: " + validation.consensus_summary,
                    validation=validation,
                )

        return result
```

#### CLI Validation Command

```bash
# Manual validation check
swarm-attack cos validate spec chief-of-staff-v2
swarm-attack cos validate code swarm_attack/chief_of_staff/
```

```python
# In CLI
@cos_group.command("validate")
@click.argument("artifact_type", type=click.Choice(["spec", "code", "test"]))
@click.argument("path")
def validate_artifact(artifact_type: str, path: str):
    """Run validation critics on an artifact."""
    content = Path(path).read_text()
    result = asyncio.run(validation_layer.validate(content, artifact_type))

    if result.approved:
        click.echo(f"✓ APPROVED: {result.consensus_summary}")
    else:
        click.echo(f"✗ NEEDS REVIEW: {result.consensus_summary}")
        for issue in result.blocking_issues:
            click.echo(f"  - {issue}")
```

#### Gating Rules Summary

| Artifact | Gate Location | Auto-Approve Threshold | Human Required |
|----------|---------------|----------------------|----------------|
| Spec | Before `SPEC_NEEDS_APPROVAL` | 60% critic approval | Security veto OR <60% |
| Code | Before goal marked complete | 60% critic approval | Security veto OR <60% |
| Test | Before Verifier runs | 60% critic approval | Coverage <80% |

### Implementation Tasks (6 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 11.1 | Create Critic base class and CriticScore | S | - |
| 11.2 | Implement SpecCritic variants | M | 11.1 |
| 11.3 | Implement CodeCritic variants | M | 11.1 |
| 11.4 | Implement TestCritic variants | M | 11.1 |
| 11.5 | Implement ValidationLayer consensus | M | 11.2-11.4 |
| 11.6 | Integrate validation gates into pipelines | M | 11.5, Phase 7 |

---


---

## 7. World-Class Enhancements (Research-Driven)

Based on analysis of LangGraph interrupt patterns, Apify orchestration, and agent-harness architecture, these enhancements elevate the checkpoint system to industry-leading standards.

### 7.1 Risk Scoring Engine

**Pattern:** Calculate risk 0-1 instead of binary pattern matching. More nuanced than current trigger detection.

```python
@dataclass
class RiskAssessment:
    """Computed risk assessment for an action."""
    score: float                    # 0.0 to 1.0
    factors: dict[str, float]       # Individual risk factors
    reversibility: str              # "full", "partial", "none"
    estimated_cost: float
    estimated_duration_seconds: int
    recommendation: str             # "proceed", "checkpoint", "block"

class RiskScoringEngine:
    """Calculate nuanced risk scores for checkpoint decisions."""

    # Risk weights by category
    WEIGHTS = {
        "cost": 0.25,           # Cost impact
        "scope": 0.20,          # Scope of changes
        "reversibility": 0.25,  # Can we undo this?
        "confidence": 0.15,     # How confident are we?
        "precedent": 0.15,      # Have we done similar before?
    }

    def __init__(self, episode_store: EpisodeStore, preference_learner: PreferenceLearner):
        self.episode_store = episode_store
        self.preference_learner = preference_learner

    def assess_risk(self, goal: DailyGoal, context: dict) -> RiskAssessment:
        """Calculate comprehensive risk score."""
        factors = {}

        # Cost factor (0-1 based on budget percentage)
        budget = context.get("session_budget", 25.0)
        est_cost = goal.estimated_cost_usd or 0
        factors["cost"] = min(1.0, est_cost / (budget * 0.3))  # 30% of budget = 1.0 risk

        # Scope factor (files touched, core paths)
        files_affected = len(context.get("files_to_modify", []))
        core_path_affected = any(
            "core" in f or "models" in f or "api" in f
            for f in context.get("files_to_modify", [])
        )
        factors["scope"] = min(1.0, (files_affected / 10) + (0.3 if core_path_affected else 0))

        # Reversibility factor
        is_destructive = any(
            kw in goal.content.lower()
            for kw in ["delete", "drop", "remove", "destroy", "reset"]
        )
        is_external = any(
            kw in goal.content.lower()
            for kw in ["deploy", "publish", "push", "release", "migrate"]
        )
        if is_destructive:
            factors["reversibility"] = 1.0
        elif is_external:
            factors["reversibility"] = 0.7
        else:
            factors["reversibility"] = 0.2

        # Confidence factor (based on similar past successes)
        similar_episodes = self.episode_store.find_similar(goal.content, k=5)
        if similar_episodes:
            success_rate = sum(1 for e in similar_episodes if e.outcome.success) / len(similar_episodes)
            factors["confidence"] = 1.0 - success_rate  # Low success = high risk
        else:
            factors["confidence"] = 0.5  # Unknown = medium risk

        # Precedent factor (has human approved similar before?)
        similar_decisions = self.preference_learner.find_similar_decisions(goal)
        if similar_decisions:
            approval_rate = sum(1 for d in similar_decisions if d["was_accepted"]) / len(similar_decisions)
            factors["precedent"] = 1.0 - approval_rate  # Low approval = high risk
        else:
            factors["precedent"] = 0.5  # No precedent = medium risk

        # Weighted score
        score = sum(factors[k] * self.WEIGHTS[k] for k in factors)

        # Determine reversibility category
        if factors["reversibility"] > 0.8:
            reversibility = "none"
        elif factors["reversibility"] > 0.4:
            reversibility = "partial"
        else:
            reversibility = "full"

        # Determine recommendation
        if score > 0.7:
            recommendation = "block"      # Too risky - require explicit approval
        elif score > 0.4:
            recommendation = "checkpoint" # Medium risk - checkpoint with recommendation
        else:
            recommendation = "proceed"    # Low risk - proceed with logging

        return RiskAssessment(
            score=score,
            factors=factors,
            reversibility=reversibility,
            estimated_cost=est_cost,
            estimated_duration_seconds=context.get("estimated_duration", 300),
            recommendation=recommendation,
        )
```

**Integration:** Risk score feeds into checkpoint trigger detection:

```python
class CheckpointSystem:
    def _detect_triggers(self, goal: DailyGoal) -> list[CheckpointTrigger]:
        triggers = []

        # NEW: Risk-based trigger (replaces simple pattern matching)
        risk = self.risk_engine.assess_risk(goal, self._get_context())
        if risk.recommendation == "block":
            triggers.append(CheckpointTrigger.HIGH_RISK)
        elif risk.recommendation == "checkpoint":
            # Include risk assessment in checkpoint
            self._pending_risk_assessment = risk

        # ... existing trigger detection ...
```

### 7.2 Pre-flight Validation

**Pattern:** Validate BEFORE execution starts, not just after. Catch issues early.

```python
class PreFlightChecker:
    """Validate before execution to catch issues early."""

    def __init__(
        self,
        risk_engine: RiskScoringEngine,
        checkpoint_system: CheckpointSystem,
        config: ChiefOfStaffConfig,
    ):
        self.risk_engine = risk_engine
        self.checkpoint_system = checkpoint_system
        self.config = config

    async def validate_before_execute(
        self,
        goal: DailyGoal,
        action_plan: dict,
    ) -> PreFlightResult:
        """Run all pre-execution validations."""
        issues = []
        warnings = []

        # 1. Budget check
        remaining_budget = action_plan.get("session_budget", 0) - action_plan.get("spent", 0)
        estimated_cost = goal.estimated_cost_usd or 0
        if estimated_cost > remaining_budget:
            issues.append(PreFlightIssue(
                severity="critical",
                category="budget",
                message=f"Estimated cost ${estimated_cost:.2f} exceeds remaining budget ${remaining_budget:.2f}",
                suggested_action="Reduce scope or request budget increase",
            ))
        elif estimated_cost > remaining_budget * 0.5:
            warnings.append(PreFlightWarning(
                category="budget",
                message=f"This action will use {estimated_cost/remaining_budget*100:.0f}% of remaining budget",
            ))

        # 2. Dependency check
        dependencies = action_plan.get("dependencies", [])
        for dep in dependencies:
            if not await self._check_dependency_available(dep):
                issues.append(PreFlightIssue(
                    severity="blocking",
                    category="dependency",
                    message=f"Required dependency not available: {dep}",
                    suggested_action=f"Complete {dep} first or remove dependency",
                ))

        # 3. Risk assessment
        risk = self.risk_engine.assess_risk(goal, action_plan)
        if risk.score > 0.7:
            issues.append(PreFlightIssue(
                severity="high_risk",
                category="risk",
                message=f"Risk score {risk.score:.2f} exceeds threshold (0.7)",
                factors=risk.factors,
                suggested_action="Review risk factors and consider breaking into smaller tasks",
            ))

        # 4. Conflict check (files being modified elsewhere)
        conflicts = await self._check_file_conflicts(action_plan.get("files_to_modify", []))
        if conflicts:
            issues.append(PreFlightIssue(
                severity="blocking",
                category="conflict",
                message=f"Files are being modified by another session: {conflicts}",
                suggested_action="Wait for other session to complete or coordinate changes",
            ))

        # Determine result
        has_blocking = any(i.severity in ("critical", "blocking") for i in issues)

        return PreFlightResult(
            passed=not has_blocking,
            issues=issues,
            warnings=warnings,
            risk_assessment=risk,
            requires_checkpoint=risk.recommendation in ("checkpoint", "block"),
        )

# Integration in AutopilotRunner
class AutopilotRunner:
    async def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        # PRE-FLIGHT CHECK (NEW - before any execution)
        action_plan = await self._plan_goal_execution(goal)
        preflight = await self.preflight_checker.validate_before_execute(goal, action_plan)

        if not preflight.passed:
            # Surface issues to user via checkpoint
            checkpoint = await self._create_preflight_checkpoint(goal, preflight)
            return GoalExecutionResult(
                success=False,
                error="Pre-flight validation failed",
                checkpoint_pending=True,
                preflight_issues=preflight.issues,
            )

        if preflight.requires_checkpoint:
            # Create checkpoint with risk context
            checkpoint_result = await self.checkpoint_system.check_before_execution(
                goal,
                risk_assessment=preflight.risk_assessment,
            )
            if not checkpoint_result.approved:
                return GoalExecutionResult(
                    success=False,
                    error="Awaiting human approval",
                    checkpoint_pending=True,
                )

        # ... proceed with execution ...
```

### 7.5 Feedback Incorporation Loop

**Pattern:** Capture human feedback at checkpoints, inject into subsequent agent prompts. Learning that sticks.

```python
@dataclass
class HumanFeedback:
    """Structured feedback from checkpoint resolution."""
    checkpoint_id: str
    timestamp: str
    feedback_type: str              # "guidance", "correction", "preference"
    content: str
    applies_to: list[str]           # Tags for what this feedback applies to
    expires_at: Optional[str]       # When this feedback becomes stale

class FeedbackIncorporator:
    """Manages feedback incorporation into agent prompts."""

    def __init__(self, feedback_store: FeedbackStore):
        self.store = feedback_store

    def record_feedback(self, checkpoint: Checkpoint, notes: str) -> HumanFeedback:
        """Record human feedback from checkpoint resolution."""
        # Analyze feedback to extract structure
        feedback_type = self._classify_feedback(notes)
        applies_to = self._extract_tags(checkpoint, notes)

        feedback = HumanFeedback(
            checkpoint_id=checkpoint.checkpoint_id,
            timestamp=datetime.now().isoformat(),
            feedback_type=feedback_type,
            content=notes,
            applies_to=applies_to,
            expires_at=self._calculate_expiry(feedback_type),
        )

        self.store.save(feedback)
        return feedback

    def get_relevant_feedback(self, goal: DailyGoal) -> list[HumanFeedback]:
        """Get feedback relevant to current goal."""
        all_feedback = self.store.load_active()

        relevant = []
        for fb in all_feedback:
            # Check tag overlap
            goal_tags = set(goal.tags or [])
            feedback_tags = set(fb.applies_to)
            if goal_tags & feedback_tags:
                relevant.append(fb)

            # Check content similarity
            elif self._is_content_similar(goal.content, fb.content):
                relevant.append(fb)

        return relevant

    def build_feedback_context(self, goal: DailyGoal) -> str:
        """Build context string for agent prompt."""
        relevant = self.get_relevant_feedback(goal)

        if not relevant:
            return ""

        context = "\n\n## Human Feedback from Recent Checkpoints\n"
        context += "Incorporate this guidance from the PM/founder:\n\n"

        for fb in relevant:
            context += f"- **{fb.feedback_type}**: {fb.content}\n"

        return context

# Integration in agent prompts
class CoderAgent:
    async def run(self, goal: DailyGoal, context: dict) -> CoderResult:
        # Get relevant human feedback
        feedback_context = self.feedback_incorporator.build_feedback_context(goal)

        prompt = f"""
        {self.BASE_PROMPT}

        {feedback_context}  # NEW: Human feedback injected

        Goal: {goal.content}
        """

        # ... rest of coder logic ...
```

### 7.7 Continue-on-Block Strategy

**Pattern:** Don't halt entire feature when one issue fails. Continue with independent issues.

```python
class ExecutionStrategy(Enum):
    SEQUENTIAL = "sequential"           # Stop on any failure (current)
    CONTINUE_ON_BLOCK = "continue"      # Continue independent issues
    PARALLEL_SAFE = "parallel_safe"     # Parallel non-conflicting issues

@dataclass
class DependencyGraph:
    """Track dependencies between issues."""
    issues: list[TaskRef]
    dependencies: dict[int, list[int]]  # issue_number -> depends_on

    def get_ready_issues(self, completed: set[int], blocked: set[int]) -> list[TaskRef]:
        """Get issues that can start (dependencies met, not blocked)."""
        ready = []
        for issue in self.issues:
            if issue.issue_number in completed or issue.issue_number in blocked:
                continue

            deps = self.dependencies.get(issue.issue_number, [])
            if all(d in completed for d in deps):
                ready.append(issue)

        return ready

class AutopilotRunner:
    async def _execute_goals_continue_on_block(
        self,
        goals: list[DailyGoal],
    ) -> list[GoalExecutionResult]:
        """Execute goals, continuing past blocked issues."""
        results = []
        completed: set[str] = set()
        blocked: set[str] = set()

        # Build dependency graph
        dep_graph = self._build_dependency_graph(goals)

        while True:
            # Get ready goals (dependencies met, not blocked)
            ready = dep_graph.get_ready_goals(completed, blocked)

            if not ready:
                # No more ready goals
                break

            for goal in ready:
                result = await self._execute_goal(goal)
                results.append(result)

                if result.success:
                    completed.add(goal.goal_id)
                else:
                    # Mark as blocked, but continue with other goals
                    blocked.add(goal.goal_id)

                    # Create hiccup checkpoint for blocked goal
                    if result.error:
                        goal.is_hiccup = True
                        await self._create_hiccup_checkpoint(goal, result.error)

                # Check session-level triggers
                if result.checkpoint_pending:
                    break

        return results
```

### 7.8 Enhanced Q&A Format

**Pattern:** Structured Q&A with tradeoffs, similar past decisions, and clear recommendations.

```python
@dataclass
class EnhancedCheckpointOption:
    """Rich option with tradeoffs and context."""
    id: str
    label: str
    description: str
    tradeoffs: dict[str, str]       # {"pros": ..., "cons": ...}
    estimated_cost: Optional[float]
    estimated_time: Optional[str]
    risk_level: str                 # "low", "medium", "high"
    is_recommended: bool = False
    recommendation_reason: Optional[str] = None

@dataclass
class EnhancedCheckpoint:
    """World-class checkpoint format."""
    checkpoint_id: str
    trigger: CheckpointTrigger

    # Context
    context: str
    current_progress: ProgressSnapshot
    risk_assessment: RiskAssessment

    # Q&A Format
    question: str                           # Clear question
    options: list[EnhancedCheckpointOption]
    recommended_option_id: str
    recommendation_rationale: str

    # Learning context
    similar_past_decisions: list[PastDecision]
    preference_insights: list[str]          # "You usually prefer X over Y"

    # Metadata
    created_at: str
    expires_at: Optional[str]
    urgency: str                            # "immediate", "soon", "whenever"

class CheckpointSystem:
    async def _create_enhanced_checkpoint(
        self,
        goal: DailyGoal,
        trigger: CheckpointTrigger,
    ) -> EnhancedCheckpoint:
        """Create world-class checkpoint with full context."""

        # Get risk assessment
        risk = self.risk_engine.assess_risk(goal, self._get_context())

        # Get progress snapshot
        progress = self.progress_tracker.get_snapshot(goal.linked_feature)

        # Get similar past decisions
        similar = self.preference_learner.find_similar_decisions(goal)

        # Get preference insights
        insights = self.preference_learner.get_insights_for_context(goal)

        # Build enhanced options with tradeoffs
        options = self._build_enhanced_options(goal, trigger, risk)

        # Determine recommendation
        rec_option, rec_reason = self._determine_recommendation(
            goal, trigger, options, similar, insights
        )

        return EnhancedCheckpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            trigger=trigger,
            context=self._build_context(goal, trigger),
            current_progress=progress,
            risk_assessment=risk,
            question=self._build_question(goal, trigger),
            options=options,
            recommended_option_id=rec_option.id,
            recommendation_rationale=rec_reason,
            similar_past_decisions=similar,
            preference_insights=insights,
            created_at=datetime.now().isoformat(),
            expires_at=self._calculate_expiry(trigger),
            urgency=self._determine_urgency(trigger, risk),
        )

    def _build_enhanced_options(
        self,
        goal: DailyGoal,
        trigger: CheckpointTrigger,
        risk: RiskAssessment,
    ) -> list[EnhancedCheckpointOption]:
        """Build options with tradeoffs."""

        if trigger == CheckpointTrigger.COST_SINGLE:
            return [
                EnhancedCheckpointOption(
                    id="proceed",
                    label="Proceed with estimated cost",
                    description=f"Execute as planned (${goal.estimated_cost_usd:.2f})",
                    tradeoffs={
                        "pros": "Complete goal without modification",
                        "cons": f"Uses {goal.estimated_cost_usd/risk.estimated_cost*100:.0f}% of typical budget",
                    },
                    estimated_cost=goal.estimated_cost_usd,
                    risk_level="medium",
                    is_recommended=True,
                    recommendation_reason="Within session budget limits",
                ),
                EnhancedCheckpointOption(
                    id="optimize",
                    label="Optimize to reduce cost",
                    description="Break into smaller chunks or use cheaper models",
                    tradeoffs={
                        "pros": "Preserve budget for later goals",
                        "cons": "May take longer or reduce output quality",
                    },
                    estimated_cost=goal.estimated_cost_usd * 0.6,
                    risk_level="low",
                ),
                EnhancedCheckpointOption(
                    id="skip",
                    label="Skip this goal",
                    description="Move to next goal, come back later",
                    tradeoffs={
                        "pros": "Zero cost, preserve full budget",
                        "cons": "Goal remains incomplete, may block dependents",
                    },
                    estimated_cost=0,
                    risk_level="low",
                ),
            ]

        # ... similar for other trigger types ...
```

**CLI Output:**

```
🔔 CHECKPOINT: COST (Single Action)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Context: About to implement user authentication flow
Risk Score: 0.45 (medium) | Reversibility: full

Progress: 5/20 issues (25%) | Budget: $18.60 remaining

❓ How should we proceed with this $7.50 action?

  1. ✅ Proceed with estimated cost [$7.50] (Recommended)
     Pros: Complete goal without modification
     Cons: Uses 40% of remaining budget

  2. 💰 Optimize to reduce cost [$4.50]
     Pros: Preserve budget for later goals
     Cons: May take longer or reduce quality

  3. ⏭️  Skip this goal [$0]
     Pros: Zero cost, preserve full budget
     Cons: Goal remains incomplete

💡 Recommendation: Proceed - similar past decisions were approved 4/5 times
   You typically approve cost actions under $10.

📊 Similar past decisions:
   - [Dec 15] Auth middleware: Approved ($6.20)
   - [Dec 14] API routes: Approved ($8.10)

[1] Proceed  [2] Optimize  [3] Skip  [?] Discuss
```


### 7.9 Implementation Tasks (v3 World-Class)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 12.1 | Implement RiskScoringEngine | M | v2 complete (9.2, 9.3) |
| 12.2 | Implement PreFlightChecker | M | 12.1 |
| 12.5 | Implement FeedbackIncorporator | M | v2 complete (7.6) |
| 12.7 | Implement continue-on-block execution strategy | M | v2 complete (7.2) |
| 12.8 | Implement EnhancedCheckpoint format | M | v2 complete (7.6), 12.1 |
| 12.9 | Add progress and feedback CLI commands | S | 12.5, v2 (12.6) |

---

## 8. Success Metrics

| Metric | v2 Baseline | v3 Target | Measurement |
|--------|-------------|-----------|-------------|
| Multi-day completion | N/A | >75% | Campaigns finished as planned |
| Human review reduction | 100% manual | <30% | Artifacts bypassing review (via critics) |
| Risk detection accuracy | Basic triggers | >85% | False positive/negative rate |
| Continue-on-block success | N/A | >60% | Goals recovered via alternative paths |
| Feedback incorporation | None | Track usage | Feedback applied to future prompts |

---

## 9. Risk Mitigations

| Risk | Mitigation | Owner |
|------|------------|-------|
| Runaway campaigns | Per-campaign budget caps, milestone checkpoints | David's design |
| Bad critic consensus | Require 2/3 agreement, human override path | Harrison's design |
| Over-automation | Weekly summary review gate | Shunyu's design |
| Stale feedback | Expiration on feedback, recency weighting | Kanjun's design |
| Continue-on-block loops | Maximum skip count per session | Jerry's design |

---

## 10. Implementation Roadmap

### Phase 10: Multi-Day Campaigns + Weekly Planning (Strategic)
**8 issues** (7 campaigns + 1 weekly)

Graduate from "daily tasks" to "build this feature over the week." Weekly planning satisfies PRD User Story #6.

### Phase 11: Internal Validation (Scale)
**6 issues**

Reduces human bottleneck. Most specs/code auto-approve; you only see the hard cases.

### Phase 12 (Remaining): World-Class Enhancements (Research-Driven)
**6 issues**

Industry-leading patterns:
- Risk scoring engine (nuanced 0-1 scores vs binary)
- Pre-flight validation (catch issues before execution)
- Feedback incorporation (learning that sticks)
- Continue-on-block (resilient execution)
- Enhanced Q&A format (tradeoffs, recommendations, context)

**v3 Total: 20 issues across 3 phases**

---

## 11. Expert Panel Statement (v3 Scope)

**Harrison Chase:** "With v2's autonomous foundation in place, campaigns and critics are the natural next step. Risk scoring from LangGraph interrupt patterns is exactly right for nuanced decision-making."

**Jerry Liu:** "Weekly summaries (PRD User Story #6) require the episode memory from v2. Campaign state tracking builds cleanly on existing infrastructure."

**Kanjun Qiu:** "Risk scoring with nuanced 0-1 values (vs binary) is a massive upgrade. Combined with feedback incorporation, the system continuously improves."

**David Dohan:** "Pre-flight validation catches issues BEFORE spending tokens - this is the right safety enhancement. Critics reduce human load while maintaining security veto."

**Shunyu Yao:** "Continue-on-block makes campaigns practical for overnight runs. The enhanced Q&A format with tradeoffs matches how senior engineers actually want to review decisions."

---

## 12. Dependencies on v2

v3 explicitly depends on v2 completion:

| v3 Issue | Depends on v2 |
|----------|---------------|
| 12.1 (Risk Scoring) | 9.2 (EpisodeStore), 9.3 (ReflexionEngine) |
| 12.5 (Feedback) | 7.6 (CheckpointStore) |
| 12.7 (Continue-on-Block) | 7.2 (Execution paths) |
| 12.8 (Enhanced Checkpoint) | 7.6 (CheckpointStore), 12.1 |
| 12.9 (CLI Commands) | 12.6 (ProgressTracker) |
| Phase 10 (Campaigns) | Phase 7 (Execution), Phase 9 (Memory) |
| Phase 11 (Critics) | Phase 7 (Pipeline integration) |

---

*v3 Spec finalized: December 2025*
*Expert Panel: LangChain, LlamaIndex, Imbue, Anthropic, Princeton*
*Prerequisites: v2 complete (24 issues)*
*Phases: 10 (Campaigns), 11 (Critics), 12-remaining (World-Class)*
*Issues: 20*
*Ready for implementation after v2*
