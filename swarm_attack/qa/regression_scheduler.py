# swarm_attack/qa/regression_scheduler.py
"""RegressionScheduler - Tracks commits/issues and triggers periodic regression testing.

Triggers full regression testing after:
- N issues committed (default: 10)
- N commits (default: 25)
- N hours since last regression (default: 24)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json


@dataclass
class RegressionSchedulerConfig:
    """Configuration for periodic regression testing."""
    issues_between_regressions: int = 10
    commits_between_regressions: int = 25
    time_between_regressions_hours: int = 24
    state_file: str = ".swarm/regression_state.json"


class RegressionScheduler:
    """Tracks commits/issues and triggers regression testing periodically."""

    def __init__(self, config: RegressionSchedulerConfig, project_root: Path):
        self.config = config
        self.project_root = Path(project_root)
        self.state_file = self.project_root / config.state_file
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load state from disk or return fresh state."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "issues_since_last_regression": 0,
            "commits_since_last_regression": 0,
            "last_regression_timestamp": None,
            "last_regression_result": None,
        }

    def _save_state(self) -> None:
        """Persist state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def record_issue_committed(self, issue_id: str) -> bool:
        """Record that an issue was committed. Returns True if regression needed."""
        self.state["issues_since_last_regression"] += 1
        self._save_state()
        return self.should_run_regression()

    def record_commit(self, commit_hash: str) -> bool:
        """Record a commit. Returns True if regression needed."""
        self.state["commits_since_last_regression"] += 1
        self._save_state()
        return self.should_run_regression()

    def should_run_regression(self) -> bool:
        """Check if regression testing should run based on all triggers."""
        # Issue threshold
        if self.state["issues_since_last_regression"] >= self.config.issues_between_regressions:
            return True

        # Commit threshold
        if self.state["commits_since_last_regression"] >= self.config.commits_between_regressions:
            return True

        # Time threshold
        if self.state["last_regression_timestamp"]:
            try:
                last = datetime.fromisoformat(self.state["last_regression_timestamp"])
                if datetime.now() - last > timedelta(hours=self.config.time_between_regressions_hours):
                    return True
            except ValueError:
                pass

        return False

    def record_regression_completed(self, result: dict) -> None:
        """Record that a regression run completed. Resets counters."""
        self.state["issues_since_last_regression"] = 0
        self.state["commits_since_last_regression"] = 0
        self.state["last_regression_timestamp"] = datetime.now().isoformat()
        self.state["last_regression_result"] = result.get("verdict", "UNKNOWN")
        self._save_state()

    def get_status(self) -> dict:
        """Get current regression status."""
        return {
            "issues_until_regression": max(0,
                self.config.issues_between_regressions - self.state["issues_since_last_regression"]),
            "commits_until_regression": max(0,
                self.config.commits_between_regressions - self.state["commits_since_last_regression"]),
            "last_regression": self.state["last_regression_timestamp"],
            "last_result": self.state["last_regression_result"],
        }
