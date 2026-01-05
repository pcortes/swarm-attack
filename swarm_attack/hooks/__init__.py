"""Hooks module for swarm_attack.

This module provides hooks for validating and intercepting operations.
"""

from swarm_attack.hooks.safety_net import (
    SafetyNetHook,
    SafetyNetResult,
    SafetyNetConfig,
    DestructiveCommandError,
)
from swarm_attack.hooks.auto_verify import (
    AutoVerifyHook,
    VerificationResult,
    VerificationRecord,
    VerificationError,
)

__all__ = [
    # SafetyNet Hook
    "SafetyNetHook",
    "SafetyNetResult",
    "SafetyNetConfig",
    "DestructiveCommandError",
    # AutoVerify Hook
    "AutoVerifyHook",
    "VerificationResult",
    "VerificationRecord",
    "VerificationError",
]
