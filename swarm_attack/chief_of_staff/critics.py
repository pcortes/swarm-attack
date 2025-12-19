"""Critic base class and CriticScore dataclass for internal validation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CriticFocus(Enum):
    """Focus areas for critics."""

    COMPLETENESS = "completeness"
    FEASIBILITY = "feasibility"
    SECURITY = "security"
    STYLE = "style"
    COVERAGE = "coverage"
    EDGE_CASES = "edge_cases"


@dataclass
class CriticScore:
    """Score from a critic evaluation."""

    critic_name: str
    focus: CriticFocus
    score: float  # 0-1
    approved: bool
    issues: list[str]
    suggestions: list[str]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "critic_name": self.critic_name,
            "focus": self.focus.name,
            "score": self.score,
            "approved": self.approved,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticScore":
        """Deserialize from dictionary."""
        return cls(
            critic_name=data["critic_name"],
            focus=CriticFocus[data["focus"]],
            score=data["score"],
            approved=data["approved"],
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            reasoning=data.get("reasoning", ""),
        )


class Critic(ABC):
    """Base class for internal validation critics."""

    def __init__(
        self,
        focus: CriticFocus,
        llm: Any,
        weight: float = 1.0,
    ) -> None:
        """Initialize critic.

        Args:
            focus: The focus area for this critic
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)
        """
        self.focus = focus
        self.llm = llm
        self.weight = weight

    @property
    def has_veto(self) -> bool:
        """Whether this critic has veto power (blocks consensus).

        Only SECURITY focus has veto power.
        """
        return self.focus == CriticFocus.SECURITY

    @abstractmethod
    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate an artifact and return a score.

        Args:
            artifact: The artifact to evaluate (code, spec, plan, etc.)

        Returns:
            CriticScore with evaluation results
        """
        pass