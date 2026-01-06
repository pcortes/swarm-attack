"""Tests for AutoFixConfig in the swarm_attack config system.

Verifies that AutoFixConfig:
- Has correct default values
- Serializes to/from dict correctly
- Integrates properly with SwarmConfig
- Is parsed correctly from YAML config
"""
import pytest
import tempfile
import os
from pathlib import Path

from swarm_attack.config import AutoFixConfig, SwarmConfig, load_config, clear_config_cache


class TestAutoFixConfigDefaults:
    """Tests for AutoFixConfig default values."""

    def test_defaults(self):
        """Test default values match spec requirements."""
        config = AutoFixConfig()
        assert config.enabled is False
        assert config.max_iterations == 3
        assert config.auto_approve is False
        assert config.dry_run is False
        assert config.watch_poll_seconds == 5

    def test_can_override_defaults(self):
        """Test that all fields can be overridden."""
        config = AutoFixConfig(
            enabled=True,
            max_iterations=5,
            auto_approve=True,
            dry_run=True,
            watch_poll_seconds=10,
        )
        assert config.enabled is True
        assert config.max_iterations == 5
        assert config.auto_approve is True
        assert config.dry_run is True
        assert config.watch_poll_seconds == 10


class TestAutoFixConfigToDict:
    """Tests for AutoFixConfig.to_dict() method."""

    def test_to_dict_default_values(self):
        """Test serialization of default values."""
        config = AutoFixConfig()
        d = config.to_dict()

        assert d["enabled"] is False
        assert d["max_iterations"] == 3
        assert d["auto_approve"] is False
        assert d["dry_run"] is False
        assert d["watch_poll_seconds"] == 5

    def test_to_dict_custom_values(self):
        """Test serialization of custom values."""
        config = AutoFixConfig(
            enabled=True,
            max_iterations=10,
            auto_approve=True,
            dry_run=True,
            watch_poll_seconds=15,
        )
        d = config.to_dict()

        assert d["enabled"] is True
        assert d["max_iterations"] == 10
        assert d["auto_approve"] is True
        assert d["dry_run"] is True
        assert d["watch_poll_seconds"] == 15

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict includes all expected fields."""
        config = AutoFixConfig()
        d = config.to_dict()

        expected_keys = {"enabled", "max_iterations", "auto_approve", "dry_run", "watch_poll_seconds"}
        assert set(d.keys()) == expected_keys


class TestAutoFixConfigFromDict:
    """Tests for AutoFixConfig.from_dict() class method."""

    def test_from_dict_full_data(self):
        """Test deserialization with all fields provided."""
        d = {
            "enabled": True,
            "max_iterations": 7,
            "auto_approve": True,
            "dry_run": True,
            "watch_poll_seconds": 20,
        }
        config = AutoFixConfig.from_dict(d)

        assert config.enabled is True
        assert config.max_iterations == 7
        assert config.auto_approve is True
        assert config.dry_run is True
        assert config.watch_poll_seconds == 20

    def test_from_dict_empty_uses_defaults(self):
        """Test deserialization from empty dict uses defaults."""
        config = AutoFixConfig.from_dict({})

        assert config.enabled is False
        assert config.max_iterations == 3
        assert config.auto_approve is False
        assert config.dry_run is False
        assert config.watch_poll_seconds == 5

    def test_from_dict_none_uses_defaults(self):
        """Test deserialization from None uses defaults."""
        config = AutoFixConfig.from_dict(None)

        assert config.enabled is False
        assert config.max_iterations == 3

    def test_from_dict_partial_data(self):
        """Test deserialization with partial data uses defaults for missing fields."""
        d = {"enabled": True, "max_iterations": 5}
        config = AutoFixConfig.from_dict(d)

        assert config.enabled is True
        assert config.max_iterations == 5
        # Defaults for unspecified fields
        assert config.auto_approve is False
        assert config.dry_run is False
        assert config.watch_poll_seconds == 5


class TestAutoFixConfigRoundTrip:
    """Tests for serialization round-trip."""

    def test_round_trip_default_values(self):
        """Test serialization round-trip with default values."""
        original = AutoFixConfig()
        restored = AutoFixConfig.from_dict(original.to_dict())
        assert original == restored

    def test_round_trip_custom_values(self):
        """Test serialization round-trip with custom values."""
        original = AutoFixConfig(
            enabled=True,
            max_iterations=8,
            auto_approve=True,
            dry_run=True,
            watch_poll_seconds=30,
        )
        restored = AutoFixConfig.from_dict(original.to_dict())
        assert original == restored


class TestSwarmConfigAutoFixIntegration:
    """Tests for AutoFixConfig integration with SwarmConfig."""

    def test_swarm_config_has_auto_fix_field(self):
        """Test that SwarmConfig has an auto_fix attribute."""
        # Use SwarmConfig default (won't be usable without config file, but can check structure)
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SwarmConfig)}
        assert "auto_fix" in fields

    def test_swarm_config_default_auto_fix(self):
        """Test that SwarmConfig default auto_fix is an AutoFixConfig instance."""
        # Create a minimal valid config for testing
        config = SwarmConfig()
        assert isinstance(config.auto_fix, AutoFixConfig)
        assert config.auto_fix.enabled is False


class TestAutoFixConfigYamlParsing:
    """Tests for parsing auto_fix section from YAML config."""

    def setup_method(self):
        """Clear config cache before each test."""
        clear_config_cache()

    def teardown_method(self):
        """Clear config cache after each test."""
        clear_config_cache()

    def test_load_config_with_auto_fix_section(self):
        """Test loading config with auto_fix section."""
        yaml_content = """
github:
  repo: "test/repo"
tests:
  command: "pytest"
auto_fix:
  enabled: true
  max_iterations: 5
  auto_approve: true
  dry_run: true
  watch_poll_seconds: 10
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(yaml_content)

            config = load_config(str(config_path), repo_root=tmpdir)

            assert config.auto_fix.enabled is True
            assert config.auto_fix.max_iterations == 5
            assert config.auto_fix.auto_approve is True
            assert config.auto_fix.dry_run is True
            assert config.auto_fix.watch_poll_seconds == 10

    def test_load_config_without_auto_fix_section(self):
        """Test loading config without auto_fix section uses defaults."""
        yaml_content = """
github:
  repo: "test/repo"
tests:
  command: "pytest"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(yaml_content)

            config = load_config(str(config_path), repo_root=tmpdir)

            assert config.auto_fix.enabled is False
            assert config.auto_fix.max_iterations == 3
            assert config.auto_fix.auto_approve is False
            assert config.auto_fix.dry_run is False
            assert config.auto_fix.watch_poll_seconds == 5

    def test_load_config_with_partial_auto_fix_section(self):
        """Test loading config with partial auto_fix section."""
        yaml_content = """
github:
  repo: "test/repo"
tests:
  command: "pytest"
auto_fix:
  enabled: true
  max_iterations: 10
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(yaml_content)

            config = load_config(str(config_path), repo_root=tmpdir)

            assert config.auto_fix.enabled is True
            assert config.auto_fix.max_iterations == 10
            # Defaults for unspecified
            assert config.auto_fix.auto_approve is False
            assert config.auto_fix.dry_run is False
            assert config.auto_fix.watch_poll_seconds == 5


class TestAutoFixConfigAccessibility:
    """Tests for accessing auto_fix config via config.auto_fix."""

    def test_access_via_config_auto_fix(self):
        """Test that config.auto_fix provides direct access."""
        yaml_content = """
github:
  repo: "test/repo"
tests:
  command: "pytest"
auto_fix:
  enabled: true
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(yaml_content)

            clear_config_cache()
            config = load_config(str(config_path), repo_root=tmpdir)

            # Should be accessible via config.auto_fix
            assert config.auto_fix is not None
            assert config.auto_fix.enabled is True

            # Should be able to access nested attributes
            assert config.auto_fix.max_iterations == 3
            clear_config_cache()
