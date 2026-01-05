"""
Dashboard StatusView - Lightweight Dashboard for Autopilot Orchestration.

Deliverable 3.2: Lightweight Dashboard
- Write .swarm/status.json on state changes
- Include: agents, tasks, context, last_update timestamp
- Support terminal-based viewer (optional)
"""

import json
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Union


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class AgentEntry:
    """Agent entry for status tracking."""

    name: str
    status: str
    started_at: str
    current_task: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "current_task": self.current_task,
        }


@dataclass
class TaskEntry:
    """Task entry for status tracking."""

    id: str
    title: str
    status: str
    agent: Optional[str] = None
    progress: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
        }
        if self.agent is not None:
            result["agent"] = self.agent
        if self.progress is not None:
            result["progress"] = self.progress
        return result


@dataclass
class ContextEntry:
    """Context entry for status tracking."""

    model: Optional[str] = None
    context_percentage: Optional[float] = None
    tokens_used: Optional[int] = None
    max_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {}
        if self.model is not None:
            result["model"] = self.model
        if self.context_percentage is not None:
            result["context_percentage"] = self.context_percentage
        if self.tokens_used is not None:
            result["tokens_used"] = self.tokens_used
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens
        return result


@dataclass
class StatusEntry:
    """Status entry containing all state."""

    agents: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    context: Dict[str, Any]
    last_update: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agents": self.agents,
            "tasks": self.tasks,
            "context": self.context,
            "last_update": self.last_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusEntry":
        """Deserialize from dictionary."""
        return cls(
            agents=data.get("agents", []),
            tasks=data.get("tasks", []),
            context=data.get("context", {}),
            last_update=data.get("last_update", ""),
        )


# =============================================================================
# StatusView Class
# =============================================================================


class StatusView:
    """
    Lightweight dashboard for autopilot orchestration status.

    Writes .swarm/status.json on state changes with:
    - agents: List of agent states
    - tasks: List of task states
    - context: Model/context information
    - last_update: ISO timestamp
    """

    def __init__(self, swarm_dir: Optional[Path] = None):
        """
        Initialize StatusView.

        Args:
            swarm_dir: Path to .swarm directory. Defaults to .swarm in CWD.
        """
        self._swarm_dir = swarm_dir or Path.cwd() / ".swarm"
        self._agents: List[Dict[str, Any]] = []
        self._tasks: List[Dict[str, Any]] = []
        self._context: Dict[str, Any] = {}
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._batch_mode = False

    @property
    def status_path(self) -> Path:
        """Path to status.json file."""
        return self._swarm_dir / "status.json"

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _write_status(self) -> None:
        """Write current state to status.json."""
        if self._batch_mode:
            return

        # Ensure parent directories exist
        self._swarm_dir.mkdir(parents=True, exist_ok=True)

        state = {
            "agents": self._agents,
            "tasks": self._tasks,
            "context": self._context,
            "last_update": self._get_timestamp(),
        }

        # Write atomically using temp file
        temp_fd = None
        temp_path = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self._swarm_dir,
                suffix=".tmp",
            )
            with open(temp_fd, "w") as f:
                json.dump(state, f, indent=2)
            temp_fd = None  # Close handled by context manager
            Path(temp_path).replace(self.status_path)
        except Exception:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

        # Notify callbacks
        for callback in self._callbacks:
            callback(state)

    def update(
        self,
        agents: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> None:
        """
        Update entire state and write to file.

        Args:
            agents: List of agent state dictionaries
            tasks: List of task state dictionaries
            context: Context dictionary with model info
        """
        self._agents = list(agents)
        self._tasks = list(tasks)
        self._context = dict(context)
        self._write_status()

    def update_agent(
        self,
        name: str,
        status: str,
        current_task: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Update or create an agent entry.

        Args:
            name: Agent name (required)
            status: Agent status (required)
            current_task: Current task description
            **kwargs: Additional agent fields
        """
        if not name:
            raise ValueError("Agent name is required")

        # Find existing agent or create new
        existing = next((a for a in self._agents if a["name"] == name), None)

        if existing:
            existing["status"] = status
            existing["current_task"] = current_task
            existing.update(kwargs)
        else:
            agent = {
                "name": name,
                "status": status,
                "started_at": self._get_timestamp(),
                "current_task": current_task,
                **kwargs,
            }
            self._agents.append(agent)

        self._write_status()

    def update_task(
        self,
        task_id: str,
        status: str,
        title: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Update or create a task entry.

        Args:
            task_id: Task ID (required)
            status: Task status (required)
            title: Task title
            **kwargs: Additional task fields
        """
        if not task_id:
            raise ValueError("Task ID is required")

        # Find existing task or create new
        existing = next((t for t in self._tasks if t["id"] == task_id), None)

        if existing:
            existing["status"] = status
            if title is not None:
                existing["title"] = title
            existing.update(kwargs)
        else:
            task = {
                "id": task_id,
                "status": status,
                "title": title or "",
                **kwargs,
            }
            self._tasks.append(task)

        self._write_status()

    def update_context(self, **kwargs: Any) -> None:
        """
        Update context information.

        Args:
            **kwargs: Context fields (model, context_percentage, etc.)
        """
        self._context = dict(kwargs)
        self._write_status()

    def remove_agent(self, name: str) -> None:
        """
        Remove an agent from status.

        Args:
            name: Agent name to remove
        """
        self._agents = [a for a in self._agents if a["name"] != name]
        self._write_status()

    def remove_task(self, task_id: str) -> None:
        """
        Remove a task from status.

        Args:
            task_id: Task ID to remove
        """
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        self._write_status()

    def clear(self) -> None:
        """Clear all state (agents, tasks, context)."""
        self._agents = []
        self._tasks = []
        self._context = {}
        self._write_status()

    @contextmanager
    def batch_update(self) -> Generator[None, None, None]:
        """
        Context manager for batch updates.

        Defers writing to file until all updates are complete.
        """
        self._batch_mode = True
        try:
            yield
        finally:
            self._batch_mode = False
            self._write_status()

    def on_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback for state changes.

        Args:
            callback: Function to call with new state on each change
        """
        self._callbacks.append(callback)

    def read(self) -> Optional[Dict[str, Any]]:
        """
        Read current state from file.

        Returns:
            State dictionary or None if file doesn't exist or is invalid
        """
        if not self.status_path.exists():
            return None

        try:
            with open(self.status_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def format_terminal(self) -> str:
        """
        Format status for terminal display.

        Returns:
            Human-readable string representation of current status
        """
        state = self.read()
        if state is None:
            return "No status available"

        lines = []
        lines.append("=" * 60)
        lines.append("SWARM STATUS")
        lines.append("=" * 60)

        # Agents section
        lines.append("\nAGENTS:")
        if state.get("agents"):
            for agent in state["agents"]:
                status = agent.get("status", "unknown")
                name = agent.get("name", "unknown")
                task = agent.get("current_task", "N/A")
                lines.append(f"  [{status}] {name}: {task}")
        else:
            lines.append("  No agents")

        # Tasks section
        lines.append("\nTASKS:")
        tasks = state.get("tasks", [])
        if tasks:
            done_count = sum(1 for t in tasks if t.get("status") == "done")
            total_count = len(tasks)

            # Progress bar
            if total_count > 0:
                progress_pct = (done_count / total_count) * 100
                bar_width = 20
                filled = int(bar_width * done_count / total_count)
                bar = "#" * filled + "-" * (bar_width - filled)
                lines.append(f"  Progress: [{bar}] {done_count}/{total_count} ({progress_pct:.1f}%)")

            # Individual tasks
            for task in tasks:
                status = task.get("status", "unknown")
                task_id = task.get("id", "?")
                title = task.get("title", task_id)
                marker = "[x]" if status == "done" else "[ ]" if status == "pending" else "[>]"
                lines.append(f"  {marker} {title}")
        else:
            lines.append("  No tasks")

        # Context section
        lines.append("\nCONTEXT:")
        context = state.get("context", {})
        if context:
            model = context.get("model", "N/A")
            pct = context.get("context_percentage")
            lines.append(f"  Model: {model}")
            if pct is not None:
                lines.append(f"  Context: {pct}%")
        else:
            lines.append("  No context info")

        # Last update
        last_update = state.get("last_update", "unknown")
        lines.append(f"\nLast updated: {last_update}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def watch(self, interval: float = 1.0) -> Generator[Dict[str, Any], None, None]:
        """
        Generator that yields status updates at given interval.

        Args:
            interval: Seconds between checks

        Yields:
            State dictionary on each check
        """
        last_state = None
        while True:
            state = self.read()
            if state != last_state:
                last_state = state
                if state is not None:
                    yield state
            time.sleep(interval)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with total_tasks, completed_tasks, active_agents
        """
        state = self.read()
        if state is None:
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "active_agents": 0,
            }

        tasks = state.get("tasks", [])
        agents = state.get("agents", [])

        return {
            "total_tasks": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.get("status") == "done"),
            "active_agents": sum(1 for a in agents if a.get("status") == "active"),
        }
