"""Recommendation Engine for Memory-based Suggestions.

Provides recommendations based on historical patterns in the memory store.
Works with MemoryStore and optionally PatternDetector to suggest actions
for schema drift issues, test failures, and other scenarios.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from swarm_attack.memory.patterns import PatternDetector
    from swarm_attack.memory.store import MemoryStore


@dataclass
class Recommendation:
    """A recommendation based on historical patterns.

    Attributes:
        suggestion: The recommended action/fix to apply.
        confidence: Confidence score (0.0-1.0) for this recommendation.
        context: Additional context about the recommendation.
        source_entries: List of entry IDs that informed this recommendation.
        action: Alias for suggestion (for backward compatibility).
    """

    suggestion: str
    confidence: float
    context: Dict = field(default_factory=dict)
    source_entries: List[str] = field(default_factory=list)

    @property
    def action(self) -> str:
        """Alias for suggestion (backward compatibility)."""
        return self.suggestion


class RecommendationEngine:
    """Engine for generating recommendations based on memory patterns.

    Uses MemoryStore to analyze historical entries and provide
    actionable recommendations for current issues.

    Attributes:
        store: The MemoryStore containing historical entries.
        pattern_detector: Optional PatternDetector for pattern-based recommendations.
    """

    def __init__(
        self,
        store: "MemoryStore",
        pattern_detector: Optional["PatternDetector"] = None,
    ) -> None:
        """Initialize the RecommendationEngine.

        Args:
            store: The MemoryStore to query for historical data.
            pattern_detector: Optional PatternDetector for pattern analysis.
        """
        self.store = store
        self.pattern_detector = pattern_detector

    def get_recommendations(
        self,
        current_issue: dict,
        limit: int = 3,
    ) -> List[Recommendation]:
        """Get recommendations based on similar past issues.

        This method searches for similar past issues that were successfully
        resolved and returns recommendations based on those solutions.
        Aggregates entries by solution to calculate combined success rates.

        Args:
            current_issue: Dictionary describing the current issue with
                          keys like "error_type", "context", "tags".
            limit: Maximum number of recommendations to return.

        Returns:
            List of Recommendation objects sorted by confidence (highest first).
        """
        # Extract keywords and tags from current issue
        issue_keywords = self._extract_keywords(current_issue)
        issue_tags = set(current_issue.get("tags", []))

        # Search in success categories
        success_categories = ["implementation_success", "recovery_pattern"]

        # Group entries by solution text to aggregate success rates
        solution_groups: Dict[str, list] = defaultdict(list)

        for category in success_categories:
            entries = self.store.query(category=category, limit=100)

            for entry in entries:
                # Calculate similarity
                similarity = self._calculate_similarity(
                    entry, issue_keywords, issue_tags
                )

                if similarity > 0:
                    # Extract solution from entry
                    suggestion = self._extract_suggestion(entry)
                    if not suggestion:
                        continue

                    solution_groups[suggestion].append({
                        "entry": entry,
                        "similarity": similarity,
                        "category": category,
                    })

        # Create recommendations from aggregated groups
        recommendations: List[Recommendation] = []

        for suggestion, group_data in solution_groups.items():
            if not group_data:
                continue

            # Count successes and failures
            success_count = 0
            failure_count = 0
            total_similarity = 0.0
            entry_ids = []
            most_recent_date = None

            for data in group_data:
                entry = data["entry"]
                total_similarity += data["similarity"]
                entry_ids.append(entry.id)

                if entry.outcome == "success":
                    success_count += 1
                elif entry.outcome == "failure":
                    failure_count += 1

                # Track most recent
                entry_date = datetime.fromisoformat(entry.created_at)
                if most_recent_date is None or entry_date > most_recent_date:
                    most_recent_date = entry_date

            # Calculate aggregated confidence
            avg_similarity = total_similarity / len(group_data)
            confidence = self._calculate_aggregated_confidence(
                avg_similarity,
                success_count,
                failure_count,
                most_recent_date,
            )

            rec = Recommendation(
                suggestion=suggestion,
                confidence=confidence,
                context={
                    "category": group_data[0]["category"],
                    "source_entry_id": entry_ids[0],
                    "success_count": success_count,
                    "failure_count": failure_count,
                },
                source_entries=entry_ids,
            )
            recommendations.append(rec)

        # Sort by confidence descending
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations[:limit]

    def get_recommendations_by_category(
        self,
        category: str,
        context: dict,
        limit: int = 3,
    ) -> List[Recommendation]:
        """Get recommendations for a specific category.

        Args:
            category: The category to search (e.g., "schema_drift", "test_failure").
            context: Context dict with query parameters (e.g., class_name, test_path).
            limit: Maximum number of recommendations to return.

        Returns:
            List of Recommendation objects sorted by confidence (highest first).
        """
        recommendations: List[Recommendation] = []

        if category == "schema_drift":
            class_name = context.get("class_name")
            if class_name:
                recommendations = self._get_schema_drift_recommendations(
                    class_name, limit
                )
        elif category == "test_failure":
            test_path = context.get("test_path")
            if test_path:
                recommendations = self._get_test_failure_recommendations(
                    test_path, limit
                )
        else:
            # Generic category handling
            recommendations = self._get_generic_recommendations(
                category, context, limit
            )

        # Sort by confidence descending
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations[:limit]

    def recommend_for_schema_drift(self, class_name: str) -> List[Recommendation]:
        """Get recommendations for schema drift issues.

        Args:
            class_name: The class experiencing schema drift.

        Returns:
            List of Recommendation objects for addressing the drift.
        """
        return self._get_schema_drift_recommendations(class_name, limit=5)

    def recommend_for_test_failure(self, test_path: str) -> List[Recommendation]:
        """Get recommendations for test failures.

        Args:
            test_path: The path to the failing test file.

        Returns:
            List of Recommendation objects based on past similar failures.
        """
        return self._get_test_failure_recommendations(test_path, limit=5)

    def _get_schema_drift_recommendations(
        self,
        class_name: str,
        limit: int = 5,
    ) -> List[Recommendation]:
        """Get recommendations for a specific class's schema drift.

        Looks for historical schema_drift entries for the same class
        that have successful resolutions.

        Args:
            class_name: The class name to find recommendations for.
            limit: Maximum recommendations to return.

        Returns:
            List of Recommendation objects.
        """
        # Query schema_drift entries for this class
        entries = self.store.get_schema_drift_warnings([class_name])

        # Filter to entries with resolutions (successful outcomes)
        resolved_entries = [
            e for e in entries
            if e.outcome in ("resolved", "success", "applied")
            and e.content.get("resolution")
        ]

        if not resolved_entries:
            return []

        # Group by resolution to find common fixes
        resolution_groups: Dict[str, list] = defaultdict(list)
        for entry in resolved_entries:
            resolution = entry.content.get("resolution", "")
            if resolution:
                resolution_groups[resolution].append(entry)

        # Create recommendations from most common resolutions
        recommendations: List[Recommendation] = []
        sorted_resolutions = sorted(
            resolution_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for resolution, group_entries in sorted_resolutions[:limit]:
            confidence = self._calculate_confidence(group_entries, len(resolved_entries))
            rec = Recommendation(
                suggestion=resolution,
                confidence=confidence,
                context={
                    "category": "schema_drift",
                    "class_name": class_name,
                    "occurrence_count": len(group_entries),
                },
                source_entries=[e.id for e in group_entries],
            )
            recommendations.append(rec)

        return recommendations

    def _get_test_failure_recommendations(
        self,
        test_path: str,
        limit: int = 5,
    ) -> List[Recommendation]:
        """Get recommendations for a specific test file's failures.

        Looks for historical test_failure entries for the same test path
        that have successful resolutions.

        Args:
            test_path: The test file path to find recommendations for.
            limit: Maximum recommendations to return.

        Returns:
            List of Recommendation objects.
        """
        # Query test_failure entries for this test path
        entries = self.store.get_test_failure_patterns(test_path)

        # Filter to entries with resolutions (successful outcomes)
        resolved_entries = [
            e for e in entries
            if e.outcome in ("resolved", "success", "fixed")
            and e.content.get("resolution")
        ]

        if not resolved_entries:
            return []

        # Group by resolution to find common fixes
        resolution_groups: Dict[str, list] = defaultdict(list)
        for entry in resolved_entries:
            resolution = entry.content.get("resolution", "")
            if resolution:
                resolution_groups[resolution].append(entry)

        # Create recommendations from most common resolutions
        recommendations: List[Recommendation] = []
        sorted_resolutions = sorted(
            resolution_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for resolution, group_entries in sorted_resolutions[:limit]:
            confidence = self._calculate_confidence(group_entries, len(resolved_entries))
            rec = Recommendation(
                suggestion=resolution,
                confidence=confidence,
                context={
                    "category": "test_failure",
                    "test_path": test_path,
                    "occurrence_count": len(group_entries),
                },
                source_entries=[e.id for e in group_entries],
            )
            recommendations.append(rec)

        return recommendations

    def _get_generic_recommendations(
        self,
        category: str,
        context: dict,
        limit: int = 5,
    ) -> List[Recommendation]:
        """Get recommendations for a generic category.

        Falls back to keyword-based similarity search.

        Args:
            category: The category to search.
            context: Context dict for similarity matching.
            limit: Maximum recommendations to return.

        Returns:
            List of Recommendation objects.
        """
        # Use find_similar to get related entries
        similar_entries = self.store.find_similar(
            content=context,
            category=category,
            limit=50,
        )

        # Filter to resolved entries
        resolved_entries = [
            e for e in similar_entries
            if e.outcome in ("resolved", "success", "applied", "fixed")
            and e.content.get("resolution")
        ]

        if not resolved_entries:
            return []

        # Group by resolution
        resolution_groups: Dict[str, list] = defaultdict(list)
        for entry in resolved_entries:
            resolution = entry.content.get("resolution", "")
            if resolution:
                resolution_groups[resolution].append(entry)

        # Create recommendations
        recommendations: List[Recommendation] = []
        sorted_resolutions = sorted(
            resolution_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for resolution, group_entries in sorted_resolutions[:limit]:
            confidence = self._calculate_confidence(group_entries, len(resolved_entries))
            rec = Recommendation(
                suggestion=resolution,
                confidence=confidence,
                context={
                    "category": category,
                    "occurrence_count": len(group_entries),
                },
                source_entries=[e.id for e in group_entries],
            )
            recommendations.append(rec)

        return recommendations

    def _calculate_confidence(
        self,
        entries: list,
        total_resolved: int,
    ) -> float:
        """Calculate confidence score for a recommendation.

        Confidence is based on:
        - Proportion of resolved entries using this fix
        - Recency of the entries
        - Number of occurrences

        Args:
            entries: List of MemoryEntry objects for this recommendation.
            total_resolved: Total number of resolved entries considered.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not entries or total_resolved == 0:
            return 0.0

        # Proportion score (how common is this fix?)
        proportion = len(entries) / total_resolved
        proportion_score = min(1.0, proportion * 2)  # Scale up, cap at 1.0

        # Occurrence score (more occurrences = higher confidence)
        # 1 occurrence = 0.2, 5 occurrences = 0.6, 10+ = 1.0
        import math
        occurrence_score = min(1.0, math.log10(len(entries) + 1) / math.log10(11))

        # Recency score (more recent = higher confidence)
        now = datetime.now()
        recency_scores = []
        for entry in entries:
            created = datetime.fromisoformat(entry.created_at)
            age_days = (now - created).days
            # Decay: 0 days = 1.0, 30 days = 0.5, 60 days = 0.25
            recency = 0.5 ** (age_days / 30) if age_days >= 0 else 1.0
            recency_scores.append(recency)

        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5

        # Combined score: 40% proportion, 30% occurrence, 30% recency
        confidence = 0.4 * proportion_score + 0.3 * occurrence_score + 0.3 * avg_recency

        return min(1.0, max(0.0, confidence))

    # =========================================================================
    # Helper methods for get_recommendations (issue-based API)
    # =========================================================================

    def _calculate_aggregated_confidence(
        self,
        avg_similarity: float,
        success_count: int,
        failure_count: int,
        most_recent_date: Optional[datetime],
    ) -> float:
        """Calculate confidence based on aggregated success/failure rates.

        Args:
            avg_similarity: Average similarity score across entries.
            success_count: Number of successful outcomes.
            failure_count: Number of failed outcomes.
            most_recent_date: Most recent entry date.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Base confidence from similarity (30%)
        base_confidence = avg_similarity * 0.3

        # Success rate factor (50% weight) - most important
        total = success_count + failure_count
        if total > 0:
            success_rate = success_count / total
            success_factor = success_rate * 0.5
        else:
            # No outcome data - neutral
            success_factor = 0.25

        # Recency factor (20% weight)
        if most_recent_date:
            age_days = (datetime.now() - most_recent_date).days
            # Recent entries (< 7 days) get full bonus
            recency_factor = max(0.0, 0.2 * (1 - age_days / 30))
        else:
            recency_factor = 0.1

        confidence = base_confidence + success_factor + recency_factor

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))

    def _extract_keywords(self, data: dict) -> set:
        """Extract searchable keywords from a dictionary.

        Args:
            data: Dictionary to extract keywords from.

        Returns:
            Set of lowercase keywords.
        """
        keywords = set()

        def extract(obj):
            if isinstance(obj, str):
                # Add words from string
                for word in obj.lower().split():
                    if len(word) > 2:  # Skip very short words
                        keywords.add(word)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)

        extract(data)
        return keywords

    def _calculate_similarity(
        self,
        entry,  # MemoryEntry
        issue_keywords: set,
        issue_tags: set,
    ) -> float:
        """Calculate similarity between entry and current issue.

        Args:
            entry: Memory entry to compare.
            issue_keywords: Keywords from current issue.
            issue_tags: Tags from current issue.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not issue_keywords and not issue_tags:
            return 0.0

        # Extract keywords from entry content
        entry_keywords = self._extract_keywords(entry.content)
        entry_tags = set(entry.tags)

        # Keyword overlap score
        if issue_keywords and entry_keywords:
            keyword_overlap = len(issue_keywords & entry_keywords)
            keyword_score = keyword_overlap / len(issue_keywords)
        else:
            keyword_score = 0.0

        # Tag overlap score
        if issue_tags and entry_tags:
            tag_overlap = len(issue_tags & entry_tags)
            tag_score = tag_overlap / len(issue_tags)
        else:
            tag_score = 0.0

        # Combine scores (60% keywords, 40% tags)
        return 0.6 * keyword_score + 0.4 * tag_score

    def _extract_suggestion(self, entry) -> Optional[str]:
        """Extract the solution/fix suggestion from entry content.

        Args:
            entry: Memory entry to extract suggestion from.

        Returns:
            Suggestion string or None if not found.
        """
        content = entry.content

        # Try various keys that might contain the solution
        for key in ["solution", "fix", "suggestion", "action", "description", "resolution"]:
            if key in content and isinstance(content[key], str):
                return content[key]

        return None

    def _calculate_entry_confidence(
        self,
        entry,  # MemoryEntry
        similarity: float,
    ) -> float:
        """Calculate confidence score for a single entry recommendation.

        Based on:
        - Similarity to current issue
        - Recency of the entry
        - Outcome of the entry

        Args:
            entry: Memory entry being recommended.
            similarity: Similarity score to current issue.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Base confidence from similarity
        base_confidence = similarity * 0.5

        # Recency factor (newer = higher confidence)
        entry_date = datetime.fromisoformat(entry.created_at)
        age_days = (datetime.now() - entry_date).days
        # Recent entries (< 7 days) get full bonus, decays over 30 days
        recency_factor = max(0.0, 0.2 * (1 - age_days / 30))

        # Entry outcome factor
        outcome_factor = 0.15  # Default for no outcome
        if entry.outcome == "success":
            outcome_factor = 0.3
        elif entry.outcome == "failure":
            outcome_factor = 0.0

        confidence = base_confidence + recency_factor + outcome_factor

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))

    def record_outcome(
        self,
        entry_id: str,
        success: bool,
        notes: str = "",
    ) -> bool:
        """Record the outcome of a fix attempt.

        Updates the memory entry with the outcome to improve
        future confidence scoring.

        Args:
            entry_id: ID of the entry (recommendation or fix attempt).
            success: Whether the fix was successful.
            notes: Additional notes about the outcome.

        Returns:
            True if entry was found and updated, False otherwise.
        """
        entry = self.store.get_entry(entry_id)
        if entry is None:
            return False

        # Update the outcome
        entry.outcome = "success" if success else "failure"

        # Add notes to content if provided
        if notes:
            if "outcome_notes" not in entry.content:
                entry.content["outcome_notes"] = []
            entry.content["outcome_notes"].append({
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "notes": notes,
            })

        return True
