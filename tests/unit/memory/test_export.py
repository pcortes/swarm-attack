"""
TDD tests for Memory Export/Import functionality.

Tests for MemoryExporter class in swarm_attack/memory/export.py.
These tests are written in TDD RED phase - they should FAIL because
MemoryExporter doesn't exist yet.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from swarm_attack.memory.store import MemoryEntry, MemoryStore

# This import should fail initially (RED phase)
from swarm_attack.memory.export import MemoryExporter


@pytest.fixture
def sample_entries() -> list[MemoryEntry]:
    """Create sample memory entries for testing."""
    return [
        MemoryEntry(
            id="entry-1",
            category="schema_drift",
            feature_id="feature-a",
            issue_number=1,
            content={"class_name": "UserModel", "conflict": "duplicate field"},
            outcome="detected",
            created_at="2025-01-01T10:00:00",
            tags=["model", "user"],
            hit_count=5,
        ),
        MemoryEntry(
            id="entry-2",
            category="test_failure",
            feature_id="feature-b",
            issue_number=2,
            content={"test_path": "tests/test_user.py", "error": "AssertionError"},
            outcome="failed",
            created_at="2025-01-02T11:00:00",
            tags=["test", "regression"],
            hit_count=3,
        ),
        MemoryEntry(
            id="entry-3",
            category="schema_drift",
            feature_id="feature-c",
            issue_number=3,
            content={"class_name": "OrderModel", "conflict": "missing method"},
            outcome="resolved",
            created_at="2025-01-03T12:00:00",
            tags=["model", "order"],
            hit_count=1,
        ),
    ]


@pytest.fixture
def populated_store(sample_entries: list[MemoryEntry], tmp_path: Path) -> MemoryStore:
    """Create a memory store populated with sample entries."""
    store = MemoryStore(store_path=tmp_path / "memories.json")
    for entry in sample_entries:
        store.add(entry)
    return store


@pytest.fixture
def exporter() -> MemoryExporter:
    """Create a MemoryExporter instance."""
    return MemoryExporter()


class TestExportToJsonFormat:
    """Test: export_json creates valid JSON file."""

    def test_export_to_json_format(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that export_json creates a valid JSON file with all entries."""
        output_path = tmp_path / "export.json"

        # Export to JSON
        exporter.export_json(populated_store, output_path)

        # Verify file exists
        assert output_path.exists(), "Export file should be created"

        # Verify it's valid JSON
        with open(output_path, "r") as f:
            data = json.load(f)

        # Verify entries are present
        assert "entries" in data, "JSON should have 'entries' key"
        assert len(data["entries"]) == 3, "Should export all 3 entries"

        # Verify entry structure
        entry_ids = {e["id"] for e in data["entries"]}
        assert entry_ids == {"entry-1", "entry-2", "entry-3"}

    def test_export_json_preserves_entry_data(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that exported JSON preserves all entry fields."""
        output_path = tmp_path / "export.json"

        exporter.export_json(populated_store, output_path)

        with open(output_path, "r") as f:
            data = json.load(f)

        # Find entry-1 and verify all fields
        entry_1 = next(e for e in data["entries"] if e["id"] == "entry-1")
        assert entry_1["category"] == "schema_drift"
        assert entry_1["feature_id"] == "feature-a"
        assert entry_1["issue_number"] == 1
        assert entry_1["content"]["class_name"] == "UserModel"
        assert entry_1["outcome"] == "detected"
        assert entry_1["created_at"] == "2025-01-01T10:00:00"
        assert entry_1["tags"] == ["model", "user"]
        assert entry_1["hit_count"] == 5


class TestImportFromJsonFormat:
    """Test: import_json loads entries correctly."""

    def test_import_from_json_format(
        self, exporter: MemoryExporter, tmp_path: Path
    ) -> None:
        """Test that import_json loads entries from a JSON file."""
        # Create a JSON file to import
        input_path = tmp_path / "import.json"
        data = {
            "version": "1.0",
            "entries": [
                {
                    "id": "imported-1",
                    "category": "bug_pattern",
                    "feature_id": "feature-x",
                    "issue_number": 10,
                    "content": {"pattern": "null pointer"},
                    "outcome": "identified",
                    "created_at": "2025-01-05T09:00:00",
                    "tags": ["bug"],
                    "hit_count": 0,
                },
                {
                    "id": "imported-2",
                    "category": "recovery_pattern",
                    "feature_id": "feature-y",
                    "issue_number": None,
                    "content": {"action": "retry"},
                    "outcome": "success",
                    "created_at": "2025-01-06T10:00:00",
                    "tags": ["recovery"],
                    "hit_count": 2,
                },
            ],
            "metadata": {
                "version": "1.0",
                "exported_at": "2025-01-06T12:00:00",
            },
        }
        with open(input_path, "w") as f:
            json.dump(data, f)

        # Create an empty store to import into
        store = MemoryStore(store_path=tmp_path / "memories.json")

        # Import from JSON
        count = exporter.import_json(store, input_path)

        # Verify import count
        assert count == 2, "Should import 2 entries"

        # Verify entries are in store
        entry_1 = store.get_entry("imported-1")
        assert entry_1 is not None
        assert entry_1.category == "bug_pattern"
        assert entry_1.content["pattern"] == "null pointer"

        entry_2 = store.get_entry("imported-2")
        assert entry_2 is not None
        assert entry_2.category == "recovery_pattern"


class TestExportFiltersByCategory:
    """Test: export with category filter only exports matching entries."""

    def test_export_filters_by_category(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that categories parameter filters exported entries."""
        output_path = tmp_path / "filtered_export.json"

        # Export only schema_drift entries
        exporter.export_json(
            populated_store, output_path, categories=["schema_drift"]
        )

        with open(output_path, "r") as f:
            data = json.load(f)

        # Should only have 2 entries (entry-1 and entry-3 are schema_drift)
        assert len(data["entries"]) == 2, "Should only export schema_drift entries"

        for entry in data["entries"]:
            assert entry["category"] == "schema_drift"

    def test_export_filters_multiple_categories(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test filtering by multiple categories."""
        output_path = tmp_path / "multi_category_export.json"

        # Export schema_drift and test_failure
        exporter.export_json(
            populated_store, output_path, categories=["schema_drift", "test_failure"]
        )

        with open(output_path, "r") as f:
            data = json.load(f)

        # Should have all 3 entries
        assert len(data["entries"]) == 3

    def test_export_empty_when_no_matching_category(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that export with non-matching category produces empty entries."""
        output_path = tmp_path / "empty_export.json"

        exporter.export_json(
            populated_store, output_path, categories=["nonexistent_category"]
        )

        with open(output_path, "r") as f:
            data = json.load(f)

        assert len(data["entries"]) == 0, "Should export no entries for non-matching category"


class TestExportIncludesMetadata:
    """Test: exported files include metadata."""

    def test_export_includes_metadata(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that export includes version and timestamp metadata."""
        output_path = tmp_path / "export_with_metadata.json"

        exporter.export_json(populated_store, output_path)

        with open(output_path, "r") as f:
            data = json.load(f)

        # Verify metadata section exists
        assert "metadata" in data, "Export should include metadata"
        metadata = data["metadata"]

        # Verify version
        assert "version" in metadata, "Metadata should include version"
        assert metadata["version"] == "1.0", "Version should be 1.0"

        # Verify export timestamp
        assert "exported_at" in metadata, "Metadata should include export timestamp"
        # Should be a valid ISO timestamp
        export_time = datetime.fromisoformat(metadata["exported_at"])
        assert export_time is not None

    def test_metadata_includes_entry_count(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that metadata includes entry count."""
        output_path = tmp_path / "export_with_count.json"

        exporter.export_json(populated_store, output_path)

        with open(output_path, "r") as f:
            data = json.load(f)

        assert "metadata" in data
        assert data["metadata"].get("entry_count") == 3


class TestImportMergesWithExisting:
    """Test: import with merge=True adds to existing entries."""

    def test_import_merges_with_existing(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that merge=True adds entries without overwriting existing."""
        # Create a JSON file with new entries
        input_path = tmp_path / "new_entries.json"
        data = {
            "version": "1.0",
            "entries": [
                {
                    "id": "new-entry-1",
                    "category": "new_category",
                    "feature_id": "feature-new",
                    "issue_number": 99,
                    "content": {"data": "new"},
                    "outcome": "pending",
                    "created_at": "2025-01-10T08:00:00",
                    "tags": ["new"],
                    "hit_count": 0,
                }
            ],
            "metadata": {"version": "1.0"},
        }
        with open(input_path, "w") as f:
            json.dump(data, f)

        # populated_store already has 3 entries
        initial_count = len(populated_store.query(limit=100))
        assert initial_count == 3

        # Import with merge=True (default)
        count = exporter.import_json(populated_store, input_path, merge=True)

        # Verify new entry was added
        assert count == 1

        # Verify store now has 4 entries
        all_entries = populated_store.query(limit=100)
        assert len(all_entries) == 4

        # Verify original entries still exist
        assert populated_store.get_entry("entry-1") is not None
        assert populated_store.get_entry("entry-2") is not None
        assert populated_store.get_entry("entry-3") is not None

        # Verify new entry exists
        new_entry = populated_store.get_entry("new-entry-1")
        assert new_entry is not None
        assert new_entry.category == "new_category"

    def test_import_replace_mode_overwrites(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that merge=False replaces all existing entries."""
        # Create a JSON file with replacement entries
        input_path = tmp_path / "replacement_entries.json"
        data = {
            "version": "1.0",
            "entries": [
                {
                    "id": "replacement-1",
                    "category": "replacement",
                    "feature_id": "feature-replace",
                    "issue_number": 100,
                    "content": {"data": "replaced"},
                    "outcome": "done",
                    "created_at": "2025-01-11T08:00:00",
                    "tags": ["replaced"],
                    "hit_count": 0,
                }
            ],
            "metadata": {"version": "1.0"},
        }
        with open(input_path, "w") as f:
            json.dump(data, f)

        # Import with merge=False (replace mode)
        count = exporter.import_json(populated_store, input_path, merge=False)

        # Verify only new entry exists
        assert count == 1

        # Original entries should be gone
        assert populated_store.get_entry("entry-1") is None
        assert populated_store.get_entry("entry-2") is None
        assert populated_store.get_entry("entry-3") is None

        # Only the replacement entry should exist
        all_entries = populated_store.query(limit=100)
        assert len(all_entries) == 1
        assert all_entries[0].id == "replacement-1"


class TestExportToYamlFormat:
    """Test: export_yaml creates valid YAML file."""

    def test_export_to_yaml_format(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that export_yaml creates a valid YAML file."""
        output_path = tmp_path / "export.yaml"

        # Export to YAML
        exporter.export_yaml(populated_store, output_path)

        # Verify file exists
        assert output_path.exists(), "YAML export file should be created"

        # Verify it's valid YAML
        with open(output_path, "r") as f:
            data = yaml.safe_load(f)

        # Verify entries are present
        assert "entries" in data, "YAML should have 'entries' key"
        assert len(data["entries"]) == 3, "Should export all 3 entries"

    def test_yaml_export_filters_by_category(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that YAML export respects category filter."""
        output_path = tmp_path / "filtered_export.yaml"

        # Export only test_failure entries
        exporter.export_yaml(
            populated_store, output_path, categories=["test_failure"]
        )

        with open(output_path, "r") as f:
            data = yaml.safe_load(f)

        # Should only have 1 entry (entry-2 is test_failure)
        assert len(data["entries"]) == 1
        assert data["entries"][0]["category"] == "test_failure"

    def test_yaml_export_includes_metadata(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that YAML export includes metadata."""
        output_path = tmp_path / "export_with_metadata.yaml"

        exporter.export_yaml(populated_store, output_path)

        with open(output_path, "r") as f:
            data = yaml.safe_load(f)

        assert "metadata" in data
        assert "version" in data["metadata"]
        assert "exported_at" in data["metadata"]

    def test_yaml_preserves_complex_content(
        self, exporter: MemoryExporter, populated_store: MemoryStore, tmp_path: Path
    ) -> None:
        """Test that YAML export preserves nested content structures."""
        output_path = tmp_path / "complex_export.yaml"

        exporter.export_yaml(populated_store, output_path)

        with open(output_path, "r") as f:
            data = yaml.safe_load(f)

        # Find entry-1 and verify content is preserved
        entry_1 = next(e for e in data["entries"] if e["id"] == "entry-1")
        assert entry_1["content"]["class_name"] == "UserModel"
        assert entry_1["content"]["conflict"] == "duplicate field"
