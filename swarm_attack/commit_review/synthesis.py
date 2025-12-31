"""Finding synthesis, scoring, and verdict determination."""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from swarm_attack.commit_review.models import (
    Finding,
    Severity,
    Verdict,
    CommitReview,
    ReviewReport,
)


# Severity weights for scoring
SEVERITY_WEIGHTS = {
    Severity.LOW: 0.05,
    Severity.MEDIUM: 0.15,
    Severity.HIGH: 0.30,
    Severity.CRITICAL: 0.50,
}

# Score thresholds for verdicts
LEAVE_THRESHOLD = 0.8
FIX_THRESHOLD = 0.5


def synthesize_findings(
    findings: list[Finding],
    repo_path: str = "",
    branch: str = "main",
    since: str = "24 hours ago",
) -> ReviewReport:
    """Combine findings from all agents into a unified report.

    Args:
        findings: List of findings from all review agents
        repo_path: Path to the repository
        branch: Branch being reviewed
        since: Time range for the review

    Returns:
        Complete ReviewReport with all commit reviews
    """
    if not findings:
        return ReviewReport(
            generated_at=datetime.now().isoformat(),
            repo_path=repo_path,
            branch=branch,
            since=since,
            commit_reviews=[],
            overall_score=1.0,
            summary="No findings to report",
        )

    # Group findings by commit
    by_commit: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_commit[finding.commit_sha].append(finding)

    # Create commit reviews
    commit_reviews = []
    total_score = 0.0

    for commit_sha, commit_findings in by_commit.items():
        score = calculate_score(commit_findings)
        verdict = determine_verdict(commit_findings, score)

        review = CommitReview(
            commit_sha=commit_sha,
            message="",  # Would be populated from commit info
            author="",  # Would be populated from commit info
            findings=commit_findings,
            score=score,
            verdict=verdict,
            tdd_plans=[],  # Will be generated separately
        )
        commit_reviews.append(review)
        total_score += score

    # Calculate overall score
    overall_score = total_score / len(commit_reviews) if commit_reviews else 1.0

    # Generate summary
    leave_count = sum(1 for r in commit_reviews if r.verdict == Verdict.LEAVE)
    fix_count = sum(1 for r in commit_reviews if r.verdict == Verdict.FIX)
    revert_count = sum(1 for r in commit_reviews if r.verdict == Verdict.REVERT)

    summary = _generate_summary(len(commit_reviews), leave_count, fix_count, revert_count)

    return ReviewReport(
        generated_at=datetime.now().isoformat(),
        repo_path=repo_path,
        branch=branch,
        since=since,
        commit_reviews=commit_reviews,
        overall_score=overall_score,
        summary=summary,
    )


def calculate_score(findings: list[Finding]) -> float:
    """Calculate a weighted score based on findings.

    Score starts at 1.0 (perfect) and decreases based on
    the severity of findings.

    Args:
        findings: List of findings to score

    Returns:
        Score between 0.0 and 1.0
    """
    if not findings:
        return 1.0

    # Calculate total penalty
    total_penalty = 0.0
    for finding in findings:
        weight = SEVERITY_WEIGHTS.get(finding.severity, 0.1)
        total_penalty += weight

    # Score is 1.0 minus penalty, clamped to [0, 1]
    score = max(0.0, min(1.0, 1.0 - total_penalty))
    return round(score, 2)


def determine_verdict(findings: list[Finding], score: float) -> Verdict:
    """Determine verdict based on findings and score.

    Verdict logic:
    - LEAVE: Score >= 0.8 (minor or no issues)
    - FIX: Score 0.5-0.8 (issues that should be addressed)
    - REVERT: Score < 0.5 OR any CRITICAL finding

    Args:
        findings: List of findings
        score: Calculated score

    Returns:
        Verdict enum value
    """
    # Check for critical findings - always REVERT
    has_critical = any(f.severity == Severity.CRITICAL for f in findings)
    if has_critical and score < FIX_THRESHOLD:
        return Verdict.REVERT

    # Score-based verdicts
    if score >= LEAVE_THRESHOLD:
        return Verdict.LEAVE
    elif score >= FIX_THRESHOLD:
        return Verdict.FIX
    else:
        return Verdict.REVERT


def _generate_summary(
    total: int,
    leave: int,
    fix: int,
    revert: int,
) -> str:
    """Generate a human-readable summary."""
    parts = []
    parts.append(f"{total} commit{'s' if total != 1 else ''} reviewed")

    if leave > 0:
        parts.append(f"{leave} OK")
    if fix > 0:
        parts.append(f"{fix} need{'s' if fix == 1 else ''} fixes")
    if revert > 0:
        parts.append(f"{revert} should be reverted")

    return ", ".join(parts)
