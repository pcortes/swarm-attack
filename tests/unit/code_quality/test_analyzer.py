"""Tests for CodeQualityAnalyzer - the main analysis orchestrator.

Tests verify:
- All three detection modules (SmellDetector, SOLIDChecker, LLMAuditor) are used
- Priority classification follows spec rules (fix_now, fix_later, ignore)
- Verdict determination (APPROVE, REFACTOR, ESCALATE)
- Timing budget enforcement (90 seconds)
- Unified AnalysisResult generation
"""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.code_quality.analyzer import CodeQualityAnalyzer
from swarm_attack.code_quality.models import (
    AnalysisResult,
    Category,
    Finding,
    Priority,
    Severity,
    Verdict,
)


# ============================================================
# Test Fixtures
# ============================================================


@pytest.fixture
def analyzer() -> CodeQualityAnalyzer:
    """Create a fresh analyzer instance for each test."""
    return CodeQualityAnalyzer()


@pytest.fixture
def tmp_python_file(tmp_path: Path) -> Path:
    """Create a temporary Python file for testing."""
    file_path = tmp_path / "test_file.py"
    file_path.write_text("""
class SimpleClass:
    def short_method(self):
        return "hello"
""")
    return file_path


@pytest.fixture
def tmp_problematic_file(tmp_path: Path) -> Path:
    """Create a Python file with multiple issues."""
    file_path = tmp_path / "problematic.py"
    # Create content with known issues:
    # - Long method (> 50 lines)
    # - TODO comment
    # - Empty except block
    content = '''
class ProblematicClass:
    def very_long_method(self):
        """This method is way too long."""
        x = 1
        x = 2
        x = 3
        x = 4
        x = 5
        x = 6
        x = 7
        x = 8
        x = 9
        x = 10
        x = 11
        x = 12
        x = 13
        x = 14
        x = 15
        x = 16
        x = 17
        x = 18
        x = 19
        x = 20
        x = 21
        x = 22
        x = 23
        x = 24
        x = 25
        x = 26
        x = 27
        x = 28
        x = 29
        x = 30
        x = 31
        x = 32
        x = 33
        x = 34
        x = 35
        x = 36
        x = 37
        x = 38
        x = 39
        x = 40
        x = 41
        x = 42
        x = 43
        x = 44
        x = 45
        x = 46
        x = 47
        x = 48
        x = 49
        x = 50
        x = 51
        x = 52
        return x

    def method_with_todo(self):
        # TODO: Implement this properly
        pass

    def method_with_swallowed_exception(self):
        try:
            risky_operation()
        except:
            pass
'''
    file_path.write_text(content)
    return file_path


def create_finding(
    finding_id: str = "CQA-001",
    severity: Severity = Severity.HIGH,
    category: Category = Category.CODE_SMELL,
    priority: Priority = Priority.FIX_NOW,
    confidence: float = 0.9,
) -> Finding:
    """Helper to create a Finding with sensible defaults."""
    return Finding(
        finding_id=finding_id,
        severity=severity,
        category=category,
        file="test.py",
        line=10,
        title="Test Finding",
        description="A test finding",
        priority=priority,
        confidence=confidence,
    )


# ============================================================
# Test: Analyzer Uses All Detectors
# ============================================================


class TestAnalyzerUsesAllDetectors:
    """Verify that all three detection modules are called."""

    def test_analyzer_calls_smell_detector(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """SmellDetector should be used during analysis."""
        with patch.object(
            analyzer.smell_detector, "analyze_file", return_value=[]
        ) as mock_smell:
            analyzer.analyze_files([tmp_python_file])
            mock_smell.assert_called()

    def test_analyzer_calls_solid_checker(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """SOLIDChecker should be used during analysis."""
        with patch.object(
            analyzer.solid_checker, "analyze_file", return_value=[]
        ) as mock_solid:
            analyzer.analyze_files([tmp_python_file])
            mock_solid.assert_called()

    def test_analyzer_calls_llm_auditor(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """LLMAuditor should be used during analysis."""
        with patch.object(
            analyzer.llm_auditor, "analyze_file", return_value=[]
        ) as mock_llm:
            analyzer.analyze_files([tmp_python_file])
            mock_llm.assert_called()

    def test_analyze_single_file_returns_findings(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """analyze_file should return list of Findings from all detectors."""
        findings = analyzer.analyze_file(tmp_problematic_file)
        assert isinstance(findings, list)
        # Should find at least the long method and TODO
        assert len(findings) >= 2

    def test_analyze_files_returns_analysis_result(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """analyze_files should return an AnalysisResult object."""
        result = analyzer.analyze_files([tmp_python_file])
        assert isinstance(result, AnalysisResult)
        assert str(tmp_python_file) in result.files_analyzed


# ============================================================
# Test: Priority Classification
# ============================================================


class TestPriorityClassification:
    """Test priority classification rules from the spec."""

    def test_critical_high_confidence_is_fix_now(self, analyzer: CodeQualityAnalyzer):
        """Critical severity with confidence > 0.8 should be FIX_NOW."""
        finding = create_finding(
            severity=Severity.CRITICAL,
            confidence=0.9,
            priority=Priority.FIX_LATER,  # Will be overridden
        )
        prioritized = analyzer.prioritize_findings([finding])
        assert prioritized[0].priority == Priority.FIX_NOW

    def test_high_severity_high_confidence_is_fix_now(
        self, analyzer: CodeQualityAnalyzer
    ):
        """High severity with confidence > 0.8 should be FIX_NOW."""
        finding = create_finding(
            severity=Severity.HIGH,
            confidence=0.85,
            priority=Priority.FIX_LATER,
        )
        prioritized = analyzer.prioritize_findings([finding])
        assert prioritized[0].priority == Priority.FIX_NOW

    def test_high_severity_low_confidence_is_fix_later(
        self, analyzer: CodeQualityAnalyzer
    ):
        """High severity with lower confidence should be FIX_LATER."""
        finding = create_finding(
            severity=Severity.HIGH,
            confidence=0.6,
            priority=Priority.FIX_NOW,  # Will be overridden
        )
        prioritized = analyzer.prioritize_findings([finding])
        assert prioritized[0].priority == Priority.FIX_LATER

    def test_medium_severity_is_fix_later(self, analyzer: CodeQualityAnalyzer):
        """Medium severity should be FIX_LATER regardless of confidence."""
        finding = create_finding(
            severity=Severity.MEDIUM,
            confidence=0.95,
            priority=Priority.FIX_NOW,
        )
        prioritized = analyzer.prioritize_findings([finding])
        assert prioritized[0].priority == Priority.FIX_LATER

    def test_low_severity_is_ignore(self, analyzer: CodeQualityAnalyzer):
        """Low severity should be IGNORE."""
        finding = create_finding(
            severity=Severity.LOW,
            confidence=0.95,
            priority=Priority.FIX_NOW,
        )
        prioritized = analyzer.prioritize_findings([finding])
        assert prioritized[0].priority == Priority.IGNORE


# ============================================================
# Test: Verdict Determination
# ============================================================


class TestVerdictDetermination:
    """Test verdict determination logic."""

    def test_approve_when_no_fix_now_findings(self, analyzer: CodeQualityAnalyzer):
        """APPROVE when there are no fix_now findings."""
        findings = [
            create_finding(priority=Priority.FIX_LATER),
            create_finding(finding_id="CQA-002", priority=Priority.IGNORE),
        ]
        verdict = analyzer.determine_verdict(findings)
        assert verdict == Verdict.APPROVE.value

    def test_refactor_when_has_fix_now_findings(self, analyzer: CodeQualityAnalyzer):
        """REFACTOR when there are addressable fix_now findings."""
        findings = [
            create_finding(priority=Priority.FIX_NOW),
            create_finding(finding_id="CQA-002", priority=Priority.FIX_LATER),
        ]
        verdict = analyzer.determine_verdict(findings)
        assert verdict == Verdict.REFACTOR.value

    def test_approve_when_no_findings(self, analyzer: CodeQualityAnalyzer):
        """APPROVE when there are no findings at all."""
        verdict = analyzer.determine_verdict([])
        assert verdict == Verdict.APPROVE.value

    def test_escalate_with_major_architectural_issues(
        self, analyzer: CodeQualityAnalyzer
    ):
        """ESCALATE when there are multiple critical architectural issues."""
        # Multiple critical SOLID violations suggest architectural problems
        findings = [
            create_finding(
                finding_id="SOLID-001",
                severity=Severity.CRITICAL,
                category=Category.SOLID,
                priority=Priority.FIX_NOW,
            ),
            create_finding(
                finding_id="SOLID-002",
                severity=Severity.CRITICAL,
                category=Category.SOLID,
                priority=Priority.FIX_NOW,
            ),
            create_finding(
                finding_id="SOLID-003",
                severity=Severity.CRITICAL,
                category=Category.SOLID,
                priority=Priority.FIX_NOW,
            ),
        ]
        # Mark as architectural issue (simulating 3+ retry iterations)
        verdict = analyzer.determine_verdict(findings, retry_iteration=3)
        assert verdict == Verdict.ESCALATE.value


# ============================================================
# Test: Timing Budget
# ============================================================


class TestTimingBudget:
    """Test timing budget enforcement."""

    def test_timing_budget_constant_is_90_seconds(self):
        """Timing budget should be 90 seconds per spec."""
        assert CodeQualityAnalyzer.TIMING_BUDGET_SECONDS == 90

    def test_check_timing_budget_within_limit(self, analyzer: CodeQualityAnalyzer):
        """check_timing_budget returns True when within budget."""
        start_time = time.time()
        assert analyzer.check_timing_budget(start_time) is True

    def test_check_timing_budget_exceeded(self, analyzer: CodeQualityAnalyzer):
        """check_timing_budget returns False when budget exceeded."""
        # Simulate start time 100 seconds ago
        start_time = time.time() - 100
        assert analyzer.check_timing_budget(start_time) is False


# ============================================================
# Test: Confidence Calculation
# ============================================================


class TestConfidenceCalculation:
    """Test confidence score calculation."""

    def test_calculate_confidence_returns_float(self, analyzer: CodeQualityAnalyzer):
        """calculate_confidence should return a float between 0 and 1."""
        finding = create_finding(confidence=0.85)
        confidence = analyzer.calculate_confidence(finding)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_llm_hallucination_high_confidence(self, analyzer: CodeQualityAnalyzer):
        """LLM hallucinations should have high confidence (detected reliably)."""
        finding = create_finding(
            category=Category.LLM_HALLUCINATION,
            confidence=0.95,
        )
        confidence = analyzer.calculate_confidence(finding)
        assert confidence >= 0.9


# ============================================================
# Test: AnalysisResult Generation
# ============================================================


class TestAnalysisResultGeneration:
    """Test that AnalysisResult is properly generated."""

    def test_analysis_result_has_correct_id_format(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """Analysis ID should match format: cqa-YYYYMMDD-HHMMSS."""
        result = analyzer.analyze_files([tmp_python_file])
        assert result.analysis_id.startswith("cqa-")
        # Validate timestamp portion
        parts = result.analysis_id.split("-")
        assert len(parts) == 3
        # Date part should be 8 digits
        assert len(parts[1]) == 8
        # Time part should be 6 digits
        assert len(parts[2]) == 6

    def test_analysis_result_counts_severities(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """AnalysisResult should correctly count severity levels."""
        result = analyzer.analyze_files([tmp_problematic_file])
        # Counts should sum to total_issues
        total = result.critical + result.high + result.medium + result.low
        assert total == result.total_issues

    def test_analysis_result_counts_priorities(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """AnalysisResult should correctly count priority levels."""
        result = analyzer.analyze_files([tmp_problematic_file])
        # Priority counts should sum to total_issues
        total = result.fix_now + result.fix_later + result.ignore
        assert total == result.total_issues

    def test_analysis_result_has_recommendation(
        self, analyzer: CodeQualityAnalyzer, tmp_python_file: Path
    ):
        """AnalysisResult should have a recommendation verdict."""
        result = analyzer.analyze_files([tmp_python_file])
        assert result.recommendation in [
            Verdict.APPROVE,
            Verdict.REFACTOR,
            Verdict.ESCALATE,
        ]


# ============================================================
# Test: Edge Cases
# ============================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_analyze_nonexistent_file(self, analyzer: CodeQualityAnalyzer):
        """Analyzing non-existent file should return empty findings."""
        findings = analyzer.analyze_file(Path("/nonexistent/file.py"))
        assert findings == []

    def test_analyze_empty_file_list(self, analyzer: CodeQualityAnalyzer):
        """Analyzing empty file list should return APPROVE."""
        result = analyzer.analyze_files([])
        assert result.recommendation == Verdict.APPROVE
        assert result.total_issues == 0

    def test_analyze_non_python_file(self, analyzer: CodeQualityAnalyzer, tmp_path: Path):
        """Analyzing non-Python file should be handled gracefully."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("This is not Python code.")
        findings = analyzer.analyze_file(txt_file)
        # Should return empty list or skip gracefully
        assert isinstance(findings, list)

    def test_analyze_file_with_syntax_error(
        self, analyzer: CodeQualityAnalyzer, tmp_path: Path
    ):
        """Files with syntax errors should be handled gracefully."""
        bad_file = tmp_path / "syntax_error.py"
        bad_file.write_text("def broken(:\n    pass")
        findings = analyzer.analyze_file(bad_file)
        assert isinstance(findings, list)


# ============================================================
# Test: Integration
# ============================================================


class TestIntegration:
    """Integration tests for the full analysis pipeline."""

    def test_full_analysis_pipeline(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """Full analysis should detect issues and produce valid result."""
        result = analyzer.analyze_files([tmp_problematic_file])

        # Should have findings
        assert result.total_issues > 0

        # Should have a valid recommendation
        assert result.recommendation in [
            Verdict.APPROVE,
            Verdict.REFACTOR,
            Verdict.ESCALATE,
        ]

        # Should have files_analyzed populated
        assert len(result.files_analyzed) == 1

        # Should have a refactor_summary if there are issues
        if result.total_issues > 0:
            assert result.refactor_summary != ""

    def test_findings_have_required_fields(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """All findings should have the required evidence fields."""
        result = analyzer.analyze_files([tmp_problematic_file])

        for finding in result.findings:
            # Every finding must have file:line evidence (per spec)
            assert finding.file != ""
            assert finding.line > 0
            assert finding.title != ""
            assert finding.description != ""

    def test_analysis_completes_within_timing_budget(
        self, analyzer: CodeQualityAnalyzer, tmp_problematic_file: Path
    ):
        """Analysis should complete within the 90-second timing budget."""
        start_time = time.time()
        analyzer.analyze_files([tmp_problematic_file])
        elapsed = time.time() - start_time

        assert elapsed < CodeQualityAnalyzer.TIMING_BUDGET_SECONDS
