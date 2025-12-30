"""Tests for UserMetrics data model.

These tests verify the UserMetrics model implementation for the external dashboard.
Tests MUST FAIL before implementation (RED phase of TDD).
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path


class TestUserMetricsModelExists:
    """Tests that verify the UserMetrics model file and class exist."""

    def test_model_file_exists(self):
        """Test that the UserMetrics model file exists at expected path."""
        # Model should be in the feature directory (external_dashboard)
        model_path = Path.cwd() / "external_dashboard" / "models" / "user_metrics.py"
        assert model_path.exists(), (
            "UserMetrics model file must exist at: external_dashboard/models/user_metrics.py"
        )

    def test_user_metrics_class_importable(self):
        """Test that UserMetrics class can be imported."""
        try:
            from external_dashboard.models.user_metrics import UserMetrics
        except ImportError:
            pytest.fail("UserMetrics class must be importable from external_dashboard.models.user_metrics")


class TestUserMetricsFields:
    """Tests that verify UserMetrics has required fields with correct types."""

    @pytest.fixture
    def user_metrics_class(self):
        """Import and return the UserMetrics class."""
        from external_dashboard.models.user_metrics import UserMetrics
        return UserMetrics

    def test_user_id_field_is_string(self, user_metrics_class):
        """Test that UserMetrics has user_id field as string."""
        now = datetime.now(timezone.utc)
        metrics = user_metrics_class(
            user_id="test-user-123",
            login_history=[now],
            last_active=now,
            total_actions=10
        )
        assert isinstance(metrics.user_id, str), "user_id must be a string"
        assert metrics.user_id == "test-user-123"

    def test_login_history_field_is_list_of_datetimes(self, user_metrics_class):
        """Test that UserMetrics has login_history field as list of datetime."""
        now = datetime.now(timezone.utc)
        yesterday = datetime(2025, 1, 14, 9, 15, 0, tzinfo=timezone.utc)

        metrics = user_metrics_class(
            user_id="test-user",
            login_history=[now, yesterday],
            last_active=now,
            total_actions=5
        )

        assert isinstance(metrics.login_history, list), "login_history must be a list"
        assert len(metrics.login_history) == 2, "login_history should contain 2 entries"
        assert all(isinstance(dt, datetime) for dt in metrics.login_history), \
            "All login_history entries must be datetime objects"

    def test_last_active_field_is_datetime(self, user_metrics_class):
        """Test that UserMetrics has last_active field as datetime."""
        now = datetime.now(timezone.utc)

        metrics = user_metrics_class(
            user_id="test-user",
            login_history=[now],
            last_active=now,
            total_actions=0
        )

        assert isinstance(metrics.last_active, datetime), "last_active must be a datetime"

    def test_total_actions_field_is_integer(self, user_metrics_class):
        """Test that UserMetrics has total_actions field as integer."""
        now = datetime.now(timezone.utc)

        metrics = user_metrics_class(
            user_id="test-user",
            login_history=[now],
            last_active=now,
            total_actions=42
        )

        assert isinstance(metrics.total_actions, int), "total_actions must be an integer"
        assert metrics.total_actions == 42

    def test_empty_login_history_allowed(self, user_metrics_class):
        """Test that UserMetrics allows empty login_history list."""
        now = datetime.now(timezone.utc)

        metrics = user_metrics_class(
            user_id="new-user",
            login_history=[],
            last_active=now,
            total_actions=0
        )

        assert metrics.login_history == [], "Empty login_history should be allowed"


class TestUserMetricsTypeHints:
    """Tests that verify UserMetrics has proper type hints."""

    def test_model_has_type_annotations(self):
        """Test that UserMetrics class has type annotations for all fields."""
        from external_dashboard.models.user_metrics import UserMetrics

        # Check that the class has __annotations__ with required fields
        annotations = getattr(UserMetrics, '__annotations__', {})

        # If using dataclass or pydantic, annotations should be present
        # Allow for fields to be defined in __init__ signature for regular classes
        import inspect
        sig = inspect.signature(UserMetrics.__init__)
        params = list(sig.parameters.keys())

        required_fields = ['user_id', 'login_history', 'last_active', 'total_actions']

        # Check either annotations or init parameters
        has_annotations = all(field in annotations for field in required_fields)
        has_params = all(field in params for field in required_fields)

        assert has_annotations or has_params, \
            f"UserMetrics must have type hints for: {required_fields}"
