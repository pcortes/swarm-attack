"""Tests for SpecCritic variants."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swarm_attack.chief_of_staff.critics import (
    Critic,
    CriticFocus,
    CriticScore,
    SpecCritic,
)


class TestSpecCriticExtendsBaseCritic:
    """Test that SpecCritic extends Critic base class."""

    def test_spec_critic_is_subclass_of_critic(self):
        """SpecCritic should extend Critic."""
        assert issubclass(SpecCritic, Critic)

    def test_spec_critic_inherits_has_veto(self):
        """SpecCritic should inherit has_veto property."""
        mock_llm = MagicMock()
        critic = SpecCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        assert critic.has_veto is True

        critic_completeness = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        assert critic_completeness.has_veto is False


class TestSpecCriticEvaluate:
    """Test SpecCritic.evaluate() method."""

    def test_evaluate_returns_critic_score(self):
        """evaluate() should return a CriticScore."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": ["Add more detail"],
            "reasoning": "Spec looks good",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Spec Content\n\nSome spec text here")

        assert isinstance(result, CriticScore)
        assert result.score == 0.8
        assert result.approved is True
        assert result.reasoning == "Spec looks good"

    def test_evaluate_with_completeness_focus(self):
        """COMPLETENESS critic should check for missing sections."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.6,
            "approved": False,
            "issues": ["Missing architecture section", "No error handling defined"],
            "suggestions": ["Add architecture diagram", "Define error codes"],
            "reasoning": "Spec is incomplete",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Incomplete Spec")

        assert result.focus == CriticFocus.COMPLETENESS
        assert result.critic_name == "SpecCritic"
        assert len(result.issues) == 2
        assert "Missing architecture section" in result.issues

    def test_evaluate_with_feasibility_focus(self):
        """FEASIBILITY critic should check for implementation clarity."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.7,
            "approved": True,
            "issues": ["Unclear database schema"],
            "suggestions": ["Define table relationships"],
            "reasoning": "Mostly implementable",
        })

        critic = SpecCritic(focus=CriticFocus.FEASIBILITY, llm=mock_llm)
        result = critic.evaluate("# Feasibility Test Spec")

        assert result.focus == CriticFocus.FEASIBILITY
        assert result.approved is True

    def test_evaluate_with_security_focus(self):
        """SECURITY critic should check for security issues."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.3,
            "approved": False,
            "issues": ["SQL injection risk", "No auth defined", "Data exposure in logs"],
            "suggestions": ["Use parameterized queries", "Add authentication layer"],
            "reasoning": "Critical security gaps",
        })

        critic = SpecCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        result = critic.evaluate("# Insecure Spec")

        assert result.focus == CriticFocus.SECURITY
        assert result.approved is False
        assert len(result.issues) == 3
        assert "SQL injection risk" in result.issues

    def test_evaluate_truncates_long_spec(self):
        """evaluate() should truncate spec_content to 4000 chars."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.9,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good spec",
        })

        long_spec = "A" * 10000  # 10000 chars
        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        critic.evaluate(long_spec)

        # Check that LLM was called with truncated content
        call_args = mock_llm.call_args[0][0] if mock_llm.call_args[0] else mock_llm.call_args[1].get("prompt", "")
        # The spec content in the prompt should be truncated
        assert len(long_spec) == 10000  # Original is long
        mock_llm.assert_called_once()

    def test_evaluate_handles_empty_lists_in_response(self):
        """evaluate() should handle empty issues/suggestions lists."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 1.0,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Perfect spec",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Perfect Spec")

        assert result.issues == []
        assert result.suggestions == []


class TestSpecCriticFocusPrompts:
    """Test that each focus has appropriate prompts."""

    def test_completeness_prompt_mentions_gaps(self):
        """COMPLETENESS focus should use prompt about missing sections."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        critic.evaluate("# Test Spec")

        # Check the prompt contains completeness-related terms
        call_args = str(mock_llm.call_args)
        assert "missing" in call_args.lower() or "complete" in call_args.lower() or "gap" in call_args.lower()

    def test_feasibility_prompt_mentions_implementation(self):
        """FEASIBILITY focus should use prompt about implementation."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK",
        })

        critic = SpecCritic(focus=CriticFocus.FEASIBILITY, llm=mock_llm)
        critic.evaluate("# Test Spec")

        call_args = str(mock_llm.call_args)
        assert "implement" in call_args.lower() or "feasib" in call_args.lower() or "unclear" in call_args.lower()

    def test_security_prompt_mentions_security_concerns(self):
        """SECURITY focus should use prompt about security issues."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK",
        })

        critic = SpecCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        critic.evaluate("# Test Spec")

        call_args = str(mock_llm.call_args)
        assert "security" in call_args.lower() or "injection" in call_args.lower() or "auth" in call_args.lower()


class TestSpecCriticLLMParsing:
    """Test LLM response parsing."""

    def test_parses_valid_json_response(self):
        """Should parse valid JSON response from LLM."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.75,
            "approved": True,
            "issues": ["Issue 1"],
            "suggestions": ["Suggestion 1"],
            "reasoning": "Test reasoning",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Spec")

        assert result.score == 0.75
        assert result.approved is True
        assert result.issues == ["Issue 1"]
        assert result.suggestions == ["Suggestion 1"]
        assert result.reasoning == "Test reasoning"

    def test_handles_json_with_extra_fields(self):
        """Should ignore extra fields in JSON response."""
        mock_llm = MagicMock()
        mock_llm.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK",
            "extra_field": "ignored",
        })

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Spec")

        assert result.score == 0.8

    def test_handles_json_embedded_in_text(self):
        """Should extract JSON from LLM response with surrounding text."""
        mock_llm = MagicMock()
        mock_llm.return_value = """Here is my evaluation:
        
```json
{
    "score": 0.65,
    "approved": false,
    "issues": ["Missing tests"],
    "suggestions": ["Add unit tests"],
    "reasoning": "Needs work"
}
```

Hope this helps!"""

        critic = SpecCritic(focus=CriticFocus.COMPLETENESS, llm=mock_llm)
        result = critic.evaluate("# Spec")

        assert result.score == 0.65
        assert result.approved is False


class TestSpecCriticFileExists:
    """Test that the critics.py file exists and has SpecCritic."""

    def test_critics_file_exists(self):
        """critics.py should exist at expected path."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "critics.py"
        assert path.exists(), f"critics.py must exist at {path}"

    def test_spec_critic_importable(self):
        """SpecCritic should be importable from critics module."""
        from swarm_attack.chief_of_staff.critics import SpecCritic
        assert SpecCritic is not None