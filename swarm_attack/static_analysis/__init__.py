"""Static analysis module for bug detection.

This module provides tools for detecting bugs through static analysis
including pytest test failures, mypy type errors, and ruff linting issues.
"""

from .detector import StaticBugDetector
from .models import StaticAnalysisResult, StaticBugReport

__all__ = [
    "StaticBugDetector",
    "StaticBugReport",
    "StaticAnalysisResult",
]
