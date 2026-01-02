"""Code quality analysis module for detecting code smells, SOLID violations, and LLM issues."""

from .models import (
    # Enums
    Severity,
    Priority,
    Category,
    Verdict,
    IssueType,
    CriticRecommendation,
    # Finding
    Finding,
    # AnalysisResult
    AnalysisResult,
    # CriticReview
    CriticIssue,
    CriticReview,
    # TDD Plan
    TDDPhase,
    TDDPlan,
    # ModeratorDecision
    ApprovedFinding,
    RejectedFinding,
    TechDebtItem,
    ModeratorDecision,
    # RetryContext
    ValidatedFinding,
    RejectedHistoricalFinding,
    TechDebtEntry,
    IterationHistory,
    RetryContext,
)
from .analyzer import CodeQualityAnalyzer
from .llm_auditor import LLMAuditor
from .refactor_suggester import RefactorSuggester
from .smell_detector import SmellDetector
from .solid_checker import SOLIDChecker
from .tdd_generator import TDDGenerator
from .dispatcher import CodeQualityDispatcher

__all__ = [
    # Enums
    "Severity",
    "Priority",
    "Category",
    "Verdict",
    "IssueType",
    "CriticRecommendation",
    # Finding
    "Finding",
    # AnalysisResult
    "AnalysisResult",
    # CriticReview
    "CriticIssue",
    "CriticReview",
    # TDD Plan
    "TDDPhase",
    "TDDPlan",
    # ModeratorDecision
    "ApprovedFinding",
    "RejectedFinding",
    "TechDebtItem",
    "ModeratorDecision",
    # RetryContext
    "ValidatedFinding",
    "RejectedHistoricalFinding",
    "TechDebtEntry",
    "IterationHistory",
    "RetryContext",
    # Detectors
    "SmellDetector",
    "SOLIDChecker",
    "LLMAuditor",
    # Suggester
    "RefactorSuggester",
    # TDD Generator
    "TDDGenerator",
    # Analyzer
    "CodeQualityAnalyzer",
    # Dispatcher
    "CodeQualityDispatcher",
]
