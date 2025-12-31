"""Tests for state lifecycle management."""
import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from swarm_attack.state.lifecycle import (
    LifecycleMetadata,
    StateCleanupJob,
    get_staleness_indicator,
)


class TestLifecycleMetadata:
    """Tests for LifecycleMetadata."""

    def test_now_creates_current_timestamp(self):
        """now() creates metadata with current time."""
        meta = LifecycleMetadata.now()
        created = datetime.fromisoformat(meta.created_at)
        assert (datetime.now() - created).total_seconds() < 1

    def test_now_sets_same_created_and_updated(self):
        """now() sets created_at and updated_at to same value."""
        meta = LifecycleMetadata.now()
        assert meta.created_at == meta.updated_at

    def test_now_with_ttl_sets_expiration(self):
        """now() with TTL sets expires_at."""
        meta = LifecycleMetadata.now(ttl_seconds=3600)
        assert meta.expires_at is not None
        expires = datetime.fromisoformat(meta.expires_at)
        assert expires > datetime.now()

    def test_now_without_ttl_no_expiration(self):
        """now() without TTL has no expires_at."""
        meta = LifecycleMetadata.now()
        assert meta.expires_at is None

    def test_touch_updates_timestamp(self):
        """touch() updates updated_at."""
        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        meta = LifecycleMetadata(created_at=old_time, updated_at=old_time)
        meta.touch()
        updated = datetime.fromisoformat(meta.updated_at)
        assert (datetime.now() - updated).total_seconds() < 1
        # created_at should not change
        assert meta.created_at == old_time

    def test_is_stale_returns_true_for_old_state(self):
        """is_stale returns True for state older than max_age."""
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        meta = LifecycleMetadata(created_at=old_time, updated_at=old_time)
        assert meta.is_stale(timedelta(hours=1)) is True

    def test_is_stale_returns_false_for_fresh_state(self):
        """is_stale returns False for recently updated state."""
        meta = LifecycleMetadata.now()
        assert meta.is_stale(timedelta(hours=1)) is False

    def test_is_expired_returns_true_after_expiration(self):
        """is_expired returns True after expires_at passes."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        meta = LifecycleMetadata(
            created_at=past,
            updated_at=past,
            expires_at=past,
        )
        assert meta.is_expired() is True

    def test_is_expired_returns_false_before_expiration(self):
        """is_expired returns False before expires_at."""
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        now = datetime.now().isoformat()
        meta = LifecycleMetadata(
            created_at=now,
            updated_at=now,
            expires_at=future,
        )
        assert meta.is_expired() is False

    def test_is_expired_returns_false_when_no_expiration(self):
        """is_expired returns False when expires_at is None."""
        meta = LifecycleMetadata.now()
        assert meta.is_expired() is False

    def test_age_seconds(self):
        """age_seconds returns correct value."""
        old_time = (datetime.now() - timedelta(seconds=60)).isoformat()
        meta = LifecycleMetadata(created_at=old_time, updated_at=old_time)
        age = meta.age_seconds()
        assert 58 <= age <= 62  # Allow some tolerance

    def test_to_dict_and_from_dict(self):
        """Round-trip serialization works."""
        meta = LifecycleMetadata.now(ttl_seconds=3600)
        d = meta.to_dict()
        restored = LifecycleMetadata.from_dict(d)
        assert restored.created_at == meta.created_at
        assert restored.updated_at == meta.updated_at
        assert restored.expires_at == meta.expires_at


class TestStateCleanupJob:
    """Tests for StateCleanupJob."""

    def test_removes_expired_files(self, tmp_path: Path):
        """Cleanup removes files past expiration."""
        state_file = tmp_path / "test.json"
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        state_file.write_text(json.dumps({
            "data": "test",
            "lifecycle": {
                "created_at": past,
                "updated_at": past,
                "expires_at": past,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 1
        assert not state_file.exists()

    def test_removes_stale_files(self, tmp_path: Path):
        """Cleanup removes files older than max_age."""
        state_file = tmp_path / "stale.json"
        old = (datetime.now() - timedelta(days=60)).isoformat()
        state_file.write_text(json.dumps({
            "data": "test",
            "lifecycle": {
                "created_at": old,
                "updated_at": old,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 1
        assert not state_file.exists()

    def test_keeps_fresh_files(self, tmp_path: Path):
        """Cleanup keeps files that are not expired or stale."""
        state_file = tmp_path / "fresh.json"
        now = datetime.now().isoformat()
        state_file.write_text(json.dumps({
            "data": "test",
            "lifecycle": {
                "created_at": now,
                "updated_at": now,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 0
        assert state_file.exists()

    def test_ignores_files_without_lifecycle(self, tmp_path: Path):
        """Cleanup ignores files without lifecycle metadata."""
        state_file = tmp_path / "no_lifecycle.json"
        state_file.write_text(json.dumps({
            "data": "test",
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 0
        assert state_file.exists()

    def test_dry_run_does_not_delete(self, tmp_path: Path):
        """Dry run reports but doesn't delete."""
        state_file = tmp_path / "expired.json"
        past = (datetime.now() - timedelta(days=60)).isoformat()
        state_file.write_text(json.dumps({
            "lifecycle": {
                "created_at": past,
                "updated_at": past,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30, dry_run=True)
        removed = job.run()

        assert len(removed) == 1
        assert state_file.exists()  # Still exists because dry_run

    def test_handles_malformed_json(self, tmp_path: Path):
        """Cleanup gracefully handles malformed JSON."""
        state_file = tmp_path / "bad.json"
        state_file.write_text("not valid json")

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 0
        assert state_file.exists()

    def test_handles_nonexistent_directory(self, tmp_path: Path):
        """Cleanup handles non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        job = StateCleanupJob(nonexistent, max_age_days=30)
        removed = job.run()
        assert len(removed) == 0

    def test_processes_nested_directories(self, tmp_path: Path):
        """Cleanup processes nested directories."""
        subdir = tmp_path / "nested" / "deep"
        subdir.mkdir(parents=True)
        state_file = subdir / "nested.json"
        past = (datetime.now() - timedelta(days=60)).isoformat()
        state_file.write_text(json.dumps({
            "lifecycle": {
                "created_at": past,
                "updated_at": past,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 1
        assert not state_file.exists()


class TestGetStalenessIndicator:
    """Tests for staleness indicator."""

    def test_returns_none_for_fresh(self):
        """Fresh state returns None."""
        now = datetime.now().isoformat()
        assert get_staleness_indicator(now) is None

    def test_returns_stale_after_5_minutes(self):
        """State over 5 minutes old is stale."""
        old = (datetime.now() - timedelta(minutes=10)).isoformat()
        result = get_staleness_indicator(old)
        assert "stale" in result
        assert "10m ago" in result

    def test_returns_very_stale_after_1_hour(self):
        """State over 1 hour old is very stale."""
        old = (datetime.now() - timedelta(hours=2)).isoformat()
        result = get_staleness_indicator(old)
        assert "very stale" in result
        assert "2h ago" in result

    def test_returns_outdated_after_1_day(self):
        """State over 1 day old is outdated."""
        old = (datetime.now() - timedelta(days=3)).isoformat()
        result = get_staleness_indicator(old)
        assert "outdated" in result
        assert "3d ago" in result

    def test_custom_thresholds(self):
        """Custom thresholds work."""
        old = (datetime.now() - timedelta(seconds=120)).isoformat()
        result = get_staleness_indicator(old, thresholds={60: "custom"})
        assert "custom" in result

    def test_returns_unknown_for_invalid_timestamp(self):
        """Invalid timestamp returns 'unknown'."""
        result = get_staleness_indicator("not a timestamp")
        assert result == "unknown"
