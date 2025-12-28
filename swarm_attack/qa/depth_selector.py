"""DepthSelector for determining QA testing depth.

Implements spec section 8: Depth Selector
- Select depth based on trigger type
- Escalate depth for high-risk code changes
- Consider time and cost budgets
- Support manual depth override
"""

from __future__ import annotations

import re
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QATrigger,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class DepthSelector:
    """
    Selects appropriate QA testing depth based on context and constraints.

    Depth selection rules (from spec section 8):
    - POST_VERIFICATION → STANDARD (may escalate for high-risk)
    - BUG_REPRODUCTION → DEEP
    - USER_COMMAND → uses provided or STANDARD
    - PRE_MERGE → REGRESSION
    """

    # High-risk patterns for file paths
    HIGH_RISK_PATTERNS = [
        r"auth",
        r"authentication",
        r"login",
        r"password",
        r"payment",
        r"billing",
        r"checkout",
        r"stripe",
        r"security",
        r"crypto",
        r"token",
        r"session",
        r"credential",
    ]

    # Estimated costs per depth level (USD)
    DEPTH_COSTS = {
        QADepth.SHALLOW: 0.02,
        QADepth.STANDARD: 0.10,
        QADepth.DEEP: 0.30,
        QADepth.REGRESSION: 0.08,
    }

    # Estimated time per depth level (minutes)
    DEPTH_TIMES = {
        QADepth.SHALLOW: 0.5,
        QADepth.STANDARD: 2.0,
        QADepth.DEEP: 5.0,
        QADepth.REGRESSION: 1.5,
    }

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the DepthSelector.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.high_risk_threshold = 0.8

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "depth_selector"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def select_depth(
        self,
        trigger: QATrigger,
        context: QAContext,
        risk_score: float = 0.5,
        time_budget_minutes: Optional[float] = None,
        cost_budget_usd: Optional[float] = None,
        override_depth: Optional[QADepth] = None,
    ) -> QADepth:
        """
        Select appropriate testing depth.

        Args:
            trigger: What initiated this QA session.
            context: QAContext with file/endpoint info.
            risk_score: Optional pre-calculated risk score (0.0-1.0).
            time_budget_minutes: Optional time budget in minutes.
            cost_budget_usd: Optional cost budget in USD.
            override_depth: Optional explicit depth override.

        Returns:
            Selected QADepth level.
        """
        self._log("select_depth_start", {
            "trigger": trigger.value,
            "risk_score": risk_score,
            "override": override_depth.value if override_depth else None,
        })

        # Step 1: Determine base depth from trigger
        base_depth = self._get_base_depth(trigger, override_depth)

        # Step 2: Calculate actual risk score from context
        actual_risk = self.calculate_risk_score(context)
        # Use the higher of provided risk_score and calculated risk
        effective_risk = max(risk_score, actual_risk)

        # Step 3: Apply risk escalation
        escalated_depth = self._apply_risk_escalation(base_depth, effective_risk, context)

        # Step 4: Apply budget constraints (may downgrade)
        final_depth = self._apply_budget_constraints(
            escalated_depth,
            time_budget_minutes,
            cost_budget_usd,
        )

        self._log("select_depth_complete", {
            "base_depth": base_depth.value,
            "escalated_depth": escalated_depth.value,
            "final_depth": final_depth.value,
        })

        return final_depth

    def _get_base_depth(
        self,
        trigger: QATrigger,
        override: Optional[QADepth] = None,
    ) -> QADepth:
        """
        Get base depth from trigger type.

        Args:
            trigger: QA trigger type.
            override: Optional explicit override.

        Returns:
            Base QADepth level.
        """
        if override is not None:
            return override

        trigger_to_depth = {
            QATrigger.POST_VERIFICATION: QADepth.STANDARD,
            QATrigger.BUG_REPRODUCTION: QADepth.DEEP,
            QATrigger.USER_COMMAND: QADepth.STANDARD,
            QATrigger.PRE_MERGE: QADepth.REGRESSION,
        }

        return trigger_to_depth.get(trigger, QADepth.STANDARD)

    def _apply_risk_escalation(
        self,
        depth: QADepth,
        risk_score: float,
        context: QAContext,
    ) -> QADepth:
        """
        Apply risk-based escalation to depth.

        High risk (>0.8) escalates by one level.
        Critical files (auth, payment) always escalate to DEEP.

        Args:
            depth: Current depth level.
            risk_score: Risk score (0.0-1.0).
            context: QAContext with file/endpoint info.

        Returns:
            Possibly escalated QADepth level.
        """
        # Check for critical files/endpoints that always require DEEP
        if self._has_critical_files(context):
            return QADepth.DEEP

        # Check for high risk score
        if risk_score >= self.high_risk_threshold:
            return self._escalate_depth(depth)

        return depth

    def _has_critical_files(self, context: QAContext) -> bool:
        """Check if context contains critical files/endpoints."""
        # Check target files
        for file_path in context.target_files:
            for pattern in self.HIGH_RISK_PATTERNS:
                if re.search(pattern, file_path.lower()):
                    return True

        # Check target endpoints
        for endpoint in context.target_endpoints:
            for pattern in self.HIGH_RISK_PATTERNS:
                if re.search(pattern, endpoint.path.lower()):
                    return True

        return False

    def _escalate_depth(self, depth: QADepth) -> QADepth:
        """Escalate depth by one level."""
        escalation = {
            QADepth.SHALLOW: QADepth.STANDARD,
            QADepth.STANDARD: QADepth.DEEP,
            QADepth.DEEP: QADepth.DEEP,  # Can't go higher
            QADepth.REGRESSION: QADepth.STANDARD,  # Escalate to STANDARD then...
        }
        return escalation.get(depth, depth)

    def _apply_budget_constraints(
        self,
        depth: QADepth,
        time_budget_minutes: Optional[float],
        cost_budget_usd: Optional[float],
    ) -> QADepth:
        """
        Apply budget constraints, potentially downgrading depth.

        Args:
            depth: Current depth level.
            time_budget_minutes: Optional time budget.
            cost_budget_usd: Optional cost budget.

        Returns:
            Possibly downgraded QADepth level.
        """
        current_depth = depth

        # Apply time budget constraint
        if time_budget_minutes is not None:
            while current_depth != QADepth.SHALLOW:
                estimated_time = self.get_estimated_time(current_depth)
                if estimated_time <= time_budget_minutes:
                    break
                current_depth = self._downgrade_depth(current_depth)

        # Apply cost budget constraint
        if cost_budget_usd is not None and cost_budget_usd >= 0:
            while current_depth != QADepth.SHALLOW:
                estimated_cost = self.get_estimated_cost(current_depth)
                if estimated_cost <= cost_budget_usd:
                    break
                current_depth = self._downgrade_depth(current_depth)

        return current_depth

    def _downgrade_depth(self, depth: QADepth) -> QADepth:
        """Downgrade depth by one level."""
        downgrade = {
            QADepth.DEEP: QADepth.STANDARD,
            QADepth.STANDARD: QADepth.SHALLOW,
            QADepth.SHALLOW: QADepth.SHALLOW,  # Can't go lower
            QADepth.REGRESSION: QADepth.SHALLOW,
        }
        return downgrade.get(depth, depth)

    def calculate_risk_score(self, context: QAContext) -> float:
        """
        Calculate risk score from context.

        Factors considered:
        - File paths (auth, payment, security)
        - Number of endpoints affected
        - Size of git diff
        - Endpoint criticality

        Args:
            context: QAContext with file/endpoint info.

        Returns:
            Risk score between 0.0 and 1.0.
        """
        score = 0.3  # Base score

        # Check for high-risk file patterns
        for file_path in context.target_files:
            for pattern in self.HIGH_RISK_PATTERNS:
                if re.search(pattern, file_path.lower()):
                    score = max(score, 0.9)
                    break

        # Check for high-risk endpoint patterns
        for endpoint in context.target_endpoints:
            for pattern in self.HIGH_RISK_PATTERNS:
                if re.search(pattern, endpoint.path.lower()):
                    score = max(score, 0.9)
                    break

        # Factor in number of endpoints (more = higher risk)
        num_endpoints = len(context.target_endpoints)
        if num_endpoints > 3:
            score = max(score, 0.5 + (num_endpoints - 3) * 0.05)

        # Factor in git diff size
        if context.git_diff:
            diff_lines = len(context.git_diff.split('\n'))
            if diff_lines > 50:
                score = max(score, 0.6)
            if diff_lines > 100:
                score = max(score, 0.7)

        # Ensure score is within bounds
        return min(max(score, 0.0), 1.0)

    def get_estimated_cost(self, depth: QADepth) -> float:
        """
        Get estimated cost for a depth level.

        Args:
            depth: QADepth level.

        Returns:
            Estimated cost in USD.
        """
        return self.DEPTH_COSTS.get(depth, 0.10)

    def get_estimated_time(self, depth: QADepth) -> float:
        """
        Get estimated time for a depth level.

        Args:
            depth: QADepth level.

        Returns:
            Estimated time in minutes.
        """
        return self.DEPTH_TIMES.get(depth, 2.0)
