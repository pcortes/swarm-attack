"""Tests for ChiefOfStaffConfig integration into SwarmConfig.

Issue #3: Integrate ChiefOfStaffConfig into SwarmConfig

Acceptance Criteria:
- SwarmConfig has optional chief_of_staff: Optional[ChiefOfStaffConfig] field
- _parse_chief_of_staff_config() function parses the config section
- Config loading handles missing chief_of_staff section gracefully (returns None or defaults)
- Unit tests for config parsing with and without chief_of_staff section
- Integration test: load sample config.yaml with chief_of_staff section
"""

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from swarm_attack.chief_of_staff.config import (
    AutopilotConfig,
    CheckpointConfig,
    ChiefOfStaffConfig,
    PriorityConfig,
    StandupConfig,
)
from swarm_attack.config import (
    SwarmConfig,
    _parse_chief_of_staff_config,
    load_config,
)


class TestSwarmConfigHasChiefOfStaffField:
    """Test that SwarmConfig has the chief_of_staff field."""

    def test_swarm_config_has_chief_of_staff_attribute(self):
        """SwarmConfig should have chief_of_staff attribute."""
        assert hasattr(SwarmConfig, "__dataclass_fields__")
        assert "chief_of_staff" in SwarmConfig.__dataclass_fields__

    def test_chief_of_staff_field_type_is_chief_of_staff_config(self):
        """The chief_of_staff field should be of type ChiefOfStaffConfig."""
        field = SwarmConfig.__dataclass_fields__["chief_of_staff"]
        # With PEP 563 (from __future__ import annotations), field.type is a string
        # Check both string form and default_factory for type correctness
        assert field.type == "ChiefOfStaffConfig" or field.type == ChiefOfStaffConfig
        assert field.default_factory == ChiefOfStaffConfig

    def test_default_chief_of_staff_is_created(self):
        """SwarmConfig should create a default ChiefOfStaffConfig."""
        from swarm_attack.config import GitHubConfig, TestRunnerConfig

        config = SwarmConfig(
            github=GitHubConfig(repo="test/repo"),
            tests=TestRunnerConfig(command="pytest"),
        )
        assert config.chief_of_staff is not None
        assert isinstance(config.chief_of_staff, ChiefOfStaffConfig)


class TestParseChiefOfStaffConfig:
    """Test the _parse_chief_of_staff_config function."""

    def test_parse_chief_of_staff_config_exists(self):
        """The _parse_chief_of_staff_config function should exist."""
        from swarm_attack import config

        assert hasattr(config, "_parse_chief_of_staff_config")
        assert callable(config._parse_chief_of_staff_config)

    def test_parse_empty_dict_returns_defaults(self):
        """Parsing an empty dict should return ChiefOfStaffConfig with defaults."""
        result = _parse_chief_of_staff_config({})
        assert isinstance(result, ChiefOfStaffConfig)
        # Check default values
        assert result.storage_path == ".swarm/chief-of-staff"
        assert isinstance(result.checkpoints, CheckpointConfig)
        assert isinstance(result.priorities, PriorityConfig)
        assert isinstance(result.standup, StandupConfig)
        assert isinstance(result.autopilot, AutopilotConfig)

    def test_parse_full_config(self):
        """Parsing a full config dict should create ChiefOfStaffConfig with all values."""
        data: dict[str, Any] = {
            "checkpoints": {
                "budget_usd": 20.0,
                "duration_minutes": 60,
                "error_streak": 5,
            },
            "priorities": {
                "blocker_weight": 0.95,
                "approval_weight": 0.85,
                "regression_weight": 0.80,
                "spec_review_weight": 0.82,
                "in_progress_weight": 0.65,
                "new_feature_weight": 0.45,
            },
            "standup": {
                "auto_run_on_start": True,
                "include_github": False,
                "include_tests": False,
                "include_specs": False,
                "history_days": 14,
            },
            "autopilot": {
                "default_budget": 25.0,
                "default_duration": "4h",
                "pause_on_approval": False,
                "pause_on_high_risk": False,
                "persist_on_checkpoint": False,
            },
            "storage_path": ".custom/chief",
        }
        result = _parse_chief_of_staff_config(data)

        assert result.storage_path == ".custom/chief"
        assert result.checkpoints.budget_usd == 20.0
        assert result.checkpoints.duration_minutes == 60
        assert result.checkpoints.error_streak == 5
        assert result.priorities.blocker_weight == 0.95
        assert result.priorities.approval_weight == 0.85
        assert result.standup.auto_run_on_start is True
        assert result.standup.history_days == 14
        assert result.autopilot.default_budget == 25.0
        assert result.autopilot.default_duration == "4h"

    def test_parse_partial_config(self):
        """Parsing a partial config should use defaults for missing fields."""
        data = {
            "checkpoints": {"budget_usd": 15.0},
            "storage_path": ".partial/path",
        }
        result = _parse_chief_of_staff_config(data)

        # Custom values
        assert result.checkpoints.budget_usd == 15.0
        assert result.storage_path == ".partial/path"
        # Defaults
        assert result.checkpoints.duration_minutes == 120
        assert result.checkpoints.error_streak == 3
        assert result.priorities.blocker_weight == 1.0
        assert result.standup.auto_run_on_start is False
        assert result.autopilot.default_budget == 10.0


class TestLoadConfigWithChiefOfStaff:
    """Test config loading with and without chief_of_staff section."""

    def test_load_config_without_chief_of_staff_section(self, tmp_path: Path):
        """Loading config without chief_of_staff section should use defaults."""
        config_data = {
            "github": {"repo": "owner/repo"},
            "tests": {"command": "pytest"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))

        assert config.chief_of_staff is not None
        assert isinstance(config.chief_of_staff, ChiefOfStaffConfig)
        # Verify defaults
        assert config.chief_of_staff.storage_path == ".swarm/chief-of-staff"
        assert config.chief_of_staff.checkpoints.budget_usd == 10.0
        assert config.chief_of_staff.priorities.blocker_weight == 1.0
        assert config.chief_of_staff.standup.auto_run_on_start is False
        assert config.chief_of_staff.autopilot.pause_on_approval is True

    def test_load_config_with_chief_of_staff_section(self, tmp_path: Path):
        """Loading config with chief_of_staff section should parse it correctly."""
        config_data = {
            "github": {"repo": "owner/repo"},
            "tests": {"command": "pytest"},
            "chief_of_staff": {
                "storage_path": ".custom/cos",
                "checkpoints": {
                    "budget_usd": 50.0,
                    "duration_minutes": 240,
                },
                "priorities": {
                    "blocker_weight": 0.99,
                },
                "standup": {
                    "auto_run_on_start": True,
                    "history_days": 30,
                },
                "autopilot": {
                    "default_budget": 100.0,
                    "default_duration": "8h",
                },
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))

        assert config.chief_of_staff.storage_path == ".custom/cos"
        assert config.chief_of_staff.checkpoints.budget_usd == 50.0
        assert config.chief_of_staff.checkpoints.duration_minutes == 240
        assert config.chief_of_staff.priorities.blocker_weight == 0.99
        assert config.chief_of_staff.standup.auto_run_on_start is True
        assert config.chief_of_staff.standup.history_days == 30
        assert config.chief_of_staff.autopilot.default_budget == 100.0
        assert config.chief_of_staff.autopilot.default_duration == "8h"

    def test_load_config_with_empty_chief_of_staff_section(self, tmp_path: Path):
        """Loading config with empty chief_of_staff section should use defaults."""
        config_data = {
            "github": {"repo": "owner/repo"},
            "tests": {"command": "pytest"},
            "chief_of_staff": {},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))

        assert config.chief_of_staff is not None
        assert isinstance(config.chief_of_staff, ChiefOfStaffConfig)
        assert config.chief_of_staff.storage_path == ".swarm/chief-of-staff"
        assert config.chief_of_staff.checkpoints.budget_usd == 10.0

    def test_load_config_with_null_chief_of_staff_section(self, tmp_path: Path):
        """Loading config with null chief_of_staff section should use defaults."""
        config_content = """
github:
  repo: owner/repo
tests:
  command: pytest
chief_of_staff: null
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        # Should handle null gracefully and use defaults
        assert config.chief_of_staff is not None
        assert isinstance(config.chief_of_staff, ChiefOfStaffConfig)


class TestIntegrationLoadSampleConfig:
    """Integration test for loading a complete sample config.yaml."""

    def test_integration_full_config_yaml(self, tmp_path: Path):
        """Integration test: load a complete sample config.yaml with chief_of_staff section."""
        config_content = """
github:
  repo: "anthropics/swarm-attack"
  token_env_var: "GITHUB_TOKEN"

claude:
  binary: "claude"
  max_turns: 10
  timeout_seconds: 600

tests:
  command: "pytest"
  args: ["-v", "--tb=short"]

spec_debate:
  max_rounds: 3
  success_threshold: 0.85

chief_of_staff:
  storage_path: ".swarm/chief-of-staff"
  checkpoints:
    budget_usd: 25.0
    duration_minutes: 180
    error_streak: 4
  priorities:
    blocker_weight: 1.0
    approval_weight: 0.9
    regression_weight: 0.85
    spec_review_weight: 0.88
    in_progress_weight: 0.7
    new_feature_weight: 0.5
  standup:
    auto_run_on_start: true
    include_github: true
    include_tests: true
    include_specs: true
    history_days: 7
  autopilot:
    default_budget: 10.0
    default_duration: "2h"
    pause_on_approval: true
    pause_on_high_risk: true
    persist_on_checkpoint: true
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        # Verify main config
        assert config.github.repo == "anthropics/swarm-attack"
        assert config.claude.max_turns == 10
        assert config.tests.command == "pytest"
        assert "-v" in config.tests.args

        # Verify chief_of_staff config
        cos = config.chief_of_staff
        assert cos.storage_path == ".swarm/chief-of-staff"
        assert cos.checkpoints.budget_usd == 25.0
        assert cos.checkpoints.duration_minutes == 180
        assert cos.checkpoints.error_streak == 4
        assert cos.priorities.blocker_weight == 1.0
        assert cos.priorities.approval_weight == 0.9
        assert cos.standup.auto_run_on_start is True
        assert cos.standup.history_days == 7
        assert cos.autopilot.default_budget == 10.0
        assert cos.autopilot.default_duration == "2h"
        assert cos.autopilot.pause_on_approval is True


class TestChiefOfStaffConfigDefaultValues:
    """Test that default values are correctly applied."""

    def test_checkpoint_defaults(self):
        """CheckpointConfig should have correct defaults."""
        config = CheckpointConfig()
        assert config.budget_usd == 10.0
        assert config.duration_minutes == 120
        assert config.error_streak == 3

    def test_priority_defaults(self):
        """PriorityConfig should have correct defaults."""
        config = PriorityConfig()
        assert config.blocker_weight == 1.0
        assert config.approval_weight == 0.9
        assert config.regression_weight == 0.85
        assert config.spec_review_weight == 0.88
        assert config.in_progress_weight == 0.7
        assert config.new_feature_weight == 0.5

    def test_standup_defaults(self):
        """StandupConfig should have correct defaults."""
        config = StandupConfig()
        assert config.auto_run_on_start is False
        assert config.include_github is True
        assert config.include_tests is True
        assert config.include_specs is True
        assert config.history_days == 7

    def test_autopilot_defaults(self):
        """AutopilotConfig should have correct defaults."""
        config = AutopilotConfig()
        assert config.default_budget == 10.0
        assert config.default_duration == "2h"
        assert config.pause_on_approval is True
        assert config.pause_on_high_risk is True
        assert config.persist_on_checkpoint is True

    def test_chief_of_staff_defaults(self):
        """ChiefOfStaffConfig should have correct defaults."""
        config = ChiefOfStaffConfig()
        assert config.storage_path == ".swarm/chief-of-staff"
        assert isinstance(config.checkpoints, CheckpointConfig)
        assert isinstance(config.priorities, PriorityConfig)
        assert isinstance(config.standup, StandupConfig)
        assert isinstance(config.autopilot, AutopilotConfig)