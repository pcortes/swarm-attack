"""Semantic search with weighted keyword matching for memory entries.

Provides advanced search capabilities over MemoryStore entries with:
- Keyword weighting (error/fail/exception get higher weights)
- Category boost (same category entries score higher)
- Recency factor (recent entries preferred)
- Exact match boost (exact phrase matches score highest)
- Partial match scoring (partial matches included)
- Category filtering support
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryEntry, MemoryStore


@dataclass
class SearchResult:
    """Result from a semantic search query.

    Attributes:
        entry: The matched MemoryEntry.
        score: Relevance score (higher = more relevant).
        matched_keywords: List of keywords that matched.
    """

    entry: Any  # MemoryEntry
    score: float
    matched_keywords: List[str]


class SemanticSearch:
    """Advanced search over memory entries with weighted keyword matching.

    Features:
    - Weighted keywords: error/fail/exception score 2x, class/method/import score 1.5x
    - Category boosting: Same category entries get 1.5x boost
    - Recency factor: Recent entries score higher (exponential decay)
    - Exact match boost: Exact phrase matches get 2x boost
    - Partial matching: Returns entries with any keyword overlap
    """

    KEYWORD_WEIGHTS = {
        "error": 2.0,
        "fail": 2.0,
        "exception": 2.0,
        "class": 1.5,
        "method": 1.5,
        "import": 1.5,
    }

    # Category boost multiplier when query category matches entry category
    CATEGORY_BOOST = 1.5

    # Exact match boost multiplier
    EXACT_MATCH_BOOST = 2.0

    # Recency decay rate (per 24 hours)
    RECENCY_DECAY_RATE = 0.95

    def __init__(self, store: "MemoryStore"):
        """Initialize SemanticSearch with a memory store.

        Args:
            store: The MemoryStore to search over.
        """
        self.store = store

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search entries with weighted keyword matching.

        Args:
            query: Search query string.
            category: Optional category to filter/boost results.
            limit: Maximum number of results to return (default 10).

        Returns:
            List of SearchResult objects sorted by score (highest first).
        """
        # Extract keywords from query
        query_keywords = self._extract_keywords_from_text(query)

        if not query_keywords:
            return []

        # Get all entries from store
        entries = list(self.store._entries.values())

        if not entries:
            return []

        # Score each entry
        scored_results: List[SearchResult] = []

        for entry in entries:
            # Extract keywords from entry content
            entry_keywords = self._extract_keywords_from_content(entry.content)

            # Find matching keywords
            matched = query_keywords & entry_keywords

            if not matched:
                continue

            # Calculate score
            score = self.calculate_score(
                query_keywords, entry, query_category=category
            )

            # Check for exact match boost
            if self._is_exact_match(query, entry.content):
                score *= self.EXACT_MATCH_BOOST

            scored_results.append(
                SearchResult(
                    entry=entry,
                    score=score,
                    matched_keywords=list(matched),
                )
            )

        # Sort by score descending
        scored_results.sort(key=lambda r: r.score, reverse=True)

        # Apply limit
        return scored_results[:limit]

    def calculate_score(
        self,
        query_keywords: Set[str],
        entry: "MemoryEntry",
        query_category: Optional[str] = None,
    ) -> float:
        """Calculate relevance score for entry.

        Score formula combines:
        - Keyword match score (weighted by KEYWORD_WEIGHTS)
        - Category boost (if query category matches entry category)
        - Recency factor (exponential decay based on age)

        Args:
            query_keywords: Set of keywords from the query.
            entry: The memory entry to score.
            query_category: Optional category to boost matching entries.

        Returns:
            Relevance score (higher is more relevant).
        """
        # Extract entry keywords
        entry_keywords = self._extract_keywords_from_content(entry.content)

        # Find matching keywords
        matched = query_keywords & entry_keywords

        if not matched:
            return 0.0

        # Calculate keyword score with weights
        keyword_score = 0.0
        for keyword in matched:
            weight = self.KEYWORD_WEIGHTS.get(keyword, 1.0)
            keyword_score += weight

        # Apply category boost
        category_multiplier = 1.0
        if query_category is not None:
            if entry.category == query_category:
                category_multiplier = self.CATEGORY_BOOST
            else:
                # Slight penalty for different category
                category_multiplier = 0.8

        # Calculate recency factor
        recency_factor = self._calculate_recency_factor(entry.created_at)

        # Combined score
        return keyword_score * category_multiplier * recency_factor

    def _extract_keywords_from_text(self, text: str) -> Set[str]:
        """Extract keywords from text string.

        Splits on whitespace and normalizes to lowercase.

        Args:
            text: Text to extract keywords from.

        Returns:
            Set of lowercase keyword strings.
        """
        if not text:
            return set()

        # Split on whitespace and convert to lowercase
        words = text.lower().split()

        # Filter out very short words
        return {w for w in words if len(w) >= 2}

    def _extract_keywords_from_content(self, content: dict) -> Set[str]:
        """Extract keywords from content dictionary.

        Recursively extracts string values and keys.

        Args:
            content: Dictionary to extract keywords from.

        Returns:
            Set of lowercase keyword strings.
        """
        keywords: Set[str] = set()

        def extract(obj: Any) -> None:
            if isinstance(obj, str):
                # Split string into words and add each
                words = obj.lower().split()
                keywords.update(w for w in words if len(w) >= 2)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    # Add key as keyword
                    keywords.add(str(key).lower())
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(content)
        return keywords

    def _calculate_recency_factor(self, created_at_str: str) -> float:
        """Calculate recency factor based on entry age.

        Uses exponential decay: 0.95 ^ (age_hours / 24)

        Args:
            created_at_str: ISO timestamp string.

        Returns:
            Recency factor between 0 and 1.
        """
        try:
            created_at = datetime.fromisoformat(created_at_str)
            now = datetime.now()
            age_delta = now - created_at
            age_hours = age_delta.total_seconds() / 3600.0

            # Exponential decay
            return self.RECENCY_DECAY_RATE ** (age_hours / 24.0)
        except (ValueError, TypeError):
            # If parsing fails, return neutral factor
            return 1.0

    def _is_exact_match(self, query: str, content: dict) -> bool:
        """Check if query phrase appears exactly in content.

        Args:
            query: Search query string.
            content: Entry content dictionary.

        Returns:
            True if exact phrase match found, False otherwise.
        """
        query_lower = query.lower()

        def check_content(obj: Any) -> bool:
            if isinstance(obj, str):
                return query_lower in obj.lower()
            elif isinstance(obj, dict):
                return any(check_content(v) for v in obj.values())
            elif isinstance(obj, list):
                return any(check_content(item) for item in obj)
            return False

        return check_content(content)
