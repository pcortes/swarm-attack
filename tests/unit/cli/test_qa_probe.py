"""Tests for qa probe CLI command."""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

runner = CliRunner()


class TestQaProbeCommand:
    """Tests for the qa probe command."""

    def test_probe_valid_url_returns_result(self):
        """qa probe with valid URL returns a result."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.text = '{"status": "ok"}'
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, ["probe", "http://localhost:8080/api/health"])

            assert result.exit_code == 0
            assert "200" in result.stdout

    def test_probe_post_method(self):
        """qa probe with --method POST uses POST request."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.text = '{"id": 1}'
            mock_response.elapsed.total_seconds.return_value = 0.3
            mock_post.return_value = mock_response

            result = runner.invoke(qa_app, ["probe", "http://localhost:8080/api/users", "--method", "POST"])

            assert result.exit_code == 0
            mock_post.assert_called_once()

    def test_probe_with_custom_headers(self):
        """qa probe with --header adds custom headers."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = ''
            mock_response.elapsed.total_seconds.return_value = 0.2
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, [
                "probe", "http://localhost:8080/api/health",
                "--header", "Authorization: Bearer token123"
            ])

            assert result.exit_code == 0
            # Verify headers were passed
            call_kwargs = mock_get.call_args
            assert 'headers' in call_kwargs.kwargs
            assert 'Authorization' in call_kwargs.kwargs['headers']

    def test_probe_with_json_body(self):
        """qa probe with --body sends JSON body."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.headers = {}
            mock_response.text = '{"created": true}'
            mock_response.elapsed.total_seconds.return_value = 0.4
            mock_post.return_value = mock_response

            result = runner.invoke(qa_app, [
                "probe", "http://localhost:8080/api/users",
                "--method", "POST",
                "--body", '{"name": "test"}'
            ])

            assert result.exit_code == 0

    def test_probe_expect_status_match(self):
        """qa probe with --expect matching status shows success."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = ''
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, [
                "probe", "http://localhost:8080/api/health",
                "--expect", "200"
            ])

            assert result.exit_code == 0
            assert "PASS" in result.stdout or "200" in result.stdout

    def test_probe_expect_status_mismatch(self):
        """qa probe with --expect mismatching status shows failure."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.headers = {}
            mock_response.text = 'Internal Server Error'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, [
                "probe", "http://localhost:8080/api/health",
                "--expect", "200"
            ])

            # Should indicate failure or mismatch
            assert "FAIL" in result.stdout or "500" in result.stdout

    def test_probe_timeout_option(self):
        """qa probe with --timeout sets request timeout."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = ''
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, [
                "probe", "http://localhost:8080/api/health",
                "--timeout", "5"
            ])

            assert result.exit_code == 0
            # Verify timeout was passed
            call_kwargs = mock_get.call_args
            assert 'timeout' in call_kwargs.kwargs
            assert call_kwargs.kwargs['timeout'] == 5.0

    def test_probe_invalid_url(self):
        """qa probe with invalid URL shows error."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_get.side_effect = Exception("Invalid URL")

            result = runner.invoke(qa_app, ["probe", "not-a-valid-url"])

            # Should show error or fail gracefully
            assert result.exit_code != 0 or "error" in result.stdout.lower()

    def test_probe_missing_url_argument(self):
        """qa probe without URL argument shows usage error."""
        from swarm_attack.cli.qa import qa_app

        result = runner.invoke(qa_app, ["probe"])

        # Should show usage error
        assert result.exit_code != 0

    def test_probe_output_shows_status_code(self):
        """qa probe output shows the response status code."""
        from swarm_attack.cli.qa import qa_app

        with patch('httpx.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.text = 'Not Found'
            mock_response.elapsed.total_seconds.return_value = 0.2
            mock_get.return_value = mock_response

            result = runner.invoke(qa_app, ["probe", "http://localhost:8080/api/missing"])

            assert result.exit_code == 0
            assert "404" in result.stdout
