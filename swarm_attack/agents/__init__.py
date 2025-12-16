"""
Feature Swarm agents package.

This package contains the AI agents that perform automated tasks:
- BaseAgent: Abstract base class for all agents
- SpecAuthorAgent: Generates engineering specs from PRDs
- SpecCriticAgent: Reviews and scores specs
- SpecModeratorAgent: Applies feedback to improve specs
- IssueCreatorAgent: Generates GitHub issues from specs
- IssueValidatorAgent: Validates generated issues
- PrioritizationAgent: Determines which issue to work on next
- CoderAgent: Implementation Agent with full TDD workflow (test + code + verify)
- VerifierAgent: Runs tests to verify implementation correctness
- RecoveryAgent: Analyzes failures and generates recovery plans
- BugCriticAgent: Reviews root cause analysis and fix plans (uses Codex)
- BugModeratorAgent: Applies critic feedback to improve analysis/plans
"""

from swarm_attack.agents.base import AgentResult, BaseAgent
from swarm_attack.agents.bug_critic import BugCriticAgent
from swarm_attack.agents.bug_moderator import BugModeratorAgent
from swarm_attack.agents.coder import CoderAgent
from swarm_attack.agents.issue_creator import IssueCreatorAgent
from swarm_attack.agents.issue_validator import IssueValidatorAgent
from swarm_attack.agents.prioritization import PrioritizationAgent
from swarm_attack.agents.recovery import RecoveryAgent
from swarm_attack.agents.spec_author import SpecAuthorAgent
from swarm_attack.agents.spec_critic import SpecCriticAgent
from swarm_attack.agents.spec_moderator import SpecModeratorAgent
from swarm_attack.agents.verifier import VerifierAgent

__all__ = [
    "AgentResult",
    "BaseAgent",
    "BugCriticAgent",
    "BugModeratorAgent",
    "CoderAgent",
    "IssueCreatorAgent",
    "IssueValidatorAgent",
    "PrioritizationAgent",
    "RecoveryAgent",
    "SpecAuthorAgent",
    "SpecCriticAgent",
    "SpecModeratorAgent",
    "VerifierAgent",
]
