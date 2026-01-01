"""Unit tests for CoderAgent context injection (Issue 4).

This test file validates acceptance criterion 4.2:
- 4.2: CoderAgent._build_prompt() uses injected AgentContext

The CoderAgent should use the injected context from UniversalContextBuilder
to provide token-budgeted, tailored context for code generation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.agents.coder import CoderAgent
from swarm_attack.config import SwarmConfig
from swarm_attack.universal_context_builder import AgentContext


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create mock SwarmConfig with tmp_path as repo_root."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.state_path = tmp_path / ".swarm" / "state"

    # Create necessary directories
    config.specs_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def sample_agent_context() -> AgentContext:
    """Create sample AgentContext with coder profile."""
    return AgentContext(
        agent_type="coder",
        built_at=datetime.now(),
        project_instructions="# Swarm Attack Project\n\nUse TDD for all implementations.",
        module_registry="## Existing Classes\n\n### AutopilotSession\n```python\n@dataclass\nclass AutopilotSession:\n    session_id: str\n```",
        completed_summaries="## Prior Work\nIssue #1 completed: Created AutopilotSession model.",
        test_structure="## Test Structure\n- tests/unit/: 50 test files\n- tests/integration/: 10 test files",
        token_count=1500,
    )


@pytest.fixture
def setup_feature_files(tmp_path: Path, mock_config: SwarmConfig) -> dict[str, Any]:
    """Create required feature files for CoderAgent tests."""
    feature_id = "test-feature"

    # Create spec directory and files
    spec_dir = mock_config.specs_path / feature_id
    spec_dir.mkdir(parents=True, exist_ok=True)

    # Create spec-final.md
    spec_content = """# Test Feature Spec

## Overview
This is a test feature for unit testing.

## Requirements
- Implement a TestClass with method `process()`
- Follow existing patterns
"""
    (spec_dir / "spec-final.md").write_text(spec_content)

    # Create issues.json
    issues_data = {
        "feature_id": feature_id,
        "issues": [
            {
                "order": 1,
                "title": "Implement TestClass",
                "body": "Create TestClass with process() method.",
                "labels": ["implementation"],
                "estimated_size": "small",
            }
        ],
    }
    (spec_dir / "issues.json").write_text(json.dumps(issues_data))

    # Create skill file
    skills_dir = tmp_path / ".claude" / "skills" / "coder"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "SKILL.md").write_text("""# Coder Skill

You are a code implementation agent. Follow TDD principles.

## Instructions
1. Read the test file
2. Implement code to pass tests
3. Output files with # FILE: markers
""")

    return {
        "feature_id": feature_id,
        "spec_dir": spec_dir,
        "issues_data": issues_data,
    }


class TestCoderAgentBuildPromptWithContext:
    """Tests for CoderAgent._build_prompt() using injected context."""

    def test_build_prompt_uses_injected_context_for_project_instructions(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """AC 4.2: _build_prompt() should use project_instructions from AgentContext.

        When AgentContext is injected, the project instructions should come
        from the context rather than being re-read from disk.
        """
        coder = CoderAgent(mock_config)
        coder.with_context(sample_agent_context)

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
        )

        # Should contain context from injected AgentContext
        assert "# Swarm Attack Project" in prompt
        assert "Use TDD for all implementations" in prompt

    def test_build_prompt_uses_injected_module_registry(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """AC 4.2: _build_prompt() should use module_registry from AgentContext.

        The injected module registry should be used instead of building it fresh.
        """
        coder = CoderAgent(mock_config)
        coder.with_context(sample_agent_context)

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
        )

        # Should contain module registry from context
        assert "AutopilotSession" in prompt
        assert "session_id: str" in prompt

    def test_build_prompt_uses_injected_completed_summaries(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """AC 4.2: _build_prompt() should use completed_summaries from AgentContext."""
        coder = CoderAgent(mock_config)
        coder.with_context(sample_agent_context)

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
        )

        # Should contain completed summaries from context
        assert "Prior Work" in prompt
        assert "Issue #1 completed" in prompt

    def test_build_prompt_backward_compatible_without_context(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """AC 4.6: _build_prompt() should work without injected context.

        When no context is injected, should fall back to existing behavior
        (reading from disk, using module_registry parameter).
        """
        coder = CoderAgent(mock_config)
        # Don't inject context

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        # Should not raise even without context
        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
            module_registry={"modules": {}},  # Fallback parameter
        )

        # Should still produce valid prompt
        assert "Test spec content" in prompt
        assert "Implement" in prompt  # From issue title

    def test_build_prompt_context_appears_before_task(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """Injected context should appear before the task-specific content."""
        coder = CoderAgent(mock_config)
        coder.with_context(sample_agent_context)

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
        )

        # Context sections should appear before issue details
        context_pos = prompt.find("# Swarm Attack Project")
        issue_pos = prompt.find("Issue to Implement")

        assert context_pos < issue_pos, "Context should come before issue details"


class TestCoderAgentContextIntegration:
    """Integration tests for CoderAgent context flow."""

    def test_context_flows_through_run_method(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """Context injected via with_context() should flow through run().

        The run() method should use the injected context when building prompts.
        """
        # Mock event emission before creating agent to avoid validation issues
        with patch('swarm_attack.agents.coder.CoderAgent._emit_event'):
            coder = CoderAgent(mock_config)
            coder.with_context(sample_agent_context)

            feature_id = setup_feature_files["feature_id"]

            # Create test file that coder expects (with failing test so it doesn't skip)
            test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("def test_example(): assert False  # Should fail")

            # Mock the LLM call to capture the prompt
            captured_prompts = []

            def mock_run(prompt, **kwargs):
                captured_prompts.append(prompt)
                result = MagicMock()
                result.text = "# FILE: src/test.py\nclass Test: pass"
                result.total_cost_usd = 0.01
                return result

            coder._llm = MagicMock()
            coder._llm.run = mock_run

            # Mock the test pass check to always return False (tests don't pass yet)
            coder._check_tests_pass = MagicMock(return_value=False)

            # Run the agent
            context = {
                "feature_id": feature_id,
                "issue_number": 1,
            }
            coder.run(context)

            # Verify context was included in prompt
            assert len(captured_prompts) == 1
            prompt = captured_prompts[0]
            assert "# Swarm Attack Project" in prompt
            assert "AutopilotSession" in prompt

    def test_context_priority_over_parameter(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
        setup_feature_files: dict[str, Any],
    ) -> None:
        """Injected context should take priority over parameters.

        When both injected context and module_registry parameter are provided,
        the injected context should be preferred.
        """
        coder = CoderAgent(mock_config)
        coder.with_context(sample_agent_context)

        feature_id = setup_feature_files["feature_id"]
        issue = setup_feature_files["issues_data"]["issues"][0]

        # Provide conflicting module_registry parameter
        conflicting_registry = {
            "modules": {
                "other/path.py": {
                    "classes": ["DifferentClass"],
                    "created_by_issue": 99,
                }
            }
        }

        prompt = coder._build_prompt(
            feature_id=feature_id,
            issue=issue,
            spec_content="Test spec content",
            test_content="def test_example(): pass",
            expected_modules=[],
            module_registry=conflicting_registry,
        )

        # Should use context's module_registry, not parameter
        assert "AutopilotSession" in prompt  # From context


class TestCoderAgentTokenBudget:
    """Tests for token budget handling in CoderAgent."""

    def test_token_budget_logged_for_coder(
        self,
        mock_config: SwarmConfig,
        sample_agent_context: AgentContext,
    ) -> None:
        """Token count from context should be accessible for logging."""
        mock_logger = MagicMock()
        coder = CoderAgent(mock_config, logger=mock_logger)

        coder.with_context(sample_agent_context)

        # Token count should be available
        assert coder._universal_context is not None
        assert coder._universal_context.token_count == 1500

        # Injection should be logged
        mock_logger.log.assert_called_once()
        log_data = mock_logger.log.call_args[0][1]
        assert log_data["token_count"] == 1500

    def test_coder_profile_has_15k_token_budget(self) -> None:
        """Verify coder profile specifies 15k token budget.

        This is a documentation/specification test to ensure the profile
        is configured correctly.
        """
        from swarm_attack.universal_context_builder import AGENT_CONTEXT_PROFILES

        coder_profile = AGENT_CONTEXT_PROFILES.get("coder")
        assert coder_profile is not None
        assert coder_profile.get("max_tokens") == 15000
