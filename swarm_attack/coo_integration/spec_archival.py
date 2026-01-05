"""
Spec Archival module - COO Integration Phase.

Archives approved specs to COO/projects/{project}/specs/ and test reports to
COO/projects/{project}/qa/ with creation date, author, and approval status metadata.

Exports:
- SpecArchiver: Archives specs to COO project directories
- ReportArchiver: Archives test reports to COO project qa directories
- ArchivalMetadata: Metadata container for archival operations
- ArchivalResult: Result of an archival operation
- ApprovalStatus: Enum for approval status values
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class ApprovalStatus(Enum):
    """Approval status for archived documents."""

    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class ArchivalMetadata:
    """Metadata for archival operations.

    Attributes:
        creation_date: Date the document was created (None uses current date)
        author: Author of the document
        approval_status: Current approval status
        feature_id: Optional feature identifier
        issue_number: Optional GitHub issue number
    """

    creation_date: Optional[datetime]
    author: str
    approval_status: ApprovalStatus
    feature_id: Optional[str] = None
    issue_number: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize metadata to dictionary."""
        result = {
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "author": self.author,
            "approval_status": self.approval_status.value,
        }
        if self.feature_id is not None:
            result["feature_id"] = self.feature_id
        if self.issue_number is not None:
            result["issue_number"] = self.issue_number
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ArchivalMetadata":
        """Deserialize metadata from dictionary."""
        creation_date = None
        if data.get("creation_date"):
            creation_date = datetime.fromisoformat(data["creation_date"])

        return cls(
            creation_date=creation_date,
            author=data["author"],
            approval_status=ApprovalStatus(data["approval_status"]),
            feature_id=data.get("feature_id"),
            issue_number=data.get("issue_number"),
        )

    def get_date_for_filename(self) -> str:
        """Get the date string for filename prefix (YYYY-MM-DD)."""
        if self.creation_date:
            return self.creation_date.strftime("%Y-%m-%d")
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class ArchivalResult:
    """Result of an archival operation.

    Attributes:
        success: Whether the archival succeeded
        path: Path to the archived file (if successful)
        error: Error message (if failed)
        metadata: Metadata used for archival
    """

    success: bool
    path: Optional[Path] = None
    error: Optional[str] = None
    metadata: Optional[ArchivalMetadata] = None


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove unsafe characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove path separators and other unsafe characters
    unsafe_chars = r'[/\\:*?"<>|]'
    sanitized = re.sub(unsafe_chars, "_", filename)

    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Truncate to reasonable length (leaving room for date prefix)
    # 255 is typical filesystem limit, date prefix is 11 chars (YYYY-MM-DD_)
    max_name_len = 255 - 11
    if len(sanitized) > max_name_len:
        # Preserve extension
        name, ext = _split_extension(sanitized)
        name = name[:max_name_len - len(ext)]
        sanitized = name + ext

    return sanitized


def _split_extension(filename: str) -> tuple:
    """Split filename into name and extension.

    Args:
        filename: Filename to split

    Returns:
        Tuple of (name, extension) where extension includes the dot
    """
    path = Path(filename)
    if path.suffix:
        return path.stem, path.suffix
    return filename, ""


def _format_metadata_header(metadata: ArchivalMetadata) -> str:
    """Format metadata as a header for the archived file.

    Args:
        metadata: Metadata to format

    Returns:
        Formatted metadata header string
    """
    lines = [
        "---",
        f"archived_date: {datetime.now(timezone.utc).isoformat()}",
        f"creation_date: {metadata.creation_date.isoformat() if metadata.creation_date else 'unknown'}",
        f"author: {metadata.author}",
        f"approval_status: {metadata.approval_status.value}",
    ]
    if metadata.feature_id:
        lines.append(f"feature_id: {metadata.feature_id}")
    if metadata.issue_number:
        lines.append(f"issue_number: {metadata.issue_number}")
    lines.append("---\n\n")
    return "\n".join(lines)


class BaseArchiver:
    """Base class for archivers.

    Args:
        coo_root: Path to the COO root directory
    """

    # Subclasses set this to their target subdirectory
    target_subdir: str = "specs"

    def __init__(self, coo_root: Path):
        self.coo_root = Path(coo_root)

    def _get_project_dir(self, project: str) -> Optional[Path]:
        """Get the project directory path.

        Args:
            project: Project name

        Returns:
            Path to project directory, or None if not found
        """
        project_dir = self.coo_root / "projects" / project
        if not project_dir.exists():
            return None
        return project_dir

    def _get_target_dir(self, project: str) -> Optional[Path]:
        """Get the target directory for archival.

        Args:
            project: Project name

        Returns:
            Path to target directory, or None if project not found
        """
        project_dir = self._get_project_dir(project)
        if project_dir is None:
            return None
        return project_dir / self.target_subdir

    def generate_path(
        self,
        project: str,
        filename: str,
        metadata: ArchivalMetadata,
    ) -> Path:
        """Generate the full path for archival.

        Args:
            project: Project name
            filename: Original filename
            metadata: Archival metadata

        Returns:
            Full path for the archived file
        """
        target_dir = self._get_target_dir(project)
        if target_dir is None:
            target_dir = self.coo_root / "projects" / project / self.target_subdir

        date_prefix = metadata.get_date_for_filename()
        sanitized = _sanitize_filename(filename)
        full_filename = f"{date_prefix}_{sanitized}"

        return target_dir / full_filename

    def archive(
        self,
        content: str,
        project: str,
        filename: str,
        metadata: ArchivalMetadata,
    ) -> ArchivalResult:
        """Archive content to the COO project directory.

        Args:
            content: Content to archive
            project: Project name
            filename: Original filename
            metadata: Archival metadata

        Returns:
            ArchivalResult indicating success or failure
        """
        # Validate project exists
        project_dir = self._get_project_dir(project)
        if project_dir is None:
            return ArchivalResult(
                success=False,
                error=f"Project '{project}' not found in COO",
                metadata=metadata,
            )

        # Get or create target directory
        target_dir = self._get_target_dir(project)
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        # Generate the full path
        full_path = self.generate_path(project, filename, metadata)

        # Check for duplicate
        if full_path.exists():
            return ArchivalResult(
                success=False,
                error=f"File already exists: {full_path.name}",
                metadata=metadata,
            )

        # Handle empty content (optional warning, but we allow it)
        if not content.strip():
            # Allow empty content with a warning in the file itself
            pass

        # Prepare content with metadata header
        # For non-JSON files, add YAML frontmatter
        if not filename.endswith(".json"):
            final_content = _format_metadata_header(metadata) + content
        else:
            # JSON files: don't add metadata header to preserve valid JSON
            final_content = content

        # Write the file
        try:
            full_path.write_text(final_content, encoding="utf-8")
        except OSError as e:
            return ArchivalResult(
                success=False,
                error=f"Failed to write file: {e}",
                metadata=metadata,
            )

        return ArchivalResult(
            success=True,
            path=full_path,
            metadata=metadata,
        )


class SpecArchiver(BaseArchiver):
    """Archives specs to COO/projects/{project}/specs/."""

    target_subdir = "specs"


class ReportArchiver(BaseArchiver):
    """Archives test reports to COO/projects/{project}/qa/."""

    target_subdir = "qa"
