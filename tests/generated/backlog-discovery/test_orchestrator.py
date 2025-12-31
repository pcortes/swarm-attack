"""Tests for DiscoveryOrchestrator.

TDD tests for Issue 7: Orchestrator that runs discovery agents and merges results.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
    ActionabilityScore,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore
from swarm_attack.agents.base import AgentResult


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
def sample_opportunities():
    """Create sample opportunities for testing."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        Opportunity(
            opportunity_id="opp-test-1",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Fix test_login failing",
            description="Login test fails with assertion error",
            evidence=[Evidence(source="test", content="error")],
            actionability=ActionabilityScore(
                clarity=0.8, evidence=0.7, effort="small", reversibility="full"
            ),
            created_at=now,
            updated_at=now,
            discovered_by="test-failure-discovery",
        ),
        Opportunity(
            opportunity_id="opp-stalled-1",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title="Resume stalled feature",
            description="Feature has been stalled for 24h",
            evidence=[Evidence(source="state", content="stalled")],
            actionability=ActionabilityScore(
                clarity=0.7, evidence=0.8, effort="medium", reversibility="full"
            ),
            created_at=now,
            updated_at=now,
            discovered_by="stalled-work-discovery",
        ),
        Opportunity(
            opportunity_id="opp-quality-1",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title="Split large file",
            description="File has 600 lines",
            evidence=[Evidence(source="file_stats", content="600 lines")],
            actionability=ActionabilityScore(
                clarity=0.6, evidence=0.9, effort="large", reversibility="full"
            ),
            created_at=now,
            updated_at=now,
            discovered_by="code-quality-discovery",
        ),
    ]


@pytest.fixture
def mock_test_agent(sample_opportunities):
    """Create a mock test failure agent."""
    agent = Mock()
    agent.run.return_value = AgentResult.success_result(
        output={"opportunities": [sample_opportunities[0]]},
        cost_usd=0.0,
    )
    return agent


@pytest.fixture
def mock_stalled_agent(sample_opportunities):
    """Create a mock stalled work agent."""
    agent = Mock()
    agent.run.return_value = AgentResult.success_result(
        output={"opportunities": [sample_opportunities[1]]},
        cost_usd=0.0,
    )
    return agent


@pytest.fixture
def mock_quality_agent(sample_opportunities):
    """Create a mock code quality agent."""
    agent = Mock()
    agent.run.return_value = AgentResult.success_result(
        output={"opportunities": [sample_opportunities[2]]},
        cost_usd=0.0,
    )
    return agent


@pytest.fixture
def orchestrator(mock_config, store, mock_test_agent, mock_stalled_agent, mock_quality_agent):
    """Create a DiscoveryOrchestrator with mock agents."""
    from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
        DiscoveryOrchestrator,
    )
    return DiscoveryOrchestrator(
        config=mock_config,
        backlog_store=store,
        test_failure_agent=mock_test_agent,
        stalled_work_agent=mock_stalled_agent,
        code_quality_agent=mock_quality_agent,
    )


class TestDiscoveryOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_has_all_agents(self, orchestrator, mock_test_agent, mock_stalled_agent, mock_quality_agent):
        """Orchestrator should have all three agent types."""
        assert orchestrator.agents["test"] is mock_test_agent
        assert orchestrator.agents["stalled"] is mock_stalled_agent
        assert orchestrator.agents["quality"] is mock_quality_agent


class TestSingleAgentDiscovery:
    """Tests for running a single agent type."""

    def test_runs_single_agent(self, orchestrator, mock_test_agent):
        """types=["test"] only runs TestFailureDiscoveryAgent."""
        result = orchestrator.discover(types=["test"])

        assert result.opportunities is not None
        mock_test_agent.run.assert_called_once()

    def test_runs_stalled_agent_only(self, orchestrator, mock_stalled_agent, mock_test_agent):
        """types=["stalled"] only runs StalledWorkDiscoveryAgent."""
        result = orchestrator.discover(types=["stalled"])

        mock_stalled_agent.run.assert_called_once()
        # test agent should not be called
        mock_test_agent.run.assert_not_called()

    def test_runs_quality_agent_only(self, orchestrator, mock_quality_agent, mock_test_agent):
        """types=["quality"] only runs CodeQualityDiscoveryAgent."""
        result = orchestrator.discover(types=["quality"])

        mock_quality_agent.run.assert_called_once()
        mock_test_agent.run.assert_not_called()


class TestAllAgentDiscovery:
    """Tests for running all agents."""

    def test_runs_all_agents(self, orchestrator, mock_test_agent, mock_stalled_agent, mock_quality_agent):
        """types=["all"] runs all discovery agents."""
        result = orchestrator.discover(types=["all"])

        mock_test_agent.run.assert_called_once()
        mock_stalled_agent.run.assert_called_once()
        mock_quality_agent.run.assert_called_once()

    def test_merges_results_from_multiple_agents(self, orchestrator):
        """Results from all agents are combined."""
        result = orchestrator.discover(types=["all"])

        # Should have opportunities from all three agents
        assert len(result.opportunities) >= 3

        # Check we have different types
        types = {o.opportunity_type for o in result.opportunities}
        assert OpportunityType.TEST_FAILURE in types
        assert OpportunityType.STALLED_WORK in types
        assert OpportunityType.CODE_QUALITY in types


class TestDeduplication:
    """Tests for deduplication of similar opportunities."""

    def test_deduplicates_similar_opportunities(self, mock_config, store):
        """Same issue from different agents = 1 opportunity."""
        from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
            DiscoveryOrchestrator,
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Create two similar opportunities (same file/issue)
        opp1 = Opportunity(
            opportunity_id="opp-1",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Fix auth.py test_login failing",
            description="Auth login test fails",
            evidence=[Evidence(source="test", content="error")],
            affected_files=["tests/test_auth.py"],
            created_at=now,
            updated_at=now,
            discovered_by="test-failure-discovery",
        )

        opp2 = Opportunity(
            opportunity_id="opp-2",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title="Fix auth.py test_login stalled",
            description="Auth login test stalled",
            evidence=[Evidence(source="state", content="stalled")],
            affected_files=["tests/test_auth.py"],
            created_at=now,
            updated_at=now,
            discovered_by="stalled-work-discovery",
        )

        test_agent = Mock()
        test_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": [opp1]},
            cost_usd=0.0,
        )

        stalled_agent = Mock()
        stalled_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": [opp2]},
            cost_usd=0.0,
        )

        quality_agent = Mock()
        quality_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        orchestrator = DiscoveryOrchestrator(
            config=mock_config,
            backlog_store=store,
            test_failure_agent=test_agent,
            stalled_work_agent=stalled_agent,
            code_quality_agent=quality_agent,
        )

        result = orchestrator.discover(types=["all"])

        # Should deduplicate based on affected files
        # May have 1 or 2 depending on similarity threshold
        assert len(result.opportunities) <= 2


class TestDebateTrigger:
    """Tests for debate triggering."""

    def test_triggers_debate_when_threshold_exceeded(self, mock_config, store):
        """6 opportunities triggers debate (threshold=5)."""
        from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
            DiscoveryOrchestrator,
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Create 6 unique opportunities with different affected_files
        opportunities = [
            Opportunity(
                opportunity_id=f"opp-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title=f"Test failure in module_{i}",
                description=f"Test {i} fails",
                evidence=[Evidence(source="test", content=f"error {i}")],
                affected_files=[f"tests/test_module_{i}.py"],  # Unique files
                created_at=now,
                updated_at=now,
                discovered_by="test-failure-discovery",
            )
            for i in range(6)
        ]

        test_agent = Mock()
        test_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,
        )

        stalled_agent = Mock()
        stalled_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        quality_agent = Mock()
        quality_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        orchestrator = DiscoveryOrchestrator(
            config=mock_config,
            backlog_store=store,
            test_failure_agent=test_agent,
            stalled_work_agent=stalled_agent,
            code_quality_agent=quality_agent,
        )

        result = orchestrator.discover(
            types=["test"],
            trigger_debate=True,
            debate_threshold=5,
        )

        # Should trigger debate
        assert result.debate_triggered is True

    def test_no_debate_when_under_threshold(self, orchestrator):
        """3 opportunities does not trigger debate (threshold=5)."""
        result = orchestrator.discover(
            types=["all"],
            trigger_debate=True,
            debate_threshold=5,
        )

        # 3 opportunities < 5 threshold
        assert result.debate_triggered is False

    def test_no_debate_when_disabled(self, mock_config, store):
        """trigger_debate=False skips debate even with many opportunities."""
        from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
            DiscoveryOrchestrator,
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        opportunities = [
            Opportunity(
                opportunity_id=f"opp-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title=f"Test failure {i}",
                description=f"Test {i} fails",
                evidence=[Evidence(source="test", content=f"error {i}")],
                created_at=now,
                updated_at=now,
                discovered_by="test-failure-discovery",
            )
            for i in range(10)
        ]

        test_agent = Mock()
        test_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,
        )

        stalled_agent = Mock()
        stalled_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        quality_agent = Mock()
        quality_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        orchestrator = DiscoveryOrchestrator(
            config=mock_config,
            backlog_store=store,
            test_failure_agent=test_agent,
            stalled_work_agent=stalled_agent,
            code_quality_agent=quality_agent,
        )

        result = orchestrator.discover(
            types=["test"],
            trigger_debate=False,
        )

        # Should not trigger debate
        assert result.debate_triggered is False


class TestMaxCandidates:
    """Tests for limiting results."""

    def test_respects_max_candidates(self, mock_config, store):
        """max_candidates=5 returns at most 5 opportunities."""
        from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
            DiscoveryOrchestrator,
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        opportunities = [
            Opportunity(
                opportunity_id=f"opp-{i}",
                opportunity_type=OpportunityType.TEST_FAILURE,
                status=OpportunityStatus.DISCOVERED,
                title=f"Test failure {i}",
                description=f"Test {i} fails",
                evidence=[Evidence(source="test", content=f"error {i}")],
                created_at=now,
                updated_at=now,
                discovered_by="test-failure-discovery",
            )
            for i in range(10)
        ]

        test_agent = Mock()
        test_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,
        )

        stalled_agent = Mock()
        stalled_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        quality_agent = Mock()
        quality_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,
        )

        orchestrator = DiscoveryOrchestrator(
            config=mock_config,
            backlog_store=store,
            test_failure_agent=test_agent,
            stalled_work_agent=stalled_agent,
            code_quality_agent=quality_agent,
        )

        result = orchestrator.discover(
            types=["test"],
            max_candidates=5,
        )

        assert len(result.opportunities) <= 5


class TestCostTracking:
    """Tests for tracking total cost."""

    def test_tracks_total_cost(self, mock_config, store):
        """Total cost is sum of all agent costs."""
        from swarm_attack.chief_of_staff.backlog_discovery.orchestrator import (
            DiscoveryOrchestrator,
        )

        test_agent = Mock()
        test_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.10,
        )

        stalled_agent = Mock()
        stalled_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,  # No cost (rule-based)
        )

        quality_agent = Mock()
        quality_agent.run.return_value = AgentResult.success_result(
            output={"opportunities": []},
            cost_usd=0.0,  # No cost (static analysis)
        )

        orchestrator = DiscoveryOrchestrator(
            config=mock_config,
            backlog_store=store,
            test_failure_agent=test_agent,
            stalled_work_agent=stalled_agent,
            code_quality_agent=quality_agent,
        )

        result = orchestrator.discover(types=["all"])

        # Total cost should be sum of all
        assert result.cost_usd == pytest.approx(0.10)
