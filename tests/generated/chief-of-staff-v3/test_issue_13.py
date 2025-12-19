"""Tests for Critic base class and CriticScore dataclass."""

import pytest
from abc import ABC
from enum import Enum

from swarm_attack.chief_of_staff.critics import (
    Critic,
    CriticFocus,
    CriticScore,
)


class TestCriticFocus:
    """Tests for CriticFocus enum."""

    def test_completeness_exists(self):
        assert hasattr(CriticFocus, 'COMPLETENESS')

    def test_feasibility_exists(self):
        assert hasattr(CriticFocus, 'FEASIBILITY')

    def test_security_exists(self):
        assert hasattr(CriticFocus, 'SECURITY')

    def test_style_exists(self):
        assert hasattr(CriticFocus, 'STYLE')

    def test_coverage_exists(self):
        assert hasattr(CriticFocus, 'COVERAGE')

    def test_edge_cases_exists(self):
        assert hasattr(CriticFocus, 'EDGE_CASES')

    def test_is_enum(self):
        assert issubclass(CriticFocus, Enum)

    def test_all_focus_types_count(self):
        """Ensure we have exactly 6 focus types."""
        assert len(CriticFocus) == 6


class TestCriticScore:
    """Tests for CriticScore dataclass."""

    def test_critic_score_has_critic_name(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.8,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="test reasoning"
        )
        assert score.critic_name == "test_critic"

    def test_critic_score_has_focus(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.SECURITY,
            score=0.9,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="test reasoning"
        )
        assert score.focus == CriticFocus.SECURITY

    def test_critic_score_has_score(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.75,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="test reasoning"
        )
        assert score.score == 0.75

    def test_critic_score_has_approved(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.8,
            approved=False,
            issues=["missing tests"],
            suggestions=[],
            reasoning="test reasoning"
        )
        assert score.approved is False

    def test_critic_score_has_issues(self):
        issues = ["issue 1", "issue 2"]
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.5,
            approved=False,
            issues=issues,
            suggestions=[],
            reasoning="test reasoning"
        )
        assert score.issues == issues

    def test_critic_score_has_suggestions(self):
        suggestions = ["suggestion 1", "suggestion 2"]
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.STYLE,
            score=0.7,
            approved=True,
            issues=[],
            suggestions=suggestions,
            reasoning="test reasoning"
        )
        assert score.suggestions == suggestions

    def test_critic_score_has_reasoning(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.8,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="Detailed reasoning here"
        )
        assert score.reasoning == "Detailed reasoning here"

    def test_to_dict_returns_dict(self):
        score = CriticScore(
            critic_name="test_critic",
            focus=CriticFocus.COMPLETENESS,
            score=0.8,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="test reasoning"
        )
        result = score.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        score = CriticScore(
            critic_name="my_critic",
            focus=CriticFocus.SECURITY,
            score=0.95,
            approved=True,
            issues=["issue1"],
            suggestions=["suggestion1"],
            reasoning="good reasoning"
        )
        result = score.to_dict()
        assert result["critic_name"] == "my_critic"
        assert result["focus"] == "SECURITY"
        assert result["score"] == 0.95
        assert result["approved"] is True
        assert result["issues"] == ["issue1"]
        assert result["suggestions"] == ["suggestion1"]
        assert result["reasoning"] == "good reasoning"

    def test_from_dict_creates_instance(self):
        data = {
            "critic_name": "test_critic",
            "focus": "COMPLETENESS",
            "score": 0.8,
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reasoning": "test"
        }
        score = CriticScore.from_dict(data)
        assert isinstance(score, CriticScore)

    def test_from_dict_restores_all_fields(self):
        data = {
            "critic_name": "restored_critic",
            "focus": "FEASIBILITY",
            "score": 0.65,
            "approved": False,
            "issues": ["problem1", "problem2"],
            "suggestions": ["fix1"],
            "reasoning": "detailed reasoning"
        }
        score = CriticScore.from_dict(data)
        assert score.critic_name == "restored_critic"
        assert score.focus == CriticFocus.FEASIBILITY
        assert score.score == 0.65
        assert score.approved is False
        assert score.issues == ["problem1", "problem2"]
        assert score.suggestions == ["fix1"]
        assert score.reasoning == "detailed reasoning"

    def test_roundtrip_serialization(self):
        original = CriticScore(
            critic_name="roundtrip_critic",
            focus=CriticFocus.EDGE_CASES,
            score=0.88,
            approved=True,
            issues=["minor issue"],
            suggestions=["consider edge case"],
            reasoning="thorough analysis"
        )
        roundtrip = CriticScore.from_dict(original.to_dict())
        assert roundtrip.critic_name == original.critic_name
        assert roundtrip.focus == original.focus
        assert roundtrip.score == original.score
        assert roundtrip.approved == original.approved
        assert roundtrip.issues == original.issues
        assert roundtrip.suggestions == original.suggestions
        assert roundtrip.reasoning == original.reasoning


class TestCritic:
    """Tests for Critic base class."""

    def test_critic_is_abstract(self):
        """Critic should be an abstract base class."""
        assert issubclass(Critic, ABC)

    def test_critic_constructor_takes_focus(self):
        """Critic constructor accepts focus parameter."""
        class TestCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="test",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = TestCritic(focus=CriticFocus.COMPLETENESS, llm=None)
        assert critic.focus == CriticFocus.COMPLETENESS

    def test_critic_constructor_takes_llm(self):
        """Critic constructor accepts llm parameter."""
        class TestCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="test",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        mock_llm = object()
        critic = TestCritic(focus=CriticFocus.STYLE, llm=mock_llm)
        assert critic.llm is mock_llm

    def test_critic_constructor_weight_default(self):
        """Critic weight defaults to 1.0."""
        class TestCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="test",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = TestCritic(focus=CriticFocus.COVERAGE, llm=None)
        assert critic.weight == 1.0

    def test_critic_constructor_accepts_custom_weight(self):
        """Critic constructor accepts custom weight parameter."""
        class TestCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="test",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = TestCritic(focus=CriticFocus.FEASIBILITY, llm=None, weight=0.5)
        assert critic.weight == 0.5

    def test_has_veto_true_for_security(self):
        """SECURITY focus has veto power."""
        class SecurityCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="security",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = SecurityCritic(focus=CriticFocus.SECURITY, llm=None)
        assert critic.has_veto is True

    def test_has_veto_false_for_completeness(self):
        """COMPLETENESS focus does not have veto power."""
        class CompletenessCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="completeness",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = CompletenessCritic(focus=CriticFocus.COMPLETENESS, llm=None)
        assert critic.has_veto is False

    def test_has_veto_false_for_style(self):
        """STYLE focus does not have veto power."""
        class StyleCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="style",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = StyleCritic(focus=CriticFocus.STYLE, llm=None)
        assert critic.has_veto is False

    def test_has_veto_false_for_feasibility(self):
        """FEASIBILITY focus does not have veto power."""
        class FeasibilityCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="feasibility",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = FeasibilityCritic(focus=CriticFocus.FEASIBILITY, llm=None)
        assert critic.has_veto is False

    def test_has_veto_false_for_coverage(self):
        """COVERAGE focus does not have veto power."""
        class CoverageCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="coverage",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = CoverageCritic(focus=CriticFocus.COVERAGE, llm=None)
        assert critic.has_veto is False

    def test_has_veto_false_for_edge_cases(self):
        """EDGE_CASES focus does not have veto power."""
        class EdgeCasesCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="edge_cases",
                    focus=self.focus,
                    score=1.0,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning="test"
                )

        critic = EdgeCasesCritic(focus=CriticFocus.EDGE_CASES, llm=None)
        assert critic.has_veto is False

    def test_evaluate_is_abstract(self):
        """evaluate method must be implemented by subclasses."""
        # Attempting to instantiate Critic directly should fail
        with pytest.raises(TypeError):
            Critic(focus=CriticFocus.COMPLETENESS, llm=None)

    def test_subclass_can_implement_evaluate(self):
        """Subclasses can implement evaluate method."""
        class ConcreteCritic(Critic):
            def evaluate(self, artifact: str) -> CriticScore:
                return CriticScore(
                    critic_name="concrete",
                    focus=self.focus,
                    score=0.9,
                    approved=True,
                    issues=[],
                    suggestions=[],
                    reasoning=f"Evaluated: {artifact}"
                )

        critic = ConcreteCritic(focus=CriticFocus.COMPLETENESS, llm=None)
        result = critic.evaluate("test artifact")
        assert isinstance(result, CriticScore)
        assert result.score == 0.9
        assert "test artifact" in result.reasoning