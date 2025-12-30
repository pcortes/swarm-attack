# Expert Panel: Adaptive LLM-Powered QA System for Swarm Attack

## Your Role

You are a panel of world-class experts in:
- **QA Architecture**: Designing intelligent, adaptive testing systems
- **LLM Agent Design**: Building context-aware AI agents that reason about code
- **API Testing**: Behavioral validation, contract testing, integration verification
- **DevOps Integration**: CI/CD pipelines, automated gates, orchestration patterns

Your mission: Design and specify an **Adaptive QA Agent** that seamlessly integrates into the Swarm Attack multi-agent development automation system.

---

## Context: Swarm Attack System

Swarm Attack is an AI-powered development automation system with three pipelines:

### 1. Feature Pipeline
```
PRD → SpecAuthor → SpecCritic → SpecModerator → Approved Spec
    → IssueCreator → IssueValidator → GitHub Issues
    → ComplexityGate → Coder (TDD) → Verifier → Commit
```

### 2. Bug Bash Pipeline
```
Bug Report → BugResearcher (reproduce) → RootCauseAnalyzer → FixPlanner
           → BugCritic → BugModerator → Human Approval → Apply Fix
```

### 3. Chief of Staff (COS)
```
Standup → Goal Setting → Autopilot Execution → Checkpoints → Wrapup
```

**Key Integration Points:**
- `Verifier` agent runs pytest after Coder implements
- `BugResearcher` attempts reproduction via test execution
- `Autopilot` can execute goals with budget/time limits and checkpoint gates
- State is persisted in `.swarm/` directory
- Issues tracked in `specs/{feature}/issues.json`
- Bug state in `.swarm/bugs/{bug-id}/`

**Current Gap:** The system validates code via unit tests (pytest) but lacks:
- Behavioral validation (does the API actually work as expected?)
- Contract validation (do responses match what consumers expect?)
- Integration validation (does new code break existing integrations?)
- Manual-style exploratory testing (what a human QA would do)

---

## The Vision: Adaptive QA Agent

Design an **Adaptive QA Agent** (or agent swarm) that:

### Core Capabilities

1. **Context Acquisition**
   - Reads the spec, issue, or bug report to understand WHAT should be tested
   - Studies relevant code to understand HOW the system works
   - Identifies API endpoints, request/response schemas, dependencies
   - Learns the "contract" - what callers expect from this code

2. **Behavioral Testing**
   - Spins up the system (or connects to running instance)
   - Crafts curl/HTTP requests based on understanding
   - Executes requests and captures responses
   - Validates: status codes, response structure, data correctness, timing

3. **Contract Validation**
   - Identifies consumers (frontend, other services, CLI)
   - Validates responses match consumer expectations
   - Checks field names, types, ordering, nullability
   - Detects breaking changes

4. **Adaptive Depth**
   - **Shallow**: Quick smoke test (happy path only)
   - **Standard**: Happy path + error cases + edge cases
   - **Deep**: Full exploratory testing, security probes, load patterns
   - **Regression**: Focus on areas affected by recent changes

5. **Output**
   - Creates timestamped QA report: `.swarm/qa/qa-report-{timestamp}.md`
   - If issues found: Creates bug bash document: `.swarm/qa/qa-bugs-{timestamp}.md`
   - Structured JSON for programmatic consumption
   - Can feed directly into Bug Bash pipeline

---

## Integration Scenarios

The QA Agent must adapt to these contexts:

### Scenario A: Post-Implementation Validation
**Trigger:** Coder completes an issue, Verifier passes
**Context:** Issue spec, implemented code, test results
**Question:** "Does this actually work when you hit it?"
**Depth:** Standard

### Scenario B: Bug Bash Reproduction Enhancement
**Trigger:** BugResearcher attempting reproduction
**Context:** Bug report, error message, affected code
**Question:** "Can we reproduce this behaviorally, not just via unit test?"
**Depth:** Deep on affected area

### Scenario C: User-Prompted Testing
**Trigger:** User runs `swarm-attack qa test "messaging in chat service"`
**Context:** User's natural language description
**Question:** "What should I test and how?"
**Depth:** User-specified or inferred

### Scenario D: Pre-Merge Validation
**Trigger:** Before marking issue as complete
**Context:** Full diff, spec, integration points
**Question:** "Will this break anything when merged?"
**Depth:** Regression-focused

### Scenario E: Full System Health Check
**Trigger:** User runs `swarm-attack qa health` or COS autopilot scheduled
**Context:** Entire system
**Question:** "Is everything working?"
**Depth:** Shallow across all endpoints

### Scenario F: Spec Compliance Validation
**Trigger:** After implementation, before greenlight
**Context:** Original spec, implemented code
**Question:** "Does implementation match spec requirements?"
**Depth:** Standard with spec traceability

---

## Design Questions for the Expert Panel

### Architecture

1. **Single Agent vs. Agent Swarm?**
   - One QA agent that adapts, or specialized sub-agents?
   - e.g., ContractValidator, BehavioralTester, RegressionAnalyzer
   - How do they coordinate?

2. **Context Building Strategy**
   - How does the agent acquire enough context to test intelligently?
   - What's the minimum context for shallow vs. deep testing?
   - How to avoid context window limits for large codebases?

3. **Test Generation**
   - How does the agent decide WHAT to test?
   - How does it craft curl commands / HTTP requests?
   - How does it know expected responses without hardcoding?

4. **Execution Environment**
   - Does it spin up the service? Connect to running instance?
   - How to handle database state, auth tokens, dependencies?
   - Sandboxing for destructive tests?

### Integration with Existing Pipelines

5. **Where does QA Agent fit in Feature Pipeline?**
   ```
   Coder → Verifier → [QA Agent?] → Commit
   ```
   - After Verifier? Parallel to Verifier?
   - Blocking or advisory?

6. **How does it enhance Bug Bash?**
   - Replace BugResearcher? Augment it?
   - New phase: `BEHAVIORAL_REPRODUCTION`?
   - Feed findings back into RootCauseAnalyzer?

7. **COS Autopilot Integration**
   - New goal type: `qa_validation`?
   - Checkpoint trigger for QA failures?
   - Budget allocation for QA runs?

8. **CLI Interface**
   ```bash
   swarm-attack qa <command>
   ```
   - What commands? What options?
   - How to specify scope, depth, target?

### State & Output

9. **QA State Management**
   - Where to store QA results? `.swarm/qa/`?
   - How to track QA debt / known issues?
   - History for regression detection?

10. **Bug Bash Document Format**
    ```markdown
    # QA Findings: {timestamp}

    ## Summary
    - Endpoints tested: X
    - Passed: Y
    - Failed: Z

    ## Failures
    ### [FAIL-001] POST /api/messages returns wrong status
    - Expected: 201 Created
    - Actual: 200 OK
    - Severity: Medium
    - Suggested fix: ...
    ```
    - What fields are essential?
    - How to auto-create Bug Bash entries?

### Adaptiveness

11. **Learning from History**
    - Can QA agent learn from past failures?
    - Prioritize testing areas that failed before?
    - Build a "test knowledge base"?

12. **Consumer Discovery**
    - How to automatically find consumers of an API?
    - Parse frontend code? OpenAPI specs? Integration tests?
    - Infer contracts from usage patterns?

13. **Dynamic Depth Adjustment**
    - Start shallow, go deep if issues found?
    - Risk-based depth (high-risk code = deeper testing)?
    - Time/budget-based depth limits?

---

## Deliverables Requested

### 1. Architecture Document
- Agent structure (single vs. swarm)
- Context flow diagram
- Integration points with existing pipelines

### 2. Skill Definition
Create the skill file(s) for the QA agent(s):
```yaml
---
name: qa-validator
description: Adaptive behavioral QA agent
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - WebFetch
  - Write
triggers:
  - post_verification
  - bug_reproduction
  - user_command
  - scheduled
---
```

### 3. State Schema
Define the QA state structures:
```python
@dataclass
class QASession:
    session_id: str
    trigger: QATrigger
    context: QAContext
    depth: QADepth
    results: List[QAResult]
    bugs_found: List[QABug]
```

### 4. CLI Specification
```bash
swarm-attack qa test <target>      # Test specific area
swarm-attack qa validate <issue>   # Validate issue implementation
swarm-attack qa health             # System health check
swarm-attack qa report [--since]   # View QA reports
swarm-attack qa bugs               # View QA-discovered bugs
```

### 5. Integration Plan
- Modifications to `orchestrator.py`
- Modifications to `bug_orchestrator.py`
- New files needed
- State store changes
- COS integration

### 6. Example Flows
Walk through each scenario (A-F) with:
- Trigger event
- Context gathered
- Tests generated
- Execution steps
- Output produced

---

## Constraints & Considerations

1. **Cost Awareness**: QA can be expensive (many LLM calls). Budget limits essential.

2. **Speed**: Shallow tests should complete in <30 seconds. Deep tests may take minutes.

3. **Reliability**: False positives erode trust. High confidence threshold for failures.

4. **Reproducibility**: QA runs should be reproducible. Capture all inputs/outputs.

5. **Security**: QA agent has curl access. Must not leak secrets or attack external systems.

6. **Existing Patterns**: Follow swarm-attack patterns:
   - Skills in `swarm_attack/skills/`
   - Agents in `swarm_attack/agents/`
   - State in `.swarm/`
   - CLI in `swarm_attack/cli/`

---

## Reference: Existing Agent Pattern

```python
# swarm_attack/agents/verifier.py pattern
class Verifier:
    def __init__(self, config: SwarmConfig):
        self.config = config
        self.skill = SkillLoader.load("verifier")

    def verify(self, context: VerifyContext) -> VerifyResult:
        # Build prompt from skill + context
        # Execute via Claude CLI
        # Parse structured output
        # Return result
```

The QA agent(s) should follow this pattern.

---

## Success Criteria

The design is successful if:

1. **Adaptive**: Same agent handles all scenarios with appropriate depth
2. **Integrated**: Fits naturally into existing pipelines without major refactoring
3. **Actionable**: Findings feed directly into Bug Bash or block merges
4. **Efficient**: Minimal redundant testing, smart prioritization
5. **Trustworthy**: Low false positive rate, clear evidence for findings
6. **Extensible**: Easy to add new test types, protocols, validators

---

## Begin Analysis

Study the existing swarm-attack codebase thoroughly. Understand:
- How agents are structured
- How state flows through pipelines
- How the Verifier currently works
- How BugResearcher attempts reproduction
- How COS autopilot executes goals

Then design the Adaptive QA Agent system that elevates swarm-attack to world-class quality automation.

Think deeply. Consider edge cases. Propose innovative solutions. Challenge assumptions.

Output your complete design.
