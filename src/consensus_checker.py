"""Consensus checking module for priority board.

Implements consensus detection and weighted voting for panel prioritization.
"""

from collections import Counter
from statistics import stdev
from src.models.priority import ConsensusResult


def check_consensus(
    panel_rankings: list[list[str]],
    round_number: int,
    max_rounds: int = 5,
    min_overlap: int = 3,
    max_std_dev: float = 1.5,
) -> ConsensusResult:
    """Check if panels have reached consensus on priorities.

    Natural consensus requires:
    - 3+ common priorities in top 5 across 4+ panels
    - Score standard deviation below max_std_dev threshold

    Forced consensus occurs after max_rounds.

    Args:
        panel_rankings: List of rankings (each ranking is list of priority names, top 10)
        round_number: Current debate round number
        max_rounds: Maximum rounds before forcing consensus (default 5)
        min_overlap: Minimum overlapping priorities needed (default 3)
        max_std_dev: Maximum standard deviation for agreement strength (default 1.5)

    Returns:
        ConsensusResult with reached status, common priorities, and overlap count
    """
    # Handle empty input
    if not panel_rankings:
        return ConsensusResult(
            reached=False,
            overlap_count=0,
            common_priorities=[],
            forced=False,
        )

    # Check if we should force consensus
    if round_number >= max_rounds:
        # Force consensus - get whatever overlap exists
        common = _find_common_priorities(panel_rankings, min_panels=1)
        return ConsensusResult(
            reached=True,
            overlap_count=len(common),
            common_priorities=common,
            forced=True,
        )

    # Need at least 4 panels for natural consensus
    if len(panel_rankings) < 4:
        common = _find_common_priorities(panel_rankings, min_panels=len(panel_rankings))
        return ConsensusResult(
            reached=False,
            overlap_count=len(common),
            common_priorities=common,
            forced=False,
        )

    # Extract top 5 from each panel
    top_5_rankings = [ranking[:5] for ranking in panel_rankings]

    # Find common priorities that appear in top 5 of at least 4 panels
    common = _find_common_priorities(top_5_rankings, min_panels=4)

    # Check if we have enough overlap
    if len(common) < min_overlap:
        return ConsensusResult(
            reached=False,
            overlap_count=len(common),
            common_priorities=common,
            forced=False,
        )

    # Check standard deviation of rankings for agreement strength
    std_dev = _calculate_rank_std_dev(top_5_rankings, common)
    if std_dev > max_std_dev:
        return ConsensusResult(
            reached=False,
            overlap_count=len(common),
            common_priorities=common,
            forced=False,
        )

    return ConsensusResult(
        reached=True,
        overlap_count=len(common),
        common_priorities=common,
        forced=False,
    )


def _find_common_priorities(
    rankings: list[list[str]], min_panels: int
) -> list[str]:
    """Find priorities that appear in at least min_panels rankings.

    Args:
        rankings: List of priority rankings
        min_panels: Minimum number of panels a priority must appear in

    Returns:
        List of common priority names
    """
    if not rankings:
        return []

    # Count occurrences across panels (use set per panel to handle duplicates)
    counter: Counter[str] = Counter()
    for ranking in rankings:
        unique_items = set(ranking)
        counter.update(unique_items)

    # Return items that appear in at least min_panels
    return [item for item, count in counter.items() if count >= min_panels]


def _calculate_rank_std_dev(
    rankings: list[list[str]], common_priorities: list[str]
) -> float:
    """Calculate standard deviation of rankings for common priorities.

    Lower values indicate stronger agreement on priority ordering.

    Args:
        rankings: List of priority rankings
        common_priorities: Priorities to calculate std dev for

    Returns:
        Average standard deviation across common priorities (0.0 if perfect agreement)
    """
    if not common_priorities or not rankings:
        return 0.0

    std_devs = []
    for priority in common_priorities:
        ranks = []
        for ranking in rankings:
            if priority in ranking:
                # Find position (1-indexed)
                try:
                    rank = ranking.index(priority) + 1
                    ranks.append(rank)
                except ValueError:
                    pass

        if len(ranks) >= 2:
            std_devs.append(stdev(ranks))
        else:
            std_devs.append(0.0)

    return sum(std_devs) / len(std_devs) if std_devs else 0.0


def weighted_vote(
    panel_rankings: dict[str, list[str]],
    weights: dict[str, float],
    top_n: int = 10,
) -> list[str]:
    """Calculate weighted vote ranking from panel submissions.

    Each panel's ranking contributes points based on:
    - Panel weight (e.g., Product 30%, CEO 30%, Eng 20%, Design 10%, Ops 10%)
    - Position points (10 for #1, 9 for #2, ..., 1 for #10)

    First-place items from each panel receive a bonus to ensure representation
    of each panel's top priority in the final ranking.

    Args:
        panel_rankings: Dict mapping panel name to list of priority names (ordered)
        weights: Dict mapping panel name to weight (0.0-1.0)
        top_n: Number of top priorities to return (default 10)

    Returns:
        List of top N priority names ordered by weighted score
    """
    if not panel_rankings or not weights:
        return []

    # Calculate scores for each priority
    scores: dict[str, float] = {}
    # Track first-place items for bonus
    first_place_items: set[str] = set()

    for panel_name, ranking in panel_rankings.items():
        # Skip panels not in weights
        if panel_name not in weights:
            continue

        weight = weights[panel_name]

        # Calculate points for each position (10 for #1, 9 for #2, etc.)
        for position, priority in enumerate(ranking[:10]):
            points = 10 - position  # 10, 9, 8, ..., 1
            weighted_points = points * weight

            if priority not in scores:
                scores[priority] = 0.0
            scores[priority] += weighted_points

            # Track first place items
            if position == 0:
                first_place_items.add(priority)

    # Apply bonus to first-place items to ensure panel representation
    # This bonus is small enough to not disrupt same-panel ordering
    # but large enough to lift first-place items above lower-ranked items
    # from higher-weighted panels
    first_place_bonus = 0.5
    for item in first_place_items:
        if item in scores:
            scores[item] += first_place_bonus

    # Sort by score (descending), then by name for stable tie-breaking
    sorted_priorities = sorted(
        scores.items(),
        key=lambda x: (-x[1], x[0]),  # Negative score for descending, name for tie-breaking
    )

    # Return top N names
    return [name for name, score in sorted_priorities[:top_n]]