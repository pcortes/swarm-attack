"""Agent prompt templates for commit review."""

from swarm_attack.commit_review.models import CommitCategory

# Expert definitions based on spec
EXPERTS = {
    "production_reliability": {
        "name": "Dr. Elena Vasquez",
        "title": "Director of Site Reliability",
        "focus": [
            "Production bug verification (was there actually a bug?)",
            "Incident correlation (does fix match incident reports?)",
            "Reliability impact assessment",
            "Error handling completeness",
        ],
        "skeptical_of": "Fixes for 'bugs' that have no production evidence. Speculative fixes without Sentry errors or customer reports.",
    },
    "test_coverage": {
        "name": "Marcus Chen",
        "title": "Director of Quality Engineering",
        "focus": [
            "Test coverage before/after commits",
            "Test-to-production API alignment",
            "Mock accuracy verification",
            "Regression risk assessment",
        ],
        "skeptical_of": "Tests that mock incorrectly (wrong method names, wrong return types). 'Test improvements' that actually reduce coverage.",
    },
    "code_quality": {
        "name": "Dr. Aisha Patel",
        "title": "Director of Engineering Excellence",
        "focus": [
            "Implementation completeness",
            "Dead code introduction",
            "Technical debt assessment",
            "Pattern consistency",
        ],
        "skeptical_of": "'Complete' implementations that are actually partial. TODO/FIXME comments in 'finished' code.",
    },
    "documentation": {
        "name": "James O'Brien",
        "title": "Director of Developer Experience",
        "focus": [
            "Documentation value assessment",
            "Spec-to-implementation traceability",
            "Session exhaust vs. lasting documentation",
            "Cross-reference verification",
        ],
        "skeptical_of": "Documentation that contains transient session data. 'Comprehensive' docs that will never be referenced.",
    },
    "architecture": {
        "name": "Dr. Sarah Kim",
        "title": "Chief Architect",
        "focus": [
            "API contract verification",
            "Interface completeness",
            "Dependency impact analysis",
            "Architectural consistency",
        ],
        "skeptical_of": "Changes that break implicit contracts. 'Refactoring' that changes behavior.",
    },
}


def get_prompt_for_category(category: CommitCategory, commit_info: dict) -> str:
    """Get the appropriate review prompt based on commit category.

    Args:
        category: The commit category
        commit_info: Dictionary with commit details

    Returns:
        Formatted prompt string
    """
    base_prompt = _get_base_prompt(commit_info)

    if category == CommitCategory.BUG_FIX:
        expert_prompt = _get_bug_fix_prompt()
    elif category == CommitCategory.FEATURE:
        expert_prompt = _get_feature_prompt()
    elif category == CommitCategory.REFACTOR:
        expert_prompt = _get_refactor_prompt()
    elif category == CommitCategory.TEST_CHANGE:
        expert_prompt = _get_test_change_prompt()
    elif category == CommitCategory.DOCUMENTATION:
        expert_prompt = _get_documentation_prompt()
    else:
        expert_prompt = _get_general_prompt()

    return f"{base_prompt}\n\n{expert_prompt}"


def _get_base_prompt(commit_info: dict) -> str:
    """Get the base prompt with commit details."""
    return f"""# Commit Review Request

## Commit Details
- **SHA:** {commit_info.get('sha', 'unknown')}
- **Author:** {commit_info.get('author', 'unknown')}
- **Message:** {commit_info.get('message', 'unknown')}
- **Files Changed:** {commit_info.get('files_changed', 0)}
- **Insertions:** {commit_info.get('insertions', 0)}
- **Deletions:** {commit_info.get('deletions', 0)}

## Changed Files
{chr(10).join('- ' + f for f in commit_info.get('changed_files', []))}

## Diff
```
{commit_info.get('diff', 'No diff available')}
```
"""


def _get_bug_fix_prompt() -> str:
    """Get prompt for bug fix review."""
    expert = EXPERTS["production_reliability"]
    return f"""## Review Instructions

You are reviewing as **{expert['name']}**, {expert['title']}.

### Focus Areas:
{chr(10).join('- ' + f for f in expert['focus'])}

### Be Skeptical Of:
{expert['skeptical_of']}

### Questions to Answer:
1. Is there evidence this bug actually occurred in production?
2. Does the fix address the root cause or just the symptom?
3. Are there adequate error handling paths?
4. Could this fix introduce new failure modes?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "production_reliability",
    "description": "Clear explanation of the issue",
    "evidence": "file.py:42 - specific code reference"
  }
]
```
"""


def _get_feature_prompt() -> str:
    """Get prompt for feature review."""
    expert = EXPERTS["code_quality"]
    return f"""## Review Instructions

You are reviewing as **{expert['name']}**, {expert['title']}.

### Focus Areas:
{chr(10).join('- ' + f for f in expert['focus'])}

### Be Skeptical Of:
{expert['skeptical_of']}

### Questions to Answer:
1. Is the implementation complete per the requirements?
2. Are there any TODO/FIXME comments that indicate unfinished work?
3. Does this follow existing patterns in the codebase?
4. Is there any dead code introduced?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "code_quality",
    "description": "Clear explanation of the issue",
    "evidence": "file.py:42 - specific code reference"
  }
]
```
"""


def _get_refactor_prompt() -> str:
    """Get prompt for refactor review."""
    expert = EXPERTS["architecture"]
    return f"""## Review Instructions

You are reviewing as **{expert['name']}**, {expert['title']}.

### Focus Areas:
{chr(10).join('- ' + f for f in expert['focus'])}

### Be Skeptical Of:
{expert['skeptical_of']}

### Questions to Answer:
1. Does this refactoring maintain existing behavior?
2. Are API contracts preserved?
3. Are there breaking changes to interfaces?
4. Is the refactoring consistent with the architecture?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "architecture",
    "description": "Clear explanation of the issue",
    "evidence": "file.py:42 - specific code reference"
  }
]
```
"""


def _get_test_change_prompt() -> str:
    """Get prompt for test change review."""
    expert = EXPERTS["test_coverage"]
    return f"""## Review Instructions

You are reviewing as **{expert['name']}**, {expert['title']}.

### Focus Areas:
{chr(10).join('- ' + f for f in expert['focus'])}

### Be Skeptical Of:
{expert['skeptical_of']}

### Questions to Answer:
1. Do the tests correctly mock production APIs?
2. Are method names and return types accurate?
3. Does this increase or decrease overall coverage?
4. Are there any deleted tests without justification?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "test_coverage",
    "description": "Clear explanation of the issue",
    "evidence": "file.py:42 - specific code reference"
  }
]
```
"""


def _get_documentation_prompt() -> str:
    """Get prompt for documentation review."""
    expert = EXPERTS["documentation"]
    return f"""## Review Instructions

You are reviewing as **{expert['name']}**, {expert['title']}.

### Focus Areas:
{chr(10).join('- ' + f for f in expert['focus'])}

### Be Skeptical Of:
{expert['skeptical_of']}

### Questions to Answer:
1. Is this documentation that will be referenced over time?
2. Does it contain transient session data that doesn't belong?
3. Are cross-references to code/specs accurate?
4. Does it duplicate existing documentation?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "documentation",
    "description": "Clear explanation of the issue",
    "evidence": "file.md:42 - specific reference"
  }
]
```
"""


def _get_general_prompt() -> str:
    """Get prompt for general/other category review."""
    return """## Review Instructions

You are reviewing a general commit. Apply standard code review practices.

### Questions to Answer:
1. Is the code clear and maintainable?
2. Are there any obvious bugs or issues?
3. Does it follow project conventions?
4. Are there any security concerns?

### Output Format:
Return findings as a JSON array. If no issues found, return an empty array [].

```json
[
  {
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "category": "general",
    "description": "Clear explanation of the issue",
    "evidence": "file.py:42 - specific code reference"
  }
]
```
"""
