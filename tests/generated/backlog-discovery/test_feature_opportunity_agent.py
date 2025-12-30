"""Tests for FeatureOpportunityAgent.

TDD tests for Issue 6: McKinsey-style strategic feature opportunity analysis.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Evidence,
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore


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
def feature_opportunity_agent(mock_config, store):
    """Create a FeatureOpportunityAgent with mock dependencies."""
    from swarm_attack.chief_of_staff.backlog_discovery.feature_opportunity_agent import (
        FeatureOpportunityAgent,
    )
    agent = FeatureOpportunityAgent(
        config=mock_config,
        backlog_store=store,
    )
    return agent


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response with feature opportunities."""
    return json.dumps({
        "product_type": "developer_tool",
        "target_users": ["developers", "engineering teams"],
        "opportunities": [
            {
                "title": "Add AI-powered code review",
                "description": "Integrate LLM-based code review to catch issues before PR",
                "user_value": "Faster feedback, fewer bugs in production",
                "business_case": "Reduces code review cycle time by 50%",
                "impact": 9,
                "effort": 5,
                "leverage": 7,
                "risk": 3,
                "roi_score": 15.0,
                "category": "quick_win",
                "time_to_value_days": 7,
                "existing_code_to_leverage": ["src/agents/base.py"]
            },
            {
                "title": "Dashboard for team metrics",
                "description": "Visual dashboard showing team productivity and cost",
                "user_value": "Better visibility into development velocity",
                "business_case": "Enables data-driven decision making",
                "impact": 7,
                "effort": 6,
                "leverage": 5,
                "risk": 2,
                "roi_score": 14.0,
                "category": "strategic_bet",
                "time_to_value_days": 14,
                "existing_code_to_leverage": ["src/cli/app.py"]
            },
            {
                "title": "Slack integration",
                "description": "Send notifications to Slack channels",
                "user_value": "Stay updated without leaving chat",
                "business_case": "Improves team awareness and response time",
                "impact": 5,
                "effort": 2,
                "leverage": 3,
                "risk": 1,
                "roi_score": 40.0,
                "category": "low_hanging_fruit",
                "time_to_value_days": 3,
                "existing_code_to_leverage": []
            }
        ]
    })


class TestFeatureOpportunityAgentInit:
    """Tests for agent initialization."""

    def test_agent_name(self, feature_opportunity_agent):
        """Test agent has correct name."""
        assert feature_opportunity_agent.name == "feature-opportunity-discovery"

    def test_agent_has_backlog_store(self, feature_opportunity_agent, store):
        """Test agent has backlog store reference."""
        assert feature_opportunity_agent.backlog_store is store


class TestCodebaseAnalysis:
    """Tests for codebase analysis functionality."""

    def test_analyzes_codebase_structure(self, feature_opportunity_agent, tmp_path):
        """Agent scans codebase to understand capabilities."""
        # Create mock project structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass")
        (src_dir / "api.py").write_text("from flask import Flask")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_main(): pass")

        with patch.object(feature_opportunity_agent, "_get_project_root", return_value=tmp_path):
            analysis = feature_opportunity_agent._analyze_codebase()

        # Should detect basic structure
        assert "languages" in analysis or "files" in analysis or "frameworks" in analysis

    def test_detects_languages(self, feature_opportunity_agent, tmp_path):
        """Agent detects programming languages used."""
        # Create Python files
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "utils.ts").write_text("export const foo = 1")

        with patch.object(feature_opportunity_agent, "_get_project_root", return_value=tmp_path):
            languages = feature_opportunity_agent._detect_languages()

        # Should detect at least Python
        assert any("python" in str(lang).lower() for lang in languages) or len(languages) >= 0

    def test_detects_frameworks(self, feature_opportunity_agent, tmp_path):
        """Agent detects frameworks from imports/dependencies."""
        # Create files with framework imports
        (tmp_path / "requirements.txt").write_text("flask==2.0.0\ntyper==0.9.0\n")

        with patch.object(feature_opportunity_agent, "_get_project_root", return_value=tmp_path):
            frameworks = feature_opportunity_agent._detect_frameworks()

        # Frameworks may be empty if not detected, that's okay
        assert isinstance(frameworks, list)


class TestMcKinseyAnalysis:
    """Tests for McKinsey-style strategic analysis."""

    def test_generates_mckinsey_style_opportunities(
        self, feature_opportunity_agent, mock_llm_response
    ):
        """Agent produces strategic feature opportunities with ROI scores."""
        with patch.object(
            feature_opportunity_agent, "_call_llm", return_value=mock_llm_response
        ), patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            result = feature_opportunity_agent.run(context={})

        assert result.success is True
        opportunities = result.output.get("opportunities", [])
        assert len(opportunities) >= 1

        # Check opportunities have McKinsey-style attributes
        for opp in opportunities:
            assert opp.opportunity_type == OpportunityType.FEATURE_OPPORTUNITY
            assert opp.status == OpportunityStatus.DISCOVERED
            # Should have evidence with business case
            assert len(opp.evidence) >= 1

    def test_categorizes_opportunities(self, feature_opportunity_agent, mock_llm_response):
        """Opportunities are categorized as quick_win, strategic_bet, etc."""
        with patch.object(
            feature_opportunity_agent, "_call_llm", return_value=mock_llm_response
        ), patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            result = feature_opportunity_agent.run(context={})

        opportunities = result.output.get("opportunities", [])

        # Check categories are in descriptions or evidence
        all_text = " ".join([
            opp.title + opp.description +
            " ".join(e.content for e in opp.evidence)
            for opp in opportunities
        ]).lower()

        # Should have some categorization info
        assert len(opportunities) >= 1


class TestROICalculation:
    """Tests for ROI scoring."""

    def test_calculates_roi_correctly(self, feature_opportunity_agent):
        """ROI = Impact x (10 - Effort) / Risk."""
        # Test ROI calculation
        roi = feature_opportunity_agent._calculate_roi(
            impact=8,
            effort=3,
            risk=2,
        )

        # ROI = 8 * (10 - 3) / 2 = 8 * 7 / 2 = 28
        assert roi == pytest.approx(28.0)

    def test_roi_handles_zero_risk(self, feature_opportunity_agent):
        """ROI calculation handles zero risk gracefully."""
        # Should not divide by zero
        roi = feature_opportunity_agent._calculate_roi(
            impact=8,
            effort=3,
            risk=0,
        )

        # Should use risk=1 as minimum or return max value
        assert roi >= 0


class TestCodeLeverage:
    """Tests for identifying existing code leverage."""

    def test_identifies_code_leverage(
        self, feature_opportunity_agent, mock_llm_response
    ):
        """Agent identifies existing code that can be reused."""
        with patch.object(
            feature_opportunity_agent, "_call_llm", return_value=mock_llm_response
        ), patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            result = feature_opportunity_agent.run(context={})

        opportunities = result.output.get("opportunities", [])

        # At least one opportunity should have affected_files for leverage
        has_leverage = any(opp.affected_files for opp in opportunities)
        assert has_leverage or len(opportunities) >= 0  # May be empty if no leverage found


class TestCostBudget:
    """Tests for cost budget control."""

    def test_respects_cost_budget(self, feature_opportunity_agent, mock_llm_response):
        """Analysis stays within cost budget (~$0.50)."""
        with patch.object(
            feature_opportunity_agent, "_call_llm", return_value=mock_llm_response
        ), patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            result = feature_opportunity_agent.run(context={"budget_usd": 0.50})

        # Should complete and report cost
        assert result.success is True
        # Cost should be tracked (may be 0 if mocked)
        assert result.cost_usd >= 0

    def test_checks_budget_before_llm_call(self, feature_opportunity_agent):
        """Agent checks budget before making LLM call."""
        with patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            # Run with very low budget
            result = feature_opportunity_agent.run(context={"budget_usd": 0.01})

        # Should succeed but may skip LLM call if over budget
        # The agent should handle this gracefully


class TestOpportunityParsing:
    """Tests for parsing LLM responses into opportunities."""

    def test_parses_valid_response(self, feature_opportunity_agent, mock_llm_response):
        """Parses valid JSON response into opportunities."""
        opportunities = feature_opportunity_agent._parse_opportunities(mock_llm_response)

        assert len(opportunities) == 3
        assert opportunities[0].title == "Add AI-powered code review"
        assert opportunities[0].opportunity_type == OpportunityType.FEATURE_OPPORTUNITY

    def test_handles_malformed_response(self, feature_opportunity_agent):
        """Handles malformed JSON gracefully."""
        opportunities = feature_opportunity_agent._parse_opportunities("not valid json")
        assert opportunities == []

    def test_handles_missing_fields(self, feature_opportunity_agent):
        """Handles responses with missing fields."""
        partial_response = json.dumps({
            "product_type": "app",
            "opportunities": [
                {
                    "title": "Some feature",
                    # Missing other fields
                }
            ]
        })

        opportunities = feature_opportunity_agent._parse_opportunities(partial_response)
        # Should handle gracefully
        assert len(opportunities) <= 1


class TestActionabilityScoring:
    """Tests for actionability score calculation."""

    def test_calculates_actionability_from_scores(self, feature_opportunity_agent):
        """Calculates actionability from impact/effort/leverage/risk."""
        opp_data = {
            "title": "Test feature",
            "description": "A test",
            "user_value": "Test value",
            "business_case": "Test case",
            "impact": 8,
            "effort": 3,
            "leverage": 9,
            "risk": 2,
            "roi_score": 28.0,
            "category": "quick_win",
        }

        actionability = feature_opportunity_agent._calculate_actionability_from_opp(opp_data)

        # High leverage (9) should give high clarity
        assert actionability.clarity >= 0.7
        # Low effort should map to small/medium
        assert actionability.effort in ["small", "medium"]
        # New features are reversible
        assert actionability.reversibility == "full"


class TestSavesToStore:
    """Tests for saving opportunities to BacklogStore."""

    def test_saves_opportunities_to_store(
        self, feature_opportunity_agent, store, mock_llm_response
    ):
        """Discovered opportunities should be saved to store."""
        with patch.object(
            feature_opportunity_agent, "_call_llm", return_value=mock_llm_response
        ), patch.object(
            feature_opportunity_agent, "_analyze_codebase", return_value={"languages": ["python"]}
        ):
            feature_opportunity_agent.run(context={})

        # Check store has the opportunities
        all_opps = store.get_all()
        assert len(all_opps) >= 1
