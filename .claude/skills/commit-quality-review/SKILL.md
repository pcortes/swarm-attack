# Commit Quality Review

> Review recent commits with a panel of expert engineering directors.

## Invocation

```bash
/review-commits
```

## Description

Runs a multi-agent review of recent commits, analyzing code changes through the lens of 5 expert engineering directors:

1. **Dr. Elena Vasquez** (Production Reliability) - Skeptical of fixes without production evidence
2. **Marcus Chen** (Test Coverage) - Skeptical of test mocks that don't match production APIs
3. **Dr. Aisha Patel** (Code Quality) - Skeptical of "complete" implementations that are partial
4. **James O'Brien** (Documentation) - Skeptical of docs that are session exhaust, not lasting reference
5. **Dr. Sarah Kim** (Architecture) - Skeptical of changes that break implicit contracts

Each expert reviews commits in their domain and provides findings with:
- Severity: LOW | MEDIUM | HIGH | CRITICAL
- Evidence: file:line references
- TDD fix plans for actionable issues

## Usage

```bash
# Review commits from last 24 hours
swarm-attack review-commits

# Review commits from last week
swarm-attack review-commits --since="1 week ago"

# Review specific branch
swarm-attack review-commits --branch=feature/xyz

# Strict mode (fail on medium+ issues)
swarm-attack review-commits --strict

# Output as XML
swarm-attack review-commits --output xml

# Save report to file
swarm-attack review-commits --save report.md
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--since` | "24 hours ago" | Time range for commits |
| `--branch` | current | Branch to review |
| `--output` | markdown | Format: markdown, xml, json |
| `--strict` | false | Fail on medium+ severity issues |
| `--save` | - | Save report to file path |

## Output

The report includes:

1. **Summary** - Overview of commits reviewed and verdicts
2. **Commit Reviews** - Per-commit findings with:
   - Score (0.0 - 1.0)
   - Verdict: LEAVE | FIX | REVERT
   - Findings with evidence
3. **TDD Fix Plans** - For actionable issues:
   - Red Phase: Failing test to write
   - Green Phase: Minimal fix steps
   - Refactor Phase: Cleanup suggestions

## Example Output

```markdown
# Commit Quality Review

**Generated:** 2025-12-31T12:00:00
**Branch:** main
**Overall Score:** 0.75

## Summary
3 commits reviewed, 1 OK, 2 need fixes

## Commit Reviews

### ⚠️ abc1234
**Message:** fix: handle edge case
**Score:** 0.70
**Verdict:** FIX

#### Findings
- 🟡 **MEDIUM** (Dr. Elena Vasquez)
  - Bug fix without production evidence
  - Evidence: `fix.py:45`

#### TDD Fix Plans
...
```

## Integration

This skill integrates with:
- **COO midday check-in** - Reviews commits since last checkpoint
- **COO daily digest** - Reviews all commits from past 24 hours
- **CI/CD pre-merge gate** - Optional strict mode for PR checks

## See Also

- `/status` - Check feature status
- `/approve` - Approve pending changes
