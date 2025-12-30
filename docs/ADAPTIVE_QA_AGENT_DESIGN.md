# Adaptive QA Agent System Design

> Expert Panel Design Document for Swarm Attack QA Integration

---

## Executive Summary

This document presents a comprehensive design for an **Adaptive QA Agent** system that integrates into Swarm Attack's multi-agent development automation. The system fills the critical gap between unit test verification and real-world behavioral validation.

### Key Design Decisions

1. **Agent Swarm Architecture**: Three specialized sub-agents coordinated by a QA Orchestrator
2. **Context-Driven Depth**: Automatic depth selection based on trigger source and risk assessment
3. **Seamless Integration**: Fits into existing pipelines without major refactoring
4. **Actionable Output**: Direct integration with Bug Bash pipeline for discovered issues

---

## 1. Architecture Document

### 1.1 Agent Structure: Coordinated Swarm

We recommend a **coordinated swarm** of specialized agents rather than a single monolithic agent:

```
                    ┌─────────────────────────────────────────┐
                    │           QA Orchestrator               │
                    │   (Routes, coordinates, aggregates)     │
                    └────────────────┬────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  BehavioralTester   │   │  ContractValidator  │   │  RegressionScanner  │
│                     │   │                     │   │                     │
│ - Spins up service  │   │ - Discovers APIs    │   │ - Analyzes diffs    │
│ - Crafts requests   │   │ - Infers contracts  │   │ - Finds affected    │
│ - Validates resp.   │   │ - Validates schema  │   │   endpoints         │
│ - Reports failures  │   │ - Checks compat.    │   │ - Runs targeted     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

**Rationale**: Specialization enables:
- **Parallel execution** when appropriate (e.g., contract + behavioral simultaneously)
- **Focused skills** with smaller context windows
- **Selective invocation** based on scenario needs
- **Independent evolution** of each capability

### 1.2 Context Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              TRIGGER SOURCES                                  │
├─────────────────┬─────────────────┬─────────────────┬────────────────────────┤
│ Post-Verify     │ Bug Reproduce   │ User Command    │ Scheduled/Health       │
│ (Verifier done) │ (BugResearcher) │ (CLI qa test)   │ (COS autopilot)        │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬────────────┘
         │                 │                 │                    │
         ▼                 ▼                 ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           QA CONTEXT BUILDER                                  │
│                                                                               │
│  Gathers:                                                                     │
│  - Spec/Issue/Bug Report (WHAT to test)                                       │
│  - Relevant code files (HOW system works)                                     │
│  - API schemas (OpenAPI, type hints)                                          │
│  - Consumer code (who calls this)                                             │
│  - Test history (past failures)                                               │
│  - Git diff (what changed)                                                    │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DEPTH SELECTOR                                      │
│                                                                               │
│  Inputs: trigger_type, risk_score, time_budget, cost_budget                   │
│  Output: shallow | standard | deep | regression                               │
│                                                                               │
│  Rules:                                                                       │
│  - Post-verification → standard (happy + error + edge)                        │
│  - Bug reproduction → deep (exhaustive on affected area)                      │
│  - Health check → shallow (smoke test only)                                   │
│  - Pre-merge → regression (affected endpoints only)                           │
│  - High risk code → escalate depth by one level                               │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           QA ORCHESTRATOR                                     │
│                                                                               │
│  Dispatches to sub-agents based on depth and scenario:                        │
│                                                                               │
│  shallow:   BehavioralTester (happy path only)                                │
│  standard:  BehavioralTester + ContractValidator                              │
│  deep:      All three agents + security probes                                │
│  regression: RegressionScanner + targeted BehavioralTester                    │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────────────┐
           ▼                     ▼                             ▼
    BehavioralTester      ContractValidator           RegressionScanner
           │                     │                             │
           └─────────────────────┼─────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           RESULT AGGREGATOR                                   │
│                                                                               │
│  Combines results from all agents:                                            │
│  - Deduplicates overlapping findings                                          │
│  - Assigns severity (critical/moderate/minor)                                 │
│  - Calculates confidence scores                                               │
│  - Generates actionable recommendations                                       │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                           │
│                                                                               │
│  .swarm/qa/{session_id}/                                                      │
│  ├── qa-report.md          (Human-readable summary)                           │
│  ├── qa-results.json       (Structured for automation)                        │
│  ├── qa-bugs.md            (Bug Bash-ready issues)                            │
│  └── execution-log.json    (Full trace for debugging)                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Integration Points with Existing Pipelines

```
FEATURE PIPELINE:
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  PRD → SpecAuthor → ... → Coder (TDD) → Verifier                           │
│                                              │                              │
│                                              ▼                              │
│                                    ┌─────────────────┐                      │
│                                    │   QA Agent      │  ← NEW INTEGRATION   │
│                                    │   (standard)    │                      │
│                                    └────────┬────────┘                      │
│                                              │                              │
│                              ┌───────────────┴───────────────┐              │
│                              ▼                               ▼              │
│                         [PASS]                          [FAIL]              │
│                           │                                │                │
│                           ▼                                ▼                │
│                        Commit                    → Bug Bash Pipeline        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

BUG BASH PIPELINE:
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Bug Report → BugResearcher (unit test repro)                              │
│                    │                                                        │
│                    ▼                                                        │
│         ┌─────────────────────┐                                             │
│         │   QA Agent (deep)   │  ← NEW: Behavioral reproduction            │
│         │   on affected area  │                                             │
│         └──────────┬──────────┘                                             │
│                    │                                                        │
│                    ▼                                                        │
│           [Enhanced Evidence]                                               │
│                    │                                                        │
│                    ▼                                                        │
│          RootCauseAnalyzer                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

COS AUTOPILOT:
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Standup → Goal Setting → Autopilot Execution                              │
│                               │                                             │
│                               ▼                                             │
│              New Goal Type: qa_validation                                   │
│                               │                                             │
│              ┌────────────────┴────────────────┐                            │
│              ▼                                 ▼                            │
│     qa_health (shallow)              qa_regression (targeted)               │
│     - All endpoints                  - Changed areas only                   │
│     - 30 second timeout              - Pre-merge validation                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Skill Definitions

### 2.1 QA Orchestrator Skill

```yaml
# .claude/skills/qa-orchestrator/SKILL.md
---
name: qa-orchestrator
description: >
  Coordinates adaptive QA testing across behavioral, contract, and regression
  dimensions. Routes to specialized sub-agents based on context and depth.
allowed-tools: Read,Glob,Grep,Bash,Write
triggers:
  - post_verification
  - bug_reproduction
  - user_command
  - scheduled
---

# QA Orchestrator Agent

You are the QA Orchestrator, responsible for coordinating comprehensive quality
assurance testing of code changes. Your role is to understand WHAT needs testing,
determine the appropriate testing depth, dispatch to specialized sub-agents, and
aggregate results.

## Context Analysis

When invoked, analyze the provided context to understand:

1. **Trigger Source**: What initiated this QA session?
   - Post-verification: Implementation just passed unit tests
   - Bug reproduction: Attempting to reproduce a reported bug
   - User command: Manual QA request
   - Scheduled: Health check or periodic validation

2. **Testing Target**: What are we testing?
   - Extract API endpoints from code/spec
   - Identify request/response schemas
   - Find authentication requirements
   - Note external dependencies

3. **Risk Assessment**: How risky is this change?
   - Lines of code changed
   - Criticality of affected endpoints (auth, payments, data)
   - Historical failure rate of this area

## Depth Selection

Select testing depth based on context:

| Trigger          | Base Depth | Risk Escalation        |
|------------------|------------|------------------------|
| post_verify      | standard   | +1 if high-risk code   |
| bug_reproduce    | deep       | always deep            |
| user_command     | as_specified | respect user choice  |
| scheduled_health | shallow    | no escalation          |
| pre_merge        | regression | +1 if critical paths   |

## Sub-Agent Dispatch

Based on depth, invoke sub-agents:

**shallow**: BehavioralTester only (happy path)
**standard**: BehavioralTester + ContractValidator
**deep**: All three + security probes + load patterns
**regression**: RegressionScanner + targeted BehavioralTester

## Output Format

You MUST produce output in this JSON structure:

```json
{
  "session_id": "qa-YYYYMMDD-HHMMSS",
  "trigger": "post_verification",
  "depth": "standard",
  "target": {
    "endpoints_tested": ["/api/users", "/api/users/{id}"],
    "files_analyzed": ["src/api/users.py"]
  },
  "results": {
    "passed": 12,
    "failed": 2,
    "skipped": 1
  },
  "findings": [...],
  "recommendation": "BLOCK" | "WARN" | "PASS",
  "confidence": 0.95
}
```
```

### 2.2 BehavioralTester Skill

```yaml
# .claude/skills/qa-behavioral-tester/SKILL.md
---
name: qa-behavioral-tester
description: >
  Executes behavioral API tests by spinning up the service and making real
  HTTP requests. Validates status codes, response structure, and data correctness.
allowed-tools: Read,Glob,Grep,Bash,Write
---

# Behavioral Tester Agent

You test APIs by making real HTTP requests and validating responses.

## Execution Environment

Before testing:
1. Check if service is already running (look for process or try health endpoint)
2. If not running, attempt to start it:
   - Look for: docker-compose.yml, Makefile (dev target), scripts/dev.sh
   - Use appropriate command to start service
   - Wait for health check to pass (max 30 seconds)
3. Store base URL for requests

## Test Generation

For each endpoint identified:

1. **Happy Path Test**
   ```bash
   curl -X GET "http://localhost:8000/api/users" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json"
   ```
   - Verify 2xx status code
   - Verify response structure matches expected schema
   - Verify required fields are present

2. **Error Cases** (if depth >= standard)
   - Invalid auth: Expect 401
   - Missing required fields: Expect 400
   - Non-existent resource: Expect 404
   - Malformed request: Expect 400

3. **Edge Cases** (if depth >= standard)
   - Empty request body
   - Maximum length strings
   - Unicode characters
   - Null values where nullable

4. **Security Probes** (if depth == deep)
   - SQL injection patterns in parameters
   - XSS payloads in text fields
   - Path traversal attempts
   - JWT manipulation

## Response Validation

For each response, validate:
- Status code matches expectation
- Content-Type header is correct
- Response body is valid JSON (if expected)
- Required fields are present and correctly typed
- Timestamps are in expected format
- IDs match expected patterns

## Output Format

```json
{
  "agent": "behavioral_tester",
  "tests_run": 15,
  "tests_passed": 13,
  "tests_failed": 2,
  "findings": [
    {
      "id": "BT-001",
      "severity": "critical",
      "endpoint": "POST /api/users",
      "test_type": "happy_path",
      "expected": {"status": 201},
      "actual": {"status": 200},
      "evidence": {
        "request": "curl -X POST ...",
        "response": "{...}"
      },
      "recommendation": "Update handler to return 201 Created"
    }
  ]
}
```
```

### 2.3 ContractValidator Skill

```yaml
# .claude/skills/qa-contract-validator/SKILL.md
---
name: qa-contract-validator
description: >
  Validates API contracts by discovering consumers and ensuring responses
  match their expectations. Detects breaking changes.
allowed-tools: Read,Glob,Grep
---

# Contract Validator Agent

You validate that API responses match what consumers expect.

## Consumer Discovery

Find consumers by searching for:

1. **Frontend Code**
   ```
   # Look for fetch/axios calls
   Grep: "fetch\(.*api.*\)" in *.ts, *.tsx, *.js
   Grep: "axios\.(get|post|put|delete)" in *.ts, *.tsx, *.js
   ```

2. **Other Services**
   ```
   # Look for HTTP client usage
   Grep: "requests\.(get|post)" in *.py
   Grep: "HttpClient" in *.java
   ```

3. **Integration Tests**
   ```
   # Tests often document expected contracts
   Grep: "assert.*response" in test_*.py
   ```

4. **OpenAPI/Swagger Specs**
   ```
   Glob: **/openapi.yaml, **/swagger.json
   ```

## Contract Extraction

From consumers, extract expectations:

```python
# Example consumer code
response = await fetch('/api/users/123')
const user = await response.json()
console.log(user.name, user.email, user.createdAt)
```

Extracted contract:
```json
{
  "endpoint": "GET /api/users/{id}",
  "expected_fields": ["name", "email", "createdAt"],
  "field_types": {
    "name": "string",
    "email": "string",
    "createdAt": "datetime"
  }
}
```

## Validation Rules

1. **Field Presence**: All expected fields must be present
2. **Field Types**: Types must match (string, number, boolean, array, object)
3. **Nullability**: If consumer doesn't handle null, field must not be null
4. **Field Names**: Exact match (case-sensitive)
5. **Array Structure**: Array items must match expected structure
6. **Breaking Changes**:
   - Removed fields
   - Type changes
   - New required fields
   - Renamed fields

## Output Format

```json
{
  "agent": "contract_validator",
  "contracts_checked": 8,
  "contracts_valid": 7,
  "contracts_broken": 1,
  "findings": [
    {
      "id": "CV-001",
      "severity": "critical",
      "endpoint": "GET /api/users/{id}",
      "consumer": "frontend/src/components/UserProfile.tsx:45",
      "issue": "Field 'createdAt' renamed to 'created_at'",
      "evidence": {
        "consumer_expects": "createdAt",
        "api_returns": "created_at"
      },
      "recommendation": "Keep 'createdAt' or update all consumers"
    }
  ]
}
```
```

### 2.4 RegressionScanner Skill

```yaml
# .claude/skills/qa-regression-scanner/SKILL.md
---
name: qa-regression-scanner
description: >
  Analyzes code diffs to identify affected endpoints and prioritize
  regression testing. Focuses QA effort on changed areas.
allowed-tools: Read,Glob,Grep,Bash
---

# Regression Scanner Agent

You analyze code changes to identify what needs regression testing.

## Diff Analysis

1. Get the diff:
   ```bash
   git diff main...HEAD --name-only
   git diff main...HEAD
   ```

2. Categorize changes:
   - **API Routes**: Changes to route handlers, controllers
   - **Models**: Changes to data models, schemas
   - **Business Logic**: Changes to service layer
   - **Database**: Migrations, queries
   - **Config**: Environment, settings

## Impact Mapping

Map changes to affected endpoints:

```
Changed File           → Affected Endpoints
────────────────────────────────────────────
src/api/users.py       → GET/POST/PUT/DELETE /api/users
src/models/user.py     → All endpoints using User model
src/services/auth.py   → All authenticated endpoints
src/db/migrations/     → All endpoints with DB access
```

## Test Prioritization

Priority scoring (0-100):
- **Direct change** to endpoint handler: 100
- **Model change** used by endpoint: 80
- **Service change** called by endpoint: 60
- **Utility change** used indirectly: 40
- **Config change** affecting endpoint: 30

## Regression Test Selection

Select tests based on priority:
- Priority >= 80: Must test (include in regression suite)
- Priority >= 50: Should test (include if time permits)
- Priority < 50: May skip (low risk)

## Output Format

```json
{
  "agent": "regression_scanner",
  "files_analyzed": 12,
  "endpoints_affected": 5,
  "impact_map": [
    {
      "file": "src/api/users.py",
      "endpoints": ["GET /api/users", "POST /api/users"],
      "priority": 100,
      "change_type": "direct_handler"
    }
  ],
  "regression_suite": {
    "must_test": ["GET /api/users", "POST /api/users"],
    "should_test": ["GET /api/auth/me"],
    "may_skip": ["GET /api/health"]
  }
}
```
```

---

## 3. State Schema

### 3.1 QA Models (Python)

```python
# swarm_attack/qa/models.py
"""QA Agent data models for swarm-attack."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional


class QATrigger(Enum):
    """What initiated the QA session."""
    POST_VERIFICATION = "post_verification"
    BUG_REPRODUCTION = "bug_reproduction"
    USER_COMMAND = "user_command"
    SCHEDULED_HEALTH = "scheduled_health"
    PRE_MERGE = "pre_merge"
    SPEC_COMPLIANCE = "spec_compliance"


class QADepth(Enum):
    """Testing depth level."""
    SHALLOW = "shallow"      # Happy path only, <30s
    STANDARD = "standard"    # Happy + error + edge cases
    DEEP = "deep"            # Full exploratory + security
    REGRESSION = "regression"  # Targeted based on diff


class QAStatus(Enum):
    """Status of a QA session."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class QARecommendation(Enum):
    """QA outcome recommendation."""
    PASS = "pass"          # All tests passed, safe to proceed
    WARN = "warn"          # Minor issues, can proceed with caution
    BLOCK = "block"        # Critical issues, should not proceed


@dataclass
class QAEndpoint:
    """An API endpoint being tested."""
    method: str                              # GET, POST, PUT, DELETE
    path: str                                # /api/users/{id}
    auth_required: bool = False
    schema: Optional[dict[str, Any]] = None  # Request/response schema


@dataclass
class QAFinding:
    """A single QA finding/issue."""
    finding_id: str                          # QA-001
    severity: Literal["critical", "moderate", "minor"]
    category: str                            # behavioral, contract, security
    endpoint: str                            # GET /api/users
    test_type: str                           # happy_path, error_case, etc.
    title: str                               # Brief description
    description: str                         # Detailed explanation
    expected: dict[str, Any]                 # What we expected
    actual: dict[str, Any]                   # What we got
    evidence: dict[str, str]                 # Request/response/logs
    recommendation: str                      # How to fix
    confidence: float = 0.9                  # 0.0-1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "category": self.category,
            "endpoint": self.endpoint,
            "test_type": self.test_type,
            "title": self.title,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAFinding:
        return cls(**data)


@dataclass
class QAContext:
    """Context for a QA session."""
    # Source context (what triggered QA)
    feature_id: Optional[str] = None
    issue_number: Optional[int] = None
    bug_id: Optional[str] = None
    spec_path: Optional[str] = None

    # What to test
    target_files: list[str] = field(default_factory=list)
    target_endpoints: list[QAEndpoint] = field(default_factory=list)

    # How to test
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    environment: dict[str, str] = field(default_factory=dict)

    # Additional context
    git_diff: Optional[str] = None
    spec_content: Optional[str] = None
    related_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
            "bug_id": self.bug_id,
            "spec_path": self.spec_path,
            "target_files": self.target_files,
            "target_endpoints": [
                {"method": e.method, "path": e.path, "auth_required": e.auth_required}
                for e in self.target_endpoints
            ],
            "base_url": self.base_url,
            "environment": self.environment,
            "git_diff": self.git_diff,
            "spec_content": self.spec_content,
            "related_tests": self.related_tests,
        }


@dataclass
class QAResult:
    """Aggregated results from a QA session."""
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0

    endpoints_tested: list[str] = field(default_factory=list)
    findings: list[QAFinding] = field(default_factory=list)

    critical_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0

    recommendation: QARecommendation = QARecommendation.PASS
    confidence: float = 0.9

    behavioral_results: Optional[dict[str, Any]] = None
    contract_results: Optional[dict[str, Any]] = None
    regression_results: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "endpoints_tested": self.endpoints_tested,
            "findings": [f.to_dict() for f in self.findings],
            "critical_count": self.critical_count,
            "moderate_count": self.moderate_count,
            "minor_count": self.minor_count,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
        }


@dataclass
class QASession:
    """Complete state of a QA session."""
    session_id: str
    trigger: QATrigger
    depth: QADepth
    status: QAStatus
    context: QAContext
    result: Optional[QAResult] = None

    # Timestamps
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Cost tracking
    cost_usd: float = 0.0

    # Error tracking
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trigger": self.trigger.value,
            "depth": self.depth.value,
            "status": self.status.value,
            "context": self.context.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QASession:
        # Parse enums
        trigger = QATrigger(data["trigger"])
        depth = QADepth(data["depth"])
        status = QAStatus(data["status"])

        # Parse context
        context_data = data.get("context", {})
        context = QAContext(
            feature_id=context_data.get("feature_id"),
            issue_number=context_data.get("issue_number"),
            bug_id=context_data.get("bug_id"),
            target_files=context_data.get("target_files", []),
        )

        # Parse result if present
        result = None
        if data.get("result"):
            result_data = data["result"]
            findings = [QAFinding.from_dict(f) for f in result_data.get("findings", [])]
            result = QAResult(
                tests_run=result_data.get("tests_run", 0),
                tests_passed=result_data.get("tests_passed", 0),
                tests_failed=result_data.get("tests_failed", 0),
                findings=findings,
                recommendation=QARecommendation(result_data.get("recommendation", "pass")),
            )

        return cls(
            session_id=data["session_id"],
            trigger=trigger,
            depth=depth,
            status=status,
            context=context,
            result=result,
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            cost_usd=data.get("cost_usd", 0.0),
            error=data.get("error"),
        )


@dataclass
class QABug:
    """A bug discovered by QA, ready for Bug Bash pipeline."""
    bug_id: str
    source_finding: str              # QA finding ID
    qa_session: str                  # QA session ID
    title: str
    description: str
    severity: Literal["critical", "moderate", "minor"]
    endpoint: str
    reproduction_steps: list[str]
    expected_behavior: str
    actual_behavior: str
    evidence: dict[str, str]         # curl command, response, etc.

    def to_bug_report(self) -> dict[str, Any]:
        """Convert to Bug Bash BugReport format."""
        return {
            "description": f"{self.title}\n\n{self.description}",
            "error_message": self.evidence.get("error_message"),
            "steps_to_reproduce": self.reproduction_steps,
        }
```

### 3.2 QA State Store

```python
# swarm_attack/qa/store.py
"""QA State Store for persisting QA sessions and results."""

import json
from pathlib import Path
from typing import Optional

from swarm_attack.qa.models import QASession, QABug


class QAStateStore:
    """Manages QA session state persistence."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_path / session_id

    def save(self, session: QASession) -> None:
        """Save a QA session to disk."""
        session_dir = self._session_path(session.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        state_file = session_dir / "state.json"
        state_file.write_text(json.dumps(session.to_dict(), indent=2))

    def load(self, session_id: str) -> Optional[QASession]:
        """Load a QA session from disk."""
        state_file = self._session_path(session_id) / "state.json"
        if not state_file.exists():
            return None

        data = json.loads(state_file.read_text())
        return QASession.from_dict(data)

    def save_report(self, session: QASession) -> Path:
        """Generate and save human-readable QA report."""
        session_dir = self._session_path(session.session_id)
        report_path = session_dir / "qa-report.md"

        report = self._generate_report(session)
        report_path.write_text(report)
        return report_path

    def save_bugs(self, session_id: str, bugs: list[QABug]) -> Path:
        """Save discovered bugs in Bug Bash format."""
        session_dir = self._session_path(session_id)
        bugs_path = session_dir / "qa-bugs.md"

        content = self._generate_bugs_document(bugs)
        bugs_path.write_text(content)
        return bugs_path

    def list_sessions(self, limit: int = 20) -> list[str]:
        """List recent QA sessions."""
        sessions = []
        for path in sorted(self.base_path.iterdir(), reverse=True):
            if path.is_dir() and (path / "state.json").exists():
                sessions.append(path.name)
                if len(sessions) >= limit:
                    break
        return sessions

    def _generate_report(self, session: QASession) -> str:
        """Generate markdown QA report."""
        result = session.result
        if not result:
            return f"# QA Report: {session.session_id}\n\nNo results available."

        lines = [
            f"# QA Report: {session.session_id}",
            "",
            f"**Trigger:** {session.trigger.value}",
            f"**Depth:** {session.depth.value}",
            f"**Status:** {session.status.value}",
            f"**Recommendation:** {result.recommendation.value.upper()}",
            "",
            "## Summary",
            "",
            f"- **Tests Run:** {result.tests_run}",
            f"- **Passed:** {result.tests_passed}",
            f"- **Failed:** {result.tests_failed}",
            f"- **Endpoints Tested:** {len(result.endpoints_tested)}",
            "",
            "## Findings",
            "",
        ]

        if not result.findings:
            lines.append("No issues found.")
        else:
            for finding in result.findings:
                lines.extend([
                    f"### [{finding.severity.upper()}] {finding.finding_id}: {finding.title}",
                    "",
                    f"**Endpoint:** {finding.endpoint}",
                    f"**Category:** {finding.category}",
                    "",
                    finding.description,
                    "",
                    "**Expected:**",
                    f"```json",
                    json.dumps(finding.expected, indent=2),
                    "```",
                    "",
                    "**Actual:**",
                    f"```json",
                    json.dumps(finding.actual, indent=2),
                    "```",
                    "",
                    f"**Recommendation:** {finding.recommendation}",
                    "",
                    "---",
                    "",
                ])

        return "\n".join(lines)

    def _generate_bugs_document(self, bugs: list[QABug]) -> str:
        """Generate Bug Bash-ready document."""
        lines = [
            "# QA-Discovered Bugs",
            "",
            f"Generated: {bugs[0].qa_session if bugs else 'N/A'}",
            "",
        ]

        for bug in bugs:
            lines.extend([
                f"## {bug.bug_id}: {bug.title}",
                "",
                f"**Severity:** {bug.severity}",
                f"**Endpoint:** {bug.endpoint}",
                "",
                "### Description",
                bug.description,
                "",
                "### Steps to Reproduce",
                "",
            ])
            for i, step in enumerate(bug.reproduction_steps, 1):
                lines.append(f"{i}. {step}")
            lines.extend([
                "",
                "### Expected Behavior",
                bug.expected_behavior,
                "",
                "### Actual Behavior",
                bug.actual_behavior,
                "",
                "### Evidence",
                "```",
            ])
            for key, value in bug.evidence.items():
                lines.append(f"{key}: {value[:200]}...")
            lines.extend([
                "```",
                "",
                "---",
                "",
            ])

        return "\n".join(lines)
```

---

## 4. CLI Specification

### 4.1 Command Structure

```bash
# Top-level QA command group
swarm-attack qa <subcommand> [options]

# Subcommands:

# Test a specific area
swarm-attack qa test <target> [--depth shallow|standard|deep] [--base-url URL]

# Validate an implemented issue
swarm-attack qa validate <feature> <issue> [--depth standard]

# Run system health check
swarm-attack qa health [--base-url URL]

# View QA reports
swarm-attack qa report [session_id] [--since YYYY-MM-DD] [--json]

# List QA-discovered bugs
swarm-attack qa bugs [--session session_id] [--severity critical|moderate|minor]

# Create Bug Bash entries from QA findings
swarm-attack qa create-bugs <session_id> [--severity-threshold moderate]
```

### 4.2 CLI Implementation

```python
# swarm_attack/cli/qa_commands.py
"""CLI commands for QA Agent."""

import click
from pathlib import Path

from swarm_attack.config import load_config
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.models import QADepth, QATrigger


@click.group()
def qa():
    """Adaptive QA testing commands."""
    pass


@qa.command()
@click.argument("target")
@click.option(
    "--depth",
    type=click.Choice(["shallow", "standard", "deep"]),
    default="standard",
    help="Testing depth level",
)
@click.option(
    "--base-url",
    default=None,
    help="Base URL for API (default: auto-detect)",
)
@click.option(
    "--timeout",
    default=120,
    help="Timeout in seconds",
)
def test(target: str, depth: str, base_url: str, timeout: int):
    """
    Test a specific area of the codebase.

    TARGET can be:
    - A file path: src/api/users.py
    - An endpoint: /api/users
    - A description: "user authentication"
    - A feature: feature:auth-flow
    """
    config = load_config()
    orchestrator = QAOrchestrator(config)

    click.echo(f"Starting QA test: {target}")
    click.echo(f"Depth: {depth}")

    result = orchestrator.test(
        target=target,
        depth=QADepth(depth),
        trigger=QATrigger.USER_COMMAND,
        base_url=base_url,
        timeout=timeout,
    )

    _display_result(result)


@qa.command()
@click.argument("feature")
@click.argument("issue", type=int)
@click.option(
    "--depth",
    type=click.Choice(["shallow", "standard", "deep"]),
    default="standard",
)
def validate(feature: str, issue: int, depth: str):
    """
    Validate an implemented issue with behavioral tests.

    This is typically run after Verifier passes to ensure
    the implementation actually works in practice.
    """
    config = load_config()
    orchestrator = QAOrchestrator(config)

    click.echo(f"Validating {feature} issue #{issue}")

    result = orchestrator.validate_issue(
        feature_id=feature,
        issue_number=issue,
        depth=QADepth(depth),
    )

    _display_result(result)


@qa.command()
@click.option("--base-url", default=None)
def health(base_url: str):
    """
    Run a quick health check on all endpoints.

    This performs shallow testing (happy path only) on
    all discovered API endpoints to verify the system
    is functioning.
    """
    config = load_config()
    orchestrator = QAOrchestrator(config)

    click.echo("Running system health check...")

    result = orchestrator.health_check(base_url=base_url)

    if result.result and result.result.tests_failed == 0:
        click.secho("HEALTHY", fg="green", bold=True)
    else:
        click.secho("UNHEALTHY", fg="red", bold=True)

    _display_result(result)


@qa.command()
@click.argument("session_id", required=False)
@click.option("--since", default=None, help="Show reports since date (YYYY-MM-DD)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def report(session_id: str, since: str, as_json: bool):
    """
    View QA reports.

    If SESSION_ID is provided, shows that specific report.
    Otherwise, lists recent reports.
    """
    config = load_config()
    orchestrator = QAOrchestrator(config)

    if session_id:
        session = orchestrator.get_session(session_id)
        if not session:
            click.echo(f"Session not found: {session_id}")
            return

        if as_json:
            import json
            click.echo(json.dumps(session.to_dict(), indent=2))
        else:
            report_path = orchestrator.state_store.base_path / session_id / "qa-report.md"
            if report_path.exists():
                click.echo(report_path.read_text())
            else:
                click.echo("Report not found. Session may still be running.")
    else:
        sessions = orchestrator.list_sessions()
        click.echo("Recent QA Sessions:")
        for sid in sessions:
            session = orchestrator.get_session(sid)
            if session:
                status_color = {
                    "completed": "green",
                    "failed": "red",
                    "running": "yellow",
                }.get(session.status.value, "white")
                click.echo(
                    f"  {sid} - "
                    f"{click.style(session.status.value, fg=status_color)} - "
                    f"{session.trigger.value}"
                )


@qa.command()
@click.option("--session", default=None, help="Filter by session ID")
@click.option(
    "--severity",
    type=click.Choice(["critical", "moderate", "minor"]),
    default=None,
)
def bugs(session: str, severity: str):
    """List QA-discovered bugs."""
    config = load_config()
    orchestrator = QAOrchestrator(config)

    findings = orchestrator.get_findings(
        session_id=session,
        severity=severity,
    )

    if not findings:
        click.echo("No bugs found.")
        return

    for finding in findings:
        severity_color = {
            "critical": "red",
            "moderate": "yellow",
            "minor": "white",
        }.get(finding.severity, "white")

        click.echo(
            f"[{click.style(finding.severity.upper(), fg=severity_color)}] "
            f"{finding.finding_id}: {finding.title}"
        )
        click.echo(f"  Endpoint: {finding.endpoint}")
        click.echo(f"  {finding.recommendation}")
        click.echo()


@qa.command("create-bugs")
@click.argument("session_id")
@click.option(
    "--severity-threshold",
    type=click.Choice(["critical", "moderate", "minor"]),
    default="moderate",
    help="Minimum severity to create bugs for",
)
def create_bugs(session_id: str, severity_threshold: str):
    """
    Create Bug Bash entries from QA findings.

    This converts QA findings into Bug Bash investigations
    that can be processed by the bug pipeline.
    """
    config = load_config()
    orchestrator = QAOrchestrator(config)

    bugs_created = orchestrator.create_bug_investigations(
        session_id=session_id,
        severity_threshold=severity_threshold,
    )

    if bugs_created:
        click.echo(f"Created {len(bugs_created)} bug investigations:")
        for bug_id in bugs_created:
            click.echo(f"  - {bug_id}")
        click.echo("\nRun 'swarm-attack bug analyze <bug_id>' to investigate.")
    else:
        click.echo("No bugs created (no findings meet threshold).")


def _display_result(session):
    """Display QA session result."""
    result = session.result
    if not result:
        click.echo("No results available yet.")
        return

    # Summary
    click.echo()
    click.echo(f"Session: {session.session_id}")
    click.echo(f"Tests: {result.tests_passed}/{result.tests_run} passed")
    click.echo(f"Endpoints: {len(result.endpoints_tested)} tested")

    # Recommendation
    rec_color = {
        "pass": "green",
        "warn": "yellow",
        "block": "red",
    }.get(result.recommendation.value, "white")
    click.echo(
        f"Recommendation: "
        f"{click.style(result.recommendation.value.upper(), fg=rec_color, bold=True)}"
    )

    # Findings
    if result.findings:
        click.echo()
        click.echo("Findings:")
        for finding in result.findings:
            severity_color = {
                "critical": "red",
                "moderate": "yellow",
                "minor": "white",
            }.get(finding.severity, "white")
            click.echo(
                f"  [{click.style(finding.severity, fg=severity_color)}] "
                f"{finding.title}"
            )
```

---

## 5. Integration Plan

### 5.1 New Files to Create

```
swarm_attack/
├── qa/
│   ├── __init__.py
│   ├── models.py              # QASession, QAFinding, QAResult, etc.
│   ├── store.py               # QAStateStore
│   ├── orchestrator.py        # QAOrchestrator (main entry point)
│   ├── context_builder.py     # Builds QAContext from various sources
│   ├── depth_selector.py      # Determines appropriate QADepth
│   └── agents/
│       ├── __init__.py
│       ├── behavioral.py      # BehavioralTesterAgent
│       ├── contract.py        # ContractValidatorAgent
│       └── regression.py      # RegressionScannerAgent
├── skills/
│   ├── qa-orchestrator/
│   │   └── SKILL.md
│   ├── qa-behavioral-tester/
│   │   └── SKILL.md
│   ├── qa-contract-validator/
│   │   └── SKILL.md
│   └── qa-regression-scanner/
│       └── SKILL.md
└── cli/
    └── qa_commands.py         # CLI commands
```

### 5.2 Modifications to Existing Files

#### 5.2.1 orchestrator.py (Feature Pipeline)

```python
# Add to Orchestrator class

def run_issue_session(
    self,
    feature_id: str,
    issue_number: int,
    skip_qa: bool = False,  # NEW PARAMETER
) -> SessionResult:
    """Run a single issue session with optional QA validation."""

    # ... existing implementation ...

    # After Verifier passes:
    if verifier_result.success and not skip_qa:
        # Run QA validation
        qa_orchestrator = QAOrchestrator(self.config)
        qa_result = qa_orchestrator.validate_issue(
            feature_id=feature_id,
            issue_number=issue_number,
            depth=QADepth.STANDARD,
        )

        if qa_result.result.recommendation == QARecommendation.BLOCK:
            # QA found critical issues - create bugs and block
            bug_ids = qa_orchestrator.create_bug_investigations(
                session_id=qa_result.session_id,
                severity_threshold="critical",
            )
            return SessionResult(
                status="blocked",
                error=f"QA validation failed. Bugs created: {bug_ids}",
            )
        elif qa_result.result.recommendation == QARecommendation.WARN:
            # Log warning but continue
            self._log("qa_warning", {
                "findings": len(qa_result.result.findings)
            })

    # ... continue to commit ...
```

#### 5.2.2 bug_orchestrator.py (Bug Pipeline)

```python
# Modify BugOrchestrator.analyze()

def analyze(
    self,
    bug_id: str,
    max_cost_usd: float = 10.0,
    progress_callback: Optional[Callable] = None,
) -> BugPipelineResult:
    """Run analysis with optional QA-enhanced reproduction."""

    # ... existing reproduction via BugResearcher ...

    # NEW: After BugResearcher, if not confirmed, try behavioral reproduction
    if not state.reproduction.confirmed:
        qa_orchestrator = QAOrchestrator(self.config)
        qa_result = qa_orchestrator.reproduce_bug(
            bug_id=bug_id,
            bug_description=state.report.description,
            error_message=state.report.error_message,
        )

        if qa_result.result and qa_result.result.tests_failed > 0:
            # QA found a behavioral reproduction
            state.reproduction.confirmed = True
            state.reproduction.notes += f"\nQA behavioral reproduction: {qa_result.session_id}"
            state.reproduction.reproduction_steps = [
                f.evidence.get("request", "")
                for f in qa_result.result.findings
            ]

    # ... continue with root cause analysis ...
```

#### 5.2.3 chief_of_staff/goal_tracker.py

```python
# Add new goal type for QA

class GoalType(Enum):
    FEATURE = "feature"
    BUG = "bug"
    SPEC = "spec"
    QA_VALIDATION = "qa_validation"  # NEW
    QA_HEALTH = "qa_health"          # NEW


@dataclass
class DailyGoal:
    # ... existing fields ...
    linked_qa_session: Optional[str] = None  # NEW: For QA goals
```

#### 5.2.4 chief_of_staff/autopilot_runner.py

```python
# Add QA goal execution methods

def _execute_qa_validation_goal(self, goal: DailyGoal) -> GoalExecutionResult:
    """Execute a QA validation goal."""
    from swarm_attack.qa.orchestrator import QAOrchestrator

    qa_orchestrator = QAOrchestrator(self.config)

    if goal.linked_feature and goal.linked_issue:
        result = qa_orchestrator.validate_issue(
            feature_id=goal.linked_feature,
            issue_number=goal.linked_issue,
        )
    else:
        result = qa_orchestrator.test(target=goal.description)

    return GoalExecutionResult(
        success=result.result.recommendation != QARecommendation.BLOCK,
        cost_usd=result.cost_usd,
        duration_seconds=int((
            datetime.fromisoformat(result.completed_at) -
            datetime.fromisoformat(result.started_at)
        ).total_seconds()) if result.completed_at else 0,
    )


def _execute_qa_health_goal(self, goal: DailyGoal) -> GoalExecutionResult:
    """Execute a QA health check goal."""
    from swarm_attack.qa.orchestrator import QAOrchestrator

    qa_orchestrator = QAOrchestrator(self.config)
    result = qa_orchestrator.health_check()

    return GoalExecutionResult(
        success=result.result.tests_failed == 0,
        cost_usd=result.cost_usd,
        duration_seconds=30,  # Health checks are fast
    )
```

#### 5.2.5 config.py

```python
# Add QA configuration section

@dataclass
class QAConfig:
    """Configuration for QA Agent."""
    enabled: bool = True
    default_depth: str = "standard"
    timeout_seconds: int = 120
    max_cost_usd: float = 2.0
    auto_create_bugs: bool = True
    bug_severity_threshold: str = "moderate"
    base_url: Optional[str] = None

    # Depth-specific settings
    shallow_timeout: int = 30
    standard_timeout: int = 120
    deep_timeout: int = 300

    # Integration flags
    post_verify_qa: bool = True      # Run QA after Verifier
    block_on_critical: bool = True   # Block merge on critical findings
    enhance_bug_repro: bool = True   # Use QA for bug reproduction


@dataclass
class SwarmConfig:
    # ... existing fields ...
    qa: QAConfig = field(default_factory=QAConfig)  # NEW
```

### 5.3 State Store Changes

```
.swarm/
├── qa/                              # NEW: QA state directory
│   ├── qa-20241225-143022/         # Session directory
│   │   ├── state.json              # QASession state
│   │   ├── qa-report.md            # Human-readable report
│   │   ├── qa-results.json         # Structured results
│   │   ├── qa-bugs.md              # Bug Bash-ready issues
│   │   └── execution-log.json      # Full trace
│   └── history.json                # Session history index
├── bugs/                            # Existing bug state
└── state/                           # Existing feature state
```

---

## 6. Example Flows

### Scenario A: Post-Implementation Validation

```
TRIGGER: Verifier passes for issue #42 in feature "user-auth"

1. Orchestrator calls QAOrchestrator.validate_issue("user-auth", 42)

2. QA Context Builder:
   - Reads specs/user-auth/spec-final.md
   - Reads specs/user-auth/issues.json[42]
   - Finds affected files from Coder output
   - Discovers endpoints: POST /api/auth/login, GET /api/auth/me

3. Depth Selector:
   - Trigger: POST_VERIFICATION → base depth: STANDARD
   - Risk: "auth" in path → HIGH RISK → escalate to DEEP
   - Final depth: DEEP

4. QA Orchestrator dispatches:
   - BehavioralTester: Run all test types on /api/auth/*
   - ContractValidator: Check frontend/src/auth/* expectations
   - (RegressionScanner not needed - no diff context)

5. BehavioralTester execution:
   - Starts service (docker-compose up -d)
   - Waits for health check
   - Runs 15 test cases:
     - Happy path: POST /api/auth/login → 200 OK ✓
     - Invalid creds: POST /api/auth/login → 401 ✓
     - Missing field: POST /api/auth/login → 400 ✓
     - SQL injection: POST /api/auth/login → 400 ✓
     - Token validation: GET /api/auth/me → 200 ✓
     - Expired token: GET /api/auth/me → 401 ✓

6. ContractValidator execution:
   - Finds consumer: frontend/src/hooks/useAuth.ts
   - Extracts expected fields: {user: {id, email, name}}
   - Validates actual response matches

7. Result Aggregation:
   - Tests: 15/15 passed
   - Contracts: 1/1 valid
   - Recommendation: PASS
   - Confidence: 0.95

8. Output:
   - .swarm/qa/qa-20241225-143022/qa-report.md
   - Log event: qa_validation_complete

9. Orchestrator continues to commit
```

### Scenario B: Bug Bash Reproduction Enhancement

```
TRIGGER: BugResearcher fails to reproduce bug "api-500-on-special-chars"

1. BugOrchestrator calls QAOrchestrator.reproduce_bug()

2. QA Context Builder:
   - Reads .swarm/bugs/api-500-on-special-chars/state.json
   - Extracts error_message: "500 Internal Server Error"
   - Extracts description: "API returns 500 when user name contains emoji"
   - Identifies endpoint: PUT /api/users/{id}

3. Depth Selector:
   - Trigger: BUG_REPRODUCTION → always DEEP
   - Focus: PUT /api/users/{id} only

4. QA Orchestrator dispatches:
   - BehavioralTester only (focused on reproduction)

5. BehavioralTester execution:
   - Generates edge case payloads for user name field:
     - Unicode: "José" → 200 OK ✓
     - Emoji: "John 🎉" → 500 ERROR ✗ FOUND!
     - Mixed: "Müller-O'Brien 👨‍💻" → 500 ERROR ✗
     - Long string: "A" * 1000 → 400 OK ✓
     - SQL chars: "'; DROP TABLE--" → 400 OK ✓

6. Result Aggregation:
   - Tests: 3/5 passed
   - Findings:
     - [CRITICAL] QA-001: Emoji in name causes 500
       - Evidence: curl -X PUT ... -d '{"name": "John 🎉"}'
       - Response: {"error": "Internal Server Error"}

7. Output:
   - Reproduction confirmed!
   - .swarm/qa/qa-20241225-144500/qa-bugs.md

8. BugOrchestrator receives:
   - state.reproduction.confirmed = True
   - state.reproduction.reproduction_steps = ["PUT /api/users/1 with name='John 🎉'"]

9. Continues to RootCauseAnalyzer with evidence
```

### Scenario C: User-Prompted Testing

```
TRIGGER: User runs: swarm-attack qa test "messaging in chat service"

1. CLI parses command, calls QAOrchestrator.test("messaging in chat service")

2. QA Context Builder:
   - Searches codebase for "message", "chat", "messaging"
   - Finds: src/api/messages.py, src/services/chat.py
   - Discovers endpoints:
     - GET /api/messages
     - POST /api/messages
     - GET /api/messages/{id}
     - DELETE /api/messages/{id}
     - GET /api/chats/{id}/messages

3. Depth Selector:
   - Trigger: USER_COMMAND
   - No --depth specified → use default: STANDARD

4. QA Orchestrator dispatches:
   - BehavioralTester: Standard tests on all 5 endpoints
   - ContractValidator: Check for consumers

5. Execution:
   - 20 test cases generated and run
   - 18 pass, 2 fail

6. Findings:
   - [MODERATE] POST /api/messages returns 200 instead of 201
   - [MINOR] GET /api/messages missing pagination headers

7. CLI Output:
   ```
   Session: qa-20241225-150000
   Tests: 18/20 passed
   Endpoints: 5 tested
   Recommendation: WARN

   Findings:
     [moderate] Wrong status code on message creation
     [minor] Missing pagination headers
   ```
```

### Scenario D: Pre-Merge Validation

```
TRIGGER: Issue marked complete, pre-commit hook or explicit command

1. QAOrchestrator.pre_merge_check(feature_id="user-profile")

2. QA Context Builder:
   - Runs: git diff main...HEAD
   - Identifies changed files:
     - src/api/users.py (modified)
     - src/models/profile.py (added)
     - tests/test_users.py (modified)

3. Depth Selector:
   - Trigger: PRE_MERGE → REGRESSION depth
   - Plus any triggered depth escalation

4. QA Orchestrator dispatches:
   - RegressionScanner first (to identify affected endpoints)
   - BehavioralTester on affected endpoints only

5. RegressionScanner execution:
   - Maps diff to endpoints:
     - src/api/users.py → GET/PUT /api/users/{id}
     - src/models/profile.py → All user endpoints
   - Priority scoring:
     - GET /api/users/{id}: 100 (direct change)
     - PUT /api/users/{id}: 100 (direct change)
     - GET /api/users: 60 (uses changed model)

6. BehavioralTester execution:
   - Runs only on priority >= 60 endpoints
   - Focused regression tests

7. Result:
   - All tests pass
   - Recommendation: PASS
   - Commit proceeds
```

### Scenario E: Full System Health Check

```
TRIGGER: User runs: swarm-attack qa health
         OR: COS autopilot scheduled goal

1. QAOrchestrator.health_check()

2. QA Context Builder:
   - Scans entire codebase for API endpoints
   - Finds 25 endpoints across 8 modules
   - No specific context needed

3. Depth Selector:
   - Trigger: SCHEDULED_HEALTH → SHALLOW
   - Timeout: 30 seconds total

4. QA Orchestrator dispatches:
   - BehavioralTester only (happy path per endpoint)

5. BehavioralTester execution:
   - Parallel requests to all 25 endpoints
   - Only checks: responds, returns 2xx or expected error, responds in <5s
   - No edge case testing

6. Result:
   - 24/25 endpoints healthy
   - 1 endpoint returning 503 (service dependency down)

7. Output:
   ```
   UNHEALTHY

   Failing endpoints:
     [critical] GET /api/notifications - 503 Service Unavailable

   All other endpoints responding normally.
   ```
```

### Scenario F: Spec Compliance Validation

```
TRIGGER: After implementation, before greenlight
         swarm-attack qa spec-compliance user-auth

1. QAOrchestrator.validate_spec_compliance("user-auth")

2. QA Context Builder:
   - Reads specs/user-auth/spec-final.md
   - Extracts all requirements with traceability tags:
     - [REQ-001] User can log in with email/password
     - [REQ-002] Session expires after 24 hours
     - [REQ-003] Password reset sends email
   - Maps requirements to endpoints

3. Depth Selector:
   - Trigger: SPEC_COMPLIANCE → STANDARD
   - Plus traceability tracking

4. QA Orchestrator dispatches:
   - BehavioralTester with requirement tagging
   - ContractValidator with spec schema

5. Execution with traceability:
   - [REQ-001] Test login flow → PASS
   - [REQ-002] Test session expiry → PASS (with time manipulation)
   - [REQ-003] Test password reset → PARTIAL (email not verifiable)

6. Result:
   - 2/3 requirements fully verified
   - 1/3 requirements partially verified (needs manual check)

7. Output:
   ```
   Spec Compliance Report: user-auth

   REQUIREMENTS COVERAGE:
     [PASS]    REQ-001: User login
     [PASS]    REQ-002: Session expiry
     [PARTIAL] REQ-003: Password reset email (manual verification needed)

   Overall: 66% automated, 33% manual required
   Recommendation: PASS (with manual verification of REQ-003)
   ```
```

---

## 7. Cost Estimates

| Scenario | Depth | Typical LLM Calls | Estimated Cost |
|----------|-------|-------------------|----------------|
| Post-Verify | STANDARD | 3-5 | $0.05 - $0.15 |
| Bug Repro | DEEP | 5-10 | $0.10 - $0.30 |
| User Test | STANDARD | 3-5 | $0.05 - $0.15 |
| Pre-Merge | REGRESSION | 2-4 | $0.03 - $0.10 |
| Health Check | SHALLOW | 1-2 | $0.01 - $0.05 |
| Spec Compliance | STANDARD | 4-8 | $0.08 - $0.25 |

**Total per feature lifecycle:** $0.20 - $0.75

---

## 8. Success Criteria Validation

| Criterion | How Design Addresses It |
|-----------|------------------------|
| **Adaptive** | Depth selector automatically adjusts based on trigger, risk, budget |
| **Integrated** | Clean hooks into Orchestrator, BugOrchestrator, Autopilot |
| **Actionable** | Direct Bug Bash creation, clear PASS/WARN/BLOCK recommendations |
| **Efficient** | Parallel sub-agents, targeted regression, shallow health checks |
| **Trustworthy** | Confidence scores, evidence capture, reproducible curl commands |
| **Extensible** | Modular sub-agents, skill-based prompts, configurable thresholds |

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create `swarm_attack/qa/` module structure
- [ ] Implement `QASession`, `QAFinding`, `QAResult` models
- [ ] Implement `QAStateStore`
- [ ] Create skill files for all 4 agents

### Phase 2: Core Agents (Week 3-4)
- [ ] Implement `BehavioralTesterAgent`
- [ ] Implement `ContractValidatorAgent`
- [ ] Implement `RegressionScannerAgent`
- [ ] Implement `QAOrchestrator`

### Phase 3: CLI & Integration (Week 5-6)
- [ ] Implement CLI commands
- [ ] Integrate with `Orchestrator.run_issue_session()`
- [ ] Integrate with `BugOrchestrator.analyze()`
- [ ] Add COS autopilot goal types

### Phase 4: Polish & Testing (Week 7-8)
- [ ] End-to-end testing of all scenarios
- [ ] Performance optimization
- [ ] Documentation
- [ ] Cost tracking validation

---

## Appendix: Design Rationale

### Why Agent Swarm vs. Single Agent?

A single monolithic QA agent would:
- Hit context window limits on deep testing
- Be harder to maintain and evolve
- Not parallelize well

The swarm approach:
- Each sub-agent has focused context
- Can run in parallel when appropriate
- Independent skill updates
- Clearer responsibility boundaries

### Why Not Replace Verifier?

The existing Verifier (pytest runner) provides:
- Fast feedback (no service startup)
- Deterministic results
- No network dependencies
- Lower cost (no LLM calls)

QA Agent provides:
- Behavioral validation (real HTTP)
- Contract validation (consumer expectations)
- Security probing
- Integration testing

They are complementary, not competing.

### Why Depth Levels?

Different contexts need different thoroughness:
- Health checks need speed (shallow)
- Post-verify needs confidence (standard)
- Bug repro needs exhaustiveness (deep)
- Pre-merge needs focus (regression)

Dynamic depth prevents both under-testing and over-spending.

---

## 10. Edge Cases & Failure Modes

> **Expert Panel Analysis**: The following edge cases MUST be handled in v1 to prevent implementation failures.

### 10.1 Service Startup Failures

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Service won't start (missing deps) | Complete QA failure | Detect startup failure, report as `BLOCKED` with clear error, don't report as test failures |
| Port already in use | Startup hangs | Check port availability before starting, use configurable/dynamic ports |
| Docker not installed/running | Can't start containerized services | Detect Docker availability, fall back to native startup or fail gracefully |
| Health check never passes | Infinite wait | **Hard timeout**: 60s max for service startup, then abort |
| Service starts but crashes immediately | False "healthy" | Wait 2-3 seconds after health check, verify still responding |
| No standard health endpoint | Can't verify startup | Try common paths: `/health`, `/healthz`, `/api/health`, `/_health`, `/`, allow config override |

**Implementation Requirement:**
```python
class ServiceStartupResult(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    PORT_CONFLICT = "port_conflict"
    DOCKER_UNAVAILABLE = "docker_unavailable"
    STARTUP_CRASHED = "startup_crashed"
    NO_HEALTH_ENDPOINT = "no_health_endpoint"

# QA session should NOT proceed if startup fails
# Return BLOCKED, not FAIL (this is infrastructure, not a test failure)
```

### 10.2 Authentication Edge Cases

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| No way to get test tokens | Can't test authenticated endpoints | Support multiple auth strategies (see below) |
| Token expires during test run | Mid-session auth failures | Track token TTL, refresh proactively, or get fresh token per request for long runs |
| Complex auth (OAuth2, OIDC, MFA) | Can't automate login | Require pre-configured test token in config, skip auth endpoints with warning |
| CSRF tokens required | 403 on mutations | Fetch CSRF token from session/cookie endpoint first |
| Different auth for different endpoints | Mixed auth failures | Per-endpoint auth config, not global |
| API key in query param vs. header | Wrong placement = 401 | Auto-detect from OpenAPI spec or config |

**Auth Strategy Hierarchy:**
```python
class AuthStrategy(Enum):
    BEARER_TOKEN = "bearer"      # Authorization: Bearer <token>
    API_KEY_HEADER = "api_key"   # X-API-Key: <key>
    API_KEY_QUERY = "api_key_query"  # ?api_key=<key>
    BASIC_AUTH = "basic"         # Authorization: Basic <base64>
    COOKIE_SESSION = "cookie"    # Cookie from login endpoint
    NONE = "none"                # Public endpoints

# Config must support:
qa:
  auth:
    strategy: bearer
    token_env_var: QA_TEST_TOKEN  # Read from environment
    # OR
    token_command: "scripts/get-test-token.sh"  # Execute to get token
    # OR
    login_endpoint: /api/auth/login
    login_body: {"email": "test@test.com", "password": "testpass"}
```

### 10.3 Endpoint Discovery Failures

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| No endpoints found | Empty test suite | Require explicit endpoint list OR fail with clear message |
| Only finds some endpoints | Partial coverage | Log discovered vs. expected, allow manual supplement |
| Discovers internal/admin endpoints | Tests things user shouldn't | Filter by path prefix (exclude `/internal/*`, `/admin/*`) |
| Wrong HTTP methods inferred | 405 Method Not Allowed | Prefer OpenAPI spec, fall back to heuristics |
| Path parameters not detected | `/users/{id}` tested as literal | Regex patterns for common param styles `{id}`, `:id`, `<id>` |
| Query parameters unknown | Missing required params | Extract from code/tests, allow config override |

**Endpoint Source Priority:**
1. OpenAPI/Swagger spec (most reliable)
2. Route decorators in code (`@app.route`, `@router.get`)
3. Test files (what endpoints tests call)
4. Config file explicit list (user override)

```python
# CRITICAL: Never silently return empty endpoint list
def discover_endpoints(context: QAContext) -> list[QAEndpoint]:
    endpoints = []
    endpoints += discover_from_openapi(context)
    endpoints += discover_from_code(context)
    endpoints += discover_from_tests(context)
    endpoints += context.explicit_endpoints  # Config override

    if not endpoints:
        raise EndpointDiscoveryError(
            "No endpoints discovered. Either:\n"
            "1. Add openapi.yaml to your project\n"
            "2. Specify endpoints in config.yaml under qa.endpoints\n"
            "3. Check that API code follows standard patterns"
        )

    return deduplicate(endpoints)
```

### 10.4 Request Generation Failures

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Can't infer request body schema | Wrong/empty payloads | Use OpenAPI, fall back to code analysis, then use minimal valid JSON |
| File upload endpoints | curl can't handle multipart | Detect multipart, use `-F` flag, create temp test files |
| Binary request bodies | Can't represent in JSON | Skip with warning, or use base64 if schema indicates |
| Very large request bodies | Context overflow | Truncate in evidence, use checksums |
| GraphQL endpoints | REST patterns don't apply | Detect GraphQL, use introspection query, different test patterns |
| gRPC/WebSocket | Not HTTP request/response | Detect and skip with warning "Non-HTTP endpoint not supported in v1" |

**Request Body Strategy:**
```python
def generate_request_body(endpoint: QAEndpoint, test_type: str) -> dict:
    # Priority: OpenAPI schema > Type hints > Integration tests > Minimal guess

    if endpoint.schema and endpoint.schema.get("requestBody"):
        return generate_from_schema(endpoint.schema["requestBody"])

    if endpoint.type_hints:
        return generate_from_type_hints(endpoint.type_hints)

    if endpoint.test_examples:
        return endpoint.test_examples[0]

    # Last resort: minimal valid payload for common patterns
    if "user" in endpoint.path:
        return {"name": "Test User", "email": "test@example.com"}

    return {}  # Empty body for GET, minimal for POST
```

### 10.5 Response Validation Failures

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Non-JSON response (HTML, XML, binary) | JSON parse error | Check Content-Type first, handle each type appropriately |
| Very large responses (pagination) | Context overflow | Truncate in evidence, validate structure on first page only |
| Streaming responses | Never completes | Set response timeout, capture first N bytes |
| Empty 204 responses | "No content to validate" | 204 with empty body is valid, don't fail |
| Null vs. missing fields | False positives | Distinguish `{"field": null}` from `{}` in schema |
| Inconsistent timestamps | Flaky comparisons | Compare structure, not exact timestamp values |
| Dynamic fields (UUIDs, dates) | Can't hardcode expected | Use pattern matching, not exact value matching |

**Response Validation Rules:**
```python
def validate_response(expected: dict, actual: dict) -> list[ValidationError]:
    errors = []

    for field, expected_type in expected.items():
        if field not in actual:
            if expected_type.get("required", True):
                errors.append(MissingFieldError(field))
            continue

        actual_value = actual[field]

        # Handle dynamic fields
        if expected_type.get("pattern"):
            if not re.match(expected_type["pattern"], str(actual_value)):
                errors.append(PatternMismatchError(field, expected_type["pattern"]))
        elif expected_type.get("type") == "datetime":
            # Just check it's a valid datetime, not exact value
            try:
                parse_datetime(actual_value)
            except:
                errors.append(InvalidDatetimeError(field))
        elif expected_type.get("type") == "uuid":
            if not is_valid_uuid(actual_value):
                errors.append(InvalidUuidError(field))
        else:
            # Standard type check
            if not isinstance(actual_value, TYPE_MAP[expected_type["type"]]):
                errors.append(TypeMismatchError(field, expected_type["type"], type(actual_value)))

    return errors
```

### 10.6 Database & State Issues

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Tests require specific data | 404 on GET, FK violations on POST | Support test data setup phase OR use idempotent operations |
| Tests modify data | Later tests fail | Isolate tests, use unique identifiers, or reset state |
| DELETE tests remove needed data | Cascade failures | Test DELETE last, use test-specific resources, or mock |
| Concurrent QA sessions | Data conflicts | Include session ID in test data, isolate by prefix |
| Database not seeded | Empty responses everywhere | Detect empty DB, warn user, offer to skip DB-dependent tests |

**Test Data Strategy:**
```python
@dataclass
class TestDataConfig:
    """Configure how QA handles test data."""
    mode: Literal["shared", "isolated", "readonly"] = "shared"

    # shared: Use existing data, may modify
    # isolated: Create unique test data per session, clean up after
    # readonly: Only test GET endpoints, skip mutations

    prefix: str = "qa_test_"  # Prefix for created test data
    cleanup_on_success: bool = True
    cleanup_on_failure: bool = False  # Keep for debugging

# Usage in tests:
def create_test_resource(session: QASession) -> str:
    """Create a resource with session-unique identifier."""
    resource_id = f"{session.session_id}_{uuid4().hex[:8]}"
    # Create resource...
    return resource_id
```

### 10.7 Network & Reliability Issues

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Request timeout | False negative | Distinguish timeout from failure, retry with backoff |
| Connection refused | Server not running | Detect and report as infrastructure issue, not test failure |
| DNS resolution failure | Can't reach host | Pre-validate hostname resolution |
| SSL certificate errors | Connection fails | Option to skip SSL verification for local dev (with warning) |
| Rate limiting (429) | Tests fail after N requests | Detect 429, back off exponentially, respect Retry-After header |
| Flaky tests | Random failures | Retry failed tests once before reporting, flag as "flaky" if passes on retry |
| External service down | Cascading failures | Detect external dependency failures, categorize separately |

**Retry & Resilience Config:**
```python
@dataclass
class ResilienceConfig:
    """Configure retry and timeout behavior."""
    request_timeout_seconds: int = 30
    connect_timeout_seconds: int = 5

    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    retry_on_status: list[int] = field(default_factory=lambda: [429, 502, 503, 504])

    # Rate limiting
    requests_per_second: float = 10.0  # Max RPS to avoid overwhelming server
    respect_retry_after: bool = True

    # SSL
    verify_ssl: bool = True  # Set False for local dev with self-signed certs
```

### 10.8 Contract Discovery Failures

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| No consumers found | Contract validation skipped | Log warning, continue without contract validation |
| Consumer code too complex | Can't extract expectations | Fall back to OpenAPI schema, then skip |
| Consumer uses dynamic field access | Can't determine fields | Skip with warning, suggest manual contract definition |
| Multiple conflicting consumers | Which is right? | Report all consumers, let user decide |
| Consumer in different repo | Can't access code | Support external contract files, or skip with warning |
| Frontend uses GraphQL | REST contract patterns don't apply | Detect GraphQL consumers, use different extraction |

**Contract Discovery Fallback Chain:**
```python
def discover_contracts(endpoint: QAEndpoint, context: QAContext) -> list[Contract]:
    contracts = []

    # 1. OpenAPI spec (most authoritative)
    if openapi := find_openapi_spec(context):
        contracts.append(Contract.from_openapi(openapi, endpoint))

    # 2. Type definitions (TypeScript, Python dataclasses)
    if types := find_type_definitions(endpoint, context):
        contracts.append(Contract.from_types(types))

    # 3. Consumer code analysis
    consumers = find_consumers(endpoint, context)
    for consumer in consumers:
        try:
            contracts.append(Contract.from_consumer(consumer))
        except ContractExtractionError as e:
            log.warning(f"Could not extract contract from {consumer}: {e}")

    # 4. Integration tests
    if test_contracts := extract_from_tests(endpoint, context):
        contracts.extend(test_contracts)

    if not contracts:
        log.warning(f"No contracts found for {endpoint.path}. "
                   "Contract validation will be skipped.")

    return merge_contracts(contracts)  # Combine overlapping contracts
```

### 10.9 Git & VCS Issues

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Dirty worktree | Diff includes uncommitted changes | Warn user, include uncommitted in analysis |
| Detached HEAD | `git diff main...HEAD` fails | Detect and handle, use commit hash instead of HEAD |
| No main/master branch | Reference branch not found | Configurable base branch, detect common names |
| Shallow clone | History not available | Detect shallow clone, fetch more history or skip diff analysis |
| Uncommitted new files | Not in diff output | Use `git status` + `git diff` combined |
| Binary files in diff | Can't analyze | Skip binary files, note in report |

**Git Safety Wrapper:**
```python
def get_diff_safely(base_branch: str = "main") -> tuple[str, list[str]]:
    """Get git diff with fallbacks and warnings."""
    warnings = []

    # Check if in git repo
    if not is_git_repo():
        return "", ["Not a git repository - diff analysis skipped"]

    # Check for dirty worktree
    if has_uncommitted_changes():
        warnings.append("Working tree has uncommitted changes")

    # Find base branch
    if not branch_exists(base_branch):
        for fallback in ["main", "master", "develop"]:
            if branch_exists(fallback):
                base_branch = fallback
                warnings.append(f"Using '{fallback}' as base ('{base_branch}' not found)")
                break
        else:
            return "", ["No base branch found - diff analysis skipped"]

    # Handle detached HEAD
    if is_detached_head():
        warnings.append("Detached HEAD - using current commit")
        current = get_current_commit()
        diff = run(f"git diff {base_branch}...{current}")
    else:
        diff = run(f"git diff {base_branch}...HEAD")

    return diff, warnings
```

### 10.10 Cost & Runaway Prevention

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Deep testing on 100+ endpoints | $50+ cost | Hard cap on endpoints per session, require explicit override |
| Infinite retry loop | Never completes | Max retries per test, max tests per session |
| LLM generates invalid requests | Wasted tokens on errors | Validate generated requests before execution |
| Contract validator analyzes huge codebase | Context explosion | Limit file count, prioritize by relevance |
| Session runs forever | Resource leak | Hard timeout at session level (not just request level) |

**Cost & Resource Limits:**
```python
@dataclass
class QALimits:
    """Hard limits to prevent runaway execution."""

    # Cost limits
    max_cost_usd: float = 5.0  # Per session
    warn_cost_usd: float = 2.0  # Emit warning at this threshold

    # Endpoint limits
    max_endpoints_shallow: int = 100
    max_endpoints_standard: int = 50
    max_endpoints_deep: int = 20

    # Test limits
    max_tests_per_endpoint: int = 20  # Even for deep testing
    max_retries_per_test: int = 2

    # Time limits
    session_timeout_minutes: int = 30
    request_timeout_seconds: int = 30

    # Context limits
    max_files_for_contract_analysis: int = 50
    max_consumers_per_endpoint: int = 10

def check_limits(session: QASession, limits: QALimits) -> Optional[str]:
    """Check if session should be terminated due to limits."""
    if session.cost_usd > limits.max_cost_usd:
        return f"Cost limit exceeded: ${session.cost_usd:.2f} > ${limits.max_cost_usd}"

    if session.elapsed_minutes > limits.session_timeout_minutes:
        return f"Session timeout: {session.elapsed_minutes}m > {limits.session_timeout_minutes}m"

    if session.cost_usd > limits.warn_cost_usd:
        log.warning(f"Approaching cost limit: ${session.cost_usd:.2f}")

    return None  # OK to continue
```

### 10.11 Security & Safety

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| Security probes trigger IDS/WAF | Blocked IP, alerts | Only run security tests in dev/staging, never production |
| Credentials logged in curl commands | Secret exposure | Redact tokens in logs/reports, use `$TOKEN` placeholder |
| SQL injection test hits production | Data corruption | NEVER run deep tests against production without explicit flag |
| DELETE tests remove real data | Data loss | Require explicit confirmation for destructive tests |
| QA agent makes unexpected mutations | Side effects | Support readonly mode, log all mutations |

**Safety Configuration:**
```python
@dataclass
class QASafetyConfig:
    """Safety settings to prevent accidents."""

    # Environment detection
    detect_production: bool = True  # Auto-detect prod by URL patterns
    production_url_patterns: list[str] = field(default_factory=lambda: [
        r".*\.prod\..*",
        r".*production.*",
        r"api\.(company)\.com",  # No subdomain = prod
    ])

    # What's allowed in each environment
    allow_mutations_in_prod: bool = False
    allow_deep_tests_in_prod: bool = False
    allow_security_probes_in_prod: bool = False

    # Credential handling
    redact_tokens_in_logs: bool = True
    redact_patterns: list[str] = field(default_factory=lambda: [
        r"Bearer [A-Za-z0-9\-_]+",
        r"api[_-]?key[=:]\s*\S+",
        r"password[=:]\s*\S+",
    ])

    # Destructive operations
    require_confirmation_for_delete: bool = True
    readonly_mode: bool = False  # If True, skip all mutations

def check_environment_safety(base_url: str, depth: QADepth, config: QASafetyConfig) -> list[str]:
    """Check if planned tests are safe for target environment."""
    errors = []

    is_prod = any(re.match(p, base_url) for p in config.production_url_patterns)

    if is_prod:
        if depth == QADepth.DEEP and not config.allow_deep_tests_in_prod:
            errors.append("Deep testing not allowed in production. Use --depth standard or --allow-prod-deep")

        if not config.allow_mutations_in_prod:
            errors.append("Mutations not allowed in production. Use --readonly or --allow-prod-mutations")

    return errors
```

### 10.12 Graceful Degradation Matrix

When edge cases occur, the system should degrade gracefully rather than fail completely:

| Scenario | Behavior | Output |
|----------|----------|--------|
| Service won't start | Skip all behavioral tests | `status: BLOCKED`, `reason: "service_startup_failed"` |
| No auth token available | Test only public endpoints | `warning: "authenticated_endpoints_skipped"` |
| No endpoints discovered | Abort with clear error | `status: BLOCKED`, `reason: "no_endpoints"` |
| Contract discovery fails | Skip contract validation | `warning: "contracts_not_validated"` |
| Git diff unavailable | Skip regression scanning | `warning: "regression_analysis_skipped"` |
| Rate limited | Complete with partial results | `warning: "rate_limited"`, include completed tests |
| Cost limit reached | Stop and report partial results | `status: COMPLETED_PARTIAL`, `reason: "cost_limit"` |
| Timeout reached | Stop and report partial results | `status: COMPLETED_PARTIAL`, `reason: "timeout"` |

**Partial Completion Handling:**
```python
class QAStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"           # All tests ran successfully
    COMPLETED_PARTIAL = "partial"     # Some tests ran, stopped early
    BLOCKED = "blocked"               # Could not run tests (infrastructure)
    FAILED = "failed"                 # Agent error, not test failure

@dataclass
class QAResult:
    # ... existing fields ...

    # Degradation tracking
    skipped_reasons: dict[str, str] = field(default_factory=dict)
    # e.g., {"contract_validation": "no_consumers_found",
    #        "security_probes": "production_environment"}

    partial_completion_reason: Optional[str] = None
    # e.g., "cost_limit_reached", "timeout", "rate_limited"
```

---

## 11. Pre-Implementation Checklist

Before starting implementation, verify:

- [ ] **Config schema** includes all safety/limits fields from Section 10
- [ ] **Auth strategy** supports at least: Bearer token, API key, Cookie session
- [ ] **Endpoint discovery** has fallback chain and never returns empty silently
- [ ] **Service startup** has hard timeout and detects common failure modes
- [ ] **Request generation** handles file uploads, empty bodies, unknown schemas
- [ ] **Response validation** uses pattern matching for dynamic fields
- [ ] **Contract discovery** degrades gracefully when no consumers found
- [ ] **Git operations** handle detached HEAD, missing branches, dirty worktree
- [ ] **Cost tracking** enforced at orchestrator level with hard limits
- [ ] **Credentials** redacted in all logs and reports
- [ ] **Production detection** prevents destructive tests
- [ ] **Partial completion** properly tracked and reported
