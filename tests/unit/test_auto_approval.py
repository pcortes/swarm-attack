"""
Unit tests for auto-approval system.

Tests the three auto-approvers:
- SpecAutoApprover: Auto-approve specs when score >= 0.85 for 2+ rounds
- IssueAutoGreenlighter: Auto-greenlight when complexity gate passes
- BugAutoApprover: Auto-approve bug fixes when confidence >= 0.9 AND risk != high
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import Mock, MagicMock, patch

import pytest


# ============================================================================
# Mock Data Structures (simulating existing models)
# ============================================================================

@dataclass
class MockDebateScore:
    """Mock debate score for testing."""
    clarity: float = 0.85
    coverage: float = 0.85
    architecture: float = 0.85
    risk: float = 0.85

    @property
    def average(self) -> float:
        return (self.clarity + self.coverage + self.architecture + self.risk) / 4


@dataclass
class MockTask:
    """Mock task/issue for testing."""
    issue_number: int
    complexity_gate_passed: bool = True
    has_interface_contract: bool = True
    dependencies: list[int] = field(default_factory=list)


@dataclass
class MockRunState:
    """Mock run state for testing."""
    feature_id: str
    debate_scores: list[MockDebateScore] = field(default_factory=list)
    tasks: list[MockTask] = field(default_factory=list)
    manual_mode: bool = False


@dataclass
class MockFixPlan:
    """Mock fix plan for testing."""
    confidence: float = 0.95
    risk_level: str = "low"
    breaks_api: bool = False
    requires_migration: bool = False


@dataclass
class MockBugState:
    """Mock bug state for testing."""
    bug_id: str
    fix_plan: Optional[MockFixPlan] = None


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_state_store():
    """Create a mock state store."""
    store = Mock()
    store.get_run_state = Mock(return_value=None)
    store.approve_spec = Mock()
    store.greenlight_feature = Mock()
    store.set_manual_mode = Mock()
    store.veto_approval = Mock()
    store.is_manual_mode = Mock(return_value=False)
    return store


@pytest.fixture
def mock_bug_store():
    """Create a mock bug store."""
    store = Mock()
    store.get = Mock(return_value=None)
    store.approve_fix = Mock()
    store.veto_approval = Mock()
    return store


@pytest.fixture
def mock_event_logger():
    """Create a mock event logger."""
    logger = Mock()
    logger.log_auto_approval = Mock()
    return logger


# ============================================================================
# SpecAutoApprover Tests
# ============================================================================

class TestSpecAutoApprover:
    """Tests for spec auto-approval."""

    def test_approves_when_score_meets_threshold(self, mock_state_store, mock_event_logger):
        """Auto-approve when score >= 0.85 for 2+ rounds."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            debate_scores=[
                MockDebateScore(clarity=0.86, coverage=0.87, architecture=0.88, risk=0.85),
                MockDebateScore(clarity=0.88, coverage=0.89, architecture=0.90, risk=0.86),
            ]
        )
        mock_state_store.is_manual_mode.return_value = False

        approver = SpecAutoApprover(mock_state_store, mock_event_logger)
        should, reason = approver.should_auto_approve("test-feature")

        assert should is True
        assert "Auto-approved" in reason

    def test_rejects_when_below_threshold(self, mock_state_store, mock_event_logger):
        """Reject when score < 0.85."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            debate_scores=[
                MockDebateScore(clarity=0.80, coverage=0.75, architecture=0.70, risk=0.65),
                MockDebateScore(clarity=0.82, coverage=0.78, architecture=0.72, risk=0.68),
            ]
        )

        approver = SpecAutoApprover(mock_state_store, mock_event_logger)
        should, reason = approver.should_auto_approve("test-feature")

        assert should is False
        assert "below threshold" in reason

    def test_requires_two_consecutive_rounds(self, mock_state_store, mock_event_logger):
        """Need 2 consecutive rounds above threshold."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            debate_scores=[
                MockDebateScore(clarity=0.90, coverage=0.90, architecture=0.90, risk=0.90),
            ]  # Only 1 round
        )

        approver = SpecAutoApprover(mock_state_store, mock_event_logger)
        should, reason = approver.should_auto_approve("test-feature")

        assert should is False
        assert "Need 2 debate rounds" in reason

    def test_respects_manual_mode(self, mock_state_store, mock_event_logger):
        """Manual mode blocks auto-approval."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            debate_scores=[
                MockDebateScore(clarity=0.90, coverage=0.90, architecture=0.90, risk=0.90),
                MockDebateScore(clarity=0.90, coverage=0.90, architecture=0.90, risk=0.90),
            ],
            manual_mode=True,
        )
        mock_state_store.is_manual_mode.return_value = True

        approver = SpecAutoApprover(mock_state_store, mock_event_logger)
        result = approver.auto_approve_if_ready("test-feature")

        assert result.approved is False
        assert "Manual mode" in result.reason

    def test_auto_approve_if_ready_success(self, mock_state_store, mock_event_logger):
        """Test full auto_approve_if_ready flow."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            debate_scores=[
                MockDebateScore(clarity=0.90, coverage=0.90, architecture=0.90, risk=0.90),
                MockDebateScore(clarity=0.90, coverage=0.90, architecture=0.90, risk=0.90),
            ],
        )
        mock_state_store.is_manual_mode.return_value = False

        approver = SpecAutoApprover(mock_state_store, mock_event_logger)
        result = approver.auto_approve_if_ready("test-feature")

        assert result.approved is True
        mock_state_store.approve_spec.assert_called_once_with("test-feature")
        mock_event_logger.log_auto_approval.assert_called_once()


# ============================================================================
# IssueAutoGreenlighter Tests
# ============================================================================

class TestIssueAutoGreenlighter:
    """Tests for issue auto-greenlight."""

    def test_greenlights_when_all_pass_complexity(self, mock_state_store, mock_event_logger):
        """Greenlight when all issues pass complexity gate."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            tasks=[
                MockTask(issue_number=1, complexity_gate_passed=True, has_interface_contract=True),
                MockTask(issue_number=2, complexity_gate_passed=True, has_interface_contract=True),
            ],
        )
        mock_state_store.is_manual_mode.return_value = False

        greenlighter = IssueAutoGreenlighter(mock_state_store, mock_event_logger)
        should, reason = greenlighter.should_auto_greenlight("test-feature")

        assert should is True

    def test_rejects_when_complexity_fails(self, mock_state_store, mock_event_logger):
        """Reject when any issue fails complexity gate."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            tasks=[
                MockTask(issue_number=1, complexity_gate_passed=True, has_interface_contract=True),
                MockTask(issue_number=2, complexity_gate_passed=False, has_interface_contract=True),
            ],
        )

        greenlighter = IssueAutoGreenlighter(mock_state_store, mock_event_logger)
        should, reason = greenlighter.should_auto_greenlight("test-feature")

        assert should is False
        assert "failed complexity gate" in reason

    def test_rejects_when_no_issues(self, mock_state_store, mock_event_logger):
        """Reject when there are no issues to greenlight."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            tasks=[],
        )

        greenlighter = IssueAutoGreenlighter(mock_state_store, mock_event_logger)
        should, reason = greenlighter.should_auto_greenlight("test-feature")

        assert should is False
        assert "No issues" in reason

    def test_rejects_when_missing_interface_contract(self, mock_state_store, mock_event_logger):
        """Reject when issues are missing interface contracts."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            tasks=[
                MockTask(issue_number=1, complexity_gate_passed=True, has_interface_contract=False),
            ],
        )

        greenlighter = IssueAutoGreenlighter(mock_state_store, mock_event_logger)
        should, reason = greenlighter.should_auto_greenlight("test-feature")

        assert should is False
        assert "missing interface contract" in reason

    def test_respects_manual_mode(self, mock_state_store, mock_event_logger):
        """Manual mode blocks auto-greenlight."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_state_store.get_run_state.return_value = MockRunState(
            feature_id="test-feature",
            tasks=[
                MockTask(issue_number=1, complexity_gate_passed=True, has_interface_contract=True),
            ],
        )
        mock_state_store.is_manual_mode.return_value = True

        greenlighter = IssueAutoGreenlighter(mock_state_store, mock_event_logger)
        result = greenlighter.auto_greenlight_if_ready("test-feature")

        assert result.approved is False
        assert "Manual mode" in result.reason


# ============================================================================
# BugAutoApprover Tests
# ============================================================================

class TestBugAutoApprover:
    """Tests for bug fix auto-approval."""

    def test_approves_low_risk_high_confidence(self, mock_bug_store, mock_event_logger):
        """Approve low-risk bugs with high confidence."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.95,
                risk_level="low",
                breaks_api=False,
                requires_migration=False,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is True

    def test_approves_medium_risk_high_confidence(self, mock_bug_store, mock_event_logger):
        """Approve medium-risk bugs with high confidence."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.92,
                risk_level="medium",
                breaks_api=False,
                requires_migration=False,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is True

    def test_rejects_high_risk(self, mock_bug_store, mock_event_logger):
        """High-risk bugs require manual review."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.99,
                risk_level="high",
                breaks_api=False,
                requires_migration=False,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is False
        assert "requires manual review" in reason

    def test_rejects_low_confidence(self, mock_bug_store, mock_event_logger):
        """Reject when confidence is below threshold."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.85,
                risk_level="low",
                breaks_api=False,
                requires_migration=False,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is False
        assert "below threshold" in reason

    def test_rejects_api_breaking(self, mock_bug_store, mock_event_logger):
        """API-breaking changes require manual review."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.99,
                risk_level="low",
                breaks_api=True,
                requires_migration=False,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is False
        assert "API-breaking" in reason

    def test_rejects_migration_required(self, mock_bug_store, mock_event_logger):
        """Migration required means manual review."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=MockFixPlan(
                confidence=0.99,
                risk_level="low",
                breaks_api=False,
                requires_migration=True,
            ),
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is False
        assert "Migration required" in reason

    def test_rejects_no_fix_plan(self, mock_bug_store, mock_event_logger):
        """Reject when there's no fix plan."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_bug_store.get.return_value = MockBugState(
            bug_id="bug-123",
            fix_plan=None,
        )

        approver = BugAutoApprover(mock_bug_store, mock_event_logger)
        should, reason = approver.should_auto_approve("bug-123")

        assert should is False
        assert "No fix plan" in reason


# ============================================================================
# Human Override Tests
# ============================================================================

class TestHumanOverride:
    """Tests for human override commands."""

    def test_veto_reverts_approval(self, mock_state_store):
        """Veto command reverts auto-approval."""
        from swarm_attack.auto_approval.overrides import veto_feature

        veto_feature(mock_state_store, "test-feature", reason="Need review")

        mock_state_store.veto_approval.assert_called_with("test-feature", "Need review")

    def test_manual_mode_disables_auto(self, mock_state_store):
        """Manual mode disables auto-approval."""
        from swarm_attack.auto_approval.overrides import enable_manual_mode

        enable_manual_mode(mock_state_store, "test-feature")

        mock_state_store.set_manual_mode.assert_called_with("test-feature", True)

    def test_auto_mode_enables_auto(self, mock_state_store):
        """Auto mode re-enables auto-approval."""
        from swarm_attack.auto_approval.overrides import enable_auto_mode

        enable_auto_mode(mock_state_store, "test-feature")

        mock_state_store.set_manual_mode.assert_called_with("test-feature", False)


# ============================================================================
# ApprovalResult Tests
# ============================================================================

class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_approval_result_basic(self):
        """Test basic ApprovalResult creation."""
        from swarm_attack.auto_approval.models import ApprovalResult

        result = ApprovalResult(approved=True, reason="Auto-approved: 0.90 score for 2 rounds")

        assert result.approved is True
        assert "Auto-approved" in result.reason
        assert result.confidence == 0.0  # default

    def test_approval_result_with_confidence(self):
        """Test ApprovalResult with confidence."""
        from swarm_attack.auto_approval.models import ApprovalResult

        result = ApprovalResult(approved=True, reason="High confidence", confidence=0.95)

        assert result.approved is True
        assert result.confidence == 0.95
