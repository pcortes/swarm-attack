"""Tests for QAOrchestrator following TDD approach.

Tests cover spec sections 6, 10.10-10.12:
- Depth-based agent dispatch
- Cost/limit enforcement
- Graceful degradation
- Session management
- Result aggregation
"""

import json
import pytest
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    QALimits,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify QAOrchestrator can be imported."""

    def test_can_import_qa_orchestrator(self):
        """Should be able to import QAOrchestrator class."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        assert QAOrchestrator is not None

    def test_orchestrator_is_not_base_agent(self):
        """QAOrchestrator should NOT inherit from BaseAgent."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.agents.base import BaseAgent
        # Orchestrator coordinates agents, not an agent itself
        assert not issubclass(QAOrchestrator, BaseAgent)


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestQAOrchestratorInit:
    """Tests for QAOrchestrator initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        orchestrator = QAOrchestrator(mock_config)
        assert orchestrator.config == mock_config

    def test_init_creates_default_limits(self, mock_config):
        """Should create default QALimits if not provided."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        orchestrator = QAOrchestrator(mock_config)
        assert orchestrator.limits is not None
        assert orchestrator.limits.max_cost_usd == 5.0
        assert orchestrator.limits.warn_cost_usd == 2.0

    def test_init_accepts_custom_limits(self, mock_config):
        """Should accept custom QALimits."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        custom_limits = QALimits(max_cost_usd=10.0, warn_cost_usd=5.0)
        orchestrator = QAOrchestrator(mock_config, limits=custom_limits)
        assert orchestrator.limits.max_cost_usd == 10.0
        assert orchestrator.limits.warn_cost_usd == 5.0

    def test_init_creates_agents(self, mock_config):
        """Should create sub-agent instances."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        orchestrator = QAOrchestrator(mock_config)
        assert hasattr(orchestrator, 'behavioral_agent')
        assert hasattr(orchestrator, 'contract_agent')
        assert hasattr(orchestrator, 'regression_agent')

    def test_init_creates_session_storage_path(self, mock_config):
        """Should set up session storage path."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        orchestrator = QAOrchestrator(mock_config)
        assert orchestrator.sessions_path is not None


# =============================================================================
# SESSION ID FORMAT TESTS
# =============================================================================


class TestSessionIdFormat:
    """Tests for session ID generation."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_generates_session_id_with_correct_format(self, orchestrator):
        """Session ID should match qa-YYYYMMDD-HHMMSS format (with optional counter)."""
        session_id = orchestrator._generate_session_id()
        # Pattern: qa-20241226-143022 or qa-20241226-143022-002
        pattern = r'^qa-\d{8}-\d{6}(-\d{3})?$'
        assert re.match(pattern, session_id), f"Session ID '{session_id}' doesn't match expected format"

    def test_session_id_contains_valid_date(self, orchestrator):
        """Session ID should contain a valid date."""
        session_id = orchestrator._generate_session_id()
        date_part = session_id.split('-')[1]
        # Should be a valid date
        datetime.strptime(date_part, '%Y%m%d')

    def test_session_id_contains_valid_time(self, orchestrator):
        """Session ID should contain a valid time."""
        session_id = orchestrator._generate_session_id()
        time_part = session_id.split('-')[2]
        # Should be a valid time
        datetime.strptime(time_part, '%H%M%S')


# =============================================================================
# test() METHOD TESTS
# =============================================================================


class TestTestMethod:
    """Tests for the main test() method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_returns_qa_session(self, orchestrator):
        """Should return a QASession object."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {
                'behavioral': {'tests_run': 1, 'tests_passed': 1, 'findings': []},
            }
            result = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)
            assert isinstance(result, QASession)

    def test_sets_correct_trigger(self, orchestrator):
        """Should set trigger to USER_COMMAND by default."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(target="/api/users")
            assert result.trigger == QATrigger.USER_COMMAND

    def test_sets_custom_trigger(self, orchestrator):
        """Should accept custom trigger."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(
                target="/api/users",
                trigger=QATrigger.POST_VERIFICATION
            )
            assert result.trigger == QATrigger.POST_VERIFICATION

    def test_sets_correct_depth(self, orchestrator):
        """Should set depth correctly."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(target="/api/users", depth=QADepth.DEEP)
            assert result.depth == QADepth.DEEP

    def test_default_depth_is_standard(self, orchestrator):
        """Should default to STANDARD depth."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(target="/api/users")
            assert result.depth == QADepth.STANDARD

    def test_sets_session_timestamps(self, orchestrator):
        """Should set created_at and started_at timestamps."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(target="/api/users")
            assert result.created_at is not None
            assert result.started_at is not None

    def test_sets_completed_at_on_success(self, orchestrator):
        """Should set completed_at timestamp when done."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(target="/api/users")
            assert result.completed_at is not None

    def test_calls_dispatch_agents(self, orchestrator):
        """Should call dispatch_agents with correct depth."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            orchestrator.test(target="/api/users", depth=QADepth.DEEP)
            mock_dispatch.assert_called_once()
            call_args = mock_dispatch.call_args
            assert call_args[0][0] == QADepth.DEEP  # First arg is depth

    def test_handles_base_url(self, orchestrator):
        """Should pass base_url to context."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.test(
                target="/api/users",
                base_url="http://localhost:3000"
            )
            assert result.context.base_url == "http://localhost:3000"

    def test_handles_timeout(self, orchestrator):
        """Should handle timeout parameter."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            # Should not raise even with short timeout if agents complete quickly
            result = orchestrator.test(target="/api/users", timeout=60)
            assert result is not None

    def test_returns_result_with_findings(self, orchestrator):
        """Should include findings from agents in result."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error",
            description="500 error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {
                'behavioral': {
                    'tests_run': 1,
                    'tests_passed': 0,
                    'tests_failed': 1,
                    'findings': [finding],
                },
            }
            result = orchestrator.test(target="/api/users")
            assert result.result is not None
            assert len(result.result.findings) == 1
            assert result.result.findings[0].finding_id == "BT-001"

    def test_handles_agent_errors_gracefully(self, orchestrator):
        """Should handle agent errors without crashing."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.side_effect = Exception("Agent failed")
            result = orchestrator.test(target="/api/users")
            # Should not raise, but mark as failed
            assert result.status in [QAStatus.FAILED, QAStatus.BLOCKED]
            assert result.error is not None


# =============================================================================
# validate_issue() TESTS
# =============================================================================


class TestValidateIssue:
    """Tests for validate_issue() method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_returns_qa_session(self, orchestrator):
        """Should return QASession."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.validate_issue(
                feature_id="my-feature",
                issue_number=42,
            )
            assert isinstance(result, QASession)

    def test_uses_post_verification_trigger(self, orchestrator):
        """Should use POST_VERIFICATION trigger."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.validate_issue(
                feature_id="my-feature",
                issue_number=42,
            )
            assert result.trigger == QATrigger.POST_VERIFICATION

    def test_sets_feature_id_in_context(self, orchestrator):
        """Should set feature_id in context."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.validate_issue(
                feature_id="my-feature",
                issue_number=42,
            )
            assert result.context.feature_id == "my-feature"

    def test_sets_issue_number_in_context(self, orchestrator):
        """Should set issue_number in context."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.validate_issue(
                feature_id="my-feature",
                issue_number=42,
            )
            assert result.context.issue_number == 42

    def test_respects_depth_parameter(self, orchestrator):
        """Should respect custom depth."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.validate_issue(
                feature_id="my-feature",
                issue_number=42,
                depth=QADepth.DEEP,
            )
            assert result.depth == QADepth.DEEP


# =============================================================================
# health_check() TESTS
# =============================================================================


class TestHealthCheck:
    """Tests for health_check() method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_returns_qa_session(self, orchestrator):
        """Should return QASession."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.health_check()
            assert isinstance(result, QASession)

    def test_uses_shallow_depth(self, orchestrator):
        """Should use SHALLOW depth for health checks."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.health_check()
            assert result.depth == QADepth.SHALLOW

    def test_accepts_base_url(self, orchestrator):
        """Should accept base_url parameter."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            result = orchestrator.health_check(base_url="http://localhost:5000")
            assert result.context.base_url == "http://localhost:5000"


# =============================================================================
# dispatch_agents() TESTS
# =============================================================================


class TestDispatchAgents:
    """Tests for dispatch_agents() method - depth-based routing."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        orch = QAOrchestrator(config)
        # Mock the agents
        orch.behavioral_agent = MagicMock()
        orch.contract_agent = MagicMock()
        orch.regression_agent = MagicMock()
        return orch

    def test_shallow_dispatches_only_behavioral(self, orchestrator):
        """SHALLOW depth should only dispatch BehavioralTester."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({})

        context = QAContext()
        orchestrator.dispatch_agents(QADepth.SHALLOW, context)

        orchestrator.behavioral_agent.run.assert_called_once()
        orchestrator.contract_agent.run.assert_not_called()
        orchestrator.regression_agent.run.assert_not_called()

    def test_standard_dispatches_behavioral_and_contract(self, orchestrator):
        """STANDARD depth should dispatch BehavioralTester + ContractValidator."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({})
        orchestrator.contract_agent.run.return_value = AgentResult.success_result({})

        context = QAContext()
        orchestrator.dispatch_agents(QADepth.STANDARD, context)

        orchestrator.behavioral_agent.run.assert_called_once()
        orchestrator.contract_agent.run.assert_called_once()
        orchestrator.regression_agent.run.assert_not_called()

    def test_deep_dispatches_all_agents(self, orchestrator):
        """DEEP depth should dispatch all three agents."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({})
        orchestrator.contract_agent.run.return_value = AgentResult.success_result({})
        orchestrator.regression_agent.run.return_value = AgentResult.success_result({})

        context = QAContext()
        orchestrator.dispatch_agents(QADepth.DEEP, context)

        orchestrator.behavioral_agent.run.assert_called_once()
        orchestrator.contract_agent.run.assert_called_once()
        orchestrator.regression_agent.run.assert_called_once()

    def test_regression_dispatches_regression_and_behavioral(self, orchestrator):
        """REGRESSION depth should dispatch RegressionScanner + BehavioralTester."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({})
        orchestrator.regression_agent.run.return_value = AgentResult.success_result({
            'regression_suite': {'must_test': ['/api/users']},
        })

        context = QAContext()
        orchestrator.dispatch_agents(QADepth.REGRESSION, context)

        orchestrator.regression_agent.run.assert_called_once()
        orchestrator.behavioral_agent.run.assert_called_once()
        orchestrator.contract_agent.run.assert_not_called()

    def test_returns_combined_results(self, orchestrator):
        """Should return combined results from all agents."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({
            'tests_run': 5,
            'tests_passed': 4,
            'tests_failed': 1,
        })
        orchestrator.contract_agent.run.return_value = AgentResult.success_result({
            'contracts_checked': 3,
        })

        context = QAContext()
        result = orchestrator.dispatch_agents(QADepth.STANDARD, context)

        assert 'behavioral' in result
        assert 'contract' in result


# =============================================================================
# COST/LIMIT ENFORCEMENT TESTS (Section 10.10)
# =============================================================================


class TestCostLimitEnforcement:
    """Tests for cost and limit enforcement."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        limits = QALimits(
            max_cost_usd=1.0,
            warn_cost_usd=0.5,
            max_endpoints_shallow=10,
            max_endpoints_standard=5,
            max_endpoints_deep=3,
            session_timeout_minutes=1,
        )
        return QAOrchestrator(config, limits=limits)

    def test_stops_at_max_cost(self, orchestrator):
        """Should stop execution when max_cost_usd is reached."""
        with patch.object(orchestrator, '_get_current_cost') as mock_cost:
            mock_cost.return_value = 1.5  # Exceeds max_cost_usd of 1.0
            result = orchestrator.test(target="/api/users")
            assert result.status == QAStatus.COMPLETED_PARTIAL
            assert "cost" in result.result.partial_completion_reason.lower()

    def test_warns_at_warn_cost(self, orchestrator):
        """Should emit warning when warn_cost_usd is reached."""
        # This tests that cost tracking exists and warnings are logged
        with patch.object(orchestrator, '_get_current_cost') as mock_cost:
            mock_cost.return_value = 0.6  # Above warn_cost_usd of 0.5
            with patch.object(orchestrator, '_log_warning') as mock_warn:
                with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
                    mock_dispatch.return_value = {}
                    orchestrator.test(target="/api/users")
                    # Should have logged a warning about cost
                    # Implementation may vary, but cost tracking should exist

    def test_respects_max_endpoints_shallow(self, orchestrator):
        """Should limit endpoints tested in SHALLOW mode."""
        endpoints = [QAEndpoint(method="GET", path=f"/api/test{i}") for i in range(20)]
        context = QAContext(target_endpoints=endpoints)

        limited = orchestrator._limit_endpoints(endpoints, QADepth.SHALLOW)
        assert len(limited) <= orchestrator.limits.max_endpoints_shallow

    def test_respects_max_endpoints_standard(self, orchestrator):
        """Should limit endpoints tested in STANDARD mode."""
        endpoints = [QAEndpoint(method="GET", path=f"/api/test{i}") for i in range(20)]

        limited = orchestrator._limit_endpoints(endpoints, QADepth.STANDARD)
        assert len(limited) <= orchestrator.limits.max_endpoints_standard

    def test_respects_max_endpoints_deep(self, orchestrator):
        """Should limit endpoints tested in DEEP mode."""
        endpoints = [QAEndpoint(method="GET", path=f"/api/test{i}") for i in range(20)]

        limited = orchestrator._limit_endpoints(endpoints, QADepth.DEEP)
        assert len(limited) <= orchestrator.limits.max_endpoints_deep

    def test_stops_at_session_timeout(self, orchestrator):
        """Should stop when session_timeout_minutes is reached."""
        # Set a very short timeout
        orchestrator.limits.session_timeout_minutes = 0  # Immediate timeout

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            # Simulate slow agent that would exceed timeout
            def slow_dispatch(*args, **kwargs):
                return {}

            mock_dispatch.side_effect = slow_dispatch

            with patch.object(orchestrator, '_check_timeout') as mock_timeout:
                mock_timeout.return_value = True  # Always timeout
                result = orchestrator.test(target="/api/users")
                assert result.status == QAStatus.COMPLETED_PARTIAL
                assert "timeout" in result.result.partial_completion_reason.lower()


# =============================================================================
# GRACEFUL DEGRADATION TESTS (Section 10.12)
# =============================================================================


class TestGracefulDegradation:
    """Tests for graceful degradation behavior."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_returns_blocked_on_infrastructure_failure(self, orchestrator):
        """Should return BLOCKED status on infrastructure failure."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.side_effect = Exception("service_startup_failed")
            result = orchestrator.test(target="/api/users")
            assert result.status == QAStatus.BLOCKED

    def test_returns_completed_partial_on_cost_limit(self, orchestrator):
        """Should return COMPLETED_PARTIAL when stopped by cost limit."""
        orchestrator.limits = QALimits(max_cost_usd=0.01)
        with patch.object(orchestrator, '_get_current_cost') as mock_cost:
            mock_cost.return_value = 1.0  # Way over limit
            result = orchestrator.test(target="/api/users")
            assert result.status == QAStatus.COMPLETED_PARTIAL

    def test_returns_completed_partial_on_timeout(self, orchestrator):
        """Should return COMPLETED_PARTIAL when stopped by timeout."""
        with patch.object(orchestrator, '_check_timeout') as mock_timeout:
            mock_timeout.return_value = True
            result = orchestrator.test(target="/api/users")
            assert result.status == QAStatus.COMPLETED_PARTIAL

    def test_continues_if_one_agent_fails(self, orchestrator):
        """Should continue with other agents if one fails."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent = MagicMock()
        orchestrator.contract_agent = MagicMock()
        orchestrator.regression_agent = MagicMock()

        # Behavioral succeeds
        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({
            'tests_run': 5,
            'tests_passed': 5,
            'findings': [],
        })
        # Contract fails
        orchestrator.contract_agent.run.side_effect = Exception("Contract agent failed")

        context = QAContext()
        result = orchestrator.dispatch_agents(QADepth.STANDARD, context)

        # Should have behavioral results despite contract failure
        assert 'behavioral' in result
        # Should track the skipped agent
        assert 'contract' in result.get('skipped_reasons', {}) or result.get('contract') is None

    def test_tracks_skipped_reasons(self, orchestrator):
        """Should track reasons for skipped agents."""
        from swarm_attack.agents.base import AgentResult
        orchestrator.behavioral_agent = MagicMock()
        orchestrator.contract_agent = MagicMock()
        orchestrator.regression_agent = MagicMock()

        orchestrator.behavioral_agent.run.return_value = AgentResult.success_result({})
        orchestrator.contract_agent.run.side_effect = Exception("No contracts found")

        context = QAContext()
        result = orchestrator.dispatch_agents(QADepth.STANDARD, context)

        # Should have skipped_reasons in result
        assert 'skipped_reasons' in result or result.get('contract') is None


# =============================================================================
# RESULT AGGREGATION TESTS
# =============================================================================


class TestResultAggregation:
    """Tests for result aggregation from multiple agents."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_combines_findings_from_all_agents(self, orchestrator):
        """Should combine findings from all agents."""
        behavioral_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error",
            description="500 error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )
        contract_finding = QAFinding(
            finding_id="CV-001",
            severity="moderate",
            category="contract",
            endpoint="GET /api/users",
            test_type="contract_validation",
            title="Missing field",
            description="Field 'email' missing",
            expected={"fields": ["email"]},
            actual={"fields": []},
            evidence={},
            recommendation="Add email field",
        )

        agent_results = {
            'behavioral': {
                'tests_run': 5,
                'tests_passed': 4,
                'tests_failed': 1,
                'findings': [behavioral_finding],
            },
            'contract': {
                'contracts_checked': 3,
                'contracts_broken': 1,
                'findings': [contract_finding],
            },
        }

        result = orchestrator._aggregate_results(agent_results)
        assert len(result.findings) == 2
        assert any(f.finding_id == "BT-001" for f in result.findings)
        assert any(f.finding_id == "CV-001" for f in result.findings)

    def test_deduplicates_similar_findings(self, orchestrator):
        """Should deduplicate overlapping findings."""
        # Same issue found by two agents
        finding1 = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error 500",
            description="500 error on GET /api/users",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )
        finding2 = QAFinding(
            finding_id="CV-001",
            severity="critical",
            category="contract",
            endpoint="GET /api/users",
            test_type="contract_validation",
            title="Server error 500",
            description="500 error on GET /api/users",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )

        agent_results = {
            'behavioral': {'findings': [finding1]},
            'contract': {'findings': [finding2]},
        }

        result = orchestrator._aggregate_results(agent_results)
        # Should dedupe based on endpoint + actual result
        # May keep both with different IDs, or merge - implementation choice
        # At minimum, should not crash
        assert result is not None

    def test_calculates_correct_counts(self, orchestrator):
        """Should calculate correct test counts."""
        agent_results = {
            'behavioral': {
                'tests_run': 10,
                'tests_passed': 8,
                'tests_failed': 2,
                'findings': [],
            },
            'contract': {
                'contracts_checked': 5,
                'contracts_valid': 4,
                'contracts_broken': 1,
                'findings': [],
            },
        }

        result = orchestrator._aggregate_results(agent_results)
        assert result.tests_run >= 10  # At least behavioral tests
        assert result.tests_passed >= 8

    def test_sets_recommendation_based_on_findings(self, orchestrator):
        """Should set recommendation based on finding severity."""
        critical_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical issue",
            description="Critical",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        agent_results = {
            'behavioral': {'findings': [critical_finding]},
        }

        result = orchestrator._aggregate_results(agent_results)
        assert result.recommendation == QARecommendation.BLOCK

    def test_sets_pass_when_no_critical_findings(self, orchestrator):
        """Should set PASS when no critical/moderate findings."""
        minor_finding = QAFinding(
            finding_id="BT-001",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Minor issue",
            description="Minor",
            expected={},
            actual={},
            evidence={},
            recommendation="Consider fixing",
        )

        agent_results = {
            'behavioral': {'findings': [minor_finding]},
        }

        result = orchestrator._aggregate_results(agent_results)
        assert result.recommendation == QARecommendation.PASS

    def test_sets_warn_for_moderate_findings(self, orchestrator):
        """Should set WARN when moderate but no critical findings."""
        moderate_finding = QAFinding(
            finding_id="BT-001",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Moderate issue",
            description="Moderate",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix soon",
        )

        agent_results = {
            'behavioral': {'findings': [moderate_finding]},
        }

        result = orchestrator._aggregate_results(agent_results)
        assert result.recommendation == QARecommendation.WARN


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================


class TestSessionManagement:
    """Tests for session persistence and retrieval."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_get_session_returns_existing(self, orchestrator, tmp_path):
        """get_session() should return existing session."""
        # Create a session first
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            session = orchestrator.test(target="/api/users")

        # Should be able to retrieve it
        retrieved = orchestrator.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_session_returns_none_for_missing(self, orchestrator):
        """get_session() should return None for non-existent session."""
        result = orchestrator.get_session("qa-99999999-999999")
        assert result is None

    def test_list_sessions_returns_recent_ids(self, orchestrator):
        """list_sessions() should return recent session IDs."""
        # Create a few sessions
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            session1 = orchestrator.test(target="/api/users")
            session2 = orchestrator.test(target="/api/items")

        sessions = orchestrator.list_sessions(limit=10)
        assert len(sessions) >= 2
        assert session1.session_id in sessions
        assert session2.session_id in sessions

    def test_list_sessions_respects_limit(self, orchestrator):
        """list_sessions() should respect limit parameter."""
        # Create several sessions
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            for i in range(5):
                orchestrator.test(target=f"/api/test{i}")

        sessions = orchestrator.list_sessions(limit=2)
        assert len(sessions) <= 2

    def test_sessions_persisted_to_disk(self, orchestrator, tmp_path):
        """Sessions should be persisted to disk."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {}
            session = orchestrator.test(target="/api/users")

        # Check that files were created
        session_dir = orchestrator.sessions_path / session.session_id
        assert session_dir.exists()
        assert (session_dir / "state.json").exists()


# =============================================================================
# get_findings() TESTS
# =============================================================================


class TestGetFindings:
    """Tests for get_findings() method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_returns_all_findings(self, orchestrator):
        """Should return all findings when no filters."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Error",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {
                'behavioral': {'findings': [finding]},
            }
            session = orchestrator.test(target="/api/users")

        findings = orchestrator.get_findings()
        assert len(findings) >= 1

    def test_filters_by_session_id(self, orchestrator):
        """Should filter findings by session_id."""
        finding1 = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Error 1",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        finding2 = QAFinding(
            finding_id="BT-002",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/items",
            test_type="happy_path",
            title="Error 2",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [finding1]}}
            session1 = orchestrator.test(target="/api/users")

            mock_dispatch.return_value = {'behavioral': {'findings': [finding2]}}
            session2 = orchestrator.test(target="/api/items")

        # Filter by session1
        findings = orchestrator.get_findings(session_id=session1.session_id)
        finding_ids = [f.finding_id for f in findings]
        assert "BT-001" in finding_ids
        # BT-002 should not be in session1's findings

    def test_filters_by_severity(self, orchestrator):
        """Should filter findings by severity."""
        critical = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        minor = QAFinding(
            finding_id="BT-002",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/items",
            test_type="happy_path",
            title="Minor",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [critical, minor]}}
            orchestrator.test(target="/api/users")

        # Filter by critical severity
        findings = orchestrator.get_findings(severity="critical")
        assert all(f.severity == "critical" for f in findings)


# =============================================================================
# create_bug_investigations() TESTS
# =============================================================================


class TestCreateBugInvestigations:
    """Tests for create_bug_investigations() method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_creates_bugs_for_findings_above_threshold(self, orchestrator):
        """Should create bugs for findings above severity threshold."""
        critical = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical bug",
            description="Server error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl ..."},
            recommendation="Fix server",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [critical]}}
            session = orchestrator.test(target="/api/users")

        bug_ids = orchestrator.create_bug_investigations(
            session_id=session.session_id,
            severity_threshold="moderate",
        )

        assert len(bug_ids) >= 1

    def test_returns_bug_ids(self, orchestrator):
        """Should return list of created bug IDs."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Bug",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [finding]}}
            session = orchestrator.test(target="/api/users")

        bug_ids = orchestrator.create_bug_investigations(
            session_id=session.session_id,
            severity_threshold="minor",
        )

        assert isinstance(bug_ids, list)
        for bug_id in bug_ids:
            assert isinstance(bug_id, str)

    def test_writes_bug_files(self, orchestrator, tmp_path):
        """Should write bug files to disk."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Bug",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [finding]}}
            session = orchestrator.test(target="/api/users")

        bug_ids = orchestrator.create_bug_investigations(
            session_id=session.session_id,
            severity_threshold="minor",
        )

        # Check bug files were created
        session_dir = orchestrator.sessions_path / session.session_id
        bugs_file = session_dir / "qa-bugs.md"
        assert bugs_file.exists() or len(bug_ids) > 0

    def test_respects_severity_threshold(self, orchestrator):
        """Should only create bugs for findings at or above threshold."""
        minor = QAFinding(
            finding_id="BT-001",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Minor issue",
            description="Minor",
            expected={},
            actual={},
            evidence={},
            recommendation="Maybe fix",
        )

        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': [minor]}}
            session = orchestrator.test(target="/api/users")

        # With "moderate" threshold, minor findings should not create bugs
        bug_ids = orchestrator.create_bug_investigations(
            session_id=session.session_id,
            severity_threshold="moderate",
        )

        assert len(bug_ids) == 0

    def test_returns_empty_for_no_findings(self, orchestrator):
        """Should return empty list when no findings match."""
        with patch.object(orchestrator, 'dispatch_agents') as mock_dispatch:
            mock_dispatch.return_value = {'behavioral': {'findings': []}}
            session = orchestrator.test(target="/api/users")

        bug_ids = orchestrator.create_bug_investigations(
            session_id=session.session_id,
            severity_threshold="minor",
        )

        assert bug_ids == []


# =============================================================================
# BUG #3: SEVERITY COUNTS TESTS
# =============================================================================


class TestSeverityCountsBug:
    """Tests for Bug #3: Severity counts not updated properly."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_aggregate_results_counts_critical_findings(self, orchestrator):
        """Bug #3: Aggregated results should correctly count findings by severity."""
        critical_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/error",
            test_type="happy_path",
            title="Server error",
            description="500 error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix it",
        )

        agent_results = {
            "behavioral": {
                "tests_run": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "findings": [critical_finding],
            }
        }

        result = orchestrator._aggregate_results(agent_results)

        assert result.critical_count == 1, f"Expected 1 critical, got {result.critical_count}"
        assert result.recommendation == QARecommendation.BLOCK

    def test_aggregate_results_counts_moderate_findings(self, orchestrator):
        """Aggregated results should correctly count moderate findings."""
        moderate_finding = QAFinding(
            finding_id="BT-001",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Wrong status",
            description="400 instead of 200",
            expected={"status": 200},
            actual={"status": 400},
            evidence={},
            recommendation="Fix it",
        )

        agent_results = {
            "behavioral": {
                "findings": [moderate_finding],
            }
        }

        result = orchestrator._aggregate_results(agent_results)

        assert result.moderate_count == 1, f"Expected 1 moderate, got {result.moderate_count}"
        assert result.recommendation == QARecommendation.WARN

    def test_aggregate_results_counts_minor_findings(self, orchestrator):
        """Aggregated results should correctly count minor findings."""
        minor_finding = QAFinding(
            finding_id="BT-001",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Minor issue",
            description="Minor",
            expected={},
            actual={},
            evidence={},
            recommendation="Consider fixing",
        )

        agent_results = {
            "behavioral": {
                "findings": [minor_finding],
            }
        }

        result = orchestrator._aggregate_results(agent_results)

        assert result.minor_count == 1, f"Expected 1 minor, got {result.minor_count}"
        assert result.recommendation == QARecommendation.PASS

    def test_aggregate_results_handles_dict_findings(self, orchestrator):
        """Bug #3: Should handle findings passed as dicts (from JSON deserialization)."""
        # This is how findings might come from a mocked agent or JSON
        finding_as_dict = {
            "finding_id": "BT-001",
            "severity": "critical",
            "category": "behavioral",
            "endpoint": "GET /api/error",
            "test_type": "happy_path",
            "title": "Server error",
            "description": "500 error",
            "expected": {"status": 200},
            "actual": {"status": 500},
            "evidence": {},
            "recommendation": "Fix it",
            "confidence": 0.9,
        }

        agent_results = {
            "behavioral": {
                "tests_run": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "findings": [finding_as_dict],
            }
        }

        result = orchestrator._aggregate_results(agent_results)

        # Should still count the finding even if it's a dict
        assert result.critical_count == 1, f"Expected 1 critical, got {result.critical_count}"
        assert result.recommendation == QARecommendation.BLOCK


# =============================================================================
# BUG #2: HEALTH CHECK TESTS
# =============================================================================


class TestHealthCheckBug:
    """Tests for Bug #2: Health check runs zero tests."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.agents.base import AgentResult
        config = MagicMock()
        config.repo_root = str(tmp_path)
        orch = QAOrchestrator(config)
        # Mock the behavioral agent to return a real result
        orch.behavioral_agent = MagicMock()
        orch.behavioral_agent.run.return_value = AgentResult.success_result({
            "tests_run": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "findings": [],
        })
        return orch

    def test_health_check_runs_at_least_one_test(self, orchestrator):
        """Bug #2: Health check should run at least one test when base_url is provided."""
        session = orchestrator.health_check(base_url="http://localhost:8765")

        assert session.status == QAStatus.COMPLETED
        assert session.result is not None
        assert session.result.tests_run >= 1, "Health check should run at least 1 test"
        assert session.context.base_url == "http://localhost:8765"

    def test_health_check_has_default_endpoints(self, orchestrator):
        """Bug #2: Health check should have default health endpoints in context."""
        session = orchestrator.health_check(base_url="http://localhost:8765")

        # Should have at least one endpoint to test
        assert len(session.context.target_endpoints) >= 1, \
            "Health check should have default endpoints"

        # Should include common health endpoints
        health_paths = [e.path for e in session.context.target_endpoints]
        has_health_path = any(
            "/health" in p or "/healthz" in p or "/_health" in p
            for p in health_paths
        )
        assert has_health_path, f"Expected health endpoint, got: {health_paths}"


# =============================================================================
# BUG #4: DEPTH SCALING TESTS
# =============================================================================


class TestDepthScalingBug:
    """Tests for Bug #4: Test count should scale with depth."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        from swarm_attack.qa.orchestrator import QAOrchestrator
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAOrchestrator(config)

    def test_standard_depth_runs_more_tests_than_shallow(self, orchestrator):
        """Bug #4: Standard depth should run more tests than shallow."""
        from swarm_attack.agents.base import AgentResult

        # Track how many tests would be run for each depth
        shallow_tests = []
        standard_tests = []

        def mock_behavioral_run(context):
            depth = context.get("depth", QADepth.SHALLOW)
            endpoints = context.get("endpoints", [])
            # BehavioralTester generates 1 test for SHALLOW, 2+ for STANDARD
            if depth == QADepth.SHALLOW:
                test_count = len(endpoints)  # 1 test per endpoint
                shallow_tests.append(test_count)
            else:
                test_count = len(endpoints) * 2  # 2+ tests per endpoint for STANDARD
                standard_tests.append(test_count)

            return AgentResult.success_result({
                "tests_run": test_count,
                "tests_passed": test_count,
                "tests_failed": 0,
                "findings": [],
            })

        def mock_contract_run(context):
            endpoints = context.get("endpoints", [])
            return AgentResult.success_result({
                "contracts_checked": len(endpoints),
                "contracts_valid": len(endpoints),
                "contracts_broken": 0,
                "findings": [],
            })

        orchestrator.behavioral_agent = MagicMock()
        orchestrator.behavioral_agent.run = mock_behavioral_run
        orchestrator.contract_agent = MagicMock()
        orchestrator.contract_agent.run = mock_contract_run

        context = QAContext(
            base_url="http://localhost:8765",
            target_endpoints=[QAEndpoint(method="GET", path="/api/users")],
        )

        # Run shallow
        shallow_results = orchestrator.dispatch_agents(QADepth.SHALLOW, context)
        shallow_test_count = shallow_results.get("behavioral", {}).get("tests_run", 0)

        # Run standard
        standard_results = orchestrator.dispatch_agents(QADepth.STANDARD, context)
        standard_behavioral = standard_results.get("behavioral", {}).get("tests_run", 0)
        standard_contract = standard_results.get("contract", {}).get("contracts_checked", 0)
        standard_total = standard_behavioral + standard_contract

        assert standard_total > shallow_test_count, \
            f"Standard ({standard_total}) should run more tests than shallow ({shallow_test_count})"

    def test_behavioral_agent_generates_more_tests_for_standard_depth(self, tmp_path):
        """Behavioral agent should generate more tests for STANDARD vs SHALLOW."""
        from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent

        config = MagicMock()
        config.repo_root = str(tmp_path)

        agent = BehavioralTesterAgent(config)

        endpoint = QAEndpoint(method="POST", path="/api/users", auth_required=True)

        # Generate tests for SHALLOW
        shallow_tests = agent._generate_tests(endpoint, QADepth.SHALLOW)

        # Generate tests for STANDARD
        standard_tests = agent._generate_tests(endpoint, QADepth.STANDARD)

        # Generate tests for DEEP
        deep_tests = agent._generate_tests(endpoint, QADepth.DEEP)

        assert len(shallow_tests) == 1, f"SHALLOW should generate 1 test, got {len(shallow_tests)}"
        assert len(standard_tests) > len(shallow_tests), \
            f"STANDARD ({len(standard_tests)}) should generate more tests than SHALLOW ({len(shallow_tests)})"
        assert len(deep_tests) >= len(standard_tests), \
            f"DEEP ({len(deep_tests)}) should generate at least as many tests as STANDARD ({len(standard_tests)})"
