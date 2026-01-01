# PRD: Dispatcher Claude CLI Integration

## Problem Statement
The AgentDispatcher._run_agent() method is a placeholder that returns empty findings.
We need it to call Claude CLI to get real expert reviews of commits.

## Requirements

### Functional Requirements
1. _run_agent() must call Claude CLI via subprocess
2. Parse JSON response into Finding objects
3. Handle errors gracefully (timeout, invalid JSON, CLI errors)
4. Log warnings but don't crash on failures

### Technical Requirements
1. Use subprocess.run() with ["claude", "--print", "--output-format", "json", "-p", prompt]
2. Timeout of 300 seconds per agent call
3. Return empty list on any error (graceful degradation)

### Interface Contract
```python
async def _run_agent(
    self,
    commit: CommitInfo,
    category: CommitCategory,
    prompt: str,
) -> list[Finding]:
```

### Test Requirements
1. Test Claude CLI is called with correct args
2. Test JSON response parsed correctly
3. Test timeout handling
4. Test invalid JSON handling
5. Test CLI error handling

## Reference Files
- Pattern: swarm_attack/agents/base.py (see _run_claude)
- Models: swarm_attack/commit_review/models.py
- Prompts: swarm_attack/commit_review/prompts.py
- Spec: specs/commit-quality-review/IMPLEMENTATION_SPEC.xml

## Acceptance Criteria
- [ ] Claude CLI called via subprocess
- [ ] Findings parsed from JSON response
- [ ] All error cases handled gracefully
- [ ] 5 new unit tests pass
- [ ] Existing tests still pass
