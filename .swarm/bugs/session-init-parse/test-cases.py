"""
Generated test cases for bug: session-init-parse

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: _parse_failures should not capture '[' from pytest progress indicators
def test_parse_failures_ignores_progress_indicator():
    """Regression test for bug: regex captured '[' from '[ 75%]' progress indicator."""
    from swarm_attack.session_initializer import SessionInitializer
    from unittest.mock import Mock
    
    # Create a minimal initializer for testing
    config = Mock()
    config.repo_root = '/tmp'
    initializer = SessionInitializer(config, Mock(), Mock())
    
    # Pytest output with progress indicators (the problematic format)
    pytest_output = '''tests/test_foo.py::test_one FAILED [ 25%]
tests/test_foo.py::test_two PASSED [ 50%]
tests/test_bar.py::test_three FAILED [ 75%]
tests/test_bar.py::test_four PASSED [100%]
'''
    
    failures = initializer._parse_failures(pytest_output)
    
    # Should capture the full test paths, not '['
    assert '[' not in failures, f"Should not capture '[' from progress indicator, got: {failures}"
    assert len(failures) == 2
    assert 'tests/test_foo.py::test_one' in failures
    assert 'tests/test_bar.py::test_three' in failures

# Test parsing of pytest short test summary format with error messages
def test_parse_failures_with_summary_format():
    """Test parsing pytest summary format: FAILED path::test - Error."""
    from swarm_attack.session_initializer import SessionInitializer
    from unittest.mock import Mock
    
    config = Mock()
    config.repo_root = '/tmp'
    initializer = SessionInitializer(config, Mock(), Mock())
    
    # Pytest short test summary format
    pytest_output = '''=== short test summary info ===
FAILED tests/unit/test_user.py::test_create_user - NameError: name 'datetime' is not defined
FAILED tests/unit/test_auth.py::TestLogin::test_login - AssertionError: expected True
'''
    
    failures = initializer._parse_failures(pytest_output)
    
    assert len(failures) == 2
    # Should capture up to and including the test identifier
    assert 'tests/unit/test_user.py::test_create_user' in failures
    assert 'tests/unit/test_auth.py::TestLogin::test_login' in failures

# Verify session_finalizer has the same fix applied
def test_parse_failures_session_finalizer():
    """Verify session_finalizer._parse_failures also handles progress indicators."""
    from swarm_attack.session_finalizer import SessionFinalizer
    from unittest.mock import Mock
    
    config = Mock()
    config.repo_root = '/tmp'
    finalizer = SessionFinalizer(config, Mock(), Mock(), Mock())
    
    # Pytest output with progress indicators
    pytest_output = '''tests/test_api.py::test_endpoint FAILED [ 33%]
tests/test_api.py::test_health PASSED [ 66%]
tests/test_api.py::test_error FAILED [100%]
'''
    
    failures = finalizer._parse_failures(pytest_output)
    
    # Should not capture '[' from progress indicators
    assert '[' not in failures, f"Should not capture '[', got: {failures}"
    assert len(failures) == 2
    assert 'tests/test_api.py::test_endpoint' in failures
    assert 'tests/test_api.py::test_error' in failures

# Edge case: empty or no failures in output
def test_parse_failures_empty_output():
    """Test _parse_failures with no failures."""
    from swarm_attack.session_initializer import SessionInitializer
    from unittest.mock import Mock
    
    config = Mock()
    config.repo_root = '/tmp'
    initializer = SessionInitializer(config, Mock(), Mock())
    
    # Test empty output
    assert initializer._parse_failures('') == []
    
    # Test output with only passing tests
    passing_output = '''tests/test_foo.py::test_one PASSED [ 50%]
tests/test_foo.py::test_two PASSED [100%]
===== 2 passed =====
'''
    assert initializer._parse_failures(passing_output) == []

