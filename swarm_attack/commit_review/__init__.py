"""Commit Quality Review module.

Provides multi-agent review of recent commits with expert panel analysis.
"""

from swarm_attack.commit_review.models import (
    CommitInfo,
    CommitCategory,
    Finding,
    Severity,
    Verdict,
    TDDPlan,
    CommitReview,
    ReviewReport,
)
from swarm_attack.commit_review.discovery import discover_commits
from swarm_attack.commit_review.categorizer import categorize_commit
from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.synthesis import (
    synthesize_findings,
    calculate_score,
    determine_verdict,
)
from swarm_attack.commit_review.tdd_generator import TDDPlanGenerator
from swarm_attack.commit_review.report import ReportGenerator

__all__ = [
    # Models
    "CommitInfo",
    "CommitCategory",
    "Finding",
    "Severity",
    "Verdict",
    "TDDPlan",
    "CommitReview",
    "ReviewReport",
    # Functions
    "discover_commits",
    "categorize_commit",
    "synthesize_findings",
    "calculate_score",
    "determine_verdict",
    # Classes
    "AgentDispatcher",
    "TDDPlanGenerator",
    "ReportGenerator",
]
