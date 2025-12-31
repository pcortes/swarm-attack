# Changelog

All notable changes to Swarm Attack are documented here.

## [0.3.0] - 2025-12-29

### Major Features

#### Session Initialization Protocol
- **SessionInitializer** - 5-step initialization protocol for agent sessions
- **ProgressLogger** - Append-only progress tracking to `.swarm/features/{id}/progress.txt`
- **SessionFinalizer** - Ensures all feature tests pass before completion
- **VerificationTracker** - JSON-based verification status at `.swarm/features/{id}/verification.json`

#### Autopilot Event Infrastructure
- **EventBus** - Pub/sub system for agent communication with typed events
- **SwarmEvent** - 27 event types (SPEC_*, ISSUE_*, IMPL_*, BUG_*, SYSTEM_*, AUTO_*)
- **EventPersistence** - JSONL storage at `.swarm/events/events-YYYY-MM-DD.jsonl`
- **BaseAgent Integration** - `_emit_event()` method for all agents

#### Autopilot Auto-Approval System
- **SpecAutoApprover** - Auto-approves specs with score >= 0.85 after 2+ rounds
- **IssueAutoGreenlighter** - Auto-greenlights issues passing complexity gate
- **BugAutoApprover** - Auto-approves bug fixes with confidence >= 0.9 and low/medium risk
- **Manual Mode** - Override support for human-in-the-loop workflows
- **CLI Integration** - `swarm-attack approve --auto` and `--manual` flags

#### Universal Context Builder
- **Agent Context Profiles** - Per-agent context configuration (token budgets, depth levels)
- **Token Budget Management** - Coder: 15000 tokens, Verifier: 3000 tokens
- **BaseAgent Integration** - `with_context()` method for context injection

#### QA Session Extension
- **CoverageTracker** - Baseline capture and delta comparison for test coverage
- **RegressionDetector** - Severity-based regression detection (critical/moderate/none)
- **QASessionExtension** - Blocks on critical regressions or >10% coverage drops

#### Context Flow P0 Fixes
- **Modified File Tracking** - `_extract_outputs()` now tracks classes from modified files
- **Module Registry Enhancement** - Includes both created and modified file classes
- **Schema Drift Prevention** - Classes in modified files appear in context for subsequent issues

### Files Added
- `swarm_attack/session_initializer.py`
- `swarm_attack/progress_logger.py`
- `swarm_attack/session_finalizer.py`
- `swarm_attack/verification_tracker.py`
- `swarm_attack/events/types.py`
- `swarm_attack/events/bus.py`
- `swarm_attack/events/persistence.py`
- `swarm_attack/auto_approval/models.py`
- `swarm_attack/auto_approval/spec.py`
- `swarm_attack/auto_approval/issue.py`
- `swarm_attack/auto_approval/bug.py`
- `swarm_attack/auto_approval/overrides.py`
- `swarm_attack/universal_context_builder.py`
- `swarm_attack/qa/coverage_tracker.py`
- `swarm_attack/qa/regression_detector.py`
- `swarm_attack/qa/session_extension.py`

### Test Coverage
- 120+ new tests for v0.3.0 features
- All context flow integration tests passing (9/9)
- Session init tests passing (18/18)
- Event infrastructure tests passing (26/26)
- Auto-approval tests passing (22/22)

---

## [0.2.0] - 2025-12-29

### Bug Bash Fixes

This release includes comprehensive bug fixes from the bug bash session (BUG-1 through BUG-18).

#### Input Validation & Security

- **BUG-1/BUG-3: Path Traversal Prevention** - Feature and bug IDs now reject `..`, `/`, and `\` characters to prevent directory traversal attacks
- **Shell Metacharacter Validation** - IDs reject shell metacharacters (`$`, backticks, `|`, `;`, etc.)
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
