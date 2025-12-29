"""Level 2 intelligent recovery with LLM-powered decision making.

When a systematic error occurs (CLI crash, JSON parse error), this module
uses an LLM to decide recovery strategy instead of immediately escalating
to a human. This is part of the Self-Healing Jarvis feature.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


class RecoveryActionType(Enum):
    """Types of recovery actions Level 2 can suggest."""

    ALTERNATIVE = "alternative"  # Try different approach
    DIAGNOSTICS = "diagnostics"  # Run bug bash / diagnostics
    UNBLOCK = "unblock"  # Use admin unblock commands
    ESCALATE = "escalate"  # Give up, escalate to human


@dataclass
class RecoveryAction:
    """Action suggested by Level 2 analyzer."""

    action_type: RecoveryActionType
    hint: str = ""  # Hint for retry (e.g., "try async")
    reasoning: str = ""  # Why this action


class Level2Analyzer:
    """LLM-powered recovery analyzer for systematic errors.

    When a systematic error occurs (not transient, not fatal),
    asks LLM to suggest a recovery strategy.
    """

    def __init__(
        self,
        llm: Any,
        max_alternatives: int = 2,  # Max alternative attempts before escalate
    ):
        """Initialize Level 2 analyzer.

        Args:
            llm: LLM client with async ask() method.
            max_alternatives: Max times to try alternative before escalating.
        """
        self.llm = llm
        self.max_alternatives = max_alternatives
        self._alternative_count = 0

    async def analyze(
        self,
        goal: "DailyGoal",
        error: Exception,
    ) -> RecoveryAction:
        """Analyze error and suggest recovery action.

        Calls LLM with prompt:
        - Goal description
        - Error message
        - Ask for: action (alternative/diagnostics/unblock/escalate), hint, reasoning

        Args:
            goal: The goal that failed.
            error: The exception that occurred.

        Returns:
            RecoveryAction with suggested strategy.
        """
        # Check if we've exceeded max alternatives
        if self._alternative_count >= self.max_alternatives:
            return RecoveryAction(
                action_type=RecoveryActionType.ESCALATE,
                hint="",
                reasoning=f"Exceeded max alternatives ({self.max_alternatives})",
            )

        try:
            # Build prompt and call LLM
            prompt = self._build_prompt(goal, error)
            response = await self.llm.ask(prompt)

            # Parse response
            action = self._parse_response(response)

            # Track alternative count
            if action.action_type == RecoveryActionType.ALTERNATIVE:
                self._alternative_count += 1

            return action

        except Exception:
            # LLM exception - return ESCALATE
            return RecoveryAction(
                action_type=RecoveryActionType.ESCALATE,
                hint="",
                reasoning="LLM unavailable or error during analysis",
            )

    def _build_prompt(self, goal: "DailyGoal", error: Exception) -> str:
        """Build LLM prompt for recovery analysis."""
        return f"""You are a recovery analyzer for an AI development system.

A goal failed with a systematic error. Analyze and suggest recovery.

GOAL: {goal.description}
ERROR: {str(error)}

Choose ONE action:
- "alternative": Suggest a different approach to try
- "diagnostics": Run bug bash or diagnostics to investigate
- "unblock": Use admin commands to reset/unblock state
- "escalate": Give up and ask human (last resort)

Respond with JSON only:
{{"action": "alternative|diagnostics|unblock|escalate", "hint": "specific suggestion", "reasoning": "why this action"}}
"""

    def _parse_response(self, response: str) -> RecoveryAction:
        """Parse LLM response into RecoveryAction."""
        try:
            data = json.loads(response)
            action_type = RecoveryActionType(data.get("action", "escalate"))
            return RecoveryAction(
                action_type=action_type,
                hint=data.get("hint", ""),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError):
            return RecoveryAction(
                action_type=RecoveryActionType.ESCALATE,
                hint="",
                reasoning="Failed to parse LLM response",
            )

    def reset_alternative_count(self) -> None:
        """Reset the alternative attempt counter."""
        self._alternative_count = 0
