# Auto-Split Issues Feature

## Overview

When ComplexityGateAgent detects an issue is too complex (`needs_split=True`), automatically split it into smaller sub-issues instead of failing with suggestions.

## Problem

Currently when complexity gate fails:
```
ComplexityGate → needs_split=True → FAILURE + suggestions → STOP
```

Issues get blocked and require manual intervention to split.

## Solution

Auto-trigger issue splitting:
```
ComplexityGate → needs_split=True → IssueSplitterAgent → create sub-issues → CONTINUE
```

## Requirements

### 1. IssueSplitterAgent (NEW)

Create `swarm_attack/agents/issue_splitter.py`:

```python
from dataclasses import dataclass
from typing import Optional
from swarm_attack.agents.base import BaseAgent, AgentResult

@dataclass
class SplitIssue:
    """A sub-issue created from splitting a complex issue."""
    title: str
    body: str
    estimated_size: str  # "small" or "medium"
    order: int  # Relative order within split

@dataclass
class SplitResult:
    """Result from splitting an issue."""
    success: bool
    sub_issues: list[SplitIssue]
    error: Optional[str] = None

class IssueSplitterAgent(BaseAgent):
    """Splits a complex issue into 2-4 smaller sub-issues."""

    def run(self, context: dict) -> AgentResult:
        """
        Args:
            context:
                - issue_title: str
                - issue_body: str
                - split_suggestions: list[str]
                - estimated_turns: int
                - spec_context: Optional[str]

        Returns:
            AgentResult with output:
                - sub_issues: list[dict] with title, body, estimated_size
                - count: int
        """
```

**Prompt Strategy:**
- Use the split_suggestions from complexity gate as guidance
- Read the issue body to understand acceptance criteria
- Split by: trigger type, CRUD operation, layer, or criteria groups
- Each sub-issue should have 3-5 acceptance criteria max
- Output JSON array of sub-issues

### 2. State Model Changes

Modify `swarm_attack/models.py` TaskRef:

```python
@dataclass
class TaskRef:
    # ... existing fields ...
    parent_issue: Optional[int] = None  # If this is a sub-issue
    child_issues: list[int] = field(default_factory=list)  # If split
```

Add new TaskStage:
```python
class TaskStage(Enum):
    # ... existing ...
    SPLIT = "split"  # Issue was split into children
```

### 3. Orchestrator Integration

Modify `swarm_attack/orchestrator.py` in `_run_implementation_cycle`:

When `gate_estimate.needs_split == True`:
1. Call `_auto_split_issue()` instead of returning failure
2. Create sub-issues in state with proper dependencies
3. Mark parent issue as SPLIT stage
4. Update dependent issues to depend on last child
5. Return success with split action

```python
def _auto_split_issue(self, feature_id: str, issue_number: int,
                       gate_estimate: ComplexityEstimate) -> SplitResult:
    """Auto-split a complex issue into smaller sub-issues."""
    splitter = IssueSplitterAgent(self.config, self._logger, self._llm)

    # Get issue details from state
    state = self._state_store.load(feature_id)
    task = next(t for t in state.tasks if t.issue_number == issue_number)

    result = splitter.run({
        "issue_title": task.title,
        "issue_body": self._get_issue_body_from_spec(feature_id, issue_number),
        "split_suggestions": gate_estimate.split_suggestions,
        "estimated_turns": gate_estimate.estimated_turns,
    })

    if result.success:
        self._apply_split_to_state(feature_id, issue_number, result.output["sub_issues"])

    return result
```

### 4. Dependency Rewiring

When issue #5 (with deps [3]) is split into #10, #11, #12:

```python
def _apply_split_to_state(self, feature_id, parent_num, sub_issues):
    state = self._state_store.load(feature_id)
    parent = next(t for t in state.tasks if t.issue_number == parent_num)

    # Get next available issue number
    max_num = max(t.issue_number for t in state.tasks)

    # Create child tasks
    child_nums = []
    for i, sub in enumerate(sub_issues):
        new_num = max_num + 1 + i
        child_nums.append(new_num)

        # First child inherits parent's deps, others chain sequentially
        if i == 0:
            deps = parent.dependencies.copy()
        else:
            deps = [child_nums[i-1]]

        child_task = TaskRef(
            issue_number=new_num,
            stage=TaskStage.READY if not deps else TaskStage.BACKLOG,
            title=sub["title"],
            dependencies=deps,
            estimated_size=sub["estimated_size"],
            parent_issue=parent_num,
        )
        state.tasks.append(child_task)

    # Update parent
    parent.stage = TaskStage.SPLIT
    parent.child_issues = child_nums

    # Rewire dependents: anything depending on parent now depends on last child
    last_child = child_nums[-1]
    for task in state.tasks:
        if parent_num in task.dependencies:
            task.dependencies.remove(parent_num)
            task.dependencies.append(last_child)

    self._state_store.save(state)
```

### 5. Skip SPLIT Issues in Prioritization

Modify `swarm_attack/agents/prioritization.py`:

```python
def _filter_actionable_tasks(self, tasks):
    """Filter out completed and split issues."""
    return [t for t in tasks
            if t.stage not in (TaskStage.DONE, TaskStage.SPLIT, TaskStage.SKIPPED)]
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `swarm_attack/agents/issue_splitter.py` | CREATE |
| `swarm_attack/skills/issue-splitter/SKILL.md` | CREATE |
| `swarm_attack/models.py` | MODIFY - add parent_issue, child_issues, SPLIT stage |
| `swarm_attack/orchestrator.py` | MODIFY - add _auto_split_issue, _apply_split_to_state |
| `swarm_attack/agents/prioritization.py` | MODIFY - skip SPLIT issues |

## Success Criteria

1. When complexity gate returns `needs_split=True`, splitter agent is called
2. Sub-issues are created with proper dependencies
3. Parent issue marked as SPLIT, not BLOCKED
4. Dependent issues rewired to depend on last child
5. Implementation continues with first sub-issue
6. Tests verify split flow end-to-end

## Testing

Create `tests/generated/auto-split-issues/test_issue_splitter.py`:

```python
def test_splitter_creates_sub_issues():
    """Verify splitter creates 2-4 sub-issues from complex issue."""

def test_split_preserves_parent_dependencies():
    """First child inherits parent's dependencies."""

def test_split_chains_children():
    """Child N+1 depends on child N."""

def test_dependents_rewired_to_last_child():
    """Issues depending on parent now depend on last child."""

def test_parent_marked_split():
    """Parent issue stage is SPLIT after splitting."""

def test_prioritization_skips_split():
    """Prioritization agent doesn't select SPLIT issues."""
```
