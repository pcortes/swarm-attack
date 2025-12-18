"""
GitHub Synchronization for Feature Swarm.

This module provides GitHub label and comment management:
- Updates issue labels based on swarm state transitions
- Posts rich status comments when issues are blocked or completed
- Creates swarm:* labels if they don't exist
- Gracefully handles missing gh CLI or authentication errors
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class GitHubSync:
    """
    Synchronizes swarm state to GitHub issues.

    Updates labels and posts comments based on implementation progress.
    All operations are optional - failures are logged but don't block work.
    """

    # Label mappings for swarm states
    LABELS = {
        "ready": "swarm:ready",
        "in_progress": "swarm:in-progress",
        "blocked": "swarm:blocked",
        "done": "swarm:done",
    }

    # Label colors (for creation)
    LABEL_COLORS = {
        "swarm:ready": "0E8A16",      # Green
        "swarm:in-progress": "FBCA04",  # Yellow
        "swarm:blocked": "D93F0B",     # Red
        "swarm:done": "1D76DB",        # Blue
    }

    # Label descriptions
    LABEL_DESCRIPTIONS = {
        "swarm:ready": "Issue ready for swarm implementation",
        "swarm:in-progress": "Swarm actively working on this issue",
        "swarm:blocked": "Implementation blocked - needs attention",
        "swarm:done": "Successfully implemented by swarm",
    }

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize GitHub sync.

        Args:
            config: SwarmConfig with repo_root.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self._gh_available: Optional[bool] = None

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "github_sync"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _check_gh_available(self) -> bool:
        """
        Check if gh CLI is available and authenticated.

        Results are cached after first check.

        Returns:
            True if gh CLI is available and authenticated.
        """
        if self._gh_available is not None:
            return self._gh_available

        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._gh_available = result.returncode == 0
            if not self._gh_available:
                self._log("gh_auth_failed", {
                    "stderr": result.stderr[:200] if result.stderr else "",
                }, level="warning")
        except FileNotFoundError:
            self._gh_available = False
            self._log("gh_not_found", level="warning")
        except subprocess.TimeoutExpired:
            self._gh_available = False
            self._log("gh_timeout", level="warning")

        return self._gh_available

    def _run_gh_command(
        self,
        args: list[str],
        timeout: int = 30,
    ) -> tuple[bool, str, str]:
        """
        Run a gh CLI command.

        Args:
            args: Arguments to pass to gh CLI.
            timeout: Command timeout in seconds.

        Returns:
            Tuple of (success, stdout, stderr).
        """
        if not self._check_gh_available():
            return False, "", "gh CLI not available"

        try:
            result = subprocess.run(
                ["gh"] + args,
                cwd=str(self.config.repo_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def ensure_labels_exist(self) -> bool:
        """
        Create swarm:* labels if they don't exist.

        Should be called once per repository to set up labels.

        Returns:
            True if all labels exist/were created, False on error.
        """
        if not self._check_gh_available():
            return False

        all_success = True
        for label_name, color in self.LABEL_COLORS.items():
            description = self.LABEL_DESCRIPTIONS.get(label_name, "")

            # Try to create label (will fail if exists, which is fine)
            success, _, stderr = self._run_gh_command([
                "label", "create", label_name,
                "--color", color,
                "--description", description,
                "--force",  # Update if exists
            ])

            if not success and "already exists" not in stderr.lower():
                self._log("label_create_failed", {
                    "label": label_name,
                    "error": stderr[:200],
                }, level="warning")
                all_success = False

        return all_success

    def _remove_swarm_labels(self, issue_number: int) -> bool:
        """
        Remove all swarm:* labels from an issue.

        Args:
            issue_number: The GitHub issue number.

        Returns:
            True if successful (or no labels to remove).
        """
        for label in self.LABELS.values():
            # Remove label (ignore errors - label might not be present)
            self._run_gh_command([
                "issue", "edit", str(issue_number),
                "--remove-label", label,
            ])
        return True

    def update_issue_state(
        self,
        issue_number: int,
        state: str,
    ) -> bool:
        """
        Update GitHub issue label based on state.

        Removes existing swarm:* labels and adds the new one.

        Args:
            issue_number: The GitHub issue number.
            state: State key ("ready", "in_progress", "blocked", "done").

        Returns:
            True if label was updated successfully.
        """
        if state not in self.LABELS:
            self._log("invalid_state", {
                "issue_number": issue_number,
                "state": state,
            }, level="warning")
            return False

        label = self.LABELS[state]

        # Remove old swarm labels first
        self._remove_swarm_labels(issue_number)

        # Add new label
        success, _, stderr = self._run_gh_command([
            "issue", "edit", str(issue_number),
            "--add-label", label,
        ])

        if success:
            self._log("label_updated", {
                "issue_number": issue_number,
                "label": label,
            })
        else:
            self._log("label_update_failed", {
                "issue_number": issue_number,
                "label": label,
                "error": stderr[:200],
            }, level="warning")

        return success

    def post_blocked_comment(
        self,
        issue_number: int,
        reason: str,
        test_output: Optional[str] = None,
        files_modified: Optional[list[str]] = None,
        retry_count: int = 0,
        feature_id: str = "",
    ) -> bool:
        """
        Post a detailed comment when an issue is blocked.

        Args:
            issue_number: The GitHub issue number.
            reason: Why the implementation is blocked.
            test_output: Optional test failure output.
            files_modified: Optional list of files that were modified.
            retry_count: Number of retry attempts made.
            feature_id: Feature ID for recovery command.

        Returns:
            True if comment was posted successfully.
        """
        # Build comment body
        lines = [
            "## :no_entry: Implementation Blocked",
            "",
            f"**Reason:** {reason}",
            "",
        ]

        if retry_count > 0:
            lines.append(f"**Attempts:** {retry_count + 1}")
            lines.append("")

        if test_output:
            # Truncate very long output
            truncated = test_output[:2000] if len(test_output) > 2000 else test_output
            lines.extend([
                "**Test Output:**",
                "```",
                truncated,
                "```",
                "",
            ])

        if files_modified:
            lines.append("**Files Modified:**")
            for f in files_modified[:10]:  # Limit to 10 files
                lines.append(f"- `{f}`")
            if len(files_modified) > 10:
                lines.append(f"- ... and {len(files_modified) - 10} more")
            lines.append("")

        lines.extend([
            "**Next Steps:**",
            "1. Review the error above and fix the root cause",
            f"2. Run `swarm-attack unblock {feature_id} --issue {issue_number}` to retry" if feature_id else "2. Run the swarm again to retry",
            "",
            "---",
            "*:robot: Posted by swarm-attack*",
        ])

        comment_body = "\n".join(lines)

        success, _, stderr = self._run_gh_command([
            "issue", "comment", str(issue_number),
            "--body", comment_body,
        ])

        if success:
            self._log("blocked_comment_posted", {
                "issue_number": issue_number,
            })
        else:
            self._log("blocked_comment_failed", {
                "issue_number": issue_number,
                "error": stderr[:200],
            }, level="warning")

        return success

    def post_done_comment(
        self,
        issue_number: int,
        commit_hash: str,
        files_created: Optional[list[str]] = None,
        files_modified: Optional[list[str]] = None,
        test_count: int = 0,
        completion_summary: Optional[str] = None,
        close_issue: bool = True,
    ) -> bool:
        """
        Post a success comment and optionally close the issue.

        Args:
            issue_number: The GitHub issue number.
            commit_hash: Git commit hash.
            files_created: Optional list of files created.
            files_modified: Optional list of files modified.
            test_count: Number of tests passing.
            completion_summary: Optional semantic summary.
            close_issue: Whether to close the issue.

        Returns:
            True if comment was posted successfully.
        """
        # Build comment body
        lines = [
            "## :white_check_mark: Implementation Complete",
            "",
            f"**Commit:** `{commit_hash[:7] if commit_hash else 'N/A'}`",
            "",
        ]

        if completion_summary:
            lines.extend([
                f"**Summary:** {completion_summary}",
                "",
            ])

        if files_created:
            lines.append("**Files Created:**")
            for f in files_created[:10]:
                lines.append(f"- `{f}`")
            if len(files_created) > 10:
                lines.append(f"- ... and {len(files_created) - 10} more")
            lines.append("")

        if files_modified:
            lines.append("**Files Modified:**")
            for f in files_modified[:10]:
                lines.append(f"- `{f}`")
            if len(files_modified) > 10:
                lines.append(f"- ... and {len(files_modified) - 10} more")
            lines.append("")

        if test_count > 0:
            lines.extend([
                f"**Test Results:** {test_count} test(s) passing",
                "",
            ])

        lines.extend([
            ":rocket: Ready for review!",
            "",
            "---",
            "*:robot: Posted by swarm-attack*",
        ])

        comment_body = "\n".join(lines)

        # Post comment
        success, _, stderr = self._run_gh_command([
            "issue", "comment", str(issue_number),
            "--body", comment_body,
        ])

        if not success:
            self._log("done_comment_failed", {
                "issue_number": issue_number,
                "error": stderr[:200],
            }, level="warning")
            return False

        self._log("done_comment_posted", {
            "issue_number": issue_number,
        })

        # Close issue if requested
        if close_issue:
            close_success, _, close_stderr = self._run_gh_command([
                "issue", "close", str(issue_number),
            ])
            if close_success:
                self._log("issue_closed", {
                    "issue_number": issue_number,
                })
            else:
                self._log("issue_close_failed", {
                    "issue_number": issue_number,
                    "error": close_stderr[:200],
                }, level="warning")

        return success

    def post_in_progress_comment(
        self,
        issue_number: int,
        session_id: str = "",
    ) -> bool:
        """
        Post a comment indicating work has started.

        Args:
            issue_number: The GitHub issue number.
            session_id: Optional session ID for tracking.

        Returns:
            True if comment was posted successfully.
        """
        lines = [
            "## :gear: Implementation Started",
            "",
            "Swarm is now working on this issue.",
            "",
        ]

        if session_id:
            lines.append(f"**Session:** `{session_id}`")
            lines.append("")

        lines.extend([
            "---",
            "*:robot: Posted by swarm-attack*",
        ])

        comment_body = "\n".join(lines)

        success, _, stderr = self._run_gh_command([
            "issue", "comment", str(issue_number),
            "--body", comment_body,
        ])

        if success:
            self._log("in_progress_comment_posted", {
                "issue_number": issue_number,
            })
        else:
            self._log("in_progress_comment_failed", {
                "issue_number": issue_number,
                "error": stderr[:200],
            }, level="warning")

        return success
