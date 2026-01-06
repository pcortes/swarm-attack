"""Data models for static analysis results.

This module contains the core data models used by StaticBugDetector
to report findings and by AutoFixOrchestrator to process them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class StaticBugReport:
    """A single bug report from static analysis.
    
    Attributes:
        source: The tool that detected the bug (pytest, mypy, or ruff)
        file_path: Path to the file containing the bug
        line_number: Line number where the bug was found
        error_code: Error code from the tool
        message: Human-readable description of the bug
        severity: Bug severity level (critical, moderate, or minor)
    """
    source: Literal["pytest", "mypy", "ruff"]
    file_path: str
    line_number: int
    error_code: str
    message: str
    severity: Literal["critical", "moderate", "minor"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StaticBugReport":
        """Create a StaticBugReport from a dictionary.
        
        Args:
            data: Dictionary containing bug report fields
            
        Returns:
            StaticBugReport instance
        """
        return cls(
            source=data["source"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            error_code=data["error_code"],
            message=data["message"],
            severity=data["severity"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this bug report to a dictionary.
        
        Returns:
            Dictionary containing all bug report fields
        """
        return {
            "source": self.source,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class StaticAnalysisResult:
    """Results from running static analysis tools.
    
    Attributes:
        bugs: List of bug reports found
        tools_run: List of tools that were successfully run
        tools_skipped: List of tools that were skipped (not installed)
    """
    bugs: list[StaticBugReport]
    tools_run: list[str]
    tools_skipped: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StaticAnalysisResult":
        """Create a StaticAnalysisResult from a dictionary.
        
        Args:
            data: Dictionary containing analysis result fields
            
        Returns:
            StaticAnalysisResult instance
        """
        bugs = [StaticBugReport.from_dict(bug) for bug in data.get("bugs", [])]
        return cls(
            bugs=bugs,
            tools_run=data.get("tools_run", []),
            tools_skipped=data.get("tools_skipped", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this analysis result to a dictionary.
        
        Returns:
            Dictionary containing all result fields
        """
        return {
            "bugs": [bug.to_dict() for bug in self.bugs],
            "tools_run": self.tools_run,
            "tools_skipped": self.tools_skipped,
        }