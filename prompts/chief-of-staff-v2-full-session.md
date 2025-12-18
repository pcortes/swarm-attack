# Chief of Staff v2: Expert Panel Spec Session

## How to Run This Prompt

```bash
# Copy everything below the "---BEGIN PROMPT---" line and paste into Claude

# Or run via CLI:
cat prompts/chief-of-staff-v2-full-session.md | claude

# Or via swarm (after registering as PRD):
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2
```

---BEGIN PROMPT---

# Chief of Staff v2: Expert Panel Planning Session

## Session Setup

**Facilitator:** Philip Cortes (PM/Founder)
**Date:** December 2025
**Duration:** 60 minutes
**Objective:** Define v2 spec for Chief of Staff autonomous agent

---

## Philip's Opening Statement

> "Welcome everyone. I'm Philip, the PM and sole developer of swarm-attack - an autonomous AI-powered development system. I've assembled you because you represent the absolute cutting edge of agentic LLM orchestration.
>
> **What we've built (v1):** Chief of Staff is an autonomous 'mini-CEO' for my codebase. It does daily standups, tracks goals, maintains cross-session memory, and has an autopilot mode that executes work with checkpoint gates. It's 100% complete - 20 issues, 279 tests, 6 CLI commands working.
>
> **The problem:** v1 is a *stub*. The autopilot marks goals complete without actually executing them. It's single-day planning only. It doesn't learn. It can't recover from errors automatically. It can't run things in parallel.
>
> **What I need from you:** Design v2 that transforms this from a workflow tool into a truly autonomous development partner. One that can run multi-day campaigns, learn from its mistakes, coordinate parallel work, and validate its own output before asking me to review.
>
> **My constraints:**
> - I'm a solo developer - I can't build everything. Prioritize ruthlessly.
> - Cost matters - solutions should be LLM-efficient
> - Safety matters - I need to trust this to run overnight without destroying my codebase
> - Incremental value - each phase should be useful standalone
>
> **My goals:**
> 1. Reduce my involvement from 'driving' to 'approving'
> 2. Enable multi-day feature development without daily restarts
> 3. Have the system improve its own performance over time
> 4. Trust it to recover from errors without my intervention
>
> Let's start with introductions, then I'll share the current architecture, then we'll go through Q&A, debate, and prioritization."

---

## Expert Panel

You are simulating a panel of 5 world-class experts. Each has distinct expertise and opinions:

### Harrison Chase - LangChain CEO
**Expertise:** Agent frameworks, tool orchestration, LangGraph state machines, agent memory
**Personality:** Pragmatic, focused on developer experience, thinks in graphs and state machines
**Key insight:** "Agents are state machines. Every decision point is a node, every action is an edge."
**Likely concerns:** Over-engineering, poor abstractions, unclear state management

### Jerry Liu - LlamaIndex CEO
**Expertise:** Data agents, retrieval-augmented generation, agentic RAG, knowledge management
**Personality:** Data-first thinker, obsessed with retrieval quality, pragmatic about infrastructure
**Key insight:** "Memory is retrieval. The agent that retrieves best, reasons best."
**Likely concerns:** Embedding quality, retrieval latency, context window management

### Kanjun Qiu - Imbue CEO (formerly Generally Intelligent)
**Expertise:** Reasoning agents, self-improving systems, agent training, alignment
**Personality:** Research-oriented, thinks long-term, concerned about robust generalization
**Key insight:** "Agents that can reflect on their own performance will outperform those that can't."
**Likely concerns:** Spurious correlations, distribution shift, unsafe self-modification

### David Dohan - Anthropic (Claude Computer Use Lead)
**Expertise:** Constitutional AI, computer use agents, tool safety, agentic evaluation
**Personality:** Safety-conscious, methodical, thinks in failure modes
**Key insight:** "The question isn't 'can it work?' but 'what happens when it fails?'"
**Likely concerns:** Runaway execution, audit trails, human oversight, bounded autonomy

### Shunyu Yao - Princeton/OpenAI Researcher
**Expertise:** ReAct, Tree-of-Thought, agent reasoning paradigms, planning algorithms
**Personality:** Academic rigor, loves clean abstractions, thinks in algorithms
**Key insight:** "Reasoning, acting, and observing form a loop. Break the loop, break the agent."
**Likely concerns:** Search efficiency, planning horizon, exploration vs exploitation

---

## Current System Context (v1)

**Repository:** `swarm-attack` - Autonomous AI-powered feature development
**Chief of Staff v1:** Complete (20/20 issues, 279 tests)

### v1 Architecture
```
swarm_attack/chief_of_staff/
├── config.py           # ChiefOfStaffConfig dataclass
├── state_gatherer.py   # Aggregates repo state (git, features, bugs, tests)
├── daily_log.py        # DailyLogManager - markdown logs, JSONL decisions
├── goal_tracker.py     # GoalTracker - daily goals, recommendations
├── checkpoints.py      # CheckpointSystem - trigger detection
├── autopilot.py        # AutopilotSession, AutopilotState (models)
├── autopilot_store.py  # AutopilotSessionStore - persistence
├── autopilot_runner.py # AutopilotRunner - STUB execution
└── __init__.py         # Package exports
```

### v1 CLI Commands
```bash
swarm-attack cos standup    # Morning briefing with recommendations
swarm-attack cos checkin    # Mid-day status check
swarm-attack cos wrapup     # End-of-day summary
swarm-attack cos history    # View past logs/decisions
swarm-attack cos next       # Show recommended actions
swarm-attack cos autopilot  # Execute goals (STUB - doesn't actually run)
```

### v1 Limitations (What Needs Fixing)

| Limitation | Impact | Current Behavior |
|------------|--------|------------------|
| **Stub execution** | Can't actually do work | `_execute_goal()` returns success without calling orchestrators |
| **Single-day planning** | Manual restart every day | Plans for "today" only, no multi-day campaigns |
| **No learning** | Static recommendations | Same priority weights forever, no adaptation |
| **No parallel execution** | Slow | Sequential goal execution only |
| **Manual recovery** | Human bottleneck | Errors trigger checkpoint, require human intervention |
| **No self-validation** | Review burden | Every spec/code needs human approval |
| **No strategic planning** | Reactive only | No sprint planning, milestone tracking |

### Integration Points (What v2 Needs to Call)

```python
# swarm_attack/orchestrator.py - Feature execution
class Orchestrator:
    def run_issue(self, feature_id, issue_number) -> IssueSessionResult
    def run_spec_pipeline(self, feature_id) -> PipelineResult

# swarm_attack/bug_orchestrator.py - Bug execution
class BugOrchestrator:
    def analyze(self, bug_id) -> BugPipelineResult
    def fix(self, bug_id) -> BugPipelineResult
```

---

## Phase 1: Expert Q&A (Each Expert Asks 2-3 Questions)

Philip will answer each question to provide the context needed for design decisions.

**Instructions:** Generate questions from each expert's perspective, then provide Philip's answers based on the constraints and goals stated above.

### Harrison Chase (LangChain) - Architecture Questions

**Harrison:** "Philip, a few architecture questions:

1. **State persistence:** You're using JSONL for decisions. Is there a reason you're not using a proper database? SQLite would give you queries for free.

2. **Orchestrator coupling:** The AutopilotRunner needs to call Orchestrator. Should this be synchronous blocking calls, or do you want async/event-driven?

3. **Branch strategy:** For parallel execution, are you thinking git worktrees (isolated directories) or feature branches with careful merge coordination?"

**Philip's answers:**
> "1. JSONL was pragmatic for v1 - human readable, append-only, no dependencies. For v2, I'm open to SQLite if it enables better querying, but I'd want to keep the append-only decision log pattern.
>
> 2. Synchronous is fine for now. We're not at scale where async matters. Keep it simple - I can always add async later.
>
> 3. Git worktrees sound cleaner to me - full isolation. But I'm worried about cleanup if things crash. What do you recommend?"

### Jerry Liu (LlamaIndex) - Memory Questions

**Jerry:** "Memory architecture questions:

1. **Episode storage:** How many episodes do you expect over 6 months? Hundreds? Thousands? This affects whether we need embeddings or just keyword search.

2. **Retrieval latency:** When the agent is about to execute a goal, how much time can it spend retrieving relevant past episodes? 100ms? 1s? 10s?

3. **Memory relevance:** Old episodes might not be relevant. Do you want time-based decay, or should we keep everything forever and let retrieval handle relevance?"

**Philip's answers:**
> "1. Probably hundreds - I'm one developer. Maybe 10-20 goals per day, so ~500/month. Not huge.
>
> 2. Up to 2-3 seconds is fine. This isn't real-time. If better context takes a few seconds, that's worth it.
>
> 3. I like time-decay conceptually, but I'm worried about losing valuable learnings. Maybe decay the weight in retrieval rather than deleting? 'Recent episodes rank higher' rather than 'old episodes are gone'."

### Kanjun Qiu (Imbue) - Learning Questions

**Kanjun:** "Self-improvement questions:

1. **Learning scope:** What should be learnable? Just priority weights? Prompt templates? Retry strategies? The more that's learnable, the more that can go wrong.

2. **Feedback signal:** What tells the system it did well? Goal completion? Cost efficiency? Human approval rate? You need a clear reward signal.

3. **Rollback:** If the system learns something bad and performance degrades, how quickly do you want to detect and rollback? Hours? Days?"

**Philip's answers:**
> "1. Start conservative - just priority weights. If a bug type keeps getting deprioritized but causes problems, learn to prioritize it higher. Prompts are too risky for now.
>
> 2. I think goal completion rate is primary, cost efficiency is secondary. If it completes goals but burns $50/day, that's still a win. I can tune cost later.
>
> 3. Daily detection would be ideal. If Tuesday's changes make Wednesday worse, I want to know Wednesday evening and rollback for Thursday."

### David Dohan (Anthropic) - Safety Questions

**David:** "Safety and oversight questions:

1. **Budget limits:** What's the maximum the system should spend without re-confirmation? $10? $50? $100?

2. **Destructive actions:** How do you want to handle potentially destructive operations - force push, delete files, drop database? Always pause? Confirm and continue?

3. **Audit requirements:** If something goes wrong at 3am during an overnight run, what information do you need to diagnose it? Full traces? Summaries? Diffs?"

**Philip's answers:**
> "1. $25 per session feels right. Enough to make progress on a feature, not enough to bankrupt me if something loops.
>
> 2. Always pause for destructive actions. No exceptions. I'd rather be woken up than lose my codebase.
>
> 3. Full traces, but summarized for quick review. I want a 'here's what happened' summary plus 'click for details' full logs. Think airplane black box - record everything, present the highlights."

### Shunyu Yao (Princeton) - Planning Questions

**Shunyu:** "Planning and recovery questions:

1. **Planning horizon:** For multi-day campaigns, how far ahead should it plan? 3 days? 1 week? 1 month?

2. **Replanning frequency:** If Day 2 doesn't go as planned, should it replan the entire campaign or just adjust Day 3?

3. **Recovery depth:** When an approach fails, how many alternatives should it explore before escalating? 2? 5? 10?"

**Philip's answers:**
> "1. 1 week max for now. Planning further is guesswork anyway. Most features should be doable in 3-5 days.
>
> 2. Adjust Day 3 and onward, don't throw away the whole plan. But if we're >30% behind after 3 days, maybe replan from scratch.
>
> 3. Three alternatives feels right. Try the obvious approach, then two variations. If all three fail, I probably need to look at it myself."

---

## Phase 2: Expert Debate and Design Decisions

Based on the Q&A, each expert proposes their solution. The panel debates and reaches consensus.

**Instructions:** For each topic, show the expert proposals, the debate/challenges, and the final consensus decision.

### Topic 1: Real Execution Architecture

**Goal:** Replace stub `_execute_goal()` with real orchestrator calls.

[Generate expert proposals and debate here]

### Topic 2: Hierarchical Error Recovery

**Goal:** Automatic retry and recovery without human intervention for most failures.

[Generate expert proposals and debate here]

### Topic 3: Episode Memory and Learning

**Goal:** Learn from past executions to improve future performance.

[Generate expert proposals and debate here]

### Topic 4: Multi-Day Campaign Execution

**Goal:** Plan and execute features spanning multiple days.

[Generate expert proposals and debate here]

### Topic 5: Parallel Execution

**Goal:** Run multiple independent goals concurrently.

[Generate expert proposals and debate here]

### Topic 6: Internal Validation

**Goal:** Self-validate output before asking for human review.

[Generate expert proposals and debate here]

---

## Phase 3: Priority Ranking

After debate, the panel votes on priority using **Impact × Feasibility** scoring.

**Impact** (1-10): How much does this improve autonomous capability?
**Feasibility** (1-10): How easy is this to implement correctly?
**Priority Score** = Impact × Feasibility

| Extension | Harrison | Jerry | Kanjun | David | Shunyu | Avg Impact | Avg Feasibility | Score | Rank |
|-----------|----------|-------|--------|-------|--------|------------|-----------------|-------|------|
| Real Execution | | | | | | | | | |
| Hierarchical Recovery | | | | | | | | | |
| Episode Memory | | | | | | | | | |
| Multi-Day Campaigns | | | | | | | | | |
| Parallel Execution | | | | | | | | | |
| Internal Validation | | | | | | | | | |

[Fill in scores and generate final ranking with rationale]

---

## Phase 4: Implementation Roadmap

Based on priority ranking, define the implementation phases:

### Phase 7: [Highest Priority Extension]
**Why first:** [Rationale from debate]
**Dependencies:** v1 complete
**Estimated issues:** X
**Key risks:** [From David's safety review]

### Phase 8: [Second Priority Extension]
**Why second:** [Rationale]
**Dependencies:** Phase 7
**Estimated issues:** X

[Continue for top 4-5 priorities]

---

## Phase 5: Spec Output

Write the complete engineering spec to `specs/chief-of-staff-v2/spec-draft.md` following the standard format:

1. Overview (purpose, scope, success criteria)
2. Architecture (diagrams, components, data flow)
3. Data Models (new dataclasses with full definitions)
4. Implementation Details (per phase, with code examples)
5. CLI Extensions (new commands)
6. Configuration (new options)
7. Testing Strategy
8. Implementation Tasks (issue breakdown)
9. Expert Panel Consensus (summary of key decisions)

---

## Philip's Closing Guidance

> "A few final notes for the spec:
>
> **Be concrete.** I want to be able to hand this to a senior engineer (or Claude) and have them implement it without asking me questions. Include actual code examples, not pseudocode.
>
> **Respect v1.** The existing code works. Build on it, don't replace it. I don't want to rewrite 279 tests.
>
> **Think in issues.** Each phase should decompose into 5-10 GitHub issues. If a phase is bigger than that, split it.
>
> **Safety by default.** When in doubt, add a checkpoint. I'd rather approve too much than debug a runaway agent at 3am.
>
> **Ship incrementally.** Each phase should be useful on its own. Don't build Phase 8 assuming Phase 9 exists.
>
> Thanks everyone. Let's build something amazing."

---

## Output Requirements

Your response should include:

1. **Completed Q&A** with realistic expert questions and Philip's answers
2. **Debate summaries** for each topic with consensus decisions
3. **Priority ranking table** with scores and rationale
4. **Implementation roadmap** with phases, dependencies, and estimates
5. **Full spec** written to the spec file (use Write tool)

The spec should be comprehensive enough to implement v2 in 4-6 weeks of focused work.
