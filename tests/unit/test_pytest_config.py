# tests/unit/test_pytest_config.py
"""Tests for pytest configuration (BUG-17)."""
import tomllib


def test_pytest_asyncio_configured():
    """BUG-17: pytest-asyncio loop scope must be configured."""
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    pytest_opts = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "asyncio_default_fixture_loop_scope" in pytest_opts
    assert pytest_opts["asyncio_default_fixture_loop_scope"] == "function"


def test_pytest_testpaths_configured():
    """Ensure test discovery paths are configured."""
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    pytest_opts = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "testpaths" in pytest_opts
    assert "tests" in pytest_opts["testpaths"]


def test_pytest_collection_warning_filtered():
    """Ensure PytestCollectionWarning is filtered."""
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    pytest_opts = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "filterwarnings" in pytest_opts
    has_collection_filter = any(
        "PytestCollectionWarning" in w for w in pytest_opts["filterwarnings"]
    )
    assert has_collection_filter, "PytestCollectionWarning should be filtered"


def test_pytest_importlib_mode_configured():
    """BUG-6: importlib mode prevents module name collisions."""
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    pytest_opts = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "addopts" in pytest_opts
    assert "--import-mode=importlib" in pytest_opts["addopts"]
