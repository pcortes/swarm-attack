# Compound Engineering Plugin vs Swarm Attack: Key Architectural Differences

> **STATUS UPDATE:** This analysis led to the implementation of `swarm_attack/agents/tool_sets.py`. Key agents like `IssueCreatorAgent` and `ComplexityGateAgent` now use `get_tools_for_agent()` to get research tools (`["Read", "Glob", "Grep"]`). The `BaseAgent` class now has `DEFAULT_TOOLS = ["Read", "Glob", "Grep"]` and a `get_tools()` method. See `specs/agent-research-capability/SPEC.md` for full implementation details.

## Executive Summary

**The Core Problem (PARTIALLY RESOLVED):** Our Coder agent previously ran with `allowed_tools=[]` and received only text-based context in the prompt. This has been partially addressed - agents now use `get_tools_for_agent()` from `tool_sets.py` to get appropriate research tools.

---

## Detailed Comparison Table

| **Dimension** | **Compound Engineering Plugin** | **Our Swarm Attack** | **Impact** |
|--------------|----------------------------------|----------------------|------------|
| **🔧 Tool Access** | ✅ Agents have `allowed-tools: [Read, Edit, Bash, Glob]` | ❌ Coder runs with `allowed_tools=[]` | **CRITICAL**: Their agents can explore files, search code, run git commands. Ours are completely blind. |
| **📝 Context Mechanism** | Dynamic shell injection: `!`ls -1 ./skills/*/SKILL.md`\` executes during prompt construction | Static text only: All context pre-loaded into prompt string | **CRITICAL**: They inject live codebase state. We inject stale summaries. |
| **🧠 Agent Architecture** | Thin agents with tools (20-30 line prompts + exploration) | Thick agents without tools (1000+ line prompts with everything pre-baked) | **BLOCKER**: We compensate for no tools by injecting massive context, hitting token limits. |
| **📂 File Discovery** | Agents use `Glob` and `Read` to find integration points | Orchestrator must pre-extract and inject all file paths/content | **BLOCKER**: We miss files because orchestrator doesn't know what coder will need. |
| **🔍 Code Reading** | `Read` tool during execution to check existing implementations | All code injected as markdown in prompt | **REGRESSION**: Our prompts show truncated/stale code. Theirs always see latest. |
| **✏️ File Writing** | `Edit` tool for surgical changes, `Write` for new files | Text output with `# FILE:` markers, orchestrator parses and writes | **FRAGILE**: Our parsing can fail. Their tool calls are validated by CLI. |
| **🐚 Shell Commands** | `Bash` tool for git status, pytest, ls, etc. | No shell access - orchestrator runs tests externally | **BLIND**: Coder can't see test output, git state, or file listings. |
| **🔄 Context Handoff** | Each agent re-explores codebase via tools (no handoff needed) | Orchestrator extracts summaries → StateStore → CoderAgent context dict | **DRIFT**: Summaries lose 40% fidelity per transition. |
| **🎯 Prompt Size** | Small (skill prompt + live context from tools) | Massive (skill + spec + tests + existing code + summaries + registry) | **TOKEN LIMIT**: We hit max_turns because prompts are 20k+ chars. |
| **🏗️ Workflow Pattern** | Sequential tool calls: `Read(test) → Bash(pytest) → Edit(impl) → Bash(pytest)` | Single LLM call: `run(giant_prompt, allowed_tools=[])` | **ITERATION**: They iterate in-context. We retry entire agent. |
| **📊 State Management** | Stateless - tools provide current state on demand | StateStore persists everything (tasks, outputs, summaries) | **COMPLEXITY**: We need complex state hydration. They just read files. |
| **🧪 Test Feedback** | `Bash(pytest)` shows exact failures in context | Verifier agent runs pytest, extracts failures, passes to retry | **LATENCY**: They see failures instantly. We wait for full verifier cycle. |
| **🔐 Frontmatter Handling** | Frontmatter declares tools: `allowed-tools: Read,Edit,Bash` | We strip frontmatter to avoid tool confusion | **MISMATCH**: Their frontmatter = agent capability. Ours = misleading metadata we delete. |
| **🌲 Git Integration** | `Bash(git status)`, `Bash(git diff)` in agent context | Orchestrator manages git externally via GitHubSync | **CONTEXT**: They see uncommitted changes. We don't. |
| **📦 Module Discovery** | `Grep(pattern)` or `Glob(**/*.py)` to find classes/APIs | StateStore module registry + manual extraction | **STALE**: Registry reflects past state. Tools show current state. |

---

## Key Insight: The Blindness Problem

### Compound Engineering Pattern:
```yaml
---
name: coder
allowed-tools: Read,Glob,Bash,Write,Edit
---

# Coder Skill
You implement features. Here's how:

1. Read the test file to understand requirements
2. Search for integration points using Glob
3. Read existing code to match patterns
4. Write your implementation
5. Run tests to verify
6. Iterate until green
```

**Agent execution:**
1. LLM receives short prompt
2. Uses `Read` to examine test file
3. Uses `Glob` to find similar implementations
4. Uses `Bash` to run tests and see failures
5. Uses `Edit` to fix issues
6. Loop continues until tests pass

### Our Swarm Pattern:
```python
# coder.py line 1530
result = self.llm.run(
    prompt,  # 20,000+ char prompt with spec, tests, code, summaries
    allowed_tools=[],  # NO TOOLS
    max_turns=20,
)
```

**Coder execution:**
1. LLM receives massive prompt (all context pre-baked)
2. Has NO ability to explore codebase
3. Can't read files to check integration points
4. Can't run tests to see what failed
5. Must output text with `# FILE:` markers
6. Orchestrator parses text and writes files
7. Verifier runs tests externally and reports back

---

## What We're Missing: Dynamic Context Injection

### Their Dynamic Context (Shell Injection):
```markdown
## Context
<context>
Recent skills: !`ls -1 ./skills/*/SKILL.md | head -5`
Project files: !`find src -name "*.py" | wc -l`
Git status: !`git status --short`
</context>
```

**At runtime**, those `!`command`\` expressions execute and inject live output:
```markdown
## Context
<context>
Recent skills:
./skills/coder/SKILL.md
./skills/verifier/SKILL.md
./skills/critic/SKILL.md

Project files: 42

Git status:
M swarm_attack/agents/coder.py
A tests/test_new_feature.py
</context>
```

### Our Static Context:
```python
# coder.py _build_prompt()
completed_summaries_section = self._format_completed_summaries(completed_summaries)
module_context_section = self._format_module_registry(module_registry)
existing_section = self._format_existing_implementation(existing_implementation)

prompt = f"""{skill_prompt}

{project_instructions}
{completed_summaries_section}
{module_context_section}
{existing_section}
...
"""
```

**All context is pre-extracted** by orchestrator and baked into text. If orchestrator didn't think to include a file, coder can't access it.

---

## The Test/Implementation Mismatch Root Cause

### Scenario: Issue N+1 needs to import classes from Issue N

**Compound Engineering:**
1. Coder reads test file (sees `from lib.auth import User`)
2. Uses `Read("lib/auth.py")` to check if `User` exists
3. Sees actual class definition and API
4. Implements integration correctly

**Our Swarm:**
1. Coder reads test from prompt (sees `from lib.auth import User`)
2. Module registry says: `"lib/auth.py": ["User"] (issue #5)`
3. No actual code - just summary: "User model with validation"
4. Coder guesses API (maybe `User.validate()` when it's `User.is_valid()`)
5. Implementation compiles but wrong method name
6. Tests fail with AttributeError

---

## Why Their Prompts Stay Small

### Tool-Based Exploration (Compound):
- **Prompt**: 500 chars (skill definition)
- **Read calls**: 3-5 files × 2000 chars = 10,000 chars (loaded on-demand)
- **Total context**: ~10,500 chars
- **In-context tools**: Can call Read again if needed more files

### Pre-Baked Context (Swarm):
- **Prompt**: 25,000 chars (skill + spec + tests + code + summaries)
- **Read calls**: None (no tools)
- **Total context**: 25,000 chars (all upfront)
- **If missing context**: Agent is blind, can't recover

---

## The Allowed-Tools Mismatch

### Their Skill Files:
```yaml
---
name: coder
allowed-tools: Read,Glob,Bash,Write,Edit
---
```

✅ **Frontmatter matches reality**: Agent actually gets those tools

### Our Skill Files:
```yaml
---
name: coder
allowed-tools: Read,Glob,Bash,Write,Edit
---
```

❌ **Frontmatter is a lie**: We strip it and run with `allowed_tools=[]`

**The fix we applied:**
```python
# base.py load_skill_with_metadata()
content, metadata = self.load_skill_with_metadata("coder")
# Strip frontmatter to avoid confusing Claude
```

**Why we strip it:**
> "The skill file may contain YAML frontmatter with metadata like 'allowed-tools: Read,Glob,Bash,Write,Edit'. Since we run with allowed_tools=[] (no tools), this frontmatter can confuse Claude into attempting tool use, burning through max_turns."
> — coder.py line 195

**This is backwards.** We should give coder the tools, not strip the frontmatter.

---

## Workflow Comparison: Implementing an Issue

### Compound Engineering (Tool-Based):

```
1. Parse issue body
   ↓ [Bash: git status]
2. Check current branch state
   ↓ [Read: tests/test_feature.py]
3. Read test file
   ↓ [Glob: src/**/*.py]
4. Find similar implementations
   ↓ [Read: src/auth/signup.py]
5. Read pattern reference
   ↓ [Write: src/auth/login.py]
6. Create implementation
   ↓ [Bash: pytest tests/test_feature.py]
7. Run tests, see failures
   ↓ [Edit: src/auth/login.py]
8. Fix specific failure
   ↓ [Bash: pytest tests/test_feature.py]
9. Verify all tests pass
   ✓ DONE
```

**Turns used**: 8-12 (each tool call = 1 turn)
**Context size**: ~500 chars prompt + files read on-demand
**Failure recovery**: In-context iteration

### Our Swarm (Prompt-Based):

```
1. Orchestrator extracts all context
   ↓
2. Build giant prompt (spec + tests + summaries + code)
   ↓
3. LLM generates text output (no tools)
   ↓
4. Orchestrator parses # FILE: markers
   ↓
5. Orchestrator writes files
   ↓
6. Verifier agent runs pytest
   ↓ [IF FAILURES]
7. Orchestrator extracts failures
   ↓
8. Build NEW giant prompt with failure details
   ↓
9. LLM retries (still no tools)
   ↓
10. Orchestrator parses and writes again
   ✓ DONE (after N retries)
```

**Turns used**: 1-3 per attempt × retries = 3-9 total
**Context size**: 20,000+ chars per attempt
**Failure recovery**: Full agent re-invocation

---

## Solution Paths

### Option A: Give Coder Tools (Align with Compound Pattern)
```python
# coder.py
result = self.llm.run(
    prompt,
    allowed_tools=["Read", "Glob", "Bash", "Write", "Edit"],  # Enable tools
    max_turns=20,
)
```

**Pros:**
- Matches compound-engineering pattern
- Agents can explore codebase
- No context loss
- Smaller prompts

**Cons:**
- Need to validate tool outputs
- Can't parse text for file writes anymore (tools handle it)
- Different workflow

### Option B: Enhance Static Context (Keep No-Tools)
```python
# More aggressive context extraction
context = {
    "spec": spec_content,
    "tests": test_content,
    "issue": issue_body,
    "existing_code": self._read_all_integration_points(issue),  # NEW
    "git_status": subprocess.run(["git", "status", "--short"]),  # NEW
    "similar_files": self._find_similar_implementations(issue),  # NEW
}
```

**Pros:**
- Keep existing architecture
- More control over context
- Easier to debug

**Cons:**
- Still limited by what orchestrator thinks to include
- Prompt size grows even larger
- Token limit issues persist

### Option C: Hybrid (Best of Both)
```python
# Small prompt + targeted tools
result = self.llm.run(
    prompt,  # Just skill + issue + tests
    allowed_tools=["Read", "Glob"],  # Exploration only
    max_turns=20,
)
# Then parse output for file writes (keep our pattern)
```

**Pros:**
- Agents can explore for context
- Orchestrator still controls writes (validation, logging)
- Smaller prompts

**Cons:**
- Need to handle tool calls in output parsing
- Complexity of both patterns

---

## Recommendation

**Enable tools for Coder agent** (Option A or C).

**Why:**
1. Our current "massive prompt" approach is hitting token limits (20k+ chars)
2. We're compensating for blindness by injecting everything, causing bloat
3. Context handoff loses fidelity - tools eliminate handoff entirely
4. Their pattern is proven and simpler

**Implementation:**
```python
# coder.py line 1530
result = self.llm.run(
    prompt,  # Shrink this by 70% - remove code dumps
    allowed_tools=["Read", "Glob", "Bash"],  # Enable exploration
    max_turns=20,
)
```

**Remove from prompt:**
- Existing implementation code (coder can Read it)
- Module registry (coder can Glob for files)
- Large spec sections (coder can Read spec if needed)

**Keep in prompt:**
- Issue body (what to implement)
- Test path (where tests are)
- Integration requirements (what to preserve)

**Result:**
- Prompt size: 25,000 chars → 5,000 chars (80% reduction)
- Agent can explore codebase dynamically
- No more test/implementation mismatches (coder sees actual APIs)
- Matches proven compound-engineering pattern
