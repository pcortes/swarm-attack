"""Unit tests for Orchestrator memory store integration.

TDD RED Phase - Tests for wiring MemoryStore to Orchestrator.
The Orchestrator should:
1. Accept an optional memory_store parameter
2. Create a default MemoryStore if none provided
3. Pass memory_store to CoderAgent and VerifierAgent
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from swarm_attack.config import SwarmConfig
from swarm_attack.orchestrator import Orchestrator
from swarm_attack.memory.store import MemoryStore


@pytest.fixture
def mock_config(tmp_path):
    """Create a minimal SwarmConfig for testing."""
    repo_root = tmp_path / "test-repo"
    repo_root.mkdir()

    # Create required directories
    (repo_root / ".swarm").mkdir()
    (repo_root / ".swarm" / "state").mkdir()
    (repo_root / ".swarm" / "memory").mkdir()
    (repo_root / "specs").mkdir()

    return SwarmConfig(repo_root=str(repo_root))


class TestOrchestratorMemoryStoreCreation:
    """Tests for Orchestrator creating/accepting MemoryStore."""

    def test_orchestrator_accepts_memory_store_parameter(self, mock_config):
        """Orchestrator.__init__ should accept an optional memory_store parameter."""
        memory = MemoryStore()

        # This should not raise - memory_store should be a valid parameter
        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Verify the orchestrator stored the memory
        assert hasattr(orchestrator, '_memory_store')
        assert orchestrator._memory_store is memory

    def test_orchestrator_creates_default_memory_store_if_none_provided(self, mock_config):
        """Orchestrator should create a MemoryStore if none provided."""
        orchestrator = Orchestrator(mock_config)

        # Should have a memory store even if not explicitly provided
        assert hasattr(orchestrator, '_memory_store')
        assert orchestrator._memory_store is not None
        assert isinstance(orchestrator._memory_store, MemoryStore)

    def test_orchestrator_uses_provided_memory_store(self, mock_config):
        """Orchestrator should use the provided MemoryStore, not create a new one."""
        memory = MemoryStore()

        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Should be the exact same instance
        assert orchestrator._memory_store is memory


class TestOrchestratorPassesMemoryToAgents:
    """Tests for Orchestrator passing memory_store to agents."""

    def test_orchestrator_passes_memory_to_coder_agent(self, mock_config):
        """Orchestrator should pass memory_store to CoderAgent."""
        memory = MemoryStore()

        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Access the internal coder agent
        coder = orchestrator._coder

        # CoderAgent should have received the memory store
        assert hasattr(coder, '_memory')
        assert coder._memory is memory

    def test_orchestrator_passes_memory_to_verifier_agent(self, mock_config):
        """Orchestrator should pass memory_store to VerifierAgent."""
        memory = MemoryStore()

        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Access the internal verifier agent
        verifier = orchestrator._verifier

        # VerifierAgent should have received the memory store
        assert hasattr(verifier, '_memory_store')
        assert verifier._memory_store is memory

    def test_both_agents_share_same_memory_instance(self, mock_config):
        """CoderAgent and VerifierAgent should share the same MemoryStore instance."""
        memory = MemoryStore()

        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Both agents should have the same memory instance
        assert orchestrator._coder._memory is orchestrator._verifier._memory_store
        assert orchestrator._coder._memory is memory

    def test_default_memory_is_shared_across_agents(self, mock_config):
        """When no memory_store provided, the default should be shared across agents."""
        orchestrator = Orchestrator(mock_config)

        # Both agents should share the same default memory
        assert orchestrator._coder._memory is orchestrator._verifier._memory_store


class TestOrchestratorMemoryStoreProperty:
    """Tests for accessing memory_store from Orchestrator."""

    def test_orchestrator_has_memory_store_property(self, mock_config):
        """Orchestrator should expose memory_store as a property."""
        memory = MemoryStore()
        orchestrator = Orchestrator(mock_config, memory_store=memory)

        # Should have a property to access memory
        assert hasattr(orchestrator, 'memory_store')
        assert orchestrator.memory_store is memory

    def test_memory_store_property_returns_default_when_created(self, mock_config):
        """When memory_store not provided, property should return the created default."""
        orchestrator = Orchestrator(mock_config)

        # Should return the default memory store that was created
        assert orchestrator.memory_store is not None
        assert isinstance(orchestrator.memory_store, MemoryStore)
        assert orchestrator.memory_store is orchestrator._memory_store
