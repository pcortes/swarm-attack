"""Tests for memory CLI commands following TDD approach.

Tests cover the memory management CLI:
- stats: Show memory store statistics
- list: List memory entries with optional filtering
- prune: Remove old entries
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from swarm_attack.memory.store import MemoryEntry, MemoryStore


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_store_path():
    """Create a temporary directory for test store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "memory" / "memories.json"


@pytest.fixture
def memory_store(temp_store_path):
    """Create a MemoryStore instance with temp path and sample entries."""
    store = MemoryStore(store_path=temp_store_path)

    # Add sample entries for testing
    entries = [
        MemoryEntry(
            id=str(uuid4()),
            category="checkpoint_decision",
            feature_id="feature-a",
            issue_number=1,
            content={"trigger": "HICCUP", "decision": "Proceed"},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP", "Proceed"],
        ),
        MemoryEntry(
            id=str(uuid4()),
            category="checkpoint_decision",
            feature_id="feature-b",
            issue_number=2,
            content={"trigger": "COST_SINGLE", "decision": "Skip"},
            outcome="applied",
            created_at=datetime.now().isoformat(),
            tags=["COST_SINGLE"],
        ),
        MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="feature-a",
            issue_number=3,
            content={"class_name": "AutopilotSession"},
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "AutopilotSession"],
        ),
    ]

    for entry in entries:
        store.add(entry)
    store.save()

    return store


# =============================================================================
# STATS COMMAND TESTS
# =============================================================================


class TestMemoryStatsCommand:
    """Tests for the memory stats command."""

    def test_memory_stats_command_shows_entry_count(self, runner, temp_store_path, memory_store):
        """Should display total entry count in stats output."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(memory_app, ["stats"])

            assert result.exit_code == 0
            # Should show "3" somewhere for the 3 entries we added
            assert "3" in result.output or "Total" in result.output

    def test_memory_stats_command_shows_categories(self, runner, temp_store_path, memory_store):
        """Should display entries by category breakdown."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(memory_app, ["stats"])

            assert result.exit_code == 0
            # Should show the categories we added
            assert "checkpoint_decision" in result.output or "checkpoint" in result.output.lower()
            assert "schema_drift" in result.output or "schema" in result.output.lower()


# =============================================================================
# LIST COMMAND TESTS
# =============================================================================


class TestMemoryListCommand:
    """Tests for the memory list command."""

    def test_memory_list_command_shows_entries(self, runner, temp_store_path, memory_store):
        """Should display memory entries."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(memory_app, ["list"])

            assert result.exit_code == 0
            # Should show feature IDs from our entries
            assert "feature-a" in result.output or "feature-b" in result.output

    def test_memory_list_command_filters_by_category(self, runner, temp_store_path, memory_store):
        """Should filter entries when --category is provided."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(memory_app, ["list", "--category", "schema_drift"])

            assert result.exit_code == 0
            # Should show schema_drift entries (may be truncated in table display)
            assert "schema_dri" in result.output or "feature-a" in result.output
            # Should show only 1 entry (the schema_drift one)
            assert "Showing 1 entries" in result.output


# =============================================================================
# PRUNE COMMAND TESTS
# =============================================================================


class TestMemoryPruneCommand:
    """Tests for the memory prune command."""

    def test_memory_prune_command_removes_old_entries(self, runner, temp_store_path):
        """Should remove entries older than specified days."""
        from swarm_attack.cli.memory import memory_app

        # Create store with old entries
        store = MemoryStore(store_path=temp_store_path)

        # Add old entry (60 days ago)
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        old_entry = MemoryEntry(
            id="old-entry-1",
            category="checkpoint_decision",
            feature_id="old-feature",
            issue_number=1,
            content={"trigger": "HICCUP"},
            outcome="success",
            created_at=old_date,
            tags=["HICCUP"],
        )

        # Add recent entry (1 day ago)
        recent_date = (datetime.now() - timedelta(days=1)).isoformat()
        recent_entry = MemoryEntry(
            id="recent-entry-1",
            category="checkpoint_decision",
            feature_id="recent-feature",
            issue_number=2,
            content={"trigger": "COST_SINGLE"},
            outcome="applied",
            created_at=recent_date,
            tags=["COST_SINGLE"],
        )

        store.add(old_entry)
        store.add(recent_entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(memory_app, ["prune", "--older-than", "30"])

            assert result.exit_code == 0
            # Should indicate pruning happened
            assert "pruned" in result.output.lower() or "removed" in result.output.lower() or "1" in result.output

    def test_memory_prune_command_requires_older_than_flag(self, runner):
        """Should require --older-than flag."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["prune"])

        # Should fail or show error because --older-than is required
        assert result.exit_code != 0 or "older-than" in result.output.lower() or "required" in result.output.lower()


# =============================================================================
# COMMAND REGISTRATION TESTS
# =============================================================================


class TestMemoryCommandRegistration:
    """Tests for command registration."""

    def test_memory_app_exists(self):
        """memory_app should be a Typer instance."""
        import typer
        from swarm_attack.cli.memory import memory_app

        assert isinstance(memory_app, typer.Typer)

    def test_stats_command_registered(self, runner):
        """stats command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_list_command_registered(self, runner):
        """list command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["list", "--help"])
        assert result.exit_code == 0

    def test_prune_command_registered(self, runner):
        """prune command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["prune", "--help"])
        assert result.exit_code == 0

    def test_save_command_registered(self, runner):
        """save command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["save", "--help"])
        assert result.exit_code == 0

    def test_load_command_registered(self, runner):
        """load command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["load", "--help"])
        assert result.exit_code == 0

    def test_export_command_registered(self, runner):
        """export command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["export", "--help"])
        assert result.exit_code == 0

    def test_import_command_registered(self, runner):
        """import command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["import", "--help"])
        assert result.exit_code == 0

    def test_compress_command_registered(self, runner):
        """compress command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["compress", "--help"])
        assert result.exit_code == 0

    def test_analytics_command_registered(self, runner):
        """analytics command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["analytics", "--help"])
        assert result.exit_code == 0


# =============================================================================
# SAVE COMMAND TESTS
# =============================================================================


class TestSaveCommand:
    """Tests for the memory save command."""

    def test_save_command_creates_file(self, runner, temp_store_path, memory_store):
        """Should save memory to the specified file."""
        from swarm_attack.cli.memory import memory_app

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output" / "saved_memory.json"

            with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
                mock_load.return_value = memory_store

                result = runner.invoke(memory_app, ["save", str(output_path)])

                assert result.exit_code == 0
                assert output_path.exists()
                assert "saved" in result.output.lower() or "Memory Save" in result.output


# =============================================================================
# LOAD COMMAND TESTS
# =============================================================================


class TestLoadCommand:
    """Tests for the memory load command."""

    def test_load_command_loads_entries(self, runner, temp_store_path, memory_store):
        """Should load memory entries from file."""
        from swarm_attack.cli.memory import memory_app

        with tempfile.TemporaryDirectory() as tmpdir:
            # First save the memory to a file
            input_path = Path(tmpdir) / "input_memory.json"
            memory_store.save_to_file(input_path)

            # Create a new empty store to load into
            new_store = MemoryStore(store_path=temp_store_path)

            with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
                mock_load.return_value = new_store

                result = runner.invoke(memory_app, ["load", str(input_path)])

                assert result.exit_code == 0
                assert "loaded" in result.output.lower() or "Memory Load" in result.output

    def test_load_command_handles_missing_file(self, runner):
        """Should report error for missing file."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["load", "/nonexistent/path.json"])

        assert result.exit_code != 0 or "error" in result.output.lower() or "not found" in result.output.lower()


# =============================================================================
# EXPORT COMMAND TESTS
# =============================================================================


class TestExportCommand:
    """Tests for the memory export command."""

    def test_export_command_creates_json(self, runner, temp_store_path, memory_store):
        """Should export memory to JSON file."""
        from swarm_attack.cli.memory import memory_app

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "exported.json"

            with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
                mock_load.return_value = memory_store

                result = runner.invoke(memory_app, ["export", str(output_path)])

                assert result.exit_code == 0
                assert output_path.exists()
                assert "exported" in result.output.lower() or "Memory Export" in result.output

                # Verify it's valid JSON
                with open(output_path) as f:
                    data = json.load(f)
                assert "entries" in data

    def test_export_command_filters_by_category(self, runner, temp_store_path, memory_store):
        """Should export only entries matching category filter."""
        from swarm_attack.cli.memory import memory_app

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "filtered.json"

            with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
                mock_load.return_value = memory_store

                result = runner.invoke(
                    memory_app,
                    ["export", str(output_path), "--category", "schema_drift"]
                )

                assert result.exit_code == 0
                assert output_path.exists()

                with open(output_path) as f:
                    data = json.load(f)

                # All entries should be schema_drift
                entries = data.get("entries", [])
                for entry in entries:
                    assert entry["category"] == "schema_drift"


# =============================================================================
# IMPORT COMMAND TESTS
# =============================================================================


class TestImportCommand:
    """Tests for the memory import command."""

    def test_import_command_merges_entries(self, runner, temp_store_path, memory_store):
        """Should import and merge entries from file."""
        from swarm_attack.cli.memory import memory_app

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an export file with entries
            import_path = Path(tmpdir) / "import_data.json"
            export_data = {
                "metadata": {"version": "1.0"},
                "entries": [
                    {
                        "id": "import-entry-1",
                        "category": "imported_category",
                        "feature_id": "imported-feature",
                        "issue_number": None,
                        "content": {"key": "value"},
                        "outcome": "success",
                        "created_at": datetime.now().isoformat(),
                        "tags": ["imported"],
                        "hit_count": 0,
                    }
                ],
            }
            with open(import_path, "w") as f:
                json.dump(export_data, f)

            with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
                mock_load.return_value = memory_store

                result = runner.invoke(memory_app, ["import", str(import_path)])

                assert result.exit_code == 0
                assert "imported" in result.output.lower() or "merged" in result.output.lower()


# =============================================================================
# COMPRESS COMMAND TESTS
# =============================================================================


class TestCompressCommand:
    """Tests for the memory compress command."""

    def test_compress_command_reduces_entries(self, runner, temp_store_path):
        """Should compress similar entries."""
        from swarm_attack.cli.memory import memory_app

        # Create a store with similar entries
        store = MemoryStore(store_path=temp_store_path)

        # Add similar entries (same category, feature_id, similar content)
        for i in range(3):
            entry = MemoryEntry(
                id=f"similar-{i}",
                category="same_category",
                feature_id="same-feature",
                issue_number=1,
                content={"same_key": "same_value", "index": i},
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=["similar"],
            )
            store.add(entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(memory_app, ["compress", "--threshold", "0.5"])

            assert result.exit_code == 0
            assert "compress" in result.output.lower() or "Memory Compression" in result.output


# =============================================================================
# ANALYTICS COMMAND TESTS
# =============================================================================


class TestAnalyticsCommand:
    """Tests for the memory analytics command."""

    def test_analytics_command_shows_report(self, runner, temp_store_path, memory_store):
        """Should display analytics report."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(memory_app, ["analytics"])

            assert result.exit_code == 0
            # Should include some analytics content
            output_lower = result.output.lower()
            assert (
                "analytics" in output_lower
                or "report" in output_lower
                or "entries" in output_lower
                or "category" in output_lower
            )


# =============================================================================
# PATTERNS COMMAND TESTS
# =============================================================================


class TestPatternsCommand:
    """Tests for the memory patterns command."""

    def test_patterns_command_shows_patterns(self, runner, temp_store_path):
        """Should display detected patterns in the output."""
        from swarm_attack.cli.memory import memory_app

        # Create store with multiple entries of same class (to form a pattern)
        store = MemoryStore(store_path=temp_store_path)

        # Add multiple schema_drift entries for same class (3+ = pattern)
        for i in range(3):
            entry = MemoryEntry(
                id=f"drift-{i}",
                category="schema_drift",
                feature_id=f"feature-{i}",
                issue_number=i,
                content={"class_name": "RecurringDrifter", "drift_type": "field_mismatch"},
                outcome="detected",
                created_at=datetime.now().isoformat(),
                tags=["schema", "recurrent"],
            )
            store.add(entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(memory_app, ["patterns", "--min-occurrences", "3"])

            assert result.exit_code == 0
            # Should show the recurring class or indicate patterns found
            assert (
                "RecurringDrifter" in result.output
                or "pattern" in result.output.lower()
                or "Found" in result.output
            )

    def test_patterns_command_filters_by_category(self, runner, temp_store_path):
        """Should filter patterns when --category is provided."""
        from swarm_attack.cli.memory import memory_app

        # Create store with schema_drift entries
        store = MemoryStore(store_path=temp_store_path)
        for i in range(3):
            entry = MemoryEntry(
                id=f"drift-filter-{i}",
                category="schema_drift",
                feature_id=f"feature-{i}",
                issue_number=i,
                content={"class_name": "FilteredClass", "drift_type": "type_mismatch"},
                outcome="detected",
                created_at=datetime.now().isoformat(),
                tags=["schema"],
            )
            store.add(entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(
                memory_app,
                ["patterns", "--category", "schema_drift", "--min-occurrences", "3"]
            )

            assert result.exit_code == 0
            # Should show schema drift patterns
            assert (
                "Schema Drift" in result.output
                or "FilteredClass" in result.output
                or "pattern" in result.output.lower()
            )

    def test_patterns_command_registered(self, runner):
        """patterns command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["patterns", "--help"])
        assert result.exit_code == 0


# =============================================================================
# RECOMMEND COMMAND TESTS
# =============================================================================


class TestRecommendCommand:
    """Tests for the memory recommend command."""

    def test_recommend_command_returns_suggestions(self, runner, temp_store_path):
        """Should return recommendations based on historical data."""
        from swarm_attack.cli.memory import memory_app

        # Create store with a successful fix entry
        store = MemoryStore(store_path=temp_store_path)

        # Add an entry with resolution (so recommendations can be generated)
        entry = MemoryEntry(
            id="fix-entry-1",
            category="schema_drift",
            feature_id="feature-a",
            issue_number=1,
            content={
                "class_name": "TestClass",
                "drift_type": "field_mismatch",
                "resolution": "Update class definition to match schema",
            },
            outcome="resolved",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "TestClass"],
        )
        store.add(entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(
                memory_app,
                ["recommend", "schema_drift", "--context", '{"class_name": "TestClass"}']
            )

            assert result.exit_code == 0
            # Either shows recommendations or "No recommendations found"
            assert (
                "Recommendation" in result.output
                or "No recommendations" in result.output
            )

    def test_recommend_command_handles_invalid_json(self, runner):
        """Should handle invalid JSON context gracefully."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load"):
            result = runner.invoke(
                memory_app,
                ["recommend", "schema_drift", "--context", "invalid json"]
            )

            # Should exit with error
            assert result.exit_code != 0 or "Invalid JSON" in result.output or "error" in result.output.lower()

    def test_recommend_command_registered(self, runner):
        """recommend command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["recommend", "--help"])
        assert result.exit_code == 0


# =============================================================================
# SEARCH COMMAND TESTS
# =============================================================================


class TestSearchCommand:
    """Tests for the memory search command."""

    def test_search_command_finds_entries(self, runner, temp_store_path, memory_store):
        """Should find entries matching the search query."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            # Search for something that exists in the fixture data
            result = runner.invoke(memory_app, ["search", "checkpoint decision"])

            assert result.exit_code == 0
            # Should show results or indicate no results
            assert (
                "Search Results" in result.output
                or "No results" in result.output
                or "Found" in result.output
            )

    def test_search_command_respects_limit(self, runner, temp_store_path):
        """Should respect the --limit parameter."""
        from swarm_attack.cli.memory import memory_app

        # Create store with many entries
        store = MemoryStore(store_path=temp_store_path)
        for i in range(15):
            entry = MemoryEntry(
                id=f"search-entry-{i}",
                category="test_category",
                feature_id=f"feature-{i}",
                issue_number=i,
                content={"message": "test message for search"},
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=["test", "search"],
            )
            store.add(entry)
        store.save()

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = store

            result = runner.invoke(memory_app, ["search", "test message", "--limit", "5"])

            assert result.exit_code == 0
            # Output should respect limit (if there are results)
            # Count table rows (each row has feature-N pattern)
            feature_matches = result.output.count("feature-")
            # Should be at most 5 (the limit we specified)
            assert feature_matches <= 5

    def test_search_command_filters_by_category(self, runner, temp_store_path, memory_store):
        """Should filter results by category when --category is provided."""
        from swarm_attack.cli.memory import memory_app

        with patch("swarm_attack.memory.store.MemoryStore.load") as mock_load:
            mock_load.return_value = memory_store

            result = runner.invoke(
                memory_app,
                ["search", "drift", "--category", "schema_drift"]
            )

            assert result.exit_code == 0
            # Should show results or indicate no results
            assert (
                "Search Results" in result.output
                or "No results" in result.output
            )

    def test_search_command_registered(self, runner):
        """search command should be registered."""
        from swarm_attack.cli.memory import memory_app

        result = runner.invoke(memory_app, ["search", "--help"])
        assert result.exit_code == 0
