"""
Data models for auto-approval system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApprovalResult:
    """
    Result from an auto-approval check.

    Attributes:
        approved: Whether the item was auto-approved.
        reason: Human-readable explanation of the decision.
        confidence: Confidence level of the approval (0.0-1.0).
    """
    approved: bool
    reason: str
    confidence: float = 0.0
