# Root Cause Analysis: session-init-parse

## Summary
Regex r'FAILED\s+([^\s]+)' captures '[' from pytest progress indicator instead of test path

## Confidence: high

## Root Cause Location
- **File:** `swarm_attack/session_initializer.py`
- **Line:** 288

## Root Cause Code
```python
for match in re.finditer(r"FAILED\s+([^\s]+)", output):
    failures.append(match.group(1))
```

## Explanation
The regex pattern r'FAILED\s+([^\s]+)' is designed to capture any non-whitespace characters after 'FAILED '. However, pytest output format includes both inline progress indicators (e.g., 'FAILED [ 75%]' on the same line as the test result) and separate failure summary lines (e.g., 'FAILED tests/path.py::test_name - Error'). The regex incorrectly matches the '[' character from progress indicators like '[ 75%]' because it captures the first non-whitespace token after 'FAILED' without validating that it looks like a test path. The verifier.py agent uses a more robust pattern r'FAILED\s+([\w/._-]+)::' that requires the '::' separator which is part of pytest's test path format (file.py::TestClass::test_name). The fix should use a pattern that requires test path characteristics (path separator, ::, or test file extension) rather than just any non-whitespace.

## Why Tests Didn't Catch It
1. The existing unit tests in tests/unit/test_session_initializer.py mock _run_verification_tests() entirely, so they never actually test _parse_failures() with real pytest output. 2. There are no unit tests that directly test _parse_failures() with various pytest output formats. 3. The test fixtures use Mock(passed=True/False) which bypasses the actual parsing logic. 4. The same bug exists in session_finalizer.py:219 (identical code, line 219), so both files have untested parsing logic. 5. The verifier.py agent has a more robust regex but this pattern wasn't reused in the session initializer/finalizer modules.

## Execution Trace
1. 1. SessionInitializer._run_verification_tests() runs pytest on feature tests
2. 2. pytest produces output with progress indicators: 'tests/test_foo.py::test_baz FAILED [ 75%]'
3. 3. _parse_failures() is called with the pytest output string
4. 4. Regex r'FAILED\s+([^\s]+)' matches 'FAILED ' and captures the first non-whitespace after it
5. 5. The regex captures '[' from '[ 75%]' because '[' is the first non-whitespace character after 'FAILED '
6. 6. Multiple test failures each add '[' to the failures list, resulting in ['[', '[', '[', '[', '[']
7. 7. InitResult.blocked() is called with reason='Verification failed: ["[", "[", "[", "[", "["]'

## Alternative Hypotheses Considered
- Considered whether the issue was with pytest version differences in output format - ruled out because the progress indicator format '[ XX%]' is standard across pytest versions
- Considered whether there might be edge cases with test names containing brackets - ruled out because the root cause is clearly the progress indicator matching before any test path matching
