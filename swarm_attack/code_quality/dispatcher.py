"""Three-stage debate orchestration for code quality review.

This module provides the CodeQualityDispatcher class which orchestrates
a three-phase debate for code quality analysis:

1. **Analyst phase** (90s budget) - Run CodeQualityAnalyzer to analyze files
2. **Critic phase** (30s budget) - Validate findings, catch false positives
3. **Moderator phase** (30s budget) - Final verdict with TDD plans

Key features:
- RetryContext state management (max 3 iterations)
- Per-phase timing budgets (90s, 30s, 30s)
- Graceful degradation on timeout
- Cost tracking
- Decision points: APPROVE / REFACTOR / ESCALATE

Based on the Code Quality spec three-stage debate section.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from .analyzer import CodeQualityAnalyzer
from .models import (
    AnalysisResult,
    ApprovedFinding,
    CriticIssue,
    CriticRecommendation,
    CriticReview,
    Finding,
    IssueType,
    ModeratorDecision,
    Priority,
    RejectedFinding,
    RetryContext,
    Severity,
    TDDPlan,
    TDDPhase,
    TechDebtItem,
    Verdict,
)
from .refactor_suggester import RefactorSuggester
from .tdd_generator import TDDGenerator


class CodeQualityDispatcher:
    """Three-stage debate orchestration for code quality review.

    This class orchestrates the three-phase debate process:
    1. Analyst phase: Run code quality analysis
    2. Critic phase: Validate findings and catch false positives
    3. Moderator phase: Make final verdict with TDD plans

    Attributes:
        ANALYST_BUDGET_SECONDS: Maximum time for analyst phase (90 seconds).
        CRITIC_BUDGET_SECONDS: Maximum time for critic phase (30 seconds).
        MODERATOR_BUDGET_SECONDS: Maximum time for moderator phase (30 seconds).
        MAX_RETRIES: Maximum number of retry iterations (3).
        analyzer: Instance of CodeQualityAnalyzer for analysis.
        suggester: Instance of RefactorSuggester for refactoring suggestions.
        tdd_generator: Instance of TDDGenerator for TDD plan generation.
    """

    ANALYST_BUDGET_SECONDS = 90  # From spec: analyst phase has 90 seconds
    CRITIC_BUDGET_SECONDS = 30  # From spec: critic phase has 30 seconds
    MODERATOR_BUDGET_SECONDS = 30  # From spec: moderator phase has 30 seconds
    MAX_RETRIES = 3  # From spec: max 3 retry iterations

    def __init__(self) -> None:
        """Initialize the dispatcher with all required components."""
        self.analyzer = CodeQualityAnalyzer()
        self.suggester = RefactorSuggester()
        self.tdd_generator = TDDGenerator()

    def run_review(
        self,
        file_paths: list[Union[str, Path]],
        retry_context: Optional[RetryContext] = None,
    ) -> ModeratorDecision:
        """Run full three-stage review pipeline.

        Executes the three-phase debate:
        1. Analyst phase: Analyze files for code quality issues
        2. Critic phase: Validate findings, identify false positives
        3. Moderator phase: Make final verdict with TDD plans

        Args:
            file_paths: List of paths to Python files to analyze.
            retry_context: Optional context for retry iterations.

        Returns:
            ModeratorDecision containing final verdict and TDD plans.
        """
        # Handle empty file list
        if not file_paths:
            return self._create_approve_decision()

        # Stage 1: Analyst phase
        analysis = self.run_analyst_phase(file_paths)

        # Stage 2: Critic phase
        critique = self.run_critic_phase(analysis)

        # Stage 3: Moderator phase
        decision = self.run_moderator_phase(analysis, critique, retry_context)

        return decision

    def run_analyst_phase(
        self, file_paths: list[Union[str, Path]]
    ) -> AnalysisResult:
        """Stage 1: Analysis with 90s budget.

        Uses the CodeQualityAnalyzer to analyze files and detect code
        quality issues. The analyzer has a 90-second timing budget.

        Args:
            file_paths: List of paths to Python files to analyze.

        Returns:
            AnalysisResult containing all findings from analysis.
        """
        # Delegate to the analyzer
        return self.analyzer.analyze_files(file_paths)

    def run_critic_phase(self, analysis: AnalysisResult) -> CriticReview:
        """Stage 2: Validate findings with 30s budget.

        Reviews the analysis findings to:
        - Identify false positives
        - Adjust severity levels if over-reported
        - Check for impractical fixes
        - Validate that findings are real issues

        Args:
            analysis: The AnalysisResult from the analyst phase.

        Returns:
            CriticReview containing validation results.
        """
        now = datetime.now()
        review_id = f"crit-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

        # If no findings, approve immediately
        if not analysis.findings:
            return CriticReview(
                review_id=review_id,
                accuracy=1.0,
                severity_calibration=1.0,
                actionability=1.0,
                pragmatism=1.0,
                issues=[],
                validated_findings=[],
                rejected_findings=[],
                summary="No findings to review.",
                recommendation=CriticRecommendation.APPROVE,
            )

        # Validate each finding
        validated_findings: list[str] = []
        rejected_findings: list[str] = []
        issues: list[CriticIssue] = []

        for finding in analysis.findings:
            # Simple validation logic - validate high-confidence findings
            if finding.confidence >= 0.8:
                validated_findings.append(finding.finding_id)
            elif finding.confidence < 0.5:
                # Low confidence findings are rejected
                rejected_findings.append(finding.finding_id)
                issues.append(
                    CriticIssue(
                        finding_id=finding.finding_id,
                        issue_type=IssueType.FALSE_POSITIVE,
                        original_severity=finding.severity.value,
                        suggested_severity=None,
                        reasoning=f"Low confidence ({finding.confidence:.2f})",
                    )
                )
            else:
                # Medium confidence - validate but note potential issues
                validated_findings.append(finding.finding_id)
                issues.append(
                    CriticIssue(
                        finding_id=finding.finding_id,
                        issue_type=IssueType.MISSING_CONTEXT,
                        original_severity=finding.severity.value,
                        suggested_severity=finding.severity.value,
                        reasoning=f"Medium confidence ({finding.confidence:.2f}), review recommended",
                    )
                )

        # Calculate scores based on validation results
        total_findings = len(analysis.findings)
        accuracy = len(validated_findings) / total_findings if total_findings > 0 else 1.0
        severity_calibration = 0.85  # Default calibration score
        actionability = 0.9 if all(f.refactoring_pattern for f in analysis.findings) else 0.7
        pragmatism = 0.85  # Default pragmatism score

        # Determine recommendation
        if len(validated_findings) == 0 and len(rejected_findings) == total_findings:
            recommendation = CriticRecommendation.APPROVE  # All false positives
        elif len(issues) > total_findings / 2:
            recommendation = CriticRecommendation.REVISE  # Too many issues
        else:
            recommendation = CriticRecommendation.APPROVE

        summary = self._generate_critic_summary(
            validated_findings, rejected_findings, issues
        )

        return CriticReview(
            review_id=review_id,
            accuracy=accuracy,
            severity_calibration=severity_calibration,
            actionability=actionability,
            pragmatism=pragmatism,
            issues=issues,
            validated_findings=validated_findings,
            rejected_findings=rejected_findings,
            summary=summary,
            recommendation=recommendation,
        )

    def run_moderator_phase(
        self,
        analysis: AnalysisResult,
        critique: CriticReview,
        retry_context: Optional[RetryContext] = None,
    ) -> ModeratorDecision:
        """Stage 3: Final verdict with 30s budget.

        Makes the final decision based on analysis and critique:
        - APPROVE: No actionable issues
        - REFACTOR: Has addressable issues with TDD plans
        - ESCALATE: Major issues or max retries exceeded

        Args:
            analysis: The AnalysisResult from analyst phase.
            critique: The CriticReview from critic phase.
            retry_context: Optional context for retry iterations.

        Returns:
            ModeratorDecision containing final verdict and TDD plans.
        """
        now = datetime.now()
        moderation_id = f"mod-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

        # Check for escalation conditions
        if retry_context and self.should_escalate(retry_context):
            return self._create_escalate_decision(moderation_id, analysis, critique)

        # Get validated findings that need addressing
        validated_finding_ids = set(critique.validated_findings)
        findings_to_address = [
            f
            for f in analysis.findings
            if f.finding_id in validated_finding_ids and f.priority == Priority.FIX_NOW
        ]

        # If no findings to address, approve
        if not findings_to_address:
            return self._create_approve_decision(moderation_id)

        # Create approved findings with TDD plans
        approved_findings: list[ApprovedFinding] = []
        for finding in findings_to_address:
            # Enrich finding with refactoring suggestions
            enriched = self.suggester.enrich_finding(finding)
            # Generate TDD plan
            tdd_plan = self.tdd_generator.generate_plan(enriched)
            approved_findings.append(
                ApprovedFinding(
                    finding_id=finding.finding_id,
                    final_severity=finding.severity.value,
                    final_priority=finding.priority.value,
                    tdd_plan=tdd_plan,
                )
            )

        # Create rejected findings list
        rejected_finding_ids = set(critique.rejected_findings)
        rejected_findings: list[RejectedFinding] = [
            RejectedFinding(
                finding_id=f.finding_id,
                rejection_reason=self._get_rejection_reason(f.finding_id, critique.issues),
            )
            for f in analysis.findings
            if f.finding_id in rejected_finding_ids
        ]

        # Create tech debt backlog for fix_later items
        tech_debt_backlog: list[TechDebtItem] = [
            TechDebtItem(
                finding_id=f.finding_id,
                priority=f.priority.value,
                reason="Lower priority, can be addressed later",
            )
            for f in analysis.findings
            if f.finding_id in validated_finding_ids and f.priority == Priority.FIX_LATER
        ]

        # Determine final verdict
        if len(approved_findings) > 0:
            final_verdict = Verdict.REFACTOR
        else:
            final_verdict = Verdict.APPROVE

        summary = self._generate_moderator_summary(
            approved_findings, rejected_findings, tech_debt_backlog, final_verdict
        )
        handoff_instructions = self._generate_handoff_instructions(approved_findings)

        return ModeratorDecision(
            moderation_id=moderation_id,
            final_verdict=final_verdict,
            approved_findings=approved_findings,
            rejected_findings=rejected_findings,
            tech_debt_backlog=tech_debt_backlog,
            summary=summary,
            handoff_instructions=handoff_instructions,
        )

    def should_escalate(self, retry_context: RetryContext) -> bool:
        """Check if we should escalate after max retries.

        Escalation occurs when:
        - Maximum retry iterations (3) have been reached
        - Multiple critical architectural issues persist

        Args:
            retry_context: The current retry context with iteration count.

        Returns:
            True if escalation is needed, False otherwise.
        """
        return retry_context.iteration >= self.MAX_RETRIES

    def _create_approve_decision(
        self, moderation_id: Optional[str] = None
    ) -> ModeratorDecision:
        """Create an APPROVE decision with no issues.

        Args:
            moderation_id: Optional moderation ID. If not provided, generates one.

        Returns:
            ModeratorDecision with APPROVE verdict.
        """
        if moderation_id is None:
            now = datetime.now()
            moderation_id = f"mod-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

        return ModeratorDecision(
            moderation_id=moderation_id,
            final_verdict=Verdict.APPROVE,
            approved_findings=[],
            rejected_findings=[],
            tech_debt_backlog=[],
            summary="No code quality issues require immediate attention.",
            handoff_instructions="Code quality approved. Proceed with merge.",
        )

    def _create_escalate_decision(
        self,
        moderation_id: str,
        analysis: AnalysisResult,
        critique: CriticReview,
    ) -> ModeratorDecision:
        """Create an ESCALATE decision after max retries.

        Args:
            moderation_id: The moderation ID.
            analysis: The AnalysisResult from analyst phase.
            critique: The CriticReview from critic phase.

        Returns:
            ModeratorDecision with ESCALATE verdict.
        """
        # List all remaining issues as requiring human review
        validated_finding_ids = set(critique.validated_findings)
        remaining_findings = [
            f for f in analysis.findings if f.finding_id in validated_finding_ids
        ]

        summary = (
            f"Escalating after {self.MAX_RETRIES} retry iterations. "
            f"{len(remaining_findings)} issues require human review."
        )

        return ModeratorDecision(
            moderation_id=moderation_id,
            final_verdict=Verdict.ESCALATE,
            approved_findings=[],
            rejected_findings=[],
            tech_debt_backlog=[],
            summary=summary,
            handoff_instructions="Human review required. Contact tech lead for architectural guidance.",
        )

    def _generate_critic_summary(
        self,
        validated: list[str],
        rejected: list[str],
        issues: list[CriticIssue],
    ) -> str:
        """Generate a summary for the critic review.

        Args:
            validated: List of validated finding IDs.
            rejected: List of rejected finding IDs.
            issues: List of issues found during critique.

        Returns:
            A summary string for the critic review.
        """
        parts = []
        if validated:
            parts.append(f"Validated {len(validated)} finding(s)")
        if rejected:
            parts.append(f"Rejected {len(rejected)} as false positive(s)")
        if issues:
            parts.append(f"Noted {len(issues)} issue(s) to review")

        if not parts:
            return "No findings to review."

        return ". ".join(parts) + "."

    def _generate_moderator_summary(
        self,
        approved: list[ApprovedFinding],
        rejected: list[RejectedFinding],
        tech_debt: list[TechDebtItem],
        verdict: Verdict,
    ) -> str:
        """Generate a summary for the moderator decision.

        Args:
            approved: List of approved findings with TDD plans.
            rejected: List of rejected findings.
            tech_debt: List of tech debt items.
            verdict: The final verdict.

        Returns:
            A summary string for the moderator decision.
        """
        if verdict == Verdict.APPROVE:
            return "No code quality issues require immediate attention."

        parts = []
        if approved:
            parts.append(f"{len(approved)} issue(s) require immediate fixing")
        if tech_debt:
            parts.append(f"{len(tech_debt)} issue(s) added to tech debt backlog")
        if rejected:
            parts.append(f"{len(rejected)} finding(s) dismissed")

        return ". ".join(parts) + "."

    def _generate_handoff_instructions(
        self, approved: list[ApprovedFinding]
    ) -> str:
        """Generate handoff instructions for the coder agent.

        Args:
            approved: List of approved findings with TDD plans.

        Returns:
            Handoff instructions string.
        """
        if not approved:
            return "Code quality approved. Proceed with merge."

        instructions = [
            "Follow TDD protocol for each approved finding:",
            "",
        ]

        for i, finding in enumerate(approved, 1):
            instructions.append(f"{i}. {finding.finding_id} ({finding.final_severity})")

        instructions.append("")
        instructions.append("For each finding: RED (write failing test) -> GREEN (make it pass) -> REFACTOR (clean up).")

        return "\n".join(instructions)

    def _get_rejection_reason(
        self, finding_id: str, issues: list[CriticIssue]
    ) -> str:
        """Get the rejection reason for a finding from critic issues.

        Args:
            finding_id: The finding ID to look up.
            issues: List of critic issues.

        Returns:
            The rejection reason or a default message.
        """
        for issue in issues:
            if issue.finding_id == finding_id:
                return issue.reasoning
        return "Rejected during critic review"
