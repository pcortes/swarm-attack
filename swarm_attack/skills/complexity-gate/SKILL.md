---
name: complexity-gate
description: >
  Estimate issue complexity before implementation to prevent timeouts.
  Uses cheap estimation to save expensive implementation tokens.
allowed-tools: []
---

# Complexity Gate

You estimate whether a GitHub issue is too complex for a single LLM implementation session.

## Task

Given an issue's title, body, and acceptance criteria, estimate:
1. How many LLM turns the implementation would take
2. Whether the issue needs to be split into smaller pieces

## Complexity Guidelines

| Complexity | Turns | Characteristics |
|------------|-------|-----------------|
| Simple | 5-8 | 1-3 criteria, single method, no edge cases |
| Medium | 8-15 | 4-6 criteria, 2-4 methods, standard patterns |
| Complex | 15-25 | 7-10 criteria, 5-7 methods, edge cases |
| Too Large | 25+ | 10+ criteria, 8+ methods, multiple subsystems |

## Output Format

Return ONLY JSON (no markdown, no explanation):

```json
{
  "estimated_turns": 15,
  "complexity_score": 0.5,
  "needs_split": false,
  "reasoning": "Standard CRUD with 5 methods, well-defined interface"
}
```

## Red Flags (triggers auto-split)

- More than 8 acceptance criteria
- More than 6 methods to implement
- Multiple enum types or trigger handlers
- Changes to config + implementation + tests
- "Implement X with Y integration" (two things at once)

**Note:** When `needs_split=true`, the orchestrator automatically invokes the IssueSplitterAgent to create 2-4 smaller sub-issues. The parent issue is marked as SPLIT and implementation continues with the child issues.

## Turn Estimation Heuristics

When estimating turns, consider:

1. **Test Writing**: +2-4 turns for writing comprehensive tests
2. **Implementation**: +1-2 turns per method
3. **Iteration**: +2-5 turns for fixing test failures
4. **Edge Cases**: +1-2 turns per edge case to handle
5. **Config/Setup**: +1-2 turns if config changes needed

## Examples

### Simple Issue (8 turns)
```
Title: Add helper method for string sanitization
Criteria:
- [ ] Create sanitize_input() function
- [ ] Handle empty strings
- [ ] Unit tests
```
Reasoning: Single function with clear behavior, 3 criteria.

### Medium Issue (15 turns)
```
Title: Implement user CRUD operations
Criteria:
- [ ] create_user() method
- [ ] get_user() method
- [ ] update_user() method
- [ ] delete_user() method
- [ ] Input validation
- [ ] Unit tests for each operation
```
Reasoning: 4 methods with validation, standard pattern.

### Too Large (30+ turns - needs split)
```
Title: Implement CheckpointSystem with trigger detection
Criteria:
- [ ] 6 trigger types to detect
- [ ] 8+ methods to implement
- [ ] Config changes
- [ ] Async operations
- [ ] Unit tests for each trigger
```
Reasoning: Multiple subsystems (triggers + checkpoints), too many methods.
