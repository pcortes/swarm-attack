"""
GitHub integration for Feature Swarm.

This module provides:
- IssueContextManager: Manages context propagation between GitHub issues
"""

from swarm_attack.github.issue_context import IssueContextManager

__all__ = ["IssueContextManager"]
