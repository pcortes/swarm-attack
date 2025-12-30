"""
Human override functions for auto-approval system.

These functions provide manual control over the auto-approval system:
- veto_feature: Revoke an auto-approved feature
- veto_bug: Revoke an auto-approved bug fix
- enable_manual_mode: Disable auto-approval for a feature
- enable_auto_mode: Re-enable auto-approval for a feature
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    pass


class StateStoreProtocol(Protocol):
    """Protocol for state store operations."""
    def veto_approval(self, feature_id: str, reason: str) -> None: ...
    def set_manual_mode(self, feature_id: str, enabled: bool) -> None: ...


class BugStoreProtocol(Protocol):
    """Protocol for bug store operations."""
    def veto_approval(self, bug_id: str, reason: str) -> None: ...


def veto_feature(
    state_store: StateStoreProtocol,
    feature_id: str,
    reason: str,
) -> None:
    """
    Veto an auto-approved feature.

    This reverts the feature from SPEC_APPROVED back to SPEC_NEEDS_APPROVAL,
    requiring manual approval.

    Args:
        state_store: State store for feature state.
        feature_id: The feature identifier.
        reason: Human-provided reason for the veto.
    """
    state_store.veto_approval(feature_id, reason)


def veto_bug(
    bug_store: BugStoreProtocol,
    bug_id: str,
    reason: str,
) -> None:
    """
    Veto an auto-approved bug fix.

    This reverts the bug from APPROVED back to PLANNED,
    requiring manual approval.

    Args:
        bug_store: Bug store for bug state.
        bug_id: The bug identifier.
        reason: Human-provided reason for the veto.
    """
    bug_store.veto_approval(bug_id, reason)


def enable_manual_mode(
    state_store: StateStoreProtocol,
    feature_id: str,
) -> None:
    """
    Enable manual approval mode for a feature.

    When enabled, the feature will not be auto-approved even if
    quality thresholds are met. Requires explicit manual approval.

    Args:
        state_store: State store for feature state.
        feature_id: The feature identifier.
    """
    state_store.set_manual_mode(feature_id, True)


def enable_auto_mode(
    state_store: StateStoreProtocol,
    feature_id: str,
) -> None:
    """
    Re-enable auto-approval mode for a feature.

    This allows the feature to be auto-approved when quality thresholds
    are met.

    Args:
        state_store: State store for feature state.
        feature_id: The feature identifier.
    """
    state_store.set_manual_mode(feature_id, False)
