"""
TDD tests for HandoffManager - Auto-Handoff System.

Tests for Phase 1.3: Auto-Handoff System
Tests written BEFORE implementation (RED phase).

Acceptance Criteria:
1. Generate handoff on PreCompact hook
2. Include: completed work, pending goals, blockers, context
3. Inject handoff automatically on SessionStart
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest


# =============================================================================
# TestHandoffGeneration - Test generating handoffs from ledger
# =============================================================================


class TestHandoffGeneration:
    """Test generating handoffs from ledger state."""

    def test_generate_handoff_from_ledger(self, tmp_path):
        """Generate a handoff from a populated ledger."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Setup: Create ledger with data
        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-001")
        ledger.add_goal("Complete Phase 1 safety net")
        ledger.add_decision("Use YAML for config files")
        ledger.mark_complete("Implemented SafetyNetHook")
        ledger.add_blocker("Need code review before merge")

        # Act: Generate handoff
        manager = HandoffManager(storage_dir=tmp_path)
        handoff = manager.generate_handoff(ledger)

        # Assert: Handoff contains ledger data
        assert handoff is not None
        assert handoff.session_id == "sess-001"
        assert "Complete Phase 1 safety net" in handoff.goals
        assert "Use YAML for config files" in handoff.decisions
        assert "Implemented SafetyNetHook" in handoff.completed
        assert "Need code review before merge" in handoff.blockers

    def test_generate_handoff_empty_ledger(self, tmp_path):
        """Generate a handoff from an empty ledger."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-empty")
        manager = HandoffManager(storage_dir=tmp_path)

        handoff = manager.generate_handoff(ledger)

        assert handoff is not None
        assert handoff.session_id == "sess-empty"
        assert handoff.goals == []
        assert handoff.decisions == []
        assert handoff.completed == []
        assert handoff.blockers == []

    def test_generate_handoff_includes_timestamp(self, tmp_path):
        """Handoff includes generation timestamp."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-time")
        manager = HandoffManager(storage_dir=tmp_path)

        before = datetime.now(timezone.utc)
        handoff = manager.generate_handoff(ledger)
        after = datetime.now(timezone.utc)

        assert handoff.generated_at is not None
        generated = datetime.fromisoformat(handoff.generated_at)
        assert before <= generated <= after

    def test_generate_handoff_on_precompact_hook(self, tmp_path):
        """Handoff is generated when PreCompact hook fires."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-compact")
        ledger.add_goal("Finish implementation")
        ledger.mark_complete("Tests written")

        manager = HandoffManager(storage_dir=tmp_path)

        # Simulate PreCompact hook
        handoff = manager.on_precompact(ledger)

        assert handoff is not None
        assert "Finish implementation" in handoff.goals
        assert "Tests written" in handoff.completed

    def test_generate_handoff_includes_context_summary(self, tmp_path):
        """Handoff includes context/summary information."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-context")
        ledger.add_goal("Build feature X")
        ledger.set_context("Working on swarm-attack autopilot orchestration")

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = manager.generate_handoff(ledger)

        assert handoff.context is not None
        assert "swarm-attack" in handoff.context or "autopilot" in handoff.context


# =============================================================================
# TestHandoffContent - Test that handoffs include all required content
# =============================================================================


class TestHandoffContent:
    """Test that handoffs include all required content fields."""

    def test_handoff_has_all_required_fields(self, tmp_path):
        """Handoff object has all required fields."""
        from swarm_attack.continuity.handoff import Handoff

        handoff = Handoff(
            session_id="sess-fields",
            goals=["Goal 1", "Goal 2"],
            decisions=["Decision 1"],
            completed=["Task 1 done"],
            blockers=["Blocker 1"],
            context="Working on feature X",
            generated_at="2026-01-05T12:00:00Z",
        )

        assert handoff.session_id == "sess-fields"
        assert handoff.goals == ["Goal 1", "Goal 2"]
        assert handoff.decisions == ["Decision 1"]
        assert handoff.completed == ["Task 1 done"]
        assert handoff.blockers == ["Blocker 1"]
        assert handoff.context == "Working on feature X"
        assert handoff.generated_at == "2026-01-05T12:00:00Z"

    def test_handoff_to_dict(self, tmp_path):
        """Handoff can be serialized to dictionary."""
        from swarm_attack.continuity.handoff import Handoff

        handoff = Handoff(
            session_id="sess-dict",
            goals=["Complete testing"],
            decisions=["Use pytest"],
            completed=["Setup done"],
            blockers=[],
            context="TDD workflow",
            generated_at="2026-01-05T12:00:00Z",
        )

        data = handoff.to_dict()

        assert isinstance(data, dict)
        assert data["session_id"] == "sess-dict"
        assert data["goals"] == ["Complete testing"]
        assert data["decisions"] == ["Use pytest"]
        assert data["completed"] == ["Setup done"]
        assert data["blockers"] == []
        assert data["context"] == "TDD workflow"
        assert data["generated_at"] == "2026-01-05T12:00:00Z"

    def test_handoff_from_dict(self, tmp_path):
        """Handoff can be deserialized from dictionary."""
        from swarm_attack.continuity.handoff import Handoff

        data = {
            "session_id": "sess-from-dict",
            "goals": ["Goal A"],
            "decisions": ["Decision B"],
            "completed": ["Work C"],
            "blockers": ["Blocker D"],
            "context": "Context E",
            "generated_at": "2026-01-05T14:00:00Z",
        }

        handoff = Handoff.from_dict(data)

        assert handoff.session_id == "sess-from-dict"
        assert handoff.goals == ["Goal A"]
        assert handoff.decisions == ["Decision B"]
        assert handoff.completed == ["Work C"]
        assert handoff.blockers == ["Blocker D"]
        assert handoff.context == "Context E"
        assert handoff.generated_at == "2026-01-05T14:00:00Z"

    def test_handoff_includes_pending_goals(self, tmp_path):
        """Handoff includes pending (incomplete) goals."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-pending")
        ledger.add_goal("Goal 1 - done")
        ledger.add_goal("Goal 2 - pending")
        ledger.mark_goal_complete("Goal 1 - done")

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = manager.generate_handoff(ledger)

        # Goals should contain all goals
        assert "Goal 1 - done" in handoff.goals or "Goal 2 - pending" in handoff.goals
        # Pending goals should be identifiable
        assert hasattr(handoff, "pending_goals") or any(
            "pending" in g.lower() for g in handoff.goals
        )

    def test_handoff_includes_completed_work(self, tmp_path):
        """Handoff includes completed work items."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-completed")
        ledger.mark_complete("Implemented feature A")
        ledger.mark_complete("Fixed bug B")
        ledger.mark_complete("Wrote tests for C")

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = manager.generate_handoff(ledger)

        assert "Implemented feature A" in handoff.completed
        assert "Fixed bug B" in handoff.completed
        assert "Wrote tests for C" in handoff.completed

    def test_handoff_includes_blockers(self, tmp_path):
        """Handoff includes current blockers."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-blockers")
        ledger.add_blocker("Waiting for API access")
        ledger.add_blocker("Need design review")

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = manager.generate_handoff(ledger)

        assert "Waiting for API access" in handoff.blockers
        assert "Need design review" in handoff.blockers


# =============================================================================
# TestHandoffInjection - Test injecting handoffs into new sessions
# =============================================================================


class TestHandoffInjection:
    """Test injecting handoffs into new sessions."""

    def test_inject_handoff_on_session_start(self, tmp_path):
        """Handoff is injected when SessionStart hook fires."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        # Setup: Create a saved handoff
        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-previous",
            goals=["Complete Phase 1"],
            decisions=["Use YAML config"],
            completed=["Setup done"],
            blockers=["Need review"],
            context="Working on safety net",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        # Act: Inject into new session
        injected = manager.on_session_start(new_session_id="sess-new")

        # Assert: Previous handoff is returned for injection
        assert injected is not None
        assert injected.session_id == "sess-previous"
        assert "Complete Phase 1" in injected.goals

    def test_inject_most_recent_handoff(self, tmp_path):
        """Injects the most recent handoff when multiple exist."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)

        # Save older handoff
        older = Handoff(
            session_id="sess-old",
            goals=["Old goal"],
            decisions=[],
            completed=[],
            blockers=[],
            context="Old context",
            generated_at="2026-01-05T08:00:00Z",
        )
        manager.save_handoff(older)

        # Save newer handoff
        newer = Handoff(
            session_id="sess-new",
            goals=["New goal"],
            decisions=[],
            completed=[],
            blockers=[],
            context="New context",
            generated_at="2026-01-05T12:00:00Z",
        )
        manager.save_handoff(newer)

        # Act: Get handoff for new session
        injected = manager.on_session_start(new_session_id="sess-current")

        # Assert: Most recent handoff is injected
        assert injected is not None
        assert injected.session_id == "sess-new"
        assert "New goal" in injected.goals

    def test_inject_returns_none_when_no_handoff(self, tmp_path):
        """Returns None when no previous handoff exists."""
        from swarm_attack.continuity.handoff import HandoffManager

        manager = HandoffManager(storage_dir=tmp_path)

        injected = manager.on_session_start(new_session_id="sess-first")

        assert injected is None

    def test_inject_handoff_to_ledger(self, tmp_path):
        """Handoff data is injected into new session's ledger."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Setup: Save a handoff
        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-prev",
            goals=["Continue feature work"],
            decisions=["Using TDD"],
            completed=["Tests written"],
            blockers=["API not ready"],
            context="Building autopilot",
            generated_at="2026-01-05T09:00:00Z",
        )
        manager.save_handoff(handoff)

        # Act: Create new ledger and inject handoff
        new_ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-new")
        manager.inject_into_ledger(new_ledger)

        # Assert: Ledger has prior context
        prior_goals = new_ledger.get_prior_goals()
        prior_context = new_ledger.get_prior_context()

        assert "Continue feature work" in prior_goals
        assert prior_context is not None

    def test_inject_formats_handoff_as_context(self, tmp_path):
        """Handoff is formatted as readable context for LLM."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-format",
            goals=["Finish implementation"],
            decisions=["Use dataclasses"],
            completed=["Setup complete"],
            blockers=["Waiting for review"],
            context="Working on continuity module",
            generated_at="2026-01-05T11:00:00Z",
        )

        formatted = manager.format_for_injection(handoff)

        # Assert: Formatted text is readable
        assert isinstance(formatted, str)
        assert "Finish implementation" in formatted
        assert "Use dataclasses" in formatted
        assert "Setup complete" in formatted
        assert "Waiting for review" in formatted
        assert "continuity" in formatted.lower()


# =============================================================================
# TestHandoffPersistence - Test saving and loading handoffs
# =============================================================================


class TestHandoffPersistence:
    """Test saving and loading handoffs to/from disk."""

    def test_save_handoff_creates_file(self, tmp_path):
        """Saving a handoff creates a JSON file."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-save",
            goals=["Test goal"],
            decisions=["Test decision"],
            completed=["Test complete"],
            blockers=["Test blocker"],
            context="Test context",
            generated_at="2026-01-05T10:00:00Z",
        )

        manager.save_handoff(handoff)

        # Assert: File exists
        handoff_files = list(tmp_path.glob("**/handoff*.json"))
        assert len(handoff_files) >= 1

        # Assert: File contains handoff data
        content = json.loads(handoff_files[0].read_text())
        assert content["session_id"] == "sess-save"
        assert content["goals"] == ["Test goal"]

    def test_load_handoff_by_session_id(self, tmp_path):
        """Load a specific handoff by session ID."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-load",
            goals=["Loaded goal"],
            decisions=[],
            completed=[],
            blockers=[],
            context="Loaded context",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        # Act: Load by session ID
        loaded = manager.load_handoff("sess-load")

        # Assert: Loaded handoff matches
        assert loaded is not None
        assert loaded.session_id == "sess-load"
        assert "Loaded goal" in loaded.goals
        assert loaded.context == "Loaded context"

    def test_load_returns_none_for_nonexistent(self, tmp_path):
        """Loading nonexistent handoff returns None."""
        from swarm_attack.continuity.handoff import HandoffManager

        manager = HandoffManager(storage_dir=tmp_path)

        loaded = manager.load_handoff("nonexistent-session")

        assert loaded is None

    def test_load_latest_handoff(self, tmp_path):
        """Load the most recent handoff regardless of session ID."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff
        import time

        manager = HandoffManager(storage_dir=tmp_path)

        # Save multiple handoffs with different timestamps
        for i in range(3):
            handoff = Handoff(
                session_id=f"sess-{i}",
                goals=[f"Goal {i}"],
                decisions=[],
                completed=[],
                blockers=[],
                context=f"Context {i}",
                generated_at=f"2026-01-05T{10+i}:00:00Z",
            )
            manager.save_handoff(handoff)
            time.sleep(0.01)  # Ensure different timestamps

        # Act: Load latest
        latest = manager.load_latest_handoff()

        # Assert: Most recent is returned
        assert latest is not None
        assert latest.session_id == "sess-2"
        assert "Goal 2" in latest.goals

    def test_handoff_storage_location(self, tmp_path):
        """Handoffs are stored in correct directory."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-location",
            goals=[],
            decisions=[],
            completed=[],
            blockers=[],
            context="",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        # Assert: Stored in expected location
        expected_dir = tmp_path / "handoffs"
        assert expected_dir.exists()
        handoff_files = list(expected_dir.glob("*.json"))
        assert len(handoff_files) >= 1

    def test_handoff_filename_includes_session_id(self, tmp_path):
        """Handoff filename includes session ID for easy lookup."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-filename-test",
            goals=[],
            decisions=[],
            completed=[],
            blockers=[],
            context="",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        # Assert: Filename contains session ID
        handoff_files = list(tmp_path.glob("**/*.json"))
        assert any("sess-filename-test" in f.name for f in handoff_files)

    def test_list_all_handoffs(self, tmp_path):
        """List all available handoffs."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)

        # Save multiple handoffs
        for i in range(5):
            handoff = Handoff(
                session_id=f"sess-list-{i}",
                goals=[f"Goal {i}"],
                decisions=[],
                completed=[],
                blockers=[],
                context="",
                generated_at=f"2026-01-05T{10+i}:00:00Z",
            )
            manager.save_handoff(handoff)

        # Act: List all
        all_handoffs = manager.list_handoffs()

        # Assert: All are listed
        assert len(all_handoffs) == 5
        session_ids = [h.session_id for h in all_handoffs]
        for i in range(5):
            assert f"sess-list-{i}" in session_ids


# =============================================================================
# TestHandoffEdgeCases - Test edge cases and error handling
# =============================================================================


class TestHandoffEdgeCases:
    """Test edge cases and error handling."""

    def test_handoff_with_unicode_content(self, tmp_path):
        """Handoff handles unicode content correctly."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)
        handoff = Handoff(
            session_id="sess-unicode",
            goals=["Complete task with emoji"],
            decisions=["Use UTF-8 encoding"],
            completed=["Done"],
            blockers=[],
            context="Testing unicode support",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        loaded = manager.load_handoff("sess-unicode")
        assert loaded is not None
        assert "emoji" in loaded.goals[0]

    def test_handoff_with_large_content(self, tmp_path):
        """Handoff handles large content gracefully."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)

        # Create large content
        large_goals = [f"Goal {i}: " + "x" * 1000 for i in range(100)]
        large_context = "Context: " + "y" * 10000

        handoff = Handoff(
            session_id="sess-large",
            goals=large_goals,
            decisions=[],
            completed=[],
            blockers=[],
            context=large_context,
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        loaded = manager.load_handoff("sess-large")
        assert loaded is not None
        assert len(loaded.goals) == 100
        assert len(loaded.context) > 10000

    def test_handoff_concurrent_save(self, tmp_path):
        """Multiple handoffs can be saved concurrently."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff
        import threading

        manager = HandoffManager(storage_dir=tmp_path)
        errors = []

        def save_handoff(idx):
            try:
                handoff = Handoff(
                    session_id=f"sess-concurrent-{idx}",
                    goals=[f"Goal {idx}"],
                    decisions=[],
                    completed=[],
                    blockers=[],
                    context=f"Context {idx}",
                    generated_at=f"2026-01-05T{10+idx:02d}:00:00Z",
                )
                manager.save_handoff(handoff)
            except Exception as e:
                errors.append(e)

        # Create threads
        threads = [threading.Thread(target=save_handoff, args=(i,)) for i in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Assert: No errors
        assert len(errors) == 0

        # Assert: All handoffs saved
        all_handoffs = manager.list_handoffs()
        assert len(all_handoffs) == 10

    def test_handoff_corrupted_file_handling(self, tmp_path):
        """Gracefully handle corrupted handoff files."""
        from swarm_attack.continuity.handoff import HandoffManager

        manager = HandoffManager(storage_dir=tmp_path)

        # Create corrupted file
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir(parents=True, exist_ok=True)
        corrupted = handoffs_dir / "handoff-sess-corrupted.json"
        corrupted.write_text("{ invalid json content")

        # Act: Try to load
        loaded = manager.load_handoff("sess-corrupted")

        # Assert: Returns None or raises specific exception
        assert loaded is None or isinstance(loaded, type(None))

    def test_handoff_missing_storage_dir_creates_it(self, tmp_path):
        """HandoffManager creates storage directory if missing."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        storage = tmp_path / "nested" / "deep" / "storage"
        assert not storage.exists()

        manager = HandoffManager(storage_dir=storage)
        handoff = Handoff(
            session_id="sess-create-dir",
            goals=["Test"],
            decisions=[],
            completed=[],
            blockers=[],
            context="",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(handoff)

        assert storage.exists()
        loaded = manager.load_handoff("sess-create-dir")
        assert loaded is not None


# =============================================================================
# TestHandoffIntegrationWithHooks - Test hook integration
# =============================================================================


class TestHandoffIntegrationWithHooks:
    """Test handoff integration with PreCompact and SessionStart hooks."""

    def test_precompact_hook_saves_handoff(self, tmp_path):
        """PreCompact hook triggers handoff save."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(storage_dir=tmp_path, session_id="sess-precompact")
        ledger.add_goal("Finish before compaction")
        ledger.mark_complete("First task done")

        manager = HandoffManager(storage_dir=tmp_path)

        # Act: Trigger PreCompact
        handoff = manager.on_precompact(ledger)

        # Assert: Handoff generated and saved
        assert handoff is not None
        saved = manager.load_handoff("sess-precompact")
        assert saved is not None
        assert "Finish before compaction" in saved.goals

    def test_session_start_hook_injects_handoff(self, tmp_path):
        """SessionStart hook injects previous handoff."""
        from swarm_attack.continuity.handoff import HandoffManager, Handoff

        manager = HandoffManager(storage_dir=tmp_path)

        # Setup: Previous session's handoff
        prev_handoff = Handoff(
            session_id="sess-prev-hook",
            goals=["Continue from previous"],
            decisions=["Keep using TDD"],
            completed=["Phase 1 done"],
            blockers=[],
            context="Autopilot work",
            generated_at="2026-01-05T10:00:00Z",
        )
        manager.save_handoff(prev_handoff)

        # Act: New session starts
        injected = manager.on_session_start(new_session_id="sess-new-hook")

        # Assert: Previous handoff is available
        assert injected is not None
        assert "Continue from previous" in injected.goals

    def test_full_handoff_lifecycle(self, tmp_path):
        """Test complete handoff lifecycle: create -> save -> load -> inject."""
        from swarm_attack.continuity.handoff import HandoffManager
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Session 1: Work and compaction
        ledger1 = ContinuityLedger(storage_dir=tmp_path, session_id="sess-1")
        ledger1.add_goal("Build safety net hook")
        ledger1.add_decision("Block rm -rf commands")
        ledger1.mark_complete("Wrote tests")
        ledger1.add_blocker("Need to implement blocking logic")

        manager = HandoffManager(storage_dir=tmp_path)

        # PreCompact triggers handoff
        handoff1 = manager.on_precompact(ledger1)
        assert handoff1 is not None

        # Session 2: Resume
        injected = manager.on_session_start(new_session_id="sess-2")
        assert injected is not None
        assert "Build safety net hook" in injected.goals
        assert "Block rm -rf commands" in injected.decisions
        assert "Wrote tests" in injected.completed
        assert "Need to implement blocking logic" in injected.blockers

        # New ledger has prior context
        ledger2 = ContinuityLedger(storage_dir=tmp_path, session_id="sess-2")
        manager.inject_into_ledger(ledger2)
        prior_goals = ledger2.get_prior_goals()
        assert "Build safety net hook" in prior_goals
