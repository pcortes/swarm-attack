"""Tests for FeedbackIncorporator core data models and FeedbackStore."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class TestHumanFeedbackDataclass:
    """Tests for HumanFeedback dataclass."""

    def test_human_feedback_exists(self):
        """HumanFeedback class should exist."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        assert HumanFeedback is not None

    def test_human_feedback_has_required_fields(self):
        """HumanFeedback should have all required fields."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        feedback = HumanFeedback(
            checkpoint_id="cp_123",
            timestamp=datetime.now(),
            feedback_type="approval",
            content="Looks good",
            applies_to=["goal_1"],
            expires_at=None
        )
        
        assert feedback.checkpoint_id == "cp_123"
        assert isinstance(feedback.timestamp, datetime)
        assert feedback.feedback_type == "approval"
        assert feedback.content == "Looks good"
        assert feedback.applies_to == ["goal_1"]
        assert feedback.expires_at is None

    def test_human_feedback_with_expiration(self):
        """HumanFeedback should support expiration datetime."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        expires = datetime.now() + timedelta(days=7)
        feedback = HumanFeedback(
            checkpoint_id="cp_456",
            timestamp=datetime.now(),
            feedback_type="rejection",
            content="Needs more testing",
            applies_to=["goal_2", "goal_3"],
            expires_at=expires
        )
        
        assert feedback.expires_at == expires

    def test_human_feedback_to_dict(self):
        """HumanFeedback should serialize to dict."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        expires = datetime(2025, 1, 22, 10, 30, 0)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_789",
            timestamp=timestamp,
            feedback_type="modification",
            content="Change approach",
            applies_to=["goal_a"],
            expires_at=expires
        )
        
        data = feedback.to_dict()
        
        assert data["checkpoint_id"] == "cp_789"
        assert data["timestamp"] == "2025-01-15T10:30:00"
        assert data["feedback_type"] == "modification"
        assert data["content"] == "Change approach"
        assert data["applies_to"] == ["goal_a"]
        assert data["expires_at"] == "2025-01-22T10:30:00"

    def test_human_feedback_to_dict_with_none_expires(self):
        """HumanFeedback should handle None expires_at in to_dict."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_abc",
            timestamp=timestamp,
            feedback_type="approval",
            content="Approved",
            applies_to=[],
            expires_at=None
        )
        
        data = feedback.to_dict()
        assert data["expires_at"] is None

    def test_human_feedback_from_dict(self):
        """HumanFeedback should deserialize from dict."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        data = {
            "checkpoint_id": "cp_xyz",
            "timestamp": "2025-01-15T10:30:00",
            "feedback_type": "rejection",
            "content": "Not ready",
            "applies_to": ["goal_x", "goal_y"],
            "expires_at": "2025-01-22T10:30:00"
        }
        
        feedback = HumanFeedback.from_dict(data)
        
        assert feedback.checkpoint_id == "cp_xyz"
        assert feedback.timestamp == datetime(2025, 1, 15, 10, 30, 0)
        assert feedback.feedback_type == "rejection"
        assert feedback.content == "Not ready"
        assert feedback.applies_to == ["goal_x", "goal_y"]
        assert feedback.expires_at == datetime(2025, 1, 22, 10, 30, 0)

    def test_human_feedback_from_dict_with_none_expires(self):
        """HumanFeedback should handle None expires_at in from_dict."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        data = {
            "checkpoint_id": "cp_none",
            "timestamp": "2025-01-15T10:30:00",
            "feedback_type": "approval",
            "content": "OK",
            "applies_to": [],
            "expires_at": None
        }
        
        feedback = HumanFeedback.from_dict(data)
        assert feedback.expires_at is None

    def test_human_feedback_roundtrip(self):
        """HumanFeedback should survive to_dict/from_dict roundtrip."""
        from swarm_attack.chief_of_staff.feedback import HumanFeedback
        
        original = HumanFeedback(
            checkpoint_id="cp_roundtrip",
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            feedback_type="modification",
            content="Make it better",
            applies_to=["goal_1", "goal_2", "goal_3"],
            expires_at=datetime(2025, 2, 15, 10, 30, 0)
        )
        
        roundtrip = HumanFeedback.from_dict(original.to_dict())
        
        assert roundtrip.checkpoint_id == original.checkpoint_id
        assert roundtrip.timestamp == original.timestamp
        assert roundtrip.feedback_type == original.feedback_type
        assert roundtrip.content == original.content
        assert roundtrip.applies_to == original.applies_to
        assert roundtrip.expires_at == original.expires_at


class TestFeedbackStore:
    """Tests for FeedbackStore class."""

    def test_feedback_store_exists(self):
        """FeedbackStore class should exist."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore
        assert FeedbackStore is not None

    def test_feedback_store_init_with_path(self, tmp_path):
        """FeedbackStore should accept a base path."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore
        
        store = FeedbackStore(base_path=tmp_path)
        assert store.base_path == tmp_path

    def test_feedback_store_init_default_path(self, tmp_path, monkeypatch):
        """FeedbackStore should default to .swarm/feedback/ directory."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore
        
        monkeypatch.chdir(tmp_path)
        store = FeedbackStore()
        
        assert store.base_path == Path(tmp_path) / ".swarm" / "feedback"

    def test_feedback_store_creates_directory(self, tmp_path):
        """FeedbackStore should create the feedback directory."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore
        
        feedback_dir = tmp_path / "feedback"
        store = FeedbackStore(base_path=feedback_dir)
        
        # Directory should be created on first operation
        store.get_all()
        assert feedback_dir.exists()

    def test_feedback_store_add_feedback(self, tmp_path):
        """FeedbackStore should add feedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        store = FeedbackStore(base_path=tmp_path)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_add",
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            feedback_type="approval",
            content="Approved",
            applies_to=["goal_1"],
            expires_at=None
        )
        
        store.add_feedback(feedback)
        
        all_feedback = store.get_all()
        assert len(all_feedback) == 1
        assert all_feedback[0].checkpoint_id == "cp_add"

    def test_feedback_store_add_multiple_feedback(self, tmp_path):
        """FeedbackStore should add multiple feedback entries."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        store = FeedbackStore(base_path=tmp_path)
        
        for i in range(3):
            feedback = HumanFeedback(
                checkpoint_id=f"cp_{i}",
                timestamp=datetime(2025, 1, 15, 10, 30, i),
                feedback_type="approval",
                content=f"Feedback {i}",
                applies_to=[f"goal_{i}"],
                expires_at=None
            )
            store.add_feedback(feedback)
        
        all_feedback = store.get_all()
        assert len(all_feedback) == 3

    def test_feedback_store_save(self, tmp_path):
        """FeedbackStore should save feedback to JSON file."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        store = FeedbackStore(base_path=tmp_path)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_save",
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            feedback_type="approval",
            content="Saved",
            applies_to=["goal_1"],
            expires_at=None
        )
        
        store.add_feedback(feedback)
        store.save()
        
        # Verify file exists
        feedback_file = tmp_path / "feedback.json"
        assert feedback_file.exists()
        
        # Verify content
        with open(feedback_file) as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert data[0]["checkpoint_id"] == "cp_save"

    def test_feedback_store_load(self, tmp_path):
        """FeedbackStore should load feedback from JSON file."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        # Create initial store and add feedback
        store1 = FeedbackStore(base_path=tmp_path)
        
        feedback = HumanFeedback(
            checkpoint_id="cp_load",
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            feedback_type="rejection",
            content="Loaded",
            applies_to=["goal_2"],
            expires_at=datetime(2025, 2, 15, 10, 30, 0)
        )
        
        store1.add_feedback(feedback)
        store1.save()
        
        # Create new store and load
        store2 = FeedbackStore(base_path=tmp_path)
        store2.load()
        
        all_feedback = store2.get_all()
        assert len(all_feedback) == 1
        assert all_feedback[0].checkpoint_id == "cp_load"
        assert all_feedback[0].content == "Loaded"

    def test_feedback_store_load_empty(self, tmp_path):
        """FeedbackStore should handle loading when no file exists."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore
        
        store = FeedbackStore(base_path=tmp_path)
        store.load()  # Should not raise
        
        all_feedback = store.get_all()
        assert len(all_feedback) == 0

    def test_feedback_store_get_all_returns_list(self, tmp_path):
        """FeedbackStore.get_all() should return a list of HumanFeedback."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        store = FeedbackStore(base_path=tmp_path)
        
        result = store.get_all()
        assert isinstance(result, list)

    def test_feedback_store_persistence_roundtrip(self, tmp_path):
        """FeedbackStore should persist and reload correctly."""
        from swarm_attack.chief_of_staff.feedback import FeedbackStore, HumanFeedback
        
        store1 = FeedbackStore(base_path=tmp_path)
        
        feedbacks = [
            HumanFeedback(
                checkpoint_id="cp_1",
                timestamp=datetime(2025, 1, 15, 10, 30, 0),
                feedback_type="approval",
                content="First",
                applies_to=["goal_1"],
                expires_at=None
            ),
            HumanFeedback(
                checkpoint_id="cp_2",
                timestamp=datetime(2025, 1, 16, 11, 30, 0),
                feedback_type="rejection",
                content="Second",
                applies_to=["goal_2", "goal_3"],
                expires_at=datetime(2025, 2, 16, 11, 30, 0)
            ),
        ]
        
        for fb in feedbacks:
            store1.add_feedback(fb)
        store1.save()
        
        # Create new store and load
        store2 = FeedbackStore(base_path=tmp_path)
        store2.load()
        
        loaded = store2.get_all()
        assert len(loaded) == 2
        assert loaded[0].checkpoint_id == "cp_1"
        assert loaded[1].checkpoint_id == "cp_2"
        assert loaded[1].applies_to == ["goal_2", "goal_3"]


class TestFeedbackFileExists:
    """Tests for feedback module file existence."""

    def test_feedback_module_exists(self):
        """The feedback.py module should exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "feedback.py"
        assert path.exists(), "swarm_attack/chief_of_staff/feedback.py must exist"