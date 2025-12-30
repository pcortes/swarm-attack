# Continue QA CLI & Hooks Integration Testing via TDD

## Current State

The Adaptive QA Agent core implementation is complete with E2E tests:

### Completed Components (577 QA tests passing)

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| QA Models | `swarm_attack/qa/models.py` | ~50 tests | ✓ Complete |
| QA Orchestrator | `swarm_attack/qa/orchestrator.py` | ~60 tests | ✓ Complete |
| Behavioral Agent | `swarm_attack/qa/agents/behavioral.py` | ~50 tests | ✓ Complete |
| Contract Agent | `swarm_attack/qa/agents/contract.py` | ~45 tests | ✓ Complete |
| Regression Agent | `swarm_attack/qa/agents/regression.py` | ~40 tests | ✓ Complete |
| Context Builder | `swarm_attack/qa/context_builder.py` | ~30 tests | ✓ Complete |
| Depth Selector | `swarm_attack/qa/depth_selector.py` | ~25 tests | ✓ Complete |
| Feature Pipeline Integration | `swarm_attack/qa/integrations/feature_pipeline.py` | 37 tests | ✓ Complete |
| Bug Pipeline Integration | `swarm_attack/qa/integrations/bug_pipeline.py` | 28 tests | ✓ Complete |
| COS Goals | `swarm_attack/qa/integrations/cos_goals.py` | 28 tests | ✓ Complete |
| COS Autopilot | `swarm_attack/qa/integrations/cos_autopilot.py` | 33 tests | ✓ Complete |
| QA Config | `swarm_attack/qa/qa_config.py` | 38 tests | ✓ Complete |
| Verifier Hook | `swarm_attack/qa/hooks/verifier_hook.py` | 32 tests | ✓ Complete |
| Bug Researcher Hook | `swarm_attack/qa/hooks/bug_researcher_hook.py` | 23 tests | ✓ Complete |
| CLI Commands | `swarm_attack/cli/qa_commands.py` | 37 tests | ✓ Complete |
| E2E Integration Tests | `tests/integration/qa/test_qa_e2e.py` | 25 tests | ✓ Complete |
| Real HTTP Validation | `tests/integration/qa/test_real_http.py` | 21 tests | ✓ Complete |

---

## Priority 7: CLI Command Integration Tests

Write integration tests that verify CLI commands work end-to-end.

### Test File Location

Create: `tests/integration/qa/test_cli_integration.py`

### Reference: CLI Commands to Test

Based on `swarm_attack/cli/qa_commands.py`:

1. **`swarm-attack qa test <target>`** - Run QA tests on target
2. **`swarm-attack qa health`** - Run health check
3. **`swarm-attack qa status [session_id]`** - Show QA session status
4. **`swarm-attack qa findings [--severity]`** - List QA findings
5. **`swarm-attack qa report <session_id>`** - Generate QA report

### TDD Requirements

1. Write ALL tests first in `test_cli_integration.py`
2. Tests should use Click's CliRunner for testing
3. Mock external dependencies (orchestrator, agents)
4. Verify output formatting and exit codes

### Test Structure

```python
"""CLI Integration Tests for QA Commands.

Tests the CLI interface for QA functionality:
- Command parsing and validation
- Output formatting
- Exit codes
- Error handling
"""

import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

class TestQATestCommand:
    """Tests for 'swarm-attack qa test' command."""

    def test_test_command_runs_qa(self):
        """Should run QA on specified target."""

    def test_test_command_accepts_depth_option(self):
        """Should accept --depth option."""

    def test_test_command_shows_results(self):
        """Should display test results."""

    def test_test_command_exits_nonzero_on_block(self):
        """Should exit with non-zero code on BLOCK recommendation."""


class TestQAHealthCommand:
    """Tests for 'swarm-attack qa health' command."""

    def test_health_command_runs_shallow_check(self):
        """Should run shallow health check."""

    def test_health_command_shows_endpoint_status(self):
        """Should display endpoint health status."""

    def test_health_command_exits_nonzero_on_failures(self):
        """Should exit with non-zero code on health failures."""


class TestQAStatusCommand:
    """Tests for 'swarm-attack qa status' command."""

    def test_status_shows_session_info(self):
        """Should display session information."""

    def test_status_shows_findings_summary(self):
        """Should display findings summary."""

    def test_status_without_session_lists_recent(self):
        """Should list recent sessions when no ID provided."""


class TestQAFindingsCommand:
    """Tests for 'swarm-attack qa findings' command."""

    def test_findings_lists_all_findings(self):
        """Should list all findings."""

    def test_findings_filters_by_severity(self):
        """Should filter by severity when --severity provided."""

    def test_findings_shows_empty_message(self):
        """Should show message when no findings."""


class TestQAReportCommand:
    """Tests for 'swarm-attack qa report' command."""

    def test_report_generates_markdown(self):
        """Should generate markdown report."""

    def test_report_includes_findings(self):
        """Should include findings in report."""

    def test_report_errors_on_invalid_session(self):
        """Should error when session not found."""
```

---

## Priority 8: Hook Registration Tests

Write tests that verify hooks are properly registered and triggered.

### Test File Location

Create: `tests/integration/qa/test_hook_registration.py`

### Scope

Test that hooks are properly:
- Registered in the pipeline
- Called at the right time
- Passed correct context
- Handle errors gracefully

### Test Structure

```python
"""Hook Registration Tests.

Tests that QA hooks are properly integrated into the pipeline.
"""

class TestVerifierHookRegistration:
    """Tests for Verifier hook registration."""

    def test_hook_registered_post_verification(self):
        """Hook should be registered to run after verification."""

    def test_hook_receives_verification_context(self):
        """Hook should receive full verification context."""

    def test_hook_skipped_on_verification_failure(self):
        """Hook should not run if verification failed."""


class TestBugResearcherHookRegistration:
    """Tests for BugResearcher hook registration."""

    def test_hook_registered_on_reproduction_failure(self):
        """Hook should be registered for reproduction failures."""

    def test_hook_receives_bug_context(self):
        """Hook should receive bug details."""

    def test_hook_provides_enhanced_reproduction(self):
        """Hook should provide enhanced reproduction data."""
```

---

## Priority 9: Skill Integration Tests

Write tests for Claude Code skill integration.

### Test File Location

Create: `tests/integration/qa/test_skill_integration.py`

### Scope

Test the QA-related skills:
- `qa-orchestrator` skill
- `qa-behavioral-tester` skill
- `qa-contract-validator` skill
- `qa-regression-scanner` skill

### Test Structure

```python
"""Skill Integration Tests.

Tests that QA skills work correctly with Claude Code.
"""

class TestQAOrchestratorSkill:
    """Tests for qa-orchestrator skill."""

    def test_skill_file_exists(self):
        """Skill definition file should exist."""

    def test_skill_has_required_sections(self):
        """Skill should have all required sections."""

    def test_skill_prompt_is_valid(self):
        """Skill prompt should be valid markdown."""


class TestQAAgentSkills:
    """Tests for individual QA agent skills."""

    def test_behavioral_tester_skill_exists(self):
        """Behavioral tester skill should exist."""

    def test_contract_validator_skill_exists(self):
        """Contract validator skill should exist."""

    def test_regression_scanner_skill_exists(self):
        """Regression scanner skill should exist."""
```

---

## Implementation Order

Follow strict TDD:

1. **Write CLI integration tests** in `tests/integration/qa/test_cli_integration.py`
2. **Run tests** - verify they fail initially
3. **Implement any missing CLI functionality**
4. **Verify all tests pass**

Then:

5. **Write hook registration tests** in `tests/integration/qa/test_hook_registration.py`
6. **Run tests** - verify they fail initially
7. **Implement any missing hook registration**
8. **Verify all tests pass**

Finally:

9. **Write skill integration tests** in `tests/integration/qa/test_skill_integration.py`
10. **Run tests** - verify they fail initially
11. **Verify skill files exist and are valid**
12. **Verify all tests pass**

---

## Verification

After implementation, run:

```bash
# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ -v

# Verify no regressions
PYTHONPATH=. python -m pytest tests/unit/ -v

# Check test count (should be 577+)
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ --collect-only | tail -5
```

Expected: All tests pass, including new CLI/Hook/Skill tests.

---

## Notes

- Use Click's CliRunner for CLI tests
- Mock orchestrator/agents to avoid external dependencies
- Test both success and error paths
- Verify exit codes match expected behavior
- Use `tmp_path` fixture for file-based tests
