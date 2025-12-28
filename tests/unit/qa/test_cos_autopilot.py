"""Tests for Chief of Staff Autopilot QA Runner following TDD approach.

Tests cover spec section 5.2.4:
- Execute QA validation goals in autopilot
- Execute health check goals (shallow depth)
- Track QA sessions linked to goals
- Return success/failure with metrics
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import fields

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAFinding,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)
from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify COS Autopilot can be imported."""

    def test_can_import_qa_autopilot_runner(self):
        """Should be able to import QAAutopilotRunner class."""
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        assert QAAutopilotRunner is not None

    def test_can_import_goal_execution_result(self):
        """Should be able to import GoalExecutionResult dataclass."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        assert GoalExecutionResult is not None


# =============================================================================
# GoalExecutionResult DATACLASS TESTS
# =============================================================================


class TestGoalExecutionResult:
    """Tests for GoalExecutionResult dataclass."""

    def test_has_success_field(self):
        """GoalExecutionResult should have success field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "success")
        assert isinstance(result.success, bool)

    def test_has_session_id_field(self):
        """GoalExecutionResult should have session_id field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "session_id")

    def test_has_cost_usd_field(self):
        """GoalExecutionResult should have cost_usd field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "cost_usd")

    def test_has_duration_seconds_field(self):
        """GoalExecutionResult should have duration_seconds field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "duration_seconds")

    def test_has_findings_count_field(self):
        """GoalExecutionResult should have findings_count field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "findings_count")

    def test_has_error_field(self):
        """GoalExecutionResult should have error field."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert hasattr(result, "error")

    def test_defaults_are_sensible(self):
        """GoalExecutionResult should have sensible defaults."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult
        result = GoalExecutionResult()
        assert result.success is False
        assert result.session_id is None
        assert result.cost_usd == 0.0
        assert result.duration_seconds == 0
        assert result.findings_count == 0
        assert result.error is None


# =============================================================================
# QAAutopilotRunner INITIALIZATION TESTS
# =============================================================================


class TestQAAutopilotRunnerInit:
    """Tests for QAAutopilotRunner initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        runner = QAAutopilotRunner(mock_config)
        assert runner.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        logger = MagicMock()
        runner = QAAutopilotRunner(mock_config, logger=logger)
        assert runner._logger == logger

    def test_init_creates_orchestrator(self, mock_config):
        """Should create QAOrchestrator instance."""
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        runner = QAAutopilotRunner(mock_config)
        assert hasattr(runner, "orchestrator")
        assert runner.orchestrator is not None


# =============================================================================
# execute_qa_validation_goal() TESTS
# =============================================================================


class TestExecuteQAValidationGoal:
    """Tests for execute_qa_validation_goal() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def runner(self, mock_config):
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        return QAAutopilotRunner(mock_config)

    def test_returns_goal_execution_result(self, runner):
        """Should return GoalExecutionResult."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test-feature",
            linked_issue=42,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.15
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                findings=[],
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert isinstance(result, GoalExecutionResult)

    def test_calls_validate_issue_with_feature_and_issue(self, runner):
        """Should call validate_issue with linked feature and issue."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="user-auth",
            linked_issue=123,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            runner.execute_qa_validation_goal(goal)

            mock_validate.assert_called_once()
            call_args = mock_validate.call_args
            assert call_args.kwargs.get("feature_id") == "user-auth" or call_args[0][0] == "user-auth"
            assert call_args.kwargs.get("issue_number") == 123 or (len(call_args[0]) >= 2 and call_args[0][1] == 123)

    def test_falls_back_to_test_when_no_feature_issue(self, runner):
        """Should fall back to test() when no feature/issue linked."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            description="Validate user authentication flow",
        )

        with patch.object(runner.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_test.return_value = mock_session

            runner.execute_qa_validation_goal(goal)

            mock_test.assert_called_once()
            call_args = mock_test.call_args
            target = call_args.kwargs.get("target") or call_args[0][0]
            assert "Validate user authentication flow" in target

    def test_success_true_when_not_blocked(self, runner):
        """Should set success=True when recommendation is not BLOCK."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is True

    def test_success_true_on_warn_recommendation(self, runner):
        """Should set success=True when recommendation is WARN."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(recommendation=QARecommendation.WARN)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is True

    def test_success_false_on_block_recommendation(self, runner):
        """Should set success=False when recommendation is BLOCK."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.2
            mock_session.result = QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[MagicMock()],
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is False

    def test_includes_session_id(self, runner):
        """Should include session_id in result."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-validation-456"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.session_id == "qa-validation-456"

    def test_includes_cost(self, runner):
        """Should include cost_usd in result."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.25
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.cost_usd == 0.25

    def test_includes_findings_count(self, runner):
        """Should include findings_count in result."""
        findings = [
            QAFinding(
                finding_id="BT-001",
                severity="moderate",
                category="behavioral",
                endpoint="GET /api",
                test_type="happy_path",
                title="Issue",
                description="Desc",
                expected={},
                actual={},
                evidence={},
                recommendation="Fix",
            ),
            QAFinding(
                finding_id="BT-002",
                severity="minor",
                category="behavioral",
                endpoint="POST /api",
                test_type="error_case",
                title="Minor issue",
                description="Desc",
                expected={},
                actual={},
                evidence={},
                recommendation="Fix",
            ),
        ]

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.cost_usd = 0.1
            mock_session.result = QAResult(
                recommendation=QARecommendation.WARN,
                findings=findings,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:30Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.findings_count == 2

    def test_handles_orchestrator_error_gracefully(self, runner):
        """Should handle orchestrator errors gracefully."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test",
            linked_issue=1,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_validate.side_effect = Exception("Orchestrator crashed")

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is False
            assert result.error is not None
            assert "Orchestrator crashed" in result.error


# =============================================================================
# execute_qa_health_goal() TESTS
# =============================================================================


class TestExecuteQAHealthGoal:
    """Tests for execute_qa_health_goal() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def runner(self, mock_config):
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        return QAAutopilotRunner(mock_config)

    def test_returns_goal_execution_result(self, runner):
        """Should return GoalExecutionResult."""
        from swarm_attack.qa.integrations.cos_autopilot import GoalExecutionResult

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="Daily health check",
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-123"
            mock_session.cost_usd = 0.05
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert isinstance(result, GoalExecutionResult)

    def test_calls_health_check(self, runner):
        """Should call orchestrator health_check method."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="System health check",
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-123"
            mock_session.cost_usd = 0.05
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            runner.execute_qa_health_goal(goal)

            mock_health.assert_called_once()

    def test_success_true_when_no_failures(self, runner):
        """Should set success=True when no tests fail."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-123"
            mock_session.cost_usd = 0.05
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_run=10,
                tests_passed=10,
                tests_failed=0,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.success is True

    def test_success_false_when_tests_fail(self, runner):
        """Should set success=False when tests fail."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-123"
            mock_session.cost_usd = 0.05
            mock_session.result = QAResult(
                recommendation=QARecommendation.BLOCK,
                tests_run=10,
                tests_passed=8,
                tests_failed=2,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.success is False

    def test_includes_session_id(self, runner):
        """Should include session_id in result."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-789"
            mock_session.cost_usd = 0.05
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.session_id == "qa-health-789"

    def test_includes_cost(self, runner):
        """Should include cost_usd in result."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-health-123"
            mock_session.cost_usd = 0.03
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:10Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.cost_usd == 0.03

    def test_handles_orchestrator_error_gracefully(self, runner):
        """Should handle orchestrator errors gracefully."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_health.side_effect = Exception("Health check failed")

            result = runner.execute_qa_health_goal(goal)

            assert result.success is False
            assert result.error is not None
            assert "Health check failed" in result.error


# =============================================================================
# INTEGRATION WORKFLOW TESTS
# =============================================================================


class TestAutopilotWorkflow:
    """End-to-end workflow tests."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def runner(self, mock_config):
        from swarm_attack.qa.integrations.cos_autopilot import QAAutopilotRunner
        return QAAutopilotRunner(mock_config)

    def test_full_validation_goal_workflow(self, runner):
        """Should handle full validation goal workflow."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="user-auth",
            linked_issue=42,
            description="Validate user authentication",
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = QASession(
                session_id="qa-validation-001",
                trigger=QATrigger.POST_VERIFICATION,
                depth=QADepth.STANDARD,
                status=QAStatus.COMPLETED,
                context=QAContext(feature_id="user-auth", issue_number=42),
                result=QAResult(
                    recommendation=QARecommendation.PASS,
                    tests_run=15,
                    tests_passed=15,
                    tests_failed=0,
                ),
                cost_usd=0.12,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:45Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is True
            assert result.session_id == "qa-validation-001"
            assert result.cost_usd == 0.12
            assert result.findings_count == 0

    def test_full_health_goal_workflow(self, runner):
        """Should handle full health goal workflow."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="Daily health check",
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = QASession(
                session_id="qa-health-001",
                trigger=QATrigger.USER_COMMAND,
                depth=QADepth.SHALLOW,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.PASS,
                    tests_run=25,
                    tests_passed=25,
                    tests_failed=0,
                ),
                cost_usd=0.02,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:15Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.success is True
            assert result.session_id == "qa-health-001"
            assert result.cost_usd == 0.02

    def test_failed_validation_workflow(self, runner):
        """Should handle failed validation workflow."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="POST /api/auth/login",
            test_type="happy_path",
            title="Login fails with valid credentials",
            description="Authentication returns 500",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix auth service",
        )

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="user-auth",
            linked_issue=42,
        )

        with patch.object(runner.orchestrator, "validate_issue") as mock_validate:
            mock_session = QASession(
                session_id="qa-validation-002",
                trigger=QATrigger.POST_VERIFICATION,
                depth=QADepth.STANDARD,
                status=QAStatus.COMPLETED,
                context=QAContext(feature_id="user-auth", issue_number=42),
                result=QAResult(
                    recommendation=QARecommendation.BLOCK,
                    tests_run=15,
                    tests_passed=12,
                    tests_failed=3,
                    critical_count=1,
                    findings=[finding],
                ),
                cost_usd=0.15,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:45Z"
            mock_validate.return_value = mock_session

            result = runner.execute_qa_validation_goal(goal)

            assert result.success is False
            assert result.session_id == "qa-validation-002"
            assert result.findings_count == 1

    def test_unhealthy_system_workflow(self, runner):
        """Should handle unhealthy system health check."""
        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
        )

        with patch.object(runner.orchestrator, "health_check") as mock_health:
            mock_session = QASession(
                session_id="qa-health-002",
                trigger=QATrigger.USER_COMMAND,
                depth=QADepth.SHALLOW,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.BLOCK,
                    tests_run=25,
                    tests_passed=23,
                    tests_failed=2,
                ),
                cost_usd=0.02,
            )
            mock_session.started_at = "2024-12-25T14:30:00Z"
            mock_session.completed_at = "2024-12-25T14:30:15Z"
            mock_health.return_value = mock_session

            result = runner.execute_qa_health_goal(goal)

            assert result.success is False
