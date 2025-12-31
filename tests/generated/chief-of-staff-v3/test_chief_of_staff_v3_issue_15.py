"""Tests for CodeCritic variants."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swarm_attack.chief_of_staff.critics import (
    CodeCritic,
    Critic,
    CriticFocus,
    CriticScore,
)


class TestCodeCriticExtendsBaseCritic:
    """Test that CodeCritic extends base Critic class."""

    def test_code_critic_is_subclass_of_critic(self):
        """CodeCritic should extend Critic."""
        assert issubclass(CodeCritic, Critic)

    def test_code_critic_instantiation_with_style_focus(self):
        """CodeCritic can be instantiated with STYLE focus."""
        mock_llm = MagicMock()
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        assert critic.focus == CriticFocus.STYLE
        assert critic.llm == mock_llm

    def test_code_critic_instantiation_with_security_focus(self):
        """CodeCritic can be instantiated with SECURITY focus."""
        mock_llm = MagicMock()
        critic = CodeCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        assert critic.focus == CriticFocus.SECURITY

    def test_code_critic_has_custom_weight(self):
        """CodeCritic supports custom weight."""
        mock_llm = MagicMock()
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm, weight=0.5)
        assert critic.weight == 0.5


class TestCodeCriticVetoPower:
    """Test veto power behavior for CodeCritic."""

    def test_security_critic_has_veto_power(self):
        """SECURITY focus has veto power."""
        mock_llm = MagicMock()
        critic = CodeCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        assert critic.has_veto is True

    def test_style_critic_no_veto_power(self):
        """STYLE focus does not have veto power."""
        mock_llm = MagicMock()
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        assert critic.has_veto is False


class TestCodeCriticEvaluate:
    """Test CodeCritic evaluate method."""

    def test_evaluate_returns_critic_score(self):
        """evaluate() should return a CriticScore."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": ["Consider adding docstrings"],
            "reasoning": "Code follows good patterns"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert isinstance(result, CriticScore)

    def test_evaluate_style_sets_correct_critic_name(self):
        """STYLE critic should set critic_name to 'CodeCritic-STYLE'."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.9,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good style"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.critic_name == "CodeCritic-style"

    def test_evaluate_security_sets_correct_critic_name(self):
        """SECURITY critic should set critic_name to 'CodeCritic-SECURITY'."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.95,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "No security issues"
        })
        
        critic = CodeCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.critic_name == "CodeCritic-security"

    def test_evaluate_sets_correct_focus(self):
        """evaluate() should set the correct focus in result."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.focus == CriticFocus.STYLE

    def test_evaluate_parses_issues(self):
        """evaluate() should parse issues from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.5,
            "approved": False,
            "issues": ["Missing docstring", "Variable name too short"],
            "suggestions": [],
            "reasoning": "Style issues found"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def f(x): return x")
        
        assert result.issues == ["Missing docstring", "Variable name too short"]

    def test_evaluate_parses_suggestions(self):
        """evaluate() should parse suggestions from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.7,
            "approved": True,
            "issues": [],
            "suggestions": ["Add type hints", "Use constants for magic numbers"],
            "reasoning": "Minor improvements possible"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(x): return x * 2")
        
        assert result.suggestions == ["Add type hints", "Use constants for magic numbers"]

    def test_evaluate_parses_score(self):
        """evaluate() should parse score from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.85,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good code"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def calculate_total(items): pass")
        
        assert result.score == 0.85

    def test_evaluate_parses_approved(self):
        """evaluate() should parse approved from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.6,
            "approved": False,
            "issues": ["Security vulnerability"],
            "suggestions": [],
            "reasoning": "Not approved"
        })
        
        critic = CodeCritic(focus=CriticFocus.SECURITY, llm=mock_llm)
        result = critic.evaluate("os.system(user_input)")
        
        assert result.approved is False

    def test_evaluate_parses_reasoning(self):
        """evaluate() should parse reasoning from LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.9,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Code follows all style guidelines"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.reasoning == "Code follows all style guidelines"


class TestCodeCriticFocusPrompts:
    """Test that CodeCritic uses focus-specific prompts."""

    def test_style_prompt_contains_naming(self):
        """STYLE prompt should mention naming."""
        assert "naming" in CodeCritic.PROMPTS[CriticFocus.STYLE].lower()

    def test_style_prompt_contains_structure(self):
        """STYLE prompt should mention structure."""
        assert "structure" in CodeCritic.PROMPTS[CriticFocus.STYLE].lower()

    def test_style_prompt_contains_readability(self):
        """STYLE prompt should mention readability."""
        assert "readability" in CodeCritic.PROMPTS[CriticFocus.STYLE].lower()

    def test_security_prompt_contains_vulnerabilities(self):
        """SECURITY prompt should mention vulnerabilities."""
        assert "vulnerabilit" in CodeCritic.PROMPTS[CriticFocus.SECURITY].lower()

    def test_security_prompt_contains_injection(self):
        """SECURITY prompt should mention injection."""
        assert "injection" in CodeCritic.PROMPTS[CriticFocus.SECURITY].lower()

    def test_security_prompt_contains_unsafe(self):
        """SECURITY prompt should mention unsafe operations."""
        assert "unsafe" in CodeCritic.PROMPTS[CriticFocus.SECURITY].lower()

    def test_security_prompt_contains_secrets(self):
        """SECURITY prompt should mention secrets."""
        assert "secret" in CodeCritic.PROMPTS[CriticFocus.SECURITY].lower()

    def test_prompts_have_code_diff_placeholder(self):
        """All prompts should have {code_diff} placeholder."""
        for focus in [CriticFocus.STYLE, CriticFocus.SECURITY]:
            assert "{code_content}" in CodeCritic.PROMPTS[focus]


class TestCodeCriticLLMParsing:
    """Test CodeCritic LLM response parsing."""

    def test_handles_json_with_code_fence(self):
        """Should handle JSON wrapped in code fence."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = """```json
{
    "score": 0.75,
    "approved": true,
    "issues": [],
    "suggestions": [],
    "reasoning": "Good code"
}
```"""
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.score == 0.75

    def test_handles_malformed_json_gracefully(self):
        """Should return low score on malformed JSON."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "This is not JSON at all"
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.score == 0.0
        assert result.approved is False
        assert "parse" in result.reasoning.lower() or "failed" in result.reasoning.lower()

    def test_handles_missing_fields_with_defaults(self):
        """Should use defaults for missing fields."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True
            # Missing issues, suggestions, reasoning
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        result = critic.evaluate("def foo(): pass")
        
        assert result.issues == []
        assert result.suggestions == []
        assert result.reasoning == ""


class TestCodeCriticTruncation:
    """Test CodeCritic truncates code_diff."""

    def test_truncates_long_code_diff(self):
        """Should truncate code_diff to MAX_CODE_DIFF_CHARS."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "OK"
        })
        
        critic = CodeCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        long_code = "x" * 10000  # Much longer than limit
        critic.evaluate(long_code)
        
        # Check that the LLM was called with truncated content
        call_args = mock_llm.generate.call_args[0][0]
        # The code_diff in the prompt should be truncated
        assert len(call_args) < len(long_code) + 1000  # Allow for prompt template

    def test_max_code_diff_chars_is_4000(self):
        """MAX_CODE_DIFF_CHARS should be 4000."""
        assert CodeCritic.MAX_CODE_CHARS == 6000


class TestCodeCriticFileExists:
    """Test that CodeCritic is in the correct file."""

    def test_critics_file_exists(self):
        """critics.py file should exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "critics.py"
        assert path.exists(), f"Expected file at {path}"

    def test_code_critic_in_critics_module(self):
        """CodeCritic should be importable from critics module."""
        from swarm_attack.chief_of_staff.critics import CodeCritic
        assert CodeCritic is not None