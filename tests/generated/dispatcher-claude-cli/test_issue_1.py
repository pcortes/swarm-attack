"""Tests for AgentDispatcher._parse_findings() method.

TDD tests for parsing Claude CLI JSON responses into Finding objects.
"""

import pytest
from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.models import (
    CommitCategory,
    Finding,
    Severity,
)


class TestParseFindings:
    """Tests for _parse_findings() helper method."""

    @pytest.fixture
    def dispatcher(self):
        """Create an AgentDispatcher instance."""
        return AgentDispatcher(max_concurrent=5)

    @pytest.fixture
    def commit_sha(self):
        """Sample commit SHA."""
        return "abc1234567890"

    def test_parse_findings_method_exists(self, dispatcher):
        """_parse_findings method exists on AgentDispatcher."""
        assert hasattr(dispatcher, "_parse_findings")
        assert callable(getattr(dispatcher, "_parse_findings"))

    def test_parse_findings_returns_list(self, dispatcher, commit_sha):
        """_parse_findings returns a list."""
        result = dispatcher._parse_findings(
            response={},
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert isinstance(result, list)

    def test_parse_findings_empty_response(self, dispatcher, commit_sha):
        """Returns empty list for empty response."""
        result = dispatcher._parse_findings(
            response={},
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert result == []

    def test_parse_findings_no_result_field(self, dispatcher, commit_sha):
        """Returns empty list when response has no result field."""
        result = dispatcher._parse_findings(
            response={"other": "data"},
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert result == []

    def test_parse_findings_json_structured_output(self, dispatcher, commit_sha):
        """Parses findings from JSON-structured result field."""
        response = {
            "result": '[{"severity": "MEDIUM", "category": "production_reliability", "description": "Missing error handling", "evidence": "src/app.py:42"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        finding = result[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.description == "Missing error handling"
        assert finding.evidence == "src/app.py:42"

    def test_parse_findings_maps_severity_low(self, dispatcher, commit_sha):
        """Maps LOW severity string to Severity.LOW enum."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Minor issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].severity == Severity.LOW

    def test_parse_findings_maps_severity_high(self, dispatcher, commit_sha):
        """Maps HIGH severity string to Severity.HIGH enum."""
        response = {
            "result": '[{"severity": "HIGH", "category": "test", "description": "Major issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].severity == Severity.HIGH

    def test_parse_findings_maps_severity_critical(self, dispatcher, commit_sha):
        """Maps CRITICAL severity string to Severity.CRITICAL enum."""
        response = {
            "result": '[{"severity": "CRITICAL", "category": "test", "description": "Critical issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL

    def test_parse_findings_assigns_commit_sha(self, dispatcher, commit_sha):
        """Finding objects have correct commit_sha."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].commit_sha == commit_sha

    def test_parse_findings_assigns_expert_bug_fix(self, dispatcher, commit_sha):
        """BUG_FIX category maps to Dr. Elena Vasquez."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].expert == "Dr. Elena Vasquez"

    def test_parse_findings_assigns_expert_feature(self, dispatcher, commit_sha):
        """FEATURE category maps to Dr. Aisha Patel."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.FEATURE,
        )
        assert len(result) == 1
        assert result[0].expert == "Dr. Aisha Patel"

    def test_parse_findings_assigns_expert_refactor(self, dispatcher, commit_sha):
        """REFACTOR category maps to Dr. Sarah Kim."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.REFACTOR,
        )
        assert len(result) == 1
        assert result[0].expert == "Dr. Sarah Kim"

    def test_parse_findings_assigns_expert_test_change(self, dispatcher, commit_sha):
        """TEST_CHANGE category maps to Marcus Chen."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.TEST_CHANGE,
        )
        assert len(result) == 1
        assert result[0].expert == "Marcus Chen"

    def test_parse_findings_assigns_expert_documentation(self, dispatcher, commit_sha):
        """DOCUMENTATION category maps to James O'Brien."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.DOCUMENTATION,
        )
        assert len(result) == 1
        assert result[0].expert == "James O'Brien"

    def test_parse_findings_assigns_expert_chore(self, dispatcher, commit_sha):
        """CHORE category maps to General Reviewer."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.CHORE,
        )
        assert len(result) == 1
        assert result[0].expert == "General Reviewer"

    def test_parse_findings_assigns_expert_other(self, dispatcher, commit_sha):
        """OTHER category maps to General Reviewer."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.OTHER,
        )
        assert len(result) == 1
        assert result[0].expert == "General Reviewer"

    def test_parse_findings_multiple_findings(self, dispatcher, commit_sha):
        """Parses multiple findings from result."""
        response = {
            "result": '[{"severity": "LOW", "category": "c1", "description": "Issue 1", "evidence": "file.py:1"}, {"severity": "HIGH", "category": "c2", "description": "Issue 2", "evidence": "file.py:2"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 2
        assert result[0].severity == Severity.LOW
        assert result[1].severity == Severity.HIGH

    def test_parse_findings_populates_all_fields(self, dispatcher, commit_sha):
        """All required Finding fields are populated."""
        response = {
            "result": '[{"severity": "MEDIUM", "category": "production_reliability", "description": "Missing error handling", "evidence": "src/app.py:42"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        finding = result[0]
        # Check all required fields
        assert finding.commit_sha == commit_sha
        assert finding.expert == "Dr. Elena Vasquez"
        assert finding.severity == Severity.MEDIUM
        assert finding.category == "production_reliability"
        assert finding.description == "Missing error handling"
        assert finding.evidence == "src/app.py:42"

    def test_parse_findings_handles_invalid_json(self, dispatcher, commit_sha):
        """Returns empty list on invalid JSON in result field."""
        response = {"result": "not valid json ["}
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert result == []

    def test_parse_findings_handles_plain_text(self, dispatcher, commit_sha):
        """Returns empty list when result is plain text without findings."""
        response = {"result": "No issues found in this commit."}
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert result == []

    def test_parse_findings_handles_missing_severity(self, dispatcher, commit_sha):
        """Handles finding with missing severity gracefully."""
        response = {
            "result": '[{"category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        # Should skip invalid findings or use default
        # Either empty or has finding with default severity
        if len(result) > 0:
            assert result[0].severity in list(Severity)

    def test_parse_findings_handles_invalid_severity(self, dispatcher, commit_sha):
        """Handles finding with invalid severity gracefully."""
        response = {
            "result": '[{"severity": "INVALID", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        # Should skip invalid findings
        assert result == []

    def test_parse_findings_handles_missing_required_fields(self, dispatcher, commit_sha):
        """Handles finding with missing required fields gracefully."""
        response = {
            "result": '[{"severity": "LOW"}]'  # Missing category, description, evidence
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        # Should skip incomplete findings
        assert result == []

    def test_parse_findings_handles_key_error(self, dispatcher, commit_sha):
        """Returns empty list on KeyError during parsing."""
        # Simulate an edge case that could cause KeyError
        response = {"result": '[{"extra": "field"}]'}
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert result == []

    def test_parse_findings_lowercase_severity(self, dispatcher, commit_sha):
        """Handles lowercase severity strings."""
        response = {
            "result": '[{"severity": "medium", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        assert len(result) == 1
        assert result[0].severity == Severity.MEDIUM

    def test_parse_findings_result_as_dict_with_findings(self, dispatcher, commit_sha):
        """Handles result that is already a dict with findings key."""
        # Some Claude responses might have structured result
        response = {
            "result": '{"findings": [{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]}'
        }
        result = dispatcher._parse_findings(
            response=response,
            commit_sha=commit_sha,
            category=CommitCategory.BUG_FIX,
        )
        # Should extract from nested findings
        assert len(result) == 1
        assert result[0].severity == Severity.LOW