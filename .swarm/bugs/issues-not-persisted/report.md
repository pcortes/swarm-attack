# Bug Report: issues-not-persisted

## Status
- **Phase:** created
- **Created:** 2026-01-01T03:49:17.018219Z
- **Updated:** 2026-01-01T03:49:17.018219Z
- **Total Cost:** $0.00

## Description
Issues command creates issues.json but never populates state.tasks - tasks only loaded in greenlight command, so when validation fails, state.tasks stays empty despite 'Created X issues' message

### Test Path
`tests/cli/test_feature_issues.py`

### Error Message
```
Phase goes to BLOCKED, tasks[] stays empty despite Created 5 issues message
```

