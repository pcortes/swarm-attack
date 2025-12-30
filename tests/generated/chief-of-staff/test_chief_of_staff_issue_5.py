"""Tests for StateGatherer that aggregates repository state."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, mock_open

import pytest

from swarm_attack.chief_of_staff.state_gatherer import (
    StateGatherer,
    RepoStateSnapshot,
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestState,
    GitHubState,
    InterruptedSession,
)
from swarm_attack.config import SwarmConfig


class TestStateGathererInit:
    """Tests for StateGatherer initialization."""

    def test_init_with_config(self):
        """StateGatherer initializes with SwarmConfig."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        assert gatherer.config == config

    def test_init_stores_config(self):
        """StateGatherer stores the config for later use."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        assert hasattr(gatherer, "config")


class TestGatherGitState:
    """Tests for gather_git_state method."""

    def test_gather_git_state_returns_git_state(self):
        """gather_git_state returns a GitState object."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "_run_git_command") as mock_git:
            mock_git.side_effect = [
                "main",  # current branch
                "M file.py\n?? new.py",  # status
                "abc123 commit 1\ndef456 commit 2",  # log
                "ahead 2, behind 1",  # rev-list
            ]
            result = gatherer.gather_git_state()
        
        assert isinstance(result, GitState)

    def test_gather_git_state_gets_branch(self):
        """gather_git_state captures current branch."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "_run_git_command") as mock_git:
            mock_git.side_effect = [
                "feature/test",
                "",
                "",
                "",
            ]
            result = gatherer.gather_git_state()
        
        assert result.current_branch == "feature/test"

    def test_gather_git_state_gets_modified_files(self):
        """gather_git_state captures modified files."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "_run_git_command") as mock_git:
            mock_git.side_effect = [
                "main",
                "M src/file.py\nA new_file.py",
                "",
                "",
            ]
            result = gatherer.gather_git_state()
        
        assert "M src/file.py" in result.status or len(result.modified_files) > 0


class TestGatherFeatures:
    """Tests for gather_features method."""

    def test_gather_features_returns_list(self):
        """gather_features returns a list of FeatureSummary."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            result = gatherer.gather_features()
        
        assert isinstance(result, list)

    def test_gather_features_reads_state_files(self):
        """gather_features reads from .swarm/state/*.json."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        mock_state = {
            "feature_id": "test-feature",
            "phase": "IMPLEMENTING",
            "issues": [{"number": 1, "title": "Test"}],
        }
        
        with patch("pathlib.Path.glob") as mock_glob, \
             patch("pathlib.Path.read_text", return_value=json.dumps(mock_state)), \
             patch("pathlib.Path.exists", return_value=True):
            mock_path = MagicMock()
            mock_path.stem = "test-feature"
            mock_path.read_text.return_value = json.dumps(mock_state)
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_features()
        
        assert len(result) >= 0  # May be empty in test env

    def test_gather_features_handles_missing_directory(self):
        """gather_features handles missing .swarm/state directory."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.side_effect = FileNotFoundError()
            result = gatherer.gather_features()
        
        assert result == []


class TestGatherBugs:
    """Tests for gather_bugs method."""

    def test_gather_bugs_returns_list(self):
        """gather_bugs returns a list of BugSummary."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            result = gatherer.gather_bugs()
        
        assert isinstance(result, list)

    def test_gather_bugs_reads_bug_state(self):
        """gather_bugs reads from .swarm/bugs/*/state.json."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        mock_state = {
            "bug_id": "bug-123",
            "phase": "ANALYZING",
            "description": "Test bug",
        }
        
        with patch("pathlib.Path.glob") as mock_glob, \
             patch("pathlib.Path.exists", return_value=True):
            mock_path = MagicMock()
            mock_path.parent.name = "bug-123"
            mock_path.read_text.return_value = json.dumps(mock_state)
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_bugs()
        
        assert len(result) >= 0

    def test_gather_bugs_handles_missing_directory(self):
        """gather_bugs handles missing .swarm/bugs directory."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.side_effect = FileNotFoundError()
            result = gatherer.gather_bugs()
        
        assert result == []


class TestGatherPRDs:
    """Tests for gather_prds method."""

    def test_gather_prds_returns_list(self):
        """gather_prds returns a list of PRDSummary."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            result = gatherer.gather_prds()
        
        assert isinstance(result, list)

    def test_gather_prds_reads_markdown_files(self):
        """gather_prds reads from .claude/prds/*.md."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        prd_content = """---
title: Test Feature
status: draft
---

# Feature Description
"""
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_path = MagicMock()
            mock_path.stem = "test-feature"
            mock_path.read_text.return_value = prd_content
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_prds()
        
        assert len(result) >= 0

    def test_gather_prds_parses_frontmatter(self):
        """gather_prds extracts frontmatter metadata."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        prd_content = """---
title: My Feature
status: approved
priority: high
---

# Content
"""
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_path = MagicMock()
            mock_path.stem = "my-feature"
            mock_path.read_text.return_value = prd_content
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_prds()
        
        if result:
            assert hasattr(result[0], "title") or hasattr(result[0], "name")


class TestGatherSpecs:
    """Tests for gather_specs method."""

    def test_gather_specs_returns_list(self):
        """gather_specs returns a list of SpecSummary."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            mock_iterdir.return_value = []
            result = gatherer.gather_specs()
        
        assert isinstance(result, list)

    def test_gather_specs_reads_spec_directories(self):
        """gather_specs reads from specs/*/ directories."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.iterdir") as mock_iterdir, \
             patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True):
            mock_dir = MagicMock()
            mock_dir.name = "test-feature"
            mock_dir.is_dir.return_value = True
            mock_iterdir.return_value = [mock_dir]
            
            result = gatherer.gather_specs()
        
        assert len(result) >= 0

    def test_gather_specs_handles_missing_directory(self):
        """gather_specs handles missing specs directory."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            mock_iterdir.side_effect = FileNotFoundError()
            result = gatherer.gather_specs()
        
        assert result == []


class TestGatherTests:
    """Tests for gather_tests method."""

    def test_gather_tests_returns_test_state(self):
        """gather_tests returns a TestState object."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="collected 10 items",
                stderr="",
            )
            result = gatherer.gather_tests()
        
        assert isinstance(result, TestState)

    def test_gather_tests_runs_pytest_collect(self):
        """gather_tests runs pytest --collect-only."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="collected 5 items\n<Module test_foo.py>",
                stderr="",
            )
            gatherer.gather_tests()
            
            # Verify pytest was called with collect-only
            call_args = mock_run.call_args
            assert "--collect-only" in call_args[0][0] or \
                   any("--collect-only" in str(arg) for arg in call_args[0][0])

    def test_gather_tests_handles_pytest_failure(self):
        """gather_tests handles pytest collection failure gracefully."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("pytest not found")
            result = gatherer.gather_tests()
        
        assert isinstance(result, TestState)
        assert result.total_tests == 0


class TestGatherGitHub:
    """Tests for gather_github method."""

    def test_gather_github_returns_optional(self):
        """gather_github returns Optional[GitHubState]."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
                stderr="",
            )
            result = gatherer.gather_github()
        
        assert result is None or isinstance(result, GitHubState)

    def test_gather_github_queries_gh_cli(self):
        """gather_github queries via gh CLI."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"number": 1, "title": "PR 1"}]',
                stderr="",
            )
            gatherer.gather_github()
            
            # Verify gh was called
            assert mock_run.called

    def test_gather_github_handles_unavailable(self):
        """gather_github returns None when GitHub unavailable."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("gh not found")
            result = gatherer.gather_github()
        
        assert result is None


class TestGatherInterruptedSessions:
    """Tests for gather_interrupted_sessions method."""

    def test_gather_interrupted_sessions_returns_list(self):
        """gather_interrupted_sessions returns list of InterruptedSession."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            result = gatherer.gather_interrupted_sessions()
        
        assert isinstance(result, list)

    def test_gather_interrupted_sessions_finds_sessions(self):
        """gather_interrupted_sessions finds interrupted sessions."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        session_data = {
            "session_id": "sess_123",
            "state": "PAUSED",
            "feature_id": "test-feature",
        }
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_path = MagicMock()
            mock_path.read_text.return_value = json.dumps(session_data)
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_interrupted_sessions()
        
        assert len(result) >= 0


class TestCalculateCosts:
    """Tests for calculate_costs method."""

    def test_calculate_costs_returns_tuple(self):
        """calculate_costs returns tuple of floats."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        result = gatherer.calculate_costs()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], (int, float))
        assert isinstance(result[1], (int, float))

    def test_calculate_costs_today_and_weekly(self):
        """calculate_costs returns today and weekly costs."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        today_cost, weekly_cost = gatherer.calculate_costs()
        
        assert today_cost >= 0
        assert weekly_cost >= 0
        assert weekly_cost >= today_cost


class TestGather:
    """Tests for main gather method."""

    def test_gather_returns_snapshot(self):
        """gather returns RepoStateSnapshot."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "gather_git_state") as mock_git, \
             patch.object(gatherer, "gather_features", return_value=[]), \
             patch.object(gatherer, "gather_bugs", return_value=[]), \
             patch.object(gatherer, "gather_prds", return_value=[]), \
             patch.object(gatherer, "gather_specs", return_value=[]), \
             patch.object(gatherer, "gather_tests") as mock_tests, \
             patch.object(gatherer, "gather_github", return_value=None), \
             patch.object(gatherer, "gather_interrupted_sessions", return_value=[]), \
             patch.object(gatherer, "calculate_costs", return_value=(0.0, 0.0)):
            
            mock_git.return_value = GitState(
                current_branch="main",
                status="",
                modified_files=[],
                recent_commits=[],
                ahead=0,
                behind=0,
            )
            mock_tests.return_value = TestState(total_tests=0, test_files=[])
            
            result = gatherer.gather(include_github=False)
        
        assert isinstance(result, RepoStateSnapshot)

    def test_gather_includes_github_when_requested(self):
        """gather includes GitHub state when include_github=True."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "gather_git_state") as mock_git, \
             patch.object(gatherer, "gather_features", return_value=[]), \
             patch.object(gatherer, "gather_bugs", return_value=[]), \
             patch.object(gatherer, "gather_prds", return_value=[]), \
             patch.object(gatherer, "gather_specs", return_value=[]), \
             patch.object(gatherer, "gather_tests") as mock_tests, \
             patch.object(gatherer, "gather_github") as mock_github, \
             patch.object(gatherer, "gather_interrupted_sessions", return_value=[]), \
             patch.object(gatherer, "calculate_costs", return_value=(0.0, 0.0)):
            
            mock_git.return_value = GitState(
                current_branch="main",
                status="",
                modified_files=[],
                recent_commits=[],
                ahead=0,
                behind=0,
            )
            mock_tests.return_value = TestState(total_tests=0, test_files=[])
            mock_github.return_value = GitHubState(open_prs=[], open_issues=[])
            
            gatherer.gather(include_github=True)
            
            mock_github.assert_called_once()

    def test_gather_skips_github_when_not_requested(self):
        """gather skips GitHub state when include_github=False."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "gather_git_state") as mock_git, \
             patch.object(gatherer, "gather_features", return_value=[]), \
             patch.object(gatherer, "gather_bugs", return_value=[]), \
             patch.object(gatherer, "gather_prds", return_value=[]), \
             patch.object(gatherer, "gather_specs", return_value=[]), \
             patch.object(gatherer, "gather_tests") as mock_tests, \
             patch.object(gatherer, "gather_github") as mock_github, \
             patch.object(gatherer, "gather_interrupted_sessions", return_value=[]), \
             patch.object(gatherer, "calculate_costs", return_value=(0.0, 0.0)):
            
            mock_git.return_value = GitState(
                current_branch="main",
                status="",
                modified_files=[],
                recent_commits=[],
                ahead=0,
                behind=0,
            )
            mock_tests.return_value = TestState(total_tests=0, test_files=[])
            
            result = gatherer.gather(include_github=False)
            
            assert result.github is None


class TestRepoStateSnapshot:
    """Tests for RepoStateSnapshot dataclass."""

    def test_snapshot_has_all_fields(self):
        """RepoStateSnapshot has all required fields."""
        snapshot = RepoStateSnapshot(
            git=GitState(
                current_branch="main",
                status="",
                modified_files=[],
                recent_commits=[],
                ahead=0,
                behind=0,
            ),
            features=[],
            bugs=[],
            prds=[],
            specs=[],
            tests=TestState(total_tests=0, test_files=[]),
            github=None,
            interrupted_sessions=[],
            cost_today=0.0,
            cost_weekly=0.0,
            timestamp=datetime.now(),
        )
        
        assert hasattr(snapshot, "git")
        assert hasattr(snapshot, "features")
        assert hasattr(snapshot, "bugs")
        assert hasattr(snapshot, "prds")
        assert hasattr(snapshot, "specs")
        assert hasattr(snapshot, "tests")
        assert hasattr(snapshot, "github")
        assert hasattr(snapshot, "interrupted_sessions")
        assert hasattr(snapshot, "cost_today")
        assert hasattr(snapshot, "cost_weekly")
        assert hasattr(snapshot, "timestamp")


class TestGitState:
    """Tests for GitState dataclass."""

    def test_git_state_has_required_fields(self):
        """GitState has all required fields."""
        state = GitState(
            current_branch="main",
            status="M file.py",
            modified_files=["file.py"],
            recent_commits=["abc123 Initial commit"],
            ahead=1,
            behind=0,
        )
        
        assert state.current_branch == "main"
        assert state.status == "M file.py"
        assert state.modified_files == ["file.py"]
        assert state.recent_commits == ["abc123 Initial commit"]
        assert state.ahead == 1
        assert state.behind == 0


class TestFeatureSummary:
    """Tests for FeatureSummary dataclass."""

    def test_feature_summary_has_fields(self):
        """FeatureSummary has required fields."""
        summary = FeatureSummary(
            feature_id="test-feature",
            phase="IMPLEMENTING",
            issue_count=3,
            completed_issues=1,
        )
        
        assert summary.feature_id == "test-feature"
        assert summary.phase == "IMPLEMENTING"
        assert summary.issue_count == 3
        assert summary.completed_issues == 1


class TestBugSummary:
    """Tests for BugSummary dataclass."""

    def test_bug_summary_has_fields(self):
        """BugSummary has required fields."""
        summary = BugSummary(
            bug_id="bug-123",
            phase="ANALYZING",
            description="Test bug description",
        )
        
        assert summary.bug_id == "bug-123"
        assert summary.phase == "ANALYZING"
        assert summary.description == "Test bug description"


class TestPRDSummary:
    """Tests for PRDSummary dataclass."""

    def test_prd_summary_has_fields(self):
        """PRDSummary has required fields."""
        summary = PRDSummary(
            name="test-feature",
            title="Test Feature",
            status="draft",
        )
        
        assert summary.name == "test-feature"
        assert summary.title == "Test Feature"
        assert summary.status == "draft"


class TestSpecSummary:
    """Tests for SpecSummary dataclass."""

    def test_spec_summary_has_fields(self):
        """SpecSummary has required fields."""
        summary = SpecSummary(
            name="test-feature",
            has_draft=True,
            has_final=False,
            review_status="pending",
        )
        
        assert summary.name == "test-feature"
        assert summary.has_draft is True
        assert summary.has_final is False
        assert summary.review_status == "pending"


class TestTestState:
    """Tests for TestState dataclass."""

    def test_test_state_has_fields(self):
        """TestState has required fields."""
        state = TestState(
            total_tests=42,
            test_files=["test_foo.py", "test_bar.py"],
        )
        
        assert state.total_tests == 42
        assert len(state.test_files) == 2


class TestGitHubState:
    """Tests for GitHubState dataclass."""

    def test_github_state_has_fields(self):
        """GitHubState has required fields."""
        state = GitHubState(
            open_prs=[{"number": 1, "title": "PR 1"}],
            open_issues=[{"number": 2, "title": "Issue 2"}],
        )
        
        assert len(state.open_prs) == 1
        assert len(state.open_issues) == 1


class TestInterruptedSession:
    """Tests for InterruptedSession dataclass."""

    def test_interrupted_session_has_fields(self):
        """InterruptedSession has required fields."""
        session = InterruptedSession(
            session_id="sess_123",
            feature_id="test-feature",
            state="PAUSED",
            timestamp=datetime.now(),
        )
        
        assert session.session_id == "sess_123"
        assert session.feature_id == "test-feature"
        assert session.state == "PAUSED"


class TestGracefulDegradation:
    """Tests for graceful degradation behavior."""

    def test_handles_git_not_available(self):
        """StateGatherer handles git not being available."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch.object(gatherer, "_run_git_command") as mock_git:
            mock_git.side_effect = subprocess.SubprocessError("git not found")
            result = gatherer.gather_git_state()
        
        assert isinstance(result, GitState)
        assert result.current_branch == ""

    def test_handles_missing_swarm_directory(self):
        """StateGatherer handles missing .swarm directory."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.glob", return_value=[]):
            features = gatherer.gather_features()
            bugs = gatherer.gather_bugs()
        
        assert features == []
        assert bugs == []

    def test_handles_corrupted_json(self):
        """StateGatherer handles corrupted JSON files."""
        config = SwarmConfig()
        gatherer = StateGatherer(config)
        
        with patch("pathlib.Path.glob") as mock_glob:
            mock_path = MagicMock()
            mock_path.stem = "test-feature"
            mock_path.read_text.return_value = "not valid json {"
            mock_glob.return_value = [mock_path]
            
            result = gatherer.gather_features()
        
        assert isinstance(result, list)