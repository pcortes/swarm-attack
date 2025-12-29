# Changelog

All notable changes to Swarm Attack are documented here.

## [0.2.0] - 2025-12-29

### Bug Bash Fixes

This release includes comprehensive bug fixes from the bug bash session (BUG-1 through BUG-18).

#### Input Validation & Security

- **BUG-1/BUG-3: Path Traversal Prevention** - Feature and bug IDs now reject `..`, `/`, and `\` characters to prevent directory traversal attacks
- **BUG-6: Shell Metacharacter Validation** - IDs reject shell metacharacters (`$`, backticks, `|`, `;`, etc.)
- **BUG-9: Empty Description Validation** - `bug init` now rejects empty or whitespace-only descriptions
- **BUG-10: Positive Integer Validation** - Issue numbers must be >= 1 (enforced in `TaskRef` and CLI)
- **BUG-11: ID Format Validation** - Feature IDs must be lowercase alphanumeric with hyphens (max 64 chars)

#### Budget & Duration Validation

- **BUG-7/BUG-16: Budget Validation** - Autopilot budget must be positive (> 0)
- **BUG-8/BUG-12: Duration Validation** - Duration strings validated for format and positive values

#### Schema Drift Detection

- **BUG-4/BUG-18: Schema Drift Prevention** - Verifier now detects duplicate class definitions across modules
- **Subclass Detection** - Uses AST parsing to allow legitimate subclasses while flagging true duplicates

#### Code Extraction

- **BUG-2/BUG-6: LLM Code Extraction** - New `extract_code_from_response()` function strips markdown fences and LLM commentary from generated code

#### Error Handling

- **BUG-5: BACKOFF_SECONDS Export** - Fixed missing export in recovery module
- **BUG-12: Standup Error Handling** - Improved error handling in Chief of Staff standup command

#### Checkpoint Management

- **BUG-15: Stale Checkpoint Cleanup** - Checkpoints older than 8 days are automatically cleaned up when listing

#### Class Renames (pytest Collection Fix)

- **BUG-13/BUG-14/BUG-17: Test* Class Renames** - Renamed classes starting with `Test` to avoid pytest collection conflicts

| Old Name | New Name | Location |
|----------|----------|----------|
| `TestRunnerConfig` | `ExecutorConfig` | `swarm_attack/config.py` |
| `TestRunResult` | `ExecutionResult` | `swarm_attack/recovery.py` |
| `TestRunner` | `Executor` | `swarm_attack/recovery.py` |
| `TestFailureError` | `ExecutionFailureError` | `swarm_attack/edge_cases.py` |
| `TestFailureHandler` | `FailureHandler` | `swarm_attack/edge_cases.py` |
| `TestCase` | `BugTestCase` | `swarm_attack/bug_models.py` |
| `TestValidationGate` | `TestingValidationGate` | `swarm_attack/chief_of_staff/validation_gates.py` |
| `TestCritic` | `TestingCritic` | `swarm_attack/chief_of_staff/critics.py` |
| `TestFailureDiscoveryAgent` | `FailureDiscoveryAgent` | `swarm_attack/chief_of_staff/backlog_discovery/` |

**Backward Compatibility**: All renamed classes have aliases for backward compatibility. Existing imports continue to work.

#### pytest Configuration

- **BUG-17: pytest-asyncio Config** - Added `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` to `pyproject.toml`

### Files Changed

- `swarm_attack/agents/verifier.py` - Schema drift + subclass detection
- `swarm_attack/agents/coder.py` - Code extraction function
- `swarm_attack/cli/chief_of_staff.py` - Error handling + checkpoint cleanup
- `swarm_attack/cli/feature.py` - Input validation
- `swarm_attack/cli/bug.py` - Description validation
- `swarm_attack/models.py` - Issue number validation
- `swarm_attack/event_logger.py` - Issue validation
- `swarm_attack/config.py` - ExecutorConfig rename
- `swarm_attack/recovery.py` - Executor rename
- `swarm_attack/edge_cases.py` - FailureHandler rename
- `swarm_attack/bug_models.py` - BugTestCase rename
- `swarm_attack/chief_of_staff/*.py` - Various Test* renames
- `swarm_attack/validation/input_validator.py` - New validation module
- `pyproject.toml` - pytest-asyncio configuration

### Test Coverage

- 308+ tests passing
- New test files:
  - `tests/unit/test_candidates_validation.py`
  - `tests/unit/test_coder_code_extraction.py`
  - `tests/unit/test_class_naming.py`
  - `tests/unit/test_verifier_schema_drift.py`
  - `tests/unit/test_schema_drift_prevention.py`

---

## [0.1.0] - 2025-12-01

### Initial Release

- Feature Swarm Pipeline (PRD → Spec → Issues → Implementation → Verify)
- Bug Bash Pipeline (Reproduce → Analyze → Plan → Fix → Verify)
- Multi-agent debate system for spec generation
- Thick-agent implementation model
- Chief of Staff orchestration (standup, checkin, wrapup, autopilot)
- GitHub integration for issue management
