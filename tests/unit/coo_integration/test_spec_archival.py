"""
TDD Tests for Spec Archival module - COO Integration Phase.

Tests written BEFORE implementation (RED phase) following swarm-attack TDD protocol.

Acceptance Criteria:
1. Archive approved specs to COO/projects/{project}/specs/
2. Archive test reports to COO/projects/{project}/qa/
3. Include creation date, author, and approval status

Test Classes:
- TestSpecArchival: Test archiving specs
- TestReportArchival: Test archiving test reports
- TestArchivalMetadata: Test metadata inclusion
- TestArchivalPaths: Test correct path generation
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.coo_integration.spec_archival import (
    SpecArchiver,
    ReportArchiver,
    ArchivalMetadata,
    ArchivalResult,
    ApprovalStatus,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_coo_root(tmp_path):
    """Create a temporary COO directory structure."""
    coo_root = tmp_path / "coo"
    coo_root.mkdir()

    # Create projects directory structure
    projects_dir = coo_root / "projects"
    projects_dir.mkdir()

    # Create swarm-attack project structure
    swarm_project = projects_dir / "swarm-attack"
    swarm_project.mkdir()
    (swarm_project / "specs").mkdir()
    (swarm_project / "prompts").mkdir()
    (swarm_project / "qa").mkdir()

    # Create desktop-miami project structure
    miami_project = projects_dir / "desktop-miami"
    miami_project.mkdir()
    (miami_project / "specs").mkdir()
    (miami_project / "prompts").mkdir()
    (miami_project / "qa").mkdir()

    return coo_root


@pytest.fixture
def spec_archiver(tmp_coo_root):
    """Create a SpecArchiver with temporary COO root."""
    return SpecArchiver(coo_root=tmp_coo_root)


@pytest.fixture
def report_archiver(tmp_coo_root):
    """Create a ReportArchiver with temporary COO root."""
    return ReportArchiver(coo_root=tmp_coo_root)


@pytest.fixture
def sample_spec_content():
    """Sample spec content for testing."""
    return """# Feature Specification: Auto-Approval System

**Author:** Claude Code
**Date:** 2026-01-05
**Status:** Approved

## Overview

This specification defines the auto-approval system for feature implementations.

## Requirements

1. Must validate all test passes
2. Must verify code quality metrics
3. Must check for security vulnerabilities

## Implementation Details

The system will integrate with the existing verification pipeline.
"""


@pytest.fixture
def sample_report_content():
    """Sample test report content for testing."""
    return """# QA Test Report

**Feature:** chief-of-staff-v3
**Date:** 2026-01-05
**Author:** QA Agent
**Status:** PASSED

## Test Summary

- Total Tests: 150
- Passed: 148
- Failed: 2
- Skipped: 0

## Coverage

- Line Coverage: 92%
- Branch Coverage: 87%

## Failed Tests

1. test_edge_case_timeout - AssertionError
2. test_concurrent_access - TimeoutError
"""


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return ArchivalMetadata(
        creation_date=datetime(2026, 1, 5, 10, 30, 0, tzinfo=timezone.utc),
        author="Claude Code",
        approval_status=ApprovalStatus.APPROVED,
        feature_id="chief-of-staff-v3",
        issue_number=42,
    )


# =============================================================================
# TestSpecArchival - Test archiving specs
# =============================================================================


class TestSpecArchival:
    """Tests for SpecArchiver - archiving specs to COO/projects/{project}/specs/."""

    def test_archive_spec_creates_file_in_correct_location(
        self, spec_archiver, sample_spec_content, sample_metadata, tmp_coo_root
    ):
        """Spec is archived to COO/projects/{project}/specs/ directory."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="auto-approval-system.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        expected_dir = tmp_coo_root / "projects" / "swarm-attack" / "specs"
        assert result.path.parent == expected_dir
        assert result.path.exists()

    def test_archive_spec_uses_date_prefix(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archived spec filename uses YYYY-MM-DD prefix from creation date."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="feature-spec.md",
            metadata=sample_metadata,
        )

        # Metadata has creation_date of 2026-01-05
        assert result.path.name.startswith("2026-01-05_")
        assert result.path.name.endswith("feature-spec.md")

    def test_archive_spec_preserves_content(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archived spec preserves the original content."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test-spec.md",
            metadata=sample_metadata,
        )

        archived_content = result.path.read_text()
        # Content should be present (may have metadata header added)
        assert "Auto-Approval System" in archived_content
        assert "Must validate all test passes" in archived_content

    def test_archive_spec_to_different_projects(
        self, spec_archiver, sample_spec_content, sample_metadata, tmp_coo_root
    ):
        """Specs can be archived to different project directories."""
        # Archive to swarm-attack
        result1 = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="spec1.md",
            metadata=sample_metadata,
        )

        # Archive to desktop-miami
        result2 = spec_archiver.archive(
            content=sample_spec_content,
            project="desktop-miami",
            filename="spec2.md",
            metadata=sample_metadata,
        )

        assert "swarm-attack" in str(result1.path)
        assert "desktop-miami" in str(result2.path)
        assert result1.path.exists()
        assert result2.path.exists()

    def test_archive_spec_fails_for_unknown_project(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archiving to unknown project returns failure result."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="nonexistent-project",
            filename="spec.md",
            metadata=sample_metadata,
        )

        assert result.success is False
        assert "not found" in result.error.lower() or "unknown" in result.error.lower()

    def test_archive_spec_handles_duplicate_filename(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archiving duplicate filename generates unique name or fails gracefully."""
        # First archive
        result1 = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="duplicate.md",
            metadata=sample_metadata,
        )

        # Second archive with same name
        result2 = spec_archiver.archive(
            content=sample_spec_content + "\n\n## Updated",
            project="swarm-attack",
            filename="duplicate.md",
            metadata=sample_metadata,
        )

        # Either both succeed with different paths, or second returns error
        assert result1.success is True
        if result2.success:
            assert result1.path != result2.path
        else:
            assert "exists" in result2.error.lower() or "duplicate" in result2.error.lower()


# =============================================================================
# TestReportArchival - Test archiving test reports
# =============================================================================


class TestReportArchival:
    """Tests for ReportArchiver - archiving test reports to COO/projects/{project}/qa/."""

    def test_archive_report_creates_file_in_qa_directory(
        self, report_archiver, sample_report_content, sample_metadata, tmp_coo_root
    ):
        """Test report is archived to COO/projects/{project}/qa/ directory."""
        result = report_archiver.archive(
            content=sample_report_content,
            project="swarm-attack",
            filename="test-report.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        expected_dir = tmp_coo_root / "projects" / "swarm-attack" / "qa"
        assert result.path.parent == expected_dir
        assert result.path.exists()

    def test_archive_report_uses_date_prefix(
        self, report_archiver, sample_report_content, sample_metadata
    ):
        """Archived report filename uses YYYY-MM-DD prefix from creation date."""
        result = report_archiver.archive(
            content=sample_report_content,
            project="swarm-attack",
            filename="qa-report.md",
            metadata=sample_metadata,
        )

        # Metadata has creation_date of 2026-01-05
        assert result.path.name.startswith("2026-01-05_")
        assert result.path.name.endswith("qa-report.md")

    def test_archive_report_preserves_content(
        self, report_archiver, sample_report_content, sample_metadata
    ):
        """Archived report preserves the original content."""
        result = report_archiver.archive(
            content=sample_report_content,
            project="swarm-attack",
            filename="coverage-report.md",
            metadata=sample_metadata,
        )

        archived_content = result.path.read_text()
        assert "QA Test Report" in archived_content
        assert "Total Tests: 150" in archived_content
        assert "Line Coverage: 92%" in archived_content

    def test_archive_report_with_json_format(
        self, report_archiver, sample_metadata, tmp_coo_root
    ):
        """JSON test reports can be archived."""
        json_report = {
            "feature": "chief-of-staff-v3",
            "total_tests": 150,
            "passed": 148,
            "failed": 2,
            "coverage": {"line": 92, "branch": 87},
        }

        result = report_archiver.archive(
            content=json.dumps(json_report, indent=2),
            project="swarm-attack",
            filename="test-results.json",
            metadata=sample_metadata,
        )

        assert result.success is True
        assert result.path.suffix == ".json"

        # Verify content is valid JSON
        archived_content = result.path.read_text()
        parsed = json.loads(archived_content)
        assert parsed["total_tests"] == 150

    def test_archive_report_creates_qa_directory_if_missing(
        self, tmp_coo_root, sample_report_content, sample_metadata
    ):
        """If qa/ directory doesn't exist, it is created."""
        # Create a new project without qa directory
        new_project = tmp_coo_root / "projects" / "new-project"
        new_project.mkdir()
        (new_project / "specs").mkdir()
        # Note: qa/ is NOT created

        report_archiver = ReportArchiver(coo_root=tmp_coo_root)
        result = report_archiver.archive(
            content=sample_report_content,
            project="new-project",
            filename="report.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        qa_dir = new_project / "qa"
        assert qa_dir.exists()
        assert result.path.exists()


# =============================================================================
# TestArchivalMetadata - Test metadata inclusion
# =============================================================================


class TestArchivalMetadata:
    """Tests for metadata handling in archival process."""

    def test_metadata_includes_creation_date(self):
        """ArchivalMetadata stores creation date."""
        metadata = ArchivalMetadata(
            creation_date=datetime(2026, 1, 5, 14, 30, 0, tzinfo=timezone.utc),
            author="Test Author",
            approval_status=ApprovalStatus.APPROVED,
        )

        assert metadata.creation_date.year == 2026
        assert metadata.creation_date.month == 1
        assert metadata.creation_date.day == 5

    def test_metadata_includes_author(self):
        """ArchivalMetadata stores author information."""
        metadata = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Claude Code Agent",
            approval_status=ApprovalStatus.APPROVED,
        )

        assert metadata.author == "Claude Code Agent"

    def test_metadata_includes_approval_status(self):
        """ArchivalMetadata stores approval status."""
        approved = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Author",
            approval_status=ApprovalStatus.APPROVED,
        )
        pending = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Author",
            approval_status=ApprovalStatus.PENDING,
        )
        rejected = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Author",
            approval_status=ApprovalStatus.REJECTED,
        )

        assert approved.approval_status == ApprovalStatus.APPROVED
        assert pending.approval_status == ApprovalStatus.PENDING
        assert rejected.approval_status == ApprovalStatus.REJECTED

    def test_metadata_optional_feature_id(self):
        """ArchivalMetadata can include optional feature_id."""
        metadata = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Author",
            approval_status=ApprovalStatus.APPROVED,
            feature_id="my-awesome-feature",
        )

        assert metadata.feature_id == "my-awesome-feature"

    def test_metadata_optional_issue_number(self):
        """ArchivalMetadata can include optional issue_number."""
        metadata = ArchivalMetadata(
            creation_date=datetime.now(timezone.utc),
            author="Author",
            approval_status=ApprovalStatus.APPROVED,
            issue_number=123,
        )

        assert metadata.issue_number == 123

    def test_metadata_to_dict(self, sample_metadata):
        """ArchivalMetadata can be serialized to dictionary."""
        data = sample_metadata.to_dict()

        assert "creation_date" in data
        assert "author" in data
        assert "approval_status" in data
        assert data["author"] == "Claude Code"
        assert data["approval_status"] == "approved"

    def test_metadata_from_dict(self):
        """ArchivalMetadata can be deserialized from dictionary."""
        data = {
            "creation_date": "2026-01-05T10:30:00+00:00",
            "author": "Test Author",
            "approval_status": "approved",
            "feature_id": "test-feature",
            "issue_number": 42,
        }

        metadata = ArchivalMetadata.from_dict(data)

        assert metadata.author == "Test Author"
        assert metadata.approval_status == ApprovalStatus.APPROVED
        assert metadata.feature_id == "test-feature"
        assert metadata.issue_number == 42

    def test_archived_file_contains_metadata_header(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archived file includes metadata in frontmatter/header."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="with-metadata.md",
            metadata=sample_metadata,
        )

        archived_content = result.path.read_text()

        # Should include metadata in some format (YAML frontmatter, comment, etc.)
        assert "2026-01-05" in archived_content  # creation date
        assert "Claude Code" in archived_content  # author
        # Approval status should be present
        assert "approved" in archived_content.lower() or "APPROVED" in archived_content


# =============================================================================
# TestArchivalPaths - Test correct path generation
# =============================================================================


class TestArchivalPaths:
    """Tests for path generation in archival process."""

    def test_path_uses_coo_root(self, spec_archiver, sample_spec_content, sample_metadata, tmp_coo_root):
        """Generated path starts with COO root directory."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert str(result.path).startswith(str(tmp_coo_root))

    def test_path_includes_projects_directory(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Generated path includes /projects/ directory."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert "/projects/" in str(result.path)

    def test_path_includes_correct_project_name(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Generated path includes the correct project name."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="desktop-miami",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert "/desktop-miami/" in str(result.path)

    def test_spec_path_includes_specs_directory(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Spec path includes /specs/ directory."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert "/specs/" in str(result.path)

    def test_report_path_includes_qa_directory(
        self, report_archiver, sample_report_content, sample_metadata
    ):
        """Report path includes /qa/ directory."""
        result = report_archiver.archive(
            content=sample_report_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert "/qa/" in str(result.path)

    def test_path_sanitizes_filename(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Filename is sanitized to remove unsafe characters."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="unsafe/file:name*.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        # Path should not contain unsafe characters
        assert "/" not in result.path.name.replace("2026-01-05_", "")
        assert ":" not in result.path.name
        assert "*" not in result.path.name

    def test_path_generation_for_full_coo_path(self, tmp_coo_root, sample_metadata):
        """Generate correct full path: COO/projects/{project}/specs/YYYY-MM-DD_filename.md"""
        spec_archiver = SpecArchiver(coo_root=tmp_coo_root)

        path = spec_archiver.generate_path(
            project="swarm-attack",
            filename="feature-spec.md",
            metadata=sample_metadata,
        )

        expected = tmp_coo_root / "projects" / "swarm-attack" / "specs" / "2026-01-05_feature-spec.md"
        assert path == expected

    def test_path_generation_for_qa_report(self, tmp_coo_root, sample_metadata):
        """Generate correct full path for QA: COO/projects/{project}/qa/YYYY-MM-DD_filename.md"""
        report_archiver = ReportArchiver(coo_root=tmp_coo_root)

        path = report_archiver.generate_path(
            project="swarm-attack",
            filename="test-report.md",
            metadata=sample_metadata,
        )

        expected = tmp_coo_root / "projects" / "swarm-attack" / "qa" / "2026-01-05_test-report.md"
        assert path == expected


# =============================================================================
# TestArchivalResult - Test result handling
# =============================================================================


class TestArchivalResult:
    """Tests for ArchivalResult return values."""

    def test_successful_result_has_path(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Successful archival returns result with valid path."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        assert result.path is not None
        assert isinstance(result.path, Path)

    def test_successful_result_has_no_error(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Successful archival returns result with no error message."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        assert result.error is None or result.error == ""

    def test_failed_result_has_error_message(self, spec_archiver, sample_spec_content, sample_metadata):
        """Failed archival returns result with error message."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="nonexistent-project",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert result.success is False
        assert result.error is not None
        assert len(result.error) > 0

    def test_result_includes_metadata_in_response(
        self, spec_archiver, sample_spec_content, sample_metadata
    ):
        """Archival result includes the metadata that was used."""
        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="test.md",
            metadata=sample_metadata,
        )

        assert result.metadata is not None
        assert result.metadata.author == sample_metadata.author
        assert result.metadata.approval_status == sample_metadata.approval_status


# =============================================================================
# TestApprovalStatusEnum - Test approval status values
# =============================================================================


class TestApprovalStatusEnum:
    """Tests for ApprovalStatus enum values."""

    def test_approval_status_values(self):
        """ApprovalStatus has expected values."""
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_approval_status_from_string(self):
        """ApprovalStatus can be created from string."""
        assert ApprovalStatus("approved") == ApprovalStatus.APPROVED
        assert ApprovalStatus("pending") == ApprovalStatus.PENDING
        assert ApprovalStatus("rejected") == ApprovalStatus.REJECTED

    def test_approval_status_invalid_raises(self):
        """Invalid approval status raises ValueError."""
        with pytest.raises(ValueError):
            ApprovalStatus("invalid")


# =============================================================================
# TestEdgeCases - Edge case handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in archival process."""

    def test_archive_empty_content(self, spec_archiver, sample_metadata):
        """Archiving empty content should fail or warn."""
        result = spec_archiver.archive(
            content="",
            project="swarm-attack",
            filename="empty.md",
            metadata=sample_metadata,
        )

        # Either fails or succeeds with warning
        if not result.success:
            assert "empty" in result.error.lower() or "content" in result.error.lower()

    def test_archive_very_long_filename(self, spec_archiver, sample_spec_content, sample_metadata):
        """Archiving with very long filename is handled gracefully."""
        long_name = "a" * 300 + ".md"

        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename=long_name,
            metadata=sample_metadata,
        )

        # Should either truncate or fail with clear error
        if result.success:
            assert len(result.path.name) <= 255  # filesystem limit
        else:
            assert "name" in result.error.lower() or "long" in result.error.lower()

    def test_archive_with_special_characters_in_content(
        self, spec_archiver, sample_metadata
    ):
        """Content with special characters is preserved."""
        special_content = """# Test Spec

Unicode: \u2713 \u2717 \u2192
Emojis: \U0001f680 \U0001f4a1
Code: `def foo(): pass`
Math: 2 + 2 = 4
"""
        result = spec_archiver.archive(
            content=special_content,
            project="swarm-attack",
            filename="special.md",
            metadata=sample_metadata,
        )

        assert result.success is True
        archived = result.path.read_text()
        assert "\u2713" in archived
        assert "\U0001f680" in archived

    def test_archive_without_metadata_date_uses_now(self, spec_archiver, sample_spec_content):
        """If metadata has no creation_date, current date is used."""
        metadata = ArchivalMetadata(
            creation_date=None,
            author="Author",
            approval_status=ApprovalStatus.PENDING,
        )

        result = spec_archiver.archive(
            content=sample_spec_content,
            project="swarm-attack",
            filename="no-date.md",
            metadata=metadata,
        )

        assert result.success is True
        # Should use today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in result.path.name
