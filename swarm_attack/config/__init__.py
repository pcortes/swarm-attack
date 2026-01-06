"""
Configuration package for Feature Swarm.

This package provides:
- Main configuration loading (SwarmConfig, load_config, get_config)
- Model variants configuration (ModelConfig, ModelVariantsConfig)
- Task queue isolation (TaskQueueConfig)
"""

# Re-export everything from the main configuration module
from swarm_attack.config.main import (
    ConfigError,
    GitHubConfig,
    ClaudeConfig,
    OpenAIConfig,
    CodexConfig,
    RetryConfig,
    PreflightConfig,
    SpecDebateConfig,
    SessionConfig,
    ExecutorConfig,
    TestRunnerConfig,
    GitConfig,
    BugDebateConfig,
    BugBashConfig,
    AutoFixConfig,
    SwarmConfig,
    load_config,
    get_config,
    clear_config_cache,
)

# Export model variants configuration
from swarm_attack.config.model_variants import (
    ModelConfig,
    ModelProvider,
    ProjectModelConfig,
    TaskQueueConfig,
    ModelVariantsConfig,
    get_model_for_project,
    get_task_queue_for_project,
)

__all__ = [
    # Main configuration
    "ConfigError",
    "GitHubConfig",
    "ClaudeConfig",
    "OpenAIConfig",
    "CodexConfig",
    "RetryConfig",
    "PreflightConfig",
    "SpecDebateConfig",
    "SessionConfig",
    "ExecutorConfig",
    "TestRunnerConfig",
    "GitConfig",
    "BugDebateConfig",
    "BugBashConfig",
    "AutoFixConfig",
    "SwarmConfig",
    "load_config",
    "get_config",
    "clear_config_cache",
    # Model variants
    "ModelConfig",
    "ModelProvider",
    "ProjectModelConfig",
    "TaskQueueConfig",
    "ModelVariantsConfig",
    "get_model_for_project",
    "get_task_queue_for_project",
]
