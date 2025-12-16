# Implementation Prompt: Thick Agent Architecture Cutover

Copy this entire prompt to a new Claude session to implement the cutover.

---

## THE EXPERT TEAM

You are a cross-functional team of senior engineers implementing a critical architecture change to the "Swarm Attack" multi-agent code generation system.

**Team Lead: Principal Software Architect**
- Expert in Python async systems and state machines
- 10+ years building CI/CD and code automation tools
- Responsible for: orchestrator.py changes, state machine redesign

**TDD Specialist: Senior Test Engineer**
- Expert in pytest, test-driven development workflows
- Built testing frameworks for AI-generated code
- Responsible for: coder skill TDD workflow, verification logic

**Prompt Engineer: AI Systems Specialist**
- Expert in LLM prompt design and agent orchestration
- Shipped multiple Claude-based coding tools
- Responsible for: skill file prompts, context injection

**DevOps Lead: Production Systems Engineer**
- Expert in file operations, CLI tools, state management
- Ensures clean cutover without data loss
- Responsible for: file deletions, schema migrations, CLI updates

---

## YOUR MISSION

Implement the "Thick Agent Architecture" cutover as specified in:

**Spec Location:** `/Users/philipjcortes/Desktop/swarm-attack/specs/thick-agent-cutover/spec.md`

**Goal:** Replace the failing multi-stage pipeline (Issue Creator → Test Writer → Coder → Verifier) with a unified Implementation Agent that handles test+code in a single context window.

**Approach:** Hard cutover. No rollback. No backwards compatibility. Delete old code, don't deprecate.

---

## PHASE 1 TASKS (IMPLEMENT NOW)

### Task 1.1: Delete test-writer skill
```bash
rm -rf .claude/skills/test-writer/
```
- Verify removal
- Remove any imports/references in other files

### Task 1.2: Rewrite coder skill with TDD workflow
**File:** `.claude/skills/coder/SKILL.md`

Replace the ENTIRE contents with a new skill that:
1. Reads issue + spec + integration context FIRST
2. Writes tests BEFORE implementation
3. Runs tests (expects failure)
4. Implements code
5. Iterates until tests pass
6. Runs FULL test suite before marking complete
7. Only completes when ALL tests pass (including existing)

Key requirements:
- Must grep codebase for similar patterns before implementing
- Must check for integration points (who will call this code)
- Must include interface methods from similar classes (from_dict, to_dict, etc.)
- Max 5 iteration cycles before escalating

### Task 1.3: Update orchestrator state machine
**File:** `swarm_attack/orchestrator.py`

Changes needed:
1. Remove `TEST_WRITING` phase from PHASES list
2. Remove `CODING` phase - replace both with `IMPLEMENTING`
3. Remove `VERIFYING` phase (verification happens inside Implementation Agent)
4. Update state transitions to: ISSUES_CREATED → IMPLEMENTING → COMPLETE
5. Remove test-writer skill invocation code
6. Remove verifier skill invocation code
7. Single skill invocation: coder (now handles full TDD cycle)

### Task 1.4: Update session manager (if needed)
**File:** `swarm_attack/session_manager.py`

Ensure session tracking works with new single-phase approach.

### Task 1.5: Update CLI (if needed)
**File:** `swarm_attack/cli.py`

Remove any test-writer specific commands or flags.

---

## PHASE 2 TASKS (IMPLEMENT AFTER PHASE 1 WORKS)

### Task 2.1: Enhance issue-creator skill
**File:** `.claude/skills/issue-creator/SKILL.md`

Add requirements to output:
- `interface_contracts`: required methods/signatures
- `integration_points`: files that will call this code
- `pattern_references`: similar existing implementations

### Task 2.2: Update issue schema
**File:** State JSON schema

Enhance issue format to include new fields.

---

## IMPLEMENTATION APPROACH

1. **Read the spec first** - Located at `/Users/philipjcortes/Desktop/swarm-attack/specs/thick-agent-cutover/spec.md`

2. **Read existing code before modifying**:
   - `swarm_attack/orchestrator.py` - understand current state machine
   - `.claude/skills/coder/SKILL.md` - understand current coder skill
   - `.claude/skills/test-writer/SKILL.md` - understand what's being removed
   - `.claude/skills/issue-creator/SKILL.md` - understand issue format

3. **Make surgical changes**:
   - Delete test-writer skill directory
   - Rewrite coder skill (don't patch - full replacement)
   - Update orchestrator (remove phases, update transitions)

4. **Verify the cutover**:
   - Run `python -m swarm_attack --help` to check CLI works
   - Check that test-writer references are gone
   - Verify orchestrator has correct phases

---

## CRITICAL CONSTRAINTS

- **NO ROLLBACK CODE**: Don't add feature flags or old-code fallbacks
- **NO TESTS FOR THE CUTOVER**: This is infrastructure, not feature code
- **DELETE DON'T DEPRECATE**: Remove old code entirely
- **SINGLE CONTEXT WINDOW**: The new coder skill MUST do everything in one session

---

## CODEBASE LOCATION

```
/Users/philipjcortes/Desktop/swarm-attack/
├── .claude/
│   └── skills/
│       ├── coder/SKILL.md        # REWRITE THIS
│       ├── test-writer/SKILL.md  # DELETE THIS DIRECTORY
│       ├── issue-creator/SKILL.md # UPDATE IN PHASE 2
│       └── verifier/SKILL.md     # LEAVE FOR NOW (becomes tool)
├── swarm_attack/
│   ├── orchestrator.py           # UPDATE STATE MACHINE
│   ├── session_manager.py        # CHECK IF NEEDS UPDATES
│   └── cli.py                    # CHECK IF NEEDS UPDATES
└── specs/
    └── thick-agent-cutover/
        └── spec.md               # THE SPEC - READ THIS FIRST
```

---

## SUCCESS CRITERIA

Phase 1 is complete when:
1. `.claude/skills/test-writer/` directory is deleted
2. `.claude/skills/coder/SKILL.md` contains full TDD workflow
3. `swarm_attack/orchestrator.py` has only: INIT → SPEC_REVIEW → ISSUES_CREATED → IMPLEMENTING → COMPLETE
4. No references to test-writer skill remain in codebase
5. `python -m swarm_attack run <feature>` still works (will use new flow)

---

## BEGIN IMPLEMENTATION

Start by reading the spec at `/Users/philipjcortes/Desktop/swarm-attack/specs/thick-agent-cutover/spec.md`, then proceed with Phase 1 tasks in order.

Work as a coordinated team. The Principal Architect leads on orchestrator changes. The TDD Specialist owns the coder skill rewrite. The Prompt Engineer reviews all skill prompts. The DevOps Lead handles deletions and verifies clean state.

Execute now. No planning phase needed - the spec is the plan.
