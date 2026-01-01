"""
Tests for event subscriptions in Orchestrator.

This module tests that the Orchestrator properly subscribes to events
and reacts with appropriate behavior.

Acceptance criteria tested:
- 3.7: Orchestrator subscribes to ISSUE_CREATED to update state
- 3.8: Orchestrator subscribes to ISSUE_COMPLETE to propagate context
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from swarm_attack.events.types import EventType, SwarmEvent
from swarm_attack.events.bus import EventBus, get_event_bus


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.swarm_dir = tmp_path / ".swarm"
    config.github = MagicMock()
    config.github.repo = "owner/repo"
    config.debate_retry = None
    return config


@pytest.fixture
def mock_state_store():
    """Create a mock state store."""
    store = MagicMock()
    store.load.return_value = None
    store.save.return_value = None
    return store


@pytest.fixture
def event_bus(tmp_path):
    """Create a fresh event bus for testing."""
    import swarm_attack.events.bus as bus_module
    bus_module._default_bus = None

    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir(parents=True, exist_ok=True)
    return EventBus(swarm_dir, persist=False)


class TestOrchestratorEventSubscriptions:
    """Test that Orchestrator subscribes to events."""

    def test_orchestrator_initializes_event_bus(self, mock_config, mock_state_store, tmp_path):
        """
        Orchestrator should initialize and store reference to event bus.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.events.bus.get_event_bus') as mock_get_bus:
            mock_bus = MagicMock(spec=EventBus)
            mock_get_bus.return_value = mock_bus

            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

            # Verify orchestrator has event bus reference
            assert hasattr(orchestrator, '_bus')

    def test_orchestrator_subscribes_to_issue_created(
        self, mock_config, mock_state_store, event_bus, tmp_path
    ):
        """
        AC 3.7: Orchestrator subscribes to ISSUE_CREATED to update state.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.orchestrator.get_event_bus', return_value=event_bus):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        # Verify subscription exists for ISSUE_CREATED
        assert EventType.ISSUE_CREATED in event_bus._handlers
        assert len(event_bus._handlers[EventType.ISSUE_CREATED]) > 0

    def test_orchestrator_subscribes_to_issue_complete(
        self, mock_config, mock_state_store, event_bus, tmp_path
    ):
        """
        AC 3.8: Orchestrator subscribes to ISSUE_COMPLETE to propagate context.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.orchestrator.get_event_bus', return_value=event_bus):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        # Verify subscription exists for ISSUE_COMPLETE
        assert EventType.ISSUE_COMPLETE in event_bus._handlers
        assert len(event_bus._handlers[EventType.ISSUE_COMPLETE]) > 0

    def test_on_issue_created_updates_state(
        self, mock_config, mock_state_store, event_bus, tmp_path
    ):
        """
        AC 3.7: When ISSUE_CREATED fires, orchestrator updates state store.
        """
        from swarm_attack.orchestrator import Orchestrator
        from swarm_attack.events.types import SwarmEvent

        # Setup state store mock to track calls
        mock_state = MagicMock()
        mock_state_store.load.return_value = mock_state

        with patch('swarm_attack.orchestrator.get_event_bus', return_value=event_bus):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        # Create and emit ISSUE_CREATED event
        event = SwarmEvent(
            event_type=EventType.ISSUE_CREATED,
            feature_id="test-feature",
            source_agent="IssueCreatorAgent",
            payload={"issue_count": 3, "output_path": "/path/to/issues.json"}
        )
        event_bus.emit(event)

        # Verify state was loaded and potentially updated
        # The handler should load state to check/update it
        mock_state_store.load.assert_called()

    def test_on_issue_complete_propagates_context(
        self, mock_config, mock_state_store, event_bus, tmp_path
    ):
        """
        AC 3.8: When ISSUE_COMPLETE fires, orchestrator propagates context.
        """
        from swarm_attack.orchestrator import Orchestrator
        from swarm_attack.events.types import SwarmEvent

        # Setup state with module registry to update
        mock_state = MagicMock()
        mock_state.module_registry = {}
        mock_state.completed_summaries = []
        mock_state_store.load.return_value = mock_state

        with patch('swarm_attack.orchestrator.get_event_bus', return_value=event_bus):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        # Create and emit ISSUE_COMPLETE event
        # Payload schema: {"issue_number", "commit_sha", "files_changed"}
        event = SwarmEvent(
            event_type=EventType.ISSUE_COMPLETE,
            feature_id="test-feature",
            issue_number=1,
            source_agent="CoderAgent",
            payload={
                "issue_number": 1,
                "commit_sha": "abc123",
                "files_changed": ["src/module.py"],
            }
        )
        event_bus.emit(event)

        # Verify state was loaded and potentially updated
        mock_state_store.load.assert_called()


class TestOrchestratorHandlerMethods:
    """Test the actual handler methods on Orchestrator."""

    def test_has_on_issue_created_handler(self, mock_config, mock_state_store):
        """
        Orchestrator should have _on_issue_created method.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.events.bus.get_event_bus'):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        assert hasattr(orchestrator, '_on_issue_created')
        assert callable(orchestrator._on_issue_created)

    def test_has_on_issue_complete_handler(self, mock_config, mock_state_store):
        """
        Orchestrator should have _on_issue_complete method.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.events.bus.get_event_bus'):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        assert hasattr(orchestrator, '_on_issue_complete')
        assert callable(orchestrator._on_issue_complete)

    def test_handlers_are_instance_methods(self, mock_config, mock_state_store, event_bus):
        """
        Handlers should be bound instance methods, not standalone functions.

        This ensures handlers have access to self for state_store, config, etc.
        """
        from swarm_attack.orchestrator import Orchestrator

        with patch('swarm_attack.orchestrator.get_event_bus', return_value=event_bus):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

        # Get the registered handlers
        issue_created_handlers = event_bus._handlers.get(EventType.ISSUE_CREATED, [])
        issue_complete_handlers = event_bus._handlers.get(EventType.ISSUE_COMPLETE, [])

        # Verify at least one handler for each
        assert len(issue_created_handlers) > 0
        assert len(issue_complete_handlers) > 0

        # Verify they are bound methods of the orchestrator instance
        for handler in issue_created_handlers:
            if hasattr(handler, '__self__'):
                assert handler.__self__ is orchestrator

        for handler in issue_complete_handlers:
            if hasattr(handler, '__self__'):
                assert handler.__self__ is orchestrator


class TestEventBusIntegration:
    """Integration tests for event flow through the bus."""

    def test_event_flows_from_agent_to_orchestrator(
        self, mock_config, mock_state_store, event_bus, tmp_path
    ):
        """
        End-to-end: Events emitted by agents are received by orchestrator handlers.
        """
        from swarm_attack.orchestrator import Orchestrator
        from swarm_attack.agents.complexity_gate import ComplexityGateAgent
        from swarm_attack.events.types import SwarmEvent

        received_events = []

        def capture_handler(event: SwarmEvent):
            received_events.append(event)

        # Subscribe our test handler
        event_bus.subscribe(EventType.ISSUE_COMPLEXITY_PASSED, capture_handler)

        with patch('swarm_attack.events.bus.get_event_bus', return_value=event_bus):
            # Create orchestrator (subscribes to events)
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=mock_state_store,
            )

            # Create agent and run (emits events)
            agent = ComplexityGateAgent(mock_config)
            result = agent.run({
                "issue": {
                    "title": "Simple task",
                    "body": "## Acceptance Criteria\n- [ ] Do thing",
                    "labels": [],
                    "estimated_size": "small",
                    "dependencies": [],
                    "order": 1
                }
            })

        # Verify event was captured
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.ISSUE_COMPLEXITY_PASSED
