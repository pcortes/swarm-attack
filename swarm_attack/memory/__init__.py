"""
Persistent Memory Layer for Swarm Attack.

Phase 5 implementation: Pattern detection, recommendations, semantic search, indexing.
"""

from swarm_attack.memory.categories import (
    BUG_PATTERN,
    IMPLEMENTATION_SUCCESS,
    RECOVERY_PATTERN,
    SCHEMA_DRIFT,
    TEST_FAILURE,
)
from swarm_attack.memory.index import MemoryIndex
from swarm_attack.memory.patterns import PatternDetector, VerificationPattern
from swarm_attack.memory.recommendations import Recommendation, RecommendationEngine
from swarm_attack.memory.search import SearchResult, SemanticSearch
from swarm_attack.memory.store import MemoryEntry, MemoryStore

__all__ = [
    # Core storage
    "MemoryEntry",
    "MemoryStore",
    # Pattern detection
    "PatternDetector",
    "VerificationPattern",
    # Recommendations
    "RecommendationEngine",
    "Recommendation",
    # Semantic search
    "SemanticSearch",
    "SearchResult",
    # Indexing
    "MemoryIndex",
    # Category constants
    "SCHEMA_DRIFT",
    "TEST_FAILURE",
    "RECOVERY_PATTERN",
    "IMPLEMENTATION_SUCCESS",
    "BUG_PATTERN",
]
