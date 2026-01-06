"""
Tests for BugFixerAgent memory_store parameter.

TDD - RED phase: These tests verify that BugFixerAgent properly accepts
and stores a memory_store parameter, following the same pattern as
CoderAgent and VerifierAgent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryStore


class TestBugFixerMemoryStore:
    """Tests for BugFixerAgent memory_store parameter."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock SwarmConfig."""
        config = MagicMock()
        config.repo_root = "/tmp/test-repo"
        config.specs_path = "/tmp/test-repo/specs"
        return config

    @pytest.fixture
    def mock_memory_store(self) -> MagicMock:
        """Create a mock MemoryStore."""
        return MagicMock(spec=["query", "add", "save"])

    def test_bug_fixer_accepts_memory_store_parameter(
        self, mock_config: MagicMock, mock_memory_store: MagicMock
    ) -> None:
        """Test that BugFixerAgent.__init__ accepts memory_store parameter."""
        from swarm_attack.agents.bug_fixer import BugFixerAgent

        # Should not raise any errors when memory_store is provided
        agent = BugFixerAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        assert agent is not None

    def test_bug_fixer_stores_memory_store_as_attribute(
        self, mock_config: MagicMock, mock_memory_store: MagicMock
    ) -> None:
        """Test that BugFixerAgent stores memory_store as self._memory_store."""
        from swarm_attack.agents.bug_fixer import BugFixerAgent

        agent = BugFixerAgent(
            config=mock_config,
            memory_store=mock_memory_store,
        )

        # Verify the memory_store is stored as _memory_store attribute
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is mock_memory_store

    def test_bug_fixer_handles_none_memory_store(
        self, mock_config: MagicMock
    ) -> None:
        """Test that BugFixerAgent handles None memory_store without errors."""
        from swarm_attack.agents.bug_fixer import BugFixerAgent

        # Should not raise any errors when memory_store is None (default)
        agent = BugFixerAgent(
            config=mock_config,
            memory_store=None,
        )

        assert agent is not None
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is None

    def test_bug_fixer_memory_store_defaults_to_none(
        self, mock_config: MagicMock
    ) -> None:
        """Test that memory_store defaults to None when not provided."""
        from swarm_attack.agents.bug_fixer import BugFixerAgent

        # Should work without passing memory_store at all
        agent = BugFixerAgent(config=mock_config)

        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is None
