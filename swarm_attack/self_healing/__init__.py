"""Self-healing module for autonomous failure prediction and recovery.

This module provides:
- FailurePredictor: Detect failure trajectories before task completion
- ExecutionState: Represents the current execution state
- PredictionResult: Result of failure prediction analysis
- RecoverySuggestion: Suggested recovery action
- EscalationManager: Human-in-loop escalation with context preservation
- RecoveryHandler: Tiered recovery strategies for different failure modes
- CoderSelfHealingIntegration: Integration layer for CoderAgent execution loop
"""

from swarm_attack.self_healing.failure_predictor import (
    ExecutionState,
    FailurePredictor,
    FailureType,
    PredictionResult,
    RecoveryAction,
    RecoverySuggestion,
)

from swarm_attack.self_healing.escalation_manager import (
    EscalationContext,
    EscalationManager,
    EscalationTicket,
    EscalationTrigger,
    FailureContext,
    Priority,
    ResumeResult,
)

from swarm_attack.self_healing.coder_integration import (
    CoderSelfHealingIntegration,
)

from swarm_attack.self_healing.recovery_handler import (
    FailureInfo,
    RecoveryHandler,
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategy,
    RecoveryTier,
)

__all__ = [
    # Failure Predictor
    "ExecutionState",
    "FailurePredictor",
    "FailureType",
    "PredictionResult",
    "RecoveryAction",
    "RecoverySuggestion",
    # Escalation Manager
    "EscalationContext",
    "EscalationManager",
    "EscalationTicket",
    "EscalationTrigger",
    "FailureContext",
    "Priority",
    "ResumeResult",
    # Coder Integration
    "CoderSelfHealingIntegration",
    # Recovery Handler
    "FailureInfo",
    "RecoveryHandler",
    "RecoveryResult",
    "RecoveryStatus",
    "RecoveryStrategy",
    "RecoveryTier",
]
