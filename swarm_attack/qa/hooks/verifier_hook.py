"""VerifierQAHook for post-verification QA integration.

Implements spec section 3: Pipeline Integration - Verifier Hook
- Post-verification QA hook that runs after Verifier completes
- Skips on verification failure
- Passes context to QA orchestrator
- Reports findings back to pipeline
- Graceful degradation if QA fails
- Integrates QASessionExtension for coverage tracking and regression detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import uuid

from swarm_attack.qa.context_builder import QAContextBuilder
from swarm_attack.qa.depth_selector import DepthSelector
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAFinding,
    QARecommendation,
    QATrigger,
)
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.session_extension import QASessionExtension

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class VerifierHookResult:
    """Result of running the VerifierQAHook."""

    session_id: Optional[str] = None
    recommendation: QARecommendation = QARecommendation.PASS
    findings: list[QAFinding] = field(default_factory=list)
    created_bugs: list[str] = field(default_factory=list)

    # Pipeline control flags
    should_block: bool = False
    should_continue: bool = True
    has_warnings: bool = False

    # Error handling
    skipped: bool = False
    error: Optional[str] = None


class VerifierQAHook:
    """
    Hook that runs QA validation after Verifier completes.

    This hook integrates QA testing into the feature pipeline,
    running behavioral and contract validation after unit tests pass.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the VerifierQAHook.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.qa_enabled = True

        # Create QA components
        self.orchestrator = QAOrchestrator(config, logger)
        self.context_builder = QAContextBuilder(config, logger)
        self.depth_selector = DepthSelector(config, logger)

        # Initialize session extension for coverage tracking and regression detection
        swarm_dir = Path(config.repo_root) / ".swarm"
        self.session_extension = QASessionExtension(swarm_dir)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "verifier_qa_hook"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def should_run(
        self,
        verification_success: bool,
        feature_id: str,
        issue_number: int,
    ) -> bool:
        """
        Determine if QA hook should run.

        Args:
            verification_success: Whether unit test verification passed.
            feature_id: Feature identifier.
            issue_number: Issue number.

        Returns:
            True if hook should run, False otherwise.
        """
        # Skip if QA is disabled
        if not self.qa_enabled:
            self._log("qa_hook_skip", {"reason": "qa_disabled"})
            return False

        # Skip if verification failed
        if not verification_success:
            self._log("qa_hook_skip", {"reason": "verification_failed"})
            return False

        return True

    def run(
        self,
        feature_id: str,
        issue_number: int,
        target_files: list[str],
        base_url: Optional[str] = None,
    ) -> VerifierHookResult:
        """
        Run QA validation after verification.

        Args:
            feature_id: Feature identifier.
            issue_number: Issue number.
            target_files: List of files modified/verified.
            base_url: Optional base URL for API requests.

        Returns:
            VerifierHookResult with QA outcomes.
        """
        self._log("qa_hook_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "files": len(target_files),
        })

        try:
            # Build context from available information
            context = self.context_builder.build_context(
                trigger=QATrigger.POST_VERIFICATION,
                target=target_files[0] if target_files else "",
                feature_id=feature_id,
                issue_number=issue_number,
                base_url=base_url,
            )
            context.target_files = target_files

            # Determine appropriate depth
            depth = self.depth_selector.select_depth(
                trigger=QATrigger.POST_VERIFICATION,
                context=context,
            )

            # Generate session ID for tracking
            session_id = f"qa-{feature_id}-{issue_number}-{uuid.uuid4().hex[:8]}"

            # Derive endpoints from target files (simplified mapping)
            endpoints_discovered = [f"/{f.replace('.py', '').replace('/', '.')}" for f in target_files]

            # Call session extension on_session_start BEFORE validate_issue
            self.session_extension.on_session_start(session_id, endpoints_discovered)

            # Run QA validation
            session = self.orchestrator.validate_issue(
                feature_id=feature_id,
                issue_number=issue_number,
                depth=depth,
            )

            # Build result
            result = VerifierHookResult(
                session_id=session.session_id,
            )

            # Get findings from session result
            findings = []
            endpoints_tested = []
            if session.result:
                result.recommendation = session.result.recommendation
                result.findings = session.result.findings
                findings = session.result.findings

                # Extract tested endpoints from findings
                for finding in findings:
                    if hasattr(finding, 'endpoint') and finding.endpoint:
                        endpoints_tested.append(finding.endpoint)

                # Determine blocking behavior from QA result
                if session.result.recommendation == QARecommendation.BLOCK:
                    result.should_block = True
                    result.should_continue = False

                    # Create bugs for critical findings
                    bug_ids = self.orchestrator.create_bug_investigations(
                        session_id=session.session_id,
                        severity_threshold="critical",
                    )
                    result.created_bugs = bug_ids

                elif session.result.recommendation == QARecommendation.WARN:
                    result.has_warnings = True
                    result.should_continue = True

                else:  # PASS
                    result.should_continue = True

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
                endpoints_tested or endpoints_discovered,  # Use discovered if none tested
                findings_dicts,
            )

            # Check if session extension requires blocking (regression/coverage drop)
            if session_ext_result.should_block:
                result.should_block = True
                result.should_continue = False
                self._log("qa_hook_session_extension_block", {
                    "session_id": session.session_id,
                    "block_reason": session_ext_result.block_reason,
                })

            self._log("qa_hook_complete", {
                "session_id": session.session_id,
                "recommendation": result.recommendation.value,
                "should_block": result.should_block,
            })

            return result

        except TimeoutError as e:
            self._log("qa_hook_timeout", {"error": str(e)}, level="warning")
            return VerifierHookResult(
                skipped=True,
                error=f"QA timed out: {e}",
                should_continue=True,  # Don't block on timeout
            )

        except Exception as e:
            self._log("qa_hook_error", {"error": str(e)}, level="error")
            return VerifierHookResult(
                skipped=True,
                error=f"QA failed: {e}",
                should_continue=True,  # Graceful degradation
            )
