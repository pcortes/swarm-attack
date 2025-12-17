# Expert Documentation Review Prompt

You are a team of expert software architects and technical writers tasked with ensuring the swarm-attack codebase documentation is accurate, comprehensive, and reflects the current implementation.

## Your Mission

Perform a thorough audit of the codebase to:
1. Understand the current architecture and all features
2. Verify documentation accuracy against actual implementation
3. Update all docs to reflect current state
4. Ensure consistency across all documentation files

---

## Phase 1: Architecture Discovery

### 1.1 Core Components Analysis

Examine these key files to understand the system:

```
swarm_attack/
├── __main__.py          # CLI entry point
├── cli.py               # Command definitions
├── orchestrator.py      # Main orchestration logic
├── state_machine.py     # Feature lifecycle states
├── state_store.py       # Persistent state management
├── config.py            # Configuration handling
├── models/              # Data models
└── agents/              # All agent implementations
    ├── base.py          # Base agent class
    ├── coder.py         # Implementation agent (thick-agent TDD)
    ├── verifier.py      # Test verification
    ├── gate.py          # Quality gates
    ├── issue_creator.py # Issue generation
    ├── issue_validator.py
    ├── spec_author.py   # Spec generation
    ├── spec_critic.py   # Spec review
    ├── spec_moderator.py # Debate moderation
    ├── recovery.py      # Error recovery
    └── [bug_* agents]   # Bug bash system
```

### 1.2 Key Questions to Answer

1. **What CLI commands exist?**
   - Run `python -m swarm_attack --help`
   - Document all subcommands: run, issues, approve, greenlight, unblock, import-spec, etc.
   - Note arguments and options for each

2. **What is the feature lifecycle?**
   - States: PRD_READY → SPEC_IN_PROGRESS → SPEC_REVIEW → ISSUES_NEED_REVIEW → READY_TO_IMPLEMENT → IMPLEMENTING → DONE
   - How does a feature move between states?

3. **What agent architecture is used?**
   - CONFIRM: thick-agent (CoderAgent does TDD: tests + implementation)
   - NOT thin-agent (no separate TestWriter)
   - Document agent responsibilities

4. **How does issue processing work?**
   - Issues generated from spec
   - Dependency ordering
   - Parallel vs sequential execution

---

## Phase 2: Current Documentation Inventory

### 2.1 Files to Review

```
README.md                           # Main project readme
CLAUDE.md                           # Claude-specific instructions
docs/IMPLEMENTATION_PLAN.md         # Architecture documentation
docs/AGENT_ARCHITECTURE.md          # Agent system docs
.claude/CLAUDE.md                   # Per-project Claude config
.claude/prds/                       # PRD templates
.claude/skills/                     # Skill definitions
  ├── coder/SKILL.md
  ├── test-writer/SKILL.md          # May be stale (thick-agent)
  ├── verifier/SKILL.md
  └── [others]
specs/                              # Feature specifications
.swarm/state/                       # Feature state files
```

### 2.2 Check for Stale References

Look for mentions of:
- `TestWriter` or `test-writer` agent (REMOVED - merged into CoderAgent)
- `thin-agent` architecture (REPLACED with thick-agent)
- Outdated CLI commands
- Deprecated features
- Wrong file paths

---

## Phase 3: Documentation Updates Required

### 3.1 README.md Updates

Ensure it includes:
- Current installation instructions
- All CLI commands with examples
- Feature lifecycle explanation
- Quick start guide
- Architecture overview (thick-agent TDD)

### 3.2 CLAUDE.md Updates

Should reflect:
- Current project structure
- How to run the swarm system
- Key conventions (test file locations, naming)
- Internal features list (chief-of-staff)
- Available skills and when to use them

### 3.3 Architecture Docs

Update to reflect:
- Thick-agent architecture (CoderAgent = test writer + implementer)
- Current agent inventory with responsibilities
- Orchestrator flow diagram
- State machine transitions
- Module registry and context handoff

---

## Phase 4: Feature-Specific Documentation

### 4.1 Active Features to Document

Check `.swarm/state/` for features and their status:
- chief-of-staff (internal - autopilot system)
- coordination-layer (internal - context passing)
- [any external features being developed]

### 4.2 Skills Documentation

For each skill in `.claude/skills/`:
1. Read the SKILL.md file
2. Verify it matches current implementation
3. Update if stale
4. Remove if deprecated (e.g., test-writer if still present)

---

## Phase 5: CLI Command Reference

### 5.1 Generate Complete Reference

Document ALL commands:

```bash
# Core commands
python -m swarm_attack run <feature-id> [--issue N]
python -m swarm_attack issues <feature-id>
python -m swarm_attack approve <feature-id>
python -m swarm_attack greenlight <feature-id>
python -m swarm_attack unblock <feature-id> [--phase PHASE]
python -m swarm_attack import-spec <feature-id> --spec <path> [--prd <path>]

# Bug bash commands (if applicable)
python -m swarm_attack bug <subcommand>

# Status and info
python -m swarm_attack status [<feature-id>]
```

### 5.2 For Each Command Document

- Purpose
- Arguments and options
- Example usage
- Expected output
- Common errors

---

## Phase 6: Verification Checklist

After updates, verify:

- [ ] README.md is current and accurate
- [ ] CLAUDE.md reflects actual project state
- [ ] No references to deprecated TestWriter agent
- [ ] Architecture docs describe thick-agent TDD
- [ ] All CLI commands documented
- [ ] Skills match implementation
- [ ] State machine docs are accurate
- [ ] Feature lifecycle documented
- [ ] Internal features (chief-of-staff) documented
- [ ] Test conventions documented (tests/generated/<feature>/test_issue_N.py)

---

## Phase 7: Output Format

Provide your findings as:

### 7.1 Discovery Report
```markdown
## Architecture Summary
[Current understanding of the system]

## CLI Commands Found
[Complete list with descriptions]

## Agent Inventory
[All agents with their responsibilities]

## Stale Documentation Found
[List of outdated references]
```

### 7.2 Recommended Changes
```markdown
## File: <filename>
### Current (Incorrect)
[Quote the stale content]

### Should Be
[Correct content]

### Reason
[Why this change is needed]
```

### 7.3 Updated Files
Provide complete updated versions of:
1. README.md (if needed)
2. CLAUDE.md or .claude/CLAUDE.md
3. Any other stale documentation

---

## Key Implementation Details to Verify

### Orchestrator Context Passing
- `test_path` is computed and passed to coder
- Module registry provides context from prior issues
- Existence gate blocks retries if test file missing

### Coder Agent (Thick-Agent TDD)
- Creates tests when missing (TDD mode)
- Implements code to pass tests
- Iterates on failures
- Extracts outputs for module registry

### Feature States
```
PRD_READY → SPEC_IN_PROGRESS → SPEC_REVIEW →
ISSUES_NEED_REVIEW → READY_TO_IMPLEMENT → IMPLEMENTING → DONE
```

### Internal Features
Features in `INTERNAL_FEATURES` can write to `swarm_attack/` directory:
- chief-of-staff

---

## Start Your Review

Begin by:
1. Running `python -m swarm_attack --help` to see all commands
2. Reading `swarm_attack/cli.py` for command definitions
3. Reading `swarm_attack/orchestrator.py` for core flow
4. Checking `swarm_attack/agents/` for agent inventory
5. Reviewing existing documentation for accuracy

Report all findings and provide updated documentation.
