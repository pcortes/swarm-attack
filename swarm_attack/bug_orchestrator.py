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

from swarm_attack.agents.bug_critic import BugCriticAgent
from swarm_attack.agents.bug_fixer import BugFixerAgent
from swarm_attack.agents.bug_moderator import BugModeratorAgent
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
    DebateHistory,
    DebateIssue,
    FixPlan,
    FixPlanDebateResult,
    InvalidPhaseError,
    RootCauseAnalysis,
    RootCauseDebateResult,
)
from swarm_attack.bug_state_store import BugStateStore
from swarm_attack.debate_retry import DebateRetryHandler
from swarm_attack.events.bus import get_event_bus
from swarm_attack.events.types import EventType, SwarmEvent

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
        critic: Optional[BugCriticAgent] = None,
        moderator: Optional[BugModeratorAgent] = None,
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
            critic: Optional Bug Critic agent (created if not provided).
            moderator: Optional Bug Moderator agent (created if not provided).
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
        self._critic = critic
        self._moderator = moderator

        # Debate retry handler for transient error recovery
        retry_config = getattr(config, 'debate_retry', None)
        if retry_config:
            self._debate_retry_handler = DebateRetryHandler(
                max_retries=retry_config.max_retries,
                backoff_base_seconds=retry_config.backoff_base_seconds,
                backoff_multiplier=retry_config.backoff_multiplier,
            )
        else:
            self._debate_retry_handler = DebateRetryHandler()

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

    @property
    def critic(self) -> BugCriticAgent:
        """Get the Bug Critic agent (lazy init)."""
        if self._critic is None:
            self._critic = BugCriticAgent(self.config, self._logger)
        return self._critic

    @property
    def moderator(self) -> BugModeratorAgent:
        """Get the Bug Moderator agent (lazy init)."""
        if self._moderator is None:
            self._moderator = BugModeratorAgent(self.config, self._logger)
        return self._moderator

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

    def _emit_bug_event(
        self,
        event_type: EventType,
        bug_id: str,
        payload: Optional[dict] = None,
        confidence: float = 0.0,
    ) -> SwarmEvent:
        """
        Emit a bug lifecycle event.

        Args:
            event_type: The type of event (from EventType enum).
            bug_id: The bug being tracked.
            payload: Additional data for the event.
            confidence: Confidence score for auto-approval decisions.

        Returns:
            The emitted SwarmEvent.
        """
        bugs_path = Path(self.config.repo_root) / ".swarm"
        bus = get_event_bus(bugs_path)

        event = SwarmEvent(
            event_type=event_type,
            bug_id=bug_id,
            source_agent="BugOrchestrator",
            payload=payload or {},
            confidence=confidence,
        )
        bus.emit(event)

        self._log(
            "bug_event_emitted",
            {
                "event_type": event_type.value,
                "bug_id": bug_id,
                "event_id": event.event_id,
            },
        )

        return event

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
    # Debate Layer Methods
    # =========================================================================

    def _run_root_cause_debate(
        self,
        state: BugState,
        progress_callback: Optional[Callable[[str, int, int, Optional[str]], None]] = None,
    ) -> tuple[RootCauseAnalysis, float]:
        """
        Run debate loop to refine root cause analysis.

        Args:
            state: Current bug state with root_cause.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (improved_root_cause, total_debate_cost)
        """
        debate_config = self.config.bug_bash.debate
        if not debate_config.enabled:
            self._log("debate_skipped", {"reason": "disabled_in_config"})
            return state.root_cause, 0.0

        if not state.root_cause:
            self._log("debate_skipped", {"reason": "no_root_cause"})
            return state.root_cause, 0.0

        # Initialize debate history if needed
        if not state.debate_history:
            state.debate_history = DebateHistory()

        current_root_cause = state.root_cause
        total_cost = 0.0
        max_rounds = debate_config.max_rounds
        thresholds = debate_config.root_cause_thresholds

        self._log("root_cause_debate_start", {
            "bug_id": state.bug_id,
            "max_rounds": max_rounds,
            "thresholds": thresholds,
        })

        for round_num in range(1, max_rounds + 1):
            self._log("root_cause_debate_round_start", {
                "round": round_num,
                "bug_id": state.bug_id,
            })

            if progress_callback:
                progress_callback(
                    f"Debating root cause (round {round_num}/{max_rounds})",
                    2, 3,
                    f"Critic reviewing analysis..."
                )

            # Step 1: Critic reviews the analysis (with retry for transient errors)
            critic_retry_result = self._debate_retry_handler.run_with_retry(
                self.critic,
                {
                    "bug_id": state.bug_id,
                    "mode": "root_cause",
                    "root_cause": current_root_cause,
                    "bug_description": state.report.description,
                    "reproduction_summary": state.reproduction.notes if state.reproduction else "",
                },
            )

            if not critic_retry_result.success:
                # Critic failed (auth error or exhausted retries) - stop debate
                self._log("root_cause_debate_critic_failed", {
                    "error": critic_retry_result.errors[0] if critic_retry_result.errors else "Unknown",
                    "round": round_num,
                    "retry_count": critic_retry_result.retry_count,
                })
                # Return current analysis without improvement
                break

            total_cost += critic_retry_result.cost_usd
            review = critic_retry_result.output

            # Build debate result
            issues = [
                DebateIssue(
                    severity=i.get("severity", "minor"),
                    description=i.get("description", ""),
                    suggestion=i.get("suggestion", ""),
                )
                for i in review.get("issues", [])
            ]

            debate_result = RootCauseDebateResult(
                round_number=round_num,
                scores=review.get("scores", {}),
                issues=issues,
                recommendation=review.get("recommendation", "REVISE"),
                critic_cost_usd=critic_retry_result.cost_usd,
            )

            # Check if we meet thresholds
            meets_thresholds = debate_result.meets_thresholds(thresholds)
            no_critical = debate_result.critical_issue_count == 0
            few_moderate = debate_result.moderate_issue_count < 2

            self._log("root_cause_debate_critic_complete", {
                "round": round_num,
                "scores": review.get("scores", {}),
                "critical_issues": debate_result.critical_issue_count,
                "moderate_issues": debate_result.moderate_issue_count,
                "meets_thresholds": meets_thresholds,
                "recommendation": review.get("recommendation"),
            })

            # If all conditions met, we're done
            if meets_thresholds and no_critical and few_moderate:
                debate_result.continue_debate = False
                state.debate_history.root_cause_rounds.append(debate_result)
                self._log("root_cause_debate_success", {
                    "round": round_num,
                    "final_scores": review.get("scores"),
                })
                break

            # Otherwise, run moderator to improve
            if progress_callback:
                progress_callback(
                    f"Debating root cause (round {round_num}/{max_rounds})",
                    2, 3,
                    f"Moderator improving analysis..."
                )

            # Moderator with retry for transient errors
            moderator_retry_result = self._debate_retry_handler.run_with_retry(
                self.moderator,
                {
                    "bug_id": state.bug_id,
                    "mode": "root_cause",
                    "root_cause": current_root_cause,
                    "review": review,
                    "bug_description": state.report.description,
                    "reproduction_summary": state.reproduction.notes if state.reproduction else "",
                    "round": round_num,
                },
            )

            total_cost += moderator_retry_result.cost_usd
            debate_result.moderator_cost_usd = moderator_retry_result.cost_usd

            if moderator_retry_result.success:
                improved = moderator_retry_result.output.get("improved_content", {})
                if improved:
                    # Update root cause with improvements
                    current_root_cause = RootCauseAnalysis(
                        summary=improved.get("summary", current_root_cause.summary),
                        execution_trace=improved.get("execution_trace", current_root_cause.execution_trace),
                        root_cause_file=improved.get("root_cause_file", current_root_cause.root_cause_file),
                        root_cause_line=improved.get("root_cause_line", current_root_cause.root_cause_line),
                        root_cause_code=improved.get("root_cause_code", current_root_cause.root_cause_code),
                        root_cause_explanation=improved.get("root_cause_explanation", current_root_cause.root_cause_explanation),
                        why_not_caught=improved.get("why_not_caught", current_root_cause.why_not_caught),
                        confidence=improved.get("confidence", current_root_cause.confidence),
                        alternative_hypotheses=improved.get("alternative_hypotheses", current_root_cause.alternative_hypotheses),
                    )
                debate_result.improvements = moderator_retry_result.output.get("improvements", [])

            state.debate_history.root_cause_rounds.append(debate_result)

            self._log("root_cause_debate_round_complete", {
                "round": round_num,
                "cost": debate_result.total_cost_usd,
            })

        self._log("root_cause_debate_complete", {
            "total_rounds": len(state.debate_history.root_cause_rounds),
            "total_cost": total_cost,
            "final_scores": state.debate_history.root_cause_final_scores,
        })

        return current_root_cause, total_cost

    def _run_fix_plan_debate(
        self,
        state: BugState,
        progress_callback: Optional[Callable[[str, int, int, Optional[str]], None]] = None,
    ) -> tuple[FixPlan, float]:
        """
        Run debate loop to refine fix plan.

        Args:
            state: Current bug state with fix_plan.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (improved_fix_plan, total_debate_cost)
        """
        debate_config = self.config.bug_bash.debate
        if not debate_config.enabled:
            self._log("debate_skipped", {"reason": "disabled_in_config"})
            return state.fix_plan, 0.0

        if not state.fix_plan:
            self._log("debate_skipped", {"reason": "no_fix_plan"})
            return state.fix_plan, 0.0

        # Initialize debate history if needed
        if not state.debate_history:
            state.debate_history = DebateHistory()

        current_fix_plan = state.fix_plan
        total_cost = 0.0
        max_rounds = debate_config.max_rounds
        thresholds = debate_config.fix_plan_thresholds

        self._log("fix_plan_debate_start", {
            "bug_id": state.bug_id,
            "max_rounds": max_rounds,
            "thresholds": thresholds,
        })

        for round_num in range(1, max_rounds + 1):
            self._log("fix_plan_debate_round_start", {
                "round": round_num,
                "bug_id": state.bug_id,
            })

            if progress_callback:
                progress_callback(
                    f"Debating fix plan (round {round_num}/{max_rounds})",
                    3, 3,
                    f"Critic reviewing plan..."
                )

            # Step 1: Critic reviews the plan (with retry for transient errors)
            critic_retry_result = self._debate_retry_handler.run_with_retry(
                self.critic,
                {
                    "bug_id": state.bug_id,
                    "mode": "fix_plan",
                    "fix_plan": current_fix_plan,
                    "bug_description": state.report.description,
                    "root_cause_summary": state.root_cause.summary if state.root_cause else "",
                },
            )

            if not critic_retry_result.success:
                # Critic failed - stop debate
                self._log("fix_plan_debate_critic_failed", {
                    "error": critic_retry_result.errors[0] if critic_retry_result.errors else "Unknown",
                    "round": round_num,
                    "retry_count": critic_retry_result.retry_count,
                })
                break

            total_cost += critic_retry_result.cost_usd
            review = critic_retry_result.output

            # Build debate result
            issues = [
                DebateIssue(
                    severity=i.get("severity", "minor"),
                    description=i.get("description", ""),
                    suggestion=i.get("suggestion", ""),
                )
                for i in review.get("issues", [])
            ]

            debate_result = FixPlanDebateResult(
                round_number=round_num,
                scores=review.get("scores", {}),
                issues=issues,
                recommendation=review.get("recommendation", "REVISE"),
                critic_cost_usd=critic_retry_result.cost_usd,
            )

            # Check if we meet thresholds
            meets_thresholds = debate_result.meets_thresholds(thresholds)
            no_critical = debate_result.critical_issue_count == 0
            few_moderate = debate_result.moderate_issue_count < 2

            self._log("fix_plan_debate_critic_complete", {
                "round": round_num,
                "scores": review.get("scores", {}),
                "critical_issues": debate_result.critical_issue_count,
                "moderate_issues": debate_result.moderate_issue_count,
                "meets_thresholds": meets_thresholds,
                "recommendation": review.get("recommendation"),
            })

            # If all conditions met, we're done
            if meets_thresholds and no_critical and few_moderate:
                debate_result.continue_debate = False
                state.debate_history.fix_plan_rounds.append(debate_result)
                self._log("fix_plan_debate_success", {
                    "round": round_num,
                    "final_scores": review.get("scores"),
                })
                break

            # Otherwise, run moderator to improve
            if progress_callback:
                progress_callback(
                    f"Debating fix plan (round {round_num}/{max_rounds})",
                    3, 3,
                    f"Moderator improving plan..."
                )

            # Moderator with retry for transient errors
            moderator_retry_result = self._debate_retry_handler.run_with_retry(
                self.moderator,
                {
                    "bug_id": state.bug_id,
                    "mode": "fix_plan",
                    "fix_plan": current_fix_plan,
                    "review": review,
                    "bug_description": state.report.description,
                    "root_cause_summary": state.root_cause.summary if state.root_cause else "",
                    "round": round_num,
                },
            )

            total_cost += moderator_retry_result.cost_usd
            debate_result.moderator_cost_usd = moderator_retry_result.cost_usd

            if moderator_retry_result.success:
                improved = moderator_retry_result.output.get("improved_content", {})
                if improved:
                    # Update fix plan with improvements
                    from swarm_attack.bug_models import FileChange, TestCase
                    changes = [
                        FileChange(
                            file_path=c.get("file_path", ""),
                            change_type=c.get("change_type", "modify"),
                            current_code=c.get("current_code"),
                            proposed_code=c.get("proposed_code"),
                            explanation=c.get("explanation", ""),
                        )
                        for c in improved.get("changes", [])
                    ] if improved.get("changes") else current_fix_plan.changes

                    test_cases = [
                        TestCase(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            test_code=t.get("test_code", ""),
                            category=t.get("category", "regression"),
                        )
                        for t in improved.get("test_cases", [])
                    ] if improved.get("test_cases") else current_fix_plan.test_cases

                    current_fix_plan = FixPlan(
                        summary=improved.get("summary", current_fix_plan.summary),
                        changes=changes,
                        test_cases=test_cases,
                        risk_level=improved.get("risk_level", current_fix_plan.risk_level),
                        risk_explanation=improved.get("risk_explanation", current_fix_plan.risk_explanation),
                        scope=improved.get("scope", current_fix_plan.scope),
                        side_effects=improved.get("side_effects", current_fix_plan.side_effects),
                        rollback_plan=improved.get("rollback_plan", current_fix_plan.rollback_plan),
                        estimated_effort=improved.get("estimated_effort", current_fix_plan.estimated_effort),
                    )
                debate_result.improvements = moderator_retry_result.output.get("improvements", [])

            state.debate_history.fix_plan_rounds.append(debate_result)

            self._log("fix_plan_debate_round_complete", {
                "round": round_num,
                "cost": debate_result.total_cost_usd,
            })

        self._log("fix_plan_debate_complete", {
            "total_rounds": len(state.debate_history.fix_plan_rounds),
            "total_cost": total_cost,
            "final_scores": state.debate_history.fix_plan_final_scores,
        })

        return current_fix_plan, total_cost

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

        # Emit BUG_DETECTED event
        self._emit_bug_event(
            EventType.BUG_DETECTED,
            bug_id,
            payload={"description": description, "test_path": test_path},
        )

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

        # Emit BUG_REPRODUCED event
        self._emit_bug_event(EventType.BUG_REPRODUCED, bug_id)

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

        # Run root cause debate to refine the analysis
        improved_root_cause, debate_cost = self._run_root_cause_debate(state, progress_callback)
        if improved_root_cause != state.root_cause:
            state.root_cause = improved_root_cause
        total_cost += debate_cost
        state.add_cost(AgentCost.create("root_cause_debate", cost_usd=debate_cost))

        state.transition_to(BugPhase.ANALYZED, "agent_output")
        self._state_store.save(state)
        self._state_store.write_root_cause_report(state)

        # Emit BUG_ANALYZED event
        self._emit_bug_event(
            EventType.BUG_ANALYZED,
            bug_id,
            payload={"confidence": state.root_cause.confidence if state.root_cause else 0.0},
            confidence=state.root_cause.confidence if state.root_cause else 0.0,
        )

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

        # Run fix plan debate to refine the plan
        improved_fix_plan, fix_debate_cost = self._run_fix_plan_debate(state, progress_callback)
        if improved_fix_plan != state.fix_plan:
            state.fix_plan = improved_fix_plan
        total_cost += fix_debate_cost
        state.add_cost(AgentCost.create("fix_plan_debate", cost_usd=fix_debate_cost))

        state.transition_to(BugPhase.PLANNED, "agent_output")
        self._state_store.save(state)
        self._state_store.write_fix_plan_report(state)

        # Emit BUG_PLANNED event - ready for approval
        self._emit_bug_event(
            EventType.BUG_PLANNED,
            bug_id,
            payload={"risk_level": state.fix_plan.risk_level if state.fix_plan else "unknown"},
        )

        # Calculate debate scores for summary
        debate_summary = ""
        if state.debate_history:
            if state.debate_history.root_cause_final_scores:
                rc_avg = sum(state.debate_history.root_cause_final_scores.values()) / len(state.debate_history.root_cause_final_scores)
                debate_summary += f" RC score: {rc_avg:.2f}."
            if state.debate_history.fix_plan_final_scores:
                fp_avg = sum(state.debate_history.fix_plan_final_scores.values()) / len(state.debate_history.fix_plan_final_scores)
                debate_summary += f" Fix score: {fp_avg:.2f}."

        self._log(
            "analysis_complete",
            {
                "bug_id": bug_id,
                "cost_usd": total_cost,
                "fix_risk": state.fix_plan.risk_level,
                "debate_rounds": {
                    "root_cause": len(state.debate_history.root_cause_rounds) if state.debate_history else 0,
                    "fix_plan": len(state.debate_history.fix_plan_rounds) if state.debate_history else 0,
                },
            },
        )

        return BugPipelineResult(
            success=True,
            bug_id=bug_id,
            phase=BugPhase.PLANNED,
            cost_usd=total_cost,
            message=f"Analysis complete. Fix plan ready for approval. Risk: {state.fix_plan.risk_level}.{debate_summary}",
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

        # Emit BUG_APPROVED event
        self._emit_bug_event(
            EventType.BUG_APPROVED,
            bug_id,
            payload={"approved_by": approved_by},
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

        # Execute fix using BugFixerAgent (intelligent LLM-based fix application)
        # This replaces the old "simplified" string-replace implementation that was
        # fragile (required exact string matches) and couldn't handle formatting issues.
        files_changed = []
        agent_cost = 0.0
        try:
            fixer = BugFixerAgent(self.config, logger=self._logger)
            fixer_result = fixer.run({
                "fix_plan": state.fix_plan,
                "bug_id": bug_id,
            })

            agent_cost = fixer_result.cost_usd

            if fixer_result.success:
                files_changed = fixer_result.output.get("files_changed", [])
                self._log("bug_fixer_success", {
                    "bug_id": bug_id,
                    "files_changed": files_changed,
                    "syntax_verified": fixer_result.output.get("syntax_verified", False),
                })
            else:
                # Agent failed - fall back to blocked state
                state.blocked_reason = f"BugFixerAgent failed: {fixer_result.error}"
                state.transition_to(BugPhase.BLOCKED, "auto")
                self._state_store.save(state)

                return BugPipelineResult(
                    success=False,
                    bug_id=bug_id,
                    phase=BugPhase.BLOCKED,
                    cost_usd=agent_cost,
                    error=state.blocked_reason,
                )

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

                # Emit BUG_FIXED event
                self._emit_bug_event(
                    EventType.BUG_FIXED,
                    bug_id,
                    payload={"files_changed": files_changed},
                )

                return BugPipelineResult(
                    success=True,
                    bug_id=bug_id,
                    phase=BugPhase.FIXED,
                    cost_usd=agent_cost,
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
                    cost_usd=agent_cost,
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
                cost_usd=agent_cost,
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
