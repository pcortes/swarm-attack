"""CodeQualityDiscoveryAgent for finding code quality issues.

This module provides:
- CodeQualityDiscoveryAgent: Discovers code quality issues via static analysis
- No LLM cost - uses radon, coverage.py, and file stats
- Gracefully degrades if tools unavailable
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    ActionabilityScore,
    Evidence,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class CodeQualityDiscoveryAgent(BaseAgent):
    """Discovers code quality issues via static analysis.

    No LLM cost - uses radon, coverage.py, and file stats.
    Gracefully degrades if tools unavailable.

    Detects:
    1. Complexity hotspots (radon cc > 10)
    2. Coverage gaps (files with <50% coverage)
    3. Oversized files (>500 lines)
    4. Missing tests (src/*.py without tests/*.py)

    Attributes:
        name: Agent identifier for logs and checkpoints.
        backlog_store: Store for persisting discovered opportunities.
    """

    name: str = "code-quality-discovery"

    # Thresholds
    COMPLEXITY_HIGH = 15
    COMPLEXITY_MEDIUM = 10
    COVERAGE_LOW = 0.30
    COVERAGE_MEDIUM = 0.50
    FILE_SIZE_THRESHOLD = 500

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: Optional[BacklogStore] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CodeQualityDiscoveryAgent.

        Args:
            config: SwarmConfig with paths and settings.
            backlog_store: Optional BacklogStore for persistence.
            **kwargs: Additional arguments passed to BaseAgent.
        """
        super().__init__(config=config, **kwargs)
        self.backlog_store = backlog_store

    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute code quality discovery.

        Discovers:
        1. Complexity hotspots (radon cc > 10)
        2. Coverage gaps (files with <50% coverage)
        3. Oversized files (>500 lines)
        4. Missing tests (src/*.py without tests/*.py)

        Gracefully skips if radon/coverage unavailable.

        Args:
            context: Context dict with optional keys:
                - max_opportunities: Limit on opportunities (default 10)

        Returns:
            AgentResult with list of Opportunity objects
        """
        max_opportunities = context.get("max_opportunities", 10)
        opportunities: list[Opportunity] = []

        # 1. Check complexity (if radon available)
        complexity_opps = self._check_complexity()
        opportunities.extend(complexity_opps)

        # 2. Check coverage (if coverage file exists)
        coverage_opps = self._check_coverage()
        opportunities.extend(coverage_opps)

        # 3. Check file sizes
        file_size_opps = self._check_file_size()
        opportunities.extend(file_size_opps)

        # 4. Check for missing tests
        missing_tests_opps = self._check_missing_tests()
        opportunities.extend(missing_tests_opps)

        # Limit results
        opportunities = opportunities[:max_opportunities]

        # Save to store
        if self.backlog_store:
            for opp in opportunities:
                self.backlog_store.save_opportunity(opp)

        self._log("discovery_complete", {
            "complexity_issues": len(complexity_opps),
            "coverage_gaps": len(coverage_opps),
            "oversized_files": len(file_size_opps),
            "missing_tests": len(missing_tests_opps),
            "opportunities_created": len(opportunities),
        })

        return AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,  # No LLM cost
        )

    def _get_project_root(self) -> Path:
        """Get project root path."""
        return Path.cwd()

    def _check_complexity(self) -> list[Opportunity]:
        """Use radon if available, else skip.

        Returns:
            List of COMPLEXITY opportunities.
        """
        try:
            from radon.complexity import cc_visit
        except ImportError:
            self._log("radon_unavailable", {}, level="warning")
            return []

        opportunities = []
        root = self._get_project_root()

        try:
            for py_file in root.glob("**/*.py"):
                # Skip test files and hidden directories
                if "test" in py_file.name.lower() or any(
                    part.startswith(".") for part in py_file.parts
                ):
                    continue

                try:
                    content = py_file.read_text()
                    blocks = cc_visit(content)

                    for block in blocks:
                        if block.complexity > self.COMPLEXITY_MEDIUM:
                            opp = self._create_complexity_opportunity(
                                file_path=str(py_file.relative_to(root)),
                                function_name=block.name,
                                complexity=block.complexity,
                                line_number=block.lineno,
                            )
                            opportunities.append(opp)
                except Exception:
                    continue
        except Exception as e:
            self._log("complexity_check_error", {"error": str(e)}, level="warning")

        return opportunities

    def _check_coverage(self) -> list[Opportunity]:
        """Parse .coverage or coverage.xml if available.

        Returns:
            List of COVERAGE_GAP opportunities.
        """
        opportunities = []
        root = self._get_project_root()

        # Try coverage.xml first
        coverage_xml = root / "coverage.xml"
        if coverage_xml.exists():
            try:
                tree = ET.parse(coverage_xml)
                root_elem = tree.getroot()

                for package in root_elem.findall(".//package"):
                    for cls in package.findall(".//class"):
                        filename = cls.get("filename", "")
                        line_rate = float(cls.get("line-rate", "1.0"))

                        if line_rate < self.COVERAGE_MEDIUM:
                            opp = self._create_coverage_opportunity(
                                file_path=filename,
                                coverage=line_rate,
                            )
                            opportunities.append(opp)
            except Exception as e:
                self._log("coverage_parse_error", {"error": str(e)}, level="warning")

        return opportunities

    def _check_file_size(self) -> list[Opportunity]:
        """Find files >500 lines.

        Returns:
            List of CODE_QUALITY opportunities for oversized files.
        """
        opportunities = []
        root = self._get_project_root()

        try:
            for py_file in root.glob("**/*.py"):
                # Skip hidden directories
                if any(part.startswith(".") for part in py_file.parts):
                    continue

                try:
                    content = py_file.read_text()
                    lines = content.count("\n") + 1

                    if lines > self.FILE_SIZE_THRESHOLD:
                        opp = self._create_file_size_opportunity(
                            file_path=str(py_file.relative_to(root)),
                            lines=lines,
                        )
                        opportunities.append(opp)
                except Exception:
                    continue
        except Exception as e:
            self._log("file_size_check_error", {"error": str(e)}, level="warning")

        return opportunities

    def _check_missing_tests(self) -> list[Opportunity]:
        """Find src files without corresponding test files.

        Returns:
            List of CODE_QUALITY opportunities for missing tests.
        """
        opportunities = []
        root = self._get_project_root()

        # Find source directories
        src_dirs = []
        for candidate in ["src", "lib", "app"]:
            src_dir = root / candidate
            if src_dir.exists():
                src_dirs.append(src_dir)

        # Also check root level .py files
        if not src_dirs:
            src_dirs.append(root)

        # Find test directories
        tests_dir = root / "tests"
        test_files: set[str] = set()

        if tests_dir.exists():
            for test_file in tests_dir.glob("**/*.py"):
                # Extract module name from test_module.py -> module
                name = test_file.stem
                if name.startswith("test_"):
                    test_files.add(name[5:])  # Remove test_ prefix

        # Check each source file
        for src_dir in src_dirs:
            for src_file in src_dir.glob("**/*.py"):
                # Skip __init__.py and test files
                if src_file.name.startswith("_") or "test" in src_file.name.lower():
                    continue

                module_name = src_file.stem

                if module_name not in test_files:
                    opp = self._create_missing_tests_opportunity(
                        file_path=str(src_file.relative_to(root)),
                        module_name=module_name,
                    )
                    opportunities.append(opp)

        return opportunities

    def _create_complexity_opportunity(
        self,
        file_path: str,
        function_name: str,
        complexity: int,
        line_number: int,
    ) -> Opportunity:
        """Create an opportunity for high complexity code.

        Args:
            file_path: Path to the file.
            function_name: Name of the complex function.
            complexity: Cyclomatic complexity score.
            line_number: Line number of the function.

        Returns:
            New COMPLEXITY Opportunity.
        """
        opp_id = self._generate_opportunity_id(f"complexity-{file_path}-{function_name}")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        title = f"Refactor complex function: {function_name} (CC={complexity})"
        description = (
            f"Function '{function_name}' in {file_path} has cyclomatic complexity "
            f"of {complexity}, which exceeds the threshold of {self.COMPLEXITY_MEDIUM}. "
            f"Consider breaking it into smaller functions."
        )

        evidence = [
            Evidence(
                source="radon",
                content=f"Cyclomatic complexity: {complexity}",
                file_path=file_path,
                line_number=line_number,
                timestamp=now,
            )
        ]

        actionability = self._calculate_complexity_actionability(complexity)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.COMPLEXITY,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            affected_files=[file_path],
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _create_coverage_opportunity(
        self,
        file_path: str,
        coverage: float,
    ) -> Opportunity:
        """Create an opportunity for low coverage.

        Args:
            file_path: Path to the file.
            coverage: Coverage ratio (0.0 to 1.0).

        Returns:
            New COVERAGE_GAP Opportunity.
        """
        opp_id = self._generate_opportunity_id(f"coverage-{file_path}")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        pct = coverage * 100
        title = f"Improve test coverage: {file_path} ({pct:.0f}%)"
        description = (
            f"File '{file_path}' has only {pct:.0f}% test coverage. "
            f"Consider adding tests to improve coverage above {self.COVERAGE_MEDIUM * 100:.0f}%."
        )

        evidence = [
            Evidence(
                source="coverage.xml",
                content=f"Line coverage: {pct:.0f}%",
                file_path=file_path,
                timestamp=now,
            )
        ]

        actionability = self._calculate_coverage_actionability(coverage)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.COVERAGE_GAP,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            affected_files=[file_path],
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _create_file_size_opportunity(
        self,
        file_path: str,
        lines: int,
    ) -> Opportunity:
        """Create an opportunity for an oversized file.

        Args:
            file_path: Path to the file.
            lines: Number of lines.

        Returns:
            New CODE_QUALITY Opportunity.
        """
        opp_id = self._generate_opportunity_id(f"filesize-{file_path}")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        title = f"Split large file: {file_path} ({lines} lines)"
        description = (
            f"File '{file_path}' has {lines} lines, exceeding the threshold of "
            f"{self.FILE_SIZE_THRESHOLD} lines. Consider splitting into smaller modules."
        )

        evidence = [
            Evidence(
                source="file_stats",
                content=f"File has {lines} lines (threshold: {self.FILE_SIZE_THRESHOLD})",
                file_path=file_path,
                timestamp=now,
            )
        ]

        actionability = self._calculate_file_size_actionability(lines)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            affected_files=[file_path],
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _create_missing_tests_opportunity(
        self,
        file_path: str,
        module_name: str,
    ) -> Opportunity:
        """Create an opportunity for a missing test file.

        Args:
            file_path: Path to the source file.
            module_name: Name of the module.

        Returns:
            New CODE_QUALITY Opportunity.
        """
        opp_id = self._generate_opportunity_id(f"missing-test-{file_path}")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        title = f"Add tests for: {module_name}"
        description = (
            f"Module '{file_path}' does not have a corresponding test file "
            f"(expected: tests/test_{module_name}.py). Consider adding tests."
        )

        evidence = [
            Evidence(
                source="file_analysis",
                content=f"No test file found for {module_name}",
                file_path=file_path,
                timestamp=now,
            )
        ]

        actionability = self._calculate_missing_tests_actionability()

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            affected_files=[file_path],
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _calculate_complexity_actionability(
        self, complexity: int
    ) -> ActionabilityScore:
        """Calculate actionability for complexity issues.

        Args:
            complexity: Cyclomatic complexity score.

        Returns:
            ActionabilityScore based on complexity level.
        """
        if complexity > self.COMPLEXITY_HIGH:
            return ActionabilityScore(
                clarity=0.9,
                evidence=0.9,
                effort="large",
                reversibility="full",
            )
        else:  # COMPLEXITY_MEDIUM to COMPLEXITY_HIGH
            return ActionabilityScore(
                clarity=0.7,
                evidence=0.8,
                effort="medium",
                reversibility="full",
            )

    def _calculate_coverage_actionability(
        self, coverage: float
    ) -> ActionabilityScore:
        """Calculate actionability for coverage issues.

        Args:
            coverage: Coverage ratio (0.0 to 1.0).

        Returns:
            ActionabilityScore based on coverage level.
        """
        if coverage < self.COVERAGE_LOW:
            clarity = 0.8
        else:
            clarity = 0.7

        return ActionabilityScore(
            clarity=clarity,
            evidence=0.9,
            effort="medium",
            reversibility="full",
        )

    def _calculate_file_size_actionability(
        self, lines: int
    ) -> ActionabilityScore:
        """Calculate actionability for oversized files.

        Args:
            lines: Number of lines.

        Returns:
            ActionabilityScore based on file size.
        """
        return ActionabilityScore(
            clarity=0.6,
            evidence=0.9,
            effort="large",
            reversibility="full",
        )

    def _calculate_missing_tests_actionability(self) -> ActionabilityScore:
        """Calculate actionability for missing tests.

        Returns:
            ActionabilityScore for adding tests.
        """
        return ActionabilityScore(
            clarity=0.8,
            evidence=0.7,
            effort="medium",
            reversibility="full",
        )

    def _generate_opportunity_id(self, seed: str) -> str:
        """Generate a unique opportunity ID.

        Args:
            seed: Seed string for the hash.

        Returns:
            Unique opportunity ID string.
        """
        hash_suffix = hashlib.md5(seed.encode()).hexdigest()[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"opp-cq-{timestamp}-{hash_suffix}"
