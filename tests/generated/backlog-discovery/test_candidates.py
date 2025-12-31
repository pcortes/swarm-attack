"""Tests for backlog discovery candidate dataclasses.

TDD tests for Issue 1.1: Opportunity, Evidence, and ActionabilityScore dataclasses.
"""

import pytest
from datetime import datetime

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    ActionabilityScore,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_basic_evidence_creation(self):
        """Test creating basic Evidence without file info."""
        evidence = Evidence(
            source="test_output",
            content="AssertionError: expected 1, got 2",
        )
        assert evidence.source == "test_output"
        assert evidence.content == "AssertionError: expected 1, got 2"
        assert evidence.file_path is None
        assert evidence.line_number is None
        assert evidence.timestamp is None

    def test_evidence_with_file_path(self):
        """Test creating Evidence with file location."""
        evidence = Evidence(
            source="test_output",
            content="ImportError: No module named 'foo'",
            file_path="tests/test_foo.py",
            line_number=42,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert evidence.file_path == "tests/test_foo.py"
        assert evidence.line_number == 42
        assert evidence.timestamp == "2025-01-15T10:30:00Z"

    def test_evidence_serialization_roundtrip(self):
        """Test Evidence to_dict/from_dict roundtrip."""
        evidence = Evidence(
            source="static_analysis",
            content="Cyclomatic complexity: 15",
            file_path="src/complex.py",
            line_number=100,
            timestamp="2025-01-15T10:30:00Z",
        )

        data = evidence.to_dict()
        restored = Evidence.from_dict(data)

        assert restored.source == evidence.source
        assert restored.content == evidence.content
        assert restored.file_path == evidence.file_path
        assert restored.line_number == evidence.line_number
        assert restored.timestamp == evidence.timestamp

    def test_evidence_to_dict_structure(self):
        """Test Evidence to_dict produces expected structure."""
        evidence = Evidence(
            source="git_log",
            content="Feature stalled for 48 hours",
            file_path=None,
            line_number=None,
        )

        data = evidence.to_dict()
        assert data["source"] == "git_log"
        assert data["content"] == "Feature stalled for 48 hours"
        assert data["file_path"] is None
        assert data["line_number"] is None


class TestActionabilityScore:
    """Tests for ActionabilityScore dataclass."""

    def test_actionability_score_creation(self):
        """Test creating ActionabilityScore."""
        score = ActionabilityScore(
            clarity=0.9,
            evidence=0.8,
            effort="small",
            reversibility="full",
        )
        assert score.clarity == 0.9
        assert score.evidence == 0.8
        assert score.effort == "small"
        assert score.reversibility == "full"

    def test_actionability_score_calculation_small_effort(self):
        """Test overall score calculation with small effort."""
        score = ActionabilityScore(
            clarity=1.0,
            evidence=1.0,
            effort="small",
            reversibility="full",
        )
        # (1.0 * 0.4) + (1.0 * 0.4) + 0.2 = 1.0
        assert score.overall == pytest.approx(1.0)

    def test_actionability_score_calculation_medium_effort(self):
        """Test overall score calculation with medium effort."""
        score = ActionabilityScore(
            clarity=1.0,
            evidence=1.0,
            effort="medium",
            reversibility="partial",
        )
        # (1.0 * 0.4) + (1.0 * 0.4) + 0.1 = 0.9
        assert score.overall == pytest.approx(0.9)

    def test_actionability_score_calculation_large_effort(self):
        """Test overall score calculation with large effort."""
        score = ActionabilityScore(
            clarity=1.0,
            evidence=1.0,
            effort="large",
            reversibility="none",
        )
        # (1.0 * 0.4) + (1.0 * 0.4) + 0.0 = 0.8
        assert score.overall == pytest.approx(0.8)

    def test_actionability_score_calculation_mixed(self):
        """Test overall score calculation with mixed values."""
        score = ActionabilityScore(
            clarity=0.5,
            evidence=0.5,
            effort="small",
            reversibility="full",
        )
        # (0.5 * 0.4) + (0.5 * 0.4) + 0.2 = 0.6
        assert score.overall == pytest.approx(0.6)

    def test_actionability_score_serialization_roundtrip(self):
        """Test ActionabilityScore to_dict/from_dict roundtrip."""
        score = ActionabilityScore(
            clarity=0.75,
            evidence=0.85,
            effort="medium",
            reversibility="partial",
        )

        data = score.to_dict()
        restored = ActionabilityScore.from_dict(data)

        assert restored.clarity == score.clarity
        assert restored.evidence == score.evidence
        assert restored.effort == score.effort
        assert restored.reversibility == score.reversibility
        assert restored.overall == pytest.approx(score.overall)


class TestOpportunityType:
    """Tests for OpportunityType enum."""

    def test_opportunity_type_values(self):
        """Test OpportunityType enum has expected values."""
        assert OpportunityType.TEST_FAILURE.value == "test_failure"
        assert OpportunityType.STALLED_WORK.value == "stalled_work"
        assert OpportunityType.CODE_QUALITY.value == "code_quality"
        assert OpportunityType.COVERAGE_GAP.value == "coverage_gap"
        assert OpportunityType.COMPLEXITY.value == "complexity"
        assert OpportunityType.FEATURE_OPPORTUNITY.value == "feature_opportunity"


class TestOpportunityStatus:
    """Tests for OpportunityStatus enum."""

    def test_opportunity_status_values(self):
        """Test OpportunityStatus enum has expected values."""
        assert OpportunityStatus.DISCOVERED.value == "discovered"
        assert OpportunityStatus.DEBATING.value == "debating"
        assert OpportunityStatus.ACTIONABLE.value == "actionable"
        assert OpportunityStatus.ACCEPTED.value == "accepted"
        assert OpportunityStatus.REJECTED.value == "rejected"
        assert OpportunityStatus.DEFERRED.value == "deferred"


class TestOpportunity:
    """Tests for Opportunity dataclass."""

    def test_opportunity_basic_creation(self):
        """Test creating basic Opportunity."""
        evidence = Evidence(
            source="test_output",
            content="TestFoo::test_bar FAILED",
        )
        opp = Opportunity(
            opportunity_id="opp-001",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Fix failing test_bar",
            description="The test_bar test is failing due to assertion error",
            evidence=[evidence],
        )

        assert opp.opportunity_id == "opp-001"
        assert opp.opportunity_type == OpportunityType.TEST_FAILURE
        assert opp.status == OpportunityStatus.DISCOVERED
        assert opp.title == "Fix failing test_bar"
        assert len(opp.evidence) == 1
        assert opp.actionability is None
        assert opp.suggested_fix is None
        assert opp.affected_files == []

    def test_opportunity_with_actionability(self):
        """Test Opportunity with ActionabilityScore."""
        evidence = Evidence(source="test_output", content="FAILED")
        score = ActionabilityScore(
            clarity=0.9,
            evidence=0.85,
            effort="small",
            reversibility="full",
        )
        opp = Opportunity(
            opportunity_id="opp-002",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.ACTIONABLE,
            title="Fix test",
            description="Test is failing",
            evidence=[evidence],
            actionability=score,
            affected_files=["tests/test_foo.py", "src/foo.py"],
        )

        assert opp.actionability is not None
        assert opp.actionability.overall == pytest.approx(0.9)
        assert opp.affected_files == ["tests/test_foo.py", "src/foo.py"]

    def test_opportunity_serialization_roundtrip(self):
        """Test Opportunity to_dict/from_dict roundtrip preserves all fields."""
        evidence1 = Evidence(
            source="test_output",
            content="AssertionError",
            file_path="tests/test_foo.py",
            line_number=42,
        )
        evidence2 = Evidence(
            source="git_log",
            content="Last commit 3 days ago",
        )
        score = ActionabilityScore(
            clarity=0.8,
            evidence=0.7,
            effort="medium",
            reversibility="partial",
        )
        opp = Opportunity(
            opportunity_id="opp-003",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DEBATING,
            title="Resume stalled feature",
            description="Feature has been stalled for 3 days",
            evidence=[evidence1, evidence2],
            actionability=score,
            suggested_fix="Resume from checkpoint 2",
            affected_files=["src/feature.py"],
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T12:00:00Z",
            discovered_by="stalled-work-discovery",
            priority_rank=2,
            debate_session_id="debate-001",
        )

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert restored.opportunity_id == opp.opportunity_id
        assert restored.opportunity_type == opp.opportunity_type
        assert restored.status == opp.status
        assert restored.title == opp.title
        assert restored.description == opp.description
        assert len(restored.evidence) == 2
        assert restored.evidence[0].source == "test_output"
        assert restored.evidence[0].file_path == "tests/test_foo.py"
        assert restored.actionability is not None
        assert restored.actionability.effort == "medium"
        assert restored.suggested_fix == "Resume from checkpoint 2"
        assert restored.affected_files == ["src/feature.py"]
        assert restored.created_at == "2025-01-15T10:00:00Z"
        assert restored.updated_at == "2025-01-15T12:00:00Z"
        assert restored.discovered_by == "stalled-work-discovery"
        assert restored.priority_rank == 2
        assert restored.debate_session_id == "debate-001"

    def test_opportunity_to_dict_enum_values(self):
        """Test that enums are serialized as strings in to_dict."""
        opp = Opportunity(
            opportunity_id="opp-004",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.ACCEPTED,
            title="Reduce complexity",
            description="High cyclomatic complexity",
            evidence=[],
        )

        data = opp.to_dict()

        # Enums should be serialized as their string values
        assert data["opportunity_type"] == "code_quality"
        assert data["status"] == "accepted"

    def test_opportunity_from_dict_handles_string_enums(self):
        """Test from_dict properly converts string values to enums."""
        data = {
            "opportunity_id": "opp-005",
            "opportunity_type": "coverage_gap",
            "status": "deferred",
            "title": "Add tests for module X",
            "description": "Low coverage",
            "evidence": [],
            "actionability": None,
            "suggested_fix": None,
            "affected_files": [],
            "created_at": None,
            "updated_at": None,
            "discovered_by": None,
            "priority_rank": None,
            "debate_session_id": None,
            "linked_issue": None,
        }

        opp = Opportunity.from_dict(data)

        assert opp.opportunity_type == OpportunityType.COVERAGE_GAP
        assert opp.status == OpportunityStatus.DEFERRED

    def test_opportunity_with_all_optional_fields(self):
        """Test Opportunity with all optional fields populated."""
        opp = Opportunity(
            opportunity_id="opp-full",
            opportunity_type=OpportunityType.COMPLEXITY,
            status=OpportunityStatus.ACCEPTED,
            title="Refactor complex function",
            description="Function exceeds complexity threshold",
            evidence=[
                Evidence(
                    source="static_analysis",
                    content="Cyclomatic complexity: 25",
                    file_path="src/complex.py",
                    line_number=50,
                )
            ],
            actionability=ActionabilityScore(
                clarity=0.95,
                evidence=0.9,
                effort="large",
                reversibility="full",
            ),
            suggested_fix="Extract helper methods",
            affected_files=["src/complex.py"],
            created_at="2025-01-15T08:00:00Z",
            updated_at="2025-01-15T16:00:00Z",
            discovered_by="code-quality-discovery",
            priority_rank=1,
            debate_session_id="debate-002",
            linked_issue=42,
        )

        assert opp.linked_issue == 42
        assert opp.priority_rank == 1
        assert opp.debate_session_id == "debate-002"


class TestOpportunityEdgeCases:
    """Edge case tests for Opportunity."""

    def test_opportunity_empty_evidence_list(self):
        """Test Opportunity with empty evidence list."""
        opp = Opportunity(
            opportunity_id="opp-empty",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title="Empty evidence",
            description="No evidence yet",
            evidence=[],
        )

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert restored.evidence == []

    def test_opportunity_multiple_evidence_items(self):
        """Test Opportunity with multiple evidence items."""
        evidence_list = [
            Evidence(source="test_output", content="FAILED test_1"),
            Evidence(source="test_output", content="FAILED test_2"),
            Evidence(source="coverage", content="50% coverage"),
        ]

        opp = Opportunity(
            opportunity_id="opp-multi",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Multiple failures",
            description="Several related failures",
            evidence=evidence_list,
        )

        assert len(opp.evidence) == 3

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert len(restored.evidence) == 3
        assert restored.evidence[2].source == "coverage"

    def test_opportunity_special_characters_in_content(self):
        """Test Opportunity with special characters in fields."""
        opp = Opportunity(
            opportunity_id="opp-special",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title='Fix test with "quotes" and <brackets>',
            description="Error: Expected 'foo\\nbar' but got 'baz\\ttab'",
            evidence=[
                Evidence(
                    source="test_output",
                    content='AssertionError: "foo" != "bar"',
                )
            ],
        )

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert restored.title == opp.title
        assert restored.description == opp.description
        assert restored.evidence[0].content == opp.evidence[0].content
