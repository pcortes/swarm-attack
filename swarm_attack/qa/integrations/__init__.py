"""QA Pipeline Integration modules.

Provides integrations for:
- Feature Pipeline (post-verification QA)
- Bug Pipeline (enhanced reproduction)
- Chief of Staff (autopilot goals)
"""

from swarm_attack.qa.integrations.feature_pipeline import (
    FeaturePipelineQAIntegration,
    QAIntegrationResult,
)
from swarm_attack.qa.integrations.bug_pipeline import (
    BugPipelineQAIntegration,
    BugReproductionResult,
)
from swarm_attack.qa.integrations.cos_goals import (
    QAGoalTypes,
    QAGoal,
)
from swarm_attack.qa.integrations.cos_autopilot import (
    QAAutopilotRunner,
    GoalExecutionResult,
)

__all__ = [
    "FeaturePipelineQAIntegration",
    "QAIntegrationResult",
    "BugPipelineQAIntegration",
    "BugReproductionResult",
    "QAGoalTypes",
    "QAGoal",
    "QAAutopilotRunner",
    "GoalExecutionResult",
]
