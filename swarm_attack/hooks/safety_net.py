"""SafetyNetHook module for blocking destructive commands.

This module provides a safety net that blocks dangerous commands like:
- rm -rf on dangerous paths
- git push --force
- DROP TABLE / TRUNCATE / DELETE without WHERE
- Windows destructive commands (del /s /q, rd /s /q, format)
- PowerShell destructive commands

Cross-platform: Uses Python regex, no bash or subprocess dependency.
Configurable via .claude/safety-net.yaml
Override via SAFETY_NET_OVERRIDE=1 environment variable.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Pattern, Union
import logging
import os
import re

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class SafetyNetResult:
    """Result of checking a command against the safety net.

    Attributes:
        allowed: Whether the command is allowed to execute.
        overridden: Whether the command was allowed due to SAFETY_NET_OVERRIDE.
        reason: Human-readable reason for the result.
        matched_pattern: The pattern that matched (if any).
        severity: Severity level of the matched pattern (if blocked).
    """
    allowed: bool
    overridden: bool = False
    reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    severity: Optional[str] = None


class DestructiveCommandError(Exception):
    """Exception raised when a destructive command is detected.

    Attributes:
        command: The command that was blocked.
        matched_pattern: The pattern that matched the command.
        severity: The severity level of the violation.
    """

    def __init__(
        self,
        command: str,
        message: str,
        matched_pattern: Optional[str] = None,
        severity: Optional[str] = None
    ):
        self.command = command
        self.matched_pattern = matched_pattern
        self.severity = severity
        super().__init__(message)


@dataclass
class SafetyNetConfig:
    """Configuration for SafetyNetHook.

    Attributes:
        enabled: Whether the safety net is active.
        block_patterns: List of regex patterns to block.
        allow_patterns: List of regex patterns that override blocks.
        patterns: List of pattern dicts with severity and action.
    """
    enabled: bool = True
    block_patterns: List[str] = field(default_factory=list)
    allow_patterns: List[str] = field(default_factory=list)
    patterns: List[dict] = field(default_factory=list)


# Default dangerous patterns
DEFAULT_BLOCK_PATTERNS = [
    # rm -rf dangerous paths (Unix)
    r'rm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*|--force\s+--recursive|--recursive\s+--force)\s+(/|/\*|\*|~|\.\.|\$HOME|/Users/[^/\s]+)(\s|$)',
    r'rm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*|--force\s+--recursive|--recursive\s+--force)\s+(/|\*|~|\.\.)',
    # Catch standalone rm -rf / rm -fr patterns with dangerous targets
    r'\brm\s+(-rf|-fr)\s+(/\s*$|/\*|\*\s*$|~\s*$|\.\.\s*$|/Users/\w+\s*$)',
    r'\brm\s+--force\s+--recursive\s+(/\s*$|/\*|\*\s*$|~\s*$|\.\.\s*$)',
    r'\brm\s+--recursive\s+--force\s+(/\s*$|/\*|\*\s*$|~\s*$|\.\.\s*$)',

    # git push --force variants
    r'git\s+push\s+(-[a-z]*f[a-z]*|--force|--force-with-lease)',

    # SQL destructive commands
    r'(?i)\b(drop|truncate)\s+(table|database)\b',
    r'(?i)\bdelete\s+from\s+\w+\s*;',  # DELETE without WHERE

    # chmod/chown dangerous operations
    r'chmod\s+\d{3,4}\s+/',
    r'chown\s+(-[a-z]*R[a-z]*|--recursive)\s+\w+\s+/',

    # dd to disk device
    r'dd\s+.*of=/dev/(sd|hd|nvme|disk)',

    # mkfs (format filesystem)
    r'mkfs\.',

    # Windows format command
    r'\bformat\s+[A-Za-z]:',

    # git reset --hard with remote
    r'git\s+reset\s+--hard\s+(origin|upstream)/',

    # git clean with dangerous flags
    r'git\s+clean\s+(-[a-z]*f[a-z]*d[a-z]*x[a-z]*|-[a-z]*d[a-z]*f[a-z]*x[a-z]*|-[a-z]*x[a-z]*f[a-z]*d[a-z]*|-fdx|-fxd|-dfx|-dxf|-xfd|-xdf)',

    # Windows del command
    r'\bdel\s+/s\s+/q\b',
    r'\bdel\s+/q\s+/s\b',

    # Windows rd/rmdir command
    r'\b(rd|rmdir)\s+/s\s+/q\b',
    r'\b(rd|rmdir)\s+/q\s+/s\b',

    # PowerShell Remove-Item
    r'Remove-Item\s+.*-Recurse.*-Force',
    r'Remove-Item\s+.*-Force.*-Recurse',

    # xargs with rm -rf
    r'xargs\s+.*rm\s+(-rf|-fr)',
]

# Default safe patterns (override blocks)
DEFAULT_ALLOW_PATTERNS = [
    r'rm\s+(-rf|-fr)\s+(node_modules|build/|dist/|\.cache|__pycache__|\.pytest_cache|\.tox|\.venv|venv|\.git/hooks)',
    r'rm\s+(-rf|-fr)\s+/tmp/',
    r'rm\s+(-rf|-fr)\s+\./node_modules',
    r'rm\s+(-rf|-fr)\s+\./build/',
]


class SafetyNetHook:
    """Hook that blocks destructive commands from executing.

    This hook checks commands against a set of patterns before allowing
    them to execute. It can be configured via .claude/safety-net.yaml
    and overridden via the SAFETY_NET_OVERRIDE environment variable.

    Attributes:
        config: SafetyNetConfig with patterns and settings.
        repo_root: Path to repository root for config discovery.
        _logger: Optional logger for warnings/info.
        patterns: Compiled block patterns.
        _compiled_patterns: Dict of compiled regex patterns.
    """

    def __init__(
        self,
        config: Optional[SafetyNetConfig] = None,
        repo_root: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize SafetyNetHook.

        Args:
            config: Optional SafetyNetConfig. If not provided, will load from
                    .claude/safety-net.yaml or use defaults.
            repo_root: Path to repository root for config file discovery.
            logger: Optional logger for warnings.
        """
        self.repo_root = repo_root
        self._logger = logger or logging.getLogger(__name__)

        # Load config if not provided
        if config is not None:
            self.config = config
        else:
            self.config = self._load_config()

        # Compile patterns
        self._compile_patterns()

    def _load_config(self) -> SafetyNetConfig:
        """Load configuration from .claude/safety-net.yaml."""
        config = SafetyNetConfig()

        if self.repo_root is None:
            return config

        config_path = Path(self.repo_root) / ".claude" / "safety-net.yaml"

        if not config_path.exists():
            return config

        if not YAML_AVAILABLE:
            self._logger.warning(
                "PyYAML not available, using default configuration"
            )
            return config

        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                return config

            if isinstance(data, dict):
                config.enabled = data.get('enabled', True)
                config.block_patterns = data.get('block_patterns', [])
                config.allow_patterns = data.get('allow_patterns', [])
                config.patterns = data.get('patterns', [])
        except yaml.YAMLError:
            self._logger.warning(
                f"Invalid YAML in {config_path}, using defaults"
            )
        except Exception as e:
            self._logger.warning(
                f"Error loading config from {config_path}: {e}"
            )

        return config

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        self._compiled_patterns = {
            'block': [],
            'allow': [],
        }
        self.patterns = []

        # Compile default block patterns
        for pattern in DEFAULT_BLOCK_PATTERNS:
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled_patterns['block'].append((pattern, compiled, 'critical'))
                self.patterns.append(pattern)
            except re.error as e:
                self._logger.warning(f"Invalid regex pattern '{pattern}': {e}")

        # Compile custom block patterns from config
        for pattern in self.config.block_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled_patterns['block'].append((pattern, compiled, 'critical'))
                self.patterns.append(pattern)
            except re.error as e:
                self._logger.warning(f"Invalid custom block pattern '{pattern}': {e}")

        # Compile patterns with severity/action
        for pattern_config in self.config.patterns:
            if isinstance(pattern_config, dict) and 'pattern' in pattern_config:
                pattern = pattern_config['pattern']
                severity = pattern_config.get('severity', 'warning')
                action = pattern_config.get('action', 'block')
                try:
                    compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                    if action in ('block', 'warn'):
                        self._compiled_patterns['block'].append((pattern, compiled, severity))
                        self.patterns.append(pattern)
                except re.error as e:
                    self._logger.warning(f"Invalid pattern '{pattern}': {e}")

        # Compile default allow patterns
        for pattern in DEFAULT_ALLOW_PATTERNS:
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled_patterns['allow'].append((pattern, compiled))
            except re.error as e:
                self._logger.warning(f"Invalid allow pattern '{pattern}': {e}")

        # Compile custom allow patterns from config
        for pattern in self.config.allow_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled_patterns['allow'].append((pattern, compiled))
            except re.error as e:
                self._logger.warning(f"Invalid custom allow pattern '{pattern}': {e}")

    def _is_override_enabled(self) -> bool:
        """Check if SAFETY_NET_OVERRIDE environment variable is set."""
        override = os.environ.get('SAFETY_NET_OVERRIDE', '').lower()
        return override in ('1', 'true', 'yes')

    def _normalize_command(self, cmd: str) -> str:
        """Normalize command for pattern matching.

        Handles line continuations, trims whitespace, etc.
        """
        # Handle line continuations (backslash + newline)
        cmd = re.sub(r'\\\n', ' ', cmd)
        # Normalize whitespace
        cmd = ' '.join(cmd.split())
        return cmd

    def check_command(self, cmd: str) -> SafetyNetResult:
        """Check if a command is safe to execute.

        Args:
            cmd: The command string to check.

        Returns:
            SafetyNetResult indicating whether command is allowed.

        Raises:
            DestructiveCommandError: If command matches a block pattern
                                    and no override is enabled.
        """
        # Handle empty/whitespace commands
        if not cmd or not cmd.strip():
            return SafetyNetResult(allowed=True, reason="Empty command")

        # Check if safety net is disabled
        if not self.config.enabled:
            return SafetyNetResult(
                allowed=True,
                reason="Safety net disabled in config"
            )

        # Normalize the command
        normalized = self._normalize_command(cmd)

        # Check allow patterns first (safe operations)
        for pattern, compiled in self._compiled_patterns['allow']:
            if compiled.search(normalized):
                return SafetyNetResult(
                    allowed=True,
                    reason=f"Matched allow pattern: {pattern}"
                )

        # Check block patterns
        for pattern, compiled, severity in self._compiled_patterns['block']:
            if compiled.search(normalized):
                # Check for override
                if self._is_override_enabled():
                    self._logger.warning(
                        f"SAFETY_NET_OVERRIDE enabled, allowing dangerous "
                        f"command: {cmd[:100]}..."
                    )
                    return SafetyNetResult(
                        allowed=True,
                        overridden=True,
                        reason=f"Override enabled for pattern: {pattern}",
                        matched_pattern=pattern,
                        severity=severity,
                    )

                # Block the command
                raise DestructiveCommandError(
                    command=cmd,
                    message=f"Destructive command blocked: matches pattern '{pattern}'",
                    matched_pattern=pattern,
                    severity=severity,
                )

        # Command is safe
        return SafetyNetResult(
            allowed=True,
            reason="No dangerous patterns matched"
        )


__all__ = [
    'SafetyNetHook',
    'SafetyNetResult',
    'SafetyNetConfig',
    'DestructiveCommandError',
]
