"""
Integration tests for Memory Layer Integration Points (Issue A2).

Tests for:
1. CheckpointSystem -> MemoryStore integration
2. VerifierAgent -> MemoryStore integration

TDD: Tests written BEFORE implementation (RED phase).
"""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


class TestCheckpointMemoryIntegration:
    """Tests for CheckpointSystem -> MemoryStore integration."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, temp_store_path):
        """Create a MemoryStore instance with temp path."""
        return MemoryStore(store_path=temp_store_path)

    @pytest.fixture
    def checkpoint_store_path(self):
        """Create a temporary directory for checkpoint store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "checkpoints"

    @pytest.fixture
    def sample_checkpoint(self, checkpoint_store_path):
        """Create a sample pending checkpoint."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointStore,
            CheckpointTrigger,
        )

        checkpoint = Checkpoint(
            checkpoint_id=f"chk-{uuid4().hex[:12]}",
            trigger=CheckpointTrigger.HICCUP,
            context="Goal failed after retries. Error: Import failed in test suite",
            options=[
                CheckpointOption(label="Proceed", description="Continue", is_recommended=True),
                CheckpointOption(label="Skip", description="Skip goal", is_recommended=False),
            ],
            recommendation="Proceed - Similar errors resolved by continuing",
            created_at=datetime.now().isoformat(),
            goal_id="goal-test-123",
            status="pending",
        )

        return checkpoint

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_stores_decision_in_memory(
        self, memory_store, checkpoint_store_path, sample_checkpoint
    ):
        """Resolving a checkpoint should record the decision in memory."""
        from swarm_attack.chief_of_staff.checkpoints import (
            CheckpointStore,
            CheckpointSystem,
        )

        # Setup
        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(sample_checkpoint)

        system = CheckpointSystem(config=None, store=store, memory_store=memory_store)

        # Act
        await system.resolve_checkpoint(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            chosen_option="Proceed",
            notes="Resolved import error on retry",
        )

        # Assert
        results = memory_store.query(category="checkpoint_decision")
        assert len(results) == 1
        assert results[0].category == "checkpoint_decision"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_stores_trigger_type(
        self, memory_store, checkpoint_store_path, sample_checkpoint
    ):
        """Memory entry should include the checkpoint trigger type."""
        from swarm_attack.chief_of_staff.checkpoints import (
            CheckpointStore,
            CheckpointSystem,
        )

        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(sample_checkpoint)

        system = CheckpointSystem(config=None, store=store, memory_store=memory_store)

        await system.resolve_checkpoint(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            chosen_option="Proceed",
            notes="Test notes",
        )

        results = memory_store.query(category="checkpoint_decision")
        assert len(results) == 1
        assert results[0].content["trigger"] == "HICCUP"
        assert "HICCUP" in results[0].tags

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_stores_chosen_option(
        self, memory_store, checkpoint_store_path, sample_checkpoint
    ):
        """Memory entry should include the chosen option."""
        from swarm_attack.chief_of_staff.checkpoints import (
            CheckpointStore,
            CheckpointSystem,
        )

        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(sample_checkpoint)

        system = CheckpointSystem(config=None, store=store, memory_store=memory_store)

        await system.resolve_checkpoint(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            chosen_option="Skip",
            notes="Skipping due to time constraints",
        )

        results = memory_store.query(category="checkpoint_decision")
        assert len(results) == 1
        assert results[0].content["decision"] == "Skip"
        assert "Skip" in results[0].tags

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_truncates_long_context(
        self, memory_store, checkpoint_store_path
    ):
        """Context should be truncated to 500 chars to prevent bloat."""
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointStore,
            CheckpointSystem,
            CheckpointTrigger,
        )

        # Create checkpoint with very long context
        long_context = "A" * 1000  # 1000 chars
        checkpoint = Checkpoint(
            checkpoint_id=f"chk-{uuid4().hex[:12]}",
            trigger=CheckpointTrigger.HICCUP,
            context=long_context,
            options=[CheckpointOption(label="Proceed", description="Continue", is_recommended=True)],
            recommendation="Proceed",
            created_at=datetime.now().isoformat(),
            goal_id="goal-long-context",
            status="pending",
        )

        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(checkpoint)

        system = CheckpointSystem(config=None, store=store, memory_store=memory_store)

        await system.resolve_checkpoint(
            checkpoint_id=checkpoint.checkpoint_id,
            chosen_option="Proceed",
            notes="Test",
        )

        results = memory_store.query(category="checkpoint_decision")
        assert len(results) == 1
        # Context should be truncated to 500 chars
        assert len(results[0].content["context"]) <= 500

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_works_without_memory_store(
        self, checkpoint_store_path, sample_checkpoint
    ):
        """Existing behavior preserved when memory_store=None."""
        from swarm_attack.chief_of_staff.checkpoints import (
            CheckpointStore,
            CheckpointSystem,
        )

        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(sample_checkpoint)

        # No memory_store provided
        system = CheckpointSystem(config=None, store=store)

        # Should not raise
        resolved = await system.resolve_checkpoint(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            chosen_option="Proceed",
            notes="Test notes",
        )

        assert resolved.status == "approved"
        assert resolved.chosen_option == "Proceed"

    @pytest.mark.asyncio
    async def test_memory_queryable_by_trigger_tag(
        self, memory_store, checkpoint_store_path, sample_checkpoint
    ):
        """After resolving, memory should be queryable by trigger type."""
        from swarm_attack.chief_of_staff.checkpoints import (
            CheckpointStore,
            CheckpointSystem,
        )

        store = CheckpointStore(base_path=checkpoint_store_path)
        await store.save(sample_checkpoint)

        system = CheckpointSystem(config=None, store=store, memory_store=memory_store)

        await system.resolve_checkpoint(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            chosen_option="Proceed",
            notes="Test",
        )

        # Query by trigger tag
        results = memory_store.query(
            category="checkpoint_decision",
            tags=["HICCUP"],
        )

        assert len(results) == 1
        assert results[0].content["trigger"] == "HICCUP"


class TestVerifierMemoryIntegration:
    """Tests for VerifierAgent -> MemoryStore integration."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, temp_store_path):
        """Create a MemoryStore instance with temp path."""
        return MemoryStore(store_path=temp_store_path)

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory with test file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create tests/generated/test-feature directory
            test_dir = repo_path / "tests" / "generated" / "test-feature"
            test_dir.mkdir(parents=True)

            # Create a simple passing test file
            test_file = test_dir / "test_issue_1.py"
            test_file.write_text("""
def test_placeholder():
    assert True
""")

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for VerifierAgent."""
        from dataclasses import dataclass, field
        from typing import List

        @dataclass
        class MockTestConfig:
            timeout_seconds: int = 30

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            tests: MockTestConfig = field(default_factory=MockTestConfig)

        return MockConfig(repo_root=temp_repo)

    def test_schema_drift_stored_in_memory(self, memory_store, mock_config):
        """Detecting schema drift should record conflict in memory."""
        from swarm_attack.agents.verifier import VerifierAgent

        agent = VerifierAgent(
            config=mock_config,
            memory_store=memory_store,
        )

        # Simulate schema drift detection context
        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["AutopilotSession"],
                    }
                }
            },
            "new_classes_defined": {
                "runner.py": ["AutopilotSession"],  # Duplicate!
            },
        }

        # Run the agent (will detect schema drift)
        result = agent.run(context)

        # Schema drift should be recorded in memory
        assert not result.success
        assert "schema_conflicts" in result.output

        # Check memory was recorded
        results = memory_store.query(category="schema_drift")
        assert len(results) == 1
        assert results[0].content["class_name"] == "AutopilotSession"

    def test_schema_drift_includes_class_name(self, memory_store, mock_config):
        """Memory entry should include the conflicting class name."""
        from swarm_attack.agents.verifier import VerifierAgent

        agent = VerifierAgent(
            config=mock_config,
            memory_store=memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,  # Must match existing test file
            "module_registry": {
                "modules": {
                    "goals.py": {
                        "created_by_issue": 1,
                        "classes": ["DailyGoal"],
                    }
                }
            },
            "new_classes_defined": {
                "tracker.py": ["DailyGoal"],
            },
        }

        agent.run(context)

        results = memory_store.query(category="schema_drift")
        assert len(results) == 1
        assert results[0].content["class_name"] == "DailyGoal"
        assert "DailyGoal" in results[0].tags

    def test_schema_drift_includes_file_paths(self, memory_store, mock_config):
        """Memory entry should include both existing and new file paths."""
        from swarm_attack.agents.verifier import VerifierAgent

        agent = VerifierAgent(
            config=mock_config,
            memory_store=memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,  # Must match existing test file
            "module_registry": {
                "modules": {
                    "swarm_attack/models.py": {
                        "created_by_issue": 1,
                        "classes": ["SessionState"],
                    }
                }
            },
            "new_classes_defined": {
                "swarm_attack/runner.py": ["SessionState"],
            },
        }

        agent.run(context)

        results = memory_store.query(category="schema_drift")
        assert len(results) == 1
        assert results[0].content["existing_file"] == "swarm_attack/models.py"
        assert results[0].content["new_file"] == "swarm_attack/runner.py"

    def test_no_memory_write_when_no_conflicts(self, memory_store, mock_config, temp_repo):
        """No memory entry when no schema drift detected."""
        from swarm_attack.agents.verifier import VerifierAgent

        agent = VerifierAgent(
            config=mock_config,
            memory_store=memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["SomeOtherClass"],
                    }
                }
            },
            "new_classes_defined": {
                "new_module.py": ["NewClass"],  # No conflict
            },
        }

        agent.run(context)

        results = memory_store.query(category="schema_drift")
        assert len(results) == 0

    def test_verifier_works_without_memory_store(self, mock_config, temp_repo):
        """Existing behavior preserved when memory_store=None."""
        from swarm_attack.agents.verifier import VerifierAgent

        # No memory_store provided
        agent = VerifierAgent(config=mock_config)

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["AutopilotSession"],
                    }
                }
            },
            "new_classes_defined": {
                "runner.py": ["AutopilotSession"],
            },
        }

        # Should not raise
        result = agent.run(context)

        # Schema drift detected but no memory store to write to
        assert not result.success
        assert "schema_conflicts" in result.output

    def test_memory_queryable_by_class_name_tag(self, memory_store, mock_config):
        """After drift detection, memory should be queryable by class name."""
        from swarm_attack.agents.verifier import VerifierAgent

        agent = VerifierAgent(
            config=mock_config,
            memory_store=memory_store,
        )

        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "module_registry": {
                "modules": {
                    "models.py": {
                        "created_by_issue": 1,
                        "classes": ["CheckpointStore"],
                    }
                }
            },
            "new_classes_defined": {
                "stores.py": ["CheckpointStore"],
            },
        }

        agent.run(context)

        # Query by class name tag
        results = memory_store.query(
            category="schema_drift",
            tags=["CheckpointStore"],
        )

        assert len(results) == 1
        assert results[0].content["class_name"] == "CheckpointStore"


class TestMemoryQueryAfterIntegration:
    """Tests for querying memory after integration points fire."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def populated_memory_store(self, temp_store_path):
        """Create a MemoryStore with pre-populated entries."""
        store = MemoryStore(store_path=temp_store_path)

        # Add checkpoint decisions
        for trigger in ["HICCUP", "HICCUP", "COST_SINGLE"]:
            entry = MemoryEntry(
                id=str(uuid4()),
                category="checkpoint_decision",
                feature_id="test-feature",
                issue_number=None,
                content={
                    "trigger": trigger,
                    "decision": "Proceed",
                    "context": f"Sample context for {trigger}",
                },
                outcome="applied",
                created_at=datetime.now().isoformat(),
                tags=[trigger, "Proceed"],
            )
            store.add(entry)

        # Add schema drift entries
        for class_name in ["AutopilotSession", "DailyGoal"]:
            entry = MemoryEntry(
                id=str(uuid4()),
                category="schema_drift",
                feature_id="test-feature",
                issue_number=1,
                content={
                    "class_name": class_name,
                    "existing_file": "models.py",
                    "new_file": "duplicate.py",
                },
                outcome="blocked",
                created_at=datetime.now().isoformat(),
                tags=["schema_drift", class_name],
            )
            store.add(entry)

        store.save()
        return store

    def test_find_similar_checkpoint_decisions(self, populated_memory_store):
        """find_similar should return past checkpoint decisions."""
        results = populated_memory_store.find_similar(
            content={"trigger": "HICCUP", "decision": "Proceed"},
            category="checkpoint_decision",
        )

        assert len(results) >= 1
        # At least one result should have HICCUP trigger
        # (find_similar uses keyword matching, so other entries may also match)
        assert any(r.content["trigger"] == "HICCUP" for r in results)

    def test_find_similar_schema_drifts(self, populated_memory_store):
        """find_similar should return past schema drift events."""
        results = populated_memory_store.find_similar(
            content={"class_name": "AutopilotSession"},
            category="schema_drift",
        )

        assert len(results) >= 1
        assert any(r.content["class_name"] == "AutopilotSession" for r in results)

    def test_query_checkpoint_decisions_by_trigger(self, populated_memory_store):
        """query() with tags=['HICCUP'] should return HICCUP decisions."""
        results = populated_memory_store.query(
            category="checkpoint_decision",
            tags=["HICCUP"],
        )

        assert len(results) == 2  # We added 2 HICCUP entries
        assert all(r.content["trigger"] == "HICCUP" for r in results)


class TestGlobalMemoryStore:
    """Tests for get_global_memory_store() convenience function."""

    def test_get_global_memory_store_returns_same_instance(self):
        """get_global_memory_store should return the same instance."""
        from swarm_attack.memory.store import get_global_memory_store

        store1 = get_global_memory_store()
        store2 = get_global_memory_store()

        assert store1 is store2

    def test_get_global_memory_store_is_usable(self):
        """Global memory store should be usable for add/query."""
        from swarm_attack.memory.store import get_global_memory_store

        store = get_global_memory_store()

        # Should have standard MemoryStore methods
        assert hasattr(store, "add")
        assert hasattr(store, "query")
        assert hasattr(store, "find_similar")
        assert hasattr(store, "save")
