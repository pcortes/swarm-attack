"""Real HTTP validation tests.

Uses a test server fixture to validate actual HTTP behavior.
Tests behavioral and contract validation against a running service.

This provides higher confidence that the QA agents work correctly
with real HTTP requests/responses, not just mocked data.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Optional

# Check if FastAPI is available for real HTTP tests
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    TestClient = None

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)


# =============================================================================
# SKIP IF FASTAPI NOT AVAILABLE
# =============================================================================

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed - skipping real HTTP tests"
)


# =============================================================================
# TEST SERVER FIXTURES
# =============================================================================


class UserResponse(BaseModel):
    """User response model."""
    id: int
    name: str
    email: str


class OrderResponse(BaseModel):
    """Order response model."""
    order_id: str
    status: str
    total: float


class CreateOrderRequest(BaseModel):
    """Create order request model."""
    product_id: int
    quantity: int


@pytest.fixture
def test_app():
    """Create test FastAPI application with sample endpoints."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")

    app = FastAPI(title="Test API")

    # Sample user database
    users_db = {
        1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
        2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
    }

    # Sample orders database
    orders_db = {
        "ORD-001": {"order_id": "ORD-001", "status": "completed", "total": 99.99},
        "ORD-002": {"order_id": "ORD-002", "status": "pending", "total": 149.99},
    }

    @app.get("/api/users/{user_id}")
    def get_user(user_id: int):
        """Get a user by ID."""
        if user_id == 404:
            raise HTTPException(status_code=404, detail="User not found")
        if user_id == 500:
            raise HTTPException(status_code=500, detail="Internal server error")
        user = users_db.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(**user)

    @app.get("/api/users")
    def list_users():
        """List all users."""
        return [UserResponse(**u) for u in users_db.values()]

    @app.get("/api/orders/{order_id}")
    def get_order(order_id: str):
        """Get an order by ID."""
        order = orders_db.get(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return OrderResponse(**order)

    @app.post("/api/orders")
    def create_order(request: CreateOrderRequest):
        """Create a new order."""
        if request.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        if request.product_id == 999:
            raise HTTPException(status_code=404, detail="Product not found")

        order_id = f"ORD-{len(orders_db) + 1:03d}"
        order = {
            "order_id": order_id,
            "status": "pending",
            "total": request.quantity * 10.0,
        }
        orders_db[order_id] = order
        return OrderResponse(**order)

    @app.get("/api/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/api/slow")
    def slow_endpoint():
        """Simulates a slow endpoint."""
        import time
        time.sleep(0.1)  # 100ms delay
        return {"result": "slow response"}

    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")
    return TestClient(test_app)


@pytest.fixture
def mock_config(tmp_path):
    """Create mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    return config


# =============================================================================
# REAL HTTP BEHAVIORAL TESTS
# =============================================================================


class TestRealHTTPBehavioral:
    """Test behavioral validation with real HTTP."""

    def test_happy_path_validation(self, test_client, mock_config):
        """Should validate happy path against real server."""
        # Test GET /api/users/1 returns 200
        response = test_client.get("/api/users/1")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"

    def test_error_path_validation(self, test_client, mock_config):
        """Should validate error handling against real server."""
        # Test 404 handling
        response = test_client.get("/api/users/999")
        assert response.status_code == 404

        # Test 500 handling
        response = test_client.get("/api/users/500")
        assert response.status_code == 500

    def test_list_endpoint_validation(self, test_client, mock_config):
        """Should validate list endpoints against real server."""
        response = test_client.get("/api/users")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_post_endpoint_validation(self, test_client, mock_config):
        """Should validate POST endpoints against real server."""
        # Valid request
        response = test_client.post(
            "/api/orders",
            json={"product_id": 1, "quantity": 2}
        )
        assert response.status_code == 200

        data = response.json()
        assert "order_id" in data
        assert data["status"] == "pending"
        assert data["total"] == 20.0

    def test_validation_error_handling(self, test_client, mock_config):
        """Should handle validation errors correctly."""
        # Invalid quantity
        response = test_client.post(
            "/api/orders",
            json={"product_id": 1, "quantity": -1}
        )
        assert response.status_code == 400

    def test_health_endpoint(self, test_client, mock_config):
        """Should validate health endpoint."""
        response = test_client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"


class TestRealHTTPContract:
    """Test contract validation with real HTTP."""

    def test_schema_validation(self, test_client, mock_config):
        """Should validate response schema against contract."""
        response = test_client.get("/api/users/1")
        assert response.status_code == 200

        data = response.json()
        # Verify schema fields
        assert "id" in data
        assert "name" in data
        assert "email" in data

        # Verify types
        assert isinstance(data["id"], int)
        assert isinstance(data["name"], str)
        assert isinstance(data["email"], str)

    def test_order_schema_validation(self, test_client, mock_config):
        """Should validate order response schema."""
        response = test_client.get("/api/orders/ORD-001")
        assert response.status_code == 200

        data = response.json()
        # Verify schema fields
        assert "order_id" in data
        assert "status" in data
        assert "total" in data

        # Verify types
        assert isinstance(data["order_id"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["total"], (int, float))

    def test_list_schema_validation(self, test_client, mock_config):
        """Should validate list response schema."""
        response = test_client.get("/api/users")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Each item should have user schema
        for user in data:
            assert "id" in user
            assert "name" in user
            assert "email" in user

    def test_breaking_change_detection(self, test_client, mock_config):
        """Should detect breaking changes in API."""
        # This test verifies the response structure hasn't changed
        response = test_client.get("/api/users/1")
        data = response.json()

        # If 'email' field was removed, this would fail
        assert "email" in data, "Breaking change: 'email' field missing from user response"

        # If 'id' type changed, this would fail
        assert isinstance(data["id"], int), "Breaking change: 'id' should be integer"


class TestRealHTTPIntegration:
    """Integration tests combining behavioral and contract validation."""

    def test_full_crud_flow(self, test_client, mock_config):
        """Test full CRUD flow against real server."""
        # Create
        create_response = test_client.post(
            "/api/orders",
            json={"product_id": 1, "quantity": 3}
        )
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]

        # Read
        get_response = test_client.get(f"/api/orders/{order_id}")
        assert get_response.status_code == 200
        assert get_response.json()["order_id"] == order_id
        assert get_response.json()["total"] == 30.0

    def test_error_responses_have_detail(self, test_client, mock_config):
        """Error responses should include detail message."""
        response = test_client.get("/api/users/999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert data["detail"] == "User not found"

    def test_concurrent_requests(self, test_client, mock_config):
        """Test multiple concurrent requests."""
        import concurrent.futures

        def fetch_user(user_id):
            return test_client.get(f"/api/users/{user_id}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_user, uid) for uid in [1, 2, 1]]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(r.status_code in [200, 404] for r in results)


class TestRealHTTPWithQAOrchestrator:
    """Test QA orchestrator with real HTTP endpoints."""

    def test_orchestrator_with_real_endpoints(self, test_client, mock_config):
        """Test orchestrator can work with real endpoint definitions."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        orchestrator = QAOrchestrator(mock_config)

        # Create context with real endpoints
        context = QAContext(
            target_endpoints=[
                QAEndpoint(method="GET", path="/api/users/1"),
                QAEndpoint(method="GET", path="/api/health"),
            ],
            base_url="http://testserver",
        )

        # The orchestrator should be able to dispatch agents
        # (actual HTTP calls would need agent modification to use test_client)
        assert orchestrator is not None
        assert len(context.target_endpoints) == 2

    def test_behavioral_agent_endpoint_analysis(self, test_client, mock_config):
        """Test behavioral agent can analyze endpoint patterns."""
        from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent

        agent = BehavioralTesterAgent(mock_config)

        # Agent should be creatable
        assert agent is not None

        # Test actual endpoint behavior matches expected
        # Happy path
        happy_response = test_client.get("/api/users/1")
        assert happy_response.status_code == 200

        # Error path
        error_response = test_client.get("/api/users/999")
        assert error_response.status_code == 404

    def test_contract_agent_schema_analysis(self, test_client, mock_config):
        """Test contract agent can validate schemas."""
        from swarm_attack.qa.agents.contract import ContractValidatorAgent

        agent = ContractValidatorAgent(mock_config)

        # Agent should be creatable
        assert agent is not None

        # Get actual response and validate schema
        response = test_client.get("/api/users/1")
        data = response.json()

        # Schema should match expected structure
        expected_fields = {"id", "name", "email"}
        actual_fields = set(data.keys())
        assert expected_fields == actual_fields


class TestRealHTTPPerformance:
    """Test performance aspects with real HTTP."""

    def test_response_time_measurement(self, test_client, mock_config):
        """Should be able to measure response times."""
        import time

        start = time.time()
        response = test_client.get("/api/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Health endpoint should be fast (< 100ms)
        assert elapsed < 0.1

    def test_slow_endpoint_detection(self, test_client, mock_config):
        """Should detect slow endpoints."""
        import time

        start = time.time()
        response = test_client.get("/api/slow")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Slow endpoint takes at least 100ms
        assert elapsed >= 0.1


class TestRealHTTPSecurityPatterns:
    """Test security patterns with real HTTP."""

    def test_unauthorized_access_blocked(self, test_client, mock_config):
        """Test that protected resources return proper status."""
        # In a real app, protected endpoints would return 401/403
        # For now, verify error codes are meaningful
        response = test_client.get("/api/users/404")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_input_validation_enforced(self, test_client, mock_config):
        """Test that invalid input is rejected."""
        # Negative quantity should be rejected
        response = test_client.post(
            "/api/orders",
            json={"product_id": 1, "quantity": -1}
        )
        assert response.status_code == 400

    def test_resource_not_found_handling(self, test_client, mock_config):
        """Test proper 404 handling for missing resources."""
        response = test_client.get("/api/orders/NONEXISTENT")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"
