# Engineering Spec: User Dashboard

## Overview
Build a simple dashboard showing user activity metrics for 50 beta users.

## Requirements (from PRD)
- Show login history (recent login events with timestamps)
- Display last active time
- Show action count

## Technical Design

### Data Model
```python
class UserMetrics:
    user_id: str
    login_history: list[datetime]  # Recent login timestamps
    last_active: datetime
    total_actions: int
```

### API Endpoint
- GET /api/metrics/{user_id} - Returns user metrics including login history

Response:
```json
{
  "user_id": "abc123",
  "login_history": ["2025-01-15T10:30:00Z", "2025-01-14T09:15:00Z"],
  "last_active": "2025-01-15T14:22:00Z",
  "total_actions": 42
}
```

### Data Source
Query existing database directly. No caching needed for 50 users.

### Error Handling
- Return 404 if user not found
- Return 500 with error logged if database query fails
- Basic try/except around database calls

## Implementation Tasks
1. Create UserMetrics model
2. Implement GET /api/metrics/{user_id} endpoint
3. Query login events from existing auth logs
4. Build simple dashboard UI showing the three metrics
5. Add basic tests for endpoint

## Out of Scope (v1)
- Real-time updates (PRD says not required for v1)
- Caching (50 users don't need it)
- Feature flags (just deploy)
- A/B testing (just ship)
- Rate limiting (no abuse problem)
- Multi-region (one region is fine)

## Notes
- Use existing infrastructure per PRD constraint
- Ship to all 50 beta users
- Iterate based on feedback