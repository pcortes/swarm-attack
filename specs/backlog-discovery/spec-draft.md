# Backlog Discovery: Autonomous Opportunity Detection

## Expert Panel Consensus Document

**Panel Members:**
- Architecture Expert - Agent frameworks, state machines, existing patterns
- Product Expert - Value proposition, user experience, positioning
- Engineering Expert - Cost controls, parsing reliability, incremental delivery
- Agentic Systems Expert - Multi-agent debate patterns, loop control, convergence

**Date:** December 2025
**Status:** Phase 1-2 COMPLETE (128 tests passing), Phase 3 pending
**Version:** v2 (Phase 1-2 implemented)

---

## 1. Executive Summary

### Problem Statement

Developers using Swarm Attack currently must manually identify what to work on next. The system executes tasks well but lacks **proactive opportunity detection**. Key pain points:

1. **Test failures accumulate** - Failed tests aren't surfaced as actionable work items
2. **Stalled work goes unnoticed** - Interrupted sessions, abandoned features decay silently
3. **Code quality debt invisible** - No systematic detection of complexity, duplication, coverage gaps
4. **Manual backlog curation** - Human must review codebase, write issues, prioritize

### What Backlog Discovery Adds

Backlog Discovery introduces **autonomous opportunity detection** with human-in-the-loop approval:

| Capability | Current State | Target State |
|------------|---------------|--------------|
| Test Failures | Manual `pytest` review | **Auto-detected with fix suggestions** |
| Stalled Work | Hidden in `.swarm/state/` | **Surfaced with recovery recommendations** |
| Code Quality | Manual review | **Complexity/coverage gap detection** |
| Opportunity Curation | Human-driven | **AI discovery → Human approval** |

### Positioning (Product Expert Consensus)

**"Opportunity Detection"** NOT "Backlog Management"

This feature answers: *"What should I be working on that I'm not?"*

NOT: *"Reorder my existing backlog"* (that's `PrioritizationAgent`)

### Architecture Approach (Architecture Expert Consensus)

Leverage existing infrastructure:
- `StateGatherer` already aggregates system state - reuse, don't rebuild
- Clone proven 3-agent debate pattern from `spec_moderator.py`
- Store in `.swarm/backlog/` following existing patterns
- Trigger via `cos standup --deep` (opt-in, not every standup)

### Scope (12 Issues)

| Phase | Issues | Description | Status |
|-------|--------|-------------|--------|
| Phase 1 | 1-4 (4) | MVP: Test Failure Analyzer | **COMPLETE** (66 tests) |
| Phase 2 | 5-8 (4) | Stalled Work + Code Quality Discovery | **COMPLETE** (62 tests) |
| Phase 3 | 9-12 (4) | Full Debate Prioritization | Pending |

**Total: 128 tests passing**

---

## 2. Prerequisites

### Required: Chief of Staff v2 Complete

Backlog Discovery builds on the foundation established in v2:

**What v2 Provides (Required):**
- `StateGatherer` - System state aggregation (`chief_of_staff/state_gatherer.py`)
- `EpisodeStore` with `find_similar()` - Historical episode lookup
- `AutopilotRunner` - Goal execution infrastructure
- Checkpoint system with 6 triggers
- `.swarm/` directory structure and patterns

**What v3 Provides (Optional but Recommended):**
- `PreferenceLearner.find_similar_decisions()` - For learning from past approvals
- `ProgressTracker` - For real-time progress display
- Risk scoring engine - For actionability assessment

---

## 3. Expert Panel Debate Summary

### Architecture Expert

**Strong Support with Refinements:**

> "The proposal's 6 perspectives in Phase 1 is over-engineered. `StateGatherer` already provides structured data. Don't reanalyze - CLASSIFY existing output."

**Key Recommendation:**
```python
# Instead of 6 separate analysis passes:
class BacklogDiscoveryAgent(BaseAgent):
    def run(self, context):
        state = StateGatherer().gather()  # Already has everything

        candidates = []
        candidates += self._from_test_failures(state.test_state)
        candidates += self._from_stalled_work(state.features)
        candidates += self._from_code_quality(state.git_state)

        return AgentResult(success=True, output=candidates, cost_usd=0.50)
```

**Storage Recommendation:**
```
.swarm/backlog/
├── candidates.json       # Current candidate pool
├── debates/
│   └── <session-id>.json # Debate history
└── accepted.json         # Human-approved items
```

### Product Expert

**GO with Scope Clarity:**

> "The existing `PrioritizationAgent` is non-LLM algorithmic scoring. Creating a SECOND prioritization system (debate) could confuse users. Debate should focus on VALIDITY and ACTIONABILITY, not priority."

| Existing System | New System Should Focus On |
|-----------------|----------------------------|
| Scores known tasks | Discovers unknown opportunities |
| Ranks by value/risk | Validates if opportunity is real |
| Orders implementation | Filters noise from signal |

### Engineering Expert

**GO with Cost Controls:**

> "Proposal budget is reasonable IF you skip '6 perspectives'. The real challenge is parsing reliability - copy `spec_moderator.py`'s 5-strategy parser."

**Realistic Cost Estimate:**
- Discovery: $0.50-1.00 (simple classification)
- 3-round debate (when triggered): $1.50-2.50
- Actionability filter: $0.25-0.50
- **Total: $2.25-4.00 per session**

**Critical Path Recommendation:**
```
PHASE 1 MVP: Skip debate entirely
  - DiscoveryAgent analyzes test failures + stalled work
  - Apply actionability filter (hardcoded thresholds)
  - Present to human
  - COST: ~$0.75 per session

PHASE 2: Add debate for ambiguous cases only
  - If multiple valid opportunities detected
  - Debate to rank/filter
  - COST: +$1.50 when triggered
```

### Agentic Systems Expert

**STRONG GO - Proven Pattern:**

> "The proposal's 3-agent debate maps EXACTLY to existing proven pattern. ProductChampion = SpecAuthorAgent, EngineeringCritic = SpecCriticAgent, BusinessModerator = SpecModeratorAgent."

**Key Insight:**
```python
# From spec_critic.py - Uses Codex for independent validation
# This prevents "self-review bias"
# Keep Codex as EngineeringCritic for same reason
```

**Unified Recommendation:**
Don't create 4 phases. Create 3:
1. **Discovery** (single agent) → candidates
2. **Debate** (3-agent, when needed) → ranked candidates WITH actionability scores embedded
3. **Human Review** (checkpoint) → approval

Actionability should be a SCORE in the debate output, not a separate gate.

---

## 4. Phase 1: MVP - Test Failure Analyzer (4 Issues)

### Consensus Decision

Start with test failures because:
- **Highest signal** (objective failures, not subjective opinions)
- **Lowest false positive risk** (test failed = real problem)
- **Uses existing data** (EpisodeStore, pytest output)
- **Clear value prop** (prevent repeat failures)

### 4.1 Candidate Data Model

```python
# New file: swarm_attack/chief_of_staff/backlog_discovery/candidates.py

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any
from enum import Enum
import json


class OpportunityType(Enum):
    """Type of discovered opportunity."""
    TEST_FAILURE = "test_failure"
    STALLED_WORK = "stalled_work"
    CODE_QUALITY = "code_quality"
    COVERAGE_GAP = "coverage_gap"
    COMPLEXITY = "complexity"
    DUPLICATION = "duplication"


class OpportunityStatus(Enum):
    """Status of an opportunity in the pipeline."""
    DISCOVERED = "discovered"       # Just found
    DEBATING = "debating"           # In 3-agent debate
    ACTIONABLE = "actionable"       # Passed filters, ready for human
    ACCEPTED = "accepted"           # Human approved
    REJECTED = "rejected"           # Human declined
    DEFERRED = "deferred"           # Human said "later"


@dataclass
class Evidence:
    """Supporting evidence for an opportunity."""
    source: str                     # "test_output", "git_log", "static_analysis"
    content: str                    # The actual evidence
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        return cls(**data)


@dataclass
class ActionabilitySCore:
    """Scores for how actionable an opportunity is."""
    clarity: float          # 0-1: Is the problem clearly defined?
    evidence: float         # 0-1: How strong is the supporting evidence?
    effort: str            # "small", "medium", "large"
    reversibility: str      # "full", "partial", "none"

    @property
    def overall(self) -> float:
        """Weighted overall actionability score."""
        return (self.clarity * 0.4) + (self.evidence * 0.4) + (
            0.2 if self.effort == "small" else 0.1 if self.effort == "medium" else 0.0
        )

    def to_dict(self) -> dict:
        return {
            "clarity": self.clarity,
            "evidence": self.evidence,
            "effort": self.effort,
            "reversibility": self.reversibility,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionabilityScore":
        return cls(
            clarity=data["clarity"],
            evidence=data["evidence"],
            effort=data["effort"],
            reversibility=data["reversibility"],
        )


@dataclass
class Opportunity:
    """A discovered opportunity for improvement."""
    opportunity_id: str
    opportunity_type: OpportunityType
    status: OpportunityStatus

    # Core content
    title: str
    description: str
    evidence: list[Evidence]

    # Actionability
    actionability: Optional[ActionabilityScore] = None
    suggested_fix: Optional[str] = None
    affected_files: list[str] = field(default_factory=list)

    # Debate tracking (if debated)
    debate_session_id: Optional[str] = None
    champion_score: Optional[float] = None    # ProductChampion rating
    critic_score: Optional[float] = None      # EngineeringCritic rating
    moderator_decision: Optional[str] = None  # WORTH_PURSUING, NEEDS_EVIDENCE, NOT_ACTIONABLE

    # Metadata
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at: Optional[str] = None
    linked_issue: Optional[int] = None        # If converted to GitHub issue
    linked_goal: Optional[str] = None         # If added to daily goals

    # Similarity tracking (for deduplication)
    semantic_key: Optional[str] = None        # Stable identity for repeat detection
    similar_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "actionability": self.actionability.to_dict() if self.actionability else None,
            "suggested_fix": self.suggested_fix,
            "affected_files": self.affected_files,
            "debate_session_id": self.debate_session_id,
            "champion_score": self.champion_score,
            "critic_score": self.critic_score,
            "moderator_decision": self.moderator_decision,
            "discovered_at": self.discovered_at,
            "resolved_at": self.resolved_at,
            "linked_issue": self.linked_issue,
            "linked_goal": self.linked_goal,
            "semantic_key": self.semantic_key,
            "similar_to": self.similar_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Opportunity":
        return cls(
            opportunity_id=data["opportunity_id"],
            opportunity_type=OpportunityType(data["opportunity_type"]),
            status=OpportunityStatus(data["status"]),
            title=data["title"],
            description=data["description"],
            evidence=[Evidence.from_dict(e) for e in data["evidence"]],
            actionability=ActionabilityScore.from_dict(data["actionability"])
                if data.get("actionability") else None,
            suggested_fix=data.get("suggested_fix"),
            affected_files=data.get("affected_files", []),
            debate_session_id=data.get("debate_session_id"),
            champion_score=data.get("champion_score"),
            critic_score=data.get("critic_score"),
            moderator_decision=data.get("moderator_decision"),
            discovered_at=data.get("discovered_at", datetime.utcnow().isoformat()),
            resolved_at=data.get("resolved_at"),
            linked_issue=data.get("linked_issue"),
            linked_goal=data.get("linked_goal"),
            semantic_key=data.get("semantic_key"),
            similar_to=data.get("similar_to", []),
        )


@dataclass
class DiscoverySession:
    """A discovery session that found opportunities."""
    session_id: str
    started_at: str
    completed_at: Optional[str] = None

    # Configuration
    discovery_types: list[OpportunityType] = field(default_factory=list)
    max_candidates: int = 20
    budget_usd: float = 2.0

    # Results
    candidates_found: int = 0
    candidates_actionable: int = 0
    candidates_accepted: int = 0
    opportunities: list[str] = field(default_factory=list)  # opportunity_ids

    # Cost tracking
    cost_usd: float = 0.0
    debate_triggered: bool = False
    debate_rounds: int = 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "discovery_types": [t.value for t in self.discovery_types],
            "max_candidates": self.max_candidates,
            "budget_usd": self.budget_usd,
            "candidates_found": self.candidates_found,
            "candidates_actionable": self.candidates_actionable,
            "candidates_accepted": self.candidates_accepted,
            "opportunities": self.opportunities,
            "cost_usd": self.cost_usd,
            "debate_triggered": self.debate_triggered,
            "debate_rounds": self.debate_rounds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoverySession":
        return cls(
            session_id=data["session_id"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            discovery_types=[OpportunityType(t) for t in data.get("discovery_types", [])],
            max_candidates=data.get("max_candidates", 20),
            budget_usd=data.get("budget_usd", 2.0),
            candidates_found=data.get("candidates_found", 0),
            candidates_actionable=data.get("candidates_actionable", 0),
            candidates_accepted=data.get("candidates_accepted", 0),
            opportunities=data.get("opportunities", []),
            cost_usd=data.get("cost_usd", 0.0),
            debate_triggered=data.get("debate_triggered", False),
            debate_rounds=data.get("debate_rounds", 0),
        )
```

**Tests:**
```python
class TestOpportunity:
    def test_create_opportunity_from_test_failure(self):
        opp = Opportunity(
            opportunity_id="opp-12345678",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="test_user_auth fails with timeout",
            description="Test times out when auth service unavailable",
            evidence=[
                Evidence(
                    source="test_output",
                    content="TimeoutError: Auth service did not respond",
                    file_path="tests/test_auth.py",
                    line_number=45,
                )
            ],
            affected_files=["src/auth.py", "src/services/auth_client.py"],
        )

        assert opp.opportunity_type == OpportunityType.TEST_FAILURE
        assert len(opp.evidence) == 1
        assert opp.evidence[0].file_path == "tests/test_auth.py"

    def test_actionability_score_calculation(self):
        score = ActionabilityScore(
            clarity=0.9,
            evidence=0.8,
            effort="small",
            reversibility="full",
        )

        # (0.9 * 0.4) + (0.8 * 0.4) + 0.2 = 0.36 + 0.32 + 0.2 = 0.88
        assert score.overall == pytest.approx(0.88)

    def test_opportunity_serialization_roundtrip(self):
        opp = Opportunity(
            opportunity_id="opp-abc",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.ACTIONABLE,
            title="Feature X stalled for 3 days",
            description="No commits since Monday",
            evidence=[],
            actionability=ActionabilityScore(
                clarity=0.7,
                evidence=0.6,
                effort="medium",
                reversibility="full",
            ),
        )

        data = opp.to_dict()
        restored = Opportunity.from_dict(data)

        assert restored.opportunity_id == opp.opportunity_id
        assert restored.actionability.clarity == 0.7
```

---

### 4.2 Backlog Store

```python
# New file: swarm_attack/chief_of_staff/backlog_discovery/store.py

from pathlib import Path
from typing import Optional
import json
import fcntl
from datetime import datetime

from .candidates import Opportunity, OpportunityStatus, DiscoverySession


class BacklogStore:
    """Persistent storage for discovered opportunities."""

    def __init__(self, base_path: Path):
        self.base_path = base_path / "backlog"
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.candidates_file = self.base_path / "candidates.json"
        self.accepted_file = self.base_path / "accepted.json"
        self.sessions_path = self.base_path / "sessions"
        self.sessions_path.mkdir(exist_ok=True)

    def save_opportunity(self, opportunity: Opportunity) -> None:
        """Save or update an opportunity."""
        candidates = self._load_candidates()

        # Update or add
        candidates[opportunity.opportunity_id] = opportunity.to_dict()

        self._save_candidates(candidates)

    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]:
        """Get a specific opportunity."""
        candidates = self._load_candidates()
        data = candidates.get(opportunity_id)
        return Opportunity.from_dict(data) if data else None

    def get_opportunities_by_status(
        self,
        status: OpportunityStatus
    ) -> list[Opportunity]:
        """Get all opportunities with a given status."""
        candidates = self._load_candidates()
        return [
            Opportunity.from_dict(data)
            for data in candidates.values()
            if data["status"] == status.value
        ]

    def get_actionable(self) -> list[Opportunity]:
        """Get opportunities ready for human review."""
        return self.get_opportunities_by_status(OpportunityStatus.ACTIONABLE)

    def get_accepted(self) -> list[Opportunity]:
        """Get human-approved opportunities."""
        return self.get_opportunities_by_status(OpportunityStatus.ACCEPTED)

    def mark_accepted(self, opportunity_id: str, linked_issue: Optional[int] = None) -> None:
        """Mark opportunity as accepted by human."""
        opp = self.get_opportunity(opportunity_id)
        if opp:
            opp.status = OpportunityStatus.ACCEPTED
            opp.resolved_at = datetime.utcnow().isoformat()
            if linked_issue:
                opp.linked_issue = linked_issue
            self.save_opportunity(opp)

    def mark_rejected(self, opportunity_id: str, reason: Optional[str] = None) -> None:
        """Mark opportunity as rejected by human."""
        opp = self.get_opportunity(opportunity_id)
        if opp:
            opp.status = OpportunityStatus.REJECTED
            opp.resolved_at = datetime.utcnow().isoformat()
            self.save_opportunity(opp)

    def mark_deferred(self, opportunity_id: str) -> None:
        """Mark opportunity as deferred (review later)."""
        opp = self.get_opportunity(opportunity_id)
        if opp:
            opp.status = OpportunityStatus.DEFERRED
            self.save_opportunity(opp)

    def find_similar(self, opportunity: Opportunity, k: int = 5) -> list[Opportunity]:
        """Find similar past opportunities for deduplication."""
        candidates = self._load_candidates()

        # Simple keyword-based similarity (like EpisodeStore.find_similar)
        opp_words = set(opportunity.title.lower().split())

        scored = []
        for data in candidates.values():
            if data["opportunity_id"] == opportunity.opportunity_id:
                continue

            title_words = set(data["title"].lower().split())
            if opp_words or title_words:
                intersection = len(opp_words & title_words)
                union = len(opp_words | title_words)
                score = intersection / union if union > 0 else 0
                if score > 0.3:  # Similarity threshold
                    scored.append((score, Opportunity.from_dict(data)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [opp for score, opp in scored[:k]]

    def save_session(self, session: DiscoverySession) -> None:
        """Save a discovery session."""
        path = self.sessions_path / f"{session.session_id}.json"
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def get_session(self, session_id: str) -> Optional[DiscoverySession]:
        """Load a discovery session."""
        path = self.sessions_path / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return DiscoverySession.from_dict(json.load(f))

    def get_recent_sessions(self, limit: int = 10) -> list[DiscoverySession]:
        """Get recent discovery sessions."""
        sessions = []
        for path in sorted(self.sessions_path.glob("*.json"), reverse=True)[:limit]:
            with open(path, "r") as f:
                sessions.append(DiscoverySession.from_dict(json.load(f)))
        return sessions

    def _load_candidates(self) -> dict:
        """Load candidates from disk."""
        if not self.candidates_file.exists():
            return {}
        with open(self.candidates_file, "r") as f:
            return json.load(f)

    def _save_candidates(self, candidates: dict) -> None:
        """Save candidates to disk atomically."""
        temp_file = self.candidates_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(candidates, f, indent=2)
        temp_file.rename(self.candidates_file)
```

**Tests:**
```python
class TestBacklogStore:
    def test_save_and_retrieve_opportunity(self, tmp_path):
        store = BacklogStore(tmp_path)

        opp = Opportunity(
            opportunity_id="opp-test-1",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Test failure in auth module",
            description="Auth test times out",
            evidence=[],
        )

        store.save_opportunity(opp)
        retrieved = store.get_opportunity("opp-test-1")

        assert retrieved is not None
        assert retrieved.title == "Test failure in auth module"

    def test_get_actionable_opportunities(self, tmp_path):
        store = BacklogStore(tmp_path)

        # Save one discovered, one actionable
        store.save_opportunity(Opportunity(
            opportunity_id="opp-1",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Discovered",
            description="",
            evidence=[],
        ))
        store.save_opportunity(Opportunity(
            opportunity_id="opp-2",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.ACTIONABLE,
            title="Actionable",
            description="",
            evidence=[],
        ))

        actionable = store.get_actionable()
        assert len(actionable) == 1
        assert actionable[0].opportunity_id == "opp-2"

    def test_mark_accepted_updates_status(self, tmp_path):
        store = BacklogStore(tmp_path)

        store.save_opportunity(Opportunity(
            opportunity_id="opp-accept",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.ACTIONABLE,
            title="To Accept",
            description="",
            evidence=[],
        ))

        store.mark_accepted("opp-accept", linked_issue=42)

        opp = store.get_opportunity("opp-accept")
        assert opp.status == OpportunityStatus.ACCEPTED
        assert opp.linked_issue == 42
        assert opp.resolved_at is not None

    def test_find_similar_opportunities(self, tmp_path):
        store = BacklogStore(tmp_path)

        store.save_opportunity(Opportunity(
            opportunity_id="opp-auth-1",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.REJECTED,
            title="Auth test failure timeout",
            description="",
            evidence=[],
        ))
        store.save_opportunity(Opportunity(
            opportunity_id="opp-unrelated",
            opportunity_type=OpportunityType.CODE_QUALITY,
            status=OpportunityStatus.REJECTED,
            title="Database migration slow",
            description="",
            evidence=[],
        ))

        new_opp = Opportunity(
            opportunity_id="opp-auth-2",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Auth test timeout error",
            description="",
            evidence=[],
        )

        similar = store.find_similar(new_opp)
        assert len(similar) == 1
        assert similar[0].opportunity_id == "opp-auth-1"
```

---

### 4.3 Test Failure Discovery Agent

```python
# New file: swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py

import uuid
from datetime import datetime
from typing import Optional

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.chief_of_staff.state_gatherer import StateGatherer
from swarm_attack.chief_of_staff.episodes import EpisodeStore

from .candidates import (
    Opportunity,
    OpportunityType,
    OpportunityStatus,
    Evidence,
    ActionabilityScore,
    DiscoverySession,
)
from .store import BacklogStore


class TestFailureDiscoveryAgent(BaseAgent):
    """Discovers actionable opportunities from test failures.

    MVP agent that analyzes test failures from EpisodeStore and pytest output
    to generate fix suggestions. Does NOT use LLM for discovery (cost control).
    """

    AGENT_NAME = "test-failure-discovery"

    def __init__(
        self,
        state_gatherer: StateGatherer,
        episode_store: EpisodeStore,
        backlog_store: BacklogStore,
        llm_client: Optional[any] = None,  # Only for fix suggestions
    ):
        super().__init__()
        self.state_gatherer = state_gatherer
        self.episode_store = episode_store
        self.backlog_store = backlog_store
        self.llm_client = llm_client

    async def run(self, context: dict) -> AgentResult:
        """Discover opportunities from test failures.

        Args:
            context: Dict with optional keys:
                - max_candidates: Max opportunities to return (default 10)
                - include_fix_suggestions: Whether to use LLM for fixes (default False)
                - since_hours: Only look at failures from last N hours (default 24)

        Returns:
            AgentResult with output being list of Opportunity objects
        """
        max_candidates = context.get("max_candidates", 10)
        include_suggestions = context.get("include_fix_suggestions", False)
        since_hours = context.get("since_hours", 24)

        cost_usd = 0.0
        opportunities = []
        errors = []

        try:
            # 1. Gather current test state (no LLM, just data gathering)
            state = self.state_gatherer.gather()

            # 2. Find failed tests from recent episodes
            recent_episodes = self.episode_store.load_recent(limit=100)
            failed_episodes = [
                e for e in recent_episodes
                if not e.success and "test" in e.goal_id.lower()
            ]

            # 3. Parse pytest failures from state
            test_failures = self._extract_test_failures(state)

            # 4. Combine and deduplicate
            all_failures = self._merge_failures(failed_episodes, test_failures)

            # 5. Convert to opportunities
            for failure in all_failures[:max_candidates]:
                opp = self._failure_to_opportunity(failure)

                # Check for duplicates
                similar = self.backlog_store.find_similar(opp)
                if similar:
                    opp.similar_to = [s.opportunity_id for s in similar]
                    # Skip if very recent similar exists
                    if any(s.status == OpportunityStatus.REJECTED for s in similar):
                        continue  # Already rejected this type

                # Calculate actionability (no LLM)
                opp.actionability = self._assess_actionability(opp)

                # Optionally get fix suggestion (uses LLM)
                if include_suggestions and self.llm_client:
                    suggestion, suggestion_cost = await self._generate_fix_suggestion(opp)
                    opp.suggested_fix = suggestion
                    cost_usd += suggestion_cost

                # Mark as actionable if passes threshold
                if opp.actionability.overall >= 0.5:
                    opp.status = OpportunityStatus.ACTIONABLE

                opportunities.append(opp)
                self.backlog_store.save_opportunity(opp)

            return AgentResult(
                success=True,
                output=opportunities,
                errors=errors,
                cost_usd=cost_usd,
            )

        except Exception as e:
            errors.append(str(e))
            return AgentResult(
                success=False,
                output=[],
                errors=errors,
                cost_usd=cost_usd,
            )

    def _extract_test_failures(self, state) -> list[dict]:
        """Extract test failures from StateGatherer output."""
        failures = []

        # From test_state if available
        if hasattr(state, 'test_state') and state.test_state:
            for test in state.test_state.get('failures', []):
                failures.append({
                    'test_name': test.get('nodeid', 'unknown'),
                    'error_message': test.get('message', ''),
                    'file_path': test.get('path'),
                    'line_number': test.get('lineno'),
                    'source': 'pytest',
                })

        return failures

    def _merge_failures(self, episodes, test_failures) -> list[dict]:
        """Merge failures from episodes and pytest, deduplicating."""
        seen = set()
        merged = []

        # Episodes first (more context)
        for ep in episodes:
            key = ep.goal_id.lower()
            if key not in seen:
                seen.add(key)
                merged.append({
                    'test_name': ep.goal_id,
                    'error_message': ep.error or '',
                    'file_path': None,
                    'line_number': None,
                    'source': 'episode',
                    'retry_count': ep.retry_count,
                    'recovery_level': ep.recovery_level,
                })

        # Then pytest failures
        for failure in test_failures:
            key = failure['test_name'].lower()
            if key not in seen:
                seen.add(key)
                merged.append(failure)

        return merged

    def _failure_to_opportunity(self, failure: dict) -> Opportunity:
        """Convert a failure dict to an Opportunity."""
        opp_id = f"opp-{uuid.uuid4().hex[:8]}"

        evidence = [
            Evidence(
                source=failure.get('source', 'unknown'),
                content=failure.get('error_message', 'No error message'),
                file_path=failure.get('file_path'),
                line_number=failure.get('line_number'),
                timestamp=datetime.utcnow().isoformat(),
            )
        ]

        # Extract affected files from test path
        affected_files = []
        if failure.get('file_path'):
            affected_files.append(failure['file_path'])
            # Infer source file from test file
            test_path = failure['file_path']
            if 'test_' in test_path:
                source_path = test_path.replace('tests/', 'src/').replace('test_', '')
                affected_files.append(source_path)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title=f"Fix failing test: {failure['test_name']}",
            description=failure.get('error_message', 'Test failure needs investigation'),
            evidence=evidence,
            affected_files=affected_files,
            semantic_key=f"test-failure:{failure['test_name'].lower()}",
        )

    def _assess_actionability(self, opp: Opportunity) -> ActionabilityScore:
        """Assess actionability without LLM (rule-based)."""
        # Clarity: based on evidence quality
        has_file = any(e.file_path for e in opp.evidence)
        has_line = any(e.line_number for e in opp.evidence)
        has_message = any(len(e.content) > 20 for e in opp.evidence)

        clarity = 0.3
        if has_message:
            clarity += 0.3
        if has_file:
            clarity += 0.2
        if has_line:
            clarity += 0.2

        # Evidence: based on source reliability
        evidence_score = 0.7  # Test failures are reliable evidence
        if any(e.source == 'pytest' for e in opp.evidence):
            evidence_score = 0.9  # Direct pytest output is best

        # Effort: estimate from error type
        error_content = ' '.join(e.content.lower() for e in opp.evidence)
        if 'timeout' in error_content or 'connection' in error_content:
            effort = "medium"  # Infrastructure issues
        elif 'import' in error_content or 'undefined' in error_content:
            effort = "small"  # Simple fixes
        else:
            effort = "medium"  # Default

        return ActionabilityScore(
            clarity=clarity,
            evidence=evidence_score,
            effort=effort,
            reversibility="full",  # Tests are always reversible
        )

    async def _generate_fix_suggestion(self, opp: Opportunity) -> tuple[str, float]:
        """Generate fix suggestion using LLM. Returns (suggestion, cost)."""
        if not self.llm_client:
            return None, 0.0

        evidence_text = '\n'.join(
            f"- {e.source}: {e.content}" for e in opp.evidence
        )

        prompt = f"""
        A test is failing. Suggest a fix.

        Test: {opp.title}
        Files: {', '.join(opp.affected_files)}

        Evidence:
        {evidence_text}

        Provide a brief (2-3 sentence) suggestion for fixing this test.
        Focus on the most likely cause based on the error message.
        """

        response = await self.llm_client.complete(prompt, max_tokens=200)

        # Estimate cost (rough)
        cost = 0.01  # ~$0.01 per suggestion

        return response.strip(), cost
```

**Tests:**
```python
class TestTestFailureDiscoveryAgent:
    @pytest.fixture
    def agent(self, tmp_path):
        state_gatherer = Mock(spec=StateGatherer)
        episode_store = Mock(spec=EpisodeStore)
        backlog_store = BacklogStore(tmp_path)

        return TestFailureDiscoveryAgent(
            state_gatherer=state_gatherer,
            episode_store=episode_store,
            backlog_store=backlog_store,
        )

    def test_discovers_opportunities_from_failures(self, agent):
        # Mock state with test failures
        agent.state_gatherer.gather.return_value = Mock(
            test_state={
                'failures': [
                    {
                        'nodeid': 'tests/test_auth.py::test_login',
                        'message': 'AssertionError: Expected 200, got 401',
                        'path': 'tests/test_auth.py',
                        'lineno': 45,
                    }
                ]
            }
        )
        agent.episode_store.load_recent.return_value = []

        result = asyncio.run(agent.run({}))

        assert result.success
        assert len(result.output) == 1
        assert result.output[0].opportunity_type == OpportunityType.TEST_FAILURE
        assert "test_login" in result.output[0].title

    def test_merges_episodes_and_pytest_failures(self, agent):
        agent.state_gatherer.gather.return_value = Mock(
            test_state={
                'failures': [
                    {'nodeid': 'test_a', 'message': 'fail a', 'path': None, 'lineno': None}
                ]
            }
        )
        agent.episode_store.load_recent.return_value = [
            Mock(success=False, goal_id='test issue: test_b', error='fail b', retry_count=2, recovery_level='L1'),
        ]

        result = asyncio.run(agent.run({"max_candidates": 10}))

        assert result.success
        assert len(result.output) == 2

    def test_skips_duplicates_of_rejected(self, agent, tmp_path):
        # Pre-populate with rejected opportunity
        store = BacklogStore(tmp_path)
        store.save_opportunity(Opportunity(
            opportunity_id="old-opp",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.REJECTED,
            title="test auth login failure",
            description="",
            evidence=[],
        ))
        agent.backlog_store = store

        agent.state_gatherer.gather.return_value = Mock(
            test_state={
                'failures': [
                    {'nodeid': 'test_auth_login', 'message': 'same failure', 'path': None, 'lineno': None}
                ]
            }
        )
        agent.episode_store.load_recent.return_value = []

        result = asyncio.run(agent.run({}))

        # Should skip because similar was rejected
        assert result.success
        assert len(result.output) == 0

    def test_actionability_scoring(self, agent):
        opp = Opportunity(
            opportunity_id="test",
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title="Test",
            description="",
            evidence=[
                Evidence(
                    source="pytest",
                    content="AssertionError: expected True, got False",
                    file_path="tests/test_foo.py",
                    line_number=10,
                )
            ],
        )

        score = agent._assess_actionability(opp)

        assert score.clarity >= 0.7  # Has file, line, message
        assert score.evidence == 0.9  # pytest source
        assert score.effort in ["small", "medium", "large"]
```

---

### 4.4 CLI Integration

```python
# Additions to swarm_attack/cli/chief_of_staff.py

import click
from rich.console import Console
from rich.table import Table

from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import TestFailureDiscoveryAgent
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore
from swarm_attack.chief_of_staff.backlog_discovery.candidates import OpportunityStatus


@cos_group.command("discover")
@click.option("--deep", is_flag=True, help="Run full discovery with LLM suggestions")
@click.option("--type", "opp_type", type=click.Choice(["test", "stalled", "quality", "all"]), default="test")
@click.option("--max", "max_candidates", type=int, default=10)
def discover(deep: bool, opp_type: str, max_candidates: int):
    """Discover opportunities for improvement.

    Analyzes test failures, stalled work, and code quality issues
    to suggest actionable improvements.

    Examples:
        cos discover                  # Test failures (default)
        cos discover --type all       # All types (test + stalled + quality)
        cos discover --type stalled   # Stalled work only
        cos discover --type quality   # Code quality only
        cos discover --max 5          # Limit to 5 opportunities
        cos discover --no-debate      # Skip debate prioritization
    """
    console = Console()

    # Initialize components
    backlog_store = BacklogStore(Path.cwd() / ".swarm")

    with console.status("[bold green]Discovering opportunities..."):
        agent = TestFailureDiscoveryAgent(
            state_gatherer=StateGatherer(Path.cwd()),
            episode_store=EpisodeStore(Path.cwd() / ".swarm/chief-of-staff/episodes"),
            backlog_store=backlog_store,
            llm_client=get_llm_client() if deep else None,
        )

        result = asyncio.run(agent.run({
            "max_candidates": max_candidates,
            "include_fix_suggestions": deep,
        }))

    if not result.success:
        console.print(f"[red]Discovery failed: {result.errors}")
        return

    opportunities = result.output
    actionable = [o for o in opportunities if o.status == OpportunityStatus.ACTIONABLE]

    if not opportunities:
        console.print("[green]No opportunities found. Your codebase looks healthy!")
        return

    # Display results
    console.print(f"\n[bold]Found {len(opportunities)} opportunities ({len(actionable)} actionable)[/bold]\n")

    table = Table(title="Discovered Opportunities")
    table.add_column("#", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Title")
    table.add_column("Score", justify="right")
    table.add_column("Effort", justify="center")

    for i, opp in enumerate(opportunities[:10], 1):
        score = f"{opp.actionability.overall:.0%}" if opp.actionability else "-"
        effort = opp.actionability.effort if opp.actionability else "-"
        type_emoji = {
            "test_failure": "🧪",
            "stalled_work": "⏸️",
            "code_quality": "📊",
        }.get(opp.opportunity_type.value, "❓")

        table.add_row(
            str(i),
            f"{type_emoji} {opp.opportunity_type.value}",
            opp.title[:50] + "..." if len(opp.title) > 50 else opp.title,
            score,
            effort,
        )

    console.print(table)

    # Prompt for action
    if actionable:
        console.print(f"\n[bold]Cost: ${result.cost_usd:.2f}[/bold]")
        console.print("\n[dim]Actions: [1-N] Review  [a] Accept all  [Enter] Skip[/dim]")

        choice = click.prompt("", default="", show_default=False)

        if choice.lower() == 'a':
            for opp in actionable:
                backlog_store.mark_accepted(opp.opportunity_id)
            console.print(f"[green]Accepted {len(actionable)} opportunities[/green]")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(opportunities):
                _review_opportunity(console, opportunities[idx], backlog_store)


@cos_group.command("backlog")
@click.option("--status", type=click.Choice(["actionable", "accepted", "all"]), default="actionable")
def show_backlog(status: str):
    """Show discovered opportunities.

    Examples:
        cos backlog                # Show actionable items
        cos backlog --status all   # Show all items
    """
    console = Console()
    backlog_store = BacklogStore(Path.cwd() / ".swarm")

    if status == "actionable":
        opportunities = backlog_store.get_actionable()
    elif status == "accepted":
        opportunities = backlog_store.get_accepted()
    else:
        opportunities = list(backlog_store._load_candidates().values())
        opportunities = [Opportunity.from_dict(o) for o in opportunities]

    if not opportunities:
        console.print(f"[dim]No {status} opportunities[/dim]")
        return

    table = Table(title=f"{status.title()} Opportunities")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Discovered")

    for opp in opportunities:
        table.add_row(
            opp.opportunity_id[:12],
            opp.opportunity_type.value,
            opp.title[:40],
            opp.status.value,
            opp.discovered_at[:10],
        )

    console.print(table)


def _review_opportunity(console: Console, opp: Opportunity, store: BacklogStore):
    """Interactive review of a single opportunity."""
    console.print(f"\n[bold]{opp.title}[/bold]")
    console.print(f"Type: {opp.opportunity_type.value}")
    console.print(f"Description: {opp.description}")

    if opp.evidence:
        console.print("\n[bold]Evidence:[/bold]")
        for e in opp.evidence:
            console.print(f"  - [{e.source}] {e.content[:100]}")
            if e.file_path:
                console.print(f"    File: {e.file_path}:{e.line_number or '?'}")

    if opp.suggested_fix:
        console.print(f"\n[bold]Suggested Fix:[/bold]\n{opp.suggested_fix}")

    console.print("\n[dim][a]ccept  [r]eject  [d]efer  [c]reate issue  [Enter] skip[/dim]")

    choice = click.prompt("", default="", show_default=False)

    if choice.lower() == 'a':
        store.mark_accepted(opp.opportunity_id)
        console.print("[green]Accepted[/green]")
    elif choice.lower() == 'r':
        store.mark_rejected(opp.opportunity_id)
        console.print("[red]Rejected[/red]")
    elif choice.lower() == 'd':
        store.mark_deferred(opp.opportunity_id)
        console.print("[yellow]Deferred[/yellow]")
    elif choice.lower() == 'c':
        # Create GitHub issue
        issue_number = _create_github_issue(opp)
        store.mark_accepted(opp.opportunity_id, linked_issue=issue_number)
        console.print(f"[green]Created issue #{issue_number}[/green]")
```

**Integration with standup --deep:**

```python
# In standup command
@cos_group.command("standup")
@click.option("--deep", is_flag=True, help="Include opportunity discovery")
def standup(deep: bool):
    """Run daily standup with optional deep discovery."""
    # ... existing standup logic ...

    if deep:
        console.print("\n[bold]Running opportunity discovery...[/bold]")
        ctx.invoke(discover, deep=True, opp_type="test", max_candidates=5)
```

---

### Phase 1 Implementation Tasks (4 Issues)

| # | Task | Size | Dependencies | Acceptance Criteria |
|---|------|------|--------------|---------------------|
| 1.1 | Create Opportunity and Evidence dataclasses | S | - | All tests pass, serialization roundtrip works |
| 1.2 | Implement BacklogStore persistence | M | 1.1 | CRUD operations work, similarity search works |
| 1.3 | Implement TestFailureDiscoveryAgent | L | 1.1, 1.2 | Discovers from pytest + episodes, deduplicates, scores actionability |
| 1.4 | Add `cos discover` and `cos backlog` CLI commands | M | 1.3 | Interactive review flow works, integrates with standup --deep |

---

## 5. Phase 2: Stalled Work + Code Quality Discovery (4 Issues)

### Consensus Decision

After MVP proves value, expand to:
1. **Stalled Work** - Features/bugs that haven't progressed
2. **Code Quality** - Complexity hotspots, coverage gaps

### 5.1 Stalled Work Discovery Agent

```python
class StalledWorkDiscoveryAgent(BaseAgent):
    """Discovers opportunities from stalled/interrupted work.

    Analyzes:
    - Features stuck in non-terminal phases
    - Sessions that were interrupted
    - Goals that failed repeatedly
    """

    def _extract_stalled_features(self, state) -> list[dict]:
        """Find features that haven't progressed."""
        stalled = []

        for feature_id, feature_state in state.features.items():
            # Check if stuck in same phase for >24 hours
            if feature_state.phase_stuck_hours > 24:
                stalled.append({
                    'type': 'stuck_phase',
                    'feature_id': feature_id,
                    'phase': feature_state.phase,
                    'hours_stuck': feature_state.phase_stuck_hours,
                    'last_activity': feature_state.last_activity,
                })

            # Check for interrupted sessions
            if feature_state.has_interrupted_session:
                stalled.append({
                    'type': 'interrupted',
                    'feature_id': feature_id,
                    'session_id': feature_state.interrupted_session_id,
                    'interrupted_at': feature_state.interrupted_at,
                })

        return stalled

    def _stalled_to_opportunity(self, stalled: dict) -> Opportunity:
        """Convert stalled work to opportunity."""
        if stalled['type'] == 'stuck_phase':
            title = f"Unblock {stalled['feature_id']}: stuck in {stalled['phase']}"
            description = f"Feature has been in {stalled['phase']} phase for {stalled['hours_stuck']} hours"
        else:
            title = f"Resume interrupted work on {stalled['feature_id']}"
            description = f"Session was interrupted at {stalled['interrupted_at']}"

        return Opportunity(
            opportunity_id=f"opp-{uuid.uuid4().hex[:8]}",
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=[Evidence(
                source="state_gatherer",
                content=json.dumps(stalled),
            )],
            semantic_key=f"stalled:{stalled['feature_id']}",
        )
```

### 5.2 Code Quality Discovery Agent

```python
class CodeQualityDiscoveryAgent(BaseAgent):
    """Discovers code quality opportunities.

    Analyzes:
    - Complexity hotspots (cyclomatic complexity)
    - Coverage gaps (files with low test coverage)
    - Large files (potential split candidates)

    Uses static analysis, NOT LLM (cost control).
    """

    COMPLEXITY_THRESHOLD = 10  # McCabe complexity
    COVERAGE_THRESHOLD = 0.5   # 50% minimum
    FILE_SIZE_THRESHOLD = 500  # Lines

    async def run(self, context: dict) -> AgentResult:
        opportunities = []

        # 1. Find complexity hotspots (using radon if available)
        complex_files = await self._find_complexity_hotspots()
        for cf in complex_files[:5]:
            opportunities.append(self._complexity_to_opportunity(cf))

        # 2. Find coverage gaps (using coverage.py data if available)
        coverage_gaps = await self._find_coverage_gaps()
        for gap in coverage_gaps[:5]:
            opportunities.append(self._coverage_to_opportunity(gap))

        # 3. Find oversized files
        large_files = await self._find_large_files()
        for lf in large_files[:3]:
            opportunities.append(self._large_file_to_opportunity(lf))

        return AgentResult(
            success=True,
            output=opportunities,
            errors=[],
            cost_usd=0.0,  # Static analysis only
        )

    async def _find_complexity_hotspots(self) -> list[dict]:
        """Find functions with high cyclomatic complexity."""
        try:
            # Use radon for complexity analysis
            result = await run_command(
                f"radon cc {self.source_path} -a -j",
                timeout=30,
            )
            data = json.loads(result.stdout)

            hotspots = []
            for file_path, functions in data.items():
                for func in functions:
                    if func['complexity'] > self.COMPLEXITY_THRESHOLD:
                        hotspots.append({
                            'file': file_path,
                            'function': func['name'],
                            'complexity': func['complexity'],
                            'line': func['lineno'],
                        })

            return sorted(hotspots, key=lambda x: x['complexity'], reverse=True)
        except Exception:
            return []  # Radon not available

    async def _find_coverage_gaps(self) -> list[dict]:
        """Find files with low test coverage."""
        coverage_file = Path.cwd() / ".coverage"
        if not coverage_file.exists():
            return []

        try:
            result = await run_command("coverage json -o /tmp/coverage.json", timeout=10)
            with open("/tmp/coverage.json") as f:
                data = json.load(f)

            gaps = []
            for file_path, file_data in data.get('files', {}).items():
                coverage_pct = file_data.get('summary', {}).get('percent_covered', 100)
                if coverage_pct < self.COVERAGE_THRESHOLD * 100:
                    gaps.append({
                        'file': file_path,
                        'coverage': coverage_pct,
                        'missing_lines': file_data.get('missing_lines', []),
                    })

            return sorted(gaps, key=lambda x: x['coverage'])
        except Exception:
            return []

    def _complexity_to_opportunity(self, hotspot: dict) -> Opportunity:
        return Opportunity(
            opportunity_id=f"opp-{uuid.uuid4().hex[:8]}",
            opportunity_type=OpportunityType.COMPLEXITY,
            status=OpportunityStatus.DISCOVERED,
            title=f"Reduce complexity in {hotspot['function']}",
            description=f"Cyclomatic complexity of {hotspot['complexity']} exceeds threshold of {self.COMPLEXITY_THRESHOLD}",
            evidence=[Evidence(
                source="radon",
                content=f"Complexity: {hotspot['complexity']}",
                file_path=hotspot['file'],
                line_number=hotspot['line'],
            )],
            affected_files=[hotspot['file']],
            actionability=ActionabilityScore(
                clarity=0.9,
                evidence=0.95,
                effort="medium",
                reversibility="full",
            ),
        )
```

### Phase 2 Implementation Tasks (4 Issues)

| # | Task | Size | Dependencies | Acceptance Criteria |
|---|------|------|--------------|---------------------|
| 5 | Implement StalledWorkDiscoveryAgent | M | Phase 1 | Finds stuck features, interrupted sessions |
| 6 | Implement CodeQualityDiscoveryAgent | L | Phase 1 | Complexity, coverage, file size detection |
| 7 | Create unified DiscoveryOrchestrator | M | 5, 6 | Runs all agents, merges results |
| 8 | Update CLI for multi-type discovery | S | 7 | `--type all` works, shows combined results |

---

## 6. Phase 3: Debate Prioritization (4 Issues)

### Consensus Decision

When multiple opportunities are found, use 3-agent debate to prioritize:

| Agent | Role | Model |
|-------|------|-------|
| ProductChampion | Argues for user impact, market fit | Claude |
| EngineeringCritic | Assesses feasibility, risk, effort | Codex |
| BusinessModerator | Reconciles, makes final ranking | Claude |

### 6.1 Debate Data Model

```python
@dataclass
class DebateRound:
    """One round of the 3-agent debate."""
    round_number: int

    # Agent outputs
    champion_argument: str
    champion_rankings: list[str]      # opportunity_ids in order

    critic_argument: str
    critic_concerns: dict[str, list[str]]  # opportunity_id -> concerns

    moderator_decision: str
    moderator_rankings: list[str]     # Final rankings this round
    continue_debate: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DebateSession:
    """A complete debate session."""
    session_id: str
    opportunities: list[str]          # opportunity_ids being debated

    rounds: list[DebateRound] = field(default_factory=list)
    max_rounds: int = 3

    # Outcome
    final_rankings: list[str] = field(default_factory=list)
    consensus_reached: bool = False
    stalemate: bool = False

    # Cost
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "opportunities": self.opportunities,
            "rounds": [r.to_dict() for r in self.rounds],
            "max_rounds": self.max_rounds,
            "final_rankings": self.final_rankings,
            "consensus_reached": self.consensus_reached,
            "stalemate": self.stalemate,
            "cost_usd": self.cost_usd,
        }
```

### 6.2 Debate Agents

```python
class BacklogChampionAgent(BaseAgent):
    """Champions opportunities from product/user perspective.

    Cloned from SpecAuthorAgent pattern.
    """

    SKILL = "backlog-champion"

    async def run(self, context: dict) -> AgentResult:
        opportunities = context["opportunities"]
        prior_arguments = context.get("prior_arguments", [])

        prompt = self.load_skill(self.SKILL)
        prompt += f"""

        Evaluate these opportunities from a PRODUCT perspective:

        {self._format_opportunities(opportunities)}

        Prior discussion:
        {self._format_prior_arguments(prior_arguments)}

        For each opportunity, assess:
        1. User impact (how much does this help users?)
        2. Market fit (does this align with product direction?)
        3. Urgency (is this blocking users now?)

        Return JSON:
        {{
            "argument": "Your reasoning for the rankings",
            "rankings": ["opp-id-1", "opp-id-2", ...]  // Best first
        }}
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)

        return AgentResult(
            success=True,
            output=data,
            cost_usd=self._estimate_cost(prompt, response),
        )


class BacklogCriticAgent(BaseAgent):
    """Critiques opportunities from engineering perspective.

    Uses Codex for independent validation (prevents self-review bias).
    """

    SKILL = "backlog-critic"
    MODEL = "codex"  # Use Codex for independence

    async def run(self, context: dict) -> AgentResult:
        opportunities = context["opportunities"]
        champion_rankings = context["champion_rankings"]

        prompt = self.load_skill(self.SKILL)
        prompt += f"""

        The ProductChampion ranked opportunities as: {champion_rankings}

        Evaluate from an ENGINEERING perspective:

        {self._format_opportunities(opportunities)}

        For each opportunity, assess:
        1. Feasibility (can we actually do this?)
        2. Risk (what could go wrong?)
        3. Effort (small/medium/large)
        4. Dependencies (what needs to happen first?)

        Return JSON:
        {{
            "argument": "Your engineering critique",
            "concerns": {{
                "opp-id-1": ["concern 1", "concern 2"],
                ...
            }}
        }}
        """

        response = await self.codex.complete(prompt)
        data = json.loads(response)

        return AgentResult(
            success=True,
            output=data,
            cost_usd=self._estimate_cost(prompt, response),
        )


class BacklogModeratorAgent(BaseAgent):
    """Reconciles champion and critic, produces final rankings.

    Cloned from SpecModeratorAgent pattern with disposition tracking.
    """

    SKILL = "backlog-moderator"

    async def run(self, context: dict) -> AgentResult:
        opportunities = context["opportunities"]
        champion = context["champion_output"]
        critic = context["critic_output"]
        round_number = context["round_number"]
        prior_decisions = context.get("prior_decisions", [])

        prompt = self.load_skill(self.SKILL)
        prompt += f"""

        Round {round_number} of debate.

        ProductChampion argues: {champion["argument"]}
        ProductChampion rankings: {champion["rankings"]}

        EngineeringCritic concerns:
        {json.dumps(critic["concerns"], indent=2)}

        Prior moderator decisions: {prior_decisions}

        Your task:
        1. Reconcile champion and critic perspectives
        2. Produce final rankings for this round
        3. Decide if consensus reached or more debate needed

        Return JSON:
        {{
            "decision": "Your reconciliation reasoning",
            "rankings": ["opp-id-1", ...],
            "consensus_reached": true/false,
            "continue_debate": true/false
        }}
        """

        response = await self.llm.complete(prompt)
        data = json.loads(response)

        return AgentResult(
            success=True,
            output=data,
            cost_usd=self._estimate_cost(prompt, response),
        )
```

### 6.3 Debate Orchestrator

```python
class BacklogDebateOrchestrator:
    """Orchestrates the 3-agent debate for opportunity prioritization.

    Pattern cloned from Orchestrator.run_spec_pipeline().
    """

    def __init__(
        self,
        champion: BacklogChampionAgent,
        critic: BacklogCriticAgent,
        moderator: BacklogModeratorAgent,
        backlog_store: BacklogStore,
        max_rounds: int = 3,
        budget_usd: float = 1.50,
    ):
        self.champion = champion
        self.critic = critic
        self.moderator = moderator
        self.backlog_store = backlog_store
        self.max_rounds = max_rounds
        self.budget_usd = budget_usd

    async def debate(self, opportunities: list[Opportunity]) -> DebateSession:
        """Run debate to prioritize opportunities."""
        session = DebateSession(
            session_id=f"debate-{uuid.uuid4().hex[:8]}",
            opportunities=[o.opportunity_id for o in opportunities],
        )

        prior_arguments = []
        prior_decisions = []

        for round_num in range(1, self.max_rounds + 1):
            # Check budget
            if session.cost_usd >= self.budget_usd:
                session.stalemate = True
                break

            # Phase 1: Champion argues
            champion_result = await self.champion.run({
                "opportunities": opportunities,
                "prior_arguments": prior_arguments,
            })
            session.cost_usd += champion_result.cost_usd

            # Phase 2: Critic responds
            critic_result = await self.critic.run({
                "opportunities": opportunities,
                "champion_rankings": champion_result.output["rankings"],
            })
            session.cost_usd += critic_result.cost_usd

            # Phase 3: Moderator reconciles
            moderator_result = await self.moderator.run({
                "opportunities": opportunities,
                "champion_output": champion_result.output,
                "critic_output": critic_result.output,
                "round_number": round_num,
                "prior_decisions": prior_decisions,
            })
            session.cost_usd += moderator_result.cost_usd

            # Record round
            round = DebateRound(
                round_number=round_num,
                champion_argument=champion_result.output["argument"],
                champion_rankings=champion_result.output["rankings"],
                critic_argument=critic_result.output["argument"],
                critic_concerns=critic_result.output["concerns"],
                moderator_decision=moderator_result.output["decision"],
                moderator_rankings=moderator_result.output["rankings"],
                continue_debate=moderator_result.output.get("continue_debate", False),
            )
            session.rounds.append(round)

            # Update tracking
            prior_arguments.append(champion_result.output["argument"])
            prior_decisions.append(moderator_result.output["decision"])

            # Check for consensus
            if moderator_result.output.get("consensus_reached", False):
                session.consensus_reached = True
                session.final_rankings = round.moderator_rankings
                break

            if not round.continue_debate:
                session.final_rankings = round.moderator_rankings
                break

        # If no consensus after all rounds, use last moderator rankings
        if not session.final_rankings and session.rounds:
            session.final_rankings = session.rounds[-1].moderator_rankings
            session.stalemate = True

        # Update opportunities with debate results
        for i, opp_id in enumerate(session.final_rankings):
            opp = self.backlog_store.get_opportunity(opp_id)
            if opp:
                opp.debate_session_id = session.session_id
                opp.champion_score = self._rank_to_score(i, len(session.final_rankings))
                opp.critic_score = self._concerns_to_score(
                    opp_id,
                    session.rounds[-1].critic_concerns if session.rounds else {}
                )
                self.backlog_store.save_opportunity(opp)

        return session

    def _rank_to_score(self, rank: int, total: int) -> float:
        """Convert rank position to 0-1 score."""
        return 1.0 - (rank / total)

    def _concerns_to_score(self, opp_id: str, concerns: dict) -> float:
        """Convert concerns count to 0-1 score (fewer = higher)."""
        opp_concerns = concerns.get(opp_id, [])
        # Max 5 concerns = 0, 0 concerns = 1
        return max(0.0, 1.0 - (len(opp_concerns) / 5))
```

### Phase 3 Implementation Tasks (4 Issues)

| # | Task | Size | Dependencies | Acceptance Criteria |
|---|------|------|--------------|---------------------|
| 9 | Create DebateSession and DebateRound models | S | Phase 1 | Serialization works |
| 10 | Implement BacklogChampion/Critic/Moderator agents | L | 9 | Each agent produces valid output |
| 11 | Implement BacklogDebateOrchestrator | L | 10 | 3-round debate works, handles consensus/stalemate |
| 12 | Integrate debate into discovery pipeline | M | 11 | Auto-triggers when >5 opportunities, updates rankings |

---

## 7. Configuration

```python
# Additions to swarm_attack/chief_of_staff/config.py

@dataclass
class BacklogDiscoveryConfig:
    """Configuration for backlog discovery."""

    # Discovery settings
    max_candidates: int = 20
    actionability_threshold: float = 0.5
    similarity_threshold: float = 0.3

    # Trigger settings
    trigger_on_standup_deep: bool = True
    auto_discover_on_test_failure: bool = False

    # Debate settings
    debate_threshold: int = 5           # Trigger debate if > N candidates
    debate_max_rounds: int = 3
    debate_budget_usd: float = 1.50

    # Agent settings
    include_fix_suggestions: bool = False  # LLM suggestions (adds cost)
    discovery_budget_usd: float = 2.00

    # Discovery types enabled
    discover_test_failures: bool = True
    discover_stalled_work: bool = True
    discover_code_quality: bool = False  # Disabled by default (requires radon)
```

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Discovery accuracy | >80% | Opportunities marked actionable that human accepts |
| False positive rate | <20% | Opportunities human rejects as irrelevant |
| Time to discovery | <30s | CLI response time for `cos discover` |
| Cost per session | <$3 | Average cost including debate |
| Adoption rate | >50% | Users who use `--deep` flag regularly |

---

## 9. Risk Mitigations

| Risk | Mitigation | Owner |
|------|------------|-------|
| Too many low-quality candidates | Actionability threshold filter | Engineering |
| Duplicate detection fails | Semantic key + similarity matching | Architecture |
| Debate doesn't converge | Max 3 rounds + budget cap | Agentic Systems |
| Human approval bottleneck | Clear "Accept all" option | Product |
| Cost overruns | Per-session budget limits | Engineering |

---

## 10. Dependencies

### Required
- Chief of Staff v2 complete (StateGatherer, EpisodeStore)
- `.swarm/` directory structure

### Optional but Recommended
- `radon` for complexity analysis (Phase 2)
- `coverage.py` for coverage gap detection (Phase 2)
- Chief of Staff v3 for enhanced learning (Phase 3)

---

## 11. Issue Summary

### Phase 1: MVP - Test Failure Analyzer (4 issues) - **COMPLETE**
| # | Title | Size | Status |
|---|-------|------|--------|
| 1.1 | Create Opportunity and Evidence dataclasses | S | **Done** |
| 1.2 | Implement BacklogStore persistence | M | **Done** |
| 1.3 | Implement TestFailureDiscoveryAgent | L | **Done** |
| 1.4 | Add `cos discover` and `cos backlog` CLI commands | M | **Done** |

### Phase 2: Stalled Work + Code Quality (4 issues) - **COMPLETE**
| # | Title | Size | Status |
|---|-------|------|--------|
| 5 | Implement StalledWorkDiscoveryAgent | M | **Done** |
| 6 | Implement FeatureOpportunityAgent (McKinsey-style) | L | **Done** |
| 6b | Implement CodeQualityDiscoveryAgent | L | **Done** |
| 7 | Create unified DiscoveryOrchestrator | M | **Done** |
| 8 | Update CLI for multi-type discovery | S | **Done** |

### Phase 3: Debate Prioritization (4 issues) - Pending
| # | Title | Size | Status |
|---|-------|------|--------|
| 9 | Create DebateSession and DebateRound models | S | Pending |
| 10 | Implement BacklogChampion/Critic/Moderator agents | L | Pending |
| 11 | Implement BacklogDebateOrchestrator | L | Pending |
| 12 | Integrate debate into discovery pipeline | M | Pending |

**Total: 12 issues (8 complete, 4 pending)**
**Test Coverage: 128 tests passing**

### Implementation Files (Phase 1-2)

**Core Modules (`swarm_attack/chief_of_staff/backlog_discovery/`):**
| File | Lines | Description |
|------|-------|-------------|
| `candidates.py` | ~350 | Data models: Opportunity, Evidence, ActionabilityScore |
| `store.py` | ~180 | BacklogStore: persistence, similarity search, status transitions |
| `discovery_agent.py` | ~250 | TestFailureDiscoveryAgent: pytest + episode analysis |
| `stalled_work_agent.py` | ~350 | StalledWorkDiscoveryAgent: stuck features, sessions, failures |
| `feature_opportunity_agent.py` | ~400 | FeatureOpportunityAgent: McKinsey-style ROI analysis |
| `code_quality_agent.py` | ~380 | CodeQualityDiscoveryAgent: complexity, coverage, size |
| `orchestrator.py` | ~160 | DiscoveryOrchestrator: runs agents, merges, deduplicates |

**Test Files (`tests/generated/backlog-discovery/`):**
| File | Tests | Description |
|------|-------|-------------|
| `test_candidates.py` | 21 | Data model tests |
| `test_store.py` | 18 | Persistence tests |
| `test_discovery_agent.py` | 15 | Test failure discovery |
| `test_stalled_work_agent.py` | 14 | Stalled work detection |
| `test_feature_opportunity_agent.py` | 17 | McKinsey analysis |
| `test_code_quality_agent.py` | 19 | Static analysis |
| `test_orchestrator.py` | 12 | Multi-agent orchestration |

---

## 12. Expert Panel Statement

**Architecture Expert:** "This design correctly reuses existing patterns. StateGatherer provides the data, debate pattern from spec_moderator is proven, storage follows .swarm conventions."

**Product Expert:** "Clear positioning as 'Opportunity Detection' differentiates from existing PrioritizationAgent. The human approval gate ensures trust."

**Engineering Expert:** "MVP cost of ~$0.75 per session is sustainable. Debate only triggers when needed, keeping average cost under $3."

**Agentic Systems Expert:** "3-agent debate with Codex as independent critic prevents self-review bias. Loop control with max rounds and budget cap ensures convergence."

---

*Spec Version: v1 MVP*
*Expert Panel: Architecture, Product, Engineering, Agentic Systems*
*Prerequisites: Chief of Staff v2*
*Issues: 12 across 3 phases*
*Ready for review*
