"""Tests for Checkpoint and CheckpointStore dataclasses."""

import pytest
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
import tempfile
import shutil

from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointTrigger,
    CheckpointOption,
    Checkpoint,
    CheckpointResult,
    CheckpointStore,
)


class TestCheckpointTrigger:
    """Tests for CheckpointTrigger enum."""

    def test_has_ux_change(self):
        assert hasattr(CheckpointTrigger, 'UX_CHANGE')

    def test_has_cost_single(self):
        assert hasattr(CheckpointTrigger, 'COST_SINGLE')

    def test_has_cost_cumulative(self):
        assert hasattr(CheckpointTrigger, 'COST_CUMULATIVE')

    def test_has_architecture(self):
        assert hasattr(CheckpointTrigger, 'ARCHITECTURE')

    def test_has_scope_change(self):
        assert hasattr(CheckpointTrigger, 'SCOPE_CHANGE')

    def test_has_hiccup(self):
        assert hasattr(CheckpointTrigger, 'HICCUP')

    def test_enum_values(self):
        triggers = [
            CheckpointTrigger.UX_CHANGE,
            CheckpointTrigger.COST_SINGLE,
            CheckpointTrigger.COST_CUMULATIVE,
            CheckpointTrigger.ARCHITECTURE,
            CheckpointTrigger.SCOPE_CHANGE,
            CheckpointTrigger.HICCUP,
        ]
        assert len(triggers) == 6


class TestCheckpointOption:
    """Tests for CheckpointOption dataclass."""

    def test_has_label_field(self):
        option = CheckpointOption(label="Test", description="Test desc")
        assert hasattr(option, 'label')
        assert option.label == "Test"

    def test_has_description_field(self):
        option = CheckpointOption(label="Test", description="Test desc")
        assert hasattr(option, 'description')
        assert option.description == "Test desc"

    def test_has_is_recommended_field(self):
        option = CheckpointOption(label="Test", description="Test desc", is_recommended=True)
        assert hasattr(option, 'is_recommended')
        assert option.is_recommended is True

    def test_is_recommended_default_false(self):
        option = CheckpointOption(label="Test", description="Test desc")
        assert option.is_recommended is False

    def test_to_dict(self):
        option = CheckpointOption(label="Option A", description="First option", is_recommended=True)
        result = option.to_dict()
        assert isinstance(result, dict)
        assert result["label"] == "Option A"
        assert result["description"] == "First option"
        assert result["is_recommended"] is True

    def test_from_dict(self):
        data = {
            "label": "Option B",
            "description": "Second option",
            "is_recommended": False,
        }
        option = CheckpointOption.from_dict(data)
        assert isinstance(option, CheckpointOption)
        assert option.label == "Option B"
        assert option.description == "Second option"
        assert option.is_recommended is False

    def test_from_dict_missing_is_recommended(self):
        data = {
            "label": "Option C",
            "description": "Third option",
        }
        option = CheckpointOption.from_dict(data)
        assert option.is_recommended is False

    def test_roundtrip(self):
        original = CheckpointOption(label="Test", description="Test desc", is_recommended=True)
        roundtrip = CheckpointOption.from_dict(original.to_dict())
        assert roundtrip.label == original.label
        assert roundtrip.description == original.description
        assert roundtrip.is_recommended == original.is_recommended


class TestCheckpoint:
    """Tests for Checkpoint dataclass."""

    def test_has_checkpoint_id_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'checkpoint_id')

    def test_has_trigger_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'trigger')
        assert isinstance(cp.trigger, CheckpointTrigger)

    def test_has_context_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'context')

    def test_has_options_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'options')
        assert isinstance(cp.options, list)

    def test_has_recommendation_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'recommendation')

    def test_has_created_at_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'created_at')

    def test_has_goal_id_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'goal_id')

    def test_has_status_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'status')

    def test_default_status_pending(self):
        cp = self._make_checkpoint()
        assert cp.status == "pending"

    def test_has_chosen_option_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'chosen_option')

    def test_has_human_notes_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'human_notes')

    def test_has_resolved_at_field(self):
        cp = self._make_checkpoint()
        assert hasattr(cp, 'resolved_at')

    def test_to_dict(self):
        cp = self._make_checkpoint()
        result = cp.to_dict()
        assert isinstance(result, dict)
        assert result["checkpoint_id"] == cp.checkpoint_id
        assert result["trigger"] == cp.trigger.value
        assert result["context"] == cp.context
        assert result["recommendation"] == cp.recommendation
        assert result["goal_id"] == cp.goal_id
        assert result["status"] == cp.status

    def test_to_dict_options_serialized(self):
        option = CheckpointOption(label="Test", description="Test desc")
        cp = self._make_checkpoint(options=[option])
        result = cp.to_dict()
        assert len(result["options"]) == 1
        assert result["options"][0]["label"] == "Test"

    def test_from_dict(self):
        data = {
            "checkpoint_id": "cp-123",
            "trigger": "UX_CHANGE",
            "context": "Test context",
            "options": [{"label": "A", "description": "Option A", "is_recommended": True}],
            "recommendation": "Choose A",
            "created_at": "2024-01-01T00:00:00",
            "goal_id": "goal-456",
            "status": "pending",
            "chosen_option": None,
            "human_notes": None,
            "resolved_at": None,
        }
        cp = Checkpoint.from_dict(data)
        assert isinstance(cp, Checkpoint)
        assert cp.checkpoint_id == "cp-123"
        assert cp.trigger == CheckpointTrigger.UX_CHANGE
        assert cp.context == "Test context"
        assert len(cp.options) == 1
        assert cp.options[0].label == "A"

    def test_from_dict_with_resolved(self):
        data = {
            "checkpoint_id": "cp-789",
            "trigger": "COST_SINGLE",
            "context": "Cost exceeded",
            "options": [],
            "recommendation": "Proceed",
            "created_at": "2024-01-01T00:00:00",
            "goal_id": "goal-789",
            "status": "approved",
            "chosen_option": "proceed",
            "human_notes": "Approved by admin",
            "resolved_at": "2024-01-01T01:00:00",
        }
        cp = Checkpoint.from_dict(data)
        assert cp.status == "approved"
        assert cp.chosen_option == "proceed"
        assert cp.human_notes == "Approved by admin"
        assert cp.resolved_at is not None

    def test_roundtrip(self):
        original = self._make_checkpoint()
        roundtrip = Checkpoint.from_dict(original.to_dict())
        assert roundtrip.checkpoint_id == original.checkpoint_id
        assert roundtrip.trigger == original.trigger
        assert roundtrip.context == original.context
        assert roundtrip.goal_id == original.goal_id
        assert roundtrip.status == original.status

    def _make_checkpoint(self, **kwargs):
        defaults = {
            "checkpoint_id": "cp-test-123",
            "trigger": CheckpointTrigger.UX_CHANGE,
            "context": "Test context",
            "options": [],
            "recommendation": "Test recommendation",
            "created_at": datetime.now().isoformat(),
            "goal_id": "goal-test-456",
        }
        defaults.update(kwargs)
        return Checkpoint(**defaults)


class TestCheckpointResult:
    """Tests for CheckpointResult dataclass."""

    def test_has_requires_approval_field(self):
        result = CheckpointResult(requires_approval=True)
        assert hasattr(result, 'requires_approval')
        assert result.requires_approval is True

    def test_has_approved_field(self):
        result = CheckpointResult(requires_approval=False, approved=True)
        assert hasattr(result, 'approved')
        assert result.approved is True

    def test_has_checkpoint_field(self):
        cp = Checkpoint(
            checkpoint_id="cp-1",
            trigger=CheckpointTrigger.ARCHITECTURE,
            context="Test",
            options=[],
            recommendation="Test",
            created_at=datetime.now().isoformat(),
            goal_id="g-1",
        )
        result = CheckpointResult(requires_approval=True, checkpoint=cp)
        assert hasattr(result, 'checkpoint')
        assert result.checkpoint == cp

    def test_approved_default_none(self):
        result = CheckpointResult(requires_approval=True)
        assert result.approved is None

    def test_checkpoint_default_none(self):
        result = CheckpointResult(requires_approval=False)
        assert result.checkpoint is None


class TestCheckpointStore:
    """Tests for CheckpointStore class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp)

    @pytest.fixture
    def store(self, temp_dir):
        """Create a CheckpointStore with temp directory."""
        return CheckpointStore(base_path=temp_dir / "checkpoints")

    def test_base_path_attribute(self, store, temp_dir):
        assert store.base_path == temp_dir / "checkpoints"

    def test_default_base_path(self):
        store = CheckpointStore()
        assert ".swarm" in str(store.base_path)
        assert "chief-of-staff" in str(store.base_path)
        assert "checkpoints" in str(store.base_path)

    @pytest.mark.asyncio
    async def test_save_creates_file(self, store, temp_dir):
        cp = self._make_checkpoint("cp-save-1")
        await store.save(cp)
        file_path = store.base_path / "cp-save-1.json"
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_save_file_content_is_json(self, store, temp_dir):
        cp = self._make_checkpoint("cp-save-2")
        await store.save(cp)
        file_path = store.base_path / "cp-save-2.json"
        content = file_path.read_text()
        data = json.loads(content)
        assert data["checkpoint_id"] == "cp-save-2"

    @pytest.mark.asyncio
    async def test_get_returns_checkpoint(self, store):
        cp = self._make_checkpoint("cp-get-1")
        await store.save(cp)
        result = await store.get("cp-get-1")
        assert result is not None
        assert isinstance(result, Checkpoint)
        assert result.checkpoint_id == "cp-get-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, store):
        result = await store.get("nonexistent-cp")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pending_for_goal_returns_checkpoint(self, store):
        cp = self._make_checkpoint("cp-pending-1", goal_id="goal-pending-test", status="pending")
        await store.save(cp)
        result = await store.get_pending_for_goal("goal-pending-test")
        assert result is not None
        assert result.checkpoint_id == "cp-pending-1"

    @pytest.mark.asyncio
    async def test_get_pending_for_goal_ignores_resolved(self, store):
        cp = self._make_checkpoint("cp-resolved-1", goal_id="goal-resolved-test", status="approved")
        await store.save(cp)
        result = await store.get_pending_for_goal("goal-resolved-test")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pending_for_goal_no_match(self, store):
        result = await store.get_pending_for_goal("nonexistent-goal")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_pending_returns_all_pending(self, store):
        cp1 = self._make_checkpoint("cp-list-1", status="pending")
        cp2 = self._make_checkpoint("cp-list-2", status="pending")
        cp3 = self._make_checkpoint("cp-list-3", status="approved")
        await store.save(cp1)
        await store.save(cp2)
        await store.save(cp3)
        
        result = await store.list_pending()
        assert isinstance(result, list)
        assert len(result) == 2
        ids = [cp.checkpoint_id for cp in result]
        assert "cp-list-1" in ids
        assert "cp-list-2" in ids
        assert "cp-list-3" not in ids

    @pytest.mark.asyncio
    async def test_list_pending_empty_when_none(self, store):
        result = await store.list_pending()
        assert result == []

    @pytest.mark.asyncio
    async def test_save_overwrites_existing(self, store):
        cp = self._make_checkpoint("cp-overwrite", status="pending")
        await store.save(cp)
        
        cp_updated = self._make_checkpoint("cp-overwrite", status="approved")
        await store.save(cp_updated)
        
        result = await store.get("cp-overwrite")
        assert result.status == "approved"

    def _make_checkpoint(self, checkpoint_id: str, **kwargs) -> Checkpoint:
        defaults = {
            "checkpoint_id": checkpoint_id,
            "trigger": CheckpointTrigger.UX_CHANGE,
            "context": "Test context",
            "options": [],
            "recommendation": "Test recommendation",
            "created_at": datetime.now().isoformat(),
            "goal_id": kwargs.pop("goal_id", f"goal-for-{checkpoint_id}"),
            "status": kwargs.pop("status", "pending"),
        }
        defaults.update(kwargs)
        return Checkpoint(**defaults)


class TestStatusValues:
    """Tests to verify status value constraints."""

    def test_pending_status(self):
        cp = Checkpoint(
            checkpoint_id="cp-status-1",
            trigger=CheckpointTrigger.HICCUP,
            context="Test",
            options=[],
            recommendation="Test",
            created_at=datetime.now().isoformat(),
            goal_id="g-1",
            status="pending",
        )
        assert cp.status == "pending"

    def test_approved_status(self):
        cp = Checkpoint(
            checkpoint_id="cp-status-2",
            trigger=CheckpointTrigger.HICCUP,
            context="Test",
            options=[],
            recommendation="Test",
            created_at=datetime.now().isoformat(),
            goal_id="g-1",
            status="approved",
        )
        assert cp.status == "approved"

    def test_rejected_status(self):
        cp = Checkpoint(
            checkpoint_id="cp-status-3",
            trigger=CheckpointTrigger.HICCUP,
            context="Test",
            options=[],
            recommendation="Test",
            created_at=datetime.now().isoformat(),
            goal_id="g-1",
            status="rejected",
        )
        assert cp.status == "rejected"

    def test_expired_status(self):
        cp = Checkpoint(
            checkpoint_id="cp-status-4",
            trigger=CheckpointTrigger.HICCUP,
            context="Test",
            options=[],
            recommendation="Test",
            created_at=datetime.now().isoformat(),
            goal_id="g-1",
            status="expired",
        )
        assert cp.status == "expired"