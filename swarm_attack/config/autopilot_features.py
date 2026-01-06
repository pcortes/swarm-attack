"""Feature flag configuration for autopilot integration.

This module provides configuration dataclasses for enabling/disabling
autopilot features including self-healing and learning systems.

All features are disabled by default to maintain backward compatibility.
When autopilot_enabled=False, all feature checks return False regardless
of individual feature settings.

Usage:
    from swarm_attack.config.autopilot_features import AutopilotFeaturesConfig

    config = AutopilotFeaturesConfig(autopilot_enabled=True)

    if config.is_enabled("self_healing"):
        # Use self-healing hooks
        pass

    if config.is_enabled("learning"):
        # Use learning wrapper
        pass
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SelfHealingConfig:
    """Configuration for self-healing integration.

    Attributes:
        enabled: Master switch for self-healing features.
        failure_prediction_enabled: Enable failure trajectory prediction.
        escalation_enabled: Enable human-in-loop escalation.
        token_threshold: Token usage ratio threshold for warnings (0.0-1.0).
        error_threshold: Number of errors before suggesting recovery.
    """
    enabled: bool = False
    failure_prediction_enabled: bool = True
    escalation_enabled: bool = True
    token_threshold: float = 0.85
    error_threshold: int = 3

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.token_threshold <= 1.0:
            raise ValueError(f"token_threshold must be between 0.0 and 1.0, got {self.token_threshold}")
        if self.error_threshold < 0:
            raise ValueError(f"error_threshold must be non-negative, got {self.error_threshold}")


@dataclass
class LearningConfig:
    """Configuration for learning integration.

    Attributes:
        enabled: Master switch for learning features.
        episode_logging_enabled: Enable execution episode logging.
        pattern_extraction_enabled: Enable pattern extraction from history.
        strategy_optimization_enabled: Enable strategy optimization.
        min_episodes_for_patterns: Minimum episodes before extracting patterns.
        min_confidence: Minimum confidence threshold for patterns.
    """
    enabled: bool = False
    episode_logging_enabled: bool = True
    pattern_extraction_enabled: bool = True
    strategy_optimization_enabled: bool = True
    min_episodes_for_patterns: int = 5
    min_confidence: float = 0.7

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be between 0.0 and 1.0, got {self.min_confidence}")
        if self.min_episodes_for_patterns < 1:
            raise ValueError(f"min_episodes_for_patterns must be at least 1, got {self.min_episodes_for_patterns}")


@dataclass
class AutopilotFeaturesConfig:
    """Main configuration for all autopilot features.

    This is the master configuration that controls whether autopilot
    features are active. When autopilot_enabled=False, all feature
    checks return False regardless of individual settings.

    Attributes:
        autopilot_enabled: Master switch for all autopilot features.
        self_healing: Configuration for self-healing integration.
        learning: Configuration for learning integration.
    """
    autopilot_enabled: bool = False
    self_healing: SelfHealingConfig = field(default_factory=SelfHealingConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)

    def is_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled.

        Features are only enabled if:
        1. autopilot_enabled is True (master switch)
        2. The specific feature's enabled flag is True

        Args:
            feature: Feature name to check. Valid values:
                - "self_healing": Self-healing integration
                - "learning": Learning integration
                - "failure_prediction": Failure prediction (requires self_healing)
                - "escalation": Escalation management (requires self_healing)
                - "episode_logging": Episode logging (requires learning)
                - "pattern_extraction": Pattern extraction (requires learning)
                - "strategy_optimization": Strategy optimization (requires learning)

        Returns:
            True if the feature is enabled, False otherwise.

        Raises:
            ValueError: If feature name is not recognized.
        """
        # Valid feature names
        valid_features = {
            "self_healing",
            "learning",
            "failure_prediction",
            "escalation",
            "episode_logging",
            "pattern_extraction",
            "strategy_optimization",
        }

        # Always validate feature name first
        if feature not in valid_features:
            raise ValueError(f"Unknown feature: {feature}")

        if not self.autopilot_enabled:
            return False

        # Top-level features
        if feature == "self_healing":
            return self.self_healing.enabled
        elif feature == "learning":
            return self.learning.enabled

        # Self-healing sub-features
        elif feature == "failure_prediction":
            return self.self_healing.enabled and self.self_healing.failure_prediction_enabled
        elif feature == "escalation":
            return self.self_healing.enabled and self.self_healing.escalation_enabled

        # Learning sub-features
        elif feature == "episode_logging":
            return self.learning.enabled and self.learning.episode_logging_enabled
        elif feature == "pattern_extraction":
            return self.learning.enabled and self.learning.pattern_extraction_enabled
        elif feature == "strategy_optimization":
            return self.learning.enabled and self.learning.strategy_optimization_enabled

        return False  # Fallback (should never reach here)

    def get_self_healing_config(self) -> Optional[SelfHealingConfig]:
        """Get self-healing config if enabled.

        Returns:
            SelfHealingConfig if self-healing is enabled, None otherwise.
        """
        if self.is_enabled("self_healing"):
            return self.self_healing
        return None

    def get_learning_config(self) -> Optional[LearningConfig]:
        """Get learning config if enabled.

        Returns:
            LearningConfig if learning is enabled, None otherwise.
        """
        if self.is_enabled("learning"):
            return self.learning
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutopilotFeaturesConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary with configuration values.

        Returns:
            AutopilotFeaturesConfig instance.
        """
        self_healing_data = data.get("self_healing", {})
        learning_data = data.get("learning", {})

        return cls(
            autopilot_enabled=data.get("autopilot_enabled", False),
            self_healing=SelfHealingConfig(**self_healing_data) if self_healing_data else SelfHealingConfig(),
            learning=LearningConfig(**learning_data) if learning_data else LearningConfig(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary representation of the config.
        """
        return {
            "autopilot_enabled": self.autopilot_enabled,
            "self_healing": {
                "enabled": self.self_healing.enabled,
                "failure_prediction_enabled": self.self_healing.failure_prediction_enabled,
                "escalation_enabled": self.self_healing.escalation_enabled,
                "token_threshold": self.self_healing.token_threshold,
                "error_threshold": self.self_healing.error_threshold,
            },
            "learning": {
                "enabled": self.learning.enabled,
                "episode_logging_enabled": self.learning.episode_logging_enabled,
                "pattern_extraction_enabled": self.learning.pattern_extraction_enabled,
                "strategy_optimization_enabled": self.learning.strategy_optimization_enabled,
                "min_episodes_for_patterns": self.learning.min_episodes_for_patterns,
                "min_confidence": self.learning.min_confidence,
            },
        }
