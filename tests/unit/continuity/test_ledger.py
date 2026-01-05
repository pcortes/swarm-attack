"""
Unit tests for ContinuityLedger - Session Continuity Phase.

TDD Tests for ContinuityLedger module.
Tests written BEFORE implementation (RED phase).

The ContinuityLedger records:
1. Goals - what the session is trying to achieve
2. Decisions - important choices made during the session
3. Blockers - obstacles encountered
4. Handoff notes - context for the next session

Acceptance Criteria:
1. Record goals, decisions, blockers, and handoff notes
2. Inject prior ledger on SessionStart hook
3. Auto-serialize before context compaction
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# TestLedgerCreation - Test creating and initializing ledgers
# =============================================================================


class TestLedgerCreation:
    """Tests for creating and initializing ContinuityLedger instances."""

    def test_create_ledger_with_session_id(self):
        """Test creating a ledger with a session ID."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        session_id = "session-123"
        ledger = ContinuityLedger(session_id=session_id)

        assert ledger.session_id == session_id
        assert ledger.goals == []
        assert ledger.decisions == []
        assert ledger.blockers == []
        assert ledger.handoff_notes == []

    def test_create_ledger_with_feature_id(self):
        """Test creating a ledger associated with a feature."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(
            session_id="session-456",
            feature_id="feature/my-feature",
        )

        assert ledger.session_id == "session-456"
        assert ledger.feature_id == "feature/my-feature"

    def test_create_ledger_with_issue_number(self):
        """Test creating a ledger associated with an issue."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(
            session_id="session-789",
            issue_number=42,
        )

        assert ledger.issue_number == 42

    def test_ledger_has_created_at_timestamp(self):
        """Test that ledger records creation timestamp."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        before = datetime.now().isoformat()
        ledger = ContinuityLedger(session_id="session-ts")
        after = datetime.now().isoformat()

        assert ledger.created_at is not None
        assert before <= ledger.created_at <= after

    def test_ledger_generates_unique_id_if_not_provided(self):
        """Test that ledger auto-generates session_id if not provided."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger1 = ContinuityLedger()
        ledger2 = ContinuityLedger()

        assert ledger1.session_id is not None
        assert ledger2.session_id is not None
        assert ledger1.session_id != ledger2.session_id

    def test_create_ledger_with_parent_session(self):
        """Test creating a ledger that references a parent session."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        parent_id = "parent-session-123"
        ledger = ContinuityLedger(
            session_id="child-session-456",
            parent_session_id=parent_id,
        )

        assert ledger.parent_session_id == parent_id


# =============================================================================
# TestLedgerRecording - Test adding goals, decisions, blockers
# =============================================================================


class TestLedgerRecording:
    """Tests for recording entries to the ledger."""

    @pytest.fixture
    def ledger(self):
        """Create a fresh ledger for each test."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        return ContinuityLedger(session_id="test-session")

    # -------------------------------------------------------------------------
    # Goals
    # -------------------------------------------------------------------------

    def test_add_goal(self, ledger):
        """Test adding a goal to the ledger."""
        ledger.add_goal("Implement user authentication")

        assert len(ledger.goals) == 1
        assert ledger.goals[0]["description"] == "Implement user authentication"

    def test_add_goal_with_priority(self, ledger):
        """Test adding a goal with priority level."""
        ledger.add_goal("Fix critical bug", priority="high")

        assert ledger.goals[0]["priority"] == "high"

    def test_add_goal_with_status(self, ledger):
        """Test adding a goal with initial status."""
        ledger.add_goal("Complete refactor", status="in_progress")

        assert ledger.goals[0]["status"] == "in_progress"

    def test_add_multiple_goals(self, ledger):
        """Test adding multiple goals."""
        ledger.add_goal("Goal 1")
        ledger.add_goal("Goal 2")
        ledger.add_goal("Goal 3")

        assert len(ledger.goals) == 3

    def test_update_goal_status(self, ledger):
        """Test updating a goal's status."""
        ledger.add_goal("Complete task")
        goal_id = ledger.goals[0]["id"]

        ledger.update_goal(goal_id, status="completed")

        assert ledger.goals[0]["status"] == "completed"

    def test_goal_has_timestamp(self, ledger):
        """Test that goals have timestamps."""
        ledger.add_goal("New goal")

        assert "created_at" in ledger.goals[0]

    # -------------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------------

    def test_add_decision(self, ledger):
        """Test adding a decision to the ledger."""
        ledger.add_decision(
            decision="Use factory pattern for object creation",
            rationale="Improves testability and decoupling",
        )

        assert len(ledger.decisions) == 1
        assert ledger.decisions[0]["decision"] == "Use factory pattern for object creation"
        assert ledger.decisions[0]["rationale"] == "Improves testability and decoupling"

    def test_add_decision_with_alternatives(self, ledger):
        """Test adding a decision with alternatives considered."""
        ledger.add_decision(
            decision="Use PostgreSQL",
            rationale="Better JSON support",
            alternatives=["MySQL", "MongoDB", "SQLite"],
        )

        assert ledger.decisions[0]["alternatives"] == ["MySQL", "MongoDB", "SQLite"]

    def test_add_decision_with_impact(self, ledger):
        """Test adding a decision with impact assessment."""
        ledger.add_decision(
            decision="Migrate to async",
            rationale="Performance requirements",
            impact="high",
        )

        assert ledger.decisions[0]["impact"] == "high"

    def test_decision_has_timestamp(self, ledger):
        """Test that decisions have timestamps."""
        ledger.add_decision(
            decision="Test decision",
            rationale="Test rationale",
        )

        assert "created_at" in ledger.decisions[0]

    def test_add_decision_with_context(self, ledger):
        """Test adding a decision with additional context."""
        ledger.add_decision(
            decision="Use retry mechanism",
            rationale="Handle transient failures",
            context={"error_type": "NetworkError", "frequency": "occasional"},
        )

        assert ledger.decisions[0]["context"]["error_type"] == "NetworkError"

    # -------------------------------------------------------------------------
    # Blockers
    # -------------------------------------------------------------------------

    def test_add_blocker(self, ledger):
        """Test adding a blocker to the ledger."""
        ledger.add_blocker(
            description="Missing API credentials",
            severity="critical",
        )

        assert len(ledger.blockers) == 1
        assert ledger.blockers[0]["description"] == "Missing API credentials"
        assert ledger.blockers[0]["severity"] == "critical"

    def test_add_blocker_with_suggested_resolution(self, ledger):
        """Test adding a blocker with suggested resolution."""
        ledger.add_blocker(
            description="Circular dependency detected",
            severity="high",
            suggested_resolution="Introduce interface to break cycle",
        )

        assert ledger.blockers[0]["suggested_resolution"] == "Introduce interface to break cycle"

    def test_add_blocker_with_related_files(self, ledger):
        """Test adding a blocker with related file paths."""
        ledger.add_blocker(
            description="Type mismatch in models",
            severity="medium",
            related_files=["src/models.py", "src/schemas.py"],
        )

        assert ledger.blockers[0]["related_files"] == ["src/models.py", "src/schemas.py"]

    def test_resolve_blocker(self, ledger):
        """Test marking a blocker as resolved."""
        ledger.add_blocker(
            description="Test blocker",
            severity="low",
        )
        blocker_id = ledger.blockers[0]["id"]

        ledger.resolve_blocker(blocker_id, resolution="Fixed by updating config")

        assert ledger.blockers[0]["resolved"] is True
        assert ledger.blockers[0]["resolution"] == "Fixed by updating config"

    def test_blocker_has_timestamp(self, ledger):
        """Test that blockers have timestamps."""
        ledger.add_blocker(description="Test blocker", severity="low")

        assert "created_at" in ledger.blockers[0]

    # -------------------------------------------------------------------------
    # Handoff Notes
    # -------------------------------------------------------------------------

    def test_add_handoff_note(self, ledger):
        """Test adding a handoff note for the next session."""
        ledger.add_handoff_note(
            "Remember to run integration tests after the API changes",
        )

        assert len(ledger.handoff_notes) == 1
        assert ledger.handoff_notes[0]["note"] == "Remember to run integration tests after the API changes"

    def test_add_handoff_note_with_category(self, ledger):
        """Test adding a handoff note with category."""
        ledger.add_handoff_note(
            "Check memory usage after processing large files",
            category="warning",
        )

        assert ledger.handoff_notes[0]["category"] == "warning"

    def test_add_handoff_note_with_priority(self, ledger):
        """Test adding a handoff note with priority."""
        ledger.add_handoff_note(
            "Critical: Must complete security audit",
            priority="urgent",
        )

        assert ledger.handoff_notes[0]["priority"] == "urgent"

    def test_handoff_note_has_timestamp(self, ledger):
        """Test that handoff notes have timestamps."""
        ledger.add_handoff_note("Test note")

        assert "created_at" in ledger.handoff_notes[0]


# =============================================================================
# TestLedgerPersistence - Test save/load functionality
# =============================================================================


class TestLedgerPersistence:
    """Tests for saving and loading ledgers."""

    @pytest.fixture
    def temp_ledger_path(self):
        """Create a temporary directory for test ledgers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "continuity" / "ledger.json"

    @pytest.fixture
    def populated_ledger(self):
        """Create a ledger with sample data."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(
            session_id="test-persist",
            feature_id="feature/test",
            issue_number=42,
        )
        ledger.add_goal("Complete implementation", priority="high")
        ledger.add_decision(
            decision="Use TDD approach",
            rationale="Ensures correctness",
        )
        ledger.add_blocker(
            description="Missing test fixtures",
            severity="medium",
        )
        ledger.add_handoff_note("Tests need more coverage")

        return ledger

    def test_save_ledger_to_file(self, populated_ledger, temp_ledger_path):
        """Test saving a ledger to a JSON file."""
        populated_ledger.save(temp_ledger_path)

        assert temp_ledger_path.exists()

    def test_save_creates_parent_directories(self, populated_ledger, temp_ledger_path):
        """Test that save creates parent directories if needed."""
        assert not temp_ledger_path.parent.exists()

        populated_ledger.save(temp_ledger_path)

        assert temp_ledger_path.parent.exists()

    def test_load_ledger_from_file(self, populated_ledger, temp_ledger_path):
        """Test loading a ledger from a JSON file."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        assert loaded.session_id == populated_ledger.session_id
        assert loaded.feature_id == populated_ledger.feature_id
        assert loaded.issue_number == populated_ledger.issue_number

    def test_load_preserves_goals(self, populated_ledger, temp_ledger_path):
        """Test that loading preserves all goals."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        assert len(loaded.goals) == len(populated_ledger.goals)
        assert loaded.goals[0]["description"] == "Complete implementation"
        assert loaded.goals[0]["priority"] == "high"

    def test_load_preserves_decisions(self, populated_ledger, temp_ledger_path):
        """Test that loading preserves all decisions."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        assert len(loaded.decisions) == len(populated_ledger.decisions)
        assert loaded.decisions[0]["decision"] == "Use TDD approach"

    def test_load_preserves_blockers(self, populated_ledger, temp_ledger_path):
        """Test that loading preserves all blockers."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        assert len(loaded.blockers) == len(populated_ledger.blockers)
        assert loaded.blockers[0]["description"] == "Missing test fixtures"

    def test_load_preserves_handoff_notes(self, populated_ledger, temp_ledger_path):
        """Test that loading preserves all handoff notes."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        assert len(loaded.handoff_notes) == len(populated_ledger.handoff_notes)
        assert loaded.handoff_notes[0]["note"] == "Tests need more coverage"

    def test_load_nonexistent_file_returns_none(self, temp_ledger_path):
        """Test that loading a nonexistent file returns None."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        result = ContinuityLedger.load(temp_ledger_path)

        assert result is None

    def test_to_dict_serialization(self, populated_ledger):
        """Test that ledger can be serialized to dictionary."""
        data = populated_ledger.to_dict()

        assert data["session_id"] == "test-persist"
        assert data["feature_id"] == "feature/test"
        assert data["issue_number"] == 42
        assert "goals" in data
        assert "decisions" in data
        assert "blockers" in data
        assert "handoff_notes" in data

    def test_from_dict_deserialization(self, populated_ledger):
        """Test that ledger can be deserialized from dictionary."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        data = populated_ledger.to_dict()
        restored = ContinuityLedger.from_dict(data)

        assert restored.session_id == populated_ledger.session_id
        assert len(restored.goals) == len(populated_ledger.goals)

    def test_roundtrip_preserves_all_data(self, populated_ledger, temp_ledger_path):
        """Test that save/load roundtrip preserves all data."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        populated_ledger.save(temp_ledger_path)
        loaded = ContinuityLedger.load(temp_ledger_path)

        # Compare serialized forms
        original_dict = populated_ledger.to_dict()
        loaded_dict = loaded.to_dict()

        # Compare key fields (timestamps may differ slightly)
        assert original_dict["session_id"] == loaded_dict["session_id"]
        assert original_dict["feature_id"] == loaded_dict["feature_id"]
        assert original_dict["goals"] == loaded_dict["goals"]
        assert original_dict["decisions"] == loaded_dict["decisions"]
        assert original_dict["blockers"] == loaded_dict["blockers"]
        assert original_dict["handoff_notes"] == loaded_dict["handoff_notes"]


# =============================================================================
# TestLedgerSessionRestore - Test restoring from prior sessions
# =============================================================================


class TestLedgerSessionRestore:
    """Tests for restoring ledger from prior sessions."""

    @pytest.fixture
    def temp_continuity_dir(self):
        """Create a temporary continuity directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_dir = Path(tmpdir) / ".swarm" / "continuity"
            continuity_dir.mkdir(parents=True)
            yield continuity_dir

    @pytest.fixture
    def prior_session_ledger(self, temp_continuity_dir):
        """Create a prior session ledger for testing."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(
            session_id="prior-session-001",
            feature_id="feature/auth",
            issue_number=10,
        )
        ledger.add_goal("Implement OAuth2 flow", priority="high", status="in_progress")
        ledger.add_decision(
            decision="Use PKCE for public clients",
            rationale="Security best practice",
        )
        ledger.add_blocker(
            description="Token refresh logic unclear",
            severity="medium",
        )
        ledger.add_handoff_note("Check token expiry handling")

        # Save to the continuity directory
        ledger_path = temp_continuity_dir / "prior-session-001.json"
        ledger.save(ledger_path)

        return ledger, ledger_path

    def test_find_latest_ledger_for_feature(self, temp_continuity_dir, prior_session_ledger):
        """Test finding the most recent ledger for a feature."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger.find_latest(
            continuity_dir=temp_continuity_dir,
            feature_id="feature/auth",
        )

        assert ledger is not None
        assert ledger.feature_id == "feature/auth"

    def test_find_latest_ledger_for_issue(self, temp_continuity_dir, prior_session_ledger):
        """Test finding the most recent ledger for an issue number."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger.find_latest(
            continuity_dir=temp_continuity_dir,
            issue_number=10,
        )

        assert ledger is not None
        assert ledger.issue_number == 10

    def test_find_latest_returns_none_when_no_match(self, temp_continuity_dir):
        """Test that find_latest returns None when no matching ledger exists."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger.find_latest(
            continuity_dir=temp_continuity_dir,
            feature_id="feature/nonexistent",
        )

        assert ledger is None

    def test_create_continuation_from_prior(self, prior_session_ledger, temp_continuity_dir):
        """Test creating a new ledger that continues from a prior session."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        new_ledger = ContinuityLedger.continue_from(
            prior_ledger,
            new_session_id="continuation-session-002",
        )

        # New ledger should reference the parent
        assert new_ledger.parent_session_id == prior_ledger.session_id
        # Should inherit feature/issue context
        assert new_ledger.feature_id == prior_ledger.feature_id
        assert new_ledger.issue_number == prior_ledger.issue_number
        # Should have a new session ID
        assert new_ledger.session_id == "continuation-session-002"

    def test_continuation_carries_over_incomplete_goals(self, prior_session_ledger, temp_continuity_dir):
        """Test that continuing from prior session carries over incomplete goals."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        new_ledger = ContinuityLedger.continue_from(prior_ledger)

        # Incomplete goals should be carried over
        incomplete_goals = [g for g in new_ledger.goals if g.get("status") != "completed"]
        assert len(incomplete_goals) >= 1
        assert any("OAuth2" in g["description"] for g in incomplete_goals)

    def test_continuation_carries_over_unresolved_blockers(self, prior_session_ledger, temp_continuity_dir):
        """Test that continuing from prior session carries over unresolved blockers."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        new_ledger = ContinuityLedger.continue_from(prior_ledger)

        # Unresolved blockers should be carried over
        unresolved = [b for b in new_ledger.blockers if not b.get("resolved")]
        assert len(unresolved) >= 1

    def test_continuation_includes_prior_handoff_notes(self, prior_session_ledger, temp_continuity_dir):
        """Test that continuing from prior session includes handoff notes."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        new_ledger = ContinuityLedger.continue_from(prior_ledger)

        # Prior session's handoff notes should be available
        assert new_ledger.prior_handoff_notes is not None
        assert len(new_ledger.prior_handoff_notes) >= 1
        assert any("token expiry" in n["note"] for n in new_ledger.prior_handoff_notes)

    def test_get_context_for_injection(self, prior_session_ledger, temp_continuity_dir):
        """Test getting formatted context for injection into new session."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        context = prior_ledger.get_injection_context()

        # Context should be a string suitable for prompt injection
        assert isinstance(context, str)
        assert "OAuth2" in context  # Goals mentioned
        assert "PKCE" in context  # Decisions mentioned
        assert "token refresh" in context.lower()  # Blockers mentioned

    def test_get_summary_for_session_start(self, prior_session_ledger, temp_continuity_dir):
        """Test getting a summary of prior session for SessionStart hook."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        prior_ledger, _ = prior_session_ledger

        summary = prior_ledger.get_summary()

        assert "goals" in summary
        assert "decisions" in summary
        assert "blockers" in summary
        assert "handoff_notes" in summary
        assert summary["goals"]["total"] >= 1
        assert summary["blockers"]["unresolved"] >= 1


# =============================================================================
# TestLedgerAutoSerialization - Test auto-serialize before compaction
# =============================================================================


class TestLedgerAutoSerialization:
    """Tests for auto-serialization before context compaction."""

    @pytest.fixture
    def temp_continuity_dir(self):
        """Create a temporary continuity directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_dir = Path(tmpdir) / ".swarm" / "continuity"
            continuity_dir.mkdir(parents=True)
            yield continuity_dir

    def test_register_compaction_callback(self, temp_continuity_dir):
        """Test registering a callback for context compaction events."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(session_id="compaction-test")
        callback_called = []

        def on_compaction():
            callback_called.append(True)

        ledger.on_compaction(on_compaction)

        # Trigger compaction event
        ledger.trigger_compaction_save()

        assert len(callback_called) == 1

    def test_auto_save_on_compaction(self, temp_continuity_dir):
        """Test that ledger auto-saves when compaction is triggered."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        save_path = temp_continuity_dir / "auto-save-test.json"
        ledger = ContinuityLedger(session_id="auto-save-test")
        ledger.add_goal("Important goal")

        ledger.configure_auto_save(save_path)
        ledger.trigger_compaction_save()

        assert save_path.exists()

        # Verify content was saved
        loaded = ContinuityLedger.load(save_path)
        assert loaded.goals[0]["description"] == "Important goal"

    def test_compaction_preserves_critical_context(self, temp_continuity_dir):
        """Test that compaction preserves the most critical context."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(session_id="critical-context")

        # Add various entries with different priorities
        ledger.add_goal("Critical goal", priority="critical")
        ledger.add_goal("Normal goal", priority="normal")
        ledger.add_blocker("Critical blocker", severity="critical")
        ledger.add_blocker("Low blocker", severity="low")

        compacted = ledger.get_compacted_context(max_tokens=500)

        # Critical items should be preserved
        assert "Critical goal" in compacted
        assert "Critical blocker" in compacted

    def test_updated_at_timestamp_on_save(self, temp_continuity_dir):
        """Test that save updates the updated_at timestamp."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        ledger = ContinuityLedger(session_id="timestamp-test")
        original_created = ledger.created_at

        # Wait a tiny bit and save
        import time
        time.sleep(0.01)

        save_path = temp_continuity_dir / "timestamp.json"
        ledger.save(save_path)

        assert ledger.updated_at is not None
        assert ledger.updated_at >= original_created


# =============================================================================
# TestLedgerEntry - Test individual entry dataclasses
# =============================================================================


class TestLedgerEntry:
    """Tests for individual ledger entry types."""

    def test_goal_entry_creation(self):
        """Test creating a GoalEntry."""
        from swarm_attack.continuity.ledger import GoalEntry

        goal = GoalEntry(
            id="goal-1",
            description="Complete implementation",
            priority="high",
            status="pending",
            created_at=datetime.now().isoformat(),
        )

        assert goal.id == "goal-1"
        assert goal.description == "Complete implementation"
        assert goal.priority == "high"
        assert goal.status == "pending"

    def test_decision_entry_creation(self):
        """Test creating a DecisionEntry."""
        from swarm_attack.continuity.ledger import DecisionEntry

        decision = DecisionEntry(
            id="decision-1",
            decision="Use async pattern",
            rationale="Better performance",
            alternatives=["sync", "threading"],
            impact="medium",
            created_at=datetime.now().isoformat(),
        )

        assert decision.id == "decision-1"
        assert decision.decision == "Use async pattern"
        assert decision.rationale == "Better performance"
        assert decision.alternatives == ["sync", "threading"]

    def test_blocker_entry_creation(self):
        """Test creating a BlockerEntry."""
        from swarm_attack.continuity.ledger import BlockerEntry

        blocker = BlockerEntry(
            id="blocker-1",
            description="Missing dependency",
            severity="high",
            resolved=False,
            created_at=datetime.now().isoformat(),
        )

        assert blocker.id == "blocker-1"
        assert blocker.description == "Missing dependency"
        assert blocker.severity == "high"
        assert blocker.resolved is False

    def test_handoff_note_entry_creation(self):
        """Test creating a HandoffNoteEntry."""
        from swarm_attack.continuity.ledger import HandoffNoteEntry

        note = HandoffNoteEntry(
            id="note-1",
            note="Remember to test edge cases",
            category="testing",
            priority="normal",
            created_at=datetime.now().isoformat(),
        )

        assert note.id == "note-1"
        assert note.note == "Remember to test edge cases"
        assert note.category == "testing"


# =============================================================================
# TestLedgerIntegration - Integration tests for realistic workflows
# =============================================================================


class TestLedgerIntegration:
    """Integration tests for realistic ledger usage patterns."""

    @pytest.fixture
    def temp_continuity_dir(self):
        """Create a temporary continuity directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_dir = Path(tmpdir) / ".swarm" / "continuity"
            continuity_dir.mkdir(parents=True)
            yield continuity_dir

    def test_full_session_workflow(self, temp_continuity_dir):
        """Test a complete session workflow with ledger."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Session 1: Start work on a feature
        session1 = ContinuityLedger(
            session_id="session-1",
            feature_id="feature/user-auth",
            issue_number=42,
        )

        # Record goals
        session1.add_goal("Implement login endpoint", priority="high")
        session1.add_goal("Add password validation", priority="high")

        # Make decisions
        session1.add_decision(
            decision="Use bcrypt for password hashing",
            rationale="Industry standard, secure",
        )

        # Hit a blocker
        session1.add_blocker(
            description="JWT secret not configured",
            severity="critical",
        )

        # Update goal progress
        goal_id = session1.goals[0]["id"]
        session1.update_goal(goal_id, status="completed")

        # Add handoff notes before ending
        session1.add_handoff_note("Need to configure JWT_SECRET in .env")
        session1.add_handoff_note("Password validation regex may need adjustment")

        # Save session
        session1_path = temp_continuity_dir / "session-1.json"
        session1.save(session1_path)

        # Session 2: Continue from session 1
        session2 = ContinuityLedger.continue_from(session1, new_session_id="session-2")

        # Verify context was carried over
        assert session2.parent_session_id == "session-1"
        assert session2.feature_id == "feature/user-auth"
        assert len(session2.prior_handoff_notes) >= 2

        # Resolve the blocker from session 1
        blocker_id = session2.blockers[0]["id"]
        session2.resolve_blocker(blocker_id, resolution="Added JWT_SECRET to .env")

        # Complete remaining goals
        remaining = [g for g in session2.goals if g.get("status") != "completed"]
        for goal in remaining:
            session2.update_goal(goal["id"], status="completed")

        # Save session 2
        session2_path = temp_continuity_dir / "session-2.json"
        session2.save(session2_path)

        # Verify final state
        loaded = ContinuityLedger.load(session2_path)
        assert all(g.get("status") == "completed" for g in loaded.goals)
        assert all(b.get("resolved") for b in loaded.blockers)

    def test_session_chain_tracking(self, temp_continuity_dir):
        """Test tracking a chain of sessions."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Create a chain of 3 sessions
        session1 = ContinuityLedger(session_id="chain-1")
        session1.add_goal("Initial work")
        session1.save(temp_continuity_dir / "chain-1.json")

        session2 = ContinuityLedger.continue_from(session1, new_session_id="chain-2")
        session2.add_goal("Continued work")
        session2.save(temp_continuity_dir / "chain-2.json")

        session3 = ContinuityLedger.continue_from(session2, new_session_id="chain-3")
        session3.add_goal("Final work")
        session3.save(temp_continuity_dir / "chain-3.json")

        # Verify chain
        assert session3.parent_session_id == "chain-2"
        assert session2.parent_session_id == "chain-1"
        assert session1.parent_session_id is None

    def test_concurrent_sessions_different_features(self, temp_continuity_dir):
        """Test managing concurrent sessions for different features."""
        from swarm_attack.continuity.ledger import ContinuityLedger

        # Two features being worked on in parallel
        auth_session = ContinuityLedger(
            session_id="auth-session-1",
            feature_id="feature/auth",
            issue_number=10,
        )
        auth_session.add_goal("Implement auth")
        auth_session.save(temp_continuity_dir / "auth-session-1.json")

        api_session = ContinuityLedger(
            session_id="api-session-1",
            feature_id="feature/api",
            issue_number=20,
        )
        api_session.add_goal("Implement API")
        api_session.save(temp_continuity_dir / "api-session-1.json")

        # Find latest for each feature
        auth_latest = ContinuityLedger.find_latest(
            continuity_dir=temp_continuity_dir,
            feature_id="feature/auth",
        )
        api_latest = ContinuityLedger.find_latest(
            continuity_dir=temp_continuity_dir,
            feature_id="feature/api",
        )

        assert auth_latest.session_id == "auth-session-1"
        assert api_latest.session_id == "api-session-1"
        assert auth_latest.issue_number == 10
        assert api_latest.issue_number == 20
