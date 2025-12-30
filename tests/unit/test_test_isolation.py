# tests/unit/test_test_isolation.py
"""Tests for test file isolation (BUG-6)."""
import ast
from collections import defaultdict
from pathlib import Path


def test_all_generated_test_dirs_have_init():
    """BUG-6: All test directories must be proper packages."""
    generated_path = Path("tests/generated")
    if not generated_path.exists():
        return  # No generated tests yet - pass

    missing = []
    for test_dir in generated_path.iterdir():
        if test_dir.is_dir() and test_dir.name != "__pycache__":
            init_file = test_dir / "__init__.py"
            if not init_file.exists():
                missing.append(str(test_dir))

    assert not missing, f"Missing __init__.py in:\n" + "\n".join(missing)


def test_all_generated_tests_have_valid_syntax():
    """BUG-6: All generated test files must be syntactically valid."""
    generated_path = Path("tests/generated")
    if not generated_path.exists():
        return  # No generated tests yet - pass

    errors = []
    for test_file in generated_path.rglob("test_*.py"):
        try:
            ast.parse(test_file.read_text())
        except SyntaxError as e:
            errors.append(f"{test_file}:{e.lineno} - {e.msg}")

    assert not errors, f"Syntax errors in test files:\n" + "\n".join(errors)


def test_no_duplicate_test_basenames_without_init():
    """BUG-6: Test isolation requires __init__.py when basenames collide."""
    generated_path = Path("tests/generated")
    if not generated_path.exists():
        return  # No generated tests yet - pass

    basenames = defaultdict(list)
    for test_file in generated_path.rglob("test_*.py"):
        basenames[test_file.name].append(test_file)

    collisions_without_init = []
    for basename, files in basenames.items():
        if len(files) > 1:
            # Check if all parent dirs have __init__.py
            for f in files:
                if not (f.parent / "__init__.py").exists():
                    collisions_without_init.append(f"{basename}: {[str(p) for p in files]}")
                    break

    assert not collisions_without_init, (
        f"Colliding basenames without __init__.py:\n" + "\n".join(collisions_without_init)
    )
