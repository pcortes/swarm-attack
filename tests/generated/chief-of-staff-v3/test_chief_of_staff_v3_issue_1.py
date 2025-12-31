"""Tests for EpisodeStore.find_similar() method.

Tests Jaccard-based keyword similarity matching for episodes.
"""

import pytest
from pathlib import Path
from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore


class TestFindSimilar:
    """Test find_similar() method on EpisodeStore."""

    def test_finds_similar_by_keywords(self, tmp_path: Path) -> None:
        """Test that find_similar finds episodes matching keywords."""
        store = EpisodeStore(tmp_path)
        
        # Save episodes with different keywords
        store.save(Episode(
            episode_id="ep1",
            timestamp="2025-12-18T10:00:00",
            goal_id="implement user auth",
            success=True,
            cost_usd=1.50,
            duration_seconds=120,
        ))
        store.save(Episode(
            episode_id="ep2",
            timestamp="2025-12-18T10:05:00",
            goal_id="implement user login",
            success=True,
            cost_usd=2.00,
            duration_seconds=150,
        ))
        store.save(Episode(
            episode_id="ep3",
            timestamp="2025-12-18T10:10:00",
            goal_id="fix database bug",
            success=False,
            cost_usd=0.75,
            duration_seconds=60,
        ))

        similar = store.find_similar("user authentication", k=2)
        
        assert len(similar) == 2
        # Both "implement user auth" and "implement user login" contain "user"
        assert "user" in similar[0].goal_id

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Test that find_similar returns empty list when no episodes match."""
        store = EpisodeStore(tmp_path)
        
        store.save(Episode(
            episode_id="ep1",
            timestamp="2025-12-18T10:00:00",
            goal_id="database migration",
            success=True,
            cost_usd=1.00,
            duration_seconds=100,
        ))

        similar = store.find_similar("completely unrelated xyz", k=5)
        
        assert similar == []

    def test_respects_k_limit(self, tmp_path: Path) -> None:
        """Test that find_similar respects the k limit parameter."""
        store = EpisodeStore(tmp_path)
        
        # Save 10 episodes with overlapping keywords
        for i in range(10):
            store.save(Episode(
                episode_id=f"ep{i}",
                timestamp=f"2025-12-18T10:{i:02d}:00",
                goal_id=f"feature task {i}",
                success=True,
                cost_usd=1.00,
                duration_seconds=100,
            ))

        similar = store.find_similar("feature", k=3)
        
        assert len(similar) == 3

    def test_returns_sorted_by_relevance(self, tmp_path: Path) -> None:
        """Test that results are sorted by relevance (highest first)."""
        store = EpisodeStore(tmp_path)
        
        # Episode with more matching keywords should rank higher
        store.save(Episode(
            episode_id="ep1",
            timestamp="2025-12-18T10:00:00",
            goal_id="single match",
            success=True,
            cost_usd=1.00,
            duration_seconds=100,
        ))
        store.save(Episode(
            episode_id="ep2",
            timestamp="2025-12-18T10:05:00",
            goal_id="user auth login api",
            success=True,
            cost_usd=1.00,
            duration_seconds=100,
        ))
        store.save(Episode(
            episode_id="ep3",
            timestamp="2025-12-18T10:10:00",
            goal_id="user auth",
            success=True,
            cost_usd=1.00,
            duration_seconds=100,
        ))

        # Search for "user auth" - ep3 should match better than ep2 (Jaccard)
        similar = store.find_similar("user auth", k=5)
        
        # Both ep2 and ep3 should be found
        assert len(similar) >= 2
        # ep3 "user auth" has Jaccard 1.0 with query "user auth"
        # ep2 "user auth login api" has Jaccard 2/6 = 0.33
        assert similar[0].goal_id == "user auth"

    def test_returns_empty_for_empty_store(self, tmp_path: Path) -> None:
        """Test that find_similar returns empty list for empty store."""
        store = EpisodeStore(tmp_path)
        
        similar = store.find_similar("any search term", k=5)
        
        assert similar == []

    def test_default_k_value(self, tmp_path: Path) -> None:
        """Test that default k value is 5."""
        store = EpisodeStore(tmp_path)
        
        # Save 10 matching episodes
        for i in range(10):
            store.save(Episode(
                episode_id=f"ep{i}",
                timestamp=f"2025-12-18T10:{i:02d}:00",
                goal_id=f"test task {i}",
                success=True,
                cost_usd=1.00,
                duration_seconds=100,
            ))

        # Use default k (should be 5)
        similar = store.find_similar("test")
        
        assert len(similar) == 5

    def test_case_insensitive_matching(self, tmp_path: Path) -> None:
        """Test that matching is case-insensitive."""
        store = EpisodeStore(tmp_path)
        
        store.save(Episode(
            episode_id="ep1",
            timestamp="2025-12-18T10:00:00",
            goal_id="USER Authentication",
            success=True,
            cost_usd=1.00,
            duration_seconds=100,
        ))

        similar = store.find_similar("user authentication", k=5)
        
        assert len(similar) == 1
        assert similar[0].goal_id == "USER Authentication"