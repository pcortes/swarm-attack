"""
GitHub Issue Context Manager for Feature Swarm.

This module manages context propagation between GitHub issues:
1. Adds implementation summaries to completed issues
2. Propagates context to dependent issues

This is a key component of schema drift prevention - by adding summaries
to GitHub issues, we ensure that:
- The coder sees what classes exist (in the issue body it's implementing)
- The context is human-debuggable (can read GitHub issues to see what agent knew)
- The context persists naturally (no separate state file to corrupt)
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.planning.dependency_graph import DependencyGraph


class IssueContextManager:
    """
    Manages context propagation between GitHub issues.

    After an issue is completed, this manager:
    1. Adds an "Implementation Summary" section to the completed issue
    2. Adds "Context from Dependencies" sections to all dependent issues

    This ensures that when the coder agent picks up a dependent issue,
    it sees the context from all issues it depends on directly in the
    issue body (which is already injected into the coder prompt).
    """

    # Section markers for finding/replacing context blocks
    SUMMARY_MARKER_START = "<!-- SWARM:IMPLEMENTATION_SUMMARY:START -->"
    SUMMARY_MARKER_END = "<!-- SWARM:IMPLEMENTATION_SUMMARY:END -->"
    CONTEXT_MARKER_START = "<!-- SWARM:DEPENDENCY_CONTEXT:START -->"
    CONTEXT_MARKER_END = "<!-- SWARM:DEPENDENCY_CONTEXT:END -->"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the issue context manager.

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
            log_data = {"component": "issue_context"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _check_gh_available(self) -> bool:
        """
        Check if gh CLI is available and authenticated.

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
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._gh_available = False

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

    def _get_issue_body(self, issue_number: int) -> Optional[str]:
        """
        Get the current body of a GitHub issue.

        Args:
            issue_number: The GitHub issue number.

        Returns:
            Issue body string, or None if failed.
        """
        success, stdout, _ = self._run_gh_command([
            "issue", "view", str(issue_number), "--json", "body", "-q", ".body"
        ])

        if success:
            return stdout.strip()
        return None

    def _update_issue_body(self, issue_number: int, new_body: str) -> bool:
        """
        Update the body of a GitHub issue.

        Args:
            issue_number: The GitHub issue number.
            new_body: The new body content.

        Returns:
            True if update was successful.
        """
        success, _, stderr = self._run_gh_command([
            "issue", "edit", str(issue_number), "--body", new_body
        ])

        if not success:
            self._log("issue_body_update_failed", {
                "issue_number": issue_number,
                "error": stderr[:200],
            }, level="warning")

        return success

    def _insert_or_replace_section(
        self,
        body: str,
        section_content: str,
        start_marker: str,
        end_marker: str,
    ) -> str:
        """
        Insert or replace a marked section in the issue body.

        If the markers exist, replaces content between them.
        If not, appends the section to the end.

        Args:
            body: Current issue body.
            section_content: Content to insert.
            start_marker: HTML comment marking section start.
            end_marker: HTML comment marking section end.

        Returns:
            Updated body with section inserted/replaced.
        """
        full_section = f"{start_marker}\n{section_content}\n{end_marker}"

        if start_marker in body and end_marker in body:
            # Replace existing section
            start_idx = body.find(start_marker)
            end_idx = body.find(end_marker) + len(end_marker)
            return body[:start_idx] + full_section + body[end_idx:]
        else:
            # Append new section
            return body.strip() + "\n\n---\n\n" + full_section

    def add_summary_to_issue(
        self,
        issue_number: int,
        summary_markdown: str,
    ) -> bool:
        """
        Add implementation summary to a completed issue.

        Adds a collapsible "Implementation Summary" section to the issue body.
        If the section already exists, it's replaced.

        Args:
            issue_number: The GitHub issue number.
            summary_markdown: Formatted markdown summary from SummarizerAgent.

        Returns:
            True if summary was added successfully.
        """
        self._log("adding_summary_to_issue", {"issue_number": issue_number})

        # Get current body
        current_body = self._get_issue_body(issue_number)
        if current_body is None:
            self._log("get_issue_body_failed", {
                "issue_number": issue_number,
            }, level="warning")
            return False

        # Format summary in collapsible section
        section_content = f"""<details>
<summary><strong>Implementation Summary</strong> (Auto-generated by swarm-attack)</summary>

{summary_markdown}

</details>"""

        # Insert or replace
        new_body = self._insert_or_replace_section(
            current_body,
            section_content,
            self.SUMMARY_MARKER_START,
            self.SUMMARY_MARKER_END,
        )

        # Update issue
        success = self._update_issue_body(issue_number, new_body)

        if success:
            self._log("summary_added_to_issue", {"issue_number": issue_number})

        return success

    def propagate_context_to_dependents(
        self,
        completed_issue: int,
        dependent_issues: list[int],
        context_markdown: str,
    ) -> dict[int, bool]:
        """
        Propagate context from completed issue to all dependent issues.

        Adds a "Context from Dependencies" section to each dependent issue.
        If multiple dependencies complete, their contexts are accumulated.

        Args:
            completed_issue: Issue number that was just completed.
            dependent_issues: List of issue numbers that depend on this one.
            context_markdown: Compact context from SummarizerAgent.

        Returns:
            Dict mapping issue_number -> success boolean.
        """
        results: dict[int, bool] = {}

        self._log("propagating_context", {
            "completed_issue": completed_issue,
            "dependent_count": len(dependent_issues),
        })

        for dep_issue in dependent_issues:
            success = self._add_dependency_context(
                dep_issue, completed_issue, context_markdown
            )
            results[dep_issue] = success

        success_count = sum(1 for s in results.values() if s)
        self._log("context_propagation_complete", {
            "completed_issue": completed_issue,
            "success_count": success_count,
            "total_count": len(dependent_issues),
        })

        return results

    def _add_dependency_context(
        self,
        issue_number: int,
        source_issue: int,
        context_markdown: str,
    ) -> bool:
        """
        Add dependency context to a single issue.

        Args:
            issue_number: Issue to update.
            source_issue: Issue this context is from.
            context_markdown: Context to add.

        Returns:
            True if successful.
        """
        # Get current body
        current_body = self._get_issue_body(issue_number)
        if current_body is None:
            return False

        # Build context section
        # Use unique marker per source issue to allow multiple dependencies
        source_marker_start = f"<!-- SWARM:DEP:{source_issue}:START -->"
        source_marker_end = f"<!-- SWARM:DEP:{source_issue}:END -->"

        section_content = f"""<details>
<summary><strong>Context from Issue #{source_issue}</strong> (Auto-generated)</summary>

{context_markdown}

**DO NOT recreate classes defined above. Import and use them.**

</details>"""

        # Insert this dependency's context
        if source_marker_start in current_body:
            # Replace existing context for this dependency
            new_body = self._insert_or_replace_section(
                current_body,
                section_content,
                source_marker_start,
                source_marker_end,
            )
        else:
            # Add new dependency context
            # Find the main context section or create it
            if self.CONTEXT_MARKER_START in current_body:
                # Add within existing context section
                marker_end_idx = current_body.find(self.CONTEXT_MARKER_END)
                new_body = (
                    current_body[:marker_end_idx]
                    + f"\n\n{source_marker_start}\n{section_content}\n{source_marker_end}\n\n"
                    + current_body[marker_end_idx:]
                )
            else:
                # Create new context section
                context_section = f"""{self.CONTEXT_MARKER_START}

## Context from Dependencies

{source_marker_start}
{section_content}
{source_marker_end}

{self.CONTEXT_MARKER_END}"""

                new_body = current_body.strip() + "\n\n---\n\n" + context_section

        return self._update_issue_body(issue_number, new_body)

    def propagate_to_transitive_dependents(
        self,
        completed_issue: int,
        dependency_graph: DependencyGraph,
        context_markdown: str,
    ) -> dict[int, bool]:
        """
        Propagate context to all transitive dependents using dependency graph.

        Args:
            completed_issue: Issue that was completed.
            dependency_graph: DependencyGraph for computing dependents.
            context_markdown: Context to propagate.

        Returns:
            Dict mapping issue_number -> success boolean.
        """
        dependents = dependency_graph.get_transitive_dependents(completed_issue)
        return self.propagate_context_to_dependents(
            completed_issue,
            list(dependents),
            context_markdown,
        )

    def get_dependency_context_from_issue(
        self,
        issue_number: int,
    ) -> dict[int, str]:
        """
        Extract dependency context sections from an issue body.

        Useful for debugging or verifying what context an issue has.

        Args:
            issue_number: The issue to inspect.

        Returns:
            Dict mapping source_issue_number -> context_markdown.
        """
        import re

        body = self._get_issue_body(issue_number)
        if not body:
            return {}

        contexts: dict[int, str] = {}

        # Find all dependency context blocks
        pattern = r'<!-- SWARM:DEP:(\d+):START -->(.*?)<!-- SWARM:DEP:\1:END -->'
        matches = re.findall(pattern, body, re.DOTALL)

        for source_issue_str, content in matches:
            source_issue = int(source_issue_str)
            contexts[source_issue] = content.strip()

        return contexts
