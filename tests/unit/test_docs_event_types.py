"""Test that documented event types actually exist in the codebase."""
import re
from pathlib import Path
from swarm_attack.events.types import EventType


def test_claude_md_event_types_exist():
    """All EventType references in CLAUDE.md must exist."""
    claude_md = Path("CLAUDE.md").read_text()
    # Find all EventType.XXX references
    matches = re.findall(r'EventType\.([A-Z_]+)', claude_md)
    valid_names = {e.name for e in EventType}
    for match in matches:
        assert match in valid_names, f"EventType.{match} referenced in CLAUDE.md does not exist"


def test_expert_tester_event_types_exist():
    """All EventType references in expert-tester.md must exist."""
    expert_md = Path(".claude/prompts/expert-tester.md").read_text()
    matches = re.findall(r'EventType\.([A-Z_]+)', expert_md)
    valid_names = {e.name for e in EventType}
    for match in matches:
        assert match in valid_names, f"EventType.{match} in expert-tester.md does not exist"


def test_user_guide_event_types_exist():
    """All EventType references in docs/USER_GUIDE.md must exist."""
    user_guide = Path("docs/USER_GUIDE.md").read_text()
    matches = re.findall(r'EventType\.([A-Z_]+)', user_guide)
    valid_names = {e.name for e in EventType}
    for match in matches:
        assert match in valid_names, f"EventType.{match} in docs/USER_GUIDE.md does not exist"
