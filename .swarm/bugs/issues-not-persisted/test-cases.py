"""
Generated test cases for bug: issues-not-persisted

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: issues command should populate state.tasks even when validation fails
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

# Edge case: When validation fails and phase is BLOCKED, tasks should still be visible
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

# Verify helper function preserves DONE/SKIPPED task progress on reload
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

