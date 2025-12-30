"""Tests for CheckpointSystem trigger detection."""

import pytest
from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointStore,
    CheckpointTrigger,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus


class TestCheckpointSystemInit:
    """Tests for CheckpointSystem initialization."""

    def test_init_with_store_and_config(self):
        """CheckpointSystem can be initialized with store and config."""
        store = CheckpointStore()
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config, store=store)
        assert system.store is store
        assert system.config is config

    def test_init_creates_default_store(self):
        """CheckpointSystem creates default store if not provided."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        assert system.store is not None
        assert isinstance(system.store, CheckpointStore)


class TestDetectTriggers:
    """Tests for _detect_triggers method."""

    def test_detect_triggers_returns_list(self):
        """_detect_triggers returns a list."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        result = system._detect_triggers(goal)
        assert isinstance(result, list)

    def test_detect_triggers_returns_empty_for_normal_goal(self):
        """_detect_triggers returns empty list for normal goal."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Normal task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["backend"],
        )
        result = system._detect_triggers(goal)
        assert result == []


class TestUXChangeTrigger:
    """Tests for UX_CHANGE trigger detection."""

    def test_ux_change_trigger_on_ui_tag(self):
        """UX_CHANGE triggered when tags contain 'ui'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Update button",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["ui", "button"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result

    def test_ux_change_trigger_on_ux_tag(self):
        """UX_CHANGE triggered when tags contain 'ux'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Improve flow",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["ux"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result

    def test_ux_change_trigger_on_frontend_tag(self):
        """UX_CHANGE triggered when tags contain 'frontend'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Fix styles",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["frontend"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result

    def test_ux_change_trigger_case_insensitive(self):
        """UX_CHANGE is case-insensitive."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Fix UI",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["UI", "FRONTEND"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result

    def test_ux_change_trigger_mixed_case(self):
        """UX_CHANGE handles mixed case tags."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Update Frontend",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["FrontEnd"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result


class TestCostSingleTrigger:
    """Tests for COST_SINGLE trigger detection."""

    def test_cost_single_trigger_above_threshold(self):
        """COST_SINGLE triggered when estimated_cost_usd > checkpoint_cost_single."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Expensive task",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=10.0,  # Above default 5.0
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_SINGLE in result

    def test_cost_single_trigger_below_threshold(self):
        """COST_SINGLE not triggered when estimated_cost_usd <= checkpoint_cost_single."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Cheap task",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
            estimated_cost_usd=2.0,  # Below default 5.0
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_SINGLE not in result

    def test_cost_single_trigger_at_threshold(self):
        """COST_SINGLE not triggered when estimated_cost_usd == checkpoint_cost_single."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Exact threshold task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=5.0,  # Equal to default 5.0
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_SINGLE not in result

    def test_cost_single_trigger_no_cost_estimate(self):
        """COST_SINGLE not triggered when estimated_cost_usd is None."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="No cost estimate",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=None,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_SINGLE not in result


class TestCostCumulativeTrigger:
    """Tests for COST_CUMULATIVE trigger detection."""

    def test_cost_cumulative_trigger_above_threshold(self):
        """COST_CUMULATIVE triggered when daily_cost > checkpoint_cost_daily."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        system.daily_cost = 20.0  # Above default 15.0
        goal = DailyGoal(
            goal_id="test-1",
            description="Task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_CUMULATIVE in result

    def test_cost_cumulative_trigger_below_threshold(self):
        """COST_CUMULATIVE not triggered when daily_cost <= checkpoint_cost_daily."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        system.daily_cost = 10.0  # Below default 15.0
        goal = DailyGoal(
            goal_id="test-1",
            description="Task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_CUMULATIVE not in result

    def test_cost_cumulative_trigger_at_threshold(self):
        """COST_CUMULATIVE not triggered when daily_cost == checkpoint_cost_daily."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        system.daily_cost = 15.0  # Equal to default 15.0
        goal = DailyGoal(
            goal_id="test-1",
            description="Task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.COST_CUMULATIVE not in result


class TestArchitectureTrigger:
    """Tests for ARCHITECTURE trigger detection."""

    def test_architecture_trigger_on_architecture_tag(self):
        """ARCHITECTURE triggered when tags contain 'architecture'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Redesign system",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            tags=["architecture"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.ARCHITECTURE in result

    def test_architecture_trigger_on_refactor_tag(self):
        """ARCHITECTURE triggered when tags contain 'refactor'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Refactor module",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            tags=["refactor"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.ARCHITECTURE in result

    def test_architecture_trigger_on_core_tag(self):
        """ARCHITECTURE triggered when tags contain 'core'."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Update core logic",
            priority=GoalPriority.HIGH,
            estimated_minutes=90,
            tags=["core"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.ARCHITECTURE in result

    def test_architecture_trigger_case_insensitive(self):
        """ARCHITECTURE is case-insensitive."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Arch changes",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            tags=["ARCHITECTURE", "CORE"],
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.ARCHITECTURE in result


class TestScopeChangeTrigger:
    """Tests for SCOPE_CHANGE trigger detection."""

    def test_scope_change_trigger_when_unplanned(self):
        """SCOPE_CHANGE triggered when is_unplanned is True."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Unplanned work",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            is_unplanned=True,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.SCOPE_CHANGE in result

    def test_scope_change_trigger_when_planned(self):
        """SCOPE_CHANGE not triggered when is_unplanned is False."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Planned work",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_unplanned=False,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.SCOPE_CHANGE not in result


class TestHiccupTrigger:
    """Tests for HICCUP trigger detection."""

    def test_hiccup_trigger_when_error_count_positive(self):
        """HICCUP triggered when error_count > 0."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Task with errors",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            error_count=1,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.HICCUP in result

    def test_hiccup_trigger_when_error_count_multiple(self):
        """HICCUP triggered when error_count > 1."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Task with many errors",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            error_count=5,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.HICCUP in result

    def test_hiccup_trigger_when_is_hiccup_true(self):
        """HICCUP triggered when is_hiccup is True."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Hiccup task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_hiccup=True,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.HICCUP in result

    def test_hiccup_trigger_not_triggered_no_errors_no_hiccup(self):
        """HICCUP not triggered when error_count is 0 and is_hiccup is False."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Clean task",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
            error_count=0,
            is_hiccup=False,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.HICCUP not in result


class TestMultipleTriggers:
    """Tests for multiple trigger detection."""

    def test_multiple_triggers_detected(self):
        """Multiple triggers can be detected for same goal."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="test-1",
            description="Complex task",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            tags=["ui", "architecture"],
            is_unplanned=True,
            error_count=2,
        )
        result = system._detect_triggers(goal)
        assert CheckpointTrigger.UX_CHANGE in result
        assert CheckpointTrigger.ARCHITECTURE in result
        assert CheckpointTrigger.SCOPE_CHANGE in result
        assert CheckpointTrigger.HICCUP in result

    def test_all_triggers_can_be_detected(self):
        """All trigger types can be detected together."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        system.daily_cost = 20.0  # Above threshold
        goal = DailyGoal(
            goal_id="test-1",
            description="Full trigger task",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            tags=["frontend", "core"],
            estimated_cost_usd=10.0,  # Above single threshold
            is_unplanned=True,
            error_count=1,
        )
        result = system._detect_triggers(goal)
        assert len(result) == 6
        assert CheckpointTrigger.UX_CHANGE in result
        assert CheckpointTrigger.COST_SINGLE in result
        assert CheckpointTrigger.COST_CUMULATIVE in result
        assert CheckpointTrigger.ARCHITECTURE in result
        assert CheckpointTrigger.SCOPE_CHANGE in result
        assert CheckpointTrigger.HICCUP in result


class TestConfigCostThresholds:
    """Tests for config checkpoint cost thresholds."""

    def test_config_has_checkpoint_cost_single(self):
        """ChiefOfStaffConfig has checkpoint_cost_single with default 5.0."""
        config = ChiefOfStaffConfig()
        assert hasattr(config, "checkpoint_cost_single")
        assert config.checkpoint_cost_single == 5.0

    def test_config_has_checkpoint_cost_daily(self):
        """ChiefOfStaffConfig has checkpoint_cost_daily with default 15.0."""
        config = ChiefOfStaffConfig()
        assert hasattr(config, "checkpoint_cost_daily")
        assert config.checkpoint_cost_daily == 15.0

    def test_config_cost_thresholds_from_dict(self):
        """Config cost thresholds can be set via from_dict."""
        data = {
            "checkpoint_cost_single": 10.0,
            "checkpoint_cost_daily": 25.0,
        }
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.checkpoint_cost_single == 10.0
        assert config.checkpoint_cost_daily == 25.0

    def test_config_cost_thresholds_to_dict(self):
        """Config cost thresholds are included in to_dict."""
        config = ChiefOfStaffConfig()
        data = config.to_dict()
        assert "checkpoint_cost_single" in data
        assert "checkpoint_cost_daily" in data
        assert data["checkpoint_cost_single"] == 5.0
        assert data["checkpoint_cost_daily"] == 15.0


class TestDailyCostTracking:
    """Tests for daily cost tracking in CheckpointSystem."""

    def test_checkpoint_system_has_daily_cost_attribute(self):
        """CheckpointSystem has daily_cost attribute."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        assert hasattr(system, "daily_cost")

    def test_checkpoint_system_daily_cost_default(self):
        """CheckpointSystem daily_cost defaults to 0.0."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        assert system.daily_cost == 0.0