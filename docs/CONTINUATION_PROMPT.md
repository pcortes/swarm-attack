# Feature Swarm Implementation Continuation Prompt

You are an expert Python engineer continuing the implementation of Feature Swarm, a CLI orchestrator that automates software development from PRD to shipped code.

## CRITICAL: Use Test-Driven Development (TDD)

ALL previous work was done using TDD. You MUST follow the same approach:

1. **Write tests FIRST** - Define expected behavior through tests before any implementation
2. **Run tests to see them fail** - Confirm tests are testing the right thing
3. **Implement the minimum code** - Write just enough code to make tests pass
4. **Refactor** - Clean up while keeping tests green

TDD is essential for this project. Writing tests after implementation doesn't validate design quality or catch interface issues. The tests define the contract.

---

## IMPORTANT: Multi-LLM Architecture (Subscription-Based)

This project uses **TWO different LLMs** via their CLI tools, both using **flat-rate subscriptions** (NO API keys):

### 1. Claude Code CLI (for spec writing/implementation)
- Uses `claude -p` CLI binary in headless mode
- **Auth**: Claude Code Max subscription (no API key needed)
- **Setup**: Run `claude login` once
- Used for: Writing specs, generating code, implementation tasks
- Existing implementation in `feature_swarm/llm_clients.py` via `ClaudeCliRunner`

### 2. OpenAI Codex CLI (for spec review/critique) ⚠️ MIGRATION REQUIRED
- Uses `codex exec` CLI in non-interactive mode
- **Auth**: ChatGPT Plus/Pro subscription (no API key needed)
- **Setup**: Run `codex` and select "Sign in with ChatGPT"
- **WHY**: We don't want Claude reviewing its own work - Codex provides independent review
- Used for: SpecCriticAgent, IssueValidatorAgent (review tasks)
- **NEW**: Replaces the GPT-5 API approach (GPT5Client → CodexCliRunner)

### OpenAI Codex CLI - Usage Pattern

**Installation:**
```bash
npm i -g @openai/codex
# OR
brew install --cask codex
```

**Authentication (one-time):**
```bash
codex
# Select "Sign in with ChatGPT" → uses your subscription
```

**Non-Interactive Mode (for automation):**
```bash
# Basic usage - streams to stderr, final message to stdout
codex exec "Review this spec for completeness and clarity"

# With JSON output (JSONL streaming)
codex exec "Review this spec" --json

# With structured output schema
codex exec "Review this spec" --output-schema schema.json -o result.json
```

**Python Implementation:**
```python
import subprocess
import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class CodexResult:
    """Result from Codex CLI exec call."""
    text: str
    session_id: str
    events: list[dict]  # JSONL events if --json used

    def to_dict(self) -> dict:
        return {"text": self.text, "session_id": self.session_id, "events": self.events}

    @classmethod
    def from_dict(cls, data: dict) -> "CodexResult":
        return cls(text=data["text"], session_id=data.get("session_id", ""), events=data.get("events", []))

class CodexCliRunner:
    """Client for OpenAI Codex CLI in exec mode (uses ChatGPT subscription)."""

    def __init__(self, binary: str = "codex", sandbox_mode: str = "read-only"):
        self.binary = binary
        self.sandbox_mode = sandbox_mode

    def run(
        self,
        prompt: str,
        json_output: bool = True,
        timeout_seconds: int = 120,
        output_schema_path: Optional[str] = None,
    ) -> CodexResult:
        """
        Run Codex CLI in exec (non-interactive) mode.

        Args:
            prompt: The task/prompt for Codex
            json_output: Whether to use --json for JSONL streaming
            timeout_seconds: Timeout for the command
            output_schema_path: Optional JSON schema file for structured output

        Returns:
            CodexResult with response text and events
        """
        cmd = [self.binary, "exec", prompt]

        if json_output:
            cmd.append("--json")

        if output_schema_path:
            cmd.extend(["--output-schema", output_schema_path])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            raise RuntimeError(f"codex exec failed: {result.stderr}")

        # Parse JSONL events if --json was used
        events = []
        final_text = ""
        if json_output:
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        event = json.loads(line)
                        events.append(event)
                        # Extract final message from last turn.completed event
                        if event.get("type") == "turn.completed":
                            final_text = event.get("last_message", "")
                    except json.JSONDecodeError:
                        pass
        else:
            final_text = result.stdout.strip()

        # Get session_id from thread.started event
        session_id = ""
        for event in events:
            if event.get("type") == "thread.started":
                session_id = event.get("thread_id", "")
                break

        return CodexResult(
            text=final_text,
            session_id=session_id,
            events=events,
        )
```

**JSONL Event Types:**
```
thread.started    - Session begins, contains thread_id
turn.started      - Agent turn begins
item.started      - Work item begins (reasoning, file_change, etc.)
item.updated      - Progress update
item.completed    - Work item finished
turn.completed    - Agent turn finished, contains last_message
thread.completed  - Session finished
```

**Key Differences from GPT-5 API:**
| Aspect | GPT-5 API (OLD) | Codex CLI (NEW) |
|--------|-----------------|-----------------|
| Auth | API key required | ChatGPT subscription |
| Cost | Per-token ($1.25-$10/1M) | Flat monthly fee |
| Output | Single JSON response | JSONL event stream |
| Cost tracking | Precise per request | Not available |
| Rate limits | Token-based | Message-based (30-1500/5hr) |

---

## Current Progress Summary

### Phase 1 Foundation: 7/7 Issues Complete (TDD)

| Issue | Module            | Status     | Tests      |
|-------|-------------------|------------|------------|
| #1    | models.py         | ✅ Complete | 33 passing |
| #2    | config.py         | ✅ Complete | 26 passing |
| #3    | logger.py         | ✅ Complete | 21 passing |
| #4    | state_store.py    | ✅ Complete | 43 passing |
| #5    | utils/fs.py       | ✅ Complete | 55 passing |
| #6    | llm_clients.py    | ✅ Complete | 33 passing |
| #7    | cli.py (skeleton) | ✅ Complete | 41 passing |

### Phase 2 Spec Pipeline: 7/7 Issues Complete (TDD)

| Issue | Module            | Status     | Tests      |
|-------|-------------------|------------|------------|
| #8    | agents/base.py    | ✅ Complete | 34 passing |
| #34   | Skill templates   | ✅ Complete | N/A        |
| #9    | spec_author.py    | ✅ Complete | 8 passing  |
| #10   | spec_critic.py    | ✅ Complete | 7 passing  |
| #11   | spec_moderator.py | ✅ Complete | 7 passing  |
| #12   | orchestrator.py   | ✅ Complete | 31 passing |
| #13   | cli.py (approval) | ✅ Complete | 17 passing |

### Phase 3 Issue Pipeline: 3/3 Issues Complete (TDD)

| Issue | Module                      | Status     | Tests      |
|-------|-----------------------------|------------|------------|
| #14   | Integration tests           | ✅ Complete | 6 passing  |
| #15   | agents/issue_creator.py     | ✅ Complete | 15 passing |
| #16   | agents/issue_validator.py   | ✅ Complete | 17 passing |

**Total Tests: 390 unit tests passing + 6 integration tests**

---

## What Has Been Implemented

### Package Structure

```
feature_swarm/
├── __init__.py          ✅ Complete (version 0.1.0)
├── __main__.py          ✅ Complete (entry point)
├── models.py            ✅ Complete
├── config.py            ✅ Complete
├── logger.py            ✅ Complete
├── state_store.py       ✅ Complete
├── llm_clients.py       ✅ Complete (ClaudeCliRunner)
├── cli.py               ✅ Complete (status, init, run, approve, reject)
├── orchestrator.py      ✅ Complete
├── agents/
│   ├── __init__.py      ✅ Complete (exports all agents)
│   ├── base.py          ✅ Complete
│   ├── spec_author.py   ✅ Complete (uses Claude)
│   ├── spec_critic.py   ✅ Complete (NEEDS MIGRATION TO GPT-5)
│   ├── spec_moderator.py ✅ Complete
│   ├── issue_creator.py  ✅ Complete (uses Claude)
│   └── issue_validator.py ✅ Complete (NEEDS MIGRATION TO GPT-5)
└── utils/
    ├── __init__.py
    └── fs.py            ✅ Complete

.claude/skills/
├── feature-spec-author/SKILL.md     ✅ Complete
├── feature-spec-critic/SKILL.md     ✅ Complete
├── feature-spec-moderator/SKILL.md  ✅ Complete
├── issue-creator/SKILL.md           ✅ Complete
└── issue-validator/SKILL.md         ✅ Complete

tests/
├── __init__.py
├── integration/
│   ├── __init__.py
│   └── test_spec_pipeline_integration.py  ✅ 6 tests
└── unit/
    ├── __init__.py
    ├── test_models.py       ✅ 33 tests
    ├── test_config.py       ✅ 26 tests
    ├── test_logger.py       ✅ 21 tests
    ├── test_state_store.py  ✅ 43 tests
    ├── test_fs.py           ✅ 55 tests
    ├── test_llm_clients.py  ✅ 33 tests
    ├── test_cli.py          ✅ 58 tests
    ├── test_agents_base.py  ✅ 34 tests
    ├── test_spec_agents.py  ✅ 24 tests
    ├── test_orchestrator.py ✅ 31 tests
    ├── test_issue_creator.py ✅ 15 tests
    └── test_issue_validator.py ✅ 17 tests
```

---

## YOUR TASK: Migrate from GPT-5 API to Codex CLI

**CONTEXT:** Issues #17, #18, #19 were previously implemented using GPT-5 API with API keys. We now need to migrate to Codex CLI with subscription-based authentication.

Implement the migration using TDD, then **STOP** for review.

---

### Issue #20: CodexCliRunner for Independent Review

**title:** "Implement CodexCliRunner to replace GPT5Client (subscription-based)"
**priority:** P0 (CRITICAL - removes API key dependency)
**size:** medium (2-3 hours)
**dependencies:** []

**RATIONALE:** Switch from per-token GPT-5 API to flat-rate Codex CLI subscription. Same multi-LLM architecture, but using `codex exec` instead of API calls.

**files:**
- tests/unit/test_codex_client.py (WRITE FIRST - replaces test_gpt5_client.py)
- feature_swarm/codex_client.py (implement to pass tests - replaces gpt5_client.py)
- feature_swarm/config.py (UPDATE CodexConfig to replace OpenAIConfig)

**TDD_APPROACH:**
1. FIRST: Write test_codex_client.py with ALL test cases
2. Run tests - they should FAIL
3. Create codex_client.py skeleton
4. Implement until tests pass

**test_cases_to_write_first:**
```python
class TestCodexCliRunner:
    def test_init_with_default_binary(self)
    def test_init_with_custom_binary(self)
    def test_run_returns_codex_result(self, mock_subprocess)
    def test_run_extracts_text_from_stdout(self, mock_subprocess)
    def test_run_with_json_output_parses_jsonl(self, mock_subprocess)
    def test_run_handles_cli_failure(self, mock_subprocess)
    def test_run_handles_timeout(self, mock_subprocess)
    def test_run_with_output_schema(self, mock_subprocess)
    def test_run_extracts_session_id(self, mock_subprocess)

class TestCodexResult:
    def test_result_dataclass_fields(self)
    def test_result_to_dict(self)
    def test_result_from_dict(self)

class TestCodexConfig:
    def test_config_has_codex_section(self)
    def test_codex_default_binary(self)
    def test_codex_default_sandbox_mode(self)
```

**expected_interface:**
```python
@dataclass
class CodexResult:
    text: str
    session_id: str
    events: list[dict]  # JSONL events if --json used

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict) -> "CodexResult": ...

class CodexCliRunner:
    def __init__(self, binary: str = "codex", sandbox_mode: str = "read-only")
    def run(self, prompt: str, json_output: bool = True,
            timeout_seconds: int = 120,
            output_schema_path: Optional[str] = None) -> CodexResult
```

**acceptance_criteria:**
- CodexCliRunner class that calls `codex exec` CLI
- Parses JSONL output from --json flag
- Proper error handling for CLI failures
- Timeout handling
- No API key required (uses ChatGPT subscription)

---

### Issue #21: Migrate SpecCriticAgent to Codex CLI

**title:** "Migrate SpecCriticAgent from GPT5Client to CodexCliRunner"
**priority:** P1
**size:** small (1-2 hours)
**dependencies:** [20]

**RATIONALE:** Update the critic to use subscription-based Codex CLI instead of GPT-5 API.

**files:**
- tests/unit/test_spec_agents.py (UPDATE tests to use mock_codex_runner)
- feature_swarm/agents/spec_critic.py (MIGRATE from GPT5Client to CodexCliRunner)

**TDD_APPROACH:**
1. FIRST: Update tests in test_spec_agents.py for CodexCliRunner
2. Run tests - they should FAIL
3. Update spec_critic.py to use CodexCliRunner
4. Implement until tests pass

**test_cases_to_update:**
```python
class TestSpecCriticAgent:
    # Update existing tests to mock CodexCliRunner instead of GPT5Client
    def test_uses_codex_runner(self, mock_config, mock_codex_runner, ...)
    def test_successful_review_with_codex(self, mock_config, mock_codex_runner, ...)
    def test_codex_timeout_handling(self, mock_config, mock_codex_runner, ...)
    def test_codex_cli_error_handling(self, mock_config, mock_codex_runner, ...)
```

**expected_changes:**
```python
class SpecCriticAgent(BaseAgent):
    name = "spec_critic"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        codex_runner: Optional[CodexCliRunner] = None,  # Changed from gpt5_client
        state_store: Optional[StateStore] = None,
    ) -> None:
        super().__init__(config, logger, None, state_store)
        self._codex = codex_runner

    @property
    def codex(self) -> CodexCliRunner:
        if self._codex is None:
            self._codex = CodexCliRunner()
        return self._codex

    def run(self, context: dict[str, Any]) -> AgentResult:
        # ... use self.codex.run() instead of self.gpt5.run()
```

**acceptance_criteria:**
- SpecCriticAgent uses CodexCliRunner instead of GPT5Client
- All existing tests pass with updated mocks
- Proper error handling for CLI failures
- No API key required

---

### Issue #22: Migrate IssueValidatorAgent to Codex CLI

**title:** "Migrate IssueValidatorAgent from GPT5Client to CodexCliRunner"
**priority:** P1
**size:** small (1-2 hours)
**dependencies:** [20]

**RATIONALE:** Update the validator to use subscription-based Codex CLI instead of GPT-5 API.

**files:**
- tests/unit/test_issue_validator.py (UPDATE tests to use mock_codex_runner)
- feature_swarm/agents/issue_validator.py (MIGRATE from GPT5Client to CodexCliRunner)

**TDD_APPROACH:**
1. FIRST: Update tests in test_issue_validator.py for CodexCliRunner
2. Run tests - they should FAIL
3. Update issue_validator.py to use CodexCliRunner
4. Implement until tests pass

**test_cases_to_update:**
```python
class TestIssueValidatorAgent:
    # Update tests that involve LLM calls to use CodexCliRunner
    def test_uses_codex_for_implementability_check(self, mock_config, mock_codex_runner, ...)
    def test_codex_validation_pass(self, mock_config, mock_codex_runner, ...)
    def test_codex_validation_with_issues(self, mock_config, mock_codex_runner, ...)
    def test_codex_timeout_handling(self, mock_config, mock_codex_runner, ...)
    # Note: Structural validation tests don't change (no LLM involved)
```

**expected_changes:**
```python
class IssueValidatorAgent(BaseAgent):
    name = "issue_validator"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        codex_runner: Optional[CodexCliRunner] = None,  # Changed from gpt5_client
        state_store: Optional[StateStore] = None,
    ) -> None:
        super().__init__(config, logger, None, state_store)
        self._codex = codex_runner
```

**acceptance_criteria:**
- IssueValidatorAgent uses CodexCliRunner for implementability checks
- Structural/dependency validation unchanged (no LLM)
- All existing tests pass with updated mocks
- No API key required

---

### Issue #23: Remove GPT-5 API Code (Cleanup)

**title:** "Remove deprecated GPT5Client and related code"
**priority:** P2
**size:** small (30 min)
**dependencies:** [21, 22]

**RATIONALE:** Clean up old API-based code now that we've migrated to Codex CLI.

**files to DELETE:**
- feature_swarm/gpt5_client.py
- tests/unit/test_gpt5_client.py
- tests/integration/test_gpt5_live.py

**files to UPDATE:**
- feature_swarm/config.py (remove OpenAIConfig, keep CodexConfig)
- feature_swarm/__init__.py (remove GPT5Client exports)

**acceptance_criteria:**
- No GPT-5 API code remains
- No OPENAI_API_KEY references remain
- All 420+ tests still pass

---

## Key Patterns to Follow

### Multi-LLM Pattern (Subscription-Based)

```python
# For WRITING/CREATING (use Claude Code CLI)
from feature_swarm.llm_clients import ClaudeCliRunner

class SpecAuthorAgent(BaseAgent):
    """Creates specs - uses Claude (Max subscription)."""
    def __init__(self, ..., llm_runner: Optional[ClaudeCliRunner] = None):
        self._llm = llm_runner

# For REVIEWING/CRITIQUING (use Codex CLI)
from feature_swarm.codex_client import CodexCliRunner

class SpecCriticAgent(BaseAgent):
    """Reviews specs - uses Codex (ChatGPT subscription) for independent validation."""
    def __init__(self, ..., codex_runner: Optional[CodexCliRunner] = None):
        self._codex = codex_runner
```

### Test Fixture Pattern for Codex CLI

```python
@pytest.fixture
def mock_codex_runner():
    """Create a mock Codex CLI runner."""
    runner = MagicMock(spec=CodexCliRunner)
    runner.run.return_value = CodexResult(
        text='{"scores": {"clarity": 0.85}, "issues": [], "recommendation": "APPROVE"}',
        session_id="thread_test123",
        events=[
            {"type": "thread.started", "thread_id": "thread_test123"},
            {"type": "turn.completed", "last_message": "Review complete"}
        ],
    )
    return runner

@pytest.fixture
def mock_codex_jsonl_output():
    """Sample Codex CLI JSONL output for mocking subprocess."""
    return "\n".join([
        '{"type": "thread.started", "thread_id": "thread_test123"}',
        '{"type": "turn.started"}',
        '{"type": "item.started", "item_type": "reasoning"}',
        '{"type": "item.completed"}',
        '{"type": "turn.completed", "last_message": "Review response here"}',
        '{"type": "thread.completed"}'
    ])
```

### Config Pattern for Codex CLI

```python
# In config.py, add:
@dataclass
class CodexConfig:
    """Codex CLI configuration (uses ChatGPT subscription)."""
    binary: str = "codex"
    sandbox_mode: str = "read-only"  # read-only, full-auto, danger-full-access
    timeout_seconds: int = 120
    json_output: bool = True  # Use --json for JSONL streaming

# In SwarmConfig, add:
@dataclass
class SwarmConfig:
    # ... existing fields ...
    codex: CodexConfig = field(default_factory=CodexConfig)
```

### Prerequisites Check

```python
def check_codex_auth() -> bool:
    """Check if Codex CLI is authenticated with ChatGPT subscription."""
    result = subprocess.run(
        ["codex", "--version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Codex CLI not installed. Run: npm i -g @openai/codex"
        )
    # Note: Auth is checked on first `codex exec` call
    return True
```

---

## How to Run Tests

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific module tests
python -m pytest tests/unit/test_gpt5_client.py -v
python -m pytest tests/unit/test_spec_agents.py -v
python -m pytest tests/unit/test_issue_validator.py -v

# Run with coverage
python -m pytest tests/unit/ -v --cov=feature_swarm

# Load environment for integration tests
source backend/.env
python -m pytest tests/integration/ -v
```

---

## Environment Setup

**No API keys required!** Both CLIs use subscription-based authentication.

### Prerequisites

```bash
# 1. Claude Code CLI (one-time setup)
claude login
# Uses your Claude Code Max subscription

# 2. OpenAI Codex CLI (one-time setup)
npm i -g @openai/codex
codex
# Select "Sign in with ChatGPT" → uses your ChatGPT Plus/Pro subscription
```

### Verify Authentication

```bash
# Test Claude Code CLI
claude -p "echo test" --output-format json

# Test Codex CLI
codex exec "echo test"
```

---

## Stopping Criteria

**STOP** after completing these four issues:

1. ✅ Writing ALL tests for Issue #20 (test_codex_client.py)
2. ✅ Implementing codex_client.py to pass all tests
3. ✅ Updating config.py with CodexConfig
4. ✅ Updating tests for Issue #21 (test_spec_agents.py)
5. ✅ Migrating spec_critic.py to use CodexCliRunner
6. ✅ Updating tests for Issue #22 (test_issue_validator.py)
7. ✅ Migrating issue_validator.py to use CodexCliRunner
8. ✅ Completing Issue #23 (cleanup GPT-5 API code)
9. ✅ Running `python -m pytest tests/unit/ -v` and confirming ALL tests pass

**Expected final test count: ~400+ tests**

---

## Summary of Multi-LLM Architecture (Subscription-Based)

| Agent | Purpose | CLI Tool | Subscription |
|-------|---------|----------|--------------|
| SpecAuthorAgent | Write specs | `claude -p` | Claude Code Max |
| SpecCriticAgent | Review specs | **`codex exec`** | ChatGPT Plus/Pro |
| SpecModeratorAgent | Apply feedback | `claude -p` | Claude Code Max |
| IssueCreatorAgent | Generate issues | `claude -p` | Claude Code Max |
| IssueValidatorAgent | Validate issues | **`codex exec`** | ChatGPT Plus/Pro |

**Benefits of Subscription-Based Architecture:**
- No API keys to manage
- Flat monthly cost (no per-token charges)
- Same multi-LLM validation (Claude creates, Codex reviews)
- Simpler deployment and CI/CD integration
