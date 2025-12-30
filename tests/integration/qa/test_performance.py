"""Performance Benchmark Tests.

Establishes baselines for QA system performance.
These tests ensure the QA system remains responsive and efficient.

Priority 12: Performance Benchmarks
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
def mock_config(tmp_path):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with required structure."""
    # Create .swarm directory structure
    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir()
    (swarm_dir / "qa").mkdir()

    # Create specs directory with sample data
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    feature_dir = specs_dir / "test-feature"
    feature_dir.mkdir()
    (feature_dir / "spec-final.md").write_text("# Test Feature\n\n" + "Test content. " * 100)

    return tmp_path


@pytest.fixture
def sample_api_file(tmp_path):
    """Create a sample FastAPI routes file for testing."""
    api_file = tmp_path / "routes.py"
    content = '''
from fastapi import APIRouter

router = APIRouter()
'''
    # Add 50 routes to simulate a real-world API
    for i in range(50):
        content += f'''
@router.get("/api/resource{i}")
async def get_resource{i}():
    return {{"id": {i}}}

@router.post("/api/resource{i}")
async def create_resource{i}():
    return {{"id": {i}}}
'''
    api_file.write_text(content)
    return api_file


@pytest.fixture
def large_openapi_spec(tmp_path):
    """Create a large OpenAPI spec file for testing."""
    spec_file = tmp_path / "openapi.yaml"
    content = '''openapi: "3.0.0"
info:
  title: Test API
  version: 1.0.0
paths:
'''
    # Add 100 paths to simulate a large API
    for i in range(100):
        content += f'''  /api/resource{i}:
    get:
      summary: Get resource {i}
    post:
      summary: Create resource {i}
    put:
      summary: Update resource {i}
    delete:
      summary: Delete resource {i}
'''
    spec_file.write_text(content)
    return spec_file


# =============================================================================
# TEST: INITIALIZATION PERFORMANCE
# =============================================================================


class TestInitializationPerformance:
    """Tests for initialization performance."""

    def test_orchestrator_initialization_time(self, mock_config, mock_logger, temp_project_dir):
        """Orchestrator should initialize quickly."""
        mock_config.repo_root = str(temp_project_dir)

        start = time.time()
        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(mock_config, mock_logger)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Initialization took {elapsed:.2f}s, should be < 1 second"

    def test_context_builder_initialization_time(self, mock_config, mock_logger):
        """ContextBuilder should initialize quickly."""
        start = time.time()
        builder = QAContextBuilder(mock_config, mock_logger)
        elapsed = time.time() - start

        assert elapsed < 0.1, f"Initialization took {elapsed:.3f}s, should be < 0.1 second"

    def test_depth_selector_initialization_time(self, mock_config, mock_logger):
        """DepthSelector should initialize quickly."""
        start = time.time()
        selector = DepthSelector(mock_config, mock_logger)
        elapsed = time.time() - start

        assert elapsed < 0.1, f"Initialization took {elapsed:.3f}s, should be < 0.1 second"

    def test_multiple_orchestrator_instances(self, mock_config, mock_logger, temp_project_dir):
        """Multiple orchestrator instances should initialize efficiently."""
        mock_config.repo_root = str(temp_project_dir)

        start = time.time()
        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrators = [
                        QAOrchestrator(mock_config, mock_logger)
                        for _ in range(10)
                    ]
        elapsed = time.time() - start

        assert elapsed < 3.0, f"10 initializations took {elapsed:.2f}s, should be < 3 seconds"
        assert len(orchestrators) == 10


# =============================================================================
# TEST: CONTEXT BUILDING PERFORMANCE
# =============================================================================


class TestContextBuilderPerformance:
    """Tests for context building performance."""

    def test_context_builder_basic_performance(self, mock_config, mock_logger):
        """Basic context building should be fast."""
        builder = QAContextBuilder(mock_config, mock_logger)

        start = time.time()
        for _ in range(100):
            context = builder.build_context(
                trigger=QATrigger.USER_COMMAND,
                target="/api/users",
            )
        elapsed = time.time() - start

        assert elapsed < 1.0, f"100 context builds took {elapsed:.2f}s, should be < 1 second"

    def test_endpoint_discovery_from_python(self, mock_config, mock_logger, sample_api_file):
        """Endpoint discovery from Python should be fast."""
        mock_config.repo_root = str(sample_api_file.parent)
        builder = QAContextBuilder(mock_config, mock_logger)

        start = time.time()
        endpoints = builder.discover_endpoints(str(sample_api_file))
        elapsed = time.time() - start

        assert len(endpoints) == 100, f"Expected 100 endpoints, found {len(endpoints)}"
        assert elapsed < 0.5, f"Discovery took {elapsed:.3f}s, should be < 0.5 second"

    def test_endpoint_discovery_from_openapi(self, mock_config, mock_logger, large_openapi_spec):
        """Endpoint discovery from OpenAPI should be fast."""
        mock_config.repo_root = str(large_openapi_spec.parent)
        builder = QAContextBuilder(mock_config, mock_logger)

        start = time.time()
        endpoints = builder.discover_endpoints(str(large_openapi_spec))
        elapsed = time.time() - start

        assert len(endpoints) >= 100, f"Expected 100+ endpoints, found {len(endpoints)}"
        assert elapsed < 1.0, f"Discovery took {elapsed:.3f}s, should be < 1 second"


# =============================================================================
# TEST: DEPTH SELECTION PERFORMANCE
# =============================================================================


class TestDepthSelectionPerformance:
    """Tests for depth selection performance."""

    def test_depth_selection_basic_performance(self, mock_config, mock_logger):
        """Basic depth selection should be instant."""
        selector = DepthSelector(mock_config, mock_logger)
        context = QAContext()

        start = time.time()
        for _ in range(1000):
            depth = selector.select_depth(
                trigger=QATrigger.USER_COMMAND,
                context=context,
            )
        elapsed = time.time() - start

        assert elapsed < 0.5, f"1000 depth selections took {elapsed:.3f}s, should be < 0.5 second"

    def test_risk_score_calculation_performance(self, mock_config, mock_logger):
        """Risk score calculation should be fast."""
        selector = DepthSelector(mock_config, mock_logger)

        # Create context with many files and endpoints
        context = QAContext(
            target_files=[f"/app/module{i}.py" for i in range(20)],
            target_endpoints=[
                QAEndpoint(method="GET", path=f"/api/resource{i}")
                for i in range(50)
            ],
        )

        start = time.time()
        for _ in range(1000):
            score = selector.calculate_risk_score(context)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"1000 risk calculations took {elapsed:.3f}s, should be < 1 second"

    def test_depth_selection_with_constraints(self, mock_config, mock_logger):
        """Depth selection with budget constraints should be fast."""
        selector = DepthSelector(mock_config, mock_logger)
        context = QAContext()

        start = time.time()
        for _ in range(1000):
            depth = selector.select_depth(
                trigger=QATrigger.USER_COMMAND,
                context=context,
                risk_score=0.9,
                time_budget_minutes=1.0,
                cost_budget_usd=0.05,
            )
        elapsed = time.time() - start

        assert elapsed < 0.5, f"1000 constrained selections took {elapsed:.3f}s, should be < 0.5 second"


# =============================================================================
# TEST: SESSION MANAGEMENT PERFORMANCE
# =============================================================================


class TestSessionManagementPerformance:
    """Tests for session management performance."""

    def test_session_creation_performance(self, mock_config, mock_logger, temp_project_dir):
        """Session creation should be fast."""
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

                    start = time.time()
                    for _ in range(10):
                        session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)
                    elapsed = time.time() - start

        assert elapsed < 2.0, f"10 session creations took {elapsed:.2f}s, should be < 2 seconds"

    def test_session_retrieval_performance(self, mock_config, mock_logger, temp_project_dir):
        """Session retrieval should be fast."""
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

                    # Create a session first
                    session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)
                    session_id = session.session_id

                    # Time retrieval
                    start = time.time()
                    for _ in range(100):
                        retrieved = orchestrator.get_session(session_id)
                    elapsed = time.time() - start

        assert elapsed < 1.0, f"100 retrievals took {elapsed:.3f}s, should be < 1 second"

    def test_session_listing_performance(self, mock_config, mock_logger, temp_project_dir):
        """Session listing should scale reasonably."""
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

                    # Create 20 sessions
                    for _ in range(20):
                        orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    # Time listing
                    start = time.time()
                    for _ in range(100):
                        sessions = orchestrator.list_sessions(limit=20)
                    elapsed = time.time() - start

        assert len(sessions) == 20
        assert elapsed < 1.0, f"100 listings took {elapsed:.3f}s, should be < 1 second"


# =============================================================================
# TEST: RESULT AGGREGATION PERFORMANCE
# =============================================================================


class TestResultAggregationPerformance:
    """Tests for result aggregation performance."""

    def test_result_aggregation_small(self, mock_config, mock_logger, temp_project_dir):
        """Small result aggregation should be instant."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(mock_config, mock_logger)

        agent_results = {
            "behavioral": {
                "tests_run": 10,
                "tests_passed": 8,
                "tests_failed": 2,
                "findings": [],
            }
        }

        start = time.time()
        for _ in range(1000):
            result = orchestrator._aggregate_results(agent_results)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"1000 aggregations took {elapsed:.3f}s, should be < 0.5 second"

    def test_result_aggregation_many_findings(self, mock_config, mock_logger, temp_project_dir):
        """Result aggregation with many findings should be reasonable."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Create 100 findings
        findings = [
            QAFinding(
                finding_id=f"BT-{i:03d}",
                severity="minor" if i % 3 == 0 else ("moderate" if i % 3 == 1 else "critical"),
                category="behavioral",
                endpoint=f"GET /api/resource{i}",
                test_type="happy_path",
                title=f"Finding {i}",
                description=f"Test description {i}",
                expected={"status": 200},
                actual={"status": 500},
                evidence={"request": f"test {i}"},
                recommendation=f"Fix {i}",
            )
            for i in range(100)
        ]

        agent_results = {
            "behavioral": {
                "tests_run": 100,
                "tests_passed": 0,
                "tests_failed": 100,
                "findings": findings,
            }
        }

        start = time.time()
        for _ in range(100):
            result = orchestrator._aggregate_results(agent_results)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"100 aggregations (100 findings each) took {elapsed:.3f}s, should be < 1 second"
        assert len(result.findings) == 100


# =============================================================================
# TEST: MODEL SERIALIZATION PERFORMANCE
# =============================================================================


class TestModelSerializationPerformance:
    """Tests for model serialization performance."""

    def test_qa_session_serialization_performance(self):
        """QASession serialization should be fast."""
        context = QAContext(
            base_url="http://localhost:8000",
            target_endpoints=[
                QAEndpoint(method="GET", path=f"/api/resource{i}")
                for i in range(50)
            ],
        )
        result = QAResult(
            tests_run=100,
            tests_passed=90,
            tests_failed=10,
        )
        session = QASession(
            session_id="qa-20241226-120000",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=context,
            result=result,
        )

        start = time.time()
        for _ in range(1000):
            data = session.to_dict()
        elapsed = time.time() - start

        assert elapsed < 0.5, f"1000 serializations took {elapsed:.3f}s, should be < 0.5 second"

    def test_qa_session_deserialization_performance(self):
        """QASession deserialization should be fast."""
        data = {
            "session_id": "qa-20241226-120000",
            "trigger": "user_command",
            "depth": "standard",
            "status": "completed",
            "context": {
                "base_url": "http://localhost:8000",
                "target_files": [],
                "target_endpoints": [
                    {"method": "GET", "path": f"/api/resource{i}"}
                    for i in range(50)
                ],
            },
            "result": {
                "tests_run": 100,
                "tests_passed": 90,
                "tests_failed": 10,
                "findings": [],
                "recommendation": "pass",
            },
        }

        start = time.time()
        for _ in range(1000):
            session = QASession.from_dict(data)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"1000 deserializations took {elapsed:.3f}s, should be < 0.5 second"

    def test_qa_finding_serialization_performance(self):
        """QAFinding serialization should be fast."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error",
            description="Test description " * 50,
            expected={"status": 200, "body": {"items": list(range(100))}},
            actual={"status": 500, "body": {"error": "Internal error"}},
            evidence={"request": "curl http://localhost/api/users", "response": "{}"},
            recommendation="Fix the bug " * 10,
        )

        start = time.time()
        for _ in range(10000):
            data = finding.to_dict()
        elapsed = time.time() - start

        assert elapsed < 0.5, f"10000 serializations took {elapsed:.3f}s, should be < 0.5 second"


# =============================================================================
# TEST: ENDPOINT LIMITING PERFORMANCE
# =============================================================================


class TestEndpointLimitingPerformance:
    """Tests for endpoint limiting performance."""

    def test_limit_endpoints_performance(self, mock_config, mock_logger, temp_project_dir):
        """Endpoint limiting should be fast even with many endpoints."""
        mock_config.repo_root = str(temp_project_dir)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent"):
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent"):
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent"):
                    orchestrator = QAOrchestrator(mock_config, mock_logger)

        # Create 1000 endpoints
        endpoints = [
            QAEndpoint(method="GET", path=f"/api/resource{i}")
            for i in range(1000)
        ]

        start = time.time()
        for _ in range(1000):
            limited = orchestrator._limit_endpoints(endpoints, QADepth.STANDARD)
        elapsed = time.time() - start

        assert elapsed < 0.1, f"1000 limits took {elapsed:.3f}s, should be < 0.1 second"


# =============================================================================
# TEST: MEMORY EFFICIENCY
# =============================================================================


class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    def test_session_cleanup(self, mock_config, mock_logger, temp_project_dir):
        """Creating many sessions should not leak memory significantly."""
        mock_config.repo_root = str(temp_project_dir)

        # Create and discard many sessions to check for obvious memory issues
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

                    # Create many sessions
                    for _ in range(50):
                        session = orchestrator.test(target="/api/users", depth=QADepth.SHALLOW)

                    # Should be able to list them all
                    sessions = orchestrator.list_sessions(limit=50)
                    assert len(sessions) == 50

    def test_large_findings_list(self):
        """Processing large findings lists should be efficient."""
        # Create 500 findings
        findings = [
            QAFinding(
                finding_id=f"BT-{i:03d}",
                severity="minor",
                category="behavioral",
                endpoint=f"GET /api/resource{i}",
                test_type="happy_path",
                title=f"Finding {i}",
                description=f"Test description {i}",
                expected={"status": 200},
                actual={"status": 404},
                evidence={"request": f"test {i}"},
                recommendation=f"Fix {i}",
            )
            for i in range(500)
        ]

        result = QAResult(
            tests_run=500,
            tests_passed=0,
            tests_failed=500,
            findings=findings,
        )

        # Serialize and check size is reasonable
        data = result.to_dict()
        assert len(data["findings"]) == 500


# =============================================================================
# TEST: CONCURRENT OPERATIONS
# =============================================================================


class TestConcurrentOperations:
    """Tests for concurrent operation performance."""

    def test_multiple_context_builders(self, mock_config, mock_logger):
        """Multiple context builders should work efficiently."""
        builders = [QAContextBuilder(mock_config, mock_logger) for _ in range(10)]

        start = time.time()
        for builder in builders:
            for _ in range(100):
                context = builder.build_context(
                    trigger=QATrigger.USER_COMMAND,
                    target="/api/users",
                )
        elapsed = time.time() - start

        assert elapsed < 2.0, f"1000 context builds (10 builders) took {elapsed:.2f}s, should be < 2 seconds"

    def test_multiple_depth_selectors(self, mock_config, mock_logger):
        """Multiple depth selectors should work efficiently."""
        selectors = [DepthSelector(mock_config, mock_logger) for _ in range(10)]
        context = QAContext()

        start = time.time()
        for selector in selectors:
            for _ in range(100):
                depth = selector.select_depth(
                    trigger=QATrigger.USER_COMMAND,
                    context=context,
                )
        elapsed = time.time() - start

        assert elapsed < 1.0, f"1000 selections (10 selectors) took {elapsed:.3f}s, should be < 1 second"


# =============================================================================
# TEST: ESTIMATED COSTS/TIMES
# =============================================================================


class TestEstimatedCostsAndTimes:
    """Tests for estimated costs and times accuracy."""

    def test_estimated_costs_exist_for_all_depths(self, mock_config, mock_logger):
        """All depth levels should have estimated costs."""
        selector = DepthSelector(mock_config, mock_logger)

        for depth in QADepth:
            cost = selector.get_estimated_cost(depth)
            assert cost > 0, f"Depth {depth} should have positive cost"
            assert cost < 10.0, f"Depth {depth} cost should be reasonable"

    def test_estimated_times_exist_for_all_depths(self, mock_config, mock_logger):
        """All depth levels should have estimated times."""
        selector = DepthSelector(mock_config, mock_logger)

        for depth in QADepth:
            time_mins = selector.get_estimated_time(depth)
            assert time_mins > 0, f"Depth {depth} should have positive time"
            assert time_mins < 60.0, f"Depth {depth} time should be reasonable"

    def test_deeper_depths_cost_more(self, mock_config, mock_logger):
        """Deeper depths should generally cost more."""
        selector = DepthSelector(mock_config, mock_logger)

        shallow_cost = selector.get_estimated_cost(QADepth.SHALLOW)
        standard_cost = selector.get_estimated_cost(QADepth.STANDARD)
        deep_cost = selector.get_estimated_cost(QADepth.DEEP)

        assert shallow_cost < standard_cost
        assert standard_cost < deep_cost

    def test_deeper_depths_take_longer(self, mock_config, mock_logger):
        """Deeper depths should generally take longer."""
        selector = DepthSelector(mock_config, mock_logger)

        shallow_time = selector.get_estimated_time(QADepth.SHALLOW)
        standard_time = selector.get_estimated_time(QADepth.STANDARD)
        deep_time = selector.get_estimated_time(QADepth.DEEP)

        assert shallow_time < standard_time
        assert standard_time < deep_time
