"""Mutation Test Gate - requires minimum mutation score for test adequacy.

This module provides a quality gate that ensures test suites have sufficient
mutation testing coverage. It integrates with mutmut (or similar tools) to
run mutation testing and enforce configurable score thresholds.

Requirements:
- Minimum 60% mutation score to pass (configurable)
- Integration with mutmut or similar tool
- Configurable thresholds per project
- Detailed mutation survival reports
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
import json
import subprocess


@dataclass
class MutantInfo:
    """Information about a single mutant."""
    id: int
    file: str
    line: int
    description: str
    status: str

    @classmethod
    def from_dict(cls, data: dict) -> "MutantInfo":
        """Create MutantInfo from dictionary."""
        return cls(
            id=data.get("id", 0),
            file=data.get("file", ""),
            line=data.get("line", 0),
            description=data.get("description", ""),
            status=data.get("status", "")
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class MutationTestResult:
    """Result of a mutation testing run."""
    passed: bool
    score: float
    total_mutants: int
    killed: int
    survived: int
    timeout: int
    suspicious: int
    skipped: int
    min_score_required: float
    survived_mutants: list[MutantInfo]
    report_path: Optional[str]
    error: Optional[str]

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "passed": self.passed,
            "score": self.score,
            "total_mutants": self.total_mutants,
            "killed": self.killed,
            "survived": self.survived,
            "timeout": self.timeout,
            "suspicious": self.suspicious,
            "skipped": self.skipped,
            "min_score_required": self.min_score_required,
            "survived_mutants": [m.to_dict() for m in self.survived_mutants],
            "report_path": self.report_path,
            "error": self.error
        }


class MutationTestGate:
    """Quality gate that requires minimum mutation testing score.

    This gate runs mutation testing on specified source code and verifies
    that the mutation score meets a minimum threshold. It integrates with
    mutmut to generate and test mutants.

    Attributes:
        min_score: Minimum mutation score required to pass (0-100)
        tool: Mutation testing tool to use (default: "mutmut")
        timeout_seconds: Maximum time for mutation testing run
        report_dir: Directory to save mutation reports
    """

    def __init__(
        self,
        min_score: float = 60.0,
        tool: str = "mutmut",
        timeout_seconds: int = 300,
        report_dir: Optional[Path] = None
    ):
        """Initialize the mutation test gate.

        Args:
            min_score: Minimum score (0-100) required to pass
            tool: Mutation testing tool name
            timeout_seconds: Timeout for mutation testing run
            report_dir: Directory to save reports (optional)
        """
        self.min_score = min_score
        self.tool = tool
        self.timeout_seconds = timeout_seconds
        self.report_dir = Path(report_dir) if report_dir else None

    @classmethod
    def from_config(cls, config: Any) -> "MutationTestGate":
        """Create gate from configuration object.

        Args:
            config: Configuration object with mutation_testing settings

        Returns:
            Configured MutationTestGate instance
        """
        mt_config = getattr(config, "mutation_testing", None)
        if mt_config:
            return cls(
                min_score=getattr(mt_config, "min_score", 60.0),
                tool=getattr(mt_config, "tool", "mutmut"),
                timeout_seconds=getattr(mt_config, "timeout_seconds", 300)
            )
        return cls()

    def run(
        self,
        target_path: str,
        test_path: Optional[str] = None
    ) -> MutationTestResult:
        """Run mutation testing and check if score meets threshold.

        Args:
            target_path: Path to source code to mutate
            test_path: Optional path to specific tests to run

        Returns:
            MutationTestResult with pass/fail status and details
        """
        try:
            # Run the mutation testing tool
            mutation_data = self._run_mutmut(target_path, test_path)

            # Calculate score
            total = mutation_data.get("total_mutants", 0)
            killed = mutation_data.get("killed", 0)

            if total == 0:
                # No mutants - consider this a pass
                score = 100.0
            else:
                score = round((killed / total) * 100, 2)

            # Parse survived mutants
            survived_mutants = [
                MutantInfo.from_dict(m)
                for m in mutation_data.get("survived_mutants", [])
            ]

            # Determine if gate passes
            passed = score >= self.min_score

            # Generate report if report_dir is set
            report_path = None
            if self.report_dir:
                report_path = self._generate_report(
                    score=score,
                    total=total,
                    killed=killed,
                    survived=mutation_data.get("survived", 0),
                    timeout=mutation_data.get("timeout", 0),
                    suspicious=mutation_data.get("suspicious", 0),
                    skipped=mutation_data.get("skipped", 0),
                    survived_mutants=survived_mutants,
                    passed=passed
                )

            return MutationTestResult(
                passed=passed,
                score=score,
                total_mutants=total,
                killed=killed,
                survived=mutation_data.get("survived", 0),
                timeout=mutation_data.get("timeout", 0),
                suspicious=mutation_data.get("suspicious", 0),
                skipped=mutation_data.get("skipped", 0),
                min_score_required=self.min_score,
                survived_mutants=survived_mutants,
                report_path=report_path,
                error=None
            )

        except subprocess.TimeoutExpired:
            return MutationTestResult(
                passed=False,
                score=0.0,
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                suspicious=0,
                skipped=0,
                min_score_required=self.min_score,
                survived_mutants=[],
                report_path=None,
                error=f"Mutation testing timeout after {self.timeout_seconds} seconds"
            )

        except FileNotFoundError as e:
            return MutationTestResult(
                passed=False,
                score=0.0,
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                suspicious=0,
                skipped=0,
                min_score_required=self.min_score,
                survived_mutants=[],
                report_path=None,
                error=f"Mutation tool not found: {e}"
            )

        except json.JSONDecodeError as e:
            return MutationTestResult(
                passed=False,
                score=0.0,
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                suspicious=0,
                skipped=0,
                min_score_required=self.min_score,
                survived_mutants=[],
                report_path=None,
                error=f"Invalid JSON output from mutation tool: {e}"
            )

        except Exception as e:
            return MutationTestResult(
                passed=False,
                score=0.0,
                total_mutants=0,
                killed=0,
                survived=0,
                timeout=0,
                suspicious=0,
                skipped=0,
                min_score_required=self.min_score,
                survived_mutants=[],
                report_path=None,
                error=str(e)
            )

    def _run_mutmut(
        self,
        target_path: str,
        test_path: Optional[str] = None
    ) -> dict:
        """Run mutmut and parse results.

        Args:
            target_path: Path to source code to mutate
            test_path: Optional path to specific tests

        Returns:
            Dictionary with mutation testing results
        """
        # Build mutmut command
        cmd = [
            self.tool,
            "run",
            "--paths-to-mutate", target_path,
            "--runner", "pytest",
            "--json-report"
        ]

        if test_path:
            cmd.extend(["--tests-dir", test_path])

        # Run mutmut
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds
        )

        # Check for errors
        if result.returncode != 0 and not result.stdout:
            raise RuntimeError(f"Mutation testing failed: {result.stderr}")

        # Parse JSON output
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Empty output from mutation tool")

        return json.loads(output)

    def _generate_report(
        self,
        score: float,
        total: int,
        killed: int,
        survived: int,
        timeout: int,
        suspicious: int,
        skipped: int,
        survived_mutants: list[MutantInfo],
        passed: bool
    ) -> str:
        """Generate a mutation testing report.

        Args:
            score: Mutation score percentage
            total: Total number of mutants
            killed: Number of killed mutants
            survived: Number of survived mutants
            timeout: Number of timed out mutants
            suspicious: Number of suspicious mutants
            skipped: Number of skipped mutants
            survived_mutants: List of survived mutant details
            passed: Whether the gate passed

        Returns:
            Path to the generated report file
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"mutation_report_{timestamp}.json"

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "score": score,
            "min_score_required": self.min_score,
            "summary": {
                "total_mutants": total,
                "killed": killed,
                "survived": survived,
                "timeout": timeout,
                "suspicious": suspicious,
                "skipped": skipped
            },
            "survived_mutants": [
                {
                    "id": m.id,
                    "file": m.file,
                    "line": m.line,
                    "description": m.description,
                    "status": m.status
                }
                for m in survived_mutants
            ]
        }

        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        return str(report_path)
