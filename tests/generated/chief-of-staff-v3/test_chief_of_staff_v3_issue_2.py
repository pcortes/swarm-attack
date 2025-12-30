"""Tests for PreferenceLearner.find_similar_decisions() method."""

import pytest
from datetime import datetime, timedelta
from swarm_attack.chief_of_staff.episodes import PreferenceLearner, PreferenceSignal


class MockDailyGoal:
    """Mock DailyGoal for testing."""
    
    def __init__(self, tags: list[str] | None = None):
        self.tags = tags or []


class TestFindSimilarDecisions:
    """Tests for find_similar_decisions method."""
    
    def test_method_exists(self):
        """PreferenceLearner has find_similar_decisions method."""
        learner = PreferenceLearner()
        assert hasattr(learner, 'find_similar_decisions')
        assert callable(getattr(learner, 'find_similar_decisions'))
    
    def test_returns_list(self):
        """Method returns a list."""
        learner = PreferenceLearner()
        goal = MockDailyGoal()
        result = learner.find_similar_decisions(goal)
        assert isinstance(result, list)
    
    def test_returns_empty_list_when_no_signals(self):
        """Returns empty list when no signals recorded."""
        learner = PreferenceLearner()
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)
        assert result == []
    
    def test_returns_dicts_with_required_keys(self):
        """Each result dict has required keys."""
        learner = PreferenceLearner()
        signal = PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="UI button change",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        )
        learner.signals.append(signal)
        
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 1
        assert "trigger" in result[0]
        assert "context_summary" in result[0]
        assert "was_accepted" in result[0]
        assert "chosen_option" in result[0]
        assert "timestamp" in result[0]
    
    def test_finds_ux_change_for_ui_tag(self):
        """UX_CHANGE signals match goals with 'ui' tag."""
        learner = PreferenceLearner()
        signal = PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="Updated button styling",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        )
        learner.signals.append(signal)
        
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 1
        assert result[0]["trigger"] == "UX_CHANGE"
    
    def test_finds_ux_change_for_ux_tag(self):
        """UX_CHANGE signals match goals with 'ux' tag."""
        learner = PreferenceLearner()
        signal = PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="Improved UX flow",
            was_accepted=False,
            chosen_option="reject",
            timestamp=datetime.now()
        )
        learner.signals.append(signal)
        
        goal = MockDailyGoal(tags=["ux"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 1
        assert result[0]["was_accepted"] is False
    
    def test_finds_architecture_for_architecture_tag(self):
        """ARCHITECTURE signals match goals with 'architecture' tag."""
        learner = PreferenceLearner()
        signal = PreferenceSignal(
            trigger="ARCHITECTURE",
            context_summary="Refactored module structure",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        )
        learner.signals.append(signal)
        
        goal = MockDailyGoal(tags=["architecture"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 1
        assert result[0]["trigger"] == "ARCHITECTURE"
    
    def test_finds_architecture_for_refactor_tag(self):
        """ARCHITECTURE signals match goals with 'refactor' tag."""
        learner = PreferenceLearner()
        signal = PreferenceSignal(
            trigger="ARCHITECTURE",
            context_summary="Code refactoring",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        )
        learner.signals.append(signal)
        
        goal = MockDailyGoal(tags=["refactor"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 1
    
    def test_cost_triggers_always_included(self):
        """COST_SINGLE and COST_CUMULATIVE always considered relevant."""
        learner = PreferenceLearner()
        learner.signals.append(PreferenceSignal(
            trigger="COST_SINGLE",
            context_summary="High cost action",
            was_accepted=False,
            chosen_option="reject",
            timestamp=datetime.now()
        ))
        learner.signals.append(PreferenceSignal(
            trigger="COST_CUMULATIVE",
            context_summary="Budget exceeded",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        ))
        
        # Even with unrelated tags, cost triggers should be included
        goal = MockDailyGoal(tags=["documentation"])
        result = learner.find_similar_decisions(goal)
        
        triggers = [r["trigger"] for r in result]
        assert "COST_SINGLE" in triggers
        assert "COST_CUMULATIVE" in triggers
    
    def test_sorted_by_recency_most_recent_first(self):
        """Results sorted by timestamp, most recent first."""
        learner = PreferenceLearner()
        now = datetime.now()
        
        learner.signals.append(PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="Old change",
            was_accepted=True,
            chosen_option="approve",
            timestamp=now - timedelta(days=3)
        ))
        learner.signals.append(PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="Recent change",
            was_accepted=True,
            chosen_option="approve",
            timestamp=now - timedelta(days=1)
        ))
        learner.signals.append(PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="Middle change",
            was_accepted=True,
            chosen_option="approve",
            timestamp=now - timedelta(days=2)
        ))
        
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)
        
        assert len(result) == 3
        assert result[0]["context_summary"] == "Recent change"
        assert result[1]["context_summary"] == "Middle change"
        assert result[2]["context_summary"] == "Old change"
    
    def test_respects_k_limit(self):
        """Returns at most k results."""
        learner = PreferenceLearner()
        now = datetime.now()
        
        for i in range(5):
            learner.signals.append(PreferenceSignal(
                trigger="UX_CHANGE",
                context_summary=f"Change {i}",
                was_accepted=True,
                chosen_option="approve",
                timestamp=now - timedelta(days=i)
            ))
        
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal, k=3)
        
        assert len(result) == 3
    
    def test_default_k_is_3(self):
        """Default k parameter is 3."""
        learner = PreferenceLearner()
        now = datetime.now()
        
        for i in range(5):
            learner.signals.append(PreferenceSignal(
                trigger="UX_CHANGE",
                context_summary=f"Change {i}",
                was_accepted=True,
                chosen_option="approve",
                timestamp=now - timedelta(days=i)
            ))
        
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)  # No k specified
        
        assert len(result) == 3
    
    def test_was_accepted_flag_correct(self):
        """was_accepted flag reflects actual signal value."""
        learner = PreferenceLearner()
        learner.signals.append(PreferenceSignal(
            trigger="COST_SINGLE",
            context_summary="Accepted cost",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        ))
        learner.signals.append(PreferenceSignal(
            trigger="COST_CUMULATIVE",
            context_summary="Rejected cost",
            was_accepted=False,
            chosen_option="reject",
            timestamp=datetime.now()
        ))
        
        goal = MockDailyGoal(tags=[])
        result = learner.find_similar_decisions(goal)
        
        accepted = [r for r in result if r["context_summary"] == "Accepted cost"]
        rejected = [r for r in result if r["context_summary"] == "Rejected cost"]
        
        assert accepted[0]["was_accepted"] is True
        assert rejected[0]["was_accepted"] is False
    
    def test_does_not_match_unrelated_triggers(self):
        """Non-matching triggers (except cost) are excluded."""
        learner = PreferenceLearner()
        learner.signals.append(PreferenceSignal(
            trigger="ARCHITECTURE",
            context_summary="Arch change",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        ))
        
        # Goal with 'ui' tag should not match ARCHITECTURE trigger
        goal = MockDailyGoal(tags=["ui"])
        result = learner.find_similar_decisions(goal)
        
        # Should be empty - ARCHITECTURE doesn't match 'ui' tag
        assert len(result) == 0
    
    def test_multiple_matching_tags(self):
        """Goals with multiple tags find all matching signals."""
        learner = PreferenceLearner()
        learner.signals.append(PreferenceSignal(
            trigger="UX_CHANGE",
            context_summary="UI update",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        ))
        learner.signals.append(PreferenceSignal(
            trigger="ARCHITECTURE",
            context_summary="Refactor",
            was_accepted=True,
            chosen_option="approve",
            timestamp=datetime.now()
        ))
        
        goal = MockDailyGoal(tags=["ui", "refactor"])
        result = learner.find_similar_decisions(goal, k=10)
        
        triggers = [r["trigger"] for r in result]
        assert "UX_CHANGE" in triggers
        assert "ARCHITECTURE" in triggers