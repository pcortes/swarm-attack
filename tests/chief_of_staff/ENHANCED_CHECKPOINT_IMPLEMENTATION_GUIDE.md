# Enhanced Checkpoint Format - Implementation Guide

## Overview

This guide documents the implementation approach for **Issue #39: Enhanced Checkpoint Format**. The TDD tests in `test_enhanced_checkpoint.py` define the expected behavior. This document provides the implementation roadmap to move from RED → GREEN → REFACTOR.

## Current State vs. Target State

### Current Implementation (Basic)
The current `checkpoint_ux.py` provides:
- Basic blocking prompts with numbered options
- Trigger type display (HICCUP, UX_CHANGE, etc.)
- Context description
- Simple recommendation text
- User input handling with reprompting

### Target Implementation (Enhanced)
The enhanced version will add:
1. **Tradeoffs per option** - Pros/cons, cost impact, risk level for each choice
2. **Similar past decisions** - Show 2-3 relevant historical decisions from PreferenceLearner
3. **Progress context** - Display session progress, budget status, and estimated runway

## Implementation Roadmap

### Phase 1: Enhanced CheckpointOption

**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoint_ux.py`

**Create**: `EnhancedCheckpointOption` dataclass

```python
@dataclass
class EnhancedCheckpointOption:
    """Enhanced checkpoint option with tradeoffs and risk information.

    Extends the basic CheckpointOption with additional decision-making context
    including pros/cons, cost impact, and risk level.
    """

    label: str
    description: str
    is_recommended: bool = False

    # Enhanced fields (Issue #39)
    tradeoffs: dict[str, list[str]] = field(default_factory=lambda: {"pros": [], "cons": []})
    estimated_cost_impact: Optional[float] = None  # USD delta (+ = additional cost, - = savings)
    risk_level: str = "medium"  # "low", "medium", "high"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "label": self.label,
            "description": self.description,
            "is_recommended": self.is_recommended,
            "tradeoffs": self.tradeoffs,
            "estimated_cost_impact": self.estimated_cost_impact,
            "risk_level": self.risk_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnhancedCheckpointOption":
        """Deserialize from dictionary."""
        return cls(
            label=data["label"],
            description=data["description"],
            is_recommended=data.get("is_recommended", False),
            tradeoffs=data.get("tradeoffs", {"pros": [], "cons": []}),
            estimated_cost_impact=data.get("estimated_cost_impact"),
            risk_level=data.get("risk_level", "medium"),
        )
```

**Tests to pass**:
- `test_option_has_tradeoffs`
- `test_option_has_estimated_cost`
- `test_option_has_risk_level`
- `test_enhanced_option_backward_compatible`

### Phase 2: Similar Past Decisions Integration

**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoint_ux.py`

**Modify**: `CheckpointUX` class

```python
class CheckpointUX:
    """Interactive checkpoint UX that blocks until user decides.

    Enhanced version includes similar past decisions and progress context
    for richer decision-making experience.
    """

    def __init__(
        self,
        preference_learner: Optional["PreferenceLearner"] = None,
        session: Optional["AutopilotSession"] = None,
    ):
        """Initialize CheckpointUX.

        Args:
            preference_learner: Optional PreferenceLearner for showing similar past decisions.
            session: Optional AutopilotSession for showing progress context.
        """
        self.preference_learner = preference_learner
        self.session = session

    def format_checkpoint(
        self,
        checkpoint: Checkpoint,
        goal: Optional[Any] = None,
        session: Optional["AutopilotSession"] = None,
    ) -> str:
        """Format checkpoint for display with enhanced features.

        Args:
            checkpoint: The checkpoint to format.
            goal: Optional DailyGoal for similar decision lookup.
            session: Optional AutopilotSession for progress display (overrides self.session).

        Returns:
            Formatted string with sections:
            - Header (trigger type)
            - Progress context (if session available)
            - Context description
            - Similar past decisions (if preference_learner and goal available)
            - Options with tradeoffs
            - Recommendation
        """
        lines = []

        # Header with trigger type
        trigger_name = checkpoint.trigger.value if hasattr(checkpoint.trigger, 'value') else str(checkpoint.trigger)
        lines.append(f"⚠️  {trigger_name} Checkpoint")
        lines.append("━" * 60)
        lines.append("")

        # Progress context section (if session available)
        session_to_use = session or self.session
        if session_to_use:
            progress_section = self._format_progress_context(session_to_use)
            if progress_section:
                lines.append(progress_section)
                lines.append("")

        # Context
        lines.append(checkpoint.context)
        lines.append("")

        # Similar past decisions section (if available)
        if self.preference_learner and goal:
            similar_section = self._format_similar_decisions(goal)
            if similar_section:
                lines.append(similar_section)
                lines.append("")

        # Options
        lines.append("Options:")
        for i, option in enumerate(checkpoint.options, start=1):
            option_text = self._format_option(option, i)
            lines.append(option_text)

        # Recommendation
        lines.append("")
        lines.append(f"Recommendation: {checkpoint.recommendation}")

        return "\n".join(lines)
```

**Add helper methods**:

```python
def _format_similar_decisions(self, goal: Any) -> str:
    """Format similar past decisions section.

    Args:
        goal: DailyGoal with tags for similarity matching.

    Returns:
        Formatted section showing 2-3 similar past decisions, or empty string if none.
    """
    if not self.preference_learner:
        return ""

    similar = self.preference_learner.find_similar_decisions(goal, k=3)

    if not similar:
        return "Similar Past Decisions: None (first time seeing this scenario)"

    lines = ["Similar Past Decisions:"]
    for decision in similar[:3]:  # Limit to top 3
        outcome = "✓ Approved" if decision.get("was_accepted") else "✗ Rejected"
        trigger = decision.get("trigger", "Unknown")
        context = decision.get("context_summary", "")[:80]  # Truncate

        lines.append(f"  • {outcome} - {trigger}: {context}...")

    return "\n".join(lines)

def _format_option(self, option: Any, number: int) -> str:
    """Format a single option with tradeoffs if available.

    Args:
        option: CheckpointOption or EnhancedCheckpointOption.
        number: Option number (1-indexed).

    Returns:
        Formatted option string with tradeoffs, cost, and risk if available.
    """
    # Check if this is an EnhancedCheckpointOption
    has_tradeoffs = hasattr(option, 'tradeoffs') and option.tradeoffs
    has_cost = hasattr(option, 'estimated_cost_impact') and option.estimated_cost_impact is not None
    has_risk = hasattr(option, 'risk_level')

    recommended_marker = " (recommended)" if option.is_recommended else ""

    lines = [f"  [{number}] {option.label} - {option.description}{recommended_marker}"]

    # Add tradeoffs if available
    if has_tradeoffs:
        pros = option.tradeoffs.get("pros", [])
        cons = option.tradeoffs.get("cons", [])

        if pros:
            lines.append(f"      Pros: {', '.join(pros)}")
        if cons:
            lines.append(f"      Cons: {', '.join(cons)}")

    # Add cost impact if available
    if has_cost:
        cost = option.estimated_cost_impact
        cost_str = f"+${cost:.2f}" if cost > 0 else f"${cost:.2f}" if cost < 0 else "No cost"
        lines.append(f"      Cost impact: {cost_str}")

    # Add risk level if available
    if has_risk:
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(option.risk_level, "⚪")
        lines.append(f"      Risk: {risk_emoji} {option.risk_level.capitalize()}")

    return "\n".join(lines)
```

**Tests to pass**:
- `test_checkpoint_ux_accepts_preference_learner`
- `test_includes_similar_decisions`
- `test_shows_decision_outcome`
- `test_similar_decisions_limited_to_top_results`
- `test_no_similar_decisions_message`

### Phase 3: Progress Context Display

**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoint_ux.py`

**Add helper method**:

```python
def _format_progress_context(self, session: "AutopilotSession") -> str:
    """Format session progress context.

    Args:
        session: AutopilotSession with goals and budget info.

    Returns:
        Formatted progress section showing completed goals, budget, and runway.
    """
    lines = ["Session Progress:"]

    # Goals completed
    total_goals = len(session.goals)
    completed_goals = sum(1 for g in session.goals if g.get("status") == "completed")
    current_goal_idx = session.current_goal_index

    if total_goals > 0:
        current_goal = session.goals[current_goal_idx] if current_goal_idx < total_goals else None
        current_desc = current_goal.get("description", "Unknown") if current_goal else "None"
        lines.append(f"  Goals: {completed_goals}/{total_goals} completed (current: {current_desc[:40]}...)")

    # Budget status
    spent = session.total_cost_usd
    budget = session.budget_usd

    if budget:
        remaining = budget - spent
        percent_used = (spent / budget * 100) if budget > 0 else 0
        lines.append(f"  Budget: ${spent:.2f} / ${budget:.2f} spent (${remaining:.2f} remaining, {percent_used:.0f}% used)")

        # Estimated runway
        if completed_goals > 0:
            avg_cost_per_goal = spent / completed_goals
            estimated_remaining_goals = int(remaining / avg_cost_per_goal) if avg_cost_per_goal > 0 else 0
            lines.append(f"  Estimated runway: ~{estimated_remaining_goals} more goals at current burn rate")
    else:
        lines.append(f"  Cost so far: ${spent:.2f}")

    return "\n".join(lines)
```

**Tests to pass**:
- `test_checkpoint_ux_accepts_session`
- `test_includes_session_progress`
- `test_shows_budget_remaining`
- `test_shows_estimated_runway`
- `test_progress_context_optional`

### Phase 4: Integration and Polish

**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoints.py`

**Update**: `CheckpointSystem._build_options()` to create `EnhancedCheckpointOption` instances

```python
def _build_options(self, goal: "DailyGoal", trigger: CheckpointTrigger) -> list[CheckpointOption]:
    """Build enhanced options for a checkpoint.

    Creates EnhancedCheckpointOption instances with tradeoffs, cost estimates,
    and risk levels based on the trigger type and goal context.

    Args:
        goal: The DailyGoal triggering the checkpoint.
        trigger: The trigger type.

    Returns:
        List of EnhancedCheckpointOption instances with context-aware tradeoffs.
    """
    from swarm_attack.chief_of_staff.checkpoint_ux import EnhancedCheckpointOption

    # Estimate cost for "Proceed" option
    proceed_cost = goal.estimated_cost_usd if goal.estimated_cost_usd else 0.0

    # Build tradeoffs based on trigger type
    if trigger == CheckpointTrigger.HICCUP:
        proceed_pros = ["May succeed on retry", "Maintains progress momentum"]
        proceed_cons = ["May fail again", "Consumes budget on uncertain outcome"]
        proceed_risk = "medium"

        skip_pros = ["Saves budget for other goals", "Avoids repeated failures"]
        skip_cons = ["Goal remains incomplete", "May require manual intervention later"]
        skip_risk = "low"

    elif trigger == CheckpointTrigger.COST_SINGLE or trigger == CheckpointTrigger.COST_CUMULATIVE:
        proceed_pros = ["Completes planned work", "Goal may be high-value"]
        proceed_cons = ["High cost impact", "Reduces budget for remaining goals"]
        proceed_risk = "high"

        skip_pros = ["Preserves budget", "Can tackle lower-cost goals instead"]
        skip_cons = ["Work remains incomplete", "May be critical functionality"]
        skip_risk = "low"

    elif trigger == CheckpointTrigger.UX_CHANGE:
        proceed_pros = ["Implements planned UX improvement", "Enhances user experience"]
        proceed_cons = ["May affect existing user workflows", "Requires validation"]
        proceed_risk = "medium"

        skip_pros = ["Avoids user-facing changes", "Reduces UX risk"]
        skip_cons = ["UX improvement not delivered", "User pain point persists"]
        skip_risk = "low"

    elif trigger == CheckpointTrigger.ARCHITECTURE:
        proceed_pros = ["Implements architectural improvement", "Long-term code quality"]
        proceed_cons = ["Wide-reaching changes", "Potential for subtle bugs"]
        proceed_risk = "high"

        skip_pros = ["Avoids architectural risk", "Maintains stability"]
        skip_cons = ["Technical debt accumulates", "May be harder to change later"]
        skip_risk = "low"

    else:  # SCOPE_CHANGE or other
        proceed_pros = ["Addresses emergent need", "May be important work"]
        proceed_cons = ["Deviates from plan", "May indicate scope creep"]
        proceed_risk = "medium"

        skip_pros = ["Maintains focus on planned work", "Controls scope"]
        skip_cons = ["Emergent need unaddressed", "May resurface later"]
        skip_risk = "low"

    return [
        EnhancedCheckpointOption(
            label="Proceed",
            description="Continue with the goal as planned.",
            is_recommended=True,
            tradeoffs={"pros": proceed_pros, "cons": proceed_cons},
            estimated_cost_impact=proceed_cost,
            risk_level=proceed_risk,
        ),
        EnhancedCheckpointOption(
            label="Skip",
            description="Skip this goal and move to the next one.",
            is_recommended=False,
            tradeoffs={"pros": skip_pros, "cons": skip_cons},
            estimated_cost_impact=0.0,
            risk_level=skip_risk,
        ),
        EnhancedCheckpointOption(
            label="Modify",
            description="Modify the goal before proceeding.",
            is_recommended=False,
            tradeoffs={
                "pros": ["Adjust approach", "Reduce risk or cost"],
                "cons": ["Requires manual intervention", "Delays progress"],
            },
            estimated_cost_impact=None,  # Unknown
            risk_level="medium",
        ),
        EnhancedCheckpointOption(
            label="Pause",
            description="Pause the session for manual review.",
            is_recommended=False,
            tradeoffs={
                "pros": ["Full manual control", "Thorough review"],
                "cons": ["Stops automation", "Requires immediate attention"],
            },
            estimated_cost_impact=0.0,
            risk_level="low",
        ),
    ]
```

**Tests to pass**:
- `test_complete_enhanced_format`
- `test_enhanced_format_layout`
- `test_enhanced_format_user_friendly`

### Phase 5: Wire into Autopilot Runner

**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/autopilot_runner.py`

**Modify**: Initialize `CheckpointUX` with dependencies

```python
# In AutopilotRunner.__init__ or equivalent
from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX
from swarm_attack.chief_of_staff.episodes import PreferenceLearner

# Initialize with full context
self.checkpoint_ux = CheckpointUX(
    preference_learner=self.preference_learner,  # From existing integration
    session=self.session,  # Current AutopilotSession
)
```

**Modify**: Pass `goal` to `format_checkpoint` when triggering checkpoints

```python
# When checkpoint is triggered
checkpoint_result = await self.checkpoint_system.check_before_execution(goal)

if checkpoint_result.requires_approval:
    # Display checkpoint with full context
    decision = self.checkpoint_ux.prompt_and_wait(
        checkpoint_result.checkpoint,
        goal=goal,  # Pass goal for similar decisions
        session=self.session,  # Pass session for progress
    )
```

## Implementation Notes

### Backward Compatibility

- Existing code using `CheckpointOption` continues to work
- `EnhancedCheckpointOption` adds optional fields with defaults
- `CheckpointUX` gracefully handles missing `preference_learner` or `session`
- `format_checkpoint` works with both basic and enhanced options

### Data Sources

1. **Tradeoffs**: Generated by `CheckpointSystem._build_options()` based on trigger type
2. **Similar decisions**: Queried from `PreferenceLearner.find_similar_decisions(goal)`
3. **Progress context**: Read from `AutopilotSession` (goals, budget, timestamps)
4. **Cost impact**: Derived from `goal.estimated_cost_usd` for Proceed option
5. **Risk level**: Mapped from trigger type (HICCUP=medium, COST=high, etc.)

### Visual Design

The enhanced format uses:
- `━` for section separators (box drawing characters)
- Indentation (2-6 spaces) for hierarchy
- Emoji markers: `⚠️` (checkpoint), `✓` (approved), `✗` (rejected)
- Risk indicators: `🟢` (low), `🟡` (medium), `🔴` (high)
- Clear section headers: "Session Progress:", "Similar Past Decisions:", "Options:"

### Performance Considerations

- `find_similar_decisions()` is fast (in-memory search, top-3 results)
- Session progress calculations are O(n) on number of goals (typically < 100)
- No additional API calls or I/O required
- Display formatting is negligible overhead

## Testing Strategy

### Unit Tests (test_enhanced_checkpoint.py)

1. **TestEnhancedCheckpointOption**: Verify new dataclass fields and serialization
2. **TestSimilarPastDecisions**: Verify PreferenceLearner integration and display
3. **TestProgressContext**: Verify AutopilotSession integration and calculations
4. **TestEnhancedCheckpointIntegration**: Verify complete enhanced format

### Manual Testing

1. Trigger HICCUP checkpoint during autopilot run
2. Verify all sections display correctly
3. Verify similar decisions show relevant past choices
4. Verify progress shows accurate counts and budget
5. Verify option tradeoffs are helpful and accurate

### Acceptance Criteria

From Issue #39:
- [ ] Each option shows pros and cons
- [ ] Each option shows estimated cost impact
- [ ] Each option shows risk level (low/medium/high)
- [ ] Checkpoint displays 2-3 similar past decisions
- [ ] Similar decisions show approval/rejection outcome
- [ ] Checkpoint displays session progress (goals completed)
- [ ] Checkpoint displays budget status (spent/remaining)
- [ ] Checkpoint displays estimated runway
- [ ] All enhancements are optional (backward compatible)
- [ ] Layout is clear and scannable (under 50 lines typical)

## Example Output

```
⚠️  HICCUP Checkpoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Session Progress:
  Goals: 2/4 completed (current: Fix authentication bug...)
  Budget: $10.00 / $25.00 spent ($15.00 remaining, 40% used)
  Estimated runway: ~3 more goals at current burn rate

Goal encountered error after 2 retries.
Goal: Implement authentication system
Error: ImportError: cannot import name 'hash_password'

Similar Past Decisions:
  • ✓ Approved - HICCUP: Previous error, proceeded successfully...
  • ✗ Rejected - HICCUP: Goal failed with timeout. Error: Connection timeout...

Options:
  [1] Proceed - Continue and retry (recommended)
      Pros: May succeed on retry, Maintains progress momentum
      Cons: May fail again, Consumes budget on uncertain outcome
      Cost impact: +$3.00
      Risk: 🟡 Medium
  [2] Skip - Skip this goal and move to the next one.
      Pros: Saves budget for other goals, Avoids repeated failures
      Cons: Goal remains incomplete, May require manual intervention later
      Cost impact: No cost
      Risk: 🟢 Low
  [3] Pause - Pause the session for manual review.
      Pros: Full manual control, Thorough review
      Cons: Stops automation, Requires immediate attention
      Cost impact: No cost
      Risk: 🟢 Low

Recommendation: Proceed based on similar past success (70% approval rate)

Select option: _
```

## Next Steps

1. **Implement EnhancedCheckpointOption** (Phase 1)
2. **Add PreferenceLearner integration** (Phase 2)
3. **Add progress context display** (Phase 3)
4. **Update CheckpointSystem** (Phase 4)
5. **Wire into AutopilotRunner** (Phase 5)
6. **Run tests**: `PYTHONPATH=. pytest tests/chief_of_staff/test_enhanced_checkpoint.py -v`
7. **Manual testing** with real autopilot session
8. **Document in CLAUDE.md** and update user-facing docs

## Files to Modify

1. `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoint_ux.py` - Core implementation
2. `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/checkpoints.py` - Enhanced options builder
3. `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/chief_of_staff/autopilot_runner.py` - Wire dependencies
4. `/Users/philipjcortes/Desktop/swarm-attack/CLAUDE.md` - Update documentation
