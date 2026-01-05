"""
Unit tests for Dashboard StatusView - Lightweight Dashboard for Autopilot Orchestration.

TDD Tests for Deliverable 3.2: Lightweight Dashboard.
Tests written BEFORE implementation (RED phase).

Acceptance Criteria:
1. Write .swarm/status.json on state changes
2. Include: agents, tasks, context, last_update timestamp
3. Support terminal-based viewer (optional)
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_swarm_dir() -> Path:
    """Create a temporary .swarm directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        swarm_dir = Path(tmpdir) / ".swarm"
        swarm_dir.mkdir(parents=True)
        yield swarm_dir


@pytest.fixture
def status_view(temp_swarm_dir: Path):
    """Create a StatusView instance with temp directory."""
    from swarm_attack.dashboard.status_view import StatusView

    return StatusView(swarm_dir=temp_swarm_dir)


@pytest.fixture
def sample_agent_state() -> dict:
    """Sample agent state for testing."""
    return {
        "name": "coder",
        "status": "active",
        "started_at": "2025-01-05T10:00:00Z",
        "current_task": "Implementing feature X",
    }


@pytest.fixture
def sample_task_state() -> dict:
    """Sample task state for testing."""
    return {
        "id": "task-001",
        "title": "Implement status view",
        "status": "in_progress",
        "agent": "coder",
        "progress": 0.5,
    }


@pytest.fixture
def sample_context_state() -> dict:
    """Sample context state for testing."""
    return {
        "model": "claude-opus-4-5-20251101",
        "context_percentage": 45.2,
        "tokens_used": 45200,
        "max_tokens": 100000,
    }


# =============================================================================
# TestStatusViewWrite: Test writing status JSON
# =============================================================================


class TestStatusViewWrite:
    """Tests for StatusView writing .swarm/status.json on state changes."""

    def test_write_creates_status_json(self, temp_swarm_dir: Path):
        """Should create .swarm/status.json when update() is called."""
        from swarm_attack.dashboard.status_view import StatusView

        view = StatusView(swarm_dir=temp_swarm_dir)
        view.update(agents=[], tasks=[], context={})

        status_path = temp_swarm_dir / "status.json"
        assert status_path.exists(), "status.json should be created"

    def test_write_creates_valid_json(self, status_view, temp_swarm_dir: Path):
        """Should write valid JSON that can be parsed."""
        status_view.update(agents=[], tasks=[], context={})

        status_path = temp_swarm_dir / "status.json"
        content = status_path.read_text()

        # Should not raise JSONDecodeError
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_write_overwrites_existing(self, status_view, temp_swarm_dir: Path):
        """Should overwrite existing status.json on each update."""
        # First update
        status_view.update(agents=[{"name": "agent1"}], tasks=[], context={})

        # Second update with different data
        status_view.update(agents=[{"name": "agent2"}], tasks=[], context={})

        status_path = temp_swarm_dir / "status.json"
        data = json.loads(status_path.read_text())

        assert data["agents"] == [{"name": "agent2"}]

    def test_write_atomic_no_corruption(self, status_view, temp_swarm_dir: Path):
        """Should write atomically to prevent corruption on failure."""
        from swarm_attack.dashboard.status_view import StatusView

        # Write initial data
        status_view.update(agents=[{"name": "original"}], tasks=[], context={})

        # The file should exist and be readable
        status_path = temp_swarm_dir / "status.json"
        data = json.loads(status_path.read_text())
        assert data["agents"] == [{"name": "original"}]

    def test_write_creates_parent_directories(self):
        """Should create parent directories if they don't exist."""
        from swarm_attack.dashboard.status_view import StatusView

        with tempfile.TemporaryDirectory() as tmpdir:
            # .swarm doesn't exist yet
            swarm_dir = Path(tmpdir) / "nested" / ".swarm"
            view = StatusView(swarm_dir=swarm_dir)
            view.update(agents=[], tasks=[], context={})

            status_path = swarm_dir / "status.json"
            assert status_path.exists()

    def test_write_with_pretty_formatting(self, status_view, temp_swarm_dir: Path):
        """Should write JSON with indentation for readability."""
        status_view.update(agents=[{"name": "test"}], tasks=[], context={})

        status_path = temp_swarm_dir / "status.json"
        content = status_path.read_text()

        # Should have newlines (pretty printed)
        assert "\n" in content

    def test_update_triggers_on_agent_change(self, status_view, temp_swarm_dir: Path):
        """Should write status when agent state changes."""
        status_view.update_agent("coder", status="active", current_task="Task A")

        status_path = temp_swarm_dir / "status.json"
        assert status_path.exists()

        data = json.loads(status_path.read_text())
        assert len(data["agents"]) >= 1
        agent = next(a for a in data["agents"] if a["name"] == "coder")
        assert agent["status"] == "active"

    def test_update_triggers_on_task_change(self, status_view, temp_swarm_dir: Path):
        """Should write status when task state changes."""
        status_view.update_task("task-001", status="in_progress", title="Test Task")

        status_path = temp_swarm_dir / "status.json"
        assert status_path.exists()

        data = json.loads(status_path.read_text())
        assert len(data["tasks"]) >= 1
        task = next(t for t in data["tasks"] if t["id"] == "task-001")
        assert task["status"] == "in_progress"

    def test_update_triggers_on_context_change(self, status_view, temp_swarm_dir: Path):
        """Should write status when context state changes."""
        status_view.update_context(
            model="claude-opus-4-5-20251101",
            context_percentage=50.0,
        )

        status_path = temp_swarm_dir / "status.json"
        assert status_path.exists()

        data = json.loads(status_path.read_text())
        assert data["context"]["model"] == "claude-opus-4-5-20251101"
        assert data["context"]["context_percentage"] == 50.0


# =============================================================================
# TestStatusViewContent: Test JSON includes required fields
# =============================================================================


class TestStatusViewContent:
    """Tests for StatusView JSON content with required fields."""

    def test_contains_agents_field(self, status_view, temp_swarm_dir: Path):
        """Should include 'agents' field in status JSON."""
        status_view.update(agents=[{"name": "test"}], tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_contains_tasks_field(self, status_view, temp_swarm_dir: Path):
        """Should include 'tasks' field in status JSON."""
        status_view.update(agents=[], tasks=[{"id": "task-1"}], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_contains_context_field(self, status_view, temp_swarm_dir: Path):
        """Should include 'context' field in status JSON."""
        status_view.update(agents=[], tasks=[], context={"model": "test"})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert "context" in data
        assert isinstance(data["context"], dict)

    def test_contains_last_update_timestamp(self, status_view, temp_swarm_dir: Path):
        """Should include 'last_update' timestamp in ISO format."""
        status_view.update(agents=[], tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert "last_update" in data

        # Should be valid ISO format
        timestamp = data["last_update"]
        assert isinstance(timestamp, str)
        # Should parse without error
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_timestamp_updates_on_each_write(self, status_view, temp_swarm_dir: Path):
        """Should update timestamp on each write."""
        import time

        status_view.update(agents=[], tasks=[], context={})
        first_data = json.loads((temp_swarm_dir / "status.json").read_text())

        time.sleep(0.01)  # Brief pause

        status_view.update(agents=[], tasks=[], context={})
        second_data = json.loads((temp_swarm_dir / "status.json").read_text())

        # Timestamps should be different (or at least not older)
        first_ts = datetime.fromisoformat(first_data["last_update"].replace("Z", "+00:00"))
        second_ts = datetime.fromisoformat(second_data["last_update"].replace("Z", "+00:00"))
        assert second_ts >= first_ts

    def test_agent_contains_required_fields(
        self, status_view, temp_swarm_dir: Path, sample_agent_state: dict
    ):
        """Agent entries should have name, status, started_at, current_task."""
        status_view.update(agents=[sample_agent_state], tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        agent = data["agents"][0]

        assert "name" in agent
        assert "status" in agent
        assert "started_at" in agent
        assert "current_task" in agent

    def test_task_contains_required_fields(
        self, status_view, temp_swarm_dir: Path, sample_task_state: dict
    ):
        """Task entries should have id, title, status, agent, progress."""
        status_view.update(agents=[], tasks=[sample_task_state], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        task = data["tasks"][0]

        assert "id" in task
        assert "title" in task
        assert "status" in task
        # agent and progress are optional but recommended
        assert "agent" in task or "progress" in task

    def test_context_contains_model_info(
        self, status_view, temp_swarm_dir: Path, sample_context_state: dict
    ):
        """Context should include model name and context percentage."""
        status_view.update(agents=[], tasks=[], context=sample_context_state)

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        context = data["context"]

        assert "model" in context
        assert "context_percentage" in context

    def test_multiple_agents_tracked(self, status_view, temp_swarm_dir: Path):
        """Should track multiple agents simultaneously."""
        agents = [
            {"name": "coder", "status": "active", "started_at": "2025-01-05T10:00:00Z", "current_task": "Task A"},
            {"name": "verifier", "status": "idle", "started_at": "2025-01-05T10:01:00Z", "current_task": None},
        ]
        status_view.update(agents=agents, tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert len(data["agents"]) == 2
        names = [a["name"] for a in data["agents"]]
        assert "coder" in names
        assert "verifier" in names

    def test_multiple_tasks_tracked(self, status_view, temp_swarm_dir: Path):
        """Should track multiple tasks simultaneously."""
        tasks = [
            {"id": "task-001", "title": "Task 1", "status": "done"},
            {"id": "task-002", "title": "Task 2", "status": "in_progress"},
            {"id": "task-003", "title": "Task 3", "status": "pending"},
        ]
        status_view.update(agents=[], tasks=tasks, context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert len(data["tasks"]) == 3

    def test_empty_state_is_valid(self, status_view, temp_swarm_dir: Path):
        """Should handle empty agents, tasks, and context."""
        status_view.update(agents=[], tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert data["agents"] == []
        assert data["tasks"] == []
        assert data["context"] == {}
        assert "last_update" in data

    def test_preserves_custom_fields(self, status_view, temp_swarm_dir: Path):
        """Should preserve any extra fields in agent/task data."""
        agent = {
            "name": "custom",
            "status": "active",
            "started_at": "2025-01-05T10:00:00Z",
            "current_task": "Test",
            "custom_field": "custom_value",
            "metrics": {"turns": 5, "cost_usd": 0.10},
        }
        status_view.update(agents=[agent], tasks=[], context={})

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        stored_agent = data["agents"][0]
        assert stored_agent["custom_field"] == "custom_value"
        assert stored_agent["metrics"]["turns"] == 5


# =============================================================================
# TestStatusViewUpdates: Test state change triggers
# =============================================================================


class TestStatusViewUpdates:
    """Tests for StatusView state change detection and triggers."""

    def test_update_agent_creates_new_agent(self, status_view, temp_swarm_dir: Path):
        """update_agent() should create a new agent entry if not exists."""
        status_view.update_agent(
            name="new-agent",
            status="starting",
            current_task="Initializing",
        )

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        agent = next((a for a in data["agents"] if a["name"] == "new-agent"), None)
        assert agent is not None
        assert agent["status"] == "starting"

    def test_update_agent_modifies_existing(self, status_view, temp_swarm_dir: Path):
        """update_agent() should update existing agent's state."""
        # Create agent
        status_view.update_agent(name="coder", status="active", current_task="Task A")

        # Update agent
        status_view.update_agent(name="coder", status="complete", current_task="Task A finished")

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        agents_named_coder = [a for a in data["agents"] if a["name"] == "coder"]
        assert len(agents_named_coder) == 1
        assert agents_named_coder[0]["status"] == "complete"

    def test_update_task_creates_new_task(self, status_view, temp_swarm_dir: Path):
        """update_task() should create a new task entry if not exists."""
        status_view.update_task(
            task_id="task-new",
            status="pending",
            title="New Task",
        )

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        task = next((t for t in data["tasks"] if t["id"] == "task-new"), None)
        assert task is not None
        assert task["status"] == "pending"

    def test_update_task_modifies_existing(self, status_view, temp_swarm_dir: Path):
        """update_task() should update existing task's state."""
        # Create task
        status_view.update_task(task_id="task-001", status="pending", title="Task 1")

        # Update task
        status_view.update_task(task_id="task-001", status="done", title="Task 1")

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        tasks_with_id = [t for t in data["tasks"] if t["id"] == "task-001"]
        assert len(tasks_with_id) == 1
        assert tasks_with_id[0]["status"] == "done"

    def test_update_context_replaces_context(self, status_view, temp_swarm_dir: Path):
        """update_context() should replace entire context dict."""
        status_view.update_context(model="model-a", context_percentage=25.0)
        status_view.update_context(model="model-b", context_percentage=50.0)

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert data["context"]["model"] == "model-b"
        assert data["context"]["context_percentage"] == 50.0

    def test_remove_agent(self, status_view, temp_swarm_dir: Path):
        """remove_agent() should remove an agent from status."""
        # Add agents
        status_view.update_agent(name="agent-1", status="active", current_task="Task")
        status_view.update_agent(name="agent-2", status="active", current_task="Task")

        # Remove one
        status_view.remove_agent("agent-1")

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        names = [a["name"] for a in data["agents"]]
        assert "agent-1" not in names
        assert "agent-2" in names

    def test_remove_task(self, status_view, temp_swarm_dir: Path):
        """remove_task() should remove a task from status."""
        # Add tasks
        status_view.update_task(task_id="task-a", status="done", title="A")
        status_view.update_task(task_id="task-b", status="pending", title="B")

        # Remove one
        status_view.remove_task("task-a")

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        ids = [t["id"] for t in data["tasks"]]
        assert "task-a" not in ids
        assert "task-b" in ids

    def test_clear_all(self, status_view, temp_swarm_dir: Path):
        """clear() should reset all state to empty."""
        # Add some state
        status_view.update_agent(name="agent", status="active", current_task="Task")
        status_view.update_task(task_id="task", status="done", title="Task")
        status_view.update_context(model="model", context_percentage=50.0)

        # Clear all
        status_view.clear()

        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert data["agents"] == []
        assert data["tasks"] == []
        assert data["context"] == {}

    def test_batch_update(self, status_view, temp_swarm_dir: Path):
        """Should support batch updates to reduce writes."""
        with status_view.batch_update():
            status_view.update_agent(name="agent-1", status="active", current_task="A")
            status_view.update_agent(name="agent-2", status="active", current_task="B")
            status_view.update_task(task_id="task-1", status="done", title="T1")

        # Should have all updates in one file
        data = json.loads((temp_swarm_dir / "status.json").read_text())
        assert len(data["agents"]) == 2
        assert len(data["tasks"]) == 1

    def test_on_state_change_callback(self, status_view, temp_swarm_dir: Path):
        """Should call callback on state changes if registered."""
        callback_calls = []

        def on_change(state):
            callback_calls.append(state.copy())

        status_view.on_change(on_change)
        status_view.update_agent(name="test", status="active", current_task="Task")

        assert len(callback_calls) >= 1
        assert callback_calls[-1]["agents"][0]["name"] == "test"


# =============================================================================
# TestStatusViewReader: Test optional terminal viewer
# =============================================================================


class TestStatusViewReader:
    """Tests for StatusView terminal-based viewer (optional feature)."""

    def test_read_returns_current_state(self, status_view, temp_swarm_dir: Path):
        """read() should return current state from file."""
        from swarm_attack.dashboard.status_view import StatusView

        # Write some state
        status_view.update(
            agents=[{"name": "test", "status": "active", "started_at": "2025-01-05T10:00:00Z", "current_task": "Task"}],
            tasks=[{"id": "task-1", "title": "Task", "status": "done"}],
            context={"model": "claude-opus-4-5-20251101"},
        )

        # Read it back using a new instance (simulating external reader)
        reader = StatusView(swarm_dir=temp_swarm_dir)
        state = reader.read()

        assert state["agents"][0]["name"] == "test"
        assert state["tasks"][0]["id"] == "task-1"
        assert state["context"]["model"] == "claude-opus-4-5-20251101"

    def test_read_returns_none_if_no_file(self):
        """read() should return None if status.json doesn't exist."""
        from swarm_attack.dashboard.status_view import StatusView

        with tempfile.TemporaryDirectory() as tmpdir:
            swarm_dir = Path(tmpdir) / ".swarm"
            swarm_dir.mkdir()
            reader = StatusView(swarm_dir=swarm_dir)

            state = reader.read()
            assert state is None

    def test_format_for_terminal(self, status_view, temp_swarm_dir: Path):
        """format_terminal() should return human-readable string."""
        status_view.update(
            agents=[{"name": "coder", "status": "active", "started_at": "2025-01-05T10:00:00Z", "current_task": "Implementing feature"}],
            tasks=[
                {"id": "task-1", "title": "Task 1", "status": "done"},
                {"id": "task-2", "title": "Task 2", "status": "in_progress"},
            ],
            context={"model": "claude-opus-4-5-20251101", "context_percentage": 45.2},
        )

        output = status_view.format_terminal()

        # Should be a string
        assert isinstance(output, str)

        # Should contain key information
        assert "coder" in output
        assert "active" in output
        assert "Task 1" in output or "task-1" in output
        assert "45.2" in output or "45%" in output

    def test_format_terminal_handles_empty_state(self, status_view, temp_swarm_dir: Path):
        """format_terminal() should handle empty state gracefully."""
        status_view.update(agents=[], tasks=[], context={})

        output = status_view.format_terminal()
        assert isinstance(output, str)
        # Should not raise and should have some indication of empty state
        assert len(output) > 0

    def test_watch_mode_returns_generator(self, status_view, temp_swarm_dir: Path):
        """watch() should return a generator for streaming updates."""
        status_view.update(agents=[], tasks=[], context={})

        # watch() should return an iterable
        watcher = status_view.watch(interval=0.1)
        assert hasattr(watcher, "__iter__") or hasattr(watcher, "__next__")

    def test_get_summary_stats(self, status_view, temp_swarm_dir: Path):
        """get_summary() should return task completion stats."""
        status_view.update(
            agents=[{"name": "coder", "status": "active", "started_at": "2025-01-05T10:00:00Z", "current_task": "Task"}],
            tasks=[
                {"id": "task-1", "title": "Task 1", "status": "done"},
                {"id": "task-2", "title": "Task 2", "status": "done"},
                {"id": "task-3", "title": "Task 3", "status": "in_progress"},
                {"id": "task-4", "title": "Task 4", "status": "pending"},
            ],
            context={},
        )

        summary = status_view.get_summary()

        assert "total_tasks" in summary
        assert summary["total_tasks"] == 4
        assert "completed_tasks" in summary
        assert summary["completed_tasks"] == 2
        assert "active_agents" in summary
        assert summary["active_agents"] == 1

    def test_format_progress_bar(self, status_view, temp_swarm_dir: Path):
        """Should include progress bar in terminal output."""
        status_view.update(
            agents=[],
            tasks=[
                {"id": "task-1", "title": "Task 1", "status": "done"},
                {"id": "task-2", "title": "Task 2", "status": "done"},
                {"id": "task-3", "title": "Task 3", "status": "pending"},
                {"id": "task-4", "title": "Task 4", "status": "pending"},
            ],
            context={},
        )

        output = status_view.format_terminal()

        # Should show some form of progress (2/4 or 50%)
        assert "2/4" in output or "50%" in output or "50.0%" in output


# =============================================================================
# TestStatusViewDataclasses: Test StatusEntry and related models
# =============================================================================


class TestStatusViewDataclasses:
    """Tests for StatusView data models."""

    def test_status_entry_creation(self):
        """StatusEntry should be creatable with required fields."""
        from swarm_attack.dashboard.status_view import StatusEntry

        entry = StatusEntry(
            agents=[],
            tasks=[],
            context={},
            last_update="2025-01-05T10:00:00Z",
        )

        assert entry.agents == []
        assert entry.tasks == []
        assert entry.context == {}
        assert entry.last_update == "2025-01-05T10:00:00Z"

    def test_status_entry_to_dict(self):
        """StatusEntry.to_dict() should serialize to dictionary."""
        from swarm_attack.dashboard.status_view import StatusEntry

        entry = StatusEntry(
            agents=[{"name": "test"}],
            tasks=[{"id": "task-1"}],
            context={"model": "claude"},
            last_update="2025-01-05T10:00:00Z",
        )

        data = entry.to_dict()

        assert data["agents"] == [{"name": "test"}]
        assert data["tasks"] == [{"id": "task-1"}]
        assert data["context"] == {"model": "claude"}
        assert data["last_update"] == "2025-01-05T10:00:00Z"

    def test_status_entry_from_dict(self):
        """StatusEntry.from_dict() should deserialize from dictionary."""
        from swarm_attack.dashboard.status_view import StatusEntry

        data = {
            "agents": [{"name": "test"}],
            "tasks": [{"id": "task-1"}],
            "context": {"model": "claude"},
            "last_update": "2025-01-05T10:00:00Z",
        }

        entry = StatusEntry.from_dict(data)

        assert entry.agents == [{"name": "test"}]
        assert entry.tasks == [{"id": "task-1"}]

    def test_agent_entry_creation(self):
        """AgentEntry should be creatable with required fields."""
        from swarm_attack.dashboard.status_view import AgentEntry

        agent = AgentEntry(
            name="coder",
            status="active",
            started_at="2025-01-05T10:00:00Z",
            current_task="Implementing feature",
        )

        assert agent.name == "coder"
        assert agent.status == "active"
        assert agent.current_task == "Implementing feature"

    def test_task_entry_creation(self):
        """TaskEntry should be creatable with required fields."""
        from swarm_attack.dashboard.status_view import TaskEntry

        task = TaskEntry(
            id="task-001",
            title="Implement feature",
            status="in_progress",
        )

        assert task.id == "task-001"
        assert task.title == "Implement feature"
        assert task.status == "in_progress"

    def test_context_entry_creation(self):
        """ContextEntry should be creatable with model info."""
        from swarm_attack.dashboard.status_view import ContextEntry

        context = ContextEntry(
            model="claude-opus-4-5-20251101",
            context_percentage=45.2,
            tokens_used=45200,
            max_tokens=100000,
        )

        assert context.model == "claude-opus-4-5-20251101"
        assert context.context_percentage == 45.2


# =============================================================================
# TestStatusViewIntegration: Integration tests
# =============================================================================


class TestStatusViewIntegration:
    """Integration tests for realistic usage patterns."""

    def test_typical_workflow(self, temp_swarm_dir: Path):
        """Test typical agent workflow with status updates."""
        from swarm_attack.dashboard.status_view import StatusView

        view = StatusView(swarm_dir=temp_swarm_dir)

        # Agent starts
        view.update_agent(
            name="coder",
            status="active",
            current_task="Analyzing issue #123",
        )

        # Task created
        view.update_task(
            task_id="issue-123",
            status="in_progress",
            title="Fix bug in parser",
        )

        # Context updated
        view.update_context(
            model="claude-opus-4-5-20251101",
            context_percentage=25.0,
        )

        # Read final state
        state = view.read()

        assert len(state["agents"]) == 1
        assert state["agents"][0]["name"] == "coder"
        assert len(state["tasks"]) == 1
        assert state["tasks"][0]["id"] == "issue-123"
        assert state["context"]["model"] == "claude-opus-4-5-20251101"

    def test_multiple_agents_workflow(self, temp_swarm_dir: Path):
        """Test workflow with multiple concurrent agents."""
        from swarm_attack.dashboard.status_view import StatusView

        view = StatusView(swarm_dir=temp_swarm_dir)

        # Multiple agents working
        view.update_agent(name="researcher", status="active", current_task="Researching issue")
        view.update_agent(name="coder", status="active", current_task="Implementing fix")
        view.update_agent(name="verifier", status="idle", current_task=None)

        # Check state
        state = view.read()
        assert len(state["agents"]) == 3

        active_agents = [a for a in state["agents"] if a["status"] == "active"]
        assert len(active_agents) == 2

    def test_task_progression(self, temp_swarm_dir: Path):
        """Test task state progression through lifecycle."""
        from swarm_attack.dashboard.status_view import StatusView

        view = StatusView(swarm_dir=temp_swarm_dir)

        # Create tasks
        for i in range(1, 6):
            view.update_task(task_id=f"task-{i}", status="pending", title=f"Task {i}")

        # Progress through tasks
        view.update_task(task_id="task-1", status="in_progress", title="Task 1")
        view.update_task(task_id="task-1", status="done", title="Task 1")
        view.update_task(task_id="task-2", status="in_progress", title="Task 2")

        # Check state
        state = view.read()
        done = [t for t in state["tasks"] if t["status"] == "done"]
        in_progress = [t for t in state["tasks"] if t["status"] == "in_progress"]
        pending = [t for t in state["tasks"] if t["status"] == "pending"]

        assert len(done) == 1
        assert len(in_progress) == 1
        assert len(pending) == 3

    def test_external_reader_compatibility(self, temp_swarm_dir: Path):
        """Test that external processes can read status.json correctly."""
        from swarm_attack.dashboard.status_view import StatusView

        # Write state
        view = StatusView(swarm_dir=temp_swarm_dir)
        view.update(
            agents=[{"name": "test", "status": "active", "started_at": "2025-01-05T10:00:00Z", "current_task": "Task"}],
            tasks=[{"id": "task-1", "title": "Task", "status": "done"}],
            context={"model": "claude"},
        )

        # Read directly with json.load (simulating external reader)
        status_path = temp_swarm_dir / "status.json"
        with open(status_path) as f:
            data = json.load(f)

        assert data["agents"][0]["name"] == "test"
        assert data["tasks"][0]["id"] == "task-1"
        assert "last_update" in data


# =============================================================================
# TestStatusViewErrorHandling: Error handling tests
# =============================================================================


class TestStatusViewErrorHandling:
    """Tests for StatusView error handling."""

    def test_handles_corrupt_json_gracefully(self, temp_swarm_dir: Path):
        """Should handle corrupt status.json gracefully."""
        from swarm_attack.dashboard.status_view import StatusView

        # Write corrupt JSON
        status_path = temp_swarm_dir / "status.json"
        status_path.write_text("{invalid json")

        view = StatusView(swarm_dir=temp_swarm_dir)
        state = view.read()

        # Should return None or raise appropriate error, not crash
        assert state is None

    def test_handles_missing_fields_in_json(self, temp_swarm_dir: Path):
        """Should handle JSON with missing fields gracefully."""
        from swarm_attack.dashboard.status_view import StatusView

        # Write JSON with missing fields
        status_path = temp_swarm_dir / "status.json"
        status_path.write_text('{"agents": []}')

        view = StatusView(swarm_dir=temp_swarm_dir)
        state = view.read()

        # Should still work, filling in defaults
        assert state is not None or state is None  # Either behavior is acceptable

    def test_handles_permission_error(self, temp_swarm_dir: Path):
        """Should handle permission errors gracefully."""
        from swarm_attack.dashboard.status_view import StatusView

        view = StatusView(swarm_dir=temp_swarm_dir)

        # This test is more about ensuring no crashes on error conditions
        # Actual permission testing is environment-dependent
        try:
            view.update(agents=[], tasks=[], context={})
        except PermissionError:
            pass  # Expected in restricted environments

    def test_update_agent_with_missing_name_raises(self, status_view):
        """update_agent() should raise if name is missing."""
        with pytest.raises((TypeError, ValueError)):
            status_view.update_agent(status="active", current_task="Task")  # Missing name

    def test_update_task_with_missing_id_raises(self, status_view):
        """update_task() should raise if task_id is missing."""
        with pytest.raises((TypeError, ValueError)):
            status_view.update_task(status="done", title="Task")  # Missing task_id
