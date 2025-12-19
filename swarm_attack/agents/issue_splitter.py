"""
Issue Splitter Agent for Feature Swarm.

Automatically splits complex issues into smaller, implementable sub-issues
when the ComplexityGateAgent determines an issue needs splitting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


@dataclass
class SplitIssue:
    """A sub-issue created from splitting a complex issue."""

    title: str
    body: str
    estimated_size: str = "small"  # "small" or "medium"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "body": self.body,
            "estimated_size": self.estimated_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SplitIssue:
        """Create from dictionary."""
        return cls(
            title=data.get("title", ""),
            body=data.get("body", ""),
            estimated_size=data.get("estimated_size", "small"),
        )


class IssueSplitterAgent(BaseAgent):
    """
    Splits a complex issue into 2-4 smaller sub-issues.

    Called automatically when ComplexityGateAgent determines an issue
    is too complex (needs_split=True). Uses the split_suggestions from
    the complexity gate as guidance.

    Each sub-issue:
    - Has 3-5 acceptance criteria max
    - Is sized as "small" or "medium"
    - Can be completed in under 20 turns
    """

    name = "issue_splitter"

    # Target constraints for sub-issues
    MAX_CRITERIA_PER_ISSUE = 5
    MAX_SUB_ISSUES = 4
    MIN_SUB_ISSUES = 2

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Issue Splitter agent."""
        super().__init__(config, logger, llm_runner, state_store)

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Split a complex issue into smaller sub-issues.

        Args:
            context:
                - issue_title: str - Original issue title
                - issue_body: str - Original issue body with acceptance criteria
                - split_suggestions: list[str] - Suggestions from complexity gate
                - estimated_turns: int - Original estimated turns
                - feature_id: str - Feature being implemented
                - issue_number: int - Original issue number

        Returns:
            AgentResult with output:
                - sub_issues: list[dict] - Sub-issues with title, body, estimated_size
                - count: int - Number of sub-issues created
                - split_strategy: str - Strategy used for splitting
        """
        issue_title = context.get("issue_title", "")
        issue_body = context.get("issue_body", "")
        split_suggestions = context.get("split_suggestions", [])
        estimated_turns = context.get("estimated_turns", 30)
        feature_id = context.get("feature_id", "")
        issue_number = context.get("issue_number", 0)

        self._log("split_started", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "issue_title": issue_title,
            "estimated_turns": estimated_turns,
            "split_suggestions": split_suggestions,
        })

        # Build prompt for LLM
        prompt = self._build_prompt(
            issue_title=issue_title,
            issue_body=issue_body,
            split_suggestions=split_suggestions,
            estimated_turns=estimated_turns,
        )

        # Call LLM (use sonnet for quality splitting)
        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob"],  # Read-only for context
                max_turns=8,
            )

            if not result.success:
                self._log("split_llm_failed", {"error": result.error})
                return AgentResult.failure_result(
                    agent=self.name,
                    error=f"LLM failed: {result.error}",
                )

            # Parse response
            sub_issues = self._parse_response(result.text)

            if not sub_issues:
                self._log("split_parse_failed", {"response": result.text[:500]})
                return AgentResult.failure_result(
                    agent=self.name,
                    error="Failed to parse sub-issues from LLM response",
                )

            # Validate sub-issues
            if len(sub_issues) < self.MIN_SUB_ISSUES:
                self._log("split_too_few", {"count": len(sub_issues)})
                return AgentResult.failure_result(
                    agent=self.name,
                    error=f"Only {len(sub_issues)} sub-issues created, need at least {self.MIN_SUB_ISSUES}",
                )

            if len(sub_issues) > self.MAX_SUB_ISSUES:
                # Truncate to max
                sub_issues = sub_issues[:self.MAX_SUB_ISSUES]

            self._log("split_success", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "sub_issue_count": len(sub_issues),
                "sub_issue_titles": [s["title"] for s in sub_issues],
                "cost_usd": result.cost_usd,
            })

            return AgentResult.success_result(
                agent=self.name,
                output={
                    "sub_issues": sub_issues,
                    "count": len(sub_issues),
                    "split_strategy": self._detect_strategy(split_suggestions),
                    "cost_usd": result.cost_usd,
                },
                cost_usd=result.cost_usd,
            )

        except Exception as e:
            self._log("split_exception", {"error": str(e)})
            return AgentResult.failure_result(
                agent=self.name,
                error=f"Exception during split: {e}",
            )

    def _build_prompt(
        self,
        issue_title: str,
        issue_body: str,
        split_suggestions: list[str],
        estimated_turns: int,
    ) -> str:
        """Build the LLM prompt for splitting."""
        suggestions_text = "\n".join(f"- {s}" for s in split_suggestions) if split_suggestions else "No specific suggestions"

        return f"""You are an expert at breaking down complex software engineering tasks into smaller, focused issues.

## Original Issue

**Title:** {issue_title}

**Body:**
{issue_body}

## Complexity Analysis

- Estimated turns needed: {estimated_turns} (max allowed: 20)
- Split suggestions from complexity analysis:
{suggestions_text}

## Your Task

Split this issue into 2-4 smaller sub-issues. Each sub-issue should:

1. Have a clear, focused title
2. Have 3-5 acceptance criteria maximum
3. Be completable in under 15 conversation turns
4. Be sized as "small" (1-2 hours) or "medium" (half day)

## Output Format

Output a JSON array of sub-issues. Each sub-issue must have:
- "title": A clear title (prefix with parent context if needed)
- "body": Markdown body with ## Description and ## Acceptance Criteria sections
- "estimated_size": "small" or "medium"

```json
[
  {{
    "title": "Sub-issue 1 title",
    "body": "## Description\\n...\\n\\n## Acceptance Criteria\\n- [ ] Criterion 1\\n- [ ] Criterion 2",
    "estimated_size": "small"
  }},
  {{
    "title": "Sub-issue 2 title",
    "body": "## Description\\n...\\n\\n## Acceptance Criteria\\n- [ ] Criterion 1\\n- [ ] Criterion 2",
    "estimated_size": "small"
  }}
]
```

## Splitting Strategies

Choose the most appropriate strategy:

1. **By Layer**: Separate model/data, service/logic, API/endpoint, UI layers
2. **By Operation**: Separate CRUD operations (Create, Read, Update, Delete)
3. **By Criteria Groups**: Group related acceptance criteria together
4. **By Phase**: Separate setup/config, core implementation, integration/testing

Output ONLY the JSON array, no other text."""

    def _parse_response(self, response: str) -> list[dict[str, Any]]:
        """Parse sub-issues from LLM response."""
        # Try to extract JSON from response

        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(response.strip())
            if isinstance(data, list):
                return self._validate_sub_issues(data)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    return self._validate_sub_issues(data)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find array pattern
        array_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response)
        if array_match:
            try:
                data = json.loads(array_match.group(0))
                if isinstance(data, list):
                    return self._validate_sub_issues(data)
            except json.JSONDecodeError:
                pass

        return []

    def _validate_sub_issues(self, data: list[Any]) -> list[dict[str, Any]]:
        """Validate and normalize sub-issue data."""
        valid_issues = []

        for item in data:
            if not isinstance(item, dict):
                continue

            title = item.get("title", "").strip()
            body = item.get("body", "").strip()
            size = item.get("estimated_size", "small")

            if not title or not body:
                continue

            # Normalize size
            if size not in ("small", "medium"):
                size = "small"

            valid_issues.append({
                "title": title,
                "body": body,
                "estimated_size": size,
            })

        return valid_issues

    def _detect_strategy(self, suggestions: list[str]) -> str:
        """Detect the split strategy from suggestions."""
        suggestions_lower = " ".join(suggestions).lower()

        if "layer" in suggestions_lower:
            return "by_layer"
        elif "operation" in suggestions_lower or "crud" in suggestions_lower:
            return "by_operation"
        elif "trigger" in suggestions_lower:
            return "by_trigger"
        elif "criteria" in suggestions_lower:
            return "by_criteria"
        else:
            return "by_phase"

    def _log(self, event: str, data: dict[str, Any]) -> None:
        """Log an event."""
        if self.logger:
            self.logger.log(event, data)
