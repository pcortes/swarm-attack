"""Tests for response validation edge cases (Section 10.5).

Tests cover spec section 10.5: Response Validation Failures
- Malformed JSON response handling
- Non-UTF8 response handling
- Streaming response handling
- Response size limits
- Empty response body handling
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
# Test Malformed JSON Response (Section 10.5)
# =============================================================================


class TestMalformedJSONResponse:
    """Section 10.5: Agent should handle malformed JSON responses."""

    def test_handles_invalid_json_response(self, agent):
        """Agent should handle responses with invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "{ invalid json }"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should pass since status code matches
            assert result["passed"] is True

    def test_handles_truncated_json_response(self, agent):
        """Agent should handle truncated JSON responses."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test", "nested": {"val'  # Truncated
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Status code check should still work
            assert result["passed"] is True

    def test_handles_json_with_trailing_content(self, agent):
        """Agent should handle JSON with trailing garbage."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}extra garbage here'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Empty Response Handling (Section 10.5)
# =============================================================================


class TestEmptyResponseHandling:
    """Section 10.5: Agent should handle empty response bodies."""

    def test_handles_204_no_content(self, agent):
        """Agent should handle 204 No Content responses correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="DELETE", path="/api/items/1")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 204},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_empty_200_response(self, agent):
        """Agent should handle 200 with empty body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_whitespace_only_response(self, agent):
        """Agent should handle responses with only whitespace."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "   \n\t  "
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_null_json_response(self, agent):
        """Agent should handle null JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "null"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Large Response Handling (Section 10.5)
# =============================================================================


class TestLargeResponseHandling:
    """Section 10.5: Agent should handle large responses."""

    def test_truncates_large_response_in_evidence(self, agent):
        """Agent should truncate large responses during test execution.

        Note: Truncation happens in _execute_test, not _create_finding.
        The _execute_test method truncates response.text[:500] before passing
        to _create_finding.
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "x" * 10000
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/large")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            finding = result.get("finding")
            # Evidence should be truncated (the implementation truncates at 500 chars)
            assert finding is not None
            assert len(finding.evidence.get("response", "")) <= 500

    def test_handles_megabyte_response(self, agent):
        """Agent should handle very large responses without crashing."""
        large_response = "x" * 1_000_000  # 1MB

        # Creating finding shouldn't crash
        finding = agent._create_finding(
            endpoint="GET /api/huge",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 500},
            request_evidence="curl -X GET ...",
            response_evidence=large_response,
        )
        assert finding is not None
        assert finding.finding_id.startswith("BT-")

    def test_large_response_test_execution(self, agent):
        """Agent should handle large response during test execution."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "x" * 2000  # Large error response
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should still create finding with truncated response
            assert result["passed"] is False
            assert result.get("finding") is not None
            assert len(result["finding"].evidence.get("response", "")) <= 500


# =============================================================================
# Test Non-UTF8 Response Handling (Section 10.5)
# =============================================================================


class TestNonUTF8ResponseHandling:
    """Section 10.5: Agent should handle non-UTF8 responses."""

    def test_handles_binary_in_text_field(self, agent):
        """Agent should handle binary data that ends up in text field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulate binary data as string
        mock_response.text = "Binary:\x00\x01\x02data"
        mock_response.headers = {"content-type": "application/octet-stream"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/binary")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_utf16_content(self, agent):
        """Agent should handle UTF-16 encoded content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Test content with special chars"
        mock_response.headers = {"content-type": "text/plain; charset=utf-16"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/text")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Content-Type Mismatch Handling (Section 10.5)
# =============================================================================


class TestContentTypeMismatchHandling:
    """Section 10.5: Agent should handle content-type mismatches."""

    def test_handles_json_without_json_content_type(self, agent):
        """Agent should handle JSON content with text/plain content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_response.headers = {"content-type": "text/plain"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_html_with_json_content_type(self, agent):
        """Agent should handle HTML content with application/json content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Error page</body></html>"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Status matches, so it passes
            assert result["passed"] is True

    def test_handles_missing_content_type_header(self, agent):
        """Agent should handle responses without content-type header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_response.headers = {}  # No content-type

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Error Response Handling (Section 10.5)
# =============================================================================


class TestErrorResponseHandling:
    """Section 10.5: Agent should handle various error response formats."""

    def test_handles_error_as_string(self, agent):
        """Agent should handle error response as plain string."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.headers = {"content-type": "text/plain"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            finding = result.get("finding")
            assert finding is not None
            assert finding.severity == "critical"

    def test_handles_error_as_json(self, agent):
        """Agent should handle error response as JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"error": "Internal error", "code": "ERR_500"}'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            finding = result.get("finding")
            assert "ERR_500" in finding.evidence.get("response", "")

    def test_handles_html_error_page(self, agent):
        """Agent should handle HTML error page response."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = """<!DOCTYPE html>
        <html>
        <head><title>502 Bad Gateway</title></head>
        <body><h1>Bad Gateway</h1></body>
        </html>"""
        mock_response.headers = {"content-type": "text/html"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            assert result["finding"].actual.get("status") == 502


# =============================================================================
# Test Response Headers Handling (Section 10.5)
# =============================================================================


class TestResponseHeadersHandling:
    """Section 10.5: Agent should handle various response headers."""

    def test_handles_response_with_many_headers(self, agent):
        """Agent should handle responses with many headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_response.headers = {
            "content-type": "application/json",
            "x-request-id": "abc123",
            "x-rate-limit-remaining": "100",
            "cache-control": "no-cache",
            "x-custom-header-1": "value1",
            "x-custom-header-2": "value2",
        }

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_empty_header_values(self, agent):
        """Agent should handle headers with empty values."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_response.headers = {
            "content-type": "application/json",
            "x-empty": "",
        }

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Special Response Formats (Section 10.5)
# =============================================================================


class TestSpecialResponseFormats:
    """Section 10.5: Agent should handle special response formats."""

    def test_handles_json_array_response(self, agent):
        """Agent should handle JSON array as response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '[{"id": 1}, {"id": 2}, {"id": 3}]'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/items")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_json_primitive_response(self, agent):
        """Agent should handle JSON primitive (string, number) as response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '"just a string"'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/status")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_number_response(self, agent):
        """Agent should handle JSON number as response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "42"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/count")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_handles_boolean_response(self, agent):
        """Agent should handle JSON boolean as response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "true"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/enabled")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Finding Evidence Quality (Section 10.5)
# =============================================================================


class TestFindingEvidenceQuality:
    """Section 10.5: Findings should have quality evidence."""

    def test_evidence_includes_request_curl(self, agent):
        """Evidence should include curl-style request."""
        finding = agent._create_finding(
            endpoint="GET /api/test",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 404},
            request_evidence="curl -X GET http://localhost:8000/api/test",
            response_evidence='{"error": "Not found"}',
        )
        assert "curl" in finding.evidence["request"]

    def test_evidence_preserves_response_content(self, agent):
        """Evidence should preserve response content."""
        response_content = '{"error": "Resource not found", "id": "abc123"}'
        finding = agent._create_finding(
            endpoint="GET /api/test",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 404},
            request_evidence="curl -X GET ...",
            response_evidence=response_content,
        )
        # Response should be preserved (up to truncation limit)
        assert finding.evidence["response"] == response_content

    def test_evidence_truncation_preserves_beginning(self, agent):
        """When truncating during test execution, should preserve beginning of response.

        Note: Truncation happens in _execute_test via response.text[:500], not in
        _create_finding. This test verifies the truncation behavior through the
        execution path.
        """
        long_response = "START_MARKER" + "x" * 10000 + "END_MARKER"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = long_response
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/test")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            finding = result.get("finding")
            assert finding is not None
            # Should preserve start
            assert finding.evidence["response"].startswith("START_MARKER")
            # Should be truncated (won't have end marker)
            assert "END_MARKER" not in finding.evidence["response"]


# =============================================================================
# Test BOM and Special Characters (Section 10.5)
# =============================================================================


class TestBOMAndSpecialCharacters:
    """Section 10.5: Agent should handle BOM and special characters in responses."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_utf8_bom_at_start_of_json(self, agent):
        """Agent should handle UTF-8 BOM at start of JSON response."""
        # UTF-8 BOM is \xef\xbb\xbf
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '\ufeff{"data": "test"}'  # BOM + JSON
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should pass since status code matches (BOM shouldn't crash)
            assert result["passed"] is True

    def test_should_handle_empty_body_with_json_content_type(self, agent):
        """Agent should handle empty body with application/json content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""  # Empty body
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_json_with_unicode_escape_sequences(self, agent):
        """Agent should handle JSON with unicode escape sequences."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"emoji": "\\u2764", "text": "\\u0048\\u0065\\u006c\\u006c\\u006f"}'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Encoding Edge Cases (Section 10.5)
# =============================================================================


class TestEncodingEdgeCases:
    """Section 10.5: Agent should handle various encoding edge cases."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_latin1_encoded_response(self, agent):
        """Agent should handle Latin-1 encoded response without charset header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Latin-1 characters
        mock_response.text = "Caf\xe9 au lait"
        mock_response.headers = {"content-type": "text/plain"}  # No charset

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/text")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_mixed_encoding_content(self, agent):
        """Agent should handle response with mixed encoding characters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mix of ASCII, Unicode, and potentially problematic characters
        mock_response.text = "Hello \u4e16\u754c - Caf\xe9"
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_null_bytes_in_response(self, agent):
        """Agent should handle null bytes in text response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "data\x00with\x00null\x00bytes"
        mock_response.headers = {"content-type": "text/plain"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Streaming Response Edge Cases (Section 10.5)
# =============================================================================


class TestStreamingResponseEdgeCases:
    """Section 10.5: Agent should handle streaming response edge cases."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_ndjson_response(self, agent):
        """Agent should handle NDJSON (newline-delimited JSON) response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"id": 1, "name": "a"}\n{"id": 2, "name": "b"}\n{"id": 3, "name": "c"}'
        mock_response.headers = {"content-type": "application/x-ndjson"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/stream")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_sse_response_format(self, agent):
        """Agent should handle Server-Sent Events (SSE) response format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "event: message\ndata: {\"id\": 1}\n\nevent: message\ndata: {\"id\": 2}\n\n"
        mock_response.headers = {"content-type": "text/event-stream"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/events")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_chunked_transfer_encoding_header(self, agent):
        """Agent should handle chunked transfer-encoding header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "complete"}'
        mock_response.headers = {
            "content-type": "application/json",
            "transfer-encoding": "chunked"
        }

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_partial_json_in_stream(self, agent):
        """Agent should handle partial JSON that may occur in streaming."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulates partial chunk - incomplete JSON
        mock_response.text = '{"data": "te'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/stream")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should still pass based on status code
            assert result["passed"] is True


# =============================================================================
# Test Extreme Large Response Cases (Section 10.5)
# =============================================================================


class TestExtremeLargeResponses:
    """Section 10.5: Agent should handle extreme large response edge cases."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_10mb_response_without_crashing(self, agent):
        """Agent should handle response >10MB without crashing."""
        large_response = "x" * 10_000_000  # 10MB

        # Test via _create_finding - shouldn't crash
        finding = agent._create_finding(
            endpoint="GET /api/huge",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 500},
            request_evidence="curl -X GET ...",
            response_evidence=large_response,
        )
        assert finding is not None
        assert finding.finding_id.startswith("BT-")

    def test_should_handle_response_with_many_array_elements(self, agent):
        """Agent should handle response with many array elements."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Generate a large array (simulated for efficiency)
        mock_response.text = "[" + ",".join('{"id":' + str(i) + '}' for i in range(1000)) + "]"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/items")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_deeply_nested_json_100_levels(self, agent):
        """Agent should handle deeply nested JSON (100+ levels)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Build deeply nested JSON
        nested = '"value"'
        for i in range(100):
            nested = '{"level' + str(i) + '":' + nested + '}'
        mock_response.text = nested
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/nested")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_very_long_string_value_in_json(self, agent):
        """Agent should handle JSON with very long string value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        long_string = "a" * 100000
        mock_response.text = '{"content": "' + long_string + '"}'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Additional Content-Type Mismatches (Section 10.5)
# =============================================================================


class TestAdditionalContentTypeMismatches:
    """Section 10.5: Additional content-type mismatch edge cases."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_json_body_with_text_html_content_type(self, agent):
        """Agent should handle JSON body with text/html content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"valid": "json"}'
        mock_response.headers = {"content-type": "text/html"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_xml_body_with_json_content_type(self, agent):
        """Agent should handle XML body with application/json content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<?xml version="1.0"?><root><data>test</data></root>'
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Status matches, so it passes
            assert result["passed"] is True

    def test_should_handle_multipart_content_type(self, agent):
        """Agent should handle multipart content-type header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "--boundary\r\nContent-Type: text/plain\r\n\r\ndata\r\n--boundary--"
        mock_response.headers = {"content-type": "multipart/form-data; boundary=boundary"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/upload")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_charset_in_content_type(self, agent):
        """Agent should handle charset specification in content-type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "test"}'
        mock_response.headers = {"content-type": "application/json; charset=iso-8859-1"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Malformed JSON Edge Cases (Section 10.5)
# =============================================================================


class TestMalformedJSONEdgeCases:
    """Section 10.5: Additional malformed JSON edge cases."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_json_with_unquoted_keys(self, agent):
        """Agent should handle JSON with unquoted keys (invalid JSON)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{key: "value"}'  # Invalid - keys must be quoted
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Status code check still works
            assert result["passed"] is True

    def test_should_handle_json_with_single_quotes(self, agent):
        """Agent should handle JSON with single quotes (invalid JSON)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "{'key': 'value'}"  # Invalid - must use double quotes
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_json_with_trailing_comma(self, agent):
        """Agent should handle JSON with trailing comma (invalid JSON)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"key": "value",}'  # Invalid - trailing comma
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_should_handle_json_with_comments(self, agent):
        """Agent should handle JSON with comments (invalid JSON)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"key": "value" /* comment */}'  # Invalid - no comments in JSON
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Request/Response Timeout Edge Cases (Section 10.5)
# =============================================================================


class TestTimeoutEdgeCases:
    """Section 10.5: Agent should handle timeout scenarios gracefully."""

    @pytest.fixture
    def agent(self):
        """Create a BehavioralTesterAgent for testing."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_should_handle_timeout_exception_gracefully(self, agent):
        """Agent should handle timeout exception during request."""
        from requests.exceptions import Timeout

        with patch.object(agent, '_make_request_with_retry', side_effect=Timeout("Request timed out")):
            endpoint = QAEndpoint(method="GET", path="/api/slow")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should handle gracefully (not crash)
            assert result["passed"] is False
            assert "error" in result or result.get("finding") is not None

    def test_should_handle_connection_reset_error(self, agent):
        """Agent should handle connection reset errors."""
        from requests.exceptions import ConnectionError

        with patch.object(agent, '_make_request_with_retry', side_effect=ConnectionError("Connection reset")):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
