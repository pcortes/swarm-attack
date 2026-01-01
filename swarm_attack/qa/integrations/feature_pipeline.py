"""Feature Pipeline QA Integration.

Implements spec section 5.2.1:
- Integrate QA validation after Verifier passes
- Skip QA with skip_qa flag
- Block on critical QA findings
- Create bugs for critical/moderate findings
- Log warnings but continue on WARN recommendation
- Integrates QASessionExtension for coverage tracking per issue
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import uuid

from swarm_attack.qa.models import (
    QADepth,
    QARecommendation,
    QASession,
)
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.session_extension import QASessionExtension

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


# High-risk file patterns that should trigger DEEP testing
HIGH_RISK_PATTERNS = [
    "auth",
    "authentication",
    "payment",
    "payments",
    "billing",
    "security",
    "crypto",
    "encryption",
    "password",
    "credential",
    "token",
    "secret",
    "permission",
    "access",
]


@dataclass
class QAIntegrationResult:
    """Result of running QA in a pipeline integration."""
    session_id: Optional[str] = None
    recommendation: QARecommendation = QARecommendation.PASS
    should_block: bool = False
    block_reason: Optional[str] = None
    created_bugs: list[str] = field(default_factory=list)
    findings_summary: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


class FeaturePipelineQAIntegration:
    """
    Integration layer for running QA after Verifier passes in the feature pipeline.

    Provides methods to:
    - Run post-verification QA with appropriate depth
    - Determine if findings should block commit
    - Create bug investigations from QA findings
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the FeaturePipelineQAIntegration.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.orchestrator = QAOrchestrator(config, logger)

        # Initialize session extension for coverage tracking per issue
        swarm_dir = Path(config.repo_root) / ".swarm"
        self.session_extension = QASessionExtension(swarm_dir)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "feature_pipeline_qa_integration"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def run_post_verification_qa(
        self,
        feature_id: str,
        issue_number: int,
        verified_files: list[str],
        skip_qa: bool = False,
    ) -> QAIntegrationResult:
        """
        Run QA after successful verification.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            verified_files: List of file paths that were verified.
            skip_qa: If True, skip QA and return PASS immediately.

        Returns:
            QAIntegrationResult with session details and recommendations.
        """
        # Skip QA if requested - don't call session extension
        if skip_qa:
            self._log("qa_skipped", {"feature_id": feature_id, "issue_number": issue_number})
            return QAIntegrationResult(
                session_id=None,
                recommendation=QARecommendation.PASS,
                should_block=False,
            )

        # Determine depth based on file risk
        depth = QADepth.STANDARD
        if self._has_high_risk_files(verified_files):
            depth = QADepth.DEEP
            self._log("qa_depth_escalated", {
                "feature_id": feature_id,
                "reason": "high_risk_files_detected",
            })

        try:
            # Generate session ID for per-issue tracking
            session_id = f"qa-{feature_id}-issue{issue_number}-{uuid.uuid4().hex[:8]}"

            # Derive endpoints from verified files (simplified mapping)
            endpoints_discovered = [f"/{f.replace('.py', '').replace('/', '.')}" for f in verified_files]

            # Call session extension on_session_start BEFORE validation
            self.session_extension.on_session_start(session_id, endpoints_discovered)

            # Run QA validation
            session = self.orchestrator.validate_issue(
                feature_id=feature_id,
                issue_number=issue_number,
                depth=depth,
            )

            # Build result
            result = QAIntegrationResult(
                session_id=session.session_id,
            )

            # Get findings from session result
            findings = []
            endpoints_tested = []
            if session.result:
                result.recommendation = session.result.recommendation
                findings = session.result.findings or []

                # Extract tested endpoints from findings
                for finding in findings:
                    if hasattr(finding, 'endpoint') and finding.endpoint:
                        endpoints_tested.append(finding.endpoint)

                # Check if should block from QA
                should_block, block_reason = self.should_block_commit(session)
                result.should_block = should_block
                result.block_reason = block_reason

                # Build findings summary
                result.findings_summary = {
                    "critical": session.result.critical_count,
                    "moderate": session.result.moderate_count,
                    "minor": session.result.minor_count,
                }

            # Call session extension on_session_complete AFTER getting results
            # Convert findings to dicts for session extension
            findings_dicts = []
            for f in findings:
                if hasattr(f, '__dict__'):
                    findings_dicts.append({k: v for k, v in f.__dict__.items() if not k.startswith('_')})
                elif isinstance(f, dict):
                    findings_dicts.append(f)

            session_ext_result = self.session_extension.on_session_complete(
                session.session_id,
                endpoints_tested or endpoints_discovered,
                findings_dicts,
            )

            # Check if session extension requires blocking (regression/coverage drop)
            if session_ext_result.should_block:
                result.should_block = True
                result.block_reason = session_ext_result.block_reason or result.block_reason

            self._log("qa_post_verification_complete", {
                "session_id": session.session_id,
                "recommendation": result.recommendation.value,
                "should_block": result.should_block,
            })

            return result

        except Exception as e:
            self._log("qa_post_verification_error", {"error": str(e)}, level="error")
            return QAIntegrationResult(
                error=str(e),
                recommendation=QARecommendation.PASS,  # Fail open
                should_block=False,
            )

    def should_block_commit(
        self,
        qa_result: QASession,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if QA findings should block commit.

        Args:
            qa_result: The QASession with results.

        Returns:
            Tuple of (should_block, reason). Reason is None if not blocking.
        """
        # No result means session failed - fail open
        if qa_result.result is None:
            return False, None

        # Check recommendation
        if qa_result.result.recommendation == QARecommendation.BLOCK:
            critical_count = qa_result.result.critical_count
            finding_details = ""
            if qa_result.result.findings:
                first_finding = qa_result.result.findings[0]
                finding_details = f": {first_finding.title}"

            reason = f"QA found {critical_count} critical issue(s){finding_details}"
            return True, reason

        # WARN and PASS do not block
        return False, None

    def create_bugs_from_findings(
        self,
        session_id: str,
        severity_threshold: str = "moderate",
    ) -> list[str]:
        """
        Create bug investigations from QA findings.

        Args:
            session_id: The QA session ID.
            severity_threshold: Minimum severity for bug creation.
                Options: "critical", "moderate", "minor".

        Returns:
            List of created bug IDs.
        """
        try:
            bug_ids = self.orchestrator.create_bug_investigations(
                session_id=session_id,
                severity_threshold=severity_threshold,
            )

            self._log("bugs_created_from_findings", {
                "session_id": session_id,
                "bug_count": len(bug_ids),
                "severity_threshold": severity_threshold,
            })

            return bug_ids

        except Exception as e:
            self._log("bug_creation_error", {"error": str(e)}, level="error")
            return []

    def _is_high_risk_file(self, file_path: str) -> bool:
        """
        Check if a file path indicates high-risk code.

        Args:
            file_path: The file path to check.

        Returns:
            True if file is high-risk, False otherwise.
        """
        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in HIGH_RISK_PATTERNS)

    def _has_high_risk_files(self, files: list[str]) -> bool:
        """
        Check if any files in the list are high-risk.

        Args:
            files: List of file paths.

        Returns:
            True if any file is high-risk, False otherwise.
        """
        return any(self._is_high_risk_file(f) for f in files)

    def set_coverage_baseline(
        self,
        session_id: str,
        endpoints_tested: list[str],
        findings: list,
    ) -> None:
        """
        Set coverage baseline after feature completion.

        Call this method after a feature is fully implemented and verified
        to establish a baseline for future regression detection.

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
