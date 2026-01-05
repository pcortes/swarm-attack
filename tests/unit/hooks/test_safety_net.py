"""TDD Tests for SafetyNetHook module.

Tests cover the SafetyNetHook that blocks destructive commands:
1. Block rm -rf, git push --force, DROP TABLE patterns
2. Allow explicit override via SAFETY_NET_OVERRIDE=1 env var
3. Cross-platform: no bash dependency, works on Windows
4. Configurable via .claude/safety-net.yaml

These tests are written BEFORE implementation (TDD RED phase).
Import from swarm_attack.hooks.safety_net.
"""

import os
import pytest
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestSafetyNetImports:
    """Tests to verify SafetyNetHook can be imported."""

    def test_can_import_safety_net_hook(self):
        """Should be able to import SafetyNetHook class."""
        from swarm_attack.hooks.safety_net import SafetyNetHook
        assert SafetyNetHook is not None

    def test_can_import_safety_net_result(self):
        """Should be able to import SafetyNetResult dataclass."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        assert SafetyNetResult is not None

    def test_can_import_destructive_command_error(self):
        """Should be able to import DestructiveCommandError exception."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        assert DestructiveCommandError is not None

    def test_can_import_safety_net_config(self):
        """Should be able to import SafetyNetConfig dataclass."""
        from swarm_attack.hooks.safety_net import SafetyNetConfig
        assert SafetyNetConfig is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestSafetyNetInit:
    """Tests for SafetyNetHook initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default configuration."""
        from swarm_attack.hooks.safety_net import SafetyNetHook
        hook = SafetyNetHook()
        assert hook is not None

    def test_init_with_custom_config(self):
        """Should accept custom SafetyNetConfig."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, SafetyNetConfig
        config = SafetyNetConfig(enabled=True)
        hook = SafetyNetHook(config=config)
        assert hook.config == config

    def test_init_with_repo_root(self, tmp_path):
        """Should accept repo_root for config file discovery."""
        from swarm_attack.hooks.safety_net import SafetyNetHook
        hook = SafetyNetHook(repo_root=str(tmp_path))
        assert hook.repo_root == str(tmp_path)

    def test_init_accepts_logger(self):
        """Should accept optional logger."""
        from swarm_attack.hooks.safety_net import SafetyNetHook
        logger = MagicMock()
        hook = SafetyNetHook(logger=logger)
        assert hook._logger == logger


# =============================================================================
# BLOCKING TESTS - rm -rf patterns
# =============================================================================


class TestSafetyNetBlockingRmRf:
    """Tests that rm -rf patterns are blocked."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_blocks_rm_rf_root(self, hook):
        """Should block rm -rf /"""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /")

    def test_blocks_rm_rf_star(self, hook):
        """Should block rm -rf *"""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf *")

    def test_blocks_rm_rf_home(self, hook):
        """Should block rm -rf ~"""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf ~")

    def test_blocks_rm_rf_home_expanded(self, hook):
        """Should block rm -rf /Users/..."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /Users/philipjcortes")

    def test_blocks_rm_rf_dotdot(self, hook):
        """Should block rm -rf with parent directory traversal."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf ..")

    def test_blocks_rm_fr_variant(self, hook):
        """Should block rm -fr (alternative flag order)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -fr /")

    def test_blocks_rm_force_recursive(self, hook):
        """Should block rm --force --recursive."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm --force --recursive /")

    def test_blocks_rm_recursive_force(self, hook):
        """Should block rm --recursive --force."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm --recursive --force /")

    def test_allows_rm_rf_safe_directory(self, hook):
        """Should allow rm -rf on specific safe directory."""
        # This should pass (no exception raised)
        result = hook.check_command("rm -rf /tmp/build-artifacts")
        assert result.allowed is True

    def test_allows_rm_rf_node_modules(self, hook):
        """Should allow rm -rf node_modules (common dev pattern)."""
        result = hook.check_command("rm -rf node_modules")
        assert result.allowed is True

    def test_allows_rm_rf_build(self, hook):
        """Should allow rm -rf build/ (common dev pattern)."""
        result = hook.check_command("rm -rf build/")
        assert result.allowed is True

    def test_allows_rm_single_file(self, hook):
        """Should allow rm on single file."""
        result = hook.check_command("rm some_file.txt")
        assert result.allowed is True


# =============================================================================
# BLOCKING TESTS - git push --force patterns
# =============================================================================


class TestSafetyNetBlockingGitPushForce:
    """Tests that git push --force patterns are blocked."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_blocks_git_push_force(self, hook):
        """Should block git push --force."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git push --force")

    def test_blocks_git_push_f(self, hook):
        """Should block git push -f."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git push -f")

    def test_blocks_git_push_force_origin_main(self, hook):
        """Should block git push --force origin main."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git push --force origin main")

    def test_blocks_git_push_force_origin_master(self, hook):
        """Should block git push --force origin master."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git push --force origin master")

    def test_blocks_git_push_force_with_lease(self, hook):
        """Should block git push --force-with-lease (still risky)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git push --force-with-lease origin main")

    def test_allows_git_push(self, hook):
        """Should allow regular git push."""
        result = hook.check_command("git push")
        assert result.allowed is True

    def test_allows_git_push_origin_main(self, hook):
        """Should allow git push origin main."""
        result = hook.check_command("git push origin main")
        assert result.allowed is True

    def test_allows_git_push_upstream(self, hook):
        """Should allow git push -u origin feature-branch."""
        result = hook.check_command("git push -u origin feature-branch")
        assert result.allowed is True


# =============================================================================
# BLOCKING TESTS - DROP TABLE patterns
# =============================================================================


class TestSafetyNetBlockingDropTable:
    """Tests that DROP TABLE patterns are blocked."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_blocks_drop_table(self, hook):
        """Should block DROP TABLE."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("DROP TABLE users;")

    def test_blocks_drop_table_lowercase(self, hook):
        """Should block drop table (case insensitive)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("drop table users;")

    def test_blocks_drop_table_mixed_case(self, hook):
        """Should block DrOp TaBlE (mixed case)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("DrOp TaBlE users;")

    def test_blocks_drop_table_if_exists(self, hook):
        """Should block DROP TABLE IF EXISTS."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("DROP TABLE IF EXISTS users;")

    def test_blocks_drop_database(self, hook):
        """Should block DROP DATABASE."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("DROP DATABASE production;")

    def test_blocks_truncate_table(self, hook):
        """Should block TRUNCATE TABLE."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("TRUNCATE TABLE users;")

    def test_blocks_delete_without_where(self, hook):
        """Should block DELETE without WHERE clause."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("DELETE FROM users;")

    def test_blocks_psql_with_drop(self, hook):
        """Should block psql -c 'DROP TABLE'."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("psql -c 'DROP TABLE users;'")

    def test_blocks_mysql_with_drop(self, hook):
        """Should block mysql -e 'DROP TABLE'."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("mysql -e 'DROP TABLE users;'")

    def test_allows_select_query(self, hook):
        """Should allow SELECT queries."""
        result = hook.check_command("SELECT * FROM users;")
        assert result.allowed is True

    def test_allows_insert_query(self, hook):
        """Should allow INSERT queries."""
        result = hook.check_command("INSERT INTO users (name) VALUES ('test');")
        assert result.allowed is True

    def test_allows_delete_with_where(self, hook):
        """Should allow DELETE with WHERE clause."""
        result = hook.check_command("DELETE FROM users WHERE id = 1;")
        assert result.allowed is True


# =============================================================================
# BLOCKING TESTS - Additional dangerous patterns
# =============================================================================


class TestSafetyNetBlockingAdditional:
    """Tests for additional dangerous command patterns."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_blocks_chmod_777_root(self, hook):
        """Should block chmod 777 /."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("chmod 777 /")

    def test_blocks_chown_recursive_root(self, hook):
        """Should block chown -R on root."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("chown -R nobody /")

    def test_blocks_dd_to_disk(self, hook):
        """Should block dd to disk device."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("dd if=/dev/zero of=/dev/sda")

    def test_blocks_mkfs(self, hook):
        """Should block mkfs (format) commands."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("mkfs.ext4 /dev/sda1")

    def test_blocks_format_command_windows(self, hook):
        """Should block format command (Windows)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("format C:")

    def test_blocks_git_reset_hard_origin(self, hook):
        """Should block git reset --hard origin/main."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git reset --hard origin/main")

    def test_blocks_git_clean_fdx(self, hook):
        """Should block git clean -fdx (removes untracked files)."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("git clean -fdx")

    def test_allows_git_reset_soft(self, hook):
        """Should allow git reset --soft."""
        result = hook.check_command("git reset --soft HEAD~1")
        assert result.allowed is True


# =============================================================================
# OVERRIDE TESTS
# =============================================================================


class TestSafetyNetOverride:
    """Tests for the SAFETY_NET_OVERRIDE environment variable."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_override_allows_rm_rf(self, hook):
        """Should allow rm -rf when SAFETY_NET_OVERRIDE=1."""
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "1"}):
            result = hook.check_command("rm -rf /")
            assert result.allowed is True
            assert result.overridden is True

    def test_override_allows_git_push_force(self, hook):
        """Should allow git push --force when SAFETY_NET_OVERRIDE=1."""
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "1"}):
            result = hook.check_command("git push --force")
            assert result.allowed is True
            assert result.overridden is True

    def test_override_allows_drop_table(self, hook):
        """Should allow DROP TABLE when SAFETY_NET_OVERRIDE=1."""
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "1"}):
            result = hook.check_command("DROP TABLE users;")
            assert result.allowed is True
            assert result.overridden is True

    def test_override_case_insensitive_true(self, hook):
        """Should accept SAFETY_NET_OVERRIDE=TRUE."""
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "TRUE"}):
            result = hook.check_command("rm -rf /")
            assert result.allowed is True

    def test_override_accepts_yes(self, hook):
        """Should accept SAFETY_NET_OVERRIDE=yes."""
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "yes"}):
            result = hook.check_command("rm -rf /")
            assert result.allowed is True

    def test_override_zero_does_not_override(self, hook):
        """Should NOT override when SAFETY_NET_OVERRIDE=0."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "0"}):
            with pytest.raises(DestructiveCommandError):
                hook.check_command("rm -rf /")

    def test_override_false_does_not_override(self, hook):
        """Should NOT override when SAFETY_NET_OVERRIDE=false."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "false"}):
            with pytest.raises(DestructiveCommandError):
                hook.check_command("rm -rf /")

    def test_override_empty_does_not_override(self, hook):
        """Should NOT override when SAFETY_NET_OVERRIDE is empty."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": ""}):
            with pytest.raises(DestructiveCommandError):
                hook.check_command("rm -rf /")

    def test_override_logs_warning(self, hook):
        """Should log a warning when override is used."""
        logger = MagicMock()
        from swarm_attack.hooks.safety_net import SafetyNetHook
        hook = SafetyNetHook(logger=logger)
        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "1"}):
            hook.check_command("rm -rf /")
            logger.warning.assert_called()


# =============================================================================
# CONFIG FILE TESTS
# =============================================================================


class TestSafetyNetConfig:
    """Tests for configuration file loading."""

    def test_loads_config_from_yaml(self, tmp_path):
        """Should load configuration from .claude/safety-net.yaml."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        # Create config directory and file
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: true
block_patterns:
  - "rm -rf /"
  - "git push --force"
allow_patterns:
  - "rm -rf node_modules"
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        assert hook.config.enabled is True

    def test_config_custom_block_patterns(self, tmp_path):
        """Should use custom block patterns from config."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, DestructiveCommandError

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: true
block_patterns:
  - "custom_dangerous_command"
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        with pytest.raises(DestructiveCommandError):
            hook.check_command("custom_dangerous_command --execute")

    def test_config_custom_allow_patterns(self, tmp_path):
        """Should respect custom allow patterns from config."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: true
allow_patterns:
  - "rm -rf /custom/safe/path"
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        result = hook.check_command("rm -rf /custom/safe/path")
        assert result.allowed is True

    def test_config_disabled_allows_all(self, tmp_path):
        """Should allow all commands when enabled: false in config."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: false
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        result = hook.check_command("rm -rf /")
        assert result.allowed is True

    def test_config_missing_uses_defaults(self, tmp_path):
        """Should use default patterns when config file is missing."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, DestructiveCommandError

        hook = SafetyNetHook(repo_root=str(tmp_path))
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /")

    def test_config_invalid_yaml_uses_defaults(self, tmp_path):
        """Should use defaults when config file has invalid YAML."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, DestructiveCommandError

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("invalid: yaml: content: [}")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /")

    def test_config_severity_levels(self, tmp_path):
        """Should support severity levels for patterns."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: true
patterns:
  - pattern: "rm -rf /"
    severity: critical
    action: block
  - pattern: "git push --force"
    severity: warning
    action: warn
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        assert hook.config is not None


# =============================================================================
# CROSS-PLATFORM TESTS
# =============================================================================


class TestSafetyNetCrossPlatform:
    """Tests for cross-platform compatibility (no bash dependency)."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_uses_python_regex_not_bash(self, hook):
        """Should use Python regex, not subprocess/bash."""
        # Internal implementation should use re module, not subprocess
        assert hasattr(hook, '_compiled_patterns') or hasattr(hook, 'patterns')

    def test_works_on_windows_paths(self, hook):
        """Should handle Windows-style paths."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command(r"del /s /q C:\Users")

    def test_blocks_windows_del_command(self, hook):
        """Should block Windows del /s /q."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("del /s /q *.*")

    def test_blocks_windows_rd_command(self, hook):
        """Should block Windows rd /s /q."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rd /s /q C:\\")

    def test_blocks_windows_rmdir_command(self, hook):
        """Should block Windows rmdir /s /q."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rmdir /s /q C:\\Windows")

    def test_blocks_powershell_remove_item(self, hook):
        """Should block PowerShell Remove-Item -Recurse -Force."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("Remove-Item -Recurse -Force C:\\")

    def test_no_subprocess_calls(self, hook):
        """Should not use subprocess module internally."""
        import subprocess
        original_run = subprocess.run
        subprocess.run = MagicMock(side_effect=AssertionError("subprocess.run should not be called"))
        try:
            result = hook.check_command("echo hello")
            assert result.allowed is True
        finally:
            subprocess.run = original_run

    def test_no_os_system_calls(self, hook):
        """Should not use os.system internally."""
        original_system = os.system
        os.system = MagicMock(side_effect=AssertionError("os.system should not be called"))
        try:
            result = hook.check_command("echo hello")
            assert result.allowed is True
        finally:
            os.system = original_system

    def test_handles_unicode_commands(self, hook):
        """Should handle unicode characters in commands."""
        result = hook.check_command("echo 'Hello \u4e16\u754c'")
        assert result.allowed is True

    def test_handles_empty_command(self, hook):
        """Should handle empty command string."""
        result = hook.check_command("")
        assert result.allowed is True

    def test_handles_whitespace_only_command(self, hook):
        """Should handle whitespace-only command."""
        result = hook.check_command("   ")
        assert result.allowed is True


# =============================================================================
# RESULT OBJECT TESTS
# =============================================================================


class TestSafetyNetResult:
    """Tests for SafetyNetResult dataclass."""

    def test_result_has_allowed_field(self):
        """SafetyNetResult should have 'allowed' field."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=True)
        assert hasattr(result, 'allowed')
        assert result.allowed is True

    def test_result_has_overridden_field(self):
        """SafetyNetResult should have 'overridden' field."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=True, overridden=True)
        assert hasattr(result, 'overridden')
        assert result.overridden is True

    def test_result_has_reason_field(self):
        """SafetyNetResult should have 'reason' field."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=False, reason="Blocked: rm -rf detected")
        assert hasattr(result, 'reason')
        assert "rm -rf" in result.reason

    def test_result_has_matched_pattern_field(self):
        """SafetyNetResult should have 'matched_pattern' field."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=False, matched_pattern="rm -rf /")
        assert hasattr(result, 'matched_pattern')

    def test_result_has_severity_field(self):
        """SafetyNetResult should have 'severity' field."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=False, severity="critical")
        assert hasattr(result, 'severity')
        assert result.severity == "critical"

    def test_result_defaults(self):
        """SafetyNetResult should have sensible defaults."""
        from swarm_attack.hooks.safety_net import SafetyNetResult
        result = SafetyNetResult(allowed=True)
        assert result.overridden is False
        assert result.reason is None or result.reason == ""
        assert result.matched_pattern is None


# =============================================================================
# ERROR OBJECT TESTS
# =============================================================================


class TestDestructiveCommandError:
    """Tests for DestructiveCommandError exception."""

    def test_error_is_exception(self):
        """DestructiveCommandError should be an Exception."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        assert issubclass(DestructiveCommandError, Exception)

    def test_error_has_command_field(self):
        """DestructiveCommandError should store the command."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        error = DestructiveCommandError("rm -rf /", "Destructive command blocked")
        assert error.command == "rm -rf /"

    def test_error_has_pattern_field(self):
        """DestructiveCommandError should store the matched pattern."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        error = DestructiveCommandError(
            "rm -rf /",
            "Destructive command blocked",
            matched_pattern="rm -rf /"
        )
        assert error.matched_pattern == "rm -rf /"

    def test_error_message_includes_command(self):
        """Error message should include the blocked command."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        error = DestructiveCommandError("rm -rf /", "Blocked destructive command")
        assert "rm -rf /" in str(error) or "Blocked" in str(error)

    def test_error_has_severity(self):
        """DestructiveCommandError should have severity field."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        error = DestructiveCommandError(
            "rm -rf /",
            "Blocked",
            severity="critical"
        )
        assert error.severity == "critical"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestSafetyNetIntegration:
    """Integration tests for SafetyNetHook."""

    def test_full_flow_block_and_raise(self, tmp_path):
        """Test complete flow: command blocked, exception raised."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, DestructiveCommandError

        hook = SafetyNetHook(repo_root=str(tmp_path))

        with pytest.raises(DestructiveCommandError) as exc_info:
            hook.check_command("rm -rf /")

        error = exc_info.value
        assert "rm -rf" in str(error).lower() or "destructive" in str(error).lower()

    def test_full_flow_override_with_env(self, tmp_path):
        """Test complete flow: command allowed with override."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        hook = SafetyNetHook(repo_root=str(tmp_path))

        with patch.dict(os.environ, {"SAFETY_NET_OVERRIDE": "1"}):
            result = hook.check_command("rm -rf /")
            assert result.allowed is True
            assert result.overridden is True

    def test_full_flow_config_file_override(self, tmp_path):
        """Test complete flow: config file allows specific pattern."""
        from swarm_attack.hooks.safety_net import SafetyNetHook

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "safety-net.yaml"
        config_file.write_text("""
enabled: true
allow_patterns:
  - "rm -rf /tmp/test-cleanup"
""")

        hook = SafetyNetHook(repo_root=str(tmp_path))
        result = hook.check_command("rm -rf /tmp/test-cleanup")
        assert result.allowed is True

    def test_multiple_commands_in_sequence(self):
        """Should check multiple commands independently."""
        from swarm_attack.hooks.safety_net import SafetyNetHook, DestructiveCommandError

        hook = SafetyNetHook()

        # First command: allowed
        result1 = hook.check_command("echo hello")
        assert result1.allowed is True

        # Second command: blocked
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /")

        # Third command: allowed
        result3 = hook.check_command("ls -la")
        assert result3.allowed is True


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestSafetyNetEdgeCases:
    """Edge case tests for SafetyNetHook."""

    @pytest.fixture
    def hook(self):
        from swarm_attack.hooks.safety_net import SafetyNetHook
        return SafetyNetHook()

    def test_command_with_leading_whitespace(self, hook):
        """Should detect dangerous command with leading whitespace."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("   rm -rf /")

    def test_command_with_trailing_whitespace(self, hook):
        """Should detect dangerous command with trailing whitespace."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /   ")

    def test_command_in_subshell(self, hook):
        """Should detect dangerous command in subshell."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("$(rm -rf /)")

    def test_command_in_backticks(self, hook):
        """Should detect dangerous command in backticks."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("`rm -rf /`")

    def test_command_chained_with_and(self, hook):
        """Should detect dangerous command chained with &&."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("echo hello && rm -rf /")

    def test_command_chained_with_or(self, hook):
        """Should detect dangerous command chained with ||."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("echo hello || rm -rf /")

    def test_command_chained_with_semicolon(self, hook):
        """Should detect dangerous command chained with ;."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("echo hello; rm -rf /")

    def test_command_piped(self, hook):
        """Should detect dangerous command in pipe."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("cat file.txt | xargs rm -rf")

    def test_command_with_env_prefix(self, hook):
        """Should detect dangerous command with env prefix."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("FORCE=1 rm -rf /")

    def test_command_with_sudo(self, hook):
        """Should detect dangerous command with sudo."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("sudo rm -rf /")

    def test_very_long_command(self, hook):
        """Should handle very long commands."""
        long_command = "echo " + "a" * 10000
        result = hook.check_command(long_command)
        assert result.allowed is True

    def test_null_bytes_in_command(self, hook):
        """Should handle null bytes in command."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm -rf /\x00")

    def test_newlines_in_command(self, hook):
        """Should detect dangerous command spanning newlines."""
        from swarm_attack.hooks.safety_net import DestructiveCommandError
        with pytest.raises(DestructiveCommandError):
            hook.check_command("rm \\\n-rf \\\n/")
