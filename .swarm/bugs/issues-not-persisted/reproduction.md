# Reproduction Results: issues-not-persisted

## Status: CONFIRMED
- **Confidence:** high
- **Attempts:** 1

## Reproduction Steps
1. Step 1: Review the `issues` command in swarm_attack/cli/feature.py:1199-1346
2. Step 2: Review the `greenlight` command in swarm_attack/cli/feature.py:1082-1196
3. Step 3: Observed that `issues` command creates issues.json via IssueCreatorAgent (line 1254) but never populates state.tasks
4. Step 4: Observed that `greenlight` command is the only place that loads issues.json and populates state.tasks (lines 1141-1186)
5. Step 5: Observed that when validation fails in `issues` command, phase goes to BLOCKED (line 1295-1297) but state.tasks remains empty

## Affected Files
- `swarm_attack/cli/feature.py`
- `swarm_attack/agents/issue_creator.py`
- `swarm_attack/agents/issue_validator.py`

## Error Message
```
Phase goes to BLOCKED, tasks[] stays empty despite Created 5 issues message
```

## Test Output
```
Test file tests/cli/test_feature_issues.py not found in test directory. Bug confirmed through static code analysis of swarm_attack/cli/feature.py
```

## Related Code Snippets

### swarm_attack/cli/feature.py:1270-1302
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

    total_cost = creator_result.cost_usd + validator_result.cost_usd

    if not validator_result.success:
        console.print(
            Panel(
                f"[red]Issue validation failed.[/red]\n\n"
                f"Error: {validator_result.errors[0] if validator_result.errors else 'Unknown error'}\n"
                f"Cost: {format_cost(total_cost)}",
                title="Issue Validation Failed",
                border_style="red",
            )
        )
        state.update_phase(FeaturePhase.BLOCKED)
        store.save(state)  # NOTE: state.tasks is EMPTY here
        raise typer.Exit(1)
```

### swarm_attack/cli/feature.py:1140-1186
```python
    # Load issues.json and populate tasks in state
    try:
        issues_content = read_file(issues_path)
        issues_data = json.loads(issues_content)
        issues_list = issues_data.get("issues", [])

        # MERGE strategy: preserve existing task progress (DONE status, outputs, commits)
        # Build a map of existing progress by issue_number
        existing_progress = {t.issue_number: t for t in state.tasks}
        preserved_count = 0

        new_tasks = []
        for issue in issues_list:
            issue_num = issue.get("order", 0)
            deps = issue.get("dependencies", [])

            # Check if we have existing progress for this issue
            existing = existing_progress.get(issue_num)

            if existing and existing.stage in (TaskStage.DONE, TaskStage.SKIPPED):
                # Preserve completed/skipped task progress
                existing.title = issue.get("title", existing.title)
                existing.dependencies = deps
                existing.estimated_size = issue.get("estimated_size", existing.estimated_size)
                new_tasks.append(existing)
                preserved_count += 1
            else:
                # Create new task or reset non-completed task
                initial_stage = TaskStage.READY if not deps else TaskStage.BACKLOG

                task = TaskRef(
                    issue_number=issue_num,
                    stage=initial_stage,
                    title=issue.get("title", "Untitled"),
                    dependencies=deps,
                    estimated_size=issue.get("estimated_size", "medium"),
                )
                new_tasks.append(task)

        state.tasks = new_tasks  # THIS IS THE ONLY PLACE tasks IS POPULATED
```

## Environment
- **python_version:** 3.13.3
- **os:** Darwin 24.6.0
- **pytest_version:** 8.3.5

## Notes
This is a design bug, not a runtime error. The `issues` command creates issues.json and displays 'Created X issues' but never populates state.tasks. The task loading logic (lines 1140-1186) exists ONLY in the `greenlight` command. When validation fails in `issues` command and phase goes to BLOCKED, state.tasks remains empty []. The fix would be to either: (1) move the task loading logic to run in `issues` command before validation, or (2) have the IssueCreatorAgent populate state.tasks after writing issues.json. This explains why 'Created 5 issues' message appears but state.tasks stays empty.
