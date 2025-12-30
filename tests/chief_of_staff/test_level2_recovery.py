"""Tests for Level 2 intelligent recovery.

TDD RED phase: These tests define the expected behavior of Level2Analyzer.
They should FAIL until we implement the actual code.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from swarm_attack.chief_of_staff.recovery import (
    RecoveryManager,
    RetryStrategy,
    ErrorCategory,
    classify_error,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.errors import LLMError, LLMErrorType


class TestLevel2Analyzer:
    """Tests for Level 2 intelligent recovery analyzer."""

    @pytest.fixture
    def sample_goal(self):
        """Create a sample goal for testing."""
        return DailyGoal(
            goal_id="test-goal",
            description="Implement auth feature",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
        )

    @pytest.fixture
    def systematic_error(self):
        """Create a systematic error for testing."""
        return LLMError("CLI crashed unexpectedly", error_type=LLMErrorType.CLI_CRASH)

    @pytest.fixture
    def json_parse_error(self):
        """Create a JSON parse error for testing."""
        return LLMError("Invalid JSON in response", error_type=LLMErrorType.JSON_PARSE_ERROR)

    def test_level2_analyzer_import(self):
        """Level2Analyzer module can be imported."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer
        assert Level2Analyzer is not None

    def test_level2_analyzer_init(self):
        """Level2Analyzer can be instantiated with LLM."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer

        mock_llm = Mock()
        analyzer = Level2Analyzer(llm=mock_llm)
        assert analyzer is not None
        assert analyzer.llm == mock_llm

    def test_recovery_action_types_exist(self):
        """RecoveryActionType enum has expected values."""
        from swarm_attack.chief_of_staff.level2_recovery import RecoveryActionType

        assert hasattr(RecoveryActionType, 'ALTERNATIVE')
        assert hasattr(RecoveryActionType, 'DIAGNOSTICS')
        assert hasattr(RecoveryActionType, 'UNBLOCK')
        assert hasattr(RecoveryActionType, 'ESCALATE')

    def test_recovery_action_dataclass(self):
        """RecoveryAction has required fields."""
        from swarm_attack.chief_of_staff.level2_recovery import RecoveryAction, RecoveryActionType

        action = RecoveryAction(
            action_type=RecoveryActionType.ALTERNATIVE,
            hint="Try using async pattern",
            reasoning="The sync approach caused deadlock",
        )

        assert action.action_type == RecoveryActionType.ALTERNATIVE
        assert action.hint == "Try using async pattern"
        assert action.reasoning == "The sync approach caused deadlock"

    @pytest.mark.asyncio
    async def test_analyze_calls_llm(self, sample_goal, systematic_error):
        """analyze() calls LLM to determine recovery strategy."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "alternative", "hint": "Try async", "reasoning": "Sync failed"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        await analyzer.analyze(sample_goal, systematic_error)

        mock_llm.ask.assert_called_once()
        call_args = mock_llm.ask.call_args[0][0]
        assert "Implement auth feature" in call_args
        assert "CLI crashed" in call_args

    @pytest.mark.asyncio
    async def test_analyze_returns_alternative(self, sample_goal, systematic_error):
        """analyze() returns ALTERNATIVE when LLM suggests it."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "alternative", "hint": "Try async pattern", "reasoning": "Sync approach deadlocked"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        assert action.action_type == RecoveryActionType.ALTERNATIVE
        assert "async" in action.hint.lower()

    @pytest.mark.asyncio
    async def test_analyze_returns_diagnostics(self, sample_goal, systematic_error):
        """analyze() returns DIAGNOSTICS when LLM suggests running bug bash."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "diagnostics", "hint": "Run bug bash to investigate", "reasoning": "Error is unclear"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        assert action.action_type == RecoveryActionType.DIAGNOSTICS

    @pytest.mark.asyncio
    async def test_analyze_returns_unblock(self, sample_goal, systematic_error):
        """analyze() returns UNBLOCK when LLM suggests admin commands."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "unblock", "hint": "Reset the issue state", "reasoning": "State is corrupted"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        assert action.action_type == RecoveryActionType.UNBLOCK

    @pytest.mark.asyncio
    async def test_analyze_returns_escalate_as_fallback(self, sample_goal, systematic_error):
        """analyze() returns ESCALATE when LLM gives up."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "escalate", "hint": "Needs human review", "reasoning": "Too complex for auto-recovery"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        assert action.action_type == RecoveryActionType.ESCALATE

    @pytest.mark.asyncio
    async def test_analyze_handles_invalid_llm_response(self, sample_goal, systematic_error):
        """analyze() handles invalid LLM response gracefully."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='not valid json at all')

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        # Should fall back to escalate
        assert action.action_type == RecoveryActionType.ESCALATE

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_exception(self, sample_goal, systematic_error):
        """analyze() handles LLM exception gracefully."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(side_effect=Exception("LLM unavailable"))

        analyzer = Level2Analyzer(llm=mock_llm)
        action = await analyzer.analyze(sample_goal, systematic_error)

        # Should fall back to escalate
        assert action.action_type == RecoveryActionType.ESCALATE


class TestLevel2Integration:
    """Tests for Level 2 integration with RecoveryManager."""

    @pytest.fixture
    def sample_goal(self):
        """Create a sample goal for testing."""
        return DailyGoal(
            goal_id="test-goal-2",
            description="Fix database connection",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

    @pytest.fixture
    def systematic_error(self):
        """Create a systematic error for testing."""
        return LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

    def test_recovery_manager_has_level2_analyzer(self):
        """RecoveryManager can be initialized with Level2Analyzer."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer
        from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem

        mock_checkpoint = Mock(spec=CheckpointSystem)
        mock_llm = Mock()

        analyzer = Level2Analyzer(llm=mock_llm)
        manager = RecoveryManager(
            checkpoint_system=mock_checkpoint,
            level2_analyzer=analyzer,
        )

        assert manager.level2_analyzer == analyzer

    @pytest.mark.asyncio
    async def test_systematic_error_triggers_level2(self, sample_goal, systematic_error):
        """Systematic errors go through Level 2 analysis."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType
        from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem

        mock_checkpoint = Mock(spec=CheckpointSystem)
        mock_checkpoint.store = Mock()
        mock_checkpoint.store.save = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "alternative", "hint": "Retry with timeout", "reasoning": "May be transient"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        manager = RecoveryManager(
            checkpoint_system=mock_checkpoint,
            level2_analyzer=analyzer,
        )

        # Execute function that fails with systematic error
        call_count = 0
        async def execute_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise systematic_error
            return Mock(success=True, cost_usd=1.0)

        result = await manager.execute_with_recovery(sample_goal, execute_fn)

        # Should have called LLM for Level 2 analysis
        mock_llm.ask.assert_called()

    @pytest.mark.asyncio
    async def test_level2_alternative_retries_with_hint(self, sample_goal, systematic_error):
        """When Level 2 suggests alternative, retry includes hint in context."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer
        from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem

        mock_checkpoint = Mock(spec=CheckpointSystem)
        mock_checkpoint.store = Mock()
        mock_checkpoint.store.save = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.ask = AsyncMock(return_value='{"action": "alternative", "hint": "Use async pattern", "reasoning": "Sync deadlocked"}')

        analyzer = Level2Analyzer(llm=mock_llm)
        manager = RecoveryManager(
            checkpoint_system=mock_checkpoint,
            level2_analyzer=analyzer,
        )

        hints_received = []
        call_count = 0

        async def execute_fn():
            nonlocal call_count
            call_count += 1
            # Check if hint was added to goal context
            if hasattr(sample_goal, 'recovery_hint'):
                hints_received.append(sample_goal.recovery_hint)
            if call_count < 3:
                raise systematic_error
            return Mock(success=True, cost_usd=1.0)

        result = await manager.execute_with_recovery(sample_goal, execute_fn)

        # Hint should have been added for retry
        assert len(hints_received) > 0 or hasattr(sample_goal, 'recovery_hint')

    @pytest.mark.asyncio
    async def test_level2_limits_alternative_attempts(self, sample_goal, systematic_error):
        """Level 2 limits alternative attempts before escalating."""
        from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer
        from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem

        mock_checkpoint = Mock(spec=CheckpointSystem)
        mock_checkpoint.store = Mock()
        mock_checkpoint.store.save = AsyncMock()

        mock_llm = AsyncMock()
        # Always suggest alternative
        mock_llm.ask = AsyncMock(return_value='{"action": "alternative", "hint": "Try again", "reasoning": "May work"}')

        analyzer = Level2Analyzer(llm=mock_llm, max_alternatives=2)
        manager = RecoveryManager(
            checkpoint_system=mock_checkpoint,
            level2_analyzer=analyzer,
        )

        attempts = 0

        async def execute_fn():
            nonlocal attempts
            attempts += 1
            raise systematic_error

        result = await manager.execute_with_recovery(sample_goal, execute_fn)

        # Should have limited retries (3 transient + 2 alternative max)
        assert attempts <= 5
        assert result.success == False
