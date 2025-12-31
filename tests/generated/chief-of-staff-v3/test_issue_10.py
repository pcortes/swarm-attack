"""Tests for Issue #10: Campaign CLI commands.

Tests the campaign CLI commands:
- campaign-create
- campaign-list
- campaign-status
- campaign-run
- campaign-replan
"""

import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from click.testing import CliRunner
from typer.testing import CliRunner as TyperCliRunner
import tempfile
import json


class TestCampaignCreateCommand:
    """Tests for the campaign-create CLI command."""

    def test_campaign_create_basic(self):
        """Test creating a campaign with name and deadline."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()
        deadline = (date.today() + timedelta(days=7)).isoformat()

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.save = AsyncMock()

            result = runner.invoke(
                app, ["campaign-create", "test-campaign", "--deadline", deadline]
            )

            # Check it succeeded
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "test-campaign" in result.output.lower() or "created" in result.output.lower()

    def test_campaign_create_missing_deadline(self):
        """Test that campaign-create requires deadline."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()
        result = runner.invoke(app, ["campaign-create", "test-campaign"])

        # Should fail due to missing required option
        assert result.exit_code != 0

    def test_campaign_create_invalid_deadline_format(self):
        """Test campaign-create with invalid deadline format."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()
        result = runner.invoke(
            app, ["campaign-create", "test-campaign", "--deadline", "not-a-date"]
        )

        # Should fail or show error
        assert result.exit_code != 0 or "invalid" in result.output.lower() or "error" in result.output.lower()


class TestCampaignListCommand:
    """Tests for the campaign-list CLI command."""

    def test_campaign_list_empty(self):
        """Test listing campaigns when none exist."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.list_all = AsyncMock(return_value=[])

            result = runner.invoke(app, ["campaign-list"])

            assert result.exit_code == 0
            # Should indicate no campaigns
            assert "no campaign" in result.output.lower() or result.output.strip() == "" or "empty" in result.output.lower() or len(result.output.strip()) < 100

    def test_campaign_list_with_campaigns(self):
        """Test listing campaigns when some exist."""
        from swarm_attack.cli.chief_of_staff import app
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState

        runner = TyperCliRunner()

        mock_campaigns = [
            Campaign(
                id="campaign-1",
                name="Feature Campaign",
                state=CampaignState.ACTIVE,
            ),
            Campaign(
                id="campaign-2",
                name="Bug Fix Campaign",
                state=CampaignState.PAUSED,
            ),
        ]

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.list_all = AsyncMock(return_value=mock_campaigns)

            result = runner.invoke(app, ["campaign-list"])

            assert result.exit_code == 0
            # Should show campaign names or IDs
            output_lower = result.output.lower()
            assert "campaign-1" in output_lower or "feature" in output_lower


class TestCampaignStatusCommand:
    """Tests for the campaign-status CLI command."""

    def test_campaign_status_existing(self):
        """Test getting status of existing campaign."""
        from swarm_attack.cli.chief_of_staff import app
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan

        runner = TyperCliRunner()

        mock_campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            planned_days=7,
            current_day=3,
            spent_usd=15.50,
            day_plans=[
                DayPlan(date=date.today(), goals=["Goal 1", "Goal 2"], day_number=4)
            ],
        )

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.load = AsyncMock(return_value=mock_campaign)

            result = runner.invoke(app, ["campaign-status", "test-campaign"])

            assert result.exit_code == 0
            output_lower = result.output.lower()
            # Should show campaign info
            assert "test-campaign" in output_lower or "test campaign" in output_lower or "active" in output_lower

    def test_campaign_status_not_found(self):
        """Test getting status of non-existent campaign."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.load = AsyncMock(return_value=None)

            result = runner.invoke(app, ["campaign-status", "nonexistent"])

            # Should show error or not found message
            assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()


class TestCampaignRunCommand:
    """Tests for the campaign-run CLI command."""

    def test_campaign_run_success(self):
        """Test running a campaign successfully."""
        from swarm_attack.cli.chief_of_staff import app
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        runner = TyperCliRunner()

        mock_campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(date=date.today(), goals=["Goal 1"], day_number=1)
            ],
        )

        mock_result = DayExecutionResult(
            goals_completed=1,
            goals_blocked=[],
            cost_usd=2.50,
            needs_replan=False,
        )

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            with patch("swarm_attack.cli.chief_of_staff._get_campaign_executor") as mock_executor:
                mock_store.return_value = MagicMock()
                mock_store.return_value.load = AsyncMock(return_value=mock_campaign)

                mock_executor.return_value = MagicMock()
                mock_executor.return_value.execute_day = AsyncMock(return_value=mock_result)

                result = runner.invoke(app, ["campaign-run", "test-campaign"])

                assert result.exit_code == 0
                # Should show execution results
                output_lower = result.output.lower()
                assert "complete" in output_lower or "success" in output_lower or "1" in result.output

    def test_campaign_run_campaign_not_found(self):
        """Test running a non-existent campaign."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            with patch("swarm_attack.cli.chief_of_staff._get_campaign_executor") as mock_executor:
                mock_store.return_value = MagicMock()
                mock_store.return_value.load = AsyncMock(return_value=None)

                mock_executor.return_value = MagicMock()
                mock_executor.return_value.execute_day = AsyncMock(
                    side_effect=ValueError("Campaign not found: nonexistent")
                )

                result = runner.invoke(app, ["campaign-run", "nonexistent"])

                # Should show error
                assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()

    def test_campaign_run_with_blocked_goals(self):
        """Test running a campaign that has blocked goals."""
        from swarm_attack.cli.chief_of_staff import app
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        runner = TyperCliRunner()

        mock_campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(date=date.today(), goals=["Goal 1", "Goal 2"], day_number=1)
            ],
        )

        mock_result = DayExecutionResult(
            goals_completed=1,
            goals_blocked=["goal-2"],
            cost_usd=1.50,
            needs_replan=False,
        )

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            with patch("swarm_attack.cli.chief_of_staff._get_campaign_executor") as mock_executor:
                mock_store.return_value = MagicMock()
                mock_store.return_value.load = AsyncMock(return_value=mock_campaign)

                mock_executor.return_value = MagicMock()
                mock_executor.return_value.execute_day = AsyncMock(return_value=mock_result)

                result = runner.invoke(app, ["campaign-run", "test-campaign"])

                # Should indicate blocked goals
                assert result.exit_code == 0
                output_lower = result.output.lower()
                assert "blocked" in output_lower or "1" in result.output


class TestCampaignReplanCommand:
    """Tests for the campaign-replan CLI command."""

    def test_campaign_replan_success(self):
        """Test replanning a campaign."""
        from swarm_attack.cli.chief_of_staff import app
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState

        runner = TyperCliRunner()

        mock_campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            planned_days=7,
            current_day=2,
        )

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            with patch("swarm_attack.cli.chief_of_staff._get_campaign_planner") as mock_planner:
                mock_store.return_value = MagicMock()
                mock_store.return_value.load = AsyncMock(return_value=mock_campaign)
                mock_store.return_value.save = AsyncMock()

                mock_planner.return_value = MagicMock()
                mock_planner.return_value.replan = AsyncMock(return_value=mock_campaign)

                result = runner.invoke(app, ["campaign-replan", "test-campaign"])

                assert result.exit_code == 0
                output_lower = result.output.lower()
                # Should indicate replanning happened
                assert "replan" in output_lower or "success" in output_lower or "updated" in output_lower

    def test_campaign_replan_not_found(self):
        """Test replanning a non-existent campaign."""
        from swarm_attack.cli.chief_of_staff import app

        runner = TyperCliRunner()

        with patch("swarm_attack.cli.chief_of_staff._get_campaign_store") as mock_store:
            mock_store.return_value = MagicMock()
            mock_store.return_value.load = AsyncMock(return_value=None)

            result = runner.invoke(app, ["campaign-replan", "nonexistent"])

            # Should show error
            assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()


class TestCampaignCLIHelpers:
    """Tests for CLI helper functions."""

    def test_get_campaign_store_returns_store(self):
        """Test _get_campaign_store returns a CampaignStore."""
        from swarm_attack.cli.chief_of_staff import _get_campaign_store
        from swarm_attack.chief_of_staff.campaigns import CampaignStore

        with patch("swarm_attack.cli.chief_of_staff.get_project_dir") as mock_dir:
            mock_dir.return_value = "/tmp/test-project"

            store = _get_campaign_store()

            assert isinstance(store, CampaignStore)

    def test_get_campaign_executor_returns_executor(self):
        """Test _get_campaign_executor returns a CampaignExecutor."""
        from swarm_attack.cli.chief_of_staff import _get_campaign_executor
        from swarm_attack.chief_of_staff.campaign_executor import CampaignExecutor

        with patch("swarm_attack.cli.chief_of_staff.get_project_dir") as mock_dir:
            with patch("swarm_attack.cli.chief_of_staff._get_autopilot_runner") as mock_runner:
                mock_dir.return_value = "/tmp/test-project"
                mock_runner.return_value = MagicMock()

                executor = _get_campaign_executor()

                assert isinstance(executor, CampaignExecutor)
