# QA Report: qa-20251231-181406

**Trigger:** user_command
**Depth:** shallow
**Status:** completed
**Recommendation:** BLOCK

## Summary

- **Tests Run:** 3
- **Passed:** 0
- **Failed:** 3
- **Endpoints Tested:** 0

## Findings

### [CRITICAL] BT-001: Request failed

**Endpoint:** GET /health
**Category:** behavioral

Test 'happy_path' failed for endpoint GET /health

**Expected:**
```json
{
  "status": 200
}
```

**Actual:**
```json
{
  "error": "HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x106e36710>: Failed to establish a new connection: [Errno 61] Connection refused'))"
}
```

**Recommendation:** Investigate server error immediately. Check logs for stack traces.

---

### [CRITICAL] BT-002: Request failed

**Endpoint:** GET /healthz
**Category:** behavioral

Test 'happy_path' failed for endpoint GET /healthz

**Expected:**
```json
{
  "status": 200
}
```

**Actual:**
```json
{
  "error": "HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /healthz (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x106e80e90>: Failed to establish a new connection: [Errno 61] Connection refused'))"
}
```

**Recommendation:** Investigate server error immediately. Check logs for stack traces.

---

### [CRITICAL] BT-003: Request failed

**Endpoint:** GET /api/health
**Category:** behavioral

Test 'happy_path' failed for endpoint GET /api/health

**Expected:**
```json
{
  "status": 200
}
```

**Actual:**
```json
{
  "error": "HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /api/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x106b8ad50>: Failed to establish a new connection: [Errno 61] Connection refused'))"
}
```

**Recommendation:** Investigate server error immediately. Check logs for stack traces.

---
