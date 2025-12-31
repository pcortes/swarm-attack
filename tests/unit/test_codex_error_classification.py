"""
Unit tests for Codex error classification.

Tests that ErrorClassifier.classify_codex_error correctly distinguishes
between real authentication errors and false positives from content
mentioning authentication.

Bug Context:
- The pattern r"authentication" was too broad and matched content in stdout
- This caused false positives when PRDs/specs mentioned "authentication"
- Fix: Only check stderr for auth patterns, not stdout (user content)
"""

import pytest

from swarm_attack.errors import ErrorClassifier, LLMErrorType


class TestCodexAuthErrorClassification:
    """Tests for classify_codex_error auth pattern matching."""

    # ========================================================================
    # FALSE POSITIVE TESTS - These MUST NOT trigger AUTH_REQUIRED
    # ========================================================================

    def test_no_false_positive_from_stdout_content_mentioning_auth(self):
        """Content mentioning 'authentication' in stdout should NOT trigger AUTH_REQUIRED.

        This is the primary bug: PRDs and specs that discuss authentication features
        were incorrectly triggering auth errors when Codex failed for unrelated reasons.
        """
        result = ErrorClassifier.classify_codex_error(
            stderr="Error: command failed",
            stdout="The user authentication flow should validate tokens",
            returncode=1
        )
        assert result != LLMErrorType.AUTH_REQUIRED, (
            "Content mentioning 'authentication' in stdout should not trigger AUTH_REQUIRED"
        )
        assert result == LLMErrorType.CLI_CRASH

    def test_no_false_positive_from_prompt_about_auth_features(self):
        """Prompts asking about auth features should NOT trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="timeout exceeded",
            stdout="Review the spec for user authentication and authorization",
            returncode=1
        )
        assert result != LLMErrorType.AUTH_REQUIRED

    def test_no_false_positive_from_llm_response_discussing_auth(self):
        """LLM responses discussing authentication should NOT trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="process terminated",
            stdout="The authentication module implements OAuth2 with JWT tokens",
            returncode=1
        )
        assert result != LLMErrorType.AUTH_REQUIRED

    def test_no_false_positive_when_unauthorized_in_code_context(self):
        """'unauthorized' in code/spec context should NOT trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="command failed",
            stdout="return 401 Unauthorized if token is invalid",  # Code snippet
            returncode=1
        )
        assert result != LLMErrorType.AUTH_REQUIRED

    # ========================================================================
    # TRUE POSITIVE TESTS - These MUST trigger AUTH_REQUIRED
    # ========================================================================

    def test_detects_not_logged_in_error(self):
        """'not logged in' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="Error: not logged in. Please run `codex login`",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_401_unauthorized_error(self):
        """'401 Unauthorized' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="exceeded retry limit, last status: 401 Unauthorized",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_authentication_error_from_api(self):
        """'AuthenticationError:' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="AuthenticationError: the API key is missing or invalid",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_login_required_error(self):
        """'login required' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="login required: please authenticate first",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_session_expired_error(self):
        """'session expired' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="Error: session expired. Please run codex login again.",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_codex_login_prompt(self):
        """'please run `codex login`' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="please run `codex login` to authenticate",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_detects_token_exchange_error(self):
        """'Token exchange error' in stderr should trigger AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="Token exchange error: error sending request",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    # ========================================================================
    # EDGE CASES
    # ========================================================================

    def test_success_returncode_never_triggers_auth_error(self):
        """Return code 0 should never classify as an error, regardless of content."""
        result = ErrorClassifier.classify_codex_error(
            stderr="",
            stdout="authentication module loaded successfully",
            returncode=0
        )
        # With returncode=0, this shouldn't even be called, but if it is:
        assert result == LLMErrorType.UNKNOWN

    def test_empty_stderr_and_stdout_with_failure(self):
        """Empty outputs with non-zero exit should be CLI_CRASH, not AUTH_REQUIRED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.CLI_CRASH

    def test_auth_error_in_stderr_takes_precedence(self):
        """Auth error in stderr should be detected even if stdout has other content."""
        result = ErrorClassifier.classify_codex_error(
            stderr="not logged in",
            stdout="This is some random output about code",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED

    def test_case_insensitive_matching_in_stderr(self):
        """Auth patterns should match case-insensitively in stderr."""
        result = ErrorClassifier.classify_codex_error(
            stderr="NOT LOGGED IN",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.AUTH_REQUIRED


class TestCodexRateLimitClassification:
    """Tests for rate limit error classification."""

    def test_detects_rate_limit_in_stderr(self):
        """'rate limit' in stderr should trigger RATE_LIMIT."""
        result = ErrorClassifier.classify_codex_error(
            stderr="rate limit exceeded, please wait",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.RATE_LIMIT

    def test_no_false_positive_rate_limit_from_content(self):
        """Content discussing rate limits should NOT trigger RATE_LIMIT error."""
        result = ErrorClassifier.classify_codex_error(
            stderr="command failed",
            stdout="The API implements rate limiting to prevent abuse",
            returncode=1
        )
        assert result != LLMErrorType.RATE_LIMIT


class TestCodexServerErrorClassification:
    """Tests for server error classification."""

    def test_detects_503_error(self):
        """503 in stderr should trigger SERVER_OVERLOADED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="Error: 503 Service Unavailable",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.SERVER_OVERLOADED

    def test_detects_529_error(self):
        """529 in stderr should trigger SERVER_OVERLOADED."""
        result = ErrorClassifier.classify_codex_error(
            stderr="Error: 529 overloaded",
            stdout="",
            returncode=1
        )
        assert result == LLMErrorType.SERVER_OVERLOADED
