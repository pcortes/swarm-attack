# Phase 3: McKinsey Partner Debate System - Implementation Prompt

You are a team of expert software engineers implementing the debate prioritization system for Backlog Discovery in Swarm Attack.

## Context

**Phase 1-2 are COMPLETE** (128 tests passing):
- `candidates.py` - Opportunity, Evidence, ActionabilityScore models
- `store.py` - BacklogStore with persistence, similarity search
- `discovery_agent.py` - TestFailureDiscoveryAgent
- `stalled_work_agent.py` - StalledWorkDiscoveryAgent
- `feature_opportunity_agent.py` - FeatureOpportunityAgent (McKinsey ROI)
- `code_quality_agent.py` - CodeQualityDiscoveryAgent
- `orchestrator.py` - DiscoveryOrchestrator (runs agents, merges, deduplicates)

**CLI commands working:**
- `cos discover --type test|stalled|quality|all`
- `cos discover --no-debate`
- `cos backlog --status actionable|accepted|all`

## Your Task: Implement Phase 3 (4 Issues)

When >5 opportunities are discovered, run a 3-round McKinsey Partner debate to prioritize them.

---

## Issue 9: Debate Data Models

**File:** `swarm_attack/chief_of_staff/backlog_discovery/debate.py`

```python
"""Debate data models for McKinsey Partner prioritization system."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class Disposition(Enum):
    """Moderator disposition for an opportunity."""
    PRIORITIZE = "prioritize"      # Strong cross-partner support
    INVESTIGATE = "investigate"    # Partners disagree, need more data
    DEFER = "defer"                # Low priority across partners
    REJECT = "reject"              # Significant concerns from multiple partners


@dataclass
class DebateRound:
    """One round of the 3-agent debate."""
    round_number: int

    # Champion (Strategy Partner) output
    champion_argument: str
    champion_rankings: list[str]           # opportunity_ids in priority order
    champion_cost_usd: float = 0.0

    # Critic (Tech Partner) output
    critic_concerns: dict[str, list[str]]  # opportunity_id -> list of concerns
    critic_counter_rankings: list[str]     # opportunity_ids by feasibility
    critic_cost_usd: float = 0.0

    # Moderator (Managing Director) output
    moderator_dispositions: dict[str, Disposition]  # opportunity_id -> disposition
    moderator_final_rankings: list[str]
    moderator_cost_usd: float = 0.0
    continue_debate: bool = True
    consensus_reached: bool = False

    @property
    def round_cost_usd(self) -> float:
        return self.champion_cost_usd + self.critic_cost_usd + self.moderator_cost_usd

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "champion_argument": self.champion_argument,
            "champion_rankings": self.champion_rankings,
            "champion_cost_usd": self.champion_cost_usd,
            "critic_concerns": self.critic_concerns,
            "critic_counter_rankings": self.critic_counter_rankings,
            "critic_cost_usd": self.critic_cost_usd,
            "moderator_dispositions": {k: v.value for k, v in self.moderator_dispositions.items()},
            "moderator_final_rankings": self.moderator_final_rankings,
            "moderator_cost_usd": self.moderator_cost_usd,
            "continue_debate": self.continue_debate,
            "consensus_reached": self.consensus_reached,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DebateRound":
        return cls(
            round_number=data["round_number"],
            champion_argument=data["champion_argument"],
            champion_rankings=data["champion_rankings"],
            champion_cost_usd=data.get("champion_cost_usd", 0.0),
            critic_concerns=data["critic_concerns"],
            critic_counter_rankings=data["critic_counter_rankings"],
            critic_cost_usd=data.get("critic_cost_usd", 0.0),
            moderator_dispositions={
                k: Disposition(v) for k, v in data.get("moderator_dispositions", {}).items()
            },
            moderator_final_rankings=data["moderator_final_rankings"],
            moderator_cost_usd=data.get("moderator_cost_usd", 0.0),
            continue_debate=data.get("continue_debate", True),
            consensus_reached=data.get("consensus_reached", False),
        )


@dataclass
class DebateSession:
    """A complete debate session."""
    session_id: str
    started_at: str
    completed_at: Optional[str] = None

    # Input
    opportunity_ids: list[str] = field(default_factory=list)

    # Configuration
    max_rounds: int = 3
    budget_usd: float = 2.50

    # Rounds
    rounds: list[DebateRound] = field(default_factory=list)

    # Outcome
    final_rankings: list[str] = field(default_factory=list)
    consensus_reached: bool = False
    stalemate: bool = False

    @property
    def total_cost_usd(self) -> float:
        return sum(r.round_cost_usd for r in self.rounds)

    @property
    def rounds_used(self) -> int:
        return len(self.rounds)

    def add_round(self, round: DebateRound) -> None:
        self.rounds.append(round)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "opportunity_ids": self.opportunity_ids,
            "max_rounds": self.max_rounds,
            "budget_usd": self.budget_usd,
            "rounds": [r.to_dict() for r in self.rounds],
            "final_rankings": self.final_rankings,
            "consensus_reached": self.consensus_reached,
            "stalemate": self.stalemate,
            "total_cost_usd": self.total_cost_usd,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DebateSession":
        session = cls(
            session_id=data["session_id"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            opportunity_ids=data.get("opportunity_ids", []),
            max_rounds=data.get("max_rounds", 3),
            budget_usd=data.get("budget_usd", 2.50),
            final_rankings=data.get("final_rankings", []),
            consensus_reached=data.get("consensus_reached", False),
            stalemate=data.get("stalemate", False),
        )
        session.rounds = [DebateRound.from_dict(r) for r in data.get("rounds", [])]
        return session


@dataclass
class DebateResult:
    """Result of running a debate."""
    session: DebateSession
    ranked_opportunities: list  # list[Opportunity] with priority_rank set
    cost_usd: float
    rounds_used: int
```

**Tests Required:** `tests/generated/backlog-discovery/test_debate.py`
```python
class TestDebateRound:
    def test_round_cost_calculation(self):
        """Round cost is sum of all agent costs."""

    def test_serialization_roundtrip(self):
        """DebateRound serializes and deserializes correctly."""

class TestDebateSession:
    def test_total_cost_calculation(self):
        """Total cost is sum of all round costs."""

    def test_add_round(self):
        """add_round appends to rounds list."""

    def test_serialization_roundtrip(self):
        """DebateSession serializes and deserializes correctly."""
```

---

## Issue 10: Debate Agents (McKinsey Partners)

**File:** `swarm_attack/chief_of_staff/backlog_discovery/debate_agents.py`

### Agent 1: BacklogChampionAgent (Strategy Partner)

Champions opportunities from product/user/business perspective.

```python
class BacklogChampionAgent(BaseAgent):
    """Champions opportunities from product perspective.

    Evaluates:
    - User desirability (who wants this? how badly?)
    - Market timing (is there a window?)
    - RICE score (Reach, Impact, Confidence, Effort)

    Output markers for parsing:
    <<<CHAMPION_ARGUMENT_START>>>
    <<<CHAMPION_ARGUMENT_END>>>

    <<<CHAMPION_RANKINGS_START>>>
    ["opp-1", "opp-2", ...]
    <<<CHAMPION_RANKINGS_END>>>
    """

    name: str = "backlog-champion"

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                round_number: int
                prior_critic_concerns: Optional[dict]

        Returns:
            AgentResult with output:
                champion_argument: str
                champion_rankings: list[str]
        """
```

### Agent 2: BacklogCriticAgent (Tech Partner)

Critiques from engineering/feasibility perspective. **USES CODEX** for independence.

```python
class BacklogCriticAgent(BaseAgent):
    """Critiques opportunities from engineering perspective.

    IMPORTANT: Uses Codex (not Claude) for independent validation.
    This prevents self-review bias.

    Evaluates:
    - Technical feasibility
    - Risk assessment
    - Effort estimation (S/M/L/XL)
    - Dependency analysis
    - Build vs Buy vs Partner

    Output markers:
    <<<CRITIC_CONCERNS_START>>>
    {
      "opp-1": ["concern 1", "concern 2"],
      "opp-2": ["concern 1"]
    }
    <<<CRITIC_CONCERNS_END>>>

    <<<CRITIC_RANKINGS_START>>>
    ["opp-2", "opp-1", ...]  // By feasibility
    <<<CRITIC_RANKINGS_END>>>
    """

    name: str = "backlog-critic"
    MODEL: str = "codex"  # IMPORTANT: Use Codex for independence

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                champion_rankings: list[str]
                champion_argument: str

        Returns:
            AgentResult with output:
                concerns: dict[str, list[str]]
                counter_rankings: list[str]
        """
```

### Agent 3: BacklogModeratorAgent (Managing Director)

Synthesizes partner views and makes final decision.

```python
class BacklogModeratorAgent(BaseAgent):
    """Synthesizes all partner views and makes final prioritization.

    For each opportunity, assigns disposition:
    - PRIORITIZE: Strong cross-partner support
    - INVESTIGATE: Partners disagree, need more data
    - DEFER: Low priority across partners
    - REJECT: Significant concerns from multiple partners

    Output markers:
    <<<DISPOSITIONS_START>>>
    {
      "opp-1": "prioritize",
      "opp-2": "investigate",
      "opp-3": "defer"
    }
    <<<DISPOSITIONS_END>>>

    <<<FINAL_RANKINGS_START>>>
    ["opp-1", "opp-2", "opp-3"]
    <<<FINAL_RANKINGS_END>>>

    <<<DEBATE_STATUS_START>>>
    {
      "continue_debate": false,
      "consensus_reached": true
    }
    <<<DEBATE_STATUS_END>>>
    """

    name: str = "backlog-moderator"

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                champion_rankings: list[str]
                champion_argument: str
                critic_concerns: dict[str, list[str]]
                critic_counter_rankings: list[str]
                round_number: int

        Returns:
            AgentResult with output:
                dispositions: dict[str, Disposition]
                final_rankings: list[str]
                continue_debate: bool
                consensus_reached: bool
        """
```

**Tests Required:** `tests/generated/backlog-discovery/test_debate_agents.py`
```python
class TestBacklogChampionAgent:
    def test_evaluates_user_desirability(self, mock_claude):
        """Champion scores user desirability for each opportunity."""

    def test_produces_rankings(self, mock_claude):
        """Champion produces ordered rankings."""

    def test_considers_prior_concerns(self, mock_claude):
        """Champion addresses prior critic concerns in round 2+."""

class TestBacklogCriticAgent:
    def test_uses_codex_not_claude(self, mock_codex):
        """Critic uses Codex for independence."""

    def test_identifies_technical_concerns(self, mock_codex):
        """Critic flags feasibility issues."""

    def test_produces_counter_rankings(self, mock_codex):
        """Critic produces feasibility-based rankings."""

class TestBacklogModeratorAgent:
    def test_synthesizes_champion_and_critic(self, mock_claude):
        """Moderator combines both perspectives."""

    def test_assigns_dispositions(self, mock_claude):
        """Moderator assigns PRIORITIZE/INVESTIGATE/DEFER/REJECT."""

    def test_determines_consensus(self, mock_claude):
        """Moderator sets consensus_reached correctly."""

    def test_decides_continue_debate(self, mock_claude):
        """Moderator decides if more rounds needed."""
```

---

## Issue 11: BacklogDebateOrchestrator

**File:** `swarm_attack/chief_of_staff/backlog_discovery/debate_orchestrator.py`

```python
class BacklogDebateOrchestrator:
    """Runs 3-agent debate to prioritize opportunities.

    Flow per round:
    1. Champion argues for priorities (Claude)
    2. Critic challenges with concerns (Codex)
    3. Moderator synthesizes and decides (Claude)

    Stops when:
    - consensus_reached = True
    - max_rounds hit (default 3)
    - budget exceeded (default $2.50)
    """

    def __init__(
        self,
        champion: BacklogChampionAgent,
        critic: BacklogCriticAgent,
        moderator: BacklogModeratorAgent,
        store: BacklogStore,
        max_rounds: int = 3,
        budget_usd: float = 2.50,
    ):
        pass

    def debate(self, opportunities: list[Opportunity]) -> DebateResult:
        """Run the debate and return prioritized opportunities.

        Args:
            opportunities: Opportunities to prioritize (>5 typically)

        Returns:
            DebateResult with ranked opportunities
        """
        pass

    def _apply_rankings(
        self,
        opportunities: list[Opportunity],
        rankings: list[str],
        session_id: str,
    ) -> list[Opportunity]:
        """Set priority_rank and debate_session_id on opportunities."""
        pass

    def _save_session(self, session: DebateSession) -> None:
        """Save session to .swarm/backlog/debates/{session_id}.json"""
        pass
```

**Tests Required:** `tests/generated/backlog-discovery/test_debate_orchestrator.py`
```python
def test_runs_three_phase_debate(mock_agents):
    """Each round calls champion, critic, moderator in order."""

def test_stops_on_consensus(mock_agents):
    """Debate ends when moderator sets consensus_reached=True."""

def test_stops_at_max_rounds(mock_agents):
    """Debate ends after max_rounds even without consensus."""

def test_stops_when_budget_exceeded(mock_agents):
    """Debate ends when approaching budget limit."""

def test_applies_rankings_to_opportunities(mock_agents):
    """Opportunities get priority_rank from final rankings."""

def test_saves_session_to_store(mock_agents, tmp_path):
    """Debate session is persisted to .swarm/backlog/debates/."""

def test_handles_stalemate(mock_agents):
    """Budget exceeded sets stalemate=True."""

def test_passes_prior_concerns_to_champion(mock_agents):
    """Round 2+ champion receives prior critic concerns."""
```

---

## Issue 12: Integration with DiscoveryOrchestrator

**Updates to:** `swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py`

```python
# Add to DiscoveryOrchestrator.__init__:
def __init__(
    self,
    ...
    debate_orchestrator: Optional[BacklogDebateOrchestrator] = None,
):
    self.debate_orchestrator = debate_orchestrator

# Implement _run_debate:
def _run_debate(self, opportunities: list[Opportunity]) -> DebateResult:
    """Run 3-agent debate when threshold exceeded."""
    if not self.debate_orchestrator:
        self.debate_orchestrator = self._create_debate_orchestrator()
    return self.debate_orchestrator.debate(opportunities)
```

**Update CLI** `swarm_attack/cli/chief_of_staff.py`:
```python
# After displaying opportunities table, if debate was triggered:
if result.debate_triggered and result.debate_session_id:
    console.print(f"\n[bold yellow]Debate Prioritization[/bold yellow]")
    console.print(f"  Session: {result.debate_session_id}")
    console.print(f"  Rounds: {result.rounds_used}/{result.max_rounds}")
    console.print(f"  Consensus: {'Yes' if result.consensus_reached else 'No'}")
    if result.stalemate:
        console.print(f"  [yellow]Stalemate: Budget exceeded[/yellow]")
    console.print(f"  Debate cost: ${result.debate_cost_usd:.2f}")
```

**Tests Required:**
```python
def test_orchestrator_triggers_debate(mock_orchestrator):
    """Debate triggered when >5 opportunities discovered."""

def test_orchestrator_skips_debate_when_disabled(mock_orchestrator):
    """--no-debate skips debate even with >5 opportunities."""

def test_orchestrator_returns_debate_metadata(mock_orchestrator):
    """DiscoveryResult includes debate session info."""
```

---

## SKILL.md Files to Create

```bash
mkdir -p .claude/skills/backlog-champion
mkdir -p .claude/skills/backlog-critic
mkdir -p .claude/skills/backlog-moderator
```

### `.claude/skills/backlog-champion/SKILL.md`
```markdown
# Backlog Champion (Strategy Partner)

You are a Strategy Partner at a top consulting firm. Your role is to champion opportunities from a product and business perspective.

## Your Evaluation Framework

### 1. User Desirability
- Who wants this feature/fix?
- How badly do they want it? (nice-to-have vs blocking)
- How many users are affected?

### 2. Market Timing
- Is there a competitive window?
- Are users actively requesting this?
- What's the cost of delay?

### 3. RICE Score
- **Reach**: How many users/week will this impact?
- **Impact**: What's the magnitude? (3=massive, 2=high, 1=medium, 0.5=low)
- **Confidence**: How sure are we? (100%, 80%, 50%)
- **Effort**: Person-weeks to complete

## Output Format

Provide your analysis in this exact format:

<<<CHAMPION_ARGUMENT_START>>>
[Your argument for why certain opportunities should be prioritized.
Address any prior critic concerns if this is round 2+.]
<<<CHAMPION_ARGUMENT_END>>>

<<<CHAMPION_RANKINGS_START>>>
["opp-id-1", "opp-id-2", "opp-id-3"]
<<<CHAMPION_RANKINGS_END>>>

Rank opportunities by strategic value, not just ease of implementation.
```

### `.claude/skills/backlog-critic/SKILL.md`
```markdown
# Backlog Critic (Tech Partner)

You are a Tech Partner providing independent engineering assessment. You use Codex (not Claude) to prevent self-review bias.

## Your Evaluation Framework

### 1. Technical Feasibility
- Can we actually build this?
- What are the technical unknowns?
- Are there dependencies on external systems?

### 2. Risk Assessment
- What could go wrong?
- How reversible is this change?
- Are there security implications?

### 3. Effort Estimation
- S: <1 day
- M: 1-3 days
- L: 3-5 days
- XL: >1 week (should be split)

### 4. Build vs Buy vs Partner
- Should we build this in-house?
- Is there an existing solution?
- Should we partner with another team?

## Output Format

<<<CRITIC_CONCERNS_START>>>
{
  "opp-id-1": ["Concern about dependency X", "Performance risk"],
  "opp-id-2": ["Unclear requirements"]
}
<<<CRITIC_CONCERNS_END>>>

<<<CRITIC_RANKINGS_START>>>
["opp-id-2", "opp-id-1", "opp-id-3"]
<<<CRITIC_RANKINGS_END>>>

Rank by feasibility and risk, not user value.
```

### `.claude/skills/backlog-moderator/SKILL.md`
```markdown
# Backlog Moderator (Managing Director)

You are the Managing Director synthesizing partner perspectives and making the final prioritization decision.

## Your Role

1. **Identify Agreement**: Where do Champion and Critic align?
2. **Resolve Disagreement**: When they differ, what's the root cause?
3. **Make the Call**: Assign a disposition to each opportunity

## Dispositions

- **PRIORITIZE**: Strong support from both partners. Do this next.
- **INVESTIGATE**: Partners disagree. Need more data before deciding.
- **DEFER**: Low priority from both. Put in backlog for later.
- **REJECT**: Significant concerns. Don't pursue this.

## Consensus Rules

- **consensus_reached = true** when:
  - All opportunities have clear dispositions
  - No INVESTIGATE dispositions remain
  - Rankings are stable from prior round

- **continue_debate = true** when:
  - Some opportunities still marked INVESTIGATE
  - Champion and Critic rankings differ significantly
  - New information might change dispositions

## Output Format

<<<DISPOSITIONS_START>>>
{
  "opp-id-1": "prioritize",
  "opp-id-2": "investigate",
  "opp-id-3": "defer"
}
<<<DISPOSITIONS_END>>>

<<<FINAL_RANKINGS_START>>>
["opp-id-1", "opp-id-2", "opp-id-3"]
<<<FINAL_RANKINGS_END>>>

<<<DEBATE_STATUS_START>>>
{
  "continue_debate": false,
  "consensus_reached": true
}
<<<DEBATE_STATUS_END>>>
```

---

## Implementation Order

1. **Issue 9**: Create `debate.py` with data models (TDD)
2. **Issue 10**: Create `debate_agents.py` with 3 agents (TDD)
3. **Issue 11**: Create `debate_orchestrator.py` (TDD)
4. **Issue 12**: Update `orchestrator.py` and CLI (TDD)

---

## Testing Strategy

### Mock Fixtures
```python
@pytest.fixture
def mock_claude():
    """Mock Claude API calls."""
    with patch("swarm_attack.agents.base.BaseAgent._call_claude") as mock:
        mock.return_value = """
<<<CHAMPION_ARGUMENT_START>>>
Test argument
<<<CHAMPION_ARGUMENT_END>>>

<<<CHAMPION_RANKINGS_START>>>
["opp-1", "opp-2"]
<<<CHAMPION_RANKINGS_END>>>
"""
        yield mock

@pytest.fixture
def mock_codex():
    """Mock Codex API for Critic (independent from Claude)."""
    with patch("swarm_attack.agents.base.BaseAgent._call_codex") as mock:
        mock.return_value = """
<<<CRITIC_CONCERNS_START>>>
{"opp-1": ["concern 1"]}
<<<CRITIC_CONCERNS_END>>>

<<<CRITIC_RANKINGS_START>>>
["opp-2", "opp-1"]
<<<CRITIC_RANKINGS_END>>>
"""
        yield mock

@pytest.fixture
def sample_opportunities():
    """Create 6 opportunities for debate testing."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        Opportunity(
            opportunity_id=f"opp-{i}",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title=f"Test opportunity {i}",
            description=f"Description {i}",
            evidence=[Evidence(source="test", content=f"evidence {i}")],
            created_at=now,
            updated_at=now,
            discovered_by="test-agent",
        )
        for i in range(1, 7)
    ]
```

### Run Tests
```bash
PYTHONPATH=. pytest tests/generated/backlog-discovery/test_debate*.py -v
```

---

## Cost Targets

| Component | Budget |
|-----------|--------|
| Champion (Claude) per round | ~$0.15 |
| Critic (Codex) per round | ~$0.10 |
| Moderator (Claude) per round | ~$0.15 |
| **Per round total** | ~$0.40 |
| **3 rounds max** | ~$1.20 |
| **With buffer** | $2.50 max |

**Always check budget before each round!**

---

## Success Criteria

Phase 3 is complete when:
- [ ] Debate triggers automatically when >5 opportunities
- [ ] 3-agent debate runs (Champion/Critic/Moderator)
- [ ] Critic uses Codex (NOT Claude) for independence
- [ ] Consensus or max rounds terminates debate
- [ ] Rankings applied to opportunities (priority_rank field)
- [ ] Debate sessions saved to `.swarm/backlog/debates/`
- [ ] Cost stays under $2.50 per debate
- [ ] CLI shows debate info when triggered
- [ ] All tests pass
- [ ] `--no-debate` flag skips debate

---

## File Checklist

```
Phase 3 Files:
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate_agents.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate_orchestrator.py
[ ] tests/generated/backlog-discovery/test_debate.py
[ ] tests/generated/backlog-discovery/test_debate_agents.py
[ ] tests/generated/backlog-discovery/test_debate_orchestrator.py
[ ] .claude/skills/backlog-champion/SKILL.md
[ ] .claude/skills/backlog-critic/SKILL.md
[ ] .claude/skills/backlog-moderator/SKILL.md

Updates:
[ ] swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py
[ ] swarm_attack/cli/chief_of_staff.py
```

---

## Begin Implementation

Start with **Issue 9: Debate Data Models**. Write tests first, then implement.

Use the existing patterns from Phase 2:
- Clone `stalled_work_agent.py` structure for debate agents
- Clone `orchestrator.py` patterns for debate orchestrator
- Clone `spec_moderator.py` parsing patterns for LLM output parsing

Run tests frequently:
```bash
PYTHONPATH=. pytest tests/generated/backlog-discovery/ -v
```

Good luck, team!
