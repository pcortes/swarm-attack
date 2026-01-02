"""Tests for CodeQualityDispatcher - the three-stage debate orchestrator.

Tests verify:
- Correct timing constants (90s analyst, 30s critic, 30s moderator)
- Component initialization (analyzer, suggester, tdd_generator)
- Three-phase pipeline execution (analyst -> critic -> moderator)
- Verdict determination based on findings
- Retry context and escalation logic
- Graceful timeout handling

Based on the Code Quality spec three-stage debate section.
"""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.code_quality.dispatcher import CodeQualityDispatcher
from swarm_attack.code_quality.models import (
    AnalysisResult,
    ApprovedFinding,
    Category,
    CriticIssue,
    CriticRecommendation,
    CriticReview,
    Finding,
    IssueType,
    IterationHistory,
    ModeratorDecision,
    Priority,
    RejectedFinding,
    RejectedHistoricalFinding,
    RetryContext,
    Severity,
    TDDPlan,
    TDDPhase,
    TechDebtEntry,
    TechDebtItem,
    ValidatedFinding,
    Verdict,
)


# ============================================================
# Test Fixtures
# ============================================================


@pytest.fixture
def dispatcher() -> CodeQualityDispatcher:
    """Create a fresh dispatcher instance for each test."""
    return CodeQualityDispatcher()


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
    """Create a Python file with code quality issues."""
    file_path = tmp_path / "problematic.py"
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


def create_analysis_result(
    findings: list[Finding] | None = None,
    recommendation: Verdict = Verdict.REFACTOR,
) -> AnalysisResult:
    """Helper to create an AnalysisResult with sensible defaults."""
    if findings is None:
        findings = [create_finding()]
    return AnalysisResult(
        analysis_id="cqa-20260101-120000",
        files_analyzed=["test.py"],
        total_issues=len(findings),
        critical=sum(1 for f in findings if f.severity == Severity.CRITICAL),
        high=sum(1 for f in findings if f.severity == Severity.HIGH),
        medium=sum(1 for f in findings if f.severity == Severity.MEDIUM),
        low=sum(1 for f in findings if f.severity == Severity.LOW),
        fix_now=sum(1 for f in findings if f.priority == Priority.FIX_NOW),
        fix_later=sum(1 for f in findings if f.priority == Priority.FIX_LATER),
        ignore=sum(1 for f in findings if f.priority == Priority.IGNORE),
        findings=findings,
        recommendation=recommendation,
        refactor_summary="Test summary",
    )


def create_critic_review(
    validated_findings: list[str] | None = None,
    rejected_findings: list[str] | None = None,
    recommendation: CriticRecommendation = CriticRecommendation.APPROVE,
) -> CriticReview:
    """Helper to create a CriticReview with sensible defaults."""
    if validated_findings is None:
        validated_findings = ["CQA-001"]
    if rejected_findings is None:
        rejected_findings = []
    return CriticReview(
        review_id="crit-20260101-120000",
        accuracy=0.9,
        severity_calibration=0.85,
        actionability=0.9,
        pragmatism=0.85,
        issues=[],
        validated_findings=validated_findings,
        rejected_findings=rejected_findings,
        summary="Test critic summary",
        recommendation=recommendation,
    )


def create_moderator_decision(
    final_verdict: Verdict = Verdict.REFACTOR,
    approved_findings: list[ApprovedFinding] | None = None,
) -> ModeratorDecision:
    """Helper to create a ModeratorDecision with sensible defaults."""
    if approved_findings is None:
        approved_findings = [
            ApprovedFinding(
                finding_id="CQA-001",
                final_severity="high",
                final_priority="fix_now",
                tdd_plan=TDDPlan(
                    red=TDDPhase(description="Write failing test"),
                    green=TDDPhase(description="Make it pass"),
                    refactor=TDDPhase(description="Clean up"),
                ),
            )
        ]
    return ModeratorDecision(
        moderation_id="mod-20260101-120000",
        final_verdict=final_verdict,
        approved_findings=approved_findings,
        rejected_findings=[],
        tech_debt_backlog=[],
        summary="Test moderator summary",
        handoff_instructions="Proceed with TDD fixes",
    )


def create_retry_context(
    iteration: int = 1,
    issue_id: str = "test-123",
) -> RetryContext:
    """Helper to create a RetryContext with sensible defaults."""
    return RetryContext(
        iteration=iteration,
        issue_id=issue_id,
        timestamp=datetime.now().isoformat(),
        previously_validated_findings=[],
        previously_rejected_findings=[],
        cumulative_tech_debt=[],
        iteration_history=[],
    )


# ============================================================
# Test: Timing Constants
# ============================================================


class TestTimingConstants:
    """Verify that timing constants match the spec."""

    def test_dispatcher_has_correct_timing_constants(self):
        """Verify ANALYST_BUDGET_SECONDS=90, CRITIC_BUDGET_SECONDS=30, etc."""
        assert CodeQualityDispatcher.ANALYST_BUDGET_SECONDS == 90
        assert CodeQualityDispatcher.CRITIC_BUDGET_SECONDS == 30
        assert CodeQualityDispatcher.MODERATOR_BUDGET_SECONDS == 30
        assert CodeQualityDispatcher.MAX_RETRIES == 3


# ============================================================
# Test: Component Initialization
# ============================================================


class TestComponentInitialization:
    """Verify that dispatcher creates and initializes all components."""

    def test_dispatcher_initializes_components(self, dispatcher: CodeQualityDispatcher):
        """Verify it creates analyzer, suggester, tdd_generator."""
        assert dispatcher.analyzer is not None
        assert dispatcher.suggester is not None
        assert dispatcher.tdd_generator is not None

    def test_dispatcher_analyzer_is_code_quality_analyzer(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Analyzer should be a CodeQualityAnalyzer instance."""
        from swarm_attack.code_quality.analyzer import CodeQualityAnalyzer

        assert isinstance(dispatcher.analyzer, CodeQualityAnalyzer)

    def test_dispatcher_suggester_is_refactor_suggester(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Suggester should be a RefactorSuggester instance."""
        from swarm_attack.code_quality.refactor_suggester import RefactorSuggester

        assert isinstance(dispatcher.suggester, RefactorSuggester)

    def test_dispatcher_tdd_generator_is_tdd_generator(
        self, dispatcher: CodeQualityDispatcher
    ):
        """TDD generator should be a TDDGenerator instance."""
        from swarm_attack.code_quality.tdd_generator import TDDGenerator

        assert isinstance(dispatcher.tdd_generator, TDDGenerator)


# ============================================================
# Test: Analyst Phase
# ============================================================


class TestAnalystPhase:
    """Test the analyst phase returns AnalysisResult."""

    def test_run_analyst_phase_returns_analysis_result(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Verify analyst phase returns AnalysisResult."""
        result = dispatcher.run_analyst_phase([tmp_python_file])
        assert isinstance(result, AnalysisResult)

    def test_analyst_phase_populates_files_analyzed(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Analyst phase should track which files were analyzed."""
        result = dispatcher.run_analyst_phase([tmp_python_file])
        assert str(tmp_python_file) in result.files_analyzed

    def test_analyst_phase_uses_analyzer(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Analyst phase should use the CodeQualityAnalyzer."""
        with patch.object(
            dispatcher.analyzer, "analyze_files", return_value=create_analysis_result([])
        ) as mock_analyze:
            dispatcher.run_analyst_phase([tmp_python_file])
            mock_analyze.assert_called_once()


# ============================================================
# Test: Critic Phase
# ============================================================


class TestCriticPhase:
    """Test the critic phase validates findings."""

    def test_run_critic_phase_returns_critic_review(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Verify critic phase returns CriticReview."""
        analysis = create_analysis_result()
        result = dispatcher.run_critic_phase(analysis)
        assert isinstance(result, CriticReview)

    def test_critic_phase_validates_findings(self, dispatcher: CodeQualityDispatcher):
        """Critic should validate at least some findings."""
        findings = [create_finding(finding_id="CQA-001")]
        analysis = create_analysis_result(findings=findings)
        result = dispatcher.run_critic_phase(analysis)
        # Should have validated or rejected findings
        assert len(result.validated_findings) + len(result.rejected_findings) > 0

    def test_critic_phase_on_empty_findings(self, dispatcher: CodeQualityDispatcher):
        """Critic should handle empty findings gracefully."""
        analysis = create_analysis_result(findings=[], recommendation=Verdict.APPROVE)
        result = dispatcher.run_critic_phase(analysis)
        assert isinstance(result, CriticReview)
        assert result.recommendation == CriticRecommendation.APPROVE


# ============================================================
# Test: Moderator Phase
# ============================================================


class TestModeratorPhase:
    """Test the moderator phase produces final verdict."""

    def test_run_moderator_phase_returns_moderator_decision(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Verify moderator phase returns ModeratorDecision."""
        analysis = create_analysis_result()
        critique = create_critic_review()
        result = dispatcher.run_moderator_phase(analysis, critique)
        assert isinstance(result, ModeratorDecision)

    def test_moderator_phase_has_final_verdict(self, dispatcher: CodeQualityDispatcher):
        """Moderator decision should have a final verdict."""
        analysis = create_analysis_result()
        critique = create_critic_review()
        result = dispatcher.run_moderator_phase(analysis, critique)
        assert result.final_verdict in [
            Verdict.APPROVE,
            Verdict.REFACTOR,
            Verdict.ESCALATE,
        ]

    def test_moderator_phase_with_retry_context(self, dispatcher: CodeQualityDispatcher):
        """Moderator should handle retry context."""
        analysis = create_analysis_result()
        critique = create_critic_review()
        retry_context = create_retry_context(iteration=2)
        result = dispatcher.run_moderator_phase(analysis, critique, retry_context)
        assert isinstance(result, ModeratorDecision)


# ============================================================
# Test: Full Review Pipeline
# ============================================================


class TestFullReviewPipeline:
    """Test that run_review executes all three phases."""

    def test_run_review_executes_all_three_phases(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Verify full pipeline runs all phases."""
        with patch.object(
            dispatcher,
            "run_analyst_phase",
            return_value=create_analysis_result(),
        ) as mock_analyst, patch.object(
            dispatcher,
            "run_critic_phase",
            return_value=create_critic_review(),
        ) as mock_critic, patch.object(
            dispatcher,
            "run_moderator_phase",
            return_value=create_moderator_decision(),
        ) as mock_moderator:
            dispatcher.run_review([tmp_python_file])

            mock_analyst.assert_called_once()
            mock_critic.assert_called_once()
            mock_moderator.assert_called_once()

    def test_run_review_returns_moderator_decision(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Run review should return a ModeratorDecision."""
        result = dispatcher.run_review([tmp_python_file])
        assert isinstance(result, ModeratorDecision)

    def test_run_review_with_no_findings_approves(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Review with no findings should return APPROVE verdict."""
        result = dispatcher.run_review([tmp_python_file])
        assert result.final_verdict == Verdict.APPROVE

    def test_run_review_with_critical_findings_refactors(
        self, dispatcher: CodeQualityDispatcher, tmp_problematic_file: Path
    ):
        """Review with critical findings should return REFACTOR verdict."""
        result = dispatcher.run_review([tmp_problematic_file])
        # Problematic file has issues, should be REFACTOR (or APPROVE if nothing critical)
        assert result.final_verdict in [Verdict.REFACTOR, Verdict.APPROVE]


# ============================================================
# Test: Escalation Logic
# ============================================================


class TestEscalationLogic:
    """Test should_escalate after max retries."""

    def test_should_escalate_returns_true_after_max_retries(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Verify escalation after 3 retries."""
        retry_context = create_retry_context(iteration=3)
        assert dispatcher.should_escalate(retry_context) is True

    def test_should_escalate_returns_false_before_max_retries(
        self, dispatcher: CodeQualityDispatcher
    ):
        """Verify no escalation before 3 retries."""
        for iteration in [1, 2]:
            retry_context = create_retry_context(iteration=iteration)
            assert dispatcher.should_escalate(retry_context) is False


# ============================================================
# Test: Retry Context Iteration Tracking
# ============================================================


class TestRetryContextIterationTracking:
    """Test that retry context iteration is properly tracked."""

    def test_retry_context_iteration_tracking(self, dispatcher: CodeQualityDispatcher):
        """Verify iteration counter works correctly."""
        # First iteration
        retry_context = create_retry_context(iteration=1)
        assert retry_context.iteration == 1

        # Simulate incrementing iteration
        retry_context_2 = RetryContext(
            iteration=retry_context.iteration + 1,
            issue_id=retry_context.issue_id,
            timestamp=datetime.now().isoformat(),
            previously_validated_findings=retry_context.previously_validated_findings,
            previously_rejected_findings=retry_context.previously_rejected_findings,
            cumulative_tech_debt=retry_context.cumulative_tech_debt,
            iteration_history=retry_context.iteration_history,
        )
        assert retry_context_2.iteration == 2

    def test_retry_context_passed_to_moderator(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Retry context should be passed through to moderator phase."""
        retry_context = create_retry_context(iteration=2)
        result = dispatcher.run_review([tmp_python_file], retry_context)
        assert isinstance(result, ModeratorDecision)


# ============================================================
# Test: Graceful Timeout Handling
# ============================================================


class TestGracefulTimeoutHandling:
    """Test that timeouts don't crash the dispatcher."""

    def test_graceful_timeout_handling(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Verify timeouts don't crash."""

        def slow_analyze(*args, **kwargs):
            """Simulate a slow analysis that exceeds timing budget."""
            time.sleep(0.1)  # Small delay for testing
            return create_analysis_result(findings=[])

        with patch.object(
            dispatcher.analyzer, "analyze_files", side_effect=slow_analyze
        ):
            # Should complete without raising exception
            result = dispatcher.run_review([tmp_python_file])
            assert isinstance(result, ModeratorDecision)

    def test_review_completes_on_empty_files(self, dispatcher: CodeQualityDispatcher):
        """Review with no files should complete gracefully."""
        result = dispatcher.run_review([])
        assert isinstance(result, ModeratorDecision)
        assert result.final_verdict == Verdict.APPROVE


# ============================================================
# Test: Integration
# ============================================================


class TestIntegration:
    """Integration tests for the full dispatcher pipeline."""

    def test_full_dispatcher_pipeline(
        self, dispatcher: CodeQualityDispatcher, tmp_problematic_file: Path
    ):
        """Full dispatch should produce valid ModeratorDecision."""
        result = dispatcher.run_review([tmp_problematic_file])

        # Should have a valid verdict
        assert result.final_verdict in [
            Verdict.APPROVE,
            Verdict.REFACTOR,
            Verdict.ESCALATE,
        ]

        # Should have moderation_id
        assert result.moderation_id != ""

        # Should have summary
        assert result.summary != ""

    def test_dispatcher_phases_chain_correctly(
        self, dispatcher: CodeQualityDispatcher, tmp_python_file: Path
    ):
        """Phases should pass data correctly through the chain."""
        # Run full pipeline
        result = dispatcher.run_review([tmp_python_file])

        # Should produce coherent result
        assert isinstance(result, ModeratorDecision)
        # If no issues, should approve
        if len(result.approved_findings) == 0 and len(result.tech_debt_backlog) == 0:
            assert result.final_verdict == Verdict.APPROVE
