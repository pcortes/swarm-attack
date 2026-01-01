"""
Complexity Gate Agent for Feature Swarm.

Pre-execution complexity check that estimates whether an issue is too complex
for the CoderAgent to complete within max_turns. Uses cheap LLM (Haiku) for
estimation to avoid burning expensive Opus tokens on doomed attempts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent
from swarm_attack.events.types import EventType

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


@dataclass
class ComplexityEstimate:
    """Result of complexity estimation."""

    estimated_turns: int
    complexity_score: float  # 0.0 - 1.0
    needs_split: bool
    split_suggestions: list[str]  # Empty if needs_split=False
    confidence: float  # 0.0 - 1.0
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "estimated_turns": self.estimated_turns,
            "complexity_score": self.complexity_score,
            "needs_split": self.needs_split,
            "split_suggestions": self.split_suggestions,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplexityEstimate:
        """Create from dictionary."""
        return cls(
            estimated_turns=data.get("estimated_turns", 15),
            complexity_score=data.get("complexity_score", 0.5),
            needs_split=data.get("needs_split", False),
            split_suggestions=data.get("split_suggestions", []),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", ""),
        )


class ComplexityGateAgent(BaseAgent):
    """
    Pre-execution complexity check using tiered estimation.

    Strategy:
    1. Heuristic check (free, instant) for obvious cases
    2. LLM estimation (cheap Haiku) for borderline cases

    This prevents expensive Opus tokens being wasted on issues that will
    inevitably timeout due to complexity.
    """

    name = "complexity_gate"

    # Thresholds (tunable based on observed coder performance)
    MAX_ACCEPTANCE_CRITERIA = 10
    MAX_METHODS = 6
    MAX_ESTIMATED_TURNS = 20

    # Heuristic thresholds for instant decisions (no LLM needed)
    INSTANT_PASS_CRITERIA = 5
    INSTANT_PASS_METHODS = 3
    INSTANT_FAIL_CRITERIA = 12
    INSTANT_FAIL_METHODS = 8

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Complexity Gate agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def estimate_complexity(
        self,
        issue: dict[str, Any],
        spec_content: Optional[str] = None,
    ) -> ComplexityEstimate:
        """
        Estimate complexity of an issue before execution.

        Uses tiered approach:
        1. Heuristic check (free, instant) for obvious cases
        2. LLM estimation (cheap Haiku) for borderline cases

        Args:
            issue: Issue dict with title, body, labels, estimated_size
            spec_content: Optional spec for additional context

        Returns:
            ComplexityEstimate with decision and suggestions
        """
        # Extract metrics from issue
        body = issue.get("body", "")
        title = issue.get("title", "")
        estimated_size = issue.get("estimated_size", "medium")

        criteria_count = self._count_acceptance_criteria(body)
        method_count = self._count_methods_to_implement(body)

        self._log("complexity_gate_metrics", {
            "title": title,
            "criteria_count": criteria_count,
            "method_count": method_count,
            "estimated_size": estimated_size,
        })

        # Tier 1: Instant pass (obviously simple)
        if criteria_count <= self.INSTANT_PASS_CRITERIA and method_count <= self.INSTANT_PASS_METHODS:
            return ComplexityEstimate(
                estimated_turns=10,
                complexity_score=0.3,
                needs_split=False,
                split_suggestions=[],
                confidence=0.95,
                reasoning=f"Simple issue: {criteria_count} criteria, {method_count} methods",
            )

        # Tier 2: Instant fail (obviously too complex)
        if criteria_count > self.INSTANT_FAIL_CRITERIA or method_count > self.INSTANT_FAIL_METHODS:
            suggestions = self._generate_split_suggestions(issue, criteria_count, method_count)
            return ComplexityEstimate(
                estimated_turns=35,
                complexity_score=0.9,
                needs_split=True,
                split_suggestions=suggestions,
                confidence=0.95,
                reasoning=f"Too complex: {criteria_count} criteria, {method_count} methods exceeds limits",
            )

        # Tier 3: Borderline - use LLM for refined estimation (implemented in Issue #4)
        return self._llm_estimate(issue, criteria_count, method_count, spec_content)

    def _count_acceptance_criteria(self, body: str) -> int:
        """Count checkboxes in issue body (acceptance criteria)."""
        # Match markdown checkboxes: - [ ] or - [x]
        pattern = r"- \[[x ]\]"
        matches = re.findall(pattern, body, re.IGNORECASE)
        return len(matches)

    def _count_methods_to_implement(self, body: str) -> int:
        """
        Count method signatures mentioned in issue body.

        Looks for patterns like:
        - `method_name()` or `method_name(args)`
        - `def method_name`
        - `async def method_name`
        - Method names in acceptance criteria
        """
        patterns = [
            r"`(\w+)\([^)]*\)`",  # `method_name()` or `method_name(args)`
            r"(?:async\s+)?def\s+(\w+)",  # def method_name or async def method_name
            r"implement\s+`?(\w+)`?",  # implement method_name
        ]

        methods = set()
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            methods.update(m.lower() for m in matches)

        # Filter out common false positives
        false_positives = {
            "self", "cls", "none", "true", "false", "dict", "list", "str", "int", "float",
            "these", "this", "that", "method", "function", "class", "module", "file",
        }
        methods = methods - false_positives

        return len(methods)

    def _generate_split_suggestions(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
    ) -> list[str]:
        """Generate actionable split suggestions based on issue content."""
        suggestions = []
        body = issue.get("body", "").lower()

        # Check for trigger patterns (like CheckpointSystem)
        trigger_matches = re.findall(r"(\w+)_trigger|trigger[_\s](\w+)", body, re.IGNORECASE)
        if len(trigger_matches) >= 4:
            suggestions.append(
                f"Split by trigger type: Group {len(trigger_matches)} triggers into 2-3 issues of ~3 triggers each"
            )

        # Check for CRUD patterns
        crud_patterns = ["create", "read", "update", "delete", "get", "set", "add", "remove"]
        crud_found = [p for p in crud_patterns if p in body]
        if len(crud_found) >= 3:
            suggestions.append(
                "Split by operation: Separate CRUD operations into distinct issues"
            )

        # Check for layer patterns
        layer_patterns = ["model", "api", "endpoint", "ui", "frontend", "backend", "database", "config"]
        layers_found = [p for p in layer_patterns if p in body]
        if len(layers_found) >= 2:
            suggestions.append(
                f"Split by layer: Separate {', '.join(layers_found[:3])} into distinct issues"
            )

        # Generic fallback
        if not suggestions:
            if method_count > 6:
                suggestions.append(
                    f"Split by method groups: {method_count} methods -> 2-3 issues of ~3 methods each"
                )
            if criteria_count > 8:
                suggestions.append(
                    f"Split by acceptance criteria: {criteria_count} criteria -> 2-3 issues of ~4 criteria each"
                )

        return suggestions or ["Consider breaking this issue into smaller, focused pieces"]

    def _llm_estimate(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
        spec_content: Optional[str] = None,
    ) -> ComplexityEstimate:
        """
        Use LLM for refined complexity estimation on borderline cases.

        Uses Haiku model for cost efficiency.
        """
        if not self._llm:
            # No LLM available - use heuristic fallback
            # Formula calibrated to match issue sizing guidelines:
            # Small (1-4 criteria): ~10 turns
            # Medium (5-8 criteria): ~15 turns
            # Large (9-12 criteria): ~20 turns
            estimated_turns = 5 + criteria_count + int(method_count * 1.5)
            needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
            return ComplexityEstimate(
                estimated_turns=estimated_turns,
                complexity_score=min(estimated_turns / 30, 1.0),
                needs_split=needs_split,
                split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                confidence=0.6,
                reasoning="Heuristic estimate (no LLM available)",
            )

        # Build prompt for Haiku
        prompt = self._build_estimation_prompt(issue, criteria_count, method_count, spec_content)

        try:
            # Use Haiku for cheap estimation
            result = self.llm.run(
                prompt,
                allowed_tools=[],
                max_turns=1,
                model="haiku",  # Cheap, fast model
            )

            # Track cost
            self._total_cost += result.cost_usd

            # Parse response
            return self._parse_estimation_response(result.text, criteria_count, method_count, issue)

        except Exception as e:
            self._log("complexity_gate_llm_error", {"error": str(e)}, level="warning")
            # Fallback to heuristic (calibrated formula)
            estimated_turns = 5 + criteria_count + int(method_count * 1.5)
            needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
            return ComplexityEstimate(
                estimated_turns=estimated_turns,
                complexity_score=min(estimated_turns / 30, 1.0),
                needs_split=needs_split,
                split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                confidence=0.5,
                reasoning=f"Heuristic fallback after LLM error: {e}",
            )

    def _build_estimation_prompt(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
        spec_content: Optional[str] = None,
    ) -> str:
        """Build prompt for LLM complexity estimation."""
        spec_section = ""
        if spec_content:
            # Truncate large specs
            truncated = spec_content[:3000] if len(spec_content) > 3000 else spec_content
            spec_section = f"\n\n**Spec Context (truncated):**\n{truncated}"

        return f"""Estimate the complexity of implementing this GitHub issue.

**Issue Title:** {issue.get('title', 'Unknown')}

**Issue Body:**
{issue.get('body', 'No body')}

**Metrics Detected:**
- Acceptance Criteria: {criteria_count}
- Methods to Implement: {method_count}
- Estimated Size: {issue.get('estimated_size', 'medium')}
{spec_section}

**Your Task:**
Estimate how many LLM conversation turns a skilled coder would need to implement this issue,
including writing tests and iterating on failures.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "estimated_turns": <number 5-40>,
  "complexity_score": <float 0.0-1.0>,
  "needs_split": <boolean>,
  "reasoning": "<one sentence explanation>"
}}

Guidelines:
- Simple getter/setter: 5-8 turns
- Standard CRUD method: 8-12 turns
- Complex logic with edge cases: 12-18 turns
- Multiple interconnected methods: 18-25 turns
- System with many triggers/handlers: 25-35 turns

If needs_split is true, the issue exceeds reasonable single-issue complexity."""

    def _parse_estimation_response(
        self,
        response: str,
        criteria_count: int,
        method_count: int,
        issue: dict[str, Any],
    ) -> ComplexityEstimate:
        """Parse LLM response into ComplexityEstimate."""
        import json

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                needs_split = data.get("needs_split", False)
                return ComplexityEstimate(
                    estimated_turns=data.get("estimated_turns", 15),
                    complexity_score=data.get("complexity_score", 0.5),
                    needs_split=needs_split,
                    split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                    confidence=0.8,
                    reasoning=data.get("reasoning", "LLM estimate"),
                )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback if parsing fails (calibrated formula)
        estimated_turns = 5 + criteria_count + int(method_count * 1.5)
        needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
        return ComplexityEstimate(
            estimated_turns=estimated_turns,
            complexity_score=min(estimated_turns / 30, 1.0),
            needs_split=needs_split,
            split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
            confidence=0.5,
            reasoning="Heuristic fallback after parse error",
        )

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Run complexity estimation for an issue.

        Args:
            context: Dictionary containing:
                - issue: The issue dict to evaluate
                - spec_content: Optional spec content for context

        Returns:
            AgentResult with complexity estimate in output.
        """
        issue = context.get("issue")
        if not issue:
            return AgentResult.failure_result("Missing required context: issue")

        spec_content = context.get("spec_content")

        estimate = self.estimate_complexity(issue, spec_content)

        self._log("complexity_gate_result", {
            "issue_title": issue.get("title", "Unknown"),
            "estimated_turns": estimate.estimated_turns,
            "needs_split": estimate.needs_split,
            "confidence": estimate.confidence,
        })

        # AC 3.6: Emit ISSUE_COMPLEXITY_PASSED or ISSUE_COMPLEXITY_FAILED
        # Extract feature_id and issue_number from context if available
        feature_id = context.get("feature_id", "")
        issue_number = issue.get("order")

        if estimate.needs_split:
            # Payload schema: {"issue_number", "complexity_score", "split_suggestions"}
            self._emit_event(
                event_type=EventType.ISSUE_COMPLEXITY_FAILED,
                feature_id=feature_id,
                issue_number=issue_number,
                payload={
                    "issue_number": issue_number,
                    "complexity_score": estimate.complexity_score,
                    "split_suggestions": estimate.split_suggestions,
                },
            )
        else:
            # Payload schema: {"issue_number", "complexity_score", "max_turns"}
            self._emit_event(
                event_type=EventType.ISSUE_COMPLEXITY_PASSED,
                feature_id=feature_id,
                issue_number=issue_number,
                payload={
                    "issue_number": issue_number,
                    "complexity_score": estimate.complexity_score,
                    "max_turns": estimate.estimated_turns,
                },
            )

        return AgentResult.success_result(
            output=estimate.to_dict(),
            cost_usd=self._total_cost,
        )
