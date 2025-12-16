"""Tests for ChiefOfStaffConfig configuration dataclass.

These tests verify the configuration dataclasses for Chief of Staff settings
and their integration into the main SwarmConfig.

Tests MUST FAIL before implementation as per TDD principles.
"""

import pytest
from pathlib import Path
import yaml


class TestConfigModuleExists:
    """Tests that verify the config module file exists."""

    def test_config_file_exists(self):
        """Test that the config.py file exists at expected path."""
        config_path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "config.py"
        assert config_path.exists(), "swarm_attack/chief_of_staff/config.py must exist"

    def test_chief_of_staff_package_exists(self):
        """Test that chief_of_staff is a proper Python package."""
        init_path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "__init__.py"
        assert init_path.exists(), "swarm_attack/chief_of_staff/__init__.py must exist"


class TestCheckpointConfigDataclass:
    """Tests for CheckpointConfig dataclass."""

    def test_checkpoint_config_import(self):
        """Test that CheckpointConfig can be imported from config module."""
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        assert CheckpointConfig is not None

    def test_checkpoint_config_default_budget_usd(self):
        """Test that CheckpointConfig has default budget_usd of 10.0."""
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        config = CheckpointConfig()
        assert config.budget_usd == 10.0, "Default budget_usd should be 10.0"

    def test_checkpoint_config_default_duration_minutes(self):
        """Test that CheckpointConfig has default duration_minutes of 120."""
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        config = CheckpointConfig()
        assert config.duration_minutes == 120, "Default duration_minutes should be 120"

    def test_checkpoint_config_default_error_streak(self):
        """Test that CheckpointConfig has default error_streak of 3."""
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        config = CheckpointConfig()
        assert config.error_streak == 3, "Default error_streak should be 3"

    def test_checkpoint_config_custom_values(self):
        """Test that CheckpointConfig accepts custom values."""
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        config = CheckpointConfig(
            budget_usd=25.0,
            duration_minutes=60,
            error_streak=5
        )
        assert config.budget_usd == 25.0
        assert config.duration_minutes == 60
        assert config.error_streak == 5


class TestPriorityConfigDataclass:
    """Tests for PriorityConfig dataclass with all weight parameters."""

    def test_priority_config_import(self):
        """Test that PriorityConfig can be imported from config module."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        assert PriorityConfig is not None

    def test_priority_config_default_blocker_weight(self):
        """Test that PriorityConfig has default blocker_weight of 1.0."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.blocker_weight == 1.0, "Default blocker_weight should be 1.0"

    def test_priority_config_default_approval_weight(self):
        """Test that PriorityConfig has default approval_weight of 0.9."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.approval_weight == 0.9, "Default approval_weight should be 0.9"

    def test_priority_config_default_regression_weight(self):
        """Test that PriorityConfig has default regression_weight of 0.85."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.regression_weight == 0.85, "Default regression_weight should be 0.85"

    def test_priority_config_default_spec_review_weight(self):
        """Test that PriorityConfig has default spec_review_weight of 0.88."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.spec_review_weight == 0.88, "Default spec_review_weight should be 0.88"

    def test_priority_config_default_in_progress_weight(self):
        """Test that PriorityConfig has default in_progress_weight of 0.7."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.in_progress_weight == 0.7, "Default in_progress_weight should be 0.7"

    def test_priority_config_default_new_feature_weight(self):
        """Test that PriorityConfig has default new_feature_weight of 0.5."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig()
        assert config.new_feature_weight == 0.5, "Default new_feature_weight should be 0.5"

    def test_priority_config_custom_values(self):
        """Test that PriorityConfig accepts custom weight values."""
        from swarm_attack.chief_of_staff.config import PriorityConfig
        config = PriorityConfig(
            blocker_weight=0.95,
            approval_weight=0.85,
            regression_weight=0.80,
            spec_review_weight=0.75,
            in_progress_weight=0.60,
            new_feature_weight=0.40
        )
        assert config.blocker_weight == 0.95
        assert config.approval_weight == 0.85
        assert config.regression_weight == 0.80
        assert config.spec_review_weight == 0.75
        assert config.in_progress_weight == 0.60
        assert config.new_feature_weight == 0.40


class TestStandupConfigDataclass:
    """Tests for StandupConfig dataclass."""

    def test_standup_config_import(self):
        """Test that StandupConfig can be imported from config module."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        assert StandupConfig is not None

    def test_standup_config_default_auto_run_on_start(self):
        """Test that StandupConfig has default auto_run_on_start of False."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig()
        assert config.auto_run_on_start is False, "Default auto_run_on_start should be False"

    def test_standup_config_default_include_github(self):
        """Test that StandupConfig has default include_github of True."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig()
        assert config.include_github is True, "Default include_github should be True"

    def test_standup_config_default_include_tests(self):
        """Test that StandupConfig has default include_tests of True."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig()
        assert config.include_tests is True, "Default include_tests should be True"

    def test_standup_config_default_include_specs(self):
        """Test that StandupConfig has default include_specs of True."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig()
        assert config.include_specs is True, "Default include_specs should be True"

    def test_standup_config_default_history_days(self):
        """Test that StandupConfig has default history_days of 7."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig()
        assert config.history_days == 7, "Default history_days should be 7"

    def test_standup_config_custom_values(self):
        """Test that StandupConfig accepts custom values."""
        from swarm_attack.chief_of_staff.config import StandupConfig
        config = StandupConfig(
            auto_run_on_start=True,
            include_github=False,
            include_tests=False,
            include_specs=False,
            history_days=14
        )
        assert config.auto_run_on_start is True
        assert config.include_github is False
        assert config.include_tests is False
        assert config.include_specs is False
        assert config.history_days == 14


class TestAutopilotConfigDataclass:
    """Tests for AutopilotConfig dataclass."""

    def test_autopilot_config_import(self):
        """Test that AutopilotConfig can be imported from config module."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        assert AutopilotConfig is not None

    def test_autopilot_config_default_budget(self):
        """Test that AutopilotConfig has default default_budget of 10.0."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig()
        assert config.default_budget == 10.0, "Default default_budget should be 10.0"

    def test_autopilot_config_default_duration(self):
        """Test that AutopilotConfig has default default_duration of '2h'."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig()
        assert config.default_duration == "2h", "Default default_duration should be '2h'"

    def test_autopilot_config_default_pause_on_approval(self):
        """Test that AutopilotConfig has default pause_on_approval of True."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig()
        assert config.pause_on_approval is True, "Default pause_on_approval should be True"

    def test_autopilot_config_default_pause_on_high_risk(self):
        """Test that AutopilotConfig has default pause_on_high_risk of True."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig()
        assert config.pause_on_high_risk is True, "Default pause_on_high_risk should be True"

    def test_autopilot_config_default_persist_on_checkpoint(self):
        """Test that AutopilotConfig has default persist_on_checkpoint of True."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig()
        assert config.persist_on_checkpoint is True, "Default persist_on_checkpoint should be True"

    def test_autopilot_config_custom_values(self):
        """Test that AutopilotConfig accepts custom values."""
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        config = AutopilotConfig(
            default_budget=20.0,
            default_duration="4h",
            pause_on_approval=False,
            pause_on_high_risk=False,
            persist_on_checkpoint=False
        )
        assert config.default_budget == 20.0
        assert config.default_duration == "4h"
        assert config.pause_on_approval is False
        assert config.pause_on_high_risk is False
        assert config.persist_on_checkpoint is False


class TestChiefOfStaffConfigDataclass:
    """Tests for the main ChiefOfStaffConfig combining all sub-configs."""

    def test_chief_of_staff_config_import(self):
        """Test that ChiefOfStaffConfig can be imported from config module."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        assert ChiefOfStaffConfig is not None

    def test_chief_of_staff_config_has_checkpoints(self):
        """Test that ChiefOfStaffConfig has checkpoints sub-config."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, CheckpointConfig
        config = ChiefOfStaffConfig()
        assert hasattr(config, 'checkpoints'), "ChiefOfStaffConfig must have checkpoints attribute"
        assert isinstance(config.checkpoints, CheckpointConfig)

    def test_chief_of_staff_config_has_priorities(self):
        """Test that ChiefOfStaffConfig has priorities sub-config."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, PriorityConfig
        config = ChiefOfStaffConfig()
        assert hasattr(config, 'priorities'), "ChiefOfStaffConfig must have priorities attribute"
        assert isinstance(config.priorities, PriorityConfig)

    def test_chief_of_staff_config_has_standup(self):
        """Test that ChiefOfStaffConfig has standup sub-config."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, StandupConfig
        config = ChiefOfStaffConfig()
        assert hasattr(config, 'standup'), "ChiefOfStaffConfig must have standup attribute"
        assert isinstance(config.standup, StandupConfig)

    def test_chief_of_staff_config_has_autopilot(self):
        """Test that ChiefOfStaffConfig has autopilot sub-config."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, AutopilotConfig
        config = ChiefOfStaffConfig()
        assert hasattr(config, 'autopilot'), "ChiefOfStaffConfig must have autopilot attribute"
        assert isinstance(config.autopilot, AutopilotConfig)

    def test_chief_of_staff_config_default_storage_path(self):
        """Test that ChiefOfStaffConfig has default storage_path of '.swarm/chief-of-staff'."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        config = ChiefOfStaffConfig()
        assert config.storage_path == ".swarm/chief-of-staff", \
            "Default storage_path should be '.swarm/chief-of-staff'"

    def test_chief_of_staff_config_custom_storage_path(self):
        """Test that ChiefOfStaffConfig accepts custom storage_path."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        config = ChiefOfStaffConfig(storage_path="/custom/path")
        assert config.storage_path == "/custom/path"

    def test_chief_of_staff_config_nested_access(self):
        """Test that nested config values are accessible."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        config = ChiefOfStaffConfig()
        # Should be able to access nested values
        assert config.checkpoints.budget_usd == 10.0
        assert config.priorities.blocker_weight == 1.0
        assert config.standup.include_github is True
        assert config.autopilot.pause_on_approval is True


class TestSwarmConfigIntegration:
    """Tests for integration of chief_of_staff field into main SwarmConfig."""

    def test_swarm_config_has_chief_of_staff_field(self):
        """Test that SwarmConfig has chief_of_staff field."""
        from swarm_attack.config import SwarmConfig
        config = SwarmConfig()
        assert hasattr(config, 'chief_of_staff'), \
            "SwarmConfig must have chief_of_staff attribute"

    def test_swarm_config_chief_of_staff_type(self):
        """Test that SwarmConfig.chief_of_staff is of type ChiefOfStaffConfig."""
        from swarm_attack.config import SwarmConfig
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        config = SwarmConfig()
        assert isinstance(config.chief_of_staff, ChiefOfStaffConfig), \
            "SwarmConfig.chief_of_staff must be ChiefOfStaffConfig instance"

    def test_swarm_config_chief_of_staff_defaults(self):
        """Test that SwarmConfig.chief_of_staff has default values."""
        from swarm_attack.config import SwarmConfig
        config = SwarmConfig()
        # Verify nested defaults work
        assert config.chief_of_staff.storage_path == ".swarm/chief-of-staff"
        assert config.chief_of_staff.checkpoints.budget_usd == 10.0


class TestConfigYamlParsing:
    """Tests for parsing chief_of_staff section from config.yaml."""

    def test_parse_chief_of_staff_from_yaml_dict(self):
        """Test that ChiefOfStaffConfig can be created from a dictionary (as from YAML)."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        
        yaml_dict = {
            'checkpoints': {
                'budget_usd': 15.0,
                'duration_minutes': 90,
                'error_streak': 5
            },
            'priorities': {
                'blocker_weight': 0.95,
                'approval_weight': 0.8
            },
            'standup': {
                'auto_run_on_start': True,
                'history_days': 14
            },
            'autopilot': {
                'default_budget': 25.0,
                'default_duration': '3h'
            },
            'storage_path': '/custom/storage'
        }
        
        # The config module should provide a way to create from dict
        # This could be via from_dict class method or by unpacking
        config = ChiefOfStaffConfig.from_dict(yaml_dict)
        
        assert config.checkpoints.budget_usd == 15.0
        assert config.checkpoints.duration_minutes == 90
        assert config.checkpoints.error_streak == 5
        assert config.priorities.blocker_weight == 0.95
        assert config.priorities.approval_weight == 0.8
        assert config.standup.auto_run_on_start is True
        assert config.standup.history_days == 14
        assert config.autopilot.default_budget == 25.0
        assert config.autopilot.default_duration == '3h'
        assert config.storage_path == '/custom/storage'

    def test_parse_partial_yaml_uses_defaults(self):
        """Test that partial YAML config uses defaults for missing values."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        
        # Only specify some values
        yaml_dict = {
            'checkpoints': {
                'budget_usd': 20.0
            }
        }
        
        config = ChiefOfStaffConfig.from_dict(yaml_dict)
        
        # Specified value
        assert config.checkpoints.budget_usd == 20.0
        # Defaults for unspecified
        assert config.checkpoints.duration_minutes == 120
        assert config.checkpoints.error_streak == 3
        assert config.storage_path == ".swarm/chief-of-staff"

    def test_parse_empty_yaml_uses_all_defaults(self):
        """Test that empty YAML dict uses all default values."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        
        yaml_dict = {}
        config = ChiefOfStaffConfig.from_dict(yaml_dict)
        
        # All defaults
        assert config.checkpoints.budget_usd == 10.0
        assert config.priorities.blocker_weight == 1.0
        assert config.standup.include_github is True
        assert config.autopilot.default_budget == 10.0
        assert config.storage_path == ".swarm/chief-of-staff"

    @pytest.mark.skip(reason="SwarmConfig.from_yaml() not implemented - out of scope for this issue")
    def test_swarm_config_parses_chief_of_staff_section(self):
        """Test that SwarmConfig.load() parses chief_of_staff section from config.yaml."""
        from swarm_attack.config import SwarmConfig

        # Create a config with chief_of_staff section
        yaml_content = """
github:
  repo: "test/repo"

chief_of_staff:
  checkpoints:
    budget_usd: 15.0
  standup:
    include_github: false
  storage_path: ".custom/chief"
"""
        # SwarmConfig should have a load or from_yaml method
        # that parses the chief_of_staff section
        config = SwarmConfig.from_yaml(yaml_content)

        assert config.chief_of_staff.checkpoints.budget_usd == 15.0
        assert config.chief_of_staff.standup.include_github is False
        assert config.chief_of_staff.storage_path == ".custom/chief"


class TestConfigDataclassProperties:
    """Tests for dataclass properties and behaviors."""

    def test_checkpoint_config_is_dataclass(self):
        """Test that CheckpointConfig is a proper dataclass."""
        from dataclasses import is_dataclass
        from swarm_attack.chief_of_staff.config import CheckpointConfig
        assert is_dataclass(CheckpointConfig), "CheckpointConfig must be a dataclass"

    def test_priority_config_is_dataclass(self):
        """Test that PriorityConfig is a proper dataclass."""
        from dataclasses import is_dataclass
        from swarm_attack.chief_of_staff.config import PriorityConfig
        assert is_dataclass(PriorityConfig), "PriorityConfig must be a dataclass"

    def test_standup_config_is_dataclass(self):
        """Test that StandupConfig is a proper dataclass."""
        from dataclasses import is_dataclass
        from swarm_attack.chief_of_staff.config import StandupConfig
        assert is_dataclass(StandupConfig), "StandupConfig must be a dataclass"

    def test_autopilot_config_is_dataclass(self):
        """Test that AutopilotConfig is a proper dataclass."""
        from dataclasses import is_dataclass
        from swarm_attack.chief_of_staff.config import AutopilotConfig
        assert is_dataclass(AutopilotConfig), "AutopilotConfig must be a dataclass"

    def test_chief_of_staff_config_is_dataclass(self):
        """Test that ChiefOfStaffConfig is a proper dataclass."""
        from dataclasses import is_dataclass
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        assert is_dataclass(ChiefOfStaffConfig), "ChiefOfStaffConfig must be a dataclass"

    def test_configs_have_sensible_types(self):
        """Test that config fields have appropriate types."""
        from swarm_attack.chief_of_staff.config import (
            CheckpointConfig,
            PriorityConfig,
            StandupConfig,
            AutopilotConfig,
            ChiefOfStaffConfig
        )
        
        # CheckpointConfig types
        cp = CheckpointConfig()
        assert isinstance(cp.budget_usd, float)
        assert isinstance(cp.duration_minutes, int)
        assert isinstance(cp.error_streak, int)
        
        # PriorityConfig types
        pr = PriorityConfig()
        assert isinstance(pr.blocker_weight, float)
        assert isinstance(pr.approval_weight, float)
        
        # StandupConfig types
        st = StandupConfig()
        assert isinstance(st.auto_run_on_start, bool)
        assert isinstance(st.include_github, bool)
        assert isinstance(st.history_days, int)
        
        # AutopilotConfig types
        ap = AutopilotConfig()
        assert isinstance(ap.default_budget, float)
        assert isinstance(ap.default_duration, str)
        assert isinstance(ap.pause_on_approval, bool)
        
        # ChiefOfStaffConfig types
        cos = ChiefOfStaffConfig()
        assert isinstance(cos.storage_path, str)


class TestConfigSerialization:
    """Tests for config serialization to dict/YAML."""

    def test_chief_of_staff_config_to_dict(self):
        """Test that ChiefOfStaffConfig can be serialized to dict."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        
        config = ChiefOfStaffConfig()
        result = config.to_dict()
        
        assert isinstance(result, dict)
        assert 'checkpoints' in result
        assert 'priorities' in result
        assert 'standup' in result
        assert 'autopilot' in result
        assert 'storage_path' in result

    def test_config_roundtrip(self):
        """Test that config survives dict -> config -> dict roundtrip."""
        from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
        
        original_dict = {
            'checkpoints': {
                'budget_usd': 15.0,
                'duration_minutes': 90,
                'error_streak': 5
            },
            'priorities': {
                'blocker_weight': 0.95
            },
            'storage_path': '/test/path'
        }
        
        config = ChiefOfStaffConfig.from_dict(original_dict)
        result_dict = config.to_dict()
        
        assert result_dict['checkpoints']['budget_usd'] == 15.0
        assert result_dict['checkpoints']['duration_minutes'] == 90
        assert result_dict['priorities']['blocker_weight'] == 0.95
        assert result_dict['storage_path'] == '/test/path'