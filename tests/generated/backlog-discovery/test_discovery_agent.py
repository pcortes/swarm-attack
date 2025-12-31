"""Tests for TestFailureDiscoveryAgent.

TDD tests for Issue 1.3: Discovery agent for finding test failures.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore
from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import (
    TestFailureDiscoveryAgent,
)
from swarm_attack.chief_of_staff.episodes import Episode


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = Mock()
    config.repo_root = "/test/repo"
    config.state_path = Path("/test/.swarm/state")
    config.sessions_path = Path("/test/.swarm/sessions")
    return config


@pytest.fixture
def store(tmp_path: Path) -> BacklogStore:
    """Create a BacklogStore with temporary directory."""
    return BacklogStore(base_path=tmp_path)


@pytest.fixture
def discovery_agent(mock_config, store):
    """Create a TestFailureDiscoveryAgent with mock dependencies."""
    agent = TestFailureDiscoveryAgent(
        config=mock_config,
        backlog_store=store,
    )
    return agent


class TestTestFailureDiscoveryAgentInit:
    """Tests for agent initialization."""

    def test_agent_name(self, discovery_agent):
        """Test agent has correct name."""
        assert discovery_agent.name == "test-failure-discovery"

    def test_agent_has_backlog_store(self, discovery_agent, store):
        """Test agent has backlog store reference."""
        assert discovery_agent.backlog_store is store


class TestParseTestFailures:
    """Tests for parsing pytest output."""

    def test_parse_single_failure(self, discovery_agent):
        """Test parsing a single test failure."""
        pytest_output = """
FAILED tests/test_auth.py::test_login_fails - AssertionError: expected True
========================= 1 failed in 0.5s ==========================
"""
        failures = discovery_agent._parse_pytest_output(pytest_output)

        assert len(failures) == 1
        assert failures[0]["test_file"] == "tests/test_auth.py"
        assert failures[0]["test_name"] == "test_login_fails"
        assert "AssertionError" in failures[0]["error"]

    def test_parse_multiple_failures(self, discovery_agent):
        """Test parsing multiple test failures."""
        pytest_output = """
FAILED tests/test_auth.py::test_login - AssertionError
FAILED tests/test_payment.py::test_checkout - ValueError
FAILED tests/test_api.py::TestAPI::test_get - HTTPError
========================= 3 failed in 1.5s ==========================
"""
        failures = discovery_agent._parse_pytest_output(pytest_output)

        assert len(failures) == 3
        assert failures[0]["test_file"] == "tests/test_auth.py"
        assert failures[1]["test_file"] == "tests/test_payment.py"
        assert failures[2]["test_file"] == "tests/test_api.py"
        assert failures[2]["test_name"] == "TestAPI::test_get"

    def test_parse_no_failures(self, discovery_agent):
        """Test parsing output with no failures."""
        pytest_output = """
========================= 10 passed in 2.0s ==========================
"""
        failures = discovery_agent._parse_pytest_output(pytest_output)
        assert failures == []

    def test_parse_empty_output(self, discovery_agent):
        """Test parsing empty output."""
        failures = discovery_agent._parse_pytest_output("")
        assert failures == []


class TestExtractEpisodeFailures:
    """Tests for extracting failures from episodes."""

    def test_extract_failures_from_episodes(self, discovery_agent):
        """Test extracting failed test episodes."""
        episodes = [
            Episode(
                episode_id="ep-1",
                timestamp="2025-01-15T10:00:00Z",
                goal_id="test-auth-login",
                success=False,
                cost_usd=0.05,
                duration_seconds=30,
                error="Test failed: assertion error",
            ),
            Episode(
                episode_id="ep-2",
                timestamp="2025-01-15T11:00:00Z",
                goal_id="implement-feature",
                success=True,
                cost_usd=0.10,
                duration_seconds=60,
            ),
            Episode(
                episode_id="ep-3",
                timestamp="2025-01-15T12:00:00Z",
                goal_id="test-payment-flow",
                success=False,
                cost_usd=0.05,
                duration_seconds=45,
                error="Test failed: timeout",
            ),
        ]

        failures = discovery_agent._extract_episode_failures(episodes)

        assert len(failures) == 2
        assert failures[0]["episode_id"] == "ep-1"
        assert failures[1]["episode_id"] == "ep-3"

    def test_extract_failures_empty_episodes(self, discovery_agent):
        """Test extracting from empty episodes list."""
        failures = discovery_agent._extract_episode_failures([])
        assert failures == []

    def test_extract_failures_all_success(self, discovery_agent):
        """Test extracting when all episodes succeeded."""
        episodes = [
            Episode(
                episode_id="ep-1",
                timestamp="2025-01-15T10:00:00Z",
                goal_id="test-all-pass",
                success=True,
                cost_usd=0.05,
                duration_seconds=30,
            ),
        ]

        failures = discovery_agent._extract_episode_failures(episodes)
        assert failures == []


class TestConvertToOpportunities:
    """Tests for converting failures to Opportunity objects."""

    def test_convert_pytest_failure_to_opportunity(self, discovery_agent):
        """Test converting a pytest failure to Opportunity."""
        failure = {
            "test_file": "tests/test_auth.py",
            "test_name": "test_login_fails",
            "error": "AssertionError: expected True, got False",
            "source": "pytest",
        }

        opp = discovery_agent._failure_to_opportunity(failure)

        assert opp.opportunity_type == OpportunityType.TEST_FAILURE
        assert opp.status == OpportunityStatus.DISCOVERED
        assert "test_login_fails" in opp.title
        assert len(opp.evidence) >= 1
        assert opp.evidence[0].source == "test_output"
        assert "tests/test_auth.py" in opp.affected_files

    def test_convert_episode_failure_to_opportunity(self, discovery_agent):
        """Test converting an episode failure to Opportunity."""
        failure = {
            "episode_id": "ep-123",
            "goal_id": "test-payment-validation",
            "error": "Test failed: payment validation error",
            "timestamp": "2025-01-15T10:00:00Z",
            "source": "episode",
        }

        opp = discovery_agent._failure_to_opportunity(failure)

        assert opp.opportunity_type == OpportunityType.TEST_FAILURE
        assert "payment" in opp.title.lower() or "validation" in opp.title.lower()
        assert len(opp.evidence) >= 1


class TestActionabilityScoring:
    """Tests for rule-based actionability scoring."""

    def test_actionability_score_clear_error(self, discovery_agent):
        """Test scoring for clear, specific error."""
        failure = {
            "test_file": "tests/test_auth.py",
            "test_name": "test_login",
            "error": "AssertionError: expected 'admin', got 'user'",
            "source": "pytest",
        }

        score = discovery_agent._calculate_actionability(failure)

        # Clear assertion error with specific values should score high
        assert score.clarity >= 0.7
        assert score.evidence >= 0.7
        assert score.effort in ["small", "medium", "large"]

    def test_actionability_score_vague_error(self, discovery_agent):
        """Test scoring for vague error."""
        failure = {
            "test_file": "tests/test_complex.py",
            "test_name": "test_something",
            "error": "Error occurred",
            "source": "pytest",
        }

        score = discovery_agent._calculate_actionability(failure)

        # Vague error should score lower
        assert score.clarity <= 0.5

    def test_actionability_scoring_rules_detect_small_effort(self, discovery_agent):
        """Test that simple fixes are detected as small effort."""
        # Type error is usually a small fix
        failure = {
            "test_file": "tests/test_types.py",
            "test_name": "test_type_check",
            "error": "TypeError: expected str, got int",
            "source": "pytest",
        }

        score = discovery_agent._calculate_actionability(failure)
        assert score.effort in ["small", "medium"]  # Type errors are usually quick fixes


class TestDeduplication:
    """Tests for skipping duplicates of rejected opportunities."""

    def test_skips_duplicates_of_rejected(self, discovery_agent, store):
        """Test that similar rejected opportunities are skipped."""
        # First, add a rejected opportunity
        rejected = Opportunity(
            opportunity_id="opp-rejected",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.REJECTED,
            title="Fix test_login_auth failing",
            description="Auth login test failing due to assertion",
            evidence=[
                Evidence(source="test_output", content="test_login_auth FAILED")
            ],
        )
        store.save_opportunity(rejected)

        # Now try to discover a similar failure
        failure = {
            "test_file": "tests/test_auth.py",
            "test_name": "test_login_auth",
            "error": "AssertionError",
            "source": "pytest",
        }

        # This should be flagged as duplicate
        is_dup = discovery_agent._is_duplicate_of_rejected(failure, store)
        assert is_dup is True

    def test_does_not_skip_new_failures(self, discovery_agent, store):
        """Test that new failures are not skipped."""
        failure = {
            "test_file": "tests/test_payment.py",
            "test_name": "test_checkout_flow",
            "error": "ValueError",
            "source": "pytest",
        }

        is_dup = discovery_agent._is_duplicate_of_rejected(failure, store)
        assert is_dup is False


class TestMergeFailures:
    """Tests for merging failures from multiple sources."""

    def test_merges_pytest_and_episode_failures(self, discovery_agent):
        """Test merging failures from pytest and episodes."""
        pytest_failures = [
            {
                "test_file": "tests/test_auth.py",
                "test_name": "test_login",
                "error": "AssertionError",
                "source": "pytest",
            },
        ]

        episode_failures = [
            {
                "episode_id": "ep-1",
                "goal_id": "test-payment",
                "error": "Test failed",
                "source": "episode",
            },
        ]

        merged = discovery_agent._merge_failures(pytest_failures, episode_failures)

        assert len(merged) == 2

    def test_deduplicates_same_test_from_multiple_sources(self, discovery_agent):
        """Test deduplication when same test appears in both sources."""
        pytest_failures = [
            {
                "test_file": "tests/test_auth.py",
                "test_name": "test_login",
                "error": "AssertionError",
                "source": "pytest",
            },
        ]

        episode_failures = [
            {
                "episode_id": "ep-1",
                "goal_id": "test-auth-test_login",
                "error": "Test failed",
                "source": "episode",
            },
        ]

        merged = discovery_agent._merge_failures(pytest_failures, episode_failures)

        # Should deduplicate if same test
        assert len(merged) <= 2


class TestDiscoveryRun:
    """Tests for the full discovery run."""

    def test_discovers_opportunities_from_failures(
        self, discovery_agent, store, mock_config
    ):
        """Test full discovery run finds opportunities."""
        # Mock pytest run
        pytest_output = """
FAILED tests/test_auth.py::test_login - AssertionError
========================= 1 failed in 0.5s ==========================
"""
        with patch.object(
            discovery_agent, "_run_pytest", return_value=pytest_output
        ), patch.object(
            discovery_agent, "_get_recent_episodes", return_value=[]
        ):
            result = discovery_agent.run(context={})

        assert result.success is True
        assert "opportunities" in result.output
        assert len(result.output["opportunities"]) >= 1

    def test_returns_empty_when_no_failures(self, discovery_agent, store, mock_config):
        """Test discovery returns empty when no failures."""
        pytest_output = """
========================= 10 passed in 2.0s ==========================
"""
        with patch.object(
            discovery_agent, "_run_pytest", return_value=pytest_output
        ), patch.object(
            discovery_agent, "_get_recent_episodes", return_value=[]
        ):
            result = discovery_agent.run(context={})

        assert result.success is True
        assert result.output["opportunities"] == []

    def test_saves_opportunities_to_store(self, discovery_agent, store, mock_config):
        """Test that discovered opportunities are saved to store."""
        pytest_output = """
FAILED tests/test_auth.py::test_login - AssertionError
FAILED tests/test_payment.py::test_checkout - ValueError
========================= 2 failed in 1.0s ==========================
"""
        with patch.object(
            discovery_agent, "_run_pytest", return_value=pytest_output
        ), patch.object(
            discovery_agent, "_get_recent_episodes", return_value=[]
        ):
            discovery_agent.run(context={})

        # Check store has the opportunities
        all_opps = store.get_all()
        assert len(all_opps) >= 2


class TestGenerateOpportunityId:
    """Tests for opportunity ID generation."""

    def test_generates_unique_ids(self, discovery_agent):
        """Test that generated IDs are unique."""
        ids = set()
        for i in range(100):
            failure = {
                "test_file": f"tests/test_{i}.py",
                "test_name": f"test_func_{i}",
                "error": "Error",
                "source": "pytest",
            }
            opp_id = discovery_agent._generate_opportunity_id(failure)
            ids.add(opp_id)

        assert len(ids) == 100  # All unique

    def test_id_contains_type_prefix(self, discovery_agent):
        """Test that ID contains type prefix."""
        failure = {
            "test_file": "tests/test_auth.py",
            "test_name": "test_login",
            "error": "Error",
            "source": "pytest",
        }
        opp_id = discovery_agent._generate_opportunity_id(failure)

        assert opp_id.startswith("opp-tf-")  # tf = test_failure


class TestLimitResults:
    """Tests for limiting number of results."""

    def test_respects_max_opportunities_limit(self, discovery_agent, store, mock_config):
        """Test that run respects max_opportunities in context."""
        # Create output with many failures
        failures = "\n".join(
            [f"FAILED tests/test_{i}.py::test_func - Error" for i in range(20)]
        )
        pytest_output = f"""
{failures}
========================= 20 failed in 2.0s ==========================
"""
        with patch.object(
            discovery_agent, "_run_pytest", return_value=pytest_output
        ), patch.object(
            discovery_agent, "_get_recent_episodes", return_value=[]
        ):
            result = discovery_agent.run(context={"max_opportunities": 5})

        assert len(result.output["opportunities"]) <= 5
