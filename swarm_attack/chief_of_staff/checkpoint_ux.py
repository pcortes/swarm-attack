"""Blocking checkpoint UX for interactive decision making.

This module provides interactive checkpoint prompts that block execution
until the user makes a decision. This is part of the Self-Healing Jarvis
feature that transforms batch-style stops into interactive decision points.

Enhanced features (Issue #39):
- EnhancedCheckpointOption with tradeoffs, cost impact, and risk level
- Similar past decisions display from PreferenceLearner
- Session progress context (goals completed, budget, runway)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.chief_of_staff.checkpoints import Checkpoint, CheckpointOption

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.episodes import PreferenceLearner
    from swarm_attack.chief_of_staff.autopilot import AutopilotSession


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


@dataclass
class CheckpointDecision:
    """Result of a checkpoint decision."""

    checkpoint_id: str
    chosen_option: str
    notes: str = ""


class CheckpointUX:
    """Interactive checkpoint UX that blocks until user decides.

    When a checkpoint triggers, this class displays formatted checkpoint
    information and prompts the user for a decision interactively.

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

    def _format_age(self, timestamp: str) -> str:
        """Format a timestamp as relative age (e.g., '2 days ago').

        Args:
            timestamp: ISO format timestamp string.

        Returns:
            Human-readable relative time string.
        """
        try:
            # Parse the ISO timestamp
            if "T" in timestamp:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(timestamp)

            # Make naive if timezone-aware for comparison
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)

            now = datetime.now()
            delta = now - dt

            # Calculate appropriate unit
            seconds = delta.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif seconds < 604800:
                days = int(seconds / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
            else:
                weeks = int(seconds / 604800)
                return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        except (ValueError, TypeError):
            return "unknown time"

    def _format_similar_decisions(self, goal: Any) -> str:
        """Format similar past decisions section.

        Args:
            goal: DailyGoal with tags for similarity matching.

        Returns:
            Formatted section showing 2-3 similar past decisions, or message if none.
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
            timestamp = decision.get("timestamp", "")
            age = self._format_age(timestamp) if timestamp else "unknown time"

            lines.append(f"  • {outcome} - {trigger}: {context}... ({age})")

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
            if cost > 0:
                cost_str = f"+${cost:.2f}"
            elif cost < 0:
                cost_str = f"${cost:.2f}"
            else:
                cost_str = "No cost"
            lines.append(f"      Cost impact: {cost_str}")

        # Add risk level if available
        if has_risk:
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(option.risk_level, "⚪")
            lines.append(f"      Risk: {risk_emoji} {option.risk_level.capitalize()}")

        return "\n".join(lines)

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
            current_desc = current_goal.get("description", "Unknown")[:40] if current_goal else "None"
            lines.append(f"  Goals: {completed_goals}/{total_goals} completed (current: {current_desc}...)")

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

    def get_decision(
        self,
        checkpoint: Checkpoint,
        allow_notes: bool = False,
    ) -> CheckpointDecision:
        """Get user decision for checkpoint.

        Behavior:
        - Display formatted checkpoint (via prompt_and_wait or externally)
        - Prompt for input (1, 2, 3, etc.)
        - Empty input selects recommended option
        - Invalid input reprompts
        - If allow_notes, prompt for optional notes after selection

        Args:
            checkpoint: The checkpoint requiring a decision.
            allow_notes: If True, prompt for notes after selection.

        Returns:
            CheckpointDecision with chosen_option and notes.
        """
        # Find recommended option
        recommended = next(
            (o for o in checkpoint.options if o.is_recommended),
            checkpoint.options[0] if checkpoint.options else None,
        )

        # Get valid input
        while True:
            user_input = input("Select option: ").strip()

            # Empty input selects recommended
            if user_input == "":
                chosen_option = recommended.label if recommended else checkpoint.options[0].label
                break

            # Try to parse as number
            try:
                idx = int(user_input)
                if 1 <= idx <= len(checkpoint.options):
                    chosen_option = checkpoint.options[idx - 1].label
                    break
            except ValueError:
                pass

            # Invalid input - continue loop (reprompt)

        # Get notes if allowed
        notes = ""
        if allow_notes:
            notes = input("Notes (optional): ").strip()

        return CheckpointDecision(
            checkpoint_id=checkpoint.checkpoint_id,
            chosen_option=chosen_option,
            notes=notes,
        )

    def prompt_and_wait(self, checkpoint: Checkpoint) -> CheckpointDecision:
        """Display checkpoint and block until user responds.

        Convenience method that calls format_checkpoint, prints it,
        then calls get_decision.

        This is the main entry point for blocking checkpoint flow.

        Args:
            checkpoint: The checkpoint to display and get decision for.

        Returns:
            CheckpointDecision with the user's choice.
        """
        # Display formatted checkpoint
        formatted = self.format_checkpoint(checkpoint)
        print(formatted)

        # Get and return decision
        return self.get_decision(checkpoint)
