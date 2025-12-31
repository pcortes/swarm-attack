"""Data models for commit quality review."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommitCategory(Enum):
    """Categories for classifying commits."""

    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST_CHANGE = "test_change"
    DOCUMENTATION = "documentation"
    CHORE = "chore"
    OTHER = "other"


class Severity(Enum):
    """Severity levels for findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Verdict(Enum):
    """Verdict for a commit review."""

    LEAVE = "leave"  # Commit is fine, no action needed
    FIX = "fix"  # Commit has issues that should be fixed
    REVERT = "revert"  # Commit should be reverted


@dataclass
class CommitInfo:
    """Information about a git commit."""

    sha: str
    author: str
    email: str
    timestamp: str
    message: str
    files_changed: int
    insertions: int
    deletions: int
    changed_files: list[str] = field(default_factory=list)


@dataclass
class Finding:
    """A finding from an expert review."""

    commit_sha: str
    expert: str
    severity: Severity
    category: str
    description: str
    evidence: str  # file:line reference


@dataclass
class TDDPlan:
    """TDD fix plan for an actionable finding."""

    finding_id: str
    red_phase: str  # Failing test to write
    green_phase: str  # Minimal fix to implement
    refactor_phase: str  # Cleanup suggestions


@dataclass
class CommitReview:
    """Review result for a single commit."""

    commit_sha: str
    message: str
    author: str
    findings: list[Finding]
    score: float
    verdict: Verdict
    tdd_plans: list[TDDPlan] = field(default_factory=list)


@dataclass
class ReviewReport:
    """Complete review report for multiple commits."""

    generated_at: str
    repo_path: str
    branch: str
    since: str
    commit_reviews: list[CommitReview]
    overall_score: float
    summary: str
