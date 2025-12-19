# Bug Report: tdd-regression-phase8

## Status
- **Phase:** created
- **Created:** 2025-12-19T04:44:11.698054Z
- **Updated:** 2025-12-19T04:44:11.698054Z
- **Total Cost:** $0.00

## Description
TDD regression in cos-phase8-recovery: Issue #5 changes broke Issue #4 tests. 13 tests fail including retry_count (expected 3, got 4) and checkpoint creation. Root cause: coder doesn't run full test suite before committing, allowing later issues to break earlier ones.

### Error Message
```
AssertionError: assert 4 == 3 where 4 = Episode(...).retry_count
```

