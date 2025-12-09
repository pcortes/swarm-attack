"""
File system utilities for Feature Swarm.

This module provides safe file operations including:
- Atomic writes (write to temp file, then rename)
- Directory creation
- Path resolution relative to repo root
- File reading with encoding handling
- Glob pattern matching
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class FileSystemError(Exception):
    """Raised when a file system operation fails."""
    pass


def ensure_dir(path: str | Path) -> Path:
    """
    Create a directory if it does not exist.

    Creates parent directories as needed (like mkdir -p).

    Args:
        path: Path to the directory to create.

    Returns:
        Path: The path object for the created/existing directory.

    Raises:
        FileSystemError: If directory creation fails.
    """
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as e:
        raise FileSystemError(f"Failed to create directory {path}: {e}")


def safe_write(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically.

    Uses a temporary file and rename to ensure atomic write.
    This prevents partial writes if the process is interrupted.

    Args:
        path: Path to the file to write.
        content: Content to write to the file.
        encoding: Character encoding to use. Defaults to utf-8.

    Raises:
        FileSystemError: If write operation fails.
    """
    path = Path(path)

    # Ensure parent directory exists
    ensure_dir(path.parent)

    try:
        # Create temp file in same directory to ensure same filesystem
        # This allows atomic rename
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding=encoding) as f:
                f.write(content)

            # Atomic rename
            shutil.move(temp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        raise FileSystemError(f"Failed to write file {path}: {e}")


def safe_write_bytes(path: str | Path, content: bytes) -> None:
    """
    Write binary content to a file atomically.

    Uses a temporary file and rename to ensure atomic write.

    Args:
        path: Path to the file to write.
        content: Binary content to write to the file.

    Raises:
        FileSystemError: If write operation fails.
    """
    path = Path(path)

    # Ensure parent directory exists
    ensure_dir(path.parent)

    try:
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)

            shutil.move(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        raise FileSystemError(f"Failed to write file {path}: {e}")


def resolve_repo_path(
    relative: str | Path,
    config: Optional[SwarmConfig] = None
) -> Path:
    """
    Resolve a relative path to an absolute path based on repo root.

    Args:
        relative: Relative path to resolve.
        config: Optional SwarmConfig. If not provided, uses current directory.

    Returns:
        Path: Absolute path resolved relative to repo root.
    """
    if config is not None:
        base = Path(config.repo_root)
    else:
        base = Path.cwd()

    relative_path = Path(relative)

    # If already absolute, return as-is
    if relative_path.is_absolute():
        return relative_path

    return (base / relative_path).resolve()


def file_exists(path: str | Path) -> bool:
    """
    Check if a file exists.

    Args:
        path: Path to check.

    Returns:
        bool: True if file exists and is a file, False otherwise.
    """
    return Path(path).is_file()


def dir_exists(path: str | Path) -> bool:
    """
    Check if a directory exists.

    Args:
        path: Path to check.

    Returns:
        bool: True if path exists and is a directory, False otherwise.
    """
    return Path(path).is_dir()


def read_file(path: str | Path, encoding: str = "utf-8") -> str:
    """
    Read a file's contents with encoding handling.

    Args:
        path: Path to the file to read.
        encoding: Character encoding. Defaults to utf-8.

    Returns:
        str: Contents of the file.

    Raises:
        FileSystemError: If file cannot be read.
    """
    path = Path(path)

    if not path.exists():
        raise FileSystemError(f"File not found: {path}")

    if not path.is_file():
        raise FileSystemError(f"Not a file: {path}")

    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError as e:
        raise FileSystemError(f"Failed to decode file {path} with encoding {encoding}: {e}")
    except OSError as e:
        raise FileSystemError(f"Failed to read file {path}: {e}")


def read_file_bytes(path: str | Path) -> bytes:
    """
    Read a file's binary contents.

    Args:
        path: Path to the file to read.

    Returns:
        bytes: Binary contents of the file.

    Raises:
        FileSystemError: If file cannot be read.
    """
    path = Path(path)

    if not path.exists():
        raise FileSystemError(f"File not found: {path}")

    if not path.is_file():
        raise FileSystemError(f"Not a file: {path}")

    try:
        return path.read_bytes()
    except OSError as e:
        raise FileSystemError(f"Failed to read file {path}: {e}")


def list_files(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = False
) -> list[Path]:
    """
    List files matching a glob pattern in a directory.

    Args:
        directory: Directory to search in.
        pattern: Glob pattern to match. Defaults to "*" (all files).
        recursive: If True, search recursively (uses **/ prefix).

    Returns:
        list[Path]: List of matching file paths, sorted alphabetically.

    Raises:
        FileSystemError: If directory does not exist.
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileSystemError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise FileSystemError(f"Not a directory: {directory}")

    if recursive:
        matches = list(directory.rglob(pattern))
    else:
        matches = list(directory.glob(pattern))

    # Filter to files only and sort
    return sorted([p for p in matches if p.is_file()])


def list_dirs(
    directory: str | Path,
    pattern: str = "*"
) -> list[Path]:
    """
    List directories matching a glob pattern in a directory.

    Args:
        directory: Directory to search in.
        pattern: Glob pattern to match. Defaults to "*" (all).

    Returns:
        list[Path]: List of matching directory paths, sorted alphabetically.

    Raises:
        FileSystemError: If directory does not exist.
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileSystemError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise FileSystemError(f"Not a directory: {directory}")

    matches = list(directory.glob(pattern))

    # Filter to directories only and sort
    return sorted([p for p in matches if p.is_dir()])


def remove_file(path: str | Path) -> bool:
    """
    Remove a file if it exists.

    Args:
        path: Path to the file to remove.

    Returns:
        bool: True if file was removed, False if it didn't exist.

    Raises:
        FileSystemError: If removal fails.
    """
    path = Path(path)

    if not path.exists():
        return False

    if not path.is_file():
        raise FileSystemError(f"Not a file: {path}")

    try:
        path.unlink()
        return True
    except OSError as e:
        raise FileSystemError(f"Failed to remove file {path}: {e}")


def remove_dir(path: str | Path, recursive: bool = False) -> bool:
    """
    Remove a directory.

    Args:
        path: Path to the directory to remove.
        recursive: If True, remove contents recursively.

    Returns:
        bool: True if directory was removed, False if it didn't exist.

    Raises:
        FileSystemError: If removal fails.
    """
    path = Path(path)

    if not path.exists():
        return False

    if not path.is_dir():
        raise FileSystemError(f"Not a directory: {path}")

    try:
        if recursive:
            shutil.rmtree(path)
        else:
            path.rmdir()
        return True
    except OSError as e:
        raise FileSystemError(f"Failed to remove directory {path}: {e}")


def copy_file(src: str | Path, dst: str | Path) -> Path:
    """
    Copy a file to a new location.

    Args:
        src: Source file path.
        dst: Destination path.

    Returns:
        Path: Path to the copied file.

    Raises:
        FileSystemError: If copy fails.
    """
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        raise FileSystemError(f"Source file not found: {src}")

    if not src.is_file():
        raise FileSystemError(f"Source is not a file: {src}")

    # Ensure destination directory exists
    ensure_dir(dst.parent)

    try:
        shutil.copy2(src, dst)
        return dst
    except OSError as e:
        raise FileSystemError(f"Failed to copy {src} to {dst}: {e}")
