"""Integration tests for semantic tester in feature and bug pipelines."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from swarm_attack.qa.agents.semantic_tester import (
    SemanticTesterAgent,
    SemanticVerdict,
    SemanticTestResult,
    Evidence,
    SemanticIssue,
)


class TestSemanticTesterFeaturePipelineIntegration:
    """Test semantic tester integration with feature pipeline."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = Mock()
        config.repo_root = tmp_path
        config.swarm_path = tmp_path / ".swarm"
        return config

    @pytest.fixture
    def mock_subprocess_pass(self):
        """Mock subprocess.run for passing semantic test."""
        result = Mock()
        result.returncode = 0
        result.stdout = '''
        ```json
        {
            "verdict": "PASS",
            "evidence": [{"description": "Tests pass", "source": "pytest", "confidence": 0.95}],
            "issues": [],
            "recommendations": []
        }
        ```
        '''
        return result

    @pytest.fixture
    def mock_subprocess_fail(self):
        """Mock subprocess.run for failing semantic test."""
        result = Mock()
        result.returncode = 0
        result.stdout = '''
        ```json
        {
            "verdict": "FAIL",
            "evidence": [],
            "issues": [{"severity": "critical", "description": "Missing error handling", "location": "api.py:42", "suggestion": "Add try/except"}],
            "recommendations": ["Add proper error handling"]
        }
        ```
        '''
        return result

    @pytest.fixture
    def mock_subprocess_partial(self):
        """Mock subprocess.run for partial semantic test."""
        result = Mock()
        result.returncode = 0
        result.stdout = '''
        ```json
        {
            "verdict": "PARTIAL",
            "evidence": [{"description": "Basic tests pass", "source": "pytest", "confidence": 0.7}],
            "issues": [{"severity": "minor", "description": "Edge case not tested", "location": "api.py:50", "suggestion": "Add edge case test"}],
            "recommendations": ["Consider adding edge case tests"]
        }
        ```
        '''
        return result

    def test_semantic_pass_allows_commit(self, mock_config, mock_subprocess_pass):
        """PASS verdict should allow commit to proceed."""
        with patch('subprocess.run', return_value=mock_subprocess_pass):
            agent = SemanticTesterAgent(mock_config)
            result = agent.run({
                "changes": "def new_feature(): pass",
                "expected_behavior": "Feature should work",
            })

            assert result.success is True
            assert result.output["verdict"] == "PASS"

    def test_semantic_fail_blocks_commit(self, mock_config, mock_subprocess_fail):
        """FAIL verdict should block commit."""
        with patch('subprocess.run', return_value=mock_subprocess_fail):
            agent = SemanticTesterAgent(mock_config)
            result = agent.run({
                "changes": "def broken(): pass",
                "expected_behavior": "Feature should work",
            })

            assert result.success is False
            assert result.output["verdict"] == "FAIL"
            assert len(result.output["issues"]) > 0

    def test_semantic_partial_allows_commit_with_warning(self, mock_config, mock_subprocess_partial):
        """PARTIAL verdict should allow commit with warning."""
        with patch('subprocess.run', return_value=mock_subprocess_partial):
            agent = SemanticTesterAgent(mock_config)
            result = agent.run({
                "changes": "def partial_feature(): pass",
                "expected_behavior": "Feature should mostly work",
            })

            assert result.success is True  # PARTIAL counts as success
            assert result.output["verdict"] == "PARTIAL"
            assert len(result.output["recommendations"]) > 0


class TestSemanticTesterBugPipelineIntegration:
    """Test semantic tester integration with bug pipeline."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = Mock()
        config.repo_root = tmp_path
        config.swarm_path = tmp_path / ".swarm"
        return config

    def test_bug_fix_pass_continues_to_pytest(self, mock_config):
        """PASS verdict should continue to pytest verification."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}'

        with patch('subprocess.run', return_value=mock_result):
            agent = SemanticTesterAgent(mock_config)
            result = agent.run({
                "changes": "Fixed bug by adding validation",
                "expected_behavior": "Bug should be fixed",
            })

            assert result.success is True

    def test_bug_fix_fail_returns_to_analysis(self, mock_config):
        """FAIL verdict should send bug back to analysis."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''```json
{"verdict": "FAIL", "evidence": [], "issues": [{"severity": "critical", "description": "Bug not fixed", "location": "fix.py", "suggestion": "Try different approach"}], "recommendations": []}
```'''

        with patch('subprocess.run', return_value=mock_result):
            agent = SemanticTesterAgent(mock_config)
            result = agent.run({
                "changes": "Attempted fix",
                "expected_behavior": "Bug should be fixed",
            })

            assert result.success is False
            assert result.output["verdict"] == "FAIL"


class TestBugPipelineSemanticHookIntegration:
    """Integration tests for semantic hook in bug pipeline.

    Verifies:
    1. SemanticTestHook (via SemanticTesterAgent) is called during bug pipeline execution
    2. FAIL verdict blocks proceeding to pytest
    3. PARTIAL verdict allows proceeding with warning
    4. PASS verdict allows proceeding normally
    """

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock SwarmConfig for bug orchestrator."""
        config = Mock()
        config.repo_root = str(tmp_path)
        config.bug_bash = Mock()
        config.bug_bash.debate = Mock()
        config.bug_bash.debate.enabled = False
        return config

    @pytest.fixture
    def mock_state_store(self, tmp_path):
        """Create mock state store."""
        store = Mock()
        store.base_path = tmp_path / ".swarm" / "bugs"
        return store

    @pytest.fixture
    def approved_bug_state(self):
        """Create an approved bug state ready for fix."""
        from swarm_attack.bug_models import (
            BugPhase,
            BugState,
            RootCauseAnalysis,
            FixPlan,
            FileChange,
            ApprovalRecord,
        )
        state = BugState.create(
            bug_id="bug-test-integration-001",
            description="Test bug for semantic hook integration",
            test_path="tests/test_something.py",
        )
        state.phase = BugPhase.APPROVED
        state.root_cause = RootCauseAnalysis(
            summary="Missing validation in function X",
            execution_trace="trace",
            root_cause_file="src/module.py",
            root_cause_line=42,
            root_cause_code="def buggy_func():",
            root_cause_explanation="Missing check",
            why_not_caught="No tests covered this case",
            confidence=0.85,
        )
        state.fix_plan = FixPlan(
            summary="Add validation check",
            changes=[
                FileChange(
                    file_path="src/module.py",
                    change_type="modify",
                    current_code="def buggy_func():",
                    proposed_code="def buggy_func():\n    validate()",
                    explanation="Add validation",
                )
            ],
            test_cases=[],
            risk_level="low",
            risk_explanation="Simple change",
        )
        state.approval_record = ApprovalRecord.create(
            approved_by="test_user",
            fix_plan=state.fix_plan,
        )
        return state

    @pytest.fixture
    def orchestrator(self, mock_config, mock_state_store):
        """Create a BugOrchestrator with mocked dependencies."""
        from swarm_attack.bug_orchestrator import BugOrchestrator
        return BugOrchestrator(
            config=mock_config,
            logger=None,
            state_store=mock_state_store,
        )

    def test_semantic_tester_called_during_fix_pipeline(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Integration test: SemanticTesterAgent is called during bug fix pipeline."""
        from swarm_attack.agents.base import AgentResult

        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        semantic_call_tracker = {"called": False, "context": None}

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = Mock()

            def track_semantic_call(context):
                semantic_call_tracker["called"] = True
                semantic_call_tracker["context"] = context
                return AgentResult(
                    success=True,
                    output={"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []},
                    errors=[],
                    cost_usd=0.0,
                )

            mock_agent.run.side_effect = track_semantic_call
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = Mock(
                    returncode=0, stdout="Tests passed", stderr=""
                )

                orchestrator.fix("bug-test-integration-001")

                # Verify SemanticTesterAgent was instantiated and called
                MockSemanticTester.assert_called_once()
                assert semantic_call_tracker["called"] is True
                assert semantic_call_tracker["context"] is not None
                assert "changes" in semantic_call_tracker["context"]
                assert "expected_behavior" in semantic_call_tracker["context"]

    def test_fail_verdict_blocks_pytest_execution(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Integration test: FAIL verdict blocks proceeding to pytest."""
        from swarm_attack.agents.base import AgentResult
        from swarm_attack.bug_models import BugPhase

        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = Mock()
            mock_agent.run.return_value = AgentResult(
                success=False,
                output={
                    "verdict": "FAIL",
                    "issues": [{"severity": "critical", "description": "Fix does not address root cause"}],
                },
                errors=["Semantic validation failed"],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                result = orchestrator.fix("bug-test-integration-001")

                # Pytest should NOT be called when semantic test fails
                mock_subprocess.assert_not_called()

                # Result should indicate failure and blocked state
                assert result.success is False
                assert result.phase == BugPhase.BLOCKED
                assert "semantic" in result.error.lower()

    def test_partial_verdict_allows_proceeding_with_warning(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Integration test: PARTIAL verdict allows proceeding to pytest with warning logged."""
        from swarm_attack.agents.base import AgentResult
        from swarm_attack.bug_models import BugPhase

        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = Mock()
            mock_agent.run.return_value = AgentResult(
                success=True,  # PARTIAL counts as success
                output={
                    "verdict": "PARTIAL",
                    "issues": [{"severity": "minor", "description": "Edge case not covered"}],
                    "recommendations": ["Consider adding edge case tests"],
                },
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = Mock(
                    returncode=0, stdout="Tests passed", stderr=""
                )

                result = orchestrator.fix("bug-test-integration-001")

                # Pytest SHOULD be called for PARTIAL verdict
                mock_subprocess.assert_called()

                # Result should indicate success
                assert result.success is True
                assert result.phase == BugPhase.FIXED

    def test_pass_verdict_allows_proceeding_normally(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Integration test: PASS verdict allows proceeding to pytest normally."""
        from swarm_attack.agents.base import AgentResult
        from swarm_attack.bug_models import BugPhase

        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = Mock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = Mock(
                    returncode=0, stdout="Tests passed", stderr=""
                )

                result = orchestrator.fix("bug-test-integration-001")

                # Pytest SHOULD be called for PASS verdict
                mock_subprocess.assert_called()

                # Result should indicate success
                assert result.success is True
                assert result.phase == BugPhase.FIXED

    def test_semantic_call_order_before_pytest(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Integration test: Semantic test runs BEFORE pytest verification."""
        from swarm_attack.agents.base import AgentResult

        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        call_order = []

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = Mock()

            def track_semantic(*args, **kwargs):
                call_order.append("semantic_tester")
                return AgentResult(
                    success=True,
                    output={"verdict": "PASS"},
                    errors=[],
                    cost_usd=0.0,
                )

            mock_agent.run.side_effect = track_semantic
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                def track_subprocess(*args, **kwargs):
                    call_order.append("pytest")
                    result = Mock()
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                    return result

                mock_subprocess.side_effect = track_subprocess

                orchestrator.fix("bug-test-integration-001")

                # Verify call order: semantic_tester before pytest
                assert call_order == ["semantic_tester", "pytest"], \
                    f"Expected semantic_tester before pytest, got: {call_order}"


class TestRegressionSchedulerIntegration:
    """Test regression scheduler integration with verifier."""

    @pytest.fixture
    def scheduler_config(self, tmp_path):
        """Create scheduler config."""
        from swarm_attack.qa.regression_scheduler import RegressionSchedulerConfig
        return RegressionSchedulerConfig(
            issues_between_regressions=3,  # Low for testing
            commits_between_regressions=5,
            time_between_regressions_hours=24,
            state_file=str(tmp_path / ".swarm/regression_state.json"),
        )

    def test_regression_triggers_after_n_issues(self, tmp_path, scheduler_config):
        """Regression should trigger after N issues committed."""
        from swarm_attack.qa.regression_scheduler import RegressionScheduler

        scheduler = RegressionScheduler(scheduler_config, tmp_path)

        # First two issues - no regression
        assert scheduler.record_issue_committed("issue_1") is False
        assert scheduler.record_issue_committed("issue_2") is False

        # Third issue - triggers regression
        assert scheduler.record_issue_committed("issue_3") is True

    def test_regression_resets_after_run(self, tmp_path, scheduler_config):
        """Counters should reset after regression completes."""
        from swarm_attack.qa.regression_scheduler import RegressionScheduler

        scheduler = RegressionScheduler(scheduler_config, tmp_path)

        # Trigger regression
        scheduler.record_issue_committed("issue_1")
        scheduler.record_issue_committed("issue_2")
        scheduler.record_issue_committed("issue_3")

        # Complete regression
        scheduler.record_regression_completed({"verdict": "PASS"})

        # Status should be reset
        status = scheduler.get_status()
        assert status["issues_until_regression"] == 3
