"""
LLM-Adaptive Gate Agent for cross-language validation.

Uses Haiku model with tool access to validate artifacts between
agent handoffs. Automatically adapts to any programming language.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


GATE_SYSTEM_PROMPT = '''You are a validation gate agent in a multi-agent software development system.

Your job is to verify that artifacts from the previous agent exist and are valid before the next agent runs.

## Your Tools
- **Glob**: Find files matching patterns
- **Read**: Read file contents
- **Bash**: Run shell commands (syntax checks, test discovery)

## Your Task
Given context about what the previous agent should have produced, validate:
1. Files exist at expected locations (use Glob)
2. Files have valid syntax (use Bash with appropriate language command)
3. Test files contain actual test cases (use Bash for test discovery)

## Language Detection
Detect project type from these files:
- pubspec.yaml → Flutter/Dart
- package.json → Node.js (check for jest, mocha, vitest)
- pyproject.toml / setup.py / requirements.txt → Python
- go.mod → Go
- Cargo.toml → Rust
- build.gradle → Java/Kotlin

## Output Format
Always respond with valid JSON:
{
  "passed": true/false,
  "language": "python|flutter|typescript|go|rust|...",
  "artifacts": [
    {"path": "path/to/file", "exists": true, "valid_syntax": true}
  ],
  "test_count": 5,
  "errors": ["error message if any"],
  "commands_run": ["pytest --collect-only -q tests/..."]
}

## Rules
1. ALWAYS use tools to verify - never assume
2. If a file doesn't exist, report it clearly
3. If syntax check fails, include the error message
4. If test discovery finds 0 tests, that's a failure
5. Be concise - this is a gate, not a conversation
'''


@dataclass
class GateResult:
    """Result of a gate validation check."""

    passed: bool
    language: Optional[str] = None
    artifacts: Optional[list[dict]] = None
    test_count: int = 0
    errors: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    raw_output: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "language": self.language,
            "artifacts": self.artifacts,
            "test_count": self.test_count,
            "errors": self.errors,
            "commands_run": self.commands_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GateResult:
        """Create from dictionary."""
        return cls(
            passed=data.get("passed", False),
            language=data.get("language"),
            artifacts=data.get("artifacts"),
            test_count=data.get("test_count", 0),
            errors=data.get("errors", []),
            commands_run=data.get("commands_run", []),
            raw_output=data,
        )

    @classmethod
    def failure(cls, error: str) -> GateResult:
        """Create a failure result with a single error."""
        return cls(passed=False, errors=[error])


class GateAgent(BaseAgent):
    """
    LLM-powered validation gate that adapts to any language.

    Uses Haiku model for fast, cheap validation with limited tools
    (Glob, Read, Bash only). Validates artifacts between agent handoffs.
    """

    name = "gate"

    # Limited tools for gate validation
    GATE_TOOLS = ["Glob", "Read", "Bash"]

    # Max turns for gate (should be quick)
    MAX_GATE_TURNS = 5

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        gate_name: str = "validation_gate",
    ) -> None:
        """
        Initialize the Gate agent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            llm_runner: Optional Claude CLI runner (created if not provided).
            state_store: Optional state store for persistence.
            gate_name: Name for this gate (for logging).
        """
        super().__init__(config, logger, llm_runner, state_store)
        self.gate_name = gate_name

    def validate(self, context: dict[str, Any]) -> GateResult:
        """
        Run gate validation.

        Args:
            context: Dict with keys:
                - feature_id: str
                - issue_number: int
                - previous_agent: str (e.g., "coder")
                - expected_artifacts: list[str] (e.g., ["test file"])
                - project_root: str

        Returns:
            GateResult with validation outcome.
        """
        self._log("gate_validation_start", {
            "gate": self.gate_name,
            "feature_id": context.get("feature_id"),
            "issue_number": context.get("issue_number"),
        })

        try:
            # Build validation prompt
            prompt = self._build_validation_prompt(context)

            # Run LLM with limited tools
            result = self.llm.run(
                prompt,
                max_turns=self.MAX_GATE_TURNS,
                allowed_tools=self.GATE_TOOLS,
                working_dir=str(self.config.repo_root),
                timeout=60,  # Gates should be fast
            )

            # Track cost
            self._total_cost += result.cost_usd

            # Parse result
            gate_result = self._parse_llm_result(result)

            self._log("gate_validation_complete", {
                "gate": self.gate_name,
                "passed": gate_result.passed,
                "language": gate_result.language,
                "test_count": gate_result.test_count,
                "cost_usd": result.cost_usd,
            })

            return gate_result

        except Exception as e:
            self._log("gate_validation_error", {
                "gate": self.gate_name,
                "error": str(e),
            }, level="error")
            return GateResult.failure(f"Gate validation failed: {e}")

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute the agent's main task (implements BaseAgent interface).

        For GateAgent, this wraps validate() to return AgentResult.
        """
        gate_result = self.validate(context)

        if gate_result.passed:
            return AgentResult.success_result(
                output=gate_result.to_dict(),
                cost_usd=self._total_cost,
            )
        else:
            return AgentResult(
                success=False,
                output=gate_result.to_dict(),
                errors=gate_result.errors,
                cost_usd=self._total_cost,
            )

    def _build_validation_prompt(self, context: dict[str, Any]) -> str:
        """Build the validation task prompt."""
        feature_id = context.get("feature_id", "unknown")
        issue_number = context.get("issue_number", 0)
        previous_agent = context.get("previous_agent", "unknown")
        expected = context.get("expected_artifacts", ["artifacts"])
        project_root = context.get("project_root", ".")
        test_path = context.get("test_path", "")

        # Build the full prompt with system instructions and task
        prompt = f"""{GATE_SYSTEM_PROMPT}

---

## Validation Task

Validate artifacts from **{previous_agent}** for issue #{issue_number} of feature "{feature_id}".

**Project root:** {project_root}

**Expected artifacts:** {expected}

**Expected test file location:** {test_path if test_path else f"tests/generated/{feature_id}/test_issue_{issue_number}.*"}

### Steps to follow:
1. First, detect the project language (check for pubspec.yaml, package.json, pyproject.toml, etc. in project root)
2. Find test files matching the expected pattern using Glob
3. Read the test file to verify it has content
4. Run syntax check using the appropriate language command
5. Run test discovery to count tests
6. Return your findings as JSON

**Important:** Your final response MUST be valid JSON matching the output format above.
"""
        return prompt

    def _parse_llm_result(self, result: Any) -> GateResult:
        """Parse LLM result into GateResult."""
        # Check if LLM invocation succeeded
        if not result.success:
            return GateResult.failure(
                result.error or "LLM invocation failed"
            )

        # Extract text from result
        output_text = ""
        if hasattr(result, "output") and result.output:
            output_text = result.output
        elif hasattr(result, "result") and result.result:
            output_text = result.result

        if not output_text:
            return GateResult.failure("No output from gate validation")

        # Try to extract JSON from output
        try:
            # Look for JSON object in the output
            json_match = re.search(r'\{[\s\S]*\}', output_text)
            if json_match:
                parsed = json.loads(json_match.group())
                return GateResult.from_dict(parsed)
            else:
                # No JSON found - try to infer result
                return GateResult.failure(
                    f"No JSON found in gate output: {output_text[:200]}"
                )
        except json.JSONDecodeError as e:
            return GateResult.failure(
                f"Failed to parse gate output as JSON: {e}"
            )

    def _extract_text_from_result(self, result: Any) -> str:
        """Extract text content from Claude result."""
        # Handle ClaudeResult structure
        if hasattr(result, "result"):
            content = result.result
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Extract text from message content blocks
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))
                return "\n".join(texts)
        return str(result)
