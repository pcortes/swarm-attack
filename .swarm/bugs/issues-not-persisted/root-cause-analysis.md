# Root Cause Analysis: issues-not-persisted

## Summary
issues command never populates state.tasks - task loading only in greenlight

## Confidence: high

## Root Cause Location
- **File:** `swarm_attack/cli/feature.py`
- **Line:** 1270

## Root Cause Code
```python
issues_count = creator_result.output.get("count", 0)
console.print(f"[green]Created {issues_count} issues[/green]")

# Update phase to ISSUES_VALIDATING
state.update_phase(FeaturePhase.ISSUES_VALIDATING)
store.save(state)

# Run IssueValidatorAgent
issue_validator = IssueValidatorAgent(config, state_store=store)

with console.status("[yellow]Validating issues...[/yellow]"):
    validator_result = issue_validator.run({"feature_id": feature_id})
```

## Explanation
The issues() command creates issues.json via IssueCreatorAgent and displays 'Created X issues' but never populates state.tasks. The task loading logic (reading issues.json and creating TaskRef objects) exists ONLY in the greenlight() command at lines 1140-1180. This is a design flaw: the issues() command should load tasks into state after creating issues.json, so that when validation fails and phase goes to BLOCKED, the state still contains the task list for debugging/recovery. Currently, if validation fails, the user sees 'Created 5 issues' but state.tasks stays empty, which is confusing and makes recovery harder.

## Why Tests Didn't Catch It
1. No unit tests exist for the issues() CLI command itself - the test file tests/cli/test_feature_issues.py does not exist. 2. Existing tests for IssueCreatorAgent only test the agent in isolation, not the CLI command flow. 3. Integration tests for the full pipeline typically test the happy path where greenlight() is called after issues(), which masks this bug. 4. The bug only manifests when validation fails (BLOCKED phase), which is an edge case not covered by tests.

## Execution Trace
1. 1. User runs 'swarm-attack issues my-feature' CLI command
2. 2. issues() function at feature.py:1199 loads state from StateStore
3. 3. IssueCreatorAgent.run() is called at line 1254, generates issues.json
4. 4. issues_count is extracted from creator_result.output.get('count', 0) and displayed
5. 5. IssueValidatorAgent.run() validates the issues at line 1281
6. 6. If validation fails, phase is set to BLOCKED at line 1295 and state is saved
7. 7. state.tasks remains [] because task loading logic only exists in greenlight() at lines 1140-1180
8. 8. User sees 'Created 5 issues' message but state.tasks is empty []

## Alternative Hypotheses Considered
- Initially considered whether IssueCreatorAgent should populate state.tasks directly - ruled out because agents should not mutate state, the CLI layer should do this
- Considered whether this is intentional design (tasks only loaded in greenlight) - ruled out because it causes confusing UX when validation fails
