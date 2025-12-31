"""Tests for Codex auth pattern false positive prevention."""
import pytest

from swarm_attack.errors import ErrorClassifier, LLMErrorType


class TestCodexAuthPatternsFalsePositives:
    """Test that legitimate non-auth errors don't trigger AUTH_REQUIRED."""

    def test_unauthorized_access_denied_not_auth_error(self):
        """'unauthorized access denied' should NOT trigger auth error."""
        stderr = "Error: unauthorized access denied by security policy"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result != LLMErrorType.AUTH_REQUIRED, \
            f"'unauthorized access' false positive: got {result}"
        assert result == LLMErrorType.CLI_CRASH

    def test_policy_unauthorized_module_not_auth_error(self):
        """'policy unauthorized module' should NOT trigger auth error."""
        stderr = "ImportError: policy unauthorized module import detected"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result != LLMErrorType.AUTH_REQUIRED, \
            f"'policy unauthorized' false positive: got {result}"

    def test_permission_unauthorized_not_auth_error(self):
        """Permission errors with 'unauthorized' should NOT trigger auth."""
        stderr = "PermissionError: unauthorized file access to /etc/shadow"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result != LLMErrorType.AUTH_REQUIRED


class TestCodexAuthPatternsStillWork:
    """Test that legitimate auth errors still trigger AUTH_REQUIRED."""

    def test_401_unauthorized_triggers_auth_error(self):
        """HTTP 401 Unauthorized should still trigger auth error."""
        stderr = "HTTP Error: 401 Unauthorized"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_not_logged_in_triggers_auth_error(self):
        """'not logged in' should trigger auth error."""
        stderr = "Error: not logged in. Please run codex login"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_login_required_triggers_auth_error(self):
        """'login required' should trigger auth error."""
        stderr = "login required to access this resource"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_authentication_error_triggers_auth_error(self):
        """'AuthenticationError:' should trigger auth error."""
        stderr = "AuthenticationError: invalid credentials"
        result = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout="",
            returncode=1,
        )
        assert result == LLMErrorType.AUTH_REQUIRED
