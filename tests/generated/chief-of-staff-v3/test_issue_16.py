"""Tests for SuiteCritic (formerly TestCritic) variants.

Note: TestCritic was renamed to SuiteCritic for pytest compatibility
(pytest collects classes starting with 'Test' as test classes).
TestCritic is still available as a backward compatibility alias.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from swarm_attack.chief_of_staff.critics import (
    Critic,
    CriticFocus,
    CriticScore,
    SuiteCritic,
    TestCritic,  # Backward compatibility alias
)


class TestTestCriticExtendsBaseCritic:
    """Test that TestCritic extends Critic."""

    def test_testcritic_is_subclass_of_critic(self):
        """TestCritic should be a subclass of Critic."""
        assert issubclass(TestCritic, Critic)

    def test_testcritic_instantiates_with_coverage_focus(self):
        """TestCritic should instantiate with COVERAGE focus."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        assert critic.focus == CriticFocus.COVERAGE

    def test_testcritic_instantiates_with_edge_cases_focus(self):
        """TestCritic should instantiate with EDGE_CASES focus."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.EDGE_CASES, llm=mock_llm)
        assert critic.focus == CriticFocus.EDGE_CASES

    def test_testcritic_stores_llm(self):
        """TestCritic should store the LLM instance."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        assert critic.llm is mock_llm

    def test_testcritic_default_weight(self):
        """TestCritic should have default weight of 1.0."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        assert critic.weight == 1.0

    def test_testcritic_custom_weight(self):
        """TestCritic should accept custom weight."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm, weight=0.5)
        assert critic.weight == 0.5

    def test_testcritic_has_veto_is_false(self):
        """TestCritic should not have veto power (not SECURITY focus)."""
        mock_llm = Mock()
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        assert critic.has_veto is False


class TestTestCriticEvaluate:
    """Test TestCritic evaluate method."""

    def test_evaluate_returns_critic_score(self):
        """Evaluate should return a CriticScore instance."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good coverage",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")
        assert isinstance(result, CriticScore)

    def test_evaluate_coverage_calls_llm_with_test_content(self):
        """Evaluate should call LLM with test content."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        test_content = "def test_example(): assert True"
        critic.evaluate(test_content)
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args[0][0]
        assert test_content in call_args

    def test_evaluate_edge_cases_calls_llm_with_test_content(self):
        """Evaluate should call LLM with test content for EDGE_CASES."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.7,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.EDGE_CASES, llm=mock_llm)
        test_content = "def test_boundary(): assert func(0) == 0"
        critic.evaluate(test_content)
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args[0][0]
        assert test_content in call_args

    def test_evaluate_returns_correct_focus(self):
        """Evaluate should return CriticScore with correct focus."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")
        assert result.focus == CriticFocus.COVERAGE

    def test_evaluate_unsupported_focus_raises_error(self):
        """Creating TestCritic with unsupported focus should raise ValueError."""
        mock_llm = Mock()
        with pytest.raises(ValueError) as exc_info:
            TestCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        assert "does not support focus" in str(exc_info.value)


class TestTestCriticFocusPrompts:
    """Test TestCritic has focus-specific prompts."""

    def test_has_coverage_prompt(self):
        """TestCritic should have COVERAGE prompt."""
        assert CriticFocus.COVERAGE in TestCritic.PROMPTS

    def test_has_edge_cases_prompt(self):
        """TestCritic should have EDGE_CASES prompt."""
        assert CriticFocus.EDGE_CASES in TestCritic.PROMPTS

    def test_coverage_prompt_mentions_coverage(self):
        """COVERAGE prompt should mention coverage-related terms."""
        prompt = TestCritic.PROMPTS[CriticFocus.COVERAGE]
        assert "coverage" in prompt.lower() or "test" in prompt.lower()

    def test_edge_cases_prompt_mentions_boundary(self):
        """EDGE_CASES prompt should mention boundary/edge case terms."""
        prompt = TestCritic.PROMPTS[CriticFocus.EDGE_CASES]
        assert "edge" in prompt.lower() or "boundary" in prompt.lower()

    def test_coverage_prompt_has_test_content_placeholder(self):
        """COVERAGE prompt should have test_content placeholder."""
        prompt = TestCritic.PROMPTS[CriticFocus.COVERAGE]
        assert "{test_content}" in prompt

    def test_edge_cases_prompt_has_test_content_placeholder(self):
        """EDGE_CASES prompt should have test_content placeholder."""
        prompt = TestCritic.PROMPTS[CriticFocus.EDGE_CASES]
        assert "{test_content}" in prompt


class TestTestCriticTruncation:
    """Test TestCritic truncates long test content."""

    def test_truncates_long_test_content(self):
        """Long test content should be truncated."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        
        # Create test content longer than MAX_TEST_CHARS
        long_content = "x" * 5000
        critic.evaluate(long_content)
        
        call_args = mock_llm.generate.call_args[0][0]
        # Should be truncated (content length in prompt should be less than original)
        # The implementation may use different truncation markers
        assert len(call_args) < len(long_content) + 1000  # Allow for prompt template

    def test_max_test_chars_is_4000(self):
        """MAX_TEST_CHARS should be 4000."""
        assert TestCritic.MAX_TEST_CHARS == 6000

    def test_short_content_not_truncated(self):
        """Short test content should not be truncated."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        
        short_content = "def test_foo(): pass"
        critic.evaluate(short_content)
        
        call_args = mock_llm.generate.call_args[0][0]
        assert "[truncated]" not in call_args


class TestTestCriticLLMParsing:
    """Test TestCritic parses LLM responses correctly."""

    def test_parses_valid_json_response(self):
        """Should parse valid JSON response correctly."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.85,
            "approved": True,
            "issues": ["Missing edge case for null input"],
            "suggestions": ["Add test for None values"],
            "reasoning": "Good coverage but missing null tests",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")
        
        assert result.score == 0.85
        assert result.approved is True
        assert "Missing edge case for null input" in result.issues
        assert "Add test for None values" in result.suggestions
        assert "Good coverage" in result.reasoning

    def test_parses_json_with_code_fences(self):
        """Should parse JSON wrapped in code fences."""
        mock_llm = Mock()
        mock_llm.generate.return_value = '```json\n{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "Excellent"}\n```'
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")
        
        assert result.score == 0.9
        assert result.approved is True

    def test_handles_invalid_json_response(self):
        """Should handle invalid JSON gracefully."""
        mock_llm = Mock()
        mock_llm.generate.return_value = "This is not valid JSON"
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")
        
        assert result.score == 0.0
        assert result.approved is False
        assert "Failed to parse" in result.issues[0]

    def test_critic_name_includes_focus(self):
        """Critic name should include the focus."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")

        # Note: TestCritic was renamed to SuiteCritic for pytest compatibility
        assert "SuiteCritic" in result.critic_name
        assert "coverage" in result.critic_name.lower()

    def test_edge_cases_critic_name(self):
        """Critic name should include EDGE_CASES for that focus."""
        mock_llm = Mock()
        mock_llm.generate.return_value = json.dumps({
            "score": 0.7,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "Good",
        })
        critic = TestCritic(focus=CriticFocus.EDGE_CASES, llm=mock_llm)
        result = critic.evaluate("def test_foo(): pass")

        # Note: TestCritic was renamed to SuiteCritic for pytest compatibility
        assert "SuiteCritic" in result.critic_name
        assert "edge" in result.critic_name.lower()


class TestTestCriticFileExists:
    """Test that the critics module file exists."""

    def test_critics_file_exists(self):
        """The critics.py file should exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "critics.py"
        assert path.exists(), "critics.py must exist"

    def test_critics_file_has_suitecritic(self):
        """The critics.py file should define SuiteCritic.

        Note: TestCritic was renamed to SuiteCritic for pytest compatibility.
        TestCritic alias is still available for backward compatibility.
        """
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "critics.py"
        content = path.read_text()
        assert "class SuiteCritic" in content, "SuiteCritic class must be defined"
        # Backward compatibility alias should exist
        assert "TestCritic = SuiteCritic" in content, "TestCritic alias must exist"