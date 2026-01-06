"""QAOrchestrator for coordinating adaptive QA testing.

Implements spec sections 6, 10.10-10.12:
- Depth-based agent dispatch
- Cost/limit enforcement
- Graceful degradation
- Session management
- Result aggregation
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.agents.contract import ContractValidatorAgent
from swarm_attack.qa.agents.regression import RegressionScannerAgent
from swarm_attack.qa.agents.semantic_tester import SemanticTesterAgent
from swarm_attack.qa.models import (
    QABug,
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    QALimits,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class QAOrchestrator:
    """
    Orchestrator that coordinates adaptive QA testing across multiple agents.

    Routes to specialized sub-agents based on depth:
    - SHALLOW: BehavioralTester only (happy path)
    - STANDARD: BehavioralTester + ContractValidator
    - DEEP: All agents including SemanticTester
    - REGRESSION: RegressionScanner + targeted BehavioralTester
    - SEMANTIC: SemanticTester only (Claude CLI-powered)
    """

    # Class-level counter for unique session IDs
    _session_counter: int = 0

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        limits: Optional[QALimits] = None,
    ) -> None:
        """
        Initialize the QAOrchestrator.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            limits: Optional QALimits for cost/resource control.
        """
        self.config = config
        self._logger = logger
        self.limits = limits or QALimits()

        # Set up session storage path
        self.sessions_path = Path(config.repo_root) / ".swarm" / "qa"
        self.sessions_path.mkdir(parents=True, exist_ok=True)

        # Create sub-agents
        self.behavioral_agent = BehavioralTesterAgent(config, logger)
        self.contract_agent = ContractValidatorAgent(config, logger, limits=self.limits)
        self.regression_agent = RegressionScannerAgent(config, logger, limits=self.limits)
        self.semantic_tester = SemanticTesterAgent(config, logger)

        # Session tracking
        self._current_session: Optional[QASession] = None
        self._session_start_time: Optional[float] = None
        self._accumulated_cost: float = 0.0
        self._warnings: list[str] = []

    def _generate_session_id(self) -> str:
        """Generate a session ID in qa-YYYYMMDD-HHMMSS format."""
        now = datetime.now(timezone.utc)
        QAOrchestrator._session_counter += 1
        # Include counter to ensure uniqueness within same second
        base_id = f"qa-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"
        if QAOrchestrator._session_counter > 1:
            return f"{base_id}-{QAOrchestrator._session_counter:03d}"
        return base_id

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "qa_orchestrator"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _log_warning(self, message: str) -> None:
        """Log a warning message."""
        self._warnings.append(message)
        self._log("qa_warning", {"message": message}, level="warning")

    def test(
        self,
        target: str,
        depth: QADepth = QADepth.STANDARD,
        trigger: QATrigger = QATrigger.USER_COMMAND,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ) -> QASession:
        """
        Main entry point for QA testing.

        Args:
            target: What to test (file path, endpoint, or description).
            depth: Testing depth level.
            trigger: What initiated this QA session.
            base_url: Optional base URL for API requests.
            timeout: Timeout in seconds.

        Returns:
            QASession with test results.
        """
        # Generate session
        session_id = self._generate_session_id()
        context = QAContext(
            target_files=[target] if target.endswith(".py") else [],
            base_url=base_url,
        )
        if not target.endswith(".py") and target.startswith("/"):
            context.target_endpoints = [QAEndpoint(method="GET", path=target)]

        session = QASession(
            session_id=session_id,
            trigger=trigger,
            depth=depth,
            status=QAStatus.PENDING,
            context=context,
        )
        session.started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._current_session = session
        self._session_start_time = time.time()
        self._accumulated_cost = 0.0
        self._warnings = []

        self._log("qa_session_start", {
            "session_id": session_id,
            "target": target,
            "depth": depth.value,
            "trigger": trigger.value,
        })

        try:
            # Check cost limit before starting
            if self._get_current_cost() >= self.limits.max_cost_usd:
                session.status = QAStatus.COMPLETED_PARTIAL
                session.result = QAResult(
                    partial_completion_reason="cost_limit: exceeded max_cost_usd before starting"
                )
                session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._save_session(session)
                return session

            # Check timeout
            if self._check_timeout():
                session.status = QAStatus.COMPLETED_PARTIAL
                session.result = QAResult(
                    partial_completion_reason="timeout: exceeded session_timeout before starting"
                )
                session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._save_session(session)
                return session

            # Dispatch to agents
            session.status = QAStatus.RUNNING
            agent_results = self.dispatch_agents(depth, context)

            # Aggregate results
            result = self._aggregate_results(agent_results)
            session.result = result
            session.status = QAStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            session.cost_usd = self._accumulated_cost

        except Exception as e:
            self._log("qa_session_error", {"error": str(e)}, level="error")
            session.status = QAStatus.BLOCKED
            session.error = str(e)
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._save_session(session)
        return session

    def validate_issue(
        self,
        feature_id: str,
        issue_number: int,
        depth: QADepth = QADepth.STANDARD,
    ) -> QASession:
        """
        Validate an implemented issue with behavioral tests.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            depth: Testing depth level.

        Returns:
            QASession with validation results.
        """
        session_id = self._generate_session_id()
        context = QAContext(
            feature_id=feature_id,
            issue_number=issue_number,
        )

        session = QASession(
            session_id=session_id,
            trigger=QATrigger.POST_VERIFICATION,
            depth=depth,
            status=QAStatus.PENDING,
            context=context,
        )
        session.started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._current_session = session
        self._session_start_time = time.time()
        self._accumulated_cost = 0.0

        self._log("qa_validate_issue_start", {
            "session_id": session_id,
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        try:
            session.status = QAStatus.RUNNING
            agent_results = self.dispatch_agents(depth, context)
            result = self._aggregate_results(agent_results)
            session.result = result
            session.status = QAStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception as e:
            session.status = QAStatus.FAILED
            session.error = str(e)
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._save_session(session)
        return session

    def health_check(self, base_url: Optional[str] = None) -> QASession:
        """
        Run shallow health check on all endpoints.

        Args:
            base_url: Optional base URL for API requests.

        Returns:
            QASession with health check results.
        """
        session_id = self._generate_session_id()

        # Default health endpoints to check
        default_endpoints = [
            QAEndpoint(method="GET", path="/health"),
            QAEndpoint(method="GET", path="/healthz"),
            QAEndpoint(method="GET", path="/api/health"),
        ]

        context = QAContext(
            base_url=base_url,
            target_endpoints=default_endpoints,
        )

        session = QASession(
            session_id=session_id,
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.SHALLOW,
            status=QAStatus.PENDING,
            context=context,
        )
        session.started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._current_session = session
        self._session_start_time = time.time()

        self._log("qa_health_check_start", {"session_id": session_id})

        try:
            session.status = QAStatus.RUNNING
            agent_results = self.dispatch_agents(QADepth.SHALLOW, context)
            result = self._aggregate_results(agent_results)
            session.result = result
            session.status = QAStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception as e:
            session.status = QAStatus.FAILED
            session.error = str(e)
            session.completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self._save_session(session)
        return session

    def dispatch_agents(
        self,
        depth: QADepth,
        context: QAContext,
    ) -> dict[str, Any]:
        """
        Route to appropriate sub-agents based on depth.

        Depth-based dispatch (Section 6):
        - SHALLOW: BehavioralTester only (happy path)
        - STANDARD: BehavioralTester + ContractValidator
        - DEEP: All agents including SemanticTester
        - REGRESSION: RegressionScanner + targeted BehavioralTester
        - SEMANTIC: SemanticTester only (Claude CLI-powered)

        Args:
            depth: Testing depth level.
            context: QAContext for the session.

        Returns:
            Dictionary with results from each agent.
        """
        results: dict[str, Any] = {}
        skipped_reasons: dict[str, str] = {}

        # Build agent context
        agent_context = {
            "base_url": context.base_url or "http://localhost:8000",
            "endpoints": context.target_endpoints,
            "target_files": context.target_files,
            "depth": depth,
            "skip_service_start": True,  # Default to not auto-starting
        }

        # Limit endpoints based on depth
        if context.target_endpoints:
            agent_context["endpoints"] = self._limit_endpoints(
                context.target_endpoints, depth
            )

        if depth == QADepth.SHALLOW:
            # SHALLOW: BehavioralTester only
            results["behavioral"] = self._run_agent_safe(
                self.behavioral_agent, agent_context, "behavioral", skipped_reasons
            )

        elif depth == QADepth.STANDARD:
            # STANDARD: BehavioralTester + ContractValidator
            results["behavioral"] = self._run_agent_safe(
                self.behavioral_agent, agent_context, "behavioral", skipped_reasons
            )
            results["contract"] = self._run_agent_safe(
                self.contract_agent, agent_context, "contract", skipped_reasons
            )

        elif depth == QADepth.DEEP:
            # DEEP: All agents including semantic
            results["behavioral"] = self._run_agent_safe(
                self.behavioral_agent, agent_context, "behavioral", skipped_reasons
            )
            results["contract"] = self._run_agent_safe(
                self.contract_agent, agent_context, "contract", skipped_reasons
            )
            results["regression"] = self._run_agent_safe(
                self.regression_agent, agent_context, "regression", skipped_reasons
            )
            results["semantic"] = self._run_agent_safe(
                self.semantic_tester, agent_context, "semantic", skipped_reasons
            )

        elif depth == QADepth.REGRESSION:
            # REGRESSION: RegressionScanner + targeted BehavioralTester
            regression_result = self._run_agent_safe(
                self.regression_agent, agent_context, "regression", skipped_reasons
            )
            results["regression"] = regression_result

            # Use regression scanner's output to target behavioral tests
            if regression_result and isinstance(regression_result, dict):
                regression_suite = regression_result.get("regression_suite", {})
                must_test = regression_suite.get("must_test", [])
                should_test = regression_suite.get("should_test", [])
                targeted_endpoints = [
                    QAEndpoint(method="GET", path=path)
                    for path in must_test + should_test
                ]
                if targeted_endpoints:
                    agent_context["endpoints"] = targeted_endpoints

            results["behavioral"] = self._run_agent_safe(
                self.behavioral_agent, agent_context, "behavioral", skipped_reasons
            )

        elif depth == QADepth.SEMANTIC:
            # SEMANTIC: SemanticTester only (Claude CLI-powered)
            results["semantic"] = self._run_agent_safe(
                self.semantic_tester, agent_context, "semantic", skipped_reasons
            )

        if skipped_reasons:
            results["skipped_reasons"] = skipped_reasons

        return results

    def _run_agent_safe(
        self,
        agent: Any,
        context: dict[str, Any],
        agent_name: str,
        skipped_reasons: dict[str, str],
    ) -> Optional[dict[str, Any]]:
        """
        Run an agent safely, catching exceptions.

        Args:
            agent: The agent to run.
            context: Context for the agent.
            agent_name: Name of the agent for logging.
            skipped_reasons: Dict to track skipped agents.

        Returns:
            Agent output or None if failed.
        """
        try:
            result = agent.run(context)
            if result.success:
                return result.output
            else:
                skipped_reasons[agent_name] = result.error or "Agent failed"
                return None
        except Exception as e:
            self._log(f"{agent_name}_agent_error", {"error": str(e)}, level="error")
            skipped_reasons[agent_name] = str(e)
            return None

    def _normalize_finding(self, f: Any) -> Optional[QAFinding]:
        """
        Convert a finding to QAFinding if it's a dict.

        Args:
            f: Either a QAFinding or a dict representation of one.

        Returns:
            QAFinding object or None if conversion fails.
        """
        if isinstance(f, QAFinding):
            return f
        if isinstance(f, dict):
            try:
                return QAFinding.from_dict(f)
            except Exception:
                return None
        return None

    def _aggregate_results(self, agent_results: dict[str, Any]) -> QAResult:
        """
        Combine results from all agents.

        Args:
            agent_results: Dictionary of results from each agent.

        Returns:
            Aggregated QAResult.
        """
        result = QAResult()
        all_findings: list[QAFinding] = []

        # Extract behavioral results
        if behavioral := agent_results.get("behavioral"):
            if isinstance(behavioral, dict):
                result.tests_run += behavioral.get("tests_run", 0)
                result.tests_passed += behavioral.get("tests_passed", 0)
                result.tests_failed += behavioral.get("tests_failed", 0)
                findings = behavioral.get("findings", [])
                for f in findings:
                    normalized = self._normalize_finding(f)
                    if normalized:
                        all_findings.append(normalized)
                result.behavioral_results = behavioral

        # Extract contract results
        if contract := agent_results.get("contract"):
            if isinstance(contract, dict):
                contracts_checked = contract.get("contracts_checked", 0)
                result.tests_run += contracts_checked
                result.tests_passed += contract.get("contracts_valid", 0)
                result.tests_failed += contract.get("contracts_broken", 0)
                findings = contract.get("findings", [])
                for f in findings:
                    normalized = self._normalize_finding(f)
                    if normalized:
                        all_findings.append(normalized)
                result.contract_results = contract

        # Extract regression results
        if regression := agent_results.get("regression"):
            if isinstance(regression, dict):
                result.regression_results = regression
                findings = regression.get("findings", [])
                for f in findings:
                    normalized = self._normalize_finding(f)
                    if normalized:
                        all_findings.append(normalized)

        # Extract semantic results
        if semantic := agent_results.get("semantic"):
            if isinstance(semantic, dict):
                # Semantic tests don't have standard test counts
                # but may have findings
                findings = semantic.get("issues", [])
                for f in findings:
                    # Convert semantic issues to QAFinding format
                    if isinstance(f, dict):
                        qa_finding = QAFinding(
                            finding_id=f"sem-{len(all_findings)+1}",
                            severity=f.get("severity", "minor"),
                            category="semantic",
                            endpoint="",
                            test_type="semantic",
                            title=f.get("description", "Semantic issue")[:50],
                            description=f.get("description", ""),
                            expected={},
                            actual={},
                            evidence={"suggestion": f.get("suggestion", "")},
                            recommendation=f.get("suggestion", ""),
                        )
                        all_findings.append(qa_finding)

        # Track skipped reasons
        if skipped := agent_results.get("skipped_reasons"):
            result.skipped_reasons = skipped

        # Deduplicate findings (by endpoint + actual status)
        seen_keys: set[tuple] = set()
        unique_findings: list[QAFinding] = []
        for finding in all_findings:
            key = (
                finding.endpoint,
                str(finding.actual.get("status", "")),
                finding.title,
            )
            if key not in seen_keys:
                seen_keys.add(key)
                unique_findings.append(finding)

        result.findings = unique_findings

        # Count by severity
        for finding in result.findings:
            if finding.severity == "critical":
                result.critical_count += 1
            elif finding.severity == "moderate":
                result.moderate_count += 1
            else:
                result.minor_count += 1

        # Set recommendation based on findings
        if result.critical_count > 0:
            result.recommendation = QARecommendation.BLOCK
        elif result.moderate_count > 0:
            result.recommendation = QARecommendation.WARN
        else:
            result.recommendation = QARecommendation.PASS

        return result

    def _limit_endpoints(
        self, endpoints: list[QAEndpoint], depth: QADepth
    ) -> list[QAEndpoint]:
        """
        Limit the number of endpoints based on depth.

        Args:
            endpoints: List of endpoints.
            depth: Testing depth level.

        Returns:
            Limited list of endpoints.
        """
        if depth == QADepth.SHALLOW:
            max_endpoints = self.limits.max_endpoints_shallow
        elif depth == QADepth.STANDARD:
            max_endpoints = self.limits.max_endpoints_standard
        elif depth == QADepth.DEEP:
            max_endpoints = self.limits.max_endpoints_deep
        else:
            max_endpoints = self.limits.max_endpoints_standard

        return endpoints[:max_endpoints]

    def _check_timeout(self) -> bool:
        """Check if the session has timed out."""
        if self._session_start_time is None:
            return False

        elapsed_minutes = (time.time() - self._session_start_time) / 60
        return elapsed_minutes >= self.limits.session_timeout_minutes

    def _get_current_cost(self) -> float:
        """Get the current accumulated cost."""
        return self._accumulated_cost

    def _save_session(self, session: QASession) -> None:
        """Save session to disk."""
        session_dir = self.sessions_path / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        state_file = session_dir / "state.json"
        state_file.write_text(json.dumps(session.to_dict(), indent=2))

        # Generate and save report if completed
        if session.status in [QAStatus.COMPLETED, QAStatus.COMPLETED_PARTIAL]:
            self._save_report(session)

    def _save_report(self, session: QASession) -> None:
        """Generate and save QA report."""
        session_dir = self.sessions_path / session.session_id
        report_path = session_dir / "qa-report.md"

        result = session.result
        if not result:
            report_path.write_text(f"# QA Report: {session.session_id}\n\nNo results available.")
            return

        lines = [
            f"# QA Report: {session.session_id}",
            "",
            f"**Trigger:** {session.trigger.value}",
            f"**Depth:** {session.depth.value}",
            f"**Status:** {session.status.value}",
            f"**Recommendation:** {result.recommendation.value.upper()}",
            "",
            "## Summary",
            "",
            f"- **Tests Run:** {result.tests_run}",
            f"- **Passed:** {result.tests_passed}",
            f"- **Failed:** {result.tests_failed}",
            f"- **Endpoints Tested:** {len(result.endpoints_tested)}",
            "",
            "## Findings",
            "",
        ]

        if not result.findings:
            lines.append("No issues found.")
        else:
            for finding in result.findings:
                lines.extend([
                    f"### [{finding.severity.upper()}] {finding.finding_id}: {finding.title}",
                    "",
                    f"**Endpoint:** {finding.endpoint}",
                    f"**Category:** {finding.category}",
                    "",
                    finding.description,
                    "",
                    "**Expected:**",
                    "```json",
                    json.dumps(finding.expected, indent=2),
                    "```",
                    "",
                    "**Actual:**",
                    "```json",
                    json.dumps(finding.actual, indent=2),
                    "```",
                    "",
                    f"**Recommendation:** {finding.recommendation}",
                    "",
                    "---",
                    "",
                ])

        report_path.write_text("\n".join(lines))

    def get_session(self, session_id: str) -> Optional[QASession]:
        """
        Retrieve a QA session by ID.

        Args:
            session_id: The session ID to retrieve.

        Returns:
            QASession if found, None otherwise.
        """
        state_file = self.sessions_path / session_id / "state.json"
        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text())
            return QASession.from_dict(data)
        except Exception as e:
            self._log("session_load_error", {"session_id": session_id, "error": str(e)}, level="error")
            return None

    def list_sessions(self, limit: int = 20) -> list[str]:
        """
        List recent QA session IDs.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session IDs, newest first.
        """
        sessions = []
        if not self.sessions_path.exists():
            return sessions

        for path in sorted(self.sessions_path.iterdir(), reverse=True):
            if path.is_dir() and (path / "state.json").exists():
                sessions.append(path.name)
                if len(sessions) >= limit:
                    break

        return sessions

    def get_findings(
        self,
        session_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[QAFinding]:
        """
        Get findings, optionally filtered.

        Args:
            session_id: Optional session ID to filter by.
            severity: Optional severity to filter by.

        Returns:
            List of QAFinding objects.
        """
        findings: list[QAFinding] = []

        if session_id:
            # Get findings from specific session
            session = self.get_session(session_id)
            if session and session.result:
                findings = session.result.findings
        else:
            # Get findings from all recent sessions
            for sid in self.list_sessions(limit=50):
                session = self.get_session(sid)
                if session and session.result:
                    findings.extend(session.result.findings)

        # Filter by severity if specified
        if severity:
            findings = [f for f in findings if f.severity == severity]

        return findings

    def create_bug_investigations(
        self,
        session_id: str,
        severity_threshold: str = "moderate",
    ) -> list[str]:
        """
        Create Bug Bash entries from QA findings.

        Args:
            session_id: The session ID to create bugs from.
            severity_threshold: Minimum severity for bug creation.

        Returns:
            List of created bug IDs.
        """
        session = self.get_session(session_id)
        if not session or not session.result:
            return []

        # Define severity order
        severity_order = {"critical": 0, "moderate": 1, "minor": 2}
        threshold_level = severity_order.get(severity_threshold, 1)

        # Filter findings by severity threshold
        eligible_findings = [
            f for f in session.result.findings
            if severity_order.get(f.severity, 2) <= threshold_level
        ]

        if not eligible_findings:
            return []

        # Create bugs
        bugs: list[QABug] = []
        bug_ids: list[str] = []

        for i, finding in enumerate(eligible_findings, 1):
            bug_id = f"qa-bug-{session_id[-6:]}-{i:03d}"
            bug_ids.append(bug_id)

            bug = QABug(
                bug_id=bug_id,
                source_finding=finding.finding_id,
                qa_session=session_id,
                title=finding.title,
                description=finding.description,
                severity=finding.severity,
                endpoint=finding.endpoint,
                reproduction_steps=[
                    f"1. Send request to {finding.endpoint}",
                    f"2. Check response",
                    f"3. Expected: {finding.expected}",
                    f"4. Actual: {finding.actual}",
                ],
                expected_behavior=str(finding.expected),
                actual_behavior=str(finding.actual),
                evidence=finding.evidence,
            )
            bugs.append(bug)

        # Save bugs document
        if bugs:
            self._save_bugs_document(session_id, bugs)

        return bug_ids

    def _save_bugs_document(self, session_id: str, bugs: list[QABug]) -> None:
        """Save bugs document to disk."""
        session_dir = self.sessions_path / session_id
        bugs_path = session_dir / "qa-bugs.md"

        lines = [
            "# QA-Discovered Bugs",
            "",
            f"Generated from session: {session_id}",
            "",
        ]

        for bug in bugs:
            lines.extend([
                f"## {bug.bug_id}: {bug.title}",
                "",
                f"**Severity:** {bug.severity}",
                f"**Endpoint:** {bug.endpoint}",
                f"**Source Finding:** {bug.source_finding}",
                "",
                "### Description",
                bug.description,
                "",
                "### Steps to Reproduce",
                "",
            ])
            for i, step in enumerate(bug.reproduction_steps, 1):
                lines.append(f"{i}. {step}")
            lines.extend([
                "",
                "### Expected Behavior",
                bug.expected_behavior,
                "",
                "### Actual Behavior",
                bug.actual_behavior,
                "",
                "---",
                "",
            ])

        bugs_path.write_text("\n".join(lines))
