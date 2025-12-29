"""Backlog Discovery - Autonomous opportunity detection for Swarm Attack.

This module provides:
- Opportunity and Evidence dataclasses for tracking discovered work items
- BacklogStore for persistent storage of opportunities
- Discovery agents for finding test failures, stalled work, and code quality issues
- Debate agents for prioritization when multiple opportunities exist
"""

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    ActionabilityScore,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore
from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import (
    TestFailureDiscoveryAgent,
)

__all__ = [
    "Evidence",
    "ActionabilityScore",
    "Opportunity",
    "OpportunityType",
    "OpportunityStatus",
    "BacklogStore",
    "TestFailureDiscoveryAgent",
]
