"""System Validation Tests.

End-to-end validation that all QA components work together.
Tests the complete flow from CLI trigger to results.

Priority 10: Final Validation & Documentation
"""

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from typer.testing import CliRunner

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
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.context_builder import QAContextBuilder
from swarm_attack.qa.depth_selector import DepthSelector


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock()
    return logger


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with required structure."""
    # Create .swarm directory structure
    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir()
    (swarm_dir / "qa").mkdir()

    # Create specs directory
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    # Create a test feature spec
    feature_dir = specs_dir / "test-feature"
    feature_dir.mkdir()
    (feature_dir / "spec-final.md").write_text("# Test Feature\n\nTest spec content.")

    return tmp_path


@pytest.fixture
def sample_finding():
    """Create a sample QA finding."""
    return QAFinding(
        finding_id="BT-001",
        severity="critical",
        category="behavioral",
        endpoint="GET /api/users",
        test_type="happy_path",
        title="Server error on GET /api/users",
        description="Endpoint returns 500 instead of 200",
        expected={"status": 200},
        actual={"status": 500},
        evidence={"request": "curl -X GET http://localhost:8000/api/users"},
        recommendation="Fix server error handling",
    )


@pytest.fixture
def sample_session(sample_finding):
    """Create a sample QA session with results."""
    context = QAContext(base_url="http://localhost:8000")
    result = QAResult(
        tests_run=10,
        tests_passed=8,
        tests_failed=2,
        endpoints_tested=["/api/users", "/api/items"],
        findings=[sample_finding],
        critical_count=1,
        recommendation=QARecommendation.BLOCK,
    )
    session = QASession(
        session_id="qa-20241226-120000",
        trigger=QATrigger.USER_COMMAND,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=context,
        result=result,
    )
    session.started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return session


# =============================================================================
# TEST: FULL QA FLOW
# =============================================================================


class TestFullQAFlow:
    """Tests for complete QA flow."""

    def test_cli_triggers_orchestrator(self, mock_config, mock_logger, temp_project_dir):
        """CLI command should trigger orchestrator correctly."""
        mock_config.repo_root = str(temp_project_dir)

        # Create orchestrator and verify it initializes
        orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Verify agents are created
        assert orchestrator.behavioral_agent is not None
        assert orchestrator.contract_agent is not None
        assert orchestrator.regression_agent is not None

        # Verify session path is created
        assert (temp_project_dir / ".swarm" / "qa").exists()

    def test_orchestrator_dispatches_to_agents(self, mock_config, mock_logger, temp_project_dir):
        """Orchestrator should dispatch to appropriate agents."""
        mock_config.repo_root = str(temp_project_dir)
        orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Create context
        context = QAContext(
            base_url="http://localhost:8000",
            target_endpoints=[QAEndpoint(method="GET", path="/api/users")],
        )

        # Mock agent run methods
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"tests_run": 5, "tests_passed": 4, "tests_failed": 1}

        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_result)
        orchestrator.contract_agent.run = MagicMock(return_value=mock_result)
        orchestrator.regression_agent.run = MagicMock(return_value=mock_result)

        # Test SHALLOW depth - only behavioral
        results = orchestrator.dispatch_agents(QADepth.SHALLOW, context)
        assert "behavioral" in results
        assert "contract" not in results

        # Test STANDARD depth - behavioral + contract
        results = orchestrator.dispatch_agents(QADepth.STANDARD, context)
        assert "behavioral" in results
        assert "contract" in results

        # Test DEEP depth - all agents
        results = orchestrator.dispatch_agents(QADepth.DEEP, context)
        assert "behavioral" in results
        assert "contract" in results
        assert "regression" in results

    def test_agents_produce_findings(self, mock_config, mock_logger, temp_project_dir):
        """Agents should produce findings in correct format."""
        mock_config.repo_root = str(temp_project_dir)
        orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Create a finding
        finding = QAFinding(
            finding_id="BT-001",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Test finding",
            description="Test description",
            expected={"status": 200},
            actual={"status": 404},
            evidence={"request": "test"},
            recommendation="Fix it",
        )

        # Mock agent that produces findings
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {
            "tests_run": 5,
            "tests_passed": 4,
            "tests_failed": 1,
            "findings": [finding],
        }

        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_result)

        context = QAContext(
            base_url="http://localhost:8000",
            target_endpoints=[QAEndpoint(method="GET", path="/api/users")],
        )

        results = orchestrator.dispatch_agents(QADepth.SHALLOW, context)

        assert "behavioral" in results
        assert results["behavioral"]["tests_run"] == 5
        assert len(results["behavioral"]["findings"]) == 1
        assert results["behavioral"]["findings"][0].severity == "moderate"

    def test_findings_aggregate_correctly(self, mock_config, mock_logger, temp_project_dir):
        """Findings should aggregate into session result."""
        mock_config.repo_root = str(temp_project_dir)
        orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Create findings from different agents
        behavioral_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Behavioral finding",
            description="Test description",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "test"},
            recommendation="Fix it",
        )

        contract_finding = QAFinding(
            finding_id="CT-001",
            severity="moderate",
            category="contract",
            endpoint="POST /api/users",
            test_type="schema_validation",
            title="Contract finding",
            description="Schema violation",
            expected={"type": "object"},
            actual={"type": "string"},
            evidence={"response": "test"},
            recommendation="Update schema",
        )

        # Mock agents
        mock_behavioral = MagicMock()
        mock_behavioral.success = True
        mock_behavioral.output = {
            "tests_run": 3,
            "tests_passed": 2,
            "tests_failed": 1,
            "findings": [behavioral_finding],
        }

        mock_contract = MagicMock()
        mock_contract.success = True
        mock_contract.output = {
            "contracts_checked": 2,
            "contracts_valid": 1,
            "contracts_broken": 1,
            "findings": [contract_finding],
        }

        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral)
        orchestrator.contract_agent.run = MagicMock(return_value=mock_contract)

        context = QAContext(
            base_url="http://localhost:8000",
            target_endpoints=[QAEndpoint(method="GET", path="/api/users")],
        )

        # Dispatch and aggregate
        agent_results = orchestrator.dispatch_agents(QADepth.STANDARD, context)
        result = orchestrator._aggregate_results(agent_results)

        # Verify aggregation
        assert result.tests_run == 5  # 3 + 2
        assert result.tests_passed == 3  # 2 + 1
        assert result.tests_failed == 2  # 1 + 1
        assert len(result.findings) == 2
        assert result.critical_count == 1
        assert result.moderate_count == 1
        assert result.recommendation == QARecommendation.BLOCK  # Critical = BLOCK

    def test_hooks_receive_session_data(self, mock_config, mock_logger, temp_project_dir):
        """Hooks should receive complete session data."""
        mock_config.repo_root = str(temp_project_dir)

        # Mock agents to not make real calls
        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    # Setup mock agents
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Run test and get session
                    session = orchestrator.test(
                        target="/api/users",
                        depth=QADepth.SHALLOW,
                        trigger=QATrigger.USER_COMMAND,
                    )

                    # Verify session has all required fields
                    assert session.session_id is not None
                    assert session.trigger == QATrigger.USER_COMMAND
                    assert session.depth == QADepth.SHALLOW
                    assert session.status in [QAStatus.COMPLETED, QAStatus.COMPLETED_PARTIAL]
                    assert session.context is not None
                    assert session.started_at is not None
                    assert session.completed_at is not None

    def test_complete_flow_end_to_end(self, mock_config, mock_logger, temp_project_dir):
        """Complete end-to-end flow from test() to saved session."""
        mock_config.repo_root = str(temp_project_dir)

        # Create a sample finding that agent will return
        finding = QAFinding(
            finding_id="BT-001",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Minor issue",
            description="Test description",
            expected={"status": 200},
            actual={"status": 200, "warning": True},
            evidence={"request": "test"},
            recommendation="Consider fixing",
        )

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {
                        "tests_run": 5,
                        "tests_passed": 4,
                        "tests_failed": 1,
                        "findings": [finding],
                    }
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Run complete flow
                    session = orchestrator.test(
                        target="/api/users",
                        depth=QADepth.STANDARD,
                        trigger=QATrigger.USER_COMMAND,
                        base_url="http://localhost:8000",
                    )

                    # Verify session completed
                    assert session.status == QAStatus.COMPLETED

                    # Verify session was saved
                    session_dir = temp_project_dir / ".swarm" / "qa" / session.session_id
                    assert session_dir.exists()
                    assert (session_dir / "state.json").exists()
                    assert (session_dir / "qa-report.md").exists()

                    # Verify saved data matches
                    saved_data = json.loads((session_dir / "state.json").read_text())
                    assert saved_data["session_id"] == session.session_id
                    assert saved_data["status"] == "completed"

                    # Verify report contains finding
                    report = (session_dir / "qa-report.md").read_text()
                    assert "BT-001" in report
                    assert "Minor issue" in report


# =============================================================================
# TEST: CONFIGURATION VALIDATION
# =============================================================================


class TestConfigurationValidation:
    """Tests for configuration system."""

    def test_default_config_is_valid(self, mock_config, mock_logger, temp_project_dir):
        """Default config should produce valid settings."""
        mock_config.repo_root = str(temp_project_dir)

        # Create orchestrator with no explicit limits (uses defaults)
        orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Verify default limits are set
        assert orchestrator.limits is not None
        assert orchestrator.limits.max_cost_usd > 0
        assert orchestrator.limits.session_timeout_minutes > 0
        assert orchestrator.limits.max_endpoints_shallow > 0
        assert orchestrator.limits.max_endpoints_standard > 0
        assert orchestrator.limits.max_endpoints_deep > 0

    def test_config_overrides_work(self, mock_config, mock_logger, temp_project_dir):
        """Config overrides should apply correctly."""
        mock_config.repo_root = str(temp_project_dir)

        # Create custom limits
        custom_limits = QALimits(
            max_cost_usd=1.0,
            warn_cost_usd=0.5,
            session_timeout_minutes=10,
            max_endpoints_shallow=50,
            max_endpoints_standard=25,
            max_endpoints_deep=10,
        )

        orchestrator = QAOrchestrator(mock_config, mock_logger, limits=custom_limits)

        # Verify overrides applied
        assert orchestrator.limits.max_cost_usd == 1.0
        assert orchestrator.limits.warn_cost_usd == 0.5
        assert orchestrator.limits.session_timeout_minutes == 10
        assert orchestrator.limits.max_endpoints_shallow == 50
        assert orchestrator.limits.max_endpoints_standard == 25
        assert orchestrator.limits.max_endpoints_deep == 10

    def test_limits_enforce_endpoint_caps(self, mock_config, mock_logger, temp_project_dir):
        """Limits should enforce endpoint caps based on depth."""
        mock_config.repo_root = str(temp_project_dir)

        custom_limits = QALimits(
            max_endpoints_shallow=2,
            max_endpoints_standard=5,
            max_endpoints_deep=3,
        )

        orchestrator = QAOrchestrator(mock_config, mock_logger, limits=custom_limits)

        # Create 10 endpoints
        endpoints = [
            QAEndpoint(method="GET", path=f"/api/item{i}")
            for i in range(10)
        ]

        # Test SHALLOW limit
        limited = orchestrator._limit_endpoints(endpoints, QADepth.SHALLOW)
        assert len(limited) == 2

        # Test STANDARD limit
        limited = orchestrator._limit_endpoints(endpoints, QADepth.STANDARD)
        assert len(limited) == 5

        # Test DEEP limit
        limited = orchestrator._limit_endpoints(endpoints, QADepth.DEEP)
        assert len(limited) == 3

    def test_cost_limit_prevents_session(self, mock_config, mock_logger, temp_project_dir):
        """Session should not run if cost limit already exceeded."""
        mock_config.repo_root = str(temp_project_dir)

        # Create limits with zero max cost
        zero_cost_limits = QALimits(max_cost_usd=0.0)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(mock_config, mock_logger, limits=zero_cost_limits)

                    # Force accumulated cost above limit
                    orchestrator._accumulated_cost = 0.1

                    session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    assert session.status == QAStatus.COMPLETED_PARTIAL
                    assert "cost_limit" in session.result.partial_completion_reason


# =============================================================================
# TEST: ERROR RECOVERY
# =============================================================================


class TestErrorRecovery:
    """Tests for error recovery scenarios."""

    def test_partial_failure_recovery(self, mock_config, mock_logger, temp_project_dir):
        """System should recover from partial failures."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    # Make behavioral succeed
                    success_agent = MagicMock()
                    success_result = MagicMock()
                    success_result.success = True
                    success_result.output = {"tests_run": 5, "tests_passed": 5, "tests_failed": 0}
                    success_agent.run.return_value = success_result

                    # Make contract fail
                    fail_agent = MagicMock()
                    fail_result = MagicMock()
                    fail_result.success = False
                    fail_result.error = "Contract validation failed"
                    fail_agent.run.return_value = fail_result

                    mock_bta.return_value = success_agent
                    mock_cva.return_value = fail_agent
                    mock_rsa.return_value = success_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Run with STANDARD depth (uses both behavioral and contract)
                    session = orchestrator.test(
                        target="/api/users",
                        depth=QADepth.STANDARD,
                    )

                    # Session should complete (not fail) but have partial results
                    assert session.status == QAStatus.COMPLETED
                    assert session.result is not None
                    assert session.result.skipped_reasons is not None
                    assert "contract" in session.result.skipped_reasons

    def test_timeout_handling(self, mock_config, mock_logger, temp_project_dir):
        """System should handle timeouts gracefully."""
        mock_config.repo_root = str(temp_project_dir)

        # Create very short timeout
        short_timeout_limits = QALimits(session_timeout_minutes=0)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(
                        mock_config, mock_logger, limits=short_timeout_limits
                    )

                    # Simulate that time has already passed
                    orchestrator._session_start_time = 0  # Very old timestamp

                    session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    assert session.status == QAStatus.COMPLETED_PARTIAL
                    assert session.result.partial_completion_reason is not None
                    assert "timeout" in session.result.partial_completion_reason

    def test_agent_exception_recovery(self, mock_config, mock_logger, temp_project_dir):
        """System should recover when agent raises exception."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    # Make behavioral throw exception
                    exception_agent = MagicMock()
                    exception_agent.run.side_effect = Exception("Network error")

                    mock_bta.return_value = exception_agent
                    mock_cva.return_value = exception_agent
                    mock_rsa.return_value = exception_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    context = QAContext(base_url="http://localhost:8000")
                    skipped = {}

                    # Run agent safely
                    result = orchestrator._run_agent_safe(
                        exception_agent, {"base_url": "http://localhost:8000"},
                        "behavioral", skipped
                    )

                    assert result is None
                    assert "behavioral" in skipped
                    assert "Network error" in skipped["behavioral"]

    def test_session_persists_on_error(self, mock_config, mock_logger, temp_project_dir):
        """Session should be saved even when error occurs."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    # Create agent that throws
                    error_agent = MagicMock()
                    error_agent.run.side_effect = Exception("Catastrophic failure")

                    mock_bta.return_value = error_agent
                    mock_cva.return_value = error_agent
                    mock_rsa.return_value = error_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Override dispatch to throw
                    original_dispatch = orchestrator.dispatch_agents
                    orchestrator.dispatch_agents = MagicMock(
                        side_effect=Exception("Dispatch failed")
                    )

                    session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    # Session should be marked as blocked
                    assert session.status == QAStatus.BLOCKED
                    assert session.error is not None
                    assert "Dispatch failed" in session.error

                    # Session should still be saved
                    session_dir = temp_project_dir / ".swarm" / "qa" / session.session_id
                    assert session_dir.exists()


# =============================================================================
# TEST: CONTEXT BUILDER INTEGRATION
# =============================================================================


class TestContextBuilderIntegration:
    """Tests for context builder integration with orchestrator."""

    def test_context_builder_discovers_endpoints(self, mock_config, mock_logger, temp_project_dir):
        """Context builder should discover endpoints from Python files."""
        mock_config.repo_root = str(temp_project_dir)

        # Create a FastAPI routes file
        api_file = temp_project_dir / "routes.py"
        api_file.write_text('''
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/users")
async def list_users():
    return []

@router.post("/api/users")
async def create_user():
    return {}

@router.delete("/api/users/{id}")
async def delete_user(id: int):
    return {}
''')

        context_builder = QAContextBuilder(mock_config, mock_logger)
        endpoints = context_builder.discover_endpoints(str(api_file))

        assert len(endpoints) == 3
        methods = {e.method for e in endpoints}
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods

    def test_context_builder_loads_spec_content(self, mock_config, mock_logger, temp_project_dir):
        """Context builder should load spec content for features."""
        mock_config.repo_root = str(temp_project_dir)

        context_builder = QAContextBuilder(mock_config, mock_logger)
        context = context_builder.build_context(
            trigger=QATrigger.POST_VERIFICATION,
            target="/api/users",
            feature_id="test-feature",
        )

        assert context.spec_content is not None
        assert "Test Feature" in context.spec_content


# =============================================================================
# TEST: DEPTH SELECTOR INTEGRATION
# =============================================================================


class TestDepthSelectorIntegration:
    """Tests for depth selector integration with orchestrator."""

    def test_depth_selector_escalates_for_auth(self, mock_config, mock_logger):
        """Depth selector should escalate for auth-related changes."""
        depth_selector = DepthSelector(mock_config, mock_logger)

        context = QAContext(
            target_files=["/app/auth/login.py"],
            target_endpoints=[QAEndpoint(method="POST", path="/api/auth/login")],
        )

        depth = depth_selector.select_depth(
            trigger=QATrigger.POST_VERIFICATION,
            context=context,
        )

        # Auth changes should escalate to DEEP
        assert depth == QADepth.DEEP

    def test_depth_selector_respects_budget(self, mock_config, mock_logger):
        """Depth selector should respect cost budgets."""
        depth_selector = DepthSelector(mock_config, mock_logger)

        context = QAContext(target_files=["/app/utils.py"])

        # With tiny budget, should downgrade to SHALLOW
        depth = depth_selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
            cost_budget_usd=0.01,
        )

        assert depth == QADepth.SHALLOW


# =============================================================================
# TEST: SESSION MANAGEMENT
# =============================================================================


class TestSessionManagement:
    """Tests for session lifecycle management."""

    def test_session_id_uniqueness(self, mock_config, mock_logger, temp_project_dir):
        """Session IDs should be unique."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Create multiple sessions
                    session_ids = set()
                    for _ in range(5):
                        session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)
                        session_ids.add(session.session_id)

                    # All should be unique
                    assert len(session_ids) == 5

    def test_session_retrieval(self, mock_config, mock_logger, temp_project_dir):
        """Saved sessions should be retrievable."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Create and save a session
                    original = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    # Retrieve it
                    retrieved = orchestrator.get_session(original.session_id)

                    assert retrieved is not None
                    assert retrieved.session_id == original.session_id
                    assert retrieved.status == original.status

    def test_session_listing(self, mock_config, mock_logger, temp_project_dir):
        """Sessions should be listable."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    # Create a few sessions
                    for _ in range(3):
                        orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    # List sessions
                    sessions = orchestrator.list_sessions()

                    assert len(sessions) >= 3


# =============================================================================
# TEST: VALIDATE ISSUE FLOW
# =============================================================================


class TestValidateIssueFlow:
    """Tests for the validate_issue flow."""

    def test_validate_issue_creates_session(self, mock_config, mock_logger, temp_project_dir):
        """validate_issue should create a proper session."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 3, "tests_passed": 3, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    session = orchestrator.validate_issue(
                        feature_id="test-feature",
                        issue_number=1,
                        depth=QADepth.STANDARD,
                    )

                    assert session.trigger == QATrigger.POST_VERIFICATION
                    assert session.context.feature_id == "test-feature"
                    assert session.context.issue_number == 1


# =============================================================================
# TEST: HEALTH CHECK FLOW
# =============================================================================


class TestHealthCheckFlow:
    """Tests for the health_check flow."""

    def test_health_check_uses_shallow_depth(self, mock_config, mock_logger, temp_project_dir):
        """health_check should always use SHALLOW depth."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)

                    session = orchestrator.health_check(base_url="http://localhost:8000")

                    assert session.depth == QADepth.SHALLOW
