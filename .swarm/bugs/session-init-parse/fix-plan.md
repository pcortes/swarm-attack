# Fix Plan: session-init-parse

## Summary
Fix regex to require '::' separator for pytest test paths instead of matching any non-whitespace

## Risk Assessment
- **Risk Level:** LOW
- **Scope:** Two files with identical _parse_failures() methods: session_initializer.py and session_finalizer.py

### Risk Explanation
The fix is minimal and backward compatible: it restricts what the regex matches rather than expanding it. The new pattern is more precise and will only match valid pytest test identifiers that contain '::'. All existing valid test failure outputs will still be matched. The pattern is consistent with the more robust patterns already used in verifier.py and discovery_agent.py.

## Proposed Changes

### Change 1: swarm_attack/session_initializer.py
- **Type:** modify
- **Explanation:** Changed regex from r'FAILED\s+([^\s]+)' to r'FAILED\s+([\w/._-]+::[\w:]+)'. The new pattern requires the '::' separator that pytest uses between file path and test name (e.g., 'tests/foo.py::test_bar'). This prevents matching progress indicators like '[ 75%]' which don't contain '::'.

**Current Code:**
```python
    def _parse_failures(self, output: str) -> list[str]:
        """Parse failure messages from pytest output."""
        import re

        failures = []
        # Look for FAILED test names
        for match in re.finditer(r"FAILED\s+([^\s]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures
```

**Proposed Code:**
```python
    def _parse_failures(self, output: str) -> list[str]:
        """Parse failure messages from pytest output."""
        import re

        failures = []
        # Look for FAILED test names with :: separator (pytest format: file.py::test_name)
        # Pattern requires :: to avoid matching progress indicators like '[ 75%]'
        for match in re.finditer(r"FAILED\s+([\w/._-]+::[\w:]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures
```

### Change 2: swarm_attack/session_finalizer.py
- **Type:** modify
- **Explanation:** Identical fix as session_initializer.py. Changed regex from r'FAILED\s+([^\s]+)' to r'FAILED\s+([\w/._-]+::[\w:]+)' to require the '::' separator.

**Current Code:**
```python
    def _parse_failures(self, output: str) -> list[str]:
        """Parse failure messages from pytest output."""
        import re

        failures = []
        # Look for FAILED test names
        for match in re.finditer(r"FAILED\s+([^\s]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures
```

**Proposed Code:**
```python
    def _parse_failures(self, output: str) -> list[str]:
        """Parse failure messages from pytest output."""
        import re

        failures = []
        # Look for FAILED test names with :: separator (pytest format: file.py::test_name)
        # Pattern requires :: to avoid matching progress indicators like '[ 75%]'
        for match in re.finditer(r"FAILED\s+([\w/._-]+::[\w:]+)", output):
            failures.append(match.group(1))

        return failures[:5]  # Limit to first 5 failures
```

## Test Cases

### Test 1: test_parse_failures_ignores_progress_indicator
- **Category:** regression
- **Description:** Regression test: _parse_failures should not capture '[' from pytest progress indicators

```python
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
```

### Test 2: test_parse_failures_with_summary_format
- **Category:** edge_case
- **Description:** Test parsing of pytest short test summary format with error messages

```python
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
```

### Test 3: test_parse_failures_session_finalizer
- **Category:** regression
- **Description:** Verify session_finalizer has the same fix applied

```python
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
```

### Test 4: test_parse_failures_empty_output
- **Category:** edge_case
- **Description:** Edge case: empty or no failures in output

```python
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
```

## Potential Side Effects
- Output that previously matched incorrectly (like progress indicators) will now be correctly ignored
- Valid pytest failure output continues to match since it always contains '::'

## Rollback Plan
Revert the regex pattern in both files from r'FAILED\s+([\w/._-]+::[\w:]+)' back to r'FAILED\s+([^\s]+)'. This restores the original (buggy) behavior but doesn't break anything new.

## Estimated Effort
Small - identical 1-line regex change in 2 files, 4 test cases
