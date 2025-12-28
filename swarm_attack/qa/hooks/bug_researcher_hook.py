"""BugResearcherQAHook for bug reproduction validation.

Implements spec section 3: Pipeline Integration - Bug Researcher Hook
- QA hook for bug reproduction validation
- Triggers on BUG_REPRODUCTION
- Uses DEEP depth for thorough testing
- Captures evidence for root cause analysis
- Feeds back to bug pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.qa.context_builder import QAContextBuilder
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAFinding,
    QARecommendation,
    QATrigger,
)
from swarm_attack.qa.orchestrator import QAOrchestrator

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class BugHookResult:
    """Result of running the BugResearcherQAHook."""

    bug_id: str = ""
    session_id: Optional[str] = None

    # Bug validation results
    is_reproducible: Optional[bool] = None
    is_inconclusive: bool = False
    findings: list[QAFinding] = field(default_factory=list)

    # Evidence for root cause analysis
    evidence: dict[str, Any] = field(default_factory=dict)
    root_cause_hints: list[str] = field(default_factory=list)

    # Error handling
    error: Optional[str] = None


class BugResearcherQAHook:
    """
    Hook that validates bug reproduction through QA testing.

    This hook uses DEEP testing to validate whether a reported
    bug can be reproduced and gathers evidence for root cause analysis.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the BugResearcherQAHook.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger

        # Create QA components
        self.orchestrator = QAOrchestrator(config, logger)
        self.context_builder = QAContextBuilder(config, logger)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "bug_researcher_qa_hook"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def validate_bug(
        self,
        bug_id: str,
        endpoint: str,
        reproduction_steps: list[str],
        affected_files: Optional[list[str]] = None,
        base_url: Optional[str] = None,
    ) -> BugHookResult:
        """
        Validate bug reproduction through QA testing.

        Args:
            bug_id: Bug identifier (e.g., "BUG-123").
            endpoint: API endpoint affected by the bug.
            reproduction_steps: Steps to reproduce the bug.
            affected_files: Optional list of files affected.
            base_url: Optional base URL for API requests.

        Returns:
            BugHookResult with validation outcomes.
        """
        self._log("bug_validation_start", {
            "bug_id": bug_id,
            "endpoint": endpoint,
            "steps": len(reproduction_steps),
        })

        result = BugHookResult(bug_id=bug_id)

        try:
            # Build context from bug information
            context = self.context_builder.build_context(
                trigger=QATrigger.BUG_REPRODUCTION,
                target=affected_files[0] if affected_files else endpoint,
                bug_id=bug_id,
                base_url=base_url,
            )

            if affected_files:
                context.target_files = affected_files

            # Run DEEP QA testing for bug reproduction
            session = self.orchestrator.test(
                target=endpoint,
                depth=QADepth.DEEP,
                trigger=QATrigger.BUG_REPRODUCTION,
                base_url=base_url,
            )

            result.session_id = session.session_id

            if session.result:
                result.findings = session.result.findings

                # Determine if bug is reproducible
                if session.result.recommendation == QARecommendation.BLOCK:
                    # Bug confirmed - findings indicate the issue
                    result.is_reproducible = True
                elif session.result.recommendation == QARecommendation.PASS:
                    # Bug not reproduced - tests passed
                    result.is_reproducible = False
                else:
                    # Warnings - might be partially reproducible
                    result.is_reproducible = len(result.findings) > 0

                # Extract evidence from findings
                result.evidence = self._extract_evidence(result.findings)

                # Generate root cause hints
                result.root_cause_hints = self._generate_root_cause_hints(result.findings)

            self._log("bug_validation_complete", {
                "bug_id": bug_id,
                "session_id": session.session_id,
                "is_reproducible": result.is_reproducible,
                "findings_count": len(result.findings),
            })

            return result

        except TimeoutError as e:
            self._log("bug_validation_timeout", {"error": str(e)}, level="warning")
            result.error = f"Validation timed out: {e}"
            result.is_inconclusive = True
            return result

        except Exception as e:
            self._log("bug_validation_error", {"error": str(e)}, level="error")
            result.error = f"Validation failed: {e}"
            result.is_inconclusive = True
            return result

    def _extract_evidence(self, findings: list[QAFinding]) -> dict[str, Any]:
        """
        Extract evidence from QA findings.

        Args:
            findings: List of QA findings.

        Returns:
            Dictionary of evidence items.
        """
        evidence: dict[str, Any] = {}

        for i, finding in enumerate(findings):
            finding_key = f"finding_{i + 1}"
            evidence[finding_key] = {
                "endpoint": finding.endpoint,
                "expected": finding.expected,
                "actual": finding.actual,
                "severity": finding.severity,
            }

            # Include any additional evidence from the finding
            if finding.evidence:
                evidence[f"{finding_key}_details"] = finding.evidence

        return evidence

    def _generate_root_cause_hints(self, findings: list[QAFinding]) -> list[str]:
        """
        Generate hints for root cause analysis.

        Args:
            findings: List of QA findings.

        Returns:
            List of root cause hint strings.
        """
        hints: list[str] = []

        for finding in findings:
            # Add category-specific hints
            if finding.category == "behavioral":
                hints.append(f"Behavioral issue on {finding.endpoint}: Check request handling logic")
            elif finding.category == "contract":
                hints.append(f"Contract violation on {finding.endpoint}: Check response schema/model")
            elif finding.category == "regression":
                hints.append(f"Regression detected on {finding.endpoint}: Review recent changes")

            # Add severity-specific hints
            if finding.severity == "critical":
                hints.append(f"Critical: {finding.title} - Immediate investigation required")

            # Add hints from the finding's recommendation
            if finding.recommendation:
                hints.append(f"Suggested fix: {finding.recommendation}")

            # Add hints based on actual vs expected
            if "status" in finding.actual:
                status = finding.actual.get("status")
                if status == 500:
                    hints.append("Server error (500): Check server logs for stack traces")
                elif status == 503:
                    hints.append("Service unavailable (503): Check external dependencies")
                elif status == 401 or status == 403:
                    hints.append("Auth error: Check authentication/authorization logic")

        # Deduplicate hints while preserving order
        seen = set()
        unique_hints = []
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                unique_hints.append(hint)

        return unique_hints
