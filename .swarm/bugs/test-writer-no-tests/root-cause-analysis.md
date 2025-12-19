# Root Cause Analysis: test-writer-no-tests

## Summary
CoderAgent creates tests in TDD mode but doesn't implement required enums before hitting max_turns

## Confidence: high

## Root Cause Location
- **File:** `swarm_attack/agents/coder.py`
- **Line:** 1275

## Root Cause Code
```python
result = self.llm.run(
    prompt,
    allowed_tools=[],
    max_turns=max_turns,
)
```

## Explanation
The CoderAgent operates in a no-tools mode (allowed_tools=[]) and must output all code via # FILE: markers in a single LLM invocation. When in TDD mode (no test file exists), the coder is instructed to: (1) create the test file first, (2) then implement the code to make tests pass. For Issue #1, the LLM successfully generates test_issue_1.py with imports for RetryStrategy and ErrorCategory, but then hits max_turns before generating the implementation file (recovery.py additions). The max_turns limit (20 by default, adjustable by ComplexityGate) caps how long the LLM can spend generating output. Since the prompt instructs 'tests first', the test file is prioritized and written, but the implementation enums never make it into recovery.py. The coder considers this 'success' because files were parsed and written, but the implementation is incomplete - creating an impossible-to-pass test file that imports non-existent classes.

## Why Tests Didn't Catch It
1. CoderAgent success check only verifies files were written (files_created not empty), not that implementation matches test imports. 2. No validation that classes imported by generated tests actually exist in generated implementation files. 3. Pre-check at coder.py:1146 (_check_tests_pass) only runs when test file already exists - in TDD mode this is skipped. 4. Verifier error message formatting at verifier.py:618 shows 'N failed, M passed' but doesn't surface pytest collection errors (ImportError) which occur before any tests run. 5. No unit tests verify coder handles max_turns exhaustion gracefully or validates test imports against implementation outputs.

## Execution Trace
1. 1. Orchestrator.run_implementation_session() starts for cos-phase8-recovery issue #1
2. 2. CoderAgent.run() is invoked with context including issue_number=1, feature_id='cos-phase8-recovery'
3. 3. CoderAgent._get_default_test_path() returns tests/generated/cos-phase8-recovery/test_issue_1.py
4. 4. Test file doesn't exist initially - coder enters 'TDD mode' (test_file_exists=False at coder.py:1133)
5. 5. CoderAgent._format_test_section() generates prompt instructing coder to CREATE tests first
6. 6. CoderAgent invokes LLM with max_turns=20 (default or adjusted by ComplexityGate)
7. 7. LLM generates test file test_issue_1.py that imports RetryStrategy, ErrorCategory from recovery.py
8. 8. CoderAgent._parse_file_outputs() parses LLM response and extracts test file content
9. 9. Test file is written successfully to tests/generated/cos-phase8-recovery/test_issue_1.py
10. 10. LLM hits max_turns limit (error_max_turns) BEFORE generating recovery.py with RetryStrategy and ErrorCategory enums
11. 11. CoderAgent returns success=True (test file was created, but implementation incomplete)
12. 12. VerifierAgent.run() is invoked and runs pytest on test_issue_1.py
13. 13. pytest fails during test collection with ImportError - cannot import RetryStrategy from recovery.py
14. 14. _parse_pytest_output() parses 'collected 0 items / 1 error' → tests_passed=0, tests_failed=0, errors=1
15. 15. issue_tests_passed = (exit_code==0 AND tests_failed==0) evaluates to False due to exit_code!=0
16. 16. Verifier returns error message: 'Issue tests failed: 0 failed, 0 passed' (misleading - doesn't mention ImportError)

## Alternative Hypotheses Considered
- Initially considered ComplexityGate rejecting the issue - ruled out because state shows BLOCKED due to 'Max retries exceeded' not split/reject
- Considered coder parsing failure (# FILE: markers not recognized) - ruled out because test file was successfully created and written
- Considered verifier bug in failure detection - partial issue: verifier correctly detects failure but error message obscures the actual ImportError
