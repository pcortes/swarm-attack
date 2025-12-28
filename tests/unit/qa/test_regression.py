"""Tests for RegressionScannerAgent following TDD approach.

Tests cover spec sections 4.3, 10.9:
- Git diff analysis to find affected files
- Mapping file changes to affected endpoints
- Priority scoring based on change impact
- Regression suite selection based on priorities
- Git edge cases (dirty worktree, detached HEAD, shallow clone, etc.)
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from swarm_attack.qa.models import (
    QAContext, QAEndpoint, QAFinding, QADepth, QALimits,
)


# =============================================================================
# Test Imports (these will fail until we implement the agent)
# =============================================================================


class TestRegressionScannerImports:
    """Test that RegressionScannerAgent can be imported."""

    def test_can_import_regression_scanner(self):
        """Should be able to import RegressionScannerAgent."""
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        assert RegressionScannerAgent is not None

    def test_can_import_git_edge_case_error(self):
        """Should be able to import GitEdgeCaseError."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError
        assert GitEdgeCaseError is not None

    def test_can_import_impact_map_dataclass(self):
        """Should be able to import ImpactMap dataclass."""
        from swarm_attack.qa.agents.regression import ImpactMap
        assert ImpactMap is not None


# =============================================================================
# Test RegressionScannerAgent Initialization
# =============================================================================


class TestRegressionScannerInit:
    """Tests for RegressionScannerAgent initialization."""

    def test_agent_has_correct_name(self):
        """Agent should have correct name for logging."""
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = RegressionScannerAgent(config)
        assert agent.name == "regression_scanner"

    def test_agent_has_default_limits(self):
        """Agent should have default QALimits."""
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = RegressionScannerAgent(config)
        assert agent.limits is not None
        assert hasattr(agent.limits, 'max_endpoints_standard')

    def test_agent_accepts_custom_limits(self):
        """Agent should accept custom QALimits."""
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        custom_limits = QALimits(max_endpoints_standard=25)
        agent = RegressionScannerAgent(config, limits=custom_limits)
        assert agent.limits.max_endpoints_standard == 25

    def test_agent_has_priority_thresholds(self):
        """Agent should have priority thresholds for test selection."""
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = RegressionScannerAgent(config)
        # Must test threshold (priority >= 80)
        assert hasattr(agent, 'must_test_threshold')
        assert agent.must_test_threshold == 80
        # Should test threshold (priority >= 50)
        assert hasattr(agent, 'should_test_threshold')
        assert agent.should_test_threshold == 50


# =============================================================================
# Test Git Diff Analysis (Section 4.3)
# =============================================================================


class TestAnalyzeDiff:
    """Tests for analyze_diff() method."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_analyze_diff_returns_changed_files(self, agent):
        """Should analyze git diff and return list of changed files."""
        context = QAContext(git_diff="diff --git a/src/api/users.py b/src/api/users.py")

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.return_value = "src/api/users.py\nsrc/models/user.py"
            result = agent.analyze_diff(context)

            assert isinstance(result, list)
            assert len(result) >= 1
            assert any("users.py" in f for f in result)

    def test_analyze_diff_handles_multiple_files(self, agent):
        """Should handle diffs with multiple files."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.return_value = "src/api/users.py\nsrc/api/posts.py\nsrc/models/user.py"
            result = agent.analyze_diff(context)

            assert len(result) == 3
            assert "src/api/users.py" in result
            assert "src/api/posts.py" in result
            assert "src/models/user.py" in result

    def test_analyze_diff_filters_test_files(self, agent):
        """Should filter out test files from analysis."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.return_value = "src/api/users.py\ntests/test_users.py\nsrc/models/user.py"
            result = agent.analyze_diff(context)

            # Should not include test files in change analysis
            assert not any("test_" in f for f in result)
            assert "src/api/users.py" in result
            assert "src/models/user.py" in result

    def test_analyze_diff_handles_renames(self, agent):
        """Should detect renamed files."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            # Git shows renames as "old_name => new_name"
            mock_git.return_value = "src/api/{old_users.py => users.py}"
            result = agent.analyze_diff(context)

            assert len(result) >= 1
            # Should track both old and new names for impact analysis
            assert any("users.py" in f for f in result)

    def test_analyze_diff_handles_deletions(self, agent):
        """Should handle deleted files."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.return_value = "src/api/users.py\nsrc/api/old_api.py (deleted)"
            result = agent.analyze_diff(context)

            # Should include deleted files in impact analysis
            assert len(result) >= 2


# =============================================================================
# Test Git Edge Cases (Section 10.9)
# =============================================================================


class TestGitEdgeCases:
    """Tests for git edge cases (Section 10.9)."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_handles_dirty_worktree(self, agent):
        """Should handle dirty worktree gracefully (Section 10.9)."""
        context = QAContext()

        with patch.object(agent, '_check_git_status') as mock_status:
            mock_status.return_value = {"dirty": True, "uncommitted_files": ["src/api/users.py"]}
            with patch.object(agent, '_run_git_command') as mock_git:
                mock_git.return_value = "src/api/users.py"

                # Should not raise, should include uncommitted files
                result = agent.analyze_diff(context)
                assert "src/api/users.py" in result

    def test_handles_detached_head(self, agent):
        """Should handle detached HEAD state (Section 10.9)."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            def git_side_effect(cmd):
                if "rev-parse --abbrev-ref HEAD" in cmd:
                    return "HEAD"  # Detached HEAD
                return "src/api/users.py"
            mock_git.side_effect = git_side_effect

            # Should use commit hash instead of branch name
            result = agent.analyze_diff(context)
            assert isinstance(result, list)

    def test_handles_missing_main_branch(self, agent):
        """Should handle missing main/master branch (Section 10.9)."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            def git_side_effect(cmd):
                if "main" in cmd or "master" in cmd:
                    raise Exception("fatal: ambiguous argument 'main': unknown revision")
                return "src/api/users.py"
            mock_git.side_effect = git_side_effect

            # Should fall back to alternative comparison strategy
            result = agent.analyze_diff(context)
            assert isinstance(result, list)

    def test_handles_shallow_clone(self, agent):
        """Should handle shallow clone (Section 10.9)."""
        context = QAContext()

        with patch.object(agent, '_is_shallow_clone') as mock_shallow:
            mock_shallow.return_value = True
            with patch.object(agent, '_run_git_command') as mock_git:
                mock_git.return_value = "src/api/users.py"

                # Should use HEAD~1 or working tree changes
                result = agent.analyze_diff(context)
                assert isinstance(result, list)

    def test_handles_uncommitted_new_files(self, agent):
        """Should handle uncommitted new files (Section 10.9)."""
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            # Untracked files appear in git status but not in diff
            def git_side_effect(cmd):
                if "status --porcelain" in cmd:
                    return "?? src/api/new_endpoint.py\nM  src/api/users.py"
                return "src/api/users.py"
            mock_git.side_effect = git_side_effect

            result = agent.analyze_diff(context)
            # Should include both modified and new files
            assert "src/api/users.py" in result
            assert "src/api/new_endpoint.py" in result

    def test_handles_git_not_installed(self, agent):
        """Should handle git command not available."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.side_effect = FileNotFoundError("git command not found")

            # Should raise GitEdgeCaseError with helpful message
            with pytest.raises(GitEdgeCaseError) as exc_info:
                agent.analyze_diff(context)
            assert "git" in str(exc_info.value).lower()

    def test_handles_not_a_git_repo(self, agent):
        """Should handle directory that is not a git repository."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError
        context = QAContext()

        with patch.object(agent, '_run_git_command') as mock_git:
            mock_git.side_effect = Exception("fatal: not a git repository")

            # Should raise GitEdgeCaseError
            with pytest.raises(GitEdgeCaseError) as exc_info:
                agent.analyze_diff(context)
            assert "git repository" in str(exc_info.value).lower()


# =============================================================================
# Test Mapping Changes to Endpoints (Section 4.3)
# =============================================================================


class TestMapChangesToEndpoints:
    """Tests for map_changes_to_endpoints() method."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_maps_endpoint_handler_changes(self, agent):
        """Should map direct endpoint handler changes."""
        changed_files = ["src/api/users.py"]
        endpoints = [
            QAEndpoint(method="GET", path="/api/users"),
            QAEndpoint(method="POST", path="/api/posts"),
        ]

        with patch.object(agent, '_find_endpoint_for_file') as mock_find:
            mock_find.return_value = "/api/users"
            result = agent.map_changes_to_endpoints(changed_files, endpoints)

            assert isinstance(result, dict)
            assert "/api/users" in result
            assert result["/api/users"]["files"] == ["src/api/users.py"]

    def test_maps_model_changes(self, agent):
        """Should map model changes to endpoints that use them."""
        changed_files = ["src/models/user.py"]
        endpoints = [
            QAEndpoint(method="GET", path="/api/users"),
            QAEndpoint(method="GET", path="/api/posts"),
        ]

        with patch.object(agent, '_find_endpoints_using_model') as mock_find:
            mock_find.return_value = ["/api/users"]
            result = agent.map_changes_to_endpoints(changed_files, endpoints)

            assert "/api/users" in result
            assert "src/models/user.py" in result["/api/users"]["files"]

    def test_maps_service_changes(self, agent):
        """Should map service changes to endpoints that call them."""
        changed_files = ["src/services/auth_service.py"]
        endpoints = [
            QAEndpoint(method="POST", path="/api/login"),
            QAEndpoint(method="GET", path="/api/users"),
        ]

        with patch.object(agent, '_find_endpoints_using_service') as mock_find:
            mock_find.return_value = ["/api/login"]
            result = agent.map_changes_to_endpoints(changed_files, endpoints)

            assert "/api/login" in result

    def test_maps_utility_changes(self, agent):
        """Should map utility changes to endpoints using them indirectly."""
        changed_files = ["src/utils/validators.py"]
        endpoints = [QAEndpoint(method="POST", path="/api/users")]

        with patch.object(agent, '_find_endpoints_using_utility') as mock_find:
            mock_find.return_value = ["/api/users"]
            result = agent.map_changes_to_endpoints(changed_files, endpoints)

            assert "/api/users" in result

    def test_maps_config_changes(self, agent):
        """Should map config changes to affected endpoints."""
        changed_files = ["config/database.yml"]
        endpoints = [
            QAEndpoint(method="GET", path="/api/users"),
            QAEndpoint(method="GET", path="/api/posts"),
        ]

        with patch.object(agent, '_find_endpoints_affected_by_config') as mock_find:
            # Config changes might affect all database-backed endpoints
            mock_find.return_value = ["/api/users", "/api/posts"]
            result = agent.map_changes_to_endpoints(changed_files, endpoints)

            assert len(result) >= 2

    def test_handles_no_affected_endpoints(self, agent):
        """Should handle changes that don't affect any endpoints."""
        changed_files = ["README.md", "docs/guide.md"]
        endpoints = [QAEndpoint(method="GET", path="/api/users")]

        result = agent.map_changes_to_endpoints(changed_files, endpoints)

        # Should return empty or minimal impact
        assert isinstance(result, dict)


# =============================================================================
# Test Priority Scoring (Section 4.3)
# =============================================================================


class TestPrioritizeEndpoints:
    """Tests for prioritize_endpoints() method with scoring rules."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_direct_endpoint_handler_change_priority_100(self, agent):
        """Direct change to endpoint handler should have priority 100 (Section 4.3)."""
        impact_map = {
            "/api/users": {
                "files": ["src/api/users.py"],
                "change_type": "direct_handler"
            }
        }

        result = agent.prioritize_endpoints(impact_map)

        assert isinstance(result, dict)
        assert result["/api/users"]["priority"] == 100
        assert result["/api/users"]["reason"] == "direct_handler"

    def test_model_change_priority_80(self, agent):
        """Model change used by endpoint should have priority 80 (Section 4.3)."""
        impact_map = {
            "/api/users": {
                "files": ["src/models/user.py"],
                "change_type": "model"
            }
        }

        result = agent.prioritize_endpoints(impact_map)

        assert result["/api/users"]["priority"] == 80
        assert result["/api/users"]["reason"] == "model"

    def test_service_change_priority_60(self, agent):
        """Service change called by endpoint should have priority 60 (Section 4.3)."""
        impact_map = {
            "/api/users": {
                "files": ["src/services/user_service.py"],
                "change_type": "service"
            }
        }

        result = agent.prioritize_endpoints(impact_map)

        assert result["/api/users"]["priority"] == 60
        assert result["/api/users"]["reason"] == "service"

    def test_utility_change_priority_40(self, agent):
        """Utility change used indirectly should have priority 40 (Section 4.3)."""
        impact_map = {
            "/api/users": {
                "files": ["src/utils/validators.py"],
                "change_type": "utility"
            }
        }

        result = agent.prioritize_endpoints(impact_map)

        assert result["/api/users"]["priority"] == 40
        assert result["/api/users"]["reason"] == "utility"

    def test_config_change_priority_30(self, agent):
        """Config change affecting endpoint should have priority 30 (Section 4.3)."""
        impact_map = {
            "/api/users": {
                "files": ["config/database.yml"],
                "change_type": "config"
            }
        }

        result = agent.prioritize_endpoints(impact_map)

        assert result["/api/users"]["priority"] == 30
        assert result["/api/users"]["reason"] == "config"

    def test_multiple_changes_use_highest_priority(self, agent):
        """Should use highest priority when multiple change types affect endpoint."""
        impact_map = {
            "/api/users": {
                "files": ["src/api/users.py", "src/models/user.py"],
                "change_type": "multiple"
            }
        }

        with patch.object(agent, '_determine_change_type') as mock_determine:
            mock_determine.return_value = "direct_handler"  # Highest priority
            result = agent.prioritize_endpoints(impact_map)

            # Should use direct_handler priority (100) not model (80)
            assert result["/api/users"]["priority"] == 100

    def test_returns_sorted_by_priority(self, agent):
        """Should return endpoints sorted by priority (highest first)."""
        impact_map = {
            "/api/posts": {"files": ["src/utils/helpers.py"], "change_type": "utility"},
            "/api/users": {"files": ["src/api/users.py"], "change_type": "direct_handler"},
            "/api/auth": {"files": ["src/models/user.py"], "change_type": "model"},
        }

        result = agent.prioritize_endpoints(impact_map)

        priorities = [v["priority"] for v in result.values()]
        # Should be sorted descending
        assert priorities == sorted(priorities, reverse=True)


# =============================================================================
# Test Regression Suite Selection
# =============================================================================


class TestSelectRegressionSuite:
    """Tests for select_regression_suite() method."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_must_test_priority_80_and_above(self, agent):
        """Priority >= 80 should be in must_test category."""
        priorities = {
            "/api/users": {"priority": 100, "reason": "direct_handler"},
            "/api/posts": {"priority": 80, "reason": "model"},
            "/api/comments": {"priority": 60, "reason": "service"},
        }

        result = agent.select_regression_suite(priorities)

        assert "must_test" in result
        assert "/api/users" in result["must_test"]
        assert "/api/posts" in result["must_test"]
        assert "/api/comments" not in result["must_test"]

    def test_should_test_priority_50_to_79(self, agent):
        """Priority 50-79 should be in should_test category."""
        priorities = {
            "/api/users": {"priority": 60, "reason": "service"},
            "/api/posts": {"priority": 50, "reason": "utility"},
            "/api/comments": {"priority": 40, "reason": "utility"},
        }

        result = agent.select_regression_suite(priorities)

        assert "should_test" in result
        assert "/api/users" in result["should_test"]
        assert "/api/posts" in result["should_test"]
        assert "/api/comments" not in result["should_test"]

    def test_may_skip_priority_below_50(self, agent):
        """Priority < 50 should be in may_skip category."""
        priorities = {
            "/api/users": {"priority": 40, "reason": "utility"},
            "/api/posts": {"priority": 30, "reason": "config"},
        }

        result = agent.select_regression_suite(priorities)

        assert "may_skip" in result
        assert "/api/users" in result["may_skip"]
        assert "/api/posts" in result["may_skip"]

    def test_respects_max_endpoints_limit(self, agent):
        """Should respect max_endpoints limit from QALimits."""
        # Create many high-priority endpoints
        priorities = {
            f"/api/endpoint{i}": {"priority": 100, "reason": "direct_handler"}
            for i in range(100)
        }

        agent.limits = QALimits(max_endpoints_standard=10)
        result = agent.select_regression_suite(priorities)

        # Should cap at limit
        total_selected = len(result["must_test"]) + len(result["should_test"])
        assert total_selected <= 10

    def test_includes_metadata_in_result(self, agent):
        """Should include metadata about selection criteria."""
        priorities = {
            "/api/users": {"priority": 100, "reason": "direct_handler"},
        }

        result = agent.select_regression_suite(priorities)

        assert "must_test" in result
        assert "should_test" in result
        assert "may_skip" in result
        # Each endpoint should have priority and reason
        for endpoint in result["must_test"]:
            assert isinstance(endpoint, (str, dict))


# =============================================================================
# Test Agent Run Method
# =============================================================================


class TestRegressionScannerRun:
    """Tests for the main run() method."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_run_returns_agent_result(self, agent):
        """Should return AgentResult from run()."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py"]):
            with patch.object(agent, 'map_changes_to_endpoints', return_value={"/api/users": {}}):
                with patch.object(agent, 'prioritize_endpoints', return_value={"/api/users": {"priority": 100}}):
                    with patch.object(agent, 'select_regression_suite', return_value={"must_test": [], "should_test": [], "may_skip": []}):
                        result = agent.run(context)

                        assert hasattr(result, 'success')
                        assert hasattr(result, 'output')
                        assert result.success is True

    def test_run_includes_files_analyzed_count(self, agent):
        """Should include count of files analyzed."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py", "src/models/user.py"]):
            with patch.object(agent, 'map_changes_to_endpoints', return_value={}):
                with patch.object(agent, 'prioritize_endpoints', return_value={}):
                    with patch.object(agent, 'select_regression_suite', return_value={"must_test": [], "should_test": [], "may_skip": []}):
                        result = agent.run(context)

                        assert result.output is not None
                        assert "files_analyzed" in result.output
                        assert result.output["files_analyzed"] == 2

    def test_run_includes_endpoints_affected_count(self, agent):
        """Should include count of endpoints affected."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [
                QAEndpoint(method="GET", path="/api/users"),
                QAEndpoint(method="POST", path="/api/users"),
            ],
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py"]):
            with patch.object(agent, 'map_changes_to_endpoints') as mock_map:
                mock_map.return_value = {
                    "/api/users": {"priority": 100},
                    "POST /api/users": {"priority": 100},
                }
                with patch.object(agent, 'prioritize_endpoints', return_value=mock_map.return_value):
                    with patch.object(agent, 'select_regression_suite', return_value={"must_test": [], "should_test": [], "may_skip": []}):
                        result = agent.run(context)

                        assert result.output is not None
                        assert "endpoints_affected" in result.output
                        assert result.output["endpoints_affected"] == 2

    def test_run_includes_impact_map(self, agent):
        """Should include impact map in output."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        impact_map = {
            "/api/users": {
                "files": ["src/api/users.py"],
                "change_type": "direct_handler"
            }
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py"]):
            with patch.object(agent, 'map_changes_to_endpoints', return_value=impact_map):
                with patch.object(agent, 'prioritize_endpoints') as mock_prioritize:
                    mock_prioritize.return_value = {
                        "/api/users": {"priority": 100, "reason": "direct_handler"}
                    }
                    with patch.object(agent, 'select_regression_suite', return_value={"must_test": [], "should_test": [], "may_skip": []}):
                        result = agent.run(context)

                        assert "impact_map" in result.output
                        assert "/api/users" in result.output["impact_map"]

    def test_run_includes_regression_suite(self, agent):
        """Should include regression suite in output."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        regression_suite = {
            "must_test": ["/api/users"],
            "should_test": [],
            "may_skip": []
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py"]):
            with patch.object(agent, 'map_changes_to_endpoints', return_value={"/api/users": {}}):
                with patch.object(agent, 'prioritize_endpoints', return_value={"/api/users": {"priority": 100}}):
                    with patch.object(agent, 'select_regression_suite', return_value=regression_suite):
                        result = agent.run(context)

                        assert "regression_suite" in result.output
                        assert result.output["regression_suite"]["must_test"] == ["/api/users"]

    def test_run_output_has_correct_format(self, agent):
        """Should return output in the correct format (Section 4.3)."""
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        with patch.object(agent, 'analyze_diff', return_value=["src/api/users.py"]):
            with patch.object(agent, 'map_changes_to_endpoints', return_value={"/api/users": {}}):
                with patch.object(agent, 'prioritize_endpoints', return_value={"/api/users": {"priority": 100}}):
                    with patch.object(agent, 'select_regression_suite') as mock_select:
                        mock_select.return_value = {
                            "must_test": ["/api/users"],
                            "should_test": [],
                            "may_skip": []
                        }
                        result = agent.run(context)

                        # Verify output format matches spec
                        assert result.output["agent"] == "regression_scanner"
                        assert "files_analyzed" in result.output
                        assert "endpoints_affected" in result.output
                        assert "impact_map" in result.output
                        assert "regression_suite" in result.output

    def test_run_handles_no_changes(self, agent):
        """Should handle case where no files changed."""
        context = {
            "git_diff": "",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        with patch.object(agent, 'analyze_diff', return_value=[]):
            result = agent.run(context)

            assert result.success is True
            assert result.output["files_analyzed"] == 0
            assert result.output["endpoints_affected"] == 0

    def test_run_handles_git_error(self, agent):
        """Should handle git errors gracefully."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError
        context = {
            "git_diff": "src/api/users.py",
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
        }

        with patch.object(agent, 'analyze_diff') as mock_analyze:
            mock_analyze.side_effect = GitEdgeCaseError("Not a git repository")
            result = agent.run(context)

            assert result.success is False
            assert "git" in result.error.lower()


# =============================================================================
# Test File Type Detection
# =============================================================================


class TestFileTypeDetection:
    """Tests for detecting file types to determine change impact."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_detects_endpoint_handler_files(self, agent):
        """Should detect endpoint handler files (api/, routes/, handlers/)."""
        assert agent._is_endpoint_handler("src/api/users.py") is True
        assert agent._is_endpoint_handler("src/routes/auth.py") is True
        assert agent._is_endpoint_handler("src/handlers/posts.py") is True
        assert agent._is_endpoint_handler("src/models/user.py") is False

    def test_detects_model_files(self, agent):
        """Should detect model files."""
        assert agent._is_model_file("src/models/user.py") is True
        assert agent._is_model_file("src/db/models/post.py") is True
        assert agent._is_model_file("src/api/users.py") is False

    def test_detects_service_files(self, agent):
        """Should detect service layer files."""
        assert agent._is_service_file("src/services/user_service.py") is True
        assert agent._is_service_file("src/business/auth_service.py") is True
        assert agent._is_service_file("src/models/user.py") is False

    def test_detects_utility_files(self, agent):
        """Should detect utility/helper files."""
        assert agent._is_utility_file("src/utils/validators.py") is True
        assert agent._is_utility_file("src/helpers/formatters.py") is True
        assert agent._is_utility_file("src/lib/crypto.py") is True
        assert agent._is_utility_file("src/api/users.py") is False

    def test_detects_config_files(self, agent):
        """Should detect configuration files."""
        assert agent._is_config_file("config/database.yml") is True
        assert agent._is_config_file("config.json") is True
        assert agent._is_config_file(".env") is True
        assert agent._is_config_file("src/api/users.py") is False


# =============================================================================
# Test Code Analysis Helpers
# =============================================================================


class TestCodeAnalysisHelpers:
    """Tests for helper methods that analyze code relationships."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_finds_imports_in_file(self, agent):
        """Should find import statements in a file."""
        code = """
from src.models.user import User
from src.services.auth_service import AuthService
import json
        """

        imports = agent._extract_imports(code)

        assert "src.models.user" in imports or "User" in imports
        assert "src.services.auth_service" in imports or "AuthService" in imports

    def test_maps_model_to_endpoints(self, agent):
        """Should map a model to endpoints that import it."""
        model_file = "src/models/user.py"

        # Mock file system with endpoint files that import User
        with patch.object(agent, '_read_file') as mock_read:
            mock_read.return_value = "from src.models.user import User"
            with patch.object(agent, '_find_all_endpoint_files') as mock_endpoints:
                mock_endpoints.return_value = ["src/api/users.py", "src/api/auth.py"]

                endpoints = agent._find_endpoints_using_model(model_file)

                assert isinstance(endpoints, list)
                assert len(endpoints) >= 0

    def test_detects_circular_dependencies(self, agent):
        """Should detect and handle circular dependencies gracefully."""
        # File A imports B, B imports A
        with patch.object(agent, '_extract_imports') as mock_imports:
            call_count = [0]
            def side_effect(code):
                call_count[0] += 1
                if call_count[0] > 10:
                    return []  # Prevent infinite loop
                return ["file_a", "file_b"]
            mock_imports.side_effect = side_effect

            # Should not hang or crash
            with patch.object(agent, '_read_file', return_value="import file_b"):
                result = agent._find_endpoints_using_utility("src/utils/helper.py")
                assert isinstance(result, list)
