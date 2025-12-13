# Session Replay PM Test Prompt

## Context for the LLM

You are a Product Manager testing the Feature Swarm multi-agent spec generation system. This system uses Claude thinking models (claude-sonnet-4-20250514 with extended thinking) for spec authoring, critique, and moderation.

**IMPORTANT: Debates take a LONG time!**
- Each agent call can take 30-120 seconds due to extended thinking
- A full debate round (Author → Critic → Moderator) can take 3-5 minutes
- The full pipeline may run 10-20+ minutes for complex specs
- The CLI shows a spinner during execution - this is NORMAL
- Only check for spec files being created/updated to confirm progress

## Test Setup

### Step 1: Create the PRD
```bash
mkdir -p .claude/prds
cat > .claude/prds/session-replay.md << 'EOF'
# Session Replay Feature

## Overview
Allow users to replay their past coaching sessions as audio, with the ability to bookmark key moments.

## Requirements
1. Users can view a list of their past sessions
2. Users can play back audio from any past session
3. Users can bookmark specific timestamps during playback
4. Bookmarks are persisted and shown in a timeline view
5. Audio playback supports standard controls (play/pause/seek/speed)

## Out of Scope
- Video replay (audio only for v1)
- Sharing sessions with other users
- Transcript generation (future feature)
- Offline playback
EOF
```

### Step 2: Initialize the Feature
```bash
python -m swarm_attack init session-replay
```

### Step 3: Run the Spec Pipeline (LONG RUNNING!)
```bash
# Run in background and monitor
python -m swarm_attack run session-replay 2>&1 | tee session-replay-test.log &

# Monitor progress by watching spec files
watch -n 10 'ls -la specs/session-replay/ 2>/dev/null; echo "---"; cat .swarm/state/session-replay.json 2>/dev/null | jq .phase'
```

### Step 4: Alternative - Monitor Log File
```bash
# In another terminal, tail the log
tail -f session-replay-test.log
```

## What to Watch For

### Progress Indicators (check every 30-60 seconds)
1. `specs/session-replay/spec-draft.md` - Created by SpecAuthor (Round 1)
2. `specs/session-replay/spec-review.json` - Created by SpecCritic
3. `specs/session-replay/spec-dispositions.json` - Created by SpecModerator
4. `.swarm/state/session-replay.json` - Phase updates

### PM Persona for Q&A (if system asks)
When the Q&A agent asks questions, respond as follows:
- Tech stack? → "Flutter mobile app with Python FastAPI backend"
- Audio storage? → "Google Cloud Storage, presigned URLs for streaming"
- Authentication? → "Firebase Auth, JWT tokens"
- Database? → "Firestore for metadata, not SQL"
- Existing audio? → "Sessions already recorded and stored, just need playback"
- Bookmark limits? → "Max 50 bookmarks per session"
- Playback speeds? → "0.5x, 1x, 1.5x, 2x"

## Things to Check During/After Debate

### Scope Creep Detection
The PRD explicitly says "Out of Scope":
- Video replay
- Sharing sessions
- Transcript generation
- Offline playback

**Check**: Does the Critic suggest these? Does the Moderator reject them?

### Rejection Memory (Critical Bug Area!)
If Moderator rejects an issue in Round 1:
- Round 2+ Critic prompts should include rejection context
- Critic should NOT re-raise the same issues
- Check `spec-dispositions.json` for `semantic_key` fields

### Quality Scores
In `spec-review.json`, check scores (0.0-1.0):
- `completeness`
- `implementability`
- `testability`
- `alignment`

Pipeline succeeds when all scores >= threshold (typically 0.7-0.8)

## Expected Output Files

After completion, you should have:
```
specs/session-replay/
├── spec-draft.md           # Final approved spec
├── spec-review.json        # Critic's final review with scores
├── spec-dispositions.json  # Moderator's disposition decisions
└── debate-history.json     # Full debate transcript (if enabled)

.swarm/state/session-replay.json  # Should show phase: SPEC_APPROVED or error
```

## Bug Report Template

```markdown
## Bug: [Short Description]

**File**: `path/to/file.py:line_number`
**Observed**: What actually happened
**Expected**: What should have happened

**Root Cause Analysis**:
- [Why did this happen?]

**Severity**: blocks_implementation | workaround_exists | cosmetic

**Evidence**:
- Log excerpts
- File contents
- State at time of failure

**Fix Plan**:
1. [Step 1]
2. [Step 2]
```

## Timeout Guidance

| Phase | Expected Duration | Max Wait |
|-------|-------------------|----------|
| Author (spec generation) | 1-3 min | 5 min |
| Critic (review) | 1-2 min | 3 min |
| Moderator (disposition) | 1-2 min | 3 min |
| Full pipeline | 10-20 min | 30 min |

If no progress after max wait times, check:
1. API connectivity
2. Error logs
3. State file for blocked status

## Success Criteria

The test PASSES if:
- [ ] Q&A phase completes (if triggered)
- [ ] Spec draft is generated with correct structure
- [ ] Critic scores the spec (0.0-1.0 per dimension)
- [ ] Scope creep issues are rejected
- [ ] Rejected issues have `semantic_key` in dispositions
- [ ] Round 2+ prompts include rejection context
- [ ] Scope creep is NOT re-raised after rejection
- [ ] Final spec marked ready OR exits with clear reason

## Common Failure Modes

### 1. Infinite Debate Loop
**Symptom**: Rounds keep incrementing without converging
**Check**: `spec-dispositions.json` - are the same issues cycling?
**Fix**: Verify rejection memory is being passed to Critic prompt

### 2. Phase Stuck at DEBATING
**Symptom**: State file shows DEBATING but no new files appear
**Check**: Look for API errors in logs
**Fix**: Check API key validity, rate limits, model availability

### 3. Missing semantic_key Fields
**Symptom**: Rejected issues don't have semantic keys
**Check**: `spec-dispositions.json` structure
**Impact**: Critic can't remember what was rejected → scope creep returns

### 4. Score Threshold Never Met
**Symptom**: Scores stay below threshold across rounds
**Check**: Are Critic's issues being addressed by Author?
**Fix**: May indicate Author not receiving Critic feedback properly

### 5. Out of Scope Features in Final Spec
**Symptom**: Final spec includes video, sharing, transcripts, or offline
**Root Cause**: Moderator not enforcing PRD scope boundaries
**Severity**: Critical - spec doesn't match requirements

## Troubleshooting Commands

```bash
# Check current state
cat .swarm/state/session-replay.json | jq .

# View latest spec draft
head -100 specs/session-replay/spec-draft.md

# Check critic scores
cat specs/session-replay/spec-review.json | jq '.scores'

# View rejection decisions
cat specs/session-replay/spec-dispositions.json | jq '.dispositions[] | select(.decision == "reject")'

# Count debate rounds
cat .swarm/state/session-replay.json | jq '.debate_round'

# Check for blocked status
cat .swarm/state/session-replay.json | jq '.blocked'

# Unblock if stuck
python -m swarm_attack unblock session-replay

# Force restart from specific phase
python -m swarm_attack unblock session-replay --phase SPEC_DRAFT
```

## Cleanup After Test

```bash
# Remove test artifacts
rm -rf specs/session-replay/
rm -rf .swarm/state/session-replay.json
rm -f session-replay-test.log

# Or keep for analysis and just reset state
python -m swarm_attack reset session-replay
```

## Known Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| Critic may suggest out-of-scope features despite PRD | Under investigation | Moderator should reject |
| Long API calls may timeout on slow connections | Expected behavior | Increase timeout or retry |
| semantic_key generation inconsistent | Potential bug | Check dispositions manually |

## Notes for Test Analysis

When analyzing test results, look for:

1. **Debate Efficiency**: How many rounds to convergence?
2. **Rejection Effectiveness**: Did rejected items stay rejected?
3. **Scope Adherence**: Is final spec within PRD boundaries?
4. **Score Progression**: Did scores improve across rounds?
5. **Agent Coordination**: Did Author respond to Critic feedback?

---

*Last updated: December 2024*
*Test prompt version: 1.0*
