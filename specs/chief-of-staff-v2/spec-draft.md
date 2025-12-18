# Chief of Staff v2: Autonomous Development Partner

## Expert Panel Consensus Document

**Panel Members:**
- Harrison Chase (LangChain) - Agent frameworks, state machines
- Jerry Liu (LlamaIndex) - Data agents, retrieval systems
- Kanjun Qiu (Imbue) - Reasoning agents, self-improvement
- David Dohan (Anthropic) - Tool safety, bounded autonomy
- Shunyu Yao (Princeton) - ReAct, Tree-of-Thought planning

**Date:** December 2025
**Status:** FINAL - Ready for Implementation

---

## 1. Executive Summary

### What v1 Delivered
Chief of Staff v1 is **complete** (20/20 issues, 279 tests, 6 CLI commands). It provides:
- Cross-session memory via daily logs and JSONL decisions
- Daily standups with intelligent recommendations
- Goal tracking with automatic state reconciliation
- Autopilot mode with checkpoint gates (stub execution)

### What v2 Adds
v2 transforms Chief of Staff from a **workflow tool** into a **truly autonomous development partner**:

| Capability | v1 State | v2 Target |
|------------|----------|-----------|
| Execution | Stub (marks goals complete without work) | **Real orchestrator integration** |
| Recovery | Manual intervention required | **4-level automatic retry** |
| Memory | JSONL decisions only | **Episode memory + Reflexion + Preference Learning** |
| Planning | Single-day horizon | **Multi-day campaigns + Weekly summaries** |
| Validation | Human reviews everything | **Internal critics pre-filter** |
| Human Signoff | None | **Collaborative checkpoint system (P0)** |

### Expert Panel Priority Ranking (Final)

| Rank | Extension | Impact × Feasibility | Rationale |
|------|-----------|---------------------|-----------|
| **P0** | Human-in-the-Loop Checkpoints | REQUIRED | PRD mandates collaborative autonomy |
| **P1** | Real Execution | 10 × 9 = 90 | Foundation for everything - without this, nothing works |
| **P2** | Hierarchical Recovery | 9 × 8 = 72 | Essential for overnight autonomy |
| **P3** | Episode Memory + Reflexion + Preferences | 9 × 7 = 63 | Low-cost learning with high ROI |
| **P4** | Multi-Day Campaigns + Weekly Planning | 8 × 7 = 56 | Enables complex features without restarts |
| **P5** | Internal Validation Critics | 8 × 6 = 48 | Reduces human review burden by ~70% |

### Scope Boundaries (What v2 Does NOT Include)

The following PRD items are explicitly **deferred to v3** per expert panel prioritization:

| Deferred Item | PRD Priority | Rationale |
|---------------|--------------|-----------|
| Parallel Execution (P6) | 7×6=42 | Jerry Liu warned against premature parallelism; sequential campaigns cover 95% of use cases for a single developer |
| Semantic Memory/Embeddings (P8) | 6×5=30 | Nice-to-have infrastructure; simple JSONL retrieval is sufficient for v2 |
| Prompt Self-Optimization (P10) | 5×4=20 | Risky self-modification; needs careful bounds designed in v3 |

---

## 2. Phase 7: Real Execution (P1)

### Consensus Decision

**Harrison Chase:** "This is table stakes. The current stub defeats the entire purpose. Just wire it up."

**David Dohan:** "Agreed, but add defensive wrappers. Never let a goal execute without budget/time checks BEFORE the call, not just after."

### 2.1 Core Execution Design

```python
class AutopilotRunner:
    def __init__(
        self,
        orchestrator: Orchestrator,
        bug_orchestrator: BugOrchestrator,
        checkpoint_system: CheckpointSystem,
        config: ChiefOfStaffConfig,
    ):
        self.orchestrator = orchestrator
        self.bug_orchestrator = bug_orchestrator
        self.checkpoint_system = checkpoint_system
        self.config = config
        self.session: Optional[AutopilotSession] = None

    async def start(
        self,
        goals: list[DailyGoal],
        budget_usd: float,
    ) -> AutopilotResult:
        """Start autopilot session with given goals."""
        # Reset daily cost tracking at session start
        self.checkpoint_system.reset_daily_cost()

        self.session = AutopilotSession(
            session_id=f"session-{uuid.uuid4().hex[:8]}",
            goals=goals,
            budget_usd=budget_usd,
            cost_spent_usd=0.0,
            started_at=datetime.now().isoformat(),
        )

        results = []
        for goal in goals:
            result = await self._execute_goal(goal)
            results.append(result)

            # Update session cost
            self.session.cost_spent_usd += result.cost_usd

            # Update checkpoint system's daily cost tracking
            self.checkpoint_system.update_daily_cost(result.cost_usd)

            if result.checkpoint_pending:
                # Pause for human approval
                break

        return AutopilotResult(
            session_id=self.session.session_id,
            goals_completed=len([r for r in results if r.success]),
            total_cost_usd=self.session.cost_spent_usd,
            results=results,
        )

    async def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a goal by calling the appropriate orchestrator."""

        # Pre-execution safety check (David's requirement)
        remaining_budget = self.session.budget_usd - self.session.cost_spent_usd
        if remaining_budget < self.config.min_execution_budget:
            return GoalExecutionResult(
                success=False,
                error="Insufficient budget remaining",
                cost_usd=0,
            )

        # P0: Human checkpoint before expensive/risky operations
        checkpoint_result = await self.checkpoint_system.check_before_execution(goal)
        if checkpoint_result.requires_approval and not checkpoint_result.approved:
            return GoalExecutionResult(
                success=False,
                error="Awaiting human approval",
                cost_usd=0,
                checkpoint_pending=True,
            )

        try:
            if goal.linked_feature:
                result = self.orchestrator.run_issue(
                    feature_id=goal.linked_feature,
                    issue_number=goal.linked_issue,
                )
                return GoalExecutionResult(
                    success=result.status == "success",
                    cost_usd=result.cost_usd,
                    duration_seconds=result.duration_seconds,
                    output=result.summary,
                )

            elif goal.linked_bug:
                result = self.bug_orchestrator.fix(goal.linked_bug)
                return GoalExecutionResult(
                    success=result.status == "fixed",
                    cost_usd=result.cost_usd,
                    duration_seconds=result.duration_seconds,
                    output=result.summary,
                )

            elif goal.linked_spec:
                result = self.orchestrator.run_spec_pipeline(goal.linked_spec)
                return GoalExecutionResult(
                    success=result.status == "approved",
                    cost_usd=result.cost_usd,
                    duration_seconds=result.duration_seconds,
                )

            else:
                # Generic goal without linked artifact
                # Log as manual task, mark for human follow-up
                return GoalExecutionResult(
                    success=True,
                    cost_usd=0,
                    output="Manual goal - no automated execution",
                )

        except Exception as e:
            # Mark goal as having an error for hiccup detection
            goal.error_count = getattr(goal, 'error_count', 0) + 1
            return GoalExecutionResult(
                success=False,
                error=str(e),
                cost_usd=0,
            )
```

### 2.5 Human-in-the-Loop Checkpoint System (P0)

**This is a P0 requirement from the PRD.** The system operates in **collaborative autonomy** mode—like a senior engineer who knows to check in before making big calls.

#### Checkpoint Trigger Thresholds

| Trigger | Threshold | Detection Method |
|---------|-----------|------------------|
| **UX/Flow Changes** | Any user-facing change | Goal tags contain "ui", "ux", "frontend", or linked issue has UI label |
| **Cost - Single Action** | >$5 per action | Pre-execution cost estimate from goal metadata |
| **Cost - Cumulative** | >$15/day | Session.cost_spent_usd tracking via update_daily_cost() |
| **Architecture Decisions** | Any structural change | Goal tags contain "architecture", "refactor", or new file creation in core paths |
| **Scope Changes** | Deviation from approved plan | Goal not in original day plan, or goal modified from plan |
| **Hiccups** | Any unexpected situation | error_count > 0, recovery_level >= 2, is_hiccup flag, or unknown state |

#### Checkpoint Data Model

```python
class CheckpointTrigger(Enum):
    UX_CHANGE = "ux_change"
    COST_SINGLE = "cost_single"
    COST_CUMULATIVE = "cost_cumulative"
    ARCHITECTURE = "architecture"
    SCOPE_CHANGE = "scope_change"
    HICCUP = "hiccup"

@dataclass
class CheckpointOption:
    """A choice presented to the human."""
    label: str
    description: str
    is_recommended: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointOption":
        return cls(**data)

@dataclass
class Checkpoint:
    """A decision point requiring human approval."""
    checkpoint_id: str
    trigger: CheckpointTrigger
    context: str                    # What's happening and why we're asking
    options: list[CheckpointOption]
    recommendation: Optional[str]   # Which option we recommend and why
    created_at: str
    goal_id: Optional[str]          # Linked goal if applicable
    campaign_id: Optional[str]      # Linked campaign if applicable

    # Resolution
    status: str = "pending"         # pending, approved, rejected, expired
    chosen_option: Optional[str] = None
    human_notes: Optional[str] = None
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "trigger": self.trigger.value,
            "context": self.context,
            "options": [o.to_dict() for o in self.options],
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "goal_id": self.goal_id,
            "campaign_id": self.campaign_id,
            "status": self.status,
            "chosen_option": self.chosen_option,
            "human_notes": self.human_notes,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            trigger=CheckpointTrigger(data["trigger"]),
            context=data["context"],
            options=[CheckpointOption.from_dict(o) for o in data["options"]],
            recommendation=data.get("recommendation"),
            created_at=data["created_at"],
            goal_id=data.get("goal_id"),
            campaign_id=data.get("campaign_id"),
            status=data.get("status", "pending"),
            chosen_option=data.get("chosen_option"),
            human_notes=data.get("human_notes"),
            resolved_at=data.get("resolved_at"),
        )

@dataclass
class CheckpointResult:
    """Result of a checkpoint check."""
    requires_approval: bool
    approved: bool
    checkpoint: Optional[Checkpoint]

class CheckpointSystem:
    """Manages human-in-the-loop checkpoints."""

    def __init__(
        self,
        store: "CheckpointStore",
        config: ChiefOfStaffConfig,
        preference_learner: "PreferenceLearner",
        episode_store: "EpisodeStore",
    ):
        self.store = store
        self.config = config
        self.preference_learner = preference_learner
        self.episode_store = episode_store
        self.daily_cost = 0.0

    async def check_before_execution(self, goal: DailyGoal) -> CheckpointResult:
        """Check if goal requires human approval before execution."""

        triggers = self._detect_triggers(goal)

        if not triggers:
            return CheckpointResult(requires_approval=False, approved=True, checkpoint=None)

        # Check for existing pending checkpoint
        existing = await self.store.get_pending_for_goal(goal.goal_id)
        if existing:
            return CheckpointResult(
                requires_approval=True,
                approved=existing.status == "approved",
                checkpoint=existing,
            )

        # Create new checkpoint
        checkpoint = await self._create_checkpoint(goal, triggers[0])
        await self.store.save(checkpoint)

        return CheckpointResult(
            requires_approval=True,
            approved=False,
            checkpoint=checkpoint,
        )

    def _detect_triggers(self, goal: DailyGoal) -> list[CheckpointTrigger]:
        """Detect which triggers apply to this goal."""
        triggers = []

        # HICCUP detection (P0 requirement) - check this first
        # Hiccup triggers: error_count > 0, recovery_level >= 2, explicit is_hiccup flag
        if getattr(goal, 'error_count', 0) > 0:
            triggers.append(CheckpointTrigger.HICCUP)
        if getattr(goal, 'recovery_level', 0) >= 2:
            triggers.append(CheckpointTrigger.HICCUP)
        if getattr(goal, 'is_hiccup', False):
            triggers.append(CheckpointTrigger.HICCUP)

        # UX/Flow changes
        ui_tags = {"ui", "ux", "frontend", "user-facing", "screen", "flow"}
        if goal.tags and ui_tags & set(t.lower() for t in goal.tags):
            triggers.append(CheckpointTrigger.UX_CHANGE)

        # Cost - single action
        if goal.estimated_cost_usd and goal.estimated_cost_usd > self.config.checkpoint_cost_single:
            triggers.append(CheckpointTrigger.COST_SINGLE)

        # Cost - cumulative (uses daily_cost updated by AutopilotRunner)
        if self.daily_cost > self.config.checkpoint_cost_daily:
            triggers.append(CheckpointTrigger.COST_CUMULATIVE)

        # Architecture
        arch_tags = {"architecture", "refactor", "core", "infrastructure", "breaking"}
        if goal.tags and arch_tags & set(t.lower() for t in goal.tags):
            triggers.append(CheckpointTrigger.ARCHITECTURE)

        # Scope change (goal not in original plan)
        if getattr(goal, 'is_unplanned', False):
            triggers.append(CheckpointTrigger.SCOPE_CHANGE)

        return triggers

    async def _create_checkpoint(
        self,
        goal: DailyGoal,
        trigger: CheckpointTrigger,
    ) -> Checkpoint:
        """Create a checkpoint with options and recommendation."""

        context = self._build_context(goal, trigger)
        options = self._build_options(goal, trigger)
        recommendation = self._build_recommendation(goal, trigger, options)

        return Checkpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            trigger=trigger,
            context=context,
            options=options,
            recommendation=recommendation,
            created_at=datetime.now().isoformat(),
            goal_id=goal.goal_id,
        )

    def _build_context(self, goal: DailyGoal, trigger: CheckpointTrigger) -> str:
        """Build context string for checkpoint."""
        contexts = {
            CheckpointTrigger.UX_CHANGE: f"About to make user-facing changes: {goal.content}",
            CheckpointTrigger.COST_SINGLE: f"This action is estimated to cost ${goal.estimated_cost_usd:.2f}: {goal.content}",
            CheckpointTrigger.COST_CUMULATIVE: f"Daily spending has exceeded ${self.config.checkpoint_cost_daily}. Next action: {goal.content}",
            CheckpointTrigger.ARCHITECTURE: f"This involves architectural changes: {goal.content}",
            CheckpointTrigger.SCOPE_CHANGE: f"This goal was not in the original plan: {goal.content}",
            CheckpointTrigger.HICCUP: f"Encountered an unexpected situation: {goal.content}. Error count: {getattr(goal, 'error_count', 0)}, Recovery level: {getattr(goal, 'recovery_level', 0)}",
        }
        return contexts.get(trigger, f"Checkpoint for: {goal.content}")

    def _build_options(self, goal: DailyGoal, trigger: CheckpointTrigger) -> list[CheckpointOption]:
        """Build standard options for checkpoint."""
        return [
            CheckpointOption(
                label="Proceed",
                description="Approve this action and continue",
                is_recommended=True,
            ),
            CheckpointOption(
                label="Skip",
                description="Skip this goal and move to the next one",
            ),
            CheckpointOption(
                label="Modify",
                description="I'll provide adjusted instructions",
            ),
            CheckpointOption(
                label="Pause",
                description="Pause the session for manual review",
            ),
        ]

    def _build_recommendation(
        self,
        goal: DailyGoal,
        trigger: CheckpointTrigger,
        options: list[CheckpointOption],
    ) -> str:
        """Build recommendation string."""
        if trigger == CheckpointTrigger.HICCUP:
            return f"Review needed - encountered unexpected situation with {goal.content}"
        return f"Proceed - {goal.content} aligns with the current plan and is within acceptable risk bounds."

    async def resolve_checkpoint(
        self,
        checkpoint_id: str,
        chosen_option: str,
        notes: Optional[str] = None,
    ) -> Checkpoint:
        """Resolve a pending checkpoint with human decision."""
        checkpoint = await self.store.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint.status = "approved" if chosen_option == "Proceed" else "rejected"
        checkpoint.chosen_option = chosen_option
        checkpoint.human_notes = notes
        checkpoint.resolved_at = datetime.now().isoformat()

        await self.store.save(checkpoint)

        # Record for preference learning
        await self._record_decision(checkpoint)

        return checkpoint

    async def _record_decision(self, checkpoint: Checkpoint) -> None:
        """Record decision for preference learning."""
        # Get the most recent episode for this goal (if any)
        recent_episodes = self.episode_store.load_recent(limit=10)
        matching_episode = None
        for ep in reversed(recent_episodes):
            if ep.goal.goal_id == checkpoint.goal_id:
                matching_episode = ep
                break

        # Record with preference learner
        await self.preference_learner.record_decision(checkpoint, matching_episode)

    def update_daily_cost(self, cost: float) -> None:
        """Update cumulative daily cost tracking. Called by AutopilotRunner after each goal."""
        self.daily_cost += cost

    def reset_daily_cost(self) -> None:
        """Reset daily cost. Called by AutopilotRunner at session start."""
        self.daily_cost = 0.0

class CheckpointStore:
    """Persistent storage for checkpoints."""

    def __init__(self, base_path: Path):
        self.base_path = base_path / "checkpoints"
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to JSON file."""
        path = self.base_path / f"{checkpoint.checkpoint_id}.json"
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    async def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load checkpoint by ID."""
        path = self.base_path / f"{checkpoint_id}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return Checkpoint.from_dict(json.load(f))

    async def get_pending_for_goal(self, goal_id: str) -> Optional[Checkpoint]:
        """Get pending checkpoint for a goal."""
        for path in self.base_path.glob("*.json"):
            with open(path, "r") as f:
                data = json.load(f)
                if data.get("goal_id") == goal_id and data.get("status") == "pending":
                    return Checkpoint.from_dict(data)
        return None

    async def list_pending(self) -> list[Checkpoint]:
        """List all pending checkpoints."""
        pending = []
        for path in self.base_path.glob("*.json"):
            with open(path, "r") as f:
                data = json.load(f)
                if data.get("status") == "pending":
                    pending.append(Checkpoint.from_dict(data))
        return pending
```

#### CLI Surface for Checkpoints

```bash
# View pending checkpoints
swarm-attack cos checkpoints

# Approve a checkpoint
swarm-attack cos approve <checkpoint-id>

# Approve with notes
swarm-attack cos approve <checkpoint-id> --notes "Proceed with caution"

# Reject/skip a checkpoint
swarm-attack cos reject <checkpoint-id>

# Modify and continue
swarm-attack cos modify <checkpoint-id> --instructions "Use approach B instead"
```

#### Checkpoint CLI Implementation

```python
@cos_group.command("checkpoints")
def list_checkpoints():
    """List pending checkpoints requiring approval."""
    pending = asyncio.run(checkpoint_store.list_pending())

    if not pending:
        click.echo("No pending checkpoints.")
        return

    for cp in pending:
        click.echo(f"\n🔔 CHECKPOINT: {cp.trigger.value.upper()}")
        click.echo(f"   ID: {cp.checkpoint_id}")
        click.echo(f"   Context: {cp.context}")
        click.echo(f"   Options:")
        for opt in cp.options:
            marker = "💡" if opt.is_recommended else "  "
            click.echo(f"     {marker} {opt.label}: {opt.description}")
        if cp.recommendation:
            click.echo(f"   Recommendation: {cp.recommendation}")

@cos_group.command("approve")
@click.argument("checkpoint_id")
@click.option("--notes", "-n", default=None, help="Optional notes")
def approve_checkpoint(checkpoint_id: str, notes: Optional[str]):
    """Approve a pending checkpoint."""
    cp = asyncio.run(checkpoint_system.resolve_checkpoint(
        checkpoint_id, "Proceed", notes
    ))
    click.echo(f"✓ Checkpoint {checkpoint_id} approved.")

@cos_group.command("reject")
@click.argument("checkpoint_id")
@click.option("--notes", "-n", default=None, help="Optional notes")
def reject_checkpoint(checkpoint_id: str, notes: Optional[str]):
    """Reject/skip a pending checkpoint."""
    cp = asyncio.run(checkpoint_system.resolve_checkpoint(
        checkpoint_id, "Skip", notes
    ))
    click.echo(f"✗ Checkpoint {checkpoint_id} rejected.")
```

#### Integration with AutopilotRunner

The checkpoint system integrates at the start of `_execute_goal()` as shown in section 2.1. When a checkpoint is pending:

1. Execution pauses with `checkpoint_pending=True`
2. CLI shows pending checkpoints on next `swarm-attack cos status`
3. Human resolves via `swarm-attack cos approve/reject`
4. Next autopilot cycle picks up the resolved checkpoint and continues

#### Integration with CampaignExecutor

```python
class CampaignExecutor:
    async def execute_day(self, campaign: Campaign) -> "DayResult":
        """Execute one day of the campaign."""

        # Check for campaign-level checkpoint (e.g., milestone boundary)
        if self._at_milestone_boundary(campaign):
            checkpoint = await self.checkpoint_system.create_milestone_checkpoint(campaign)
            if not checkpoint.approved:
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

        # ... rest of execute_day ...
```

### Implementation Tasks (10 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 7.1 | Add orchestrator dependency to AutopilotRunner | S | - |
| 7.2 | Implement feature execution path | M | 7.1 |
| 7.3 | Implement bug execution path | M | 7.1 |
| 7.4 | Implement spec pipeline execution path | M | 7.1 |
| 7.5 | Add pre-execution budget checks | S | 7.1 |
| 7.6 | Create Checkpoint and CheckpointStore dataclasses | M | - |
| 7.7 | Implement CheckpointSystem with trigger detection (including hiccups) | M | 7.6 |
| 7.8 | Add checkpoint CLI commands (checkpoints, approve, reject) | M | 7.6, 7.7 |
| 7.9 | Integrate CheckpointSystem with AutopilotRunner (including cost tracking) | M | 7.1, 7.7 |
| 7.10 | Add checkpoint integration to CampaignExecutor | S | 7.7, Phase 10 |

---

## 3. Phase 8: Hierarchical Error Recovery (P2)

### Consensus Decision

**Shunyu Yao:** "Bounded retry with alternatives. Don't over-engineer - just try a different approach on failure."

**David Dohan:** "Agree. Add circuit breakers at each level. And the human escalation MUST happen within 30 minutes of hitting Level 4."

**Kanjun Qiu:** "Track which recovery strategies work. Feed that back into Reflexion for future episodes."

**Final Design (Simplified):**

```python
class RecoveryLevel(Enum):
    RETRY_SAME = 1      # Transient failure - retry with same approach
    RETRY_ALTERNATE = 2  # Systematic failure - try ONE alternative approach
    RETRY_CLARIFY = 3   # Missing context - optionally ask clarifying question
    ESCALATE = 4        # Human required - checkpoint pause

@dataclass
class RecoveryStrategy:
    level: RecoveryLevel
    max_attempts: int
    backoff_seconds: int

class RecoveryManager:
    LEVELS = [
        RecoveryStrategy(RecoveryLevel.RETRY_SAME, max_attempts=3, backoff_seconds=5),
        RecoveryStrategy(RecoveryLevel.RETRY_ALTERNATE, max_attempts=2, backoff_seconds=10),
        RecoveryStrategy(RecoveryLevel.RETRY_CLARIFY, max_attempts=1, backoff_seconds=0),
        RecoveryStrategy(RecoveryLevel.ESCALATE, max_attempts=1, backoff_seconds=0),
    ]

    def __init__(self, config: ChiefOfStaffConfig, reflexion: ReflexionEngine, checkpoint_system: CheckpointSystem):
        self.config = config
        self.reflexion = reflexion
        self.checkpoint_system = checkpoint_system
        self.error_streak = 0

    async def execute_with_recovery(
        self,
        goal: DailyGoal,
        action: Callable[[], GoalExecutionResult],
    ) -> GoalExecutionResult:
        """Execute action with automatic recovery through all levels."""

        last_result = None
        current_recovery_level = 0

        for strategy in self.LEVELS:
            current_recovery_level = strategy.level.value

            # Update goal's recovery level for hiccup detection
            goal.recovery_level = current_recovery_level

            for attempt in range(strategy.max_attempts):
                # Retrieve relevant past episodes for context (simple retrieval)
                context = await self.reflexion.retrieve_relevant(goal, k=3)

                if strategy.level == RecoveryLevel.RETRY_ALTERNATE and last_result:
                    # Generate ONE alternative approach (simple, no ToT)
                    alternative = await self._generate_simple_alternative(
                        goal, last_result, context
                    )
                    if alternative:
                        action = alternative

                elif strategy.level == RecoveryLevel.RETRY_CLARIFY and last_result:
                    # Optional: ask ONE clarifying question if error suggests missing info
                    if self._error_suggests_missing_info(last_result.error):
                        clarification = await self._ask_simple_clarification(goal, last_result)
                        if clarification:
                            goal = self._incorporate_clarification(goal, clarification)

                elif strategy.level == RecoveryLevel.ESCALATE:
                    # Mark goal as hiccup for checkpoint system
                    goal.is_hiccup = True
                    # Create hiccup checkpoint for human
                    return await self._escalate_to_human(goal, last_result)

                # Execute with backoff
                if attempt > 0:
                    await asyncio.sleep(strategy.backoff_seconds * (2 ** attempt))

                result = await action()

                if result.success:
                    self.error_streak = 0
                    # Record success for Reflexion learning
                    await self.reflexion.record_episode(goal, result, strategy.level.value)
                    return result

                last_result = result
                self.error_streak += 1

                # Update goal error count for hiccup detection
                goal.error_count = getattr(goal, 'error_count', 0) + 1

                # Check circuit breaker
                if self.error_streak >= self.config.error_streak_threshold:
                    break

        # All levels exhausted - escalate to human
        goal.is_hiccup = True
        return await self._escalate_to_human(goal, last_result)

    async def _escalate_to_human(
        self,
        goal: DailyGoal,
        failure: GoalExecutionResult,
    ) -> GoalExecutionResult:
        """Create hiccup checkpoint and pause for human."""
        checkpoint = Checkpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            trigger=CheckpointTrigger.HICCUP,
            context=f"Recovery failed after 4 levels. Goal: {goal.content}. Error: {failure.error}",
            options=[
                CheckpointOption(label="Retry", description="Try again with fresh context"),
                CheckpointOption(label="Skip", description="Skip this goal"),
                CheckpointOption(label="Manual", description="I'll handle this manually"),
            ],
            recommendation="Skip - automatic recovery exhausted all options",
            created_at=datetime.now().isoformat(),
            goal_id=goal.goal_id,
        )
        await self.checkpoint_system.store.save(checkpoint)

        return GoalExecutionResult(
            success=False,
            error=f"Escalated to human: {failure.error}",
            cost_usd=failure.cost_usd,
            checkpoint_pending=True,
        )

    async def _generate_simple_alternative(
        self,
        goal: DailyGoal,
        failure: GoalExecutionResult,
        context: list[Episode],
    ) -> Optional[Callable]:
        """Generate ONE alternative approach based on the failure."""
        prompt = f"""
        Goal: {goal.content}
        Failed with error: {failure.error}

        Past similar episodes that worked:
        {[e.reflection for e in context if e.outcome.success][:2]}

        Suggest ONE alternative approach. Be specific and actionable.
        """
        # Simple LLM call, return modified action if viable
        # Return None if no good alternative found

    def _error_suggests_missing_info(self, error: Optional[str]) -> bool:
        """Check if error message suggests we need more information."""
        if not error:
            return False
        missing_info_patterns = ["not found", "missing", "undefined", "unknown"]
        return any(p in error.lower() for p in missing_info_patterns)

    async def _ask_simple_clarification(
        self,
        goal: DailyGoal,
        failure: GoalExecutionResult,
    ) -> Optional[str]:
        """Ask a simple clarifying question if needed."""
        # Only ask if error clearly indicates missing info
        # Return clarification text or None
```

### Implementation Tasks (5 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 8.1 | Create RecoveryManager class with level definitions | M | Phase 7 |
| 8.2 | Implement Level 1 (retry same with backoff) | S | 8.1 |
| 8.3 | Implement Level 2 (simple alternative generation) | M | 8.1 |
| 8.4 | Implement Level 3-4 (clarification and escalation with hiccup marking) | M | 8.1, 7.7 |
| 8.5 | Add circuit breakers and error streak tracking | S | 8.1-8.4 |

---

## 4. Phase 9: Episode Memory + Reflexion + Preference Learning (P3)

### Consensus Decision

**Jerry Liu:** "JSONL episodes with simple retrieval. Don't add embeddings until you have thousands of episodes - heuristic filtering works fine at startup scale."

**Kanjun Qiu:** "Reflexion is key. After each goal, generate a verbal reflection. Store it. Retrieve relevant reflections before future actions. This is cheap and powerful."

**Harrison Chase:** "Make sure episodes are structured. Goal → Actions → Outcome → Reflection. Then you can query any dimension."

**PRD Requirement:** "Track which recommendations I accept vs adjust. Adapt future recommendations based on preferences."

### 4.1 Episode Memory Design

```python
@dataclass
class Episode:
    """A complete execution episode for learning."""
    episode_id: str
    timestamp: str
    goal: DailyGoal
    actions: list[Action]
    outcome: Outcome
    reflection: str           # LLM-generated insight
    recovery_level_used: int  # 1-4, for tracking recovery patterns
    cost_usd: float
    duration_seconds: int
    tags: list[str]           # For simple filtering: ["feature", "bug", "spec", etc.]

    # Preference learning (PRD requirement)
    approval_response: Optional[str] = None  # "accepted", "modified", "rejected"
    original_recommendation: Optional[str] = None
    human_modification: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "timestamp": self.timestamp,
            "goal": self.goal.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
            "outcome": self.outcome.to_dict(),
            "reflection": self.reflection,
            "recovery_level_used": self.recovery_level_used,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
            "tags": self.tags,
            "approval_response": self.approval_response,
            "original_recommendation": self.original_recommendation,
            "human_modification": self.human_modification,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        return cls(
            episode_id=data["episode_id"],
            timestamp=data["timestamp"],
            goal=DailyGoal.from_dict(data["goal"]),
            actions=[Action.from_dict(a) for a in data["actions"]],
            outcome=Outcome.from_dict(data["outcome"]),
            reflection=data["reflection"],
            recovery_level_used=data["recovery_level_used"],
            cost_usd=data["cost_usd"],
            duration_seconds=data["duration_seconds"],
            tags=data.get("tags", []),
            approval_response=data.get("approval_response"),
            original_recommendation=data.get("original_recommendation"),
            human_modification=data.get("human_modification"),
        )

@dataclass
class Action:
    """A single action within an episode."""
    action_type: str      # "orchestrator_call", "file_edit", "test_run", etc.
    description: str
    result: str
    cost_usd: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(**data)

@dataclass
class Outcome:
    """Outcome of an episode."""
    success: bool
    goal_status: str
    error: Optional[str]
    artifacts_created: list[str]  # Files, specs, etc.

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Outcome":
        return cls(**data)
```

### 4.2 Reflexion Engine

```python
class ReflexionEngine:
    """Generates and retrieves episode reflections for learning."""

    def __init__(self, episode_store: "EpisodeStore", llm: LLMClient):
        self.store = episode_store
        self.llm = llm

    async def reflect(self, episode: Episode) -> str:
        """Generate reflection on completed episode."""
        prompt = f"""
        Analyze this development episode:

        Goal: {episode.goal.content}
        Actions taken: {len(episode.actions)} actions
        Outcome: {"SUCCESS" if episode.outcome.success else "FAILURE"}
        {"Error: " + episode.outcome.error if episode.outcome.error else ""}
        Recovery level: {episode.recovery_level_used}
        Cost: ${episode.cost_usd:.2f}
        Duration: {episode.duration_seconds}s

        Generate a concise reflection (2-3 sentences) covering:
        1. What worked well or poorly?
        2. What would you do differently?
        3. Key insight for similar future goals?
        """

        reflection = await self.llm.complete(prompt, max_tokens=200)
        return reflection

    async def retrieve_relevant(
        self,
        goal: DailyGoal,
        k: int = 3,
        success_only: bool = False,
    ) -> list[Episode]:
        """Retrieve most relevant past episodes using simple heuristics."""

        # Load recent episodes (last 100)
        candidates = self.store.load_recent(limit=100)

        # Filter by success if requested
        if success_only:
            candidates = [e for e in candidates if e.outcome.success]

        # Score by relevance (simple heuristics, no embeddings)
        scored = []
        goal_tags = self._extract_tags(goal)

        for episode in candidates:
            score = 0.0

            # Tag overlap (most important)
            tag_overlap = len(set(episode.tags) & set(goal_tags))
            score += tag_overlap * 0.4

            # Recency boost (episodes from last 7 days score higher)
            age_days = self._days_ago(episode.timestamp)
            if age_days < 7:
                score += 0.3 * (1 - age_days / 7)

            # Success bonus
            if episode.outcome.success:
                score += 0.2

            # Low recovery level is good
            if episode.recovery_level_used == 1:
                score += 0.1

            scored.append((episode, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [ep for ep, _ in scored[:k]]

    def _extract_tags(self, goal: DailyGoal) -> list[str]:
        """Extract tags from goal for matching."""
        tags = []
        if goal.linked_feature:
            tags.append("feature")
            tags.append(goal.linked_feature)
        if goal.linked_bug:
            tags.append("bug")
            tags.append(goal.linked_bug)
        if goal.linked_spec:
            tags.append("spec")
        return tags

    def _days_ago(self, timestamp: str) -> int:
        """Calculate days since timestamp."""
        dt = datetime.fromisoformat(timestamp)
        return (datetime.now() - dt).days

    async def record_episode(
        self,
        goal: DailyGoal,
        result: GoalExecutionResult,
        recovery_level: int,
        actions: list[Action] = None,
        approval_response: Optional[str] = None,
        original_recommendation: Optional[str] = None,
        human_modification: Optional[str] = None,
    ) -> Episode:
        """Record episode and generate reflection."""

        outcome = Outcome(
            success=result.success,
            goal_status=goal.status.value if hasattr(goal.status, 'value') else str(goal.status),
            error=result.error,
            artifacts_created=[],
        )

        tags = self._extract_tags(goal)

        episode = Episode(
            episode_id=f"ep-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            goal=goal,
            actions=actions or [],
            outcome=outcome,
            reflection="",
            recovery_level_used=recovery_level,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
            tags=tags,
            approval_response=approval_response,
            original_recommendation=original_recommendation,
            human_modification=human_modification,
        )

        # Generate reflection
        episode.reflection = await self.reflect(episode)

        # Store
        await self.store.save(episode)

        return episode
```

### 4.3 Preference Learning (PRD Requirement)

```python
@dataclass
class PreferenceWeight:
    """A learned preference weight."""
    key: str                  # e.g., "cost_vs_speed", "conservative_vs_aggressive"
    value: float              # 0.0 to 1.0
    confidence: float         # How confident we are in this weight
    sample_count: int         # Number of data points
    last_updated: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PreferenceWeight":
        return cls(**data)

class PreferenceLearner:
    """Learns human preferences from approval patterns."""

    # Bounded learning: max change per update (David's safety requirement)
    MAX_WEIGHT_CHANGE = 0.1
    MIN_SAMPLES_FOR_CONFIDENCE = 5

    def __init__(self, store: "PreferenceStore"):
        self.store = store
        self.weights: dict[str, PreferenceWeight] = {}

    async def load(self) -> None:
        """Load preference weights from storage."""
        self.weights = await self.store.load_all()

    async def record_decision(
        self,
        checkpoint: Checkpoint,
        episode: Optional[Episode] = None,
    ) -> None:
        """Record a human decision and update preferences.
        
        Called by CheckpointSystem._record_decision after checkpoint resolution.
        """

        # Extract preference signals from the decision
        signals = self._extract_signals(checkpoint, episode)

        for key, direction in signals.items():
            await self._update_weight(key, direction)

        await self.store.save_all(self.weights)

    def _extract_signals(
        self,
        checkpoint: Checkpoint,
        episode: Optional[Episode],
    ) -> dict[str, float]:
        """Extract preference signals from decision."""
        signals = {}

        # Cost sensitivity: did they accept expensive action?
        if checkpoint.trigger == CheckpointTrigger.COST_SINGLE:
            if checkpoint.chosen_option == "Proceed":
                signals["cost_tolerance"] = 0.1  # Increase tolerance
            else:
                signals["cost_tolerance"] = -0.1  # Decrease tolerance

        # Cumulative cost sensitivity
        if checkpoint.trigger == CheckpointTrigger.COST_CUMULATIVE:
            if checkpoint.chosen_option == "Proceed":
                signals["daily_cost_tolerance"] = 0.1
            else:
                signals["daily_cost_tolerance"] = -0.1

        # Risk tolerance: did they accept risky action?
        if checkpoint.trigger in (CheckpointTrigger.ARCHITECTURE, CheckpointTrigger.UX_CHANGE):
            if checkpoint.chosen_option == "Proceed":
                signals["risk_tolerance"] = 0.05
            else:
                signals["risk_tolerance"] = -0.05

        # Hiccup handling preference
        if checkpoint.trigger == CheckpointTrigger.HICCUP:
            if checkpoint.chosen_option == "Retry":
                signals["retry_tolerance"] = 0.1
            elif checkpoint.chosen_option == "Skip":
                signals["skip_tendency"] = 0.1
            elif checkpoint.chosen_option == "Manual":
                signals["manual_preference"] = 0.1

        # Speed vs safety: if they modified, they wanted something different
        if checkpoint.chosen_option == "Modify":
            signals["modification_tendency"] = 0.1

        return signals

    async def _update_weight(self, key: str, direction: float) -> None:
        """Update a preference weight with bounded change."""

        if key not in self.weights:
            self.weights[key] = PreferenceWeight(
                key=key,
                value=0.5,  # Start neutral
                confidence=0.0,
                sample_count=0,
                last_updated=datetime.now().isoformat(),
            )

        weight = self.weights[key]

        # Bounded update (David's safety requirement)
        change = min(abs(direction), self.MAX_WEIGHT_CHANGE) * (1 if direction > 0 else -1)

        # Apply update
        weight.value = max(0.0, min(1.0, weight.value + change))
        weight.sample_count += 1
        weight.confidence = min(1.0, weight.sample_count / self.MIN_SAMPLES_FOR_CONFIDENCE)
        weight.last_updated = datetime.now().isoformat()

    def get_weight(self, key: str, default: float = 0.5) -> float:
        """Get a preference weight, or default if not enough data."""
        if key not in self.weights:
            return default
        weight = self.weights[key]
        if weight.confidence < 0.5:
            return default
        return weight.value

    def get_preference_summary(self) -> dict:
        """Get human-readable preference summary for standup."""
        summary = {}
        for key, weight in self.weights.items():
            if weight.confidence >= 0.5:
                if weight.value > 0.6:
                    summary[key] = "high"
                elif weight.value < 0.4:
                    summary[key] = "low"
                else:
                    summary[key] = "neutral"
        return summary

class PreferenceStore:
    """Persistent storage for preference weights."""

    def __init__(self, base_path: Path):
        self.path = base_path / "preferences.json"

    async def load_all(self) -> dict[str, PreferenceWeight]:
        """Load all preference weights."""
        if not self.path.exists():
            return {}
        with open(self.path, "r") as f:
            data = json.load(f)
            return {k: PreferenceWeight.from_dict(v) for k, v in data.items()}

    async def save_all(self, weights: dict[str, PreferenceWeight]) -> None:
        """Save all preference weights."""
        with open(self.path, "w") as f:
            json.dump({k: v.to_dict() for k, v in weights.items()}, f, indent=2)
```

### 4.4 Episode Store

```python
class EpisodeStore:
    """Persistent storage for episodes using plain JSONL."""

    def __init__(self, base_path: Path):
        self.base_path = base_path / "episodes"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.episodes_file = self.base_path / "episodes.jsonl"

    async def save(self, episode: Episode) -> None:
        """Append episode to JSONL file."""
        with open(self.episodes_file, "a") as f:
            f.write(json.dumps(episode.to_dict()) + "\n")

    def load_recent(self, limit: int = 100) -> list[Episode]:
        """Load most recent episodes from JSONL."""
        if not self.episodes_file.exists():
            return []

        episodes = []
        with open(self.episodes_file, "r") as f:
            for line in f:
                if line.strip():
                    episodes.append(Episode.from_dict(json.loads(line)))

        # Return most recent
        return episodes[-limit:]

    def load_all(self) -> list[Episode]:
        """Load all episodes."""
        return self.load_recent(limit=10000)
```

### Future Enhancement: Embeddings

When episode count exceeds ~500 and retrieval quality degrades, add embedding support:
- Generate embeddings for `goal.content + reflection`
- Store in separate `embeddings.npy` file
- Use cosine similarity for retrieval
- This is a drop-in enhancement to `retrieve_relevant()`

### Implementation Tasks (6 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 9.1 | Create Episode, Action, Outcome dataclasses with serialization | S | - |
| 9.2 | Implement EpisodeStore with JSONL persistence | M | 9.1 |
| 9.3 | Implement ReflexionEngine.reflect() | M | 9.1 |
| 9.4 | Implement ReflexionEngine.retrieve_relevant() with heuristic scoring | M | 9.2 |
| 9.5 | Integrate with RecoveryManager | M | Phase 8, 9.3, 9.4 |
| 9.6 | Implement PreferenceLearner with checkpoint integration | M | 9.1, 7.7 |

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

### 7.3 Discovery Phase (Vibe Plan)

**Pattern:** Unstructured exploration BEFORE formal spec writing. Prevents premature convergence.

```python
@dataclass
class DiscoveryNotes:
    """Output of discovery phase - unstructured exploration."""
    feature_id: str
    created_at: str

    # Unstructured outputs
    initial_reactions: str          # Excitement, concerns, ambiguities
    architecture_options: list[str] # Different approaches considered
    technology_considerations: str  # Libraries, frameworks, patterns
    edge_cases: list[str]           # Things that could go wrong
    risks: list[str]                # Potential problems
    questions_for_pm: list[str]     # Clarifications needed
    implementation_approaches: list[dict]  # MVP vs full vision

    # Raw exploration
    exploration_notes: str          # Free-form markdown

class DiscoveryAgent:
    """Run unstructured exploration before spec writing."""

    DISCOVERY_PROMPT = """
    You are exploring a feature request BEFORE writing any formal spec.
    Think freely and explore deeply. There are NO structured output requirements.

    Feature: {prd_summary}

    Explore:
    1. **Initial Reactions** - What excites you? What concerns you? What's unclear?
    2. **Architecture Options** - At least 3 different approaches. Pros/cons of each.
    3. **Technology Considerations** - Libraries, frameworks, patterns that could help.
    4. **Edge Cases** - What could go wrong? Unusual scenarios?
    5. **Risks** - Technical risks, scope risks, integration risks.
    6. **Questions for PM** - What do you need clarified before speccing?
    7. **Implementation Approaches** - MVP (minimal) vs Full Vision. What's the difference?

    Output: Free-form markdown notes. Think out loud. Explore tangents.
    This is NOT a spec - it's exploration to inform the spec.
    """

    async def explore(self, prd_path: str, feature_id: str) -> DiscoveryNotes:
        """Run discovery phase on a PRD."""
        prd_content = Path(prd_path).read_text()
        prd_summary = self._extract_summary(prd_content)

        prompt = self.DISCOVERY_PROMPT.format(prd_summary=prd_summary)

        result = await self.llm.complete(
            prompt,
            max_tokens=4000,
            temperature=0.8,  # Higher temperature for creativity
        )

        notes = self._parse_discovery_notes(result.content, feature_id)

        # Save to .swarm/discovery/{feature_id}.md
        self._save_discovery_notes(notes)

        return notes

# Integration in Orchestrator
class Orchestrator:
    async def run_spec_pipeline(self, feature_id: str) -> SpecResult:
        prd_path = self._get_prd_path(feature_id)

        # NEW: Discovery phase before spec author
        discovery = await self.discovery_agent.explore(prd_path, feature_id)

        # Surface questions to PM via checkpoint
        if discovery.questions_for_pm:
            await self._checkpoint_for_pm_questions(discovery)

        # Pass discovery context to spec author
        spec_result = await self.spec_author.run(
            prd_path,
            discovery_context=discovery,  # NEW: discovery informs spec
        )

        # ... rest of spec pipeline ...
```

### 7.4 Interval Checkpoints

**Pattern:** Periodic checkpoints every N issues, not just on events. Regular human touchpoints.

```python
@dataclass
class IntervalCheckpointConfig:
    """Configuration for interval-based checkpoints."""
    enabled: bool = True
    issues_per_checkpoint: int = 3      # Checkpoint every 3 issues
    time_based_minutes: int = 60        # Or every 60 minutes
    force_on_milestone: bool = True     # Always checkpoint at milestones

class CheckpointSystem:
    def __init__(self, ...):
        # ... existing init ...
        self._issues_since_checkpoint = 0
        self._last_checkpoint_time = datetime.now()

    def _check_interval_trigger(self, goal: DailyGoal) -> bool:
        """Check if interval checkpoint is due."""
        if not self.config.interval_checkpoints.enabled:
            return False

        # Issue count trigger
        if self._issues_since_checkpoint >= self.config.interval_checkpoints.issues_per_checkpoint:
            return True

        # Time-based trigger
        minutes_elapsed = (datetime.now() - self._last_checkpoint_time).total_seconds() / 60
        if minutes_elapsed >= self.config.interval_checkpoints.time_based_minutes:
            return True

        # Milestone trigger
        if self.config.interval_checkpoints.force_on_milestone:
            if self._is_milestone_boundary(goal):
                return True

        return False

    def _detect_triggers(self, goal: DailyGoal) -> list[CheckpointTrigger]:
        triggers = []

        # NEW: Interval checkpoint
        if self._check_interval_trigger(goal):
            triggers.append(CheckpointTrigger.INTERVAL)

        # ... existing triggers ...

        return triggers

    def mark_checkpoint_completed(self) -> None:
        """Reset interval counters after checkpoint."""
        self._issues_since_checkpoint = 0
        self._last_checkpoint_time = datetime.now()

    def increment_issue_count(self) -> None:
        """Called after each issue completes."""
        self._issues_since_checkpoint += 1
```

**CLI Enhancement:**

```bash
# Configure interval checkpoints
swarm-attack cos config set interval_checkpoint_issues 3
swarm-attack cos config set interval_checkpoint_minutes 60

# View checkpoint due status
swarm-attack cos status
# Output includes: "Next checkpoint in: 2 issues or 45 minutes"
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

### 7.6 Progress Snapshot API

**Pattern:** Real-time computed metrics without recalculation. Visibility into agent progress.

```python
@dataclass
class ProgressSnapshot:
    """Computed progress metrics at a point in time."""
    # Counts
    total: int
    completed: int
    in_progress: int
    blocked: int
    failed: int
    pending: int

    # Percentages
    percent_complete: float
    percent_blocked: float

    # Velocity
    issues_per_hour: float
    estimated_completion_hours: float

    # Cost
    total_cost_usd: float
    average_cost_per_issue: float
    remaining_budget_usd: float

    # Time
    elapsed_seconds: int
    average_seconds_per_issue: float

    # Trends
    velocity_trend: str             # "increasing", "stable", "decreasing"
    cost_trend: str                 # "under_budget", "on_budget", "over_budget"

class ProgressTracker:
    """Track and compute progress metrics."""

    def __init__(self, state_store: StateStore):
        self.state_store = state_store
        self._history: list[ProgressSnapshot] = []

    def get_snapshot(self, feature_id: str) -> ProgressSnapshot:
        """Compute current progress snapshot."""
        state = self.state_store.load(feature_id)
        tasks = state.tasks

        total = len(tasks)
        completed = sum(1 for t in tasks if t.stage == TaskStage.DONE)
        in_progress = sum(1 for t in tasks if t.stage == TaskStage.IMPLEMENTING)
        blocked = sum(1 for t in tasks if t.stage == TaskStage.BLOCKED)
        failed = sum(1 for t in tasks if t.stage == TaskStage.FAILED)
        pending = total - completed - in_progress - blocked - failed

        # Calculate velocity
        elapsed = (datetime.now() - state.started_at).total_seconds() if state.started_at else 1
        issues_per_hour = (completed / elapsed) * 3600 if elapsed > 0 else 0
        remaining = total - completed
        estimated_hours = remaining / issues_per_hour if issues_per_hour > 0 else float('inf')

        # Cost metrics
        total_cost = sum(t.cost_usd for t in tasks if t.cost_usd)
        avg_cost = total_cost / completed if completed > 0 else 0
        remaining_budget = state.budget_usd - total_cost

        # Trends
        velocity_trend = self._calculate_velocity_trend(feature_id)
        cost_trend = self._calculate_cost_trend(state.budget_usd, total_cost, completed, total)

        snapshot = ProgressSnapshot(
            total=total,
            completed=completed,
            in_progress=in_progress,
            blocked=blocked,
            failed=failed,
            pending=pending,
            percent_complete=(completed / total * 100) if total > 0 else 0,
            percent_blocked=(blocked / total * 100) if total > 0 else 0,
            issues_per_hour=issues_per_hour,
            estimated_completion_hours=estimated_hours,
            total_cost_usd=total_cost,
            average_cost_per_issue=avg_cost,
            remaining_budget_usd=remaining_budget,
            elapsed_seconds=int(elapsed),
            average_seconds_per_issue=elapsed / completed if completed > 0 else 0,
            velocity_trend=velocity_trend,
            cost_trend=cost_trend,
        )

        self._history.append(snapshot)
        return snapshot
```

**CLI Integration:**

```bash
swarm-attack cos progress chief-of-staff-v2

# Output:
# Progress: 12/35 issues (34.3%)
# ━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░░░
#
# Status: 1 in progress, 2 blocked, 0 failed
# Velocity: 2.4 issues/hour (stable)
# Cost: $15.40 spent, $34.60 remaining (on budget)
# ETA: ~9.6 hours
#
# Next checkpoint in: 1 issue
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

### 7.9 Implementation Tasks (Additional)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 12.1 | Implement RiskScoringEngine | M | 9.2, 9.3 |
| 12.2 | Implement PreFlightChecker | M | 12.1 |
| 12.3 | Implement DiscoveryAgent and discovery phase | M | - |
| 12.4 | Add interval checkpoint configuration and triggers | S | 7.7 |
| 12.5 | Implement FeedbackIncorporator | M | 7.6 |
| 12.6 | Implement ProgressTracker and snapshot API | S | - |
| 12.7 | Implement continue-on-block execution strategy | M | 7.2 |
| 12.8 | Implement EnhancedCheckpoint format | M | 7.6, 12.1 |
| 12.9 | Add progress and feedback CLI commands | S | 12.5, 12.6 |

---

## 8. Success Metrics

| Metric | v1 Baseline | v2 Target | Measurement |
|--------|-------------|-----------|-------------|
| Real execution rate | 0% (stub) | 100% | Goals that call orchestrators |
| Automatic recovery | 0% | 70% | Failures resolved without human |
| Human review reduction | 100% manual | <30% | Artifacts bypassing review |
| Multi-day completion | N/A | >75% | Campaigns finished as planned |
| Learning improvement | None | +10%/month | Goal completion rate trend |
| Cost efficiency | Unmeasured | Track | $/completed goal trend |
| Checkpoint response time | N/A | <30 min avg | Time from checkpoint to resolution |

---

## 8. Risk Mitigations

| Risk | Mitigation | Owner |
|------|------------|-------|
| Runaway execution | Per-day + per-campaign budget caps, mandatory checkpoints | David's design |
| Bad learning loops | Bounded weight changes (±10% per update), rollback on degradation | Kanjun's design |
| Infinite recovery | 4-level cap with forced escalation, circuit breakers | Shunyu's design |
| Context bloat | Episode pruning (keep last 100), recency decay | Jerry's design |
| Missed checkpoints | Explicit trigger thresholds including hiccups, default to checkpoint on uncertainty | P0 design |

---

## 9. Implementation Roadmap

### Phase 7: Real Execution + Checkpoints (MVP - Do First)
**10 issues** (5 execution + 5 checkpoint)

This is the foundation. Without real execution, v2 is just a more elaborate stub. Checkpoints are P0 - required for collaborative autonomy.

### Phase 8: Hierarchical Recovery (Core Autonomy)
**5 issues**

Enables overnight runs. Combined with Phase 7, you can say "work on this" and trust it to make progress without babysitting.

### Phase 9: Episode Memory + Reflexion + Preferences (Learning)
**6 issues** (5 memory + 1 preference learning)

Cheap investment, high payoff. Every execution makes future executions better. Preference learning satisfies PRD requirement.

### Phase 10: Multi-Day Campaigns + Weekly Planning (Strategic)
**8 issues** (7 campaigns + 1 weekly)

Graduate from "daily tasks" to "build this feature over the week." Weekly planning satisfies PRD User Story #6.

### Phase 11: Internal Validation (Scale)
**6 issues**

Reduces human bottleneck. Most specs/code auto-approve; you only see the hard cases.

### Phase 12: World-Class Enhancements (Research-Driven)
**9 issues**

Industry-leading patterns from LangGraph, Apify, and agent-harness:
- Risk scoring engine (nuanced 0-1 scores vs binary)
- Pre-flight validation (catch issues before execution)
- Discovery phase (exploration before spec)
- Interval checkpoints (regular human touchpoints)
- Feedback incorporation (learning that sticks)
- Progress tracking (real-time visibility)
- Continue-on-block (resilient execution)
- Enhanced Q&A format (tradeoffs, recommendations, context)

**Total: 44 issues across 6 phases**

---

## 10. Expert Panel Final Statement

**Harrison Chase:** "The roadmap is pragmatic. Phase 7 → 8 → 9 builds a solid autonomous agent. Phases 10-11 add strategic capability. **Phase 12's world-class enhancements** from LangGraph interrupt patterns are exactly right for the Q&A checkpoint experience. Ship Phase 7-9 first, validate, then proceed."

**Jerry Liu:** "Episode memory with simple retrieval is the right call for startup scale. Add embeddings when you have thousands of episodes, not before. **The progress snapshot API** gives you visibility without complexity. Parallel execution can wait for v3."

**Kanjun Qiu:** "Bounded learning is critical. **Risk scoring** (0-1 nuanced vs binary) is a massive upgrade - it lets the system learn what 'risky' means for YOUR codebase. **Feedback incorporation loop** ensures human guidance persists across sessions."

**David Dohan:** "I'm satisfied with the checkpoint system and escalation paths. **Pre-flight validation** is the right addition - catch issues BEFORE spending tokens, not after. The security veto in validation is essential. Don't compromise on that."

**Shunyu Yao:** "Simplified recovery is the right call. **Discovery phase** before spec writing prevents premature convergence - let the system explore before committing. **Continue-on-block** is pragmatic - don't halt the whole campaign for one stuck issue."

---

## 11. Summary: What Makes This World-Class

| Dimension | Standard Approach | World-Class Approach (This Spec) |
|-----------|-------------------|----------------------------------|
| **Risk Detection** | Pattern matching on keywords | Multi-factor scoring (cost, scope, reversibility, precedent) |
| **Checkpoints** | Event-triggered only | Event + interval + milestone triggers |
| **Q&A Format** | Yes/no approval | Options with tradeoffs, recommendations, similar past decisions |
| **Feedback** | One-time approval | Feedback incorporated into future prompts |
| **Learning** | Static weights | Preference learning from approval patterns |
| **Visibility** | Post-hoc logs | Real-time progress snapshots with velocity/cost trends |
| **Resilience** | Stop on failure | Continue with independent issues |
| **Planning** | Jump to spec | Discovery exploration → spec |

This spec combines:
- **LangGraph** interrupt/resume patterns for human-in-the-loop
- **Apify** role-based orchestration and maker-checker loops
- **agent-harness** interval checkpoints and feedback incorporation
- **Industry best practices** for risk scoring and pre-flight validation

---

*Spec finalized: December 2025*
*Expert Panel: LangChain, LlamaIndex, Imbue, Anthropic, Princeton*
*Research Sources: Apify, LangGraph, agent-harness, Azure AI Patterns*
*Ready for implementation*