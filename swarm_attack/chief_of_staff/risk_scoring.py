"""Risk scoring engine for intelligent checkpoint decisions.

This module is part of the Jarvis MVP - Chief of Staff's autonomous goal execution system.
It provides nuanced risk assessment for goals to enable intelligent decision-making about
whether to auto-approve, require a checkpoint (human review), or block execution entirely.

The risk scoring system uses a weighted multi-factor approach to evaluate:
- Cost impact on remaining budget
- Scope of changes (files affected, criticality)
- Reversibility of operations
- Historical precedent from past episodes
- Confidence based on past decision patterns

Integration Points:
    - Used by PreFlightChecker to validate goals before execution
    - Consumes data from EpisodeStore for precedent analysis
    - Consumes data from PreferenceLearner for confidence scoring
    - Informs Chief of Staff's checkpoint/approval decisions

Example:
    >>> from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
    >>> engine = RiskScoringEngine(episode_store=store, preference_learner=learner)
    >>> assessment = engine.score(goal, context={"session_budget": 25.0, "spent_usd": 5.0})
    >>> if assessment.requires_checkpoint:
    ...     print(f"Checkpoint required: {assessment.rationale}")
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.episodes import EpisodeStore, PreferenceLearner
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


@dataclass
class RiskAssessment:
    """Result of risk assessment for a goal.

    This dataclass encapsulates the output of the risk scoring engine, providing
    a comprehensive view of the risk analysis including the overall score, factor
    breakdown, recommendation, and human-readable rationale.

    Attributes:
        score: Overall risk score from 0.0 (completely safe) to 1.0 (extremely risky).
               Calculated as a weighted sum of individual risk factors.
        factors: Dictionary mapping factor names to their individual scores (0.0-1.0).
                Keys include: "cost", "scope", "reversibility", "precedent", "confidence".
        recommendation: One of "proceed" (auto-approve), "checkpoint" (require human review),
                       or "block" (prevent execution). Based on score thresholds.
        rationale: Human-readable explanation of the risk assessment, highlighting the
                  most concerning factors and providing context for the recommendation.

    Example:
        >>> assessment = RiskAssessment(
        ...     score=0.65,
        ...     factors={"cost": 0.8, "scope": 0.6, "reversibility": 0.3, "precedent": 0.4, "confidence": 0.2},
        ...     recommendation="checkpoint",
        ...     rationale="High cost impact (80% of remaining budget); Wide scope (affects 12 files)"
        ... )
        >>> if assessment.requires_checkpoint:
        ...     print(assessment.rationale)
    """

    score: float  # 0.0 (safe) to 1.0 (risky)
    factors: dict[str, float]  # Breakdown by factor
    recommendation: str  # "proceed", "checkpoint", "block"
    rationale: str  # Human-readable explanation

    @property
    def requires_checkpoint(self) -> bool:
        """Check if this assessment requires a human checkpoint.

        Returns:
            True if the recommendation is "checkpoint" or "block", indicating that
            human review is required before proceeding. False if "proceed" (auto-approve).
        """
        return self.recommendation in ("checkpoint", "block")

    @property
    def is_blocked(self) -> bool:
        """Check if execution is completely blocked.

        Returns:
            True if the recommendation is "block", indicating the risk is too high
            and execution should be prevented entirely. False otherwise.
        """
        return self.recommendation == "block"


class RiskScoringEngine:
    """Calculate nuanced risk scores for checkpoint decisions.

    The RiskScoringEngine is the core component of the Jarvis MVP's risk assessment
    system. It analyzes goals using a multi-factor weighted scoring algorithm to
    determine whether execution should proceed automatically, require human review,
    or be blocked entirely.

    Scoring Methodology:
        The engine evaluates 5 weighted factors, each contributing to the final risk score:

        1. Cost (30% weight): Impact on remaining budget. Higher cost relative to remaining
           budget increases risk. Goals using >60% of remaining budget score 1.0.

        2. Scope (25% weight): Number and criticality of files affected. More files and
           core system paths (core/, models/, api/, auth/, database/) increase risk.
           10+ files or core paths add significant risk.

        3. Reversibility (20% weight): Whether operations can be safely undone. Irreversible
           operations (delete, drop, migrate) score highest (1.0). External operations
           (deploy, publish, email) score moderately (0.7).

        4. Precedent (15% weight): Success rate of similar past episodes. No precedent or
           low success rates increase risk. Requires EpisodeStore integration.

        5. Confidence (10% weight): Historical approval patterns for similar goals. Low
           approval rates indicate higher risk. Requires PreferenceLearner integration.

    Decision Thresholds:
        - score < 0.5: Auto-approve (proceed)
        - 0.5 <= score < 0.8: Require checkpoint (human review)
        - score >= 0.8: Block execution

    Integration:
        - Requires EpisodeStore for precedent analysis (optional, defaults to 0.5 if missing)
        - Requires PreferenceLearner for confidence scoring (optional, defaults to 0.5 if missing)
        - Used by PreFlightChecker during goal validation

    Example:
        >>> engine = RiskScoringEngine(episode_store=store, preference_learner=learner)
        >>> context = {
        ...     "session_budget": 25.0,
        ...     "spent_usd": 10.0,
        ...     "files_to_modify": ["app/core/models.py", "app/core/api.py"]
        ... }
        >>> assessment = engine.score(goal, context)
        >>> print(f"Risk: {assessment.score:.2f} - {assessment.recommendation}")
        >>> print(f"Factors: {assessment.factors}")
        >>> print(f"Rationale: {assessment.rationale}")
    """

    # Risk weights
    WEIGHTS = {
        "cost": 0.30,
        "scope": 0.25,
        "reversibility": 0.20,
        "precedent": 0.15,
        "confidence": 0.10,
    }

    # Thresholds
    CHECKPOINT_THRESHOLD = 0.5  # Score > 0.5 requires checkpoint
    BLOCK_THRESHOLD = 0.8  # Score > 0.8 blocks execution

    def __init__(
        self,
        episode_store: Optional["EpisodeStore"] = None,
        preference_learner: Optional["PreferenceLearner"] = None,
    ):
        """Initialize RiskScoringEngine.

        Args:
            episode_store: Optional EpisodeStore for precedent-based scoring. If provided,
                          the engine will analyze similar past episodes to assess risk based
                          on historical success rates. If None, precedent factor defaults to 0.5.
            preference_learner: Optional PreferenceLearner for confidence scoring. If provided,
                               the engine will analyze past approval patterns for similar goals.
                               If None, confidence factor defaults to 0.5.

        Note:
            The engine can function without these dependencies, but risk scores will be less
            informed. For optimal risk assessment, provide both components.
        """
        self.episode_store = episode_store
        self.preference_learner = preference_learner

    def score(
        self,
        goal: "DailyGoal",
        context: dict,
    ) -> RiskAssessment:
        """Calculate comprehensive risk score for a goal.

        This is the main entry point for risk assessment. It evaluates all 5 risk factors,
        combines them using weighted scoring, and produces a recommendation with rationale.

        Args:
            goal: The DailyGoal to assess. Must have at minimum:
                  - description: str (used for precedent/confidence matching and reversibility)
                  - estimated_cost_usd: Optional[float] (used for cost scoring)
            context: Execution context dictionary with the following keys:
                - session_budget: float - Total budget available for the session (default: 25.0)
                - spent_usd: float - Amount already spent in the session (default: 0.0)
                - files_to_modify: list[str] - File paths that will be modified (default: [])
                - completed_goals: set[str] - IDs of completed goals (optional, not used here)
                - blocked_goals: set[str] - IDs of blocked goals (optional, not used here)

        Returns:
            RiskAssessment containing:
                - score: Weighted risk score from 0.0-1.0
                - factors: Dict of individual factor scores
                - recommendation: "proceed", "checkpoint", or "block"
                - rationale: Human-readable explanation of concerning factors

        Example:
            >>> context = {
            ...     "session_budget": 25.0,
            ...     "spent_usd": 15.0,
            ...     "files_to_modify": ["app/core/auth.py", "app/api/users.py"]
            ... }
            >>> assessment = engine.score(goal, context)
            >>> if assessment.recommendation == "checkpoint":
            ...     print(f"Checkpoint required: {assessment.rationale}")
            ...     print(f"Cost factor: {assessment.factors['cost']:.2f}")
        """
        factors = {}
        rationale_parts = []

        # Factor 1: Cost (30%)
        factors["cost"] = self._score_cost(goal, context)
        if factors["cost"] > 0.5:
            rationale_parts.append(
                f"High cost impact ({factors['cost']:.0%} of remaining budget)"
            )

        # Factor 2: Scope (25%)
        factors["scope"] = self._score_scope(goal, context)
        if factors["scope"] > 0.5:
            rationale_parts.append(
                f"Wide scope (affects {context.get('files_to_modify', ['unknown'])})"
            )

        # Factor 3: Reversibility (20%)
        factors["reversibility"] = self._score_reversibility(goal)
        if factors["reversibility"] > 0.5:
            rationale_parts.append("Contains irreversible operations")

        # Factor 4: Precedent (15%)
        factors["precedent"] = self._score_precedent(goal)
        if factors["precedent"] > 0.5:
            rationale_parts.append("No similar successful precedent")

        # Factor 5: Confidence (10%)
        factors["confidence"] = self._score_confidence(goal)
        if factors["confidence"] > 0.5:
            rationale_parts.append("Low confidence based on past outcomes")

        # Calculate weighted score
        score = sum(factors[k] * self.WEIGHTS[k] for k in factors)

        # Determine recommendation
        if score >= self.BLOCK_THRESHOLD:
            recommendation = "block"
        elif score >= self.CHECKPOINT_THRESHOLD:
            recommendation = "checkpoint"
        else:
            recommendation = "proceed"

        # Build rationale
        if not rationale_parts:
            rationale = "Low risk - no concerning factors detected"
        else:
            rationale = "; ".join(rationale_parts)

        return RiskAssessment(
            score=score,
            factors=factors,
            recommendation=recommendation,
            rationale=rationale,
        )

    def _score_cost(self, goal: "DailyGoal", context: dict) -> float:
        """Score based on budget impact.

        Evaluates the goal's estimated cost relative to remaining budget. Higher
        cost consumption results in higher risk scores.

        Args:
            goal: Goal with estimated_cost_usd attribute
            context: Must contain session_budget and spent_usd

        Returns:
            Risk score from 0.0-1.0:
                - 0.0: Minimal cost impact (<10% of remaining budget)
                - 0.5: Moderate impact (30% of remaining budget)
                - 1.0: Major impact (60%+ of remaining budget)

        Note:
            Uses a scaling factor where 60% of remaining budget = 1.0 risk.
        """
        session_budget = context.get("session_budget", 25.0)
        spent = context.get("spent_usd", 0.0)
        remaining = max(session_budget - spent, 0.01)

        estimated_cost = goal.estimated_cost_usd or 0.0

        # Cost as fraction of remaining budget
        cost_ratio = estimated_cost / remaining

        # 30% of remaining = 0.5 risk, 60% = 1.0 risk
        return min(1.0, cost_ratio / 0.6)

    def _score_scope(self, goal: "DailyGoal", context: dict) -> float:
        """Score based on scope of changes.

        Evaluates the number of files affected and whether they touch critical system
        paths. More files and core system components increase risk.

        Args:
            goal: Goal being assessed (not directly used, for interface consistency)
            context: Must contain files_to_modify list

        Returns:
            Risk score from 0.0-1.0:
                - 0.0: No files or very few files
                - 0.5: 5 files affected or 1-2 core files
                - 1.0: 10+ files or multiple core system paths

        Note:
            Core paths include: core/, models/, api/, auth/, database/
            Affecting core paths adds +0.3 to the base file count score.
        """
        files = context.get("files_to_modify", [])

        # Check for core paths
        core_patterns = ["core/", "models/", "api/", "auth/", "database/"]
        affects_core = any(
            any(pattern in f for pattern in core_patterns)
            for f in files
        )

        # Base score on file count
        file_score = min(1.0, len(files) / 10)  # 10+ files = 1.0

        # Add 0.3 if affects core paths
        if affects_core:
            file_score = min(1.0, file_score + 0.3)

        return file_score

    def _score_reversibility(self, goal: "DailyGoal") -> float:
        """Score based on reversibility of operations.

        Analyzes the goal description for keywords indicating irreversible or
        hard-to-reverse operations. Operations that can't be undone carry higher risk.

        Args:
            goal: Goal with description attribute to analyze

        Returns:
            Risk score from 0.0-1.0:
                - 0.2: Reversible operations (default for most goals)
                - 0.7: External/published operations (deploy, publish, send, email)
                - 1.0: Irreversible operations (delete, drop, remove, destroy, reset, migrate)

        Note:
            Uses keyword matching on lowercased description. Keywords are:
            - Irreversible: delete, drop, remove, destroy, reset, migrate
            - External: deploy, publish, push, release, send, email
        """
        description = goal.description.lower()

        # Irreversible keywords
        irreversible = ["delete", "drop", "remove", "destroy", "reset", "migrate"]
        if any(kw in description for kw in irreversible):
            return 1.0

        # External/publish keywords
        external = ["deploy", "publish", "push", "release", "send", "email"]
        if any(kw in description for kw in external):
            return 0.7

        return 0.2  # Default: reversible

    def _score_precedent(self, goal: "DailyGoal") -> float:
        """Score based on similar past episodes.

        Searches the episode store for similar past goals and evaluates their
        success rate. Goals similar to successful past episodes carry lower risk.

        Args:
            goal: Goal with description attribute for similarity matching

        Returns:
            Risk score from 0.0-1.0:
                - 0.0: All similar past episodes succeeded (100% success rate)
                - 0.5: No episode store available or unknown precedent
                - 0.6: No similar episodes found (no precedent)
                - 1.0: All similar past episodes failed (0% success rate)

        Note:
            Requires episode_store to be provided during initialization.
            Searches for top 5 most similar episodes based on description.
            Success rate is inverted to get risk score (high success = low risk).
        """
        if not self.episode_store:
            return 0.5  # Unknown

        similar = self.episode_store.find_similar(goal.description, k=5)

        if not similar:
            return 0.6  # No precedent = slightly risky

        # Check success rate
        successes = sum(1 for ep in similar if ep.success)
        success_rate = successes / len(similar)

        # High success rate = low risk
        return 1.0 - success_rate

    def _score_confidence(self, goal: "DailyGoal") -> float:
        """Score based on past decision patterns.

        Analyzes historical approval/rejection patterns for similar goals to assess
        confidence. Goals similar to frequently-approved past goals carry lower risk.

        Args:
            goal: Goal to find similar past decisions for

        Returns:
            Risk score from 0.0-1.0:
                - 0.0: All similar past decisions were approved (100% approval rate)
                - 0.5: No preference learner available or no decision history
                - 1.0: All similar past decisions were rejected (0% approval rate)

        Note:
            Requires preference_learner to be provided during initialization.
            Searches for top 3 most similar past decisions.
            Approval rate is inverted to get risk score (high approval = low risk).
        """
        if not self.preference_learner:
            return 0.5  # Unknown

        similar_decisions = self.preference_learner.find_similar_decisions(goal, k=3)

        if not similar_decisions:
            return 0.5  # No history

        # Check approval rate
        approvals = sum(1 for d in similar_decisions if d.get("was_accepted", False))
        approval_rate = approvals / len(similar_decisions)

        # High approval rate = low risk
        return 1.0 - approval_rate
