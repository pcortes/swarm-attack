"""Schema validation for persisted state and events.

All persisted data must conform to a schema. Loading validates
and rejects malformed data with specific errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any


class SchemaValidationError(Exception):
    """Raised when data doesn't conform to schema."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Schema validation failed for '{field}': {message}")


@dataclass
class SwarmEvent:
    """Schema for swarm events logged to event log.

    All fields are validated on construction.
    """
    ts: str
    event: str
    feature_id: str
    issue: Optional[int] = None

    # Additional optional fields
    agent: Optional[str] = None
    cost_usd: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Validate all fields on construction."""
        if not self.ts:
            raise SchemaValidationError("ts", "timestamp is required")

        if not self.event:
            raise SchemaValidationError("event", "event type is required")

        if not self.feature_id:
            raise SchemaValidationError("feature_id", "feature_id is required")

        if self.issue is not None:
            if not isinstance(self.issue, int):
                raise SchemaValidationError("issue", "must be an integer", self.issue)
            if self.issue < 1:
                raise SchemaValidationError("issue", "must be >= 1", self.issue)

        if self.cost_usd is not None:
            if not isinstance(self.cost_usd, (int, float)):
                raise SchemaValidationError("cost_usd", "must be a number", self.cost_usd)
            if self.cost_usd < 0:
                raise SchemaValidationError("cost_usd", "cannot be negative", self.cost_usd)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        d = {
            "ts": self.ts,
            "event": self.event,
            "feature_id": self.feature_id,
        }
        if self.issue is not None:
            d["issue"] = self.issue
        if self.agent is not None:
            d["agent"] = self.agent
        if self.cost_usd is not None:
            d["cost_usd"] = self.cost_usd
        if self.success is not None:
            d["success"] = self.success
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SwarmEvent":
        """Deserialize from dictionary, validating schema."""
        return cls(
            ts=data.get("ts", ""),
            event=data.get("event", ""),
            feature_id=data.get("feature_id", ""),
            issue=data.get("issue"),
            agent=data.get("agent"),
            cost_usd=data.get("cost_usd"),
            success=data.get("success"),
            error=data.get("error"),
        )


def validate_event(data: dict) -> SwarmEvent:
    """Validate event data and return typed SwarmEvent.

    Args:
        data: Raw event dictionary

    Returns:
        Validated SwarmEvent

    Raises:
        SchemaValidationError: If validation fails
    """
    return SwarmEvent.from_dict(data)
