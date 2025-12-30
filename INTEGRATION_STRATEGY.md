# Integration Strategy

## Decision: Option B - Merge Master into QA Branch

### Chosen Approach

```bash
git merge master
```

### Justification

| Criterion | Assessment |
|-----------|------------|
| Number of conflicts | 1 file (trivial) |
| Semantic complexity | None - both additions are independent |
| History preservation | Yes - maintains QA branch commits |
| Time to complete | < 30 minutes |

### Why NOT Other Options

| Option | Reason Rejected |
|--------|-----------------|
| A: Rebase | Unnecessary - only 2 QA commits, would rewrite history |
| C: Cherry-pick | Overkill - full merge is simpler with only 1 conflict |
| D: Fresh branch | Unnecessary - branches aren't significantly diverged |

## Execution Plan

### Step 1: Verify Clean State
```bash
git status  # Should be clean
git branch  # Should be feature/adaptive-qa-agent
```

### Step 2: Execute Merge
```bash
git merge master
```

### Step 3: Resolve Single Conflict
File: `swarm_attack/cli/app.py`

Resolution: Keep both CLI registrations (QA and approval)

### Step 4: Verify Tests
```bash
python -m pytest --collect-only -q  # Should show 0 errors
python -m pytest tests/ -v          # All tests pass
```

### Step 5: Commit
```bash
git add -A
git commit -m "merge: Integrate master into QA branch

- Resolved single conflict in swarm_attack/cli/app.py
- Kept both QA and approval CLI registrations
- All 2389+ tests now collect without errors"
```

## Rollback Plan

If anything goes wrong:
```bash
git merge --abort  # During merge
# OR
git reset --hard backup-qa-before-integration-20251230
```
