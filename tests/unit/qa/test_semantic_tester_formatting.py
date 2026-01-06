"""Unit tests for SemanticTesterAgent formatting (TDD).

Tests the format_results() method that produces Rich CLI output.
"""
import pytest
from unittest.mock import Mock

try:
    from swarm_attack.qa.agents.semantic_tester import (
        SemanticTesterAgent,
        SemanticTestResult,
        SemanticVerdict,
        Evidence,
        SemanticIssue,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="SemanticTesterAgent not yet implemented"
)


class TestFormatResultsMethod:
    """Test format_results() method exists and produces output."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_format_results_method_exists(self, agent):
        """format_results method should exist on agent."""
        assert hasattr(agent, "format_results")
        assert callable(agent.format_results)

    def test_format_results_returns_string(self, agent):
        """format_results should return a string."""
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        output = agent.format_results(result)
        assert isinstance(output, str)

    def test_format_results_produces_readable_output(self, agent):
        """format_results should produce human-readable output."""
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            evidence=[Evidence("Test passed", "pytest", 0.95)],
            recommendations=["Keep up the good work"],
        )
        output = agent.format_results(result)
        # Should contain verdict
        assert "PASS" in output
        # Should be non-empty
        assert len(output) > 10


class TestVerdictFormatting:
    """Test verdict display with appropriate colors."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_pass_verdict_formatted(self, agent):
        """PASS verdict should appear in output."""
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        output = agent.format_results(result)
        assert "PASS" in output

    def test_fail_verdict_formatted(self, agent):
        """FAIL verdict should appear in output."""
        result = SemanticTestResult(verdict=SemanticVerdict.FAIL)
        output = agent.format_results(result)
        assert "FAIL" in output

    def test_partial_verdict_formatted(self, agent):
        """PARTIAL verdict should appear in output."""
        result = SemanticTestResult(verdict=SemanticVerdict.PARTIAL)
        output = agent.format_results(result)
        assert "PARTIAL" in output


class TestEvidenceFormatting:
    """Test evidence display with confidence styling."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_evidence_source_shown(self, agent):
        """Evidence source should appear in output."""
        evidence = Evidence(
            description="All tests passed",
            source="pytest",
            confidence=0.95,
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            evidence=[evidence],
        )
        output = agent.format_results(result)
        assert "pytest" in output

    def test_evidence_description_shown(self, agent):
        """Evidence description should appear in output."""
        evidence = Evidence(
            description="All unit tests passed successfully",
            source="pytest",
            confidence=0.95,
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            evidence=[evidence],
        )
        output = agent.format_results(result)
        assert "All unit tests passed successfully" in output

    def test_high_confidence_shown(self, agent):
        """High confidence (>80%) should be displayed."""
        evidence = Evidence(
            description="Test",
            source="src",
            confidence=0.95,
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            evidence=[evidence],
        )
        output = agent.format_results(result)
        # Should show 95% somewhere
        assert "95%" in output

    def test_medium_confidence_shown(self, agent):
        """Medium confidence (50-80%) should be displayed."""
        evidence = Evidence(
            description="Test",
            source="src",
            confidence=0.65,
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            evidence=[evidence],
        )
        output = agent.format_results(result)
        assert "65%" in output

    def test_low_confidence_shown(self, agent):
        """Low confidence (<50%) should be displayed."""
        evidence = Evidence(
            description="Test",
            source="src",
            confidence=0.35,
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            evidence=[evidence],
        )
        output = agent.format_results(result)
        assert "35%" in output

    def test_multiple_evidence_items(self, agent):
        """Multiple evidence items should all be shown."""
        evidence1 = Evidence("First test", "pytest", 0.9)
        evidence2 = Evidence("Second test", "mypy", 0.85)
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            evidence=[evidence1, evidence2],
        )
        output = agent.format_results(result)
        assert "First test" in output
        assert "Second test" in output
        assert "pytest" in output
        assert "mypy" in output


class TestIssueFormatting:
    """Test issue display with severity colors."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_critical_issue_shown(self, agent):
        """Critical severity issues should be displayed."""
        issue = SemanticIssue(
            severity="critical",
            description="Security vulnerability found",
            location="src/auth.py:42",
            suggestion="Fix authentication",
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=[issue],
        )
        output = agent.format_results(result)
        assert "critical" in output.lower()
        assert "Security vulnerability found" in output

    def test_major_issue_shown(self, agent):
        """Major severity issues should be displayed."""
        issue = SemanticIssue(
            severity="major",
            description="Performance regression",
            location="src/data.py:100",
            suggestion="Optimize query",
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=[issue],
        )
        output = agent.format_results(result)
        assert "major" in output.lower()
        assert "Performance regression" in output

    def test_minor_issue_shown(self, agent):
        """Minor severity issues should be displayed."""
        issue = SemanticIssue(
            severity="minor",
            description="Code style issue",
            location="src/utils.py:5",
            suggestion="Follow PEP8",
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            issues=[issue],
        )
        output = agent.format_results(result)
        assert "minor" in output.lower()
        assert "Code style issue" in output

    def test_issue_location_shown(self, agent):
        """Issue location should be displayed."""
        issue = SemanticIssue(
            severity="critical",
            description="Bug",
            location="src/main.py:42",
            suggestion="Fix it",
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=[issue],
        )
        output = agent.format_results(result)
        assert "src/main.py:42" in output

    def test_issue_suggestion_shown(self, agent):
        """Issue suggestion should be displayed."""
        issue = SemanticIssue(
            severity="major",
            description="Problem",
            location="file.py:1",
            suggestion="Try this specific fix",
        )
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=[issue],
        )
        output = agent.format_results(result)
        assert "Try this specific fix" in output

    def test_multiple_issues(self, agent):
        """Multiple issues should all be shown."""
        issues = [
            SemanticIssue("critical", "First issue", "a.py:1", "Fix A"),
            SemanticIssue("major", "Second issue", "b.py:2", "Fix B"),
            SemanticIssue("minor", "Third issue", "c.py:3", "Fix C"),
        ]
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=issues,
        )
        output = agent.format_results(result)
        assert "First issue" in output
        assert "Second issue" in output
        assert "Third issue" in output


class TestRecommendationsFormatting:
    """Test recommendations display."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_recommendations_shown(self, agent):
        """Recommendations should be displayed."""
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            recommendations=[
                "Add more unit tests",
                "Review error handling",
            ],
        )
        output = agent.format_results(result)
        assert "Add more unit tests" in output
        assert "Review error handling" in output


class TestEmptyResults:
    """Test handling of empty/minimal results."""

    @pytest.fixture
    def agent(self, tmp_path):
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_no_evidence(self, agent):
        """Results with no evidence should not crash."""
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        output = agent.format_results(result)
        assert isinstance(output, str)
        assert "PASS" in output

    def test_no_issues(self, agent):
        """Results with no issues should not crash."""
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        output = agent.format_results(result)
        assert isinstance(output, str)

    def test_no_recommendations(self, agent):
        """Results with no recommendations should not crash."""
        result = SemanticTestResult(verdict=SemanticVerdict.PASS)
        output = agent.format_results(result)
        assert isinstance(output, str)
