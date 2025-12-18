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
| Memory | JSONL decisions only | **Episode memory + Reflexion** |
| Planning | Single-day horizon | **Multi-day campaigns** |
| Validation | Human reviews everything | **Internal critics pre-filter** |

### Expert Panel Priority Ranking (Final)

| Rank | Extension | Impact × Feasibility | Rationale |
|------|-----------|---------------------|-----------|
| **P1** | Real Execution | 10 × 9 = 90 | Foundation for everything - without this, nothing works |
| **P2** | Hierarchical Recovery | 9 × 8 = 72 | Essential for overnight autonomy |
| **P3** | Episode Memory + Reflexion | 9 × 7 = 63 | Low-cost learning with high ROI |
| **P4** | Multi-Day Campaigns | 8 × 7 = 56 | Enables complex features without restarts |
| **P5** | Internal Validation Critics | 8 × 6 = 48 | Reduces human review burden by ~70% |

---

## 2. Phase 7: Real Execution (P1)

### Consensus Decision

**Harrison Chase:** "This is table stakes. The current stub defeats the entire purpose. Just wire it up."

**David Dohan:** "Agreed, but add defensive wrappers. Never let a goal execute without budget/time checks BEFORE the call, not just after."

**Final Design:**

```python
class AutopilotRunner:
    def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        """Execute a goal by calling the appropriate orchestrator."""

        # Pre-execution safety check (David's requirement)
        remaining_budget = self.session.budget_usd - self.session.cost_spent_usd
        if remaining_budget < self.config.min_execution_budget:
            return GoalExecutionResult(
                success=False,
                error="Insufficient budget remaining",
                cost_usd=0,
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
            return GoalExecutionResult(
                success=False,
                error=str(e),
                cost_usd=0,
            )
```

### Implementation Tasks (5 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 7.1 | Add orchestrator dependency to AutopilotRunner | S | - |
| 7.2 | Implement feature execution path | M | 7.1 |
| 7.3 | Implement bug execution path | M | 7.1 |
| 7.4 | Implement spec pipeline execution path | M | 7.1 |
| 7.5 | Add pre-execution budget checks | S | 7.1 |

---

## 3. Phase 8: Hierarchical Error Recovery (P2)

### Consensus Decision

**Shunyu Yao:** "Use bounded Tree-of-Thought. Generate 3 alternatives, evaluate each mentally, pick best. But cap exploration depth - no infinite loops."

**David Dohan:** "Agree. Add circuit breakers at each level. And the human escalation MUST happen within 30 minutes of hitting Level 4."

**Kanjun Qiu:** "Track which recovery strategies work. Feed that back into Reflexion for future episodes."

**Final Design:**

```python
class RecoveryLevel(Enum):
    RETRY_SAME = 1      # Transient failure - retry with same approach
    RETRY_ALTERNATE = 2  # Systematic failure - try alternative approach
    RETRY_CLARIFY = 3   # Missing context - ask clarifying question
    ESCALATE = 4        # Human required - checkpoint pause

@dataclass
class RecoveryStrategy:
    level: RecoveryLevel
    max_attempts: int
    backoff_seconds: int
    alternatives_to_generate: int = 0

class RecoveryManager:
    LEVELS = [
        RecoveryStrategy(RecoveryLevel.RETRY_SAME, max_attempts=3, backoff_seconds=5),
        RecoveryStrategy(RecoveryLevel.RETRY_ALTERNATE, max_attempts=2, backoff_seconds=10, alternatives_to_generate=3),
        RecoveryStrategy(RecoveryLevel.RETRY_CLARIFY, max_attempts=1, backoff_seconds=0),
        RecoveryStrategy(RecoveryLevel.ESCALATE, max_attempts=1, backoff_seconds=0),
    ]

    def __init__(self, config: ChiefOfStaffConfig, reflexion: ReflexionEngine):
        self.config = config
        self.reflexion = reflexion
        self.error_streak = 0

    async def execute_with_recovery(
        self,
        goal: DailyGoal,
        action: Callable[[], GoalExecutionResult],
    ) -> GoalExecutionResult:
        """Execute action with automatic recovery through all levels."""

        last_result = None

        for strategy in self.LEVELS:
            for attempt in range(strategy.max_attempts):
                # Retrieve relevant past episodes for context
                context = await self.reflexion.retrieve_relevant(goal, k=3)

                if strategy.level == RecoveryLevel.RETRY_ALTERNATE:
                    # Generate alternatives using Tree-of-Thought (bounded)
                    alternatives = await self._generate_alternatives(
                        goal, last_result, context,
                        n=strategy.alternatives_to_generate
                    )
                    action = self._select_best_alternative(alternatives)

                elif strategy.level == RecoveryLevel.RETRY_CLARIFY:
                    # Ask clarifying question, incorporate answer
                    clarification = await self._ask_clarification(goal, last_result)
                    if clarification:
                        goal = self._incorporate_clarification(goal, clarification)

                # Execute with backoff
                if attempt > 0:
                    await asyncio.sleep(strategy.backoff_seconds * (2 ** attempt))

                result = await action()

                if result.success:
                    self.error_streak = 0
                    # Record success for Reflexion learning
                    await self.reflexion.record_episode(goal, result, strategy.level)
                    return result

                last_result = result
                self.error_streak += 1

                # Check circuit breaker
                if self.error_streak >= self.config.error_streak_threshold:
                    break

        # All levels exhausted - escalate to human
        return await self._escalate_to_human(goal, last_result)

    async def _generate_alternatives(
        self,
        goal: DailyGoal,
        failure: GoalExecutionResult,
        context: list[Episode],
        n: int = 3,
    ) -> list[Callable]:
        """Generate n alternative approaches using Tree-of-Thought."""
        prompt = f"""
        Goal: {goal.content}
        Failed approach: {failure.output}
        Error: {failure.error}

        Relevant past episodes:
        {[e.reflection for e in context]}

        Generate {n} alternative approaches. For each:
        1. Describe the approach
        2. Estimate probability of success (0-1)
        3. Estimate cost multiplier vs original

        Return as structured JSON.
        """
        # ... LLM call and parsing
```

### Implementation Tasks (6 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 8.1 | Create RecoveryManager class | M | Phase 7 |
| 8.2 | Implement Level 1 (retry same) | S | 8.1 |
| 8.3 | Implement Level 2 (alternatives) with ToT | L | 8.1 |
| 8.4 | Implement Level 3 (clarification) | M | 8.1 |
| 8.5 | Implement Level 4 (escalation) | S | 8.1 |
| 8.6 | Add circuit breakers and error streak tracking | S | 8.1-8.5 |

---

## 4. Phase 9: Episode Memory + Reflexion (P3)

### Consensus Decision

**Jerry Liu:** "JSONL episodes with semantic embeddings. Retrieve by similarity, not just recency. But keep it simple - local embeddings are fine for this volume."

**Kanjun Qiu:** "Reflexion is key. After each goal, generate a verbal reflection. Store it. Retrieve relevant reflections before future actions. This is cheap and powerful."

**Harrison Chase:** "Make sure episodes are structured. Goal → Actions → Outcome → Reflection. Then you can query any dimension."

**Final Design:**

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
    embedding: Optional[list[float]] = None  # For semantic search

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
        }

@dataclass
class Action:
    """A single action within an episode."""
    action_type: str      # "orchestrator_call", "file_edit", "test_run", etc.
    description: str
    result: str
    cost_usd: float

@dataclass
class Outcome:
    """Outcome of an episode."""
    success: bool
    goal_status: GoalStatus
    error: Optional[str]
    artifacts_created: list[str]  # Files, specs, etc.

class ReflexionEngine:
    """Generates and retrieves episode reflections for learning."""

    def __init__(self, episode_store: EpisodeStore, llm: LLMClient):
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
        """Retrieve most relevant past episodes."""

        # Combine semantic similarity with recency weighting
        # Jerry's requirement: recency decay without deletion

        query_embedding = await self._embed(goal.content)

        candidates = self.store.search_by_embedding(
            query_embedding,
            k=k*2,  # Over-fetch for filtering
        )

        # Apply time decay (recent episodes rank higher)
        now = datetime.now()
        for episode in candidates:
            age_days = (now - datetime.fromisoformat(episode.timestamp)).days
            episode._relevance_score *= (0.95 ** age_days)  # 5% decay per day

        # Filter and sort
        if success_only:
            candidates = [e for e in candidates if e.outcome.success]

        candidates.sort(key=lambda e: e._relevance_score, reverse=True)
        return candidates[:k]

    async def record_episode(
        self,
        goal: DailyGoal,
        result: GoalExecutionResult,
        recovery_level: int,
        actions: list[Action],
    ) -> Episode:
        """Record episode and generate reflection."""

        outcome = Outcome(
            success=result.success,
            goal_status=goal.status,
            error=result.error,
            artifacts_created=[],  # Extract from result
        )

        episode = Episode(
            episode_id=f"ep-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat(),
            goal=goal,
            actions=actions,
            outcome=outcome,
            reflection="",  # Generate next
            recovery_level_used=recovery_level,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
        )

        # Generate reflection
        episode.reflection = await self.reflect(episode)

        # Generate embedding for future retrieval
        episode.embedding = await self._embed(
            f"{goal.content} {episode.reflection}"
        )

        # Store
        await self.store.save(episode)

        return episode

class EpisodeStore:
    """Persistent storage for episodes with JSONL + embeddings."""

    def __init__(self, base_path: Path):
        self.base_path = base_path / "episodes"
        self.episodes_file = self.base_path / "episodes.jsonl"
        self.embeddings_file = self.base_path / "embeddings.npy"

    async def save(self, episode: Episode) -> None:
        """Append episode to JSONL and update embeddings."""
        # Append to JSONL
        with open(self.episodes_file, "a") as f:
            f.write(json.dumps(episode.to_dict()) + "\n")

        # Update embeddings (batch periodically for efficiency)
        if episode.embedding:
            self._append_embedding(episode.episode_id, episode.embedding)

    def search_by_embedding(
        self,
        query: list[float],
        k: int,
    ) -> list[Episode]:
        """Find k most similar episodes by embedding."""
        # Load embeddings and compute cosine similarity
        # Return top k episodes
```

### Implementation Tasks (6 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 9.1 | Create Episode, Action, Outcome dataclasses | S | - |
| 9.2 | Implement EpisodeStore with JSONL persistence | M | 9.1 |
| 9.3 | Add embedding generation (local or API) | M | 9.2 |
| 9.4 | Implement ReflexionEngine.reflect() | M | 9.1 |
| 9.5 | Implement ReflexionEngine.retrieve_relevant() | M | 9.2, 9.3 |
| 9.6 | Integrate with RecoveryManager | M | Phase 8, 9.4, 9.5 |

---

## 5. Phase 10: Multi-Day Campaigns (P4)

### Consensus Decision

**Shunyu Yao:** "Backward planning from goal state. Define milestones, then decompose into daily goals. Re-plan only when >30% off track."

**Harrison Chase:** "Add state machine for campaign lifecycle. PLANNING → ACTIVE → PAUSED → COMPLETED/FAILED. Persist everything."

**Jerry Liu:** "Campaign context needs to persist across days. Store in a campaign.json with all state."

**David Dohan:** "Budget caps must be per-campaign AND per-day. Daily cap prevents single-day runaway."

**Final Design:**

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

    def days_behind(self) -> int:
        """Calculate how many days behind schedule."""
        if self.state != CampaignState.ACTIVE:
            return 0

        planned_progress = self.current_day / self.original_duration_days
        actual_progress = len([m for m in self.milestones if m.status == "done"]) / len(self.milestones)

        if actual_progress < planned_progress:
            return int((planned_progress - actual_progress) * self.original_duration_days)
        return 0

    def needs_replan(self) -> bool:
        """Check if campaign is far enough behind to trigger replan."""
        if len(self.milestones) == 0:
            return False

        progress_gap = self.days_behind() / self.original_duration_days
        return progress_gap > self.replanning_threshold

class CampaignPlanner:
    """Plans multi-day campaigns using backward planning."""

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
        - milestones: [{name, description, target_day, success_criteria}]
        - day_plans: [{day_number, goals: [{content, priority, estimated_minutes, linked_*}]}]
        - total_estimated_days
        - total_estimated_cost_usd
        """

        plan_response = await self.llm.complete(prompt, max_tokens=2000)
        # Parse and create Campaign

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
        """

        # Generate revised plan
        campaign.replan_count += 1
        # Update day_plans for remaining days

class CampaignExecutor:
    """Executes campaign day by day."""

    def __init__(
        self,
        autopilot: AutopilotRunner,
        planner: CampaignPlanner,
        store: CampaignStore,
    ):
        self.autopilot = autopilot
        self.planner = planner
        self.store = store

    async def execute_day(self, campaign: Campaign) -> DayResult:
        """Execute one day of the campaign."""

        if campaign.state != CampaignState.ACTIVE:
            raise ValueError(f"Campaign not active: {campaign.state}")

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

        # Persist
        await self.store.save(campaign)

        return DayResult(
            campaign_id=campaign.campaign_id,
            day=campaign.current_day - 1,
            goals_completed=result.goals_completed,
            cost_usd=result.total_cost_usd,
            campaign_progress=self._calculate_progress(campaign),
        )

    async def resume(self, campaign_id: str) -> Campaign:
        """Resume a paused or next-day campaign."""
        campaign = await self.store.load(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")

        if campaign.state == CampaignState.PAUSED:
            campaign.state = CampaignState.ACTIVE

        return campaign
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
```

### Implementation Tasks (7 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 10.1 | Create Campaign, Milestone, DayPlan dataclasses | M | - |
| 10.2 | Implement CampaignStore persistence | M | 10.1 |
| 10.3 | Implement CampaignPlanner.plan() | L | 10.1 |
| 10.4 | Implement CampaignPlanner.replan() | M | 10.3 |
| 10.5 | Implement CampaignExecutor.execute_day() | L | 10.1, Phase 7 |
| 10.6 | Add campaign CLI commands | M | 10.2, 10.5 |
| 10.7 | Add campaign progress to standup | S | 10.2 |

---

## 6. Phase 11: Internal Validation Critics (P5)

### Consensus Decision

**Kanjun Qiu:** "Use diverse critics - one for each quality dimension. They should disagree with each other to surface real issues."

**Harrison Chase:** "Majority voting for approval, but ANY security critic veto blocks. Safety is not a democracy."

**David Dohan:** "Track critic accuracy over time. If a critic is consistently wrong, reduce its weight. But never zero - preserve voice."

**Final Design:**

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

@dataclass
class ValidationResult:
    artifact_type: str        # "spec", "code", "test"
    artifact_id: str
    approved: bool
    scores: list[CriticScore]
    blocking_issues: list[str]
    consensus_summary: str
    human_review_required: bool

class Critic:
    """Base class for validation critics."""

    def __init__(self, focus: CriticFocus, weight: float = 1.0):
        self.focus = focus
        self.weight = weight
        self.has_veto = focus == CriticFocus.SECURITY

    async def evaluate(self, artifact: str) -> CriticScore:
        raise NotImplementedError

class SpecCritic(Critic):
    """Evaluates engineering specs."""

    async def evaluate(self, spec_content: str) -> CriticScore:
        prompt = f"""
        Evaluate this engineering spec for {self.focus.value}:

        {spec_content[:4000]}  # Truncate for context

        Rate 0-1 on:
        - {"How complete is the spec? Missing sections? Gaps?" if self.focus == CriticFocus.COMPLETENESS else ""}
        - {"Can this be implemented as written? Unclear requirements?" if self.focus == CriticFocus.FEASIBILITY else ""}
        - {"Security issues? Injection risks? Auth gaps?" if self.focus == CriticFocus.SECURITY else ""}

        Return JSON: {{score, approved, issues: [], suggestions: [], reasoning}}
        """

        response = await self.llm.complete(prompt)
        return CriticScore.from_dict(json.loads(response))

class CodeCritic(Critic):
    """Evaluates code changes."""

    async def evaluate(self, code_diff: str) -> CriticScore:
        # Similar structure, code-specific checks

class TestCritic(Critic):
    """Evaluates test coverage and quality."""

class ValidationLayer:
    """Orchestrates multiple critics for consensus building."""

    def __init__(self, config: ChiefOfStaffConfig):
        self.config = config
        self.critics = [
            SpecCritic(CriticFocus.COMPLETENESS),
            SpecCritic(CriticFocus.FEASIBILITY),
            SpecCritic(CriticFocus.SECURITY),
            CodeCritic(CriticFocus.STYLE),
            CodeCritic(CriticFocus.SECURITY),
            TestCritic(CriticFocus.COVERAGE),
            TestCritic(CriticFocus.EDGE_CASES),
        ]

    async def validate(
        self,
        artifact: str,
        artifact_type: str,
    ) -> ValidationResult:
        """Run all relevant critics and build consensus."""

        relevant_critics = [c for c in self.critics if self._is_relevant(c, artifact_type)]

        # Run critics in parallel
        scores = await asyncio.gather(*[
            c.evaluate(artifact) for c in relevant_critics
        ])

        # Check for security veto
        security_scores = [s for s in scores if s.focus == CriticFocus.SECURITY]
        if any(not s.approved for s in security_scores):
            return ValidationResult(
                artifact_type=artifact_type,
                artifact_id="",
                approved=False,
                scores=scores,
                blocking_issues=[
                    issue for s in security_scores for issue in s.issues
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
            artifact_id="",
            approved=approved,
            scores=scores,
            blocking_issues=[
                issue for s in scores if not s.approved for issue in s.issues
            ],
            consensus_summary=self._build_summary(scores, approved),
            human_review_required=not approved,
        )

    def _build_summary(self, scores: list[CriticScore], approved: bool) -> str:
        avg_score = sum(s.score for s in scores) / len(scores)

        if approved:
            return f"APPROVED by consensus (avg score: {avg_score:.2f})"
        else:
            concerns = [s.focus.value for s in scores if not s.approved]
            return f"NEEDS REVIEW: concerns in {', '.join(concerns)} (avg: {avg_score:.2f})"
```

### Implementation Tasks (5 issues)

| # | Task | Size | Dependencies |
|---|------|------|--------------|
| 11.1 | Create Critic base class and CriticScore | S | - |
| 11.2 | Implement SpecCritic variants | M | 11.1 |
| 11.3 | Implement CodeCritic variants | M | 11.1 |
| 11.4 | Implement TestCritic variants | M | 11.1 |
| 11.5 | Implement ValidationLayer consensus | M | 11.2-11.4 |

---

## 7. Success Metrics

| Metric | v1 Baseline | v2 Target | Measurement |
|--------|-------------|-----------|-------------|
| Real execution rate | 0% (stub) | 100% | Goals that call orchestrators |
| Automatic recovery | 0% | 70% | Failures resolved without human |
| Human review reduction | 100% manual | <30% | Artifacts bypassing review |
| Multi-day completion | N/A | >75% | Campaigns finished as planned |
| Learning improvement | None | +10%/month | Goal completion rate trend |
| Cost efficiency | Unmeasured | Track | $/completed goal trend |

---

## 8. Risk Mitigations

| Risk | Mitigation | Owner |
|------|------------|-------|
| Runaway execution | Per-day + per-campaign budget caps, mandatory checkpoints | David's design |
| Bad learning loops | Bounded weight changes (±20%/week), rollback on degradation | Kanjun's design |
| Parallel corruption | Git worktrees with cleanup, conflict detection | Harrison's design |
| Infinite recovery | 4-level cap with forced escalation, circuit breakers | Shunyu's design |
| Context bloat | Episode pruning, embedding-based retrieval, recency decay | Jerry's design |

---

## 9. Implementation Roadmap

### Phase 7: Real Execution (MVP - Do First)
**5 issues, ~1 week**

This is the foundation. Without real execution, v2 is just a more elaborate stub.

### Phase 8: Hierarchical Recovery (Core Autonomy)
**6 issues, ~1.5 weeks**

Enables overnight runs. Combined with Phase 7, you can say "work on this" and trust it to make progress without babysitting.

### Phase 9: Episode Memory + Reflexion (Learning)
**6 issues, ~1.5 weeks**

Cheap investment, high payoff. Every execution makes future executions better.

### Phase 10: Multi-Day Campaigns (Strategic)
**7 issues, ~2 weeks**

Graduate from "daily tasks" to "build this feature over the week."

### Phase 11: Internal Validation (Scale)
**5 issues, ~1 week**

Reduces human bottleneck. Most specs/code auto-approve; you only see the hard cases.

---

## 10. Expert Panel Final Statement

**Harrison Chase:** "The roadmap is pragmatic. Phase 7 → 8 → 9 builds a solid autonomous agent. Phases 10-11 add strategic capability. Ship Phase 7-9 first, validate, then proceed."

**Jerry Liu:** "Episode memory with Reflexion is the sleeper hit. Low effort, compounds over time. Prioritize this once execution works."

**Kanjun Qiu:** "Bounded learning is critical. The 4-level recovery and weight caps prevent runaway self-modification. Good safety design."

**David Dohan:** "I'm satisfied with the checkpoint system and escalation paths. The security veto in validation is essential. Don't compromise on that."

**Shunyu Yao:** "Tree-of-Thought for alternatives, backward planning for campaigns - clean application of research. Keep the bounds tight on exploration depth."

---

*Spec finalized: December 2025*
*Expert Panel: LangChain, LlamaIndex, Imbue, Anthropic, Princeton*
*Ready for implementation*
