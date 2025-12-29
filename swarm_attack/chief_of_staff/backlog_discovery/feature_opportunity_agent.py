"""FeatureOpportunityAgent for McKinsey-style strategic feature analysis.

This module provides:
- FeatureOpportunityAgent: Discovers high-ROI feature opportunities via LLM analysis
- Analyzes codebase capabilities
- Identifies strategic features with business cases
- Calculates ROI scores using Impact, Effort, Leverage, Risk
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    ActionabilityScore,
    Evidence,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class FeatureOpportunityAgent(BaseAgent):
    """Discovers high-ROI feature opportunities via McKinsey-style analysis.

    Uses LLM to analyze:
    1. Codebase capabilities (what exists)
    2. Industry patterns (what competitors have)
    3. User value gaps (what's missing)
    4. Implementation leverage (what's easy to build)

    Cost: ~$0.50 per analysis (uses Claude for strategic thinking)

    Attributes:
        name: Agent identifier for logs and checkpoints.
        backlog_store: Store for persisting discovered opportunities.
    """

    name: str = "feature-opportunity-discovery"

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: Optional[BacklogStore] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FeatureOpportunityAgent.

        Args:
            config: SwarmConfig with paths and settings.
            backlog_store: Optional BacklogStore for persistence.
            **kwargs: Additional arguments passed to BaseAgent.
        """
        super().__init__(config=config, **kwargs)
        self.backlog_store = backlog_store

    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute feature opportunity discovery.

        Performs strategic analysis:
        1. Codebase Audit - features, infrastructure, patterns
        2. Market Opportunity Analysis - industry trends, competitors
        3. ROI Scoring - impact, effort, leverage, risk
        4. Prioritized Recommendations - with business cases

        Args:
            context: Context dict with optional keys:
                - budget_usd: Cost budget for LLM calls (default 0.50)
                - max_opportunities: Limit on opportunities (default 5)

        Returns:
            AgentResult with list of FEATURE_OPPORTUNITY opportunities
        """
        budget_usd = context.get("budget_usd", 0.50)
        max_opportunities = context.get("max_opportunities", 5)

        # Check budget before LLM call
        estimated_cost = 0.25  # Estimated cost per analysis
        if budget_usd < estimated_cost:
            self._log("budget_insufficient", {"budget": budget_usd})
            return AgentResult.success_result(
                output={"opportunities": []},
                cost_usd=0.0,
            )

        # 1. Analyze codebase
        codebase_analysis = self._analyze_codebase()

        # 2. Build and send analysis prompt to LLM
        prompt = self._build_analysis_prompt(codebase_analysis)
        llm_response = self._call_llm(prompt)

        # 3. Parse opportunities from response
        opportunities = self._parse_opportunities(llm_response)

        # Limit results
        opportunities = opportunities[:max_opportunities]

        # Save to store
        if self.backlog_store:
            for opp in opportunities:
                self.backlog_store.save_opportunity(opp)

        self._log("discovery_complete", {
            "opportunities_created": len(opportunities),
        })

        return AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=estimated_cost if opportunities else 0.0,
        )

    def _get_project_root(self) -> Path:
        """Get project root path."""
        return Path.cwd()

    def _analyze_codebase(self) -> dict[str, Any]:
        """Scan codebase to understand capabilities.

        Returns:
            Dict with languages, frameworks, features, apis, data_models.
        """
        return {
            "languages": self._detect_languages(),
            "frameworks": self._detect_frameworks(),
            "features": self._detect_existing_features(),
            "apis": self._detect_api_patterns(),
            "data_models": self._detect_data_models(),
        }

    def _detect_languages(self) -> list[str]:
        """Detect programming languages used in the project.

        Returns:
            List of detected language names.
        """
        root = self._get_project_root()
        languages = set()

        # Check for common file extensions
        extension_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
        }

        try:
            for ext, lang in extension_map.items():
                if list(root.glob(f"**/*{ext}"))[:1]:  # Check if any exist
                    languages.add(lang)
        except Exception:
            pass

        return list(languages)

    def _detect_frameworks(self) -> list[str]:
        """Detect frameworks from imports/dependencies.

        Returns:
            List of detected framework names.
        """
        root = self._get_project_root()
        frameworks = set()

        # Check requirements.txt
        try:
            req_file = root / "requirements.txt"
            if req_file.exists():
                content = req_file.read_text().lower()
                framework_map = {
                    "flask": "flask",
                    "django": "django",
                    "fastapi": "fastapi",
                    "typer": "typer",
                    "click": "click",
                    "pytest": "pytest",
                    "react": "react",
                }
                for keyword, framework in framework_map.items():
                    if keyword in content:
                        frameworks.add(framework)
        except Exception:
            pass

        # Check package.json
        try:
            pkg_file = root / "package.json"
            if pkg_file.exists():
                content = pkg_file.read_text().lower()
                if "react" in content:
                    frameworks.add("react")
                if "vue" in content:
                    frameworks.add("vue")
                if "next" in content:
                    frameworks.add("nextjs")
        except Exception:
            pass

        return list(frameworks)

    def _detect_existing_features(self) -> list[str]:
        """Detect existing features from directory structure.

        Returns:
            List of detected feature names.
        """
        root = self._get_project_root()
        features = []

        # Look for common feature directories
        try:
            for dir_name in ["features", "modules", "components", "services", "api"]:
                feature_dir = root / dir_name
                if feature_dir.exists() and feature_dir.is_dir():
                    for item in feature_dir.iterdir():
                        if item.is_dir():
                            features.append(item.name)
        except Exception:
            pass

        return features[:10]  # Limit

    def _detect_api_patterns(self) -> list[str]:
        """Detect API patterns from code.

        Returns:
            List of detected API patterns.
        """
        patterns = []

        try:
            root = self._get_project_root()

            # Check for REST patterns
            for py_file in list(root.glob("**/*.py"))[:20]:
                try:
                    content = py_file.read_text()
                    if "@app.route" in content or "@router" in content:
                        patterns.append("rest_api")
                        break
                except Exception:
                    continue

            # Check for GraphQL
            if list(root.glob("**/schema.graphql"))[:1]:
                patterns.append("graphql")

        except Exception:
            pass

        return list(set(patterns))

    def _detect_data_models(self) -> list[str]:
        """Detect data models from code.

        Returns:
            List of detected model names.
        """
        models = []

        try:
            root = self._get_project_root()

            # Look for model definitions
            for py_file in list(root.glob("**/models*.py"))[:5]:
                try:
                    content = py_file.read_text()
                    # Look for class definitions
                    import re
                    class_matches = re.findall(r"class\s+(\w+)", content)
                    models.extend(class_matches[:5])
                except Exception:
                    continue
        except Exception:
            pass

        return models[:10]

    def _build_analysis_prompt(self, codebase_analysis: dict[str, Any]) -> str:
        """Build McKinsey-style analysis prompt.

        Args:
            codebase_analysis: Results from codebase analysis.

        Returns:
            Prompt string for LLM.
        """
        return f"""
You are a McKinsey Senior Partner analyzing a software product for strategic opportunities.

## Codebase Analysis
{json.dumps(codebase_analysis, indent=2)}

## Your Task

Perform a rigorous strategic analysis:

### 1. Market Positioning
- What type of product is this?
- Who are the users?
- What problem does it solve?

### 2. Competitive Landscape
- What do competitors in this space typically offer?
- What features are table stakes?
- What would differentiate this product?

### 3. Opportunity Identification
For each opportunity, provide:
- **Feature**: Clear, specific feature description
- **User Value**: What problem it solves for users
- **Business Case**: Why it matters strategically
- **ROI Score**: Impact (1-10) x (10 - Effort) / Risk
- **Implementation Leverage**: What existing code can be reused?
- **Time to Value**: Days to MVP

### 4. Prioritization Matrix
Rank opportunities by:
- Quick Wins: High ROI, Low Effort
- Strategic Bets: High ROI, High Effort
- Low Hanging Fruit: Medium ROI, Very Low Effort
- Backburner: Everything else

Output as JSON:
{{
  "product_type": "...",
  "target_users": ["..."],
  "opportunities": [
    {{
      "title": "...",
      "description": "...",
      "user_value": "...",
      "business_case": "...",
      "impact": 8,
      "effort": 3,
      "leverage": 9,
      "risk": 2,
      "roi_score": 24.0,
      "category": "quick_win",
      "time_to_value_days": 5,
      "existing_code_to_leverage": ["path/to/file.py"]
    }}
  ]
}}
"""

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with the analysis prompt.

        Args:
            prompt: The prompt to send.

        Returns:
            LLM response string.
        """
        # This would be the actual LLM call in production
        # For now, return empty to be mocked in tests
        try:
            # Try to use the parent's LLM calling mechanism if available
            if hasattr(super(), "_call_claude"):
                return super()._call_claude(prompt)  # type: ignore
        except Exception:
            pass

        return ""

    def _parse_opportunities(self, response: str) -> list[Opportunity]:
        """Convert LLM response to Opportunity objects.

        Args:
            response: JSON response from LLM.

        Returns:
            List of Opportunity objects.
        """
        if not response:
            return []

        try:
            # Try to extract JSON from response
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            self._log("parse_error", {"response": response[:100]}, level="warning")
            return []

        opportunities = []
        opp_list = data.get("opportunities", [])

        for idx, opp_data in enumerate(opp_list):
            try:
                opp = self._create_opportunity_from_data(opp_data, idx)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                self._log("opportunity_parse_error", {"error": str(e)}, level="warning")
                continue

        return opportunities

    def _create_opportunity_from_data(
        self, opp_data: dict[str, Any], idx: int
    ) -> Optional[Opportunity]:
        """Create an Opportunity from parsed data.

        Args:
            opp_data: Dictionary with opportunity fields.
            idx: Index for priority ranking.

        Returns:
            Opportunity object or None if invalid.
        """
        title = opp_data.get("title", "")
        if not title:
            return None

        opp_id = self._generate_id(opp_data)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        description = opp_data.get("description", "")
        user_value = opp_data.get("user_value", "")
        business_case = opp_data.get("business_case", "")
        category = opp_data.get("category", "unknown")

        # Build evidence
        evidence = [
            Evidence(
                source="mckinsey_analysis",
                content=f"[{category}] {business_case}",
                timestamp=now,
            ),
        ]

        if user_value:
            evidence.append(
                Evidence(
                    source="user_value",
                    content=user_value,
                    timestamp=now,
                )
            )

        # Calculate actionability from scores
        actionability = self._calculate_actionability_from_opp(opp_data)

        # Get affected files for leverage
        affected_files = opp_data.get("existing_code_to_leverage", [])

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.FEATURE_OPPORTUNITY,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            suggested_fix=None,  # Feature specs come later
            affected_files=affected_files,
            priority_rank=idx + 1,
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _calculate_actionability_from_opp(
        self, opp_data: dict[str, Any]
    ) -> ActionabilityScore:
        """Calculate actionability from opportunity data.

        Args:
            opp_data: Dictionary with impact, effort, leverage, risk.

        Returns:
            ActionabilityScore based on the data.
        """
        leverage = opp_data.get("leverage", 5)
        effort = opp_data.get("effort", 5)

        # Clarity from leverage (how much we can reuse)
        clarity = min(leverage / 10, 1.0)

        # Evidence is moderate for strategic analysis
        evidence_score = 0.7

        # Effort mapping
        if effort <= 3:
            effort_str = "small"
        elif effort <= 6:
            effort_str = "medium"
        else:
            effort_str = "large"

        # New features are fully reversible (additive)
        reversibility = "full"

        return ActionabilityScore(
            clarity=clarity,
            evidence=evidence_score,
            effort=effort_str,
            reversibility=reversibility,
        )

    def _calculate_roi(
        self, impact: float, effort: float, risk: float
    ) -> float:
        """Calculate ROI score.

        Formula: Impact x (10 - Effort) / Risk

        Args:
            impact: Impact score (1-10).
            effort: Effort score (1-10).
            risk: Risk score (1-10).

        Returns:
            ROI score.
        """
        # Avoid division by zero
        if risk <= 0:
            risk = 1

        return impact * (10 - effort) / risk

    def _generate_id(self, opp_data: dict[str, Any]) -> str:
        """Generate a unique opportunity ID.

        Args:
            opp_data: Opportunity data for hashing.

        Returns:
            Unique opportunity ID string.
        """
        content = f"{opp_data.get('title', '')}-{opp_data.get('description', '')}"
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"opp-fo-{timestamp}-{hash_suffix}"
