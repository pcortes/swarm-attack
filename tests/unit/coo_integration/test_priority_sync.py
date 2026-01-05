"""
Unit tests for COO Priority Sync module.

TDD RED Phase - All tests should FAIL initially.

This module tests the integration between swarm-attack and COO (Chief Operating Officer)
for priority synchronization:
1. Push completed specs to COO archive
2. Pull priority rankings from COO board
3. Enforce budget limits from COO config
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from swarm_attack.coo_integration.priority_sync import (
    COOClient,
    COOConfig,
    COOConnectionError,
    COOBudgetExceededError,
    COOSyncError,
    COOValidationError,
    PriorityRanking,
    PrioritySyncManager,
    SpecPushResult,
    SyncDirection,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def coo_config():
    """Create a COOConfig for testing."""
    return COOConfig(
        coo_path="/Users/test/coo",
        project_name="swarm-attack",
        daily_budget_limit=100.0,
        monthly_budget_limit=2500.0,
        sync_enabled=True,
    )


@pytest.fixture
def mock_coo_client(coo_config):
    """Create a mock COO client."""
    client = Mock(spec=COOClient)
    client.config = coo_config
    client.is_connected.return_value = True
    return client


@pytest.fixture
def sync_manager(coo_config, mock_coo_client):
    """Create a PrioritySyncManager with mock client."""
    return PrioritySyncManager(config=coo_config, client=mock_coo_client)


@pytest.fixture
def sample_spec_content():
    """Sample spec content for testing."""
    return """# Feature Spec: Adaptive QA Agent

Date: 2026-01-05

## Overview
This spec describes the adaptive QA agent implementation.

## Requirements
1. Automatic test generation
2. Coverage tracking
3. Bug detection

## Implementation Notes
- TDD approach required
- All tests must pass before merge
"""


@pytest.fixture
def sample_priority_rankings():
    """Sample priority rankings from COO board."""
    return [
        PriorityRanking(
            name="Adaptive QA Agent",
            rank=1,
            effort="L",
            why="Critical for test automation",
            score=9.5,
            dependencies=[],
        ),
        PriorityRanking(
            name="Memory Store Integration",
            rank=2,
            effort="M",
            why="Enables learning from past decisions",
            score=8.2,
            dependencies=["Adaptive QA Agent"],
        ),
        PriorityRanking(
            name="Dashboard v2",
            rank=3,
            effort="S",
            why="Improved visibility",
            score=7.0,
            dependencies=[],
        ),
    ]


# =============================================================================
# TestPriorityPush: Test pushing specs to COO
# =============================================================================


class TestPriorityPush:
    """Tests for pushing completed specs to COO archive."""

    def test_push_spec_success(self, sync_manager, sample_spec_content):
        """Test successful spec push to COO."""
        result = sync_manager.push_spec(
            spec_name="adaptive-qa-agent",
            spec_content=sample_spec_content,
            category="specs",
        )

        assert result.success is True
        assert result.archived_path is not None
        assert "2026-01-05" in result.archived_path
        assert "adaptive-qa-agent" in result.archived_path
        assert result.error is None

    def test_push_spec_with_date_extraction(self, sync_manager, sample_spec_content):
        """Test that push extracts date from spec content."""
        result = sync_manager.push_spec(
            spec_name="test-spec",
            spec_content=sample_spec_content,
            category="specs",
        )

        # Should extract "2026-01-05" from content
        assert "2026-01-05" in result.archived_path

    def test_push_spec_uses_today_when_no_date(self, sync_manager):
        """Test that push uses today's date when no date in content."""
        content_no_date = """# Feature Spec: No Date Spec

## Overview
This spec has no date header.
"""
        result = sync_manager.push_spec(
            spec_name="no-date-spec",
            spec_content=content_no_date,
            category="specs",
        )

        today = datetime.now().strftime("%Y-%m-%d")
        assert today in result.archived_path

    def test_push_prompt_to_prompts_category(self, sync_manager):
        """Test pushing a prompt to the prompts category."""
        prompt_content = """# Implementation Prompt

## Task
Implement the adaptive QA agent.
"""
        result = sync_manager.push_spec(
            spec_name="adaptive-qa-prompt",
            spec_content=prompt_content,
            category="prompts",
        )

        assert result.success is True
        assert "/prompts/" in result.archived_path

    def test_push_updates_index(self, sync_manager, sample_spec_content, mock_coo_client):
        """Test that push updates INDEX.md."""
        sync_manager.push_spec(
            spec_name="indexed-spec",
            spec_content=sample_spec_content,
            category="specs",
        )

        mock_coo_client.update_index.assert_called_once()
        call_args = mock_coo_client.update_index.call_args
        assert "indexed-spec" in str(call_args)

    def test_push_validates_content_not_empty(self, sync_manager):
        """Test that push rejects empty content."""
        with pytest.raises(COOValidationError) as exc_info:
            sync_manager.push_spec(
                spec_name="empty-spec",
                spec_content="",
                category="specs",
            )

        assert "empty" in str(exc_info.value).lower()

    def test_push_validates_spec_name(self, sync_manager, sample_spec_content):
        """Test that push validates spec name format."""
        with pytest.raises(COOValidationError) as exc_info:
            sync_manager.push_spec(
                spec_name="",
                spec_content=sample_spec_content,
                category="specs",
            )

        assert "name" in str(exc_info.value).lower()

    def test_push_validates_category(self, sync_manager, sample_spec_content):
        """Test that push validates category is specs or prompts."""
        with pytest.raises(COOValidationError) as exc_info:
            sync_manager.push_spec(
                spec_name="test-spec",
                spec_content=sample_spec_content,
                category="invalid",
            )

        assert "category" in str(exc_info.value).lower()

    def test_push_handles_connection_error(self, sync_manager, sample_spec_content, mock_coo_client):
        """Test handling of connection errors during push."""
        mock_coo_client.is_connected.return_value = False

        with pytest.raises(COOConnectionError) as exc_info:
            sync_manager.push_spec(
                spec_name="conn-error-spec",
                spec_content=sample_spec_content,
                category="specs",
            )

        assert "connection" in str(exc_info.value).lower()

    def test_push_batch_specs(self, sync_manager, sample_spec_content):
        """Test pushing multiple specs in batch."""
        specs = [
            {"name": "spec-1", "content": sample_spec_content, "category": "specs"},
            {"name": "spec-2", "content": sample_spec_content, "category": "specs"},
            {"name": "prompt-1", "content": "# Prompt", "category": "prompts"},
        ]

        results = sync_manager.push_batch(specs)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_push_deduplicates_existing_spec(self, sync_manager, sample_spec_content, mock_coo_client):
        """Test that pushing existing spec updates instead of duplicating."""
        mock_coo_client.spec_exists.return_value = True

        result = sync_manager.push_spec(
            spec_name="existing-spec",
            spec_content=sample_spec_content,
            category="specs",
        )

        assert result.success is True
        assert result.updated is True
        assert result.created is False


# =============================================================================
# TestPriorityPull: Test pulling rankings from COO
# =============================================================================


class TestPriorityPull:
    """Tests for pulling priority rankings from COO board."""

    def test_pull_rankings_success(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test successful pull of priority rankings."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        rankings = sync_manager.pull_rankings()

        assert len(rankings) == 3
        assert rankings[0].name == "Adaptive QA Agent"
        assert rankings[0].rank == 1
        assert rankings[0].score == 9.5

    def test_pull_rankings_returns_sorted_by_rank(self, sync_manager, mock_coo_client):
        """Test that pulled rankings are sorted by rank."""
        unsorted = [
            PriorityRanking(name="Third", rank=3, effort="S", why="", score=5.0, dependencies=[]),
            PriorityRanking(name="First", rank=1, effort="L", why="", score=9.0, dependencies=[]),
            PriorityRanking(name="Second", rank=2, effort="M", why="", score=7.0, dependencies=[]),
        ]
        mock_coo_client.get_priority_rankings.return_value = unsorted

        rankings = sync_manager.pull_rankings()

        assert rankings[0].rank == 1
        assert rankings[1].rank == 2
        assert rankings[2].rank == 3

    def test_pull_rankings_filters_by_effort(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test filtering rankings by effort level."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        rankings = sync_manager.pull_rankings(effort_filter=["S", "M"])

        assert len(rankings) == 2
        assert all(r.effort in ["S", "M"] for r in rankings)

    def test_pull_rankings_with_dependency_resolution(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test that pulled rankings include resolved dependencies."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        rankings = sync_manager.pull_rankings(resolve_dependencies=True)

        memory_store = next(r for r in rankings if r.name == "Memory Store Integration")
        assert "Adaptive QA Agent" in memory_store.dependencies
        assert memory_store.dependency_status is not None

    def test_pull_top_n_rankings(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test pulling only top N rankings."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        rankings = sync_manager.pull_rankings(limit=2)

        assert len(rankings) == 2
        assert rankings[0].rank == 1
        assert rankings[1].rank == 2

    def test_pull_rankings_empty_board(self, sync_manager, mock_coo_client):
        """Test handling of empty priority board."""
        mock_coo_client.get_priority_rankings.return_value = []

        rankings = sync_manager.pull_rankings()

        assert rankings == []

    def test_pull_rankings_handles_connection_error(self, sync_manager, mock_coo_client):
        """Test handling of connection errors during pull."""
        mock_coo_client.is_connected.return_value = False

        with pytest.raises(COOConnectionError):
            sync_manager.pull_rankings()

    def test_pull_rankings_caches_results(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test that pulled rankings are cached."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        # First pull
        rankings1 = sync_manager.pull_rankings(use_cache=True)
        # Second pull should use cache
        rankings2 = sync_manager.pull_rankings(use_cache=True)

        mock_coo_client.get_priority_rankings.assert_called_once()
        assert rankings1 == rankings2

    def test_pull_rankings_bypasses_cache(self, sync_manager, mock_coo_client, sample_priority_rankings):
        """Test forcing fresh pull bypasses cache."""
        mock_coo_client.get_priority_rankings.return_value = sample_priority_rankings

        sync_manager.pull_rankings(use_cache=True)
        sync_manager.pull_rankings(use_cache=False)

        assert mock_coo_client.get_priority_rankings.call_count == 2

    def test_pull_specific_project_rankings(self, sync_manager, mock_coo_client):
        """Test pulling rankings for specific project."""
        sync_manager.pull_rankings(project="swarm-attack")

        mock_coo_client.get_priority_rankings.assert_called_with(project="swarm-attack")


# =============================================================================
# TestBudgetEnforcement: Test budget limits from COO config
# =============================================================================


class TestBudgetEnforcement:
    """Tests for budget limit enforcement from COO config."""

    def test_check_daily_budget_under_limit(self, sync_manager):
        """Test daily budget check when under limit."""
        result = sync_manager.check_budget(
            proposed_cost=50.0,
            budget_type="daily",
        )

        assert result.allowed is True
        assert result.remaining_budget > 0

    def test_check_daily_budget_exceeds_limit(self, sync_manager):
        """Test daily budget check when exceeds limit."""
        result = sync_manager.check_budget(
            proposed_cost=150.0,
            budget_type="daily",
        )

        assert result.allowed is False
        assert result.exceeded_by == 50.0  # 150 - 100 limit

    def test_check_monthly_budget_under_limit(self, sync_manager):
        """Test monthly budget check when under limit."""
        result = sync_manager.check_budget(
            proposed_cost=2000.0,
            budget_type="monthly",
        )

        assert result.allowed is True
        assert result.remaining_budget == 500.0  # 2500 - 2000

    def test_check_monthly_budget_exceeds_limit(self, sync_manager):
        """Test monthly budget check when exceeds limit."""
        result = sync_manager.check_budget(
            proposed_cost=3000.0,
            budget_type="monthly",
        )

        assert result.allowed is False
        assert result.exceeded_by == 500.0  # 3000 - 2500 limit

    def test_enforce_budget_raises_on_exceed(self, sync_manager):
        """Test that enforce_budget raises when limit exceeded."""
        with pytest.raises(COOBudgetExceededError) as exc_info:
            sync_manager.enforce_budget(
                proposed_cost=200.0,
                budget_type="daily",
            )

        assert "daily" in str(exc_info.value).lower()
        assert "200" in str(exc_info.value) or "100" in str(exc_info.value)

    def test_get_current_spend_daily(self, sync_manager, mock_coo_client):
        """Test getting current daily spend."""
        mock_coo_client.get_spend.return_value = 45.50

        spend = sync_manager.get_current_spend(budget_type="daily")

        assert spend == 45.50
        mock_coo_client.get_spend.assert_called_with(
            project="swarm-attack",
            period="daily",
        )

    def test_get_current_spend_monthly(self, sync_manager, mock_coo_client):
        """Test getting current monthly spend."""
        mock_coo_client.get_spend.return_value = 1250.00

        spend = sync_manager.get_current_spend(budget_type="monthly")

        assert spend == 1250.00
        mock_coo_client.get_spend.assert_called_with(
            project="swarm-attack",
            period="monthly",
        )

    def test_record_cost(self, sync_manager, mock_coo_client):
        """Test recording a cost to COO."""
        sync_manager.record_cost(
            amount=15.75,
            operation="feature_implementation",
            feature_id="adaptive-qa-agent",
        )

        mock_coo_client.record_cost.assert_called_once()
        call_args = mock_coo_client.record_cost.call_args
        assert call_args.kwargs["amount"] == 15.75
        assert call_args.kwargs["operation"] == "feature_implementation"

    def test_budget_check_includes_current_spend(self, sync_manager, mock_coo_client):
        """Test that budget check considers current spend."""
        mock_coo_client.get_spend.return_value = 80.0  # Already spent $80

        result = sync_manager.check_budget(
            proposed_cost=25.0,  # Want to spend $25 more
            budget_type="daily",
        )

        # 80 + 25 = 105 > 100 limit
        assert result.allowed is False
        assert result.exceeded_by == 5.0

    def test_budget_check_with_zero_current_spend(self, sync_manager, mock_coo_client):
        """Test budget check with no prior spend."""
        mock_coo_client.get_spend.return_value = 0.0

        result = sync_manager.check_budget(
            proposed_cost=50.0,
            budget_type="daily",
        )

        assert result.allowed is True
        assert result.remaining_budget == 50.0  # 100 - 50

    def test_budget_disabled_allows_all(self, coo_config, mock_coo_client):
        """Test that disabled sync allows all operations."""
        coo_config.sync_enabled = False
        manager = PrioritySyncManager(config=coo_config, client=mock_coo_client)

        result = manager.check_budget(
            proposed_cost=10000.0,
            budget_type="daily",
        )

        assert result.allowed is True

    def test_get_budget_summary(self, sync_manager, mock_coo_client):
        """Test getting full budget summary."""
        mock_coo_client.get_spend.side_effect = [45.0, 1200.0]  # daily, monthly

        summary = sync_manager.get_budget_summary()

        assert summary["daily"]["spent"] == 45.0
        assert summary["daily"]["limit"] == 100.0
        assert summary["daily"]["remaining"] == 55.0
        assert summary["monthly"]["spent"] == 1200.0
        assert summary["monthly"]["limit"] == 2500.0
        assert summary["monthly"]["remaining"] == 1300.0


# =============================================================================
# TestSyncErrors: Test error handling
# =============================================================================


class TestSyncErrors:
    """Tests for error handling in priority sync."""

    def test_connection_error_on_invalid_path(self):
        """Test connection error when COO path is invalid."""
        config = COOConfig(
            coo_path="/nonexistent/path",
            project_name="test",
            daily_budget_limit=100.0,
            monthly_budget_limit=2500.0,
            sync_enabled=True,
        )

        with pytest.raises(COOConnectionError) as exc_info:
            COOClient(config)

        assert "path" in str(exc_info.value).lower()

    def test_sync_error_on_corrupted_index(self, sync_manager, mock_coo_client):
        """Test handling of corrupted INDEX.md."""
        mock_coo_client.update_index.side_effect = COOSyncError("INDEX.md corrupted")

        with pytest.raises(COOSyncError) as exc_info:
            sync_manager.push_spec(
                spec_name="test",
                spec_content="# Test",
                category="specs",
            )

        assert "INDEX.md" in str(exc_info.value)

    def test_validation_error_includes_field_name(self, sync_manager):
        """Test validation errors include problematic field."""
        with pytest.raises(COOValidationError) as exc_info:
            sync_manager.push_spec(
                spec_name="valid-name",
                spec_content="",
                category="specs",
            )

        assert exc_info.value.field == "spec_content"

    def test_budget_error_includes_limit_info(self, sync_manager, mock_coo_client):
        """Test budget exceeded errors include limit information."""
        mock_coo_client.get_spend.return_value = 0.0

        with pytest.raises(COOBudgetExceededError) as exc_info:
            sync_manager.enforce_budget(
                proposed_cost=150.0,
                budget_type="daily",
            )

        error = exc_info.value
        assert error.proposed == 150.0
        assert error.limit == 100.0
        assert error.budget_type == "daily"

    def test_timeout_on_slow_coo_response(self, coo_config):
        """Test timeout handling for slow COO responses."""
        coo_config.timeout_seconds = 1

        with patch("swarm_attack.coo_integration.priority_sync.COOClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get_priority_rankings.side_effect = TimeoutError("COO response timeout")

            manager = PrioritySyncManager(config=coo_config, client=mock_instance)

            with pytest.raises(COOConnectionError) as exc_info:
                manager.pull_rankings()

            assert "timeout" in str(exc_info.value).lower()

    def test_retry_on_transient_error(self, sync_manager, mock_coo_client, sample_spec_content):
        """Test retry behavior on transient errors."""
        mock_coo_client.write_spec.side_effect = [
            COOConnectionError("Transient network error"),
            COOConnectionError("Still failing"),
            SpecPushResult(success=True, archived_path="/path/to/spec.md"),
        ]

        result = sync_manager.push_spec(
            spec_name="retry-spec",
            spec_content=sample_spec_content,
            category="specs",
            max_retries=3,
        )

        assert result.success is True
        assert mock_coo_client.write_spec.call_count == 3

    def test_no_retry_on_validation_error(self, sync_manager, mock_coo_client, sample_spec_content):
        """Test that validation errors are not retried."""
        mock_coo_client.write_spec.side_effect = COOValidationError("Invalid spec format")

        with pytest.raises(COOValidationError):
            sync_manager.push_spec(
                spec_name="invalid-spec",
                spec_content=sample_spec_content,
                category="specs",
                max_retries=3,
            )

        # Should only try once, not retry
        mock_coo_client.write_spec.assert_called_once()

    def test_partial_batch_failure(self, sync_manager, mock_coo_client, sample_spec_content):
        """Test handling of partial failures in batch push."""
        mock_coo_client.write_spec.side_effect = [
            SpecPushResult(success=True, archived_path="/path/1.md"),
            COOSyncError("Disk full"),
            SpecPushResult(success=True, archived_path="/path/3.md"),
        ]

        specs = [
            {"name": "spec-1", "content": sample_spec_content, "category": "specs"},
            {"name": "spec-2", "content": sample_spec_content, "category": "specs"},
            {"name": "spec-3", "content": sample_spec_content, "category": "specs"},
        ]

        results = sync_manager.push_batch(specs, fail_fast=False)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

    def test_fail_fast_batch(self, sync_manager, mock_coo_client, sample_spec_content):
        """Test fail-fast behavior in batch push."""
        mock_coo_client.write_spec.side_effect = [
            SpecPushResult(success=True, archived_path="/path/1.md"),
            COOSyncError("Disk full"),
            SpecPushResult(success=True, archived_path="/path/3.md"),
        ]

        specs = [
            {"name": "spec-1", "content": sample_spec_content, "category": "specs"},
            {"name": "spec-2", "content": sample_spec_content, "category": "specs"},
            {"name": "spec-3", "content": sample_spec_content, "category": "specs"},
        ]

        with pytest.raises(COOSyncError):
            sync_manager.push_batch(specs, fail_fast=True)

        # Should stop after the failure
        assert mock_coo_client.write_spec.call_count == 2

    def test_error_recovery_preserves_state(self, sync_manager, mock_coo_client, sample_spec_content):
        """Test that errors don't leave partial state."""
        mock_coo_client.write_spec.return_value = SpecPushResult(
            success=True, archived_path="/path/spec.md"
        )
        mock_coo_client.update_index.side_effect = COOSyncError("Index update failed")

        with pytest.raises(COOSyncError):
            sync_manager.push_spec(
                spec_name="partial-spec",
                spec_content=sample_spec_content,
                category="specs",
            )

        # Rollback should have been called
        mock_coo_client.rollback_spec.assert_called_once()


# =============================================================================
# TestCOOConfig: Test configuration handling
# =============================================================================


class TestCOOConfig:
    """Tests for COO configuration."""

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "coo_path": "/path/to/coo",
            "project_name": "test-project",
            "daily_budget_limit": 150.0,
            "monthly_budget_limit": 3000.0,
            "sync_enabled": True,
        }

        config = COOConfig.from_dict(data)

        assert config.coo_path == "/path/to/coo"
        assert config.project_name == "test-project"
        assert config.daily_budget_limit == 150.0
        assert config.monthly_budget_limit == 3000.0
        assert config.sync_enabled is True

    def test_config_to_dict(self, coo_config):
        """Test serializing config to dictionary."""
        data = coo_config.to_dict()

        assert data["coo_path"] == "/Users/test/coo"
        assert data["project_name"] == "swarm-attack"
        assert data["daily_budget_limit"] == 100.0
        assert data["monthly_budget_limit"] == 2500.0
        assert data["sync_enabled"] is True

    def test_config_validates_required_fields(self):
        """Test that config validates required fields."""
        with pytest.raises(ValueError) as exc_info:
            COOConfig(
                coo_path="",
                project_name="test",
                daily_budget_limit=100.0,
                monthly_budget_limit=2500.0,
                sync_enabled=True,
            )

        assert "coo_path" in str(exc_info.value).lower()

    def test_config_validates_budget_positive(self):
        """Test that config validates positive budget limits."""
        with pytest.raises(ValueError) as exc_info:
            COOConfig(
                coo_path="/path",
                project_name="test",
                daily_budget_limit=-100.0,
                monthly_budget_limit=2500.0,
                sync_enabled=True,
            )

        assert "budget" in str(exc_info.value).lower()

    def test_config_defaults(self):
        """Test config with default values."""
        config = COOConfig(
            coo_path="/path/to/coo",
            project_name="test",
        )

        assert config.daily_budget_limit > 0
        assert config.monthly_budget_limit > 0
        assert config.sync_enabled is True


# =============================================================================
# TestPriorityRanking: Test ranking data model
# =============================================================================


class TestPriorityRanking:
    """Tests for PriorityRanking data model."""

    def test_ranking_creation(self):
        """Test creating a priority ranking."""
        ranking = PriorityRanking(
            name="Test Feature",
            rank=1,
            effort="M",
            why="Important feature",
            score=8.5,
            dependencies=["Other Feature"],
        )

        assert ranking.name == "Test Feature"
        assert ranking.rank == 1
        assert ranking.effort == "M"
        assert ranking.why == "Important feature"
        assert ranking.score == 8.5
        assert ranking.dependencies == ["Other Feature"]

    def test_ranking_to_dict(self):
        """Test serializing ranking to dictionary."""
        ranking = PriorityRanking(
            name="Test",
            rank=1,
            effort="S",
            why="Test",
            score=9.0,
            dependencies=[],
        )

        data = ranking.to_dict()

        assert data["name"] == "Test"
        assert data["rank"] == 1
        assert data["effort"] == "S"
        assert data["score"] == 9.0

    def test_ranking_from_dict(self):
        """Test deserializing ranking from dictionary."""
        data = {
            "name": "From Dict",
            "rank": 2,
            "effort": "L",
            "why": "Testing",
            "score": 7.5,
            "dependencies": ["Dep1"],
        }

        ranking = PriorityRanking.from_dict(data)

        assert ranking.name == "From Dict"
        assert ranking.rank == 2
        assert ranking.dependencies == ["Dep1"]

    def test_ranking_comparison_by_rank(self):
        """Test that rankings can be compared by rank."""
        r1 = PriorityRanking(name="First", rank=1, effort="S", why="", score=9.0, dependencies=[])
        r2 = PriorityRanking(name="Second", rank=2, effort="S", why="", score=8.0, dependencies=[])

        assert r1 < r2
        assert sorted([r2, r1]) == [r1, r2]


# =============================================================================
# TestSyncDirection: Test sync direction enum
# =============================================================================


class TestSyncDirection:
    """Tests for SyncDirection enum."""

    def test_push_direction(self):
        """Test PUSH sync direction."""
        assert SyncDirection.PUSH.value == "push"

    def test_pull_direction(self):
        """Test PULL sync direction."""
        assert SyncDirection.PULL.value == "pull"

    def test_bidirectional(self):
        """Test BIDIRECTIONAL sync direction."""
        assert SyncDirection.BIDIRECTIONAL.value == "bidirectional"
