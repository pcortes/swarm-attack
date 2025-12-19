"""Tests for CoderAgent file path extraction from issue bodies.

These tests verify that the coder correctly extracts file paths from
various formats in issue bodies, including:
- **UPDATE:** section format
- **CREATE:** section format
- Technical Notes "- File:" format (the format used by issue generator)
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestExtractFilePathsFromIssueBody:
    """Tests for _extract_file_paths_from_issue_body method."""

    @pytest.fixture
    def coder(self):
        """Create a CoderAgent instance for testing."""
        # Import here to avoid issues if module has import errors
        from swarm_attack.agents.coder import CoderAgent
        from swarm_attack.config import SwarmConfig

        # Create minimal config
        config = MagicMock(spec=SwarmConfig)
        config.repo_root = Path("/tmp/test-repo")
        config.specs_path = Path("/tmp/test-repo/specs")

        return CoderAgent(config=config)

    def test_extracts_update_section_paths(self, coder):
        """Extracts paths from **UPDATE:** section."""
        issue_body = """
## Description
Some description here.

**UPDATE:**
- `swarm_attack/chief_of_staff/episodes.py`
- `swarm_attack/cli.py` (preserve: existing code)

**CREATE:**
- `swarm_attack/new_module.py`
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths
        assert "swarm_attack/cli.py" in update_paths
        assert "swarm_attack/new_module.py" in create_paths

    def test_extracts_create_section_paths(self, coder):
        """Extracts paths from **CREATE:** section."""
        issue_body = """
**CREATE:**
- `swarm_attack/new_feature/handler.py`
- `tests/test_handler.py`
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert len(update_paths) == 0
        assert "swarm_attack/new_feature/handler.py" in create_paths
        assert "tests/test_handler.py" in create_paths

    def test_extracts_technical_notes_file_format(self, coder):
        """Extracts paths from '- File:' format in Technical Notes.

        This is the format actually used by the issue generator:

        ## Technical Notes
        - File: `swarm_attack/chief_of_staff/episodes.py`
        """
        issue_body = """
## Description

Add a `find_similar()` method to the `EpisodeStore` class.

## Technical Notes

- File: `swarm_attack/chief_of_staff/episodes.py`
- Pattern Reference: See spec section 9.5.1

## Interface Contract (REQUIRED)

**Required Method:**
- `find_similar(content: str, k: int = 5) -> list[Episode]`
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        # File: format should be treated as UPDATE (modifying existing file)
        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths

    def test_extracts_multiple_file_entries(self, coder):
        """Extracts multiple File: entries from Technical Notes."""
        issue_body = """
## Technical Notes

- File: `swarm_attack/chief_of_staff/episodes.py`
- File: `swarm_attack/chief_of_staff/checkpoints.py`
- Other note without file path
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths
        assert "swarm_attack/chief_of_staff/checkpoints.py" in update_paths

    def test_handles_file_format_without_backticks(self, coder):
        """Handles File: format without backticks."""
        issue_body = """
## Technical Notes

- File: swarm_attack/chief_of_staff/episodes.py
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths

    def test_combines_update_and_file_formats(self, coder):
        """Extracts paths from both UPDATE section and File: format."""
        issue_body = """
## Description

Add new feature.

**UPDATE:**
- `swarm_attack/cli.py`

## Technical Notes

- File: `swarm_attack/chief_of_staff/episodes.py`
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert "swarm_attack/cli.py" in update_paths
        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths

    def test_empty_issue_body_returns_empty_lists(self, coder):
        """Empty issue body returns empty lists."""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body("")

        assert update_paths == []
        assert create_paths == []

    def test_no_paths_returns_empty_lists(self, coder):
        """Issue body without any paths returns empty lists."""
        issue_body = """
## Description

Just a description without any file references.

## Acceptance Criteria

- Some criteria
"""
        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        assert update_paths == []
        assert create_paths == []

    def test_real_issue_format_from_v3(self, coder):
        """Tests with actual issue format from chief-of-staff-v3."""
        # This is the exact format from issue #2
        issue_body = """## Description

Add a `find_similar_decisions()` method to the `PreferenceLearner` class that finds similar past checkpoint decisions for a goal. This is needed by Enhanced Checkpoints (12.8) to show context about similar past decisions.

## Acceptance Criteria

- [ ] `find_similar_decisions(goal: DailyGoal, k: int = 3) -> list[dict]` method implemented
- [ ] Returns dicts with keys: trigger, context_summary, was_accepted, chosen_option, timestamp
- [ ] Matches signals based on goal tags (ui/ux -> UX_CHANGE, architecture/refactor -> ARCHITECTURE)
- [ ] Cost triggers (COST_SINGLE, COST_CUMULATIVE) always considered relevant
- [ ] Results sorted by recency (most recent first)
- [ ] Respects k limit
- [ ] Unit tests for: finds decisions matching goal tags, returns was_accepted flag correctly

## Technical Notes

- File: `swarm_attack/chief_of_staff/episodes.py`
- Pattern Reference: See spec section 9.5.2 for implementation details
- Relies on existing `signals` list in PreferenceLearner

## Interface Contract (REQUIRED)

**Required Method:**
- `find_similar_decisions(goal: DailyGoal, k: int = 3) -> list[dict]`

**Called By:**
- `swarm_attack/chief_of_staff/checkpoints.py` (future - 12.8)"""

        update_paths, create_paths = coder._extract_file_paths_from_issue_body(issue_body)

        # The file should be extracted and treated as an UPDATE
        assert "swarm_attack/chief_of_staff/episodes.py" in update_paths
