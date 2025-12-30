"""
Issue Auto-Greenlighter for Feature Swarm.

Automatically greenlights issues when complexity gate passes for all issues.

Replaces manual `swarm-attack greenlight` command when conditions are met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Any

from swarm_attack.auto_approval.models import ApprovalResult

if TYPE_CHECKING:
    from swarm_attack.event_logger import EventLogger


class TaskProtocol(Protocol):
    """Protocol for task/issue objects."""
    complexity_gate_passed: bool
    has_interface_contract: bool
    dependencies: list[int]
    issue_number: int


class RunStateProtocol(Protocol):
    """Protocol for run state objects."""
    tasks: list[Any]


class StateStoreProtocol(Protocol):
    """Protocol for state store operations."""
    def get_run_state(self, feature_id: str) -> RunStateProtocol | None: ...
    def greenlight_feature(self, feature_id: str) -> None: ...
    def is_manual_mode(self, feature_id: str) -> bool: ...


class IssueAutoGreenlighter:
    """
    Replace manual `swarm-attack greenlight` command.

    Auto-greenlights when:
    - All issues pass complexity gate
    - All issues have interface contracts
    - No circular dependencies
    - Manual mode is not enabled
    """

    def __init__(
        self,
        state_store: StateStoreProtocol,
        event_logger: "EventLogger",
    ) -> None:
        """
        Initialize the issue auto-greenlighter.

        Args:
            state_store: State store for accessing feature state.
            event_logger: Event logger for audit trail.
        """
        self._state_store = state_store
        self._logger = event_logger

    def should_auto_greenlight(self, feature_id: str) -> tuple[bool, str]:
        """
        Check if feature should be auto-greenlit for implementation.

        Args:
            feature_id: The feature identifier.

        Returns:
            Tuple of (should_greenlight, reason).
        """
        run_state = self._state_store.get_run_state(feature_id)
        if run_state is None:
            return False, "Feature state not found"

        issues = run_state.tasks or []

        if not issues:
            return False, "No issues to greenlight"

        # All issues must pass complexity gate
        failed = [i for i in issues if not getattr(i, "complexity_gate_passed", False)]
        if failed:
            return False, f"{len(failed)} issues failed complexity gate"

        # No circular dependencies
        if self._has_circular_deps(issues):
            return False, "Circular dependency detected"

        # All issues must have required fields
        incomplete = [i for i in issues if not getattr(i, "has_interface_contract", False)]
        if incomplete:
            return False, f"{len(incomplete)} issues missing interface contract"

        return True, "Auto-greenlit: all issues validated"

    def _has_circular_deps(self, issues: list[Any]) -> bool:
        """
        Check for circular dependencies in issues.

        Uses simple cycle detection via DFS.
        """
        # Build adjacency map
        issue_numbers = {getattr(i, "issue_number", i) for i in issues}
        deps: dict[int, list[int]] = {}
        for issue in issues:
            issue_num = getattr(issue, "issue_number", issue)
            issue_deps = getattr(issue, "dependencies", []) or []
            deps[issue_num] = [d for d in issue_deps if d in issue_numbers]

        # DFS cycle detection
        visited: set[int] = set()
        rec_stack: set[int] = set()

        def has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in deps.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for issue_num in issue_numbers:
            if issue_num not in visited:
                if has_cycle(issue_num):
                    return True

        return False

    def _is_manual_mode(self, feature_id: str) -> bool:
        """Check if manual mode is enabled for this feature."""
        return self._state_store.is_manual_mode(feature_id)

    def auto_greenlight_if_ready(self, feature_id: str) -> ApprovalResult:
        """
        Check and auto-greenlight if conditions met.

        Args:
            feature_id: The feature identifier.

        Returns:
            ApprovalResult with greenlight status and reason.
        """
        # Check for manual mode override first
        if self._is_manual_mode(feature_id):
            return ApprovalResult(approved=False, reason="Manual mode enabled")

        should, reason = self.should_auto_greenlight(feature_id)

        if not should:
            return ApprovalResult(approved=False, reason=reason)

        self._state_store.greenlight_feature(feature_id)
        self._logger.log_auto_approval("greenlight", feature_id, reason)

        return ApprovalResult(approved=True, reason=reason)
