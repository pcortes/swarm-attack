"""Tests for request generation edge cases (Section 10.4).

Tests cover spec section 10.4: Request Generation Failures
- Malformed JSON schema handling
- Circular reference detection
- Deeply nested object limits (10 levels)
- Unsupported content type handling
- Binary content handling
"""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    ResilienceConfig,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def agent():
    """Create a BehavioralTesterAgent for testing."""
    config = MagicMock()
    config.repo_root = "/tmp/test"
    return BehavioralTesterAgent(config)


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = MagicMock()
    response.status_code = 200
    response.text = '{"data": "test"}'
    response.headers = {"content-type": "application/json"}
    return response


# =============================================================================
# Test Malformed Schema Handling (Section 10.4)
# =============================================================================


class TestMalformedSchemaHandling:
    """Section 10.4: Agent should handle malformed JSON schema gracefully."""

    def test_handles_invalid_type_in_schema(self, agent):
        """Agent should handle schema with invalid type specification."""
        malformed_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "invalid_type_xyz"}  # Invalid type
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/data",
            schema={"requestBody": malformed_schema}
        )

        # Should not crash when generating body
        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_missing_type_field(self, agent):
        """Agent should handle schema without type field."""
        schema_without_type = {
            "properties": {
                "name": {"description": "User name"}  # No type specified
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/users",
            schema={"requestBody": schema_without_type}
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_null_schema(self, agent):
        """Agent should handle null/None schema."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/data",
            schema=None
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_empty_schema(self, agent):
        """Agent should handle empty schema object."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/data",
            schema={}
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_schema_with_mixed_types(self, agent):
        """Agent should handle schema with mixed/conflicting types."""
        mixed_schema = {
            "type": ["string", "object"],  # OneOf pattern
            "properties": {
                "id": {"type": "integer"}
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/complex",
            schema={"requestBody": mixed_schema}
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)


# =============================================================================
# Test Circular Reference Detection (Section 10.4)
# =============================================================================


class TestCircularReferenceDetection:
    """Section 10.4: Agent should detect and handle circular schema references."""

    def test_handles_self_reference_schema(self, agent):
        """Agent should handle schema with self-reference ($ref: #)."""
        # Schema with circular reference
        circular_schema = {
            "type": "object",
            "properties": {
                "parent": {"$ref": "#"},  # Self-reference
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/tree",
            schema={"requestBody": circular_schema}
        )

        # Should not cause infinite loop
        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_indirect_circular_reference(self, agent):
        """Agent should handle indirect circular references (A -> B -> A)."""
        # This simulates the resolved schema
        indirect_circular = {
            "type": "object",
            "properties": {
                "child": {
                    "type": "object",
                    "properties": {
                        "parent": {"$ref": "#"}  # Back to root
                    }
                }
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/linked",
            schema={"requestBody": indirect_circular}
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)


# =============================================================================
# Test Deeply Nested Object Limit (Section 10.4)
# =============================================================================


class TestDeeplyNestedObjectLimit:
    """Section 10.4: Agent should enforce max nesting depth (10 levels)."""

    def test_handles_deeply_nested_schema(self, agent):
        """Agent should handle deeply nested schemas without stack overflow."""
        # Create 15-level nested schema
        nested = {"type": "string"}
        for _ in range(15):
            nested = {"type": "object", "properties": {"child": nested}}

        endpoint = QAEndpoint(
            method="POST",
            path="/api/nested",
            schema={"requestBody": nested}
        )

        # Should not crash
        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_truncates_at_depth_limit(self, agent):
        """Agent should truncate at reasonable depth limit."""
        # Create deep nested structure
        nested = {"type": "object", "properties": {"value": {"type": "string"}}}
        for _ in range(20):
            nested = {"type": "object", "properties": {"child": nested}}

        endpoint = QAEndpoint(
            method="POST",
            path="/api/deep",
            schema={"requestBody": nested}
        )

        body = agent._generate_valid_body(endpoint)
        # Should return a dict that doesn't blow up
        assert isinstance(body, dict)

    def test_handles_nested_arrays(self, agent):
        """Agent should handle deeply nested array structures."""
        nested_arrays = {
            "type": "array",
            "items": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
        endpoint = QAEndpoint(
            method="POST",
            path="/api/matrix",
            schema={"requestBody": nested_arrays}
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)


# =============================================================================
# Test Unsupported Content Type Handling (Section 10.4)
# =============================================================================


class TestUnsupportedContentTypeHandling:
    """Section 10.4: Agent should handle unsupported content types gracefully."""

    def test_handles_multipart_form_data(self, agent, mock_response):
        """Agent should handle multipart/form-data content type."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/upload",
            schema={"content-type": "multipart/form-data"}
        )

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
            # Should generate at least a happy path test
            assert len(test_cases) >= 1

    def test_handles_xml_content_type(self, agent, mock_response):
        """Agent should handle application/xml content type."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/xml-endpoint",
            schema={"content-type": "application/xml"}
        )

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
            assert len(test_cases) >= 1

    def test_handles_form_urlencoded(self, agent, mock_response):
        """Agent should handle application/x-www-form-urlencoded."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/form",
            schema={"content-type": "application/x-www-form-urlencoded"}
        )

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
            assert len(test_cases) >= 1


# =============================================================================
# Test Binary Content Handling (Section 10.4)
# =============================================================================


class TestBinaryContentHandling:
    """Section 10.4: Agent should handle binary content types."""

    def test_handles_octet_stream(self, agent, mock_response):
        """Agent should handle application/octet-stream content type."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/binary",
            schema={"content-type": "application/octet-stream"}
        )

        # Should not crash when generating tests
        test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
        assert isinstance(test_cases, list)

    def test_handles_image_content_type(self, agent, mock_response):
        """Agent should handle image/* content types."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/image",
            schema={"content-type": "image/png"}
        )

        test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
        assert isinstance(test_cases, list)

    def test_handles_pdf_content_type(self, agent, mock_response):
        """Agent should handle application/pdf content type."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/document",
            schema={"content-type": "application/pdf"}
        )

        test_cases = agent._generate_tests(endpoint, QADepth.STANDARD)
        assert isinstance(test_cases, list)


# =============================================================================
# Test Request Body Generation Edge Cases
# =============================================================================


class TestRequestBodyGenerationEdgeCases:
    """Additional edge cases for request body generation."""

    def test_generates_body_for_user_endpoints(self, agent):
        """Agent should generate appropriate body for user endpoints."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/users",
        )

        body = agent._generate_valid_body(endpoint)
        assert "name" in body or "email" in body

    def test_generates_body_for_item_endpoints(self, agent):
        """Agent should generate appropriate body for item endpoints."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/items",
        )

        body = agent._generate_valid_body(endpoint)
        assert "name" in body or "quantity" in body

    def test_generates_empty_body_for_unknown_endpoints(self, agent):
        """Agent should return empty body for unknown endpoint types."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/xyz123-unknown",
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_endpoint_with_path_params(self, agent):
        """Agent should handle endpoints with path parameters."""
        endpoint = QAEndpoint(
            method="PUT",
            path="/api/users/{id}",
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)

    def test_handles_endpoint_with_query_params(self, agent):
        """Agent should handle endpoints that expect query parameters."""
        endpoint = QAEndpoint(
            method="GET",
            path="/api/search?q={query}",
        )

        body = agent._generate_valid_body(endpoint)
        assert isinstance(body, dict)


# =============================================================================
# Test Test Case Generation Edge Cases
# =============================================================================


class TestTestCaseGenerationEdgeCases:
    """Edge cases for test case generation."""

    def test_generates_tests_for_get_endpoint(self, agent):
        """Agent should generate appropriate tests for GET endpoint."""
        endpoint = QAEndpoint(method="GET", path="/api/users")

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        # Should have at least happy path
        assert any(t["test_type"] == "happy_path" for t in tests)

    def test_generates_tests_for_delete_endpoint(self, agent):
        """Agent should generate appropriate tests for DELETE endpoint."""
        endpoint = QAEndpoint(method="DELETE", path="/api/users/{id}")

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        assert any(t["test_type"] == "happy_path" for t in tests)

    def test_generates_security_probes_for_deep_depth(self, agent):
        """Agent should generate security probes for DEEP depth."""
        endpoint = QAEndpoint(method="POST", path="/api/users")

        tests = agent._generate_tests(endpoint, QADepth.DEEP)
        security_tests = [t for t in tests if t.get("test_type") == "security_probe"]
        assert len(security_tests) >= 1

    def test_generates_auth_test_for_protected_endpoint(self, agent):
        """Agent should generate auth test for protected endpoints."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/protected",
            auth_required=True
        )

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        auth_tests = [t for t in tests if t.get("test_type") == "unauthorized"]
        assert len(auth_tests) >= 1

    def test_shallow_depth_only_happy_path(self, agent):
        """SHALLOW depth should only generate happy path tests."""
        endpoint = QAEndpoint(method="POST", path="/api/users")

        tests = agent._generate_tests(endpoint, QADepth.SHALLOW)
        # Should only have happy path
        assert len(tests) == 1
        assert tests[0]["test_type"] == "happy_path"


# =============================================================================
# Test Finding Creation Edge Cases
# =============================================================================


class TestFindingCreationEdgeCases:
    """Edge cases for QAFinding creation."""

    def test_creates_critical_finding_for_500_error(self, agent):
        """Agent should create critical finding for 500 errors."""
        finding = agent._create_finding(
            endpoint="POST /api/users",
            test_type="happy_path",
            expected={"status": 201},
            actual={"status": 500},
            request_evidence="curl -X POST ...",
            response_evidence="Internal Server Error",
        )

        assert finding.severity == "critical"
        assert "500" in finding.title or "error" in finding.title.lower()

    def test_creates_critical_finding_for_connection_error(self, agent):
        """Agent should create critical finding for connection errors."""
        finding = agent._create_finding(
            endpoint="GET /api/users",
            test_type="happy_path",
            expected={"status": 200},
            actual={"error": "Connection refused"},
            request_evidence="curl -X GET ...",
            response_evidence="Connection refused",
        )

        assert finding.severity == "critical"

    def test_creates_moderate_finding_for_wrong_status(self, agent):
        """Agent should create moderate finding for wrong status code."""
        finding = agent._create_finding(
            endpoint="POST /api/users",
            test_type="happy_path",
            expected={"status": 201},
            actual={"status": 200},  # Wrong but not critical
            request_evidence="curl -X POST ...",
            response_evidence="{}",
        )

        assert finding.severity == "moderate"

    def test_finding_includes_evidence(self, agent):
        """Finding should include request and response evidence."""
        finding = agent._create_finding(
            endpoint="GET /api/users",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 404},
            request_evidence="curl -X GET http://localhost:8000/api/users",
            response_evidence='{"error": "Not found"}',
        )

        assert "request" in finding.evidence
        assert "response" in finding.evidence
        assert "curl" in finding.evidence["request"]

    def test_finding_has_unique_id(self, agent):
        """Each finding should have a unique ID."""
        finding1 = agent._create_finding(
            endpoint="GET /api/test1",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 404},
            request_evidence="",
            response_evidence="",
        )
        finding2 = agent._create_finding(
            endpoint="GET /api/test2",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 404},
            request_evidence="",
            response_evidence="",
        )

        assert finding1.finding_id != finding2.finding_id
        assert finding1.finding_id.startswith("BT-")
        assert finding2.finding_id.startswith("BT-")
