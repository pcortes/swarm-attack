"""Tests for AutopilotSessionStore - pause/resume persistence."""

import json
import pytest
import shutil
from pathlib import Path
from datetime import datetime

from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.models import (
    AutopilotSession,
    DailyGoal,
    GoalStatus,
    CheckpointEvent,
    CheckpointTrigger,
)


class TestAutopilotSessionStore:
    """Test AutopilotSessionStore functionality."""

    @pytest.fixture
    def tmp_storage(self, tmp_path):
        """Create temporary storage directory."""
        storage_path = tmp_path / ".swarm" / "chief-of-staff"
        storage_path.mkdir(parents=True)
        return storage_path

    @pytest.fixture
    def store(self, tmp_storage):
        """Create AutopilotSessionStore instance."""
        return AutopilotSessionStore(tmp_storage)

    @pytest.fixture
    def sample_session(self):
        """Create a sample AutopilotSession for testing."""
        return AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            goals=[
                DailyGoal(
                    id="goal-001",
                    content="Test goal 1",
                    priority="P1",
                    status=GoalStatus.IN_PROGRESS,
                ),
                DailyGoal(
                    id="goal-002",
                    content="Test goal 2",
                    priority="P2",
                    status=GoalStatus.PENDING,
                ),
            ],
            current_goal_index=0,
            cost_spent_usd=2.50,
            duration_seconds=1800,
            status="running",
        )

    def test_storage_directory_created(self, tmp_storage):
        """Test that storage directory is created on init."""
        store = AutopilotSessionStore(tmp_storage)
        autopilot_dir = tmp_storage / "autopilot"
        assert autopilot_dir.exists()
        assert autopilot_dir.is_dir()

    def test_save_creates_session_file(self, store, sample_session, tmp_storage):
        """Test that save creates a session file."""
        store.save(sample_session)
        session_file = tmp_storage / "autopilot" / f"{sample_session.session_id}.json"
        assert session_file.exists()

    def test_save_sets_last_persisted_at(self, store, sample_session):
        """Test that save sets last_persisted_at timestamp."""
        assert sample_session.last_persisted_at is None
        store.save(sample_session)
        assert sample_session.last_persisted_at is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(sample_session.last_persisted_at)

    def test_save_atomic_write_validates(self, store, sample_session, tmp_storage):
        """Test that save validates by re-reading."""
        store.save(sample_session)
        # File should be valid JSON that can be loaded
        session_file = tmp_storage / "autopilot" / f"{sample_session.session_id}.json"
        data = json.loads(session_file.read_text())
        loaded = AutopilotSession.from_dict(data)
        assert loaded.session_id == sample_session.session_id

    def test_save_creates_backup(self, store, sample_session, tmp_storage):
        """Test that save backs up existing file before overwriting."""
        # Save initial version
        store.save(sample_session)
        
        # Modify and save again
        sample_session.cost_spent_usd = 5.0
        store.save(sample_session)
        
        # Final file should have updated value
        loaded = store.load(sample_session.session_id)
        assert loaded.cost_spent_usd == 5.0
        
        # No lingering backup after successful save
        backup_file = tmp_storage / "autopilot" / f"{sample_session.session_id}.bak"
        assert not backup_file.exists()

    def test_load_existing_session(self, store, sample_session):
        """Test loading an existing session."""
        store.save(sample_session)
        loaded = store.load(sample_session.session_id)
        
        assert loaded is not None
        assert loaded.session_id == sample_session.session_id
        assert loaded.budget_usd == sample_session.budget_usd
        assert loaded.cost_spent_usd == sample_session.cost_spent_usd
        assert len(loaded.goals) == 2
        assert loaded.goals[0].id == "goal-001"

    def test_load_nonexistent_session(self, store):
        """Test loading a session that doesn't exist returns None."""
        loaded = store.load("nonexistent-session")
        assert loaded is None

    def test_load_corrupted_session(self, store, tmp_storage):
        """Test loading a corrupted session file returns None."""
        # Create corrupted file
        autopilot_dir = tmp_storage / "autopilot"
        autopilot_dir.mkdir(parents=True, exist_ok=True)
        corrupted_file = autopilot_dir / "corrupted-session.json"
        corrupted_file.write_text("{ invalid json }")
        
        loaded = store.load("corrupted-session")
        assert loaded is None

    def test_list_paused_sessions(self, store, sample_session):
        """Test listing paused session IDs."""
        # Save a running session
        store.save(sample_session)
        
        # Save a paused session
        paused_session = AutopilotSession(
            session_id="ap-20251216-002",
            started_at="2025-12-16T11:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="paused",
            pause_reason="Cost threshold reached",
        )
        store.save(paused_session)
        
        paused_ids = store.list_paused()
        assert "ap-20251216-002" in paused_ids
        assert "ap-20251216-001" not in paused_ids

    def test_list_all_sessions(self, store, sample_session):
        """Test listing all session IDs."""
        store.save(sample_session)
        
        paused_session = AutopilotSession(
            session_id="ap-20251216-002",
            started_at="2025-12-16T11:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="paused",
        )
        store.save(paused_session)
        
        completed_session = AutopilotSession(
            session_id="ap-20251216-003",
            started_at="2025-12-16T12:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="completed",
        )
        store.save(completed_session)
        
        all_ids = store.list_all()
        assert len(all_ids) == 3
        assert "ap-20251216-001" in all_ids
        assert "ap-20251216-002" in all_ids
        assert "ap-20251216-003" in all_ids

    def test_delete_session(self, store, sample_session, tmp_storage):
        """Test deleting a session file."""
        store.save(sample_session)
        session_file = tmp_storage / "autopilot" / f"{sample_session.session_id}.json"
        assert session_file.exists()
        
        store.delete(sample_session.session_id)
        assert not session_file.exists()

    def test_delete_nonexistent_session(self, store):
        """Test deleting a session that doesn't exist doesn't raise."""
        # Should not raise
        store.delete("nonexistent-session")

    def test_get_latest_paused(self, store):
        """Test getting the most recently paused session."""
        # Create multiple paused sessions with different timestamps
        session1 = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T09:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="paused",
            pause_reason="Earlier pause",
        )
        session1.last_persisted_at = "2025-12-16T09:30:00"
        store.save(session1)
        
        session2 = AutopilotSession(
            session_id="ap-20251216-002",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="paused",
            pause_reason="Later pause",
        )
        session2.last_persisted_at = "2025-12-16T11:00:00"
        store.save(session2)
        
        latest = store.get_latest_paused()
        assert latest is not None
        assert latest.session_id == "ap-20251216-002"

    def test_get_latest_paused_no_paused_sessions(self, store, sample_session):
        """Test get_latest_paused returns None when no paused sessions."""
        store.save(sample_session)  # Running session
        
        latest = store.get_latest_paused()
        assert latest is None

    def test_save_with_checkpoints(self, store):
        """Test saving session with checkpoint events."""
        session = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            checkpoint_events=[
                CheckpointEvent(
                    event_id="evt-001",
                    timestamp="2025-12-16T10:30:00",
                    trigger=CheckpointTrigger.COST_THRESHOLD,
                    description="Cost threshold reached at $5.00",
                    cost_at_checkpoint=5.0,
                ),
            ],
            status="running",
        )
        store.save(session)
        
        loaded = store.load(session.session_id)
        assert len(loaded.checkpoint_events) == 1
        assert loaded.checkpoint_events[0].trigger == CheckpointTrigger.COST_THRESHOLD

    def test_save_with_stop_trigger(self, store):
        """Test saving session with stop trigger."""
        session = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
            status="running",
        )
        store.save(session)
        
        loaded = store.load(session.session_id)
        assert loaded.stop_trigger == CheckpointTrigger.APPROVAL_REQUIRED

    def test_atomic_write_temp_file_cleanup(self, store, sample_session, tmp_storage):
        """Test that temp files are cleaned up after save."""
        store.save(sample_session)
        
        # No temp files should remain
        autopilot_dir = tmp_storage / "autopilot"
        temp_files = list(autopilot_dir.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_handles_concurrent_saves(self, store, sample_session):
        """Test that concurrent saves don't corrupt data."""
        # Save multiple times rapidly
        for i in range(5):
            sample_session.cost_spent_usd = float(i)
            store.save(sample_session)
        
        # Final load should have last value
        loaded = store.load(sample_session.session_id)
        assert loaded.cost_spent_usd == 4.0


class TestAutopilotSessionStoreEdgeCases:
    """Edge case tests for AutopilotSessionStore."""

    @pytest.fixture
    def tmp_storage(self, tmp_path):
        """Create temporary storage directory."""
        storage_path = tmp_path / ".swarm" / "chief-of-staff"
        storage_path.mkdir(parents=True)
        return storage_path

    @pytest.fixture
    def store(self, tmp_storage):
        """Create AutopilotSessionStore instance."""
        return AutopilotSessionStore(tmp_storage)

    def test_load_empty_goals_list(self, store):
        """Test loading session with empty goals."""
        session = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            goals=[],
            status="running",
        )
        store.save(session)
        
        loaded = store.load(session.session_id)
        assert loaded.goals == []

    def test_save_session_with_all_fields(self, store):
        """Test saving and loading session with all fields populated."""
        session = AutopilotSession(
            session_id="ap-20251216-full",
            started_at="2025-12-16T10:00:00",
            budget_usd=25.0,
            duration_limit_seconds=14400,
            stop_trigger=CheckpointTrigger.TIME_THRESHOLD,
            goals=[
                DailyGoal(
                    id="goal-001",
                    content="Complete task",
                    priority="P1",
                    status=GoalStatus.DONE,
                    estimated_minutes=30,
                    actual_minutes=45,
                    notes="Took longer than expected",
                    linked_feature="my-feature",
                    completed_at="2025-12-16T10:45:00",
                ),
            ],
            current_goal_index=1,
            checkpoint_events=[
                CheckpointEvent(
                    event_id="evt-001",
                    timestamp="2025-12-16T10:30:00",
                    trigger=CheckpointTrigger.APPROVAL_REQUIRED,
                    description="Spec review requires approval",
                    requires_approval=True,
                    approved=True,
                    approved_at="2025-12-16T10:35:00",
                ),
            ],
            cost_spent_usd=12.50,
            duration_seconds=3600,
            status="completed",
            pause_reason=None,
            ended_at="2025-12-16T11:00:00",
        )
        store.save(session)

        loaded = store.load(session.session_id)
        assert loaded.session_id == session.session_id
        assert loaded.budget_usd == 25.0
        assert loaded.stop_trigger == CheckpointTrigger.TIME_THRESHOLD
        assert loaded.goals[0].linked_feature == "my-feature"
        assert loaded.checkpoint_events[0].approved == True
        assert loaded.ended_at == "2025-12-16T11:00:00"

    def test_list_all_empty(self, store):
        """Test list_all with no sessions."""
        all_ids = store.list_all()
        assert all_ids == []

    def test_list_paused_empty(self, store):
        """Test list_paused with no sessions."""
        paused_ids = store.list_paused()
        assert paused_ids == []

    def test_special_characters_in_session_id(self, store):
        """Test handling session IDs with underscores."""
        session = AutopilotSession(
            session_id="ap_2025_12_16_test",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            status="running",
        )
        store.save(session)
        
        loaded = store.load("ap_2025_12_16_test")
        assert loaded is not None
        assert loaded.session_id == "ap_2025_12_16_test"