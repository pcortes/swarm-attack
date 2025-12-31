"""Tests for commit discovery functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from swarm_attack.commit_review.discovery import discover_commits
from swarm_attack.commit_review.models import CommitInfo


class TestDiscoverCommits:
    """Tests for discover_commits function."""

    def test_discover_commits_last_24h(self, tmp_path):
        """Returns commits from last 24 hours with metadata."""
        # Given a repo with recent commits
        mock_git_output = """abc1234|John Doe|john@example.com|2025-12-31 10:00:00|feat: add new feature|5 files changed, 100 insertions(+), 20 deletions(-)"""

        with patch("swarm_attack.commit_review.discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=mock_git_output,
                returncode=0
            )

            # When discovering commits
            commits = discover_commits(str(tmp_path), since="24 hours ago")

            # Then returns list of CommitInfo with metadata
            assert len(commits) >= 1
            assert isinstance(commits[0], CommitInfo)
            assert commits[0].sha == "abc1234"
            assert commits[0].author == "John Doe"
            assert commits[0].message == "feat: add new feature"

    def test_discover_commits_by_branch(self, tmp_path):
        """Filters commits by branch name."""
        mock_git_output = """def5678|Jane Doe|jane@example.com|2025-12-31 11:00:00|fix: bug fix|2 files changed, 10 insertions(+), 5 deletions(-)"""

        with patch("swarm_attack.commit_review.discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=mock_git_output,
                returncode=0
            )

            # When filtering by branch
            commits = discover_commits(str(tmp_path), branch="feature/xyz")

            # Then git command includes branch filter
            call_args = mock_run.call_args[0][0]
            assert "feature/xyz" in call_args

    def test_discover_commits_empty_result(self, tmp_path):
        """Returns empty list when no commits in range."""
        with patch("swarm_attack.commit_review.discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                returncode=0
            )

            # When no commits in range
            commits = discover_commits(str(tmp_path), since="1 hour ago")

            # Then returns empty list
            assert commits == []

    def test_commit_info_includes_diff_stats(self, tmp_path):
        """CommitInfo includes files_changed, insertions, deletions."""
        mock_git_output = """ghi9012|Dev User|dev@example.com|2025-12-31 12:00:00|refactor: cleanup|3 files changed, 50 insertions(+), 30 deletions(-)"""

        with patch("swarm_attack.commit_review.discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=mock_git_output,
                returncode=0
            )

            commits = discover_commits(str(tmp_path))

            # Then CommitInfo includes diff stats
            assert commits[0].files_changed == 3
            assert commits[0].insertions == 50
            assert commits[0].deletions == 30

    def test_discover_commits_handles_git_error(self, tmp_path):
        """Raises exception on git error."""
        with patch("swarm_attack.commit_review.discovery.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="fatal: not a git repository",
                returncode=128
            )

            with pytest.raises(RuntimeError, match="git"):
                discover_commits(str(tmp_path))
