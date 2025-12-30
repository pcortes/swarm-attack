"""Critic base class and CriticScore dataclass for internal validation."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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


@dataclass
class ValidationResult:
    """Result from ValidationLayer consensus mechanism."""

    artifact_type: str
    artifact_id: str
    approved: bool
    scores: list[CriticScore]
    blocking_issues: list[str]
    consensus_summary: str
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "approved": self.approved,
            "scores": [s.to_dict() for s in self.scores],
            "blocking_issues": self.blocking_issues,
            "consensus_summary": self.consensus_summary,
            "human_review_required": self.human_review_required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        """Deserialize from dictionary."""
        return cls(
            artifact_type=data["artifact_type"],
            artifact_id=data["artifact_id"],
            approved=data["approved"],
            scores=[CriticScore.from_dict(s) for s in data.get("scores", [])],
            blocking_issues=data.get("blocking_issues", []),
            consensus_summary=data.get("consensus_summary", ""),
            human_review_required=data.get("human_review_required", False),
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

    def __init__(self, focus: CriticFocus, llm: Any, weight: float = 1.0) -> None:
        """Initialize SpecCritic.

        Args:
            focus: Must be COMPLETENESS, FEASIBILITY, or SECURITY
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)

        Raises:
            ValueError: If focus is not supported for spec evaluation
        """
        if focus not in self.PROMPTS:
            raise ValueError(
                f"SpecCritic does not support focus {focus}. "
                f"Supported: {list(self.PROMPTS.keys())}"
            )
        super().__init__(focus, llm, weight)

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a spec artifact.

        Args:
            artifact: The spec content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate if too long
        spec_content = artifact
        if len(spec_content) > self.MAX_SPEC_CHARS:
            spec_content = spec_content[: self.MAX_SPEC_CHARS] + "\n\n[TRUNCATED]"

        # Get the prompt for this focus
        prompt = self.PROMPTS[self.focus].format(spec_content=spec_content)

        # Call LLM
        response = self.llm.generate(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return CriticScore(
                critic_name=f"SpecCritic-{self.focus.value}",
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError) as e:
            # Return a failed score if parsing fails
            return CriticScore(
                critic_name=f"SpecCritic-{self.focus.value}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Failed to parse LLM response: {e}"],
                suggestions=["Retry evaluation"],
                reasoning=f"Parse error: {response[:200]}",
            )


class CodeCritic(Critic):
    """Critic for evaluating code quality.
    
    Supports STYLE and SECURITY focus areas.
    """

    # Maximum characters to include in prompt
    MAX_CODE_CHARS = 6000

    # Focus-specific prompts
    PROMPTS = {
        CriticFocus.STYLE: """You are a code style critic. Evaluate the following code for:
- Code readability and clarity
- Naming conventions (variables, functions, classes)
- Code organization and structure
- Comments and documentation
- Consistency with common patterns
- DRY principle adherence

Code content (truncated if long):
{code_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is excellent style>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of style violations or concerns>],
    "suggestions": [<list of style improvements>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.SECURITY: """You are a security-focused code critic. Evaluate the following code for:
- SQL injection vulnerabilities
- Command injection risks
- Path traversal issues
- Hardcoded secrets or credentials
- Unsafe deserialization
- Input validation gaps
- Authentication/authorization flaws

Code content (truncated if long):
{code_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is fully secure>,
    "approved": <boolean, true if no critical security issues>,
    "issues": [<list of security vulnerabilities>],
    "suggestions": [<list of security fixes>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",
    }

    def __init__(self, focus: CriticFocus, llm: Any, weight: float = 1.0) -> None:
        """Initialize CodeCritic.

        Args:
            focus: Must be STYLE or SECURITY
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)

        Raises:
            ValueError: If focus is not supported for code evaluation
        """
        if focus not in self.PROMPTS:
            raise ValueError(
                f"CodeCritic does not support focus {focus}. "
                f"Supported: {list(self.PROMPTS.keys())}"
            )
        super().__init__(focus, llm, weight)

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a code artifact.

        Args:
            artifact: The code content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate if too long
        code_content = artifact
        if len(code_content) > self.MAX_CODE_CHARS:
            code_content = code_content[: self.MAX_CODE_CHARS] + "\n\n# [TRUNCATED]"

        # Get the prompt for this focus
        prompt = self.PROMPTS[self.focus].format(code_content=code_content)

        # Call LLM
        response = self.llm.generate(prompt)

        # Parse JSON response
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return CriticScore(
                critic_name=f"CodeCritic-{self.focus.value}",
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError) as e:
            return CriticScore(
                critic_name=f"CodeCritic-{self.focus.value}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Failed to parse LLM response: {e}"],
                suggestions=["Retry evaluation"],
                reasoning=f"Parse error: {response[:200]}",
            )


class SuiteCritic(Critic):
    """Critic for evaluating test quality.

    Supports COVERAGE and EDGE_CASES focus areas.
    """

    # Maximum characters to include in prompt
    MAX_TEST_CHARS = 6000

    # Focus-specific prompts
    PROMPTS = {
        CriticFocus.COVERAGE: """You are a test coverage critic. Evaluate the following test code for:
- Are all major code paths tested?
- Are both success and failure cases covered?
- Are all public methods/functions tested?
- Are boundary conditions tested?
- Is the test suite comprehensive?

Test content (truncated if long):
{test_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is complete coverage>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of coverage gaps>],
    "suggestions": [<list of additional tests needed>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.EDGE_CASES: """You are a test edge cases critic. Evaluate the following test code for:
- Are edge cases covered (empty inputs, nulls, max values)?
- Are error conditions tested?
- Are race conditions considered?
- Are timeout scenarios tested?
- Are malformed inputs tested?

Test content (truncated if long):
{test_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is excellent edge case coverage>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of missing edge cases>],
    "suggestions": [<list of edge case tests to add>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",
    }

    def __init__(self, focus: CriticFocus, llm: Any, weight: float = 1.0) -> None:
        """Initialize SuiteCritic.

        Args:
            focus: Must be COVERAGE or EDGE_CASES
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)

        Raises:
            ValueError: If focus is not supported for test evaluation
        """
        if focus not in self.PROMPTS:
            raise ValueError(
                f"SuiteCritic does not support focus {focus}. "
                f"Supported: {list(self.PROMPTS.keys())}"
            )
        super().__init__(focus, llm, weight)

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a test artifact.

        Args:
            artifact: The test content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate if too long
        test_content = artifact
        if len(test_content) > self.MAX_TEST_CHARS:
            test_content = test_content[: self.MAX_TEST_CHARS] + "\n\n# [TRUNCATED]"

        # Get the prompt for this focus
        prompt = self.PROMPTS[self.focus].format(test_content=test_content)

        # Call LLM
        response = self.llm.generate(prompt)

        # Parse JSON response
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return CriticScore(
                critic_name=f"SuiteCritic-{self.focus.value}",
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError) as e:
            return CriticScore(
                critic_name=f"SuiteCritic-{self.focus.value}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Failed to parse LLM response: {e}"],
                suggestions=["Retry evaluation"],
                reasoning=f"Parse error: {response[:200]}",
            )


class ValidationLayer:
    """Orchestrates multiple critics and builds consensus for artifact validation.
    
    Security is NOT a democracy - any security veto blocks approval.
    Majority vote: 60% weighted approval threshold for non-security critics.
    """

    APPROVAL_THRESHOLD = 0.6  # 60% weighted approval required

    def __init__(self, llm: Any) -> None:
        """Initialize ValidationLayer with critic sets.

        Args:
            llm: The LLM instance to use for all critics
        """
        self.llm = llm

        # Initialize critic sets for each artifact type
        self.spec_critics: list[Critic] = [
            SpecCritic(CriticFocus.COMPLETENESS, llm, weight=1.0),
            SpecCritic(CriticFocus.FEASIBILITY, llm, weight=1.0),
            SpecCritic(CriticFocus.SECURITY, llm, weight=1.5),  # Security weighted higher
        ]

        self.code_critics: list[Critic] = [
            CodeCritic(CriticFocus.STYLE, llm, weight=1.0),
            CodeCritic(CriticFocus.SECURITY, llm, weight=1.5),  # Security weighted higher
        ]

        self.test_critics: list[Critic] = [
            SuiteCritic(CriticFocus.COVERAGE, llm, weight=1.0),
            SuiteCritic(CriticFocus.EDGE_CASES, llm, weight=1.0),
        ]

    def _get_critics_for_type(self, artifact_type: str) -> list[Critic]:
        """Get the appropriate critic set for an artifact type.

        Args:
            artifact_type: One of "spec", "code", or "test"

        Returns:
            List of critics for that artifact type
        """
        critic_map = {
            "spec": self.spec_critics,
            "code": self.code_critics,
            "test": self.test_critics,
        }
        return critic_map.get(artifact_type, self.spec_critics)

    def validate(
        self,
        artifact: str,
        artifact_type: str,
        artifact_id: str,
    ) -> ValidationResult:
        """Validate an artifact using consensus from multiple critics.

        Args:
            artifact: The artifact content to validate
            artifact_type: Type of artifact ("spec", "code", or "test")
            artifact_id: Unique identifier for the artifact

        Returns:
            ValidationResult with consensus decision
        """
        critics = self._get_critics_for_type(artifact_type)
        scores: list[CriticScore] = []
        blocking_issues: list[str] = []
        security_blocked = False

        # Evaluate with all critics
        for critic in critics:
            score = critic.evaluate(artifact)
            scores.append(score)

            # Check for security veto
            if critic.has_veto and not score.approved:
                security_blocked = True
                blocking_issues.extend(score.issues)

        # Calculate weighted approval
        total_weight = sum(c.weight for c in critics)
        weighted_approval = sum(
            c.weight for c, s in zip(critics, scores) if s.approved
        ) / total_weight if total_weight > 0 else 0.0

        # Calculate average score
        avg_score = sum(s.score * c.weight for c, s in zip(critics, scores)) / total_weight if total_weight > 0 else 0.0

        # Determine approval
        # Security veto blocks everything
        # Otherwise, need 60% weighted approval
        approved = not security_blocked and weighted_approval >= self.APPROVAL_THRESHOLD

        # Build consensus summary
        if security_blocked:
            consensus_summary = f"Blocked by security critic. Average score: {avg_score:.2f}"
        elif approved:
            consensus_summary = f"Approved with {weighted_approval:.0%} consensus. Average score: {avg_score:.2f}"
        else:
            consensus_summary = f"Rejected with {weighted_approval:.0%} approval (needs 60%). Average score: {avg_score:.2f}"

        # Determine if human review is required
        human_review_required = security_blocked or not approved

        return ValidationResult(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            approved=approved,
            scores=scores,
            blocking_issues=blocking_issues,
            consensus_summary=consensus_summary,
            human_review_required=human_review_required,
        )


class SuiteCritic(Critic):
    """Critic for evaluating test quality (BUG-13/14: renamed from TestingCritic).

    Supports COVERAGE and EDGE_CASES focus areas.
    """

    # Maximum characters to include in prompt
    MAX_TEST_CHARS = 6000

    # Focus-specific prompts
    PROMPTS = {
        CriticFocus.COVERAGE: """You are a test coverage critic. Evaluate the following test code for:
- Are all major code paths tested?
- Are both success and failure cases covered?
- Are all public methods/functions tested?
- Are boundary conditions tested?
- Is the test suite comprehensive?

Test content (truncated if long):
{test_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is complete coverage>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of coverage gaps>],
    "suggestions": [<list of additional tests needed>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",

        CriticFocus.EDGE_CASES: """You are a test edge cases critic. Evaluate the following test code for:
- Are edge cases covered (empty inputs, nulls, max values)?
- Are error conditions tested?
- Are race conditions considered?
- Are timeout scenarios tested?
- Are malformed inputs tested?

Test content (truncated if long):
{test_content}

Respond with a JSON object containing:
{{
    "score": <float 0-1, where 1 is excellent edge case coverage>,
    "approved": <boolean, true if score >= 0.7>,
    "issues": [<list of missing edge cases>],
    "suggestions": [<list of edge case tests to add>],
    "reasoning": "<brief explanation of your evaluation>"
}}

Return ONLY the JSON object.""",
    }

    def __init__(self, focus: CriticFocus, llm: Any, weight: float = 1.0) -> None:
        """Initialize SuiteCritic.

        Args:
            focus: Must be COVERAGE or EDGE_CASES
            llm: The LLM instance to use for evaluation
            weight: Weight for this critic's score (default 1.0)

        Raises:
            ValueError: If focus is not supported for test evaluation
        """
        if focus not in self.PROMPTS:
            raise ValueError(
                f"SuiteCritic does not support focus {focus}. "
                f"Supported: {list(self.PROMPTS.keys())}"
            )
        super().__init__(focus, llm, weight)

    def evaluate(self, artifact: str) -> CriticScore:
        """Evaluate a test artifact.

        Args:
            artifact: The test content to evaluate

        Returns:
            CriticScore with evaluation results
        """
        # Truncate if too long
        test_content = artifact
        if len(test_content) > self.MAX_TEST_CHARS:
            test_content = test_content[: self.MAX_TEST_CHARS] + "\n\n# [TRUNCATED]"

        # Get the prompt for this focus
        prompt = self.PROMPTS[self.focus].format(test_content=test_content)

        # Call LLM
        response = self.llm.generate(prompt)

        # Parse JSON response
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            return CriticScore(
                critic_name=f"SuiteCritic-{self.focus.value}",
                focus=self.focus,
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError) as e:
            return CriticScore(
                critic_name=f"SuiteCritic-{self.focus.value}",
                focus=self.focus,
                score=0.0,
                approved=False,
                issues=[f"Failed to parse LLM response: {e}"],
                suggestions=["Retry evaluation"],
                reasoning=f"Parse error: {response[:200]}",
            )


# BUG-13/14: Backward compatibility aliases (not class definitions, so pytest won't collect)
TestingCritic = SuiteCritic
TestCritic = SuiteCritic