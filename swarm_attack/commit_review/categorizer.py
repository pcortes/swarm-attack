"""Commit categorization functionality."""

import re
from swarm_attack.commit_review.models import CommitInfo, CommitCategory


def categorize_commit(commit: CommitInfo) -> CommitCategory:
    """Categorize a commit based on its message and changed files.

    Priority order:
    1. Check message prefix (fix:, feat:, refactor:, etc.)
    2. Check if all files are tests or docs
    3. Default to OTHER

    Args:
        commit: CommitInfo to categorize

    Returns:
        CommitCategory enum value
    """
    message_lower = commit.message.lower()

    # Check message prefixes first
    if _is_bug_fix(message_lower):
        return CommitCategory.BUG_FIX

    if _is_feature(message_lower):
        return CommitCategory.FEATURE

    if _is_refactor(message_lower):
        return CommitCategory.REFACTOR

    if _is_chore(message_lower):
        return CommitCategory.CHORE

    # Check file patterns if no clear message prefix
    if commit.changed_files:
        if _all_test_files(commit.changed_files):
            return CommitCategory.TEST_CHANGE

        if _all_doc_files(commit.changed_files):
            return CommitCategory.DOCUMENTATION

    # Check message for test/doc keywords
    if _is_test_change(message_lower):
        return CommitCategory.TEST_CHANGE

    if _is_documentation(message_lower):
        return CommitCategory.DOCUMENTATION

    return CommitCategory.OTHER


def _is_bug_fix(message: str) -> bool:
    """Check if message indicates a bug fix."""
    patterns = [
        r"^fix[:\(]",
        r"^bugfix[:\(]",
        r"^hotfix[:\(]",
        r"\bfix\b.*\bbug\b",
        r"\bfixes?\s+#\d+",
    ]
    return any(re.search(p, message) for p in patterns)


def _is_feature(message: str) -> bool:
    """Check if message indicates a new feature."""
    patterns = [
        r"^feat[:\(]",
        r"^feature[:\(]",
        r"^add[:\(]",
        r"^new[:\(]",
        r"^implement[:\(]",
    ]
    return any(re.search(p, message) for p in patterns)


def _is_refactor(message: str) -> bool:
    """Check if message indicates refactoring."""
    patterns = [
        r"^refactor[:\(]",
        r"^cleanup[:\(]",
        r"^clean[:\(]",
        r"^restructure[:\(]",
    ]
    return any(re.search(p, message) for p in patterns)


def _is_chore(message: str) -> bool:
    """Check if message indicates a chore."""
    patterns = [
        r"^chore[:\(]",
        r"^build[:\(]",
        r"^ci[:\(]",
        r"^deps[:\(]",
        r"^bump[:\(]",
    ]
    return any(re.search(p, message) for p in patterns)


def _is_test_change(message: str) -> bool:
    """Check if message indicates test changes."""
    patterns = [
        r"^test[:\(]",
        r"^tests[:\(]",
        r"\badd\s+tests?\b",
        r"\bunit\s+tests?\b",
    ]
    return any(re.search(p, message) for p in patterns)


def _is_documentation(message: str) -> bool:
    """Check if message indicates documentation."""
    patterns = [
        r"^docs?[:\(]",
        r"^documentation[:\(]",
        r"\breadme\b",
        r"\bdocumentation\b",
    ]
    return any(re.search(p, message) for p in patterns)


def _all_test_files(files: list[str]) -> bool:
    """Check if all files are test files."""
    if not files:
        return False
    return all(
        "test" in f.lower() or f.startswith("tests/") or "/tests/" in f
        for f in files
    )


def _all_doc_files(files: list[str]) -> bool:
    """Check if all files are documentation files."""
    if not files:
        return False
    doc_extensions = {".md", ".rst", ".txt", ".adoc"}
    return all(
        any(f.lower().endswith(ext) for ext in doc_extensions)
        for f in files
    )
