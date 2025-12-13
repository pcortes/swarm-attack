"""
Configuration loading and validation for Feature Swarm.

This module handles:
- Loading config.yaml from the repo root
- Environment variable resolution (${VAR} syntax)
- Validation of required fields
- Default values for optional fields
- Caching of the loaded configuration
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


@dataclass
class GitHubConfig:
    """GitHub repository configuration."""
    repo: str                                  # Repository in "owner/repo" format
    token_env_var: str = "GITHUB_TOKEN"        # Environment variable containing PAT

    def get_token(self) -> str:
        """Get the GitHub token from environment."""
        token = os.environ.get(self.token_env_var, "")
        if not token:
            raise ConfigError(f"Environment variable {self.token_env_var} is not set")
        return token


@dataclass
class ClaudeConfig:
    """Claude Code CLI configuration."""
    binary: str = "claude"                     # Path to claude binary
    max_turns: int = 6                         # Maximum conversation turns
    timeout_seconds: int = 300                 # Command timeout in seconds


@dataclass
class OpenAIConfig:
    """OpenAI API configuration for GPT-5 (DEPRECATED - use CodexConfig)."""
    api_key_env_var: str = "OPENAI_API_KEY"    # Environment variable containing API key
    model: str = "gpt-5"                       # Model to use
    reasoning_effort: str = "medium"           # Default reasoning effort
    max_output_tokens: int = 3000              # Default max output tokens
    timeout_seconds: int = 120                 # Request timeout in seconds

    def get_api_key(self) -> str:
        """Get the OpenAI API key from environment."""
        api_key = os.environ.get(self.api_key_env_var, "")
        if not api_key:
            raise ConfigError(f"Environment variable {self.api_key_env_var} is not set")
        return api_key


@dataclass
class CodexConfig:
    """Codex CLI configuration for independent review agents."""
    binary: str = "codex"                      # Path to codex binary
    model: str = "gpt-5.1-codex"               # Model to use
    sandbox_mode: str = "read-only"            # Default sandbox mode
    timeout_seconds: int = 120                 # Command timeout in seconds


@dataclass
class RetryConfig:
    """Retry strategy configuration for LLM clients."""
    max_retries: int = 3                       # Maximum retry attempts
    base_delay_seconds: float = 1.0            # Base delay between retries
    max_delay_seconds: float = 60.0            # Maximum delay between retries
    exponential_backoff: bool = True           # Use exponential backoff
    checkpoint_before_call: bool = True        # Save state before each LLM call


@dataclass
class PreflightConfig:
    """Pre-flight check configuration."""
    enabled: bool = True                       # Whether to run pre-flight checks
    check_cli_exists: bool = True              # Check if CLI binaries exist
    check_codex_auth: bool = True              # Check Codex authentication
    check_codex_account_match: bool = False    # Verify expected Codex account
    expected_codex_email: str = ""             # Expected Codex account email
    fail_on_mismatch: bool = False             # Fail if account doesn't match


@dataclass
class SpecDebateConfig:
    """Spec debate/generation configuration."""
    max_rounds: int = 5                        # Maximum debate rounds
    timeout_seconds: int = 900                 # 15 minute timeout per debate round (large specs)
    consecutive_stalemate_threshold: int = 2   # Rounds of no improvement before stalemate
    disagreement_threshold: int = 2            # Rejected issues before flagging disagreement
    rubric_thresholds: dict[str, float] = field(default_factory=lambda: {
        "clarity": 0.8,
        "coverage": 0.8,
        "architecture": 0.8,
        "risk": 0.7,
    })


@dataclass
class SessionConfig:
    """Session management configuration."""
    stale_timeout_minutes: int = 30            # Minutes before a session is considered stale
    max_implementation_retries: int = 3        # Maximum retries for failed implementations


@dataclass
class TestRunnerConfig:
    """Test execution configuration."""
    command: str                               # Test command (required, e.g., "pytest")
    args: list[str] = field(default_factory=list)  # Additional arguments
    autodetect: bool = False                   # Whether to auto-detect test framework
    timeout_seconds: int = 300                 # Timeout for test execution in seconds


@dataclass
class GitConfig:
    """Git configuration for branching and worktrees."""
    base_branch: str = "main"                  # Base branch for features
    feature_branch_pattern: str = "feature/{feature_slug}"  # Branch naming pattern
    use_worktrees: bool = True                 # Whether to use git worktrees
    worktrees_root: str = ".swarm/worktrees"   # Where to create worktrees


@dataclass
class BugDebateConfig:
    """Bug Bash debate layer configuration."""
    enabled: bool = True                        # Enable debate for root cause and fix plan
    max_rounds: int = 2                         # Maximum debate rounds (10 min each)
    timeout_seconds: int = 600                  # 10 minute timeout per debate round
    root_cause_thresholds: dict[str, float] = field(default_factory=lambda: {
        "evidence_quality": 0.8,
        "hypothesis_correctness": 0.8,
        "completeness": 0.8,
        "alternative_consideration": 0.7,
    })
    fix_plan_thresholds: dict[str, float] = field(default_factory=lambda: {
        "correctness": 0.8,
        "completeness": 0.8,
        "risk_assessment": 0.8,
        "test_coverage": 0.8,
        "side_effect_analysis": 0.7,
    })


@dataclass
class BugBashConfig:
    """Bug Bash pipeline configuration."""
    max_cost_per_bug_usd: float = 10.0         # Maximum cost for a single bug investigation
    max_reproduction_attempts: int = 3          # Max attempts to reproduce a bug
    min_test_cases: int = 2                     # Minimum test cases required in fix plan
    require_approval: bool = True               # Require human approval before fix (ALWAYS True)
    auto_commit_fixes: bool = False             # Auto-commit fixes after verification
    bugs_dir: str = ".swarm/bugs"              # Where to store bug state
    debate: BugDebateConfig = field(default_factory=BugDebateConfig)


@dataclass
class SwarmConfig:
    """
    Main configuration for Feature Swarm.

    This is the top-level config loaded from config.yaml.
    """
    # Paths
    repo_root: str = "."
    specs_dir: str = "specs"
    swarm_dir: str = ".swarm"

    # Nested configurations
    github: GitHubConfig = field(default_factory=lambda: GitHubConfig(repo=""))
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)  # DEPRECATED
    codex: CodexConfig = field(default_factory=CodexConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    preflight: PreflightConfig = field(default_factory=PreflightConfig)
    spec_debate: SpecDebateConfig = field(default_factory=SpecDebateConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    tests: TestRunnerConfig = field(default_factory=lambda: TestRunnerConfig(command=""))
    git: GitConfig = field(default_factory=GitConfig)
    bug_bash: BugBashConfig = field(default_factory=BugBashConfig)

    def __post_init__(self) -> None:
        """Convert paths to absolute paths based on repo_root."""
        self.repo_root = str(Path(self.repo_root).absolute())

    @property
    def specs_path(self) -> Path:
        """Absolute path to specs directory."""
        return Path(self.repo_root) / self.specs_dir

    @property
    def swarm_path(self) -> Path:
        """Absolute path to .swarm directory."""
        return Path(self.repo_root) / self.swarm_dir

    @property
    def state_path(self) -> Path:
        """Absolute path to state directory."""
        return self.swarm_path / "state"

    @property
    def sessions_path(self) -> Path:
        """Absolute path to sessions directory."""
        return self.swarm_path / "sessions"

    @property
    def logs_path(self) -> Path:
        """Absolute path to logs directory."""
        return self.swarm_path / "logs"


# Module-level cache for the loaded configuration
_config_cache: Optional[SwarmConfig] = None


def _resolve_env_vars(value: Any) -> Any:
    """
    Resolve environment variables in a value.

    Supports ${VAR} syntax for environment variable substitution.
    Returns the original value if it's not a string.
    """
    if isinstance(value, str):
        # Pattern matches ${VAR_NAME}
        pattern = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')

        def replace(match: re.Match) -> str:
            var_name = match.group(1)
            env_value = os.environ.get(var_name)
            if env_value is None:
                raise ConfigError(f"Environment variable ${{{var_name}}} is not set")
            return env_value

        return pattern.sub(replace, value)

    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]

    return value


def _parse_github_config(data: dict[str, Any]) -> GitHubConfig:
    """Parse GitHub configuration from dict."""
    if not data.get("repo"):
        raise ConfigError("github.repo is required")
    return GitHubConfig(
        repo=data["repo"],
        token_env_var=data.get("token_env_var", "GITHUB_TOKEN")
    )


def _parse_claude_config(data: dict[str, Any]) -> ClaudeConfig:
    """Parse Claude configuration from dict."""
    return ClaudeConfig(
        binary=data.get("binary", "claude"),
        max_turns=data.get("max_turns", 6),
        timeout_seconds=data.get("timeout_seconds", 300)
    )


def _parse_openai_config(data: dict[str, Any]) -> OpenAIConfig:
    """Parse OpenAI configuration from dict (DEPRECATED)."""
    return OpenAIConfig(
        api_key_env_var=data.get("api_key_env_var", "OPENAI_API_KEY"),
        model=data.get("model", "gpt-5"),
        reasoning_effort=data.get("reasoning_effort", "medium"),
        max_output_tokens=data.get("max_output_tokens", 3000),
        timeout_seconds=data.get("timeout_seconds", 120),
    )


def _parse_codex_config(data: dict[str, Any]) -> CodexConfig:
    """Parse Codex configuration from dict."""
    return CodexConfig(
        binary=data.get("binary", "codex"),
        model=data.get("model", "gpt-5.1-codex"),
        sandbox_mode=data.get("sandbox_mode", "read-only"),
        timeout_seconds=data.get("timeout_seconds", 120),
    )


def _parse_retry_config(data: dict[str, Any]) -> RetryConfig:
    """Parse retry configuration from dict."""
    return RetryConfig(
        max_retries=data.get("max_retries", 3),
        base_delay_seconds=data.get("base_delay_seconds", 1.0),
        max_delay_seconds=data.get("max_delay_seconds", 60.0),
        exponential_backoff=data.get("exponential_backoff", True),
        checkpoint_before_call=data.get("checkpoint_before_call", True),
    )


def _parse_preflight_config(data: dict[str, Any]) -> PreflightConfig:
    """Parse preflight configuration from dict."""
    return PreflightConfig(
        enabled=data.get("enabled", True),
        check_cli_exists=data.get("check_cli_exists", True),
        check_codex_auth=data.get("check_codex_auth", True),
        check_codex_account_match=data.get("check_codex_account_match", False),
        expected_codex_email=data.get("expected_codex_email", ""),
        fail_on_mismatch=data.get("fail_on_mismatch", False),
    )


def _parse_spec_debate_config(data: dict[str, Any]) -> SpecDebateConfig:
    """Parse spec debate configuration from dict."""
    default_thresholds = {
        "clarity": 0.8,
        "coverage": 0.8,
        "architecture": 0.8,
        "risk": 0.7,
    }
    thresholds = data.get("rubric_thresholds", default_thresholds)
    return SpecDebateConfig(
        max_rounds=data.get("max_rounds", 5),
        timeout_seconds=data.get("timeout_seconds", 900),  # 15 minutes default
        consecutive_stalemate_threshold=data.get("consecutive_stalemate_threshold", 2),
        disagreement_threshold=data.get("disagreement_threshold", 2),
        rubric_thresholds={**default_thresholds, **thresholds}
    )


def _parse_session_config(data: dict[str, Any]) -> SessionConfig:
    """Parse session configuration from dict."""
    return SessionConfig(
        stale_timeout_minutes=data.get("stale_timeout_minutes", 30),
        max_implementation_retries=data.get("max_implementation_retries", 3)
    )


def _parse_tests_config(data: dict[str, Any]) -> TestRunnerConfig:
    """Parse tests configuration from dict."""
    if not data.get("command"):
        raise ConfigError("tests.command is required")
    return TestRunnerConfig(
        command=data["command"],
        args=data.get("args", []),
        autodetect=data.get("autodetect", False)
    )


def _parse_git_config(data: dict[str, Any]) -> GitConfig:
    """Parse git configuration from dict."""
    return GitConfig(
        base_branch=data.get("base_branch", "main"),
        feature_branch_pattern=data.get("feature_branch_pattern", "feature/{feature_slug}"),
        use_worktrees=data.get("use_worktrees", True),
        worktrees_root=data.get("worktrees_root", ".swarm/worktrees")
    )


def _parse_bug_debate_config(data: dict[str, Any]) -> BugDebateConfig:
    """Parse bug debate configuration from dict."""
    default_rc_thresholds = {
        "evidence_quality": 0.8,
        "hypothesis_correctness": 0.8,
        "completeness": 0.8,
        "alternative_consideration": 0.7,
    }
    default_fp_thresholds = {
        "correctness": 0.8,
        "completeness": 0.8,
        "risk_assessment": 0.8,
        "test_coverage": 0.8,
        "side_effect_analysis": 0.7,
    }
    return BugDebateConfig(
        enabled=data.get("enabled", True),
        max_rounds=data.get("max_rounds", 2),
        timeout_seconds=data.get("timeout_seconds", 600),  # 10 minutes
        root_cause_thresholds={**default_rc_thresholds, **data.get("root_cause_thresholds", {})},
        fix_plan_thresholds={**default_fp_thresholds, **data.get("fix_plan_thresholds", {})},
    )


def _parse_bug_bash_config(data: dict[str, Any]) -> BugBashConfig:
    """Parse bug bash configuration from dict."""
    debate_data = data.get("debate", {})
    return BugBashConfig(
        max_cost_per_bug_usd=data.get("max_cost_per_bug_usd", 10.0),
        max_reproduction_attempts=data.get("max_reproduction_attempts", 3),
        min_test_cases=data.get("min_test_cases", 2),
        require_approval=True,  # Always require approval - cannot be disabled
        auto_commit_fixes=data.get("auto_commit_fixes", False),
        bugs_dir=data.get("bugs_dir", ".swarm/bugs"),
        debate=_parse_bug_debate_config(debate_data),
    )


def load_config(config_path: Optional[str] = None) -> SwarmConfig:
    """
    Load configuration from config.yaml.

    Args:
        config_path: Optional path to config file. If not provided,
                     looks for config.yaml in current directory.

    Returns:
        SwarmConfig: Loaded and validated configuration.

    Raises:
        ConfigError: If config is invalid or cannot be loaded.
    """
    if config_path is None:
        config_path = "config.yaml"

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(path, "r") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}")

    if not raw_data:
        raise ConfigError("Configuration file is empty")

    # Resolve environment variables
    data = _resolve_env_vars(raw_data)

    # Validate required sections
    if "github" not in data:
        raise ConfigError("Missing required section: github")
    if "tests" not in data:
        raise ConfigError("Missing required section: tests")

    # Parse nested configurations
    github_config = _parse_github_config(data.get("github", {}))
    claude_config = _parse_claude_config(data.get("claude", {}))
    openai_config = _parse_openai_config(data.get("openai", {}))
    codex_config = _parse_codex_config(data.get("codex", {}))
    retry_config = _parse_retry_config(data.get("retry", {}))
    preflight_config = _parse_preflight_config(data.get("preflight", {}))
    spec_debate_config = _parse_spec_debate_config(data.get("spec_debate", {}))
    session_config = _parse_session_config(data.get("sessions", {}))
    tests_config = _parse_tests_config(data.get("tests", {}))
    git_config = _parse_git_config(data.get("git", {}))
    bug_bash_config = _parse_bug_bash_config(data.get("bug_bash", {}))

    return SwarmConfig(
        repo_root=data.get("repo_root", "."),
        specs_dir=data.get("specs_dir", "specs"),
        swarm_dir=data.get("swarm_dir", ".swarm"),
        github=github_config,
        claude=claude_config,
        openai=openai_config,
        codex=codex_config,
        retry=retry_config,
        preflight=preflight_config,
        spec_debate=spec_debate_config,
        sessions=session_config,
        tests=tests_config,
        git=git_config,
        bug_bash=bug_bash_config,
    )


def get_config(config_path: Optional[str] = None, force_reload: bool = False) -> SwarmConfig:
    """
    Get the cached configuration, loading it if necessary.

    Args:
        config_path: Optional path to config file.
        force_reload: If True, reload configuration even if cached.

    Returns:
        SwarmConfig: The loaded configuration.

    Raises:
        ConfigError: If config is invalid or cannot be loaded.
    """
    global _config_cache

    if _config_cache is None or force_reload:
        _config_cache = load_config(config_path)

    return _config_cache


def clear_config_cache() -> None:
    """Clear the configuration cache. Useful for testing."""
    global _config_cache
    _config_cache = None
