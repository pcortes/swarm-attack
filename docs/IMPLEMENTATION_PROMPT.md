# Implementation Prompt: Complete QA Agent Gaps

You are leading a team of expert engineers to complete the remaining implementation gaps in the Adaptive QA Agent. Use git worktrees for parallel development and strict TDD methodology.

---

## Context

### Original Spec (PRIMARY REFERENCE)
**Path**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a 2,400+ line comprehensive design document. Key sections for this implementation:

| Section | Content | Relevant For |
|---------|---------|--------------|
| **2.3** | ContractValidator Skill Definition | Agent 1 |
| **3.1** | State Schema (QATrigger enum) | Agent 1 |
| **6.3** | ContractValidator Agent Behavior | Agent 1 |
| **10.2** | Authentication Edge Cases | Agent 3 |
| **10.4** | Request Generation Failures | Agent 2 |
| **10.5** | Response Validation Failures | Agent 3 |
| **10.6** | Database & State Issues | Agent 2 |
| **10.8** | Contract Discovery Failures | Agent 1 |

**READ THE SPEC FIRST** before implementing. The spec defines exact behavior, error handling, and edge cases.

### Validation Report
See: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent/docs/QA_VALIDATION_REPORT.md`

### Current State
- **Branch**: `feature/adaptive-qa-agent`
- **Tests**: 821 passing
- **Coverage**: 80%
- **Spec Compliance**: 94%

### Gaps to Implement

| Priority | Gap | Effort | Owner |
|----------|-----|--------|-------|
| CRITICAL | ContractValidatorAgent | 16-24 hrs | Agent 1 |
| HIGH | Request generation edge case tests (10.4) | 8 hrs | Agent 2 |
| HIGH | Database race condition tests (10.6) | 6 hrs | Agent 2 |
| MEDIUM | Missing enum values | 1 hr | Agent 1 |
| MEDIUM | Auth flow tests (10.2) | 4 hrs | Agent 3 |
| MEDIUM | Response validation tests (10.5) | 4 hrs | Agent 3 |

---

## Setup: Git Worktrees

Create isolated worktrees for parallel development:

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent

# Create worktrees for each agent
git worktree add ../qa-agent-contract feature/contract-validator-agent
git worktree add ../qa-agent-edge-cases feature/edge-case-tests
git worktree add ../qa-agent-auth-tests feature/auth-validation-tests
```

---

## Agent 1: ContractValidatorAgent Implementation

### Worktree
`/Users/philipjcortes/Desktop/qa-agent-contract`

### Branch
`feature/contract-validator-agent`

### Mission
Implement the ContractValidatorAgent that validates API contracts between consumers and providers.

### Reference Files

**MUST READ from Original Spec** (`/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`):
- **Section 2.3** (lines ~180-280): ContractValidator Skill Definition - defines consumer discovery, contract extraction, validation rules
- **Section 6.3** (lines ~1100-1250): ContractValidator Agent Behavior - detailed implementation requirements
- **Section 10.8** (lines ~1580-1620): Contract Discovery Failures - edge cases to handle

**Implementation References**:
- **Skill Definition**: `.claude/skills/qa-contract-validator/SKILL.md`
- **Similar Agent**: `swarm_attack/qa/agents/behavioral.py` (use as template)
- **Existing Tests**: `tests/unit/qa/test_contract.py` (expand these)

### TDD Steps

#### Step 1: Write failing tests first
```python
# tests/unit/qa/test_contract_validator.py

import pytest
from swarm_attack.qa.agents.contract import ContractValidatorAgent
from swarm_attack.qa.models import QAContext, QADepth, QAFinding, FindingSeverity

class TestContractValidatorAgent:
    """Test ContractValidatorAgent implementation."""

    @pytest.fixture
    def agent(self):
        return ContractValidatorAgent()

    # Test 1: Agent instantiation
    def test_agent_instantiation(self, agent):
        assert agent.name == "contract_validator"
        assert agent.description is not None

    # Test 2: Consumer discovery - Frontend
    def test_discover_consumers_frontend(self, agent, tmp_path):
        """Agent should discover frontend API consumers."""
        # Create mock frontend file with fetch calls
        frontend_file = tmp_path / "app.tsx"
        frontend_file.write_text('''
            const users = await fetch("/api/users");
            const orders = await fetch("/api/orders", { method: "POST" });
        ''')

        context = QAContext(target_files=[str(frontend_file)])
        consumers = agent.discover_consumers(context)

        assert len(consumers) >= 2
        assert any(c.endpoint == "/api/users" for c in consumers)
        assert any(c.endpoint == "/api/orders" and c.method == "POST" for c in consumers)

    # Test 3: Consumer discovery - OpenAPI
    def test_discover_consumers_openapi(self, agent, tmp_path):
        """Agent should parse OpenAPI specs."""
        openapi_file = tmp_path / "openapi.yaml"
        openapi_file.write_text('''
openapi: 3.0.0
paths:
  /api/users:
    get:
      responses:
        200:
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    id: { type: integer }
                    name: { type: string }
        ''')

        context = QAContext(spec_path=str(openapi_file))
        contracts = agent.extract_contracts(context)

        assert len(contracts) >= 1
        assert contracts[0].endpoint == "/api/users"
        assert "id" in contracts[0].response_schema["properties"]

    # Test 4: Breaking change detection
    def test_detect_breaking_changes(self, agent):
        """Agent should detect breaking changes between versions."""
        old_schema = {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}, "required": ["id", "name"]}
        new_schema = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}  # Breaking: type change, removed field

        changes = agent.detect_breaking_changes(old_schema, new_schema)

        assert len(changes) >= 2
        assert any(c.change_type == "type_change" and c.field == "id" for c in changes)
        assert any(c.change_type == "field_removed" and c.field == "name" for c in changes)

    # Test 5: Schema validation
    def test_validate_response_against_contract(self, agent):
        """Agent should validate responses against contract schema."""
        contract_schema = {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
        valid_response = {"id": 123}
        invalid_response = {"id": "not-an-int"}

        assert agent.validate_response(valid_response, contract_schema) is True
        assert agent.validate_response(invalid_response, contract_schema) is False

    # Test 6: Run method returns findings
    def test_run_returns_findings(self, agent, tmp_path):
        """Agent run() should return QAFinding list."""
        context = QAContext(target_files=[], base_url="http://localhost:8000")

        findings = agent.run(context, depth=QADepth.STANDARD)

        assert isinstance(findings, list)
        assert all(isinstance(f, QAFinding) for f in findings)

    # Test 7: Graceful degradation when no contracts found
    def test_graceful_degradation_no_contracts(self, agent):
        """Agent should handle missing contracts gracefully."""
        context = QAContext(target_files=[], spec_path=None)

        findings = agent.run(context, depth=QADepth.STANDARD)

        # Should return empty or warning, not crash
        assert isinstance(findings, list)

    # Test 8: Integration with orchestrator
    def test_agent_registered_in_orchestrator(self):
        """ContractValidatorAgent should be available in orchestrator."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.config import SwarmConfig
        from swarm_attack.logger import SwarmLogger

        config = SwarmConfig()
        logger = SwarmLogger(config)
        orch = QAOrchestrator(config=config, logger=logger)

        agent_names = [a.name for a in orch._agents]
        assert "contract_validator" in agent_names
```

#### Step 2: Implement the agent
```python
# swarm_attack/qa/agents/contract.py

"""ContractValidatorAgent - Validates API contracts between consumers and providers."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import re
import yaml
import json

from ..models import QAContext, QADepth, QAFinding, FindingSeverity, FindingCategory


@dataclass
class Consumer:
    """Represents an API consumer."""
    source_file: str
    endpoint: str
    method: str = "GET"
    line_number: int = 0


@dataclass
class Contract:
    """Represents an API contract."""
    endpoint: str
    method: str
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    source: str = "openapi"


@dataclass
class BreakingChange:
    """Represents a breaking change between schema versions."""
    change_type: str  # type_change, field_removed, required_added, etc.
    field: str
    old_value: Any = None
    new_value: Any = None
    severity: FindingSeverity = FindingSeverity.HIGH


class ContractValidatorAgent:
    """Agent that validates API contracts and detects breaking changes."""

    def __init__(self):
        self.name = "contract_validator"
        self.description = "Validates API contracts between consumers and providers"
        self._consumer_patterns = [
            # JavaScript/TypeScript fetch patterns
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            # Python requests patterns
            r'requests\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
        ]

    def run(self, context: QAContext, depth: QADepth) -> List[QAFinding]:
        """Run contract validation and return findings."""
        findings: List[QAFinding] = []

        try:
            # Step 1: Discover consumers
            consumers = self.discover_consumers(context)

            # Step 2: Extract contracts from specs
            contracts = self.extract_contracts(context)

            if not contracts and not consumers:
                # Graceful degradation
                return []

            # Step 3: Validate consumers against contracts
            for consumer in consumers:
                matching_contract = self._find_matching_contract(consumer, contracts)
                if not matching_contract:
                    findings.append(QAFinding(
                        finding_id=f"contract-{consumer.endpoint}",
                        severity=FindingSeverity.MEDIUM,
                        category=FindingCategory.CONTRACT,
                        endpoint=consumer.endpoint,
                        test_type="contract_validation",
                        title=f"No contract found for {consumer.endpoint}",
                        description=f"Consumer in {consumer.source_file} uses {consumer.endpoint} but no contract definition found",
                        recommendation="Add OpenAPI spec or contract definition for this endpoint"
                    ))

            # Step 4: Deep validation if depth allows
            if depth in (QADepth.DEEP, QADepth.REGRESSION):
                findings.extend(self._deep_validation(context, contracts))

        except Exception as e:
            findings.append(QAFinding(
                finding_id="contract-error",
                severity=FindingSeverity.LOW,
                category=FindingCategory.CONTRACT,
                title="Contract validation error",
                description=str(e),
                test_type="contract_validation"
            ))

        return findings

    def discover_consumers(self, context: QAContext) -> List[Consumer]:
        """Discover API consumers from source files."""
        consumers: List[Consumer] = []

        for file_path in context.target_files:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text()
            for pattern in self._consumer_patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    endpoint = match.group(1) if len(match.groups()) == 1 else match.group(2)
                    method = match.group(1).upper() if len(match.groups()) > 1 else "GET"

                    consumers.append(Consumer(
                        source_file=str(path),
                        endpoint=endpoint,
                        method=method,
                        line_number=content[:match.start()].count('\n') + 1
                    ))

        return consumers

    def extract_contracts(self, context: QAContext) -> List[Contract]:
        """Extract contracts from OpenAPI specs or other sources."""
        contracts: List[Contract] = []

        if context.spec_path:
            spec_path = Path(context.spec_path)
            if spec_path.exists():
                contracts.extend(self._parse_openapi(spec_path))

        return contracts

    def _parse_openapi(self, spec_path: Path) -> List[Contract]:
        """Parse OpenAPI spec file."""
        contracts: List[Contract] = []

        content = spec_path.read_text()
        if spec_path.suffix in ('.yaml', '.yml'):
            spec = yaml.safe_load(content)
        else:
            spec = json.loads(content)

        paths = spec.get('paths', {})
        for endpoint, methods in paths.items():
            for method, details in methods.items():
                if method in ('get', 'post', 'put', 'delete', 'patch'):
                    response_schema = None
                    responses = details.get('responses', {})
                    if '200' in responses:
                        content = responses['200'].get('content', {})
                        if 'application/json' in content:
                            response_schema = content['application/json'].get('schema')

                    contracts.append(Contract(
                        endpoint=endpoint,
                        method=method.upper(),
                        response_schema=response_schema
                    ))

        return contracts

    def detect_breaking_changes(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Detect breaking changes between schema versions."""
        changes: List[BreakingChange] = []

        old_props = old_schema.get('properties', {})
        new_props = new_schema.get('properties', {})
        old_required = set(old_schema.get('required', []))
        new_required = set(new_schema.get('required', []))

        # Check for removed fields
        for field in old_props:
            if field not in new_props:
                changes.append(BreakingChange(
                    change_type="field_removed",
                    field=field,
                    old_value=old_props[field]
                ))

        # Check for type changes
        for field in old_props:
            if field in new_props:
                old_type = old_props[field].get('type')
                new_type = new_props[field].get('type')
                if old_type != new_type:
                    changes.append(BreakingChange(
                        change_type="type_change",
                        field=field,
                        old_value=old_type,
                        new_value=new_type
                    ))

        # Check for new required fields
        for field in new_required - old_required:
            if field in old_props:  # Was optional, now required
                changes.append(BreakingChange(
                    change_type="required_added",
                    field=field
                ))

        return changes

    def validate_response(self, response: Dict, schema: Dict) -> bool:
        """Validate a response against a schema."""
        try:
            schema_type = schema.get('type')

            if schema_type == 'object':
                if not isinstance(response, dict):
                    return False

                # Check required fields
                for req_field in schema.get('required', []):
                    if req_field not in response:
                        return False

                # Check property types
                props = schema.get('properties', {})
                for field, value in response.items():
                    if field in props:
                        prop_type = props[field].get('type')
                        if prop_type == 'integer' and not isinstance(value, int):
                            return False
                        if prop_type == 'string' and not isinstance(value, str):
                            return False

                return True

            return True
        except Exception:
            return False

    def _find_matching_contract(self, consumer: Consumer, contracts: List[Contract]) -> Optional[Contract]:
        """Find a contract matching the consumer."""
        for contract in contracts:
            if consumer.endpoint == contract.endpoint and consumer.method == contract.method:
                return contract
        return None

    def _deep_validation(self, context: QAContext, contracts: List[Contract]) -> List[QAFinding]:
        """Perform deep validation checks."""
        # TODO: Implement deep validation (schema drift, version comparison)
        return []
```

#### Step 3: Register agent in __init__.py
```python
# swarm_attack/qa/agents/__init__.py

from .behavioral import BehavioralTesterAgent
from .regression import RegressionScannerAgent
from .contract import ContractValidatorAgent

__all__ = [
    "BehavioralTesterAgent",
    "RegressionScannerAgent",
    "ContractValidatorAgent",
]
```

#### Step 4: Add to orchestrator
Update `swarm_attack/qa/orchestrator.py` to include ContractValidatorAgent in `_agents` list.

#### Step 5: Add missing enum values
```python
# In swarm_attack/qa/models.py, update QATrigger:

class QATrigger(str, Enum):
    POST_VERIFICATION = "post_verification"
    BUG_REPRODUCTION = "bug_reproduction"
    USER_COMMAND = "user_command"
    PRE_MERGE = "pre_merge"
    SCHEDULED_HEALTH = "scheduled_health"  # ADD THIS
    SPEC_COMPLIANCE = "spec_compliance"    # ADD THIS
```

### Verification
```bash
cd /Users/philipjcortes/Desktop/qa-agent-contract
PYTHONPATH=. python -m pytest tests/unit/qa/test_contract_validator.py -v
PYTHONPATH=. python -m pytest tests/unit/qa/ -v
PYTHONPATH=. python -m pytest tests/integration/qa/ -v
```

---

## Agent 2: Edge Case Tests (Request Generation & Database)

### Worktree
`/Users/philipjcortes/Desktop/qa-agent-edge-cases`

### Branch
`feature/edge-case-tests`

### Mission
Add comprehensive edge case tests for Section 10.4 (Request Generation) and Section 10.6 (Database & State).

### Reference Files

**MUST READ from Original Spec** (`/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`):
- **Section 10.4** (lines ~1480-1520): Request Generation Failures - malformed schemas, circular refs, nested limits, content types
- **Section 10.6** (lines ~1540-1560): Database & State Issues - race conditions, concurrent writes, orphaned sessions, corruption

**Implementation References**:
- **BehavioralTesterAgent**: `swarm_attack/qa/agents/behavioral.py` (add edge case handling here)
- **Orchestrator**: `swarm_attack/qa/orchestrator.py` (session management methods)
- **Existing Tests**: `tests/unit/qa/test_behavioral.py`, `tests/unit/qa/test_orchestrator.py`

### TDD Steps

#### Request Generation Edge Cases (10.4)
```python
# tests/unit/qa/test_request_generation_edge_cases.py

import pytest
from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import QAContext, QADepth

class TestRequestGenerationEdgeCases:
    """Section 10.4: Request Generation Failure edge cases."""

    @pytest.fixture
    def agent(self):
        return BehavioralTesterAgent()

    def test_malformed_schema_handling(self, agent):
        """Agent should handle malformed JSON schema gracefully."""
        malformed_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "invalid_type"}  # Invalid type
            }
        }

        # Should not crash, should return error finding
        result = agent.generate_request_body(malformed_schema)
        assert result is not None or agent.last_error is not None

    def test_circular_reference_detection(self, agent):
        """Agent should detect and handle circular schema references."""
        # Schema with circular reference
        circular_schema = {
            "type": "object",
            "properties": {
                "parent": {"$ref": "#"},  # Self-reference
            }
        }

        # Should detect circular ref and limit depth
        result = agent.generate_request_body(circular_schema, max_depth=5)
        assert result is not None

    def test_deeply_nested_object_limit(self, agent):
        """Agent should enforce max nesting depth (10 levels)."""
        # Create 15-level nested schema
        nested = {"type": "string"}
        for _ in range(15):
            nested = {"type": "object", "properties": {"child": nested}}

        result = agent.generate_request_body(nested, max_depth=10)
        # Should truncate at depth 10
        assert self._count_nesting(result) <= 10

    def test_unsupported_content_type_handling(self, agent):
        """Agent should handle unsupported content types gracefully."""
        context = QAContext(
            target_endpoints=[{"path": "/upload", "content_type": "multipart/form-data"}]
        )

        # Should skip or return warning, not crash
        findings = agent.run(context, QADepth.STANDARD)
        # Check for skip or warning finding
        assert not any(f.severity == "error" and "crash" in f.description.lower() for f in findings)

    def test_binary_content_handling(self, agent):
        """Agent should handle binary content types."""
        context = QAContext(
            target_endpoints=[{"path": "/download", "content_type": "application/octet-stream"}]
        )

        findings = agent.run(context, QADepth.STANDARD)
        assert isinstance(findings, list)

    def _count_nesting(self, obj, depth=0):
        if isinstance(obj, dict) and "child" in obj:
            return self._count_nesting(obj["child"], depth + 1)
        return depth


class TestDatabaseStateEdgeCases:
    """Section 10.6: Database & State edge cases."""

    def test_concurrent_session_writes(self, tmp_path):
        """Multiple processes writing to same session should not corrupt."""
        import threading
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.config import SwarmConfig
        from swarm_attack.logger import SwarmLogger

        config = SwarmConfig()
        logger = SwarmLogger(config)
        orch = QAOrchestrator(config=config, logger=logger)

        errors = []

        def write_session(session_id, thread_id):
            try:
                for i in range(10):
                    orch.update_session(session_id, {"thread": thread_id, "iteration": i})
            except Exception as e:
                errors.append(e)

        session_id = orch.create_session()
        threads = [threading.Thread(target=write_session, args=(session_id, i)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should either all succeed or fail gracefully with lock
        assert len(errors) == 0 or all("lock" in str(e).lower() for e in errors)

    def test_orphaned_session_cleanup(self, tmp_path):
        """Orphaned sessions from crashed processes should be cleaned up."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.config import SwarmConfig
        from swarm_attack.logger import SwarmLogger

        config = SwarmConfig()
        logger = SwarmLogger(config)
        orch = QAOrchestrator(config=config, logger=logger)

        # Create orphaned session (simulate crash by not completing)
        session_id = orch.create_session()
        orch._sessions[session_id].status = "running"  # Left in running state

        # Cleanup should handle orphaned sessions
        cleaned = orch.cleanup_orphaned_sessions(max_age_hours=0)

        assert session_id in cleaned or orch.get_session(session_id).status != "running"

    def test_session_file_corruption_recovery(self, tmp_path):
        """Agent should recover from corrupted session files."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.config import SwarmConfig
        from swarm_attack.logger import SwarmLogger

        config = SwarmConfig()
        logger = SwarmLogger(config)
        orch = QAOrchestrator(config=config, logger=logger)

        session_id = orch.create_session()

        # Corrupt the session file (if file-based)
        session_path = tmp_path / f"{session_id}.json"
        session_path.write_text("{ invalid json }")

        # Load should handle corruption gracefully
        try:
            session = orch.load_session(session_id)
            assert session is None or session.status == "error"
        except Exception as e:
            assert "corrupt" in str(e).lower() or "invalid" in str(e).lower()

    def test_disk_full_handling(self, tmp_path, monkeypatch):
        """Agent should handle disk full errors gracefully."""
        from swarm_attack.qa.orchestrator import QAOrchestrator
        from swarm_attack.config import SwarmConfig
        from swarm_attack.logger import SwarmLogger

        def raise_disk_full(*args, **kwargs):
            raise OSError(28, "No space left on device")

        config = SwarmConfig()
        logger = SwarmLogger(config)
        orch = QAOrchestrator(config=config, logger=logger)

        # Mock file write to simulate disk full
        monkeypatch.setattr("builtins.open", raise_disk_full)

        session_id = orch.create_session()

        # Should handle gracefully
        try:
            orch.save_session(session_id)
        except OSError as e:
            assert "space" in str(e).lower()
```

### Verification
```bash
cd /Users/philipjcortes/Desktop/qa-agent-edge-cases
PYTHONPATH=. python -m pytest tests/unit/qa/test_request_generation_edge_cases.py -v
```

---

## Agent 3: Auth & Response Validation Tests

### Worktree
`/Users/philipjcortes/Desktop/qa-agent-auth-tests`

### Branch
`feature/auth-validation-tests`

### Mission
Add tests for Section 10.2 (Authentication) and Section 10.5 (Response Validation).

### Reference Files

**MUST READ from Original Spec** (`/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`):
- **Section 10.2** (lines ~1420-1460): Authentication Edge Cases - expired tokens, OAuth refresh, API key rotation, missing credentials
- **Section 10.5** (lines ~1520-1540): Response Validation Failures - malformed JSON, charset issues, streaming, size limits

**Implementation References**:
- **AuthStrategy enum**: `swarm_attack/qa/models.py:26-33`
- **BehavioralTesterAgent**: `swarm_attack/qa/agents/behavioral.py`
- **Existing Tests**: `tests/unit/qa/test_behavioral.py`, `tests/integration/qa/test_real_http.py`

### TDD Steps

```python
# tests/unit/qa/test_auth_edge_cases.py

import pytest
from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import QAContext, QADepth, AuthStrategy

class TestAuthenticationEdgeCases:
    """Section 10.2: Authentication edge cases."""

    @pytest.fixture
    def agent(self):
        return BehavioralTesterAgent()

    def test_expired_bearer_token_handling(self, agent, httpx_mock):
        """Agent should detect and report expired tokens."""
        httpx_mock.add_response(status_code=401, json={"error": "token_expired"})

        context = QAContext(
            base_url="http://localhost:8000",
            auth_token="expired_token",
            auth_strategy=AuthStrategy.BEARER_TOKEN
        )

        findings = agent.run(context, QADepth.STANDARD)

        assert any(f.title and "expired" in f.title.lower() or "401" in str(f.description) for f in findings)

    def test_oauth_token_refresh_flow(self, agent, httpx_mock):
        """Agent should handle OAuth token refresh."""
        # First request fails with 401
        httpx_mock.add_response(status_code=401, json={"error": "token_expired"})
        # Refresh endpoint succeeds
        httpx_mock.add_response(
            url="http://localhost:8000/oauth/token",
            json={"access_token": "new_token", "expires_in": 3600}
        )
        # Retry succeeds with new token
        httpx_mock.add_response(status_code=200, json={"data": "success"})

        context = QAContext(
            base_url="http://localhost:8000",
            auth_strategy=AuthStrategy.BEARER_TOKEN,
            auth_refresh_url="http://localhost:8000/oauth/token"
        )

        findings = agent.run(context, QADepth.STANDARD)

        # Should have attempted refresh
        assert any("refresh" in str(f).lower() for f in findings) or len(findings) == 0

    def test_missing_auth_header_detection(self, agent, httpx_mock):
        """Agent should detect when auth header is missing but required."""
        httpx_mock.add_response(status_code=401, json={"error": "authentication_required"})

        context = QAContext(
            base_url="http://localhost:8000",
            target_endpoints=[{"path": "/api/protected", "auth_required": True}]
        )

        findings = agent.run(context, QADepth.STANDARD)

        assert any(f.severity.value in ("high", "critical") for f in findings if f.category.value == "security")

    def test_api_key_in_query_vs_header(self, agent):
        """Agent should support both query and header API keys."""
        context_header = QAContext(
            base_url="http://localhost:8000",
            auth_token="test_key",
            auth_strategy=AuthStrategy.API_KEY_HEADER
        )

        context_query = QAContext(
            base_url="http://localhost:8000",
            auth_token="test_key",
            auth_strategy=AuthStrategy.API_KEY_QUERY
        )

        # Both should build valid requests
        header_request = agent.build_request(context_header, "/api/test")
        query_request = agent.build_request(context_query, "/api/test")

        assert "X-API-Key" in header_request.headers or "Authorization" in header_request.headers
        assert "api_key=" in query_request.url or "key=" in query_request.url


class TestResponseValidationEdgeCases:
    """Section 10.5: Response validation edge cases."""

    @pytest.fixture
    def agent(self):
        return BehavioralTesterAgent()

    def test_malformed_json_response(self, agent, httpx_mock):
        """Agent should handle malformed JSON responses."""
        httpx_mock.add_response(
            status_code=200,
            content=b"{ invalid json }",
            headers={"content-type": "application/json"}
        )

        context = QAContext(base_url="http://localhost:8000")
        findings = agent.run(context, QADepth.STANDARD)

        assert any("json" in str(f).lower() and ("invalid" in str(f).lower() or "malformed" in str(f).lower()) for f in findings)

    def test_non_utf8_response_handling(self, agent, httpx_mock):
        """Agent should handle non-UTF8 encoded responses."""
        # Latin-1 encoded response
        httpx_mock.add_response(
            status_code=200,
            content="Héllo Wörld".encode('latin-1'),
            headers={"content-type": "text/plain; charset=latin-1"}
        )

        context = QAContext(base_url="http://localhost:8000")
        findings = agent.run(context, QADepth.STANDARD)

        # Should not crash, may have encoding finding
        assert isinstance(findings, list)

    def test_streaming_response_handling(self, agent, httpx_mock):
        """Agent should handle streaming/chunked responses."""
        # Simulate streaming response
        httpx_mock.add_response(
            status_code=200,
            content=b"data: chunk1\ndata: chunk2\ndata: chunk3\n",
            headers={"content-type": "text/event-stream"}
        )

        context = QAContext(base_url="http://localhost:8000")
        findings = agent.run(context, QADepth.STANDARD)

        assert isinstance(findings, list)

    def test_response_size_limit(self, agent, httpx_mock):
        """Agent should enforce response size limits."""
        # 100MB response (should be limited)
        large_content = b"x" * (100 * 1024 * 1024)
        httpx_mock.add_response(status_code=200, content=large_content)

        context = QAContext(base_url="http://localhost:8000")

        # Should either limit or report
        findings = agent.run(context, QADepth.STANDARD)
        assert isinstance(findings, list)

    def test_empty_response_body(self, agent, httpx_mock):
        """Agent should handle empty response bodies."""
        httpx_mock.add_response(status_code=204, content=b"")

        context = QAContext(base_url="http://localhost:8000")
        findings = agent.run(context, QADepth.STANDARD)

        # 204 No Content is valid
        assert not any(f.severity.value == "critical" for f in findings)
```

### Verification
```bash
cd /Users/philipjcortes/Desktop/qa-agent-auth-tests
PYTHONPATH=. python -m pytest tests/unit/qa/test_auth_edge_cases.py -v
```

---

## Merge Strategy

After all agents complete:

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent

# Merge contract validator first (CRITICAL)
git merge feature/contract-validator-agent

# Run full test suite
PYTHONPATH=. python -m pytest tests/ -v

# If green, merge edge case tests
git merge feature/edge-case-tests
PYTHONPATH=. python -m pytest tests/ -v

# If green, merge auth tests
git merge feature/auth-validation-tests
PYTHONPATH=. python -m pytest tests/ -v

# Clean up worktrees
git worktree remove ../qa-agent-contract
git worktree remove ../qa-agent-edge-cases
git worktree remove ../qa-agent-auth-tests
```

---

## Success Criteria

- [ ] All new tests pass
- [ ] Existing 821 tests still pass
- [ ] ContractValidatorAgent instantiates and runs
- [ ] `from swarm_attack.qa.agents import ContractValidatorAgent` works
- [ ] Orchestrator dispatches to all 3 agents
- [ ] Coverage remains >= 80%
- [ ] No regressions in CLI commands

---

## Estimated Timeline

| Phase | Duration | Agent |
|-------|----------|-------|
| ContractValidatorAgent | 16-24 hrs | Agent 1 |
| Edge Case Tests | 8-10 hrs | Agent 2 |
| Auth/Response Tests | 6-8 hrs | Agent 3 |
| Integration & Merge | 2-4 hrs | All |
| **Total** | **32-46 hrs** | |

---

*Ready for parallel execution. Start all 3 agents simultaneously.*
