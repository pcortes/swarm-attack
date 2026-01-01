# tests/conftest.py additions

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from swarm_attack.config import SwarmConfig
from swarm_attack.state_store import get_store
from swarm_attack.models import RunState, FeaturePhase


@pytest.fixture
def integration_setup(tmp_path):
    """Complete feature state setup for integration testing."""
    repo_root = tmp_path / "test-repo"
    repo_root.mkdir()

    # Create .swarm directory structure
    swarm_dir = repo_root / ".swarm"
    swarm_dir.mkdir()
    (swarm_dir / "features").mkdir()
    (swarm_dir / "events").mkdir()
    (swarm_dir / "state").mkdir()

    # Create config pointing to test repo
    config = SwarmConfig(repo_root=str(repo_root))

    yield config, repo_root, swarm_dir


@pytest.fixture
def cli_runner():
    """Typer CLI test runner."""
    return CliRunner()


def invoke_approve(runner, feature_id: str, auto: bool = False, manual: bool = False):
    """Helper to invoke approve CLI command."""
    from swarm_attack.cli_legacy import app
    flags = []
    if auto:
        flags.append("--auto")
    if manual:
        flags.append("--manual")
    return runner.invoke(app, ["feature", "approve", feature_id] + flags)


def invoke_greenlight(runner, feature_id: str):
    """Helper to invoke greenlight CLI command."""
    from swarm_attack.cli_legacy import app
    return runner.invoke(app, ["feature", "greenlight", feature_id])


def invoke_bug_approve(runner, bug_id: str, auto: bool = False, manual: bool = False):
    """Helper to invoke bug approve CLI command."""
    from swarm_attack.cli_legacy import app
    flags = []
    if auto:
        flags.append("--auto")
    if manual:
        flags.append("--manual")
    return runner.invoke(app, ["bug", "approve", bug_id] + flags)


def wait_for_event(received_list, timeout_seconds=5.0, expected_count=1):
    """Wait for events with timeout to prevent flaky tests."""
    import time
    start = time.time()
    while time.time() - start < timeout_seconds:
        if len(received_list) >= expected_count:
            return True
        time.sleep(0.1)
    return False
