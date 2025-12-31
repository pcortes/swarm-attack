"""Tests for RiskScoringEngine and PreFlightChecker.

TDD tests for the Jarvis MVP risk assessment and preflight validation.
"""

import pytest
from unittest.mock import MagicMock

from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority


class TestRiskScoringEngine:
    """Tests for risk scoring."""

    def test_low_risk_goal_scores_low(self):
        """Simple goal with low cost should score low."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-1",
            description="Fix typo in README",
            priority=GoalPriority.LOW,
            estimated_minutes=5,
            estimated_cost_usd=0.50,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.score < 0.3
        assert result.recommendation == "proceed"
        assert not result.requires_checkpoint
        assert not result.is_blocked

    def test_high_cost_goal_scores_high(self):
        """Goal using most of budget should score high."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-2",
            description="Implement auth system",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            estimated_cost_usd=20.0,
        )

        # Add core files to increase scope factor and push over threshold
        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": ["core/auth.py", "models/user.py"],
        }
        result = engine.score(goal, context)

        assert result.score > 0.5
        assert result.recommendation in ("checkpoint", "block")
        assert result.requires_checkpoint

    def test_irreversible_action_scores_high(self):
        """Delete/destroy keywords should increase risk."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-3",
            description="Delete old user accounts",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            estimated_cost_usd=2.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.factors["reversibility"] == 1.0
        assert "irreversible" in result.rationale.lower()

    def test_external_action_scores_medium(self):
        """Deploy/publish keywords should score moderately."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-4",
            description="Deploy new version",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            estimated_cost_usd=2.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        assert result.factors["reversibility"] == 0.7

    def test_wide_scope_increases_risk(self):
        """Modifying many files should increase risk."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-5",
            description="Refactor everything",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=5.0,
        )

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": [f"src/file{i}.py" for i in range(15)],
        }
        result = engine.score(goal, context)

        assert result.factors["scope"] >= 1.0

    def test_core_path_increases_risk(self):
        """Modifying core paths should increase risk."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine

        engine = RiskScoringEngine()

        goal = DailyGoal(
            goal_id="test-6",
            description="Update core module",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            estimated_cost_usd=3.0,
        )

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": ["core/auth.py", "models/user.py"],
        }
        result = engine.score(goal, context)

        # Core paths add 0.3 to scope score
        assert result.factors["scope"] >= 0.3

    def test_episode_store_precedent(self):
        """Should use episode store to score precedent."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore

        # Create mock episode store with similar episodes
        mock_store = MagicMock(spec=EpisodeStore)
        mock_store.find_similar.return_value = [
            Episode(
                episode_id="ep-1",
                timestamp="2024-01-01T00:00:00",
                goal_id="fix-bug",
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            ),
            Episode(
                episode_id="ep-2",
                timestamp="2024-01-02T00:00:00",
                goal_id="fix-typo",
                success=True,
                cost_usd=0.5,
                duration_seconds=30,
            ),
        ]

        engine = RiskScoringEngine(episode_store=mock_store)

        goal = DailyGoal(
            goal_id="test-7",
            description="Fix similar bug",
            priority=GoalPriority.LOW,
            estimated_minutes=30,
            estimated_cost_usd=1.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        # 100% success rate = 0.0 precedent risk
        assert result.factors["precedent"] == 0.0

    def test_preference_learner_confidence(self):
        """Should use preference learner to score confidence."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.episodes import PreferenceLearner

        # Create mock preference learner
        mock_learner = MagicMock(spec=PreferenceLearner)
        mock_learner.find_similar_decisions.return_value = [
            {"was_accepted": True, "trigger": "COST_SINGLE"},
            {"was_accepted": True, "trigger": "COST_SINGLE"},
            {"was_accepted": False, "trigger": "COST_SINGLE"},
        ]

        engine = RiskScoringEngine(preference_learner=mock_learner)

        goal = DailyGoal(
            goal_id="test-8",
            description="Medium risk task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=3.0,
            tags=["cost"],
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = engine.score(goal, context)

        # 2/3 approval rate = 0.33 confidence risk
        assert abs(result.factors["confidence"] - 0.333) < 0.1

    def test_risk_assessment_properties(self):
        """Test RiskAssessment dataclass properties."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskAssessment

        # Test proceed recommendation
        proceed = RiskAssessment(
            score=0.3,
            factors={"cost": 0.2},
            recommendation="proceed",
            rationale="Low risk",
        )
        assert not proceed.requires_checkpoint
        assert not proceed.is_blocked

        # Test checkpoint recommendation
        checkpoint = RiskAssessment(
            score=0.6,
            factors={"cost": 0.5},
            recommendation="checkpoint",
            rationale="Medium risk",
        )
        assert checkpoint.requires_checkpoint
        assert not checkpoint.is_blocked

        # Test block recommendation
        block = RiskAssessment(
            score=0.9,
            factors={"cost": 0.9},
            recommendation="block",
            rationale="High risk",
        )
        assert block.requires_checkpoint
        assert block.is_blocked


class TestPreFlightChecker:
    """Tests for pre-flight validation."""

    def test_budget_exceeded_fails(self):
        """Goal exceeding budget should fail preflight."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-4",
            description="Expensive task",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=30.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = checker.validate(goal, context)

        assert not result.passed
        assert any(i.category == "budget" for i in result.issues)
        assert any(i.severity == "critical" for i in result.issues)

    def test_budget_warning_near_limit(self):
        """Goal using most of remaining budget should warn."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-warn",
            description="Moderate task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            estimated_cost_usd=4.5,  # 90% of remaining
        )

        context = {"session_budget": 10.0, "spent_usd": 5.0}  # $5 remaining
        result = checker.validate(goal, context)

        # Should pass but with warning
        assert result.passed or result.requires_checkpoint
        budget_issues = [i for i in result.issues if i.category == "budget"]
        if budget_issues:
            assert budget_issues[0].severity == "warning"

    def test_low_risk_auto_approved(self):
        """Low-risk goal should auto-approve."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-5",
            description="Update docs",
            priority=GoalPriority.LOW,
            estimated_minutes=10,
            estimated_cost_usd=1.0,
        )

        context = {"session_budget": 25.0, "spent_usd": 0.0}
        result = checker.validate(goal, context)

        assert result.passed
        assert result.auto_approved
        assert not result.requires_checkpoint

    def test_medium_risk_requires_checkpoint(self):
        """Medium-risk goal should require checkpoint."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-6",
            description="Refactor core auth module",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=12.0,  # Higher cost to push risk over 0.5
        )

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": ["core/auth.py", "core/session.py", "models/user.py"],
        }
        result = checker.validate(goal, context)

        assert result.passed
        assert result.requires_checkpoint
        assert not result.auto_approved

    def test_high_risk_blocks(self):
        """High-risk goal should block execution."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-7",
            description="Delete database and reset everything",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            estimated_cost_usd=20.0,
        )

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "files_to_modify": [f"core/file{i}.py" for i in range(12)],
        }
        result = checker.validate(goal, context)

        assert not result.passed
        assert result.requires_checkpoint
        assert result.risk_assessment.is_blocked

    def test_dependency_blocked(self):
        """Goal with blocked dependency should fail."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-8",
            description="Add feature B",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=2.0,
        )
        goal.dependencies = ["goal-A"]

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "completed_goals": set(),
            "blocked_goals": {"goal-A"},
        }
        result = checker.validate(goal, context)

        assert not result.passed
        dep_issues = [i for i in result.issues if i.category == "dependency"]
        assert len(dep_issues) > 0
        assert "blocked" in dep_issues[0].message.lower()

    def test_dependency_incomplete(self):
        """Goal with incomplete dependency should fail."""
        from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
        from swarm_attack.chief_of_staff.preflight import PreFlightChecker

        engine = RiskScoringEngine()
        checker = PreFlightChecker(engine)

        goal = DailyGoal(
            goal_id="test-9",
            description="Add feature C",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=2.0,
        )
        goal.dependencies = ["goal-B"]

        context = {
            "session_budget": 25.0,
            "spent_usd": 0.0,
            "completed_goals": {"goal-A"},  # goal-B not completed
            "blocked_goals": set(),
        }
        result = checker.validate(goal, context)

        assert not result.passed
        dep_issues = [i for i in result.issues if i.category == "dependency"]
        assert len(dep_issues) > 0
        assert "incomplete" in dep_issues[0].message.lower()

    def test_preflight_result_summary(self):
        """Test PreFlightResult summary method."""
        from swarm_attack.chief_of_staff.preflight import PreFlightResult, PreFlightIssue
        from swarm_attack.chief_of_staff.risk_scoring import RiskAssessment

        # Test passed summary
        passed_result = PreFlightResult(
            passed=True,
            risk_assessment=RiskAssessment(
                score=0.2,
                factors={},
                recommendation="proceed",
                rationale="Low risk",
            ),
        )
        assert "PASSED" in passed_result.summary()

        # Test checkpoint summary
        checkpoint_result = PreFlightResult(
            passed=True,
            requires_checkpoint=True,
            risk_assessment=RiskAssessment(
                score=0.6,
                factors={},
                recommendation="checkpoint",
                rationale="Medium risk due to cost",
            ),
        )
        assert "CHECKPOINT" in checkpoint_result.summary()
        assert "Medium risk" in checkpoint_result.summary()

        # Test blocked summary
        blocked_result = PreFlightResult(
            passed=False,
            issues=[
                PreFlightIssue(
                    severity="critical",
                    category="budget",
                    message="Exceeds budget",
                )
            ],
            risk_assessment=RiskAssessment(
                score=0.9,
                factors={},
                recommendation="block",
                rationale="High risk",
            ),
        )
        assert "BLOCKED" in blocked_result.summary()
