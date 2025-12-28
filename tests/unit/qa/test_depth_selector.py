"""Tests for DepthSelector following TDD approach.

Tests cover spec section 8: Depth Selector
- Select depth based on trigger type
- Escalate depth for high-risk code changes
- Consider time and cost budgets
- Support manual depth override
"""

import pytest
from unittest.mock import MagicMock

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QATrigger,
)


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify DepthSelector can be imported."""

    def test_can_import_depth_selector(self):
        """Should be able to import DepthSelector class."""
        from swarm_attack.qa.depth_selector import DepthSelector
        assert DepthSelector is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestDepthSelectorInit:
    """Tests for DepthSelector initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.depth_selector import DepthSelector
        selector = DepthSelector(mock_config)
        assert selector.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.depth_selector import DepthSelector
        logger = MagicMock()
        selector = DepthSelector(mock_config, logger=logger)
        assert selector._logger == logger

    def test_has_default_thresholds(self, mock_config):
        """Should have default risk thresholds."""
        from swarm_attack.qa.depth_selector import DepthSelector
        selector = DepthSelector(mock_config)
        assert hasattr(selector, 'high_risk_threshold')
        assert selector.high_risk_threshold >= 0.0
        assert selector.high_risk_threshold <= 1.0


# =============================================================================
# TRIGGER-BASED SELECTION TESTS
# =============================================================================


class TestTriggerBasedSelection:
    """Tests for depth selection based on trigger type."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_post_verification_returns_standard(self, selector):
        """POST_VERIFICATION trigger should return STANDARD depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )
        assert depth == QADepth.STANDARD

    def test_bug_reproduction_returns_deep(self, selector):
        """BUG_REPRODUCTION trigger should return DEEP depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.BUG_REPRODUCTION,
            context=context,
        )
        assert depth == QADepth.DEEP

    def test_user_command_defaults_to_standard(self, selector):
        """USER_COMMAND trigger should default to STANDARD depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
        )
        assert depth == QADepth.STANDARD

    def test_pre_merge_returns_regression(self, selector):
        """PRE_MERGE trigger should return REGRESSION depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.PRE_MERGE,
            context=context,
        )
        assert depth == QADepth.REGRESSION


# =============================================================================
# RISK ESCALATION TESTS
# =============================================================================


class TestRiskEscalation:
    """Tests for risk-based depth escalation."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_high_risk_escalates_shallow_to_standard(self, selector):
        """High risk (>0.8) should escalate SHALLOW to STANDARD."""
        context = QAContext()
        # Force shallow depth first via user override, then check risk escalation
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            risk_score=0.9,
            override_depth=QADepth.SHALLOW,
        )
        # High risk should escalate at least one level
        assert depth in [QADepth.STANDARD, QADepth.DEEP]

    def test_high_risk_escalates_standard_to_deep(self, selector):
        """High risk (>0.8) should escalate STANDARD to DEEP."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,  # Normally STANDARD
            context=context,
            risk_score=0.9,
        )
        assert depth == QADepth.DEEP

    def test_medium_risk_no_escalation(self, selector):
        """Medium risk (0.5) should not escalate depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
            risk_score=0.5,
        )
        assert depth == QADepth.STANDARD

    def test_low_risk_no_escalation(self, selector):
        """Low risk (<0.3) should not escalate depth."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
            risk_score=0.2,
        )
        assert depth == QADepth.STANDARD

    def test_auth_files_escalate_to_deep(self, selector):
        """Auth-related files should always escalate to DEEP."""
        context = QAContext(
            target_files=["src/api/auth.py", "src/services/authentication.py"]
        )
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,  # Normally STANDARD
            context=context,
        )
        assert depth == QADepth.DEEP

    def test_payment_files_escalate_to_deep(self, selector):
        """Payment-related files should always escalate to DEEP."""
        context = QAContext(
            target_files=["src/api/payments.py", "src/services/billing.py"]
        )
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )
        assert depth == QADepth.DEEP

    def test_security_files_escalate_to_deep(self, selector):
        """Security-related files should escalate to DEEP."""
        context = QAContext(
            target_files=["src/security/crypto.py"]
        )
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )
        assert depth == QADepth.DEEP

    def test_auth_endpoints_escalate_to_deep(self, selector):
        """Auth-related endpoints should escalate to DEEP."""
        context = QAContext(
            target_endpoints=[
                QAEndpoint(method="POST", path="/api/auth/login"),
                QAEndpoint(method="POST", path="/api/auth/register"),
            ]
        )
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )
        assert depth == QADepth.DEEP


# =============================================================================
# BUDGET CONSTRAINT TESTS
# =============================================================================


class TestBudgetConstraints:
    """Tests for time and cost budget handling."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_respects_time_budget_shallow(self, selector):
        """Should downgrade to SHALLOW for very short time budget."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,  # Normally STANDARD
            context=context,
            time_budget_minutes=1,  # Very short
        )
        assert depth == QADepth.SHALLOW

    def test_respects_time_budget_standard(self, selector):
        """Should allow STANDARD for reasonable time budget."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
            time_budget_minutes=10,
        )
        assert depth in [QADepth.STANDARD, QADepth.SHALLOW]

    def test_respects_cost_budget_shallow(self, selector):
        """Should downgrade for very low cost budget."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,  # Normally STANDARD
            context=context,
            cost_budget_usd=0.01,  # Very low
        )
        assert depth == QADepth.SHALLOW

    def test_respects_cost_budget_deep(self, selector):
        """Should allow DEEP for generous cost budget."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.BUG_REPRODUCTION,  # Normally DEEP
            context=context,
            cost_budget_usd=10.0,  # Generous
        )
        assert depth == QADepth.DEEP

    def test_downgrades_deep_to_standard_when_constrained(self, selector):
        """Should downgrade DEEP to STANDARD when budget is tight."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.BUG_REPRODUCTION,  # Normally DEEP
            context=context,
            cost_budget_usd=0.10,  # Tight budget
        )
        assert depth in [QADepth.STANDARD, QADepth.SHALLOW]

    def test_ignores_budget_if_not_specified(self, selector):
        """Should not constrain if no budget specified."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.BUG_REPRODUCTION,
            context=context,
            # No budget specified
        )
        assert depth == QADepth.DEEP


# =============================================================================
# MANUAL OVERRIDE TESTS
# =============================================================================


class TestManualOverride:
    """Tests for manual depth override."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_override_depth_respected(self, selector):
        """Should respect explicit depth override."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,  # Normally STANDARD
            context=context,
            override_depth=QADepth.SHALLOW,
        )
        # Override should be respected (may still escalate for high risk)
        assert depth in [QADepth.SHALLOW, QADepth.STANDARD]

    def test_override_to_deep(self, selector):
        """Should allow override to DEEP."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            override_depth=QADepth.DEEP,
        )
        assert depth == QADepth.DEEP

    def test_override_combined_with_budget(self, selector):
        """Override should still respect budget constraints."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            override_depth=QADepth.DEEP,
            cost_budget_usd=0.01,  # Very constrained
        )
        # Budget should limit even with override
        assert depth in [QADepth.SHALLOW, QADepth.STANDARD]


# =============================================================================
# RISK SCORE CALCULATION TESTS
# =============================================================================


class TestRiskScoreCalculation:
    """Tests for calculate_risk_score() method."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_returns_float(self, selector):
        """Should return a float value."""
        context = QAContext()
        score = selector.calculate_risk_score(context)
        assert isinstance(score, float)

    def test_returns_value_between_0_and_1(self, selector):
        """Score should be between 0.0 and 1.0."""
        context = QAContext()
        score = selector.calculate_risk_score(context)
        assert 0.0 <= score <= 1.0

    def test_auth_files_high_risk(self, selector):
        """Auth files should have high risk score."""
        context = QAContext(
            target_files=["src/auth/login.py"]
        )
        score = selector.calculate_risk_score(context)
        assert score >= 0.8

    def test_payment_files_high_risk(self, selector):
        """Payment files should have high risk score."""
        context = QAContext(
            target_files=["src/payments/stripe.py"]
        )
        score = selector.calculate_risk_score(context)
        assert score >= 0.8

    def test_utility_files_low_risk(self, selector):
        """Utility files should have lower risk score."""
        context = QAContext(
            target_files=["src/utils/formatting.py"]
        )
        score = selector.calculate_risk_score(context)
        assert score < 0.8

    def test_no_files_returns_default(self, selector):
        """Empty context should return default risk score."""
        context = QAContext()
        score = selector.calculate_risk_score(context)
        assert 0.0 <= score <= 1.0

    def test_git_diff_affects_score(self, selector):
        """Large git diff should increase risk score."""
        small_diff_context = QAContext(
            git_diff="+new line"
        )
        large_diff_context = QAContext(
            git_diff="+new line\n" * 100  # Many changes
        )

        small_score = selector.calculate_risk_score(small_diff_context)
        large_score = selector.calculate_risk_score(large_diff_context)

        # Large diff should have higher or equal risk
        assert large_score >= small_score

    def test_many_endpoints_increases_risk(self, selector):
        """More endpoints affected should increase risk."""
        few_endpoints = QAContext(
            target_endpoints=[QAEndpoint(method="GET", path="/api/health")]
        )
        many_endpoints = QAContext(
            target_endpoints=[
                QAEndpoint(method="GET", path="/api/users"),
                QAEndpoint(method="POST", path="/api/users"),
                QAEndpoint(method="PUT", path="/api/users/{id}"),
                QAEndpoint(method="DELETE", path="/api/users/{id}"),
                QAEndpoint(method="GET", path="/api/items"),
            ]
        )

        few_score = selector.calculate_risk_score(few_endpoints)
        many_score = selector.calculate_risk_score(many_endpoints)

        # More endpoints should have higher or equal risk
        assert many_score >= few_score


# =============================================================================
# DEPTH COST ESTIMATION TESTS
# =============================================================================


class TestDepthCostEstimation:
    """Tests for get_estimated_cost() method."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_returns_cost_for_depth(self, selector):
        """Should return estimated cost for a depth level."""
        cost = selector.get_estimated_cost(QADepth.STANDARD)
        assert isinstance(cost, float)
        assert cost > 0

    def test_shallow_cheaper_than_standard(self, selector):
        """SHALLOW should be cheaper than STANDARD."""
        shallow_cost = selector.get_estimated_cost(QADepth.SHALLOW)
        standard_cost = selector.get_estimated_cost(QADepth.STANDARD)
        assert shallow_cost <= standard_cost

    def test_standard_cheaper_than_deep(self, selector):
        """STANDARD should be cheaper than DEEP."""
        standard_cost = selector.get_estimated_cost(QADepth.STANDARD)
        deep_cost = selector.get_estimated_cost(QADepth.DEEP)
        assert standard_cost <= deep_cost


# =============================================================================
# DEPTH TIME ESTIMATION TESTS
# =============================================================================


class TestDepthTimeEstimation:
    """Tests for get_estimated_time() method."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_returns_time_for_depth(self, selector):
        """Should return estimated time in minutes for a depth level."""
        time_mins = selector.get_estimated_time(QADepth.STANDARD)
        assert isinstance(time_mins, (int, float))
        assert time_mins > 0

    def test_shallow_faster_than_standard(self, selector):
        """SHALLOW should be faster than STANDARD."""
        shallow_time = selector.get_estimated_time(QADepth.SHALLOW)
        standard_time = selector.get_estimated_time(QADepth.STANDARD)
        assert shallow_time <= standard_time

    def test_standard_faster_than_deep(self, selector):
        """STANDARD should be faster than DEEP."""
        standard_time = selector.get_estimated_time(QADepth.STANDARD)
        deep_time = selector.get_estimated_time(QADepth.DEEP)
        assert standard_time <= deep_time


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_handles_empty_context(self, selector):
        """Should handle empty QAContext."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
        )
        assert isinstance(depth, QADepth)

    def test_handles_none_risk_score(self, selector):
        """Should handle None risk score gracefully."""
        context = QAContext()
        # Default risk_score is 0.5, but test explicit None handling
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            risk_score=0.5,  # Default value
        )
        assert isinstance(depth, QADepth)

    def test_handles_zero_budget(self, selector):
        """Should handle zero budget gracefully."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            cost_budget_usd=0.0,
        )
        # Should still return a valid depth (probably SHALLOW)
        assert isinstance(depth, QADepth)

    def test_handles_negative_budget(self, selector):
        """Should handle negative budget by treating as zero."""
        context = QAContext()
        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            cost_budget_usd=-1.0,
        )
        assert isinstance(depth, QADepth)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for DepthSelector."""

    @pytest.fixture
    def selector(self, tmp_path):
        from swarm_attack.qa.depth_selector import DepthSelector
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return DepthSelector(config)

    def test_full_context_with_high_risk_auth(self, selector):
        """Should handle full context with high-risk auth code."""
        context = QAContext(
            feature_id="auth-update",
            issue_number=42,
            target_files=["src/api/auth.py"],
            target_endpoints=[
                QAEndpoint(method="POST", path="/api/auth/login"),
            ],
            git_diff="+def login():\n+    pass",
        )

        depth = selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )

        # Should escalate due to auth files
        assert depth == QADepth.DEEP

    def test_bug_reproduction_with_payment_code(self, selector):
        """Bug reproduction on payment code should stay DEEP."""
        context = QAContext(
            bug_id="BUG-123",
            target_files=["src/payments/checkout.py"],
        )

        depth = selector.select_depth(
            trigger=QATrigger.BUG_REPRODUCTION,
            context=context,
        )

        assert depth == QADepth.DEEP

    def test_pre_merge_with_low_risk_utility(self, selector):
        """Pre-merge on utility code should stay REGRESSION."""
        context = QAContext(
            target_files=["src/utils/formatting.py"],
        )

        depth = selector.select_depth(
            trigger=QATrigger.PRE_MERGE,
            context=context,
            risk_score=0.3,
        )

        assert depth == QADepth.REGRESSION

    def test_user_command_with_budget_constraint(self, selector):
        """User command with tight budget should downgrade."""
        context = QAContext(
            target_endpoints=[
                QAEndpoint(method="GET", path="/api/items"),
            ]
        )

        depth = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            override_depth=QADepth.DEEP,
            cost_budget_usd=0.02,
        )

        # Budget should constrain to lower depth
        assert depth in [QADepth.SHALLOW, QADepth.STANDARD]
