"""Tests for CampaignStore persistence class."""

import pytest
from pathlib import Path
from datetime import date, datetime
import json
import asyncio

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    CampaignStore,
    Milestone,
    DayPlan,
)


class TestCampaignStoreInit:
    """Tests for CampaignStore initialization."""

    def test_creates_campaigns_subdirectory(self, tmp_path: Path):
        """CampaignStore creates campaigns/ subdirectory on init."""
        store = CampaignStore(tmp_path)
        campaigns_dir = tmp_path / "campaigns"
        assert campaigns_dir.exists()
        assert campaigns_dir.is_dir()

    def test_uses_existing_campaigns_directory(self, tmp_path: Path):
        """CampaignStore uses existing campaigns/ directory if present."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir()
        marker_file = campaigns_dir / ".marker"
        marker_file.write_text("existing")
        
        store = CampaignStore(tmp_path)
        assert marker_file.exists()
        assert marker_file.read_text() == "existing"


class TestCampaignStoreSaveAndLoad:
    """Tests for save and load roundtrip."""

    @pytest.mark.asyncio
    async def test_save_creates_json_file(self, tmp_path: Path):
        """save() creates a JSON file with campaign_id as filename."""
        store = CampaignStore(tmp_path)
        campaign = Campaign(
            campaign_id="test-campaign-1",
            name="Test Campaign",
            description="A test campaign",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=100.0,
        )
        
        await store.save(campaign)
        
        expected_file = tmp_path / "campaigns" / "test-campaign-1.json"
        assert expected_file.exists()

    @pytest.mark.asyncio
    async def test_load_returns_campaign(self, tmp_path: Path):
        """load() returns the campaign from JSON file."""
        store = CampaignStore(tmp_path)
        campaign = Campaign(
            campaign_id="test-campaign-2",
            name="Test Campaign 2",
            description="Another test campaign",
            start_date=date(2025, 2, 20),
            planned_days=10,
            total_budget_usd=200.0,
            state=CampaignState.ACTIVE,
            current_day=3,
        )
        
        await store.save(campaign)
        loaded = await store.load("test-campaign-2")
        
        assert loaded is not None
        assert loaded.campaign_id == "test-campaign-2"
        assert loaded.name == "Test Campaign 2"
        assert loaded.description == "Another test campaign"
        assert loaded.start_date == date(2025, 2, 20)
        assert loaded.planned_days == 10
        assert loaded.total_budget_usd == 200.0
        assert loaded.state == CampaignState.ACTIVE
        assert loaded.current_day == 3

    @pytest.mark.asyncio
    async def test_save_load_roundtrip_with_milestones(self, tmp_path: Path):
        """save/load preserves milestones."""
        store = CampaignStore(tmp_path)
        milestone = Milestone(
            milestone_id="m1",
            name="First Milestone",
            description="Complete phase 1",
            target_day=3,
            success_criteria=["Tests pass", "Code reviewed"],
            status="completed",
            completed_at=datetime(2025, 1, 18, 10, 30, 0),
        )
        campaign = Campaign(
            campaign_id="campaign-with-milestones",
            name="Campaign With Milestones",
            description="Has milestones",
            start_date=date(2025, 1, 15),
            planned_days=7,
            total_budget_usd=150.0,
            milestones=[milestone],
        )
        
        await store.save(campaign)
        loaded = await store.load("campaign-with-milestones")
        
        assert loaded is not None
        assert len(loaded.milestones) == 1
        assert loaded.milestones[0].milestone_id == "m1"
        assert loaded.milestones[0].name == "First Milestone"
        assert loaded.milestones[0].status == "completed"
        assert loaded.milestones[0].completed_at == datetime(2025, 1, 18, 10, 30, 0)

    @pytest.mark.asyncio
    async def test_save_load_roundtrip_with_day_plans(self, tmp_path: Path):
        """save/load preserves day plans."""
        store = CampaignStore(tmp_path)
        day_plan = DayPlan(
            day_number=1,
            date=date(2025, 1, 15),
            goals=["Setup project", "Write tests"],
            budget_usd=25.0,
            status="completed",
            actual_cost_usd=22.50,
            notes="Good progress",
        )
        campaign = Campaign(
            campaign_id="campaign-with-day-plans",
            name="Campaign With Day Plans",
            description="Has day plans",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=100.0,
            day_plans=[day_plan],
        )
        
        await store.save(campaign)
        loaded = await store.load("campaign-with-day-plans")
        
        assert loaded is not None
        assert len(loaded.day_plans) == 1
        assert loaded.day_plans[0].day_number == 1
        assert loaded.day_plans[0].date == date(2025, 1, 15)
        assert loaded.day_plans[0].goals == ["Setup project", "Write tests"]
        assert loaded.day_plans[0].actual_cost_usd == 22.50

    @pytest.mark.asyncio
    async def test_load_returns_none_for_missing(self, tmp_path: Path):
        """load() returns None for non-existent campaign."""
        store = CampaignStore(tmp_path)
        
        result = await store.load("nonexistent-campaign")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_save_overwrites_existing(self, tmp_path: Path):
        """save() overwrites existing campaign file."""
        store = CampaignStore(tmp_path)
        campaign = Campaign(
            campaign_id="overwrite-test",
            name="Original Name",
            description="Original description",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=100.0,
        )
        
        await store.save(campaign)
        
        campaign.name = "Updated Name"
        campaign.description = "Updated description"
        await store.save(campaign)
        
        loaded = await store.load("overwrite-test")
        assert loaded is not None
        assert loaded.name == "Updated Name"
        assert loaded.description == "Updated description"


class TestCampaignStoreListAll:
    """Tests for list_all method."""

    @pytest.mark.asyncio
    async def test_list_all_returns_empty_list_when_no_campaigns(self, tmp_path: Path):
        """list_all() returns empty list when no campaigns exist."""
        store = CampaignStore(tmp_path)
        
        result = await store.list_all()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_returns_single_campaign(self, tmp_path: Path):
        """list_all() returns single campaign."""
        store = CampaignStore(tmp_path)
        campaign = Campaign(
            campaign_id="single-campaign",
            name="Single Campaign",
            description="Only campaign",
            start_date=date(2025, 1, 15),
            planned_days=3,
            total_budget_usd=50.0,
        )
        await store.save(campaign)
        
        result = await store.list_all()
        
        assert len(result) == 1
        assert result[0].campaign_id == "single-campaign"

    @pytest.mark.asyncio
    async def test_list_all_returns_multiple_campaigns(self, tmp_path: Path):
        """list_all() returns all saved campaigns."""
        store = CampaignStore(tmp_path)
        
        for i in range(3):
            campaign = Campaign(
                campaign_id=f"campaign-{i}",
                name=f"Campaign {i}",
                description=f"Description {i}",
                start_date=date(2025, 1, 15 + i),
                planned_days=5,
                total_budget_usd=100.0 * (i + 1),
            )
            await store.save(campaign)
        
        result = await store.list_all()
        
        assert len(result) == 3
        campaign_ids = {c.campaign_id for c in result}
        assert campaign_ids == {"campaign-0", "campaign-1", "campaign-2"}

    @pytest.mark.asyncio
    async def test_list_all_ignores_non_json_files(self, tmp_path: Path):
        """list_all() ignores non-JSON files in campaigns directory."""
        store = CampaignStore(tmp_path)
        
        campaign = Campaign(
            campaign_id="valid-campaign",
            name="Valid Campaign",
            description="Valid",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=100.0,
        )
        await store.save(campaign)
        
        # Create a non-JSON file
        non_json = tmp_path / "campaigns" / "readme.txt"
        non_json.write_text("This is not a campaign")
        
        result = await store.list_all()
        
        assert len(result) == 1
        assert result[0].campaign_id == "valid-campaign"


class TestCampaignStoreFileExists:
    """Tests for file existence."""

    def test_campaigns_module_exists(self):
        """campaigns.py module exists and has CampaignStore."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "campaigns.py"
        assert path.exists(), "campaigns.py must exist"
        content = path.read_text()
        assert "class CampaignStore" in content, "CampaignStore class must be defined"