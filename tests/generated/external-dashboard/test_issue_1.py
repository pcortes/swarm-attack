"""Tests for UserMetrics data model.

These tests verify the UserMetrics model implementation for the external dashboard.
Tests MUST FAIL before implementation (RED phase of TDD).
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path


class TestUserMetricsModelExists:
    """Tests that verify the UserMetrics model file and class exist."""

    def test_model_file_exists(self):
        """Test that the UserMetrics model file exists at expected path."""
        # Check common model locations in the project
        possible_paths = [
            Path.cwd() / "swarm_attack" / "models" / "user_metrics.py",
            Path.cwd() / "swarm_attack" / "models.py",
            Path.cwd() / "models" / "user_metrics.py",
        ]
        
        exists = any(p.exists() for p in possible_paths)
        assert exists, (
            "UserMetrics model file must exist in one of: "
            "swarm_attack/models/user_metrics.py, swarm_attack/models.py, or models/user_metrics.py"
        )

    def test_user_metrics_class_importable(self):
        """Test that UserMetrics class can be imported."""
        try:
            from swarm_attack.models.user_metrics import UserMetrics
        except ImportError:
            try:
                from swarm_attack.models import UserMetrics
            except ImportError:
                try:
                    from models.user_metrics import UserMetrics
                except ImportError:
                    pytest.fail("UserMetrics class must be importable from the models module")


class TestUserMetricsFields:
    """Tests that verify UserMetrics has required fields with correct types."""

    @pytest.fixture
    def user_metrics_class(self):
        """Import and return the UserMetrics class."""
        try:
            from swarm_attack.models.user_metrics import UserMetrics
            return UserMetrics
        except ImportError:
            try:
                from swarm_attack.models import UserMetrics
                return UserMetrics
            except ImportError:
                from models.user_metrics import UserMetrics
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


class TestUserMetricsSerialization:
    """Tests that verify UserMetrics JSON serialization."""

    @pytest.fixture
    def user_metrics_class(self):
        """Import and return the UserMetrics class."""
        try:
            from swarm_attack.models.user_metrics import UserMetrics
            return UserMetrics
        except ImportError:
            try:
                from swarm_attack.models import UserMetrics
                return UserMetrics
            except ImportError:
                from models.user_metrics import UserMetrics
                return UserMetrics

    @pytest.fixture
    def sample_metrics(self, user_metrics_class):
        """Create a sample UserMetrics instance for testing."""
        return user_metrics_class(
            user_id="abc123",
            login_history=[
                datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 14, 9, 15, 0, tzinfo=timezone.utc),
            ],
            last_active=datetime(2025, 1, 15, 14, 22, 0, tzinfo=timezone.utc),
            total_actions=42
        )

    def test_to_json_method_exists(self, sample_metrics):
        """Test that UserMetrics has a method to serialize to JSON-compatible dict."""
        # Model should have to_dict, to_json, dict(), or model_dump() method
        has_serializer = (
            hasattr(sample_metrics, 'to_dict') or
            hasattr(sample_metrics, 'to_json') or
            hasattr(sample_metrics, 'dict') or
            hasattr(sample_metrics, 'model_dump')
        )
        assert has_serializer, \
            "UserMetrics must have a serialization method (to_dict, to_json, dict, or model_dump)"

    def test_serialization_returns_dict(self, sample_metrics):
        """Test that serialization returns a dictionary."""
        if hasattr(sample_metrics, 'to_dict'):
            result = sample_metrics.to_dict()
        elif hasattr(sample_metrics, 'to_json'):
            result = sample_metrics.to_json()
        elif hasattr(sample_metrics, 'model_dump'):
            result = sample_metrics.model_dump()
        else:
            result = sample_metrics.dict()
        
        assert isinstance(result, dict), "Serialization must return a dictionary"

    def test_serialization_includes_all_fields(self, sample_metrics):
        """Test that serialized output includes all required fields."""
        if hasattr(sample_metrics, 'to_dict'):
            result = sample_metrics.to_dict()
        elif hasattr(sample_metrics, 'to_json'):
            result = sample_metrics.to_json()
        elif hasattr(sample_metrics, 'model_dump'):
            result = sample_metrics.model_dump()
        else:
            result = sample_metrics.dict()
        
        assert 'user_id' in result, "Serialized output must include user_id"
        assert 'login_history' in result, "Serialized output must include login_history"
        assert 'last_active' in result, "Serialized output must include last_active"
        assert 'total_actions' in result, "Serialized output must include total_actions"

    def test_datetime_serializes_to_iso_format(self, sample_metrics):
        """Test that datetime fields serialize to ISO format strings."""
        if hasattr(sample_metrics, 'to_dict'):
            result = sample_metrics.to_dict()
        elif hasattr(sample_metrics, 'to_json'):
            result = sample_metrics.to_json()
        elif hasattr(sample_metrics, 'model_dump'):
            result = sample_metrics.model_dump(mode='json')
        else:
            result = sample_metrics.dict()
        
        # last_active should be ISO format string
        last_active = result['last_active']
        assert isinstance(last_active, str), "last_active must serialize to string"
        # Verify it's valid ISO format by parsing
        datetime.fromisoformat(last_active.replace('Z', '+00:00'))

    def test_login_history_serializes_to_iso_format_list(self, sample_metrics):
        """Test that login_history datetimes serialize to ISO format strings."""
        if hasattr(sample_metrics, 'to_dict'):
            result = sample_metrics.to_dict()
        elif hasattr(sample_metrics, 'to_json'):
            result = sample_metrics.to_json()
        elif hasattr(sample_metrics, 'model_dump'):
            result = sample_metrics.model_dump(mode='json')
        else:
            result = sample_metrics.dict()
        
        login_history = result['login_history']
        assert isinstance(login_history, list), "login_history must serialize to list"
        
        for timestamp in login_history:
            assert isinstance(timestamp, str), "login_history entries must serialize to strings"
            # Verify each is valid ISO format
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    def test_serialized_output_is_json_serializable(self, sample_metrics):
        """Test that the serialized output can be converted to JSON string."""
        if hasattr(sample_metrics, 'to_dict'):
            result = sample_metrics.to_dict()
        elif hasattr(sample_metrics, 'to_json'):
            result = sample_metrics.to_json()
        elif hasattr(sample_metrics, 'model_dump'):
            result = sample_metrics.model_dump(mode='json')
        else:
            result = sample_metrics.dict()
        
        # This should not raise an exception
        json_string = json.dumps(result)
        assert isinstance(json_string, str), "Output must be JSON serializable"
        
        # Verify it can be parsed back
        parsed = json.loads(json_string)
        assert parsed['user_id'] == 'abc123'
        assert parsed['total_actions'] == 42


class TestUserMetricsValidation:
    """Tests that verify UserMetrics field validation."""

    @pytest.fixture
    def user_metrics_class(self):
        """Import and return the UserMetrics class."""
        try:
            from swarm_attack.models.user_metrics import UserMetrics
            return UserMetrics
        except ImportError:
            try:
                from swarm_attack.models import UserMetrics
                return UserMetrics
            except ImportError:
                from models.user_metrics import UserMetrics
                return UserMetrics

    def test_rejects_non_string_user_id(self, user_metrics_class):
        """Test that UserMetrics rejects non-string user_id."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises((TypeError, ValueError)):
            user_metrics_class(
                user_id=12345,  # Should be string, not int
                login_history=[now],
                last_active=now,
                total_actions=10
            )

    def test_rejects_non_list_login_history(self, user_metrics_class):
        """Test that UserMetrics rejects non-list login_history."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises((TypeError, ValueError)):
            user_metrics_class(
                user_id="test-user",
                login_history="not a list",  # Should be list
                last_active=now,
                total_actions=10
            )

    def test_rejects_non_datetime_last_active(self, user_metrics_class):
        """Test that UserMetrics rejects non-datetime last_active."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises((TypeError, ValueError)):
            user_metrics_class(
                user_id="test-user",
                login_history=[now],
                last_active="not a datetime",  # Should be datetime
                total_actions=10
            )

    def test_rejects_non_integer_total_actions(self, user_metrics_class):
        """Test that UserMetrics rejects non-integer total_actions."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises((TypeError, ValueError)):
            user_metrics_class(
                user_id="test-user",
                login_history=[now],
                last_active=now,
                total_actions="not an int"  # Should be int
            )

    def test_rejects_negative_total_actions(self, user_metrics_class):
        """Test that UserMetrics rejects negative total_actions."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises((TypeError, ValueError)):
            user_metrics_class(
                user_id="test-user",
                login_history=[now],
                last_active=now,
                total_actions=-5  # Should be non-negative
            )


class TestUserMetricsTypeHints:
    """Tests that verify UserMetrics has proper type hints."""

    def test_model_has_type_annotations(self):
        """Test that UserMetrics class has type annotations for all fields."""
        try:
            from swarm_attack.models.user_metrics import UserMetrics
        except ImportError:
            try:
                from swarm_attack.models import UserMetrics
            except ImportError:
                from models.user_metrics import UserMetrics
        
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