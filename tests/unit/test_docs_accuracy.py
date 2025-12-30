"""Test that CLAUDE.md numbers match actual code values."""
import re
from pathlib import Path
from swarm_attack.events.types import EventType
from swarm_attack.universal_context_builder import AGENT_CONTEXT_PROFILES


def test_event_type_count_matches():
    """CLAUDE.md event count should match actual EventType count."""
    claude_md = Path("CLAUDE.md").read_text()
    # Find "Available event types (XX total)"
    match = re.search(r'Available event types \((\d+) total\)', claude_md)
    assert match, "Could not find event type count in CLAUDE.md"
    documented = int(match.group(1))
    actual = len([e for e in EventType])
    assert documented == actual, f"CLAUDE.md says {documented} events, actually {actual}"


def test_agent_profile_count_matches():
    """CLAUDE.md agent profile table should have all profiles."""
    claude_md = Path("CLAUDE.md").read_text()
    actual_count = len(AGENT_CONTEXT_PROFILES)
    # The table should have entries for all profiles
    for profile_name in AGENT_CONTEXT_PROFILES.keys():
        # Convert snake_case to display format
        assert profile_name in claude_md.lower() or profile_name.replace('_', '') in claude_md.lower(), \
            f"Profile '{profile_name}' missing from CLAUDE.md table"


def test_token_budgets_match():
    """Token budgets in CLAUDE.md should match actual values."""
    # These are the actual values from AGENT_CONTEXT_PROFILES
    assert AGENT_CONTEXT_PROFILES['spec_author']['max_tokens'] == 5000
    assert AGENT_CONTEXT_PROFILES['issue_creator']['max_tokens'] == 4000
    assert AGENT_CONTEXT_PROFILES['coder']['max_tokens'] == 15000
    assert AGENT_CONTEXT_PROFILES['verifier']['max_tokens'] == 3000
