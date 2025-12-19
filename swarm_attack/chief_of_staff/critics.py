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

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a spec and return a score.

        Args:
            artifact: The spec content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate spec if too long
        spec_content = artifact[:self.MAX_SPEC_CHARS]
        if len(artifact) > self.MAX_SPEC_CHARS:
            spec_content += "\n... [truncated]"

        # Get the focus-specific prompt
        prompt_template = self.PROMPTS.get(self.focus)
        if not prompt_template:
            return CriticScore(
                critic_name=f"SpecCritic-{self.focus.name}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Unsupported focus: {self.focus.name}"],
                suggestions=[],
                reasoning=f"SpecCritic does not support {self.focus.name} focus",
            )

        prompt = prompt_template.format(spec_content=spec_content)

        # Call LLM
        response = self.llm(prompt)

        # Parse response
        return self._parse_response(response)

    def _parse_response(self, response: str) -> CriticScore:
        """Parse LLM response into CriticScore.

        Args:
            response: Raw LLM response

        Returns:
            CriticScore parsed from response
        """
        critic_name = f"SpecCritic-{self.focus.name}"

        # Try to extract JSON from response
        try:
            # Remove code fences if present
            json_str = response
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            return CriticScore(
                critic_name=critic_name,
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return CriticScore(
                critic_name=critic_name,
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=["Failed to parse LLM response"],
                suggestions=[],
                reasoning=f"Failed to parse response: {response[:100]}...",
            )


class CodeCritic(Critic):
    """Critic for evaluating code changes.
    
    Supports STYLE and SECURITY focus areas.
    """

    # Maximum characters to include in prompt
    MAX_CODE_DIFF_CHARS = 4000

    # Focus-specific prompts
    PROMPTS = {
        CriticFocus.STYLE: """You are a code style critic. Evaluate the following code diff for:
- Naming conventions (variables, functions, classes)
- Code structure and organization
- Readability and clarity
- Consistent formatting
- Appropriate comments and documentation
- Code complexity and maintainability

Code diff (truncated if long):
{code_diff}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is excellent style>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of style issues found>],
    "suggestions": [<list of improvements for better style>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.SECURITY: """You are a security-focused code critic. Evaluate the following code diff for:
- Security vulnerabilities (SQL injection, XSS, command injection, etc.)
- Injection attacks and unsafe string operations
- Unsafe operations (eval, exec, shell commands with user input)
- Hardcoded secrets, API keys, or credentials
- Insecure data handling
- Missing input validation or sanitization
- Unsafe deserialization

Code diff (truncated if long):
{code_diff}

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

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a code diff and return a score.

        Args:
            artifact: The code diff to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate code diff if too long
        code_diff = artifact[:self.MAX_CODE_DIFF_CHARS]
        if len(artifact) > self.MAX_CODE_DIFF_CHARS:
            code_diff += "\n... [truncated]"

        # Get the focus-specific prompt
        prompt_template = self.PROMPTS.get(self.focus)
        if not prompt_template:
            return CriticScore(
                critic_name=f"CodeCritic-{self.focus.name}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Unsupported focus: {self.focus.name}"],
                suggestions=[],
                reasoning=f"CodeCritic does not support {self.focus.name} focus",
            )

        prompt = prompt_template.format(code_diff=code_diff)

        # Call LLM
        response = self.llm(prompt)

        # Parse response
        return self._parse_response(response)

    def _parse_response(self, response: str) -> CriticScore:
        """Parse LLM response into CriticScore.

        Args:
            response: Raw LLM response

        Returns:
            CriticScore parsed from response
        """
        critic_name = f"CodeCritic-{self.focus.name}"

        # Try to extract JSON from response
        try:
            # Remove code fences if present
            json_str = response
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            return CriticScore(
                critic_name=critic_name,
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return CriticScore(
                critic_name=critic_name,
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=["Failed to parse LLM response"],
                suggestions=[],
                reasoning=f"Failed to parse response: {response[:100]}...",
            )