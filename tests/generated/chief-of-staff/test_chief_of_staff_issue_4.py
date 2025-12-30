"""Tests for DailyLogManager - persistence for daily logs and decisions."""

import json
import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from swarm_attack.chief_of_staff.daily_log import (
    DailyLogManager,
    DailyLog,
    StandupSession,
    WorkLogEntry,
    DailySummary,
    Decision,
    DecisionType,
)


class TestDailyLogManagerInit:
    """Tests for DailyLogManager initialization."""

    def test_init_creates_instance(self, tmp_path):
        """Init should create manager with base path."""
        manager = DailyLogManager(tmp_path)
        assert manager.base_path == tmp_path

    def test_init_creates_directory_if_not_exists(self, tmp_path):
        """Init should create storage directory if it doesn't exist."""
        log_path = tmp_path / "daily-log"
        manager = DailyLogManager(log_path)
        assert log_path.exists()

    def test_init_with_existing_directory(self, tmp_path):
        """Init should work with existing directory."""
        log_path = tmp_path / "daily-log"
        log_path.mkdir(parents=True)
        manager = DailyLogManager(log_path)
        assert manager.base_path == log_path


class TestGetLog:
    """Tests for get_log method."""

    def test_get_log_returns_none_for_nonexistent(self, tmp_path):
        """get_log should return None if log doesn't exist."""
        manager = DailyLogManager(tmp_path)
        result = manager.get_log(date(2025, 1, 15))
        assert result is None

    def test_get_log_returns_log_for_existing(self, tmp_path):
        """get_log should return DailyLog if it exists."""
        manager = DailyLogManager(tmp_path)
        test_date = date(2025, 1, 15)
        
        # Create a log file
        log = DailyLog(date=test_date)
        manager.save_log(log)
        
        result = manager.get_log(test_date)
        assert result is not None
        assert result.date == test_date

    def test_get_log_loads_from_json(self, tmp_path):
        """get_log should load from JSON file."""
        manager = DailyLogManager(tmp_path)
        test_date = date(2025, 1, 15)
        
        # Manually create JSON file
        json_path = tmp_path / "2025-01-15.json"
        log_data = {
            "date": "2025-01-15",
            "standups": [],
            "work_entries": [],
            "summary": None,
        }
        json_path.write_text(json.dumps(log_data))
        
        result = manager.get_log(test_date)
        assert result is not None
        assert result.date == test_date


class TestGetToday:
    """Tests for get_today method."""

    def test_get_today_creates_if_not_exists(self, tmp_path):
        """get_today should create new log if none exists."""
        manager = DailyLogManager(tmp_path)
        result = manager.get_today()
        
        assert result is not None
        assert result.date == date.today()

    def test_get_today_returns_existing(self, tmp_path):
        """get_today should return existing log."""
        manager = DailyLogManager(tmp_path)
        
        # Create today's log with a standup
        first_result = manager.get_today()
        standup = StandupSession(
            timestamp=datetime.now(),
            completed_yesterday=["task1"],
            planned_today=["task2"],
            blockers=[],
        )
        manager.add_standup(standup)
        
        # Get again
        second_result = manager.get_today()
        assert len(second_result.standups) == 1


class TestGetYesterday:
    """Tests for get_yesterday method."""

    def test_get_yesterday_returns_none_if_not_exists(self, tmp_path):
        """get_yesterday should return None if no log exists."""
        manager = DailyLogManager(tmp_path)
        result = manager.get_yesterday()
        assert result is None

    def test_get_yesterday_returns_log_if_exists(self, tmp_path):
        """get_yesterday should return log if it exists."""
        manager = DailyLogManager(tmp_path)
        yesterday = date.today() - timedelta(days=1)
        
        # Create yesterday's log
        log = DailyLog(date=yesterday)
        manager.save_log(log)
        
        result = manager.get_yesterday()
        assert result is not None
        assert result.date == yesterday


class TestSaveLog:
    """Tests for save_log method."""

    def test_save_log_creates_json_file(self, tmp_path):
        """save_log should create JSON file."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(date=date(2025, 1, 15))
        
        manager.save_log(log)
        
        json_path = tmp_path / "2025-01-15.json"
        assert json_path.exists()

    def test_save_log_creates_md_file(self, tmp_path):
        """save_log should create markdown file."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(date=date(2025, 1, 15))
        
        manager.save_log(log)
        
        md_path = tmp_path / "2025-01-15.md"
        assert md_path.exists()

    def test_save_log_json_is_valid(self, tmp_path):
        """save_log should write valid JSON."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(date=date(2025, 1, 15))
        
        manager.save_log(log)
        
        json_path = tmp_path / "2025-01-15.json"
        data = json.loads(json_path.read_text())
        assert data["date"] == "2025-01-15"

    def test_save_log_atomic_write(self, tmp_path):
        """save_log should use atomic write pattern."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(date=date(2025, 1, 15))
        
        # Save should not leave temp files
        manager.save_log(log)
        
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_save_log_overwrites_existing(self, tmp_path):
        """save_log should overwrite existing log."""
        manager = DailyLogManager(tmp_path)
        test_date = date(2025, 1, 15)
        
        # Save initial
        log1 = DailyLog(date=test_date)
        manager.save_log(log1)
        
        # Save updated with standup
        log2 = DailyLog(
            date=test_date,
            standups=[
                StandupSession(
                    timestamp=datetime.now(),
                    completed_yesterday=["task"],
                    planned_today=[],
                    blockers=[],
                )
            ],
        )
        manager.save_log(log2)
        
        # Load and verify
        result = manager.get_log(test_date)
        assert len(result.standups) == 1


class TestAddStandup:
    """Tests for add_standup method."""

    def test_add_standup_to_today(self, tmp_path):
        """add_standup should add to today's log."""
        manager = DailyLogManager(tmp_path)
        standup = StandupSession(
            timestamp=datetime.now(),
            completed_yesterday=["completed task"],
            planned_today=["planned task"],
            blockers=["blocker"],
        )
        
        manager.add_standup(standup)
        
        log = manager.get_today()
        assert len(log.standups) == 1
        assert log.standups[0].completed_yesterday == ["completed task"]

    def test_add_multiple_standups(self, tmp_path):
        """add_standup should allow multiple standups per day."""
        manager = DailyLogManager(tmp_path)
        
        standup1 = StandupSession(
            timestamp=datetime.now(),
            completed_yesterday=["task1"],
            planned_today=["plan1"],
            blockers=[],
        )
        standup2 = StandupSession(
            timestamp=datetime.now(),
            completed_yesterday=["task2"],
            planned_today=["plan2"],
            blockers=[],
        )
        
        manager.add_standup(standup1)
        manager.add_standup(standup2)
        
        log = manager.get_today()
        assert len(log.standups) == 2


class TestAddWorkEntry:
    """Tests for add_work_entry method."""

    def test_add_work_entry_to_today(self, tmp_path):
        """add_work_entry should add to today's log."""
        manager = DailyLogManager(tmp_path)
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            description="Implemented feature X",
            duration_minutes=60,
            category="development",
        )
        
        manager.add_work_entry(entry)
        
        log = manager.get_today()
        assert len(log.work_entries) == 1
        assert log.work_entries[0].description == "Implemented feature X"

    def test_add_multiple_work_entries(self, tmp_path):
        """add_work_entry should allow multiple entries."""
        manager = DailyLogManager(tmp_path)
        
        entry1 = WorkLogEntry(
            timestamp=datetime.now(),
            description="Task 1",
            duration_minutes=30,
            category="dev",
        )
        entry2 = WorkLogEntry(
            timestamp=datetime.now(),
            description="Task 2",
            duration_minutes=45,
            category="review",
        )
        
        manager.add_work_entry(entry1)
        manager.add_work_entry(entry2)
        
        log = manager.get_today()
        assert len(log.work_entries) == 2


class TestSetSummary:
    """Tests for set_summary method."""

    def test_set_summary_on_today(self, tmp_path):
        """set_summary should set summary on today's log."""
        manager = DailyLogManager(tmp_path)
        summary = DailySummary(
            highlights=["highlight1"],
            challenges=["challenge1"],
            tomorrow_priorities=["priority1"],
            notes="End of day notes",
        )
        
        manager.set_summary(summary)
        
        log = manager.get_today()
        assert log.summary is not None
        assert log.summary.highlights == ["highlight1"]

    def test_set_summary_overwrites_existing(self, tmp_path):
        """set_summary should overwrite existing summary."""
        manager = DailyLogManager(tmp_path)
        
        summary1 = DailySummary(
            highlights=["old"],
            challenges=[],
            tomorrow_priorities=[],
            notes="",
        )
        summary2 = DailySummary(
            highlights=["new"],
            challenges=[],
            tomorrow_priorities=[],
            notes="",
        )
        
        manager.set_summary(summary1)
        manager.set_summary(summary2)
        
        log = manager.get_today()
        assert log.summary.highlights == ["new"]


class TestAppendDecision:
    """Tests for append_decision method."""

    def test_append_decision_creates_jsonl(self, tmp_path):
        """append_decision should create decisions.jsonl if not exists."""
        manager = DailyLogManager(tmp_path)
        decision = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.PRIORITY,
            description="Focus on feature X",
            reasoning="High impact",
            context={},
        )
        
        manager.append_decision(decision)
        
        jsonl_path = tmp_path / "decisions.jsonl"
        assert jsonl_path.exists()

    def test_append_decision_writes_valid_json(self, tmp_path):
        """append_decision should write valid JSON line."""
        manager = DailyLogManager(tmp_path)
        decision = Decision(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            decision_type=DecisionType.PRIORITY,
            description="Test decision",
            reasoning="Test reasoning",
            context={"key": "value"},
        )
        
        manager.append_decision(decision)
        
        jsonl_path = tmp_path / "decisions.jsonl"
        line = jsonl_path.read_text().strip()
        data = json.loads(line)
        assert data["description"] == "Test decision"
        assert data["decision_type"] == "priority"

    def test_append_multiple_decisions(self, tmp_path):
        """append_decision should append to existing file."""
        manager = DailyLogManager(tmp_path)
        
        decision1 = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.PRIORITY,
            description="Decision 1",
            reasoning="Reason 1",
            context={},
        )
        decision2 = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.ESCALATION,
            description="Decision 2",
            reasoning="Reason 2",
            context={},
        )
        
        manager.append_decision(decision1)
        manager.append_decision(decision2)
        
        jsonl_path = tmp_path / "decisions.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 2


class TestGetDecisions:
    """Tests for get_decisions method."""

    def test_get_decisions_empty_file(self, tmp_path):
        """get_decisions should return empty list if no decisions."""
        manager = DailyLogManager(tmp_path)
        result = manager.get_decisions()
        assert result == []

    def test_get_decisions_all(self, tmp_path):
        """get_decisions should return all decisions."""
        manager = DailyLogManager(tmp_path)
        
        decision1 = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.PRIORITY,
            description="Decision 1",
            reasoning="Reason 1",
            context={},
        )
        decision2 = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.ESCALATION,
            description="Decision 2",
            reasoning="Reason 2",
            context={},
        )
        
        manager.append_decision(decision1)
        manager.append_decision(decision2)
        
        result = manager.get_decisions()
        assert len(result) == 2

    def test_get_decisions_since_date(self, tmp_path):
        """get_decisions should filter by since date."""
        manager = DailyLogManager(tmp_path)
        
        old_decision = Decision(
            timestamp=datetime(2025, 1, 10, 10, 0, 0),
            decision_type=DecisionType.PRIORITY,
            description="Old",
            reasoning="Old",
            context={},
        )
        new_decision = Decision(
            timestamp=datetime(2025, 1, 20, 10, 0, 0),
            decision_type=DecisionType.PRIORITY,
            description="New",
            reasoning="New",
            context={},
        )
        
        manager.append_decision(old_decision)
        manager.append_decision(new_decision)
        
        result = manager.get_decisions(since=datetime(2025, 1, 15))
        assert len(result) == 1
        assert result[0].description == "New"

    def test_get_decisions_by_type(self, tmp_path):
        """get_decisions should filter by decision type."""
        manager = DailyLogManager(tmp_path)
        
        priority_decision = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.PRIORITY,
            description="Priority",
            reasoning="Reason",
            context={},
        )
        escalation_decision = Decision(
            timestamp=datetime.now(),
            decision_type=DecisionType.ESCALATION,
            description="Escalation",
            reasoning="Reason",
            context={},
        )
        
        manager.append_decision(priority_decision)
        manager.append_decision(escalation_decision)
        
        result = manager.get_decisions(decision_type=DecisionType.PRIORITY)
        assert len(result) == 1
        assert result[0].decision_type == DecisionType.PRIORITY


class TestGetHistory:
    """Tests for get_history method."""

    def test_get_history_empty(self, tmp_path):
        """get_history should return empty list if no logs."""
        manager = DailyLogManager(tmp_path)
        result = manager.get_history(7)
        assert result == []

    def test_get_history_returns_existing_logs(self, tmp_path):
        """get_history should return existing logs for date range."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        log_today = DailyLog(date=today)
        log_yesterday = DailyLog(date=yesterday)
        
        manager.save_log(log_today)
        manager.save_log(log_yesterday)
        
        result = manager.get_history(7)
        assert len(result) == 2

    def test_get_history_respects_days_limit(self, tmp_path):
        """get_history should only return logs within days limit."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        old_date = today - timedelta(days=10)
        
        log_today = DailyLog(date=today)
        log_old = DailyLog(date=old_date)
        
        manager.save_log(log_today)
        manager.save_log(log_old)
        
        result = manager.get_history(7)
        assert len(result) == 1
        assert result[0].date == today

    def test_get_history_sorted_by_date(self, tmp_path):
        """get_history should return logs sorted by date descending."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)
        
        # Save in random order
        manager.save_log(DailyLog(date=yesterday))
        manager.save_log(DailyLog(date=today))
        manager.save_log(DailyLog(date=day_before))
        
        result = manager.get_history(7)
        assert len(result) == 3
        assert result[0].date == today
        assert result[1].date == yesterday
        assert result[2].date == day_before


class TestGenerateWeeklySummary:
    """Tests for generate_weekly_summary method."""

    def test_generate_weekly_summary_returns_markdown(self, tmp_path):
        """generate_weekly_summary should return markdown string."""
        manager = DailyLogManager(tmp_path)
        
        # Create some logs for the week
        today = date.today()
        log = DailyLog(date=today)
        manager.save_log(log)
        
        result = manager.generate_weekly_summary(
            week=today.isocalendar()[1],
            year=today.year,
        )
        
        assert isinstance(result, str)
        assert "Week" in result

    def test_generate_weekly_summary_includes_highlights(self, tmp_path):
        """generate_weekly_summary should include day highlights."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        log = DailyLog(
            date=today,
            summary=DailySummary(
                highlights=["Major achievement"],
                challenges=[],
                tomorrow_priorities=[],
                notes="",
            ),
        )
        manager.save_log(log)
        
        result = manager.generate_weekly_summary(
            week=today.isocalendar()[1],
            year=today.year,
        )
        
        assert "Major achievement" in result

    def test_generate_weekly_summary_empty_week(self, tmp_path):
        """generate_weekly_summary should handle empty week."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.generate_weekly_summary(week=1, year=2025)
        
        assert isinstance(result, str)
        assert "Week 1" in result


class TestEdgeCases:
    """Tests for edge cases."""

    def test_first_run_no_files(self, tmp_path):
        """Should handle first run with no existing files."""
        log_path = tmp_path / "new-log-dir"
        manager = DailyLogManager(log_path)
        
        # Should not raise
        assert manager.get_log(date.today()) is None
        assert manager.get_decisions() == []
        assert manager.get_history(7) == []

    def test_corrupted_json_file(self, tmp_path):
        """Should handle corrupted JSON file gracefully."""
        manager = DailyLogManager(tmp_path)
        
        # Create corrupted JSON
        json_path = tmp_path / "2025-01-15.json"
        json_path.write_text("not valid json {{{")
        
        # Should return None or raise appropriate error
        result = manager.get_log(date(2025, 1, 15))
        assert result is None

    def test_corrupted_jsonl_line(self, tmp_path):
        """Should handle corrupted JSONL line gracefully."""
        manager = DailyLogManager(tmp_path)
        
        # Create JSONL with one corrupted line
        jsonl_path = tmp_path / "decisions.jsonl"
        valid_decision = {
            "timestamp": "2025-01-15T10:00:00",
            "decision_type": "priority",
            "description": "Valid",
            "reasoning": "Valid",
            "context": {},
        }
        jsonl_path.write_text(
            json.dumps(valid_decision) + "\n" + "corrupted line\n"
        )
        
        # Should skip corrupted line and return valid ones
        result = manager.get_decisions()
        assert len(result) == 1
        assert result[0].description == "Valid"

    def test_missing_md_file_but_json_exists(self, tmp_path):
        """Should load from JSON even if MD is missing."""
        manager = DailyLogManager(tmp_path)
        
        # Create only JSON
        json_path = tmp_path / "2025-01-15.json"
        log_data = {
            "date": "2025-01-15",
            "standups": [],
            "work_entries": [],
            "summary": None,
        }
        json_path.write_text(json.dumps(log_data))
        
        result = manager.get_log(date(2025, 1, 15))
        assert result is not None


class TestDailyLogModel:
    """Tests for DailyLog dataclass."""

    def test_daily_log_from_dict(self):
        """DailyLog should have from_dict method."""
        data = {
            "date": "2025-01-15",
            "standups": [],
            "work_entries": [],
            "summary": None,
        }
        log = DailyLog.from_dict(data)
        assert log.date == date(2025, 1, 15)

    def test_daily_log_to_dict(self):
        """DailyLog should have to_dict method."""
        log = DailyLog(date=date(2025, 1, 15))
        data = log.to_dict()
        assert data["date"] == "2025-01-15"
        assert "standups" in data
        assert "work_entries" in data

    def test_daily_log_roundtrip(self):
        """DailyLog should roundtrip through dict."""
        original = DailyLog(
            date=date(2025, 1, 15),
            standups=[
                StandupSession(
                    timestamp=datetime(2025, 1, 15, 9, 0, 0),
                    completed_yesterday=["task"],
                    planned_today=["plan"],
                    blockers=[],
                )
            ],
            work_entries=[],
            summary=None,
        )
        roundtrip = DailyLog.from_dict(original.to_dict())
        assert roundtrip.date == original.date
        assert len(roundtrip.standups) == 1


class TestStandupSessionModel:
    """Tests for StandupSession dataclass."""

    def test_standup_from_dict(self):
        """StandupSession should have from_dict method."""
        data = {
            "timestamp": "2025-01-15T09:00:00",
            "completed_yesterday": ["task1"],
            "planned_today": ["task2"],
            "blockers": ["blocker1"],
        }
        standup = StandupSession.from_dict(data)
        assert standup.completed_yesterday == ["task1"]

    def test_standup_to_dict(self):
        """StandupSession should have to_dict method."""
        standup = StandupSession(
            timestamp=datetime(2025, 1, 15, 9, 0, 0),
            completed_yesterday=["task1"],
            planned_today=["task2"],
            blockers=[],
        )
        data = standup.to_dict()
        assert "timestamp" in data
        assert data["completed_yesterday"] == ["task1"]


class TestWorkLogEntryModel:
    """Tests for WorkLogEntry dataclass."""

    def test_work_entry_from_dict(self):
        """WorkLogEntry should have from_dict method."""
        data = {
            "timestamp": "2025-01-15T10:00:00",
            "description": "Did work",
            "duration_minutes": 60,
            "category": "dev",
        }
        entry = WorkLogEntry.from_dict(data)
        assert entry.description == "Did work"
        assert entry.duration_minutes == 60

    def test_work_entry_to_dict(self):
        """WorkLogEntry should have to_dict method."""
        entry = WorkLogEntry(
            timestamp=datetime(2025, 1, 15, 10, 0, 0),
            description="Did work",
            duration_minutes=60,
            category="dev",
        )
        data = entry.to_dict()
        assert data["description"] == "Did work"


class TestDailySummaryModel:
    """Tests for DailySummary dataclass."""

    def test_summary_from_dict(self):
        """DailySummary should have from_dict method."""
        data = {
            "highlights": ["highlight"],
            "challenges": ["challenge"],
            "tomorrow_priorities": ["priority"],
            "notes": "notes",
        }
        summary = DailySummary.from_dict(data)
        assert summary.highlights == ["highlight"]

    def test_summary_to_dict(self):
        """DailySummary should have to_dict method."""
        summary = DailySummary(
            highlights=["highlight"],
            challenges=["challenge"],
            tomorrow_priorities=["priority"],
            notes="notes",
        )
        data = summary.to_dict()
        assert data["highlights"] == ["highlight"]


class TestDecisionModel:
    """Tests for Decision dataclass."""

    def test_decision_from_dict(self):
        """Decision should have from_dict method."""
        data = {
            "timestamp": "2025-01-15T10:00:00",
            "decision_type": "priority",
            "description": "desc",
            "reasoning": "reason",
            "context": {"key": "value"},
        }
        decision = Decision.from_dict(data)
        assert decision.description == "desc"
        assert decision.decision_type == DecisionType.PRIORITY

    def test_decision_to_dict(self):
        """Decision should have to_dict method."""
        decision = Decision(
            timestamp=datetime(2025, 1, 15, 10, 0, 0),
            decision_type=DecisionType.ESCALATION,
            description="desc",
            reasoning="reason",
            context={},
        )
        data = decision.to_dict()
        assert data["decision_type"] == "escalation"


class TestDecisionTypeEnum:
    """Tests for DecisionType enum."""

    def test_decision_type_priority(self):
        """DecisionType should have PRIORITY value."""
        assert DecisionType.PRIORITY.value == "priority"

    def test_decision_type_escalation(self):
        """DecisionType should have ESCALATION value."""
        assert DecisionType.ESCALATION.value == "escalation"

    def test_decision_type_deferral(self):
        """DecisionType should have DEFERRAL value."""
        assert DecisionType.DEFERRAL.value == "deferral"

    def test_decision_type_assignment(self):
        """DecisionType should have ASSIGNMENT value."""
        assert DecisionType.ASSIGNMENT.value == "assignment"


class TestMarkdownGeneration:
    """Tests for markdown file generation."""

    def test_save_log_md_has_title(self, tmp_path):
        """Saved markdown should have date title."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(date=date(2025, 1, 15))
        manager.save_log(log)
        
        md_path = tmp_path / "2025-01-15.md"
        content = md_path.read_text()
        assert "2025-01-15" in content

    def test_save_log_md_has_standups_section(self, tmp_path):
        """Saved markdown should include standups."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(
            date=date(2025, 1, 15),
            standups=[
                StandupSession(
                    timestamp=datetime(2025, 1, 15, 9, 0, 0),
                    completed_yesterday=["Finished feature X"],
                    planned_today=["Start feature Y"],
                    blockers=["Waiting on review"],
                )
            ],
        )
        manager.save_log(log)
        
        md_path = tmp_path / "2025-01-15.md"
        content = md_path.read_text()
        assert "Standup" in content or "standup" in content.lower()
        assert "Finished feature X" in content

    def test_save_log_md_has_work_entries(self, tmp_path):
        """Saved markdown should include work entries."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(
            date=date(2025, 1, 15),
            work_entries=[
                WorkLogEntry(
                    timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    description="Implemented auth module",
                    duration_minutes=120,
                    category="development",
                )
            ],
        )
        manager.save_log(log)
        
        md_path = tmp_path / "2025-01-15.md"
        content = md_path.read_text()
        assert "Implemented auth module" in content

    def test_save_log_md_has_summary(self, tmp_path):
        """Saved markdown should include summary."""
        manager = DailyLogManager(tmp_path)
        log = DailyLog(
            date=date(2025, 1, 15),
            summary=DailySummary(
                highlights=["Completed major milestone"],
                challenges=["CI was flaky"],
                tomorrow_priorities=["Deploy to staging"],
                notes="Good productive day",
            ),
        )
        manager.save_log(log)
        
        md_path = tmp_path / "2025-01-15.md"
        content = md_path.read_text()
        assert "Completed major milestone" in content
        assert "CI was flaky" in content