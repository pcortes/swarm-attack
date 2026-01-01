# Engineering Spec: Dispatcher Claude CLI Integration

## 1. Overview

### 1.1 Purpose
Implement the `AgentDispatcher._run_agent()` method to call Claude CLI via subprocess, parse JSON responses into `Finding` objects, and handle errors gracefully without crashing.

### 1.2 Existing Infrastructure

**Existing code this builds on:**
- `swarm_attack/commit_review/dispatcher.py:89-129` - Placeholder `_run_agent()` method with TODOs
- `swarm_attack/llm_clients.py` - `ClaudeCliRunner` with subprocess pattern, `ClaudeInvocationError`, `ClaudeTimeoutError`
- `swarm_attack/commit_review/models.py:52-61` - `Finding` dataclass with required fields
- `swarm_attack/commit_review/prompts.py` - Expert prompts with expected output format

**Key patterns to follow:**
- `ClaudeCliRunner.run()` at `llm_clients.py:133-239` uses `subprocess.run()` with `capture_output=True, text=True, timeout=...`
- Error handling via `try/except` with logging and graceful degradation
- JSON parsing with `json.loads()` and error handling for `JSONDecodeError`

### 1.3 Scope

**In Scope:**
- Implement `_run_agent()` to call Claude CLI
- Parse JSON response into `Finding` objects
- Handle timeout, invalid JSON, and CLI errors gracefully
- Add 5 unit tests

**Out of Scope:**
- Changing the async dispatch logic
- Modifying the prompt templates
- Adding retry logic (graceful degradation is sufficient)
- Caching or rate limiting

## 2. Implementation

### 2.1 Approach

The `_run_agent()` method will:
1. Call Claude CLI via `subprocess.run()` with the `--print --output-format json` flags
2. Parse the JSON response to extract findings
3. Return empty list on any error (graceful degradation per PRD)

Since this is an async method but subprocess is sync, we'll use `asyncio.to_thread()` to avoid blocking the event loop.

### 2.2 Changes Required

| File | Change | Why |
|------|--------|-----|
| `swarm_attack/commit_review/dispatcher.py` | Implement `_run_agent()` method | Core requirement |
| `tests/unit/test_dispatcher.py` | Add 5 unit tests | Test coverage for all error paths |

### 2.3 Data Model

No new models needed. Uses existing:
- `Finding` from `models.py` - already has all required fields
- `Severity` enum from `models.py` - for severity parsing

**JSON Response Format (expected from Claude):**
```json
{
  "result": "...",
  "findings": [
    {
      "severity": "MEDIUM",
      "category": "production_reliability",
      "description": "Missing error handling",
      "evidence": "src/app.py:42"
    }
  ]
}
```

Note: Claude may return findings in `result` as text or as structured JSON. The implementation should handle both:
1. Try parsing `result` field as JSON for structured output
2. Fall back to regex parsing if `result` is plain text

## 3. API

### 3.1 Method Signature (unchanged)

```python
async def _run_agent(
    self,
    commit: CommitInfo,
    category: CommitCategory,
    prompt: str,
) -> list[Finding]:
```

### 3.2 CLI Command

```bash
claude --print --output-format json -p "{prompt}"
```

**Flags:**
- `--print` - Print output without interactive mode
- `--output-format json` - Return JSON structure
- `-p` - Prompt argument

## 4. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Add `_parse_findings()` helper method | `dispatcher.py` | S |
| 2 | Add `_call_claude_cli()` sync helper method | `dispatcher.py` | M |
| 3 | Implement `_run_agent()` with asyncio.to_thread | `dispatcher.py` | M |
| 4 | Create `tests/unit/test_dispatcher.py` with 5 tests | `test_dispatcher.py` | M |
| 5 | Run tests and verify all pass | - | S |

## 5. Detailed Implementation

### 5.1 `_parse_findings()` Helper

```python
def _parse_findings(
    self,
    response: dict,
    commit_sha: str,
    category: CommitCategory,
) -> list[Finding]:
    """Parse Claude response into Finding objects.

    Args:
        response: Parsed JSON from Claude CLI
        commit_sha: SHA of the commit being reviewed
        category: Category for expert assignment

    Returns:
        List of Finding objects, empty on parse errors
    """
    findings = []

    # Try to get findings from response
    result_text = response.get("result", "")

    # Option 1: Findings embedded as JSON in result
    # Option 2: Parse findings from text output

    # Get expert name from category mapping
    expert = self._get_expert_for_category(category)

    # Parse each finding...

    return findings
```

### 5.2 `_call_claude_cli()` Helper

```python
def _call_claude_cli(self, prompt: str) -> dict:
    """Call Claude CLI synchronously.

    Args:
        prompt: The review prompt

    Returns:
        Parsed JSON response dict

    Raises:
        Exception on any error (caught by caller)
    """
    result = subprocess.run(
        ["claude", "--print", "--output-format", "json", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr}")

    return json.loads(result.stdout)
```

### 5.3 `_run_agent()` Implementation

```python
async def _run_agent(
    self,
    commit: CommitInfo,
    category: CommitCategory,
    prompt: str,
) -> list[Finding]:
    """Run a single review agent via Claude CLI.

    Calls Claude CLI in a thread to avoid blocking the event loop.
    Returns empty list on any error (graceful degradation).
    """
    logger.debug(f"Running agent for {commit.sha} ({category.value})")

    try:
        # Run sync subprocess in thread to avoid blocking
        response = await asyncio.to_thread(
            self._call_claude_cli,
            prompt,
        )

        return self._parse_findings(response, commit.sha, category)

    except subprocess.TimeoutExpired:
        logger.warning(f"Claude CLI timed out for {commit.sha}")
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON from Claude CLI for {commit.sha}: {e}")
        return []
    except Exception as e:
        logger.warning(f"Agent failed for {commit.sha}: {e}")
        return []
```

## 6. Testing

### 6.1 Manual Test Plan

1. Run `swarm-attack review-commits --since="1 hour ago" --output json`
2. Verify output contains findings (if any commits exist)
3. Kill Claude CLI mid-request and verify graceful handling

### 6.2 Unit Tests

Create `tests/unit/test_dispatcher.py`:

| Test | What It Verifies |
|------|------------------|
| `test_run_agent_calls_claude_cli` | Subprocess called with correct args |
| `test_run_agent_parses_findings` | Valid JSON response produces Finding objects |
| `test_run_agent_handles_timeout` | TimeoutExpired returns empty list, logs warning |
| `test_run_agent_handles_invalid_json` | JSONDecodeError returns empty list, logs warning |
| `test_run_agent_handles_cli_error` | Non-zero exit returns empty list, logs warning |

### 6.3 Test Implementation Outline

```python
"""Unit tests for AgentDispatcher._run_agent()"""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock
import subprocess

from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.models import (
    CommitInfo, CommitCategory, Finding, Severity
)


@pytest.fixture
def dispatcher():
    return AgentDispatcher(max_concurrent=5)


@pytest.fixture
def sample_commit():
    return CommitInfo(
        sha="abc1234",
        author="Test Author",
        email="test@example.com",
        timestamp="2025-01-01T00:00:00",
        message="fix: test commit",
        files_changed=1,
        insertions=10,
        deletions=5,
        changed_files=["src/app.py"],
    )


class TestRunAgentClaudeCLI:
    """Tests for Claude CLI invocation."""

    @pytest.mark.asyncio
    async def test_run_agent_calls_claude_cli(self, dispatcher, sample_commit):
        """Verify Claude CLI is called with correct arguments."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"result": "No issues found"}',
                stderr="",
            )

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert cmd[0] == "claude"
            assert "--print" in cmd
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "-p" in cmd

    @pytest.mark.asyncio
    async def test_run_agent_parses_findings(self, dispatcher, sample_commit):
        """Valid JSON response produces Finding objects."""
        # Test with structured findings in response
        ...

    @pytest.mark.asyncio
    async def test_run_agent_handles_timeout(self, dispatcher, sample_commit):
        """TimeoutExpired returns empty list."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_handles_invalid_json(self, dispatcher, sample_commit):
        """Invalid JSON returns empty list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_handles_cli_error(self, dispatcher, sample_commit):
        """Non-zero exit code returns empty list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: CLI failed",
            )

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []
```

## 7. Error Handling

All errors result in graceful degradation (return empty list):

| Error Type | Handling |
|------------|----------|
| `subprocess.TimeoutExpired` | Log warning, return `[]` |
| `json.JSONDecodeError` | Log warning, return `[]` |
| Non-zero exit code | Log warning, return `[]` |
| Any other `Exception` | Log warning, return `[]` |

This matches the PRD requirement: "Return empty list on any error (graceful degradation)"

## 8. Open Questions

1. **Finding extraction format**: Claude's response format for findings needs to be specified. Current prompts ask for text output with a specific format. Should we add JSON schema instructions to the prompts?

   **Recommendation**: Start with regex parsing of the text output format (already specified in prompts.py), add JSON schema later if needed.

2. **Expert name mapping**: How to map `CommitCategory` to expert name for the `Finding.expert` field?

   **Recommendation**: Use the `EXPERTS` dict in `prompts.py` with a simple category-to-expert-key mapping.
