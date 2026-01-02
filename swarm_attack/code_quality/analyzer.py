"""Code quality analysis engine - the main orchestrator.

Orchestrates all detection modules (SmellDetector, SOLIDChecker, LLMAuditor)
and produces unified analysis results with prioritized findings.

Based on the Code Quality spec:
- Timing budget: 90 seconds for analyst phase
- Decision points: APPROVE, REFACTOR, ESCALATE
- Priority classification: FIX_NOW, FIX_LATER, IGNORE
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from .llm_auditor import LLMAuditor
from .models import (
    AnalysisResult,
    Category,
    Finding,
    Priority,
    Severity,
    Verdict,
)
from .smell_detector import SmellDetector
from .solid_checker import SOLIDChecker


class CodeQualityAnalyzer:
    """Orchestrates all detection modules and produces unified analysis.

    This is the main entry point for code quality analysis. It coordinates:
    - SmellDetector: Code smell detection (long methods, large classes, etc.)
    - SOLIDChecker: SOLID principle violation detection
    - LLMAuditor: LLM-specific issue detection (hallucinations, incomplete code)

    Attributes:
        TIMING_BUDGET_SECONDS: Maximum time allowed for analysis (90 seconds).
        smell_detector: Instance of SmellDetector for code smell detection.
        solid_checker: Instance of SOLIDChecker for SOLID violation detection.
        llm_auditor: Instance of LLMAuditor for LLM issue detection.
    """

    TIMING_BUDGET_SECONDS = 90  # From spec: analyst phase has 90 seconds

    def __init__(self) -> None:
        """Initialize the analyzer with all detection modules."""
        self.smell_detector = SmellDetector()
        self.solid_checker = SOLIDChecker()
        self.llm_auditor = LLMAuditor()

    def analyze_files(self, file_paths: list[Union[str, Path]]) -> AnalysisResult:
        """Analyze multiple files and produce unified result.

        Args:
            file_paths: List of paths to Python files to analyze.

        Returns:
            AnalysisResult containing all findings, counts, and recommendation.
        """
        start_time = time.time()

        # Normalize paths
        paths = [Path(p) for p in file_paths]

        # Collect all findings
        all_findings: list[Finding] = []
        files_analyzed: list[str] = []

        for path in paths:
            if not self.check_timing_budget(start_time):
                break  # Exit early if timing budget exceeded

            findings = self.analyze_file(path)
            if findings:
                all_findings.extend(findings)
            files_analyzed.append(str(path))

        # Prioritize findings
        prioritized_findings = self.prioritize_findings(all_findings)

        # Determine verdict
        verdict_str = self.determine_verdict(prioritized_findings)
        verdict = Verdict(verdict_str)

        # Count severities
        critical_count = sum(1 for f in prioritized_findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in prioritized_findings if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in prioritized_findings if f.severity == Severity.MEDIUM)
        low_count = sum(1 for f in prioritized_findings if f.severity == Severity.LOW)

        # Count priorities
        fix_now_count = sum(1 for f in prioritized_findings if f.priority == Priority.FIX_NOW)
        fix_later_count = sum(1 for f in prioritized_findings if f.priority == Priority.FIX_LATER)
        ignore_count = sum(1 for f in prioritized_findings if f.priority == Priority.IGNORE)

        # Generate analysis ID
        now = datetime.now()
        analysis_id = f"cqa-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

        # Generate refactor summary
        refactor_summary = self._generate_refactor_summary(prioritized_findings, verdict)

        return AnalysisResult(
            analysis_id=analysis_id,
            files_analyzed=files_analyzed,
            total_issues=len(prioritized_findings),
            critical=critical_count,
            high=high_count,
            medium=medium_count,
            low=low_count,
            fix_now=fix_now_count,
            fix_later=fix_later_count,
            ignore=ignore_count,
            findings=prioritized_findings,
            recommendation=verdict,
            refactor_summary=refactor_summary,
        )

    def analyze_file(self, file_path: Union[str, Path]) -> list[Finding]:
        """Analyze single file with all detectors.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            List of Finding objects from all detectors.
        """
        path = Path(file_path)

        # Handle non-existent files
        if not path.exists():
            return []

        # Handle non-Python files
        if path.suffix != ".py":
            return []

        findings: list[Finding] = []

        # Run all detectors
        findings.extend(self.smell_detector.analyze_file(path))
        findings.extend(self.solid_checker.analyze_file(path))
        findings.extend(self.llm_auditor.analyze_file(path))

        return findings

    def prioritize_findings(self, findings: list[Finding]) -> list[Finding]:
        """Classify findings as fix_now, fix_later, or ignore.

        Priority classification rules (from spec):
        - FIX_NOW: Critical or high severity, confidence > 0.8
        - FIX_LATER: Medium severity, or high with lower confidence
        - IGNORE: Low severity, or false positive indicators

        Args:
            findings: List of findings to prioritize.

        Returns:
            List of findings with updated priority values.
        """
        prioritized: list[Finding] = []

        for finding in findings:
            # Calculate confidence if not already set
            confidence = self.calculate_confidence(finding)

            # Apply priority classification rules
            if finding.severity == Severity.CRITICAL and confidence > 0.8:
                new_priority = Priority.FIX_NOW
            elif finding.severity == Severity.HIGH and confidence > 0.8:
                new_priority = Priority.FIX_NOW
            elif finding.severity == Severity.HIGH:
                new_priority = Priority.FIX_LATER
            elif finding.severity == Severity.MEDIUM:
                new_priority = Priority.FIX_LATER
            else:  # LOW severity
                new_priority = Priority.IGNORE

            # Create a new finding with updated priority
            # Using dataclass replace would be cleaner, but we'll modify directly
            prioritized_finding = Finding(
                finding_id=finding.finding_id,
                severity=finding.severity,
                category=finding.category,
                file=finding.file,
                line=finding.line,
                title=finding.title,
                description=finding.description,
                expert=finding.expert,
                code_snippet=finding.code_snippet,
                refactoring_pattern=finding.refactoring_pattern,
                refactoring_steps=finding.refactoring_steps,
                priority=new_priority,
                effort_estimate=finding.effort_estimate,
                confidence=confidence,
            )
            prioritized.append(prioritized_finding)

        return prioritized

    def calculate_confidence(self, finding: Finding) -> float:
        """Calculate confidence score for a finding.

        LLM hallucinations have high confidence (detected reliably by import checks).
        Code smells have moderate confidence (heuristic-based).
        SOLID violations have lower confidence (more subjective).

        Args:
            finding: The finding to calculate confidence for.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # If confidence is already set, use it
        if finding.confidence is not None:
            return min(max(finding.confidence, 0.0), 1.0)

        # Default confidence by category
        if finding.category == Category.LLM_HALLUCINATION:
            return 0.95  # Very reliable detection
        elif finding.category == Category.ERROR_HANDLING:
            return 0.90  # AST-based, reliable
        elif finding.category == Category.CODE_SMELL:
            return 0.85  # Metrics-based, fairly reliable
        elif finding.category == Category.SOLID:
            return 0.75  # More heuristic-based
        elif finding.category == Category.INCOMPLETE:
            return 0.80  # Pattern matching on TODO/FIXME
        else:
            return 0.80  # Default

    def check_timing_budget(self, start_time: float) -> bool:
        """Check if we're within timing budget.

        Args:
            start_time: The timestamp when analysis started.

        Returns:
            True if within budget, False if exceeded.
        """
        return (time.time() - start_time) < self.TIMING_BUDGET_SECONDS

    def determine_verdict(
        self,
        findings: list[Finding],
        retry_iteration: int = 1,
    ) -> str:
        """Determine APPROVE, REFACTOR, or ESCALATE based on findings.

        Verdict determination rules (from spec):
        - APPROVE: No fix_now findings
        - REFACTOR: Has fix_now findings but addressable
        - ESCALATE: Major architectural issues or 3+ failed retry iterations

        Args:
            findings: List of prioritized findings.
            retry_iteration: Current retry iteration (1-3, escalate after 3).

        Returns:
            Verdict string: "APPROVE", "REFACTOR", or "ESCALATE".
        """
        if not findings:
            return Verdict.APPROVE.value

        # Count fix_now findings
        fix_now_findings = [f for f in findings if f.priority == Priority.FIX_NOW]

        if not fix_now_findings:
            return Verdict.APPROVE.value

        # Check for escalation conditions
        # 1. Third retry iteration
        if retry_iteration >= 3:
            return Verdict.ESCALATE.value

        # 2. Multiple critical SOLID violations (architectural issues)
        critical_solid = [
            f
            for f in fix_now_findings
            if f.severity == Severity.CRITICAL and f.category == Category.SOLID
        ]
        if len(critical_solid) >= 3:
            return Verdict.ESCALATE.value

        # Has addressable fix_now findings
        return Verdict.REFACTOR.value

    def _generate_refactor_summary(
        self,
        findings: list[Finding],
        verdict: Verdict,
    ) -> str:
        """Generate a brief summary of what needs fixing.

        Args:
            findings: List of prioritized findings.
            verdict: The determined verdict.

        Returns:
            A brief description of what needs fixing.
        """
        if not findings:
            return "No code quality issues detected."

        if verdict == Verdict.APPROVE:
            return f"Found {len(findings)} minor issues (all fix_later or ignore). Code quality acceptable."

        fix_now = [f for f in findings if f.priority == Priority.FIX_NOW]

        if verdict == Verdict.ESCALATE:
            return (
                f"Found {len(fix_now)} critical issues requiring human review. "
                f"Major architectural concerns detected."
            )

        # REFACTOR case
        categories = set(f.category.value for f in fix_now)
        return (
            f"Found {len(fix_now)} issues requiring immediate attention "
            f"({', '.join(categories)}). See TDD plans for fixes."
        )
