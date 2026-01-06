"""Integration tests for Semantic QA system."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

try:
    from swarm_attack.qa.agents.semantic_tester import (
        SemanticTesterAgent,
        SemanticTestResult,
        SemanticVerdict,
        SemanticScope,
    )
    from swarm_attack.qa.regression_scheduler import (
        RegressionScheduler,
        RegressionSchedulerConfig,
    )
    from swarm_attack.qa.orchestrator import QAOrchestrator
    from swarm_attack.qa.models import QADepth
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="Semantic QA components not yet implemented"
)


class TestSemanticTesterIntegration:
    """Integration tests for SemanticTesterAgent."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a mock config."""
        config = Mock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def agent(self, config):
        """Create a SemanticTesterAgent."""
        return SemanticTesterAgent(config)

    def test_agent_loads_custom_skill(self, tmp_path, config):
        """Test that agent loads custom SKILL.md."""
        skill_dir = tmp_path / ".claude" / "skills" / "semantic-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: custom
---
Custom skill prompt for testing.""")

        agent = SemanticTesterAgent(config)
        assert "Custom skill prompt" in agent.skill_prompt

    def test_prompt_includes_all_context(self, agent):
        """Test that built prompt includes all context."""
        context = {
            "changes": "def new_feature(): pass",
            "expected_behavior": "Should create new feature",
            "test_scope": SemanticScope.AFFECTED,
            "test_scenarios": ["Test happy path", "Test error case"],
        }

        prompt = agent._build_test_prompt(context)

        assert "def new_feature(): pass" in prompt
        assert "Should create new feature" in prompt
        assert "affected" in prompt
        assert "Test happy path" in prompt
        assert "Test error case" in prompt

    @patch("subprocess.run")
    def test_full_test_flow(self, mock_run, agent):
        """Test complete test flow with mocked CLI."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='''Here's my analysis:
```json
{
    "verdict": "PASS",
    "evidence": [
        {"description": "All tests passed", "source": "pytest", "confidence": 0.95}
    ],
    "issues": [],
    "recommendations": ["Consider adding more edge case tests"]
}
```''',
            stderr="",
        )

        result = agent.run({
            "changes": "def foo(): return 42",
            "expected_behavior": "Returns 42",
        })

        assert result.success is True
        assert result.output["verdict"] == "PASS"
        assert len(result.output["evidence"]) == 1
        assert result.output["recommendations"] == ["Consider adding more edge case tests"]


class TestRegressionSchedulerIntegration:
    """Integration tests for RegressionScheduler."""

    def test_full_lifecycle(self, tmp_path):
        """Test complete scheduler lifecycle."""
        config = RegressionSchedulerConfig(
            issues_between_regressions=3,
            commits_between_regressions=5,
        )
        scheduler = RegressionScheduler(config, tmp_path)

        # Record some activity
        scheduler.record_issue_committed("issue-1")
        scheduler.record_commit("abc123")
        scheduler.record_commit("def456")

        # Check status
        status = scheduler.get_status()
        assert status["issues_until_regression"] == 2
        assert status["commits_until_regression"] == 3

        # Trigger regression
        scheduler.record_issue_committed("issue-2")
        scheduler.record_issue_committed("issue-3")  # This should trigger

        assert scheduler.should_run_regression() is True

        # Complete regression
        scheduler.record_regression_completed({"verdict": "PASS"})

        # Check reset
        status = scheduler.get_status()
        assert status["issues_until_regression"] == 3
        assert status["commits_until_regression"] == 5
        assert status["last_result"] == "PASS"

    def test_state_persistence(self, tmp_path):
        """Test that state persists across instances."""
        config = RegressionSchedulerConfig()

        # First instance
        scheduler1 = RegressionScheduler(config, tmp_path)
        scheduler1.record_issue_committed("issue-1")
        scheduler1.record_commit("abc123")

        # Second instance should load state
        scheduler2 = RegressionScheduler(config, tmp_path)
        assert scheduler2.state["issues_since_last_regression"] == 1
        assert scheduler2.state["commits_since_last_regression"] == 1


class TestOrchestratorSemanticIntegration:
    """Integration tests for Orchestrator with Semantic depth."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create mock config."""
        config = Mock()
        config.repo_root = str(tmp_path)
        return config

    @patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent")
    @patch("swarm_attack.qa.orchestrator.ContractValidatorAgent")
    @patch("swarm_attack.qa.orchestrator.RegressionScannerAgent")
    def test_semantic_depth_uses_semantic_agent(
        self, mock_regression, mock_contract, mock_behavioral, config, tmp_path
    ):
        """Test that SEMANTIC depth uses SemanticTesterAgent."""
        # Create sessions directory
        (tmp_path / ".swarm" / "qa").mkdir(parents=True)

        # Mock the agents
        mock_behavioral.return_value.run.return_value = Mock(success=True, output={}, error=None)
        mock_contract.return_value.run.return_value = Mock(success=True, output={}, error=None)
        mock_regression.return_value.run.return_value = Mock(success=True, output={}, error=None)

        with patch("swarm_attack.qa.orchestrator.SemanticTesterAgent") as mock_semantic:
            mock_semantic.return_value.run.return_value = Mock(
                success=True,
                output={"verdict": "PASS", "issues": []},
                error=None,
            )

            orchestrator = QAOrchestrator(config)

            # Verify semantic agent was created
            mock_semantic.assert_called_once()


class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.fixture
    def project_setup(self, tmp_path):
        """Set up a minimal project structure."""
        # Create .swarm directory
        (tmp_path / ".swarm" / "qa").mkdir(parents=True)

        # Create a test file
        (tmp_path / "test_file.py").write_text("def example(): return True")

        # Create SKILL.md
        skill_dir = tmp_path / ".claude" / "skills" / "semantic-test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
allowed-tools: Read,Bash
---
Test skill for integration testing.""")

        return tmp_path

    @patch("subprocess.run")
    def test_semantic_test_with_git_diff(self, mock_run, project_setup):
        """Test semantic testing with simulated git diff."""
        config = Mock()
        config.repo_root = str(project_setup)

        # Mock CLI response
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}',
            stderr="",
        )

        agent = SemanticTesterAgent(config)
        result = agent.run({
            "changes": "diff --git a/test.py\n+def new_func(): pass",
            "expected_behavior": "New function should be defined",
        })

        assert result.success is True

        # Verify CLI was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "claude" in call_args[0][0]
        assert "--model" in call_args[0][0]
