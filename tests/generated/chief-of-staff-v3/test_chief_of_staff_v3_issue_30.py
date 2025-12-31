"""Tests for execution_strategy config option in AutopilotConfig."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.chief_of_staff.config import AutopilotConfig, ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    ExecutionStrategy,
    GoalExecutionResult,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus


class TestAutopilotConfigHasExecutionStrategy:
    """Tests that AutopilotConfig has execution_strategy field."""

    def test_autopilot_config_has_execution_strategy_attr(self):
        """AutopilotConfig should have execution_strategy attribute."""
        config = AutopilotConfig()
        assert hasattr(config, "execution_strategy")

    def test_autopilot_config_execution_strategy_default_is_sequential(self):
        """execution_strategy default should be ExecutionStrategy.SEQUENTIAL."""
        config = AutopilotConfig()
        assert config.execution_strategy == ExecutionStrategy.SEQUENTIAL

    def test_autopilot_config_execution_strategy_is_enum(self):
        """execution_strategy should be an ExecutionStrategy enum."""
        config = AutopilotConfig()
        assert isinstance(config.execution_strategy, ExecutionStrategy)

    def test_autopilot_config_can_set_execution_strategy(self):
        """AutopilotConfig can be created with custom execution_strategy."""
        config = AutopilotConfig(execution_strategy=ExecutionStrategy.CONTINUE_ON_BLOCK)
        assert config.execution_strategy == ExecutionStrategy.CONTINUE_ON_BLOCK


class TestAutopilotConfigFromDict:
    """Tests for AutopilotConfig.from_dict() parsing execution_strategy."""

    def test_from_dict_parses_execution_strategy_string(self):
        """from_dict should parse execution_strategy string to enum."""
        data = {
            "autopilot": {
                "execution_strategy": "continue_on_block"
            }
        }
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.CONTINUE_ON_BLOCK

    def test_from_dict_parses_sequential_strategy(self):
        """from_dict should parse 'sequential' string."""
        data = {
            "autopilot": {
                "execution_strategy": "sequential"
            }
        }
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.SEQUENTIAL

    def test_from_dict_parses_parallel_safe_strategy(self):
        """from_dict should parse 'parallel_safe' string."""
        data = {
            "autopilot": {
                "execution_strategy": "parallel_safe"
            }
        }
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.PARALLEL_SAFE

    def test_from_dict_defaults_to_sequential_when_missing(self):
        """from_dict should default to SEQUENTIAL when execution_strategy is missing."""
        data = {
            "autopilot": {
                "default_budget": 15.0
            }
        }
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.SEQUENTIAL

    def test_from_dict_handles_empty_autopilot_section(self):
        """from_dict should handle empty autopilot section."""
        data = {"autopilot": {}}
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.SEQUENTIAL

    def test_from_dict_handles_no_autopilot_section(self):
        """from_dict should handle missing autopilot section."""
        data = {}
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.autopilot.execution_strategy == ExecutionStrategy.SEQUENTIAL


class TestAutopilotConfigToDict:
    """Tests for AutopilotConfig.to_dict() serializing execution_strategy."""

    def test_to_dict_serializes_execution_strategy_to_string(self):
        """to_dict should serialize execution_strategy enum to string value."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        
        result = config.to_dict()
        
        assert "autopilot" in result
        assert "execution_strategy" in result["autopilot"]
        assert result["autopilot"]["execution_strategy"] == "continue_on_block"

    def test_to_dict_serializes_sequential_strategy(self):
        """to_dict should serialize SEQUENTIAL to 'sequential'."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.SEQUENTIAL
        
        result = config.to_dict()
        
        assert result["autopilot"]["execution_strategy"] == "sequential"

    def test_to_dict_serializes_parallel_safe_strategy(self):
        """to_dict should serialize PARALLEL_SAFE to 'parallel_safe'."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.PARALLEL_SAFE
        
        result = config.to_dict()
        
        assert result["autopilot"]["execution_strategy"] == "parallel_safe"

    def test_from_dict_to_dict_roundtrip(self):
        """from_dict -> to_dict should preserve execution_strategy."""
        original_data = {
            "autopilot": {
                "execution_strategy": "continue_on_block"
            }
        }
        config = ChiefOfStaffConfig.from_dict(original_data)
        result = config.to_dict()
        
        assert result["autopilot"]["execution_strategy"] == "continue_on_block"


class TestAutopilotRunnerStartUsesExecutionStrategy:
    """Tests that AutopilotRunner.start() uses execution_strategy from config."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        # Make check_before_execution return a simple result
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

    def test_start_uses_sequential_by_default(self, mock_checkpoint_system, mock_session_store, sample_goals):
        """start() should use sequential strategy by default."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.SEQUENTIAL
        
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        # Patch _execute_goal to track calls
        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.1, duration_seconds=10
            )
            
            runner.start(sample_goals, budget_usd=10.0, duration_minutes=60)
            
            # Sequential strategy should call _execute_goal directly
            assert mock_execute.call_count == 2

    def test_start_calls_continue_on_block_when_configured(
        self, mock_checkpoint_system, mock_session_store, sample_goals
    ):
        """start() should use _execute_goals_continue_on_block when strategy is CONTINUE_ON_BLOCK."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        # Patch _execute_goals_continue_on_block to track calls
        with patch.object(runner, '_execute_goals_continue_on_block') as mock_continue:
            mock_continue.return_value = (2, 0.2, set())
            
            result = runner.start(sample_goals, budget_usd=10.0, duration_minutes=60)
            
            # CONTINUE_ON_BLOCK strategy should call _execute_goals_continue_on_block
            assert mock_continue.call_count == 1

    def test_start_with_continue_on_block_returns_correct_result(
        self, mock_checkpoint_system, mock_session_store, sample_goals
    ):
        """start() with CONTINUE_ON_BLOCK should return correct result structure."""
        config = ChiefOfStaffConfig()
        config.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        # Patch _execute_goals_continue_on_block
        with patch.object(runner, '_execute_goals_continue_on_block') as mock_continue:
            mock_continue.return_value = (2, 0.5, set())
            
            result = runner.start(sample_goals, budget_usd=10.0, duration_minutes=60)
            
            assert result.goals_completed == 2
            assert result.goals_total == 2
            assert result.total_cost_usd == 0.5


class TestConfigFileExists:
    """Tests to verify implementation file exists."""

    def test_config_file_exists(self):
        """config.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "config.py"
        assert path.exists(), "config.py must exist"

    def test_config_file_has_execution_strategy(self):
        """config.py must contain execution_strategy."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "config.py"
        content = path.read_text()
        assert "execution_strategy" in content, "config.py must have execution_strategy"

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"