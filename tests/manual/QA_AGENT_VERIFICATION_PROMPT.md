# QA Agent Manual Verification Prompt

> **MAINTENANCE NOTE**: This prompt should be reviewed and updated whenever the QA Agent's
> API surface, models, or behavior changes. Keep in sync with `swarm_attack/qa/models.py`
> and `swarm_attack/qa/agents/`. Last verified against spec sections 10.2 and 10.5.

---

## Instructions for Claude

You are a QA verification specialist. Your job is to **manually test the QA Agent system end-to-end** by:
1. Invoking real CLI commands
2. Making real HTTP requests
3. Inspecting actual JSON outputs
4. Verifying data formats match what downstream consumers expect

**DO NOT just run automated test suites.** This is manual integration testing.

---

## Prerequisites

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
```

Verify swarm-attack CLI is available:
```bash
swarm-attack --help
```

---

## Step 1: Start a Test API Server

First, spin up a simple test API to test against:

```bash
# Create a minimal test server
python -c "
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

@app.get('/health')
def health():
    return {'status': 'healthy', 'version': '1.0.0'}

@app.get('/api/users')
def list_users():
    return {'users': [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]}

@app.get('/api/users/{user_id}')
def get_user(user_id: int):
    if user_id == 999:
        raise HTTPException(status_code=404, detail='User not found')
    return {'id': user_id, 'name': 'Test User'}

@app.post('/api/users')
def create_user(user: dict):
    return {'id': 3, 'name': user.get('name', 'New User')}

@app.get('/api/protected')
def protected():
    # Simulates auth-required endpoint
    raise HTTPException(status_code=401, detail='Unauthorized')

@app.get('/api/error')
def error():
    raise HTTPException(status_code=500, detail='Internal server error')

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8765)
" &
TEST_SERVER_PID=$!
sleep 2
```

Verify server is running:
```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

**Expected**: `{"status": "healthy", "version": "1.0.0"}`

---

## Step 2: Test CLI Commands - `qa health`

```bash
swarm-attack qa health --base-url http://127.0.0.1:8765
```

**Verify**:
- [ ] Command completes without crash
- [ ] Shows session ID in output
- [ ] Shows test count (tests run/passed/failed)
- [ ] Shows health status (HEALTHY or UNHEALTHY)

Now get the JSON output:
```bash
swarm-attack qa report --json | python -m json.tool
```

**Verify the JSON structure**:
- [ ] Has `sessions` array
- [ ] Each session has `session_id`, `status`, `trigger`, `depth`

---

## Step 3: Test CLI Commands - `qa test`

Test a specific endpoint:
```bash
swarm-attack qa test "/api/users" --base-url http://127.0.0.1:8765 --depth shallow
```

**Verify**:
- [ ] Command completes
- [ ] Shows target being tested
- [ ] Shows depth level
- [ ] Shows recommendation (PASS/WARN/BLOCK)

Test with standard depth:
```bash
swarm-attack qa test "/api/users" --base-url http://127.0.0.1:8765 --depth standard
```

**Verify**:
- [ ] More tests run compared to shallow
- [ ] Contract validation attempted

---

## Step 4: Test Session Persistence and Retrieval

List sessions:
```bash
swarm-attack qa report
```

**Verify**:
- [ ] Shows table of recent sessions
- [ ] Session IDs match format `qa-YYYYMMDD-HHMMSS`

Get specific session details:
```bash
# Replace with actual session ID from above
SESSION_ID=$(swarm-attack qa report --json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(d['sessions'][0] if d.get('sessions') else '')")
echo "Session ID: $SESSION_ID"
swarm-attack qa report "$SESSION_ID" --json | python -m json.tool
```

**Verify session JSON structure** (this is what downstream consumers need):
```json
{
  "session_id": "qa-20241227-123456",
  "trigger": "user_command",
  "depth": "shallow|standard|deep",
  "status": "completed|failed|partial",
  "context": {
    "feature_id": null,
    "issue_number": null,
    "target_files": [],
    "target_endpoints": [{"method": "GET", "path": "/api/users", "auth_required": false}],
    "base_url": "http://127.0.0.1:8765"
  },
  "result": {
    "tests_run": 5,
    "tests_passed": 4,
    "tests_failed": 1,
    "findings": [...],
    "recommendation": "pass|warn|block"
  },
  "created_at": "2024-12-27T12:34:56Z",
  "started_at": "2024-12-27T12:34:56Z",
  "completed_at": "2024-12-27T12:34:58Z"
}
```

**Check required fields for verifier hook**:
- [ ] `session_id` is string, non-empty
- [ ] `status` is one of: pending, running, completed, partial, blocked, failed
- [ ] `result.recommendation` is one of: pass, warn, block
- [ ] `result.findings` is array (can be empty)
- [ ] `context.target_endpoints` is array of endpoint objects

---

## Step 5: Test Finding Generation

Test an endpoint that should generate findings:
```bash
swarm-attack qa test "/api/error" --base-url http://127.0.0.1:8765 --depth standard
```

**Verify**:
- [ ] Command detects 500 error
- [ ] Shows findings in output

Get findings via CLI:
```bash
swarm-attack qa bugs
```

**Verify findings JSON structure** (needed by bug pipeline):
```bash
swarm-attack qa report "$SESSION_ID" --json | python -c "
import sys, json
data = json.load(sys.stdin)
if data.get('result') and data['result'].get('findings'):
    finding = data['result']['findings'][0]
    required = ['finding_id', 'severity', 'category', 'endpoint', 'test_type',
                'title', 'description', 'expected', 'actual', 'evidence', 'recommendation']
    missing = [k for k in required if k not in finding]
    if missing:
        print(f'FAIL: Missing fields: {missing}')
    else:
        print('PASS: All required finding fields present')
        print(json.dumps(finding, indent=2))
else:
    print('No findings to verify')
"
```

**Expected QAFinding structure**:
```json
{
  "finding_id": "BEH-001-abc123",
  "severity": "critical|moderate|minor",
  "category": "behavioral|contract|regression|auth",
  "endpoint": "GET /api/error",
  "test_type": "happy_path|error_handling|auth",
  "title": "Server returned 500 error",
  "description": "The endpoint returned an unexpected 500 status code",
  "expected": {"status": 200},
  "actual": {"status": 500, "body": "..."},
  "evidence": {
    "request": "curl -X GET http://...",
    "response": "{'detail': 'Internal server error'}"
  },
  "recommendation": "Investigate server logs for root cause"
}
```

---

## Step 6: Test Auth Edge Cases

Test unauthorized endpoint:
```bash
curl -s http://127.0.0.1:8765/api/protected
# Should return 401

swarm-attack qa test "/api/protected" --base-url http://127.0.0.1:8765 --depth standard
```

**Verify**:
- [ ] QA detects 401 response
- [ ] Finding generated for auth failure (if unexpected)
- [ ] OR test passes if 401 was expected

---

## Step 7: Verify Data Flow - Orchestrator to Agents

Manually invoke the orchestrator Python API and check outputs:

```bash
python -c "
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.models import QADepth, QATrigger, QAEndpoint
from swarm_attack.cli.common import get_config_or_default

config = get_config_or_default()
orch = QAOrchestrator(config)

# Run a test
session = orch.test(
    target='/api/users',
    depth=QADepth.STANDARD,
    trigger=QATrigger.USER_COMMAND,
    base_url='http://127.0.0.1:8765',
    timeout=30
)

print('=== Session Object ===')
print(f'ID: {session.session_id}')
print(f'Status: {session.status}')
print(f'Trigger: {session.trigger}')
print(f'Depth: {session.depth}')

print('\n=== Context ===')
ctx = session.context
print(f'Base URL: {ctx.base_url}')
print(f'Endpoints: {[(e.method, e.path) for e in ctx.target_endpoints]}')

print('\n=== Result ===')
if session.result:
    r = session.result
    print(f'Tests: {r.tests_run} run, {r.tests_passed} passed, {r.tests_failed} failed')
    print(f'Recommendation: {r.recommendation}')
    print(f'Findings: {len(r.findings)}')
    for f in r.findings[:3]:
        print(f'  - [{f.severity}] {f.title}')
else:
    print('No result (session may have failed)')

print('\n=== Serialization Check ===')
import json
d = session.to_dict()
print('to_dict() keys:', list(d.keys()))
# Verify round-trip
from swarm_attack.qa.models import QASession
restored = QASession.from_dict(d)
print(f'Round-trip OK: {restored.session_id == session.session_id}')
"
```

**Verify**:
- [ ] Session object created successfully
- [ ] Context populated with base_url and endpoints
- [ ] Result has tests_run, tests_passed, findings
- [ ] to_dict() produces valid JSON
- [ ] from_dict() round-trips correctly

---

## Step 8: Verify Hook Integration Format

The verifier hook expects specific data. Verify the format:

```bash
python -c "
from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook, VerifierQAHookResult
from swarm_attack.cli.common import get_config_or_default

config = get_config_or_default()
hook = VerifierQAHook(config)

# Check what the hook produces
print('VerifierQAHookResult fields:')
import inspect
sig = inspect.signature(VerifierQAHookResult.__init__)
for param in sig.parameters:
    if param != 'self':
        print(f'  - {param}')

# Verify hook has required methods
print('\nHook methods:')
print(f'  should_run: {hasattr(hook, \"should_run\")}')
print(f'  run: {hasattr(hook, \"run\")}')
"
```

**Verify**:
- [ ] VerifierQAHookResult has: session_id, recommendation, findings, should_block
- [ ] Hook has should_run() and run() methods

---

## Step 9: Test validate_issue Flow

This is the main integration point with verifier:

```bash
python -c "
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.models import QADepth
from swarm_attack.cli.common import get_config_or_default

config = get_config_or_default()
orch = QAOrchestrator(config)

# Simulate validating an issue
session = orch.validate_issue(
    feature_id='test-feature',
    issue_number=123,
    depth=QADepth.STANDARD
)

print('=== validate_issue Result ===')
print(f'Session: {session.session_id}')
print(f'Status: {session.status}')
print(f'Feature ID in context: {session.context.feature_id}')
print(f'Issue number in context: {session.context.issue_number}')

# This is what the verifier hook will receive
if session.result:
    print(f'Recommendation: {session.result.recommendation.value}')
    print(f'Should block: {session.result.recommendation.value == \"block\"}')
"
```

**Verify**:
- [ ] feature_id stored in context
- [ ] issue_number stored in context
- [ ] Result has recommendation
- [ ] Recommendation is one of: pass, warn, block

---

## Step 10: Cleanup

```bash
# Kill test server
kill $TEST_SERVER_PID 2>/dev/null || true

# Clean up test sessions (optional)
rm -rf .swarm/qa/qa-* 2>/dev/null || true
```

---

## Verification Checklist

After completing all steps, verify:

### CLI Commands Work
- [ ] `swarm-attack qa health` - runs and shows results
- [ ] `swarm-attack qa test <target>` - tests endpoints
- [ ] `swarm-attack qa report` - lists sessions
- [ ] `swarm-attack qa report <session-id> --json` - shows session JSON
- [ ] `swarm-attack qa bugs` - lists findings

### JSON Formats Are Correct
- [ ] QASession.to_dict() includes all required fields
- [ ] QAFinding has: finding_id, severity, category, endpoint, test_type, title, description, expected, actual, evidence, recommendation
- [ ] QAResult has: tests_run, tests_passed, tests_failed, findings, recommendation
- [ ] QAContext has: target_endpoints as list of {method, path, auth_required}

### Data Flows Correctly
- [ ] Orchestrator creates session with unique ID
- [ ] Context populated from test target
- [ ] Agents produce findings in correct format
- [ ] Results aggregate from all agents
- [ ] Sessions persist to disk and reload correctly

### Integration Points Work
- [ ] VerifierQAHook can be instantiated
- [ ] validate_issue stores feature_id and issue_number
- [ ] Recommendation values match expected enum (pass/warn/block)

---

## If Issues Found

Create bug document at: `tests/manual/findings/YYYYMMDD_HHMMSS_qa_verification.md`

Include:
1. What command/operation failed
2. Expected vs actual output
3. Exact error message or incorrect data
4. Steps to reproduce

---

## Historical Notes

| Date | Verifier | Result | Notes |
|------|----------|--------|-------|
| 2024-12-27 | Claude | PASS | Initial verification after implementing 10.2/10.5 tests |

---

*This prompt is part of the QA Agent testing suite. Update when API changes.*
