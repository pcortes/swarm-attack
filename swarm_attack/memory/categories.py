"""Memory category constants for Swarm Attack.

These constants define the categories used to classify memory entries
in the persistent memory store for cross-session learning.
"""

# Schema drift detection - recorded when LLM-generated code
# violates existing patterns or class definitions
SCHEMA_DRIFT = "schema_drift"

# Test failure patterns - recorded when tests fail in specific ways
# to help future sessions avoid similar issues
TEST_FAILURE = "test_failure"

# Recovery patterns - successful recovery strategies that can be
# reused when similar blockers are encountered
RECOVERY_PATTERN = "recovery_pattern"

# Implementation success - patterns that led to successful
# implementations, for reinforcing good practices
IMPLEMENTATION_SUCCESS = "implementation_success"

# Bug patterns - recurring bug patterns to help identify
# and prevent similar issues in future sessions
BUG_PATTERN = "bug_pattern"
