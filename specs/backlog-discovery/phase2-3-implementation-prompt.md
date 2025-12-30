# Implementation Prompt: Backlog Discovery Phase 2 & 3

## Mission

You are a team of expert software engineers continuing the **Backlog Discovery** feature for Swarm Attack. Phase 1 (MVP Test Failure Analyzer) is complete. Your goal is to implement Phase 2 (Stalled Work + Code Quality) and Phase 3 (3-Agent Debate Prioritization).

---

## What's Already Complete (Phase 1)

The following files exist and are tested (66 tests passing):

```
swarm_attack/chief_of_staff/backlog_discovery/
├── __init__.py           ✅ Complete
├── candidates.py         ✅ Complete (Opportunity, Evidence, ActionabilityScore, enums)
├── store.py              ✅ Complete (BacklogStore with atomic writes, similarity search)
├── discovery_agent.py    ✅ Complete (TestFailureDiscoveryAgent)

tests/generated/backlog-discovery/
├── test_candidates.py    ✅ 21 tests passing
├── test_store.py         ✅ 21 tests passing
├── test_discovery_agent.py ✅ 24 tests passing

.claude/skills/
├── backlog-champion/SKILL.md    ✅ Complete
├── backlog-critic/SKILL.md      ✅ Complete
├── backlog-moderator/SKILL.md   ✅ Complete

CLI Commands:
- `swarm-attack cos discover`    ✅ Complete
- `swarm-attack cos backlog`     ✅ Complete
```

---

## Key Patterns to Clone

Read these existing files to understand patterns:

| Pattern | Source File | Use For |
|---------|-------------|---------|
| BaseAgent | `swarm_attack/agents/base.py` | All new agents |
| TestFailureDiscoveryAgent | `swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py` | StalledWork/CodeQuality agents |
| SpecModerator debate | `swarm_attack/agents/spec_moderator.py` | BacklogModerator output parsing |
| SpecCritic (Codex) | `swarm_attack/agents/spec_critic.py` | BacklogCritic (use Codex) |
| EpisodeStore.find_similar() | `swarm_attack/chief_of_staff/episodes.py` | Duplicate detection |
| StateGatherer | `swarm_attack/chief_of_staff/state_gatherer.py` | Gather system state |

---

## Phase 2: Stalled Work + Code Quality Discovery (Issues 5-8)

### Issue 5: StalledWorkDiscoveryAgent

**File:** `swarm_attack/chief_of_staff/backlog_discovery/stalled_work_agent.py`

```python
from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.chief_of_staff.state_gatherer import StateGatherer

class StalledWorkDiscoveryAgent(BaseAgent):
    """Discovers stalled features and interrupted sessions.

    No LLM cost - uses StateGatherer data only.
    """

    name: str = "stalled-work-discovery"

    def run(self, context: dict) -> AgentResult:
        """
        Discovers:
        1. Features stuck in same phase >24 hours
        2. Interrupted/paused sessions
        3. Goals with repeated failures (>2 attempts)
        4. Issues stuck in IN_PROGRESS

        Returns:
            AgentResult with list of Opportunity objects
        """
        pass
```

**Detection Rules (no LLM):**

| Condition | Creates Opportunity |
|-----------|---------------------|
| Feature in same phase >24h | STALLED_WORK |
| Session state = INTERRUPTED/PAUSED | STALLED_WORK |
| Same goal failed 3+ times | STALLED_WORK |
| Issue IN_PROGRESS >4 hours | STALLED_WORK |

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_stalled_work_agent.py

def test_detects_stalled_features():
    """Feature in IMPLEMENTING for >24h is detected."""

def test_detects_interrupted_sessions():
    """Session with state=INTERRUPTED creates opportunity."""

def test_detects_repeated_goal_failures():
    """Goal failing 3+ times creates opportunity."""

def test_ignores_recent_activity():
    """Feature modified <24h ago is not stalled."""

def test_calculates_actionability_based_on_progress():
    """80% complete = high actionability; 10% = low."""
```

---

### Issue 6: FeatureOpportunityAgent (McKinsey-Style Analysis)

**File:** `swarm_attack/chief_of_staff/backlog_discovery/feature_opportunity_agent.py`

```python
class FeatureOpportunityAgent(BaseAgent):
    """Discovers high-ROI feature opportunities via McKinsey-style analysis.

    Uses LLM to analyze:
    1. Codebase capabilities (what exists)
    2. Industry patterns (what competitors have)
    3. User value gaps (what's missing)
    4. Implementation leverage (what's easy to build)

    Cost: ~$0.50 per analysis (uses Claude for strategic thinking)
    """

    name: str = "feature-opportunity-discovery"

    def run(self, context: dict) -> AgentResult:
        """
        Performs strategic analysis:

        1. Codebase Audit:
           - What features exist?
           - What infrastructure is in place?
           - What patterns can be leveraged?

        2. Market Opportunity Analysis:
           - Industry trends in this domain
           - Competitor features (inferred from code type)
           - User value propositions

        3. ROI Scoring:
           - Impact: User value delivered (1-10)
           - Effort: Implementation complexity (1-10)
           - Leverage: Reuse of existing code (1-10)
           - Risk: Technical/adoption risk (1-10)

        4. Prioritized Recommendations:
           - Top 3-5 features with business cases
           - Each with clear "why now" rationale

        Returns:
            AgentResult with list of FEATURE_OPPORTUNITY opportunities
        """
        pass

    def _analyze_codebase(self) -> dict:
        """Scan codebase to understand capabilities."""
        return {
            "languages": self._detect_languages(),
            "frameworks": self._detect_frameworks(),
            "features": self._detect_existing_features(),
            "apis": self._detect_api_patterns(),
            "data_models": self._detect_data_models(),
        }

    def _build_analysis_prompt(self, codebase_analysis: dict) -> str:
        """Build McKinsey-style analysis prompt."""
        return f"""
You are a McKinsey Senior Partner analyzing a software product for strategic opportunities.

## Codebase Analysis
{json.dumps(codebase_analysis, indent=2)}

## Your Task

Perform a rigorous strategic analysis:

### 1. Market Positioning
- What type of product is this?
- Who are the users?
- What problem does it solve?

### 2. Competitive Landscape
- What do competitors in this space typically offer?
- What features are table stakes?
- What would differentiate this product?

### 3. Opportunity Identification
For each opportunity, provide:
- **Feature**: Clear, specific feature description
- **User Value**: What problem it solves for users
- **Business Case**: Why it matters strategically
- **ROI Score**: Impact (1-10) × (10 - Effort) / Risk
- **Implementation Leverage**: What existing code can be reused?
- **Time to Value**: Days to MVP

### 4. Prioritization Matrix
Rank opportunities by:
- Quick Wins: High ROI, Low Effort
- Strategic Bets: High ROI, High Effort
- Low Hanging Fruit: Medium ROI, Very Low Effort
- Backburner: Everything else

Output as JSON:
{{
  "product_type": "...",
  "target_users": ["..."],
  "opportunities": [
    {{
      "title": "...",
      "description": "...",
      "user_value": "...",
      "business_case": "...",
      "impact": 8,
      "effort": 3,
      "leverage": 9,
      "risk": 2,
      "roi_score": 24.0,
      "category": "quick_win",
      "time_to_value_days": 5,
      "existing_code_to_leverage": ["path/to/file.py"]
    }}
  ]
}}
"""

    def _parse_opportunities(self, response: str) -> list[Opportunity]:
        """Convert LLM response to Opportunity objects."""
        data = json.loads(response)

        opportunities = []
        for idx, opp in enumerate(data["opportunities"]):
            opportunities.append(Opportunity(
                opportunity_id=self._generate_id(opp),
                opportunity_type=OpportunityType.FEATURE_OPPORTUNITY,
                status=OpportunityStatus.DISCOVERED,
                title=opp["title"],
                description=opp["description"],
                evidence=[
                    Evidence(
                        source="mckinsey_analysis",
                        content=opp["business_case"],
                    ),
                    Evidence(
                        source="user_value",
                        content=opp["user_value"],
                    ),
                ],
                actionability=ActionabilityScore(
                    clarity=min(opp["leverage"] / 10, 1.0),
                    evidence=0.7,  # Strategic analysis has moderate evidence
                    effort=self._effort_from_score(opp["effort"]),
                    reversibility="full",  # New features are additive
                ),
                suggested_fix=None,  # Feature specs come later
                affected_files=opp.get("existing_code_to_leverage", []),
                priority_rank=idx + 1,
                discovered_by=self.name,
            ))

        return opportunities
```

**Add new OpportunityType:**
```python
# In candidates.py
class OpportunityType(Enum):
    TEST_FAILURE = "test_failure"
    STALLED_WORK = "stalled_work"
    CODE_QUALITY = "code_quality"
    COVERAGE_GAP = "coverage_gap"
    COMPLEXITY = "complexity"
    FEATURE_OPPORTUNITY = "feature_opportunity"  # NEW
```

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_feature_opportunity_agent.py

def test_analyzes_codebase_structure(mock_claude):
    """Agent scans codebase to understand capabilities."""

def test_generates_mckinsey_style_opportunities(mock_claude):
    """Agent produces strategic feature opportunities with ROI scores."""

def test_categorizes_opportunities(mock_claude):
    """Opportunities are categorized as quick_win, strategic_bet, etc."""

def test_calculates_roi_correctly():
    """ROI = Impact × (10 - Effort) / Risk."""

def test_identifies_code_leverage(mock_claude):
    """Agent identifies existing code that can be reused."""

def test_respects_cost_budget():
    """Analysis stays within cost budget (~$0.50)."""
```

---

### Issue 6b: CodeQualityDiscoveryAgent

**File:** `swarm_attack/chief_of_staff/backlog_discovery/code_quality_agent.py`

```python
class CodeQualityDiscoveryAgent(BaseAgent):
    """Discovers code quality issues via static analysis.

    No LLM cost - uses radon, coverage.py, and file stats.
    Gracefully degrades if tools unavailable.
    """

    name: str = "code-quality-discovery"

    def run(self, context: dict) -> AgentResult:
        """
        Discovers:
        1. Complexity hotspots (radon cc > 10)
        2. Coverage gaps (files with <50% coverage)
        3. Oversized files (>500 lines)
        4. Missing tests (src/*.py without tests/*.py)

        Gracefully skips if radon/coverage unavailable.
        """
        pass

    def _check_complexity(self) -> list[Opportunity]:
        """Use radon if available, else skip."""
        try:
            import radon.complexity as radon_cc
            # ...
        except ImportError:
            self._log("radon_unavailable", {}, level="warning")
            return []

    def _check_coverage(self) -> list[Opportunity]:
        """Parse .coverage or coverage.xml if available."""
        pass

    def _check_file_size(self) -> list[Opportunity]:
        """Find files >500 lines."""
        pass

    def _check_missing_tests(self) -> list[Opportunity]:
        """Find src files without corresponding test files."""
        pass
```

**Actionability Rules:**

| Issue Type | Clarity | Evidence | Effort |
|------------|---------|----------|--------|
| Complexity >15 | 0.9 | 0.9 | large |
| Complexity 10-15 | 0.7 | 0.8 | medium |
| Coverage <30% | 0.8 | 0.9 | medium |
| File >500 lines | 0.6 | 0.9 | large |
| Missing tests | 0.8 | 0.7 | medium |

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_code_quality_agent.py

def test_detects_high_complexity(tmp_path):
    """File with CC>10 creates COMPLEXITY opportunity."""

def test_detects_low_coverage(tmp_path):
    """File with <50% coverage creates COVERAGE_GAP opportunity."""

def test_detects_oversized_files(tmp_path):
    """File >500 lines creates CODE_QUALITY opportunity."""

def test_graceful_without_radon():
    """Skips complexity check if radon not installed."""

def test_graceful_without_coverage():
    """Skips coverage check if no .coverage file."""
```

---

### Issue 7: DiscoveryOrchestrator

**File:** `swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py`

```python
from typing import Optional

class DiscoveryOrchestrator:
    """Runs discovery agents and merges results.

    Triggers debate if >5 opportunities found.
    """

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: BacklogStore,
        test_failure_agent: Optional[TestFailureDiscoveryAgent] = None,
        stalled_work_agent: Optional[StalledWorkDiscoveryAgent] = None,
        code_quality_agent: Optional[CodeQualityDiscoveryAgent] = None,
    ):
        self.agents = {
            "test": test_failure_agent or TestFailureDiscoveryAgent(config, backlog_store),
            "stalled": stalled_work_agent or StalledWorkDiscoveryAgent(config, backlog_store),
            "quality": code_quality_agent or CodeQualityDiscoveryAgent(config, backlog_store),
        }

    def discover(
        self,
        types: list[str] = ["test"],
        max_candidates: int = 10,
        trigger_debate: bool = True,
        debate_threshold: int = 5,
    ) -> DiscoveryResult:
        """
        Run discovery agents and merge results.

        Args:
            types: Which agents to run ("test", "stalled", "quality", "all")
            max_candidates: Maximum opportunities to return
            trigger_debate: Whether to trigger debate for >threshold
            debate_threshold: Number of opportunities that triggers debate

        Returns:
            DiscoveryResult with opportunities and metadata
        """
        all_opportunities = []
        total_cost = 0.0

        agents_to_run = self.agents.values() if "all" in types else [
            self.agents[t] for t in types if t in self.agents
        ]

        for agent in agents_to_run:
            result = agent.run(context={})
            all_opportunities.extend(result.output.get("opportunities", []))
            total_cost += result.cost_usd

        # Deduplicate
        unique = self._deduplicate(all_opportunities)

        # Trigger debate if threshold exceeded
        if trigger_debate and len(unique) > debate_threshold:
            debate_result = self._run_debate(unique)
            unique = debate_result.ranked_opportunities
            total_cost += debate_result.cost_usd

        return DiscoveryResult(
            opportunities=unique[:max_candidates],
            total_candidates=len(unique),
            cost_usd=total_cost,
            debate_triggered=len(unique) > debate_threshold,
        )

    def _deduplicate(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Remove duplicates using semantic similarity."""
        pass

    def _run_debate(self, opportunities: list[Opportunity]) -> DebateResult:
        """Run 3-agent debate to prioritize. See Phase 3."""
        pass


@dataclass
class DiscoveryResult:
    opportunities: list[Opportunity]
    total_candidates: int
    cost_usd: float
    debate_triggered: bool
    debate_session_id: Optional[str] = None
```

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_orchestrator.py

def test_runs_single_agent():
    """types=["test"] only runs TestFailureDiscoveryAgent."""

def test_runs_all_agents():
    """types=["all"] runs all discovery agents."""

def test_merges_results_from_multiple_agents():
    """Results from all agents are combined."""

def test_deduplicates_similar_opportunities():
    """Same issue from different agents = 1 opportunity."""

def test_triggers_debate_when_threshold_exceeded():
    """6 opportunities triggers debate (threshold=5)."""

def test_respects_max_candidates():
    """max_candidates=5 returns at most 5 opportunities."""
```

---

### Issue 8: CLI Updates for Multi-Type Discovery

**File:** `swarm_attack/cli/chief_of_staff.py` (update existing)

```python
@app.command("discover")
def discover_command(
    deep: bool = typer.Option(False, "--deep", help="Include LLM fix suggestions"),
    opp_type: str = typer.Option("test", "--type", "-t",
        help="Discovery type: test, stalled, quality, all"),
    max_candidates: int = typer.Option(10, "--max", "-m",
        help="Maximum opportunities to discover"),
    no_debate: bool = typer.Option(False, "--no-debate",
        help="Skip debate even if >5 opportunities"),
) -> None:
    """Discover opportunities for improvement.

    Examples:
        swarm-attack cos discover                  # Test failures only
        swarm-attack cos discover --type all       # All discovery types
        swarm-attack cos discover --type stalled   # Stalled work only
        swarm-attack cos discover --type quality   # Code quality only
        swarm-attack cos discover --deep           # With LLM suggestions
        swarm-attack cos discover --no-debate      # Skip prioritization debate
    """
    # Update to use DiscoveryOrchestrator
    types = ["test", "stalled", "quality"] if opp_type == "all" else [opp_type]

    orchestrator = _get_discovery_orchestrator()
    result = orchestrator.discover(
        types=types,
        max_candidates=max_candidates,
        trigger_debate=not no_debate,
    )

    # Display results with cost summary
    console.print(f"\n[bold]Discovered {result.total_candidates} opportunities[/bold]")
    if result.debate_triggered:
        console.print(f"[dim]Debate triggered (>{debate_threshold} candidates)[/dim]")
    console.print(f"[dim]Cost: ${result.cost_usd:.2f}[/dim]")

    # ... existing table display ...
```

---

## Phase 3: 3-Agent Debate Prioritization (Issues 9-12)

### Issue 9: Debate Data Models

**File:** `swarm_attack/chief_of_staff/backlog_discovery/debate.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class DebateRound:
    """A single round of the 3-agent debate."""

    round_number: int

    # Champion phase
    champion_argument: str
    champion_rankings: list[str]  # opportunity_ids in priority order
    champion_cost_usd: float

    # Critic phase (Codex)
    critic_concerns: dict[str, list[str]]  # opportunity_id -> concerns
    critic_counter_rankings: list[str]
    critic_cost_usd: float

    # Moderator phase
    moderator_dispositions: list[dict]  # See SKILL.md format
    moderator_final_rankings: list[str]
    moderator_cost_usd: float

    continue_debate: bool
    consensus_reached: bool

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> "DebateRound": ...


@dataclass
class DebateSession:
    """Complete debate session with all rounds."""

    session_id: str
    started_at: str
    completed_at: Optional[str] = None

    opportunity_ids: list[str]
    rounds: list[DebateRound] = field(default_factory=list)
    max_rounds: int = 3

    final_rankings: list[str] = field(default_factory=list)
    consensus_reached: bool = False
    stalemate: bool = False

    total_cost_usd: float = 0.0
    budget_usd: float = 2.50

    def add_round(self, round: DebateRound) -> None:
        self.rounds.append(round)
        self.total_cost_usd += (
            round.champion_cost_usd +
            round.critic_cost_usd +
            round.moderator_cost_usd
        )

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> "DebateSession": ...


@dataclass
class DebateResult:
    """Result of running a debate."""

    session: DebateSession
    ranked_opportunities: list[Opportunity]
    cost_usd: float
    rounds_used: int
```

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_debate.py

def test_debate_round_serialization_roundtrip():
    """DebateRound to_dict/from_dict preserves all fields."""

def test_debate_session_serialization_roundtrip():
    """DebateSession to_dict/from_dict preserves all fields."""

def test_debate_session_tracks_cost():
    """add_round() updates total_cost_usd correctly."""

def test_debate_session_budget_check():
    """Session tracks when budget exceeded."""
```

---

### Issue 10: Debate Agents (McKinsey Partner Debate)

The debate uses a **4-agent McKinsey Partner structure**:

| Agent | Persona | Model | Focus |
|-------|---------|-------|-------|
| **StrategyPartner** | PM/Designer/Business | Claude | User value, market opportunity, strategic fit |
| **TechPartner** | Engineering Lead | Codex | Feasibility, complexity, tech debt |
| **FinancePartner** | ROI Analyst | Claude | Cost/benefit, resource allocation, timing |
| **ManagingDirector** | Moderator | Claude | Final decision, consensus building |

**Files:**
- `swarm_attack/chief_of_staff/backlog_discovery/debate_agents.py`
- `.claude/skills/mckinsey-strategy-partner/SKILL.md`
- `.claude/skills/mckinsey-tech-partner/SKILL.md`
- `.claude/skills/mckinsey-finance-partner/SKILL.md`
- `.claude/skills/mckinsey-managing-director/SKILL.md`

```python
from swarm_attack.agents.base import BaseAgent, AgentResult

class McKinseyStrategyPartnerAgent(BaseAgent):
    """PM/Designer/Business perspective for strategic prioritization.

    Uses Claude. Focuses on:
    - User value and desirability
    - Market opportunity and timing
    - Strategic fit with product vision
    - Competitive differentiation

    See .claude/skills/mckinsey-strategy-partner/SKILL.md
    """

    name: str = "mckinsey-strategy-partner"

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                round_number: int
                prior_feedback: Optional[dict]

        Returns:
            AgentResult with:
                rankings: list[str]
                strategic_analysis: dict[str, dict]  # opp_id -> analysis
                recommended_next_feature: str
                market_timing_score: dict[str, float]
        """
        prompt = self._build_prompt(context)
        return f"""
You are a **McKinsey Senior Partner** specializing in Product Strategy and Design.

## Your Perspective

You evaluate opportunities through the lens of:

### 1. User Desirability
- Who wants this? How badly?
- What pain point does it solve?
- Will users pay for this / engage with this?

### 2. Market Opportunity
- Is the market timing right?
- What's the competitive landscape?
- First mover advantage or fast follower?

### 3. Strategic Fit
- Does this align with product vision?
- Does it strengthen competitive moat?
- Will it attract the right users?

### 4. Feature Prioritization Framework
Use the RICE framework:
- **Reach**: How many users affected?
- **Impact**: How significant per user? (1-3)
- **Confidence**: How sure are we? (0.5-1.0)
- **Effort**: Implementation cost (person-weeks)

Score = (Reach × Impact × Confidence) / Effort

## Output Format
```json
{{
  "rankings": ["opp-1", "opp-2", ...],
  "strategic_analysis": {{
    "opp-1": {{
      "user_desirability": 8,
      "market_timing": 9,
      "strategic_fit": 7,
      "rice_score": 45.2,
      "recommendation": "BUILD NOW - Strong product-market fit signal"
    }}
  }},
  "market_thesis": "...",
  "recommended_next_feature": "opp-1"
}}
```
"""


class McKinseyTechPartnerAgent(BaseAgent):
    """Engineering Lead perspective for technical feasibility.

    Uses CODEX (not Claude) for independent technical judgment.

    Focuses on:
    - Technical feasibility and complexity
    - Architecture impact and tech debt
    - Team capacity and skill match
    - Risk and dependencies
    """

    name: str = "mckinsey-tech-partner"
    model: str = "codex"  # CRITICAL: Independent model

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                strategy_rankings: list[str]
                strategy_analysis: dict

        Returns:
            AgentResult with:
                feasibility_analysis: dict[str, dict]
                concerns: dict[str, list[str]]
                counter_rankings: list[str]
                build_vs_buy: dict[str, str]
        """
        pass


class McKinseyFinancePartnerAgent(BaseAgent):
    """ROI Analyst perspective for resource allocation.

    Focuses on:
    - Cost/benefit analysis
    - Resource allocation efficiency
    - Opportunity cost
    - Time-to-value
    """

    name: str = "mckinsey-finance-partner"

    def run(self, context: dict) -> AgentResult:
        """
        Returns:
            AgentResult with:
                roi_analysis: dict[str, dict]  # NPV, payback period
                resource_allocation: dict[str, float]  # % of sprint
                opportunity_cost_ranking: list[str]
        """
        pass


class McKinseyManagingDirectorAgent(BaseAgent):
    """Managing Director synthesizes all partner perspectives.

    Makes final prioritization decision considering:
    - Strategy Partner's user/market view
    - Tech Partner's feasibility concerns
    - Finance Partner's ROI analysis

    Output uses markers for parsing:
    <<<PARTNER_SYNTHESIS_START>>>
    <<<PARTNER_SYNTHESIS_END>>>

    <<<FINAL_DECISION_START>>>
    <<<FINAL_DECISION_END>>>
    """

    name: str = "mckinsey-managing-director"

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                opportunities: list[Opportunity]
                strategy_partner: dict
                tech_partner: dict
                finance_partner: dict
                round_number: int

        Returns:
            AgentResult with:
                partner_synthesis: list[dict]  # Agreement/disagreement per opp
                final_rankings: list[str]
                executive_summary: str
                continue_debate: bool
                consensus_reached: bool
        """
        pass

    def _build_prompt(self, context: dict) -> str:
        return f"""
You are the **Managing Director** at McKinsey leading this prioritization engagement.

## Partner Input

### Strategy Partner (PM/Design/Business)
{json.dumps(context['strategy_partner'], indent=2)}

### Tech Partner (Engineering)
{json.dumps(context['tech_partner'], indent=2)}

### Finance Partner (ROI)
{json.dumps(context['finance_partner'], indent=2)}

## Your Task

1. **Synthesize Partner Views**
   - Where do partners agree?
   - Where do they disagree?
   - What's the root cause of disagreement?

2. **Make the Call**
   For each opportunity:
   - PRIORITIZE: Strong cross-partner support
   - INVESTIGATE: Partners disagree, need more data
   - DEFER: Low priority across partners
   - REJECT: Significant concerns from multiple partners

3. **Final Recommendation**
   - Top 3 priorities with executive summary
   - Resource allocation recommendation
   - Risk mitigation for top picks

## Output Format

<<<PARTNER_SYNTHESIS_START>>>
[
  {{
    "opportunity_id": "opp-1",
    "strategy_view": "BUILD NOW",
    "tech_view": "FEASIBLE with caveats",
    "finance_view": "HIGH ROI",
    "consensus": "STRONG",
    "key_debate": "Tech wants more time, Strategy says market window closing"
  }}
]
<<<PARTNER_SYNTHESIS_END>>>

<<<FINAL_DECISION_START>>>
{{
  "final_rankings": ["opp-1", "opp-3", "opp-2"],
  "executive_summary": "...",
  "sprint_allocation": {{
    "opp-1": 0.5,
    "opp-3": 0.3,
    "opp-2": 0.2
  }},
  "continue_debate": false,
  "consensus_reached": true
}}
<<<FINAL_DECISION_END>>>
"""
```

**Create SKILL.md files for each partner:**

```bash
mkdir -p .claude/skills/mckinsey-strategy-partner
mkdir -p .claude/skills/mckinsey-tech-partner
mkdir -p .claude/skills/mckinsey-finance-partner
mkdir -p .claude/skills/mckinsey-managing-director
```

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_debate_agents.py

class TestMcKinseyStrategyPartner:
    def test_evaluates_user_desirability(self, mock_claude):
        """Strategy Partner scores user desirability for each opportunity."""

    def test_calculates_rice_scores(self, mock_claude):
        """Strategy Partner applies RICE framework."""

    def test_provides_market_timing_analysis(self, mock_claude):
        """Strategy Partner considers market timing."""


class TestMcKinseyTechPartner:
    def test_uses_codex_for_independence(self, mock_codex):
        """Tech Partner uses Codex, not Claude."""

    def test_identifies_technical_concerns(self, mock_codex):
        """Tech Partner flags feasibility issues."""

    def test_provides_build_vs_buy_recommendation(self, mock_codex):
        """Tech Partner recommends build vs buy vs partner."""


class TestMcKinseyFinancePartner:
    def test_calculates_roi_metrics(self, mock_claude):
        """Finance Partner calculates NPV and payback period."""

    def test_considers_opportunity_cost(self, mock_claude):
        """Finance Partner ranks by opportunity cost."""


class TestMcKinseyManagingDirector:
    def test_synthesizes_all_partner_views(self, mock_claude):
        """MD combines input from all three partners."""

    def test_identifies_consensus_and_disagreement(self, mock_claude):
        """MD marks where partners agree/disagree."""

    def test_makes_final_prioritization_decision(self, mock_claude):
        """MD produces final ranked list."""

    def test_determines_consensus(self, mock_claude):
        """MD sets consensus_reached correctly."""
```

---

### Issue 11: BacklogDebateOrchestrator

**File:** `swarm_attack/chief_of_staff/backlog_discovery/debate_orchestrator.py`

```python
class BacklogDebateOrchestrator:
    """Runs 3-agent debate to prioritize opportunities.

    Flow per round:
    1. Champion argues for priorities
    2. Critic challenges with concerns (Codex)
    3. Moderator synthesizes and decides

    Stops when:
    - consensus_reached = True
    - max_rounds hit
    - budget exceeded
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
        self.champion = champion
        self.critic = critic
        self.moderator = moderator
        self.store = store
        self.max_rounds = max_rounds
        self.budget_usd = budget_usd

    def debate(self, opportunities: list[Opportunity]) -> DebateResult:
        """Run the debate and return prioritized opportunities."""

        session = DebateSession(
            session_id=self._generate_session_id(),
            started_at=datetime.now(timezone.utc).isoformat(),
            opportunity_ids=[o.opportunity_id for o in opportunities],
            max_rounds=self.max_rounds,
            budget_usd=self.budget_usd,
        )

        for round_num in range(1, self.max_rounds + 1):
            # Check budget before each round
            estimated_round_cost = 0.50  # ~$0.50 per round
            if session.total_cost_usd + estimated_round_cost > self.budget_usd:
                session.stalemate = True
                self._log("budget_exceeded", {"round": round_num})
                break

            # Phase 1: Champion argues
            champion_result = self.champion.run({
                "opportunities": opportunities,
                "round_number": round_num,
                "prior_critic_concerns": (
                    session.rounds[-1].critic_concerns if session.rounds else None
                ),
            })

            # Phase 2: Critic responds
            critic_result = self.critic.run({
                "opportunities": opportunities,
                "champion_rankings": champion_result.output["champion_rankings"],
                "champion_argument": champion_result.output["champion_argument"],
            })

            # Phase 3: Moderator decides
            moderator_result = self.moderator.run({
                "opportunities": opportunities,
                "champion_rankings": champion_result.output["champion_rankings"],
                "champion_argument": champion_result.output["champion_argument"],
                "critic_concerns": critic_result.output["concerns"],
                "critic_counter_rankings": critic_result.output["counter_rankings"],
                "round_number": round_num,
            })

            # Record round
            round = DebateRound(
                round_number=round_num,
                champion_argument=champion_result.output["champion_argument"],
                champion_rankings=champion_result.output["champion_rankings"],
                champion_cost_usd=champion_result.cost_usd,
                critic_concerns=critic_result.output["concerns"],
                critic_counter_rankings=critic_result.output["counter_rankings"],
                critic_cost_usd=critic_result.cost_usd,
                moderator_dispositions=moderator_result.output["dispositions"],
                moderator_final_rankings=moderator_result.output["final_rankings"],
                moderator_cost_usd=moderator_result.cost_usd,
                continue_debate=moderator_result.output["continue_debate"],
                consensus_reached=moderator_result.output["consensus_reached"],
            )
            session.add_round(round)

            # Check for consensus
            if round.consensus_reached:
                session.consensus_reached = True
                session.final_rankings = round.moderator_final_rankings
                break

            # Check if debate should continue
            if not round.continue_debate:
                session.final_rankings = round.moderator_final_rankings
                break

        # Finalize session
        session.completed_at = datetime.now(timezone.utc).isoformat()
        if not session.final_rankings:
            # Use last round's rankings
            session.final_rankings = session.rounds[-1].moderator_final_rankings

        # Save session
        self._save_session(session)

        # Apply rankings to opportunities
        ranked = self._apply_rankings(opportunities, session.final_rankings)

        return DebateResult(
            session=session,
            ranked_opportunities=ranked,
            cost_usd=session.total_cost_usd,
            rounds_used=len(session.rounds),
        )

    def _apply_rankings(
        self,
        opportunities: list[Opportunity],
        rankings: list[str]
    ) -> list[Opportunity]:
        """Apply priority_rank to opportunities based on debate results."""
        id_to_opp = {o.opportunity_id: o for o in opportunities}
        result = []

        for rank, opp_id in enumerate(rankings, 1):
            if opp_id in id_to_opp:
                opp = id_to_opp[opp_id]
                opp.priority_rank = rank
                opp.debate_session_id = self.current_session_id
                result.append(opp)

        # Add any not in rankings at the end
        for opp in opportunities:
            if opp.opportunity_id not in rankings:
                opp.priority_rank = len(rankings) + 1
                result.append(opp)

        return result
```

**Tests Required:**
```python
# tests/generated/backlog-discovery/test_debate_orchestrator.py

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
```

---

### Issue 12: Integration

**Updates to:** `swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py`

```python
class DiscoveryOrchestrator:
    """Updated to trigger debate."""

    def __init__(self, ..., debate_orchestrator: BacklogDebateOrchestrator = None):
        self.debate_orchestrator = debate_orchestrator or self._create_debate_orchestrator()

    def _run_debate(self, opportunities: list[Opportunity]) -> DebateResult:
        """Run 3-agent debate when threshold exceeded."""
        return self.debate_orchestrator.debate(opportunities)
```

**Update CLI to show debate info:**

```python
@app.command("discover")
def discover_command(...):
    # ... existing ...

    if result.debate_triggered:
        console.print(f"\n[bold yellow]Debate Prioritization[/bold yellow]")
        console.print(f"  Rounds: {result.debate_session.rounds_used}/{result.debate_session.max_rounds}")
        console.print(f"  Consensus: {'Yes' if result.debate_session.consensus_reached else 'No'}")
        console.print(f"  Debate cost: ${result.debate_session.total_cost_usd:.2f}")
```

---

## Testing Strategy

### TDD Approach

1. Write tests FIRST for each issue
2. Run tests to see them fail
3. Implement minimal code to pass
4. Refactor if needed
5. Move to next issue

### Mock Dependencies

```python
@pytest.fixture
def mock_claude():
    """Mock Claude API calls."""
    with patch("swarm_attack.agents.base.BaseAgent._call_claude") as mock:
        mock.return_value = "..."
        yield mock

@pytest.fixture
def mock_codex():
    """Mock Codex API calls for Critic."""
    with patch("swarm_attack.agents.base.BaseAgent._call_codex") as mock:
        mock.return_value = "..."
        yield mock

@pytest.fixture
def mock_state_gatherer():
    """Mock StateGatherer for agent tests."""
    with patch("swarm_attack.chief_of_staff.state_gatherer.StateGatherer") as mock:
        mock.return_value.gather.return_value = RepoStateSnapshot(...)
        yield mock
```

---

## Cost Targets

| Scenario | Budget |
|----------|--------|
| Phase 2 discovery (no debate) | $0.00 |
| Phase 3 debate (per session) | $2.50 max |
| Full discovery + debate | $3.00 max |

**Always check budget before LLM calls!**

---

## Success Criteria

### Phase 2 Complete When:
- [ ] `cos discover --type stalled` finds stalled work
- [ ] `cos discover --type quality` finds code quality issues
- [ ] `cos discover --type all` runs all agents
- [ ] Results are merged and deduplicated
- [ ] All tests pass

### Phase 3 Complete When:
- [ ] Debate triggers when >5 opportunities
- [ ] 3-agent debate runs (Champion/Critic/Moderator)
- [ ] Critic uses Codex (not Claude)
- [ ] Consensus or max rounds terminates debate
- [ ] Rankings applied to opportunities
- [ ] Debate sessions saved to `.swarm/backlog/debates/`
- [ ] Cost stays under $3 per session
- [ ] All tests pass

---

## File Checklist

```
Phase 2 - Discovery Agents:
[ ] swarm_attack/chief_of_staff/backlog_discovery/stalled_work_agent.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/feature_opportunity_agent.py  # McKinsey analysis
[ ] swarm_attack/chief_of_staff/backlog_discovery/code_quality_agent.py
[ ] swarm_attack/chief_of_staff/backlog_discovery/orchestrator.py
[ ] tests/generated/backlog-discovery/test_stalled_work_agent.py
[ ] tests/generated/backlog-discovery/test_feature_opportunity_agent.py
[ ] tests/generated/backlog-discovery/test_code_quality_agent.py
[ ] tests/generated/backlog-discovery/test_orchestrator.py

Phase 3 - McKinsey Partner Debate:
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate.py (models)
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate_agents.py (4 McKinsey partners)
[ ] swarm_attack/chief_of_staff/backlog_discovery/debate_orchestrator.py
[ ] tests/generated/backlog-discovery/test_debate.py
[ ] tests/generated/backlog-discovery/test_debate_agents.py
[ ] tests/generated/backlog-discovery/test_debate_orchestrator.py

McKinsey Partner Skills:
[ ] .claude/skills/mckinsey-strategy-partner/SKILL.md  # PM/Design/Business
[ ] .claude/skills/mckinsey-tech-partner/SKILL.md      # Engineering Lead (Codex)
[ ] .claude/skills/mckinsey-finance-partner/SKILL.md   # ROI Analyst
[ ] .claude/skills/mckinsey-managing-director/SKILL.md # Final Decision Maker
```

---

## Begin Implementation

Start with **Issue 5: StalledWorkDiscoveryAgent**. Write tests first, then implement.

Use the patterns from the completed `discovery_agent.py` as your template.

Run tests frequently:
```bash
PYTHONPATH=. pytest tests/generated/backlog-discovery/ -v
```

Good luck, team!
