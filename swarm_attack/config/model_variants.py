"""
Model Variants Configuration Module.

This module provides configuration support for:
1. Configure model per project in config.yaml
2. Isolate task queues by project
3. Support Opus 4.5 and alternate providers

The design follows a dataclass-based approach with full serialization support
for YAML configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ModelProvider(Enum):
    """Supported model providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    BEDROCK = "bedrock"
    VERTEX = "vertex"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """
    Configuration for a specific model.

    Attributes:
        model_id: The model identifier (e.g., "claude-opus-4-5-20251101")
        provider: The model provider (defaults to ANTHROPIC)
        max_tokens: Maximum tokens for generation (optional)
        temperature: Sampling temperature (optional, 0.0 to 2.0)
        api_key_env: Environment variable name for API key (optional)
    """
    model_id: str
    provider: ModelProvider = ModelProvider.ANTHROPIC
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    api_key_env: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.model_id:
            raise ValueError("model_id cannot be empty")

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive if specified")

        if self.temperature is not None:
            if self.temperature < 0.0 or self.temperature > 2.0:
                raise ValueError("temperature must be between 0.0 and 2.0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        """
        Create ModelConfig from a dictionary (e.g., from YAML parsing).

        Args:
            data: Dictionary containing model configuration.

        Returns:
            ModelConfig instance.

        Raises:
            ValueError: If provider is invalid.
        """
        provider_str = data.get("provider", "anthropic")
        try:
            provider = ModelProvider(provider_str)
        except ValueError:
            raise ValueError(f"Invalid provider: {provider_str}")

        return cls(
            model_id=data["model_id"],
            provider=provider,
            max_tokens=data.get("max_tokens"),
            temperature=data.get("temperature"),
            api_key_env=data.get("api_key_env"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize ModelConfig to a dictionary.

        Returns:
            Dictionary representation suitable for YAML serialization.
        """
        result: dict[str, Any] = {
            "model_id": self.model_id,
            "provider": self.provider.value,
        }
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            result["temperature"] = self.temperature
        if self.api_key_env is not None:
            result["api_key_env"] = self.api_key_env
        return result


@dataclass
class TaskQueueConfig:
    """
    Configuration for a project's task queue.

    Task queues provide isolation between projects, ensuring that
    tasks from different projects don't interfere with each other.

    Attributes:
        project_id: The project identifier
        max_concurrent_tasks: Maximum concurrent tasks (default: 1)
        queue_name: Queue name (defaults to project_id)
        priority: Queue priority (optional)
    """
    project_id: str
    max_concurrent_tasks: int = 1
    queue_name: Optional[str] = None
    priority: Optional[int] = None

    def __post_init__(self) -> None:
        """Set defaults and validate configuration."""
        if self.queue_name is None:
            self.queue_name = self.project_id

        if self.max_concurrent_tasks < 0:
            raise ValueError("max_concurrent_tasks cannot be negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskQueueConfig:
        """
        Create TaskQueueConfig from a dictionary.

        Args:
            data: Dictionary containing task queue configuration.

        Returns:
            TaskQueueConfig instance.
        """
        return cls(
            project_id=data["project_id"],
            max_concurrent_tasks=data.get("max_concurrent_tasks", 1),
            queue_name=data.get("queue_name"),
            priority=data.get("priority"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize TaskQueueConfig to a dictionary.

        Returns:
            Dictionary representation suitable for YAML serialization.
        """
        result: dict[str, Any] = {
            "project_id": self.project_id,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }
        if self.queue_name is not None:
            result["queue_name"] = self.queue_name
        if self.priority is not None:
            result["priority"] = self.priority
        return result


@dataclass
class ProjectModelConfig:
    """
    Configuration for a specific project.

    Combines model configuration with task queue settings for
    complete project-level isolation.

    Attributes:
        project_id: The project identifier
        model: Model configuration (optional, uses default if not specified)
        task_queue: Task queue configuration
        enabled: Whether the project is enabled (default: True)
        description: Optional project description
    """
    project_id: str
    model: Optional[ModelConfig] = None
    task_queue: Optional[TaskQueueConfig] = None
    enabled: bool = True
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Ensure task_queue is properly initialized."""
        if self.task_queue is None:
            self.task_queue = TaskQueueConfig(project_id=self.project_id)

    @classmethod
    def from_dict(cls, project_id: str, data: dict[str, Any]) -> ProjectModelConfig:
        """
        Create ProjectModelConfig from a dictionary.

        Args:
            project_id: The project identifier.
            data: Dictionary containing project configuration.

        Returns:
            ProjectModelConfig instance.
        """
        model = None
        if "model" in data and data["model"]:
            model = ModelConfig.from_dict(data["model"])

        task_queue = None
        if "task_queue" in data:
            queue_data = data["task_queue"].copy()
            queue_data["project_id"] = project_id
            task_queue = TaskQueueConfig.from_dict(queue_data)
        else:
            task_queue = TaskQueueConfig(project_id=project_id)

        return cls(
            project_id=project_id,
            model=model,
            task_queue=task_queue,
            enabled=data.get("enabled", True),
            description=data.get("description"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize ProjectModelConfig to a dictionary.

        Returns:
            Dictionary representation suitable for YAML serialization.
        """
        result: dict[str, Any] = {
            "project_id": self.project_id,
        }
        if self.model is not None:
            result["model"] = self.model.to_dict()
        if self.task_queue is not None:
            result["task_queue"] = self.task_queue.to_dict()
        if not self.enabled:
            result["enabled"] = self.enabled
        if self.description is not None:
            result["description"] = self.description
        return result


def _default_model() -> ModelConfig:
    """Create the default model configuration (Opus 4.5)."""
    return ModelConfig(
        model_id="claude-opus-4-5-20251101",
        provider=ModelProvider.ANTHROPIC,
    )


@dataclass
class ModelVariantsConfig:
    """
    Top-level configuration for model variants across all projects.

    This is the main configuration class that holds:
    - A default model for projects without explicit configuration
    - Per-project model and task queue configurations

    Attributes:
        default_model: Default model for projects without explicit config
        projects: Dictionary of project-specific configurations
    """
    default_model: ModelConfig = field(default_factory=_default_model)
    projects: dict[str, ProjectModelConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelVariantsConfig:
        """
        Create ModelVariantsConfig from a dictionary (e.g., from YAML).

        Args:
            data: Dictionary containing the full model variants configuration.

        Returns:
            ModelVariantsConfig instance.
        """
        default_model = _default_model()
        if "default_model" in data:
            default_model = ModelConfig.from_dict(data["default_model"])

        projects: dict[str, ProjectModelConfig] = {}
        if "projects" in data:
            for project_id, project_data in data["projects"].items():
                projects[project_id] = ProjectModelConfig.from_dict(
                    project_id, project_data
                )

        return cls(
            default_model=default_model,
            projects=projects,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize ModelVariantsConfig to a dictionary.

        Returns:
            Dictionary representation suitable for YAML serialization.
        """
        result: dict[str, Any] = {
            "default_model": self.default_model.to_dict(),
        }
        if self.projects:
            result["projects"] = {
                project_id: config.to_dict()
                for project_id, config in self.projects.items()
            }
        return result


def get_model_for_project(
    project_id: str,
    config: ModelVariantsConfig,
) -> ModelConfig:
    """
    Get the model configuration for a specific project.

    If the project has explicit model configuration, returns that.
    Otherwise, returns the default model.

    Args:
        project_id: The project identifier.
        config: The model variants configuration.

    Returns:
        ModelConfig for the project.
    """
    if project_id in config.projects:
        project_config = config.projects[project_id]
        if project_config.model is not None:
            return project_config.model

    return config.default_model


def get_task_queue_for_project(
    project_id: str,
    config: ModelVariantsConfig,
) -> TaskQueueConfig:
    """
    Get the task queue configuration for a specific project.

    If the project has explicit task queue configuration, returns that.
    Otherwise, returns a default task queue with the project_id.

    Args:
        project_id: The project identifier.
        config: The model variants configuration.

    Returns:
        TaskQueueConfig for the project.
    """
    if project_id in config.projects:
        project_config = config.projects[project_id]
        if project_config.task_queue is not None:
            return project_config.task_queue

    return TaskQueueConfig(project_id=project_id)
