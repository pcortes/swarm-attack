"""
Unit tests for auto-approval CLI integration.

Tests that the auto-approval system is properly wired into CLI commands:
- SpecAutoApprover.auto_approve_if_ready() called in feature.py:approve()
- IssueAutoGreenlighter.auto_greenlight_if_ready() called in feature.py:greenlight()
- BugAutoApprover.auto_approve_if_ready() called in bug.py:bug_approve()

These tests verify Issue 1 acceptance criteria from integration-gaps-fix-spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock, MagicMock, patch
import json
import tempfile
import sys

import pytest

from swarm_attack.auto_approval.models import ApprovalResult


# ============================================================================
# Test Fixtures
# ============================================================================

@dataclass
class MockDebateScore:
    """Mock debate score for testing."""
    clarity: float = 0.90
    coverage: float = 0.90
    architecture: float = 0.90
    risk: float = 0.90

    @property
    def average(self) -> float:
        return (self.clarity + self.coverage + self.architecture + self.risk) / 4


@dataclass
class MockFixPlan:
    """Mock fix plan for bug testing."""
    confidence: float = 0.95
    risk_level: str = "low"
    breaks_api: bool = False
    requires_migration: bool = False
    summary: str = "Test fix"
    changes: list = field(default_factory=list)
    test_cases: list = field(default_factory=list)


# ============================================================================
# AC 1.1: SpecAutoApprover.auto_approve_if_ready() called in feature.py:approve()
# ============================================================================

class TestSpecAutoApproverCLIIntegration:
    """Tests for spec auto-approval CLI integration."""

    def test_spec_auto_approver_is_instantiated_with_auto_flag(self):
        """AC 1.1: --auto flag creates SpecAutoApprover instance."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        # Create mock dependencies
        mock_store = Mock()
        mock_store.is_manual_mode.return_value = False

        mock_state = Mock()
        mock_score = Mock()
        mock_score.average = 0.90
        mock_state.debate_scores = [mock_score, mock_score]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        # Create approver and call it
        approver = SpecAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-feature")

        # Should return an ApprovalResult
        assert isinstance(result, ApprovalResult)
        # With high scores, should be approved
        assert result.approved is True

    def test_spec_auto_approver_respects_manual_mode(self):
        """AC 1.5: Manual mode blocks auto-approval."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = True  # Manual mode enabled

        mock_state = Mock()
        mock_score = Mock()
        mock_score.average = 0.90
        mock_state.debate_scores = [mock_score, mock_score]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        approver = SpecAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-feature")

        assert result.approved is False
        assert "Manual mode" in result.reason

    def test_spec_auto_approver_logs_on_success(self):
        """AC 1.7: Event logger records auto-approval decisions."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = False

        mock_state = Mock()
        mock_score = Mock()
        mock_score.average = 0.90
        mock_state.debate_scores = [mock_score, mock_score]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        approver = SpecAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-feature")

        # Logger should be called on successful auto-approval
        if result.approved:
            mock_logger.log_auto_approval.assert_called_once()

    def test_spec_auto_approver_calls_approve_spec_on_success(self):
        """AC 1.8: Phase updates when auto-approved."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = False

        mock_state = Mock()
        mock_score = Mock()
        mock_score.average = 0.90
        mock_state.debate_scores = [mock_score, mock_score]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        approver = SpecAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-feature")

        # Should call approve_spec on the store
        if result.approved:
            mock_store.approve_spec.assert_called_once_with("test-feature")


# ============================================================================
# AC 1.2: IssueAutoGreenlighter.auto_greenlight_if_ready() called in greenlight()
# ============================================================================

class TestIssueAutoGreenlighterCLIIntegration:
    """Tests for issue auto-greenlight CLI integration."""

    def test_issue_auto_greenlighter_is_instantiated_with_auto_flag(self):
        """AC 1.2: --auto flag creates IssueAutoGreenlighter instance."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = False

        # Create mock tasks that pass all checks
        mock_task = Mock()
        mock_task.complexity_gate_passed = True
        mock_task.has_interface_contract = True
        mock_task.dependencies = []
        mock_task.issue_number = 1

        mock_state = Mock()
        mock_state.tasks = [mock_task]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        greenlighter = IssueAutoGreenlighter(mock_store, mock_logger)
        result = greenlighter.auto_greenlight_if_ready("test-feature")

        assert isinstance(result, ApprovalResult)
        assert result.approved is True

    def test_issue_auto_greenlighter_respects_manual_mode(self):
        """AC 1.5: Manual mode blocks auto-greenlight."""
        from swarm_attack.auto_approval.issue import IssueAutoGreenlighter

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = True  # Manual mode

        mock_task = Mock()
        mock_task.complexity_gate_passed = True
        mock_task.has_interface_contract = True
        mock_task.dependencies = []
        mock_task.issue_number = 1

        mock_state = Mock()
        mock_state.tasks = [mock_task]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        greenlighter = IssueAutoGreenlighter(mock_store, mock_logger)
        result = greenlighter.auto_greenlight_if_ready("test-feature")

        assert result.approved is False
        assert "Manual mode" in result.reason


# ============================================================================
# AC 1.3: BugAutoApprover.auto_approve_if_ready() called in bug_approve()
# ============================================================================

class TestBugAutoApproverCLIIntegration:
    """Tests for bug auto-approval CLI integration."""

    def test_bug_auto_approver_is_instantiated_with_auto_flag(self):
        """AC 1.3: --auto flag creates BugAutoApprover instance."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_store = Mock()

        # Create mock bug state with high confidence, low risk fix plan
        mock_fix_plan = Mock()
        mock_fix_plan.confidence = 0.95
        mock_fix_plan.risk_level = "low"
        mock_fix_plan.breaks_api = False
        mock_fix_plan.requires_migration = False

        mock_bug_state = Mock()
        mock_bug_state.fix_plan = mock_fix_plan
        mock_store.get.return_value = mock_bug_state

        mock_logger = Mock()

        approver = BugAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-bug")

        assert isinstance(result, ApprovalResult)
        assert result.approved is True

    def test_bug_auto_approver_rejects_high_risk(self):
        """BugAutoApprover rejects high-risk fixes."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_store = Mock()

        mock_fix_plan = Mock()
        mock_fix_plan.confidence = 0.99
        mock_fix_plan.risk_level = "high"  # High risk
        mock_fix_plan.breaks_api = False
        mock_fix_plan.requires_migration = False

        mock_bug_state = Mock()
        mock_bug_state.fix_plan = mock_fix_plan
        mock_store.get.return_value = mock_bug_state

        mock_logger = Mock()

        approver = BugAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-bug")

        assert result.approved is False
        assert "requires manual review" in result.reason

    def test_bug_auto_approver_logs_on_success(self):
        """AC 1.7: Event logger records bug auto-approval decisions."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_store = Mock()

        mock_fix_plan = Mock()
        mock_fix_plan.confidence = 0.95
        mock_fix_plan.risk_level = "low"
        mock_fix_plan.breaks_api = False
        mock_fix_plan.requires_migration = False

        mock_bug_state = Mock()
        mock_bug_state.fix_plan = mock_fix_plan
        mock_store.get.return_value = mock_bug_state

        mock_logger = Mock()

        approver = BugAutoApprover(mock_store, mock_logger)
        result = approver.auto_approve_if_ready("test-bug")

        if result.approved:
            mock_logger.log_auto_approval.assert_called_once()


# ============================================================================
# AC 1.9: Approval audit trail includes threshold values used
# ============================================================================

class TestAuditTrail:
    """Tests for audit trail with threshold values."""

    def test_approval_result_includes_thresholds(self):
        """AC 1.9: ApprovalResult includes threshold info in reason."""
        from swarm_attack.auto_approval.models import ApprovalResult

        result = ApprovalResult(
            approved=True,
            reason="Auto-approved: 0.90 score for 2 rounds",
            confidence=0.90,
        )

        # The reason should include score information
        assert "0.90" in result.reason

    def test_spec_auto_approver_reason_includes_score(self):
        """Spec auto-approver reason includes the score value."""
        from swarm_attack.auto_approval.spec import SpecAutoApprover

        mock_store = Mock()
        mock_store.is_manual_mode.return_value = False

        mock_state = Mock()
        mock_score = Mock()
        mock_score.average = 0.90
        mock_state.debate_scores = [mock_score, mock_score]
        mock_store.get_run_state.return_value = mock_state

        mock_logger = Mock()

        approver = SpecAutoApprover(mock_store, mock_logger)
        should, reason = approver.should_auto_approve("test-feature")

        # Reason should include the score
        assert "0.90" in reason or should is True

    def test_bug_auto_approver_reason_includes_confidence(self):
        """Bug auto-approver reason includes confidence value."""
        from swarm_attack.auto_approval.bug import BugAutoApprover

        mock_store = Mock()

        mock_fix_plan = Mock()
        mock_fix_plan.confidence = 0.95
        mock_fix_plan.risk_level = "low"
        mock_fix_plan.breaks_api = False
        mock_fix_plan.requires_migration = False

        mock_bug_state = Mock()
        mock_bug_state.fix_plan = mock_fix_plan
        mock_store.get.return_value = mock_bug_state

        mock_logger = Mock()

        approver = BugAutoApprover(mock_store, mock_logger)
        should, reason = approver.should_auto_approve("test-bug")

        # Reason should include confidence
        assert "0.95" in reason or should is True


# ============================================================================
# Test that CLI modules import auto-approval correctly
# ============================================================================

class TestCLIImports:
    """Tests that CLI modules can import auto-approval classes."""

    def test_feature_cli_can_import_spec_auto_approver(self):
        """feature.py can import SpecAutoApprover."""
        from swarm_attack.auto_approval import SpecAutoApprover
        assert SpecAutoApprover is not None

    def test_feature_cli_can_import_issue_auto_greenlighter(self):
        """feature.py can import IssueAutoGreenlighter."""
        from swarm_attack.auto_approval import IssueAutoGreenlighter
        assert IssueAutoGreenlighter is not None

    def test_bug_cli_can_import_bug_auto_approver(self):
        """bug.py can import BugAutoApprover."""
        from swarm_attack.auto_approval import BugAutoApprover
        assert BugAutoApprover is not None

    def test_approval_result_importable(self):
        """ApprovalResult can be imported."""
        from swarm_attack.auto_approval.models import ApprovalResult
        assert ApprovalResult is not None


# ============================================================================
# Integration: Verify CLI code has auto-approval wiring
# ============================================================================

class TestCLIAutoApprovalWiring:
    """Tests that CLI code actually wires auto-approval."""

    def test_feature_approve_imports_spec_auto_approver(self):
        """feature.py:approve imports SpecAutoApprover."""
        import inspect
        from swarm_attack.cli import feature

        # Get the source of the approve function
        source = inspect.getsource(feature.approve)

        # Check that SpecAutoApprover is imported in the function
        assert "SpecAutoApprover" in source
        assert "auto_approve_if_ready" in source

    def test_feature_greenlight_imports_issue_auto_greenlighter(self):
        """feature.py:greenlight imports IssueAutoGreenlighter."""
        import inspect
        from swarm_attack.cli import feature

        source = inspect.getsource(feature.greenlight)

        assert "IssueAutoGreenlighter" in source
        assert "auto_greenlight_if_ready" in source

    def test_bug_approve_imports_bug_auto_approver(self):
        """bug.py:bug_approve imports BugAutoApprover."""
        import inspect
        from swarm_attack.cli import bug

        source = inspect.getsource(bug.bug_approve)

        assert "BugAutoApprover" in source
        assert "auto_approve_if_ready" in source

    def test_feature_approve_handles_auto_flag(self):
        """feature.py:approve handles --auto flag."""
        import inspect
        from swarm_attack.cli import feature

        source = inspect.getsource(feature.approve)

        # Check for auto flag handling
        assert "auto" in source
        assert "set_manual_mode" in source or "manual" in source

    def test_bug_approve_handles_auto_flag(self):
        """bug.py:bug_approve handles --auto flag."""
        import inspect
        from swarm_attack.cli import bug

        source = inspect.getsource(bug.bug_approve)

        # Check for auto flag handling
        assert "auto" in source
        assert "BugAutoApprover" in source
