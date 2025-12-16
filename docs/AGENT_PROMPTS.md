# Feature Swarm: Agent Prompts

This document contains the prompts for the three-agent workflow used to break down a specification into implementable GitHub issues.

---

## Key Design Decisions (Resolved)

These decisions were clarified during planning and should be incorporated into any implementation:

| Decision | Resolution |
|----------|------------|
| **CCPM Integration** | CLI/slash-command only via Claude Code headless. PRD creation is always human/interactive. Post-PRD uses `/pm:prd-parse`, `/pm:epic-oneshot`, `/pm:epic-sync` |
| **Claude Code Output** | `--output-format json` everywhere. Parse JSON envelope: `{type, subtype, total_cost_usd, result, session_id, num_turns, duration_ms}` |
| **GitHub Auth** | REST API with PAT stored in `GITHUB_TOKEN` env var. CCPM keeps using `gh` internally |
| **Test Framework** | Explicit `tests.command` in config.yaml. Optional `feature-swarm detect-tests` helper |
| **Multi-repo** | V1 is single-repo only |
| **Cost Tracking** | Yes - track and surface per feature/session/agent |
| **Skill Files** | `.claude/skills/<skill-name>/SKILL.md` with Anthropic's official format (YAML frontmatter + markdown) |
| **Git Strategy** | One branch per **feature** (`feature/<slug>`), NOT per issue. Issues map to commits with tags like `(#45)`. Rollback = revert commits for specific issue. |

---

## Agent 1: Implementation Planner

**Role:** Senior Engineering Manager breaking down a specification into implementable work.

### Prompt

```
You are a senior engineering manager breaking down a specification into implementable work.

## THE SPEC

[Paste the contents of FEATURE_SWARM_SPEC.md here]

## YOUR TASK

Create a detailed **Implementation Plan Document** that will be reviewed by a second agent before any
GitHub issues are created.

## OUTPUT: IMPLEMENTATION_PLAN.md

Generate a markdown document with this exact structure:

---

# Feature Swarm: Implementation Plan

## 1. Spec Summary

### 1.1 Core Concept
[2-3 sentences: what is this system?]

### 1.2 Key Components
| Component | Purpose | Complexity |
|-----------|---------|------------|
| ... | ... | Low/Medium/High |

### 1.3 Critical Dependencies
- External: Claude Code CLI, CCPM, GitHub API
- Internal: [list key module dependencies]

---

## 2. Architecture Decisions

### 2.1 Decisions Made in Spec
| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| One issue per session | Atomic rollback, context management | Slower throughput |
| ... | ... | ... |

### 2.2 Decisions NOT in Spec (Assumptions)
| Gap | My Assumption | Risk if Wrong |
|-----|---------------|---------------|
| How to handle concurrent users? | Single user only for v1 | Low - can add later |
| ... | ... | ... |

### 2.3 Open Questions for Review
1. [Question that needs human/reviewer input]
2. ...

---

## 3. Module Dependency Graph

┌─────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY GRAPH                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  models.py ──────────────────────────────────────────────────┐  │
│      │                                                       │  │
│      ▼                                                       │  │
│  config.py ────► state_store.py ────► logger.py              │  │
│      │                │                   │                  │  │
│      ▼                ▼                   ▼                  │  │
│  llm_clients.py ◄─────┴───────────────────┘                  │  │
│      │                                                       │  │
│      ├──────────────────────────────────────────────────┐    │  │
│      ▼                                                  ▼    │  │
│  agent_base.py                                    cli.py     │  │
│      │                                               │       │  │
│      ├─────┬─────┬─────┬─────┐                      │       │  │
│      ▼     ▼     ▼     ▼     ▼                      │       │  │
│  spec_   spec_  spec_  issue_ priori-               │       │  │
│  author  critic modr   valid  ttic                  │       │  │
│      │     │     │       │     │                    │       │  │
│      └─────┴─────┴───────┴─────┘                    │       │  │
│                  │                                  │       │  │
│                  ▼                                  │       │  │
│           orchestrator.py ◄─────────────────────────┘       │  │
│                  │                                          │  │
│                  ▼                                          │  │
│           session_manager.py                                │  │
│                  │                                          │  │
│      ┌───────────┼───────────┐                              │  │
│      ▼           ▼           ▼                              │  │
│  coder (TDD)    verifier                                    │  │
│                                                             │  │
└─────────────────────────────────────────────────────────────────┘

---

## 4. Issues Breakdown

### Milestone 1: Foundation
*Goal: Basic infrastructure that everything else depends on*

#### Issue 1: Core Data Models
```yaml
title: "Implement core data models (models.py)"
priority: high
size: small (1-2 hours)
dependencies: none

description: |
  Create the foundational data structures for the entire system.

files:
  - feature_swarm/models.py

acceptance_criteria:
  - [ ] FeaturePhase enum with all 12 states
  - [ ] TaskStage enum with all 8 states
  - [ ] RunState dataclass with all fields
  - [ ] TaskRef dataclass
  - [ ] SessionState dataclass
  - [ ] All models are JSON-serializable
  - [ ] Unit tests for serialization round-trip

spec_reference: "Section 3.1, 3.2, 7.3"

integration_points:
  - Used by: state_store, cli, all agents
  - Uses: nothing (leaf node)

test_strategy: |
  - Unit tests for enum values
  - Unit tests for dataclass defaults
  - Test JSON serialization/deserialization
```

#### Issue 2: Configuration Loading
```yaml
title: "Implement configuration loading (config.py)"
priority: high
size: small (1-2 hours)
dependencies: [1]

description: |
  Load and validate config.yaml, resolve environment variables,
  provide SwarmConfig dataclass.

files:
  - feature_swarm/config.py
  - config.yaml.example

acceptance_criteria:
  - [ ] Load config.yaml from repo root
  - [ ] Resolve environment variables (GITHUB_TOKEN, etc.)
  - [ ] SwarmConfig dataclass with typed fields
  - [ ] Validation errors for missing required fields
  - [ ] Default values for optional fields
  - [ ] Unit tests

spec_reference: "Section 10.1"

integration_points:
  - Used by: cli, github_client, llm_clients, ccpm_adapter
  - Uses: models.py (for config-related types)

test_strategy: |
  - Test loading valid config
  - Test missing required fields
  - Test env var resolution
  - Test default values
```

[Continue for ALL issues in this format...]

---

## 5. Integration Matrix

Shows how each module integrates with others:

| Module          | Reads From            | Writes To           | Calls          | Called By         |
|-----------------|-----------------------|---------------------|----------------|-------------------|
| models.py       | -                     | -                   | -              | ALL               |
| config.py       | config.yaml, env vars | -                   | models         | cli, agents       |
| state_store.py  | .swarm/state/*.json   | .swarm/state/*.json | models, config | cli, orchestrator |
| logger.py       | -                     | .swarm/logs/*.jsonl | config         | ALL               |
| llm_clients.py  | -                     | - (subprocess)      | config, logger | agents            |
| cli.py          | user input            | stdout              | ALL            | user              |
| orchestrator.py | state                 | state               | ALL agents     | cli               |
| ...             | ...                   | ...                 | ...            | ...               |

---

## 6. Data Flow Diagrams

### 6.1 Spec Generation Flow

```
User runs `feature-swarm`
    │
    ▼
CLI checks state → PRD_READY
    │
    ▼
orchestrator.run_spec_pipeline()
    │
    ├──► SpecAuthorAgent.run()
    │        │
    │        ├── Read: .claude/prds/<feature>.md
    │        ├── Call: ClaudeCliRunner.run_json()
    │        └── Write: specs/<feature>/spec-draft.md
    │
    ├──► SpecCriticAgent.run()
    │        │
    │        ├── Read: spec-draft.md, PRD
    │        ├── Call: ClaudeCliRunner.run_json()
    │        └── Write: specs/<feature>/spec-review.json
    │
    ├──► SpecModeratorAgent.run()
    │        │
    │        ├── Read: spec-draft.md, spec-review.json
    │        ├── Call: ClaudeCliRunner.run_json()
    │        └── Write: spec-final.md, spec-rubric.json
    │
    └──► Check stopping conditions
             │
             ├── SUCCESS → phase = SPEC_NEEDS_APPROVAL
             └── CONTINUE → loop back to SpecAuthor
```

### 6.2 Implementation Session Flow

```
User runs `feature-swarm`
    │
    ▼
CLI checks state → READY_TO_IMPLEMENT
    │
    ▼
SessionManager.start_session()
    │
    ├── Check for interrupted sessions
    ├── PrioritizationAgent.get_next_issue()
    ├── Claim issue (lock)
    └── Create session record
    │
    ▼
orchestrator.run_issue_session(issue)
    │
    ├──► CoderAgent.run(issue)  # TDD: writes tests + implements code
    │        └── Checkpoint saved
    │
    ├──► VerifierAgent.run(issue)
    │        │
    │        ├── PASS → issue.stage = DONE
    │        └── FAIL → retry or BLOCKED
    │
    └──► SessionManager.end_session()
             │
             ├── Git commit
             ├── Update GitHub issue
             └── Update RunState
```

---

## 7. Risk Analysis

### 7.1 Technical Risks

| Risk                             | Likelihood | Impact | Mitigation                            |
|----------------------------------|------------|--------|---------------------------------------|
| Claude CLI output format changes | Low        | High   | Pin version, add output validation    |
| CCPM commands fail silently      | Medium     | High   | Robust file polling, timeout handling |
| Context exhaustion mid-session   | High       | Medium | Checkpoints, WIP commits              |
| ...                              | ...        | ...    | ...                                   |

### 7.2 Integration Risks

| Risk                            | Likelihood | Impact | Mitigation                |
|---------------------------------|------------|--------|---------------------------|
| State gets out of sync with git | Medium     | High   | Reconciliation on startup |
| GitHub rate limiting            | Medium     | Low    | Backoff, caching          |
| ...                             | ...        | ...    | ...                       |

---

## 8. Testing Strategy

### 8.1 Unit Tests (per module)

| Module         | Test File           | Key Test Cases                |
|----------------|---------------------|-------------------------------|
| models.py      | test_models.py      | Enum values, serialization    |
| config.py      | test_config.py      | Loading, validation, defaults |
| state_store.py | test_state_store.py | CRUD, corruption handling     |
| ...            | ...                 | ...                           |

### 8.2 Integration Tests

| Test              | Modules Involved            | What It Validates      |
|-------------------|-----------------------------|------------------------|
| Spec debate e2e   | spec agents, orchestrator   | Full debate loop works |
| Session lifecycle | session_manager, agents     | Start → work → end     |
| Recovery          | session_manager, edge_cases | Resume from checkpoint |
| ...               | ...                         | ...                    |

### 8.3 Manual Test Scenarios

1. Happy path: PRD → Spec → Issues → Implementation → Done
2. Interrupt mid-session, resume next day
3. Issue fails validation, gets revised
4. Implementation fails 3x, gets blocked
5. ...

---

## 9. Implementation Sequence

### Phase 1: Foundation (Issues 1-7)

```
Week 1, Days 1-2

   #1 models.py
        │
        ▼
   #2 config.py ──────► #3 state_store.py
        │                      │
        ▼                      ▼
   #4 logger.py          #5 utils/fs.py
        │                      │
        └──────────┬───────────┘
                   ▼
            #6 llm_clients.py
                   │
                   ▼
            #7 cli.py (skeleton)
```

Deliverable: Can run `feature-swarm status` (shows empty state)

### Phase 2: Spec Pipeline (Issues 8-13)

```
Week 1, Days 3-5

   #8 agent_base.py
        │
        ├───────────┬───────────┐
        ▼           ▼           ▼
   #9 spec_    #10 spec_   #11 spec_
      author       critic      moderator
        │           │           │
        └───────────┴───────────┘
                    │
                    ▼
            #12 spec_debate.py
                    │
                    ▼
            #13 cli: approval flow
```

Deliverable: Can run `feature-swarm` on a PRD, generates spec, asks for approval

[Continue for all phases...]

---

## 10. Checklist for Reviewer

The reviewing agent should verify:

### Completeness
- [ ] All spec sections are covered by at least one issue
- [ ] No orphan modules (everything integrates)
- [ ] All data flows are accounted for

### Feasibility
- [ ] Dependencies are correctly identified
- [ ] No circular dependencies
- [ ] Size estimates are reasonable

### Integration
- [ ] Module interfaces are clear
- [ ] Data formats are consistent
- [ ] Error handling spans modules correctly

### Testability
- [ ] Each module has a test strategy
- [ ] Integration tests cover critical paths
- [ ] Edge cases are explicitly listed

### Spec Alignment
- [ ] Issue acceptance criteria match spec requirements
- [ ] No scope creep beyond spec
- [ ] Assumptions are documented

---

## 11. Ready for Review

This implementation plan is ready for review by Agent 2.

Total Issues: X
Estimated Total Effort: Y hours
Recommended Team Size: 1 developer

Reviewer Instructions:
1. Verify all spec sections are covered
2. Check dependency graph for issues
3. Validate integration points
4. Flag any gaps or concerns
5. Approve or request changes

---

Write this complete document to IMPLEMENTATION_PLAN.md.
```

---

## Agent 2: Plan Reviewer

**Role:** Principal Engineer reviewing an implementation plan before it becomes GitHub issues.

### Prompt

```
You are a principal engineer reviewing an implementation plan before it becomes GitHub issues.

## YOUR INPUTS

1. Original Spec: [FEATURE_SWARM_SPEC.md contents]
2. Implementation Plan: [IMPLEMENTATION_PLAN.md contents]

## YOUR TASK

Review the implementation plan against the spec and produce a REVIEW REPORT.

## Review Checklist

### 1. Spec Coverage

For EACH section of the spec, verify there's a corresponding issue:

| Spec Section             | Covered By Issue(s)      | Status |
|--------------------------|--------------------------|--------|
| 0. Philosophy            | #28 (Smart CLI)          | ✅      |
| 1. What This System Does | Overview, no code needed | ✅      |
| 2. The Smart CLI         | #7, #28                  | ✅      |
| 3.1 Feature Phases       | #1                       | ✅      |
| ...                      | ...                      | ...    |

Flag any GAPS: sections not covered by issues.

### 2. Dependency Validation

Verify the dependency graph:
- No circular dependencies
- Leaf nodes have no dependencies
- Each issue lists correct dependencies
- Build order is valid

Flag any CYCLES or MISSING DEPENDENCIES.

### 3. Integration Verification

For each module boundary, verify:
- Input/output formats are specified
- Error handling is defined
- The modules will actually connect

Flag any INTEGRATION GAPS.

### 4. Acceptance Criteria Quality

For each issue, verify acceptance criteria are:
- Specific (not vague)
- Testable (can verify done)
- Complete (covers the scope)

Flag any WEAK CRITERIA.

### 5. Risk Assessment

- Are high-risk items identified?
- Are mitigations adequate?
- Any risks missed?

Flag any UNMITIGATED RISKS.

### 6. Feasibility Check

- Are size estimates reasonable?
- Are there any issues that seem too large?
- Any issues that should be split?

Flag any SIZING ISSUES.

## Output Format

# Implementation Plan Review

## Summary
- **Status:** APPROVED / APPROVED WITH CHANGES / NEEDS REWORK
- **Issues Found:** X critical, Y moderate, Z minor
- **Recommendation:** [1-2 sentences]

## Critical Issues (Must Fix)
1. [Issue description and recommendation]
2. ...

## Moderate Issues (Should Fix)
1. [Issue description and recommendation]
2. ...

## Minor Issues (Nice to Fix)
1. [Issue description and recommendation]
2. ...

## Spec Coverage Report
[Table showing each spec section and coverage status]

## Dependency Graph Validation
[Confirmed valid / Issues found]

## Integration Points Review
[List of integration points and their status]

## Approval

[ ] APPROVED - Ready to create GitHub issues
[ ] APPROVED WITH CHANGES - Create issues after fixing critical items
[ ] NEEDS REWORK - Return to Agent 1 for revision

## Sign-off
Reviewed by: Agent 2
Date: YYYY-MM-DD

---

Write your review to IMPLEMENTATION_REVIEW.md.

If APPROVED, output: "READY TO CREATE GITHUB ISSUES"
If NOT APPROVED, output: "RETURN TO PLANNING" with specific feedback.
```

---

## Agent 3: GitHub Issue Creator

**Role:** Automation agent that creates GitHub issues from an approved implementation plan.

### Prompt

```
You are an automation agent that creates GitHub issues from an approved implementation plan.

## PREREQUISITES

1. Implementation Plan: [IMPLEMENTATION_PLAN.md] - APPROVED
2. Review: [IMPLEMENTATION_REVIEW.md] - Status: APPROVED
3. Repository: owner/repo

## YOUR TASK

Execute the following steps to create all GitHub issues:

### Step 1: Verify Approval

Check that IMPLEMENTATION_REVIEW.md contains "APPROVED" status.
If not approved, STOP and output: "Cannot proceed - plan not approved"

### Step 2: Create Labels

Create the following labels if they don't exist:

```bash
gh label create "priority:P0" --color "B60205" --description "Critical - blocks all other work"
gh label create "priority:P1" --color "D93F0B" --description "High - core functionality"
gh label create "priority:P2" --color "FBCA04" --description "Medium - important but not blocking"
gh label create "size:small" --color "C2E0C6" --description "1-2 hours"
gh label create "size:medium" --color "FEF2C0" --description "2-4 hours"
gh label create "size:large" --color "F9D0C4" --description "4+ hours"
gh label create "milestone:foundation" --color "1D76DB" --description "Phase 1: Foundation"
gh label create "milestone:spec-pipeline" --color "1D76DB" --description "Phase 2: Spec Pipeline"
gh label create "milestone:issue-mgmt" --color "1D76DB" --description "Phase 3: Issue Management"
gh label create "milestone:impl-pipeline" --color "1D76DB" --description "Phase 4: Implementation Pipeline"
gh label create "milestone:recovery" --color "1D76DB" --description "Phase 5: Recovery & Edge Cases"
gh label create "milestone:smart-cli" --color "1D76DB" --description "Phase 6: Smart CLI"
gh label create "milestone:polish" --color "1D76DB" --description "Phase 7: Polish & Testing"
```

### Step 3: Create Milestones

```bash
gh api repos/{owner}/{repo}/milestones -f title="M1: Foundation" -f description="Basic infrastructure that everything else depends on"
gh api repos/{owner}/{repo}/milestones -f title="M2: Spec Pipeline" -f description="Generate engineering specs from PRDs through debate"
gh api repos/{owner}/{repo}/milestones -f title="M3: Issue Management" -f description="Create and validate issues via CCPM"
gh api repos/{owner}/{repo}/milestones -f title="M4: Implementation Pipeline" -f description="Implement issues through test-first development"
gh api repos/{owner}/{repo}/milestones -f title="M5: Recovery & Edge Cases" -f description="Handle errors gracefully and enable recovery"
gh api repos/{owner}/{repo}/milestones -f title="M6: Smart CLI" -f description="Complete the state-aware CLI experience"
gh api repos/{owner}/{repo}/milestones -f title="M7: Polish & Testing" -f description="Production-ready quality"
```

### Step 4: Create Issues in Dependency Order

For each issue in the implementation plan, create a GitHub issue:

```bash
gh issue create \
  --title "Issue Title" \
  --body "$(cat <<'EOF'
## Description
[Description from plan]

## Files
- `path/to/file.py`

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Dependencies
Blocked by: #X, #Y

## Test Strategy
[Test strategy from plan]

## Spec Reference
Section X.Y

---
*Auto-generated from IMPLEMENTATION_PLAN.md*
EOF
)" \
  --label "priority:P0" \
  --label "size:small" \
  --label "milestone:foundation"
```

### Step 5: Add Dependency Cross-References

After all issues are created, update each issue with correct dependency links:

```bash
# For each issue with dependencies
gh issue edit {number} --body "Updated body with correct #issue references"
```

### Step 6: Output Summary

```markdown
# GitHub Issues Created

## Summary
- Total issues created: X
- Labels created: Y
- Milestones created: Z

## Issues by Milestone

### M1: Foundation
- #1: Implement core data models (models.py)
- #2: Implement configuration loading (config.py)
...

### M2: Spec Pipeline
- #8: Implement agent base class
...

## Dependency Graph
[ASCII representation with issue numbers]

## Next Steps
1. Assign issues to team members
2. Start with #1 (no dependencies)
3. Track progress on project board
```

---

Execute now.
```

---

## Usage Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Agent 1: Implementation Planner                                │
│      │                                                         │
│      │  Creates: IMPLEMENTATION_PLAN.md                        │
│      │                                                         │
│      ▼                                                         │
│  Human or Agent 2: Plan Reviewer                               │
│      │                                                         │
│      │  Creates: IMPLEMENTATION_REVIEW.md                      │
│      │                                                         │
│      ├── APPROVED ─────────────────────┐                       │
│      │                                 │                       │
│      └── NOT APPROVED                  ▼                       │
│           │                     Agent 3: Issue Creator         │
│           │                            │                       │
│           │                            │  Creates: GitHub      │
│           │                            │  Issues + Labels +    │
│           ▼                            │  Milestones           │
│      Back to Agent 1                   │                       │
│      with feedback                     ▼                       │
│                                  DONE - Ready to implement     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Benefits of This Workflow

1. **Traceability** - Plan document maps every issue to spec sections
2. **Review Gate** - Catch problems before creating issues (cheaper to fix)
3. **Automation** - Once approved, issues are created automatically and consistently
4. **Documentation** - Plan serves as architecture documentation
5. **Repeatability** - Same process can be used for any feature spec

---

## Tips for Using These Prompts

### For Agent 1 (Planner):
- Always read the full spec before starting
- Ask clarifying questions if spec is ambiguous
- Be conservative with size estimates (better to overestimate)
- Document ALL assumptions

### For Agent 2 (Reviewer):
- Check spec coverage first (most important)
- Look for circular dependencies
- Verify acceptance criteria are testable
- Flag risks that seem underestimated

### For Agent 3 (Issue Creator):
- Always verify approval status first
- Create labels/milestones before issues
- Use HEREDOCs for multi-line bodies
- Output summary for human verification
