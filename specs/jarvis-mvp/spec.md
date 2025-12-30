# Minimum Viable Jarvis: Technical Specification

## Executive Summary

Transform Chief of Staff from a "supervised task executor" into an "opinionated autonomous partner" by wiring together existing infrastructure with ~440 lines of new code.

**Core Principle:** The infrastructure exists. We're adding intelligence, not features.

---

## Prerequisites

**Already Implemented (DO NOT REBUILD):**
- `AutopilotRunner` - Sequential goal execution with recovery
- `CheckpointSystem` - 6-trigger checkpoint detection (UX_CHANGE, COST_*, ARCHITECTURE, SCOPE_CHANGE, HICCUP)
- `EpisodeStore` - Episode storage with `find_similar()`
- `PreferenceLearner` - Signal extraction with `find_similar_decisions()`
- `ProgressTracker` - Real-time progress snapshots
- `RecoveryManager` - 4-level recovery hierarchy
- `ValidationLayer` - Spec/Code/Test critics (not wired)
- `DependencyGraph` - Goal dependency tracking (not wired)
- `ExecutionStrategy.CONTINUE_ON_BLOCK` - Enum exists (not active)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AutopilotRunner.start()                  │
│                              │                               │
│    ┌─────────────────────────▼─────────────────────────┐    │
│    │           PHASE 1: Goal Selection                 │    │
│    │  ┌──────────────────────────────────────────────┐│    │
│    │  │ PrioritySelector.select_next()               ││    │
│    │  │ - Filter to ready goals (deps met)           ││    │
│    │  │ - Sort by: P1>P2>P3, cheaper first           ││    │
│    │  │ - Return highest priority ready goal         ││    │
│    │  └──────────────────────────────────────────────┘│    │
│    └───────────────────────────────────────────────────┘    │
│                              │                               │
│    ┌─────────────────────────▼─────────────────────────┐    │
│    │           PHASE 2: PreFlight Check                │    │
│    │  ┌──────────────────────────────────────────────┐│    │
│    │  │ PreFlightChecker.validate()                  ││    │
│    │  │ - RiskScoringEngine.score() → 0.0-1.0        ││    │
│    │  │ - If risk > 0.5: CHECKPOINT                  ││    │
│    │  │ - If risk > 0.8: BLOCK                       ││    │
│    │  │ - Else: AUTO_PROCEED                         ││    │
│    │  └──────────────────────────────────────────────┘│    │
│    └───────────────────────────────────────────────────┘    │
│                              │                               │
│    ┌─────────────────────────▼─────────────────────────┐    │
│    │           PHASE 3: Execution                      │    │
│    │  ┌──────────────────────────────────────────────┐│    │
│    │  │ Execute goal via orchestrator                ││    │
│    │  │ - On SUCCESS: mark complete, loop            ││    │
│    │  │ - On BLOCKED: mark blocked, continue others  ││    │
│    │  │ - On HICCUP: checkpoint, await decision      ││    │
│    │  └──────────────────────────────────────────────┘│    │
│    └───────────────────────────────────────────────────┘    │
│                              │                               │
│    ┌─────────────────────────▼─────────────────────────┐    │
│    │           PHASE 4: Continue-on-Block              │    │
│    │  ┌──────────────────────────────────────────────┐│    │
│    │  │ If goal blocked:                             ││    │
│    │  │ - Check DependencyGraph for ready goals      ││    │
│    │  │ - If ready goals exist: continue with next   ││    │
│    │  │ - If no ready goals: pause session           ││    │
│    │  └──────────────────────────────────────────────┘│    │
│    └───────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### Issue #19: RiskScoringEngine (~100 LOC)

**File:** `swarm_attack/chief_of_staff/risk_scoring.py`

**Purpose:** Calculate risk score 0.0-1.0 for any goal, enabling intelligent checkpoint decisions.

```python
"""Risk scoring engine for intelligent checkpoint decisions."""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.episodes import EpisodeStore, PreferenceLearner
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


@dataclass
class RiskAssessment:
    """Result of risk assessment for a goal."""

    score: float  # 0.0 (safe) to 1.0 (risky)
    factors: dict[str, float]  # Breakdown by factor
    recommendation: str  # "proceed", "checkpoint", "block"
    rationale: str  # Human-readable explanation

    @property
    def requires_checkpoint(self) -> bool:
        return self.recommendation in ("checkpoint", "block")

    @property
    def is_blocked(self) -> bool:
        return self.recommendation == "block"


class RiskScoringEngine:
    """
    Calculate nuanced risk scores for checkpoint decisions.

    Uses 5 weighted factors:
    - cost: Budget impact (30%)
    - scope: Files/paths affected (25%)
    - reversibility: Can we undo this? (20%)
    - precedent: Similar past episodes (15%)
    - confidence: Success rate of similar work (10%)
    """

    # Risk weights
    WEIGHTS = {
        "cost": 0.30,
        "scope": 0.25,
        "reversibility": 0.20,
        "precedent": 0.15,
        "confidence": 0.10,
    }

    # Thresholds
    CHECKPOINT_THRESHOLD = 0.5  # Score > 0.5 requires checkpoint
    BLOCK_THRESHOLD = 0.8  # Score > 0.8 blocks execution

    def __init__(
        self,
        episode_store: Optional["EpisodeStore"] = None,
        preference_learner: Optional["PreferenceLearner"] = None,
    ):
        self.episode_store = episode_store
        self.preference_learner = preference_learner

    def score(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> RiskAssessment:
        """
        Calculate comprehensive risk score for a goal.

        Args:
            goal: The goal to assess
            context: Execution context including:
                - session_budget: Total budget for session
                - spent_usd: Amount already spent
                - files_to_modify: List of file paths (if known)

        Returns:
            RiskAssessment with score, factors, and recommendation
        """
        factors = {}
        rationale_parts = []

        # Factor 1: Cost (30%)
        factors["cost"] = self._score_cost(goal, context)
        if factors["cost"] > 0.5:
            rationale_parts.append(
                f"High cost impact ({factors['cost']:.0%} of remaining budget)"
            )

        # Factor 2: Scope (25%)
        factors["scope"] = self._score_scope(goal, context)
        if factors["scope"] > 0.5:
            rationale_parts.append(
                f"Wide scope (affects {context.get('files_to_modify', ['unknown'])})"
            )

        # Factor 3: Reversibility (20%)
        factors["reversibility"] = self._score_reversibility(goal)
        if factors["reversibility"] > 0.5:
            rationale_parts.append("Contains irreversible operations")

        # Factor 4: Precedent (15%)
        factors["precedent"] = self._score_precedent(goal)
        if factors["precedent"] > 0.5:
            rationale_parts.append("No similar successful precedent")

        # Factor 5: Confidence (10%)
        factors["confidence"] = self._score_confidence(goal)
        if factors["confidence"] > 0.5:
            rationale_parts.append("Low confidence based on past outcomes")

        # Calculate weighted score
        score = sum(factors[k] * self.WEIGHTS[k] for k in factors)

        # Determine recommendation
        if score >= self.BLOCK_THRESHOLD:
            recommendation = "block"
        elif score >= self.CHECKPOINT_THRESHOLD:
            recommendation = "checkpoint"
        else:
            recommendation = "proceed"

        # Build rationale
        if not rationale_parts:
            rationale = "Low risk - no concerning factors detected"
        else:
            rationale = "; ".join(rationale_parts)

        return RiskAssessment(
            score=score,
            factors=factors,
            recommendation=recommendation,
            rationale=rationale,
        )

    def _score_cost(self, goal: "DailyGoal", context: dict) -> float:
        """Score based on budget impact."""
        session_budget = context.get("session_budget", 25.0)
        spent = context.get("spent_usd", 0.0)
        remaining = max(session_budget - spent, 0.01)

        estimated_cost = goal.estimated_cost_usd or 0.0

        # Cost as fraction of remaining budget
        cost_ratio = estimated_cost / remaining

        # 30% of remaining = 0.5 risk, 60% = 1.0 risk
        return min(1.0, cost_ratio / 0.6)

    def _score_scope(self, goal: "DailyGoal", context: dict) -> float:
        """Score based on scope of changes."""
        files = context.get("files_to_modify", [])

        # Check for core paths
        core_patterns = ["core/", "models/", "api/", "auth/", "database/"]
        affects_core = any(
            any(pattern in f for pattern in core_patterns)
            for f in files
        )

        # Base score on file count
        file_score = min(1.0, len(files) / 10)  # 10+ files = 1.0

        # Add 0.3 if affects core paths
        if affects_core:
            file_score = min(1.0, file_score + 0.3)

        return file_score

    def _score_reversibility(self, goal: "DailyGoal") -> float:
        """Score based on reversibility of operations."""
        description = goal.description.lower()

        # Irreversible keywords
        irreversible = ["delete", "drop", "remove", "destroy", "reset", "migrate"]
        if any(kw in description for kw in irreversible):
            return 1.0

        # External/publish keywords
        external = ["deploy", "publish", "push", "release", "send", "email"]
        if any(kw in description for kw in external):
            return 0.7

        return 0.2  # Default: reversible

    def _score_precedent(self, goal: "DailyGoal") -> float:
        """Score based on similar past episodes."""
        if not self.episode_store:
            return 0.5  # Unknown

        similar = self.episode_store.find_similar(goal.description, k=5)

        if not similar:
            return 0.6  # No precedent = slightly risky

        # Check success rate
        successes = sum(1 for ep in similar if ep.success)
        success_rate = successes / len(similar)

        # High success rate = low risk
        return 1.0 - success_rate

    def _score_confidence(self, goal: "DailyGoal") -> float:
        """Score based on past decision patterns."""
        if not self.preference_learner:
            return 0.5  # Unknown

        similar_decisions = self.preference_learner.find_similar_decisions(goal, k=3)

        if not similar_decisions:
            return 0.5  # No history

        # Check approval rate
        approvals = sum(1 for d in similar_decisions if d.get("was_accepted", False))
        approval_rate = approvals / len(similar_decisions)

        # High approval rate = low risk
        return 1.0 - approval_rate
```

---

### Issue #20: PreFlightChecker (~80 LOC)

**File:** `swarm_attack/chief_of_staff/preflight.py`

**Purpose:** Validate goals BEFORE execution starts, catching issues early.

```python
"""Pre-flight validation before goal execution."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal
    from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine, RiskAssessment


@dataclass
class PreFlightIssue:
    """An issue detected during pre-flight check."""
    severity: str  # "critical", "warning", "info"
    category: str  # "budget", "dependency", "risk", "conflict"
    message: str
    suggested_action: Optional[str] = None


@dataclass
class PreFlightResult:
    """Result of pre-flight validation."""
    passed: bool
    issues: list[PreFlightIssue] = field(default_factory=list)
    risk_assessment: Optional["RiskAssessment"] = None

    # Checkpoint control
    requires_checkpoint: bool = False
    auto_approved: bool = False

    def summary(self) -> str:
        """Generate human-readable summary."""
        if self.passed and not self.requires_checkpoint:
            return f"PASSED (risk: {self.risk_assessment.score:.2f})"
        elif self.requires_checkpoint:
            return f"CHECKPOINT REQUIRED: {self.risk_assessment.rationale}"
        else:
            critical = [i for i in self.issues if i.severity == "critical"]
            return f"BLOCKED: {critical[0].message}" if critical else "BLOCKED"


class PreFlightChecker:
    """
    Validate goals before execution to catch issues early.

    Checks:
    1. Budget sufficiency
    2. Dependency availability
    3. Risk assessment
    4. Conflict detection (optional)
    """

    def __init__(
        self,
        risk_engine: "RiskScoringEngine",
    ):
        self.risk_engine = risk_engine

    def validate(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> PreFlightResult:
        """
        Run all pre-execution validations.

        Args:
            goal: Goal to validate
            context: Execution context including:
                - session_budget: Total budget
                - spent_usd: Amount spent
                - completed_goals: Set of completed goal IDs
                - blocked_goals: Set of blocked goal IDs

        Returns:
            PreFlightResult with pass/fail and issues
        """
        issues = []

        # Check 1: Budget sufficiency
        budget_issue = self._check_budget(goal, context)
        if budget_issue:
            issues.append(budget_issue)

        # Check 2: Dependencies
        dep_issue = self._check_dependencies(goal, context)
        if dep_issue:
            issues.append(dep_issue)

        # Check 3: Risk assessment
        risk = self.risk_engine.score(goal, context)

        # Determine outcome
        has_critical = any(i.severity == "critical" for i in issues)

        if has_critical:
            return PreFlightResult(
                passed=False,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=False,
                auto_approved=False,
            )

        if risk.is_blocked:
            issues.append(PreFlightIssue(
                severity="critical",
                category="risk",
                message=f"Risk score {risk.score:.2f} exceeds block threshold",
                suggested_action="Break into smaller tasks or get explicit approval",
            ))
            return PreFlightResult(
                passed=False,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=True,
                auto_approved=False,
            )

        if risk.requires_checkpoint:
            return PreFlightResult(
                passed=True,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=True,
                auto_approved=False,
            )

        # Low risk - auto-approve
        return PreFlightResult(
            passed=True,
            issues=issues,
            risk_assessment=risk,
            requires_checkpoint=False,
            auto_approved=True,
        )

    def _check_budget(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> Optional[PreFlightIssue]:
        """Check if budget is sufficient."""
        session_budget = context.get("session_budget", 25.0)
        spent = context.get("spent_usd", 0.0)
        remaining = session_budget - spent

        estimated = goal.estimated_cost_usd or 0.0

        if estimated > remaining:
            return PreFlightIssue(
                severity="critical",
                category="budget",
                message=f"Estimated ${estimated:.2f} exceeds remaining ${remaining:.2f}",
                suggested_action="Increase budget or reduce scope",
            )

        if estimated > remaining * 0.8:
            return PreFlightIssue(
                severity="warning",
                category="budget",
                message=f"Will use {estimated/remaining*100:.0f}% of remaining budget",
                suggested_action="Consider reserving budget for other goals",
            )

        return None

    def _check_dependencies(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> Optional[PreFlightIssue]:
        """Check if dependencies are satisfied."""
        completed = context.get("completed_goals", set())
        blocked = context.get("blocked_goals", set())

        # Get dependencies from goal (if available)
        dependencies = getattr(goal, "dependencies", []) or []

        for dep_id in dependencies:
            if dep_id in blocked:
                return PreFlightIssue(
                    severity="critical",
                    category="dependency",
                    message=f"Depends on blocked goal: {dep_id}",
                    suggested_action="Resolve blocker first or remove dependency",
                )

            if dep_id not in completed:
                return PreFlightIssue(
                    severity="critical",
                    category="dependency",
                    message=f"Depends on incomplete goal: {dep_id}",
                    suggested_action="Complete dependency first",
                )

        return None
```

---

### Issue #28-29: Continue-on-Block Loop (~75 LOC)

**File:** Modify `swarm_attack/chief_of_staff/autopilot_runner.py`

**Purpose:** When a goal blocks, continue with other ready goals instead of stopping.

```python
# Add to autopilot_runner.py

from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
from swarm_attack.chief_of_staff.preflight import PreFlightChecker


class AutopilotRunner:
    """Enhanced with continue-on-block and preflight checks."""

    def __init__(self, ...):
        # ... existing init ...

        # NEW: Risk and preflight
        self.risk_engine = RiskScoringEngine(
            episode_store=self.episode_store,
            preference_learner=self.preference_learner,
        )
        self.preflight = PreFlightChecker(self.risk_engine)

    def start(
        self,
        goals: list["DailyGoal"],
        budget_usd: float = 25.0,
        **kwargs,
    ) -> "AutopilotResult":
        """
        Execute goals with continue-on-block strategy.

        Instead of stopping on first blocker, continues with
        other ready goals that don't depend on blocked work.
        """
        completed: set[str] = set()
        blocked: set[str] = set()
        total_cost = 0.0
        checkpoints_used = 0  # NEW: Track checkpoint budget

        # Build execution context
        context = {
            "session_budget": budget_usd,
            "spent_usd": 0.0,
            "completed_goals": completed,
            "blocked_goals": blocked,
        }

        while True:
            # Select next ready goal
            ready_goals = self._get_ready_goals(goals, completed, blocked)

            if not ready_goals:
                break  # No more ready goals

            # Pick highest priority
            goal = self._select_next(ready_goals)

            # PreFlight check
            context["spent_usd"] = total_cost
            preflight_result = self.preflight.validate(goal, context)

            if not preflight_result.passed:
                # Mark as blocked, continue with others
                blocked.add(goal.goal_id)
                self._emit_preflight_blocked(goal, preflight_result)
                continue

            if preflight_result.requires_checkpoint:
                # Check checkpoint budget
                if checkpoints_used >= self.config.checkpoint_budget:
                    # Budget exhausted - log but don't pause
                    self._log_checkpoint_skipped(goal, preflight_result, "budget exhausted")
                else:
                    # Pause for human approval
                    checkpoint = self._create_preflight_checkpoint(goal, preflight_result)
                    checkpoints_used += 1
                    if not await self._await_checkpoint(checkpoint):
                        blocked.add(goal.goal_id)
                        continue

            # Execute the goal
            result = self._execute_goal(goal)

            if result.success:
                completed.add(goal.goal_id)
                total_cost += result.cost_usd
            else:
                # Mark blocked, continue with others (CONTINUE-ON-BLOCK)
                blocked.add(goal.goal_id)
                self._emit_goal_blocked(goal, result.error)

                # Check if we should continue
                if self.config.execution_strategy != ExecutionStrategy.CONTINUE_ON_BLOCK:
                    break  # Old behavior: stop on first failure

        return AutopilotResult(
            goals_completed=len(completed),
            goals_blocked=len(blocked),
            goals_total=len(goals),
            total_cost_usd=total_cost,
            blocked_goals=list(blocked),
        )

    def _get_ready_goals(
        self,
        goals: list["DailyGoal"],
        completed: set[str],
        blocked: set[str],
    ) -> list["DailyGoal"]:
        """Get goals that are ready to execute (deps met, not blocked)."""
        ready = []

        for goal in goals:
            # Skip completed or blocked
            if goal.goal_id in completed or goal.goal_id in blocked:
                continue

            # Check dependencies
            deps = getattr(goal, "dependencies", []) or []
            deps_met = all(d in completed for d in deps)
            deps_blocked = any(d in blocked for d in deps)

            if deps_blocked:
                # Transitively blocked
                blocked.add(goal.goal_id)
                continue

            if deps_met:
                ready.append(goal)

        return ready

    def _select_next(self, ready_goals: list["DailyGoal"]) -> "DailyGoal":
        """Select highest priority goal from ready goals."""
        # Priority order: P1 > P2 > P3, then cheaper first
        priority_order = {"high": 0, "medium": 1, "low": 2}

        return min(
            ready_goals,
            key=lambda g: (
                priority_order.get(g.priority.value, 1),
                g.estimated_cost_usd or 0,
            ),
        )

    def _create_preflight_checkpoint(
        self,
        goal: "DailyGoal",
        preflight: "PreFlightResult",
    ) -> "Checkpoint":
        """Create checkpoint for preflight approval."""
        risk = preflight.risk_assessment

        # NEW: Get similar past decisions to inform user
        similar_context = ""
        if self.config.show_similar_decisions and self.preference_learner:
            similar = self.preference_learner.find_similar_decisions(goal, k=3)
            if similar:
                similar_context = "\n\n**Similar Past Decisions:**\n"
                for dec in similar:
                    outcome = "✓" if dec.get("was_accepted") else "✗"
                    similar_context += f"  {outcome} {dec.get('trigger', 'unknown')}: {dec.get('chosen_option', 'N/A')}\n"

        return Checkpoint(
            checkpoint_id=f"preflight-{goal.goal_id}",
            trigger=CheckpointTrigger.SCOPE_CHANGE,
            goal_id=goal.goal_id,
            context=f"PreFlight Check: {risk.rationale}{similar_context}",
            options=[
                CheckpointOption(
                    label="Proceed",
                    description=f"Execute despite risk score {risk.score:.2f}",
                    is_recommended=risk.score < 0.7,
                ),
                CheckpointOption(
                    label="Skip",
                    description="Skip this goal, continue with others",
                    is_recommended=False,
                ),
                CheckpointOption(
                    label="Pause",
                    description="Pause session for manual review",
                    is_recommended=risk.score >= 0.7,
                ),
            ],
            recommendation=f"Risk: {risk.score:.2f} - {risk.recommendation}",
            created_at=datetime.now().isoformat(),
        )
```

---

### Issue #30: Execution Strategy Config (~20 LOC)

**File:** Modify `swarm_attack/chief_of_staff/config.py`

```python
# Add to config.py

class AutopilotConfig:
    """Configuration for autopilot execution."""

    # ... existing fields ...

    # NEW: Execution strategy
    execution_strategy: ExecutionStrategy = ExecutionStrategy.CONTINUE_ON_BLOCK

    # NEW: Risk thresholds
    risk_checkpoint_threshold: float = 0.5  # Score > this requires checkpoint
    risk_block_threshold: float = 0.8  # Score > this blocks execution

    # NEW: Auto-approve low-risk
    auto_approve_low_risk: bool = True  # If True, skip checkpoint for risk < 0.3

    # NEW: Checkpoint budget (per session) - limits interruptions
    checkpoint_budget: int = 3  # Max checkpoints before auto-logging instead of pausing

    # NEW: Show similar decisions in checkpoint context
    show_similar_decisions: bool = True  # Include past similar decisions in checkpoint
```

---

### Issue #32-33: Progress CLI (~60 LOC)

**File:** Modify `swarm_attack/cli/chief_of_staff.py`

```python
# Add to chief_of_staff.py

@app.command("progress")
def progress_command(
    history: bool = typer.Option(False, "--history", "-H", help="Show progress history"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode (refresh every 5s)"),
) -> None:
    """Show current autopilot progress.

    Displays:
    - Goals completed/blocked/remaining
    - Current goal in progress
    - Cost spent vs budget
    - Blockers with reasons

    Use --history to see progress over time.
    Use --watch for live updates during execution.
    """
    console = get_console()
    tracker = _get_progress_tracker()
    tracker.load()

    def render_progress():
        current = tracker.get_current()

        if current is None:
            console.print("[dim]No active session. Run 'cos autopilot' to start.[/dim]")
            return

        # Header
        console.print(Panel(
            f"[bold]Autopilot Progress[/bold]",
            style="cyan",
        ))

        # Progress bar
        pct = current.completion_percent
        bar_filled = int(pct / 5)  # 20 chars total
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        color = "green" if pct >= 75 else "yellow" if pct >= 50 else "red"
        console.print(f"\n[{color}]{bar}[/{color}] {pct:.0f}%")

        # Stats
        console.print(f"\nGoals: {current.goals_completed}/{current.goals_total}")
        console.print(f"Cost: ${current.cost_usd:.2f}")
        console.print(f"Duration: {current.duration_seconds // 60}m {current.duration_seconds % 60}s")

        # Current goal
        if current.current_goal:
            console.print(f"\n[bold]Current:[/bold] {current.current_goal}")

        # Blockers
        if current.blockers:
            console.print(f"\n[bold red]Blockers ({len(current.blockers)}):[/bold red]")
            for blocker in current.blockers:
                console.print(f"  [red]![/red] {blocker}")

    if watch:
        from rich.live import Live
        import time

        with Live(console=console, refresh_per_second=0.2) as live:
            while True:
                render_progress()
                time.sleep(5)
                console.clear()
    elif history:
        # Show history table
        history_entries = tracker.get_history()

        if not history_entries:
            console.print("[dim]No history available.[/dim]")
            return

        table = Table()
        table.add_column("Time", style="cyan")
        table.add_column("Progress", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Status")

        for snap in history_entries[-20:]:  # Last 20
            ts = snap.timestamp[:19]
            pct = f"{snap.completion_percent:.0f}%"
            cost = f"${snap.cost_usd:.2f}"
            status = snap.current_goal or "idle"

            table.add_row(ts, pct, cost, status[:40])

        console.print(table)
    else:
        render_progress()
```

---

### Issue #31: Tests (~25 LOC core assertions)

**File:** `tests/chief_of_staff/test_risk_scoring.py`

```python
"""Tests for RiskScoringEngine and PreFlightChecker."""

import pytest
from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine, RiskAssessment
from swarm_attack.chief_of_staff.preflight import PreFlightChecker, PreFlightResult
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority


class TestRiskScoringEngine:
    """Tests for risk scoring."""

    def test_low_risk_goal_scores_low(self):
        """Simple goal with low cost should score low."""
        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-1",
            description="Fix typo in README",
            priority=GoalPriority.LOW,
            estimated_minutes=5,
            estimated_cost_usd=0.50,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.score < 0.3
        assert result.recommendation == "proceed"

    def test_high_cost_goal_scores_high(self):
        """Goal using most of budget should score high."""
        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-2",
            description="Implement auth system",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            estimated_cost_usd=20.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.score > 0.5
        assert result.recommendation in ("checkpoint", "block")

    def test_irreversible_action_scores_high(self):
        """Delete/destroy keywords should increase risk."""
        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-3",
            description="Delete old user accounts",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            estimated_cost_usd=2.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.factors["reversibility"] == 1.0
        assert "irreversible" in result.rationale.lower()


class TestPreFlightChecker:
    """Tests for pre-flight validation."""

    def test_budget_exceeded_fails(self):
        """Goal exceeding budget should fail preflight."""
        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-4",
            description="Expensive task",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=30.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = checker.validate(goal, context)

        assert not result.passed
        assert any(i.category == "budget" for i in result.issues)

    def test_low_risk_auto_approved(self):
        """Low-risk goal should auto-approve."""
        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-5",
            description="Update docs",
            priority=GoalPriority.LOW,
            estimated_minutes=10,
            estimated_cost_usd=1.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = checker.validate(goal, context)

        assert result.passed
        assert result.auto_approved
        assert not result.requires_checkpoint

    def test_medium_risk_requires_checkpoint(self):
        """Medium-risk goal should require checkpoint."""
        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-6",
            description="Refactor core auth module",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=10.0,
        )

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": ["core/auth.py", "core/session.py"],
        }
        result = checker.validate(goal, context)

        assert result.passed
        assert result.requires_checkpoint
        assert not result.auto_approved
```

---

## Integration Points

### Wire into AutopilotRunner

```python
# In AutopilotRunner.__init__():

def __init__(self, config, checkpoint_system, session_store, orchestrator, bug_orchestrator):
    # ... existing init ...

    # NEW: Initialize risk scoring and preflight
    self.risk_engine = RiskScoringEngine(
        episode_store=getattr(self, 'episode_store', None),
        preference_learner=getattr(checkpoint_system, 'preference_learner', None),
    )
    self.preflight = PreFlightChecker(self.risk_engine)
```

### Wire into CheckpointSystem

```python
# In CheckpointSystem.check_before_execution():

async def check_before_execution(
    self,
    goal: "DailyGoal",
    context: Optional[dict] = None,
) -> "CheckpointResult":
    """Check if execution should proceed, with preflight integration."""

    # NEW: Run preflight first if context provided
    if context and hasattr(self, 'preflight'):
        preflight_result = self.preflight.validate(goal, context)

        if not preflight_result.passed:
            return CheckpointResult(
                requires_approval=True,
                approved=False,
                reason=preflight_result.summary(),
            )

        if preflight_result.auto_approved:
            return CheckpointResult(
                requires_approval=False,
                approved=True,
            )

    # ... existing trigger detection ...
```

---

## CLI Commands

### New Commands

```bash
# Progress monitoring
swarm-attack cos progress           # Current snapshot
swarm-attack cos progress --history # History table
swarm-attack cos progress --watch   # Live updates (5s refresh)
```

### Enhanced Autopilot Output

```bash
$ swarm-attack cos autopilot --budget 25

⚡ Starting autopilot (budget: $25.00)

━━━ Goal 1: Fix auth bug ━━━
   PreFlight: PASSED (risk: 0.32)
   Executing...
   ✓ Complete ($3.50)

━━━ Goal 2: Refactor database layer ━━━
   PreFlight: CHECKPOINT (risk: 0.58)
   - High scope (affects core/database.py)
   - 40% of remaining budget

   ❓ Proceed? [Y/n/skip] y
   Executing...
   ✓ Complete ($8.20)

━━━ Goal 3: Add dashboard widget ━━━
   PreFlight: PASSED (risk: 0.21)
   Executing...
   ⚠ BLOCKED: Missing /api/stats endpoint

   🔄 Continuing with other goals...

━━━ Goal 4: Update docs ━━━
   PreFlight: AUTO-APPROVED (risk: 0.12)
   Executing...
   ✓ Complete ($0.80)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SESSION COMPLETE

Goals: 3/4 complete, 1 blocked
Cost: $12.50 / $25.00
Blocked: dashboard (missing API)

Run 'cos progress' to monitor or 'cos unblock' to resolve.
```

---

## File Summary

| File | Action | LOC |
|------|--------|-----|
| `swarm_attack/chief_of_staff/risk_scoring.py` | NEW | ~100 |
| `swarm_attack/chief_of_staff/preflight.py` | NEW | ~80 |
| `swarm_attack/chief_of_staff/autopilot_runner.py` | MODIFY | ~90 |
| `swarm_attack/chief_of_staff/config.py` | MODIFY | ~25 |
| `swarm_attack/cli/chief_of_staff.py` | MODIFY | ~60 |
| `tests/chief_of_staff/test_risk_scoring.py` | NEW | ~80 |
| **TOTAL** | | **~435** |

---

## Expert Team Additions (Post-Review)

Based on analysis by the expert panel (Shunyu Yao, Scott Wu, Harrison Chase):

1. **Checkpoint Budget** (Scott Wu/Devin pattern):
   - Added `checkpoint_budget: int = 3` to config
   - When exhausted, log instead of pause (avoids trust death spiral)

2. **Similar Decisions in Context** (Harrison Chase/LangChain pattern):
   - Added `show_similar_decisions: bool = True` to config
   - Checkpoints now show past similar decisions with outcomes
   - Users see "2 similar past decisions: 1 approved, 1 rejected"

3. **Reasoning Traces** (Shunyu Yao/ReAct pattern):
   - Risk rationale is explicit and human-readable
   - Each checkpoint shows WHY it triggered, not just THAT it triggered

---

## Success Criteria

1. **PreFlight blocks over-budget goals** - Cannot start a goal that exceeds remaining budget
2. **Risk scoring produces meaningful scores** - Irreversible actions score higher than safe ones
3. **Continue-on-block works** - When goal A blocks, goals B/C/D continue if they don't depend on A
4. **Progress CLI shows real data** - `cos progress` displays current goal, completion %, blockers
5. **Low-risk auto-approves** - Goals with risk < 0.3 proceed without checkpoint
6. **Medium-risk checkpoints** - Goals with risk 0.3-0.7 pause for approval with rationale
7. **High-risk blocks** - Goals with risk > 0.8 require explicit unblock

---

## What This Enables

After implementation, Jarvis can:

1. **Give opinions** - "This is risky because it affects core paths and uses 40% of budget"
2. **Push back** - "I'm not starting this until you approve - risk score 0.72"
3. **Continue autonomously** - "Goal A blocked, but B and C don't depend on it, continuing..."
4. **Show progress** - Real-time visibility into what's happening
5. **Learn over time** - Risk scores improve as EpisodeStore and PreferenceLearner accumulate data

**This is Minimum Viable Jarvis: an opinionated partner, not a blind executor.**
