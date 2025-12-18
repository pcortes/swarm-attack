"""
Dependency Graph for Feature Swarm.

This module provides transitive dependency computation for issues.
When Issue #9 depends on Issue #5, and Issue #5 depends on Issue #1,
Issue #9 needs context from BOTH Issue #5 AND Issue #1.

This is critical for schema drift prevention - the coder needs to see
all classes from ALL transitively dependent issues, not just direct deps.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Set

if TYPE_CHECKING:
    from swarm_attack.models import TaskRef


class DependencyGraph:
    """
    Computes transitive closure of issue dependencies.

    Given a set of issues with dependencies, computes the full set of
    issues that each issue transitively depends on. This is essential
    for context handoff in schema drift prevention.

    Example:
        Issue #1: no deps       (creates models.py)
        Issue #5: deps on #1    (uses models.py, creates storage.py)
        Issue #9: deps on #5    (needs BOTH models.py AND storage.py)

        Without transitive deps, Issue #9 only sees Issue #5's classes.
        With transitive deps, Issue #9 sees Issue #1 AND Issue #5's classes.
    """

    def __init__(
        self,
        tasks: Optional[list[TaskRef]] = None,
    ) -> None:
        """
        Initialize the dependency graph.

        Args:
            tasks: Optional list of TaskRef objects with dependencies.
                   Can also use add_issue() to build incrementally.
        """
        # Adjacency list: issue_number -> set of direct dependency issue numbers
        self._graph: dict[int, set[int]] = defaultdict(set)
        # Cache for transitive deps (invalidated on modifications)
        self._transitive_cache: dict[int, set[int]] = {}

        if tasks:
            for task in tasks:
                self.add_issue(task.issue_number, task.dependencies)

    def add_issue(self, issue_number: int, dependencies: list[int]) -> None:
        """
        Add an issue and its dependencies to the graph.

        Args:
            issue_number: The issue number.
            dependencies: List of issue numbers this issue depends on.
        """
        self._graph[issue_number] = set(dependencies)
        # Invalidate cache since graph changed
        self._transitive_cache.clear()

    def get_direct_dependencies(self, issue_number: int) -> set[int]:
        """
        Get direct dependencies for an issue.

        Args:
            issue_number: The issue number.

        Returns:
            Set of issue numbers this issue directly depends on.
        """
        return self._graph.get(issue_number, set()).copy()

    def get_transitive_dependencies(self, issue_number: int) -> set[int]:
        """
        Get all issues this issue transitively depends on.

        Uses memoization to avoid recomputing for the same issue.

        Args:
            issue_number: The issue number.

        Returns:
            Set of all issue numbers this issue depends on (transitively).
            Does NOT include the issue itself.
        """
        if issue_number in self._transitive_cache:
            return self._transitive_cache[issue_number].copy()

        visited: set[int] = set()
        self._dfs(issue_number, visited)
        visited.discard(issue_number)  # Don't include self

        self._transitive_cache[issue_number] = visited
        return visited.copy()

    def _dfs(self, node: int, visited: set[int]) -> None:
        """
        Depth-first search to find all reachable nodes.

        Args:
            node: Current node to explore.
            visited: Set of already-visited nodes (mutated in place).
        """
        if node in visited:
            return

        visited.add(node)

        for dep in self._graph.get(node, set()):
            self._dfs(dep, visited)

    def get_dependents(self, issue_number: int) -> set[int]:
        """
        Get issues that depend on a given issue.

        This is the reverse lookup - useful for propagating context
        updates to dependent issues.

        Args:
            issue_number: The issue number.

        Returns:
            Set of issue numbers that directly depend on this issue.
        """
        dependents: set[int] = set()
        for issue, deps in self._graph.items():
            if issue_number in deps:
                dependents.add(issue)
        return dependents

    def get_transitive_dependents(self, issue_number: int) -> set[int]:
        """
        Get all issues that transitively depend on a given issue.

        Used for context propagation - when Issue #1 completes, we need
        to update context for ALL issues that depend on it (directly or
        transitively).

        Args:
            issue_number: The issue number.

        Returns:
            Set of all issue numbers that depend on this issue (transitively).
        """
        # Build reverse graph
        reverse_graph: dict[int, set[int]] = defaultdict(set)
        for issue, deps in self._graph.items():
            for dep in deps:
                reverse_graph[dep].add(issue)

        # DFS on reverse graph
        visited: set[int] = set()
        stack = [issue_number]

        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for dependent in reverse_graph.get(node, set()):
                if dependent not in visited:
                    stack.append(dependent)

        visited.discard(issue_number)  # Don't include self
        return visited

    def has_cycle(self) -> tuple[bool, list[int]]:
        """
        Detect cycles in the dependency graph.

        Uses Kahn's algorithm for topological sort. If not all nodes
        can be processed, there's a cycle.

        Returns:
            Tuple of (has_cycle, nodes_in_cycle).
            has_cycle is True if a cycle exists.
            nodes_in_cycle is a list of issue numbers involved in cycles.
        """
        # Calculate in-degrees
        in_degree: dict[int, int] = defaultdict(int)
        all_nodes: set[int] = set()

        for issue, deps in self._graph.items():
            all_nodes.add(issue)
            for dep in deps:
                all_nodes.add(dep)
                # Note: in_degree is backwards here - we want nodes with no dependents
                in_degree[issue] += 1  # issue depends on dep

        # Initialize in_degree for nodes with no dependencies
        for node in all_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        # Kahn's algorithm
        queue = [node for node in all_nodes if in_degree[node] == 0]
        processed = 0

        while queue:
            node = queue.pop(0)
            processed += 1

            # For each node that depends on this one
            for issue, deps in self._graph.items():
                if node in deps:
                    in_degree[issue] -= 1
                    if in_degree[issue] == 0:
                        queue.append(issue)

        has_cycle = processed < len(all_nodes)
        cycle_nodes = [node for node in all_nodes if in_degree[node] > 0]

        return has_cycle, cycle_nodes

    def topological_sort(self) -> list[int]:
        """
        Return issues in topological order (dependencies first).

        Issues with no dependencies come first, then issues that depend
        only on those, etc. Useful for determining execution order.

        Returns:
            List of issue numbers in topological order.
            Returns empty list if graph has cycles.
        """
        has_cycle, _ = self.has_cycle()
        if has_cycle:
            return []

        # Build reverse mapping for efficient lookup
        dependents_of: dict[int, set[int]] = defaultdict(set)
        for issue, deps in self._graph.items():
            for dep in deps:
                dependents_of[dep].add(issue)

        # Get all nodes
        all_nodes: set[int] = set(self._graph.keys())
        for deps in self._graph.values():
            all_nodes.update(deps)

        # Calculate initial in-degrees (how many deps each issue has)
        remaining_deps: dict[int, int] = {}
        for node in all_nodes:
            remaining_deps[node] = len(self._graph.get(node, set()))

        # Process nodes with no remaining deps
        result: list[int] = []
        available = [n for n in all_nodes if remaining_deps[n] == 0]

        while available:
            # Sort to ensure deterministic order
            available.sort()
            node = available.pop(0)
            result.append(node)

            # Decrease remaining deps for dependents
            for dependent in dependents_of[node]:
                remaining_deps[dependent] -= 1
                if remaining_deps[dependent] == 0:
                    available.append(dependent)

        return result

    def __repr__(self) -> str:
        return f"DependencyGraph(issues={len(self._graph)})"
