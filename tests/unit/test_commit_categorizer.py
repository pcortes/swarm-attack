"""Tests for commit categorization functionality."""

import pytest

from swarm_attack.commit_review.categorizer import categorize_commit
from swarm_attack.commit_review.models import CommitInfo, CommitCategory


class TestCategorizeCommit:
    """Tests for categorize_commit function."""

    def _make_commit(
        self,
        message: str,
        files: list[str] | None = None,
    ) -> CommitInfo:
        """Helper to create a CommitInfo for testing."""
        return CommitInfo(
            sha="abc123",
            author="Test User",
            email="test@example.com",
            timestamp="2025-12-31 10:00:00",
            message=message,
            files_changed=len(files) if files else 1,
            insertions=10,
            deletions=5,
            changed_files=files or ["src/main.py"],
        )

    def test_categorize_bug_fix(self):
        """Commits with 'fix' in message categorized as BUG_FIX."""
        commit = self._make_commit("fix: resolve null pointer exception")

        category = categorize_commit(commit)

        assert category == CommitCategory.BUG_FIX

    def test_categorize_bug_fix_case_insensitive(self):
        """Bug fix detection is case insensitive."""
        commit = self._make_commit("Fix: handle edge case")

        category = categorize_commit(commit)

        assert category == CommitCategory.BUG_FIX

    def test_categorize_refactor(self):
        """Commits with 'refactor' categorized as REFACTOR."""
        commit = self._make_commit("refactor: extract common logic")

        category = categorize_commit(commit)

        assert category == CommitCategory.REFACTOR

    def test_categorize_test_change(self):
        """Commits touching only test files categorized as TEST_CHANGE."""
        commit = self._make_commit(
            "add unit tests for parser",
            files=["tests/test_parser.py", "tests/conftest.py"],
        )

        category = categorize_commit(commit)

        assert category == CommitCategory.TEST_CHANGE

    def test_categorize_documentation(self):
        """Commits touching only .md files categorized as DOCUMENTATION."""
        commit = self._make_commit(
            "docs: update README",
            files=["README.md", "docs/guide.md"],
        )

        category = categorize_commit(commit)

        assert category == CommitCategory.DOCUMENTATION

    def test_categorize_feature(self):
        """Commits with 'feat' or 'add' categorized as FEATURE."""
        commit = self._make_commit("feat: implement user authentication")

        category = categorize_commit(commit)

        assert category == CommitCategory.FEATURE

    def test_categorize_feature_with_add(self):
        """Commits starting with 'add' categorized as FEATURE."""
        commit = self._make_commit("add: new API endpoint")

        category = categorize_commit(commit)

        assert category == CommitCategory.FEATURE

    def test_categorize_chore(self):
        """Commits with 'chore' categorized as CHORE."""
        commit = self._make_commit("chore: bump dependencies")

        category = categorize_commit(commit)

        assert category == CommitCategory.CHORE

    def test_categorize_mixed_files_uses_message(self):
        """When files are mixed, uses message to determine category."""
        commit = self._make_commit(
            "fix: handle edge case in parser",
            files=["src/parser.py", "tests/test_parser.py"],
        )

        category = categorize_commit(commit)

        # Message says fix, so BUG_FIX even with mixed files
        assert category == CommitCategory.BUG_FIX

    def test_categorize_unknown(self):
        """Commits with unclear intent categorized as OTHER."""
        commit = self._make_commit("update stuff", files=["src/main.py"])

        category = categorize_commit(commit)

        assert category == CommitCategory.OTHER
