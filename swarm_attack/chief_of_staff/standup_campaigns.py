"""Campaign progress display for standup command.

Provides functions to format and display active campaign progress
in the morning standup briefing.
"""

from datetime import date
from pathlib import Path
from typing import Any

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    CampaignStore,
)


def get_campaign_store(base_path: Path) -> CampaignStore:
    """Get a CampaignStore for the given base path.
    
    Args:
        base_path: Base path for the campaign store
        
    Returns:
        CampaignStore instance
    """
    return CampaignStore(base_path)


def load_campaigns_for_standup(base_path: Path) -> list[Campaign]:
    """Load all campaigns from the store.
    
    Args:
        base_path: Base path for the campaign store
        
    Returns:
        List of campaigns
    """
    store = get_campaign_store(base_path)
    return store.list_all_sync()


def get_active_campaigns(campaigns: list[Campaign]) -> list[Campaign]:
    """Filter campaigns to only active ones.
    
    Args:
        campaigns: List of all campaigns
        
    Returns:
        List of campaigns with ACTIVE state
    """
    return [c for c in campaigns if c.state == CampaignState.ACTIVE]


def count_completed_milestones(campaign: Campaign) -> int:
    """Count the number of completed milestones in a campaign.
    
    Args:
        campaign: The campaign to check
        
    Returns:
        Number of completed milestones
    """
    return sum(
        1 for m in campaign.milestones
        if m.status == "completed" or m.completed
    )


def calculate_budget_remaining(campaign: Campaign) -> float:
    """Calculate remaining budget for a campaign.
    
    Args:
        campaign: The campaign to check
        
    Returns:
        Remaining budget in USD
    """
    return max(0.0, campaign.total_budget_usd - campaign.spent_usd)


def get_todays_goals_from_campaign(campaign: Campaign) -> list[str]:
    """Get today's goals from a campaign's day plans.
    
    Args:
        campaign: The campaign to check
        
    Returns:
        List of goal descriptions for today, or empty list if none
    """
    today = date.today()
    for day_plan in campaign.day_plans:
        if day_plan.date == today:
            return day_plan.goals
    return []


def format_campaign_progress(campaign: Campaign) -> dict[str, Any]:
    """Format campaign progress information for display.
    
    Args:
        campaign: The campaign to format
        
    Returns:
        Dictionary with formatted progress info:
        - name: Campaign name
        - current_day: Current day number
        - total_days: Total planned days
        - milestones_completed: Number of completed milestones
        - milestones_total: Total number of milestones
        - budget_spent: Amount spent in USD
        - budget_total: Total budget in USD
        - budget_remaining: Remaining budget in USD
        - todays_goals: List of goals for today
    """
    return {
        "name": campaign.name,
        "current_day": campaign.current_day,
        "total_days": campaign.planned_days,
        "milestones_completed": count_completed_milestones(campaign),
        "milestones_total": len(campaign.milestones),
        "budget_spent": campaign.spent_usd,
        "budget_total": campaign.total_budget_usd,
        "budget_remaining": calculate_budget_remaining(campaign),
        "todays_goals": get_todays_goals_from_campaign(campaign),
    }


def campaign_needs_attention(campaign: Campaign) -> dict[str, Any]:
    """Check if a campaign needs attention.
    
    A campaign needs attention if:
    - It's behind schedule (needs_replan() returns True)
    - Budget is >= 80% spent
    
    Args:
        campaign: The campaign to check
        
    Returns:
        Dictionary with:
        - needs_attention: Boolean indicating if attention needed
        - reason: String describing why (empty if no attention needed)
    """
    reasons = []
    
    # Check if behind schedule
    if campaign.needs_replan():
        days_behind = campaign.days_behind()
        reasons.append(f"Behind schedule by {days_behind} days")
    
    # Check budget
    if campaign.total_budget_usd > 0:
        budget_percent = (campaign.spent_usd / campaign.total_budget_usd) * 100
        if budget_percent >= 80:
            reasons.append(f"Budget {budget_percent:.0f}% spent (${campaign.spent_usd:.2f}/${campaign.total_budget_usd:.2f})")
    
    if reasons:
        return {
            "needs_attention": True,
            "reason": "; ".join(reasons),
        }
    
    return {
        "needs_attention": False,
        "reason": "",
    }


def render_attention_flags(campaigns: list[Campaign]) -> list[str]:
    """Render attention flags for campaigns that need attention.
    
    Args:
        campaigns: List of campaigns to check
        
    Returns:
        List of attention flag strings (empty if no flags)
    """
    flags = []
    for campaign in campaigns:
        attention = campaign_needs_attention(campaign)
        if attention["needs_attention"]:
            flags.append(f"[CAMPAIGN] {campaign.name}: {attention['reason']}")
    return flags


def render_campaign_section(campaigns: list[Campaign]) -> str:
    """Render the active campaigns section for standup display.
    
    Args:
        campaigns: List of active campaigns
        
    Returns:
        Formatted string for display (empty string if no campaigns)
    """
    if not campaigns:
        return ""
    
    lines = []
    for campaign in campaigns:
        progress = format_campaign_progress(campaign)
        
        # Campaign name and day progress
        lines.append(f"  {progress['name']}: Day {progress['current_day']} / {progress['total_days']}")
        
        # Milestones
        if progress['milestones_total'] > 0:
            lines.append(f"    Milestones: {progress['milestones_completed']}/{progress['milestones_total']}")
        
        # Budget
        lines.append(f"    Budget: ${progress['budget_spent']:.2f}/${progress['budget_total']:.2f} (${progress['budget_remaining']:.2f} remaining)")
        
        # Today's goals
        if progress['todays_goals']:
            lines.append("    Today's Goals:")
            for goal in progress['todays_goals']:
                lines.append(f"      - {goal}")
        
        # Attention flags
        attention = campaign_needs_attention(campaign)
        if attention["needs_attention"]:
            lines.append(f"    [ATTENTION] {attention['reason']}")
    
    return "\n".join(lines)