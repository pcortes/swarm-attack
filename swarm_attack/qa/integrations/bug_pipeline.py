"""Bug Pipeline QA Integration.

Implements spec section 5.2.2:
- Enhance bug reproduction with behavioral tests
- Run DEEP QA on affected area when BugResearcher fails to reproduce
- Provide evidence for RootCauseAnalyzer
- Extract reproduction steps from QA findings
- Integrates QASessionExtension for endpoint tracking during reproduction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import uuid

from swarm_attack.qa.models import (
    QADepth,
    QAFinding,
    QATrigger,
)
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.session_extension import QASessionExtension

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class BugReproductionResult:
    """Result of QA-enhanced bug reproduction."""
    session_id: Optional[str] = None
    is_reproduced: bool = False
    reproduction_steps: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    root_cause_hints: list[str] = field(default_factory=list)
    error: Optional[str] = None


class BugPipelineQAIntegration:
    """
    Integration layer for enhancing bug reproduction with QA behavioral tests.

    Provides methods to:
    - Attempt behavioral reproduction of a bug
    - Extract evidence for RootCauseAnalyzer
    - Generate reproduction steps from QA findings
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the BugPipelineQAIntegration.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.orchestrator = QAOrchestrator(config, logger)

        # Initialize session extension for endpoint tracking during reproduction
        swarm_dir = Path(config.repo_root) / ".swarm"
        self.session_extension = QASessionExtension(swarm_dir)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "bug_pipeline_qa_integration"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def enhance_reproduction(
        self,
        bug_id: str,
        bug_description: str,
        error_message: Optional[str] = None,
        affected_endpoints: Optional[list[str]] = None,
    ) -> BugReproductionResult:
        """
        Attempt behavioral reproduction of a bug.

        Uses DEEP depth to thoroughly test the affected area with edge cases,
        error cases, and security probes to find the reproduction path.

        Args:
            bug_id: The bug identifier.
            bug_description: Description of the bug from the report.
            error_message: Optional error message from the bug report.
            affected_endpoints: Optional list of endpoints to focus on.

        Returns:
            BugReproductionResult with reproduction status and evidence.
        """
        # Build target string from available info
        target = self._build_target(bug_description, error_message, affected_endpoints)

        self._log("qa_bug_reproduction_start", {
            "bug_id": bug_id,
            "target": target,
        })

        try:
            # Generate session ID for tracking
            session_id = f"qa-bug-{bug_id}-{uuid.uuid4().hex[:8]}"

            # Derive endpoints to track - use affected_endpoints or derive from description
            endpoints_discovered = affected_endpoints or [target]

            # Call session extension on_session_start BEFORE running tests
            self.session_extension.on_session_start(session_id, endpoints_discovered)

            # Run QA with DEEP depth for thorough bug hunting
            session = self.orchestrator.test(
                target=target,
                depth=QADepth.DEEP,
                trigger=QATrigger.BUG_REPRODUCTION,
            )

            # Build result
            result = BugReproductionResult(
                session_id=session.session_id,
            )

            # Get findings from session result
            findings = []
            endpoints_tested = []
            if session.result:
                # Bug is reproduced if QA found any failures
                result.is_reproduced = session.result.tests_failed > 0
                findings = session.result.findings or []

                # Extract tested endpoints from findings
                for finding in findings:
                    if hasattr(finding, 'endpoint') and finding.endpoint:
                        endpoints_tested.append(finding.endpoint)

                # Extract reproduction steps from findings
                if findings:
                    result.reproduction_steps = self._extract_reproduction_steps(
                        findings
                    )
                    result.evidence = self._extract_evidence(findings)
                    result.root_cause_hints = self._extract_root_cause_hints(
                        findings
                    )

            # Call session extension on_session_complete AFTER getting results
            # Convert findings to dicts for session extension
            findings_dicts = []
            for f in findings:
                if hasattr(f, '__dict__'):
                    findings_dicts.append({k: v for k, v in f.__dict__.items() if not k.startswith('_')})
                elif isinstance(f, dict):
                    findings_dicts.append(f)

            self.session_extension.on_session_complete(
                session.session_id,
                endpoints_tested or endpoints_discovered,
                findings_dicts,
            )

            self._log("qa_bug_reproduction_complete", {
                "bug_id": bug_id,
                "session_id": session.session_id,
                "is_reproduced": result.is_reproduced,
            })

            return result

        except Exception as e:
            self._log("qa_bug_reproduction_error", {"error": str(e)}, level="error")
            return BugReproductionResult(
                error=str(e),
                is_reproduced=False,
            )

    def get_rca_evidence(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Extract evidence for root cause analysis.

        Gathers all relevant evidence from a QA session for consumption
        by the RootCauseAnalyzer agent.

        Args:
            session_id: The QA session ID.

        Returns:
            Dictionary with evidence formatted for RCA:
            - endpoints_affected: List of affected endpoints
            - findings: List of finding summaries
            - requests: List of request evidence
            - responses: List of response evidence
            - stack_traces: List of stack traces if available
            - reproduction_steps: List of steps to reproduce
        """
        session = self.orchestrator.get_session(session_id)
        if not session:
            return {}

        if not session.result:
            return {"session_id": session_id}

        evidence: dict[str, Any] = {
            "session_id": session_id,
            "endpoints_affected": [],
            "findings": [],
            "requests": [],
            "responses": [],
            "stack_traces": [],
            "reproduction_steps": [],
        }

        seen_endpoints: set[str] = set()

        for finding in session.result.findings:
            # Track unique endpoints
            if finding.endpoint not in seen_endpoints:
                evidence["endpoints_affected"].append(finding.endpoint)
                seen_endpoints.add(finding.endpoint)

            # Add finding summary
            evidence["findings"].append({
                "id": finding.finding_id,
                "severity": finding.severity,
                "title": finding.title,
                "endpoint": finding.endpoint,
                "expected": finding.expected,
                "actual": finding.actual,
            })

            # Extract request/response evidence
            if "request" in finding.evidence:
                evidence["requests"].append(finding.evidence["request"])
            if "response" in finding.evidence:
                evidence["responses"].append(finding.evidence["response"])
            if "stack_trace" in finding.evidence:
                evidence["stack_traces"].append(finding.evidence["stack_trace"])

        # Generate reproduction steps
        evidence["reproduction_steps"] = self._extract_reproduction_steps(
            session.result.findings
        )

        return evidence

    def _build_target(
        self,
        bug_description: str,
        error_message: Optional[str],
        affected_endpoints: Optional[list[str]],
    ) -> str:
        """Build a target string for QA testing."""
        if affected_endpoints:
            # Use first endpoint as primary target
            return affected_endpoints[0]

        # Extract potential endpoint from description
        description_lower = bug_description.lower()

        # Look for common API patterns
        if "/api/" in description_lower:
            # Extract endpoint pattern
            start = description_lower.find("/api/")
            end = description_lower.find(" ", start)
            if end == -1:
                end = len(description_lower)
            return description_lower[start:end]

        # Use description as-is
        return bug_description

    def _extract_reproduction_steps(
        self,
        findings: list[QAFinding],
    ) -> list[str]:
        """Extract reproduction steps from findings."""
        steps: list[str] = []

        for finding in findings:
            # Build step from evidence
            step_parts = []

            if "request" in finding.evidence:
                step_parts.append(f"Execute: {finding.evidence['request']}")
            else:
                step_parts.append(f"Send request to {finding.endpoint}")

            step_parts.append(f"Expected: {finding.expected}")
            step_parts.append(f"Actual: {finding.actual}")

            if steps:
                steps.append("---")  # Separator between findings
            steps.extend(step_parts)

        return steps

    def _extract_evidence(
        self,
        findings: list[QAFinding],
    ) -> dict[str, Any]:
        """Extract all evidence from findings."""
        evidence: dict[str, Any] = {
            "requests": [],
            "responses": [],
            "endpoints": [],
        }

        for finding in findings:
            if "request" in finding.evidence:
                evidence["requests"].append(finding.evidence["request"])
            if "response" in finding.evidence:
                evidence["responses"].append(finding.evidence["response"])
            evidence["endpoints"].append(finding.endpoint)

        # Deduplicate endpoints
        evidence["endpoints"] = list(set(evidence["endpoints"]))

        return evidence

    def _extract_root_cause_hints(
        self,
        findings: list[QAFinding],
    ) -> list[str]:
        """Extract potential root cause hints from findings."""
        hints: list[str] = []

        for finding in findings:
            # Add recommendations as hints
            if finding.recommendation:
                hints.append(finding.recommendation)

            # Look for error patterns in evidence
            if "stack_trace" in finding.evidence:
                hints.append(f"Stack trace available: {finding.evidence['stack_trace'][:100]}...")

            # Add severity-based hint
            if finding.severity == "critical":
                hints.append(f"Critical issue at {finding.endpoint}: {finding.title}")

        return hints

    def set_coverage_baseline(
        self,
        session_id: str,
        endpoints_tested: list[str],
        findings: list,
    ) -> None:
        """
        Set coverage baseline after bug fix.

        Call this method after a bug is fixed and verified to establish
        a baseline for future regression detection.

        Args:
            session_id: The QA session ID to use as baseline.
            endpoints_tested: List of endpoints that were tested.
            findings: List of findings from the session (typically empty after fix).
        """
        self._log("set_coverage_baseline", {
            "session_id": session_id,
            "endpoints_count": len(endpoints_tested),
        })

        # First call on_session_start to set the endpoints
        self.session_extension.on_session_start(session_id, endpoints_tested)

        # Then set as baseline
        self.session_extension.set_as_baseline(
            session_id,
            endpoints_tested,
            findings,
        )
