# Expert Team Prompt: Implement QA CLI Commands TDD

You are an expert team of software engineers implementing the QA CLI commands using TDD for the Adaptive QA Agent system.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system. The CLI provides user-facing commands to interact with the QA Orchestrator.

---

## What's Already Complete ✓

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| models.py | `swarm_attack/qa/models.py` | 20 tests | ✓ Complete |
| BehavioralTesterAgent | `swarm_attack/qa/agents/behavioral.py` | 33 tests | ✓ Complete |
| ContractValidatorAgent | `swarm_attack/qa/agents/contract.py` | 45 tests | ✓ Complete |
| RegressionScannerAgent | `swarm_attack/qa/agents/regression.py` | 53 tests | ✓ Complete |
| QAOrchestrator | `swarm_attack/qa/orchestrator.py` | 65 tests | ✓ Complete |
| Skill SKILL.md files | `.claude/skills/qa-*` | N/A | ✓ Complete |

**Total passing tests: 216**

---

## What Needs Implementation Now

| Component | File | Spec Sections | Test File |
|-----------|------|---------------|-----------|
| **QA CLI Commands** | `swarm_attack/cli/qa_commands.py` | 4.1-4.2 | `tests/unit/cli/test_qa_commands.py` |

---

## TDD Process (MUST FOLLOW)

1. **Write tests FIRST** in the test file
2. Run tests to confirm they fail
3. Implement the minimum code to make tests pass
4. Refactor if needed
5. Run full test suite to ensure no regressions

```bash
# Run tests for CLI commands
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
PYTHONPATH=. python -m pytest tests/unit/cli/test_qa_commands.py -v

# Run all tests
PYTHONPATH=. python -m pytest tests/unit/ -v
```

---

## QA CLI Requirements (Spec Section 4)

### Command Structure

```bash
# Top-level QA command group
swarm-attack qa <subcommand> [options]

# Subcommands:
swarm-attack qa test <target> [--depth shallow|standard|deep] [--base-url URL]
swarm-attack qa validate <feature> <issue> [--depth standard]
swarm-attack qa health [--base-url URL]
swarm-attack qa report [session_id] [--since YYYY-MM-DD] [--json]
swarm-attack qa bugs [--session session_id] [--severity critical|moderate|minor]
swarm-attack qa create-bugs <session_id> [--severity-threshold moderate]
```

### Command Implementations

```python
@click.group()
def qa():
    """Adaptive QA testing commands."""
    pass

@qa.command()
@click.argument("target")
@click.option("--depth", type=click.Choice(["shallow", "standard", "deep"]), default="standard")
@click.option("--base-url", default=None)
@click.option("--timeout", default=120)
def test(target: str, depth: str, base_url: str, timeout: int):
    """Test a specific area of the codebase."""
    ...

@qa.command()
@click.argument("feature")
@click.argument("issue", type=int)
@click.option("--depth", type=click.Choice(["shallow", "standard", "deep"]), default="standard")
def validate(feature: str, issue: int, depth: str):
    """Validate an implemented issue with behavioral tests."""
    ...

@qa.command()
@click.option("--base-url", default=None)
def health(base_url: str):
    """Run a quick health check on all endpoints."""
    ...

@qa.command()
@click.argument("session_id", required=False)
@click.option("--since", default=None)
@click.option("--json", "as_json", is_flag=True)
def report(session_id: str, since: str, as_json: bool):
    """View QA reports."""
    ...

@qa.command()
@click.option("--session", default=None)
@click.option("--severity", type=click.Choice(["critical", "moderate", "minor"]), default=None)
def bugs(session: str, severity: str):
    """List QA-discovered bugs."""
    ...

@qa.command("create-bugs")
@click.argument("session_id")
@click.option("--severity-threshold", type=click.Choice(["critical", "moderate", "minor"]), default="moderate")
def create_bugs(session_id: str, severity_threshold: str):
    """Create Bug Bash entries from QA findings."""
    ...
```

### Output Formatting

- Use `click.echo()` for normal output
- Use `click.secho()` with colors for status:
  - Green: success, healthy, pass
  - Yellow: warning, running
  - Red: failed, unhealthy, block
- Support `--json` flag for machine-readable output
- Display progress during long operations

### Integration with Orchestrator

```python
from swarm_attack.config import load_config
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.models import QADepth, QATrigger

config = load_config()
orchestrator = QAOrchestrator(config)
result = orchestrator.test(target=target, depth=QADepth(depth), ...)
```

---

## Test Categories to Write

1. **Import Tests** - Can import qa command group
2. **Command Registration Tests**
   - All commands registered under `qa` group
   - Commands have correct options/arguments
3. **qa test Command Tests**
   - Accepts target argument
   - Accepts --depth option
   - Accepts --base-url option
   - Calls orchestrator.test() correctly
   - Displays results appropriately
4. **qa validate Command Tests**
   - Accepts feature and issue arguments
   - Calls orchestrator.validate_issue()
   - Shows validation result
5. **qa health Command Tests**
   - Runs health check
   - Shows HEALTHY/UNHEALTHY status with color
6. **qa report Command Tests**
   - Lists sessions when no session_id
   - Shows specific report when session_id given
   - Supports --json output
   - Supports --since filter
7. **qa bugs Command Tests**
   - Lists bugs from findings
   - Filters by --session
   - Filters by --severity
   - Shows severity with color coding
8. **qa create-bugs Command Tests**
   - Creates bugs from session
   - Respects --severity-threshold
   - Shows created bug IDs
9. **Output Formatting Tests**
   - Colors used appropriately
   - JSON output valid
   - Progress shown for long ops
10. **Error Handling Tests**
    - Missing required arguments
    - Invalid session ID
    - Orchestrator errors handled gracefully

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/orchestrator.py` - Orchestrator to call
- `swarm_attack/qa/models.py` - Data models
- `swarm_attack/cli/` - Existing CLI patterns (if any)

**Existing tests for patterns:**
- `tests/unit/qa/test_orchestrator.py` - Mock patterns
- Click testing: Use `click.testing.CliRunner`

---

## Click Testing Pattern

```python
from click.testing import CliRunner
from swarm_attack.cli.qa_commands import qa

def test_qa_test_command():
    runner = CliRunner()
    result = runner.invoke(qa, ['test', '/api/users', '--depth', 'shallow'])
    assert result.exit_code == 0
    assert 'QA test' in result.output
```

---

## Verification Checklist

Before marking complete, verify:

- [ ] All tests pass: `PYTHONPATH=. python -m pytest tests/unit/cli/test_qa_commands.py -v`
- [ ] No regressions: Previous 216 tests still pass
- [ ] All commands implemented per spec
- [ ] Colors and formatting work correctly
- [ ] JSON output is valid
- [ ] Error handling is graceful
- [ ] Commands integrate with QAOrchestrator

---

## Instructions

1. Read existing patterns from `swarm_attack/qa/orchestrator.py`
2. Read Click documentation patterns
3. **Write comprehensive tests FIRST** in `tests/unit/cli/test_qa_commands.py`
4. Run tests to confirm they fail
5. Implement `swarm_attack/cli/qa_commands.py` to make tests pass
6. Run full test suite to verify no regressions
7. Pause for review

**Important:** Follow TDD strictly. Write tests first, then implement.
