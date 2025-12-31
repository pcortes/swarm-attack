"""Git commit discovery functionality."""

import subprocess
import re
from typing import Optional

from swarm_attack.commit_review.models import CommitInfo


def discover_commits(
    repo_path: str,
    since: str = "24 hours ago",
    branch: Optional[str] = None,
) -> list[CommitInfo]:
    """Discover commits from a git repository.

    Args:
        repo_path: Path to the git repository
        since: Time range (git date format, e.g., "24 hours ago")
        branch: Optional branch name to filter commits

    Returns:
        List of CommitInfo objects for matching commits

    Raises:
        RuntimeError: If git command fails
    """
    # Build git log command
    # Format: sha|author|email|date|subject|stats
    format_str = "%H|%an|%ae|%ai|%s"
    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        f"--since={since}",
        f"--format={format_str}",
        "--shortstat",
    ]

    if branch:
        cmd.append(branch)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

    return _parse_git_log(result.stdout)


def _parse_git_log(output: str) -> list[CommitInfo]:
    """Parse git log output into CommitInfo objects."""
    if not output.strip():
        return []

    commits = []
    lines = output.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Parse main commit line
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 5:
                sha = parts[0][:7]  # Short SHA
                author = parts[1]
                email = parts[2]
                timestamp = parts[3]
                message = parts[4]

                # Look for stats - might be in parts[5] or on next line
                files_changed = 0
                insertions = 0
                deletions = 0

                # Check if stats are on same line (parts[5])
                if len(parts) >= 6:
                    stats = _parse_stats(parts[5])
                    if stats:
                        files_changed = stats["files"]
                        insertions = stats["insertions"]
                        deletions = stats["deletions"]
                # Check next line for stats
                elif i + 1 < len(lines):
                    stats_line = lines[i + 1].strip()
                    stats = _parse_stats(stats_line)
                    if stats:
                        files_changed = stats["files"]
                        insertions = stats["insertions"]
                        deletions = stats["deletions"]
                        i += 1

                commits.append(
                    CommitInfo(
                        sha=sha,
                        author=author,
                        email=email,
                        timestamp=timestamp,
                        message=message,
                        files_changed=files_changed,
                        insertions=insertions,
                        deletions=deletions,
                        changed_files=[],
                    )
                )

        i += 1

    return commits


def _parse_stats(line: str) -> Optional[dict]:
    """Parse git shortstat line.

    Examples:
        "3 files changed, 50 insertions(+), 30 deletions(-)"
        "1 file changed, 10 insertions(+)"
    """
    if "file" not in line:
        return None

    result = {"files": 0, "insertions": 0, "deletions": 0}

    # Match files
    files_match = re.search(r"(\d+) files? changed", line)
    if files_match:
        result["files"] = int(files_match.group(1))

    # Match insertions
    ins_match = re.search(r"(\d+) insertions?\(\+\)", line)
    if ins_match:
        result["insertions"] = int(ins_match.group(1))

    # Match deletions
    del_match = re.search(r"(\d+) deletions?\(-\)", line)
    if del_match:
        result["deletions"] = int(del_match.group(1))

    return result
