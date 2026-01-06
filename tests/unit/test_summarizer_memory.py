"""
Tests for SummarizerAgent memory_store parameter.

These tests verify that SummarizerAgent:
1. Accepts an optional memory_store parameter in __init__
2. Stores the memory_store as a _memory_store attribute
3. Handles None gracefully without errors

Following the pattern established by CoderAgent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from swarm_attack.agents.summarizer import SummarizerAgent
from swarm_attack.config import SwarmConfig
from swarm_attack.memory.store import MemoryStore


@pytest.fixture
def mock_config() -> SwarmConfig:
    """Create a mock SwarmConfig for testing."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = "/tmp/test-repo"
    config.specs_path = "/tmp/test-repo/specs"
    return config


@pytest.fixture
def mock_memory_store() -> MemoryStore:
    """Create a mock MemoryStore for testing."""
    return MagicMock(spec=MemoryStore)


class TestSummarizerAgentAcceptsMemoryStoreParameter:
    """Test that SummarizerAgent.__init__ accepts memory_store parameter."""

    def test_summarizer_agent_accepts_memory_store_parameter(
        self,
        mock_config: SwarmConfig,
        mock_memory_store: MemoryStore,
    ) -> None:
        """Test __init__ accepts memory_store as a keyword argument."""
        # This should not raise TypeError
        agent = SummarizerAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )
        assert agent is not None

    def test_summarizer_agent_accepts_memory_store_with_all_params(
        self,
        mock_config: SwarmConfig,
        mock_memory_store: MemoryStore,
    ) -> None:
        """Test __init__ accepts memory_store alongside other optional params."""
        mock_logger = MagicMock()
        mock_llm_runner = MagicMock()

        agent = SummarizerAgent(
            config=mock_config,
            logger=mock_logger,
            llm_runner=mock_llm_runner,
            memory_store=mock_memory_store,
        )
        assert agent is not None


class TestSummarizerAgentStoresMemoryStoreAsAttribute:
    """Test that SummarizerAgent stores memory_store as _memory_store attribute."""

    def test_summarizer_agent_stores_memory_store_as_attribute(
        self,
        mock_config: SwarmConfig,
        mock_memory_store: MemoryStore,
    ) -> None:
        """Test self._memory_store is set to the provided memory_store."""
        agent = SummarizerAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is mock_memory_store

    def test_summarizer_agent_memory_store_is_exact_reference(
        self,
        mock_config: SwarmConfig,
        mock_memory_store: MemoryStore,
    ) -> None:
        """Test that _memory_store is the exact same object (not a copy)."""
        agent = SummarizerAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )
        # Use 'is' to verify it's the same object reference
        assert agent._memory_store is mock_memory_store


class TestSummarizerAgentHandlesNoneMemoryStore:
    """Test that SummarizerAgent handles None memory_store gracefully."""

    def test_summarizer_agent_handles_none_memory_store(
        self,
        mock_config: SwarmConfig,
    ) -> None:
        """Test None doesn't cause errors during initialization."""
        # This should not raise any exception
        agent = SummarizerAgent(
            config=mock_config,
            memory_store=None,
        )
        assert agent is not None
        assert agent._memory_store is None

    def test_summarizer_agent_default_memory_store_is_none(
        self,
        mock_config: SwarmConfig,
    ) -> None:
        """Test that memory_store defaults to None when not provided."""
        agent = SummarizerAgent(config=mock_config)
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is None

    def test_summarizer_agent_explicit_none_vs_default(
        self,
        mock_config: SwarmConfig,
    ) -> None:
        """Test explicit None behaves the same as default."""
        agent_default = SummarizerAgent(config=mock_config)
        agent_explicit = SummarizerAgent(config=mock_config, memory_store=None)

        assert agent_default._memory_store is None
        assert agent_explicit._memory_store is None
