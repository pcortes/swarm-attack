# Implementation Prompt: Backlog Discovery Feature

## Mission

You are a team of expert software engineers implementing the **Backlog Discovery** feature for Swarm Attack, an autonomous multi-agent development system. Your goal is to build a production-ready opportunity detection system that discovers actionable work items from test failures, stalled work, and code quality issues.

---

## Context: What You're Building

**Backlog Discovery** answers: *"What should I be working on that I'm not?"*

It autonomously:
1. Analyzes test failures from pytest output and EpisodeStore
2. Detects stalled features and interrupted sessions
3. Identifies code quality issues (complexity, coverage gaps)
4. Uses 3-agent debate to prioritize when multiple opportunities exist
5. Presents findings to human for approval (never auto-commits to backlog)

---

## Codebase Context

### Repository Structure
```
swarm-attack/
├── swarm_attack/
│   ├── agents/
│   │   ├── base.py              # BaseAgent class - ALL agents inherit from this
│   │   ├── spec_author.py       # Pattern for champion agent
│   │   ├── spec_critic.py       # Pattern for critic agent (uses Codex)
│   │   └── spec_moderator.py    # Pattern for moderator (disposition tracking)
│   │
│   ├── chief_of_staff/
│   │   ├── state_gatherer.py    # Aggregates system state - REUSE THIS
│   │   ├── episodes.py          # EpisodeStore with find_similar()
│   │   ├── checkpoints.py       # Checkpoint patterns
│   │   ├── config.py            # Configuration dataclasses
│   │   └── backlog_discovery/   # NEW - You will create this
│   │       ├── __init__.py
│   │       ├── candidates.py    # Opportunity, Evidence, ActionabilityScore
│   │       ├── store.py         # BacklogStore persistence
│   │       ├── discovery_agent.py
│   │       ├── debate.py
│   │       └── orchestrator.py
│   │
│   ├── cli/
│   │   └── chief_of_staff.py    # Add cos discover, cos backlog commands
│   │
│   ├── models.py                # Core data models (FeaturePhase, TaskStage, etc.)
│   ├── config.py                # SwarmConfig
│   └── state_store.py           # Atomic persistence patterns
│
├── .swarm/
│   ├── backlog/                 # NEW - You will create this structure
│   │   ├── candidates.json
│   │   ├── accepted.json
│   │   └── sessions/
│   │       └── <session-id>.json
│   │
│   └── chief-of-staff/
│       └── episodes/
│           └── episodes.jsonl   # Existing episode data
│
├── specs/
│   └── backlog-discovery/
│       └── spec-draft.md        # Full specification
│
└── tests/
    └── generated/
        └── backlog-discovery/   # NEW - Your tests go here
```

### Key Patterns to Follow

#### 1. BaseAgent Pattern (from `swarm_attack/agents/base.py`)
```python
from swarm_attack.agents.base import BaseAgent, AgentResult

class YourAgent(BaseAgent):
    AGENT_NAME = "your-agent-name"

    async def run(self, context: dict) -> AgentResult:
        # Your implementation
        return AgentResult(
            success=True,
            output=your_data,
            errors=[],
            cost_usd=0.0,
        )
```

#### 2. Dataclass Serialization Pattern (from `swarm_attack/models.py`)
```python
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class YourModel:
    id: str
    name: str
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "YourModel":
        return cls(**data)
```

#### 3. Atomic Persistence Pattern (from `swarm_attack/state_store.py`)
```python
def _save_atomic(self, data: dict, file_path: Path) -> None:
    temp_file = file_path.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=2)
    temp_file.rename(file_path)  # Atomic rename
```

#### 4. Similarity Search Pattern (from `swarm_attack/chief_of_staff/episodes.py`)
```python
def find_similar(self, content: str, k: int = 5) -> list[Episode]:
    content_words = set(content.lower().split())

    scored = []
    for item in self.items:
        item_words = set(item.content.lower().split())
        intersection = len(content_words & item_words)
        union = len(content_words | item_words)
        score = intersection / union if union > 0 else 0
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:k]]
```

#### 5. Multi-Strategy Parser Pattern (from `swarm_attack/agents/spec_moderator.py`)
```python
def _parse_response(self, response: str) -> dict:
    """Try multiple parsing strategies for LLM output reliability."""
    strategies = [
        self._parse_with_delimiters,
        self._parse_json_blocks,
        self._parse_by_headers,
    ]

    for strategy in strategies:
        try:
            result = strategy(response)
            if result:
                return result
        except Exception:
            continue

    raise ValueError("All parsing strategies failed")
```

---

## Implementation Tasks

### Phase 1: MVP - Test Failure Analyzer (4 Issues)

#### Issue 1.1: Create Opportunity and Evidence Dataclasses
**File:** `swarm_attack/chief_of_staff/backlog_discovery/candidates.py`

```python
# Required classes:
class OpportunityType(Enum):
    TEST_FAILURE = "test_failure"
    STALLED_WORK = "stalled_work"
    CODE_QUALITY = "code_quality"
    COVERAGE_GAP = "coverage_gap"
    COMPLEXITY = "complexity"

class OpportunityStatus(Enum):
    DISCOVERED = "discovered"
    DEBATING = "debating"
    ACTIONABLE = "actionable"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"

@dataclass
class Evidence:
    source: str              # "test_output", "git_log", "static_analysis"
    content: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: Optional[str] = None

@dataclass
class ActionabilityScore:
    clarity: float           # 0-1
    evidence: float          # 0-1
    effort: str             # "small", "medium", "large"
    reversibility: str       # "full", "partial", "none"

    @property
    def overall(self) -> float:
        return (self.clarity * 0.4) + (self.evidence * 0.4) + (
            0.2 if self.effort == "small" else 0.1 if self.effort == "medium" else 0.0
        )

@dataclass
class Opportunity:
    opportunity_id: str
    opportunity_type: OpportunityType
    status: OpportunityStatus
    title: str
    description: str
    evidence: list[Evidence]
    actionability: Optional[ActionabilityScore] = None
    suggested_fix: Optional[str] = None
    affected_files: list[str] = field(default_factory=list)
    # ... debate tracking fields
    # ... metadata fields
```

**Tests Required:**
- `test_opportunity_serialization_roundtrip`
- `test_actionability_score_calculation`
- `test_evidence_with_file_path`

---

#### Issue 1.2: Implement BacklogStore Persistence
**File:** `swarm_attack/chief_of_staff/backlog_discovery/store.py`

```python
class BacklogStore:
    def __init__(self, base_path: Path):
        self.base_path = base_path / "backlog"
        self.candidates_file = self.base_path / "candidates.json"

    def save_opportunity(self, opportunity: Opportunity) -> None: ...
    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]: ...
    def get_opportunities_by_status(self, status: OpportunityStatus) -> list[Opportunity]: ...
    def get_actionable(self) -> list[Opportunity]: ...
    def mark_accepted(self, opportunity_id: str, linked_issue: Optional[int] = None) -> None: ...
    def mark_rejected(self, opportunity_id: str) -> None: ...
    def mark_deferred(self, opportunity_id: str) -> None: ...
    def find_similar(self, opportunity: Opportunity, k: int = 5) -> list[Opportunity]: ...
```

**Key Requirements:**
- Atomic writes (temp file + rename)
- Similarity search using Jaccard index
- Session tracking in separate files

**Tests Required:**
- `test_save_and_retrieve_opportunity`
- `test_get_actionable_opportunities`
- `test_mark_accepted_updates_status`
- `test_find_similar_opportunities`

---

#### Issue 1.3: Implement TestFailureDiscoveryAgent
**File:** `swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py`

```python
class TestFailureDiscoveryAgent(BaseAgent):
    """Discovers opportunities from test failures.

    MVP: Does NOT use LLM for discovery (cost control).
    Optional: Uses LLM only for fix suggestions.
    """

    AGENT_NAME = "test-failure-discovery"

    async def run(self, context: dict) -> AgentResult:
        # 1. Gather state via StateGatherer (already exists)
        state = self.state_gatherer.gather()

        # 2. Extract failures from EpisodeStore
        failed_episodes = [e for e in episodes if not e.success and "test" in e.goal_id.lower()]

        # 3. Parse pytest failures from state
        test_failures = self._extract_test_failures(state)

        # 4. Merge and deduplicate
        all_failures = self._merge_failures(failed_episodes, test_failures)

        # 5. Convert to Opportunity objects
        # 6. Calculate actionability (rule-based, no LLM)
        # 7. Optional: Generate fix suggestions (LLM)
        # 8. Save to BacklogStore
```

**Key Requirements:**
- Reuse `StateGatherer` - do not rebuild
- Rule-based actionability scoring (no LLM cost)
- Skip duplicates of recently rejected opportunities
- Optional LLM for fix suggestions only when `--deep` flag

**Tests Required:**
- `test_discovers_opportunities_from_failures`
- `test_merges_episodes_and_pytest_failures`
- `test_skips_duplicates_of_rejected`
- `test_actionability_scoring_rules`

---

#### Issue 1.4: Add CLI Commands
**File:** `swarm_attack/cli/chief_of_staff.py`

```python
@cos_group.command("discover")
@click.option("--deep", is_flag=True, help="Include LLM fix suggestions")
@click.option("--type", type=click.Choice(["test", "stalled", "quality", "all"]), default="test")
@click.option("--max", type=int, default=10)
def discover(deep: bool, opp_type: str, max_candidates: int):
    """Discover opportunities for improvement."""
    # 1. Initialize agents
    # 2. Run discovery
    # 3. Display table with Rich
    # 4. Interactive prompt: [1-N] Review  [a] Accept all  [Enter] Skip

@cos_group.command("backlog")
@click.option("--status", type=click.Choice(["actionable", "accepted", "all"]), default="actionable")
def show_backlog(status: str):
    """Show discovered opportunities."""
```

**Integration Point:**
```python
@cos_group.command("standup")
@click.option("--deep", is_flag=True)
def standup(deep: bool):
    # ... existing standup ...
    if deep:
        ctx.invoke(discover, deep=True, opp_type="test", max_candidates=5)
```

---

### Phase 2: Stalled Work + Code Quality (4 Issues)

#### Issue 5: StalledWorkDiscoveryAgent
- Find features stuck in same phase >24 hours
- Detect interrupted sessions
- Find goals with repeated failures

#### Issue 6: CodeQualityDiscoveryAgent
- Integrate `radon` for complexity analysis
- Integrate `coverage.py` for coverage gaps
- Detect oversized files (>500 lines)
- **Static analysis only - no LLM cost**

#### Issue 7: DiscoveryOrchestrator
- Runs all enabled discovery agents
- Merges and deduplicates results
- Triggers debate if >5 candidates

#### Issue 8: CLI Updates
- `--type all` runs all agents
- Combined results display
- Cost summary

---

### Phase 3: Debate Prioritization (4 Issues)

#### Issue 9: Debate Data Models
```python
@dataclass
class DebateRound:
    round_number: int
    champion_argument: str
    champion_rankings: list[str]
    critic_argument: str
    critic_concerns: dict[str, list[str]]
    moderator_decision: str
    moderator_rankings: list[str]
    continue_debate: bool

@dataclass
class DebateSession:
    session_id: str
    opportunities: list[str]
    rounds: list[DebateRound]
    max_rounds: int = 3
    final_rankings: list[str]
    consensus_reached: bool
    cost_usd: float
```

#### Issue 10: Debate Agents
Clone patterns from existing agents:

| Agent | Clone From | Model |
|-------|------------|-------|
| BacklogChampionAgent | `spec_author.py` | Claude |
| BacklogCriticAgent | `spec_critic.py` | **Codex** (independent) |
| BacklogModeratorAgent | `spec_moderator.py` | Claude |

**Critical:** Use Codex for critic to prevent self-review bias.

#### Issue 11: BacklogDebateOrchestrator
```python
class BacklogDebateOrchestrator:
    async def debate(self, opportunities: list[Opportunity]) -> DebateSession:
        for round_num in range(1, self.max_rounds + 1):
            # Check budget
            if session.cost_usd >= self.budget_usd:
                session.stalemate = True
                break

            # Phase 1: Champion argues
            champion_result = await self.champion.run(...)

            # Phase 2: Critic responds
            critic_result = await self.critic.run(...)

            # Phase 3: Moderator reconciles
            moderator_result = await self.moderator.run(...)

            if moderator_result.output["consensus_reached"]:
                break
```

#### Issue 12: Integration
- Auto-trigger debate when >5 opportunities found
- Update opportunity scores from debate results
- Store debate sessions for learning

---

## Quality Standards

### Code Style
- Follow existing codebase patterns exactly
- Use dataclasses with `to_dict()` / `from_dict()`
- Type hints on all functions
- Docstrings with Args/Returns

### Testing
- TDD: Write tests before implementation
- Use pytest fixtures
- Mock external dependencies (LLM clients)
- Test serialization roundtrips
- Test edge cases (empty inputs, duplicates)

### Cost Control
- Phase 1 MVP: ~$0.75 per session (no LLM for discovery)
- With suggestions: ~$1.50
- With debate: ~$3.00 max
- Always check budget before LLM calls

### Error Handling
- Graceful degradation (if radon unavailable, skip complexity)
- Return empty lists, not exceptions
- Log errors but continue

---

## File Checklist

Create these files in order:

```
[ ] swarm_attack/chief_of_staff/backlog_discovery/__init__.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/candidates.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/store.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py
[ ] tests/generated/backlog-discovery/test_candidates.py
[ ] tests/generated/backlog-discovery/test_store.py
[ ] tests/generated/backlog-discovery/test_discovery_agent.py
[ ] tests/generated/backlog-discovery/test_debate.py
[ ] .claude/skills/backlog-champion/SKILL.md
[ ] .claude/skills/backlog-critic/SKILL.md
[ ] .claude/skills/backlog-moderator/SKILL.md
```

---

## Success Criteria

### Phase 1 Complete When:
- [ ] `cos discover` runs and finds test failures
- [ ] Opportunities are persisted to `.swarm/backlog/`
- [ ] Similarity detection prevents duplicates
- [ ] Actionability scores are calculated (no LLM)
- [ ] Interactive review flow works
- [ ] All tests pass

### Phase 2 Complete When:
- [ ] Stalled work detected from state
- [ ] Code quality issues found (if tools available)
- [ ] `--type all` runs all discovery agents
- [ ] Results are merged and deduplicated

### Phase 3 Complete When:
- [ ] 3-agent debate runs when >5 candidates
- [ ] Debate converges or hits max rounds
- [ ] Rankings are applied to opportunities
- [ ] Cost stays under $3 per session

---

## Reference Files

Read these files to understand existing patterns:

1. **Agent Pattern:** `swarm_attack/agents/base.py`, `swarm_attack/agents/spec_moderator.py`
2. **Data Models:** `swarm_attack/models.py`
3. **State Gathering:** `swarm_attack/chief_of_staff/state_gatherer.py`
4. **Episode Store:** `swarm_attack/chief_of_staff/episodes.py`
5. **Persistence:** `swarm_attack/state_store.py`
6. **CLI:** `swarm_attack/cli/chief_of_staff.py`
7. **Full Spec:** `specs/backlog-discovery/spec-draft.md`

---

## Begin Implementation

Start with Issue 1.1: Create the data models in `candidates.py`. Write tests first, then implement. Use the patterns from `swarm_attack/models.py` for serialization.

When you complete each issue, run tests to verify, then proceed to the next issue in dependency order.

Good luck, team!
