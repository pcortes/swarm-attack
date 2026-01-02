"""
Tests for code quality data models.

TDD RED Phase: These tests define the expected behavior of the data models.
All tests should fail initially until models.py is implemented.
"""

import pytest
from datetime import datetime

from swarm_attack.code_quality.models import (
    Severity,
    Priority,
    Category,
    Finding,
    AnalysisResult,
    CriticReview,
    CriticIssue,
    IssueType,
    ModeratorDecision,
    ApprovedFinding,
    RejectedFinding,
    TechDebtItem,
    TDDPlan,
    TDDPhase,
    RetryContext,
    ValidatedFinding,
    RejectedHistoricalFinding,
    TechDebtEntry,
    IterationHistory,
    Verdict,
    CriticRecommendation,
)


# ============================================================
# Enum Tests
# ============================================================

class TestSeverityEnum:
    """Test Severity enum values."""

    def test_severity_values(self):
        """Severity enum has expected values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"

    def test_severity_from_string(self):
        """Severity can be created from string value."""
        assert Severity("critical") == Severity.CRITICAL
        assert Severity("high") == Severity.HIGH
        assert Severity("medium") == Severity.MEDIUM
        assert Severity("low") == Severity.LOW


class TestPriorityEnum:
    """Test Priority enum values."""

    def test_priority_values(self):
        """Priority enum has expected values."""
        assert Priority.FIX_NOW.value == "fix_now"
        assert Priority.FIX_LATER.value == "fix_later"
        assert Priority.IGNORE.value == "ignore"

    def test_priority_from_string(self):
        """Priority can be created from string value."""
        assert Priority("fix_now") == Priority.FIX_NOW
        assert Priority("fix_later") == Priority.FIX_LATER
        assert Priority("ignore") == Priority.IGNORE


class TestCategoryEnum:
    """Test Category enum values."""

    def test_category_values(self):
        """Category enum has expected values."""
        assert Category.CODE_SMELL.value == "code_smell"
        assert Category.SOLID.value == "solid"
        assert Category.LLM_HALLUCINATION.value == "llm_hallucination"
        assert Category.INCOMPLETE.value == "incomplete"
        assert Category.ERROR_HANDLING.value == "error_handling"


class TestVerdictEnum:
    """Test Verdict enum values."""

    def test_verdict_values(self):
        """Verdict enum has expected values."""
        assert Verdict.APPROVE.value == "APPROVE"
        assert Verdict.REFACTOR.value == "REFACTOR"
        assert Verdict.ESCALATE.value == "ESCALATE"


class TestIssueTypeEnum:
    """Test IssueType enum values."""

    def test_issue_type_values(self):
        """IssueType enum has expected values."""
        assert IssueType.OVER_SEVERITY.value == "over_severity"
        assert IssueType.FALSE_POSITIVE.value == "false_positive"
        assert IssueType.IMPRACTICAL_FIX.value == "impractical_fix"
        assert IssueType.MISSING_CONTEXT.value == "missing_context"
        assert IssueType.ENTERPRISE_CREEP.value == "enterprise_creep"


class TestCriticRecommendationEnum:
    """Test CriticRecommendation enum values."""

    def test_critic_recommendation_values(self):
        """CriticRecommendation enum has expected values."""
        assert CriticRecommendation.APPROVE.value == "APPROVE"
        assert CriticRecommendation.REVISE.value == "REVISE"


# ============================================================
# Finding Dataclass Tests
# ============================================================

class TestFinding:
    """Test Finding dataclass."""

    def test_finding_creation_minimal(self):
        """Finding can be created with minimal required fields."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="swarm_attack/agent.py",
            line=42,
            title="Long Method: run()",
            description="Method is 127 lines long.",
        )
        assert finding.finding_id == "CQA-001"
        assert finding.severity == Severity.HIGH
        assert finding.category == Category.CODE_SMELL
        assert finding.file == "swarm_attack/agent.py"
        assert finding.line == 42
        assert finding.title == "Long Method: run()"
        assert finding.description == "Method is 127 lines long."

    def test_finding_creation_full(self):
        """Finding can be created with all fields."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="swarm_attack/agent.py",
            line=42,
            title="Long Method: run()",
            description="Method is 127 lines long.",
            expert="Dr. Martin Chen",
            code_snippet="def run(self, context):\n    ...",
            refactoring_pattern="Extract Method",
            refactoring_steps=["Extract lines 50-80 to _validate()"],
            priority=Priority.FIX_NOW,
            effort_estimate="medium",
            confidence=0.95,
        )
        assert finding.expert == "Dr. Martin Chen"
        assert finding.code_snippet == "def run(self, context):\n    ..."
        assert finding.refactoring_pattern == "Extract Method"
        assert finding.refactoring_steps == ["Extract lines 50-80 to _validate()"]
        assert finding.priority == Priority.FIX_NOW
        assert finding.effort_estimate == "medium"
        assert finding.confidence == 0.95

    def test_finding_defaults(self):
        """Finding has correct default values."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="agent.py",
            line=1,
            title="Test",
            description="Test description",
        )
        assert finding.expert == ""
        assert finding.code_snippet == ""
        assert finding.refactoring_pattern == ""
        assert finding.refactoring_steps == []
        assert finding.priority == Priority.FIX_LATER
        assert finding.effort_estimate == "medium"
        assert finding.confidence == 0.8

    def test_finding_to_dict(self):
        """Finding converts to dict correctly."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="agent.py",
            line=42,
            title="Long Method",
            description="Too long",
            expert="Dr. Chen",
            priority=Priority.FIX_NOW,
            confidence=0.9,
        )
        result = finding.to_dict()
        assert result["finding_id"] == "CQA-001"
        assert result["severity"] == "high"
        assert result["category"] == "code_smell"
        assert result["file"] == "agent.py"
        assert result["line"] == 42
        assert result["title"] == "Long Method"
        assert result["description"] == "Too long"
        assert result["expert"] == "Dr. Chen"
        assert result["priority"] == "fix_now"
        assert result["confidence"] == 0.9

    def test_finding_from_dict(self):
        """Finding can be created from dict."""
        data = {
            "finding_id": "CQA-002",
            "severity": "critical",
            "category": "llm_hallucination",
            "file": "module.py",
            "line": 10,
            "title": "Hallucinated Import",
            "description": "Import does not exist",
            "expert": "Dr. Liu",
            "code_snippet": "from fake import thing",
            "refactoring_pattern": "Remove Import",
            "refactoring_steps": ["Delete the import line"],
            "priority": "fix_now",
            "effort_estimate": "small",
            "confidence": 0.99,
        }
        finding = Finding.from_dict(data)
        assert finding.finding_id == "CQA-002"
        assert finding.severity == Severity.CRITICAL
        assert finding.category == Category.LLM_HALLUCINATION
        assert finding.file == "module.py"
        assert finding.line == 10
        assert finding.title == "Hallucinated Import"
        assert finding.description == "Import does not exist"
        assert finding.expert == "Dr. Liu"
        assert finding.code_snippet == "from fake import thing"
        assert finding.refactoring_pattern == "Remove Import"
        assert finding.refactoring_steps == ["Delete the import line"]
        assert finding.priority == Priority.FIX_NOW
        assert finding.effort_estimate == "small"
        assert finding.confidence == 0.99

    def test_finding_from_dict_with_defaults(self):
        """Finding from_dict uses defaults for missing optional fields."""
        data = {
            "finding_id": "CQA-003",
            "severity": "medium",
            "category": "solid",
            "file": "code.py",
            "line": 5,
            "title": "SRP Violation",
            "description": "Too many responsibilities",
        }
        finding = Finding.from_dict(data)
        assert finding.expert == ""
        assert finding.code_snippet == ""
        assert finding.refactoring_pattern == ""
        assert finding.refactoring_steps == []
        assert finding.priority == Priority.FIX_LATER
        assert finding.effort_estimate == "medium"
        assert finding.confidence == 0.8

    def test_finding_roundtrip(self):
        """Finding survives dict roundtrip."""
        original = Finding(
            finding_id="CQA-001",
            severity=Severity.CRITICAL,
            category=Category.LLM_HALLUCINATION,
            file="test.py",
            line=100,
            title="Test Finding",
            description="Test description",
            expert="Expert",
            code_snippet="code",
            refactoring_pattern="Pattern",
            refactoring_steps=["step1", "step2"],
            priority=Priority.FIX_NOW,
            effort_estimate="large",
            confidence=0.75,
        )
        roundtripped = Finding.from_dict(original.to_dict())
        assert roundtripped == original


# ============================================================
# AnalysisResult Dataclass Tests
# ============================================================

class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_analysis_result_creation(self):
        """AnalysisResult can be created with all fields."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Test",
            description="Test",
        )
        result = AnalysisResult(
            analysis_id="cqa-20260101-120000",
            files_analyzed=["file1.py", "file2.py"],
            total_issues=1,
            critical=0,
            high=1,
            medium=0,
            low=0,
            fix_now=1,
            fix_later=0,
            ignore=0,
            findings=[finding],
            recommendation=Verdict.REFACTOR,
            refactor_summary="One high issue found",
        )
        assert result.analysis_id == "cqa-20260101-120000"
        assert result.files_analyzed == ["file1.py", "file2.py"]
        assert result.total_issues == 1
        assert result.high == 1
        assert result.fix_now == 1
        assert len(result.findings) == 1
        assert result.recommendation == Verdict.REFACTOR

    def test_analysis_result_to_dict(self):
        """AnalysisResult converts to dict correctly."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Test",
            description="Test",
        )
        result = AnalysisResult(
            analysis_id="cqa-20260101-120000",
            files_analyzed=["file1.py"],
            total_issues=1,
            critical=0,
            high=1,
            medium=0,
            low=0,
            fix_now=0,
            fix_later=1,
            ignore=0,
            findings=[finding],
            recommendation=Verdict.APPROVE,
            refactor_summary="",
        )
        d = result.to_dict()
        assert d["analysis_id"] == "cqa-20260101-120000"
        assert d["files_analyzed"] == ["file1.py"]
        assert d["summary"]["total_issues"] == 1
        assert d["summary"]["high"] == 1
        assert d["recommendation"] == "APPROVE"
        assert len(d["findings"]) == 1

    def test_analysis_result_from_dict(self):
        """AnalysisResult can be created from dict."""
        data = {
            "analysis_id": "cqa-20260101-120000",
            "files_analyzed": ["a.py", "b.py"],
            "summary": {
                "total_issues": 2,
                "critical": 1,
                "high": 1,
                "medium": 0,
                "low": 0,
                "fix_now": 2,
                "fix_later": 0,
                "ignore": 0,
            },
            "findings": [
                {
                    "finding_id": "CQA-001",
                    "severity": "critical",
                    "category": "llm_hallucination",
                    "file": "a.py",
                    "line": 1,
                    "title": "Bad",
                    "description": "Really bad",
                }
            ],
            "recommendation": "REFACTOR",
            "refactor_summary": "Fix the critical issue",
        }
        result = AnalysisResult.from_dict(data)
        assert result.analysis_id == "cqa-20260101-120000"
        assert result.files_analyzed == ["a.py", "b.py"]
        assert result.total_issues == 2
        assert result.critical == 1
        assert result.recommendation == Verdict.REFACTOR
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL

    def test_analysis_result_roundtrip(self):
        """AnalysisResult survives dict roundtrip."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Test",
            description="Test",
            priority=Priority.FIX_NOW,
        )
        original = AnalysisResult(
            analysis_id="cqa-20260101-120000",
            files_analyzed=["file1.py", "file2.py"],
            total_issues=1,
            critical=0,
            high=1,
            medium=0,
            low=0,
            fix_now=1,
            fix_later=0,
            ignore=0,
            findings=[finding],
            recommendation=Verdict.REFACTOR,
            refactor_summary="Fix it",
        )
        roundtripped = AnalysisResult.from_dict(original.to_dict())
        assert roundtripped == original


# ============================================================
# CriticIssue and CriticReview Dataclass Tests
# ============================================================

class TestCriticIssue:
    """Test CriticIssue dataclass."""

    def test_critic_issue_creation(self):
        """CriticIssue can be created."""
        issue = CriticIssue(
            finding_id="CQA-001",
            issue_type=IssueType.OVER_SEVERITY,
            original_severity="high",
            suggested_severity="medium",
            reasoning="The method is well-structured",
        )
        assert issue.finding_id == "CQA-001"
        assert issue.issue_type == IssueType.OVER_SEVERITY
        assert issue.original_severity == "high"
        assert issue.suggested_severity == "medium"

    def test_critic_issue_to_dict(self):
        """CriticIssue converts to dict."""
        issue = CriticIssue(
            finding_id="CQA-002",
            issue_type=IssueType.FALSE_POSITIVE,
            original_severity="high",
            suggested_severity=None,
            reasoning="Not an issue",
        )
        d = issue.to_dict()
        assert d["finding_id"] == "CQA-002"
        assert d["issue_type"] == "false_positive"
        assert d["original_severity"] == "high"
        assert d["suggested_severity"] is None

    def test_critic_issue_from_dict(self):
        """CriticIssue can be created from dict."""
        data = {
            "finding_id": "CQA-003",
            "issue_type": "impractical_fix",
            "original_severity": "medium",
            "suggested_severity": "low",
            "reasoning": "Too risky to fix",
        }
        issue = CriticIssue.from_dict(data)
        assert issue.finding_id == "CQA-003"
        assert issue.issue_type == IssueType.IMPRACTICAL_FIX
        assert issue.suggested_severity == "low"


class TestCriticReview:
    """Test CriticReview dataclass."""

    def test_critic_review_creation(self):
        """CriticReview can be created."""
        review = CriticReview(
            review_id="crit-20260101-120000",
            accuracy=0.85,
            severity_calibration=0.70,
            actionability=0.90,
            pragmatism=0.75,
            issues=[],
            validated_findings=["CQA-002"],
            rejected_findings=["CQA-001"],
            summary="1 of 2 validated",
            recommendation=CriticRecommendation.APPROVE,
        )
        assert review.review_id == "crit-20260101-120000"
        assert review.accuracy == 0.85
        assert review.validated_findings == ["CQA-002"]
        assert review.recommendation == CriticRecommendation.APPROVE

    def test_critic_review_to_dict(self):
        """CriticReview converts to dict."""
        issue = CriticIssue(
            finding_id="CQA-001",
            issue_type=IssueType.OVER_SEVERITY,
            original_severity="high",
            suggested_severity="medium",
            reasoning="Not that bad",
        )
        review = CriticReview(
            review_id="crit-20260101-120000",
            accuracy=0.8,
            severity_calibration=0.7,
            actionability=0.9,
            pragmatism=0.8,
            issues=[issue],
            validated_findings=["CQA-002"],
            rejected_findings=[],
            summary="All good",
            recommendation=CriticRecommendation.REVISE,
        )
        d = review.to_dict()
        assert d["review_id"] == "crit-20260101-120000"
        assert d["scores"]["accuracy"] == 0.8
        assert d["scores"]["severity_calibration"] == 0.7
        assert len(d["issues"]) == 1
        assert d["recommendation"] == "REVISE"

    def test_critic_review_from_dict(self):
        """CriticReview can be created from dict."""
        data = {
            "review_id": "crit-20260101-130000",
            "scores": {
                "accuracy": 0.9,
                "severity_calibration": 0.85,
                "actionability": 0.95,
                "pragmatism": 0.88,
            },
            "issues": [
                {
                    "finding_id": "CQA-001",
                    "issue_type": "false_positive",
                    "original_severity": "high",
                    "suggested_severity": None,
                    "reasoning": "Not real",
                }
            ],
            "validated_findings": ["CQA-002", "CQA-003"],
            "rejected_findings": ["CQA-001"],
            "summary": "2 of 3 validated",
            "recommendation": "APPROVE",
        }
        review = CriticReview.from_dict(data)
        assert review.review_id == "crit-20260101-130000"
        assert review.accuracy == 0.9
        assert review.pragmatism == 0.88
        assert len(review.issues) == 1
        assert review.issues[0].issue_type == IssueType.FALSE_POSITIVE
        assert review.recommendation == CriticRecommendation.APPROVE

    def test_critic_review_roundtrip(self):
        """CriticReview survives dict roundtrip."""
        original = CriticReview(
            review_id="crit-20260101-120000",
            accuracy=0.85,
            severity_calibration=0.70,
            actionability=0.90,
            pragmatism=0.75,
            issues=[
                CriticIssue(
                    finding_id="CQA-001",
                    issue_type=IssueType.ENTERPRISE_CREEP,
                    original_severity="medium",
                    suggested_severity="low",
                    reasoning="Over-engineered",
                )
            ],
            validated_findings=["CQA-002"],
            rejected_findings=["CQA-001"],
            summary="Summary",
            recommendation=CriticRecommendation.REVISE,
        )
        roundtripped = CriticReview.from_dict(original.to_dict())
        assert roundtripped == original


# ============================================================
# TDDPlan and TDDPhase Tests
# ============================================================

class TestTDDPhase:
    """Test TDDPhase dataclass."""

    def test_tdd_phase_creation(self):
        """TDDPhase can be created."""
        phase = TDDPhase(
            description="Write failing test",
            test_file="tests/test_thing.py",
            test_code="def test_thing(): assert False",
        )
        assert phase.description == "Write failing test"
        assert phase.test_file == "tests/test_thing.py"

    def test_tdd_phase_to_dict(self):
        """TDDPhase converts to dict."""
        phase = TDDPhase(
            description="Fix the code",
            changes=[{"file": "code.py", "action": "Extract method"}],
        )
        d = phase.to_dict()
        assert d["description"] == "Fix the code"
        assert d["changes"] == [{"file": "code.py", "action": "Extract method"}]

    def test_tdd_phase_from_dict(self):
        """TDDPhase can be created from dict."""
        data = {
            "description": "Add docstrings",
            "changes": ["Add docs to method1", "Add docs to method2"],
        }
        phase = TDDPhase.from_dict(data)
        assert phase.description == "Add docstrings"
        assert phase.changes == ["Add docs to method1", "Add docs to method2"]


class TestTDDPlan:
    """Test TDDPlan dataclass."""

    def test_tdd_plan_creation(self):
        """TDDPlan can be created."""
        plan = TDDPlan(
            red=TDDPhase(description="Write test", test_file="test.py", test_code="..."),
            green=TDDPhase(description="Make pass", changes=[{"file": "code.py"}]),
            refactor=TDDPhase(description="Clean up", changes=["Add types"]),
        )
        assert plan.red.description == "Write test"
        assert plan.green.description == "Make pass"

    def test_tdd_plan_to_dict(self):
        """TDDPlan converts to dict."""
        plan = TDDPlan(
            red=TDDPhase(description="Red", test_file="t.py", test_code="code"),
            green=TDDPhase(description="Green", changes=[]),
            refactor=TDDPhase(description="Refactor", changes=[]),
        )
        d = plan.to_dict()
        assert "red" in d
        assert "green" in d
        assert "refactor" in d
        assert d["red"]["description"] == "Red"

    def test_tdd_plan_from_dict(self):
        """TDDPlan can be created from dict."""
        data = {
            "red": {"description": "Test", "test_file": "test.py", "test_code": "assert 1"},
            "green": {"description": "Impl", "changes": [{"file": "x.py"}]},
            "refactor": {"description": "Polish", "changes": ["docs"]},
        }
        plan = TDDPlan.from_dict(data)
        assert plan.red.test_file == "test.py"
        assert plan.green.changes == [{"file": "x.py"}]


# ============================================================
# ModeratorDecision Dataclass Tests
# ============================================================

class TestApprovedFinding:
    """Test ApprovedFinding dataclass."""

    def test_approved_finding_creation(self):
        """ApprovedFinding can be created."""
        tdd = TDDPlan(
            red=TDDPhase(description="Test"),
            green=TDDPhase(description="Impl"),
            refactor=TDDPhase(description="Polish"),
        )
        finding = ApprovedFinding(
            finding_id="CQA-001",
            final_severity="high",
            final_priority="fix_now",
            tdd_plan=tdd,
        )
        assert finding.finding_id == "CQA-001"
        assert finding.final_severity == "high"

    def test_approved_finding_roundtrip(self):
        """ApprovedFinding survives dict roundtrip."""
        tdd = TDDPlan(
            red=TDDPhase(description="Test", test_file="t.py", test_code="..."),
            green=TDDPhase(description="Impl", changes=[{"file": "x.py"}]),
            refactor=TDDPhase(description="Polish", changes=["add types"]),
        )
        original = ApprovedFinding(
            finding_id="CQA-001",
            final_severity="high",
            final_priority="fix_now",
            tdd_plan=tdd,
        )
        roundtripped = ApprovedFinding.from_dict(original.to_dict())
        assert roundtripped == original


class TestRejectedFinding:
    """Test RejectedFinding dataclass."""

    def test_rejected_finding_creation(self):
        """RejectedFinding can be created."""
        finding = RejectedFinding(
            finding_id="CQA-002",
            rejection_reason="False positive",
        )
        assert finding.finding_id == "CQA-002"
        assert finding.rejection_reason == "False positive"

    def test_rejected_finding_roundtrip(self):
        """RejectedFinding survives dict roundtrip."""
        original = RejectedFinding(
            finding_id="CQA-002",
            rejection_reason="Not a real issue",
        )
        roundtripped = RejectedFinding.from_dict(original.to_dict())
        assert roundtripped == original


class TestTechDebtItem:
    """Test TechDebtItem dataclass."""

    def test_tech_debt_item_creation(self):
        """TechDebtItem can be created."""
        item = TechDebtItem(
            finding_id="CQA-003",
            priority="fix_later",
            reason="Code rarely touched",
        )
        assert item.finding_id == "CQA-003"

    def test_tech_debt_item_roundtrip(self):
        """TechDebtItem survives dict roundtrip."""
        original = TechDebtItem(
            finding_id="CQA-003",
            priority="fix_later",
            reason="Low impact",
        )
        roundtripped = TechDebtItem.from_dict(original.to_dict())
        assert roundtripped == original


class TestModeratorDecision:
    """Test ModeratorDecision dataclass."""

    def test_moderator_decision_creation(self):
        """ModeratorDecision can be created."""
        tdd = TDDPlan(
            red=TDDPhase(description="Test"),
            green=TDDPhase(description="Impl"),
            refactor=TDDPhase(description="Polish"),
        )
        decision = ModeratorDecision(
            moderation_id="mod-20260101-120000",
            final_verdict=Verdict.REFACTOR,
            approved_findings=[
                ApprovedFinding("CQA-001", "high", "fix_now", tdd)
            ],
            rejected_findings=[
                RejectedFinding("CQA-002", "False positive")
            ],
            tech_debt_backlog=[
                TechDebtItem("CQA-003", "fix_later", "Low priority")
            ],
            summary="1 approved, 1 rejected, 1 tech debt",
            handoff_instructions="Fix CQA-001",
        )
        assert decision.moderation_id == "mod-20260101-120000"
        assert decision.final_verdict == Verdict.REFACTOR
        assert len(decision.approved_findings) == 1
        assert len(decision.rejected_findings) == 1

    def test_moderator_decision_to_dict(self):
        """ModeratorDecision converts to dict."""
        tdd = TDDPlan(
            red=TDDPhase(description="Test"),
            green=TDDPhase(description="Impl"),
            refactor=TDDPhase(description="Polish"),
        )
        decision = ModeratorDecision(
            moderation_id="mod-20260101-120000",
            final_verdict=Verdict.APPROVE,
            approved_findings=[],
            rejected_findings=[],
            tech_debt_backlog=[],
            summary="All good",
            handoff_instructions="Proceed to QA",
        )
        d = decision.to_dict()
        assert d["moderation_id"] == "mod-20260101-120000"
        assert d["final_verdict"] == "APPROVE"
        assert d["summary"] == "All good"

    def test_moderator_decision_from_dict(self):
        """ModeratorDecision can be created from dict."""
        data = {
            "moderation_id": "mod-20260101-130000",
            "final_verdict": "ESCALATE",
            "approved_findings": [],
            "rejected_findings": [
                {"finding_id": "CQA-001", "rejection_reason": "Not valid"}
            ],
            "tech_debt_backlog": [],
            "summary": "Needs human review",
            "handoff_instructions": "Escalate to architect",
        }
        decision = ModeratorDecision.from_dict(data)
        assert decision.moderation_id == "mod-20260101-130000"
        assert decision.final_verdict == Verdict.ESCALATE
        assert len(decision.rejected_findings) == 1

    def test_moderator_decision_roundtrip(self):
        """ModeratorDecision survives dict roundtrip."""
        tdd = TDDPlan(
            red=TDDPhase(description="Test", test_file="t.py", test_code="x"),
            green=TDDPhase(description="Impl", changes=[{"file": "a.py"}]),
            refactor=TDDPhase(description="Polish", changes=["types"]),
        )
        original = ModeratorDecision(
            moderation_id="mod-20260101-120000",
            final_verdict=Verdict.REFACTOR,
            approved_findings=[
                ApprovedFinding("CQA-001", "high", "fix_now", tdd)
            ],
            rejected_findings=[
                RejectedFinding("CQA-002", "Nope")
            ],
            tech_debt_backlog=[
                TechDebtItem("CQA-003", "fix_later", "Later")
            ],
            summary="Summary",
            handoff_instructions="Instructions",
        )
        roundtripped = ModeratorDecision.from_dict(original.to_dict())
        assert roundtripped == original


# ============================================================
# RetryContext Dataclass Tests (from <retry_state> section)
# ============================================================

class TestValidatedFinding:
    """Test ValidatedFinding dataclass."""

    def test_validated_finding_creation(self):
        """ValidatedFinding can be created."""
        finding = ValidatedFinding(
            finding_id="CQA-001",
            validated_in_iteration=1,
            status="pending_fix",
        )
        assert finding.finding_id == "CQA-001"
        assert finding.validated_in_iteration == 1
        assert finding.status == "pending_fix"

    def test_validated_finding_roundtrip(self):
        """ValidatedFinding survives dict roundtrip."""
        original = ValidatedFinding(
            finding_id="CQA-001",
            validated_in_iteration=2,
            status="fixed",
        )
        roundtripped = ValidatedFinding.from_dict(original.to_dict())
        assert roundtripped == original


class TestRejectedHistoricalFinding:
    """Test RejectedHistoricalFinding dataclass."""

    def test_rejected_historical_finding_creation(self):
        """RejectedHistoricalFinding can be created."""
        finding = RejectedHistoricalFinding(
            finding_id="CQA-002",
            rejected_in_iteration=1,
            rejection_reason="False positive",
        )
        assert finding.finding_id == "CQA-002"
        assert finding.rejected_in_iteration == 1

    def test_rejected_historical_finding_roundtrip(self):
        """RejectedHistoricalFinding survives dict roundtrip."""
        original = RejectedHistoricalFinding(
            finding_id="CQA-002",
            rejected_in_iteration=2,
            rejection_reason="Not real",
        )
        roundtripped = RejectedHistoricalFinding.from_dict(original.to_dict())
        assert roundtripped == original


class TestTechDebtEntry:
    """Test TechDebtEntry dataclass."""

    def test_tech_debt_entry_creation(self):
        """TechDebtEntry can be created."""
        entry = TechDebtEntry(
            finding_id="CQA-003",
            added_in_iteration=1,
            description="Low priority refactor",
        )
        assert entry.finding_id == "CQA-003"
        assert entry.added_in_iteration == 1

    def test_tech_debt_entry_roundtrip(self):
        """TechDebtEntry survives dict roundtrip."""
        original = TechDebtEntry(
            finding_id="CQA-003",
            added_in_iteration=2,
            description="Tech debt item",
        )
        roundtripped = TechDebtEntry.from_dict(original.to_dict())
        assert roundtripped == original


class TestIterationHistory:
    """Test IterationHistory dataclass."""

    def test_iteration_history_creation(self):
        """IterationHistory can be created."""
        history = IterationHistory(
            iteration=1,
            verdict=Verdict.REFACTOR,
            findings_count=5,
            fixes_requested=3,
            fixes_completed=0,
        )
        assert history.iteration == 1
        assert history.verdict == Verdict.REFACTOR
        assert history.findings_count == 5

    def test_iteration_history_roundtrip(self):
        """IterationHistory survives dict roundtrip."""
        original = IterationHistory(
            iteration=2,
            verdict=Verdict.APPROVE,
            findings_count=3,
            fixes_requested=2,
            fixes_completed=2,
        )
        roundtripped = IterationHistory.from_dict(original.to_dict())
        assert roundtripped == original


class TestRetryContext:
    """Test RetryContext dataclass."""

    def test_retry_context_creation_minimal(self):
        """RetryContext can be created with minimal required fields."""
        context = RetryContext(
            iteration=1,
            issue_id="ISSUE-123",
            timestamp="2026-01-01T12:00:00Z",
        )
        assert context.iteration == 1
        assert context.issue_id == "ISSUE-123"
        assert context.timestamp == "2026-01-01T12:00:00Z"

    def test_retry_context_creation_full(self):
        """RetryContext can be created with all fields."""
        context = RetryContext(
            iteration=2,
            issue_id="ISSUE-456",
            timestamp="2026-01-01T14:00:00Z",
            previously_validated_findings=[
                ValidatedFinding("CQA-001", 1, "pending_fix")
            ],
            previously_rejected_findings=[
                RejectedHistoricalFinding("CQA-002", 1, "False positive")
            ],
            cumulative_tech_debt=[
                TechDebtEntry("CQA-003", 1, "Low priority")
            ],
            iteration_history=[
                IterationHistory(1, Verdict.REFACTOR, 3, 2, 1)
            ],
        )
        assert context.iteration == 2
        assert len(context.previously_validated_findings) == 1
        assert len(context.previously_rejected_findings) == 1
        assert len(context.cumulative_tech_debt) == 1
        assert len(context.iteration_history) == 1

    def test_retry_context_defaults(self):
        """RetryContext has correct defaults for optional fields."""
        context = RetryContext(
            iteration=1,
            issue_id="ISSUE-123",
            timestamp="2026-01-01T12:00:00Z",
        )
        assert context.previously_validated_findings == []
        assert context.previously_rejected_findings == []
        assert context.cumulative_tech_debt == []
        assert context.iteration_history == []

    def test_retry_context_to_dict(self):
        """RetryContext converts to dict correctly."""
        context = RetryContext(
            iteration=1,
            issue_id="ISSUE-123",
            timestamp="2026-01-01T12:00:00Z",
            previously_validated_findings=[
                ValidatedFinding("CQA-001", 1, "fixed")
            ],
        )
        d = context.to_dict()
        assert d["iteration"] == 1
        assert d["issue_id"] == "ISSUE-123"
        assert d["timestamp"] == "2026-01-01T12:00:00Z"
        assert len(d["previously_validated_findings"]) == 1

    def test_retry_context_from_dict(self):
        """RetryContext can be created from dict."""
        data = {
            "iteration": 3,
            "issue_id": "PR-789",
            "timestamp": "2026-01-01T16:00:00Z",
            "previously_validated_findings": [
                {"finding_id": "CQA-001", "validated_in_iteration": 1, "status": "fixed"},
                {"finding_id": "CQA-002", "validated_in_iteration": 2, "status": "pending_fix"},
            ],
            "previously_rejected_findings": [
                {"finding_id": "CQA-003", "rejected_in_iteration": 1, "rejection_reason": "FP"}
            ],
            "cumulative_tech_debt": [
                {"finding_id": "CQA-004", "added_in_iteration": 2, "description": "Later"}
            ],
            "iteration_history": [
                {"iteration": 1, "verdict": "REFACTOR", "findings_count": 4, "fixes_requested": 3, "fixes_completed": 2},
                {"iteration": 2, "verdict": "REFACTOR", "findings_count": 2, "fixes_requested": 1, "fixes_completed": 0},
            ],
        }
        context = RetryContext.from_dict(data)
        assert context.iteration == 3
        assert context.issue_id == "PR-789"
        assert len(context.previously_validated_findings) == 2
        assert context.previously_validated_findings[0].status == "fixed"
        assert len(context.previously_rejected_findings) == 1
        assert len(context.cumulative_tech_debt) == 1
        assert len(context.iteration_history) == 2
        assert context.iteration_history[0].verdict == Verdict.REFACTOR

    def test_retry_context_roundtrip(self):
        """RetryContext survives dict roundtrip."""
        original = RetryContext(
            iteration=2,
            issue_id="ISSUE-456",
            timestamp="2026-01-01T14:00:00Z",
            previously_validated_findings=[
                ValidatedFinding("CQA-001", 1, "pending_fix"),
                ValidatedFinding("CQA-005", 1, "wont_fix"),
            ],
            previously_rejected_findings=[
                RejectedHistoricalFinding("CQA-002", 1, "False positive")
            ],
            cumulative_tech_debt=[
                TechDebtEntry("CQA-003", 1, "Low priority"),
                TechDebtEntry("CQA-004", 2, "Medium priority"),
            ],
            iteration_history=[
                IterationHistory(1, Verdict.REFACTOR, 3, 2, 1)
            ],
        )
        roundtripped = RetryContext.from_dict(original.to_dict())
        assert roundtripped == original

    def test_retry_context_iteration_bounds(self):
        """RetryContext iteration should be 1-3."""
        # Valid iterations
        for i in [1, 2, 3]:
            ctx = RetryContext(iteration=i, issue_id="X", timestamp="T")
            assert ctx.iteration == i
