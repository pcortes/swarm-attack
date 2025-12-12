"""
Bug Bash Orchestrator for swarm-attack.

This module coordinates the Bug Bash pipeline:
- Bug creation and initialization
- Reproduction workflow
- Root cause analysis workflow
- Fix planning workflow
- Approval gate enforcement
- Implementation workflow (post-approval)

The orchestrator is the main entry point for CLI commands.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from swarm_attack.agents.bug_researcher import BugResearcherAgent
from swarm_attack.agents.fix_planner import FixPlannerAgent
from swarm_attack.agents.root_cause_analyzer import RootCauseAnalyzerAgent
from swarm_attack.bug_models import (
    AgentCost,
    ApprovalRecord,
    ApprovalRequiredError,
    BugNotFoundError,
    BugPhase,
    BugState,
    CostLimitExceededError,
    InvalidPhaseError,
)
from swarm_attack.bug_state_store import BugStateStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


@dataclass
class BugPipelineResult:
    """Result from a bug pipeline operation."""

    success: bool
    bug_id: str
    phase: BugPhase
    cost_usd: float
    message: str = ""
    error: Optional[str] = None


class BugOrchestrator:
    """
    Orchestrator for the Bug Bash pipeline.

    Coordinates agents and state transitions for bug investigation:
    1. init: Create a new bug investigation
    2. analyze: Run reproduction → root cause → fix plan pipeline
    3. approve: Mark fix plan as approved (human gate)
    4. fix: Execute the approved fix (post-approval)
    5. reject: Mark bug as won't fix with reason
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        state_store: Optional[BugStateStore] = None,
        researcher: Optional[BugResearcherAgent] = None,
        analyzer: Optional[RootCauseAnalyzerAgent] = None,
        planner: Optional[FixPlannerAgent] = None,
    ) -> None:
        """
        Initialize the Bug Orchestrator.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            state_store: Optional state store (created if not provided).
            researcher: Optional Bug Researcher agent (created if not provided).
            analyzer: Optional Root Cause Analyzer agent (created if not provided).
            planner: Optional Fix Planner agent (created if not provided).
        """
        self.config = config
        self._logger = logger

        # Initialize state store
        bugs_path = Path(config.repo_root) / ".swarm" / "bugs"
        self._state_store = state_store or BugStateStore(base_path=bugs_path, logger=logger)

        # Initialize agents (lazy or provided)
        self._researcher = researcher
        self._analyzer = analyzer
        self._planner = planner

    @property
    def state_store(self) -> BugStateStore:
        """Get the state store."""
        return self._state_store

    @property
    def researcher(self) -> BugResearcherAgent:
        """Get the Bug Researcher agent (lazy init)."""
        if self._researcher is None:
            self._researcher = BugResearcherAgent(self.config, self._logger)
        return self._researcher

    @property
    def analyzer(self) -> RootCauseAnalyzerAgent:
        """Get the Root Cause Analyzer agent (lazy init)."""
        if self._analyzer is None:
            self._analyzer = RootCauseAnalyzerAgent(self.config, self._logger)
        return self._analyzer

    @property
    def planner(self) -> FixPlannerAgent:
        """Get the Fix Planner agent (lazy init)."""
        if self._planner is None:
            self._planner = FixPlannerAgent(self.config, self._logger)
        return self._planner

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "bug_orchestrator"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def _generate_bug_id(self, description: str) -> str:
        """
        Generate a unique bug ID from description.

        Format: bug-{slug}-{timestamp}
        """
        # Create slug from first few words of description
        words = re.sub(r"[^a-z0-9\s]", "", description.lower()).split()[:4]
        slug = "-".join(words) if words else "unknown"
        slug = slug[:30]  # Limit length

        # Add timestamp for uniqueness
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        return f"bug-{slug}-{timestamp}"

    # =========================================================================
    # Bug Lifecycle Operations
    # =========================================================================

    def init_bug(
        self,
        description: str,
        bug_id: Optional[str] = None,
        test_path: Optional[str] = None,
        github_issue: Optional[int] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> BugPipelineResult:
        """
        Initialize a new bug investigation.

        Creates the bug state and saves initial report.

        Args:
            description: Bug description (required).
            bug_id: Optional custom bug ID.
            test_path: Optional path to failing test.
            github_issue: Optional GitHub issue number.
            error_message: Optional error message.
            stack_trace: Optional stack trace.

        Returns:
            BugPipelineResult with created bug_id.
        """
        # Generate or use provided bug_id
        if not bug_id:
            bug_id = self._generate_bug_id(description)

        # Check if bug already exists
        if self._state_store.exists(bug_id):
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=f"Bug '{bug_id}' already exists",
            )

        # Create bug state
        state = BugState.create(
            bug_id=bug_id,
            description=description,
            test_path=test_path,
            github_issue=github_issue,
            error_message=error_message,
            stack_trace=stack_trace,
        )

        # Save state and report
        self._state_store.save(state)
        self._state_store.write_report(state)

        self._log("bug_created", {"bug_id": bug_id})

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.CREATED,
            cost_usd=0.0,
            message=f"Bug investigation '{bug_id}' created",
        )

    def analyze(
        self,
        bug_id: str,
        max_cost_usd: float = 10.0,
        progress_callback: Optional[Callable[[str, int, int, Optional[str]], None]] = None,
    ) -> BugPipelineResult:
        """
        Run the full analysis pipeline: Reproduce → Analyze → Plan.

        The pipeline stops at PLANNED phase, requiring human approval
        before implementation.

        Args:
            bug_id: The bug identifier.
            max_cost_usd: Maximum cost before aborting.
            progress_callback: Optional callback for progress updates.
                Called with (step_name, step_number, total_steps, detail_message).

        Returns:
            BugPipelineResult with final phase and cost.
        """
        def _progress(step: str, num: int, detail: Optional[str] = None) -> None:
            """Emit progress update."""
            if progress_callback:
                progress_callback(step, num, 3, detail)
        # Load state
        try:
            state = self._state_store.load(bug_id)
        except BugNotFoundError as e:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=str(e),
            )

        # Validate phase
        if state.phase not in (BugPhase.CREATED, BugPhase.BLOCKED):
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error=f"Cannot analyze bug in phase {state.phase.value}. Must be CREATED or BLOCKED.",
            )

        total_cost = 0.0

        # Step 1: Reproduction
        _progress("Reproducing bug", 1, "Running tests and gathering evidence...")
        self._log("reproduction_start", {"bug_id": bug_id})
        state.transition_to(BugPhase.REPRODUCING, "auto")
        self._state_store.save(state)

        self.researcher.reset()
        repro_result = self.researcher.run({
            "bug_id": bug_id,
            "report": state.report,
        })

        total_cost += repro_result.cost_usd
        state.add_cost(AgentCost.create("bug_researcher", cost_usd=repro_result.cost_usd))

        if not repro_result.success:
            state.blocked_reason = repro_result.errors[0] if repro_result.errors else "Reproduction failed"
            state.transition_to(BugPhase.BLOCKED, "agent_output")
            self._state_store.save(state)
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.BLOCKED,
                cost_usd=total_cost,
                error=state.blocked_reason,
            )

        state.reproduction = repro_result.output

        # Check if bug was confirmed
        if not state.reproduction.confirmed:
            state.transition_to(BugPhase.NOT_REPRODUCIBLE, "agent_output")
            self._state_store.save(state)
            self._state_store.write_reproduction_report(state)
            return BugPipelineResult(
                success=True,
                bug_id=bug_id,
                phase=BugPhase.NOT_REPRODUCIBLE,
                cost_usd=total_cost,
                message="Bug could not be reproduced",
            )

        state.transition_to(BugPhase.REPRODUCED, "agent_output")
        self._state_store.save(state)
        self._state_store.write_reproduction_report(state)

        # Check cost limit
        if total_cost > max_cost_usd:
            state.blocked_reason = f"Cost limit exceeded: ${total_cost:.2f} > ${max_cost_usd:.2f}"
            state.transition_to(BugPhase.BLOCKED, "auto")
            self._state_store.save(state)
            raise CostLimitExceededError(state.blocked_reason)

        # Step 2: Root Cause Analysis
        _progress("Analyzing root cause", 2, "Identifying why the bug occurs...")
        self._log("analysis_start", {"bug_id": bug_id})
        state.transition_to(BugPhase.ANALYZING, "auto")
        self._state_store.save(state)

        self.analyzer.reset()
        analysis_result = self.analyzer.run({
            "bug_id": bug_id,
            "report": state.report,
            "reproduction": state.reproduction,
        })

        total_cost += analysis_result.cost_usd
        state.add_cost(AgentCost.create("root_cause_analyzer", cost_usd=analysis_result.cost_usd))

        if not analysis_result.success:
            state.blocked_reason = analysis_result.errors[0] if analysis_result.errors else "Analysis failed"
            state.transition_to(BugPhase.BLOCKED, "agent_output")
            self._state_store.save(state)
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.BLOCKED,
                cost_usd=total_cost,
                error=state.blocked_reason,
            )

        state.root_cause = analysis_result.output
        state.transition_to(BugPhase.ANALYZED, "agent_output")
        self._state_store.save(state)
        self._state_store.write_root_cause_report(state)

        # Check cost limit
        if total_cost > max_cost_usd:
            state.blocked_reason = f"Cost limit exceeded: ${total_cost:.2f} > ${max_cost_usd:.2f}"
            state.transition_to(BugPhase.BLOCKED, "auto")
            self._state_store.save(state)
            raise CostLimitExceededError(state.blocked_reason)

        # Step 3: Fix Planning
        _progress("Planning fix", 3, "Designing implementation strategy...")
        self._log("planning_start", {"bug_id": bug_id})
        state.transition_to(BugPhase.PLANNING, "auto")
        self._state_store.save(state)

        self.planner.reset()
        plan_result = self.planner.run({
            "bug_id": bug_id,
            "report": state.report,
            "reproduction": state.reproduction,
            "root_cause": state.root_cause,
        })

        total_cost += plan_result.cost_usd
        state.add_cost(AgentCost.create("fix_planner", cost_usd=plan_result.cost_usd))

        if not plan_result.success:
            state.blocked_reason = plan_result.errors[0] if plan_result.errors else "Planning failed"
            state.transition_to(BugPhase.BLOCKED, "agent_output")
            self._state_store.save(state)
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.BLOCKED,
                cost_usd=total_cost,
                error=state.blocked_reason,
            )

        state.fix_plan = plan_result.output
        state.transition_to(BugPhase.PLANNED, "agent_output")
        self._state_store.save(state)
        self._state_store.write_fix_plan_report(state)

        self._log(
            "analysis_complete",
            {
                "bug_id": bug_id,
                "cost_usd": total_cost,
                "fix_risk": state.fix_plan.risk_level,
            },
        )

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.PLANNED,
            cost_usd=total_cost,
            message=f"Analysis complete. Fix plan ready for approval. Risk: {state.fix_plan.risk_level}",
        )

    def approve(
        self,
        bug_id: str,
        approved_by: Optional[str] = None,
    ) -> BugPipelineResult:
        """
        Approve the fix plan for implementation.

        This is the human gate before implementation proceeds.

        Args:
            bug_id: The bug identifier.
            approved_by: Who approved (defaults to USER from env).

        Returns:
            BugPipelineResult with approval status.
        """
        # Load state
        try:
            state = self._state_store.load(bug_id)
        except BugNotFoundError as e:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=str(e),
            )

        # Validate phase
        if state.phase != BugPhase.PLANNED:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error=f"Cannot approve bug in phase {state.phase.value}. Must be PLANNED.",
            )

        # Require fix plan
        if not state.fix_plan:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error="No fix plan available to approve",
            )

        # Create approval record
        if not approved_by:
            approved_by = os.environ.get("USER", "unknown")

        state.approval_record = ApprovalRecord.create(approved_by, state.fix_plan)
        state.transition_to(BugPhase.APPROVED, "user_command")
        self._state_store.save(state)
        self._state_store.append_transition(bug_id, state.transitions[-1])

        self._log(
            "bug_approved",
            {
                "bug_id": bug_id,
                "approved_by": approved_by,
                "fix_plan_hash": state.approval_record.fix_plan_hash,
            },
        )

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.APPROVED,
            cost_usd=0.0,
            message=f"Fix plan approved by {approved_by}. Ready for implementation.",
        )

    def reject(
        self,
        bug_id: str,
        reason: str,
    ) -> BugPipelineResult:
        """
        Reject the bug (won't fix).

        Args:
            bug_id: The bug identifier.
            reason: Why the bug won't be fixed.

        Returns:
            BugPipelineResult with rejection status.
        """
        # Load state
        try:
            state = self._state_store.load(bug_id)
        except BugNotFoundError as e:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=str(e),
            )

        # Can reject from most phases
        if state.phase in (BugPhase.FIXED, BugPhase.WONT_FIX):
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error=f"Cannot reject bug in final phase {state.phase.value}",
            )

        state.rejection_reason = reason
        state.transition_to(BugPhase.WONT_FIX, "user_command", {"reason": reason})
        self._state_store.save(state)

        self._log(
            "bug_rejected",
            {"bug_id": bug_id, "reason": reason},
        )

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.WONT_FIX,
            cost_usd=0.0,
            message=f"Bug marked as won't fix: {reason}",
        )

    def fix(
        self,
        bug_id: str,
        max_cost_usd: float = 10.0,
    ) -> BugPipelineResult:
        """
        Execute the approved fix plan.

        This applies the fix and runs verification tests.
        REQUIRES prior approval via approve().

        Args:
            bug_id: The bug identifier.
            max_cost_usd: Maximum cost for implementation.

        Returns:
            BugPipelineResult with implementation status.
        """
        # Load state
        try:
            state = self._state_store.load(bug_id)
        except BugNotFoundError as e:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=str(e),
            )

        # CRITICAL: Require approval
        if state.phase != BugPhase.APPROVED:
            if state.phase == BugPhase.PLANNED:
                raise ApprovalRequiredError(
                    f"Bug '{bug_id}' requires approval before implementation. "
                    "Run 'swarm-attack bug approve {bug_id}' first."
                )
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error=f"Cannot fix bug in phase {state.phase.value}. Must be APPROVED.",
            )

        if not state.approval_record:
            raise ApprovalRequiredError(f"Bug '{bug_id}' has no approval record")

        if not state.fix_plan:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error="No fix plan available",
            )

        # Verify fix plan hasn't changed since approval
        current_hash = state.fix_plan.get_hash()
        if current_hash != state.approval_record.fix_plan_hash:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error="Fix plan has changed since approval. Re-approval required.",
            )

        self._log("implementation_start", {"bug_id": bug_id})
        state.transition_to(BugPhase.IMPLEMENTING, "auto")
        self._state_store.save(state)

        # Execute fix (simplified implementation)
        # In a full implementation, this would use a CoderAgent
        files_changed = []
        try:
            for change in state.fix_plan.changes:
                if change.change_type == "modify" and change.current_code and change.proposed_code:
                    # Read file
                    file_path = Path(self.config.repo_root) / change.file_path
                    if file_path.exists():
                        content = file_path.read_text()
                        # Apply change (simple replace)
                        new_content = content.replace(change.current_code, change.proposed_code)
                        if content != new_content:
                            file_path.write_text(new_content)
                            files_changed.append(change.file_path)

            # Run verification tests
            state.transition_to(BugPhase.VERIFYING, "auto")
            self._state_store.save(state)

            # Run pytest on original test if provided
            test_passed = True
            test_output = ""
            if state.report.test_path:
                try:
                    result = subprocess.run(
                        ["pytest", state.report.test_path, "-v"],
                        cwd=self.config.repo_root,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    test_output = result.stdout + result.stderr
                    test_passed = result.returncode == 0
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    test_output = str(e)
                    test_passed = False

            if test_passed:
                from swarm_attack.bug_models import ImplementationResult
                state.implementation = ImplementationResult(
                    success=True,
                    files_changed=files_changed,
                    tests_passed=1,
                    tests_failed=0,
                )
                state.transition_to(BugPhase.FIXED, "auto")
                self._state_store.save(state)

                self._log(
                    "bug_fixed",
                    {
                        "bug_id": bug_id,
                        "files_changed": len(files_changed),
                    },
                )

                return BugPipelineResult(
                    success=True,
                    bug_id=bug_id,
                    phase=BugPhase.FIXED,
                    cost_usd=0.0,
                    message=f"Bug fixed! {len(files_changed)} files changed.",
                )

            else:
                from swarm_attack.bug_models import ImplementationResult
                state.implementation = ImplementationResult(
                    success=False,
                    files_changed=files_changed,
                    tests_passed=0,
                    tests_failed=1,
                    error=test_output[:500],
                )
                state.blocked_reason = f"Tests failed after fix: {test_output[:200]}"
                state.transition_to(BugPhase.BLOCKED, "auto")
                self._state_store.save(state)

                return BugPipelineResult(
                    success=False,
                    bug_id=bug_id,
                    phase=BugPhase.BLOCKED,
                    cost_usd=0.0,
                    error=state.blocked_reason,
                )

        except Exception as e:
            state.blocked_reason = f"Implementation error: {e}"
            state.transition_to(BugPhase.BLOCKED, "auto")
            self._state_store.save(state)

            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.BLOCKED,
                cost_usd=0.0,
                error=state.blocked_reason,
            )

    # =========================================================================
    # Status and Listing
    # =========================================================================

    def get_status(self, bug_id: str) -> Optional[BugState]:
        """Get the current state of a bug."""
        try:
            return self._state_store.load(bug_id)
        except BugNotFoundError:
            return None

    def list_bugs(
        self,
        phase: Optional[BugPhase] = None,
    ) -> list[str]:
        """List all bug IDs, optionally filtered by phase."""
        return self._state_store.list_all(phase)

    def unblock(self, bug_id: str) -> BugPipelineResult:
        """
        Reset a blocked bug to CREATED phase for re-analysis.

        Args:
            bug_id: The bug identifier.

        Returns:
            BugPipelineResult with status.
        """
        try:
            state = self._state_store.load(bug_id)
        except BugNotFoundError as e:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=BugPhase.CREATED,
                cost_usd=0.0,
                error=str(e),
            )

        if state.phase != BugPhase.BLOCKED:
            return BugPipelineResult(
                success=False,
                bug_id=bug_id,
                phase=state.phase,
                cost_usd=0.0,
                error=f"Bug is not blocked (current phase: {state.phase.value})",
            )

        # Reset to CREATED for re-analysis
        # We manually update phase since BLOCKED → CREATED is allowed via unblock
        state.phase = BugPhase.CREATED
        state.blocked_reason = None
        state.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._state_store.save(state)

        self._log("bug_unblocked", {"bug_id": bug_id})

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.CREATED,
            cost_usd=0.0,
            message=f"Bug unblocked and reset to CREATED. Run 'swarm-attack bug analyze {bug_id}' to re-analyze.",
        )
