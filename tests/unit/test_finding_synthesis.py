"""Tests for finding synthesis functionality."""

import pytest

from swarm_attack.commit_review.synthesis import (
    synthesize_findings,
    calculate_score,
    determine_verdict,
)
from swarm_attack.commit_review.models import (
    Finding,
    Severity,
    Verdict,
    ReviewReport,
    CommitReview,
)


class TestSynthesizeFindings:
    """Tests for synthesize_findings function."""

    def _make_finding(
        self,
        commit_sha: str = "abc123",
        severity: Severity = Severity.MEDIUM,
        expert: str = "test_expert",
    ) -> Finding:
        """Helper to create a Finding for testing."""
        return Finding(
            commit_sha=commit_sha,
            expert=expert,
            severity=severity,
            category="quality",
            description="Test finding",
            evidence="file.py:10",
        )

    def test_synthesize_findings(self):
        """Combines findings from all agents into unified report."""
        findings = [
            self._make_finding("sha1", Severity.LOW, "expert_a"),
            self._make_finding("sha1", Severity.MEDIUM, "expert_b"),
            self._make_finding("sha2", Severity.HIGH, "expert_a"),
        ]

        report = synthesize_findings(findings)

        # Report should be a ReviewReport
        assert isinstance(report, ReviewReport)

        # Should have reviews for each commit
        assert len(report.commit_reviews) == 2

        # Findings should be grouped by commit
        sha1_review = next(r for r in report.commit_reviews if r.commit_sha == "sha1")
        assert len(sha1_review.findings) == 2

        sha2_review = next(r for r in report.commit_reviews if r.commit_sha == "sha2")
        assert len(sha2_review.findings) == 1

    def test_synthesize_empty_findings(self):
        """Returns empty report when no findings."""
        report = synthesize_findings([])

        assert isinstance(report, ReviewReport)
        assert len(report.commit_reviews) == 0


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_calculate_score_weighted(self):
        """Weighted score calculated from criteria."""
        findings = [
            Finding(
                commit_sha="sha1",
                expert="reliability",
                severity=Severity.CRITICAL,
                category="production_bug",
                description="Production bug without evidence",
                evidence="file.py:10",
            ),
            Finding(
                commit_sha="sha1",
                expert="test_coverage",
                severity=Severity.LOW,
                category="coverage",
                description="Minor coverage gap",
                evidence="file.py:20",
            ),
        ]

        score = calculate_score(findings)

        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0

        # Critical finding should significantly lower score
        assert score < 0.7

    def test_calculate_score_no_findings(self):
        """Perfect score when no findings."""
        score = calculate_score([])

        assert score == 1.0

    def test_calculate_score_all_low_severity(self):
        """High score when only low severity findings."""
        findings = [
            Finding(
                commit_sha="sha1",
                expert="test",
                severity=Severity.LOW,
                category="style",
                description="Minor style issue",
                evidence="file.py:10",
            ),
        ]

        score = calculate_score(findings)

        assert score >= 0.8


class TestDetermineVerdict:
    """Tests for determine_verdict function."""

    def test_determine_verdict_leave(self):
        """LEAVE verdict for clean commits."""
        findings = []  # No findings
        score = 1.0

        verdict = determine_verdict(findings, score)

        assert verdict == Verdict.LEAVE

    def test_determine_verdict_fix(self):
        """FIX verdict for commits with medium issues."""
        findings = [
            Finding(
                commit_sha="sha1",
                expert="test",
                severity=Severity.MEDIUM,
                category="quality",
                description="Missing error handling",
                evidence="file.py:10",
            ),
        ]
        score = 0.6

        verdict = determine_verdict(findings, score)

        assert verdict == Verdict.FIX

    def test_determine_verdict_revert(self):
        """REVERT verdict for commits with critical issues."""
        findings = [
            Finding(
                commit_sha="sha1",
                expert="reliability",
                severity=Severity.CRITICAL,
                category="production",
                description="Breaks production API",
                evidence="api.py:50",
            ),
        ]
        score = 0.2

        verdict = determine_verdict(findings, score)

        assert verdict == Verdict.REVERT

    def test_determine_verdict_threshold(self):
        """Verdict thresholds are correctly applied."""
        # Score >= 0.8 -> LEAVE
        assert determine_verdict([], 0.85) == Verdict.LEAVE

        # Score 0.5-0.8 -> FIX
        findings = [
            Finding(
                commit_sha="sha1",
                expert="test",
                severity=Severity.MEDIUM,
                category="quality",
                description="Issue",
                evidence="file.py:10",
            ),
        ]
        assert determine_verdict(findings, 0.65) == Verdict.FIX

        # Score < 0.5 with critical -> REVERT
        critical = [
            Finding(
                commit_sha="sha1",
                expert="test",
                severity=Severity.CRITICAL,
                category="quality",
                description="Critical issue",
                evidence="file.py:10",
            ),
        ]
        assert determine_verdict(critical, 0.3) == Verdict.REVERT
