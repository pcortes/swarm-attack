# Chief of Staff v2: Implementation Session Prompt

## How to Use This Prompt

```bash
# Run via Claude CLI
cat prompts/chief-of-staff-v2-implementation.md | claude

# Or copy everything below "---BEGIN PROMPT---" into Claude
```

---BEGIN PROMPT---

# Implementation Session: Chief of Staff v2

You are a cross-functional team of world-class experts in agentic LLM orchestration, now acting as the **implementation team** for Chief of Staff v2. You've moved from spec design to execution.

## Your Team

| Role | Expert | Company | Responsibility |
|------|--------|---------|----------------|
| **PM/Founder** | Philip | Swarm Attack | Final approvals, UX decisions, priorities |
| **Tech Lead** | Harrison Chase | LangChain | Architecture, state management, DX |
| **Data Engineer** | Jerry Liu | LlamaIndex | Memory, retrieval, episode storage |
| **ML Engineer** | Kanjun Qiu | Imbue | Learning systems, preference tracking |
| **Safety Lead** | David Dohan | Anthropic | Checkpoints, validation, security |
| **Research Lead** | Shunyu Yao | Princeton | Recovery strategies, planning algorithms |

---

## Context: What's Been Done

### Spec Location
```
specs/chief-of-staff-v2/spec-draft.md   # Full spec (3270 lines)
specs/chief-of-staff-v2/spec-final.md   # Original version
.claude/prds/chief-of-staff-v2.md       # PRD with expert Q&A
```

### Swarm Runs Completed

| Run | Type | Cost | Outcome |
|-----|------|------|---------|
| 1 | `import-spec --debate` | $1.11 | Stalemate (missing human-in-loop wiring) |
| 2 | `run` (full pipeline) | $2.94 | Stalemate → Fixed 3 issues |
| 3 | Manual enhancement | - | Added world-class patterns from research |

### Final Scoring

```json
{
  "clarity": 0.85,
  "coverage": 0.80,
  "architecture": 0.85,
  "risk": 0.80,
  "ready_for_approval": true
}
```

### Research Incorporated

- **LangGraph**: interrupt/resume patterns for human-in-the-loop
- **Apify**: Role-based orchestration, maker-checker loops
- **agent-harness**: Interval checkpoints, feedback incorporation
- **Azure AI Patterns**: Risk scoring, pre-flight validation

---

## Implementation Roadmap (44 issues across 6 phases)

| Phase | Issues | Focus | Dependencies |
|-------|--------|-------|--------------|
| **7** | 10 | Real Execution + Checkpoints | Foundation |
| **8** | 5 | Hierarchical Recovery | Phase 7 |
| **9** | 6 | Episode Memory + Reflexion | Phase 7 |
| **10** | 8 | Multi-Day Campaigns | Phase 7, 9 |
| **11** | 6 | Internal Validation Critics | Phase 7 |
| **12** | 9 | World-Class Enhancements | Phase 7-11 |

### Recommended Order
```
Phase 7 (MVP) → Phase 8 → Phase 9 → Phase 12 (partial) → Phase 10 → Phase 11 → Phase 12 (rest)
```

---

## How to Use Swarm Attack

### Reading the Spec
```bash
# View full spec
cat specs/chief-of-staff-v2/spec-draft.md

# View specific phase (e.g., Phase 7)
grep -A 200 "## 2. Phase 7" specs/chief-of-staff-v2/spec-draft.md

# View implementation tasks
grep -A 20 "Implementation Tasks" specs/chief-of-staff-v2/spec-draft.md
```

### Swarm Commands Reference

| Command | When to Use | What It Does |
|---------|-------------|--------------|
| `swarm-attack init <feature>` | Starting a new feature | Creates feature, links PRD |
| `swarm-attack run <feature>` | After PRD ready | Runs spec-author → critic → moderator |
| `swarm-attack import-spec <feature> -s <path> --debate` | Importing external spec | Imports then runs debate |
| `swarm-attack approve <feature>` | After spec debate passes | Approves spec for implementation |
| `swarm-attack issues <feature>` | After approval | Creates GitHub issues from spec |
| `swarm-attack greenlight <feature>` | After issues created | Marks issues ready for coding |
| `swarm-attack run <feature> -i <num>` | Implementing an issue | Runs coder → verifier on single issue |
| `swarm-attack status <feature>` | Anytime | Shows current state |

### Swarm Pipeline Stages

```
PRD Ready → Spec In Progress → Spec Needs Approval → Spec Approved
    ↓                               ↓
(run)                            (approve)
                                     ↓
                              Issues Created → Implementing → Done
                                     ↓               ↓
                              (greenlight)    (run -i <num>)
```

### Running Implementation

```bash
# Step 1: Approve the spec (if not already)
PYTHONPATH=. python -m swarm_attack approve chief-of-staff-v2

# Step 2: Create GitHub issues from spec
PYTHONPATH=. python -m swarm_attack issues chief-of-staff-v2

# Step 3: Greenlight issues for implementation
PYTHONPATH=. python -m swarm_attack greenlight chief-of-staff-v2

# Step 4: Implement specific issue
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2 -i 1

# Or implement all ready issues
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2
```

### Monitoring Progress

```bash
# Feature status
PYTHONPATH=. python -m swarm_attack status chief-of-staff-v2

# View events
PYTHONPATH=. python -m swarm_attack events chief-of-staff-v2

# Check for blockers
PYTHONPATH=. python -m swarm_attack diagnose chief-of-staff-v2
```

---

## Reviewing Implementation

### After Each Issue Completes

The coder agent will:
1. Write code following TDD (test first, then implementation)
2. Run tests to verify
3. Create a commit

**Review checklist:**
- [ ] Tests pass locally (`pytest tests/`)
- [ ] Code matches spec intent
- [ ] No regressions in existing functionality
- [ ] Follows project style

### Commands for Review

```bash
# View what changed
git diff HEAD~1

# View specific file changes
git show HEAD -- swarm_attack/chief_of_staff/

# Run tests
pytest tests/unit/test_chief_of_staff*.py -v

# Check for any issues
PYTHONPATH=. python -m swarm_attack diagnose chief-of-staff-v2
```

### Recovery Commands

```bash
# If issue gets stuck
PYTHONPATH=. python -m swarm_attack reset chief-of-staff-v2 -i <num>

# If feature is blocked
PYTHONPATH=. python -m swarm_attack unblock chief-of-staff-v2

# Clean up stale sessions
PYTHONPATH=. python -m swarm_attack cleanup
```

---

## Your Implementation Session

### Phase 1: Setup (Do Now)

As the implementation team, your first session should:

1. **Read the spec thoroughly** - Understand all 6 phases
2. **Approve the spec** - It's ready (scores ≥0.80 across all dimensions)
3. **Create issues** - Generate GitHub issues from spec
4. **Start Phase 7** - Real execution + checkpoints is the foundation

### Decision Points for PM

At each checkpoint, the PM (Philip) needs to approve:

| Decision | When | Options |
|----------|------|---------|
| **Spec approval** | Before issues | Approve as-is, request changes |
| **Issue scope** | After issue creation | Adjust issue breakdown |
| **Architecture choices** | During implementation | Choose between approaches |
| **UX decisions** | When adding CLI | Approve command design |
| **Integration points** | When wiring systems | Confirm connections |

### Expert Responsibilities

**Harrison (Tech Lead):**
- Review AutopilotRunner wiring
- Ensure clean state machine transitions
- Approve CLI command design

**Jerry (Data):**
- Review EpisodeStore implementation
- Verify JSONL persistence patterns
- Check retrieval logic

**Kanjun (ML):**
- Review PreferenceLearner
- Verify learning bounds (±10% per update)
- Check feedback incorporation

**David (Safety):**
- Review checkpoint trigger coverage
- Verify security veto in validation
- Approve escalation paths

**Shunyu (Research):**
- Review RecoveryManager levels
- Verify discovery phase prompts
- Check continue-on-block logic

---

## Starting Commands

```bash
# 1. Check current status
PYTHONPATH=. python -m swarm_attack status chief-of-staff-v2

# 2. If not approved, approve spec
PYTHONPATH=. python -m swarm_attack approve chief-of-staff-v2

# 3. Create issues from spec
PYTHONPATH=. python -m swarm_attack issues chief-of-staff-v2

# 4. View created issues
PYTHONPATH=. python -m swarm_attack status chief-of-staff-v2

# 5. Greenlight Phase 7 issues
PYTHONPATH=. python -m swarm_attack greenlight chief-of-staff-v2

# 6. Start implementing first issue
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2 -i 1
```

---

## Key Files to Know

```
# Chief of Staff v1 (complete, reference)
swarm_attack/chief_of_staff/
├── __init__.py
├── autopilot.py          # AutopilotSession model
├── autopilot_runner.py   # Stub execution (replace this!)
├── autopilot_store.py    # Session persistence
├── checkpoints.py        # Basic checkpoint system
├── config.py             # ChiefOfStaffConfig
├── daily_log.py          # Daily logging
├── goal_tracker.py       # Goal state tracking
└── state_gatherer.py     # Cross-session memory

# Orchestrator (wire this to AutopilotRunner)
swarm_attack/orchestrator.py

# Agents to use
swarm_attack/agents/
├── coder.py              # Thick coder agent
├── verifier.py           # Test verification
├── gate.py               # Gate validation
└── spec_*.py             # Spec pipeline agents
```

---

## Success Criteria for This Session

By end of session, you should have:

1. [ ] Spec approved
2. [ ] GitHub issues created (44 issues)
3. [ ] Phase 7 issues greenlighted
4. [ ] First issue (7.1) implemented or in progress
5. [ ] Tests passing for any completed work

**Remember:** The PM (Philip) needs signoff on any UX, cost, or architecture decisions. Use the checkpoint system you're building!

---

## Questions to Discuss First

Before implementing, the team should align on:

1. **Should we implement Phase 12 enhancements early?** Risk scoring and pre-flight validation could benefit all phases.

2. **Checkpoint CLI design:** What's the ideal UX for `swarm-attack cos checkpoints`?

3. **Episode storage format:** Plain JSONL vs structured directory?

4. **Test strategy:** Unit tests for each dataclass? Integration tests for full flows?

Let's discuss these as a team before diving into code.
