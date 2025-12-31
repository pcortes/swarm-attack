"""Tests for QA report display formatting functions."""

import pytest
from rich.table import Table


class TestFormatTestResults:
    """Tests for format_test_results function."""

    def test_format_test_results_formats_x_of_y(self):
        """format_test_results returns 'X/Y passed' format."""
        from swarm_attack.cli.display import format_test_results

        result = format_test_results(8, 10)
        assert "8" in result
        assert "10" in result
        assert "/" in result or "of" in result.lower()

    def test_format_test_results_handles_zero_tests(self):
        """format_test_results handles zero tests gracefully."""
        from swarm_attack.cli.display import format_test_results

        result = format_test_results(0, 0)
        assert "0" in result


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_duration_seconds(self):
        """format_duration shows seconds for short durations."""
        from swarm_attack.cli.display import format_duration

        result = format_duration(45.0)
        assert "45" in result or "s" in result

    def test_format_duration_minutes(self):
        """format_duration shows minutes for minute-scale durations."""
        from swarm_attack.cli.display import format_duration

        result = format_duration(150.0)  # 2m 30s
        assert "2" in result or "m" in result

    def test_format_duration_hours(self):
        """format_duration shows hours for hour-scale durations."""
        from swarm_attack.cli.display import format_duration

        result = format_duration(3720.0)  # 1h 2m
        assert "1" in result or "h" in result


class TestFormatFindingsSummary:
    """Tests for format_findings_summary function."""

    def test_format_findings_summary_critical_warning(self):
        """format_findings_summary shows critical/moderate/minor counts."""
        from swarm_attack.cli.display import format_findings_summary

        result = format_findings_summary(2, 3, 5)
        # Should contain the counts
        assert "2" in result or "critical" in result.lower()


class TestFormatQaSessionTable:
    """Tests for format_qa_session_table function."""

    def test_format_qa_session_table_has_tests_column(self):
        """format_qa_session_table includes Tests column."""
        from swarm_attack.cli.display import format_qa_session_table
        from swarm_attack.qa.models import (
            QASession, QATrigger, QADepth, QAStatus, QAContext, QAResult
        )

        session = QASession(
            session_id="qa-test-001",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(tests_run=10, tests_passed=8),
        )

        table = format_qa_session_table([session])

        # Check table has Tests column
        column_names = [col.header for col in table.columns]
        assert any("test" in str(name).lower() for name in column_names)

    def test_format_qa_session_table_has_findings_column(self):
        """format_qa_session_table includes Findings column."""
        from swarm_attack.cli.display import format_qa_session_table
        from swarm_attack.qa.models import (
            QASession, QATrigger, QADepth, QAStatus, QAContext, QAResult
        )

        session = QASession(
            session_id="qa-test-002",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(critical_count=1, moderate_count=2),
        )

        table = format_qa_session_table([session])

        column_names = [col.header for col in table.columns]
        assert any("finding" in str(name).lower() for name in column_names)

    def test_format_qa_session_table_has_duration_column(self):
        """format_qa_session_table includes Duration column."""
        from swarm_attack.cli.display import format_qa_session_table
        from swarm_attack.qa.models import (
            QASession, QATrigger, QADepth, QAStatus, QAContext
        )

        session = QASession(
            session_id="qa-test-003",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            started_at="2025-01-01T10:00:00Z",
            completed_at="2025-01-01T10:05:00Z",
        )

        table = format_qa_session_table([session])

        column_names = [col.header for col in table.columns]
        assert any("duration" in str(name).lower() for name in column_names)

    def test_format_qa_session_table_has_depth_column(self):
        """format_qa_session_table includes Depth column."""
        from swarm_attack.cli.display import format_qa_session_table
        from swarm_attack.qa.models import (
            QASession, QATrigger, QADepth, QAStatus, QAContext
        )

        session = QASession(
            session_id="qa-test-004",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
        )

        table = format_qa_session_table([session])

        column_names = [col.header for col in table.columns]
        assert any("depth" in str(name).lower() for name in column_names)
