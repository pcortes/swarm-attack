"""Tests for BacklogStore persistence.

TDD tests for Issue 1.2: BacklogStore with atomic writes and similarity search.
"""

import json
import pytest
from pathlib import Path

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    ActionabilityScore,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore


@pytest.fixture
def store(tmp_path: Path) -> BacklogStore:
    """Create a BacklogStore with temporary directory."""
    return BacklogStore(base_path=tmp_path)


@pytest.fixture
def sample_opportunity() -> Opportunity:
    """Create a sample opportunity for testing."""
    return Opportunity(
        opportunity_id="opp-001",
        opportunity_type=OpportunityType.TEST_FAILURE,
        status=OpportunityStatus.DISCOVERED,
        title="Fix failing test_bar",
        description="The test_bar test is failing due to assertion error",
        evidence=[
            Evidence(
                source="test_output",
                content="TestFoo::test_bar FAILED",
                file_path="tests/test_foo.py",
                line_number=42,
            )
        ],
        actionability=ActionabilityScore(
            clarity=0.9,
            evidence=0.85,
            effort="small",
            reversibility="full",
        ),
        affected_files=["tests/test_foo.py", "src/foo.py"],
        discovered_by="test-failure-discovery",
    )


class TestBacklogStoreBasics:
    """Basic operations tests for BacklogStore."""

    def test_save_and_retrieve_opportunity(
        self, store: BacklogStore, sample_opportunity: Opportunity
    ):
        """Test saving and retrieving an opportunity."""
        store.save_opportunity(sample_opportunity)

        retrieved = store.get_opportunity(sample_opportunity.opportunity_id)

        assert retrieved is not None
        assert retrieved.opportunity_id == sample_opportunity.opportunity_id
        assert retrieved.title == sample_opportunity.title
        assert retrieved.opportunity_type == OpportunityType.TEST_FAILURE
        assert len(retrieved.evidence) == 1
        assert retrieved.evidence[0].source == "test_output"

    def test_get_nonexistent_opportunity_returns_none(self, store: BacklogStore):
        """Test getting an opportunity that doesn't exist."""
        result = store.get_opportunity("nonexistent-id")
        assert result is None

    def test_save_updates_existing_opportunity(
        self, store: BacklogStore, sample_opportunity: Opportunity
    ):
        """Test that saving an existing opportunity updates it."""
        store.save_opportunity(sample_opportunity)

        # Update the opportunity
        sample_opportunity.status = OpportunityStatus.ACTIONABLE
        sample_opportunity.priority_rank = 1
        store.save_opportunity(sample_opportunity)

        retrieved = store.get_opportunity(sample_opportunity.opportunity_id)
        assert retrieved is not None
        assert retrieved.status == OpportunityStatus.ACTIONABLE
        assert retrieved.priority_rank == 1

    def test_creates_backlog_directory(self, tmp_path: Path):
        """Test that BacklogStore creates the backlog directory."""
        store = BacklogStore(base_path=tmp_path)
        opp = Opportunity(
            opportunity_id="opp-test",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title="Test",
            description="Test description",
            evidence=[],
        )
        store.save_opportunity(opp)

        assert (tmp_path / "backlog").exists()
        assert (tmp_path / "backlog" / "candidates.json").exists()


class TestBacklogStoreStatusQueries:
    """Tests for querying opportunities by status."""

    def test_get_opportunities_by_status(self, store: BacklogStore):
        """Test filtering opportunities by status."""
        # Create opportunities with different statuses
        opps = [
            Opportunity(
                opportunity_id="opp-1",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title="Test 1",
                description="Discovered",
                evidence=[],
            ),
            Opportunity(
                opportunity_id="opp-2",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.ACTIONABLE,
                title="Test 2",
                description="Actionable",
                evidence=[],
            ),
            Opportunity(
                opportunity_id="opp-3",
                opportunity_type=OpportunityType.CODE_QUALITY,
                status=OpportunityStatus.ACTIONABLE,
                title="Test 3",
                description="Also actionable",
                evidence=[],
            ),
        ]

        for opp in opps:
            store.save_opportunity(opp)

        discovered = store.get_opportunities_by_status(OpportunityStatus.DISCOVERED)
        actionable = store.get_opportunities_by_status(OpportunityStatus.ACTIONABLE)

        assert len(discovered) == 1
        assert discovered[0].opportunity_id == "opp-1"
        assert len(actionable) == 2

    def test_get_actionable_opportunities(self, store: BacklogStore):
        """Test getting only actionable opportunities."""
        opps = [
            Opportunity(
                opportunity_id="opp-1",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title="Discovered",
                description="Not actionable yet",
                evidence=[],
            ),
            Opportunity(
                opportunity_id="opp-2",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.ACTIONABLE,
                title="Actionable 1",
                description="Ready to review",
                evidence=[],
                priority_rank=2,
            ),
            Opportunity(
                opportunity_id="opp-3",
                opportunity_type=OpportunityType.CODE_QUALITY,
                status=OpportunityStatus.ACTIONABLE,
                title="Actionable 2",
                description="Also ready",
                evidence=[],
                priority_rank=1,
            ),
        ]

        for opp in opps:
            store.save_opportunity(opp)

        actionable = store.get_actionable()

        assert len(actionable) == 2
        # Should be sorted by priority_rank (lower first)
        assert actionable[0].opportunity_id == "opp-3"
        assert actionable[1].opportunity_id == "opp-2"


class TestBacklogStoreStatusTransitions:
    """Tests for status transition operations."""

    def test_mark_accepted_updates_status(self, store: BacklogStore):
        """Test marking an opportunity as accepted."""
        opp = Opportunity(
            opportunity_id="opp-accept",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.ACTIONABLE,
            title="Ready for acceptance",
            description="Should be accepted",
            evidence=[],
        )
        store.save_opportunity(opp)

        store.mark_accepted("opp-accept", linked_issue=42)

        retrieved = store.get_opportunity("opp-accept")
        assert retrieved is not None
        assert retrieved.status == OpportunityStatus.ACCEPTED
        assert retrieved.linked_issue == 42

    def test_mark_rejected_updates_status(self, store: BacklogStore):
        """Test marking an opportunity as rejected."""
        opp = Opportunity(
            opportunity_id="opp-reject",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.ACTIONABLE,
            title="Will be rejected",
            description="User says no",
            evidence=[],
        )
        store.save_opportunity(opp)

        store.mark_rejected("opp-reject")

        retrieved = store.get_opportunity("opp-reject")
        assert retrieved is not None
        assert retrieved.status == OpportunityStatus.REJECTED

    def test_mark_deferred_updates_status(self, store: BacklogStore):
        """Test marking an opportunity as deferred."""
        opp = Opportunity(
            opportunity_id="opp-defer",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.ACTIONABLE,
            title="Defer for later",
            description="Not now",
            evidence=[],
        )
        store.save_opportunity(opp)

        store.mark_deferred("opp-defer")

        retrieved = store.get_opportunity("opp-defer")
        assert retrieved is not None
        assert retrieved.status == OpportunityStatus.DEFERRED

    def test_status_transition_on_nonexistent_opportunity(self, store: BacklogStore):
        """Test that status transitions on nonexistent opportunities are safe."""
        # Should not raise, just do nothing
        store.mark_accepted("nonexistent")
        store.mark_rejected("nonexistent")
        store.mark_deferred("nonexistent")


class TestBacklogStoreSimilaritySearch:
    """Tests for similarity search functionality."""

    def test_find_similar_opportunities_basic(self, store: BacklogStore):
        """Test finding similar opportunities."""
        opps = [
            Opportunity(
                opportunity_id="opp-1",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.REJECTED,
                title="Fix test_authentication_login failing",
                description="Authentication login test is failing",
                evidence=[
                    Evidence(source="test", content="test_authentication_login FAILED")
                ],
            ),
            Opportunity(
                opportunity_id="opp-2",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.ACCEPTED,
                title="Fix test_payment_processing",
                description="Payment test failing",
                evidence=[Evidence(source="test", content="test_payment FAILED")],
            ),
            Opportunity(
                opportunity_id="opp-3",
                opportunity_type=OpportunityType.CODE_QUALITY,
                status=OpportunityStatus.DISCOVERED,
                title="Reduce complexity in auth module",
                description="Authentication module too complex",
                evidence=[],
            ),
        ]

        for opp in opps:
            store.save_opportunity(opp)

        # Create a new opportunity about auth
        new_opp = Opportunity(
            opportunity_id="opp-new",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Fix test_authentication_logout failing",
            description="Auth logout test failing",
            evidence=[],
        )

        similar = store.find_similar(new_opp, k=2)

        # Should find the two auth-related opportunities
        assert len(similar) <= 2
        ids = [o.opportunity_id for o in similar]
        # opp-1 should be most similar (auth + test_authentication)
        assert "opp-1" in ids

    def test_find_similar_returns_empty_for_no_matches(self, store: BacklogStore):
        """Test find_similar returns empty list when nothing matches."""
        opp = Opportunity(
            opportunity_id="opp-lonely",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Completely unique xyz123 qwerty",
            description="Nothing like anything else",
            evidence=[],
        )

        similar = store.find_similar(opp)
        assert similar == []

    def test_find_similar_limits_results(self, store: BacklogStore):
        """Test that find_similar respects the k limit."""
        # Create many similar opportunities
        for i in range(10):
            opp = Opportunity(
                opportunity_id=f"opp-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title=f"Fix test number {i}",
                description=f"Test {i} is failing",
                evidence=[],
            )
            store.save_opportunity(opp)

        query = Opportunity(
            opportunity_id="query",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Fix test issue",
            description="Test failing",
            evidence=[],
        )

        similar = store.find_similar(query, k=3)
        assert len(similar) <= 3


class TestBacklogStoreAtomicWrites:
    """Tests for atomic write behavior."""

    def test_atomic_write_creates_valid_json(self, store: BacklogStore, tmp_path: Path):
        """Test that writes produce valid JSON files."""
        opp = Opportunity(
            opportunity_id="opp-atomic",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Atomic test",
            description="Should write atomically",
            evidence=[],
        )
        store.save_opportunity(opp)

        # Read the file directly and verify it's valid JSON
        candidates_file = tmp_path / "backlog" / "candidates.json"
        assert candidates_file.exists()

        with open(candidates_file, "r") as f:
            data = json.load(f)

        assert "opportunities" in data
        assert len(data["opportunities"]) == 1
        assert data["opportunities"][0]["opportunity_id"] == "opp-atomic"

    def test_no_temp_files_left_after_save(self, store: BacklogStore, tmp_path: Path):
        """Test that no .tmp files are left after saving."""
        opp = Opportunity(
            opportunity_id="opp-temp",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Temp file test",
            description="Should not leave .tmp files",
            evidence=[],
        )
        store.save_opportunity(opp)

        backlog_dir = tmp_path / "backlog"
        tmp_files = list(backlog_dir.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestBacklogStoreAllOpportunities:
    """Tests for getting all opportunities."""

    def test_get_all_opportunities(self, store: BacklogStore):
        """Test getting all opportunities regardless of status."""
        opps = [
            Opportunity(
                opportunity_id=f"opp-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=status,
                title=f"Opportunity {i}",
                description=f"Description {i}",
                evidence=[],
            )
            for i, status in enumerate(
                [
                    OpportunityStatus.DISCOVERED,
                    OpportunityStatus.ACTIONABLE,
                    OpportunityStatus.ACCEPTED,
                    OpportunityStatus.REJECTED,
                    OpportunityStatus.DEFERRED,
                ]
            )
        ]

        for opp in opps:
            store.save_opportunity(opp)

        all_opps = store.get_all()
        assert len(all_opps) == 5

    def test_get_all_empty_store(self, store: BacklogStore):
        """Test getting all from empty store."""
        all_opps = store.get_all()
        assert all_opps == []


class TestBacklogStoreEdgeCases:
    """Edge case tests for BacklogStore."""

    def test_save_opportunity_with_empty_evidence(self, store: BacklogStore):
        """Test saving opportunity with no evidence."""
        opp = Opportunity(
            opportunity_id="opp-empty-evidence",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title="No evidence yet",
            description="Will gather evidence later",
            evidence=[],
        )
        store.save_opportunity(opp)

        retrieved = store.get_opportunity("opp-empty-evidence")
        assert retrieved is not None
        assert retrieved.evidence == []

    def test_save_opportunity_without_actionability(self, store: BacklogStore):
        """Test saving opportunity without actionability score."""
        opp = Opportunity(
            opportunity_id="opp-no-score",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title="Not scored yet",
            description="Pending scoring",
            evidence=[],
            actionability=None,
        )
        store.save_opportunity(opp)

        retrieved = store.get_opportunity("opp-no-score")
        assert retrieved is not None
        assert retrieved.actionability is None

    def test_multiple_saves_to_same_store(self, store: BacklogStore):
        """Test saving multiple opportunities in sequence."""
        for i in range(5):
            opp = Opportunity(
                opportunity_id=f"opp-seq-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title=f"Sequential opportunity {i}",
                description=f"Number {i} in sequence",
                evidence=[],
            )
            store.save_opportunity(opp)

        all_opps = store.get_all()
        assert len(all_opps) == 5

        for i in range(5):
            assert store.get_opportunity(f"opp-seq-{i}") is not None

    def test_special_characters_in_opportunity_id(self, store: BacklogStore):
        """Test opportunity IDs with special characters."""
        opp = Opportunity(
            opportunity_id="opp-test_failure-2025-01-15T10:30:00",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Special ID test",
            description="ID has special chars",
            evidence=[],
        )
        store.save_opportunity(opp)

        retrieved = store.get_opportunity("opp-test_failure-2025-01-15T10:30:00")
        assert retrieved is not None
