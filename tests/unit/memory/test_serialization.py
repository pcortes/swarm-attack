"""TDD tests for MemoryEntry serialization.

Tests verify that MemoryEntry.to_dict() and MemoryEntry.from_dict() work correctly
for various edge cases including:
- Basic serialization/deserialization
- Round-trip data preservation
- ISO timestamp handling
- Complex nested metadata
- Optional fields (issue_number, outcome can be None)
- Empty metadata
"""

import pytest
from datetime import datetime, timezone

from swarm_attack.memory.store import MemoryEntry


class TestMemoryEntryToDict:
    """Tests for MemoryEntry.to_dict() method."""

    def test_memory_entry_to_dict_basic(self):
        """Entry serializes to dict with all required fields."""
        entry = MemoryEntry(
            id="test-uuid-123",
            category="checkpoint_decision",
            feature_id="my-feature",
            issue_number=42,
            content={"key": "value"},
            outcome="success",
            created_at="2025-01-06T12:00:00Z",
            tags=["tag1", "tag2"],
            hit_count=5,
        )

        result = entry.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == "test-uuid-123"
        assert result["category"] == "checkpoint_decision"
        assert result["feature_id"] == "my-feature"
        assert result["issue_number"] == 42
        assert result["content"] == {"key": "value"}
        assert result["outcome"] == "success"
        assert result["created_at"] == "2025-01-06T12:00:00Z"
        assert result["tags"] == ["tag1", "tag2"]
        assert result["hit_count"] == 5

    def test_memory_entry_to_dict_with_none_optional_fields(self):
        """Entry serializes correctly when optional fields are None."""
        entry = MemoryEntry(
            id="test-uuid-456",
            category="test_failure",
            feature_id="another-feature",
            issue_number=None,
            content={},
            outcome=None,
            created_at="2025-01-06T13:00:00Z",
        )

        result = entry.to_dict()

        assert result["issue_number"] is None
        assert result["outcome"] is None

    def test_memory_entry_to_dict_with_empty_metadata(self):
        """Entry serializes correctly with empty content dict."""
        entry = MemoryEntry(
            id="empty-content-id",
            category="schema_drift",
            feature_id="feature-x",
            issue_number=1,
            content={},
            outcome="applied",
            created_at="2025-01-06T14:00:00Z",
        )

        result = entry.to_dict()

        assert result["content"] == {}
        assert isinstance(result["content"], dict)

    def test_memory_entry_to_dict_preserves_default_values(self):
        """Entry serializes default values for tags and hit_count."""
        entry = MemoryEntry(
            id="default-values-id",
            category="checkpoint_decision",
            feature_id="feature-y",
            issue_number=None,
            content={"test": True},
            outcome="blocked",
            created_at="2025-01-06T15:00:00Z",
        )

        result = entry.to_dict()

        assert result["tags"] == []
        assert result["hit_count"] == 0


class TestMemoryEntryFromDict:
    """Tests for MemoryEntry.from_dict() method."""

    def test_memory_entry_from_dict_basic(self):
        """Entry deserializes from dict with all fields."""
        data = {
            "id": "from-dict-id",
            "category": "test_failure",
            "feature_id": "feature-z",
            "issue_number": 100,
            "content": {"error": "ImportError"},
            "outcome": "failure",
            "created_at": "2025-01-06T16:00:00Z",
            "tags": ["test", "failure"],
            "hit_count": 10,
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.id == "from-dict-id"
        assert entry.category == "test_failure"
        assert entry.feature_id == "feature-z"
        assert entry.issue_number == 100
        assert entry.content == {"error": "ImportError"}
        assert entry.outcome == "failure"
        assert entry.created_at == "2025-01-06T16:00:00Z"
        assert entry.tags == ["test", "failure"]
        assert entry.hit_count == 10

    def test_memory_entry_from_dict_with_missing_optional_fields(self):
        """Entry deserializes correctly when optional fields are missing."""
        data = {
            "id": "minimal-id",
            "category": "schema_drift",
            "feature_id": "feature-minimal",
            "created_at": "2025-01-06T17:00:00Z",
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.issue_number is None
        assert entry.content == {}
        assert entry.outcome is None
        assert entry.tags == []
        assert entry.hit_count == 0

    def test_memory_entry_from_dict_with_none_values(self):
        """Entry deserializes correctly when optional fields are explicitly None."""
        data = {
            "id": "none-values-id",
            "category": "checkpoint_decision",
            "feature_id": "feature-none",
            "issue_number": None,
            "content": {"data": "present"},
            "outcome": None,
            "created_at": "2025-01-06T18:00:00Z",
            "tags": ["important"],
            "hit_count": 3,
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.issue_number is None
        assert entry.outcome is None

    def test_memory_entry_from_dict_with_empty_content(self):
        """Entry deserializes correctly with empty content dict."""
        data = {
            "id": "empty-content-from-dict",
            "category": "test_failure",
            "feature_id": "feature-empty",
            "issue_number": 5,
            "content": {},
            "outcome": "success",
            "created_at": "2025-01-06T19:00:00Z",
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.content == {}
        assert isinstance(entry.content, dict)


class TestMemoryEntryRoundTrip:
    """Tests for serialize/deserialize round-trip data preservation."""

    def test_memory_entry_round_trip_basic(self):
        """Serialize/deserialize preserves all data."""
        original = MemoryEntry(
            id="round-trip-id",
            category="checkpoint_decision",
            feature_id="round-trip-feature",
            issue_number=42,
            content={"action": "approved", "reason": "tests pass"},
            outcome="success",
            created_at="2025-01-06T20:00:00Z",
            tags=["approved", "checkpoint"],
            hit_count=7,
        )

        serialized = original.to_dict()
        restored = MemoryEntry.from_dict(serialized)

        assert restored.id == original.id
        assert restored.category == original.category
        assert restored.feature_id == original.feature_id
        assert restored.issue_number == original.issue_number
        assert restored.content == original.content
        assert restored.outcome == original.outcome
        assert restored.created_at == original.created_at
        assert restored.tags == original.tags
        assert restored.hit_count == original.hit_count

    def test_memory_entry_round_trip_with_none_values(self):
        """Round-trip preserves None values for optional fields."""
        original = MemoryEntry(
            id="none-round-trip",
            category="schema_drift",
            feature_id="feature-with-none",
            issue_number=None,
            content={"drift": "detected"},
            outcome=None,
            created_at="2025-01-06T21:00:00Z",
        )

        serialized = original.to_dict()
        restored = MemoryEntry.from_dict(serialized)

        assert restored.issue_number is None
        assert restored.outcome is None

    def test_memory_entry_round_trip_with_empty_collections(self):
        """Round-trip preserves empty tags and content."""
        original = MemoryEntry(
            id="empty-collections",
            category="test_failure",
            feature_id="empty-feature",
            issue_number=1,
            content={},
            outcome="failure",
            created_at="2025-01-06T22:00:00Z",
            tags=[],
            hit_count=0,
        )

        serialized = original.to_dict()
        restored = MemoryEntry.from_dict(serialized)

        assert restored.content == {}
        assert restored.tags == []
        assert restored.hit_count == 0

    def test_memory_entry_round_trip_complex_nested_content(self):
        """Round-trip preserves deeply nested content structures."""
        complex_content = {
            "level1": {
                "level2": {
                    "level3": ["a", "b", "c"],
                    "number": 42,
                    "boolean": True,
                    "null_value": None,
                }
            },
            "list_of_dicts": [
                {"name": "item1", "value": 100},
                {"name": "item2", "value": 200},
            ],
            "mixed_list": [1, "two", 3.0, None, {"nested": True}],
        }

        original = MemoryEntry(
            id="complex-content-id",
            category="checkpoint_decision",
            feature_id="complex-feature",
            issue_number=99,
            content=complex_content,
            outcome="success",
            created_at="2025-01-06T23:00:00Z",
            tags=["complex", "nested"],
            hit_count=15,
        )

        serialized = original.to_dict()
        restored = MemoryEntry.from_dict(serialized)

        assert restored.content == complex_content
        assert restored.content["level1"]["level2"]["level3"] == ["a", "b", "c"]
        assert restored.content["list_of_dicts"][0]["name"] == "item1"
        assert restored.content["mixed_list"][4]["nested"] is True


class TestMemoryEntryHandlesDatetime:
    """Tests for ISO timestamp handling."""

    def test_memory_entry_handles_datetime_utc_format(self):
        """Timestamps in UTC ISO format serialize correctly."""
        entry = MemoryEntry(
            id="utc-timestamp",
            category="checkpoint_decision",
            feature_id="utc-feature",
            issue_number=1,
            content={},
            outcome="success",
            created_at="2025-01-06T12:30:45Z",
        )

        result = entry.to_dict()

        assert result["created_at"] == "2025-01-06T12:30:45Z"

    def test_memory_entry_handles_datetime_with_offset(self):
        """Timestamps with timezone offset serialize correctly."""
        entry = MemoryEntry(
            id="offset-timestamp",
            category="test_failure",
            feature_id="offset-feature",
            issue_number=2,
            content={},
            outcome="failure",
            created_at="2025-01-06T12:30:45+05:00",
        )

        result = entry.to_dict()

        assert result["created_at"] == "2025-01-06T12:30:45+05:00"

    def test_memory_entry_handles_datetime_with_microseconds(self):
        """Timestamps with microseconds serialize correctly."""
        timestamp = "2025-01-06T12:30:45.123456Z"
        entry = MemoryEntry(
            id="micro-timestamp",
            category="schema_drift",
            feature_id="micro-feature",
            issue_number=3,
            content={},
            outcome="applied",
            created_at=timestamp,
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert result["created_at"] == timestamp
        assert restored.created_at == timestamp

    def test_memory_entry_handles_datetime_round_trip(self):
        """Timestamp survives round-trip serialization."""
        now = datetime.now(timezone.utc)
        iso_timestamp = now.isoformat()

        original = MemoryEntry(
            id="datetime-round-trip",
            category="checkpoint_decision",
            feature_id="datetime-feature",
            issue_number=None,
            content={"timestamp_test": True},
            outcome="success",
            created_at=iso_timestamp,
        )

        serialized = original.to_dict()
        restored = MemoryEntry.from_dict(serialized)

        assert restored.created_at == iso_timestamp

    def test_memory_entry_handles_datetime_negative_offset(self):
        """Timestamps with negative timezone offset serialize correctly."""
        entry = MemoryEntry(
            id="negative-offset",
            category="test_failure",
            feature_id="negative-offset-feature",
            issue_number=4,
            content={},
            outcome="failure",
            created_at="2025-01-06T12:30:45-08:00",
        )

        result = entry.to_dict()

        assert result["created_at"] == "2025-01-06T12:30:45-08:00"


class TestMemoryEntryHandlesMetadata:
    """Tests for complex metadata serialization."""

    def test_memory_entry_handles_metadata_nested_dicts(self):
        """Complex nested dictionaries in content serialize correctly."""
        content = {
            "schema_info": {
                "class_name": "MyClass",
                "methods": {
                    "method1": {"args": ["a", "b"], "return_type": "str"},
                    "method2": {"args": [], "return_type": "int"},
                },
            }
        }

        entry = MemoryEntry(
            id="nested-dict-id",
            category="schema_drift",
            feature_id="nested-feature",
            issue_number=10,
            content=content,
            outcome="applied",
            created_at="2025-01-06T10:00:00Z",
        )

        result = entry.to_dict()

        assert result["content"] == content
        assert result["content"]["schema_info"]["methods"]["method1"]["args"] == ["a", "b"]

    def test_memory_entry_handles_metadata_lists_in_content(self):
        """Lists containing mixed types in content serialize correctly."""
        content = {
            "errors": [
                {"type": "ImportError", "line": 10},
                {"type": "SyntaxError", "line": 25},
            ],
            "affected_files": ["file1.py", "file2.py", "file3.py"],
            "counts": [1, 2, 3, 4, 5],
        }

        entry = MemoryEntry(
            id="lists-content-id",
            category="test_failure",
            feature_id="lists-feature",
            issue_number=11,
            content=content,
            outcome="failure",
            created_at="2025-01-06T11:00:00Z",
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert restored.content["errors"][0]["type"] == "ImportError"
        assert restored.content["affected_files"] == ["file1.py", "file2.py", "file3.py"]

    def test_memory_entry_handles_metadata_special_values(self):
        """Content with special values (None, booleans, numbers) serializes correctly."""
        content = {
            "null_field": None,
            "true_field": True,
            "false_field": False,
            "int_field": 42,
            "float_field": 3.14159,
            "negative_int": -100,
            "zero": 0,
            "empty_string": "",
        }

        entry = MemoryEntry(
            id="special-values-id",
            category="checkpoint_decision",
            feature_id="special-feature",
            issue_number=12,
            content=content,
            outcome="success",
            created_at="2025-01-06T12:00:00Z",
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert restored.content["null_field"] is None
        assert restored.content["true_field"] is True
        assert restored.content["false_field"] is False
        assert restored.content["int_field"] == 42
        assert restored.content["float_field"] == 3.14159
        assert restored.content["negative_int"] == -100
        assert restored.content["zero"] == 0
        assert restored.content["empty_string"] == ""

    def test_memory_entry_handles_metadata_unicode_content(self):
        """Content with unicode characters serializes correctly."""
        content = {
            "message": "Hello, World!",
            "unicode_text": "Cafe avec creme",
            "emoji_support": "Status: pending",
            "cjk_characters": "Chinese text",
            "arabic_text": "Some text",
        }

        entry = MemoryEntry(
            id="unicode-content-id",
            category="checkpoint_decision",
            feature_id="unicode-feature",
            issue_number=13,
            content=content,
            outcome="success",
            created_at="2025-01-06T13:00:00Z",
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert restored.content["message"] == "Hello, World!"
        assert restored.content["unicode_text"] == "Cafe avec creme"

    def test_memory_entry_handles_metadata_large_content(self):
        """Large content dictionaries serialize correctly."""
        # Create content with many keys
        content = {f"key_{i}": f"value_{i}" for i in range(100)}
        content["nested"] = {f"nested_key_{i}": i * 2 for i in range(50)}

        entry = MemoryEntry(
            id="large-content-id",
            category="schema_drift",
            feature_id="large-feature",
            issue_number=14,
            content=content,
            outcome="applied",
            created_at="2025-01-06T14:00:00Z",
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert len(restored.content) == 101  # 100 keys + nested
        assert restored.content["key_50"] == "value_50"
        assert restored.content["nested"]["nested_key_25"] == 50

    def test_memory_entry_handles_metadata_tags_with_special_chars(self):
        """Tags with various characters serialize correctly."""
        entry = MemoryEntry(
            id="special-tags-id",
            category="test_failure",
            feature_id="tags-feature",
            issue_number=15,
            content={},
            outcome="failure",
            created_at="2025-01-06T15:00:00Z",
            tags=["tag-with-dash", "tag_with_underscore", "tag.with.dots", "CamelCaseTag"],
        )

        result = entry.to_dict()
        restored = MemoryEntry.from_dict(result)

        assert "tag-with-dash" in restored.tags
        assert "tag_with_underscore" in restored.tags
        assert "tag.with.dots" in restored.tags
        assert "CamelCaseTag" in restored.tags
