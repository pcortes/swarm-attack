"""Chief of Staff QA Goals.

Implements spec section 5.2.3:
- QA_VALIDATION and QA_HEALTH goal types
- QAGoal dataclass with linking capabilities
- Goal-to-session tracking
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class QAGoalTypes(Enum):
    """QA goal types for autopilot execution.

    Based on spec section 5.2.3:
    - QA_VALIDATION: Validate a feature/issue after implementation
    - QA_HEALTH: Run system health check (shallow depth)
    """

    QA_VALIDATION = "qa_validation"
    QA_HEALTH = "qa_health"


@dataclass
class QAGoal:
    """A QA goal for autopilot execution.

    Links goals to features, issues, and QA sessions for tracking.

    Attributes:
        goal_type: The type of QA goal (validation or health).
        linked_feature: Optional feature ID this goal is linked to.
        linked_issue: Optional issue number this goal is linked to.
        linked_qa_session: Optional QA session ID from execution.
        description: Optional human-readable description of the goal.
    """

    goal_type: QAGoalTypes
    linked_feature: Optional[str] = None
    linked_issue: Optional[int] = None
    linked_qa_session: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the goal to a dictionary.

        Returns:
            Dictionary representation of the goal.
        """
        return {
            "goal_type": self.goal_type.value,
            "linked_feature": self.linked_feature,
            "linked_issue": self.linked_issue,
            "linked_qa_session": self.linked_qa_session,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAGoal:
        """Create a QAGoal from a dictionary.

        Args:
            data: Dictionary with goal data.

        Returns:
            QAGoal instance.
        """
        return cls(
            goal_type=QAGoalTypes(data["goal_type"]),
            linked_feature=data.get("linked_feature"),
            linked_issue=data.get("linked_issue"),
            linked_qa_session=data.get("linked_qa_session"),
            description=data.get("description"),
        )
