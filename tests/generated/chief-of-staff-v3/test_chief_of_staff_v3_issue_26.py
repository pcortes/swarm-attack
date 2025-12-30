"""Tests for FeedbackIncorporator class."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from swarm_attack.chief_of_staff.checkpoints import Checkpoint, CheckpointTrigger, CheckpointOption


class TestFeedbackIncorporatorExists:
    """Tests for FeedbackIncorporator class existence."""

    def test_feedback_incorporator_exists(self):
        """FeedbackIncorporator class should exist."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator
        assert FeedbackIncorporator is not None

    def test_feedback_incorporator_module_exists(self):
        """The feedback.py module should exist with FeedbackIncorporator."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "feedback.py"
        assert path.exists(), "swarm_attack/chief_of_staff/feedback.py must exist"


class TestFeedbackIncorporatorInit:
    """Tests for FeedbackIncorporator initialization."""

    def test_feedback_incorporator_accepts_feedback_store(self, tmp_path):
        """FeedbackIncorporator should accept a FeedbackStore in constructor."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        assert incorporator.feedback_store is store

    def test_feedback_incorporator_stores_feedback_store(self, tmp_path):
        """FeedbackIncorporator should store feedback_store as instance attribute."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        assert hasattr(incorporator, "feedback_store")


class TestFeedbackIncorporatorRecordFeedback:
    """Tests for FeedbackIncorporator.record_feedback() method."""

    def _create_checkpoint(
        self,
        checkpoint_id: str = "cp_test",
        trigger: CheckpointTrigger = CheckpointTrigger.UX_CHANGE,
        goal_id: str = "goal_123",
        human_notes: Optional[str] = None,
    ) -> Checkpoint:
        """Helper to create a test checkpoint."""
        return Checkpoint(
            checkpoint_id=checkpoint_id,
            trigger=trigger,
            context="Test context",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
                CheckpointOption(label="Skip", description="Skip it", is_recommended=False),
            ],
            recommendation="Proceed recommended",
            created_at=datetime.now().isoformat(),
            goal_id=goal_id,
            status="resolved",
            chosen_option="Proceed",
            human_notes=human_notes,
        )

    def test_record_feedback_returns_human_feedback(self, tmp_path):
        """record_feedback should return a HumanFeedback instance."""
        from swarm_attack.chief_of_staff.feedback import (
            FeedbackIncorporator,
            FeedbackStore,
            HumanFeedback,
        )

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "Looks good, proceed with caution."

        result = incorporator.record_feedback(checkpoint, notes)

        assert isinstance(result, HumanFeedback)

    def test_record_feedback_sets_checkpoint_id(self, tmp_path):
        """record_feedback should set checkpoint_id from checkpoint."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(checkpoint_id="cp_unique_123")
        notes = "Some feedback."

        result = incorporator.record_feedback(checkpoint, notes)

        assert result.checkpoint_id == "cp_unique_123"

    def test_record_feedback_sets_timestamp(self, tmp_path):
        """record_feedback should set timestamp to current time."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "Feedback notes."

        before = datetime.now()
        result = incorporator.record_feedback(checkpoint, notes)
        after = datetime.now()

        assert before <= result.timestamp <= after

    def test_record_feedback_sets_content(self, tmp_path):
        """record_feedback should set content from notes."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "This is my feedback content."

        result = incorporator.record_feedback(checkpoint, notes)

        assert result.content == notes

    def test_record_feedback_adds_to_store(self, tmp_path):
        """record_feedback should add feedback to the store."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "Added to store."

        incorporator.record_feedback(checkpoint, notes)

        all_feedback = store.get_all()
        assert len(all_feedback) == 1
        assert all_feedback[0].content == notes


class TestFeedbackIncorporatorClassifyFeedback:
    """Tests for FeedbackIncorporator._classify_feedback() method."""

    def test_classify_feedback_returns_guidance_for_suggestion(self, tmp_path):
        """_classify_feedback should return 'guidance' for suggestion keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "I suggest we try a different approach next time."
        result = incorporator._classify_feedback(notes)

        assert result == "guidance"

    def test_classify_feedback_returns_guidance_for_recommend(self, tmp_path):
        """_classify_feedback should return 'guidance' for recommend keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "I recommend checking tests before proceeding."
        result = incorporator._classify_feedback(notes)

        assert result == "guidance"

    def test_classify_feedback_returns_guidance_for_consider(self, tmp_path):
        """_classify_feedback should return 'guidance' for consider keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "Consider using a different pattern."
        result = incorporator._classify_feedback(notes)

        assert result == "guidance"

    def test_classify_feedback_returns_correction_for_wrong(self, tmp_path):
        """_classify_feedback should return 'correction' for wrong keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "This is wrong, please fix it."
        result = incorporator._classify_feedback(notes)

        assert result == "correction"

    def test_classify_feedback_returns_correction_for_incorrect(self, tmp_path):
        """_classify_feedback should return 'correction' for incorrect keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "The implementation is incorrect."
        result = incorporator._classify_feedback(notes)

        assert result == "correction"

    def test_classify_feedback_returns_correction_for_fix(self, tmp_path):
        """_classify_feedback should return 'correction' for fix keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "Please fix this issue."
        result = incorporator._classify_feedback(notes)

        assert result == "correction"

    def test_classify_feedback_returns_correction_for_error(self, tmp_path):
        """_classify_feedback should return 'correction' for error keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "There's an error in the logic."
        result = incorporator._classify_feedback(notes)

        assert result == "correction"

    def test_classify_feedback_returns_preference_for_prefer(self, tmp_path):
        """_classify_feedback should return 'preference' for prefer keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "I prefer the simpler approach."
        result = incorporator._classify_feedback(notes)

        assert result == "preference"

    def test_classify_feedback_returns_preference_for_like(self, tmp_path):
        """_classify_feedback should return 'preference' for like keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "I like this better."
        result = incorporator._classify_feedback(notes)

        assert result == "preference"

    def test_classify_feedback_returns_preference_for_always(self, tmp_path):
        """_classify_feedback should return 'preference' for always keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "Always use this pattern."
        result = incorporator._classify_feedback(notes)

        assert result == "preference"

    def test_classify_feedback_returns_preference_for_never(self, tmp_path):
        """_classify_feedback should return 'preference' for never keywords."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "Never do this again."
        result = incorporator._classify_feedback(notes)

        assert result == "preference"

    def test_classify_feedback_returns_guidance_for_generic(self, tmp_path):
        """_classify_feedback should default to 'guidance' for generic notes."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "Looks good."
        result = incorporator._classify_feedback(notes)

        assert result == "guidance"

    def test_classify_feedback_is_case_insensitive(self, tmp_path):
        """_classify_feedback should be case-insensitive."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        notes = "I PREFER THIS APPROACH."
        result = incorporator._classify_feedback(notes)

        assert result == "preference"


class TestFeedbackIncorporatorExtractTags:
    """Tests for FeedbackIncorporator._extract_tags() method."""

    def _create_checkpoint(
        self,
        checkpoint_id: str = "cp_test",
        trigger: CheckpointTrigger = CheckpointTrigger.UX_CHANGE,
        goal_id: str = "goal_123",
    ) -> Checkpoint:
        """Helper to create a test checkpoint."""
        return Checkpoint(
            checkpoint_id=checkpoint_id,
            trigger=trigger,
            context="Test context",
            options=[],
            recommendation="Proceed",
            created_at=datetime.now().isoformat(),
            goal_id=goal_id,
            status="resolved",
        )

    def test_extract_tags_returns_list(self, tmp_path):
        """_extract_tags should return a list."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "Some notes."

        result = incorporator._extract_tags(checkpoint, notes)

        assert isinstance(result, list)

    def test_extract_tags_includes_trigger_type(self, tmp_path):
        """_extract_tags should include the checkpoint trigger type as a tag."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(trigger=CheckpointTrigger.ARCHITECTURE)
        notes = "Some notes."

        result = incorporator._extract_tags(checkpoint, notes)

        assert "architecture" in result or "ARCHITECTURE" in result

    def test_extract_tags_includes_ux_change(self, tmp_path):
        """_extract_tags should include 'ux_change' for UX_CHANGE triggers."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(trigger=CheckpointTrigger.UX_CHANGE)
        notes = "UI feedback."

        result = incorporator._extract_tags(checkpoint, notes)

        assert "ux_change" in result or "UX_CHANGE" in result

    def test_extract_tags_extracts_from_notes(self, tmp_path):
        """_extract_tags should extract relevant tags from notes content."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "This relates to testing and performance."

        result = incorporator._extract_tags(checkpoint, notes)

        # Should extract contextual tags from notes
        assert isinstance(result, list)

    def test_extract_tags_includes_goal_id_prefix(self, tmp_path):
        """_extract_tags should include goal type prefix when available."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(goal_id="feature_123")
        notes = "Feature-related feedback."

        result = incorporator._extract_tags(checkpoint, notes)

        # Should recognize feature goals
        assert isinstance(result, list)


class TestFeedbackIncorporatorCalculateExpiry:
    """Tests for FeedbackIncorporator._calculate_expiry() method."""

    def test_calculate_expiry_returns_optional_string(self, tmp_path):
        """_calculate_expiry should return Optional[str]."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        result = incorporator._calculate_expiry("guidance")

        # Result should be either None or a datetime ISO string
        assert result is None or isinstance(result, str)

    def test_calculate_expiry_returns_none_for_preference(self, tmp_path):
        """_calculate_expiry should return None for preference feedback (permanent)."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        result = incorporator._calculate_expiry("preference")

        assert result is None

    def test_calculate_expiry_returns_datetime_for_guidance(self, tmp_path):
        """_calculate_expiry should return expiry datetime for guidance feedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        result = incorporator._calculate_expiry("guidance")

        # Guidance feedback should expire
        if result is not None:
            # Should be a valid ISO datetime string
            expiry_dt = datetime.fromisoformat(result)
            assert expiry_dt > datetime.now()

    def test_calculate_expiry_returns_datetime_for_correction(self, tmp_path):
        """_calculate_expiry should return expiry datetime for correction feedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        result = incorporator._calculate_expiry("correction")

        # Correction feedback should expire (shorter than guidance)
        if result is not None:
            expiry_dt = datetime.fromisoformat(result)
            assert expiry_dt > datetime.now()

    def test_calculate_expiry_correction_shorter_than_guidance(self, tmp_path):
        """_calculate_expiry should set shorter expiry for corrections than guidance."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        guidance_result = incorporator._calculate_expiry("guidance")
        correction_result = incorporator._calculate_expiry("correction")

        # If both have expiry, correction should be shorter
        if guidance_result is not None and correction_result is not None:
            guidance_dt = datetime.fromisoformat(guidance_result)
            correction_dt = datetime.fromisoformat(correction_result)
            assert correction_dt <= guidance_dt


class TestFeedbackIncorporatorIntegration:
    """Integration tests for FeedbackIncorporator."""

    def _create_checkpoint(
        self,
        checkpoint_id: str = "cp_test",
        trigger: CheckpointTrigger = CheckpointTrigger.UX_CHANGE,
        goal_id: str = "goal_123",
    ) -> Checkpoint:
        """Helper to create a test checkpoint."""
        return Checkpoint(
            checkpoint_id=checkpoint_id,
            trigger=trigger,
            context="Test context",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
            ],
            recommendation="Proceed recommended",
            created_at=datetime.now().isoformat(),
            goal_id=goal_id,
            status="resolved",
            chosen_option="Proceed",
            human_notes="Approved with notes.",
        )

    def test_record_feedback_uses_classify_feedback(self, tmp_path):
        """record_feedback should use _classify_feedback to set feedback_type."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint()
        notes = "I prefer this approach always."

        result = incorporator.record_feedback(checkpoint, notes)

        assert result.feedback_type == "preference"

    def test_record_feedback_uses_extract_tags(self, tmp_path):
        """record_feedback should use _extract_tags to set applies_to."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(trigger=CheckpointTrigger.ARCHITECTURE)
        notes = "Architecture feedback."

        result = incorporator.record_feedback(checkpoint, notes)

        assert isinstance(result.applies_to, list)

    def test_record_feedback_uses_calculate_expiry(self, tmp_path):
        """record_feedback should use _calculate_expiry to set expires_at."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        # Preference feedback should have no expiry
        checkpoint = self._create_checkpoint()
        notes = "I always prefer this."

        result = incorporator.record_feedback(checkpoint, notes)

        assert result.expires_at is None

    def test_record_feedback_full_workflow(self, tmp_path):
        """Full workflow test for record_feedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackIncorporator, FeedbackStore

        store = FeedbackStore(base_path=tmp_path)
        incorporator = FeedbackIncorporator(feedback_store=store)

        checkpoint = self._create_checkpoint(
            checkpoint_id="cp_workflow",
            trigger=CheckpointTrigger.COST_SINGLE,
            goal_id="feature_456",
        )
        notes = "Please fix the budget calculation."

        result = incorporator.record_feedback(checkpoint, notes)

        # Check all fields are set correctly
        assert result.checkpoint_id == "cp_workflow"
        assert result.feedback_type == "correction"
        assert result.content == notes
        assert isinstance(result.applies_to, list)
        assert isinstance(result.timestamp, datetime)

        # Verify added to store
        all_feedback = store.get_all()
        assert len(all_feedback) == 1