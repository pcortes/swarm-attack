"""Data models for static analysis results.

These models are used by StaticBugDetector to report findings
and by AutoFixOrchestrator to process them.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal


@dataclass
class StaticBugReport:
    """Report for a single bug detected by static analysis.

    Attributes:
        source: The tool that detected the bug ("pytest", "mypy", or "ruff")
        file_path: Path to the file containing the bug
        line_number: Line number where the bug was found
        error_code: Tool-specific error code
        message: Human-readable error message
        severity: Bug severity ("critical", "moderate", or "minor")
    """
    source: Literal["pytest", "mypy", "ruff"]
    file_path: str
    line_number: int
    error_code: str
    message: str
    severity: Literal["critical", "moderate", "minor"]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StaticBugReport:
        """Create instance from dictionary.

        Args:
            data: Dictionary with bug report fields

        Returns:
            New StaticBugReport instance
        """
        return cls(
            source=data["source"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            error_code=data["error_code"],
            message=data["message"],
            severity=data["severity"],
        )


@dataclass
class StaticAnalysisResult:
    """Combined results from all static analysis tools.

    Attributes:
        bugs: List of detected bugs
        tools_run: List of tools that were successfully run
        tools_skipped: List of tools that were skipped (not installed)
    """
    bugs: list[StaticBugReport]
    tools_run: list[str]
    tools_skipped: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "bugs": [bug.to_dict() for bug in self.bugs],
            "tools_run": self.tools_run,
            "tools_skipped": self.tools_skipped,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StaticAnalysisResult:
        """Create instance from dictionary.

        Args:
            data: Dictionary with analysis result fields

        Returns:
            New StaticAnalysisResult instance
        """
        return cls(
            bugs=[StaticBugReport.from_dict(b) for b in data.get("bugs", [])],
            tools_run=data.get("tools_run", []),
            tools_skipped=data.get("tools_skipped", []),
        )
