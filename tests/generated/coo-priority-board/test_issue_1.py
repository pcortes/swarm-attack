"""Tests for priority board data models."""

import pytest
from src.models.priority import (
    PanelType,
    PanelWeight,
    PriorityProposal,
    PanelSubmission,
    PriorityDisposition,
    ConsensusResult,
    ExternalReviewResult,
    PrioritizationResult,
)


class TestPanelType:
    """Tests for PanelType enum."""

    def test_has_product(self):
        assert PanelType.PRODUCT.value == "product"

    def test_has_ceo(self):
        assert PanelType.CEO.value == "ceo"

    def test_has_engineering(self):
        assert PanelType.ENGINEERING.value == "engineering"

    def test_has_design(self):
        assert PanelType.DESIGN.value == "design"

    def test_has_operations(self):
        assert PanelType.OPERATIONS.value == "operations"


class TestPanelWeight:
    """Tests for PanelWeight dataclass."""

    def test_create_panel_weight(self):
        pw = PanelWeight(panel=PanelType.PRODUCT, weight=1.5)
        assert pw.panel == PanelType.PRODUCT
        assert pw.weight == 1.5

    def test_to_dict(self):
        pw = PanelWeight(panel=PanelType.CEO, weight=2.0)
        result = pw.to_dict()
        assert result == {"panel": "ceo", "weight": 2.0}

    def test_from_dict(self):
        data = {"panel": "engineering", "weight": 1.2}
        pw = PanelWeight.from_dict(data)
        assert pw.panel == PanelType.ENGINEERING
        assert pw.weight == 1.2

    def test_roundtrip(self):
        original = PanelWeight(panel=PanelType.DESIGN, weight=0.8)
        roundtrip = PanelWeight.from_dict(original.to_dict())
        assert roundtrip.panel == original.panel
        assert roundtrip.weight == original.weight


class TestPriorityProposal:
    """Tests for PriorityProposal dataclass."""

    def test_create_minimal(self):
        pp = PriorityProposal(name="Feature X", why="User demand")
        assert pp.name == "Feature X"
        assert pp.why == "User demand"
        assert pp.effort == "M"
        assert pp.scores == []
        assert pp.dependencies == []
        assert pp.risks == []

    def test_create_full(self):
        pp = PriorityProposal(
            name="Feature Y",
            why="Revenue growth",
            effort="L",
            scores=[8.5, 9.0],
            dependencies=["Feature X"],
            risks=["Technical complexity"],
        )
        assert pp.effort == "L"
        assert pp.scores == [8.5, 9.0]
        assert pp.dependencies == ["Feature X"]
        assert pp.risks == ["Technical complexity"]

    def test_to_dict(self):
        pp = PriorityProposal(
            name="Test",
            why="Testing",
            effort="S",
            scores=[7.0],
            dependencies=["Dep1"],
            risks=["Risk1"],
        )
        result = pp.to_dict()
        assert result["name"] == "Test"
        assert result["why"] == "Testing"
        assert result["effort"] == "S"
        assert result["scores"] == [7.0]
        assert result["dependencies"] == ["Dep1"]
        assert result["risks"] == ["Risk1"]

    def test_from_dict(self):
        data = {
            "name": "FromDict",
            "why": "Testing from_dict",
            "effort": "XL",
            "scores": [6.0, 7.5],
            "dependencies": ["A", "B"],
            "risks": ["R1"],
        }
        pp = PriorityProposal.from_dict(data)
        assert pp.name == "FromDict"
        assert pp.effort == "XL"
        assert pp.scores == [6.0, 7.5]

    def test_from_dict_defaults(self):
        data = {"name": "Minimal", "why": "Test"}
        pp = PriorityProposal.from_dict(data)
        assert pp.effort == "M"
        assert pp.scores == []
        assert pp.dependencies == []
        assert pp.risks == []

    def test_roundtrip(self):
        original = PriorityProposal(
            name="Round",
            why="Trip",
            effort="L",
            scores=[8.0],
            dependencies=["X"],
            risks=["Y"],
        )
        roundtrip = PriorityProposal.from_dict(original.to_dict())
        assert roundtrip.name == original.name
        assert roundtrip.why == original.why
        assert roundtrip.effort == original.effort
        assert roundtrip.scores == original.scores


class TestPanelSubmission:
    """Tests for PanelSubmission dataclass."""

    def test_create_minimal(self):
        ps = PanelSubmission(panel=PanelType.PRODUCT, expert_name="Alice")
        assert ps.panel == PanelType.PRODUCT
        assert ps.expert_name == "Alice"
        assert ps.priorities == []
        assert ps.research == []

    def test_create_full(self):
        proposal = PriorityProposal(name="P1", why="W1")
        ps = PanelSubmission(
            panel=PanelType.ENGINEERING,
            expert_name="Bob",
            priorities=[proposal],
            research=["Finding 1", "Finding 2"],
        )
        assert ps.priorities == [proposal]
        assert ps.research == ["Finding 1", "Finding 2"]

    def test_to_dict(self):
        proposal = PriorityProposal(name="P1", why="W1")
        ps = PanelSubmission(
            panel=PanelType.CEO,
            expert_name="CEO Expert",
            priorities=[proposal],
            research=["R1"],
        )
        result = ps.to_dict()
        assert result["panel"] == "ceo"
        assert result["expert_name"] == "CEO Expert"
        assert len(result["priorities"]) == 1
        assert result["priorities"][0]["name"] == "P1"
        assert result["research"] == ["R1"]

    def test_from_dict(self):
        data = {
            "panel": "design",
            "expert_name": "Designer",
            "priorities": [{"name": "DP1", "why": "DW1"}],
            "research": ["Design research"],
        }
        ps = PanelSubmission.from_dict(data)
        assert ps.panel == PanelType.DESIGN
        assert ps.expert_name == "Designer"
        assert len(ps.priorities) == 1
        assert ps.priorities[0].name == "DP1"

    def test_roundtrip(self):
        original = PanelSubmission(
            panel=PanelType.OPERATIONS,
            expert_name="Ops",
            priorities=[PriorityProposal(name="O1", why="OW1")],
            research=["Ops research"],
        )
        roundtrip = PanelSubmission.from_dict(original.to_dict())
        assert roundtrip.panel == original.panel
        assert roundtrip.expert_name == original.expert_name
        assert len(roundtrip.priorities) == len(original.priorities)


class TestPriorityDisposition:
    """Tests for PriorityDisposition dataclass."""

    def test_create(self):
        pd = PriorityDisposition(
            priority_name="Feature X",
            classification="ACCEPT",
            reason="High value",
        )
        assert pd.priority_name == "Feature X"
        assert pd.classification == "ACCEPT"
        assert pd.reason == "High value"

    def test_valid_classifications(self):
        for classification in ["ACCEPT", "REJECT", "DEFER", "PARTIAL"]:
            pd = PriorityDisposition(
                priority_name="Test",
                classification=classification,
                reason="Test reason",
            )
            assert pd.classification == classification

    def test_to_dict(self):
        pd = PriorityDisposition(
            priority_name="Test",
            classification="DEFER",
            reason="Need more info",
        )
        result = pd.to_dict()
        assert result["priority_name"] == "Test"
        assert result["classification"] == "DEFER"
        assert result["reason"] == "Need more info"

    def test_from_dict(self):
        data = {
            "priority_name": "FromDict",
            "classification": "REJECT",
            "reason": "Low priority",
        }
        pd = PriorityDisposition.from_dict(data)
        assert pd.priority_name == "FromDict"
        assert pd.classification == "REJECT"

    def test_roundtrip(self):
        original = PriorityDisposition(
            priority_name="Round",
            classification="PARTIAL",
            reason="Some aspects",
        )
        roundtrip = PriorityDisposition.from_dict(original.to_dict())
        assert roundtrip.priority_name == original.priority_name
        assert roundtrip.classification == original.classification


class TestConsensusResult:
    """Tests for ConsensusResult dataclass."""

    def test_create_minimal(self):
        cr = ConsensusResult(reached=True, overlap_count=3)
        assert cr.reached is True
        assert cr.common_priorities == []
        assert cr.overlap_count == 3
        assert cr.forced is False

    def test_create_full(self):
        cr = ConsensusResult(
            reached=False,
            common_priorities=["P1", "P2"],
            overlap_count=2,
            forced=True,
        )
        assert cr.reached is False
        assert cr.common_priorities == ["P1", "P2"]
        assert cr.forced is True

    def test_to_dict(self):
        cr = ConsensusResult(
            reached=True,
            common_priorities=["Feature A"],
            overlap_count=5,
            forced=False,
        )
        result = cr.to_dict()
        assert result["reached"] is True
        assert result["common_priorities"] == ["Feature A"]
        assert result["overlap_count"] == 5
        assert result["forced"] is False

    def test_from_dict(self):
        data = {
            "reached": False,
            "common_priorities": ["X", "Y"],
            "overlap_count": 2,
            "forced": True,
        }
        cr = ConsensusResult.from_dict(data)
        assert cr.reached is False
        assert cr.common_priorities == ["X", "Y"]
        assert cr.forced is True

    def test_from_dict_defaults(self):
        data = {"reached": True, "overlap_count": 1}
        cr = ConsensusResult.from_dict(data)
        assert cr.common_priorities == []
        assert cr.forced is False

    def test_roundtrip(self):
        original = ConsensusResult(
            reached=True,
            common_priorities=["A", "B"],
            overlap_count=4,
            forced=True,
        )
        roundtrip = ConsensusResult.from_dict(original.to_dict())
        assert roundtrip.reached == original.reached
        assert roundtrip.common_priorities == original.common_priorities


class TestExternalReviewResult:
    """Tests for ExternalReviewResult dataclass."""

    def test_create_minimal(self):
        err = ExternalReviewResult(outcome="APPROVED")
        assert err.outcome == "APPROVED"
        assert err.feedback == ""
        assert err.challenged_priorities == []

    def test_create_full(self):
        err = ExternalReviewResult(
            outcome="CHALLENGED",
            feedback="Need reconsideration",
            challenged_priorities=["P1", "P2"],
        )
        assert err.outcome == "CHALLENGED"
        assert err.feedback == "Need reconsideration"
        assert err.challenged_priorities == ["P1", "P2"]

    def test_to_dict(self):
        err = ExternalReviewResult(
            outcome="REJECTED",
            feedback="Not aligned",
            challenged_priorities=["X"],
        )
        result = err.to_dict()
        assert result["outcome"] == "REJECTED"
        assert result["feedback"] == "Not aligned"
        assert result["challenged_priorities"] == ["X"]

    def test_from_dict(self):
        data = {
            "outcome": "APPROVED",
            "feedback": "Looks good",
            "challenged_priorities": [],
        }
        err = ExternalReviewResult.from_dict(data)
        assert err.outcome == "APPROVED"
        assert err.feedback == "Looks good"

    def test_from_dict_defaults(self):
        data = {"outcome": "PENDING"}
        err = ExternalReviewResult.from_dict(data)
        assert err.feedback == ""
        assert err.challenged_priorities == []

    def test_roundtrip(self):
        original = ExternalReviewResult(
            outcome="CHALLENGED",
            feedback="Review needed",
            challenged_priorities=["A"],
        )
        roundtrip = ExternalReviewResult.from_dict(original.to_dict())
        assert roundtrip.outcome == original.outcome
        assert roundtrip.feedback == original.feedback


class TestPrioritizationResult:
    """Tests for PrioritizationResult dataclass."""

    def test_create_minimal(self):
        pr = PrioritizationResult(success=True, project="Test Project")
        assert pr.success is True
        assert pr.project == "Test Project"
        assert pr.priorities == []
        assert pr.rounds == 0
        assert pr.cost == 0.0

    def test_create_full(self):
        proposal = PriorityProposal(name="P1", why="W1")
        pr = PrioritizationResult(
            success=True,
            project="Full Project",
            priorities=[proposal],
            rounds=3,
            cost=15.50,
        )
        assert pr.priorities == [proposal]
        assert pr.rounds == 3
        assert pr.cost == 15.50

    def test_to_dict(self):
        proposal = PriorityProposal(name="P1", why="W1", effort="S")
        pr = PrioritizationResult(
            success=True,
            project="Serialization Test",
            priorities=[proposal],
            rounds=2,
            cost=10.25,
        )
        result = pr.to_dict()
        assert result["success"] is True
        assert result["project"] == "Serialization Test"
        assert len(result["priorities"]) == 1
        assert result["priorities"][0]["name"] == "P1"
        assert result["rounds"] == 2
        assert result["cost"] == 10.25

    def test_from_dict(self):
        data = {
            "success": False,
            "project": "FromDict Project",
            "priorities": [{"name": "FD1", "why": "FDW1"}],
            "rounds": 5,
            "cost": 25.00,
        }
        pr = PrioritizationResult.from_dict(data)
        assert pr.success is False
        assert pr.project == "FromDict Project"
        assert len(pr.priorities) == 1
        assert pr.priorities[0].name == "FD1"
        assert pr.rounds == 5
        assert pr.cost == 25.00

    def test_from_dict_defaults(self):
        data = {"success": True, "project": "Minimal"}
        pr = PrioritizationResult.from_dict(data)
        assert pr.priorities == []
        assert pr.rounds == 0
        assert pr.cost == 0.0

    def test_roundtrip(self):
        original = PrioritizationResult(
            success=True,
            project="Roundtrip",
            priorities=[PriorityProposal(name="RT1", why="RTW1")],
            rounds=4,
            cost=20.0,
        )
        roundtrip = PrioritizationResult.from_dict(original.to_dict())
        assert roundtrip.success == original.success
        assert roundtrip.project == original.project
        assert roundtrip.rounds == original.rounds
        assert roundtrip.cost == original.cost
        assert len(roundtrip.priorities) == len(original.priorities)