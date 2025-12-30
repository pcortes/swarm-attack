"""Tests for FeedbackIncorporator retrieval and context building."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from swarm_attack.chief_of_staff.feedback import (
    HumanFeedback,
    FeedbackStore,
    FeedbackIncorporator,
)


class TestFeedbackIncorporatorGetRelevantFeedback:
    """Tests for get_relevant_feedback method."""

    def test_method_exists(self):
        """FeedbackIncorporator should have get_relevant_feedback method."""
        assert hasattr(FeedbackIncorporator, "get_relevant_feedback")

    def test_returns_list(self, tmp_path):
        """get_relevant_feedback should return a list."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        goal = MagicMock()
        goal.tags = []
        goal.goal_type = "feature"
        result = incorporator.get_relevant_feedback(goal)
        assert isinstance(result, list)

    def test_filters_by_tags(self, tmp_path):
        """Should return feedback matching goal tags."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        # Add feedback with different tags
        feedback1 = HumanFeedback(
            checkpoint_id="cp1",
            decision="approved",
            notes="Good work",
            timestamp=datetime.now().isoformat(),
            tags=["feature", "api"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        feedback2 = HumanFeedback(
            checkpoint_id="cp2",
            decision="rejected",
            notes="Bad approach",
            timestamp=datetime.now().isoformat(),
            tags=["bugfix"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback1)
        store.save(feedback2)
        
        goal = MagicMock()
        goal.tags = ["feature"]
        goal.goal_type = "feature"
        
        result = incorporator.get_relevant_feedback(goal)
        assert len(result) >= 1
        # Should include feedback1 which has "feature" tag
        checkpoint_ids = [f.checkpoint_id for f in result]
        assert "cp1" in checkpoint_ids

    def test_excludes_expired_feedback(self, tmp_path):
        """Should not return expired feedback."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        # Add expired feedback
        expired_feedback = HumanFeedback(
            checkpoint_id="expired",
            decision="approved",
            notes="Old feedback",
            timestamp=(datetime.now() - timedelta(days=10)).isoformat(),
            tags=["feature"],
            expires_at=(datetime.now() - timedelta(days=3)).isoformat(),
        )
        # Add valid feedback
        valid_feedback = HumanFeedback(
            checkpoint_id="valid",
            decision="approved",
            notes="Recent feedback",
            timestamp=datetime.now().isoformat(),
            tags=["feature"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(expired_feedback)
        store.save(valid_feedback)
        
        goal = MagicMock()
        goal.tags = ["feature"]
        goal.goal_type = "feature"
        
        result = incorporator.get_relevant_feedback(goal)
        checkpoint_ids = [f.checkpoint_id for f in result]
        assert "expired" not in checkpoint_ids
        assert "valid" in checkpoint_ids

    def test_matches_goal_type_as_tag(self, tmp_path):
        """Should match feedback when goal_type matches a feedback tag."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_type",
            decision="approved",
            notes="Type match",
            timestamp=datetime.now().isoformat(),
            tags=["bugfix"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback)
        
        goal = MagicMock()
        goal.tags = []
        goal.goal_type = "bugfix"
        
        result = incorporator.get_relevant_feedback(goal)
        checkpoint_ids = [f.checkpoint_id for f in result]
        assert "cp_type" in checkpoint_ids


class TestFeedbackIncorporatorBuildFeedbackContext:
    """Tests for build_feedback_context method."""

    def test_method_exists(self):
        """FeedbackIncorporator should have build_feedback_context method."""
        assert hasattr(FeedbackIncorporator, "build_feedback_context")

    def test_returns_string(self, tmp_path):
        """build_feedback_context should return a string."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        goal = MagicMock()
        goal.tags = []
        goal.goal_type = "feature"
        result = incorporator.build_feedback_context(goal)
        assert isinstance(result, str)

    def test_context_starts_with_header(self, tmp_path):
        """Context should start with proper header."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_header",
            decision="approved",
            notes="Test feedback",
            timestamp=datetime.now().isoformat(),
            tags=["feature"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback)
        
        goal = MagicMock()
        goal.tags = ["feature"]
        goal.goal_type = "feature"
        
        result = incorporator.build_feedback_context(goal)
        assert result.startswith("## Human Feedback from Recent Checkpoints")

    def test_empty_context_when_no_feedback(self, tmp_path):
        """Should return empty string when no relevant feedback."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        goal = MagicMock()
        goal.tags = ["nonexistent"]
        goal.goal_type = "nonexistent"
        
        result = incorporator.build_feedback_context(goal)
        assert result == ""

    def test_context_includes_feedback_notes(self, tmp_path):
        """Context should include feedback notes."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_notes",
            decision="approved",
            notes="Important note to include",
            timestamp=datetime.now().isoformat(),
            tags=["feature"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback)
        
        goal = MagicMock()
        goal.tags = ["feature"]
        goal.goal_type = "feature"
        
        result = incorporator.build_feedback_context(goal)
        assert "Important note to include" in result

    def test_context_includes_decision(self, tmp_path):
        """Context should indicate the decision made."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_decision",
            decision="rejected",
            notes="Rejected for good reason",
            timestamp=datetime.now().isoformat(),
            tags=["feature"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback)
        
        goal = MagicMock()
        goal.tags = ["feature"]
        goal.goal_type = "feature"
        
        result = incorporator.build_feedback_context(goal)
        assert "rejected" in result.lower() or "Rejected" in result


class TestFeedbackIncorporatorContextFormat:
    """Tests for context string format."""

    def test_context_format_prompt_ready(self, tmp_path):
        """Context should be ready for injection into prompts."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_format",
            decision="approved",
            notes="Follow this pattern",
            timestamp=datetime.now().isoformat(),
            tags=["api"],
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        store.save(feedback)
        
        goal = MagicMock()
        goal.tags = ["api"]
        goal.goal_type = "feature"
        
        result = incorporator.build_feedback_context(goal)
        # Should be a well-formed markdown section
        assert "##" in result
        assert "\n" in result

    def test_multiple_feedback_items_formatted(self, tmp_path):
        """Multiple feedback items should be formatted clearly."""
        store = FeedbackStore(tmp_path)
        incorporator = FeedbackIncorporator(store)
        
        for i in range(3):
            feedback = HumanFeedback(
                checkpoint_id=f"cp_multi_{i}",
                decision="approved",
                notes=f"Feedback item {i}",
                timestamp=datetime.now().isoformat(),
                tags=["testing"],
                expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
            )
            store.save(feedback)
        
        goal = MagicMock()
        goal.tags = ["testing"]
        goal.goal_type = "feature"
        
        result = incorporator.build_feedback_context(goal)
        # All three items should appear
        assert "Feedback item 0" in result
        assert "Feedback item 1" in result
        assert "Feedback item 2" in result


class TestFeedbackIncorporatorFileExists:
    """Tests that implementation file exists."""

    def test_feedback_module_exists(self):
        """feedback.py module should exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "feedback.py"
        assert path.exists(), "feedback.py must exist"

    def test_has_get_relevant_feedback(self):
        """FeedbackIncorporator should have get_relevant_feedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator
        assert callable(getattr(FeedbackIncorporator, "get_relevant_feedback", None))

    def test_has_build_feedback_context(self):
        """FeedbackIncorporator should have build_feedback_context."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator
        assert callable(getattr(FeedbackIncorporator, "build_feedback_context", None))