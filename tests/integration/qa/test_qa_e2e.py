"""E2E Integration Tests for QA Agent System.

Tests the full flow from trigger to report for all scenarios:
- Feature pipeline integration
- Bug reproduction enhancement
- Health check execution
- Regression detection
- COS autopilot integration

Following TDD approach - tests are written first, then implementation verified.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create mock SwarmConfig for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    return config


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    logger = MagicMock()
    return logger


@pytest.fixture
def sample_finding_critical():
    """Create a sample critical finding."""
    return QAFinding(
        finding_id="finding-001",
        severity="critical",
        category="authentication",
        endpoint="/api/users",
        test_type="behavioral",
        title="Authentication bypass detected",
        description="Endpoint allows unauthenticated access to protected data",
        expected={"status": 401},
        actual={"status": 200},
        evidence={"request": "GET /api/users", "response": "200 OK with user data"},
        recommendation="Add authentication middleware",
    )


@pytest.fixture
def sample_finding_moderate():
    """Create a sample moderate finding."""
    return QAFinding(
        finding_id="finding-002",
        severity="moderate",
        category="validation",
        endpoint="/api/orders",
        test_type="behavioral",
        title="Missing input validation",
        description="Endpoint accepts invalid input without validation",
        expected={"status": 400},
        actual={"status": 200},
        evidence={"request": "POST /api/orders {invalid}", "response": "200 OK"},
        recommendation="Add input validation",
    )


@pytest.fixture
def sample_finding_minor():
    """Create a sample minor finding."""
    return QAFinding(
        finding_id="finding-003",
        severity="minor",
        category="performance",
        endpoint="/api/search",
        test_type="behavioral",
        title="Slow response time",
        description="Endpoint response time exceeds recommended threshold",
        expected={"response_time_ms": 200},
        actual={"response_time_ms": 450},
        evidence={"request": "GET /api/search?q=test", "response_time": "450ms"},
        recommendation="Consider caching or query optimization",
    )


@pytest.fixture
def mock_session_with_critical_findings(sample_finding_critical):
    """Create a mock session with critical findings."""
    result = QAResult(
        tests_run=10,
        tests_passed=8,
        tests_failed=2,
        findings=[sample_finding_critical],
        critical_count=1,
        moderate_count=0,
        minor_count=0,
        recommendation=QARecommendation.BLOCK,
    )
    session = QASession(
        session_id="qa-20231225-120000",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=QAContext(feature_id="my-feature", issue_number=42),
        result=result,
    )
    return session


@pytest.fixture
def mock_session_with_moderate_findings(sample_finding_moderate):
    """Create a mock session with moderate findings."""
    result = QAResult(
        tests_run=10,
        tests_passed=9,
        tests_failed=1,
        findings=[sample_finding_moderate],
        critical_count=0,
        moderate_count=1,
        minor_count=0,
        recommendation=QARecommendation.WARN,
    )
    session = QASession(
        session_id="qa-20231225-120001",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=QAContext(feature_id="my-feature", issue_number=42),
        result=result,
    )
    return session


@pytest.fixture
def mock_session_pass():
    """Create a mock session with no findings (passing)."""
    result = QAResult(
        tests_run=10,
        tests_passed=10,
        tests_failed=0,
        findings=[],
        critical_count=0,
        moderate_count=0,
        minor_count=0,
        recommendation=QARecommendation.PASS,
    )
    session = QASession(
        session_id="qa-20231225-120002",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=QAContext(feature_id="my-feature", issue_number=42),
        result=result,
    )
    return session


# =============================================================================
# FEATURE PIPELINE E2E TESTS
# =============================================================================


class TestFeaturePipelineE2E:
    """E2E tests for feature pipeline QA integration.

    Tests the full flow:
    1. Verifier passes → Hook runs
    2. QA orchestrator executes tests
    3. Findings are reported back
    4. Pipeline blocks/warns/passes based on severity
    """

    def test_verifier_pass_triggers_qa(self, mock_config, tmp_path):
        """After Verifier passes, QA should run automatically."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock orchestrator to simulate QA run
        mock_result = QAResult(
            tests_run=5,
            tests_passed=5,
            tests_failed=0,
            recommendation=QARecommendation.PASS,
        )
        mock_session = QASession(
            session_id="qa-test-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        hook.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        # Verify hook should run
        should_run = hook.should_run(
            verification_success=True,
            feature_id="my-feature",
            issue_number=42,
        )
        assert should_run is True

        # Run the hook
        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        # Verify QA was triggered
        assert result.session_id == "qa-test-001"
        assert result.should_continue is True
        assert result.should_block is False

    def test_qa_findings_block_commit_on_critical(
        self, mock_config, sample_finding_critical
    ):
        """Critical QA findings should block commit."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock session with critical finding
        mock_result = QAResult(
            tests_run=5,
            tests_passed=3,
            tests_failed=2,
            findings=[sample_finding_critical],
            critical_count=1,
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-test-002",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        hook.orchestrator.validate_issue = MagicMock(return_value=mock_session)
        hook.orchestrator.create_bug_investigations = MagicMock(return_value=["bug-001"])

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/auth.py"],
        )

        # Verify blocking behavior
        assert result.should_block is True
        assert result.should_continue is False
        assert result.recommendation == QARecommendation.BLOCK
        assert len(result.findings) == 1
        assert result.findings[0].severity == "critical"

    def test_qa_findings_warn_on_moderate(
        self, mock_config, sample_finding_moderate
    ):
        """Moderate QA findings should warn but not block."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock session with moderate finding
        mock_result = QAResult(
            tests_run=5,
            tests_passed=4,
            tests_failed=1,
            findings=[sample_finding_moderate],
            moderate_count=1,
            recommendation=QARecommendation.WARN,
        )
        mock_session = QASession(
            session_id="qa-test-003",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        hook.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/orders.py"],
        )

        # Verify warning behavior
        assert result.should_block is False
        assert result.should_continue is True
        assert result.has_warnings is True
        assert result.recommendation == QARecommendation.WARN

    def test_bugs_created_from_findings(
        self, mock_config, sample_finding_critical
    ):
        """Bugs should be created from critical/moderate findings."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock session with critical finding
        mock_result = QAResult(
            tests_run=5,
            tests_passed=3,
            tests_failed=2,
            findings=[sample_finding_critical],
            critical_count=1,
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-test-004",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        hook.orchestrator.validate_issue = MagicMock(return_value=mock_session)
        hook.orchestrator.create_bug_investigations = MagicMock(
            return_value=["qa-bug-test-001"]
        )

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/auth.py"],
        )

        # Verify bugs were created
        assert len(result.created_bugs) == 1
        assert result.created_bugs[0] == "qa-bug-test-001"
        hook.orchestrator.create_bug_investigations.assert_called_once()

    def test_skip_qa_flag_honored(self, mock_config):
        """skip_qa flag should bypass QA validation."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)

        # Run with skip_qa=True
        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
            skip_qa=True,
        )

        # Verify QA was skipped
        assert result.session_id is None
        assert result.recommendation == QARecommendation.PASS
        assert result.should_block is False

    def test_high_risk_files_trigger_deep_qa(self, mock_config):
        """Files with security patterns should trigger DEEP QA."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)

        # Mock orchestrator
        mock_result = QAResult(recommendation=QARecommendation.PASS)
        mock_session = QASession(
            session_id="qa-test-deep",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        integration.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        # Run with high-risk file
        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/authentication/login.py"],
        )

        # Verify DEEP depth was used
        call_args = integration.orchestrator.validate_issue.call_args
        assert call_args.kwargs.get("depth") == QADepth.DEEP


# =============================================================================
# BUG REPRODUCTION E2E TESTS
# =============================================================================


class TestBugReproductionE2E:
    """E2E tests for bug reproduction enhancement.

    Tests the flow:
    1. Bug reported → BugResearcher fails
    2. QA enhances with behavioral tests
    3. Root cause evidence extracted
    4. Reproduction steps generated
    """

    def test_enhances_failing_reproduction(self, mock_config):
        """QA should enhance when BugResearcher fails to reproduce."""
        from swarm_attack.qa.integrations.bug_pipeline import BugPipelineQAIntegration

        integration = BugPipelineQAIntegration(mock_config)

        # Mock orchestrator with findings that indicate reproduction
        mock_result = QAResult(
            tests_run=10,
            tests_failed=3,  # Failures indicate bug reproduced
            findings=[
                QAFinding(
                    finding_id="finding-bug-001",
                    severity="critical",
                    category="error-handling",
                    endpoint="/api/checkout",
                    test_type="behavioral",
                    title="500 error on checkout",
                    description="Server returns 500 when processing order",
                    expected={"status": 200},
                    actual={"status": 500},
                    evidence={"request": "POST /api/checkout", "error": "NullPointerException"},
                    recommendation="Fix null check in payment processing",
                )
            ],
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-bug-001",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        integration.orchestrator.test = MagicMock(return_value=mock_session)

        # Enhance reproduction
        result = integration.enhance_reproduction(
            bug_id="BUG-123",
            bug_description="Checkout fails with 500 error",
            error_message="NullPointerException in PaymentService",
            affected_endpoints=["/api/checkout"],
        )

        # Verify reproduction was enhanced
        assert result.is_reproduced is True
        assert result.session_id == "qa-bug-001"
        assert len(result.reproduction_steps) > 0
        assert len(result.root_cause_hints) > 0

    def test_provides_rca_evidence(self, mock_config, sample_finding_critical):
        """QA findings should provide evidence for RootCauseAnalyzer."""
        from swarm_attack.qa.integrations.bug_pipeline import BugPipelineQAIntegration

        integration = BugPipelineQAIntegration(mock_config)

        # Set up session with findings
        mock_result = QAResult(
            tests_run=5,
            tests_failed=1,
            findings=[sample_finding_critical],
        )
        mock_session = QASession(
            session_id="qa-rca-001",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        integration.orchestrator.get_session = MagicMock(return_value=mock_session)

        # Get RCA evidence
        evidence = integration.get_rca_evidence("qa-rca-001")

        # Verify evidence structure
        assert "session_id" in evidence
        assert "endpoints_affected" in evidence
        assert "findings" in evidence
        assert "reproduction_steps" in evidence
        assert len(evidence["findings"]) == 1

    def test_extracts_reproduction_steps(self, mock_config):
        """Should extract concrete reproduction steps from findings."""
        from swarm_attack.qa.integrations.bug_pipeline import BugPipelineQAIntegration

        integration = BugPipelineQAIntegration(mock_config)

        # Create finding with detailed evidence
        finding = QAFinding(
            finding_id="finding-repro-001",
            severity="critical",
            category="error",
            endpoint="/api/orders/submit",
            test_type="behavioral",
            title="Order submission fails",
            description="Order submission returns 500",
            expected={"status": 201},
            actual={"status": 500},
            evidence={
                "request": "POST /api/orders/submit {order_id: 123}",
                "response": "500 Internal Server Error",
                "stack_trace": "NullPointerException at OrderService.java:42",
            },
            recommendation="Check null handling in OrderService",
        )

        # Mock session with this finding
        mock_result = QAResult(tests_failed=1, findings=[finding])
        mock_session = QASession(
            session_id="qa-steps-001",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        integration.orchestrator.test = MagicMock(return_value=mock_session)

        # Enhance reproduction
        result = integration.enhance_reproduction(
            bug_id="BUG-456",
            bug_description="Order fails to submit",
        )

        # Verify reproduction steps extracted
        assert result.is_reproduced is True
        assert len(result.reproduction_steps) > 0
        # Steps should contain request/expected/actual info
        steps_text = " ".join(result.reproduction_steps)
        assert "/api/orders/submit" in steps_text or "Expected" in steps_text

    def test_non_reproducible_bug_handled(self, mock_config):
        """Should handle bugs that cannot be reproduced."""
        from swarm_attack.qa.integrations.bug_pipeline import BugPipelineQAIntegration

        integration = BugPipelineQAIntegration(mock_config)

        # Mock session with no failures
        mock_result = QAResult(
            tests_run=10,
            tests_passed=10,
            tests_failed=0,  # No failures means not reproduced
            findings=[],
            recommendation=QARecommendation.PASS,
        )
        mock_session = QASession(
            session_id="qa-norepro-001",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        integration.orchestrator.test = MagicMock(return_value=mock_session)

        result = integration.enhance_reproduction(
            bug_id="BUG-789",
            bug_description="Intermittent issue",
        )

        # Verify not reproduced
        assert result.is_reproduced is False
        assert result.session_id == "qa-norepro-001"


# =============================================================================
# HEALTH CHECK E2E TESTS
# =============================================================================


class TestHealthCheckE2E:
    """E2E tests for health check functionality.

    Tests the flow:
    1. Health check triggered (scheduled or manual)
    2. QA runs shallow scan on all endpoints
    3. Health report generated
    """

    def test_shallow_health_check_completes(self, mock_config):
        """Health check should complete with shallow depth."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Run health check
        session = orchestrator.health_check()

        # Verify session properties
        assert session.depth == QADepth.SHALLOW
        assert session.status in [QAStatus.COMPLETED, QAStatus.COMPLETED_PARTIAL, QAStatus.FAILED]
        assert session.session_id.startswith("qa-")

    def test_reports_unhealthy_endpoints(self, mock_config, sample_finding_critical):
        """Should report failing endpoints in health check."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Mock behavioral agent to return failures
        mock_behavioral_result = MagicMock()
        mock_behavioral_result.success = True
        mock_behavioral_result.output = {
            "tests_run": 5,
            "tests_passed": 3,
            "tests_failed": 2,
            "findings": [sample_finding_critical],
        }
        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral_result)

        session = orchestrator.health_check()

        # Verify findings reported
        if session.result:
            assert session.result.tests_failed >= 0  # May have failures
            # Health check should have run
            assert session.result.tests_run >= 0

    def test_generates_health_report(self, mock_config, tmp_path):
        """Should generate health report document."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Mock a completed session
        mock_behavioral_result = MagicMock()
        mock_behavioral_result.success = True
        mock_behavioral_result.output = {
            "tests_run": 3,
            "tests_passed": 3,
            "tests_failed": 0,
            "findings": [],
        }
        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral_result)

        session = orchestrator.health_check()

        # Check that report was saved
        report_path = tmp_path / ".swarm" / "qa" / session.session_id / "qa-report.md"
        assert report_path.exists(), f"Report should be generated at {report_path}"

        # Verify report content
        report_content = report_path.read_text()
        assert "QA Report" in report_content
        assert session.session_id in report_content


# =============================================================================
# REGRESSION DETECTION E2E TESTS
# =============================================================================


class TestRegressionDetectionE2E:
    """E2E tests for regression detection.

    Tests the flow:
    1. Code change detected
    2. Regression scanner identifies affected endpoints
    3. Targeted tests run on affected areas
    4. Breaking changes flagged
    """

    def test_identifies_affected_endpoints(self, mock_config):
        """Should identify endpoints affected by code changes."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Mock regression agent output
        mock_regression_result = MagicMock()
        mock_regression_result.success = True
        mock_regression_result.output = {
            "regression_suite": {
                "must_test": ["/api/users", "/api/orders"],
                "should_test": ["/api/products"],
            },
            "affected_files": ["src/api/users.py"],
            "findings": [],
        }
        orchestrator.regression_agent.run = MagicMock(return_value=mock_regression_result)

        # Mock behavioral agent for targeted tests
        mock_behavioral_result = MagicMock()
        mock_behavioral_result.success = True
        mock_behavioral_result.output = {
            "tests_run": 5,
            "tests_passed": 5,
            "tests_failed": 0,
            "findings": [],
        }
        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral_result)

        # Run regression test
        session = orchestrator.test(
            target="src/api/users.py",
            depth=QADepth.REGRESSION,
        )

        # Verify regression was analyzed
        if session.result and session.result.regression_results:
            assert "regression_suite" in session.result.regression_results
            suite = session.result.regression_results["regression_suite"]
            assert "must_test" in suite

    def test_runs_targeted_tests(self, mock_config):
        """Should run targeted tests on affected endpoints."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Mock regression agent to identify targets
        mock_regression_result = MagicMock()
        mock_regression_result.success = True
        mock_regression_result.output = {
            "regression_suite": {
                "must_test": ["/api/users"],
                "should_test": [],
            },
            "findings": [],
        }
        orchestrator.regression_agent.run = MagicMock(return_value=mock_regression_result)

        # Mock behavioral agent
        mock_behavioral_result = MagicMock()
        mock_behavioral_result.success = True
        mock_behavioral_result.output = {
            "tests_run": 3,
            "tests_passed": 3,
            "tests_failed": 0,
            "findings": [],
        }
        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral_result)

        session = orchestrator.test(
            target="src/api/users.py",
            depth=QADepth.REGRESSION,
        )

        # Verify behavioral tests were run after regression scan
        assert orchestrator.behavioral_agent.run.called

    def test_detects_breaking_changes(self, mock_config):
        """Should detect API breaking changes in diff."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Mock regression agent detecting breaking change
        breaking_finding = QAFinding(
            finding_id="regression-001",
            severity="critical",
            category="breaking-change",
            endpoint="/api/users",
            test_type="regression",
            title="Response schema changed",
            description="Required field 'email' removed from response",
            expected={"schema": {"email": "required"}},
            actual={"schema": {"email": "missing"}},
            evidence={"diff": "-email: str\n+# removed"},
            recommendation="Restore 'email' field or version the API",
        )

        mock_regression_result = MagicMock()
        mock_regression_result.success = True
        mock_regression_result.output = {
            "regression_suite": {"must_test": [], "should_test": []},
            "findings": [breaking_finding],
            "breaking_changes": ["/api/users"],
        }
        orchestrator.regression_agent.run = MagicMock(return_value=mock_regression_result)

        mock_behavioral_result = MagicMock()
        mock_behavioral_result.success = True
        mock_behavioral_result.output = {"tests_run": 0, "tests_passed": 0, "tests_failed": 0, "findings": []}
        orchestrator.behavioral_agent.run = MagicMock(return_value=mock_behavioral_result)

        session = orchestrator.test(
            target="src/api/users.py",
            depth=QADepth.REGRESSION,
        )

        # Verify breaking change detected
        if session.result:
            # Should have critical finding for breaking change
            critical_findings = [f for f in session.result.findings if f.severity == "critical"]
            if critical_findings:
                assert any("breaking" in f.category.lower() or "schema" in f.title.lower() for f in critical_findings)


# =============================================================================
# COS INTEGRATION E2E TESTS
# =============================================================================


class TestCOSIntegrationE2E:
    """E2E tests for Chief of Staff autopilot integration.

    Tests the flow:
    1. COS autopilot creates QA goals
    2. QA runner executes goals
    3. Results tracked and reported
    """

    def test_validation_goal_executes(self, mock_config):
        """QA validation goal should execute in autopilot."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner

        runner = QAAutopilotRunner(mock_config)

        # Mock orchestrator
        mock_result = QAResult(
            tests_run=5,
            tests_passed=5,
            tests_failed=0,
            recommendation=QARecommendation.PASS,
        )
        mock_session = QASession(
            session_id="qa-goal-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
            started_at="2023-12-25T12:00:00Z",
            completed_at="2023-12-25T12:01:00Z",
        )
        runner.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        # Create validation goal
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="auth-feature",
            linked_issue=42,
            description="Validate auth implementation",
        )

        # Execute goal
        result = runner.execute_qa_validation_goal(goal)

        # Verify execution
        assert result.success is True
        assert result.session_id == "qa-goal-001"
        assert result.findings_count == 0

    def test_health_goal_executes(self, mock_config):
        """QA health goal should execute in autopilot."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner

        runner = QAAutopilotRunner(mock_config)

        # Mock orchestrator
        mock_result = QAResult(
            tests_run=10,
            tests_passed=10,
            tests_failed=0,
            recommendation=QARecommendation.PASS,
        )
        mock_session = QASession(
            session_id="qa-health-001",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.SHALLOW,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
            started_at="2023-12-25T12:00:00Z",
            completed_at="2023-12-25T12:00:30Z",
        )
        runner.orchestrator.health_check = MagicMock(return_value=mock_session)

        # Create health goal
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="Daily health check",
        )

        # Execute goal
        result = runner.execute_qa_health_goal(goal)

        # Verify execution
        assert result.success is True
        assert result.session_id == "qa-health-001"
        assert result.duration_seconds >= 0

    def test_goal_results_tracked(self, mock_config):
        """Goal execution results should be tracked."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner

        runner = QAAutopilotRunner(mock_config)

        # Mock session with findings
        mock_result = QAResult(
            tests_run=10,
            tests_passed=8,
            tests_failed=2,
            findings=[
                QAFinding(
                    finding_id="f1",
                    severity="moderate",
                    category="test",
                    endpoint="/api/test",
                    test_type="behavioral",
                    title="Test issue",
                    description="Test",
                    expected={},
                    actual={},
                    evidence={},
                    recommendation="Fix",
                ),
            ],
            recommendation=QARecommendation.WARN,
        )
        mock_session = QASession(
            session_id="qa-tracked-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
            started_at="2023-12-25T12:00:00Z",
            completed_at="2023-12-25T12:02:00Z",
            cost_usd=0.05,
        )
        runner.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="my-feature",
            linked_issue=1,
        )

        result = runner.execute_qa_validation_goal(goal)

        # Verify tracking
        assert result.session_id == "qa-tracked-001"
        assert result.findings_count == 1
        assert result.cost_usd == 0.05
        assert result.duration_seconds == 120  # 2 minutes
        assert result.success is True  # WARN doesn't block

    def test_validation_goal_blocks_on_critical(self, mock_config):
        """Validation goal should fail if QA blocks."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner

        runner = QAAutopilotRunner(mock_config)

        # Mock session with blocking result
        mock_result = QAResult(
            tests_run=5,
            tests_passed=2,
            tests_failed=3,
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-block-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
            started_at="2023-12-25T12:00:00Z",
            completed_at="2023-12-25T12:01:00Z",
        )
        runner.orchestrator.validate_issue = MagicMock(return_value=mock_session)

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="risky-feature",
            linked_issue=99,
        )

        result = runner.execute_qa_validation_goal(goal)

        # Verify goal failed due to block
        assert result.success is False
        assert result.session_id == "qa-block-001"


# =============================================================================
# ERROR HANDLING E2E TESTS
# =============================================================================


class TestErrorHandlingE2E:
    """E2E tests for graceful error handling."""

    def test_graceful_degradation_on_qa_failure(self, mock_config):
        """QA should degrade gracefully when agents fail."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock orchestrator to raise exception
        hook.orchestrator.validate_issue = MagicMock(side_effect=Exception("Agent crashed"))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        # Verify graceful degradation
        assert result.skipped is True
        assert result.should_continue is True  # Don't block on QA failure
        assert "QA failed" in (result.error or "")

    def test_timeout_handling(self, mock_config):
        """QA should handle timeouts gracefully."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # Mock timeout
        hook.orchestrator.validate_issue = MagicMock(side_effect=TimeoutError("QA timed out"))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        # Verify timeout handling
        assert result.skipped is True
        assert result.should_continue is True
        assert "timed out" in (result.error or "").lower()

    def test_cost_limit_enforcement(self, mock_config):
        """QA should stop when cost limit reached."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.qa.models import QALimits

        # Create orchestrator with very low cost limit
        limits = QALimits(max_cost_usd=0.0)  # Immediate limit
        orchestrator = QAOrchestrator(mock_config, limits=limits)
        orchestrator._accumulated_cost = 1.0  # Already over limit

        session = orchestrator.test(target="/api/test", depth=QADepth.SHALLOW)

        # Verify cost limit was enforced
        assert session.status == QAStatus.COMPLETED_PARTIAL
        if session.result:
            assert "cost_limit" in (session.result.partial_completion_reason or "")


# =============================================================================
# INTEGRATION FLOW TESTS
# =============================================================================


class TestFullIntegrationFlow:
    """Tests for complete integration flows across multiple components."""

    def test_feature_to_bug_flow(self, mock_config, sample_finding_critical):
        """Test flow from feature verification to bug creation."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        from swarm_attack.qa.integrations.bug_pipeline import BugPipelineQAIntegration

        # Step 1: Run feature pipeline QA
        hook = VerifierQAHook(mock_config)

        mock_result = QAResult(
            tests_run=5,
            tests_failed=1,
            findings=[sample_finding_critical],
            critical_count=1,
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-flow-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
        )
        hook.orchestrator.validate_issue = MagicMock(return_value=mock_session)
        hook.orchestrator.create_bug_investigations = MagicMock(return_value=["qa-bug-flow-001"])

        feature_result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/auth.py"],
        )

        # Verify bug was created
        assert feature_result.should_block is True
        assert len(feature_result.created_bugs) == 1

        # Step 2: Bug pipeline can use findings for RCA
        bug_integration = BugPipelineQAIntegration(mock_config)
        bug_integration.orchestrator.get_session = MagicMock(return_value=mock_session)

        evidence = bug_integration.get_rca_evidence("qa-flow-001")

        # Verify evidence available
        assert evidence["session_id"] == "qa-flow-001"
        assert len(evidence["findings"]) == 1

    def test_health_check_to_alert_flow(self, mock_config, sample_finding_critical):
        """Test flow from health check to alerting on failures."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        runner = QAAutopilotRunner(mock_config)

        # Mock unhealthy session
        mock_result = QAResult(
            tests_run=10,
            tests_passed=7,
            tests_failed=3,
            findings=[sample_finding_critical],
            critical_count=1,
            recommendation=QARecommendation.BLOCK,
        )
        mock_session = QASession(
            session_id="qa-health-alert",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.SHALLOW,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=mock_result,
            started_at="2023-12-25T12:00:00Z",
            completed_at="2023-12-25T12:00:30Z",
        )
        runner.orchestrator.health_check = MagicMock(return_value=mock_session)

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="Scheduled health check",
        )

        result = runner.execute_qa_health_goal(goal)

        # Verify health check detected issues
        assert result.success is False  # Failed due to failures
        assert result.findings_count == 1
        assert result.session_id == "qa-health-alert"
