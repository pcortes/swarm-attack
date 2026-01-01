# Fix Plan: issues-not-persisted

## Summary
Extract task loading logic into helper function and call it from both issues() and greenlight()

## Risk Assessment
- **Risk Level:** LOW
- **Scope:** Single file (feature.py) - adds helper function and one new call site

### Risk Explanation
The fix extracts existing logic into a helper function and calls it from an additional location. The task loading logic is unchanged, just refactored. greenlight() continues to work identically. The new call in issues() uses the same proven logic.

## Proposed Changes

### Change 1: swarm_attack/cli/feature.py
- **Type:** modify
- **Explanation:** Replace inline task loading logic in greenlight() with call to new helper function _load_tasks_from_issues()

**Current Code:**
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
                # Update metadata from issues.json but keep stage and outputs
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

        state.tasks = new_tasks

        console.print(f"[dim]Loaded {len(state.tasks)} tasks from issues.json[/dim]")
        if preserved_count > 0:
            console.print(f"[dim]Preserved progress for {preserved_count} completed/skipped tasks[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load issues: {e}")
        raise typer.Exit(1)
```

**Proposed Code:**
```python
    # Load issues.json and populate tasks in state
    loaded, preserved = _load_tasks_from_issues(config, state)
    if loaded < 0:
        console.print(f"[red]Error:[/red] Failed to load issues")
        raise typer.Exit(1)

    console.print(f"[dim]Loaded {loaded} tasks from issues.json[/dim]")
    if preserved > 0:
        console.print(f"[dim]Preserved progress for {preserved} completed/skipped tasks[/dim]")
```

### Change 2: swarm_attack/cli/feature.py
- **Type:** modify
- **Explanation:** Call _load_tasks_from_issues() right after issues are created, before validation. This populates state.tasks so it persists even if validation fails.

**Current Code:**
```python
    issues_count = creator_result.output.get("count", 0)
    console.print(f"[green]Created {issues_count} issues[/green]")

    # Update phase to ISSUES_VALIDATING
    state.update_phase(FeaturePhase.ISSUES_VALIDATING)
    store.save(state)
```

**Proposed Code:**
```python
    issues_count = creator_result.output.get("count", 0)
    console.print(f"[green]Created {issues_count} issues[/green]")

    # Load tasks into state immediately after issues.json is created
    # This ensures state.tasks is populated even if validation fails later
    loaded, _ = _load_tasks_from_issues(config, state)
    if loaded > 0:
        console.print(f"[dim]Loaded {loaded} tasks into state[/dim]")

    # Update phase to ISSUES_VALIDATING
    state.update_phase(FeaturePhase.ISSUES_VALIDATING)
    store.save(state)
```

### Change 3: swarm_attack/cli/feature.py
- **Type:** modify
- **Explanation:** Add helper function _load_tasks_from_issues() that encapsulates the task loading logic. This function is called from both issues() and greenlight().

**Current Code:**
```python
# Create feature command group
```

**Proposed Code:**
```python
# Create feature command group


def _load_tasks_from_issues(
    config: "SwarmConfig", state: "RunState"
) -> tuple[int, int]:
    """
    Load tasks from issues.json into state.tasks.

    Uses MERGE strategy: preserves existing task progress (DONE status, outputs, commits)
    while updating metadata from issues.json.

    Args:
        config: Swarm configuration
        state: Run state to populate (modified in place)

    Returns:
        Tuple of (total_loaded, preserved_count). Returns (-1, 0) on error.
    """
    import json

    from swarm_attack.models import TaskRef
    from swarm_attack.utils.fs import read_file

    issues_path = config.specs_path / state.feature_id / "issues.json"
    if not issues_path.exists():
        return (-1, 0)

    try:
        issues_content = read_file(issues_path)
        issues_data = json.loads(issues_content)
        issues_list = issues_data.get("issues", [])

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

        state.tasks = new_tasks
        return (len(new_tasks), preserved_count)
    except Exception:
        return (-1, 0)
```

## Test Cases

### Test 1: test_issues_command_populates_state_tasks
- **Category:** regression
- **Description:** Regression test: issues command should populate state.tasks even when validation fails

```python
def test_issues_command_populates_state_tasks(tmp_path, mocker):
    """Regression test: issues command should populate state.tasks.
    
    Bug: issues command creates issues.json but never populates state.tasks.
    Tasks were only loaded in greenlight, causing empty state.tasks when
    validation fails.
    """
    from typer.testing import CliRunner
    from swarm_attack.cli.feature import app
    from swarm_attack.models import FeaturePhase, RunState
    
    runner = CliRunner()
    
    # Setup: Create feature in SPEC_APPROVED phase with spec-final.md
    feature_id = "test-feature"
    spec_dir = tmp_path / "specs" / feature_id
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec-final.md").write_text("# Test Spec\n")
    
    # Create initial state
    state = RunState(feature_id=feature_id, phase=FeaturePhase.SPEC_APPROVED)
    
    # Mock config and state store
    mock_config = mocker.MagicMock()
    mock_config.specs_path = tmp_path / "specs"
    mocker.patch("swarm_attack.cli.feature.get_config_or_default", return_value=mock_config)
    
    mock_store = mocker.MagicMock()
    mock_store.load.return_value = state
    mocker.patch("swarm_attack.cli.feature.get_store", return_value=mock_store)
    
    # Mock IssueCreatorAgent to create issues.json with 3 issues
    issues_data = {
        "issues": [
            {"order": 1, "title": "Issue 1", "dependencies": []},
            {"order": 2, "title": "Issue 2", "dependencies": [1]},
            {"order": 3, "title": "Issue 3", "dependencies": [2]},
        ]
    }
    
    def mock_creator_run(context):
        (spec_dir / "issues.json").write_text(json.dumps(issues_data))
        return mocker.MagicMock(success=True, output={"count": 3}, cost_usd=0.01)
    
    mock_creator = mocker.MagicMock()
    mock_creator.run = mock_creator_run
    mocker.patch("swarm_attack.cli.feature.IssueCreatorAgent", return_value=mock_creator)
    
    # Mock IssueValidatorAgent to fail validation (triggers BLOCKED phase)
    mock_validator = mocker.MagicMock()
    mock_validator.run.return_value = mocker.MagicMock(
        success=False, 
        errors=["Validation failed"], 
        cost_usd=0.01
    )
    mocker.patch("swarm_attack.cli.feature.IssueValidatorAgent", return_value=mock_validator)
    
    # Run issues command
    result = runner.invoke(app, ["issues", feature_id])
    
    # Verify state.tasks was populated despite validation failure
    assert len(state.tasks) == 3, f"Expected 3 tasks, got {len(state.tasks)}"
    assert state.tasks[0].title == "Issue 1"
    assert state.tasks[1].title == "Issue 2"
    assert state.tasks[2].title == "Issue 3"
```

### Test 2: test_issues_command_blocked_state_preserves_tasks
- **Category:** edge_case
- **Description:** Edge case: When validation fails and phase is BLOCKED, tasks should still be visible

```python
def test_issues_command_blocked_state_preserves_tasks(tmp_path, mocker):
    """Edge case: BLOCKED state should have tasks for debugging/recovery.
    
    When validation fails, the phase goes to BLOCKED but tasks should
    still be populated so users can see what was created and debug.
    """
    from typer.testing import CliRunner
    from swarm_attack.cli.feature import app
    from swarm_attack.models import FeaturePhase, RunState, TaskStage
    
    runner = CliRunner()
    feature_id = "blocked-feature"
    
    # Setup dirs
    spec_dir = tmp_path / "specs" / feature_id
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec-final.md").write_text("# Spec\n")
    
    state = RunState(feature_id=feature_id, phase=FeaturePhase.SPEC_APPROVED)
    
    mock_config = mocker.MagicMock()
    mock_config.specs_path = tmp_path / "specs"
    mocker.patch("swarm_attack.cli.feature.get_config_or_default", return_value=mock_config)
    
    saved_states = []
    mock_store = mocker.MagicMock()
    mock_store.load.return_value = state
    mock_store.save.side_effect = lambda s: saved_states.append(s)
    mocker.patch("swarm_attack.cli.feature.get_store", return_value=mock_store)
    
    # Creator succeeds and creates issues
    issues_data = {"issues": [{"order": 1, "title": "Only Issue", "dependencies": []}]}
    
    def mock_creator_run(ctx):
        (spec_dir / "issues.json").write_text(json.dumps(issues_data))
        return mocker.MagicMock(success=True, output={"count": 1}, cost_usd=0.01)
    
    mock_creator = mocker.MagicMock()
    mock_creator.run = mock_creator_run
    mocker.patch("swarm_attack.cli.feature.IssueCreatorAgent", return_value=mock_creator)
    
    # Validator fails
    mock_validator = mocker.MagicMock()
    mock_validator.run.return_value = mocker.MagicMock(
        success=False, errors=["Circular dependency"], cost_usd=0.01
    )
    mocker.patch("swarm_attack.cli.feature.IssueValidatorAgent", return_value=mock_validator)
    
    result = runner.invoke(app, ["issues", feature_id])
    
    # Verify the last saved state has BLOCKED phase but tasks are populated
    final_save = saved_states[-1]
    assert final_save.phase == FeaturePhase.BLOCKED
    assert len(final_save.tasks) == 1, "Tasks should be populated even in BLOCKED state"
    assert final_save.tasks[0].stage == TaskStage.READY
```

### Test 3: test_load_tasks_preserves_completed_progress
- **Category:** edge_case
- **Description:** Verify helper function preserves DONE/SKIPPED task progress on reload

```python
def test_load_tasks_preserves_completed_progress(tmp_path, mocker):
    """Helper function should preserve completed task progress.
    
    When _load_tasks_from_issues is called, tasks that are already
    DONE or SKIPPED should keep their stage and outputs.
    """
    from swarm_attack.cli.feature import _load_tasks_from_issues
    from swarm_attack.models import RunState, TaskRef, TaskStage, IssueOutput
    
    feature_id = "progress-test"
    spec_dir = tmp_path / "specs" / feature_id
    spec_dir.mkdir(parents=True)
    
    # Create issues.json
    issues_data = {
        "issues": [
            {"order": 1, "title": "Issue 1 Updated", "dependencies": []},
            {"order": 2, "title": "Issue 2 Updated", "dependencies": [1]},
        ]
    }
    (spec_dir / "issues.json").write_text(json.dumps(issues_data))
    
    # Create state with existing completed task
    state = RunState(feature_id=feature_id)
    state.tasks = [
        TaskRef(
            issue_number=1,
            stage=TaskStage.DONE,
            title="Issue 1 Original",
            outputs=IssueOutput(
                files_created=["src/foo.py"],
                classes_defined=["FooClass"],
            ),
            completion_summary="Implemented foo module",
        ),
    ]
    
    mock_config = mocker.MagicMock()
    mock_config.specs_path = tmp_path / "specs"
    
    loaded, preserved = _load_tasks_from_issues(mock_config, state)
    
    assert loaded == 2
    assert preserved == 1
    assert len(state.tasks) == 2
    
    # Task 1 should preserve DONE status and outputs
    task1 = state.tasks[0]
    assert task1.stage == TaskStage.DONE
    assert task1.title == "Issue 1 Updated"  # Title updated from issues.json
    assert task1.outputs is not None
    assert task1.outputs.files_created == ["src/foo.py"]
    assert task1.completion_summary == "Implemented foo module"
    
    # Task 2 should be new with BACKLOG stage (has dependency)
    task2 = state.tasks[1]
    assert task2.stage == TaskStage.BACKLOG
    assert task2.title == "Issue 2 Updated"
```

## Potential Side Effects
- state.tasks will now be populated after issues command, even if validation fails
- state.json will be slightly larger when in BLOCKED phase (contains tasks)
- greenlight() continues to work unchanged - it will merge with existing tasks

## Rollback Plan
Revert the single commit. This restores the original behavior where tasks are only loaded in greenlight(). The bug would return but no new issues would be introduced.

## Estimated Effort
Small - refactoring existing code into helper function, one new call site, 3 test cases
