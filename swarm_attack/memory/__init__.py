"""
Persistent Memory Layer for Swarm Attack.

Phase A implementation: JSON-based storage with keyword matching.
"""

from swarm_attack.memory.categories import (
    BUG_PATTERN,
    IMPLEMENTATION_SUCCESS,
    RECOVERY_PATTERN,
    SCHEMA_DRIFT,
    TEST_FAILURE,
)
from swarm_attack.memory.patterns import PatternDetector, VerificationPattern
from swarm_attack.memory.store import MemoryEntry, MemoryStore

__all__ = [
    "MemoryEntry",
    "MemoryStore",
    "PatternDetector",
    "VerificationPattern",
    "SCHEMA_DRIFT",
    "TEST_FAILURE",
    "RECOVERY_PATTERN",
    "IMPLEMENTATION_SUCCESS",
    "BUG_PATTERN",
]
