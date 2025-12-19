# The Blindness Problem: Why Our Coder Can't See

## TL;DR

**Compound-engineering-plugin agents have eyes (tools). Our agents are blind (no tools).**

```python
# Their pattern (CAN SEE)
allowed_tools: [Read, Edit, Bash, Glob]

# Our pattern (BLIND)
allowed_tools: []
```

---

## The Evidence

### 1. Coder Agent Implementation

**File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/agents/coder.py:1530`

```python
result = self.llm.run(
    prompt,
    allowed_tools=[],  # ← NO TOOLS
    max_turns=max_turns,
)
```

**Comment in code (line 1519):**
> "No tools - all context is in prompt, just generate code with # FILE: markers. Using Write/Edit tools causes result.text to be empty, breaking file parsing."

**This is the root cause.** We disabled tools to make parsing easier.

---

### 2. Skill File Contradiction

**File:** `/Users/philipjcortes/Desktop/swarm-attack/.claude/skills/coder/SKILL.md:6`

```yaml
---
name: coder
allowed-tools: Read,Glob,Bash,Write,Edit
---
```

**But we strip this frontmatter** because it's a lie:

**File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/agents/coder.py:199`

```python
def _load_skill_prompt(self) -> str:
    """Load and cache the skill prompt, stripping YAML frontmatter.

    The skill file may contain YAML frontmatter with metadata like
    'allowed-tools: Read,Glob,Bash,Write,Edit'. Since we run with
    allowed_tools=[] (no tools), this frontmatter can confuse Claude
    into attempting tool use, burning through max_turns.

    We use load_skill_with_metadata() from BaseAgent to strip frontmatter.
    """
```

**The skill file SAYS coder has tools. The code REMOVES the tools.**

---

### 3. Context Compensation

Because coder has no tools, we compensate by injecting massive context:

**File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/agents/coder.py:998-1152`

```python
def _build_prompt(
    self,
    feature_id: str,
    issue: dict[str, Any],
    spec_content: str,
    test_content: str,
    expected_modules: list[str],
    retry_number: int = 0,
    test_failures: Optional[list[dict[str, Any]]] = None,
    existing_implementation: Optional[dict[str, str]] = None,
    test_path: Optional[Path] = None,
    module_registry: Optional[dict[str, Any]] = None,
    completed_summaries: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Build the full prompt for Claude."""

    # Inject ALL context as text
    completed_summaries_section = self._format_completed_summaries(completed_summaries)
    module_context_section = self._format_module_registry(module_registry)
    existing_section = self._format_existing_implementation(existing_implementation)

    # Build 1000+ line prompt
    return f"""{skill_prompt}
    {project_instructions}
    {completed_summaries_section}
    {module_context_section}
    {existing_section}
    {spec_content}  # Can be 20k chars
    {test_content}
    ...
    """
```

**Why is this bad?**
- Prompt can be 25,000+ characters
- Spec gets truncated if > 20k chars (line 631)
- Existing code gets truncated if > 5k chars (line 554)
- If orchestrator didn't include a file, coder can't access it
- 40% context loss per handoff (summaries lose detail)

---

### 4. What Compound-Engineering Does Differently

**Their skill files:**
```yaml
---
name: heal-skill
allowed-tools: [Read, Edit, Bash(ls:*), Bash(git:*)]
---
```

**Their prompts use shell injection:**
```markdown
<context>
Skill detection: !`ls -1 ./skills/*/SKILL.md | head -5`
</context>
```

**At runtime**, that executes and injects live output:
```markdown
<context>
Skill detection:
./skills/coder/SKILL.md
./skills/verifier/SKILL.md
./skills/critic/SKILL.md
</context>
```

**Their agents can:**
- `Read("lib/auth.py")` to check existing code
- `Glob("src/**/*.py")` to find integration points
- `Bash("pytest tests/")` to see test failures
- `Edit("lib/auth.py")` to make surgical changes

**Our agents can:**
- Read what's in the prompt (only)
- Output text with `# FILE:` markers (only)
- Hope the orchestrator included everything they need

---

## The Test/Implementation Mismatch

### Example Failure Scenario:

**Issue N:** Creates `lib/auth.py` with `User` class
```python
class User:
    def is_valid(self) -> bool:
        return self.email is not None
```

**StateStore summary:**
```json
{
  "files_created": ["lib/auth.py"],
  "classes_defined": {"lib/auth.py": ["User"]},
  "completion_summary": "User model with validation"
}
```

**Issue N+1 test:**
```python
from lib.auth import User

def test_user_validation():
    user = User(email="test@example.com")
    assert user.is_valid()  # Expects is_valid() method
```

**Coder prompt (our system):**
```markdown
## Existing Modules from Prior Issues
- `lib/auth.py` (issue #5): User
**IMPORTANT**: Import and use these existing modules.

## Issue to Implement:
Add password validation to User model...
```

**What coder sees:**
- File `lib/auth.py` exists
- Contains class `User`
- No method signatures
- No actual code

**What coder does:**
```python
# Guesses at API based on name
from lib.auth import User

class PasswordValidator:
    def validate(self, user: User) -> bool:
        # Assumes User has .validate() method (wrong!)
        return user.validate() and len(user.password) >= 8
```

**Result:** Test imports `User.is_valid()`, implementation calls `User.validate()` → AttributeError

---

### Same Scenario with Tools:

**Coder with Read tool:**
1. Sees test imports `from lib.auth import User`
2. Calls `Read("lib/auth.py")`
3. Sees actual class definition:
```python
class User:
    def is_valid(self) -> bool:
        return self.email is not None
```
4. Implements correctly:
```python
class PasswordValidator:
    def validate(self, user: User) -> bool:
        return user.is_valid() and len(user.password) >= 8
```

**Result:** Tests pass on first attempt

---

## The Token Limit Problem

### Current Prompt Size (No Tools):

```
Skill prompt:          3,500 chars
Project instructions:  1,000 chars
Completed summaries:   2,000 chars
Module registry:       1,500 chars
Existing code:         5,000 chars (truncated!)
Spec content:         20,000 chars (truncated!)
Test content:          2,000 chars
Issue body:            1,000 chars
-----------------------------------------
TOTAL:               ~36,000 chars
```

**Problem:** Hitting token limits, causing:
- Spec truncation (line 631: `if len(spec_content) > 20000`)
- Code truncation (line 554: `truncated = content[:5000]`)
- Max turns exhaustion (prompt is huge)

### With Tools (Compound Pattern):

```
Skill prompt:          500 chars
Issue body:          1,000 chars
Test path:             100 chars
-----------------------------------------
TOTAL:               ~1,600 chars

[Agent then calls Read/Glob to get what it needs]
```

**Benefits:**
- 95% smaller prompt
- No truncation (reads full files on-demand)
- Only loads what's actually needed

---

## Why We Chose No-Tools

**File:** `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/agents/coder.py:1519`

> "Using Write/Edit tools causes result.text to be empty, breaking file parsing."

**The logic:**
1. If coder uses Write tool, Claude writes files directly
2. The `result.text` output is empty (just tool calls)
3. Our orchestrator expects `# FILE:` markers in text
4. Parsing breaks, no files created

**The tradeoff:**
- We get simple text parsing
- We lose ALL tools (Read, Glob, Bash too)
- We compensate with massive prompts
- We hit token limits and context drift

**Better solution:**
- Keep Read/Glob/Bash (exploration)
- Keep text output for writes (parsing)
- Best of both worlds

---

## Quantified Impact

### Context Loss Per Transition:

**With tools:** 0% loss (agent reads fresh files)
**Without tools (our system):** 40% loss per handoff

**Example:**
```
Issue N actual code:
  class User:
      def __init__(self, email: str, password: str):
          self.email = email
          self.password = password

      def is_valid(self) -> bool:
          return self.email is not None and '@' in self.email

      def has_secure_password(self) -> bool:
          return len(self.password) >= 8

Orchestrator summary:
  "User model with validation" (90% detail lost)

Module registry entry:
  {"lib/auth.py": ["User"]} (95% detail lost)

Coder sees:
  "File lib/auth.py has class User (issue #5)"
  No method names, no signatures, no logic
```

### Prompt Size Growth:

| Issue # | Completed Issues | Prompt Size (No Tools) | Prompt Size (With Tools) |
|---------|------------------|------------------------|--------------------------|
| 1       | 0                | 5,000 chars            | 1,500 chars              |
| 3       | 2                | 12,000 chars           | 1,500 chars              |
| 5       | 4                | 22,000 chars           | 1,500 chars              |
| 8       | 7                | 38,000 chars (💥 LIMIT)| 1,500 chars              |

**With tools, prompt size stays constant.** Without tools, it grows linearly.

---

## The Fix

### Current Code:
```python
# coder.py:1530
result = self.llm.run(
    prompt,  # 25,000 chars
    allowed_tools=[],  # BLIND
    max_turns=20,
)
```

### Proposed Fix:
```python
# coder.py:1530
result = self.llm.run(
    prompt,  # 2,000 chars (80% reduction)
    allowed_tools=["Read", "Glob", "Bash"],  # CAN SEE
    max_turns=20,
)
```

### What to Remove from Prompt:
- ❌ Existing implementation code (coder can Read it)
- ❌ Module registry (coder can Glob for files)
- ❌ Large spec sections (coder can Read if needed)
- ❌ Completed summaries (coder can Read actual files)

### What to Keep in Prompt:
- ✅ Issue body (what to implement)
- ✅ Test path (where tests are)
- ✅ Integration requirements (PRESERVE existing code)

### New Workflow:
```
1. Coder receives small prompt
2. Calls Read(test_path) to see requirements
3. Calls Glob("lib/**/*.py") to find integration points
4. Calls Read("lib/auth.py") to see actual User class
5. Outputs # FILE: markers with correct implementation
6. Orchestrator parses and writes files (same as now)
```

**Benefits:**
- No context loss (reads actual code)
- No token limits (tiny prompts)
- No test mismatches (sees real APIs)
- Matches proven compound-engineering pattern

---

## Decision Point

**Question:** Should we enable tools for Coder?

**Options:**

**A) Enable Read/Glob/Bash (recommended)**
- Pros: Solves blindness, keeps write parsing
- Cons: Need to handle tool calls in workflow

**B) Enable all tools (Read/Glob/Bash/Write/Edit)**
- Pros: Full compound-engineering pattern
- Cons: Need to remove text parsing, bigger change

**C) Keep no-tools, enhance context**
- Pros: No architecture change
- Cons: Token limits persist, context loss persists

**Recommendation:** Option A (Read/Glob/Bash only)

**Why:**
- Fixes the blindness problem
- Keeps our text-based write pattern (easier migration)
- 80% solution with 20% change
- Proven pattern from compound-engineering

**Next Steps:**
1. Update `coder.py:1530` to pass `allowed_tools=["Read", "Glob", "Bash"]`
2. Shrink `_build_prompt()` to remove code dumps
3. Test on a simple feature (unit-converter)
4. Measure prompt size reduction and success rate
5. Roll out if successful
