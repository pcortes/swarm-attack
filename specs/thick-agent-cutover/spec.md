# Thick Agent Architecture Cutover Specification

**Version:** 1.0
**Status:** APPROVED FOR IMMEDIATE IMPLEMENTATION
**Date:** 2025-12-16

## Executive Summary

Replace the multi-stage pipeline (Issue Creator → Test Writer → Coder → Verifier) with a unified "Implementation Agent" that handles test+code in a single context window. This eliminates handoff failures that account for ~60% of current bugs.

## Current Architecture (Being Replaced)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Issue Creator  │───▶│   Test Writer   │───▶│     Coder       │───▶│    Verifier     │
│                 │    │                 │    │                 │    │                 │
│  Spec → Issues  │    │ Issue → Tests   │    │ Tests → Code    │    │ Run Tests       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Why it fails:**
- Context lost at each handoff (40% implicit knowledge lost per transition)
- Test Writer can't see what code will call the implementation
- Coder can't iterate with tests—must get them right first try
- Missing interface methods (e.g., `from_dict()`) because no agent sees the full picture

## New Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SPEC/PRD INPUT                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ISSUE DECOMPOSER                                     │
│  (Keep existing issue-creator skill, enhance output format)                  │
│                                                                             │
│  Output: Structured Issues with:                                            │
│    - interface_contracts: required methods/signatures                       │
│    - integration_points: files that call this code                          │
│    - pattern_references: similar existing implementations                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│   IMPLEMENTATION AGENT  │ │   IMPLEMENTATION AGENT  │ │   IMPLEMENTATION AGENT  │
│        (Issue 1)        │ │        (Issue 2)        │ │        (Issue N)        │
├─────────────────────────┤ ├─────────────────────────┤ ├─────────────────────────┤
│  SINGLE CONTEXT WINDOW  │ │                         │ │                         │
│                         │ │  Parallel execution     │ │                         │
│  1. Read issue + spec   │ │  across issues          │ │                         │
│  2. Read integration    │ │                         │ │                         │
│     points              │ │                         │ │                         │
│  3. Write tests (TDD)   │ │                         │ │                         │
│  4. Run tests (fail)    │ │                         │ │                         │
│  5. Implement code      │ │                         │ │                         │
│  6. Run tests (iterate) │ │                         │ │                         │
│  7. Run FULL suite      │ │                         │ │                         │
│  8. Only done when ALL  │ │                         │ │                         │
│     tests pass          │ │                         │ │                         │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

---

## Phase 1: Merge Test Writer + Coder (IMMEDIATE)

### Changes Required

#### 1.1 Delete `test-writer` skill
- Remove `.claude/skills/test-writer/SKILL.md`
- Remove test-writer stage from orchestrator state machine

#### 1.2 Create unified `coder` skill that does TDD
Update `.claude/skills/coder/SKILL.md` to include:

```markdown
## TDD Workflow (MANDATORY)

For each issue you implement:

1. **Read Context First**
   - Read the issue description fully
   - Read the spec/PRD file
   - Find and read files that will CALL your implementation (integration points)
   - Find and read similar existing implementations (patterns)

2. **Write Tests First (TDD)**
   - Create test file: `tests/generated/{feature}/test_issue_{N}.py`
   - Include unit tests for all specified functionality
   - Include integration tests that verify interface contracts
   - Tests MUST cover any `from_dict`, `to_dict`, `validate` methods if the pattern exists

3. **Run Tests (Expect Failure)**
   - Execute: `pytest tests/generated/{feature}/test_issue_{N}.py -v`
   - Verify tests fail for the right reasons (no implementation yet)

4. **Implement Code**
   - Write implementation that makes tests pass
   - Follow existing patterns in codebase
   - Include ALL interface methods found in similar classes

5. **Iterate Until Tests Pass**
   - Run tests after each change
   - Fix failures one by one
   - Maximum 5 iteration cycles

6. **Run Full Test Suite**
   - Execute: `pytest tests/ -v`
   - ALL tests must pass (not just your new ones)
   - If regressions occur, fix them before marking complete

7. **Only Mark Complete When**
   - All new tests pass
   - All existing tests pass
   - No lint errors
```

#### 1.3 Update orchestrator state machine

In `swarm_attack/orchestrator.py`:

```python
# OLD STATES (remove):
# ISSUES_CREATED → TEST_WRITING → CODING → VERIFYING → COMPLETE

# NEW STATES:
PHASES = [
    "INIT",
    "SPEC_REVIEW",
    "ISSUES_CREATED",
    "IMPLEMENTING",  # Single phase replaces TEST_WRITING + CODING + VERIFYING
    "COMPLETE"
]
```

#### 1.4 Update issue schema

In `.swarm/state/{feature}.json`, enhance issue format:

```json
{
  "issues": [
    {
      "id": 1,
      "title": "Implement ChiefOfStaffConfig dataclass",
      "description": "...",
      "status": "pending",
      "interface_contracts": {
        "required_methods": ["from_dict", "to_dict", "validate"],
        "required_properties": ["settings", "log_dir", "checkpoint_interval"]
      },
      "integration_points": [
        "config.py:411 - calls ChiefOfStaffConfig.from_dict(data)",
        "main.py:23 - imports ChiefOfStaffConfig"
      ],
      "pattern_references": [
        "swarm_attack/feature_swarm/config.py:FeatureSwarmConfig"
      ]
    }
  ]
}
```

---

## Phase 2: Enhanced Issue Creator Output (NEXT)

### Changes Required

#### 2.1 Update issue-creator skill

The issue-creator must now analyze integration context and output richer issues:

```markdown
## Issue Creation Process

For each issue you create:

1. **Analyze Integration Points**
   - Search codebase for files that will import/use this component
   - Identify method calls that don't exist yet
   - Record file:line references

2. **Identify Interface Contracts**
   - Look at similar classes in codebase
   - Extract common method patterns (from_dict, to_dict, validate, etc.)
   - List required methods and signatures

3. **Find Pattern References**
   - Search for similar implementations
   - Provide file paths the implementer should study

4. **Output Structured Issue**
   Include all fields: title, description, interface_contracts, integration_points, pattern_references
```

#### 2.2 Add pre-implementation context retrieval

Before the Implementation Agent runs, automatically:
1. Grep for imports of the module being created
2. Grep for method calls that will target this implementation
3. Inject results into the agent's context

---

## Phase 3: Integration Gate (LATER)

### Changes Required

#### 3.1 Add post-completion verification

After all issues complete:
1. Run full test suite one final time
2. Check for cross-issue conflicts
3. Generate completion report

#### 3.2 Optional human checkpoint

Allow `swarm-attack run {feature} --human-review` to pause before final merge.

---

## File Changes Summary

| File | Action | Phase |
|------|--------|-------|
| `.claude/skills/test-writer/SKILL.md` | DELETE | 1 |
| `.claude/skills/coder/SKILL.md` | REPLACE (TDD workflow) | 1 |
| `swarm_attack/orchestrator.py` | UPDATE (remove test-writer phase) | 1 |
| `swarm_attack/agents/test_writer.py` | DELETE (if exists) | 1 |
| `.claude/skills/issue-creator/SKILL.md` | UPDATE (richer output) | 2 |
| `swarm_attack/cli.py` | UPDATE (--human-review flag) | 3 |

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Integration bug rate | ~60% | <10% |
| Issues requiring manual fix | ~80% | <20% |
| Test-code sync failures | ~40% | 0% |
| First-attempt success | ~20% | >60% |

---

## Implementation Notes

- **No rollback**: This is a hard cutover. Delete old code, don't deprecate.
- **No migration**: Existing features in progress may need manual completion.
- **No backwards compatibility**: The old pipeline is fundamentally broken.

## Approval

This spec is APPROVED for immediate implementation. Begin with Phase 1.
