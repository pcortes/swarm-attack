"""Critic base class and CriticScore dataclass for internal validation."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CriticFocus(Enum):
    """Focus areas for critics."""

    COMPLETENESS = "completeness"
    FEASIBILITY = "feasibility"
    SECURITY = "security"
    STYLE = "style"
    COVERAGE = "coverage"
    EDGE_CASES = "edge_cases"


@dataclass
class CriticScore:
    """Score from a critic evaluation."""

    critic_name: str
    focus: CriticFocus
    score: float  # 0-1
    approved: bool
    issues: list[str]
    suggestions: list[str]
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "critic_name": self.critic_name,
            "focus": self.focus.name,
            "score": self.score,
            "approved": self.approved,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticScore":
        """Deserialize from dictionary."""
        return cls(
            critic_name=data["critic_name"],
            focus=CriticFocus[data["focus"]],
            score=data["score"],
            approved=data["approved"],
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            reasoning=data.get("reasoning", ""),
        )


class Critic(ABC):
    """Base class for internal validation critics."""

    def __init__(
        self,
        focus: CriticFocus,
        llm: Any,
        weight: float = 1.0,
    ) -> None:
        """Initialize critic.

        Args:
            focus: The focus area for this critic
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)
        """
        self.focus = focus
        self.llm = llm
        self.weight = weight

    @property
    def has_veto(self) -> bool:
        """Whether this critic has veto power (blocks consensus).

        Only SECURITY focus has veto power.
        """
        return self.focus == CriticFocus.SECURITY

    @abstractmethod
    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate an artifact and return a score.

        Args:
            artifact: The artifact to evaluate (code, spec, plan, etc.)

        Returns:
            CriticScore with evaluation results
        """
        pass


class SpecCritic(Critic):
    """Critic for evaluating engineering specs.
    
    Supports COMPLETENESS, FEASIBILITY, and SECURITY focus areas.
    """

    # Maximum characters to include in prompt
    MAX_SPEC_CHARS = 4000

    # Focus-specific prompts
    PROMPTS = {
        CriticFocus.COMPLETENESS: """You are a spec completeness critic. Evaluate the following engineering spec for:
- Missing sections or gaps in requirements
- Incomplete feature descriptions
- Undefined edge cases
- Missing acceptance criteria
- Gaps in the specification

Spec content (truncated if long):
{spec_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is complete>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of specific missing elements or gaps>],
    "suggestions": [<list of improvements to make spec complete>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.FEASIBILITY: """You are a spec feasibility critic. Evaluate the following engineering spec for:
- Can it be implemented with current technology?
- Are requirements clear enough to implement?
- Are there unclear or ambiguous requirements?
- Are there unrealistic expectations?
- Is the scope well-defined?

Spec content (truncated if long):
{spec_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is fully feasible>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of unclear or infeasible requirements>],
    "suggestions": [<list of clarifications needed>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.SECURITY: """You are a security-focused spec critic. Evaluate the following engineering spec for:
- SQL injection risks or database security gaps
- Authentication and authorization gaps
- Data exposure in logs or responses
- Input validation issues
- Cross-site scripting (XSS) risks
- Sensitive data handling

Spec content (truncated if long):
{spec_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is fully secure>,
    "approved": <boolean, true if no critical security issues>,
    "issues": [<list of security vulnerabilities or risks>],
    "suggestions": [<list of security improvements>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",
    }

    def __init__(
        self,
        focus: CriticFocus,
        llm: Any,
        weight: float = 1.0,
    ) -> None:
        """Initialize SpecCritic.

        Args:
            focus: The focus area (COMPLETENESS, FEASIBILITY, or SECURITY)
            llm: The LLM callable to use for evaluation
            weight: Weight for this critic's score (default 1.0)
        """
        super().__init__(focus=focus, llm=llm, weight=weight)

    def evaluate(self, spec_content: str) -> CriticScore:
        """Evaluate a spec and return a score.

        Args:
            spec_content: The engineering spec content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate spec content to max chars
        truncated_spec = spec_content[:self.MAX_SPEC_CHARS]
        
        # Get focus-specific prompt or use default completeness
        prompt_template = self.PROMPTS.get(
            self.focus, 
            self.PROMPTS[CriticFocus.COMPLETENESS]
        )
        prompt = prompt_template.format(spec_content=truncated_spec)
        
        # Call LLM
        response = self.llm(prompt)
        
        # Parse response
        parsed = self._parse_llm_response(response)
        
        return CriticScore(
            critic_name="SpecCritic",
            focus=self.focus,
            score=parsed["score"],
            approved=parsed["approved"],
            issues=parsed["issues"],
            suggestions=parsed["suggestions"],
            reasoning=parsed["reasoning"],
        )

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response into expected format.

        Args:
            response: Raw LLM response string

        Returns:
            Parsed dictionary with score, approved, issues, suggestions, reasoning
        """
        # Try to extract JSON from response
        # First try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find bare JSON object
        json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Try more aggressive JSON extraction
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(response[start:end + 1])
            except json.JSONDecodeError:
                pass
        
        # Fallback default
        return {
            "score": 0.0,
            "approved": False,
            "issues": ["Failed to parse LLM response"],
            "suggestions": [],
            "reasoning": f"Could not parse response: {response[:200]}",
        }