"""Chief of Staff module for autonomous repository management.

This module provides the Chief of Staff agent - a strategic orchestration layer
that acts as an autonomous "mini-CEO" for swarm-attack repositories.

Components:
- StateGatherer: Aggregates state from all repository data sources
- DailyLogManager: Manages daily logs and decision history
- GoalTracker: Tracks daily goals with reconciliation
- CheckpointSystem: Detects checkpoint triggers for autopilot
- AutopilotRunner: Executes goals with checkpoint gates
- AutopilotSessionStore: Persists autopilot sessions for pause/resume
- ChiefOfStaffConfig: Configuration dataclass

CLI Commands (via `swarm-attack cos`):
- standup: Morning briefing with recommendations
- checkin: Mid-day status check
- wrapup: End-of-day summary
- history: View past logs and decisions
- next: Show recommended next actions
- autopilot: Execute goals with budget/time limits
"""

# Configuration
from swarm_attack.chief_of_staff.config import (
    ChiefOfStaffConfig,
    CheckpointConfig,
    PriorityConfig,
    StandupConfig,
    AutopilotConfig,
)

# State gathering
from swarm_attack.chief_of_staff.state_gatherer import (
    StateGatherer,
    RepoStateSnapshot,
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestState,
    GitHubState,
    InterruptedSession,
)

# Daily logging
from swarm_attack.chief_of_staff.daily_log import (
    DailyLogManager,
    DailyLog,
    DailyGoal,
    DailySummary,
    StandupSession,
    Decision,
    DecisionType,
)

# Goal tracking
from swarm_attack.chief_of_staff.goal_tracker import (
    GoalTracker,
    GoalStatus,
    GoalPriority,
    Recommendation,
    RecommendationPriority,
)

# Checkpoints
from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointTrigger,
    CheckpointOption,
    Checkpoint,
    CheckpointResult,
    CheckpointStore,
    CheckpointSystem,
)

# Autopilot
from swarm_attack.chief_of_staff.autopilot import (
    AutopilotSession,
    AutopilotState,
)
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    AutopilotRunResult,
    GoalExecutionResult,
    SessionContext,
)

__all__ = [
    # Configuration
    "ChiefOfStaffConfig",
    "CheckpointConfig",
    "PriorityConfig",
    "StandupConfig",
    "AutopilotConfig",
    # State gathering
    "StateGatherer",
    "RepoStateSnapshot",
    "GitState",
    "FeatureSummary",
    "BugSummary",
    "PRDSummary",
    "SpecSummary",
    "TestState",
    "GitHubState",
    "InterruptedSession",
    # Daily logging
    "DailyLogManager",
    "DailyLog",
    "DailyGoal",
    "DailySummary",
    "StandupSession",
    "Decision",
    "DecisionType",
    # Goal tracking
    "GoalTracker",
    "GoalStatus",
    "GoalPriority",
    "Recommendation",
    "RecommendationPriority",
    # Checkpoints
    "CheckpointTrigger",
    "CheckpointOption",
    "Checkpoint",
    "CheckpointResult",
    "CheckpointStore",
    "CheckpointSystem",
    # Autopilot
    "AutopilotSession",
    "AutopilotState",
    "AutopilotSessionStore",
    "AutopilotRunner",
    "AutopilotRunResult",
    "GoalExecutionResult",
    "SessionContext",
]
