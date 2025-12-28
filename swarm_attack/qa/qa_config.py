"""QA Configuration.

Implements spec section 5.2.5:
- QA enable/disable flag
- Default depth and timeouts
- Cost limits
- Integration flags (post_verify_qa, block_on_critical, enhance_bug_repro)
- Load from config dictionary
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from swarm_attack.qa.models import QADepth


@dataclass
class QAConfig:
    """Configuration for QA Agent.

    Controls QA behavior including:
    - Whether QA is enabled
    - Default testing depth
    - Timeouts for different depth levels
    - Cost limits
    - Integration flags for pipelines

    Attributes:
        enabled: Whether QA is enabled globally.
        default_depth: Default testing depth (STANDARD by default).
        timeout_seconds: General timeout in seconds.
        max_cost_usd: Maximum cost per session in USD.
        auto_create_bugs: Whether to auto-create bugs from findings.
        bug_severity_threshold: Minimum severity for auto-bug creation.
        base_url: Optional base URL for API testing.
        shallow_timeout: Timeout for SHALLOW depth in seconds.
        standard_timeout: Timeout for STANDARD depth in seconds.
        deep_timeout: Timeout for DEEP depth in seconds.
        post_verify_qa: Run QA after Verifier passes.
        block_on_critical: Block commit on critical findings.
        enhance_bug_repro: Use QA for bug reproduction.
    """

    enabled: bool = True
    default_depth: QADepth = QADepth.STANDARD
    timeout_seconds: int = 120
    max_cost_usd: float = 2.0
    auto_create_bugs: bool = True
    bug_severity_threshold: str = "moderate"
    base_url: Optional[str] = None

    # Depth-specific timeouts
    shallow_timeout: int = 30
    standard_timeout: int = 120
    deep_timeout: int = 300

    # Integration flags
    post_verify_qa: bool = True
    block_on_critical: bool = True
    enhance_bug_repro: bool = True

    def get_timeout_for_depth(self, depth: QADepth) -> int:
        """Get the appropriate timeout for a given depth.

        Args:
            depth: The QA depth level.

        Returns:
            Timeout in seconds for the depth.
        """
        if depth == QADepth.SHALLOW:
            return self.shallow_timeout
        elif depth == QADepth.STANDARD:
            return self.standard_timeout
        elif depth == QADepth.DEEP:
            return self.deep_timeout
        elif depth == QADepth.REGRESSION:
            return self.standard_timeout  # Same as standard
        else:
            return self.timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize the config to a dictionary.

        Returns:
            Dictionary representation of the config.
        """
        return {
            "enabled": self.enabled,
            "default_depth": self.default_depth.value,
            "timeout_seconds": self.timeout_seconds,
            "max_cost_usd": self.max_cost_usd,
            "auto_create_bugs": self.auto_create_bugs,
            "bug_severity_threshold": self.bug_severity_threshold,
            "base_url": self.base_url,
            "shallow_timeout": self.shallow_timeout,
            "standard_timeout": self.standard_timeout,
            "deep_timeout": self.deep_timeout,
            "post_verify_qa": self.post_verify_qa,
            "block_on_critical": self.block_on_critical,
            "enhance_bug_repro": self.enhance_bug_repro,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAConfig:
        """Create a QAConfig from a dictionary.

        Args:
            data: Dictionary with config data. Missing keys use defaults.

        Returns:
            QAConfig instance.
        """
        # Handle depth enum conversion
        default_depth = QADepth.STANDARD
        if "default_depth" in data:
            depth_value = data["default_depth"]
            if isinstance(depth_value, str):
                default_depth = QADepth(depth_value)
            elif isinstance(depth_value, QADepth):
                default_depth = depth_value

        return cls(
            enabled=data.get("enabled", True),
            default_depth=default_depth,
            timeout_seconds=data.get("timeout_seconds", 120),
            max_cost_usd=data.get("max_cost_usd", 2.0),
            auto_create_bugs=data.get("auto_create_bugs", True),
            bug_severity_threshold=data.get("bug_severity_threshold", "moderate"),
            base_url=data.get("base_url"),
            shallow_timeout=data.get("shallow_timeout", 30),
            standard_timeout=data.get("standard_timeout", 120),
            deep_timeout=data.get("deep_timeout", 300),
            post_verify_qa=data.get("post_verify_qa", True),
            block_on_critical=data.get("block_on_critical", True),
            enhance_bug_repro=data.get("enhance_bug_repro", True),
        )
