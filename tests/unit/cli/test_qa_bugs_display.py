"""Tests for QA bugs display with session context."""

import pytest


class TestQAFindingSessionFields:
    """Tests for QAFinding session_id and created_at fields."""

    def test_qa_finding_accepts_session_id_parameter(self):
        """QAFinding accepts session_id parameter."""
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/test",
            test_type="happy_path",
            title="Test Finding",
            description="Description",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"error": "Server Error"},
            recommendation="Fix it",
            session_id="qa-session-abc123",
        )

        assert finding.session_id == "qa-session-abc123"

    def test_qa_finding_accepts_created_at_parameter(self):
        """QAFinding accepts created_at parameter."""
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-002",
            severity="moderate",
            category="contract",
            endpoint="POST /api/users",
            test_type="schema",
            title="Schema Mismatch",
            description="Description",
            expected={"type": "object"},
            actual={"type": "array"},
            evidence={},
            recommendation="Update schema",
            created_at="2025-01-01T10:00:00Z",
        )

        assert finding.created_at == "2025-01-01T10:00:00Z"

    def test_qa_finding_to_dict_includes_session_id(self):
        """QAFinding.to_dict() includes session_id field."""
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-003",
            severity="minor",
            category="behavioral",
            endpoint="GET /api/health",
            test_type="edge_case",
            title="Edge Case",
            description="Description",
            expected={},
            actual={},
            evidence={},
            recommendation="Review",
            session_id="qa-session-xyz789",
        )

        data = finding.to_dict()

        assert "session_id" in data
        assert data["session_id"] == "qa-session-xyz789"

    def test_qa_finding_to_dict_includes_created_at(self):
        """QAFinding.to_dict() includes created_at field."""
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-004",
            severity="critical",
            category="security",
            endpoint="POST /api/login",
            test_type="auth",
            title="Auth Bypass",
            description="Description",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix auth",
            created_at="2025-01-01T12:00:00Z",
        )

        data = finding.to_dict()

        assert "created_at" in data
        assert data["created_at"] == "2025-01-01T12:00:00Z"

    def test_qa_finding_from_dict_parses_session_id(self):
        """QAFinding.from_dict() parses session_id field."""
        from swarm_attack.qa.models import QAFinding

        data = {
            "finding_id": "QA-005",
            "severity": "moderate",
            "category": "behavioral",
            "endpoint": "GET /api/test",
            "test_type": "happy_path",
            "title": "Test",
            "description": "Desc",
            "expected": {},
            "actual": {},
            "evidence": {},
            "recommendation": "Fix",
            "confidence": 0.9,
            "session_id": "qa-parsed-session",
            "created_at": "",
        }

        finding = QAFinding.from_dict(data)

        assert finding.session_id == "qa-parsed-session"

    def test_qa_finding_from_dict_parses_created_at(self):
        """QAFinding.from_dict() parses created_at field."""
        from swarm_attack.qa.models import QAFinding

        data = {
            "finding_id": "QA-006",
            "severity": "minor",
            "category": "contract",
            "endpoint": "PUT /api/item",
            "test_type": "validation",
            "title": "Validation Issue",
            "description": "Desc",
            "expected": {},
            "actual": {},
            "evidence": {},
            "recommendation": "Validate",
            "confidence": 0.85,
            "session_id": "",
            "created_at": "2025-01-01T14:30:00Z",
        }

        finding = QAFinding.from_dict(data)

        assert finding.created_at == "2025-01-01T14:30:00Z"


class TestGetActionSuggestion:
    """Tests for get_action_suggestion helper function."""

    def test_get_action_suggestion_critical_returns_action(self):
        """get_action_suggestion for critical severity returns action text."""
        from swarm_attack.cli.display import get_action_suggestion

        result = get_action_suggestion("critical")

        assert result  # Non-empty
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_action_suggestion_moderate_returns_action(self):
        """get_action_suggestion for moderate severity returns action text."""
        from swarm_attack.cli.display import get_action_suggestion

        result = get_action_suggestion("moderate")

        assert result
        assert isinstance(result, str)

    def test_get_action_suggestion_minor_returns_action(self):
        """get_action_suggestion for minor severity returns action text."""
        from swarm_attack.cli.display import get_action_suggestion

        result = get_action_suggestion("minor")

        assert result
        assert isinstance(result, str)


class TestBugsTableFormat:
    """Tests for bugs display table format."""

    def test_bugs_table_has_session_column(self):
        """format_qa_bugs_table includes Session column."""
        from swarm_attack.cli.display import format_qa_bugs_table
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-007",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/test",
            test_type="happy_path",
            title="Test Finding",
            description="Description",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
            session_id="qa-session-123",
        )

        table = format_qa_bugs_table([finding])

        column_names = [col.header for col in table.columns]
        assert any("session" in str(name).lower() for name in column_names)

    def test_bugs_table_has_timestamp_column(self):
        """format_qa_bugs_table includes Timestamp/Created column."""
        from swarm_attack.cli.display import format_qa_bugs_table
        from swarm_attack.qa.models import QAFinding

        finding = QAFinding(
            finding_id="QA-008",
            severity="moderate",
            category="contract",
            endpoint="POST /api/users",
            test_type="schema",
            title="Schema Issue",
            description="Description",
            expected={},
            actual={},
            evidence={},
            recommendation="Update",
            created_at="2025-01-01T10:00:00Z",
        )

        table = format_qa_bugs_table([finding])

        column_names = [col.header for col in table.columns]
        assert any("time" in str(name).lower() or "created" in str(name).lower() or "date" in str(name).lower() for name in column_names)
