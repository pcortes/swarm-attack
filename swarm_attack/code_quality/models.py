"""
Data models for code quality findings and analysis results.

This module provides dataclasses for the code quality analysis system:
- Finding: Individual code quality issue with evidence and suggested fix
- AnalysisResult: Output from the code-quality-analyst skill
- CriticReview: Output from the refactor-critic skill
- ModeratorDecision: Output from the refactor-moderator skill
- RetryContext: State preservation across retry iterations

All dataclasses support:
- from_dict(cls, data) -> Self: Create instance from dict
- to_dict(self) -> dict: Convert to dict for JSON serialization
- Roundtrip equality: from_dict(x.to_dict()) == x
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ============================================================
# Enums
# ============================================================

class Severity(str, Enum):
    """Severity levels for findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Priority(str, Enum):
    """Priority classifications for findings."""
    FIX_NOW = "fix_now"
    FIX_LATER = "fix_later"
    IGNORE = "ignore"


class Category(str, Enum):
    """Categories of code quality findings."""
    CODE_SMELL = "code_smell"
    SOLID = "solid"
    LLM_HALLUCINATION = "llm_hallucination"
    INCOMPLETE = "incomplete"
    ERROR_HANDLING = "error_handling"


class Verdict(str, Enum):
    """Final verdict from the analysis pipeline."""
    APPROVE = "APPROVE"
    REFACTOR = "REFACTOR"
    ESCALATE = "ESCALATE"


class IssueType(str, Enum):
    """Types of issues the critic can raise about analyst findings."""
    OVER_SEVERITY = "over_severity"
    FALSE_POSITIVE = "false_positive"
    IMPRACTICAL_FIX = "impractical_fix"
    MISSING_CONTEXT = "missing_context"
    ENTERPRISE_CREEP = "enterprise_creep"


class CriticRecommendation(str, Enum):
    """Critic's recommendation for the analysis."""
    APPROVE = "APPROVE"
    REVISE = "REVISE"


# ============================================================
# Finding Dataclass
# ============================================================

@dataclass
class Finding:
    """A code quality finding with evidence and suggested fix.

    Attributes:
        finding_id: Unique identifier (e.g., "CQA-001")
        severity: How serious the issue is (critical, high, medium, low)
        category: Type of issue (code_smell, solid, llm_hallucination, etc.)
        file: Path to the file containing the issue
        line: Line number where the issue occurs
        title: Short description of the issue
        description: Detailed explanation of the issue
        expert: Name of the expert who identified the issue
        code_snippet: Code excerpt showing the issue
        refactoring_pattern: Name of the refactoring pattern to apply
        refactoring_steps: Step-by-step instructions for the fix
        priority: When to fix (fix_now, fix_later, ignore)
        effort_estimate: Estimated effort (small, medium, large)
        confidence: Confidence score (0.0 to 1.0)
    """
    finding_id: str
    severity: Severity
    category: Category
    file: str
    line: int
    title: str
    description: str
    expert: str = ""
    code_snippet: str = ""
    refactoring_pattern: str = ""
    refactoring_steps: list[str] = field(default_factory=list)
    priority: Priority = Priority.FIX_LATER
    effort_estimate: str = "medium"
    confidence: float = 0.8

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        """Create a Finding from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            severity=Severity(data["severity"]),
            category=Category(data["category"]),
            file=data["file"],
            line=data["line"],
            title=data["title"],
            description=data["description"],
            expert=data.get("expert", ""),
            code_snippet=data.get("code_snippet", ""),
            refactoring_pattern=data.get("refactoring_pattern", ""),
            refactoring_steps=data.get("refactoring_steps", []),
            priority=Priority(data.get("priority", "fix_later")),
            effort_estimate=data.get("effort_estimate", "medium"),
            confidence=data.get("confidence", 0.8),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert Finding to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "file": self.file,
            "line": self.line,
            "title": self.title,
            "description": self.description,
            "expert": self.expert,
            "code_snippet": self.code_snippet,
            "refactoring_pattern": self.refactoring_pattern,
            "refactoring_steps": self.refactoring_steps,
            "priority": self.priority.value,
            "effort_estimate": self.effort_estimate,
            "confidence": self.confidence,
        }


# ============================================================
# AnalysisResult Dataclass
# ============================================================

@dataclass
class AnalysisResult:
    """Output from the code-quality-analyst skill.

    Attributes:
        analysis_id: Unique identifier (e.g., "cqa-20260101-120000")
        files_analyzed: List of files that were analyzed
        total_issues: Total number of issues found
        critical: Count of critical severity issues
        high: Count of high severity issues
        medium: Count of medium severity issues
        low: Count of low severity issues
        fix_now: Count of issues to fix immediately
        fix_later: Count of issues for tech debt backlog
        ignore: Count of issues to ignore
        findings: List of Finding objects
        recommendation: Overall verdict (APPROVE, REFACTOR, ESCALATE)
        refactor_summary: Brief description of what needs fixing
    """
    analysis_id: str
    files_analyzed: list[str]
    total_issues: int
    critical: int
    high: int
    medium: int
    low: int
    fix_now: int
    fix_later: int
    ignore: int
    findings: list[Finding]
    recommendation: Verdict
    refactor_summary: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisResult":
        """Create an AnalysisResult from a dictionary."""
        summary = data.get("summary", {})
        return cls(
            analysis_id=data["analysis_id"],
            files_analyzed=data["files_analyzed"],
            total_issues=summary.get("total_issues", 0),
            critical=summary.get("critical", 0),
            high=summary.get("high", 0),
            medium=summary.get("medium", 0),
            low=summary.get("low", 0),
            fix_now=summary.get("fix_now", 0),
            fix_later=summary.get("fix_later", 0),
            ignore=summary.get("ignore", 0),
            findings=[Finding.from_dict(f) for f in data.get("findings", [])],
            recommendation=Verdict(data["recommendation"]),
            refactor_summary=data.get("refactor_summary", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert AnalysisResult to a dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "files_analyzed": self.files_analyzed,
            "summary": {
                "total_issues": self.total_issues,
                "critical": self.critical,
                "high": self.high,
                "medium": self.medium,
                "low": self.low,
                "fix_now": self.fix_now,
                "fix_later": self.fix_later,
                "ignore": self.ignore,
            },
            "findings": [f.to_dict() for f in self.findings],
            "recommendation": self.recommendation.value,
            "refactor_summary": self.refactor_summary,
        }


# ============================================================
# CriticIssue and CriticReview Dataclasses
# ============================================================

@dataclass
class CriticIssue:
    """An issue raised by the critic about an analyst finding.

    Attributes:
        finding_id: ID of the finding being critiqued
        issue_type: Type of issue (over_severity, false_positive, etc.)
        original_severity: The severity assigned by the analyst
        suggested_severity: The critic's suggested severity (or None)
        reasoning: Explanation for the critique
    """
    finding_id: str
    issue_type: IssueType
    original_severity: str
    suggested_severity: Optional[str]
    reasoning: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticIssue":
        """Create a CriticIssue from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            issue_type=IssueType(data["issue_type"]),
            original_severity=data["original_severity"],
            suggested_severity=data.get("suggested_severity"),
            reasoning=data["reasoning"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert CriticIssue to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "issue_type": self.issue_type.value,
            "original_severity": self.original_severity,
            "suggested_severity": self.suggested_severity,
            "reasoning": self.reasoning,
        }


@dataclass
class CriticReview:
    """Output from the refactor-critic skill.

    Attributes:
        review_id: Unique identifier (e.g., "crit-20260101-120000")
        accuracy: Score for whether findings are real issues (0.0 to 1.0)
        severity_calibration: Score for appropriate severity levels (0.0 to 1.0)
        actionability: Score for specific and doable fixes (0.0 to 1.0)
        pragmatism: Score for balancing quality with shipping (0.0 to 1.0)
        issues: List of issues with analyst findings
        validated_findings: List of finding IDs that are valid
        rejected_findings: List of finding IDs that are false positives
        summary: Brief description of the review outcome
        recommendation: APPROVE or REVISE
    """
    review_id: str
    accuracy: float
    severity_calibration: float
    actionability: float
    pragmatism: float
    issues: list[CriticIssue]
    validated_findings: list[str]
    rejected_findings: list[str]
    summary: str
    recommendation: CriticRecommendation

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticReview":
        """Create a CriticReview from a dictionary."""
        scores = data.get("scores", {})
        return cls(
            review_id=data["review_id"],
            accuracy=scores.get("accuracy", 0.0),
            severity_calibration=scores.get("severity_calibration", 0.0),
            actionability=scores.get("actionability", 0.0),
            pragmatism=scores.get("pragmatism", 0.0),
            issues=[CriticIssue.from_dict(i) for i in data.get("issues", [])],
            validated_findings=data.get("validated_findings", []),
            rejected_findings=data.get("rejected_findings", []),
            summary=data.get("summary", ""),
            recommendation=CriticRecommendation(data["recommendation"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert CriticReview to a dictionary."""
        return {
            "review_id": self.review_id,
            "scores": {
                "accuracy": self.accuracy,
                "severity_calibration": self.severity_calibration,
                "actionability": self.actionability,
                "pragmatism": self.pragmatism,
            },
            "issues": [i.to_dict() for i in self.issues],
            "validated_findings": self.validated_findings,
            "rejected_findings": self.rejected_findings,
            "summary": self.summary,
            "recommendation": self.recommendation.value,
        }


# ============================================================
# TDD Plan Dataclasses
# ============================================================

@dataclass
class TDDPhase:
    """A phase in the TDD plan (red, green, or refactor).

    Attributes:
        description: What this phase accomplishes
        test_file: Path to the test file (for red phase)
        test_code: Test code to write (for red phase)
        changes: List of changes to make (for green/refactor phases)
    """
    description: str = ""
    test_file: str = ""
    test_code: str = ""
    changes: list[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TDDPhase":
        """Create a TDDPhase from a dictionary."""
        return cls(
            description=data.get("description", ""),
            test_file=data.get("test_file", ""),
            test_code=data.get("test_code", ""),
            changes=data.get("changes", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert TDDPhase to a dictionary."""
        result: dict[str, Any] = {"description": self.description}
        if self.test_file:
            result["test_file"] = self.test_file
        if self.test_code:
            result["test_code"] = self.test_code
        if self.changes:
            result["changes"] = self.changes
        return result


@dataclass
class TDDPlan:
    """A complete TDD plan with red, green, and refactor phases.

    Attributes:
        red: Write failing test that exposes the problem
        green: Make minimal change to pass the test
        refactor: Clean up without changing behavior
    """
    red: TDDPhase
    green: TDDPhase
    refactor: TDDPhase

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TDDPlan":
        """Create a TDDPlan from a dictionary."""
        return cls(
            red=TDDPhase.from_dict(data.get("red", {})),
            green=TDDPhase.from_dict(data.get("green", {})),
            refactor=TDDPhase.from_dict(data.get("refactor", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert TDDPlan to a dictionary."""
        return {
            "red": self.red.to_dict(),
            "green": self.green.to_dict(),
            "refactor": self.refactor.to_dict(),
        }


# ============================================================
# ModeratorDecision Dataclasses
# ============================================================

@dataclass
class ApprovedFinding:
    """A finding approved by the moderator with a TDD plan.

    Attributes:
        finding_id: ID of the finding
        final_severity: Final severity after moderation
        final_priority: Final priority after moderation
        tdd_plan: TDD plan for fixing the issue
    """
    finding_id: str
    final_severity: str
    final_priority: str
    tdd_plan: TDDPlan

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovedFinding":
        """Create an ApprovedFinding from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            final_severity=data["final_severity"],
            final_priority=data["final_priority"],
            tdd_plan=TDDPlan.from_dict(data.get("tdd_plan", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert ApprovedFinding to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "final_severity": self.final_severity,
            "final_priority": self.final_priority,
            "tdd_plan": self.tdd_plan.to_dict(),
        }


@dataclass
class RejectedFinding:
    """A finding rejected by the moderator.

    Attributes:
        finding_id: ID of the finding
        rejection_reason: Why the finding was rejected
    """
    finding_id: str
    rejection_reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RejectedFinding":
        """Create a RejectedFinding from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            rejection_reason=data["rejection_reason"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert RejectedFinding to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class TechDebtItem:
    """A finding added to the tech debt backlog.

    Attributes:
        finding_id: ID of the finding
        priority: Priority level (e.g., "fix_later")
        reason: Why this is tech debt instead of fix_now
    """
    finding_id: str
    priority: str
    reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechDebtItem":
        """Create a TechDebtItem from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            priority=data["priority"],
            reason=data["reason"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert TechDebtItem to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass
class ModeratorDecision:
    """Output from the refactor-moderator skill.

    Attributes:
        moderation_id: Unique identifier (e.g., "mod-20260101-120000")
        final_verdict: Overall verdict (APPROVE, REFACTOR, ESCALATE)
        approved_findings: List of findings approved for fixing
        rejected_findings: List of rejected findings
        tech_debt_backlog: List of items for tech debt backlog
        summary: Brief description of the decision
        handoff_instructions: Instructions for the coder agent
    """
    moderation_id: str
    final_verdict: Verdict
    approved_findings: list[ApprovedFinding]
    rejected_findings: list[RejectedFinding]
    tech_debt_backlog: list[TechDebtItem]
    summary: str
    handoff_instructions: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModeratorDecision":
        """Create a ModeratorDecision from a dictionary."""
        return cls(
            moderation_id=data["moderation_id"],
            final_verdict=Verdict(data["final_verdict"]),
            approved_findings=[
                ApprovedFinding.from_dict(f) for f in data.get("approved_findings", [])
            ],
            rejected_findings=[
                RejectedFinding.from_dict(f) for f in data.get("rejected_findings", [])
            ],
            tech_debt_backlog=[
                TechDebtItem.from_dict(t) for t in data.get("tech_debt_backlog", [])
            ],
            summary=data.get("summary", ""),
            handoff_instructions=data.get("handoff_instructions", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert ModeratorDecision to a dictionary."""
        return {
            "moderation_id": self.moderation_id,
            "final_verdict": self.final_verdict.value,
            "approved_findings": [f.to_dict() for f in self.approved_findings],
            "rejected_findings": [f.to_dict() for f in self.rejected_findings],
            "tech_debt_backlog": [t.to_dict() for t in self.tech_debt_backlog],
            "summary": self.summary,
            "handoff_instructions": self.handoff_instructions,
        }


# ============================================================
# RetryContext Dataclasses
# ============================================================

@dataclass
class ValidatedFinding:
    """A finding validated in a prior iteration.

    Attributes:
        finding_id: ID of the finding
        validated_in_iteration: Which iteration validated it
        status: Current status (pending_fix, fixed, wont_fix)
    """
    finding_id: str
    validated_in_iteration: int
    status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidatedFinding":
        """Create a ValidatedFinding from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            validated_in_iteration=data["validated_in_iteration"],
            status=data["status"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert ValidatedFinding to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "validated_in_iteration": self.validated_in_iteration,
            "status": self.status,
        }


@dataclass
class RejectedHistoricalFinding:
    """A finding rejected in a prior iteration (do not re-raise).

    Attributes:
        finding_id: ID of the finding
        rejected_in_iteration: Which iteration rejected it
        rejection_reason: Why it was rejected
    """
    finding_id: str
    rejected_in_iteration: int
    rejection_reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RejectedHistoricalFinding":
        """Create a RejectedHistoricalFinding from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            rejected_in_iteration=data["rejected_in_iteration"],
            rejection_reason=data["rejection_reason"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert RejectedHistoricalFinding to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "rejected_in_iteration": self.rejected_in_iteration,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class TechDebtEntry:
    """A tech debt entry accumulated across iterations.

    Attributes:
        finding_id: ID of the finding
        added_in_iteration: Which iteration added it
        description: Description of the tech debt
    """
    finding_id: str
    added_in_iteration: int
    description: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechDebtEntry":
        """Create a TechDebtEntry from a dictionary."""
        return cls(
            finding_id=data["finding_id"],
            added_in_iteration=data["added_in_iteration"],
            description=data["description"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert TechDebtEntry to a dictionary."""
        return {
            "finding_id": self.finding_id,
            "added_in_iteration": self.added_in_iteration,
            "description": self.description,
        }


@dataclass
class IterationHistory:
    """Summary of a single iteration's outcome.

    Attributes:
        iteration: Iteration number (1-3)
        verdict: The verdict for this iteration
        findings_count: Number of findings in this iteration
        fixes_requested: Number of fixes requested
        fixes_completed: Number of fixes completed
    """
    iteration: int
    verdict: Verdict
    findings_count: int
    fixes_requested: int
    fixes_completed: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IterationHistory":
        """Create an IterationHistory from a dictionary."""
        return cls(
            iteration=data["iteration"],
            verdict=Verdict(data["verdict"]),
            findings_count=data["findings_count"],
            fixes_requested=data["fixes_requested"],
            fixes_completed=data["fixes_completed"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert IterationHistory to a dictionary."""
        return {
            "iteration": self.iteration,
            "verdict": self.verdict.value,
            "findings_count": self.findings_count,
            "fixes_requested": self.fixes_requested,
            "fixes_completed": self.fixes_completed,
        }


@dataclass
class RetryContext:
    """State preservation across retry iterations.

    Prevents re-litigation of already-validated or rejected findings.
    Enables progress tracking across the retry loop (max 3 iterations).

    Attributes:
        iteration: Current retry iteration (1-3)
        issue_id: GitHub issue or PR identifier being reviewed
        timestamp: ISO 8601 timestamp
        previously_validated_findings: Findings confirmed as real in prior iterations
        previously_rejected_findings: Findings dismissed as false positives
        cumulative_tech_debt: Issues marked fix_later across all iterations
        iteration_history: Summary of each iteration's outcome
    """
    iteration: int
    issue_id: str
    timestamp: str
    previously_validated_findings: list[ValidatedFinding] = field(default_factory=list)
    previously_rejected_findings: list[RejectedHistoricalFinding] = field(default_factory=list)
    cumulative_tech_debt: list[TechDebtEntry] = field(default_factory=list)
    iteration_history: list[IterationHistory] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetryContext":
        """Create a RetryContext from a dictionary."""
        return cls(
            iteration=data["iteration"],
            issue_id=data["issue_id"],
            timestamp=data["timestamp"],
            previously_validated_findings=[
                ValidatedFinding.from_dict(f)
                for f in data.get("previously_validated_findings", [])
            ],
            previously_rejected_findings=[
                RejectedHistoricalFinding.from_dict(f)
                for f in data.get("previously_rejected_findings", [])
            ],
            cumulative_tech_debt=[
                TechDebtEntry.from_dict(t)
                for t in data.get("cumulative_tech_debt", [])
            ],
            iteration_history=[
                IterationHistory.from_dict(h)
                for h in data.get("iteration_history", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert RetryContext to a dictionary."""
        return {
            "iteration": self.iteration,
            "issue_id": self.issue_id,
            "timestamp": self.timestamp,
            "previously_validated_findings": [
                f.to_dict() for f in self.previously_validated_findings
            ],
            "previously_rejected_findings": [
                f.to_dict() for f in self.previously_rejected_findings
            ],
            "cumulative_tech_debt": [
                t.to_dict() for t in self.cumulative_tech_debt
            ],
            "iteration_history": [
                h.to_dict() for h in self.iteration_history
            ],
        }
