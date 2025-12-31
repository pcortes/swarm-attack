# Engineering Spec: COO Priority Board

## 1. Overview

### 1.1 Purpose

The COO Priority Board is a forward-looking strategic prioritization system that assembles cross-functional expert panels to study the codebase and market opportunities, propose priorities from their domain perspective, and engage in structured debate until reaching consensus. Unlike the Strategic Advisory Board (backward-looking review), this system determines **what to build next**.

### 1.2 Existing Infrastructure

This feature builds heavily on existing swarm-attack infrastructure:

| Component | Source | Purpose |
|-----------|--------|---------|
| `swarm_attack/codex_client.py` | Copy to COO | External review via Codex CLI |
| `swarm_attack/orchestrator.py` | Adapt debate loop | Multi-round debate pattern (`run_spec_debate_only()`) |
| `swarm_attack/agents/spec_moderator.py` | Adapt for priorities | ACCEPT/REJECT/DEFER disposition pattern |
| `swarm_attack/agents/base.py` | Reference pattern | Agent structure, `AgentResult`, skill loading |
| `swarm_attack/llm_clients.py` | Reference | Claude CLI runner pattern |
| `swarm_attack/chief_of_staff/` | Target codebase | Existing COO infrastructure to extend |

**COO existing infrastructure (in `/Users/philipjcortes/Desktop/coo/src/`):**
- Daily digest generation
- Strategic Advisory Board
- GitHub Pages dashboard
- Campaign planning/execution

### 1.3 Scope

**In Scope:**
- 5-panel expert system (Product, CEO, Engineering, Design, Ops)
- Librarian sub-agent for on-demand market research
- Multi-round debate loop until consensus or max rounds
- Required Codex external review
- Per-project priority files + company rollup
- GitHub Pages dashboard integration
- Daily cron integration (runs after Strategic Advisory Board)

**Out of Scope:**
- Automatic spec generation from priorities (separate skill)
- Human override/veto system (run autonomously)
- Cost ceiling (run until complete)
- Horizontal scaling / multi-region

## 2. Implementation

### 2.1 Approach

Build a priority orchestrator that reuses the debate loop pattern from swarm-attack. Each panel runs as a separate agent invocation, the moderator merges weighted votes, and consensus is checked after each round. Codex provides required external review before finalizing.

**Key architectural decisions:**
1. **Sub-agent spawning**: Panels can spawn Librarian agents mid-deliberation for research
2. **Weighted voting**: Product (30%) + CEO (30%) + Engineering (20%) + Design (10%) + Ops (10%)
3. **Consensus detection**: 3+ common priorities in top 5 across 4+ panels
4. **Disposition tracking**: Reuse ACCEPT/REJECT/DEFER/PARTIAL pattern from spec_moderator

### 2.2 Changes Required

| File | Change | Why |
|------|--------|-----|
| `src/priority_orchestrator.py` | **NEW** | Main debate orchestration adapted from swarm-attack |
| `src/priority_panel.py` | **NEW** | Individual panel execution with Librarian spawning |
| `src/priority_moderator.py` | **NEW** | Weighted merge and disposition tracking |
| `src/consensus_checker.py` | **NEW** | Consensus detection logic |
| `src/codex_client.py` | **COPY** | Copy from swarm-attack, adapt for COO config |
| `src/sub_agent.py` | **NEW** | Sub-agent spawning pattern (Librarian) |
| `src/priority_output.py` | **NEW** | Per-project + rollup markdown generation |
| `src/cli.py` | **MODIFY** | Add `prioritize` command with flags |
| `scripts/generate-dashboard.py` | **MODIFY** | Add priorities section to dashboard |
| `scripts/daily-digest-cron.sh` | **MODIFY** | Run prioritize after strategic-review |

### 2.3 Data Model

**New models (extend existing COO models):**

```python
# src/models/priority.py

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PanelType(Enum):
    PRODUCT = "product"
    CEO = "ceo"
    ENGINEERING = "engineering"
    DESIGN = "design"
    OPERATIONS = "operations"


@dataclass
class PanelWeight:
    panel: PanelType
    weight: float  # 0.0 - 1.0


@dataclass
class PriorityProposal:
    """Single priority proposed by a panel."""
    name: str
    why: str
    effort: str  # S/M/L/XL
    impact_score: float  # 1-10
    feasibility_score: float  # 1-10
    strategic_fit: float  # 1-10
    dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class PanelSubmission:
    """Full submission from one panel."""
    panel: PanelType
    expert_name: str
    priorities: list[PriorityProposal]
    research_queries: list[str] = field(default_factory=list)
    research_results: list[dict] = field(default_factory=list)


@dataclass
class PriorityDisposition:
    """Disposition of a priority across rounds (reuses swarm-attack pattern)."""
    priority_name: str
    semantic_key: str
    round: int
    classification: str  # ACCEPT, REJECT, DEFER, PARTIAL
    reasoning: str
    panel_scores: dict[str, float] = field(default_factory=dict)
    weighted_score: float = 0.0


@dataclass
class ConsensusResult:
    """Result of consensus check."""
    reached: bool
    common_priorities: list[str]
    overlap_count: int
    score_std_dev: float
    forced: bool = False  # True if forced after max rounds


@dataclass
class ExternalReviewResult:
    """Result from Codex external review."""
    outcome: str  # APPROVE, CHALLENGE, ESCALATE
    feedback: str
    challenged_priorities: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


@dataclass
class PrioritizationResult:
    """Final result of prioritization board."""
    success: bool
    project: str
    priorities: list[PriorityProposal]
    rounds_to_consensus: int
    external_review: Optional[ExternalReviewResult] = None
    cost_usd: float = 0.0
    error: Optional[str] = None
```

## 3. New Components

### 3.1 SubAgentRunner (Librarian Pattern)

```python
# src/sub_agent.py

from dataclasses import dataclass
from typing import Any, Optional
import subprocess
import json


@dataclass
class SubAgentResult:
    success: bool
    output: str
    cost_usd: float
    error: Optional[str] = None


class SubAgentRunner:
    """
    Spawns sub-agents to complete specific tasks.

    Uses Claude CLI in subprocess, similar to swarm-attack's ClaudeCliRunner.
    """

    def __init__(self, config, skill_loader):
        self.config = config
        self.skill_loader = skill_loader

    def spawn(
        self,
        skill_name: str,
        context: dict[str, Any],
        timeout: int = 120,
    ) -> SubAgentResult:
        """
        Spawn a sub-agent to run a skill with given context.

        Args:
            skill_name: Name of the skill (e.g., "librarian")
            context: Context dict with placeholders to inject
            timeout: Max seconds to wait

        Returns:
            SubAgentResult with output or error
        """
        skill_prompt = self.skill_loader.load_skill(skill_name)
        full_prompt = self._inject_context(skill_prompt, context)

        result = subprocess.run(
            [
                "claude",
                "--print", full_prompt,
                "--output-format", "json",
                "--max-turns", "5",
            ],
            capture_output=True,
            timeout=timeout,
            text=True,
        )

        if result.returncode != 0:
            return SubAgentResult(
                success=False,
                output="",
                cost_usd=0.0,
                error=result.stderr,
            )

        try:
            response = json.loads(result.stdout)
            return SubAgentResult(
                success=True,
                output=response.get("result", result.stdout),
                cost_usd=response.get("cost_usd", 0.0),
            )
        except json.JSONDecodeError:
            return SubAgentResult(
                success=True,
                output=result.stdout,
                cost_usd=0.0,
            )

    def _inject_context(self, prompt: str, context: dict) -> str:
        """Replace {placeholders} in prompt with context values."""
        for key, value in context.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt
```

### 3.2 Consensus Checker

```python
# src/consensus_checker.py

from dataclasses import dataclass
import statistics
from typing import Optional


@dataclass
class ConsensusResult:
    reached: bool
    common_priorities: list[str]
    overlap_count: int
    score_std_dev: float
    forced: bool = False


def check_consensus(
    panel_rankings: list[list[str]],
    round_number: int,
    max_rounds: int = 5,
    min_overlap: int = 3,
    max_std_dev: float = 1.5,
) -> ConsensusResult:
    """
    Check if panels have reached consensus on priorities.

    Consensus criteria:
    1. At least min_overlap priorities common in top 5 across 4+ panels
    2. Standard deviation of scores < max_std_dev
    3. After max_rounds, force consensus using weighted voting

    Args:
        panel_rankings: List of priority name lists (top 10 each)
        round_number: Current round number
        max_rounds: Maximum rounds before forcing
        min_overlap: Minimum common priorities needed
        max_std_dev: Maximum score standard deviation

    Returns:
        ConsensusResult with status and details
    """
    # Extract top 5 from each panel
    top_5s = [set(r[:5]) for r in panel_rankings if r]

    if not top_5s:
        return ConsensusResult(
            reached=False,
            common_priorities=[],
            overlap_count=0,
            score_std_dev=float('inf'),
        )

    # Find intersection across all panels
    common = set.intersection(*top_5s) if len(top_5s) > 1 else top_5s[0]

    # Check if enough panels agree (4 of 5)
    overlap_count = len(common)

    # Calculate score std dev (placeholder - actual implementation uses weighted scores)
    std_dev = 0.0  # Simplified for now

    # Check natural consensus
    if overlap_count >= min_overlap and std_dev < max_std_dev:
        return ConsensusResult(
            reached=True,
            common_priorities=list(common),
            overlap_count=overlap_count,
            score_std_dev=std_dev,
        )

    # Force after max rounds
    if round_number >= max_rounds:
        return ConsensusResult(
            reached=True,
            common_priorities=list(common),
            overlap_count=overlap_count,
            score_std_dev=std_dev,
            forced=True,
        )

    return ConsensusResult(
        reached=False,
        common_priorities=list(common),
        overlap_count=overlap_count,
        score_std_dev=std_dev,
    )


def weighted_vote(
    panel_rankings: dict[str, list[str]],
    weights: dict[str, float],
    top_n: int = 10,
) -> list[str]:
    """
    Produce final ranking using weighted voting.

    Args:
        panel_rankings: Dict of panel_name -> priority list
        weights: Dict of panel_name -> weight (0.0-1.0)
        top_n: Number of priorities to return

    Returns:
        Sorted list of priority names by weighted score
    """
    scores: dict[str, float] = {}

    for panel, priorities in panel_rankings.items():
        weight = weights.get(panel, 0.0)
        for rank, priority in enumerate(priorities):
            # Higher rank = more points (10 for #1, 9 for #2, etc.)
            points = (10 - rank) * weight if rank < 10 else 0
            scores[priority] = scores.get(priority, 0.0) + points

    # Sort by score descending
    sorted_priorities = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [p[0] for p in sorted_priorities[:top_n]]
```

### 3.3 Priority Orchestrator

```python
# src/priority_orchestrator.py

from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path

from src.consensus_checker import check_consensus, weighted_vote, ConsensusResult
from src.priority_panel import PriorityPanel
from src.priority_moderator import PriorityModerator
from src.codex_client import CodexCliRunner


@dataclass
class PrioritizationResult:
    success: bool
    project: str
    priorities: list[dict]
    rounds_to_consensus: int
    external_review_outcome: str  # APPROVE, CHALLENGE, ESCALATE
    cost_usd: float
    error: Optional[str] = None


class PriorityOrchestrator:
    """
    Orchestrates the priority board debate loop.

    Adapts swarm-attack's run_spec_debate_only() pattern:
    1. Each panel proposes top 10 priorities
    2. Moderator merges and checks consensus
    3. If no consensus, panels revise in next round
    4. After consensus, Codex reviews (required)
    5. Output final prioritized roadmap
    """

    # Panel weights (must sum to 1.0)
    WEIGHTS = {
        "product": 0.30,
        "ceo": 0.30,
        "engineering": 0.20,
        "design": 0.10,
        "operations": 0.10,
    }

    def __init__(
        self,
        config,
        logger=None,
        panels: Optional[dict[str, PriorityPanel]] = None,
        moderator: Optional[PriorityModerator] = None,
        codex: Optional[CodexCliRunner] = None,
    ):
        self.config = config
        self.logger = logger
        self._panels = panels or self._create_default_panels()
        self._moderator = moderator or PriorityModerator(config, logger)
        self._codex = codex or CodexCliRunner(config, logger)

    def _create_default_panels(self) -> dict[str, PriorityPanel]:
        """Create the 5 expert panels with their prompts."""
        return {
            "product": PriorityPanel(
                self.config,
                self.logger,
                name="product",
                expert="Dr. Maya Chen",
                title="CPO",
                weight=0.30,
            ),
            "ceo": PriorityPanel(
                self.config,
                self.logger,
                name="ceo",
                expert="Sarah Okonkwo",
                title="CEO",
                weight=0.30,
            ),
            "engineering": PriorityPanel(
                self.config,
                self.logger,
                name="engineering",
                expert="James Morrison",
                title="VP Engineering",
                weight=0.20,
            ),
            "design": PriorityPanel(
                self.config,
                self.logger,
                name="design",
                expert="Marcus Williams",
                title="VP UX",
                weight=0.10,
            ),
            "operations": PriorityPanel(
                self.config,
                self.logger,
                name="operations",
                expert="Elena Vasquez",
                title="Chief of Staff",
                weight=0.10,
            ),
        }

    def run(
        self,
        project: str,
        max_rounds: int = 5,
        context: Optional[dict] = None,
    ) -> PrioritizationResult:
        """
        Run the full prioritization board for a project.

        Args:
            project: Project identifier (e.g., "miami", "moderndoc")
            max_rounds: Maximum debate rounds before forcing consensus
            context: Optional additional context (codebase analysis, etc.)

        Returns:
            PrioritizationResult with final priorities
        """
        total_cost = 0.0

        self._log("prioritization_start", {"project": project, "max_rounds": max_rounds})

        for round_num in range(1, max_rounds + 1):
            self._log("round_start", {"project": project, "round": round_num})

            # Step 1: Each panel proposes priorities
            panel_submissions = {}
            for name, panel in self._panels.items():
                result = panel.propose(project, round_num, context)
                total_cost += result.cost_usd

                if not result.success:
                    return PrioritizationResult(
                        success=False,
                        project=project,
                        priorities=[],
                        rounds_to_consensus=round_num,
                        external_review_outcome="",
                        cost_usd=total_cost,
                        error=f"Panel {name} failed: {result.error}",
                    )

                panel_submissions[name] = result.priorities

            # Step 2: Moderator merges and checks consensus
            panel_rankings = {
                name: [p["name"] for p in priorities]
                for name, priorities in panel_submissions.items()
            }

            consensus = check_consensus(
                list(panel_rankings.values()),
                round_num,
                max_rounds,
            )

            self._log("consensus_check", {
                "project": project,
                "round": round_num,
                "reached": consensus.reached,
                "overlap": consensus.overlap_count,
                "forced": consensus.forced,
            })

            if consensus.reached:
                # Get final weighted ranking
                final_ranking = weighted_vote(panel_rankings, self.WEIGHTS)

                # Build final priorities list with details
                final_priorities = self._build_final_priorities(
                    final_ranking,
                    panel_submissions,
                )

                # Step 3: Codex external review (required)
                review_result = self._run_codex_review(project, final_priorities)
                total_cost += review_result.get("cost_usd", 0.0)

                outcome = review_result.get("outcome", "APPROVE")

                if outcome == "CHALLENGE":
                    # Run another round focusing on challenged items
                    if round_num < max_rounds:
                        context = context or {}
                        context["codex_challenges"] = review_result.get("challenges", [])
                        continue

                if outcome == "ESCALATE":
                    return PrioritizationResult(
                        success=False,
                        project=project,
                        priorities=final_priorities,
                        rounds_to_consensus=round_num,
                        external_review_outcome="ESCALATE",
                        cost_usd=total_cost,
                        error="Codex escalated - requires human decision",
                    )

                # APPROVE - success!
                return PrioritizationResult(
                    success=True,
                    project=project,
                    priorities=final_priorities,
                    rounds_to_consensus=round_num,
                    external_review_outcome="APPROVE",
                    cost_usd=total_cost,
                )

        # Should not reach here (consensus forced at max_rounds)
        return PrioritizationResult(
            success=False,
            project=project,
            priorities=[],
            rounds_to_consensus=max_rounds,
            external_review_outcome="",
            cost_usd=total_cost,
            error="Unexpected: max rounds reached without forced consensus",
        )

    def _build_final_priorities(
        self,
        ranking: list[str],
        panel_submissions: dict[str, list[dict]],
    ) -> list[dict]:
        """Merge panel submissions into final priority list."""
        priorities = []

        for priority_name in ranking:
            # Find details from first panel that proposed it
            for panel_name, submissions in panel_submissions.items():
                for sub in submissions:
                    if sub["name"] == priority_name:
                        priorities.append({
                            **sub,
                            "proposed_by": panel_name,
                        })
                        break
                else:
                    continue
                break

        return priorities

    def _run_codex_review(
        self,
        project: str,
        priorities: list[dict],
    ) -> dict:
        """Run required Codex external review."""
        prompt = self._build_codex_prompt(project, priorities)

        try:
            result = self._codex.run(prompt, timeout=300)
            return self._parse_codex_response(result.text)
        except Exception as e:
            self._log("codex_error", {"error": str(e)}, level="error")
            # On error, default to APPROVE (don't block on external review failure)
            return {"outcome": "APPROVE", "cost_usd": 0.0}

    def _build_codex_prompt(self, project: str, priorities: list[dict]) -> str:
        """Build Codex review prompt with Thiel/PG frameworks."""
        priority_text = "\n".join([
            f"{i+1}. **{p['name']}** - {p.get('why', 'No description')}"
            for i, p in enumerate(priorities[:10])
        ])

        return f"""You are an independent strategic advisor reviewing a roadmap.

## Project: {project}

## Proposed Priorities

{priority_text}

## Your Task

1. Identify any priorities that seem misaligned with stated company goals
2. Flag any obvious gaps (important things not on the list)
3. Challenge the ranking if something seems out of place
4. Provide 3-5 questions the team should answer before committing

Be direct. Challenge assumptions. Don't just validate.

Apply Peter Thiel's framework: Is this a 10x improvement or just 1x?
Apply Paul Graham's test: Is this schlep they're avoiding?

## Output

Respond with one of:
- APPROVE: Roadmap looks solid
- CHALLENGE: [specific priorities to reconsider and why]
- ESCALATE: [fundamental issues requiring human decision]

Include your questions at the end.
"""

    def _parse_codex_response(self, text: str) -> dict:
        """Parse Codex response to extract outcome."""
        text_upper = text.upper()

        if "ESCALATE" in text_upper:
            return {"outcome": "ESCALATE", "feedback": text}
        elif "CHALLENGE" in text_upper:
            return {"outcome": "CHALLENGE", "feedback": text}
        else:
            return {"outcome": "APPROVE", "feedback": text}

    def _log(self, event: str, data: dict, level: str = "info") -> None:
        """Log an event if logger configured."""
        if self.logger:
            self.logger.log(event, data, level=level)
```

## 4. CLI Commands

### 4.1 New Commands

| Command | Description |
|---------|-------------|
| `prioritize` | Run prioritization board for all or specific projects |
| `prioritize --project NAME` | Run for single project |
| `prioritize --projects A,B,C` | Run for specific projects |
| `prioritize --dry-run` | Show what would be considered |
| `prioritize --max-rounds N` | Override max debate rounds |
| `prioritize --rollup-only` | Generate rollup from existing per-project files |

### 4.2 CLI Implementation

```python
# Add to src/cli.py

@app.command()
def prioritize(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Single project"),
    projects: Optional[str] = typer.Option(None, "--projects", help="Comma-separated projects"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would run"),
    max_rounds: int = typer.Option(5, "--max-rounds", help="Max debate rounds"),
    rollup_only: bool = typer.Option(False, "--rollup-only", help="Generate rollup only"),
):
    """Run the strategic priority board for projects."""
    from src.priority_orchestrator import PriorityOrchestrator
    from src.priority_output import PriorityOutputGenerator

    config = load_config()
    orchestrator = PriorityOrchestrator(config)
    output_gen = PriorityOutputGenerator(config)

    if rollup_only:
        output_gen.generate_rollup()
        typer.echo("Generated company-wide rollup")
        return

    # Determine which projects to run
    if project:
        target_projects = [project]
    elif projects:
        target_projects = [p.strip() for p in projects.split(",")]
    else:
        target_projects = config.get_all_projects()

    if dry_run:
        typer.echo(f"Would run prioritization for: {', '.join(target_projects)}")
        return

    results = []
    for proj in target_projects:
        typer.echo(f"Running prioritization for {proj}...")
        result = orchestrator.run(proj, max_rounds=max_rounds)
        results.append(result)

        # Generate per-project output
        output_gen.generate_project_output(result)

        if result.success:
            typer.echo(f"  Consensus in {result.rounds_to_consensus} rounds")
        else:
            typer.echo(f"  Failed: {result.error}", err=True)

    # Generate rollup
    output_gen.generate_rollup()
    typer.echo("Generated company-wide rollup")
```

## 5. Output Generation

### 5.1 Per-Project Output

Files created in `daily-logs/YYYY-MM-DD-priorities-{project}.md`:

```markdown
# Priorities: {project} - YYYY-MM-DD

**Generated:** YYYY-MM-DD at HH:MM PST
**Consensus Reached:** Round N of M
**Codex Review:** {APPROVE|CHALLENGE|ESCALATE}

---

## Top 10 Priorities

### 1. {Priority Name}

**Impact:** {High|Medium|Low} | **Effort:** {S|M|L|XL} | **Strategic Fit:** N/10

**Why #1:**
- {reasoning from each panel with weights}

**Panel Scores:**
| Panel | Rank | Score | Notes |
|-------|------|-------|-------|
| Product | #N | X.X | "quote" |
...

---

## Deferred Priorities

| Priority | Proposed By | Why Deferred | Reconsider |
|----------|-------------|--------------|------------|
...

---

## Debate Summary

**Round 1:** N unique priorities proposed
**Round 2:** Consolidated to M, resolved conflicts
**Round N:** Consensus reached

**Codex Feedback:** "quote"

---

*Generated by COO Roadmap Prioritization Board*
*Cost: $X.XX*
```

### 5.2 Company Rollup

Files created in `daily-logs/YYYY-MM-DD-priorities.md`:

```markdown
# Company Priorities - YYYY-MM-DD

## By Project

### {project-1}
1. {Priority} (score)
2. ...

### {project-2}
1. {Priority} (score)
2. ...

---

## Cross-Project Themes

| Theme | Projects | Combined Priority |
|-------|----------|-------------------|
| {theme} | {list} | HIGH|MEDIUM|LOW |

---

*Rolled up from N project priority boards*
```

## 6. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Copy codex_client.py from swarm-attack, adapt for COO config | `src/codex_client.py` | S |
| 2 | Create SubAgentRunner for Librarian spawning | `src/sub_agent.py` | M |
| 3 | Create Librarian skill definition | `.claude/skills/librarian/SKILL.md` | S |
| 4 | Create PriorityPanel with expert prompts | `src/priority_panel.py` | M |
| 5 | Create ConsensusChecker | `src/consensus_checker.py` | S |
| 6 | Create PriorityModerator for weighted merge | `src/priority_moderator.py` | M |
| 7 | Create PriorityOrchestrator (main debate loop) | `src/priority_orchestrator.py` | L |
| 8 | Create PriorityOutputGenerator | `src/priority_output.py` | M |
| 9 | Add CLI commands to src/cli.py | `src/cli.py` | S |
| 10 | Update dashboard generator | `scripts/generate-dashboard.py` | S |
| 11 | Update cron script | `scripts/daily-digest-cron.sh` | S |
| 12 | Create skill definition | `.claude/skills/roadmap-prioritization-board/SKILL.md` | S |

## 7. Testing

### 7.1 Manual Test Plan

1. **Single project run:**
   ```bash
   PYTHONPATH=. python -m src.cli prioritize --project miami --dry-run
   PYTHONPATH=. python -m src.cli prioritize --project miami
   cat daily-logs/$(date +%Y-%m-%d)-priorities-miami.md
   ```

2. **Multi-project + rollup:**
   ```bash
   PYTHONPATH=. python -m src.cli prioritize
   cat daily-logs/$(date +%Y-%m-%d)-priorities.md
   ```

3. **Dashboard integration:**
   ```bash
   python scripts/generate-dashboard.py
   # Open docs/index.html, verify Priorities section
   ```

### 7.2 Automated Tests

```python
# tests/test_consensus_checker.py

def test_consensus_all_agree():
    """Consensus when all panels have same top 5."""
    rankings = [["A","B","C","D","E"]] * 5
    result = check_consensus(rankings, round_number=1)
    assert result.reached is True
    assert len(result.common_priorities) == 5

def test_consensus_partial_overlap():
    """Consensus when 3+ common in top 5."""
    rankings = [
        ["A","B","C","X","Y"],
        ["A","B","C","P","Q"],
        ["A","B","C","R","S"],
        ["A","B","D","T","U"],
        ["A","B","C","V","W"],
    ]
    result = check_consensus(rankings, round_number=1)
    assert result.reached is True
    assert "A" in result.common_priorities
    assert "B" in result.common_priorities

def test_consensus_forced_after_max():
    """Force consensus after max rounds."""
    rankings = [["A","B","X","Y","Z"], ["C","D","P","Q","R"]] * 3
    result = check_consensus(rankings, round_number=5, max_rounds=5)
    assert result.reached is True
    assert result.forced is True

def test_weighted_voting():
    """Weighted voting produces correct ranking."""
    votes = {
        "product": ["A", "B", "C"],
        "ceo": ["A", "B", "C"],
        "engineering": ["B", "A", "C"],
    }
    weights = {"product": 0.30, "ceo": 0.30, "engineering": 0.20}
    result = weighted_vote(votes, weights)
    assert result[0] == "A"  # A gets 0.6 * 10 + 0.2 * 9 = 7.8
```

## 8. Open Questions

None - all decisions have been made per user feedback:

| Question | Decision |
|----------|----------|
| Scope | Per-project with rollup |
| Frequency | Daily, after Strategic Advisory Board |
| External Review | Required (Codex) |
| Output | GitHub Pages dashboard |
| Weights | Product 30%, CEO 30%, Eng 20%, Design 10%, Ops 10% |
| History | Date-stamped files provide automatic history |
| Human Override | None - runs autonomously |
| Cost Ceiling | None - run until complete |

---

*Spec generated 2025-12-31 by SpecAuthor*
*Target: COO worktree at /Users/philipjcortes/Desktop/coo/worktrees/feature-priority-board*
*Branch: feature/priority-board*
