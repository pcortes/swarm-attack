# Chief of Staff Agent v2 PRD

## Expert Panel Input Document

**Panel Composition:** World-class experts in agentic LLM orchestration from leading AI companies.

| Expert | Affiliation | Specialty |
|--------|-------------|-----------|
| **Harrison Chase** | LangChain | Agent frameworks, tool orchestration, LangGraph state machines |
| **Jerry Liu** | LlamaIndex | Data agents, retrieval-augmented agents, agentic RAG |
| **Kanjun Qiu** | Imbue (formerly Generally Intelligent) | Reasoning agents, self-improving systems |
| **David Dohan** | Anthropic Claude | Constitutional AI, computer use agents, tool safety |
| **Shunyu Yao** | Princeton/OpenAI | ReAct, Tree-of-Thought, agent reasoning paradigms |

---

## Executive Summary

Chief of Staff v1 is complete (20/20 issues, 279 tests). This PRD defines v2: the extensions that transform it from a daily workflow tool into a fully autonomous development partner capable of multi-day campaigns, self-improvement, and strategic planning.

**v1 Capabilities (COMPLETE):**
- Cross-session memory (daily logs, decisions)
- Daily standups with recommendations
- Plan tracking with goal reconciliation
- Autopilot mode with checkpoint gates (stub execution)

**v2 Vision:** An autonomous "AI Tech Lead" that can:
1. Plan and execute multi-day development campaigns
2. Learn from its own successes and failures
3. Coordinate multiple parallel workstreams
4. Self-recover from errors without human intervention
5. Generate and validate its own specifications

---

## Problem Statement

### Current Limitations (v1)

1. **Single-Day Horizon**: Plans only for "today" - no multi-day roadmaps or sprint planning
2. **Stub Execution**: AutopilotRunner doesn't actually call Orchestrator/BugOrchestrator
3. **No Learning**: Recommendations don't improve based on historical outcomes
4. **No Parallel Execution**: Can only work on one goal at a time
5. **Manual Recovery**: Errors require human intervention
6. **No Self-Validation**: Can't verify its own work quality
7. **No Strategic Thinking**: Reacts to state, doesn't anticipate needs

### User Stories (v2)

1. **As the developer**, I want to say "implement this feature" and have the system plan, execute, and verify over multiple days.

2. **As the developer**, I want the system to learn which approaches work best for this codebase and improve its estimates.

3. **As the developer**, I want to run multiple features in parallel with proper resource coordination.

4. **As the developer**, I want the system to automatically retry and recover from transient failures.

5. **As the developer**, I want the system to validate its own PRDs and specs before asking for my approval.

6. **As the developer**, I want a weekly planning session that projects forward, not just daily standups that look backward.

7. **As the PM/founder**, I want the system to get my signoff before any work that impacts UX, flows, cost, or architecture - like a senior engineer who knows to check in before making big calls.

8. **As the PM/founder**, I want a Q&A process where the system presents decision points with suggested options and recommendations, waits for my approval or adjustment, then proceeds.

---

## CRITICAL REQUIREMENT: Human-in-the-Loop UX/PM Signoff

**This is a P0 requirement that must be in v2.**

The system must operate in **collaborative autonomy** mode, not black-box autonomy. Think of it like: I'm the PM/eng-manager, Chief of Staff is the senior engineer who knows to check in before making big calls.

### Signoff Triggers

The system MUST pause and get human approval before:

| Trigger | Threshold | Example |
|---------|-----------|---------|
| **UX/Flow Changes** | Any user-facing change | New screens, changed interactions, copy changes |
| **Cost** | Single action >$5 OR cumulative >$15/day | Expensive LLM calls, multiple retries |
| **Architecture Decisions** | Any structural change | New modules, changed interfaces, dependencies |
| **Scope Changes** | Deviation from approved plan | Adding/removing features, changing approach |
| **Hiccups** | Any unexpected situation | Errors, blockers, unclear requirements |

### Q&A Checkpoint Format

When a checkpoint triggers, the system should:

1. **Present the Decision Point**
   ```
   🔔 CHECKPOINT: [Trigger Type]

   Context: [What's happening and why we're asking]

   Options:
   1. [Option A] - [Tradeoffs]
   2. [Option B] - [Tradeoffs]
   3. [Option C] - [Tradeoffs]

   💡 Recommendation: Option [X] because [rationale]

   [Approve Recommended] [Choose Different] [Discuss More]
   ```

2. **Wait for Human Response** - Never proceed without explicit approval

3. **Record the Decision** - Log what was proposed, what was approved, and why

### Sync Cadence

| Sync Type | When | Purpose |
|-----------|------|---------|
| **Daily Standup** | Morning (existing v1) | Plan the day, review yesterday |
| **Pre-flight Check** | Before significant work | Confirm approach before investing time |
| **Hiccup Sync** | Any unexpected situation | Surface problems early |
| **Review Gate** | Before merging/shipping | Final approval on deliverables |

### Decision Learning

The system should learn from my approval patterns:
- Track which recommendations I accept vs adjust
- Surface patterns: "You usually prefer X over Y in these situations"
- Adapt future recommendations based on preferences
- But NEVER skip checkpoints - learning improves suggestions, not autonomy level

---

## Expert Panel Q&A Phase

### Question 1: Agent Memory Architecture

**Current state:** Daily logs in markdown + decisions in JSONL. Short-term only.

**Harrison Chase (LangChain):**
> "The key missing piece is *structured long-term memory* with semantic retrieval. LangGraph supports checkpointing and memory stores. You need:
> 1. **Episode memory**: Full execution traces of successful vs failed runs
> 2. **Semantic memory**: Embeddings of code patterns, decisions, outcomes
> 3. **Procedural memory**: Learned 'playbooks' for common situations"

**Jerry Liu (LlamaIndex):**
> "I'd add *knowledge graph memory*. Store entities (files, functions, bugs) and relationships. Then recommendations become graph traversals: 'Files that were modified together historically' or 'Bugs that share root causes'."

**Kanjun Qiu (Imbue):**
> "The memory needs to be *causal*, not just correlational. Track: Action → Outcome → Why. This enables counterfactual reasoning: 'If I had done X instead of Y, what would have happened?'"

### Question 2: Self-Improvement and Learning

**Current state:** Static recommendation weights. No learning.

**Shunyu Yao (Princeton):**
> "Implement *Reflexion*: After each goal execution, generate a verbal reflection on what worked and what didn't. Store these reflections and retrieve relevant ones before future actions. This is cheap (just text) but powerful."

**David Dohan (Anthropic):**
> "For safety, any self-modification should be *bounded and auditable*. I'd suggest:
> 1. Learn preference weights only, not code
> 2. Log all parameter updates with rationale
> 3. Human review threshold for large changes
> 4. Rollback capability if performance degrades"

**Kanjun Qiu (Imbue):**
> "Look at our work on agents that improve their own prompts. The key insight: treat the agent's instructions as a learnable parameter. Run A/B tests between prompt variants, measure success rate, update."

### Question 3: Multi-Agent Coordination

**Current state:** Single-threaded execution. One goal at a time.

**Harrison Chase (LangChain):**
> "LangGraph's latest supports parallel node execution. Model this as:
> - **Planner agent**: Creates dependency graph of goals
> - **Worker agents**: Execute independent goals in parallel
> - **Coordinator agent**: Handles conflicts, merges results
> - **Critic agent**: Validates outputs before committing"

**Jerry Liu (LlamaIndex):**
> "Be careful with parallelism in codebases. You can parallelize:
> - Independent features on separate branches
> - Tests and static analysis
> - Documentation and implementation
> You CANNOT parallelize:
> - Changes to the same file
> - Dependent PRs"

### Question 4: Error Recovery and Resilience

**Current state:** Errors trigger checkpoint pause. Manual recovery required.

**David Dohan (Anthropic):**
> "Implement *hierarchical recovery*:
> 1. **Level 1 (automatic)**: Retry with same approach (transient failures)
> 2. **Level 2 (automatic)**: Retry with alternative approach (systematic failure)
> 3. **Level 3 (assisted)**: Ask clarifying question, retry with new info
> 4. **Level 4 (escalate)**: Checkpoint for human intervention"

**Shunyu Yao (Princeton):**
> "Use *Tree-of-Thought* for recovery. When an approach fails:
> 1. Generate multiple alternative approaches
> 2. Evaluate each mentally before executing
> 3. Pick the most promising
> 4. If all fail, backtrack to last good state"

### Question 5: Self-Validation and Quality Gates

**Current state:** Human approves all specs. No self-validation.

**Kanjun Qiu (Imbue):**
> "Build *internal critics*. Before showing anything to the human:
> 1. Spec-Critic validates PRD → Spec transformation
> 2. Code-Critic validates Spec → Implementation
> 3. Test-Critic validates coverage and edge cases
> 4. Only after internal critics pass does it surface to human"

**Harrison Chase (LangChain):**
> "We call this 'agentic validation'. The key is *diverse critics*:
> - One critic optimizes for simplicity
> - One critic optimizes for correctness
> - One critic optimizes for performance
> Disagreements surface real issues."

### Question 6: Strategic Planning

**Current state:** Daily planning only. No sprint/milestone planning.

**Jerry Liu (LlamaIndex):**
> "Implement *hierarchical planning*:
> - **Vision** (months): What are we building toward?
> - **Milestones** (weeks): What are the major deliverables?
> - **Sprints** (days): What's the tactical execution?
> Each level constrains the level below."

**Shunyu Yao (Princeton):**
> "Use *backward planning*: Start from the goal state, work backward to current state. This reveals the critical path and dependencies naturally. Then forward-simulate to validate feasibility."

---

## Proposed v2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CHIEF OF STAFF v2                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         STRATEGIC LAYER (NEW)                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Vision     │  │ Milestone   │  │   Sprint    │  │  Campaign   │     │   │
│  │  │  Tracker    │  │  Planner    │  │   Planner   │  │  Executor   │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Goals     │  │ • Decompose │  │ • Daily     │  │ • Multi-day │     │   │
│  │  │ • Metrics   │  │ • Sequence  │  │ • Parallel  │  │ • Resume    │     │   │
│  │  │ • Timeline  │  │ • Resource  │  │ • Balance   │  │ • Rollback  │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         MEMORY LAYER (NEW)                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Episode    │  │  Semantic   │  │ Procedural  │  │   Causal    │     │   │
│  │  │  Memory     │  │  Memory     │  │  Memory     │  │   Memory    │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Traces    │  │ • Embeddings│  │ • Playbooks │  │ • Actions   │     │   │
│  │  │ • Outcomes  │  │ • Retrieval │  │ • Patterns  │  │ • Outcomes  │     │   │
│  │  │ • Context   │  │ • Similarity│  │ • Rules     │  │ • Reasons   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         LEARNING LAYER (NEW)                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │ Reflexion   │  │  Preference │  │   A/B       │  │  Prompt     │     │   │
│  │  │ Engine      │  │  Learner    │  │  Testing    │  │  Optimizer  │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Post-exec │  │ • Weights   │  │ • Variants  │  │ • Self-     │     │   │
│  │  │ • Insights  │  │ • Decay     │  │ • Metrics   │  │   improve   │     │   │
│  │  │ • Storage   │  │ • Bounds    │  │ • Selection │  │ • Audit     │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      COORDINATION LAYER (NEW)                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Parallel   │  │   Branch    │  │  Conflict   │  │  Resource   │     │   │
│  │  │  Executor   │  │  Manager    │  │  Resolver   │  │  Allocator  │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Workers   │  │ • Create    │  │ • Detect    │  │ • Budget    │     │   │
│  │  │ • Sync      │  │ • Merge     │  │ • Prioritize│  │ • Time      │     │   │
│  │  │ • Results   │  │ • Cleanup   │  │ • Resolve   │  │ • Balance   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                       RECOVERY LAYER (NEW)                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Auto       │  │  Tree-of-   │  │  Rollback   │  │ Escalation  │     │   │
│  │  │  Retry      │  │  Thought    │  │  Manager    │  │  Handler    │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Transient │  │ • Generate  │  │ • Git reset │  │ • Level 1-4 │     │   │
│  │  │ • Backoff   │  │ • Evaluate  │  │ • State     │  │ • Context   │     │   │
│  │  │ • Limits    │  │ • Execute   │  │ • Sessions  │  │ • Handoff   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      VALIDATION LAYER (NEW)                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Spec       │  │  Code       │  │  Test       │  │  Consensus  │     │   │
│  │  │  Critic     │  │  Critic     │  │  Critic     │  │  Builder    │     │   │
│  │  │             │  │             │  │             │  │             │     │   │
│  │  │ • Complete  │  │ • Style     │  │ • Coverage  │  │ • Diverse   │     │   │
│  │  │ • Feasible  │  │ • Security  │  │ • Edge case │  │ • Vote      │     │   │
│  │  │ • Scoped    │  │ • Pattern   │  │ • Mutation  │  │ • Approve   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      EXISTING v1 LAYER (Enhanced)                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │ State       │  │ DailyLog    │  │ Goal        │  │ Autopilot   │     │   │
│  │  │ Gatherer    │  │ Manager     │  │ Tracker     │  │ Runner      │     │   │
│  │  │             │  │             │  │             │  │ (REAL exec) │     │   │
│  │  │ • v1 impl   │  │ • v1 impl   │  │ • v1 impl   │  │ + Orch call │     │   │
│  │  │ + GitHub+   │  │ + Metrics   │  │ + Learning  │  │ + Parallel  │     │   │
│  │  │ + Embeddings│  │ + Episodes  │  │ + Predict   │  │ + Recovery  │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Expert Panel Priority Ranking

After debate, the panel prioritized extensions by **Impact × Feasibility**:

| Priority | Extension | Impact | Feasibility | Rationale |
|----------|-----------|--------|-------------|-----------|
| **P1** | Real Orchestrator Integration | 10 | 9 | Stub → real execution. Foundation for everything. |
| **P2** | Hierarchical Error Recovery | 9 | 8 | Essential for autonomous operation. |
| **P3** | Episode Memory + Reflexion | 9 | 7 | Low cost, high impact learning. |
| **P4** | Multi-Day Campaign Execution | 8 | 7 | Enables complex features without daily restarts. |
| **P5** | Internal Validation Critics | 8 | 6 | Reduces human review burden. |
| **P6** | Parallel Execution on Branches | 7 | 6 | Speed improvement, but complexity cost. |
| **P7** | Preference Learning (weights) | 7 | 8 | Simple wins, bounded impact. |
| **P8** | Semantic Memory (embeddings) | 6 | 5 | Nice-to-have, needs infrastructure. |
| **P9** | Weekly Sprint Planning | 6 | 7 | UI/UX, less technical. |
| **P10** | Prompt Self-Optimization | 5 | 4 | Risky, needs careful bounds. |

---

## Implementation Phases

### Phase 7: Real Execution (P1)
**Goal:** AutopilotRunner calls Orchestrator/BugOrchestrator for real work.

```python
class AutopilotRunner:
    def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
        if goal.linked_feature:
            # Real execution!
            result = self.orchestrator.run_issue(
                feature_id=goal.linked_feature,
                issue_number=goal.linked_issue,
            )
            return GoalExecutionResult(
                success=result.status == "success",
                cost_usd=result.cost_usd,
                duration_seconds=result.duration_seconds,
            )
        elif goal.linked_bug:
            result = self.bug_orchestrator.fix(goal.linked_bug)
            return GoalExecutionResult(...)
```

### Phase 8: Hierarchical Recovery (P2)
**Goal:** Automatic retry and recovery without human intervention.

```python
class RecoveryManager:
    LEVELS = [
        (RetryStrategy.SAME, max_attempts=3),      # Level 1: Transient
        (RetryStrategy.ALTERNATIVE, max_attempts=2),  # Level 2: Systematic
        (RetryStrategy.CLARIFY, max_attempts=1),   # Level 3: Ask question
        (RetryStrategy.ESCALATE, max_attempts=1),  # Level 4: Human
    ]

    async def execute_with_recovery(self, goal, action):
        for level, strategy, max_attempts in self.LEVELS:
            for attempt in range(max_attempts):
                result = await self._try_action(action, strategy)
                if result.success:
                    return result
                if not result.retryable:
                    break
            # Progress to next level
        return self._escalate_to_human(goal, result)
```

### Phase 9: Episode Memory + Reflexion (P3)
**Goal:** Learn from execution history.

```python
@dataclass
class Episode:
    goal: DailyGoal
    actions: list[Action]
    outcome: Outcome
    reflection: str  # LLM-generated insight
    timestamp: datetime

class ReflexionEngine:
    def reflect(self, episode: Episode) -> str:
        """Generate reflection on what worked/failed."""
        prompt = f"""
        Goal: {episode.goal.description}
        Actions taken: {episode.actions}
        Outcome: {episode.outcome}

        Reflect on:
        1. What worked well?
        2. What could have been done differently?
        3. Key insight for similar future goals?
        """
        return self.llm.complete(prompt)

    def retrieve_relevant(self, goal: DailyGoal, k=3) -> list[Episode]:
        """Find similar past episodes for context."""
        # Semantic search over episode descriptions
        return self.episode_store.search(goal.description, k=k)
```

### Phase 10: Multi-Day Campaigns (P4)
**Goal:** Plan and execute work spanning multiple days.

```python
@dataclass
class Campaign:
    campaign_id: str
    name: str
    goal: str
    milestones: list[Milestone]
    current_milestone_index: int
    started_at: datetime
    deadline: Optional[datetime]
    budget_usd: float
    spent_usd: float
    state: CampaignState

class CampaignExecutor:
    def plan(self, goal: str, deadline: Optional[datetime]) -> Campaign:
        """Generate multi-day plan using backward planning."""
        # 1. Define end state
        # 2. Identify major milestones
        # 3. Decompose into daily goals
        # 4. Sequence with dependencies

    def execute_day(self, campaign: Campaign) -> DayResult:
        """Execute one day of campaign work."""
        today_goals = self._get_today_goals(campaign)
        for goal in today_goals:
            result = self.autopilot.execute(goal)
            campaign.spent_usd += result.cost_usd

    def resume(self, campaign_id: str) -> Campaign:
        """Resume campaign from last checkpoint."""
```

### Phase 11: Internal Validation Critics (P5)
**Goal:** Self-validate before surfacing to human.

```python
class ValidationLayer:
    critics = [
        SpecCritic(focus="completeness"),
        SpecCritic(focus="feasibility"),
        CodeCritic(focus="style"),
        CodeCritic(focus="security"),
        TestCritic(focus="coverage"),
    ]

    def validate(self, artifact: Artifact) -> ValidationResult:
        """Run all critics and build consensus."""
        scores = []
        for critic in self.critics:
            score = critic.evaluate(artifact)
            scores.append(score)

        # Require majority approval
        if sum(s.approved for s in scores) >= len(self.critics) / 2:
            return ValidationResult(approved=True, scores=scores)
        else:
            # Surface disagreements
            issues = [s.issues for s in scores if not s.approved]
            return ValidationResult(approved=False, issues=issues)
```

---

## CLI Extensions (v2)

```bash
# Multi-day campaigns
swarm-attack cos campaign create "Implement auth system" --deadline 2025-01-15
swarm-attack cos campaign status [CAMPAIGN_ID]
swarm-attack cos campaign resume [CAMPAIGN_ID]
swarm-attack cos campaign list

# Weekly planning
swarm-attack cos weekly               # Weekly planning session
swarm-attack cos weekly review        # Review last week's metrics

# Learning and memory
swarm-attack cos memory search "authentication patterns"
swarm-attack cos memory episodes --goal-type feature
swarm-attack cos reflect --last-week  # Generate weekly reflection

# Validation
swarm-attack cos validate spec chief-of-staff-v2
swarm-attack cos validate code swarm_attack/chief_of_staff/

# Recovery
swarm-attack cos recover --session SESSION_ID
swarm-attack cos recover --auto       # Automatic recovery mode
```

---

## Success Metrics (v2)

| Metric | v1 Baseline | v2 Target |
|--------|-------------|-----------|
| Multi-day goal completion | N/A | >80% |
| Automatic error recovery | 0% | >70% |
| Human review reduction | 100% manual | <30% manual |
| Parallel workstream support | 1 | 3 |
| Learning improvement | None | +10% goal completion per month |
| Campaign completion rate | N/A | >75% |

---

## Risks and Mitigations (v2)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Runaway self-modification | High | Bounded learning (weights only), audit logs, rollback |
| Parallel conflict corruption | High | Branch isolation, conflict detection, human review for merges |
| Error recovery loops | Medium | Maximum recursion depth, exponential backoff, escalation timeout |
| Memory bloat | Medium | Periodic pruning, relevance decay, summarization |
| Learning wrong patterns | Medium | Diverse critics, human feedback loop, A/B validation |

---

## Open Questions (v2)

1. **Embedding infrastructure**: Use local embeddings (fast, private) or API (better quality)?
2. **Campaign scope limits**: What's the maximum campaign duration before requiring re-planning?
3. **Parallel worker count**: How many parallel branches can we safely manage?
4. **Human-in-the-loop frequency**: How often should the system check in during campaigns?
5. **Cross-repo learning**: Should learnings transfer between repositories?

---

## Timeline Estimate

| Phase | Deliverable | Complexity | Dependencies |
|-------|-------------|------------|--------------|
| 7 | Real Execution | Medium | v1 complete |
| 8 | Hierarchical Recovery | Medium | Phase 7 |
| 9 | Episode Memory + Reflexion | Large | Phase 7 |
| 10 | Multi-Day Campaigns | Large | Phases 7, 8 |
| 11 | Internal Validation | Medium | Phase 7 |

**Recommended MVP (Phases 7-8-9):** Enables real autonomous operation with learning.

---

*PRD Author: Expert Panel (LangChain, LlamaIndex, Imbue, Anthropic, Princeton)*
*Created: 2025-12-18*
*Status: Draft - Ready for Spec Generation*
