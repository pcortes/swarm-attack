#!/usr/bin/env python3
"""Migrate test files to globally unique names.

Renames: test_issue_N.py -> test_{feature_slug}_issue_N.py

Usage:
    python scripts/migrate_test_names.py --dry-run  # Preview changes
    python scripts/migrate_test_names.py            # Execute rename
"""
import argparse
import re
import shutil
from pathlib import Path


def get_feature_slug(feature_dir: Path) -> str:
    """Convert feature directory name to valid Python identifier."""
    return feature_dir.name.replace("-", "_")


def migrate_tests(dry_run: bool = True) -> list[tuple[Path, Path]]:
    """Migrate test files to new naming convention.

    Returns list of (old_path, new_path) tuples.
    """
    generated = Path("tests/generated")
    if not generated.exists():
        print(f"Directory not found: {generated}")
        return []

    renames = []

    for feature_dir in sorted(generated.iterdir()):
        if not feature_dir.is_dir():
            continue

        # Skip __pycache__ directories
        if feature_dir.name == "__pycache__":
            continue

        feature_slug = get_feature_slug(feature_dir)

        # Find test_issue_*.py files (old naming)
        for test_file in sorted(feature_dir.glob("test_issue_*.py")):
            # Extract issue number
            match = re.match(r"test_issue_(\d+)\.py", test_file.name)
            if not match:
                continue

            issue_num = match.group(1)
            new_name = f"test_{feature_slug}_issue_{issue_num}.py"
            new_path = feature_dir / new_name

            if new_path.exists():
                print(f"SKIP (exists): {test_file} -> {new_path}")
                continue

            renames.append((test_file, new_path))

            if dry_run:
                print(f"WOULD RENAME: {test_file} -> {new_path}")
            else:
                print(f"RENAMING: {test_file} -> {new_path}")
                shutil.move(str(test_file), str(new_path))

    return renames


def main():
    parser = argparse.ArgumentParser(description="Migrate test file names")
    parser.add_argument("--dry-run", action="store_true", help="Preview without renaming")
    args = parser.parse_args()

    renames = migrate_tests(dry_run=args.dry_run)

    print(f"\nTotal: {len(renames)} files {'would be' if args.dry_run else ''} renamed")

    if args.dry_run and renames:
        print("\nRun without --dry-run to execute renames.")


if __name__ == "__main__":
    main()
