"""COO Integration module for swarm-attack.

This module provides integration with the COO (Chief Operating Officer) system
for priority synchronization and spec archival.
"""

from swarm_attack.coo_integration.priority_sync import (
    COOConfig,
    COOClient,
    COOConnectionError,
    COOSyncError,
    COOValidationError,
    COOBudgetExceededError,
    SyncDirection,
    SpecPushResult,
    BudgetCheckResult,
    PriorityRanking,
    PrioritySyncManager,
)

from swarm_attack.coo_integration.spec_archival import (
    ApprovalStatus,
    ArchivalMetadata,
    ArchivalResult,
    SpecArchiver,
    ReportArchiver,
)

__all__ = [
    # Priority Sync
    "COOConfig",
    "COOClient",
    "COOConnectionError",
    "COOSyncError",
    "COOValidationError",
    "COOBudgetExceededError",
    "SyncDirection",
    "SpecPushResult",
    "BudgetCheckResult",
    "PriorityRanking",
    "PrioritySyncManager",
    # Spec Archival
    "ApprovalStatus",
    "ArchivalMetadata",
    "ArchivalResult",
    "SpecArchiver",
    "ReportArchiver",
]
