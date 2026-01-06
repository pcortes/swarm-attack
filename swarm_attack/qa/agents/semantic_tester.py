# swarm_attack/qa/agents/semantic_tester.py
"""SemanticTesterAgent - Claude Code CLI-powered semantic QA testing.

Uses Claude Code CLI with Opus 4.5 to perform human-like semantic testing.
Zero API cost (Max plan), maximum intelligence, real execution.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack.agents.base import BaseAgent, AgentResult

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.state_store import StateStore


class SemanticScope(Enum):
    """Scope of semantic testing."""

    CHANGES_ONLY = "changes_only"
    AFFECTED = "affected"
    FULL_SYSTEM = "full_system"


class SemanticVerdict(Enum):
    """Verdict from semantic testing."""

    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


@dataclass
class Evidence:
    """Evidence from a test execution."""

    description: str
    source: str
    confidence: float
    details: dict = field(default_factory=dict)


@dataclass
class SemanticIssue:
    """Issue found during semantic testing."""

    severity: str
    description: str
    location: str
    suggestion: str


@dataclass
class SemanticTestResult:
    """Result of semantic testing."""

    verdict: SemanticVerdict
    evidence: list[Evidence] = field(default_factory=list)
    issues: list[SemanticIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            "verdict": self.verdict.value,
            "evidence": [
                {
                    "description": e.description,
                    "source": e.source,
                    "confidence": e.confidence,
                    "details": e.details,
                }
                for e in self.evidence
            ],
            "issues": [
                {
                    "severity": i.severity,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "recommendations": self.recommendations,
        }


class SemanticTesterAgent(BaseAgent):
    """Claude Code CLI-powered semantic QA agent.

    This agent uses the Claude Code CLI to perform human-like semantic testing
    of code changes. It leverages Opus 4.5's reasoning capabilities to:

    - Understand the semantic intent of code changes
    - Generate and execute meaningful test scenarios
    - Validate behavior matches expectations
    - Provide actionable feedback on issues found

    The agent operates with zero API cost on the Claude Max plan, making it
    ideal for comprehensive QA coverage.
    """

    name: str = "semantic_tester"
    skill_name: str = "semantic-test"

    # Claude CLI configuration
    CLAUDE_BINARY: str = "claude"
    MODEL: str = "opus"
    MAX_TURNS: int = 50
    TIMEOUT_SECONDS: int = 600
    ALLOWED_TOOLS: list[str] = ["Bash", "Read", "Glob", "Grep", "Write"]

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the SemanticTesterAgent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            llm_runner: Optional Claude CLI runner (not used, kept for interface).
            state_store: Optional state store for persistence.
        """
        super().__init__(config, logger, llm_runner, state_store)
        self.skill_prompt = self._load_skill_prompt()

    def _load_skill_prompt(self) -> str:
        """Load skill prompt from SKILL.md or return default.

        Looks for the skill prompt at:
        .claude/skills/{skill_name}/SKILL.md

        If the file contains YAML frontmatter, it is stripped before returning.

        Returns:
            The skill prompt content.
        """
        skill_path = (
            Path(self.config.repo_root)
            / ".claude"
            / "skills"
            / self.skill_name
            / "SKILL.md"
        )

        if skill_path.exists():
            content = skill_path.read_text()
            # Strip YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return content

        return self._default_skill_prompt()

    def _default_skill_prompt(self) -> str:
        """Default skill prompt for semantic testing.

        Returns:
            A comprehensive default prompt for semantic testing.
        """
        return """You are a senior QA engineer testing code changes.

TEST LIKE A HUMAN WOULD:
- Run real commands to validate behavior
- Examine actual outputs and responses
- Validate semantically - does the code do what it claims?
- Think about edge cases a human tester would catch
- Consider integration points and side effects

TESTING APPROACH:
1. Understand the changes and their intent
2. Identify key behaviors to validate
3. Execute tests using available tools
4. Collect evidence of pass/fail
5. Provide actionable recommendations

Always output results as JSON with: verdict, evidence, issues, recommendations."""

    def run(self, context: dict[str, Any]) -> AgentResult:
        """Run semantic testing on provided changes.

        Args:
            context: Dictionary containing:
                - changes: Description of changes to test (REQUIRED)
                - expected_behavior: Expected behavior description
                - test_scope: SemanticScope enum or string value
                - test_scenarios: List of specific scenarios to test
                - project_root: Optional override for project root

        Returns:
            AgentResult with SemanticTestResult data.
        """
        # Validate required fields
        if not context.get("changes"):
            return AgentResult(
                success=False,
                output=None,
                errors=["Required field 'changes' is missing or empty"],
            )

        # Support both 'scope' and 'test_scope' keys (scope takes precedence)
        scope_value = context.get("scope") or context.get("test_scope", SemanticScope.CHANGES_ONLY)
        self._log(
            "semantic_test_start",
            {
                "scope": scope_value.value
                if isinstance(scope_value, SemanticScope)
                else scope_value,
                "has_scenarios": bool(context.get("test_scenarios")),
            },
        )

        try:
            result = self._execute_semantic_test(context)
            success = result.verdict in (SemanticVerdict.PASS, SemanticVerdict.PARTIAL)
            errors = [i.description for i in result.issues if i.severity == "critical"]

            self._log(
                "semantic_test_complete",
                {
                    "verdict": result.verdict.value,
                    "issue_count": len(result.issues),
                    "evidence_count": len(result.evidence),
                },
            )

            return AgentResult(
                success=success,
                output=result.to_dict(),
                errors=errors,
                cost_usd=0.0,  # Free on Max plan
            )
        except Exception as e:
            self._log("semantic_test_error", {"error": str(e)}, level="error")
            return AgentResult(
                success=False,
                output=None,
                errors=[f"Unexpected error: {str(e)}"],
            )

    def _execute_semantic_test(self, context: dict) -> SemanticTestResult:
        """Execute semantic test via Claude Code CLI.

        Args:
            context: Test context with changes and configuration.

        Returns:
            SemanticTestResult with verdict, evidence, and issues.
        """
        prompt = self._build_test_prompt(context)

        cmd = [
            self.CLAUDE_BINARY,
            "--print",
            "--model",
            self.MODEL,
            "--max-turns",
            str(self.MAX_TURNS),
            "--allowedTools",
            ",".join(self.ALLOWED_TOOLS),
            "-p",
            prompt,
        ]

        project_root = context.get("project_root", self.config.repo_root)

        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SECONDS,
            )

            if result.returncode != 0:
                return SemanticTestResult(
                    verdict=SemanticVerdict.FAIL,
                    issues=[
                        SemanticIssue(
                            severity="critical",
                            description=f"CLI failed: {result.stderr}",
                            location="",
                            suggestion="Check CLI setup and authentication",
                        )
                    ],
                )

            return self._parse_test_output(result.stdout)

        except subprocess.TimeoutExpired:
            return SemanticTestResult(
                verdict=SemanticVerdict.FAIL,
                issues=[
                    SemanticIssue(
                        severity="critical",
                        description="Test timed out",
                        location="",
                        suggestion="Reduce test scope or increase timeout",
                    )
                ],
                recommendations=["Timeout occurred - consider reducing scope"],
            )

    def _build_test_prompt(
        self, context: dict, include_skill: bool = True
    ) -> str:
        """Build prompt for Claude CLI.

        Args:
            context: Test context with changes and configuration.
            include_skill: Whether to include the skill prompt.

        Returns:
            Complete prompt string for Claude CLI.
        """
        changes = context.get("changes", "")
        expected = context.get("expected_behavior", "")
        # Support both 'scope' and 'test_scope' keys (scope takes precedence)
        scope = context.get("scope") or context.get("test_scope", SemanticScope.CHANGES_ONLY)
        scenarios = context.get("test_scenarios", [])

        skill_section = self.skill_prompt if include_skill else ""
        scope_value = scope.value if isinstance(scope, SemanticScope) else scope

        scenarios_text = (
            chr(10).join(f"- {s}" for s in scenarios)
            if scenarios
            else "Use your judgment"
        )

        return f"""{skill_section}

## CHANGES TO TEST
{changes}

## EXPECTED BEHAVIOR
{expected}

## TEST SCOPE
{scope_value}

## SCENARIOS
{scenarios_text}

## OUTPUT FORMAT
Provide results as JSON:
```json
{{
    "verdict": "PASS" | "FAIL" | "PARTIAL",
    "evidence": [{{"description": "...", "source": "...", "confidence": 0.95}}],
    "issues": [{{"severity": "critical|major|minor", "description": "...", "location": "...", "suggestion": "..."}}],
    "recommendations": ["..."]
}}
```
BEGIN TESTING."""

    def _parse_test_output(self, output: str) -> SemanticTestResult:
        """Parse Claude CLI output into SemanticTestResult.

        Attempts to extract JSON from the output in multiple ways:
        1. Markdown JSON code block (```json ... ```)
        2. Raw JSON object at the end of output

        Args:
            output: Raw output from Claude CLI.

        Returns:
            Parsed SemanticTestResult.
        """
        try:
            # Try markdown JSON block first
            json_match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # Try raw JSON - find the last JSON object
                start = output.rfind("{")
                end = output.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(output[start:end])
                else:
                    return SemanticTestResult(
                        verdict=SemanticVerdict.PARTIAL,
                        recommendations=["Could not parse structured output"],
                    )

            verdict = SemanticVerdict(data.get("verdict", "PARTIAL"))
            evidence = [Evidence(**e) for e in data.get("evidence", [])]
            issues = [SemanticIssue(**i) for i in data.get("issues", [])]
            recommendations = data.get("recommendations", [])

            return SemanticTestResult(
                verdict=verdict,
                evidence=evidence,
                issues=issues,
                recommendations=recommendations,
            )

        except (json.JSONDecodeError, ValueError) as e:
            return SemanticTestResult(
                verdict=SemanticVerdict.PARTIAL,
                recommendations=[f"JSON parsing failed: {e}"],
            )

    def format_results(self, result: SemanticTestResult) -> str:
        """Format semantic test results for CLI display with Rich.

        Creates a beautifully formatted output with:
        - Color-coded verdict header (green=PASS, red=FAIL, yellow=PARTIAL)
        - Evidence table with confidence styling
        - Issues panels with severity-based colors
        - Recommendations list

        Args:
            result: The SemanticTestResult to format.

        Returns:
            Formatted string suitable for terminal display.
        """
        console = Console(record=True, force_terminal=True)

        # Verdict header with appropriate color
        verdict_colors = {
            SemanticVerdict.PASS: "green",
            SemanticVerdict.FAIL: "red",
            SemanticVerdict.PARTIAL: "yellow",
        }
        verdict_color = verdict_colors.get(result.verdict, "white")

        console.print(Panel(
            Text(result.verdict.value, style=f"bold {verdict_color}"),
            title="Semantic Test Result",
            border_style=verdict_color,
        ))

        # Evidence table
        if result.evidence:
            console.print()
            table = Table(title="Evidence", show_header=True, header_style="bold")
            table.add_column("Source", style="cyan")
            table.add_column("Description")
            table.add_column("Confidence", justify="right")

            for e in result.evidence:
                # Color confidence based on value
                if e.confidence > 0.8:
                    conf_color = "green"
                elif e.confidence > 0.5:
                    conf_color = "yellow"
                else:
                    conf_color = "red"
                conf_text = Text(f"{e.confidence:.0%}", style=conf_color)
                table.add_row(e.source, e.description, conf_text)

            console.print(table)

        # Issues with severity colors
        if result.issues:
            console.print()
            severity_colors = {
                "critical": "red",
                "major": "yellow",
                "minor": "blue",
            }

            for issue in result.issues:
                sev_color = severity_colors.get(issue.severity, "white")
                issue_content = (
                    f"{issue.description}\n\n"
                    f"[dim]Location:[/dim] {issue.location}\n"
                    f"[dim]Suggestion:[/dim] {issue.suggestion}"
                )
                console.print(Panel(
                    issue_content,
                    title=f"[{sev_color}]{issue.severity.upper()}[/]",
                    border_style=sev_color,
                ))

        # Recommendations
        if result.recommendations:
            console.print()
            console.print("[bold]Recommendations:[/bold]")
            for rec in result.recommendations:
                console.print(f"  - {rec}")

        return console.export_text()
