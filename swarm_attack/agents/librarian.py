"""
Open Source Librarian Agent.

A specialized research agent for external library documentation
with evidence-backed responses and GitHub permalinks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class RequestType(Enum):
    """Classification of librarian requests."""

    CONCEPTUAL = "conceptual"  # How to, best practices
    IMPLEMENTATION = "implementation"  # Show source, how does X implement
    CONTEXT = "context"  # Why changed, history of
    COMPREHENSIVE = "comprehensive"  # Complex/ambiguous


@dataclass
class Citation:
    """A verified GitHub permalink with context."""

    url: str
    context: str
    lines: Optional[str] = None
    commit_sha: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "context": self.context,
            "lines": self.lines,
            "commit_sha": self.commit_sha,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Citation:
        """Create from dictionary."""
        return cls(
            url=data.get("url", ""),
            context=data.get("context", ""),
            lines=data.get("lines"),
            commit_sha=data.get("commit_sha"),
        )


@dataclass
class LibrarianResult:
    """Result from librarian research."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    request_type: RequestType = RequestType.CONCEPTUAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": self.confidence,
            "tools_used": self.tools_used,
            "request_type": self.request_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LibrarianResult:
        """Create from dictionary."""
        citations = [
            Citation.from_dict(c) for c in data.get("citations", [])
        ]
        request_type_str = data.get("request_type", "conceptual")
        try:
            request_type = RequestType(request_type_str)
        except ValueError:
            request_type = RequestType.CONCEPTUAL

        return cls(
            answer=data.get("answer", ""),
            citations=citations,
            confidence=data.get("confidence", 0.0),
            tools_used=data.get("tools_used", []),
            request_type=request_type,
        )


class LibrarianAgent(BaseAgent):
    """
    Open Source Librarian Agent.

    Researches external libraries with evidence-backed responses.
    Never fabricates - admits uncertainty when evidence insufficient.
    """

    name = "librarian"

    # Classification patterns
    CONCEPTUAL_PATTERNS = [
        r"how do i",
        r"how can i",
        r"best practice",
        r"recommended way",
        r"what is the.*way to",
    ]

    IMPLEMENTATION_PATTERNS = [
        r"show me.*source",
        r"how does.*implement",
        r"where is.*defined",
        r"implementation of",
    ]

    CONTEXT_PATTERNS = [
        r"why was.*changed",
        r"history of",
        r"when was.*added",
        r"who added",
    ]

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Librarian agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def classify_request(self, query: str) -> RequestType:
        """Classify query into request type."""
        query_lower = query.lower()

        for pattern in self.CONCEPTUAL_PATTERNS:
            if re.search(pattern, query_lower):
                return RequestType.CONCEPTUAL

        for pattern in self.IMPLEMENTATION_PATTERNS:
            if re.search(pattern, query_lower):
                return RequestType.IMPLEMENTATION

        for pattern in self.CONTEXT_PATTERNS:
            if re.search(pattern, query_lower):
                return RequestType.CONTEXT

        # Default to comprehensive for ambiguous
        return RequestType.COMPREHENSIVE

    def _load_skill_prompt(self) -> str:
        """Load and cache skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("open-source-librarian")
        return self._skill_prompt

    def _build_prompt(
        self,
        query: str,
        request_type: RequestType,
        libraries: Optional[list[str]] = None,
        depth: str = "medium",
    ) -> str:
        """Build prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        library_focus = ""
        if libraries:
            library_focus = "\n**Focus Libraries:** " + ", ".join(libraries)

        prompt_template = """{skill_prompt}

---

## Research Request

**Query:** {query}
**Request Type:** {request_type}
**Depth:** {depth}{library_focus}

---

## Your Task

Research this query and provide an evidence-backed response with GitHub permalinks.
"""
        return prompt_template.format(
            skill_prompt=skill_prompt,
            query=query,
            request_type=request_type.value,
            depth=depth,
            library_focus=library_focus,
        )

    def _extract_result(self, response_text: str) -> Optional[LibrarianResult]:
        """Extract LibrarianResult from response."""
        # Find JSON in response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
            return LibrarianResult.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute librarian research.

        Args:
            context: Dictionary containing:
                - query: str (required) - The research question
                - libraries: Optional[list[str]] - Focus libraries
                - depth: str - "quick", "medium", "thorough"
                - request_type: Optional[str] - Override classification

        Returns:
            AgentResult with LibrarianResult output.
        """
        # Extract context
        query = context.get("query")
        if not query:
            return AgentResult.failure_result("Missing required 'query' in context")

        libraries = context.get("libraries")
        depth = context.get("depth", "medium")

        # Classify or use override
        request_type_str = context.get("request_type")
        if request_type_str:
            try:
                request_type = RequestType(request_type_str)
            except ValueError:
                return AgentResult.failure_result(
                    f"Invalid request_type: {request_type_str}"
                )
        else:
            request_type = self.classify_request(query)

        self._log("librarian_start", {"query": query, "request_type": request_type.value})
        self.checkpoint("started")

        # Load skill
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("librarian_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("skill_loaded")

        # Build prompt
        prompt = self._build_prompt(query, request_type, libraries, depth)

        # Invoke Claude
        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"],
                max_turns=50,
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("librarian_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("librarian_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse result
        librarian_result = self._extract_result(result.text)
        if librarian_result is None:
            # Return raw text if parsing fails
            librarian_result = LibrarianResult(
                answer=result.text,
                confidence=0.5,
                request_type=request_type,
            )

        self._log(
            "librarian_complete",
            {
                "citations_count": len(librarian_result.citations),
                "confidence": librarian_result.confidence,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output=librarian_result.to_dict(),
            cost_usd=cost,
        )
