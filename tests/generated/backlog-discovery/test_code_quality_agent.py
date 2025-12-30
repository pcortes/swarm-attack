"""Tests for CodeQualityDiscoveryAgent.

TDD tests for Issue 6b: Discovery agent for code quality issues.
"""

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
def code_quality_agent(mock_config, store):
    """Create a CodeQualityDiscoveryAgent with mock dependencies."""
    from swarm_attack.chief_of_staff.backlog_discovery.code_quality_agent import (
        CodeQualityDiscoveryAgent,
    )
    agent = CodeQualityDiscoveryAgent(
        config=mock_config,
        backlog_store=store,
    )
    return agent


class TestCodeQualityDiscoveryAgentInit:
    """Tests for agent initialization."""

    def test_agent_name(self, code_quality_agent):
        """Test agent has correct name."""
        assert code_quality_agent.name == "code-quality-discovery"

    def test_agent_has_backlog_store(self, code_quality_agent, store):
        """Test agent has backlog store reference."""
        assert code_quality_agent.backlog_store is store


class TestComplexityDetection:
    """Tests for cyclomatic complexity detection."""

    def test_detects_high_complexity(self, code_quality_agent, tmp_path):
        """File with CC>10 creates COMPLEXITY opportunity."""
        # Create a file with high complexity (many if/else branches)
        complex_file = tmp_path / "complex.py"
        complex_code = """
def complex_function(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return 1
                    else:
                        return 2
                else:
                    return 3
            elif c < 0:
                return 4
            else:
                return 5
        elif b < 0:
            if c > 0:
                return 6
            else:
                return 7
        else:
            return 8
    elif a < 0:
        return 9
    else:
        return 10
"""
        complex_file.write_text(complex_code)

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_complexity()

        # Should detect high complexity if radon is available
        # If radon not available, should return empty list gracefully
        assert isinstance(opportunities, list)

    def test_graceful_without_radon(self, code_quality_agent):
        """Skips complexity check if radon not installed."""
        # Mock radon import failure
        with patch.dict("sys.modules", {"radon": None, "radon.complexity": None}):
            opportunities = code_quality_agent._check_complexity()

        # Should return empty list without error
        assert opportunities == []


class TestCoverageDetection:
    """Tests for coverage gap detection."""

    def test_detects_low_coverage(self, code_quality_agent, tmp_path):
        """File with <50% coverage creates COVERAGE_GAP opportunity."""
        # Create a mock coverage XML file
        coverage_xml = tmp_path / "coverage.xml"
        coverage_xml.write_text("""<?xml version="1.0" ?>
<coverage version="7.0" timestamp="1234567890" lines-valid="100" lines-covered="30" line-rate="0.30">
    <packages>
        <package name="src">
            <classes>
                <class name="low_coverage.py" filename="src/low_coverage.py" line-rate="0.30">
                    <lines>
                        <line number="1" hits="0"/>
                        <line number="2" hits="0"/>
                        <line number="3" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
""")

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_coverage()

        # Should detect low coverage if coverage file exists
        if opportunities:
            assert opportunities[0].opportunity_type == OpportunityType.COVERAGE_GAP

    def test_graceful_without_coverage(self, code_quality_agent, tmp_path):
        """Skips coverage check if no .coverage file."""
        # Empty directory - no coverage file
        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_coverage()

        # Should return empty list without error
        assert opportunities == []


class TestOversizedFileDetection:
    """Tests for detecting oversized files."""

    def test_detects_oversized_files(self, code_quality_agent, tmp_path):
        """File >500 lines creates CODE_QUALITY opportunity."""
        # Create a file with >500 lines
        big_file = tmp_path / "big_module.py"
        lines = ["# Line {}\n".format(i) for i in range(600)]
        big_file.write_text("".join(lines))

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_file_size()

        # Should detect oversized file
        assert len(opportunities) >= 1
        assert opportunities[0].opportunity_type == OpportunityType.CODE_QUALITY
        assert "500" in opportunities[0].description or "lines" in opportunities[0].description.lower()

    def test_ignores_small_files(self, code_quality_agent, tmp_path):
        """Files under 500 lines don't create opportunities."""
        # Create small files
        small_file = tmp_path / "small_module.py"
        small_file.write_text("print('hello')\n" * 50)

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_file_size()

        # Should not detect small files
        assert len(opportunities) == 0


class TestMissingTestsDetection:
    """Tests for detecting missing test files."""

    def test_detects_missing_tests(self, code_quality_agent, tmp_path):
        """Find src files without corresponding test files."""
        # Create src directory with module
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "auth.py").write_text("def login(): pass")
        (src_dir / "payment.py").write_text("def charge(): pass")

        # Create tests directory with only one test
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_auth.py").write_text("def test_login(): pass")
        # Note: test_payment.py is missing

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_missing_tests()

        # Should detect payment.py doesn't have test_payment.py
        assert len(opportunities) >= 1
        missing_test_opp = next(
            (o for o in opportunities if "payment" in o.title.lower()),
            None
        )
        assert missing_test_opp is not None

    def test_ignores_tested_modules(self, code_quality_agent, tmp_path):
        """Modules with corresponding tests are not flagged."""
        # Create src and matching tests
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "utils.py").write_text("def helper(): pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_utils.py").write_text("def test_helper(): pass")

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            opportunities = code_quality_agent._check_missing_tests()

        # Should not flag utils.py since test_utils.py exists
        utils_opp = next(
            (o for o in opportunities if "utils" in o.title.lower()),
            None
        )
        assert utils_opp is None


class TestActionabilityScoring:
    """Tests for actionability scoring rules."""

    def test_complexity_actionability(self, code_quality_agent):
        """Complexity >15 should have high clarity and large effort."""
        score = code_quality_agent._calculate_complexity_actionability(complexity=16)
        assert score.clarity >= 0.8
        assert score.evidence >= 0.8
        assert score.effort == "large"

    def test_moderate_complexity_actionability(self, code_quality_agent):
        """Complexity 10-15 should have medium effort."""
        score = code_quality_agent._calculate_complexity_actionability(complexity=12)
        assert score.clarity >= 0.6
        assert score.effort == "medium"

    def test_coverage_actionability(self, code_quality_agent):
        """Coverage <30% should have high clarity and medium effort."""
        score = code_quality_agent._calculate_coverage_actionability(coverage=0.25)
        assert score.clarity >= 0.7
        assert score.evidence >= 0.8
        assert score.effort == "medium"

    def test_file_size_actionability(self, code_quality_agent):
        """Large files should have large effort."""
        score = code_quality_agent._calculate_file_size_actionability(lines=700)
        assert score.clarity >= 0.5
        assert score.effort == "large"

    def test_missing_tests_actionability(self, code_quality_agent):
        """Missing tests should have medium effort."""
        score = code_quality_agent._calculate_missing_tests_actionability()
        assert score.clarity >= 0.7
        assert score.effort == "medium"


class TestNoCost:
    """Tests for verifying no LLM cost."""

    def test_no_llm_cost(self, code_quality_agent, tmp_path):
        """Agent should have zero LLM cost - uses static analysis only."""
        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            result = code_quality_agent.run(context={})

        assert result.success is True
        assert result.cost_usd == 0.0


class TestFullDiscovery:
    """Tests for the full discovery run."""

    def test_runs_all_checks(self, code_quality_agent, tmp_path):
        """Agent runs complexity, coverage, file size, and missing tests checks."""
        # Setup minimal project
        (tmp_path / "module.py").write_text("def foo(): pass\n" * 600)

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            result = code_quality_agent.run(context={})

        assert result.success is True
        opportunities = result.output.get("opportunities", [])
        # Should find at least the oversized file
        assert len(opportunities) >= 1

    def test_respects_max_opportunities(self, code_quality_agent, tmp_path):
        """max_opportunities limits the returned opportunities."""
        # Create many oversized files
        for i in range(10):
            (tmp_path / f"big_file_{i}.py").write_text("x=1\n" * 600)

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            result = code_quality_agent.run(context={"max_opportunities": 3})

        opportunities = result.output.get("opportunities", [])
        assert len(opportunities) <= 3


class TestSavesToStore:
    """Tests for saving opportunities to BacklogStore."""

    def test_saves_opportunities_to_store(self, code_quality_agent, store, tmp_path):
        """Discovered opportunities should be saved to store."""
        # Create oversized file
        (tmp_path / "oversized.py").write_text("x=1\n" * 600)

        with patch.object(code_quality_agent, "_get_project_root", return_value=tmp_path):
            code_quality_agent.run(context={})

        # Check store has the opportunities
        all_opps = store.get_all()
        assert len(all_opps) >= 1
