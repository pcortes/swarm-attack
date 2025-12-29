"""Pre-flight validation before goal execution.

This module is part of the Jarvis MVP - Chief of Staff's autonomous goal execution system.
It provides comprehensive pre-execution validation to catch issues early and make intelligent
checkpoint decisions before any resources are consumed or actions are taken.

The pre-flight system validates goals across multiple dimensions:
- Budget sufficiency (do we have enough remaining budget?)
- Dependency satisfaction (are prerequisite goals completed?)
- Risk assessment (should this require human review or be blocked?)
- Conflict detection (does this conflict with other goals?)

This "fail fast" approach prevents wasted resources on goals that are doomed to fail
or require human intervention, and enables intelligent auto-approval for low-risk goals.

Integration Points:
    - Used by Chief of Staff before executing any goal
    - Consumes RiskScoringEngine for risk-based checkpoint decisions
    - Coordinates with GoalTracker for dependency and status information
    - Outputs PreFlightResult to guide execution decisions

Example:
    >>> from swarm_attack.chief_of_staff.preflight import PreFlightChecker
    >>> from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
    >>>
    >>> risk_engine = RiskScoringEngine(episode_store=store, preference_learner=learner)
    >>> checker = PreFlightChecker(risk_engine=risk_engine)
    >>>
    >>> context = {
    ...     "session_budget": 25.0,
    ...     "spent_usd": 10.0,
    ...     "completed_goals": {"goal1", "goal2"},
    ...     "blocked_goals": set()
    ... }
    >>> result = checker.validate(goal, context)
    >>>
    >>> if result.auto_approved:
    ...     print("Auto-approved, executing immediately")
    >>> elif result.requires_checkpoint:
    ...     print(f"Checkpoint required: {result.summary()}")
    >>> else:
    ...     print(f"Blocked: {result.summary()}")
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal
    from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine, RiskAssessment


@dataclass
class PreFlightIssue:
    """An issue detected during pre-flight validation.

    Represents a single validation issue found during pre-flight checks.
    Issues have severity levels that determine whether execution can proceed.

    Attributes:
        severity: Severity level of the issue:
                 - "critical": Blocks execution entirely
                 - "warning": Non-blocking but noteworthy
                 - "info": Informational only
        category: Category of the issue:
                 - "budget": Budget-related problems
                 - "dependency": Dependency satisfaction issues
                 - "risk": Risk assessment concerns
                 - "conflict": Conflicts with other goals
        message: Human-readable description of the issue
        suggested_action: Optional suggestion for how to resolve the issue

    Example:
        >>> issue = PreFlightIssue(
        ...     severity="critical",
        ...     category="budget",
        ...     message="Estimated $15.00 exceeds remaining $10.00",
        ...     suggested_action="Increase budget or reduce scope"
        ... )
    """

    severity: str  # "critical", "warning", "info"
    category: str  # "budget", "dependency", "risk", "conflict"
    message: str
    suggested_action: Optional[str] = None


@dataclass
class PreFlightResult:
    """Result of pre-flight validation.

    Encapsulates the complete outcome of pre-flight validation, including all issues
    found, the risk assessment, and the final decision about how to proceed.

    The result contains three critical decision flags:
    - passed: Whether basic validation checks passed (no critical issues)
    - requires_checkpoint: Whether human review is required before execution
    - auto_approved: Whether execution can proceed immediately without human review

    Decision Matrix:
        - passed=False: Goal is blocked, cannot execute
        - passed=True, requires_checkpoint=True: Goal requires human approval
        - passed=True, auto_approved=True: Goal can execute immediately

    Attributes:
        passed: True if validation passed (no critical issues), False if blocked
        issues: List of all issues found during validation (critical, warning, info)
        risk_assessment: RiskAssessment from the RiskScoringEngine
        requires_checkpoint: True if human review is required before execution
        auto_approved: True if goal can execute immediately without review

    Example:
        >>> result = PreFlightResult(
        ...     passed=True,
        ...     issues=[],
        ...     risk_assessment=assessment,
        ...     requires_checkpoint=False,
        ...     auto_approved=True
        ... )
        >>> print(result.summary())  # "PASSED (risk: 0.25)"
    """

    passed: bool
    issues: list[PreFlightIssue] = field(default_factory=list)
    risk_assessment: Optional["RiskAssessment"] = None

    # Checkpoint control
    requires_checkpoint: bool = False
    auto_approved: bool = False

    def summary(self) -> str:
        """Generate human-readable summary of the validation result.

        Returns:
            Concise string summarizing the outcome and reason:
                - "PASSED (risk: X.XX)" for auto-approved goals
                - "CHECKPOINT REQUIRED: [rationale]" for goals needing review
                - "BLOCKED: [reason]" for goals that cannot execute
        """
        if self.passed and not self.requires_checkpoint:
            score = self.risk_assessment.score if self.risk_assessment else 0.0
            return f"PASSED (risk: {score:.2f})"
        elif self.requires_checkpoint:
            rationale = self.risk_assessment.rationale if self.risk_assessment else "Unknown"
            return f"CHECKPOINT REQUIRED: {rationale}"
        else:
            critical = [i for i in self.issues if i.severity == "critical"]
            return f"BLOCKED: {critical[0].message}" if critical else "BLOCKED"


class PreFlightChecker:
    """Validate goals before execution to catch issues early.

    The PreFlightChecker is a critical component of the Jarvis MVP's autonomous
    execution system. It validates goals BEFORE any resources are consumed or
    actions are taken, implementing a "fail fast" strategy that prevents wasted
    effort on goals that are doomed to fail or require human intervention.

    Validation Checks (in order):
        1. Budget Sufficiency: Ensures remaining budget can cover the estimated cost
           - Critical issue if cost > remaining budget
           - Warning if cost > 80% of remaining budget

        2. Dependency Satisfaction: Ensures prerequisite goals are completed
           - Critical issue if any dependency is incomplete or blocked
           - Reads dependencies from goal.dependencies attribute (if present)

        3. Risk Assessment: Evaluates goal using RiskScoringEngine
           - Auto-approves low-risk goals (score < 0.5)
           - Requires checkpoint for medium-risk goals (0.5 <= score < 0.8)
           - Blocks high-risk goals (score >= 0.8)

        4. Conflict Detection: (Future) Check for conflicts with other goals
           - Not yet implemented

    Decision Logic:
        The checker produces one of three outcomes:
        - BLOCKED (passed=False): Critical issues prevent execution
        - CHECKPOINT (passed=True, requires_checkpoint=True): Human review required
        - AUTO-APPROVED (passed=True, auto_approved=True): Execute immediately

    Integration:
        - Requires RiskScoringEngine for risk-based decisions
        - Consumes context with budget, goals, and execution state
        - Outputs PreFlightResult to guide Chief of Staff execution

    Example:
        >>> checker = PreFlightChecker(risk_engine=risk_engine)
        >>> result = checker.validate(goal, context)
        >>> if result.auto_approved:
        ...     execute_goal(goal)
        >>> elif result.requires_checkpoint:
        ...     await human_approval(goal, result.risk_assessment)
        >>> else:
        ...     log_blocked_goal(goal, result.issues)
    """

    def __init__(
        self,
        risk_engine: "RiskScoringEngine",
    ):
        """Initialize PreFlightChecker.

        Args:
            risk_engine: RiskScoringEngine instance for performing risk assessment.
                        Required for intelligent checkpoint decisions.
        """
        self.risk_engine = risk_engine

    def validate(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> PreFlightResult:
        """Run all pre-execution validations.

        This is the main entry point for pre-flight validation. It orchestrates all
        validation checks and produces a comprehensive result with issues and a final
        decision about how to proceed.

        Validation Flow:
            1. Check budget sufficiency
            2. Check dependency satisfaction
            3. Perform risk assessment
            4. Determine final outcome based on issues and risk

        Args:
            goal: The DailyGoal to validate. Should have:
                  - description: str
                  - estimated_cost_usd: Optional[float]
                  - dependencies: Optional[list[str]] - IDs of prerequisite goals
            context: Execution context dictionary with keys:
                - session_budget: float - Total budget for session (default: 25.0)
                - spent_usd: float - Amount already spent (default: 0.0)
                - completed_goals: set[str] - IDs of completed goals (default: empty set)
                - blocked_goals: set[str] - IDs of blocked goals (default: empty set)
                - files_to_modify: list[str] - Files to be modified (optional, for risk scoring)

        Returns:
            PreFlightResult containing:
                - passed: Whether validation passed
                - issues: List of all issues found
                - risk_assessment: RiskAssessment from risk engine
                - requires_checkpoint: Whether human review is required
                - auto_approved: Whether goal can execute immediately

        Example:
            >>> context = {
            ...     "session_budget": 25.0,
            ...     "spent_usd": 10.0,
            ...     "completed_goals": {"goal1"},
            ...     "blocked_goals": set(),
            ...     "files_to_modify": ["app/models.py"]
            ... }
            >>> result = checker.validate(goal, context)
            >>> if result.passed:
            ...     print(f"Validation passed: {result.summary()}")
            ...     if result.auto_approved:
            ...         execute_immediately(goal)
            ...     else:
            ...         request_approval(goal, result.risk_assessment)
            >>> else:
            ...     print(f"Validation failed: {result.summary()}")
            ...     for issue in result.issues:
            ...         print(f"  - {issue.severity}: {issue.message}")
        """
        issues = []

        # Check 1: Budget sufficiency
        budget_issue = self._check_budget(goal, context)
        if budget_issue:
            issues.append(budget_issue)

        # Check 2: Dependencies
        dep_issue = self._check_dependencies(goal, context)
        if dep_issue:
            issues.append(dep_issue)

        # Check 3: Risk assessment
        risk = self.risk_engine.score(goal, context)

        # Determine outcome
        has_critical = any(i.severity == "critical" for i in issues)

        if has_critical:
            return PreFlightResult(
                passed=False,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=False,
                auto_approved=False,
            )

        if risk.is_blocked:
            issues.append(PreFlightIssue(
                severity="critical",
                category="risk",
                message=f"Risk score {risk.score:.2f} exceeds block threshold",
                suggested_action="Break into smaller tasks or get explicit approval",
            ))
            return PreFlightResult(
                passed=False,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=True,
                auto_approved=False,
            )

        if risk.requires_checkpoint:
            return PreFlightResult(
                passed=True,
                issues=issues,
                risk_assessment=risk,
                requires_checkpoint=True,
                auto_approved=False,
            )

        # Low risk - auto-approve
        return PreFlightResult(
            passed=True,
            issues=issues,
            risk_assessment=risk,
            requires_checkpoint=False,
            auto_approved=True,
        )

    def _check_budget(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> Optional[PreFlightIssue]:
        """Check if budget is sufficient for the goal.

        Compares the goal's estimated cost against remaining budget to prevent
        budget overruns. Issues critical error if cost exceeds budget, warning
        if it will consume >80% of remaining budget.

        Args:
            goal: Goal with estimated_cost_usd attribute
            context: Must contain session_budget and spent_usd

        Returns:
            PreFlightIssue if there's a budget problem, None if budget is sufficient.
            - Critical issue: estimated cost > remaining budget
            - Warning issue: estimated cost > 80% of remaining budget
            - None: sufficient budget available

        Note:
            If goal.estimated_cost_usd is None, defaults to 0.0 (no cost).
        """
        session_budget = context.get("session_budget", 25.0)
        spent = context.get("spent_usd", 0.0)
        remaining = session_budget - spent

        estimated = goal.estimated_cost_usd or 0.0

        if estimated > remaining:
            return PreFlightIssue(
                severity="critical",
                category="budget",
                message=f"Estimated ${estimated:.2f} exceeds remaining ${remaining:.2f}",
                suggested_action="Increase budget or reduce scope",
            )

        if estimated > remaining * 0.8:
            return PreFlightIssue(
                severity="warning",
                category="budget",
                message=f"Will use {estimated/remaining*100:.0f}% of remaining budget",
                suggested_action="Consider reserving budget for other goals",
            )

        return None

    def _check_dependencies(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> Optional[PreFlightIssue]:
        """Check if all goal dependencies are satisfied.

        Verifies that all prerequisite goals are completed and none are blocked.
        This ensures goals are executed in the correct order and don't depend on
        failed work.

        Args:
            goal: Goal with optional dependencies attribute (list of goal IDs)
            context: Must contain completed_goals and blocked_goals sets

        Returns:
            PreFlightIssue if there's a dependency problem, None if all satisfied.
            - Critical issue: dependency is blocked or incomplete
            - None: all dependencies are satisfied (or no dependencies)

        Note:
            If goal.dependencies is None or empty, returns None (no dependencies).
            Checks dependencies in order; returns first issue found.
        """
        completed = context.get("completed_goals", set())
        blocked = context.get("blocked_goals", set())

        # Get dependencies from goal (if available)
        dependencies = getattr(goal, "dependencies", []) or []

        for dep_id in dependencies:
            if dep_id in blocked:
                return PreFlightIssue(
                    severity="critical",
                    category="dependency",
                    message=f"Depends on blocked goal: {dep_id}",
                    suggested_action="Resolve blocker first or remove dependency",
                )

            if dep_id not in completed:
                return PreFlightIssue(
                    severity="critical",
                    category="dependency",
                    message=f"Depends on incomplete goal: {dep_id}",
                    suggested_action="Complete dependency first",
                )

        return None
