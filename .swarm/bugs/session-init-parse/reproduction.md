# Reproduction Results: session-init-parse

## Status: CONFIRMED
- **Confidence:** high
- **Attempts:** 1

## Reproduction Steps
1. Analyzed the regex pattern r'FAILED\s+([^\s]+)' in session_initializer.py:288 and session_finalizer.py:219
2. Simulated pytest output with progress indicators (e.g., 'FAILED [ 75%]')
3. Ran Python code to verify the regex captures '[' from progress indicator brackets

## Affected Files
- `swarm_attack/session_initializer.py`
- `swarm_attack/session_finalizer.py`

## Error Message
```
Regex r'FAILED\s+([^\s]+)' incorrectly captures '[' from pytest progress indicator '[ 75%]' instead of test path
```

## Test Output
```
$ python3 -c "
import re
output = '''
tests/test_foo.py::test_bar PASSED [ 50%]
tests/test_foo.py::test_baz FAILED [ 75%]
tests/test_foo.py::test_qux PASSED [100%]

=================================== FAILURES ===================================
tests/test_foo.py::test_baz - AssertionError
'''

for match in re.finditer(r'FAILED\s+([^\s]+)', output):
    print(f'Captured: {repr(match.group(1))}')
"
Captured: '['
```

## Related Code Snippets

### swarm_attack/session_initializer.py:282-291
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

### swarm_attack/session_finalizer.py:213-222
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

### swarm_attack/agents/verifier.py:155-156
```python
        # FAILED tests/path/file.py::TestClass::test_name - Error message
        summary_pattern = r'FAILED\s+([\w/._-]+)::(\w+)::(\w+)\s+-\s+(.+)'
```

## Environment
- **python_version:** 3.13.3
- **os:** Darwin 24.6.0 arm64
- **pytest_version:** 8.3.5

## Notes
The bug is in the _parse_failures method in both session_initializer.py and session_finalizer.py. The regex r'FAILED\s+([^\s]+)' matches any non-whitespace after FAILED, including the '[' from pytest progress indicators like '[ 75%]'. The verifier.py uses a better pattern that requires '::' separators (e.g., r'FAILED\s+([\w/._-]+)::(\w+)::(\w+)\s+-\s+(.+)'). The fix should use a pattern that requires the path::test format, such as r'FAILED\s+([\w/._-]+::[\w:]+)' or similar. Note: The existing unit tests pass because they don't test with progress indicator output.
