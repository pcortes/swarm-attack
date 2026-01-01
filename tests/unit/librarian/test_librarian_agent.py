"""Tests for LibrarianAgent."""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.agents.librarian import (
    LibrarianAgent,
    RequestType,
    Citation,
    LibrarianResult,
)


class TestRequestType:
    """Test RequestType enum."""

    def test_request_type_values(self):
        """Verify all request types have expected values."""
        assert RequestType.CONCEPTUAL.value == "conceptual"
        assert RequestType.IMPLEMENTATION.value == "implementation"
        assert RequestType.CONTEXT.value == "context"
        assert RequestType.COMPREHENSIVE.value == "comprehensive"


class TestCitation:
    """Test Citation dataclass."""

    def test_citation_to_dict(self):
        """Citation.to_dict() returns all fields."""
        citation = Citation(
            url="https://github.com/owner/repo/blob/abc123/file.py#L10-L20",
            context="This shows the implementation",
            lines="L10-L20",
            commit_sha="abc123",
        )
        result = citation.to_dict()
        assert result["url"] == citation.url
        assert result["context"] == citation.context
        assert result["lines"] == "L10-L20"
        assert result["commit_sha"] == "abc123"

    def test_citation_from_dict(self):
        """Citation.from_dict() creates instance from dict."""
        data = {
            "url": "https://github.com/owner/repo/blob/sha/file.py",
            "context": "Some context",
            "lines": "L5-L10",
            "commit_sha": "sha123",
        }
        citation = Citation.from_dict(data)
        assert citation.url == data["url"]
        assert citation.context == data["context"]


class TestLibrarianResult:
    """Test LibrarianResult dataclass."""

    def test_result_to_dict(self):
        """LibrarianResult.to_dict() returns all fields."""
        result = LibrarianResult(
            answer="Test answer",
            citations=[Citation(url="http://test", context="test")],
            confidence=0.8,
            tools_used=["WebSearch"],
            request_type=RequestType.CONCEPTUAL,
        )
        data = result.to_dict()
        assert data["answer"] == "Test answer"
        assert len(data["citations"]) == 1
        assert data["confidence"] == 0.8
        assert data["request_type"] == "conceptual"

    def test_result_from_dict(self):
        """LibrarianResult.from_dict() creates instance."""
        data = {
            "answer": "Answer",
            "citations": [{"url": "http://x", "context": "y"}],
            "confidence": 0.5,
            "tools_used": ["Read"],
            "request_type": "implementation",
        }
        result = LibrarianResult.from_dict(data)
        assert result.answer == "Answer"
        assert result.request_type == RequestType.IMPLEMENTATION


class TestClassifyRequest:
    """Test request classification."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked dependencies."""
        with patch("swarm_attack.agents.librarian.BaseAgent.__init__", return_value=None):
            agent = LibrarianAgent.__new__(LibrarianAgent)
            agent.name = "librarian"
            agent.CONCEPTUAL_PATTERNS = LibrarianAgent.CONCEPTUAL_PATTERNS
            agent.IMPLEMENTATION_PATTERNS = LibrarianAgent.IMPLEMENTATION_PATTERNS
            agent.CONTEXT_PATTERNS = LibrarianAgent.CONTEXT_PATTERNS
            return agent

    def test_classify_conceptual_how_do_i(self, agent):
        """'How do I...' queries classify as CONCEPTUAL."""
        result = agent.classify_request("How do I use React Query?")
        assert result == RequestType.CONCEPTUAL

    def test_classify_conceptual_best_practice(self, agent):
        """'Best practice' queries classify as CONCEPTUAL."""
        result = agent.classify_request("What's the best practice for caching?")
        assert result == RequestType.CONCEPTUAL

    def test_classify_implementation_show_source(self, agent):
        """'Show me source' queries classify as IMPLEMENTATION."""
        result = agent.classify_request("Show me the source code for useQuery")
        assert result == RequestType.IMPLEMENTATION

    def test_classify_implementation_how_does_implement(self, agent):
        """'How does X implement' queries classify as IMPLEMENTATION."""
        result = agent.classify_request("How does React Query implement caching?")
        assert result == RequestType.IMPLEMENTATION

    def test_classify_context_why_changed(self, agent):
        """'Why was X changed' queries classify as CONTEXT."""
        result = agent.classify_request("Why was the API changed in v5?")
        assert result == RequestType.CONTEXT

    def test_classify_context_history(self, agent):
        """'History of' queries classify as CONTEXT."""
        result = agent.classify_request("What's the history of this feature?")
        assert result == RequestType.CONTEXT

    def test_classify_comprehensive_ambiguous(self, agent):
        """Ambiguous queries classify as COMPREHENSIVE."""
        result = agent.classify_request("Tell me about React Query")
        assert result == RequestType.COMPREHENSIVE


class TestLibrarianRun:
    """Test agent run() method."""

    @pytest.fixture
    def mock_agent(self):
        """Create agent with all dependencies mocked."""
        with patch("swarm_attack.agents.librarian.BaseAgent.__init__", return_value=None):
            agent = LibrarianAgent.__new__(LibrarianAgent)
            agent.name = "librarian"
            agent._skill_prompt = None
            agent._llm = MagicMock()  # Use private attribute for property
            agent._logger = MagicMock()  # Use private attribute for property
            agent.config = MagicMock()
            agent.CONCEPTUAL_PATTERNS = LibrarianAgent.CONCEPTUAL_PATTERNS
            agent.IMPLEMENTATION_PATTERNS = LibrarianAgent.IMPLEMENTATION_PATTERNS
            agent.CONTEXT_PATTERNS = LibrarianAgent.CONTEXT_PATTERNS

            # Mock methods
            agent._log = MagicMock()
            agent.checkpoint = MagicMock()
            agent.load_skill = MagicMock(return_value="# Test Skill Prompt")
            return agent

    def test_run_requires_query(self, mock_agent):
        """run() fails without query in context."""
        result = mock_agent.run({})
        assert result.success is False
        assert "query" in result.error.lower()

    def test_run_invalid_request_type(self, mock_agent):
        """run() fails with invalid request_type."""
        result = mock_agent.run({"query": "test", "request_type": "invalid"})
        assert result.success is False
        assert "invalid" in result.error.lower()
