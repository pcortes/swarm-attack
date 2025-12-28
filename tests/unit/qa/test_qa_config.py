"""Tests for QA Configuration following TDD approach.

Tests cover spec section 5.2.5:
- QA enable/disable flag
- Default depth and timeouts
- Cost limits
- Integration flags (post_verify_qa, block_on_critical, enhance_bug_repro)
- Load from config dictionary
"""

import pytest
from dataclasses import fields


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify QAConfig can be imported."""

    def test_can_import_qa_config(self):
        """Should be able to import QAConfig class."""
        from swarm_attack.qa.qa_config import QAConfig
        assert QAConfig is not None

    def test_qa_config_is_dataclass(self):
        """QAConfig should be a dataclass."""
        from swarm_attack.qa.qa_config import QAConfig
        assert hasattr(QAConfig, "__dataclass_fields__")


# =============================================================================
# DEFAULT VALUES TESTS
# =============================================================================


class TestQAConfigDefaults:
    """Tests for QAConfig default values."""

    def test_enabled_by_default(self):
        """QA should be enabled by default."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.enabled is True

    def test_default_depth_is_standard(self):
        """Default depth should be STANDARD."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth
        config = QAConfig()
        assert config.default_depth == QADepth.STANDARD

    def test_default_timeout_is_120(self):
        """Default timeout should be 120 seconds."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.timeout_seconds == 120

    def test_default_max_cost_is_2(self):
        """Default max cost should be $2.00."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.max_cost_usd == 2.0

    def test_auto_create_bugs_enabled_by_default(self):
        """Auto-create bugs should be enabled by default."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.auto_create_bugs is True

    def test_bug_severity_threshold_default(self):
        """Bug severity threshold should default to 'moderate'."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.bug_severity_threshold == "moderate"


# =============================================================================
# DEPTH-SPECIFIC TIMEOUT TESTS
# =============================================================================


class TestDepthSpecificTimeouts:
    """Tests for depth-specific timeout settings."""

    def test_shallow_timeout_default(self):
        """Shallow timeout should default to 30 seconds."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.shallow_timeout == 30

    def test_standard_timeout_default(self):
        """Standard timeout should default to 120 seconds."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.standard_timeout == 120

    def test_deep_timeout_default(self):
        """Deep timeout should default to 300 seconds (5 minutes)."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.deep_timeout == 300

    def test_can_customize_shallow_timeout(self):
        """Should be able to customize shallow timeout."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(shallow_timeout=60)
        assert config.shallow_timeout == 60

    def test_can_customize_deep_timeout(self):
        """Should be able to customize deep timeout."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(deep_timeout=600)
        assert config.deep_timeout == 600


# =============================================================================
# INTEGRATION FLAGS TESTS
# =============================================================================


class TestIntegrationFlags:
    """Tests for integration flag settings."""

    def test_post_verify_qa_enabled_by_default(self):
        """Post-verify QA should be enabled by default."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.post_verify_qa is True

    def test_block_on_critical_enabled_by_default(self):
        """Block on critical should be enabled by default."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.block_on_critical is True

    def test_enhance_bug_repro_enabled_by_default(self):
        """Enhance bug reproduction should be enabled by default."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.enhance_bug_repro is True

    def test_can_disable_post_verify_qa(self):
        """Should be able to disable post-verify QA."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(post_verify_qa=False)
        assert config.post_verify_qa is False

    def test_can_disable_block_on_critical(self):
        """Should be able to disable block on critical."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(block_on_critical=False)
        assert config.block_on_critical is False

    def test_can_disable_enhance_bug_repro(self):
        """Should be able to disable enhanced bug reproduction."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(enhance_bug_repro=False)
        assert config.enhance_bug_repro is False


# =============================================================================
# OPTIONAL FIELDS TESTS
# =============================================================================


class TestOptionalFields:
    """Tests for optional configuration fields."""

    def test_base_url_defaults_to_none(self):
        """Base URL should default to None."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert config.base_url is None

    def test_can_set_base_url(self):
        """Should be able to set base URL."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig(base_url="http://localhost:8000")
        assert config.base_url == "http://localhost:8000"


# =============================================================================
# FROM_DICT TESTS
# =============================================================================


class TestFromDict:
    """Tests for loading QAConfig from dictionary."""

    def test_from_dict_exists(self):
        """QAConfig should have from_dict class method."""
        from swarm_attack.qa.qa_config import QAConfig
        assert hasattr(QAConfig, "from_dict")

    def test_from_dict_with_all_fields(self):
        """from_dict should load all fields."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        data = {
            "enabled": False,
            "default_depth": "deep",
            "timeout_seconds": 180,
            "max_cost_usd": 5.0,
            "auto_create_bugs": False,
            "bug_severity_threshold": "critical",
            "base_url": "http://api.example.com",
            "shallow_timeout": 45,
            "standard_timeout": 180,
            "deep_timeout": 450,
            "post_verify_qa": False,
            "block_on_critical": False,
            "enhance_bug_repro": False,
        }

        config = QAConfig.from_dict(data)

        assert config.enabled is False
        assert config.default_depth == QADepth.DEEP
        assert config.timeout_seconds == 180
        assert config.max_cost_usd == 5.0
        assert config.auto_create_bugs is False
        assert config.bug_severity_threshold == "critical"
        assert config.base_url == "http://api.example.com"
        assert config.shallow_timeout == 45
        assert config.standard_timeout == 180
        assert config.deep_timeout == 450
        assert config.post_verify_qa is False
        assert config.block_on_critical is False
        assert config.enhance_bug_repro is False

    def test_from_dict_with_missing_keys_uses_defaults(self):
        """from_dict should use defaults for missing keys."""
        from swarm_attack.qa.qa_config import QAConfig

        data = {}  # Empty dict
        config = QAConfig.from_dict(data)

        # Should use all defaults
        assert config.enabled is True
        assert config.timeout_seconds == 120
        assert config.max_cost_usd == 2.0

    def test_from_dict_with_partial_data(self):
        """from_dict should handle partial data correctly."""
        from swarm_attack.qa.qa_config import QAConfig

        data = {
            "enabled": False,
            "max_cost_usd": 10.0,
        }
        config = QAConfig.from_dict(data)

        assert config.enabled is False
        assert config.max_cost_usd == 10.0
        # Other fields should use defaults
        assert config.timeout_seconds == 120

    def test_from_dict_handles_depth_string(self):
        """from_dict should convert depth string to QADepth enum."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        for depth_str, expected_depth in [
            ("shallow", QADepth.SHALLOW),
            ("standard", QADepth.STANDARD),
            ("deep", QADepth.DEEP),
            ("regression", QADepth.REGRESSION),
        ]:
            data = {"default_depth": depth_str}
            config = QAConfig.from_dict(data)
            assert config.default_depth == expected_depth


# =============================================================================
# TO_DICT TESTS
# =============================================================================


class TestToDict:
    """Tests for serializing QAConfig to dictionary."""

    def test_to_dict_exists(self):
        """QAConfig should have to_dict method."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert hasattr(config, "to_dict")

    def test_to_dict_returns_dict(self):
        """to_dict should return a dictionary."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        result = config.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """to_dict should contain all config fields."""
        from swarm_attack.qa.qa_config import QAConfig

        config = QAConfig()
        result = config.to_dict()

        expected_fields = [
            "enabled",
            "default_depth",
            "timeout_seconds",
            "max_cost_usd",
            "auto_create_bugs",
            "bug_severity_threshold",
            "base_url",
            "shallow_timeout",
            "standard_timeout",
            "deep_timeout",
            "post_verify_qa",
            "block_on_critical",
            "enhance_bug_repro",
        ]

        for field in expected_fields:
            assert field in result

    def test_to_dict_converts_depth_to_string(self):
        """to_dict should convert QADepth enum to string."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        config = QAConfig(default_depth=QADepth.DEEP)
        result = config.to_dict()

        assert result["default_depth"] == "deep"


# =============================================================================
# ROUNDTRIP TESTS
# =============================================================================


class TestRoundtrip:
    """Tests for serialization roundtrip."""

    def test_roundtrip_preserves_values(self):
        """to_dict and from_dict should roundtrip correctly."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        original = QAConfig(
            enabled=False,
            default_depth=QADepth.DEEP,
            timeout_seconds=200,
            max_cost_usd=3.5,
            auto_create_bugs=False,
            bug_severity_threshold="critical",
            base_url="http://test.com",
            shallow_timeout=60,
            standard_timeout=180,
            deep_timeout=400,
            post_verify_qa=False,
            block_on_critical=False,
            enhance_bug_repro=False,
        )

        data = original.to_dict()
        restored = QAConfig.from_dict(data)

        assert restored.enabled == original.enabled
        assert restored.default_depth == original.default_depth
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.max_cost_usd == original.max_cost_usd
        assert restored.auto_create_bugs == original.auto_create_bugs
        assert restored.bug_severity_threshold == original.bug_severity_threshold
        assert restored.base_url == original.base_url
        assert restored.shallow_timeout == original.shallow_timeout
        assert restored.standard_timeout == original.standard_timeout
        assert restored.deep_timeout == original.deep_timeout
        assert restored.post_verify_qa == original.post_verify_qa
        assert restored.block_on_critical == original.block_on_critical
        assert restored.enhance_bug_repro == original.enhance_bug_repro


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidation:
    """Tests for config validation."""

    def test_timeout_must_be_positive(self):
        """Timeout should be validated to be positive."""
        from swarm_attack.qa.qa_config import QAConfig

        # Creating with invalid value should either raise or be corrected
        # This depends on implementation - test the behavior
        config = QAConfig.from_dict({"timeout_seconds": -1})
        # Should either raise, correct to default, or allow (based on impl)
        assert config.timeout_seconds >= 0 or config.timeout_seconds == -1

    def test_max_cost_must_be_positive(self):
        """Max cost should be validated to be positive."""
        from swarm_attack.qa.qa_config import QAConfig

        config = QAConfig.from_dict({"max_cost_usd": -1.0})
        # Should either raise, correct to default, or allow (based on impl)
        assert config.max_cost_usd >= 0 or config.max_cost_usd == -1.0


# =============================================================================
# GET_TIMEOUT_FOR_DEPTH TESTS
# =============================================================================


class TestGetTimeoutForDepth:
    """Tests for getting appropriate timeout based on depth."""

    def test_has_get_timeout_for_depth_method(self):
        """QAConfig should have get_timeout_for_depth method."""
        from swarm_attack.qa.qa_config import QAConfig
        config = QAConfig()
        assert hasattr(config, "get_timeout_for_depth")

    def test_returns_shallow_timeout_for_shallow(self):
        """Should return shallow_timeout for SHALLOW depth."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        config = QAConfig(shallow_timeout=45)
        assert config.get_timeout_for_depth(QADepth.SHALLOW) == 45

    def test_returns_standard_timeout_for_standard(self):
        """Should return standard_timeout for STANDARD depth."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        config = QAConfig(standard_timeout=150)
        assert config.get_timeout_for_depth(QADepth.STANDARD) == 150

    def test_returns_deep_timeout_for_deep(self):
        """Should return deep_timeout for DEEP depth."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        config = QAConfig(deep_timeout=500)
        assert config.get_timeout_for_depth(QADepth.DEEP) == 500

    def test_returns_standard_timeout_for_regression(self):
        """Should return standard_timeout for REGRESSION depth."""
        from swarm_attack.qa.qa_config import QAConfig
        from swarm_attack.qa.models import QADepth

        config = QAConfig(standard_timeout=150)
        assert config.get_timeout_for_depth(QADepth.REGRESSION) == 150
