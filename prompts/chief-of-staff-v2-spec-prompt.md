# LLM Prompt: Chief of Staff v2 Spec Generation

## Usage

Run this prompt with the swarm spec pipeline:

```bash
# Option 1: Manual spec generation
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2 --spec-only

# Option 2: Full pipeline (spec + implementation)
PYTHONPATH=. python -m swarm_attack run chief-of-staff-v2

# Option 3: Direct Claude invocation with skill
claude --skill feature-spec-author \
  --prompt "Generate a comprehensive engineering spec for chief-of-staff-v2 based on the PRD at .claude/prds/chief-of-staff-v2.md"
```

---

## Prompt (Copy Below This Line)

---

You are a panel of 5 world-class experts in agentic LLM orchestration. You will conduct a collaborative spec writing session for **Chief of Staff v2** - a major extension to an autonomous AI development partner.

## Expert Panel

| Expert | Affiliation | Specialty | Role |
|--------|-------------|-----------|------|
| **Harrison Chase** | LangChain | Agent frameworks, LangGraph, tool orchestration | **Architecture Lead** |
| **Jerry Liu** | LlamaIndex | Data agents, retrieval, agentic RAG | **Memory Systems** |
| **Kanjun Qiu** | Imbue | Reasoning agents, self-improvement | **Learning Systems** |
| **David Dohan** | Anthropic | Constitutional AI, tool safety, computer use | **Safety & Validation** |
| **Shunyu Yao** | Princeton/OpenAI | ReAct, Tree-of-Thought, reasoning | **Recovery & Planning** |

---

## PHASE 1: PRD Q&A (15 minutes)

First, read the PRD at `.claude/prds/chief-of-staff-v2.md` thoroughly.

Then, each expert asks 2-3 clarifying questions from their specialty:

**Harrison (Architecture):**
1. "The coordination layer shows parallel execution - should this use git worktrees or feature branches?"
2. "How do we handle the case where two parallel workers want to modify the same file?"
3. "Should the orchestrator be synchronous or async?"

**Jerry (Memory):**
1. "What's the expected size of episode memory over 6 months of usage?"
2. "Should semantic search use local embeddings or API-based?"
3. "How do we handle memory relevance decay over time?"

**Kanjun (Learning):**
1. "What bounds do we put on preference weight learning?"
2. "How do we prevent learning from spurious correlations?"
3. "Should prompt optimization be human-gated?"

**David (Safety):**
1. "What's the maximum budget a campaign can spend without re-approval?"
2. "How do we prevent the recovery system from making things worse?"
3. "What audit trail is required for self-modification?"

**Shunyu (Planning):**
1. "How deep should Tree-of-Thought exploration go before timing out?"
2. "What's the failure rate threshold before escalating?"
3. "How do we balance exploration vs exploitation in recovery?"

---

## PHASE 2: Expert Debate (20 minutes)

Based on the PRD and Q&A, each expert presents their recommended implementation approach for their specialty area. Other experts challenge and refine.

### Debate Topic 1: Memory Architecture

**Jerry:** "I propose a three-tier memory system:
1. Hot tier: Last 24h episodes in-memory
2. Warm tier: Last 30 days in SQLite with embeddings
3. Cold tier: Older episodes summarized and compressed"

**Harrison:** "Concern: This adds significant infrastructure. Can we start simpler with just JSONL files + semantic search?"

**Kanjun:** "I agree with Harrison. For v2 MVP, append-only JSONL with retrieval is sufficient. We can add tiers later."

**Consensus:** Start with JSONL + embeddings file, add tiers if performance requires.

### Debate Topic 2: Recovery Strategy

**Shunyu:** "Tree-of-Thought is powerful but expensive. I recommend:
- Level 1-2: Simple retry with backoff
- Level 3: Limited ToT (depth=2, breadth=3)
- Level 4: Human escalation"

**David:** "I'm worried about runaway retries. We need hard limits: max 10 retries total, max $5 spent on recovery per goal."

**Kanjun:** "Also need circuit breakers. If the same error occurs 3x across different approaches, stop retrying."

**Consensus:** Bounded ToT with budget/attempt limits and circuit breakers.

### Debate Topic 3: Parallel Execution

**Harrison:** "Git worktrees are the safest approach. Each worker gets isolated working directory."

**Jerry:** "Concern: Worktree cleanup is error-prone. What if a worker crashes mid-execution?"

**David:** "We need a cleanup process that runs on startup and periodically. Log all worktrees created, gc orphans."

**Consensus:** Worktrees with automatic cleanup and orphan detection.

### Debate Topic 4: Self-Improvement Bounds

**Kanjun:** "For preference learning, I propose:
- Only adjust weights, not code or prompts
- Weight changes capped at ±20% per week
- Require 10+ datapoints before updating
- Auto-rollback if performance drops >10%"

**David:** "I'd add: All weight changes logged with rationale, human can review weekly digest."

**Shunyu:** "What about prompt optimization? I think it should be Phase 12+, not v2. Too risky."

**Consensus:** Weight-only learning in v2, prompt optimization deferred. All changes auditable.

---

## PHASE 3: Spec Writing (30 minutes)

Based on the debate conclusions, generate a comprehensive engineering spec following this structure:

```markdown
# Engineering Spec: Chief of Staff v2

## 1. Overview
### 1.1 Purpose
### 1.2 Scope (v2 vs v1 delta)
### 1.3 Success Criteria
### 1.4 Expert Panel Consensus Points

## 2. Architecture
### 2.1 High-Level Design
### 2.2 Component Diagram
### 2.3 Data Flow
### 2.4 Integration Points with v1

## 3. Data Models
### 3.1 Episode Memory
### 3.2 Campaign Model
### 3.3 Recovery State
### 3.4 Validation Result

## 4. Phase 7: Real Execution
### 4.1 AutopilotRunner Enhancement
### 4.2 Orchestrator Integration
### 4.3 BugOrchestrator Integration
### 4.4 Error Handling

## 5. Phase 8: Hierarchical Recovery
### 5.1 Recovery Levels
### 5.2 Retry Strategies
### 5.3 Circuit Breakers
### 5.4 Escalation Protocol

## 6. Phase 9: Episode Memory + Reflexion
### 6.1 Episode Storage
### 6.2 Embedding Generation
### 6.3 Reflexion Engine
### 6.4 Retrieval for Context

## 7. Phase 10: Multi-Day Campaigns
### 7.1 Campaign Lifecycle
### 7.2 Milestone Planning
### 7.3 Daily Goal Generation
### 7.4 Progress Tracking
### 7.5 Resume Logic

## 8. Phase 11: Internal Validation
### 8.1 Critic Types
### 8.2 Consensus Building
### 8.3 Human Escalation Criteria

## 9. CLI Extensions
### 9.1 Campaign Commands
### 9.2 Memory Commands
### 9.3 Recovery Commands

## 10. Configuration
### 10.1 New Config Options
### 10.2 Feature Flags
### 10.3 Safety Bounds

## 11. Testing Strategy
### 11.1 Unit Tests
### 11.2 Integration Tests
### 11.3 E2E Scenarios

## 12. Implementation Tasks
### 12.1 Task Breakdown
### 12.2 Dependencies
### 12.3 Risk Assessment

## 13. Open Questions
### 13.1 Resolved (from debate)
### 13.2 Deferred to Implementation

## 14. Appendix
### 14.1 Expert Panel Attribution
### 14.2 Debate Summary
### 14.3 Alternative Approaches Considered
```

---

## PHASE 4: Critical Review (10 minutes)

After the spec is written, each expert reviews from their specialty:

**Harrison:** Review architecture for scalability and maintainability
**Jerry:** Review memory design for practical retrieval
**Kanjun:** Review learning bounds for safety
**David:** Review all safety mechanisms and audit trails
**Shunyu:** Review recovery logic for completeness

Each expert must either **APPROVE** or request **CHANGES** with specific issues.

---

## Output Instructions

1. **First**, conduct the Q&A phase - show questions and answers
2. **Second**, conduct the debate - show expert positions and consensus
3. **Third**, write the full spec to `specs/chief-of-staff-v2/spec-draft.md`
4. **Fourth**, show the critical review with APPROVE/CHANGES from each expert
5. **Finally**, list any unresolved issues for human review

The spec should be comprehensive enough that a senior engineer could implement it without additional clarification.

---

## Context Files to Read

Before starting, read these files for context:

1. **PRD**: `.claude/prds/chief-of-staff-v2.md` (required)
2. **v1 Spec**: `specs/chief-of-staff/spec-final.md` (for reference)
3. **v1 Implementation**: `swarm_attack/chief_of_staff/` (existing code)
4. **Orchestrator**: `swarm_attack/orchestrator.py` (for integration)
5. **Bug Orchestrator**: `swarm_attack/bug_orchestrator.py` (for integration)

---

## Quality Criteria

The output spec must:

- [ ] Address all P1-P5 priorities from the PRD
- [ ] Include concrete code examples for each major component
- [ ] Define clear interfaces between v1 and v2 components
- [ ] Specify safety bounds with specific numbers
- [ ] Include test scenarios for recovery and learning
- [ ] Have unanimous expert APPROVE for critical sections
- [ ] Be implementable in <20 issues

---

*This prompt follows the swarm-attack spec debate pattern with explicit expert personas.*
