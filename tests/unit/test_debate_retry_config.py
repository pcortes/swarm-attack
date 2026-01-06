"""Tests for DebateRetryConfig model and configuration-based retry handling.

TDD tests (RED phase) for DebateRetryConfig dataclass that configures
retry behavior for debate agent calls. These tests should FAIL initially
because DebateRetryConfig does not exist yet.

Key requirements:
- DebateRetryConfig should be importable from swarm_attack.config.main
- Default values: max_retries=3, backoff_base_seconds=30.0, backoff_multiplier=2.0, max_backoff_seconds=300.0
- DebateRetryHandler should accept optional config parameter
- Config loader should parse debate_retry section from YAML
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Optional
import tempfile
import os

from swarm_attack.errors import (
    LLMError,
    LLMErrorType,
    RateLimitError,
)


# ============================================================================
# Test fixtures
# ============================================================================

@dataclass
class MockAgentResult:
    """Mock agent result for testing."""
    success: bool
    output: dict
    cost_usd: float = 0.0
    errors: Optional[list] = None


@pytest.fixture
def mock_agent():
    """Create a mock agent with configurable run behavior."""
    agent = Mock()
    agent.reset = Mock()
    return agent


@pytest.fixture
def rate_limit_error():
    """Create a rate limit error."""
    return RateLimitError("Rate limit exceeded. Please wait.")


@pytest.fixture
def sample_yaml_config():
    """Sample YAML config with debate_retry section."""
    return """
github:
  repo: "test/repo"

tests:
  command: "pytest"

debate_retry:
  max_retries: 5
  backoff_base_seconds: 30.0
  backoff_multiplier: 2.0
  max_backoff_seconds: 300.0
"""


# ============================================================================
# Test: DebateRetryConfig model exists with correct fields
# ============================================================================

class TestDebateRetryConfigModelExists:
    """Test that DebateRetryConfig dataclass exists and has correct fields."""

    def test_debate_retry_config_model_exists(self):
        """DebateRetryConfig should be importable from swarm_attack.config.main."""
        from swarm_attack.config.main import DebateRetryConfig

        assert DebateRetryConfig is not None

        # Should be a dataclass with the expected fields
        config = DebateRetryConfig()
        assert hasattr(config, 'max_retries')
        assert hasattr(config, 'backoff_base_seconds')
        assert hasattr(config, 'backoff_multiplier')
        assert hasattr(config, 'max_backoff_seconds')


# ============================================================================
# Test: DebateRetryConfig default values
# ============================================================================

class TestDebateRetryConfigDefaults:
    """Test that DebateRetryConfig has the correct default values."""

    def test_debate_retry_config_defaults(self):
        """Default values should be: max_retries=3, backoff_base_seconds=30.0, backoff_multiplier=2.0, max_backoff_seconds=300.0."""
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig()

        # New default values (not the old 5s/60s)
        assert config.max_retries == 3
        assert config.backoff_base_seconds == 30.0  # NOT 5.0
        assert config.backoff_multiplier == 2.0
        assert config.max_backoff_seconds == 300.0  # NOT 60.0

    def test_debate_retry_config_custom_values(self):
        """DebateRetryConfig should accept custom values."""
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=5,
            backoff_base_seconds=60.0,
            backoff_multiplier=3.0,
            max_backoff_seconds=600.0,
        )

        assert config.max_retries == 5
        assert config.backoff_base_seconds == 60.0
        assert config.backoff_multiplier == 3.0
        assert config.max_backoff_seconds == 600.0


# ============================================================================
# Test: Config loader parses debate_retry section
# ============================================================================

class TestDebateRetryConfigLoadsFromYaml:
    """Test that config loader parses debate_retry section correctly."""

    def test_debate_retry_config_loads_from_yaml(self, sample_yaml_config):
        """Config loader should parse debate_retry section from YAML."""
        from swarm_attack.config.main import load_config

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_yaml_config)
            f.flush()

            try:
                config = load_config(config_path=f.name)

                # Should have debate_retry attribute
                assert hasattr(config, 'debate_retry')

                # Should be a DebateRetryConfig instance
                from swarm_attack.config.main import DebateRetryConfig
                assert isinstance(config.debate_retry, DebateRetryConfig)

                # Should have parsed values from YAML
                assert config.debate_retry.max_retries == 5
                assert config.debate_retry.backoff_base_seconds == 30.0
                assert config.debate_retry.backoff_multiplier == 2.0
                assert config.debate_retry.max_backoff_seconds == 300.0
            finally:
                os.unlink(f.name)

    def test_debate_retry_config_uses_defaults_when_section_missing(self):
        """Config loader should use defaults when debate_retry section is missing."""
        from swarm_attack.config.main import load_config, DebateRetryConfig

        minimal_yaml = """
github:
  repo: "test/repo"

tests:
  command: "pytest"
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_yaml)
            f.flush()

            try:
                config = load_config(config_path=f.name)

                # Should have debate_retry with defaults
                assert hasattr(config, 'debate_retry')
                assert isinstance(config.debate_retry, DebateRetryConfig)
                assert config.debate_retry.max_retries == 3
                assert config.debate_retry.backoff_base_seconds == 30.0
                assert config.debate_retry.backoff_multiplier == 2.0
                assert config.debate_retry.max_backoff_seconds == 300.0
            finally:
                os.unlink(f.name)


# ============================================================================
# Test: DebateRetryHandler accepts config object
# ============================================================================

class TestDebateRetryHandlerUsesConfig:
    """Test that DebateRetryHandler accepts and uses DebateRetryConfig."""

    def test_debate_retry_handler_uses_config(self):
        """Handler should accept config object and use its values."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=5,
            backoff_base_seconds=45.0,
            backoff_multiplier=3.0,
            max_backoff_seconds=450.0,
        )

        handler = DebateRetryHandler(config=config)

        assert handler.max_retries == 5
        assert handler.backoff_base_seconds == 45.0
        assert handler.backoff_multiplier == 3.0
        assert handler.max_backoff_seconds == 450.0

    def test_debate_retry_handler_config_overrides_positional_args(self):
        """When config is provided, it should override positional args."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=10,
            backoff_base_seconds=100.0,
            backoff_multiplier=5.0,
            max_backoff_seconds=1000.0,
        )

        # Positional args should be ignored when config is provided
        handler = DebateRetryHandler(
            max_retries=1,
            backoff_base_seconds=1.0,
            backoff_multiplier=1.0,
            max_backoff_seconds=1.0,
            config=config,
        )

        # Config values should win
        assert handler.max_retries == 10
        assert handler.backoff_base_seconds == 100.0
        assert handler.backoff_multiplier == 5.0
        assert handler.max_backoff_seconds == 1000.0


# ============================================================================
# Test: Backoff sequence with new defaults (30s base)
# ============================================================================

class TestBackoffSequence:
    """Test backoff sequence calculation with new default values."""

    def test_backoff_sequence_30_60_120(self, mock_agent, rate_limit_error):
        """Backoff sequence should be 30s -> 60s -> 120s with new defaults."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig()  # Use defaults: base=30, multiplier=2

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(config=config)

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # With base=30 and multiplier=2: 30, 60, 120
        assert sleep_times == [30.0, 60.0, 120.0]

    def test_backoff_sequence_with_custom_config(self, mock_agent, rate_limit_error):
        """Backoff sequence should respect custom config values."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=4,
            backoff_base_seconds=10.0,
            backoff_multiplier=3.0,
            max_backoff_seconds=500.0,
        )

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(config=config)

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # With base=10 and multiplier=3: 10, 30, 90, 270
        assert sleep_times == [10.0, 30.0, 90.0, 270.0]


# ============================================================================
# Test: Backoff capped at max_backoff_seconds (300s)
# ============================================================================

class TestBackoffCappedAt300:
    """Test that backoff is capped at max_backoff_seconds."""

    def test_backoff_capped_at_300(self, mock_agent, rate_limit_error):
        """Backoff should never exceed 300s even with many retries."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=10,  # Many retries
            backoff_base_seconds=30.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=300.0,
        )

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(config=config)

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # All backoffs should be <= 300
        for t in sleep_times:
            assert t <= 300.0, f"Backoff {t} exceeds max of 300s"

        # With base=30, multiplier=2: 30, 60, 120, 240, 300 (capped), 300, ...
        # After 5th retry, backoff would be 480 but should be capped at 300
        assert len(sleep_times) == 10
        assert sleep_times[4] == 300.0  # 5th backoff should be capped
        assert sleep_times[9] == 300.0  # 10th backoff should be capped

    def test_backoff_capped_at_custom_max(self, mock_agent, rate_limit_error):
        """Backoff should respect custom max_backoff_seconds."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig(
            max_retries=5,
            backoff_base_seconds=100.0,
            backoff_multiplier=10.0,
            max_backoff_seconds=150.0,  # Custom cap
        )

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(config=config)

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # All backoffs should be <= 150
        for t in sleep_times:
            assert t <= 150.0, f"Backoff {t} exceeds custom max of 150s"


# ============================================================================
# Test: Backward compatibility without config
# ============================================================================

class TestBackwardCompatibleWithoutConfig:
    """Test that handler works with positional args (backward compat)."""

    def test_backward_compatible_without_config(self, mock_agent, rate_limit_error):
        """Handler should work with positional args when config is None."""
        from swarm_attack.debate_retry import DebateRetryHandler

        # Old-style instantiation (without config)
        handler = DebateRetryHandler(
            max_retries=2,
            backoff_base_seconds=5.0,
            backoff_multiplier=2.0,
            max_backoff_seconds=60.0,
        )

        assert handler.max_retries == 2
        assert handler.backoff_base_seconds == 5.0
        assert handler.backoff_multiplier == 2.0
        assert handler.max_backoff_seconds == 60.0

        # Should still work
        success_result = MockAgentResult(success=True, output={"ok": True})
        mock_agent.run.side_effect = [rate_limit_error, success_result]

        with patch('time.sleep'):
            result = handler.run_with_retry(mock_agent, {})

        assert result.success is True
        assert mock_agent.run.call_count == 2

    def test_backward_compatible_with_defaults(self):
        """Handler without any args should use module-level defaults."""
        from swarm_attack.debate_retry import DebateRetryHandler

        # Old-style: no args uses DEFAULT_* constants
        handler = DebateRetryHandler()

        # Should use the current defaults from debate_retry.py module
        # (Currently 5s/60s, will change when we implement the fix)
        assert handler.max_retries == 3
        assert handler.backoff_base_seconds > 0
        assert handler.backoff_multiplier > 0
        assert handler.max_backoff_seconds > 0

    def test_handler_signature_accepts_optional_config(self):
        """Handler __init__ should accept config: Optional[DebateRetryConfig] = None."""
        from swarm_attack.debate_retry import DebateRetryHandler
        import inspect

        sig = inspect.signature(DebateRetryHandler.__init__)
        params = sig.parameters

        # Should have config parameter
        assert 'config' in params, "DebateRetryHandler.__init__ should have 'config' parameter"

        # config should be optional (has default value of None)
        config_param = params['config']
        assert config_param.default is None, "config parameter should default to None"
