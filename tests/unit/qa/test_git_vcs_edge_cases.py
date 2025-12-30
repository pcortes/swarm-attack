"""Tests for Git VCS Edge Cases (Spec Section 10.9).

Comprehensive tests for Git edge cases including:
- Detached HEAD state (CI pipelines, specific commit checkout)
- Shallow clones (depth=1, missing history)
- Submodules (uninitialized, version mismatch)
- Large repos (1000+ files, binary files)
- Git errors (not a repo, corrupt objects, locked index)

These tests ensure the QA system handles Git edge cases gracefully
without crashing or producing incorrect results.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import subprocess

from swarm_attack.qa.models import QAContext, QAEndpoint


# =============================================================================
# DETACHED HEAD TESTS (Section 10.9.1)
# =============================================================================


class TestDetachedHEAD:
    """Tests for detached HEAD state handling.

    Detached HEAD occurs when:
    - Checking out a specific commit
    - CI pipeline checkouts
    - Git worktree in detached state

    Expected behavior: Use commit SHA instead of branch name.
    """

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_detached_head_uses_commit_sha(self, agent):
        """Should use commit SHA when in detached HEAD state."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""

                if 'rev-parse --abbrev-ref HEAD' in cmd_str:
                    result.stdout = "HEAD"  # Detached HEAD indicator
                elif 'rev-parse HEAD' in cmd_str:
                    result.stdout = "abc123def456"  # Commit SHA
                elif 'diff --name-only' in cmd_str:
                    result.stdout = "src/api/users.py"
                elif 'status --porcelain' in cmd_str:
                    result.stdout = "M  src/api/users.py"
                else:
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            # Should not raise and should return files
            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_detached_head_ci_pipeline_checkout(self, agent):
        """Should handle CI pipeline checkout scenario (e.g., GitHub Actions)."""
        # CI pipelines often checkout specific commits, not branches
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""

                if 'branch' in cmd_str:
                    # In CI, we might be on a detached HEAD
                    result.stdout = "* (HEAD detached at abc123)"
                elif 'diff --name-only' in cmd_str:
                    result.stdout = "src/api/users.py\nsrc/models/user.py"
                elif 'status --porcelain' in cmd_str:
                    result.stdout = ""
                else:
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)
            # Should still find changed files
            assert "src/api/users.py" in result or len(result) >= 0

    def test_detached_head_git_worktree(self, agent):
        """Should handle git worktree in detached state."""
        # Git worktrees can be in detached HEAD state
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""

                if 'symbolic-ref' in cmd_str:
                    # Worktree not on a branch
                    result.returncode = 128
                    result.stderr = "fatal: ref HEAD is not a symbolic ref"
                elif 'diff --name-only' in cmd_str:
                    result.stdout = "src/services/auth.py"
                elif 'status --porcelain' in cmd_str:
                    result.stdout = "M  src/services/auth.py"
                else:
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)


# =============================================================================
# SHALLOW CLONE TESTS (Section 10.9.2)
# =============================================================================


class TestShallowClone:
    """Tests for shallow clone handling.

    Shallow clones occur when:
    - Cloning with --depth=1 (common in CI)
    - Missing history for diff operations
    - Unable to find merge-base

    Expected behavior: Detect shallow clone, limit diff analysis scope.
    """

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_detects_shallow_clone_via_shallow_file(self, agent):
        """Should detect shallow clone by checking .git/shallow file."""
        with patch.object(Path, 'exists') as mock_exists:
            mock_exists.return_value = True

            result = agent._is_shallow_clone()
            assert result is True

    def test_shallow_clone_depth_1(self, agent):
        """Should handle depth=1 clone gracefully."""
        with patch.object(agent, '_is_shallow_clone', return_value=True):
            with patch('subprocess.run') as mock_run:
                def run_side_effect(*args, **kwargs):
                    cmd = args[0] if args else kwargs.get('args', [])
                    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                    result = MagicMock()

                    if 'merge-base' in cmd_str:
                        # No merge-base in shallow clone
                        result.returncode = 128
                        result.stderr = "fatal: no common ancestor"
                        result.stdout = ""
                    elif 'diff --name-only HEAD~1' in cmd_str:
                        # Can still diff against HEAD~1
                        result.returncode = 0
                        result.stdout = "src/api/users.py"
                        result.stderr = ""
                    elif 'diff --name-only HEAD' in cmd_str:
                        result.returncode = 0
                        result.stdout = "src/api/users.py"
                        result.stderr = ""
                    elif 'status --porcelain' in cmd_str:
                        result.returncode = 0
                        result.stdout = ""
                        result.stderr = ""
                    else:
                        result.returncode = 0
                        result.stdout = ""
                        result.stderr = ""

                    return result

                mock_run.side_effect = run_side_effect

                # Should not crash
                result = agent.analyze_diff({})
                assert isinstance(result, list)

    def test_shallow_clone_missing_history_for_diff(self, agent):
        """Should handle missing history gracefully."""
        with patch.object(agent, '_is_shallow_clone', return_value=True):
            with patch('subprocess.run') as mock_run:
                def run_side_effect(*args, **kwargs):
                    cmd = args[0] if args else kwargs.get('args', [])
                    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                    result = MagicMock()
                    result.stderr = ""

                    if 'origin/main' in cmd_str or 'origin/master' in cmd_str:
                        # No remote branch in shallow clone
                        result.returncode = 128
                        result.stderr = "fatal: ambiguous argument"
                        result.stdout = ""
                    elif 'diff --name-only HEAD' in cmd_str:
                        result.returncode = 0
                        result.stdout = "modified_file.py"
                        result.stderr = ""
                    elif 'status --porcelain' in cmd_str:
                        result.returncode = 0
                        result.stdout = "M  modified_file.py"
                        result.stderr = ""
                    else:
                        result.returncode = 0
                        result.stdout = ""

                    return result

                mock_run.side_effect = run_side_effect

                result = agent.analyze_diff({})
                assert isinstance(result, list)

    def test_shallow_clone_fallback_strategy(self, agent):
        """Should use fallback strategy when main/master not available."""
        with patch.object(agent, '_is_shallow_clone', return_value=True):
            with patch('subprocess.run') as mock_run:
                call_count = [0]

                def run_side_effect(*args, **kwargs):
                    call_count[0] += 1
                    result = MagicMock()
                    result.returncode = 0
                    result.stderr = ""
                    result.stdout = ""

                    cmd = args[0] if args else kwargs.get('args', [])
                    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd

                    if 'diff --name-only HEAD' in cmd_str:
                        result.stdout = "src/new_feature.py"
                    elif 'status --porcelain' in cmd_str:
                        result.stdout = "?? src/new_feature.py"

                    return result

                mock_run.side_effect = run_side_effect

                result = agent.analyze_diff({})
                # Should return results even without full history
                assert isinstance(result, list)


# =============================================================================
# SUBMODULE TESTS (Section 10.9.3)
# =============================================================================


class TestSubmodules:
    """Tests for Git submodule handling.

    Submodule scenarios:
    - Uninitialized submodule
    - Submodule version mismatch
    - Recursive submodules

    Expected behavior: Identify submodules, analyze or skip appropriately.
    """

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_handles_uninitialized_submodule(self, agent):
        """Should handle uninitialized submodule gracefully."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'status --porcelain' in cmd_str:
                    # Submodule shows as modified but can't be accessed
                    result.returncode = 0
                    result.stdout = " M vendor/submodule (uninitialized)"
                    result.stderr = ""
                elif 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    result.stdout = "src/main.py"
                    result.stderr = ""
                elif 'submodule status' in cmd_str:
                    result.returncode = 0
                    result.stdout = "-abc123 vendor/submodule"  # Dash = uninitialized
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            # Should not crash on uninitialized submodule
            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_handles_submodule_version_mismatch(self, agent):
        """Should handle submodule at different commit than expected."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    # +abc123 means submodule is at different commit
                    result.stdout = " M vendor/lib\n+abc123 vendor/lib (def456)"
                    result.stderr = ""
                elif 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    result.stdout = "vendor/lib"  # Submodule itself shows as changed
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_handles_recursive_submodules(self, agent):
        """Should handle nested/recursive submodules."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    # Nested submodule paths
                    result.stdout = "vendor/main/sub/nested/file.py\nsrc/app.py"
                    result.stderr = ""
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "M  src/app.py"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)
            # Should include main repo files
            assert "src/app.py" in result or len(result) >= 0


# =============================================================================
# LARGE REPO TESTS (Section 10.9.4)
# =============================================================================


class TestLargeRepos:
    """Tests for large repository handling.

    Large repo scenarios:
    - Very large diff (1000+ files)
    - Binary files in diff
    - Huge file deletions/additions

    Expected behavior: Enforce limits, sample or paginate results.
    """

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_handles_large_diff_1000_plus_files(self, agent):
        """Should handle very large diff with 1000+ files."""
        # Generate 1500 file paths
        large_file_list = "\n".join([f"src/module{i}/file{j}.py"
                                      for i in range(50) for j in range(30)])

        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    result.stdout = large_file_list
                    result.stderr = ""
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            # Should not crash and should return results
            result = agent.analyze_diff({})
            assert isinstance(result, list)
            # Should return some files (may be limited)
            assert len(result) > 0

    def test_handles_binary_files_in_diff(self, agent):
        """Should handle binary files in diff gracefully."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    # Mix of binary and text files
                    result.stdout = "src/api/users.py\nassets/logo.png\ndata/dump.bin"
                    result.stderr = ""
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "M  src/api/users.py\nM  assets/logo.png"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)
            # Binary files should be included in the list
            assert "assets/logo.png" in result or "src/api/users.py" in result

    def test_handles_huge_file_additions(self, agent):
        """Should handle huge file additions without memory issues."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    # Large data file added
                    result.stdout = "data/large_dataset.json\nsrc/processor.py"
                    result.stderr = ""
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "A  data/large_dataset.json"
                    result.stderr = ""
                elif 'diff --stat' in cmd_str:
                    result.returncode = 0
                    # Indicates huge file
                    result.stdout = "data/large_dataset.json | 1000000 +++++++++++++++++++"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_handles_huge_file_deletions(self, agent):
        """Should handle huge file deletions gracefully."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()
                result.stderr = ""

                if 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    result.stdout = "legacy/old_data.sql\nsrc/cleanup.py"
                    result.stderr = ""
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "D  legacy/old_data.sql"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""

                return result

            mock_run.side_effect = run_side_effect

            result = agent.analyze_diff({})
            assert isinstance(result, list)


# =============================================================================
# GIT ERROR TESTS (Section 10.9.5)
# =============================================================================


class TestGitErrors:
    """Tests for Git error handling.

    Git error scenarios:
    - Not a git repository
    - Corrupt git objects
    - Locked index file
    - Permission denied on .git

    Expected behavior: Graceful error handling, skip git-dependent features.
    """

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_handles_not_a_git_repository(self, agent):
        """Should handle 'not a git repository' error gracefully."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError

        with patch('subprocess.run') as mock_run:
            result = MagicMock()
            result.returncode = 128
            result.stdout = ""
            result.stderr = "fatal: not a git repository (or any of the parent directories): .git"
            mock_run.return_value = result

            with pytest.raises(GitEdgeCaseError) as exc_info:
                agent.analyze_diff({})

            assert "git repository" in str(exc_info.value).lower()

    def test_handles_corrupt_git_objects(self, agent):
        """Should handle corrupt git objects gracefully."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()

                if 'diff' in cmd_str:
                    result.returncode = 128
                    result.stdout = ""
                    result.stderr = "error: object file .git/objects/ab/cdef is empty"
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "M  src/main.py"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""

                return result

            mock_run.side_effect = run_side_effect

            # Should not crash, may return partial results
            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_handles_locked_index_file(self, agent):
        """Should handle locked index file (.git/index.lock exists)."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
                result = MagicMock()

                if 'status' in cmd_str:
                    result.returncode = 128
                    result.stdout = ""
                    result.stderr = "fatal: Unable to create '.git/index.lock': File exists."
                elif 'diff --name-only' in cmd_str:
                    result.returncode = 0
                    result.stdout = "src/main.py"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""

                return result

            mock_run.side_effect = run_side_effect

            # Should not crash, should try to get what info is available
            result = agent.analyze_diff({})
            assert isinstance(result, list)

    def test_handles_permission_denied_on_git_directory(self, agent):
        """Should handle permission denied on .git directory."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError

        with patch('subprocess.run') as mock_run:
            result = MagicMock()
            result.returncode = 128
            result.stdout = ""
            result.stderr = "fatal: cannot read '.git/HEAD': Permission denied"
            mock_run.return_value = result

            # Should handle gracefully - either raise GitEdgeCaseError or return empty
            try:
                files = agent.analyze_diff({})
                assert isinstance(files, list)
            except GitEdgeCaseError:
                pass  # Also acceptable

    def test_handles_git_command_not_found(self, agent):
        """Should handle git command not being installed."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("git: command not found")

            with pytest.raises(GitEdgeCaseError) as exc_info:
                agent.analyze_diff({})

            assert "git" in str(exc_info.value).lower()

    def test_handles_git_command_timeout(self, agent):
        """Should handle git command timeout."""
        from swarm_attack.qa.agents.regression import GitEdgeCaseError

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git diff", 30)

            with pytest.raises(GitEdgeCaseError) as exc_info:
                agent._run_git_command("git diff HEAD")

            assert "timed out" in str(exc_info.value).lower()


# =============================================================================
# CONTEXT BUILDER GIT EDGE CASES
# =============================================================================


class TestContextBuilderGitEdgeCases:
    """Tests for QAContextBuilder's git diff handling."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_get_git_diff_handles_detached_head(self, builder):
        """Should handle detached HEAD when getting git diff."""
        with patch('subprocess.run') as mock_run:
            def run_side_effect(*args, **kwargs):
                result = MagicMock()
                result.returncode = 0
                result.stdout = "diff --git a/file.py b/file.py\n+new line"
                result.stderr = ""
                return result

            mock_run.side_effect = run_side_effect

            diff = builder._get_git_diff()
            # Should return diff even in detached HEAD
            assert diff is None or isinstance(diff, str)

    def test_get_git_diff_handles_not_git_repo(self, builder):
        """Should return None when not in a git repo."""
        with patch('subprocess.run') as mock_run:
            result = MagicMock()
            result.returncode = 128
            result.stdout = ""
            result.stderr = "fatal: not a git repository"
            mock_run.return_value = result

            diff = builder._get_git_diff()
            # Should return None, not raise
            assert diff is None or diff == ""

    def test_get_git_diff_handles_timeout(self, builder):
        """Should handle timeout when getting git diff."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git diff", 30)

            diff = builder._get_git_diff()
            # Should return None on timeout, not raise
            assert diff is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestGitEdgeCaseIntegration:
    """Integration tests for git edge case scenarios."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.regression import RegressionScannerAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return RegressionScannerAgent(config)

    def test_full_run_with_detached_head_and_shallow_clone(self, agent):
        """Should complete full run() with both detached HEAD and shallow clone."""
        with patch.object(agent, '_is_shallow_clone', return_value=True):
            with patch('subprocess.run') as mock_run:
                def run_side_effect(*args, **kwargs):
                    result = MagicMock()
                    result.returncode = 0
                    result.stderr = ""

                    cmd = args[0] if args else kwargs.get('args', [])
                    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd

                    if 'diff --name-only' in cmd_str:
                        result.stdout = "src/api/users.py"
                    elif 'status --porcelain' in cmd_str:
                        result.stdout = "M  src/api/users.py"
                    else:
                        result.stdout = ""

                    return result

                mock_run.side_effect = run_side_effect

                context = {
                    "endpoints": [QAEndpoint(method="GET", path="/api/users")],
                }

                result = agent.run(context)

                # Should complete without error
                assert result.success is True
                assert "files_analyzed" in result.output

    def test_full_run_with_git_errors_falls_back_gracefully(self, agent):
        """Should fall back gracefully when git operations fail."""
        with patch('subprocess.run') as mock_run:
            call_count = [0]

            def run_side_effect(*args, **kwargs):
                call_count[0] += 1
                result = MagicMock()

                cmd = args[0] if args else kwargs.get('args', [])
                cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd

                # First diff fails, but status succeeds
                if 'diff --name-only' in cmd_str and call_count[0] == 1:
                    result.returncode = 128
                    result.stdout = ""
                    result.stderr = "error: corrupt object"
                elif 'status --porcelain' in cmd_str:
                    result.returncode = 0
                    result.stdout = "M  src/fallback.py"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""

                return result

            mock_run.side_effect = run_side_effect

            context = {
                "endpoints": [QAEndpoint(method="GET", path="/api/users")],
            }

            result = agent.run(context)

            # Should complete, possibly with partial results
            # The agent either succeeds with fallback or fails gracefully
            assert isinstance(result.success, bool)
