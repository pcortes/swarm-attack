"""
Verification status tracking for features.

This module tracks per-feature, per-issue test verification status at
.swarm/features/{feature_id}/verification.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class IssueVerification:
    """
    Verification status for a single issue.

    Tracks whether tests for this issue are passing, failing, or untested.
    """
    issue_number: int
    title: str = ""
    status: str = "untested"  # "passing", "failing", "untested"
    test_count: int = 0
    last_verified: Optional[str] = None  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IssueVerification:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class FeatureVerification:
    """
    Verification status for an entire feature.

    Contains verification status for all issues in the feature.
    """
    feature_id: str
    last_updated: str
    issues: list[IssueVerification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "feature_id": self.feature_id,
            "last_updated": self.last_updated,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureVerification:
        """Create from dictionary."""
        issues = [
            IssueVerification.from_dict(issue)
            for issue in data.get("issues", [])
        ]
        return cls(
            feature_id=data["feature_id"],
            last_updated=data["last_updated"],
            issues=issues,
        )


class VerificationTracker:
    """
    Track per-feature test verification status.

    Stores verification.json files at .swarm/features/{feature_id}/verification.json
    """

    def __init__(self, swarm_dir: Path) -> None:
        """
        Initialize the verification tracker.

        Args:
            swarm_dir: Path to the .swarm directory.
        """
        self._swarm_dir = Path(swarm_dir)

    def _get_path(self, feature_id: str) -> Path:
        """Get path to verification.json for a feature."""
        return self._swarm_dir / "features" / feature_id / "verification.json"

    def _ensure_directory(self, feature_id: str) -> None:
        """Ensure the feature directory exists."""
        path = self._get_path(feature_id)
        path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, feature_id: str) -> Optional[FeatureVerification]:
        """
        Load verification status for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            FeatureVerification if exists, None otherwise.
        """
        path = self._get_path(feature_id)
        if not path.exists():
            return None

        try:
            with path.open() as f:
                data = json.load(f)
            return FeatureVerification.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _save(self, feature_id: str, verification: FeatureVerification) -> None:
        """
        Save verification status to disk.

        Args:
            feature_id: The feature identifier.
            verification: The verification data to save.
        """
        self._ensure_directory(feature_id)
        path = self._get_path(feature_id)

        with path.open("w") as f:
            json.dump(verification.to_dict(), f, indent=2)

    def update_issue_status(
        self,
        feature_id: str,
        issue_number: int,
        status: str,
        test_count: int = 0,
        title: str = "",
    ) -> None:
        """
        Update verification status for an issue.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
            status: Status string ("passing", "failing", "untested").
            test_count: Number of tests for this issue.
            title: Optional issue title.
        """
        verification = self.load(feature_id)
        now = datetime.now().isoformat()

        if verification is None:
            verification = FeatureVerification(
                feature_id=feature_id,
                last_updated=now,
                issues=[],
            )

        # Find existing issue or create new one
        issue_found = False
        for issue in verification.issues:
            if issue.issue_number == issue_number:
                issue.status = status
                issue.test_count = test_count
                issue.last_verified = now
                if title:
                    issue.title = title
                issue_found = True
                break

        if not issue_found:
            verification.issues.append(
                IssueVerification(
                    issue_number=issue_number,
                    title=title,
                    status=status,
                    test_count=test_count,
                    last_verified=now,
                )
            )

        verification.last_updated = now
        self._save(feature_id, verification)

    def get_issue_status(
        self,
        feature_id: str,
        issue_number: int
    ) -> Optional[IssueVerification]:
        """
        Get verification status for a specific issue.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.

        Returns:
            IssueVerification if found, None otherwise.
        """
        verification = self.load(feature_id)
        if verification is None:
            return None

        for issue in verification.issues:
            if issue.issue_number == issue_number:
                return issue

        return None

    def get_failing_issues(self, feature_id: str) -> list[IssueVerification]:
        """
        Get all issues with failing tests.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of IssueVerification objects with status="failing".
        """
        verification = self.load(feature_id)
        if verification is None:
            return []

        return [
            issue for issue in verification.issues
            if issue.status == "failing"
        ]

    def all_passing(self, feature_id: str) -> bool:
        """
        Check if all issues have passing tests.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if all issues are passing (or no issues exist).
        """
        verification = self.load(feature_id)
        if verification is None or not verification.issues:
            return True

        return all(
            issue.status == "passing"
            for issue in verification.issues
        )
