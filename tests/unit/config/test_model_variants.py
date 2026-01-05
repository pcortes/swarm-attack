"""
TDD Tests for Model Variants configuration module.

This module tests the configuration system for:
1. Configure model per project in config.yaml
2. Isolate task queues by project
3. Support Opus 4.5 and alternate providers
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError
from typing import Any

# Import the module under test (will fail until implementation exists)
from swarm_attack.config.model_variants import (
    ModelConfig,
    ModelProvider,
    ProjectModelConfig,
    TaskQueueConfig,
    ModelVariantsConfig,
    get_model_for_project,
    get_task_queue_for_project,
)


# =============================================================================
# TestModelConfig: Test loading model config
# =============================================================================


class TestModelConfig:
    """Tests for ModelConfig dataclass - individual model definition."""

    def test_model_config_defaults(self):
        """Test ModelConfig has sensible defaults."""
        config = ModelConfig(model_id="claude-opus-4-5-20251101")
        assert config.model_id == "claude-opus-4-5-20251101"
        assert config.provider == ModelProvider.ANTHROPIC
        assert config.max_tokens is None  # No default limit
        assert config.temperature is None  # Use provider default

    def test_model_config_with_all_fields(self):
        """Test ModelConfig with all fields specified."""
        config = ModelConfig(
            model_id="claude-opus-4-5-20251101",
            provider=ModelProvider.ANTHROPIC,
            max_tokens=4096,
            temperature=0.7,
            api_key_env="ANTHROPIC_API_KEY",
        )
        assert config.model_id == "claude-opus-4-5-20251101"
        assert config.provider == ModelProvider.ANTHROPIC
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.api_key_env == "ANTHROPIC_API_KEY"

    def test_model_config_from_dict(self):
        """Test creating ModelConfig from dictionary (YAML parsing)."""
        data = {
            "model_id": "gpt-4-turbo",
            "provider": "openai",
            "max_tokens": 8192,
            "temperature": 0.5,
            "api_key_env": "OPENAI_API_KEY",
        }
        config = ModelConfig.from_dict(data)
        assert config.model_id == "gpt-4-turbo"
        assert config.provider == ModelProvider.OPENAI
        assert config.max_tokens == 8192
        assert config.temperature == 0.5

    def test_model_config_from_dict_minimal(self):
        """Test creating ModelConfig from minimal dictionary."""
        data = {"model_id": "claude-3-sonnet"}
        config = ModelConfig.from_dict(data)
        assert config.model_id == "claude-3-sonnet"
        assert config.provider == ModelProvider.ANTHROPIC  # Default

    def test_model_config_to_dict(self):
        """Test serializing ModelConfig to dictionary."""
        config = ModelConfig(
            model_id="claude-opus-4-5-20251101",
            provider=ModelProvider.ANTHROPIC,
            max_tokens=4096,
        )
        data = config.to_dict()
        assert data["model_id"] == "claude-opus-4-5-20251101"
        assert data["provider"] == "anthropic"
        assert data["max_tokens"] == 4096

    def test_model_config_round_trip(self):
        """Test serialization round-trip preserves data."""
        original = ModelConfig(
            model_id="claude-opus-4-5-20251101",
            provider=ModelProvider.ANTHROPIC,
            max_tokens=4096,
            temperature=0.8,
            api_key_env="MY_API_KEY",
        )
        restored = ModelConfig.from_dict(original.to_dict())
        assert original == restored

    def test_model_config_equality(self):
        """Test ModelConfig equality comparison."""
        config1 = ModelConfig(model_id="claude-opus-4-5-20251101")
        config2 = ModelConfig(model_id="claude-opus-4-5-20251101")
        config3 = ModelConfig(model_id="gpt-4-turbo")

        assert config1 == config2
        assert config1 != config3

    def test_model_config_invalid_provider_from_dict(self):
        """Test that invalid provider in dict raises error."""
        data = {"model_id": "test-model", "provider": "invalid_provider"}
        with pytest.raises(ValueError, match="Invalid provider"):
            ModelConfig.from_dict(data)


# =============================================================================
# TestModelProvider: Test provider enum
# =============================================================================


class TestModelProvider:
    """Tests for ModelProvider enum."""

    def test_anthropic_provider(self):
        """Test Anthropic provider value."""
        assert ModelProvider.ANTHROPIC.value == "anthropic"

    def test_openai_provider(self):
        """Test OpenAI provider value."""
        assert ModelProvider.OPENAI.value == "openai"

    def test_azure_provider(self):
        """Test Azure OpenAI provider value."""
        assert ModelProvider.AZURE.value == "azure"

    def test_bedrock_provider(self):
        """Test AWS Bedrock provider value."""
        assert ModelProvider.BEDROCK.value == "bedrock"

    def test_vertex_provider(self):
        """Test Google Vertex AI provider value."""
        assert ModelProvider.VERTEX.value == "vertex"

    def test_custom_provider(self):
        """Test custom/local provider value."""
        assert ModelProvider.CUSTOM.value == "custom"

    def test_provider_from_string(self):
        """Test creating provider from string."""
        assert ModelProvider("anthropic") == ModelProvider.ANTHROPIC
        assert ModelProvider("openai") == ModelProvider.OPENAI

    def test_invalid_provider_raises(self):
        """Test that invalid provider string raises ValueError."""
        with pytest.raises(ValueError):
            ModelProvider("not_a_provider")


# =============================================================================
# TestProjectIsolation: Test task queue isolation by project
# =============================================================================


class TestProjectIsolation:
    """Tests for project-level task queue isolation."""

    def test_task_queue_config_defaults(self):
        """Test TaskQueueConfig has sensible defaults."""
        config = TaskQueueConfig(project_id="swarm-attack")
        assert config.project_id == "swarm-attack"
        assert config.max_concurrent_tasks == 1  # Sequential by default
        assert config.queue_name == "swarm-attack"  # Derived from project_id

    def test_task_queue_config_custom_settings(self):
        """Test TaskQueueConfig with custom settings."""
        config = TaskQueueConfig(
            project_id="desktop-miami",
            max_concurrent_tasks=3,
            queue_name="miami-tasks",
            priority=10,
        )
        assert config.project_id == "desktop-miami"
        assert config.max_concurrent_tasks == 3
        assert config.queue_name == "miami-tasks"
        assert config.priority == 10

    def test_task_queue_isolation_different_projects(self):
        """Test that different projects have isolated task queues."""
        queue1 = TaskQueueConfig(project_id="project-a")
        queue2 = TaskQueueConfig(project_id="project-b")

        assert queue1.queue_name != queue2.queue_name
        assert queue1.project_id != queue2.project_id

    def test_task_queue_from_dict(self):
        """Test creating TaskQueueConfig from dictionary."""
        data = {
            "project_id": "my-project",
            "max_concurrent_tasks": 5,
            "queue_name": "custom-queue",
            "priority": 100,
        }
        config = TaskQueueConfig.from_dict(data)
        assert config.project_id == "my-project"
        assert config.max_concurrent_tasks == 5
        assert config.queue_name == "custom-queue"
        assert config.priority == 100

    def test_task_queue_to_dict(self):
        """Test serializing TaskQueueConfig to dictionary."""
        config = TaskQueueConfig(
            project_id="test-project",
            max_concurrent_tasks=2,
        )
        data = config.to_dict()
        assert data["project_id"] == "test-project"
        assert data["max_concurrent_tasks"] == 2

    def test_get_task_queue_for_project(self):
        """Test getting task queue configuration for a specific project."""
        # Setup mock config with multiple projects
        variants_config = ModelVariantsConfig(
            projects={
                "desktop-miami": ProjectModelConfig(
                    project_id="desktop-miami",
                    task_queue=TaskQueueConfig(
                        project_id="desktop-miami",
                        max_concurrent_tasks=2,
                    ),
                ),
                "swarm-attack": ProjectModelConfig(
                    project_id="swarm-attack",
                    task_queue=TaskQueueConfig(
                        project_id="swarm-attack",
                        max_concurrent_tasks=5,
                    ),
                ),
            }
        )

        miami_queue = get_task_queue_for_project("desktop-miami", variants_config)
        swarm_queue = get_task_queue_for_project("swarm-attack", variants_config)

        assert miami_queue.max_concurrent_tasks == 2
        assert swarm_queue.max_concurrent_tasks == 5

    def test_get_task_queue_for_unknown_project_returns_default(self):
        """Test that unknown project gets default task queue."""
        variants_config = ModelVariantsConfig(projects={})
        queue = get_task_queue_for_project("unknown-project", variants_config)

        assert queue.project_id == "unknown-project"
        assert queue.max_concurrent_tasks == 1  # Default

    def test_project_model_config_with_isolated_queue(self):
        """Test ProjectModelConfig includes isolated task queue."""
        config = ProjectModelConfig(
            project_id="my-project",
            model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            task_queue=TaskQueueConfig(
                project_id="my-project",
                max_concurrent_tasks=3,
            ),
        )

        assert config.task_queue.project_id == config.project_id
        assert config.task_queue.max_concurrent_tasks == 3


# =============================================================================
# TestModelProviders: Test multiple provider support
# =============================================================================


class TestModelProviders:
    """Tests for supporting multiple model providers."""

    def test_anthropic_opus_45_config(self):
        """Test Opus 4.5 model configuration."""
        config = ModelConfig(
            model_id="claude-opus-4-5-20251101",
            provider=ModelProvider.ANTHROPIC,
        )
        assert config.model_id == "claude-opus-4-5-20251101"
        assert config.provider == ModelProvider.ANTHROPIC

    def test_anthropic_sonnet_config(self):
        """Test Sonnet model configuration."""
        config = ModelConfig(
            model_id="claude-sonnet-4-20250514",
            provider=ModelProvider.ANTHROPIC,
        )
        assert config.model_id == "claude-sonnet-4-20250514"
        assert config.provider == ModelProvider.ANTHROPIC

    def test_openai_gpt4_config(self):
        """Test OpenAI GPT-4 configuration."""
        config = ModelConfig(
            model_id="gpt-4-turbo",
            provider=ModelProvider.OPENAI,
            api_key_env="OPENAI_API_KEY",
        )
        assert config.model_id == "gpt-4-turbo"
        assert config.provider == ModelProvider.OPENAI
        assert config.api_key_env == "OPENAI_API_KEY"

    def test_azure_openai_config(self):
        """Test Azure OpenAI configuration."""
        config = ModelConfig(
            model_id="gpt-4-deployment",
            provider=ModelProvider.AZURE,
            api_key_env="AZURE_OPENAI_API_KEY",
        )
        assert config.provider == ModelProvider.AZURE

    def test_aws_bedrock_config(self):
        """Test AWS Bedrock configuration."""
        config = ModelConfig(
            model_id="anthropic.claude-v2",
            provider=ModelProvider.BEDROCK,
        )
        assert config.provider == ModelProvider.BEDROCK

    def test_google_vertex_config(self):
        """Test Google Vertex AI configuration."""
        config = ModelConfig(
            model_id="gemini-pro",
            provider=ModelProvider.VERTEX,
        )
        assert config.provider == ModelProvider.VERTEX

    def test_custom_provider_config(self):
        """Test custom/local provider configuration."""
        config = ModelConfig(
            model_id="llama-3-70b",
            provider=ModelProvider.CUSTOM,
            api_key_env="LOCAL_API_KEY",
        )
        assert config.provider == ModelProvider.CUSTOM

    def test_model_variants_config_multiple_providers(self):
        """Test ModelVariantsConfig supports multiple providers."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(
                model_id="claude-opus-4-5-20251101",
                provider=ModelProvider.ANTHROPIC,
            ),
            projects={
                "project-a": ProjectModelConfig(
                    project_id="project-a",
                    model=ModelConfig(
                        model_id="gpt-4-turbo",
                        provider=ModelProvider.OPENAI,
                    ),
                ),
                "project-b": ProjectModelConfig(
                    project_id="project-b",
                    model=ModelConfig(
                        model_id="anthropic.claude-v2",
                        provider=ModelProvider.BEDROCK,
                    ),
                ),
            },
        )

        assert config.default_model.provider == ModelProvider.ANTHROPIC
        assert config.projects["project-a"].model.provider == ModelProvider.OPENAI
        assert config.projects["project-b"].model.provider == ModelProvider.BEDROCK

    def test_get_model_for_project_with_different_providers(self):
        """Test getting model for projects using different providers."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            projects={
                "openai-project": ProjectModelConfig(
                    project_id="openai-project",
                    model=ModelConfig(
                        model_id="gpt-4-turbo",
                        provider=ModelProvider.OPENAI,
                    ),
                ),
            },
        )

        openai_model = get_model_for_project("openai-project", config)
        anthropic_model = get_model_for_project("anthropic-project", config)

        assert openai_model.provider == ModelProvider.OPENAI
        assert anthropic_model.provider == ModelProvider.ANTHROPIC  # Default


# =============================================================================
# TestModelDefaults: Test default model selection
# =============================================================================


class TestModelDefaults:
    """Tests for default model selection."""

    def test_model_variants_config_defaults(self):
        """Test ModelVariantsConfig has sensible defaults."""
        config = ModelVariantsConfig()
        assert config.default_model is not None
        assert config.default_model.model_id == "claude-opus-4-5-20251101"
        assert config.default_model.provider == ModelProvider.ANTHROPIC

    def test_get_model_for_unknown_project_returns_default(self):
        """Test that unknown project gets default model."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(model_id="claude-opus-4-5-20251101")
        )

        model = get_model_for_project("unknown-project", config)
        assert model.model_id == "claude-opus-4-5-20251101"

    def test_get_model_for_known_project_returns_project_model(self):
        """Test that known project gets its specific model."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            projects={
                "special-project": ProjectModelConfig(
                    project_id="special-project",
                    model=ModelConfig(model_id="gpt-4-turbo"),
                ),
            },
        )

        model = get_model_for_project("special-project", config)
        assert model.model_id == "gpt-4-turbo"

    def test_project_without_model_uses_default(self):
        """Test that project without explicit model uses default."""
        default_model = ModelConfig(model_id="claude-opus-4-5-20251101")
        config = ModelVariantsConfig(
            default_model=default_model,
            projects={
                "project-with-queue-only": ProjectModelConfig(
                    project_id="project-with-queue-only",
                    model=None,  # No explicit model
                    task_queue=TaskQueueConfig(
                        project_id="project-with-queue-only",
                        max_concurrent_tasks=5,
                    ),
                ),
            },
        )

        model = get_model_for_project("project-with-queue-only", config)
        assert model == default_model

    def test_model_variants_config_from_dict(self):
        """Test creating ModelVariantsConfig from dictionary (YAML)."""
        data = {
            "default_model": {
                "model_id": "claude-opus-4-5-20251101",
                "provider": "anthropic",
            },
            "projects": {
                "desktop-miami": {
                    "model": {
                        "model_id": "claude-sonnet-4-20250514",
                        "provider": "anthropic",
                    },
                    "task_queue": {
                        "max_concurrent_tasks": 2,
                    },
                },
            },
        }

        config = ModelVariantsConfig.from_dict(data)
        assert config.default_model.model_id == "claude-opus-4-5-20251101"
        assert config.projects["desktop-miami"].model.model_id == "claude-sonnet-4-20250514"
        assert config.projects["desktop-miami"].task_queue.max_concurrent_tasks == 2

    def test_model_variants_config_to_dict(self):
        """Test serializing ModelVariantsConfig to dictionary."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            projects={
                "my-project": ProjectModelConfig(
                    project_id="my-project",
                    model=ModelConfig(model_id="gpt-4-turbo"),
                ),
            },
        )

        data = config.to_dict()
        assert data["default_model"]["model_id"] == "claude-opus-4-5-20251101"
        assert data["projects"]["my-project"]["model"]["model_id"] == "gpt-4-turbo"

    def test_model_variants_config_round_trip(self):
        """Test serialization round-trip preserves data."""
        original = ModelVariantsConfig(
            default_model=ModelConfig(
                model_id="claude-opus-4-5-20251101",
                provider=ModelProvider.ANTHROPIC,
                max_tokens=4096,
            ),
            projects={
                "project-a": ProjectModelConfig(
                    project_id="project-a",
                    model=ModelConfig(
                        model_id="gpt-4-turbo",
                        provider=ModelProvider.OPENAI,
                    ),
                    task_queue=TaskQueueConfig(
                        project_id="project-a",
                        max_concurrent_tasks=3,
                    ),
                ),
            },
        )

        restored = ModelVariantsConfig.from_dict(original.to_dict())

        assert restored.default_model.model_id == original.default_model.model_id
        assert restored.projects["project-a"].model.model_id == "gpt-4-turbo"
        assert restored.projects["project-a"].task_queue.max_concurrent_tasks == 3


# =============================================================================
# TestProjectModelConfig: Test project-level model configuration
# =============================================================================


class TestProjectModelConfig:
    """Tests for ProjectModelConfig dataclass."""

    def test_project_model_config_minimal(self):
        """Test ProjectModelConfig with minimal settings."""
        config = ProjectModelConfig(project_id="my-project")
        assert config.project_id == "my-project"
        assert config.model is None
        assert config.task_queue is not None
        assert config.task_queue.project_id == "my-project"

    def test_project_model_config_full(self):
        """Test ProjectModelConfig with all settings."""
        config = ProjectModelConfig(
            project_id="full-project",
            model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            task_queue=TaskQueueConfig(
                project_id="full-project",
                max_concurrent_tasks=10,
            ),
            enabled=True,
            description="Full project configuration",
        )

        assert config.project_id == "full-project"
        assert config.model.model_id == "claude-opus-4-5-20251101"
        assert config.task_queue.max_concurrent_tasks == 10
        assert config.enabled is True
        assert config.description == "Full project configuration"

    def test_project_model_config_from_dict(self):
        """Test creating ProjectModelConfig from dictionary."""
        data = {
            "project_id": "test-project",
            "model": {
                "model_id": "gpt-4-turbo",
                "provider": "openai",
            },
            "task_queue": {
                "max_concurrent_tasks": 3,
            },
            "enabled": True,
            "description": "Test project",
        }

        config = ProjectModelConfig.from_dict("test-project", data)
        assert config.project_id == "test-project"
        assert config.model.model_id == "gpt-4-turbo"
        assert config.task_queue.max_concurrent_tasks == 3
        assert config.enabled is True

    def test_project_model_config_to_dict(self):
        """Test serializing ProjectModelConfig to dictionary."""
        config = ProjectModelConfig(
            project_id="my-project",
            model=ModelConfig(model_id="claude-opus-4-5-20251101"),
            task_queue=TaskQueueConfig(
                project_id="my-project",
                max_concurrent_tasks=2,
            ),
        )

        data = config.to_dict()
        assert data["project_id"] == "my-project"
        assert data["model"]["model_id"] == "claude-opus-4-5-20251101"
        assert data["task_queue"]["max_concurrent_tasks"] == 2

    def test_project_model_config_disabled(self):
        """Test disabled project configuration."""
        config = ProjectModelConfig(
            project_id="disabled-project",
            enabled=False,
        )

        assert config.enabled is False


# =============================================================================
# Integration Tests: Loading from YAML-like config
# =============================================================================


class TestConfigIntegration:
    """Integration tests for loading full configuration."""

    def test_load_config_from_yaml_structure(self):
        """Test loading configuration that matches config.yaml structure."""
        yaml_like_config = {
            "model_variants": {
                "default_model": {
                    "model_id": "claude-opus-4-5-20251101",
                    "provider": "anthropic",
                    "max_tokens": 4096,
                },
                "projects": {
                    "desktop-miami": {
                        "model": {
                            "model_id": "claude-sonnet-4-20250514",
                            "provider": "anthropic",
                        },
                        "task_queue": {
                            "max_concurrent_tasks": 2,
                            "priority": 100,
                        },
                    },
                    "swarm-attack": {
                        "model": {
                            "model_id": "claude-opus-4-5-20251101",
                            "provider": "anthropic",
                        },
                        "task_queue": {
                            "max_concurrent_tasks": 5,
                            "priority": 50,
                        },
                    },
                    "openai-project": {
                        "model": {
                            "model_id": "gpt-4-turbo",
                            "provider": "openai",
                            "api_key_env": "OPENAI_API_KEY",
                        },
                    },
                },
            },
        }

        config = ModelVariantsConfig.from_dict(yaml_like_config["model_variants"])

        # Verify default model
        assert config.default_model.model_id == "claude-opus-4-5-20251101"
        assert config.default_model.max_tokens == 4096

        # Verify project-specific models
        miami_model = get_model_for_project("desktop-miami", config)
        assert miami_model.model_id == "claude-sonnet-4-20250514"

        swarm_model = get_model_for_project("swarm-attack", config)
        assert swarm_model.model_id == "claude-opus-4-5-20251101"

        openai_model = get_model_for_project("openai-project", config)
        assert openai_model.provider == ModelProvider.OPENAI

        # Verify task queue isolation
        miami_queue = get_task_queue_for_project("desktop-miami", config)
        swarm_queue = get_task_queue_for_project("swarm-attack", config)

        assert miami_queue.max_concurrent_tasks == 2
        assert miami_queue.priority == 100
        assert swarm_queue.max_concurrent_tasks == 5
        assert swarm_queue.priority == 50

    def test_unknown_project_falls_back_to_defaults(self):
        """Test that unknown projects use default configuration."""
        config = ModelVariantsConfig(
            default_model=ModelConfig(
                model_id="claude-opus-4-5-20251101",
                provider=ModelProvider.ANTHROPIC,
            ),
        )

        model = get_model_for_project("unknown-project", config)
        queue = get_task_queue_for_project("unknown-project", config)

        assert model.model_id == "claude-opus-4-5-20251101"
        assert queue.max_concurrent_tasks == 1  # Default
        assert queue.project_id == "unknown-project"

    def test_opus_45_as_default_for_new_projects(self):
        """Test that Opus 4.5 is the default model for new projects."""
        config = ModelVariantsConfig()

        model = get_model_for_project("brand-new-project", config)
        assert model.model_id == "claude-opus-4-5-20251101"
        assert model.provider == ModelProvider.ANTHROPIC


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_projects_dict(self):
        """Test configuration with empty projects dictionary."""
        config = ModelVariantsConfig(projects={})
        assert len(config.projects) == 0

        # Should still return defaults
        model = get_model_for_project("any-project", config)
        assert model.model_id == "claude-opus-4-5-20251101"

    def test_project_id_with_special_characters(self):
        """Test project IDs with special characters."""
        config = ProjectModelConfig(
            project_id="my-project_v2.0",
            model=ModelConfig(model_id="test-model"),
        )
        assert config.project_id == "my-project_v2.0"

    def test_model_config_with_empty_model_id_raises(self):
        """Test that empty model_id raises an error."""
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(model_id="")

    def test_task_queue_with_zero_concurrency(self):
        """Test task queue with zero concurrent tasks is valid (paused)."""
        config = TaskQueueConfig(
            project_id="paused-project",
            max_concurrent_tasks=0,
        )
        assert config.max_concurrent_tasks == 0

    def test_task_queue_with_negative_concurrency_raises(self):
        """Test that negative concurrency raises an error."""
        with pytest.raises((ValueError, TypeError)):
            TaskQueueConfig(
                project_id="invalid",
                max_concurrent_tasks=-1,
            )

    def test_temperature_validation_bounds(self):
        """Test that temperature is validated within bounds."""
        # Valid temperature
        config = ModelConfig(model_id="test", temperature=0.5)
        assert config.temperature == 0.5

        # Temperature at bounds
        ModelConfig(model_id="test", temperature=0.0)
        ModelConfig(model_id="test", temperature=2.0)

        # Temperature out of bounds should raise
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(model_id="test", temperature=-0.1)
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(model_id="test", temperature=2.1)

    def test_max_tokens_must_be_positive(self):
        """Test that max_tokens must be positive if specified."""
        # Valid max_tokens
        config = ModelConfig(model_id="test", max_tokens=100)
        assert config.max_tokens == 100

        # Zero max_tokens should raise
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(model_id="test", max_tokens=0)

        # Negative max_tokens should raise
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(model_id="test", max_tokens=-100)
