"""
Tests for candidates.py validation.

BUG-11: Ensure invalid discovery types raise errors.
"""

import pytest

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Opportunity,
    OpportunityType,
    OpportunityStatus,
)


class TestOpportunityValidation:
    """Tests for Opportunity.from_dict validation."""

    def test_opportunity_rejects_invalid_type(self):
        """BUG-11: Invalid discovery type must raise error, not default."""
        with pytest.raises(ValueError):
            Opportunity.from_dict({"opportunity_type": "invalid_type"})

    def test_opportunity_rejects_invalid_status(self):
        """Invalid status must also raise error."""
        with pytest.raises(ValueError):
            Opportunity.from_dict({
                "opportunity_type": "test_failure",
                "status": "invalid_status"
            })

    def test_opportunity_accepts_valid_type(self):
        """Valid types should work correctly."""
        opp = Opportunity.from_dict({
            "opportunity_id": "test-1",
            "opportunity_type": "test_failure",
            "status": "discovered",
            "title": "Test",
            "description": "Test description",
            "evidence": [],
        })
        assert opp.opportunity_type == OpportunityType.TEST_FAILURE
        assert opp.status == OpportunityStatus.DISCOVERED

    def test_opportunity_accepts_all_valid_types(self):
        """All OpportunityType values should be accepted."""
        for opp_type in OpportunityType:
            opp = Opportunity.from_dict({
                "opportunity_id": f"test-{opp_type.value}",
                "opportunity_type": opp_type.value,
                "status": "discovered",
                "title": "Test",
                "description": "Test",
                "evidence": [],
            })
            assert opp.opportunity_type == opp_type
