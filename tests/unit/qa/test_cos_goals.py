"""Tests for Chief of Staff QA Goals following TDD approach.

Tests cover spec section 5.2.3:
- QA_VALIDATION and QA_HEALTH goal types
- QAGoal dataclass with linking capabilities
- Goal-to-session tracking
"""

import pytest
from dataclasses import fields
from enum import Enum


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify COS Goals can be imported."""

    def test_can_import_qa_goal_types(self):
        """Should be able to import QAGoalTypes enum."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        assert QAGoalTypes is not None

    def test_can_import_qa_goal(self):
        """Should be able to import QAGoal dataclass."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal
        assert QAGoal is not None

    def test_qa_goal_types_is_enum(self):
        """QAGoalTypes should be an Enum."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        assert issubclass(QAGoalTypes, Enum)


# =============================================================================
# QAGoalTypes TESTS
# =============================================================================


class TestQAGoalTypes:
    """Tests for QAGoalTypes enum."""

    def test_has_qa_validation_type(self):
        """Should have QA_VALIDATION goal type."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        assert hasattr(QAGoalTypes, "QA_VALIDATION")
        assert QAGoalTypes.QA_VALIDATION.value == "qa_validation"

    def test_has_qa_health_type(self):
        """Should have QA_HEALTH goal type."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        assert hasattr(QAGoalTypes, "QA_HEALTH")
        assert QAGoalTypes.QA_HEALTH.value == "qa_health"

    def test_can_iterate_goal_types(self):
        """Should be able to iterate over all goal types."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        goal_types = list(QAGoalTypes)
        assert len(goal_types) >= 2

    def test_goal_types_are_unique(self):
        """All goal type values should be unique."""
        from swarm_attack.qa.integrations.cos_goals import QAGoalTypes
        values = [gt.value for gt in QAGoalTypes]
        assert len(values) == len(set(values))


# =============================================================================
# QAGoal DATACLASS TESTS
# =============================================================================


class TestQAGoalDataclass:
    """Tests for QAGoal dataclass structure."""

    def test_has_goal_type_field(self):
        """QAGoal should have goal_type field."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_VALIDATION)
        assert hasattr(goal, "goal_type")
        assert goal.goal_type == QAGoalTypes.QA_VALIDATION

    def test_has_linked_feature_field(self):
        """QAGoal should have linked_feature field."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_VALIDATION, linked_feature="my-feature")
        assert hasattr(goal, "linked_feature")
        assert goal.linked_feature == "my-feature"

    def test_has_linked_issue_field(self):
        """QAGoal should have linked_issue field."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_VALIDATION, linked_issue=42)
        assert hasattr(goal, "linked_issue")
        assert goal.linked_issue == 42

    def test_has_linked_qa_session_field(self):
        """QAGoal should have linked_qa_session field."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_VALIDATION, linked_qa_session="qa-123")
        assert hasattr(goal, "linked_qa_session")
        assert goal.linked_qa_session == "qa-123"

    def test_has_description_field(self):
        """QAGoal should have description field."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_VALIDATION, description="Validate auth")
        assert hasattr(goal, "description")
        assert goal.description == "Validate auth"

    def test_linked_fields_default_to_none(self):
        """Linked fields should default to None."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        goal = QAGoal(goal_type=QAGoalTypes.QA_HEALTH)
        assert goal.linked_feature is None
        assert goal.linked_issue is None
        assert goal.linked_qa_session is None
        assert goal.description is None


# =============================================================================
# QAGoal CREATION TESTS
# =============================================================================


class TestQAGoalCreation:
    """Tests for creating QAGoal instances."""

    def test_create_validation_goal(self):
        """Should create QA_VALIDATION goal."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="user-auth",
            linked_issue=123,
            description="Validate user authentication",
        )

        assert goal.goal_type == QAGoalTypes.QA_VALIDATION
        assert goal.linked_feature == "user-auth"
        assert goal.linked_issue == 123
        assert goal.description == "Validate user authentication"

    def test_create_health_goal(self):
        """Should create QA_HEALTH goal."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="Daily health check",
        )

        assert goal.goal_type == QAGoalTypes.QA_HEALTH
        assert goal.description == "Daily health check"

    def test_goal_is_dataclass(self):
        """QAGoal should be a proper dataclass."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal

        # Dataclasses have __dataclass_fields__
        assert hasattr(QAGoal, "__dataclass_fields__")

    def test_goal_fields_have_correct_types(self):
        """QAGoal fields should have correct type annotations."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes
        from typing import Optional

        field_names = {f.name for f in fields(QAGoal)}

        assert "goal_type" in field_names
        assert "linked_feature" in field_names
        assert "linked_issue" in field_names
        assert "linked_qa_session" in field_names
        assert "description" in field_names


# =============================================================================
# QAGoal LINKING TESTS
# =============================================================================


class TestQAGoalLinking:
    """Tests for QAGoal linking capabilities."""

    def test_link_goal_to_feature(self):
        """Should link goal to a feature."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="user-profile",
        )

        assert goal.linked_feature == "user-profile"

    def test_link_goal_to_issue(self):
        """Should link goal to an issue number."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_issue=456,
        )

        assert goal.linked_issue == 456

    def test_link_goal_to_feature_and_issue(self):
        """Should link goal to both feature and issue."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="payment-flow",
            linked_issue=789,
        )

        assert goal.linked_feature == "payment-flow"
        assert goal.linked_issue == 789

    def test_link_goal_to_qa_session(self):
        """Should link goal to a QA session ID."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            linked_qa_session="qa-20241225-143022",
        )

        assert goal.linked_qa_session == "qa-20241225-143022"

    def test_health_goal_without_feature_link(self):
        """Health goals typically don't have feature/issue links."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_HEALTH,
            description="System health check",
        )

        assert goal.goal_type == QAGoalTypes.QA_HEALTH
        assert goal.linked_feature is None
        assert goal.linked_issue is None


# =============================================================================
# QAGoal SERIALIZATION TESTS
# =============================================================================


class TestQAGoalSerialization:
    """Tests for QAGoal serialization capabilities."""

    def test_goal_has_to_dict_method(self):
        """QAGoal should have to_dict method for serialization."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="test-feature",
        )

        assert hasattr(goal, "to_dict")
        result = goal.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """to_dict should contain all goal fields."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="my-feature",
            linked_issue=42,
            linked_qa_session="qa-123",
            description="Test goal",
        )

        result = goal.to_dict()

        assert "goal_type" in result
        assert "linked_feature" in result
        assert "linked_issue" in result
        assert "linked_qa_session" in result
        assert "description" in result

    def test_to_dict_converts_enum_to_value(self):
        """to_dict should convert enum to string value."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        goal = QAGoal(goal_type=QAGoalTypes.QA_HEALTH)
        result = goal.to_dict()

        assert result["goal_type"] == "qa_health"

    def test_goal_has_from_dict_method(self):
        """QAGoal should have from_dict class method for deserialization."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal

        assert hasattr(QAGoal, "from_dict")

    def test_from_dict_creates_goal(self):
        """from_dict should create a QAGoal from dictionary."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        data = {
            "goal_type": "qa_validation",
            "linked_feature": "test-feature",
            "linked_issue": 123,
            "linked_qa_session": None,
            "description": "Test description",
        }

        goal = QAGoal.from_dict(data)

        assert goal.goal_type == QAGoalTypes.QA_VALIDATION
        assert goal.linked_feature == "test-feature"
        assert goal.linked_issue == 123
        assert goal.description == "Test description"

    def test_roundtrip_serialization(self):
        """to_dict and from_dict should roundtrip correctly."""
        from swarm_attack.qa.integrations.cos_goals import QAGoal, QAGoalTypes

        original = QAGoal(
            goal_type=QAGoalTypes.QA_VALIDATION,
            linked_feature="roundtrip-test",
            linked_issue=999,
            linked_qa_session="qa-roundtrip",
            description="Roundtrip test",
        )

        data = original.to_dict()
        restored = QAGoal.from_dict(data)

        assert restored.goal_type == original.goal_type
        assert restored.linked_feature == original.linked_feature
        assert restored.linked_issue == original.linked_issue
        assert restored.linked_qa_session == original.linked_qa_session
        assert restored.description == original.description
