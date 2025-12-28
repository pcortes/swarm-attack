"""Tests for ContractValidatorAgent following TDD approach.

Tests cover spec sections 4.2, 10.3, 10.8:
- Endpoint discovery from OpenAPI specs, code, and tests
- Contract discovery with fallback chain
- Path parameter detection ({id}, :id, <id>)
- EndpointDiscoveryError when no endpoints found
- Graceful degradation when no consumers found
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from swarm_attack.qa.models import (
    QAContext, QAEndpoint, QAFinding, QADepth, QALimits,
)


# =============================================================================
# Test Imports (these will fail until we implement the agent)
# =============================================================================


class TestContractValidatorImports:
    """Test that ContractValidatorAgent can be imported."""

    def test_can_import_contract_validator(self):
        """Should be able to import ContractValidatorAgent."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        assert ContractValidatorAgent is not None

    def test_can_import_endpoint_discovery_error(self):
        """Should be able to import EndpointDiscoveryError."""
        from swarm_attack.qa.agents.contract import EndpointDiscoveryError
        assert EndpointDiscoveryError is not None

    def test_can_import_contract_dataclass(self):
        """Should be able to import Contract dataclass."""
        from swarm_attack.qa.agents.contract import Contract
        assert Contract is not None


# =============================================================================
# Test ContractValidatorAgent Initialization
# =============================================================================


class TestContractValidatorInit:
    """Tests for ContractValidatorAgent initialization."""

    def test_agent_has_correct_name(self):
        """Agent should have correct name for logging."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = ContractValidatorAgent(config)
        assert agent.name == "contract_validator"

    def test_agent_has_default_limits(self):
        """Agent should have default QALimits."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = ContractValidatorAgent(config)
        assert agent.limits is not None
        assert agent.limits.max_files_for_contract_analysis == 50

    def test_agent_accepts_custom_limits(self):
        """Agent should accept custom QALimits."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        custom_limits = QALimits(max_files_for_contract_analysis=25)
        agent = ContractValidatorAgent(config, limits=custom_limits)
        assert agent.limits.max_files_for_contract_analysis == 25


# =============================================================================
# Test Endpoint Discovery (Section 10.3)
# =============================================================================


class TestEndpointDiscovery:
    """Tests for discover_endpoints() method (Section 10.3)."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_discover_endpoints_raises_error_when_none_found(self, agent):
        """Should raise EndpointDiscoveryError when no endpoints found (Section 10.3)."""
        from swarm_attack.qa.agents.contract import EndpointDiscoveryError

        context = QAContext(target_files=[])

        with patch.object(agent, '_discover_from_openapi', return_value=[]):
            with patch.object(agent, '_discover_from_code', return_value=[]):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    with pytest.raises(EndpointDiscoveryError) as exc_info:
                        agent.discover_endpoints(context)
                    # Should have helpful error message
                    assert "No endpoints discovered" in str(exc_info.value)
                    assert "openapi" in str(exc_info.value).lower()

    def test_discover_endpoints_never_returns_empty_silently(self, agent):
        """Should NEVER return empty list silently (Section 10.3 requirement)."""
        from swarm_attack.qa.agents.contract import EndpointDiscoveryError

        context = QAContext(target_files=[])

        with patch.object(agent, '_discover_from_openapi', return_value=[]):
            with patch.object(agent, '_discover_from_code', return_value=[]):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    # Must raise, not return empty list
                    with pytest.raises(EndpointDiscoveryError):
                        result = agent.discover_endpoints(context)
                        # This assertion should never be reached
                        assert False, "Should have raised EndpointDiscoveryError"

    def test_discover_endpoints_from_openapi_spec(self, agent):
        """Should discover endpoints from OpenAPI spec first."""
        context = QAContext(target_files=["src/api/users.py"])

        expected = [QAEndpoint(method="GET", path="/api/users")]
        with patch.object(agent, '_discover_from_openapi', return_value=expected):
            with patch.object(agent, '_discover_from_code', return_value=[]):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    result = agent.discover_endpoints(context)
                    assert len(result) == 1
                    assert result[0].path == "/api/users"

    def test_discover_endpoints_falls_back_to_code(self, agent):
        """Should fall back to code analysis when no OpenAPI spec."""
        context = QAContext(target_files=["src/api/users.py"])

        expected = [QAEndpoint(method="POST", path="/api/items")]
        with patch.object(agent, '_discover_from_openapi', return_value=[]):
            with patch.object(agent, '_discover_from_code', return_value=expected):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    result = agent.discover_endpoints(context)
                    assert len(result) == 1
                    assert result[0].method == "POST"

    def test_discover_endpoints_combines_all_sources(self, agent):
        """Should combine endpoints from all sources."""
        context = QAContext(target_files=["src/api/users.py"])

        openapi_endpoints = [QAEndpoint(method="GET", path="/api/users")]
        code_endpoints = [QAEndpoint(method="POST", path="/api/users")]
        test_endpoints = [QAEndpoint(method="DELETE", path="/api/users/{id}")]

        with patch.object(agent, '_discover_from_openapi', return_value=openapi_endpoints):
            with patch.object(agent, '_discover_from_code', return_value=code_endpoints):
                with patch.object(agent, '_discover_from_tests', return_value=test_endpoints):
                    result = agent.discover_endpoints(context)
                    # Should have all unique endpoints
                    assert len(result) == 3

    def test_discover_endpoints_deduplicates(self, agent):
        """Should deduplicate endpoints found in multiple sources."""
        context = QAContext(target_files=["src/api/users.py"])

        # Same endpoint from both sources
        openapi_endpoints = [QAEndpoint(method="GET", path="/api/users")]
        code_endpoints = [QAEndpoint(method="GET", path="/api/users")]

        with patch.object(agent, '_discover_from_openapi', return_value=openapi_endpoints):
            with patch.object(agent, '_discover_from_code', return_value=code_endpoints):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    result = agent.discover_endpoints(context)
                    # Should deduplicate
                    assert len(result) == 1

    def test_discover_endpoints_includes_explicit_endpoints(self, agent):
        """Should include explicit endpoints from context."""
        explicit = [QAEndpoint(method="GET", path="/api/custom")]
        context = QAContext(
            target_files=[],
            target_endpoints=explicit
        )

        with patch.object(agent, '_discover_from_openapi', return_value=[]):
            with patch.object(agent, '_discover_from_code', return_value=[]):
                with patch.object(agent, '_discover_from_tests', return_value=[]):
                    result = agent.discover_endpoints(context)
                    assert len(result) == 1
                    assert result[0].path == "/api/custom"


# =============================================================================
# Test Path Parameter Detection (Section 10.3)
# =============================================================================


class TestPathParameterDetection:
    """Tests for path parameter detection ({id}, :id, <id>)."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_detects_curly_brace_params(self, agent):
        """Should detect {id} style path parameters."""
        path = "/api/users/{id}/posts/{post_id}"
        params = agent._extract_path_params(path)
        assert "id" in params
        assert "post_id" in params

    def test_detects_colon_params(self, agent):
        """Should detect :id style path parameters (Express.js style)."""
        path = "/api/users/:id/posts/:postId"
        params = agent._extract_path_params(path)
        assert "id" in params
        assert "postId" in params

    def test_detects_angle_bracket_params(self, agent):
        """Should detect <id> style path parameters (Flask style)."""
        path = "/api/users/<id>/posts/<int:post_id>"
        params = agent._extract_path_params(path)
        assert "id" in params
        assert "post_id" in params

    def test_normalizes_path_parameters(self, agent):
        """Should normalize different path parameter styles."""
        # All these should be normalized to {param} style
        paths = [
            "/api/users/{id}",
            "/api/users/:id",
            "/api/users/<id>",
        ]
        for path in paths:
            normalized = agent._normalize_path(path)
            assert "{id}" in normalized

    def test_handles_path_without_params(self, agent):
        """Should handle paths without parameters."""
        path = "/api/users"
        params = agent._extract_path_params(path)
        assert len(params) == 0


# =============================================================================
# Test Contract Discovery Fallback Chain (Section 10.8)
# =============================================================================


class TestContractDiscovery:
    """Tests for discover_contracts() with fallback chain (Section 10.8)."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_discover_contracts_openapi_first(self, agent):
        """Should try OpenAPI spec first (most authoritative - Section 10.8)."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        openapi_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name"],
            source=ContractSource.OPENAPI
        )

        with patch.object(agent, '_contract_from_openapi', return_value=openapi_contract):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        result = agent.discover_contracts(endpoint, context)
                        assert len(result) >= 1
                        assert result[0].source == ContractSource.OPENAPI

    def test_discover_contracts_type_definitions_second(self, agent):
        """Should try type definitions second."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        type_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "email"],
            source=ContractSource.TYPE_DEFINITION
        )

        with patch.object(agent, '_contract_from_openapi', return_value=None):
            with patch.object(agent, '_contract_from_types', return_value=type_contract):
                with patch.object(agent, '_contracts_from_consumers', return_value=[]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        result = agent.discover_contracts(endpoint, context)
                        assert len(result) >= 1
                        assert result[0].source == ContractSource.TYPE_DEFINITION

    def test_discover_contracts_consumers_third(self, agent):
        """Should try consumer code analysis third."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        consumer_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name", "createdAt"],
            source=ContractSource.CONSUMER,
            consumer_location="frontend/src/hooks/useUsers.ts:45"
        )

        with patch.object(agent, '_contract_from_openapi', return_value=None):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[consumer_contract]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        result = agent.discover_contracts(endpoint, context)
                        assert len(result) >= 1
                        assert result[0].source == ContractSource.CONSUMER

    def test_discover_contracts_tests_fourth(self, agent):
        """Should try integration tests fourth."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        test_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id"],
            source=ContractSource.INTEGRATION_TEST
        )

        with patch.object(agent, '_contract_from_openapi', return_value=None):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[test_contract]):
                        result = agent.discover_contracts(endpoint, context)
                        assert len(result) >= 1
                        assert result[0].source == ContractSource.INTEGRATION_TEST

    def test_discover_contracts_graceful_degradation(self, agent):
        """Should degrade gracefully when no consumers found (Section 10.8)."""
        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        with patch.object(agent, '_contract_from_openapi', return_value=None):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        # Should return empty list (not raise)
                        result = agent.discover_contracts(endpoint, context)
                        assert result == []

    def test_discover_contracts_logs_warning_when_empty(self, agent):
        """Should log warning when no contracts found."""
        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        with patch.object(agent, '_contract_from_openapi', return_value=None):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        with patch.object(agent, '_log') as mock_log:
                            agent.discover_contracts(endpoint, context)
                            # Should log a warning
                            mock_log.assert_called()
                            call_args = mock_log.call_args_list
                            assert any("warning" in str(call) or "contracts" in str(call)
                                      for call in call_args)

    def test_discover_contracts_merges_overlapping(self, agent):
        """Should merge overlapping contracts from different sources."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        endpoint = QAEndpoint(method="GET", path="/api/users")
        context = QAContext()

        openapi_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name"],
            source=ContractSource.OPENAPI
        )
        consumer_contract = Contract(
            endpoint="/api/users",
            expected_fields=["name", "email"],  # Overlaps on "name"
            source=ContractSource.CONSUMER
        )

        with patch.object(agent, '_contract_from_openapi', return_value=openapi_contract):
            with patch.object(agent, '_contract_from_types', return_value=None):
                with patch.object(agent, '_contracts_from_consumers', return_value=[consumer_contract]):
                    with patch.object(agent, '_contracts_from_tests', return_value=[]):
                        result = agent.discover_contracts(endpoint, context)
                        # Should have contracts from both sources
                        assert len(result) >= 2


# =============================================================================
# Test Consumer Discovery (Section 10.8)
# =============================================================================


class TestConsumerDiscovery:
    """Tests for finding API consumers."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_finds_fetch_calls(self, agent):
        """Should find fetch() calls in frontend code."""
        code = '''
        const users = await fetch('/api/users');
        const data = await users.json();
        console.log(data.name, data.email);
        '''
        consumers = agent._find_consumers_in_code(code, "test.ts")
        assert len(consumers) >= 1
        assert any("/api/users" in c.get("endpoint", "") for c in consumers)

    def test_finds_axios_calls(self, agent):
        """Should find axios calls."""
        code = '''
        const response = await axios.get('/api/users/123');
        const user = response.data;
        '''
        consumers = agent._find_consumers_in_code(code, "test.ts")
        assert len(consumers) >= 1

    def test_finds_requests_calls(self, agent):
        """Should find Python requests calls."""
        code = '''
        response = requests.get('/api/users')
        data = response.json()
        print(data['name'])
        '''
        consumers = agent._find_consumers_in_code(code, "test.py")
        assert len(consumers) >= 1

    def test_extracts_expected_fields_from_consumer(self, agent):
        """Should extract expected fields from consumer code."""
        code = '''
        const response = await fetch('/api/users');
        const user = await response.json();
        console.log(user.name, user.email, user.createdAt);
        '''
        consumers = agent._find_consumers_in_code(code, "test.ts")
        # Should extract fields that consumer accesses
        assert len(consumers) >= 1


# =============================================================================
# Test Contract Validation
# =============================================================================


class TestContractValidation:
    """Tests for validating API responses against contracts."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_validates_field_presence(self, agent):
        """Should validate that expected fields are present."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name", "email"],
            source=ContractSource.OPENAPI
        )
        response = {"id": 1, "name": "Test"}  # Missing email

        errors = agent._validate_response(contract, response)
        assert len(errors) >= 1
        assert any("email" in str(e) for e in errors)

    def test_validates_field_types(self, agent):
        """Should validate field types match contract."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name"],
            field_types={"id": "integer", "name": "string"},
            source=ContractSource.OPENAPI
        )
        response = {"id": "not-an-int", "name": "Test"}  # id should be int

        errors = agent._validate_response(contract, response)
        assert len(errors) >= 1
        assert any("id" in str(e) and "type" in str(e).lower() for e in errors)

    def test_detects_breaking_changes(self, agent):
        """Should detect breaking changes (removed fields, type changes)."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "name", "createdAt"],  # Consumer expects createdAt
            source=ContractSource.CONSUMER
        )
        response = {"id": 1, "name": "Test", "created_at": "2024-01-01"}  # Field renamed!

        errors = agent._validate_response(contract, response)
        assert len(errors) >= 1
        assert any("createdAt" in str(e) for e in errors)

    def test_handles_nullable_fields(self, agent):
        """Should handle nullable fields correctly."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        contract = Contract(
            endpoint="/api/users",
            expected_fields=["id", "nickname"],
            nullable_fields=["nickname"],
            source=ContractSource.OPENAPI
        )
        response = {"id": 1, "nickname": None}  # nullable is OK

        errors = agent._validate_response(contract, response)
        assert len(errors) == 0


# =============================================================================
# Test Finding Generation
# =============================================================================


class TestContractFindingGeneration:
    """Tests for generating QAFinding from contract violations."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_creates_finding_for_contract_violation(self, agent):
        """Should create QAFinding for contract violations."""
        finding = agent._create_contract_finding(
            endpoint="GET /api/users",
            consumer_location="frontend/src/UserList.tsx:45",
            issue="Field 'createdAt' renamed to 'created_at'",
            expected={"field": "createdAt"},
            actual={"field": "created_at"},
        )
        assert finding.finding_id.startswith("CV-")
        assert finding.category == "contract"
        assert finding.endpoint == "GET /api/users"
        assert "createdAt" in finding.description or "createdAt" in finding.title

    def test_assigns_critical_severity_for_missing_field(self, agent):
        """Should assign critical severity for missing required fields."""
        finding = agent._create_contract_finding(
            endpoint="GET /api/users",
            consumer_location="frontend/src/UserList.tsx:45",
            issue="Required field 'id' is missing",
            expected={"field": "id", "required": True},
            actual={"field": None},
        )
        assert finding.severity == "critical"

    def test_includes_consumer_location_in_evidence(self, agent):
        """Should include consumer location in evidence."""
        finding = agent._create_contract_finding(
            endpoint="GET /api/users",
            consumer_location="frontend/src/UserList.tsx:45",
            issue="Type mismatch",
            expected={"type": "number"},
            actual={"type": "string"},
        )
        assert "frontend/src/UserList.tsx:45" in finding.evidence.get("consumer", "")


# =============================================================================
# Test Agent Run Method
# =============================================================================


class TestContractValidatorRun:
    """Tests for the main run() method."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_run_returns_agent_result(self, agent):
        """Should return AgentResult from run()."""
        context = {
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
            "base_url": "http://localhost:8000",
            "depth": QADepth.STANDARD,
        }

        with patch.object(agent, 'discover_contracts', return_value=[]):
            result = agent.run(context)
            assert hasattr(result, 'success')
            assert hasattr(result, 'output')

    def test_run_includes_contracts_checked_count(self, agent):
        """Should include count of contracts checked."""
        from swarm_attack.qa.agents.contract import Contract, ContractSource

        context = {
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
            "depth": QADepth.STANDARD,
        }

        test_contract = Contract(
            endpoint="/api/users",
            expected_fields=["id"],
            source=ContractSource.OPENAPI
        )

        with patch.object(agent, 'discover_contracts', return_value=[test_contract]):
            with patch.object(agent, '_validate_contract', return_value=[]):
                result = agent.run(context)
                assert result.output is not None
                assert "contracts_checked" in result.output

    def test_run_skips_validation_when_no_contracts(self, agent):
        """Should skip validation gracefully when no contracts found."""
        context = {
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
            "depth": QADepth.STANDARD,
        }

        with patch.object(agent, 'discover_contracts', return_value=[]):
            result = agent.run(context)
            # Should not fail, just skip
            assert result.success is True
            assert result.output.get("contracts_checked", 0) == 0

    def test_run_records_skipped_reason(self, agent):
        """Should record reason for skipped validation."""
        context = {
            "endpoints": [QAEndpoint(method="GET", path="/api/users")],
            "depth": QADepth.STANDARD,
        }

        with patch.object(agent, 'discover_contracts', return_value=[]):
            result = agent.run(context)
            # Should have skipped_reasons in output
            assert "skipped_reasons" in result.output or result.output.get("contracts_checked") == 0


# =============================================================================
# Test OpenAPI Spec Parsing
# =============================================================================


class TestOpenAPIDiscovery:
    """Tests for OpenAPI/Swagger spec parsing."""

    @pytest.fixture
    def agent(self):
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return ContractValidatorAgent(config)

    def test_finds_openapi_yaml(self, agent):
        """Should find openapi.yaml files."""
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [Path("/tmp/test/openapi.yaml")]
            specs = agent._find_openapi_specs(Path("/tmp/test"))
            assert len(specs) >= 1

    def test_finds_swagger_json(self, agent):
        """Should find swagger.json files."""
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [Path("/tmp/test/swagger.json")]
            specs = agent._find_openapi_specs(Path("/tmp/test"))
            assert len(specs) >= 1

    def test_extracts_endpoints_from_openapi(self, agent):
        """Should extract endpoints from OpenAPI spec."""
        openapi_content = {
            "openapi": "3.0.0",
            "paths": {
                "/api/users": {
                    "get": {"summary": "List users"},
                    "post": {"summary": "Create user"}
                },
                "/api/users/{id}": {
                    "get": {"summary": "Get user"}
                }
            }
        }

        endpoints = agent._extract_endpoints_from_openapi(openapi_content)
        assert len(endpoints) == 3
        methods = [e.method for e in endpoints]
        assert "GET" in methods
        assert "POST" in methods


# =============================================================================
# Test Limits Enforcement (Section 10.10)
# =============================================================================


class TestLimitsEnforcement:
    """Tests for enforcing QALimits."""

    def test_respects_max_files_limit(self):
        """Should respect max_files_for_contract_analysis limit."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        limits = QALimits(max_files_for_contract_analysis=2)
        agent = ContractValidatorAgent(config, limits=limits)

        # Create 5 mock files
        files = [f"/tmp/test/file{i}.ts" for i in range(5)]

        with patch.object(agent, '_read_file', return_value=""):
            analyzed = agent._analyze_files_for_consumers(files)
            # Should only analyze max_files_for_contract_analysis files
            assert agent._files_analyzed <= 2

    def test_respects_max_consumers_per_endpoint(self):
        """Should respect max_consumers_per_endpoint limit."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent
        config = MagicMock()
        config.repo_root = "/tmp/test"
        limits = QALimits(max_consumers_per_endpoint=3)
        agent = ContractValidatorAgent(config, limits=limits)

        # Mock finding 10 consumers
        mock_consumers = [{"endpoint": "/api/users", "file": f"file{i}.ts"} for i in range(10)]

        with patch.object(agent, '_find_all_consumers', return_value=mock_consumers):
            result = agent._get_consumers_for_endpoint("/api/users")
            # Should only return max_consumers_per_endpoint
            assert len(result) <= 3
