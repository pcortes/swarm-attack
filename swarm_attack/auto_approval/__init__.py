"""
Auto-Approval System for Swarm Attack.

This package provides confidence-based auto-approval for:
- Spec approval (when debate scores meet threshold for 2+ rounds)
- Issue greenlight (when complexity gate passes for all issues)
- Bug fix approval (when confidence >= 0.9 and risk != high)

Human override always available via veto/manual commands.
"""

from swarm_attack.auto_approval.models import ApprovalResult
from swarm_attack.auto_approval.spec import SpecAutoApprover
from swarm_attack.auto_approval.issue import IssueAutoGreenlighter
from swarm_attack.auto_approval.bug import BugAutoApprover
from swarm_attack.auto_approval.overrides import (
    veto_feature,
    veto_bug,
    enable_manual_mode,
    enable_auto_mode,
)

__all__ = [
    "ApprovalResult",
    "SpecAutoApprover",
    "IssueAutoGreenlighter",
    "BugAutoApprover",
    "veto_feature",
    "veto_bug",
    "enable_manual_mode",
    "enable_auto_mode",
]
