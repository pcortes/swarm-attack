"""
Tests for RecoveryAgent memory_store parameter support.

TDD tests for adding memory_store parameter to RecoveryAgent.__init__,
following the same pattern as CoderAgent.
"""

from unittest.mock import MagicMock

import pytest


def _create_config_mock() -> MagicMock:
    """Create a properly configured SwarmConfig mock for RecoveryAgent."""
    config = MagicMock()
    config.retry = MagicMock()
    config.retry.max_retries = 3
    return config


class TestRecoveryAgentMemoryStore:
    """Tests for RecoveryAgent memory_store parameter."""

    def test_recovery_agent_accepts_memory_store_parameter(self) -> None:
        """Test that RecoveryAgent.__init__ accepts memory_store parameter."""
        from swarm_attack.agents.recovery import RecoveryAgent

        # Create minimal config mock
        config = _create_config_mock()

        # Create a mock memory store
        memory_store = MagicMock()

        # Should not raise - agent accepts memory_store parameter
        agent = RecoveryAgent(
            config=config,
            memory_store=memory_store,
        )

        assert agent is not None

    def test_recovery_agent_stores_memory_store_as_attribute(self) -> None:
        """Test that RecoveryAgent stores memory_store as self._memory_store."""
        from swarm_attack.agents.recovery import RecoveryAgent

        # Create minimal config mock
        config = _create_config_mock()

        # Create a mock memory store
        memory_store = MagicMock()
        memory_store.query = MagicMock(return_value=[])

        # Create agent with memory_store
        agent = RecoveryAgent(
            config=config,
            memory_store=memory_store,
        )

        # Verify memory_store is stored as _memory_store attribute
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is memory_store

    def test_recovery_agent_handles_none_memory_store(self) -> None:
        """Test that RecoveryAgent handles None memory_store without errors."""
        from swarm_attack.agents.recovery import RecoveryAgent

        # Create minimal config mock
        config = _create_config_mock()

        # Create agent with None memory_store (default)
        agent = RecoveryAgent(
            config=config,
            memory_store=None,
        )

        # Should not raise and should have _memory_store set to None
        assert hasattr(agent, "_memory_store")
        assert agent._memory_store is None

        # Also test without passing memory_store at all (uses default)
        agent_default = RecoveryAgent(config=config)
        assert hasattr(agent_default, "_memory_store")
        assert agent_default._memory_store is None
