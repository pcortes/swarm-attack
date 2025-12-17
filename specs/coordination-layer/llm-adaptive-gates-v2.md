# Expert Debate v2: LLM-Adaptive Coordination Layer

## Context Update (December 2025)

The original spec (expert-debate-and-plan.md) was written with assumptions about LLM limitations that no longer hold:

| Original Assumption | Current Reality (Dec 2025) |
|---------------------|---------------------------|
| LLMs hallucinate frequently | Opus 4.5 / GPT-5.2 Pro have near-zero hallucination with tool grounding |
| LLM validation is expensive | Haiku-class models cost <$0.001 per gate check |
| LLMs can't reliably parse varied outputs | Modern LLMs excel at structured output parsing |
| Deterministic > LLM for reliability | Tool-grounded LLMs match deterministic reliability |

## Expert Panel: Reconsidering the Architecture

---

### Expert 1: LLM Orchestration Specialist

**Position:** Replace deterministic gates entirely with LLM-adaptive validation.

**Rationale:**
```
Old approach:
  if project == "python":
      run(["pytest", "--collect-only"])
  elif project == "flutter":
      run(["flutter", "test", "--reporter", "expanded"])
  elif project == "typescript":
      run(["jest", "--listTests"])
  # ... endless if/else for each language

New approach:
  llm.validate(
      context="Test-writer just completed. Validate artifacts exist and are syntactically correct.",
      tools=[Read, Bash, Glob],
      constraints="Return structured GateResult"
  )
```

**Key Insight:** The LLM already knows:
- How to detect project type (pubspec.yaml = Flutter, package.json = Node, etc.)
- The appropriate validation commands for each ecosystem
- How to parse varied output formats
- Edge cases humans forget to handle

**Proposed Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│                    GATE AGENT                           │
│  Model: claude-haiku (fast, cheap, reliable)            │
│  Tools: Read, Bash, Glob                                │
│  System Prompt: "You are a validation gate..."          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Input Context:                                         │
│  - feature_id, issue_number                             │
│  - previous_agent: "test-writer"                        │
│  - expected_artifacts: ["test file"]                    │
│  - project_root: "/path/to/repo"                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Gate Agent Actions (autonomous):                       │
│  1. Glob for test files matching patterns               │
│  2. Read detected files to verify content               │
│  3. Bash to run language-appropriate syntax check       │
│  4. Bash to run test collection/discovery               │
│  5. Return structured GateResult                        │
└─────────────────────────────────────────────────────────┘
```

---

### Expert 2: Cost/Latency Engineer

**Position:** Use tiered validation - fast checks first, LLM only when needed.

**Analysis:**
```
Tier 1: File existence (0ms, $0)
  Path(test_path).exists()

Tier 2: LLM adaptive check (~500ms, ~$0.0005)
  Only if Tier 1 passes
  Handles syntax, test count, language detection
```

**Cost Model (per gate check):**
| Approach | Latency | Cost | Reliability |
|----------|---------|------|-------------|
| Pure deterministic (Python-only) | 100ms | $0 | 99% (Python), 0% (other) |
| Pure LLM (Haiku) | 500ms | $0.0005 | 99.5% (any language) |
| Hybrid (existence + LLM) | 300ms | $0.0003 | 99.8% (any language) |

**Recommendation:** Hybrid approach with file existence as fast-path.

---

### Expert 3: Multi-Language Platform Architect

**Position:** LLM-adaptive is the only scalable solution for multi-language support.

**The Maintenance Burden Problem:**
```python
# Current approach requires maintaining:
LANGUAGE_CONFIGS = {
    "python": {
        "test_patterns": ["test_*.py", "*_test.py"],
        "syntax_check": ["python", "-m", "py_compile"],
        "test_collect": ["pytest", "--collect-only"],
    },
    "dart": {
        "test_patterns": ["*_test.dart"],
        "syntax_check": ["dart", "analyze"],
        "test_collect": ["flutter", "test", "--reporter", "expanded"],
    },
    "typescript": {
        "test_patterns": ["*.test.ts", "*.spec.ts"],
        "syntax_check": ["tsc", "--noEmit"],
        "test_collect": ["jest", "--listTests"],
    },
    # Go, Rust, Ruby, Java, Kotlin, Swift, C#...
    # Each with their own quirks, flags, output formats
}
```

**LLM Alternative:**
```python
GATE_SYSTEM_PROMPT = """
You are a validation gate agent. Your job is to verify that artifacts
from the previous agent exist and are valid.

You have access to: Read, Bash, Glob tools.

For ANY programming language:
1. Detect the project type from config files
2. Find test files using appropriate patterns
3. Run the language's syntax/compile check
4. Run test discovery to count tests
5. Return a structured result

You know how to validate: Python, Dart/Flutter, TypeScript, JavaScript,
Go, Rust, Ruby, Java, Kotlin, Swift, C#, and any other language.

Output format:
{
  "passed": true/false,
  "language_detected": "flutter",
  "artifacts_found": ["test/widget_test.dart"],
  "test_count": 5,
  "errors": [],
  "commands_run": ["flutter test --reporter expanded"]
}
"""
```

**Key Advantage:** Zero maintenance. LLM already knows every language.

---

### Expert 4: Reliability Engineer (SRE)

**Position:** Tool grounding eliminates hallucination risk.

**The Hallucination Problem (Solved):**

Old concern:
> "LLM might say 'looks good' when file doesn't exist"

Solution with tool grounding:
```
Gate Agent:
1. Uses Glob tool → Gets ACTUAL file list from filesystem
2. Uses Read tool → Gets ACTUAL file contents
3. Uses Bash tool → Gets ACTUAL command output

The LLM cannot hallucinate filesystem state because it's reading
real tool outputs, not imagining them.
```

**Failure Mode Analysis:**
| Failure Mode | Deterministic Gate | LLM Gate (Tool-Grounded) |
|--------------|-------------------|--------------------------|
| File doesn't exist | Catches | Catches (Glob returns empty) |
| Syntax error | Catches (py_compile) | Catches (runs compile check) |
| Wrong language config | Fails silently | Adapts automatically |
| New framework version | May break | Adapts automatically |
| Edge case output format | Regex may fail | LLM parses flexibly |

**Conclusion:** Tool-grounded LLMs are MORE reliable than deterministic for varied inputs.

---

### Expert 5: Agent SDK Developer

**Position:** Use the existing agent infrastructure - gates ARE agents.

**Insight:** We already have `ThickAgent` with tool access. A gate is just a constrained agent:

```python
class GateAgent(ThickAgent):
    """Validation gate implemented as a thin agent."""

    def __init__(self, config: SwarmConfig):
        super().__init__(
            config=config,
            model="haiku",  # Fast, cheap
            tools=[Read, Bash, Glob],  # Limited tool set
            system_prompt=GATE_SYSTEM_PROMPT,
            max_turns=3,  # Constrained - just validate, don't loop
        )

    def validate(self, context: dict) -> GateResult:
        """Run gate validation and return structured result."""
        result = self.run(context)
        return self._parse_gate_result(result)
```

**Benefits:**
- Reuses existing agent infrastructure
- Same logging, cost tracking, session management
- Consistent patterns across codebase

---

## Consensus: LLM-Adaptive Gate Architecture

### Final Design

```
┌─────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                            │
└─────────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ test-writer │──▶│  GATE 1     │──▶│   coder     │
│   Agent     │   │  (LLM)      │   │   Agent     │
└─────────────┘   └─────────────┘   └─────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  GATE 2     │
                                    │  (LLM)      │
                                    └─────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  verifier   │
                                    │   Agent     │
                                    └─────────────┘
```

### Gate Types

**Gate 1: Post-Test-Writer Validation**
```yaml
name: test_artifacts_gate
trigger: after test-writer completes
checks:
  - Test file exists at expected location
  - Test file has valid syntax (language-appropriate)
  - Test file contains at least 1 test case
  - Test file imports/references correct modules
output:
  - test_path (actual location found)
  - test_count (number of tests)
  - language (detected project type)
```

**Gate 2: Post-Coder Validation**
```yaml
name: implementation_gate
trigger: after coder completes
checks:
  - Implementation file exists
  - Implementation passes syntax check
  - All tests pass
  - No new linting errors introduced
output:
  - impl_path (actual location)
  - test_results (pass/fail details)
```

---

## Implementation Plan (Revised)

### Phase 1: Gate Agent Foundation (Do First)

**File:** `swarm_attack/agents/gate.py`

```python
"""
LLM-Adaptive Gate Agent for cross-language validation.

Uses Haiku model with tool access to validate artifacts between
agent handoffs. Automatically adapts to any programming language.
"""

from dataclasses import dataclass
from typing import Any, Optional
import json

from .base import ThickAgent, AgentResult
from ..config import SwarmConfig

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
    errors: list[str] = None
    commands_run: list[str] = None
    raw_output: Optional[dict] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.commands_run is None:
            self.commands_run = []


class GateAgent(ThickAgent):
    """LLM-powered validation gate that adapts to any language."""

    def __init__(self, config: SwarmConfig, gate_name: str = "validation_gate"):
        super().__init__(
            config=config,
            model="haiku",  # Fast and cheap
            system_prompt=GATE_SYSTEM_PROMPT,
            max_turns=5,  # Limited - just validate
        )
        self.gate_name = gate_name

    def validate(self, context: dict[str, Any]) -> GateResult:
        """
        Run gate validation.

        Args:
            context: Dict with keys:
                - feature_id: str
                - issue_number: int
                - previous_agent: str (e.g., "test-writer")
                - expected_artifacts: list[str] (e.g., ["test file"])
                - project_root: str

        Returns:
            GateResult with validation outcome
        """
        # Build validation prompt
        prompt = self._build_validation_prompt(context)

        # Run agent
        result = self.run({"task": prompt, **context})

        # Parse result
        return self._parse_result(result)

    def _build_validation_prompt(self, context: dict) -> str:
        """Build the validation task prompt."""
        feature_id = context.get("feature_id", "unknown")
        issue_number = context.get("issue_number", 0)
        previous_agent = context.get("previous_agent", "unknown")
        expected = context.get("expected_artifacts", ["artifacts"])
        project_root = context.get("project_root", ".")

        return f'''Validate artifacts from {previous_agent} for issue #{issue_number} of feature "{feature_id}".

Project root: {project_root}

Expected artifacts: {expected}

Expected test file location pattern: tests/generated/{feature_id}/test_issue_{issue_number}.*

Steps:
1. First, detect the project language (check for pubspec.yaml, package.json, pyproject.toml, etc.)
2. Find test files matching the expected pattern
3. Verify syntax is valid
4. Run test discovery to count tests
5. Return your findings as JSON
'''

    def _parse_result(self, result: AgentResult) -> GateResult:
        """Parse agent result into GateResult."""
        if not result.success:
            return GateResult(
                passed=False,
                errors=[result.error or "Gate agent failed"],
            )

        # Try to extract JSON from output
        output = result.output or {}
        if isinstance(output, str):
            try:
                # Find JSON in the output
                import re
                json_match = re.search(r'\{[\s\S]*\}', output)
                if json_match:
                    output = json.loads(json_match.group())
                else:
                    output = {}
            except json.JSONDecodeError:
                output = {}

        return GateResult(
            passed=output.get("passed", False),
            language=output.get("language"),
            artifacts=output.get("artifacts"),
            test_count=output.get("test_count", 0),
            errors=output.get("errors", []),
            commands_run=output.get("commands_run", []),
            raw_output=output,
        )
```

### Phase 2: Orchestrator Integration

**File:** `swarm_attack/orchestrator.py` (modify `_run_implementation_cycle`)

```python
# Add to imports
from .agents.gate import GateAgent, GateResult

# Add to __init__
self._gate_agent: Optional[GateAgent] = None

# In _run_implementation_cycle, before running coder:

# Initialize gate agent if needed
if self._gate_agent is None:
    self._gate_agent = GateAgent(self.config, gate_name="pre_coder_gate")

# Run gate validation
gate_context = {
    "feature_id": feature_id,
    "issue_number": issue_number,
    "previous_agent": "test-writer",
    "expected_artifacts": ["test file"],
    "project_root": str(self.config.repo_root),
}

gate_result = self._gate_agent.validate(gate_context)

if not gate_result.passed:
    error_msg = f"Gate validation failed: {'; '.join(gate_result.errors)}"
    self._log("gate_failed", {
        "gate": "pre_coder_gate",
        "errors": gate_result.errors,
        "language": gate_result.language,
    }, level="error")
    return False, AgentResult.failure_result(error_msg), 0.0

# Update context with gate findings
context["test_path"] = gate_result.artifacts[0]["path"] if gate_result.artifacts else test_path
context["language"] = gate_result.language
context["test_count"] = gate_result.test_count

self._log("gate_passed", {
    "gate": "pre_coder_gate",
    "language": gate_result.language,
    "test_count": gate_result.test_count,
})
```

### Phase 3: Tests

**File:** `tests/unit/test_gate_agent.py`

```python
"""Tests for LLM-adaptive gate agent."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.agents.gate import GateAgent, GateResult, GATE_SYSTEM_PROMPT
from swarm_attack.config import SwarmConfig


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    return config


class TestGateResult:
    def test_passed_result(self):
        result = GateResult(
            passed=True,
            language="python",
            test_count=5,
        )
        assert result.passed
        assert result.language == "python"
        assert result.test_count == 5
        assert result.errors == []

    def test_failed_result(self):
        result = GateResult(
            passed=False,
            errors=["Test file not found"],
        )
        assert not result.passed
        assert "Test file not found" in result.errors


class TestGateAgent:
    def test_system_prompt_contains_language_detection(self):
        assert "pubspec.yaml" in GATE_SYSTEM_PROMPT
        assert "package.json" in GATE_SYSTEM_PROMPT
        assert "pyproject.toml" in GATE_SYSTEM_PROMPT

    def test_system_prompt_requires_json_output(self):
        assert '"passed"' in GATE_SYSTEM_PROMPT
        assert '"language"' in GATE_SYSTEM_PROMPT
        assert '"test_count"' in GATE_SYSTEM_PROMPT

    def test_build_validation_prompt(self, mock_config):
        gate = GateAgent(mock_config)
        prompt = gate._build_validation_prompt({
            "feature_id": "my-feature",
            "issue_number": 42,
            "previous_agent": "test-writer",
            "project_root": "/repo",
        })

        assert "my-feature" in prompt
        assert "42" in prompt
        assert "test-writer" in prompt

    def test_parse_result_success(self, mock_config):
        gate = GateAgent(mock_config)

        mock_agent_result = MagicMock()
        mock_agent_result.success = True
        mock_agent_result.output = {
            "passed": True,
            "language": "flutter",
            "test_count": 3,
            "artifacts": [{"path": "test/widget_test.dart", "exists": True}],
        }

        result = gate._parse_result(mock_agent_result)

        assert result.passed
        assert result.language == "flutter"
        assert result.test_count == 3

    def test_parse_result_failure(self, mock_config):
        gate = GateAgent(mock_config)

        mock_agent_result = MagicMock()
        mock_agent_result.success = False
        mock_agent_result.error = "Agent timed out"

        result = gate._parse_result(mock_agent_result)

        assert not result.passed
        assert "Agent timed out" in result.errors
```

---

## Implementation Sequence

1. **Create `agents/gate.py`** - GateAgent class with system prompt
2. **Add unit tests** - Verify prompt structure and result parsing
3. **Integrate into orchestrator** - Add gate check before coder
4. **Test with Python project** - Verify it works for existing flow
5. **Test with Flutter project** - Verify language adaptation
6. **Add gate after coder** - Verify implementation before verifier

---

## Cost Analysis

| Gate Check | Model | Input Tokens | Output Tokens | Cost |
|------------|-------|--------------|---------------|------|
| Pre-coder (test validation) | Haiku | ~500 | ~200 | $0.00035 |
| Post-coder (impl validation) | Haiku | ~800 | ~300 | $0.00055 |
| **Total per issue** | | | | **$0.0009** |

At 100 issues/day = $0.09/day = $2.70/month

**Verdict:** Cost is negligible. Use LLM gates.

---

## Migration Path

1. Keep existing `test_path` context passing (it works)
2. Add GateAgent as NEW layer (doesn't break existing)
3. Gate validates and ENHANCES context (adds language, test_count)
4. Gradually remove hardcoded Python assumptions from coder/verifier
5. Full multi-language support achieved

---

*Expert Debate v2 - Updated for Opus 4.5 / GPT-5.2 Pro era - December 2025*
