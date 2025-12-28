"""RegressionScannerAgent for regression test prioritization.

Implements spec sections 4.3, 10.9:
- Git diff analysis to find affected files
- Mapping file changes to affected endpoints
- Priority scoring based on change impact
- Regression suite selection based on priorities
- Git edge cases (dirty worktree, detached HEAD, shallow clone, etc.)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.qa.models import QAEndpoint, QALimits

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.qa.models import QAContext


class GitEdgeCaseError(Exception):
    """Raised when git operations fail due to edge cases."""
    pass


@dataclass
class ImpactMap:
    """Maps changed files to affected endpoints."""
    endpoint_impacts: dict[str, dict[str, Any]] = field(default_factory=dict)


class RegressionScannerAgent(BaseAgent):
    """
    Agent that analyzes code changes and prioritizes regression tests.

    Analyzes git diffs to determine which endpoints are most affected
    by changes and should be prioritized for testing.
    """

    name: str = "regression_scanner"

    # Priority thresholds (Section 4.3)
    must_test_threshold: int = 80
    should_test_threshold: int = 50

    # Priority scores by change type (Section 4.3)
    PRIORITY_SCORES = {
        "direct_handler": 100,
        "model": 80,
        "service": 60,
        "utility": 40,
        "config": 30,
    }

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        limits: Optional[QALimits] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the RegressionScannerAgent."""
        super().__init__(config, logger, **kwargs)
        self.limits = limits or QALimits()

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute regression analysis on code changes.

        Args:
            context: Dictionary containing:
                - git_diff: Optional git diff string
                - endpoints: List of QAEndpoint to analyze
                - depth: Optional QADepth level

        Returns:
            AgentResult with regression analysis results.
        """
        endpoints = context.get("endpoints", [])

        self._log("regression_analysis_start", {
            "endpoint_count": len(endpoints),
        })

        try:
            # Analyze git diff to find changed files
            changed_files = self.analyze_diff(context)

            # Map changes to affected endpoints
            impact_map = self.map_changes_to_endpoints(changed_files, endpoints)

            # Prioritize endpoints based on impact
            priorities = self.prioritize_endpoints(impact_map)

            # Select regression test suite
            regression_suite = self.select_regression_suite(priorities)

            output = {
                "agent": "regression_scanner",
                "files_analyzed": len(changed_files),
                "endpoints_affected": len(impact_map),
                "impact_map": impact_map,
                "regression_suite": regression_suite,
            }

            return AgentResult.success_result(output=output)

        except GitEdgeCaseError as e:
            return AgentResult.failure_result(str(e))
        except Exception as e:
            return AgentResult.failure_result(f"Regression analysis failed: {e}")

    def analyze_diff(self, context: dict[str, Any]) -> list[str]:
        """
        Analyze git diff and return list of changed files.

        Args:
            context: QAContext or dict with git_diff info.

        Returns:
            List of changed file paths.

        Raises:
            GitEdgeCaseError: When git operations fail.
        """
        # Get changed files from diff and status
        changed_files = set()

        # Track if we encountered fatal errors
        git_available = True

        # Run git diff to find changed files
        try:
            diff_output = self._run_git_command("git diff --name-only HEAD")
            if diff_output:
                for line in diff_output.strip().split('\n'):
                    if line and not self._is_test_file(line):
                        changed_files.add(line)
        except FileNotFoundError as e:
            raise GitEdgeCaseError("git command not found. Please install git.")
        except Exception as e:
            error_msg = str(e).lower()
            if "not a git repository" in error_msg:
                raise GitEdgeCaseError("Not a git repository. Initialize git or skip regression analysis.")
            # For other errors, try to continue with status
            git_available = False

        # Check git status for uncommitted files (including untracked)
        # Only if we haven't found any files yet or to catch new untracked files
        if git_available:
            try:
                status_output = self._run_git_command("git status --porcelain")
                if status_output:
                    for line in status_output.strip().split('\n'):
                        if not line:
                            continue
                        # Parse porcelain format: "XY filename"
                        # Status format is "XY filename" where X and Y are status codes
                        if len(line) > 3 and line[2] == ' ':
                            filename = line[3:].strip()
                            if filename and not self._is_test_file(filename):
                                changed_files.add(filename)
            except FileNotFoundError as e:
                raise GitEdgeCaseError("git command not found. Please install git.")
            except Exception as e:
                error_msg = str(e).lower()
                if "not a git repository" in error_msg:
                    raise GitEdgeCaseError("Not a git repository. Initialize git or skip regression analysis.")
                # If status fails, we'll use what we got from diff
                pass

        return sorted(changed_files)

    def _run_git_command(self, cmd: str) -> str:
        """
        Run a git command and return output.

        Args:
            cmd: Git command to run.

        Returns:
            Command output as string.

        Raises:
            Exception: When command fails.
        """
        try:
            result = subprocess.run(
                cmd.split(),
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check for detached HEAD
            if "rev-parse --abbrev-ref HEAD" in cmd and result.stdout.strip() == "HEAD":
                # Detached HEAD - use commit hash instead
                commit_hash = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.config.repo_root,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                return commit_hash

            # Handle missing main/master branch
            if ("main" in cmd or "master" in cmd) and result.returncode != 0:
                # Try alternative comparison strategy
                return self._fallback_diff_strategy()

            if result.returncode != 0:
                raise Exception(result.stderr)

            return result.stdout

        except subprocess.TimeoutExpired:
            raise GitEdgeCaseError("Git command timed out")

    def _check_git_status(self) -> dict[str, Any]:
        """
        Check git status for uncommitted changes.

        Returns:
            Dict with dirty flag and uncommitted files.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {"dirty": False, "uncommitted_files": []}

            uncommitted = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                # Parse porcelain format: "XY filename"
                if len(line) > 3:
                    status = line[:2]
                    filename = line[3:]
                    if status.startswith('??'):
                        # Untracked file
                        uncommitted.append(filename)
                    elif status.strip():
                        # Modified, added, deleted, etc.
                        uncommitted.append(filename)

            return {
                "dirty": len(uncommitted) > 0,
                "uncommitted_files": uncommitted,
            }

        except Exception:
            return {"dirty": False, "uncommitted_files": []}

    def _is_shallow_clone(self) -> bool:
        """
        Check if the repository is a shallow clone.

        Returns:
            True if shallow clone, False otherwise.
        """
        shallow_file = Path(self.config.repo_root) / ".git" / "shallow"
        return shallow_file.exists()

    def _fallback_diff_strategy(self) -> str:
        """
        Fallback strategy when main/master branch doesn't exist.

        Returns:
            List of changed files using alternative strategy.
        """
        # Try HEAD~1 comparison for shallow clones
        if self._is_shallow_clone():
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1"],
                    cwd=self.config.repo_root,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception:
                pass

        # Fall back to uncommitted changes only
        return ""

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        return (
            "test_" in file_path or
            "_test" in file_path or
            "/tests/" in file_path or
            "/test/" in file_path or
            ".test." in file_path or
            ".spec." in file_path
        )

    def map_changes_to_endpoints(
        self,
        changed_files: list[str],
        endpoints: list[QAEndpoint],
    ) -> dict[str, dict[str, Any]]:
        """
        Map changed files to affected endpoints.

        Args:
            changed_files: List of changed file paths.
            endpoints: List of endpoints to check.

        Returns:
            Dictionary mapping endpoint paths to impact info.
        """
        impact_map = {}

        for file_path in changed_files:
            # Determine change type
            change_type = self._determine_change_type(file_path)

            # Find affected endpoints
            affected = []

            if self._is_endpoint_handler(file_path):
                # Direct handler changes
                endpoint_path = self._find_endpoint_for_file(file_path)
                if endpoint_path:
                    affected.append(endpoint_path)

            elif self._is_model_file(file_path):
                # Model changes - find endpoints that use this model
                affected = self._find_endpoints_using_model(file_path)

            elif self._is_service_file(file_path):
                # Service changes - find endpoints that call this service
                affected = self._find_endpoints_using_service(file_path)

            elif self._is_utility_file(file_path):
                # Utility changes - find endpoints that use utilities
                affected = self._find_endpoints_using_utility(file_path)

            elif self._is_config_file(file_path):
                # Config changes - might affect all endpoints
                affected = self._find_endpoints_affected_by_config(file_path)

            # Add to impact map
            for endpoint in affected:
                if endpoint not in impact_map:
                    impact_map[endpoint] = {
                        "files": [],
                        "change_type": change_type,
                    }
                impact_map[endpoint]["files"].append(file_path)

        return impact_map

    def _determine_change_type(self, file_path: str) -> str:
        """Determine the type of change based on file path."""
        if self._is_endpoint_handler(file_path):
            return "direct_handler"
        elif self._is_model_file(file_path):
            return "model"
        elif self._is_service_file(file_path):
            return "service"
        elif self._is_utility_file(file_path):
            return "utility"
        elif self._is_config_file(file_path):
            return "config"
        return "unknown"

    def _is_endpoint_handler(self, file_path: str) -> bool:
        """Check if file is an endpoint handler."""
        return any(pattern in file_path for pattern in ["/api/", "/routes/", "/handlers/"])

    def _is_model_file(self, file_path: str) -> bool:
        """Check if file is a model file."""
        return "/models/" in file_path or "/db/models/" in file_path

    def _is_service_file(self, file_path: str) -> bool:
        """Check if file is a service layer file."""
        return "/services/" in file_path or "/business/" in file_path

    def _is_utility_file(self, file_path: str) -> bool:
        """Check if file is a utility/helper file."""
        return any(pattern in file_path for pattern in ["/utils/", "/helpers/", "/lib/"])

    def _is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file."""
        return (
            file_path.startswith("config/") or
            file_path.endswith("config.json") or
            file_path.endswith(".env") or
            file_path.endswith(".yml") or
            file_path.endswith(".yaml")
        )

    def _find_endpoint_for_file(self, file_path: str) -> Optional[str]:
        """Find the endpoint path for a handler file."""
        # Simple heuristic: extract from file name
        # e.g., src/api/users.py -> /api/users
        match = re.search(r'/api/(\w+)', file_path)
        if match:
            return f"/api/{match.group(1)}"
        return None

    def _find_endpoints_using_model(self, model_file: str) -> list[str]:
        """Find endpoints that use a specific model."""
        endpoints = []

        # Extract model name from file path
        model_name = Path(model_file).stem

        # Search for files that import this model
        try:
            repo_root = Path(self.config.repo_root)
            endpoint_files = self._find_all_endpoint_files()

            for endpoint_file in endpoint_files:
                try:
                    content = self._read_file(endpoint_file)
                    imports = self._extract_imports(content)

                    # Check if this file imports the model
                    if any(model_name in imp for imp in imports):
                        endpoint_path = self._find_endpoint_for_file(endpoint_file)
                        if endpoint_path:
                            endpoints.append(endpoint_path)
                except Exception:
                    continue

        except Exception:
            pass

        return endpoints

    def _find_endpoints_using_service(self, service_file: str) -> list[str]:
        """Find endpoints that use a specific service."""
        # Similar to model finding
        return self._find_endpoints_using_model(service_file)

    def _find_endpoints_using_utility(self, utility_file: str) -> list[str]:
        """Find endpoints that use a specific utility."""
        # Track visited files to avoid circular dependencies
        visited = set()
        return self._find_endpoints_using_utility_recursive(utility_file, visited)

    def _find_endpoints_using_utility_recursive(
        self,
        utility_file: str,
        visited: set[str],
        max_depth: int = 3,
    ) -> list[str]:
        """Recursively find endpoints using a utility, avoiding cycles."""
        if utility_file in visited or len(visited) > max_depth * 10:
            return []

        visited.add(utility_file)
        endpoints = []

        try:
            # Find files that import this utility
            endpoint_files = self._find_all_endpoint_files()

            for endpoint_file in endpoint_files[:20]:  # Limit search
                try:
                    content = self._read_file(endpoint_file)
                    imports = self._extract_imports(content)

                    utility_name = Path(utility_file).stem
                    if any(utility_name in imp for imp in imports):
                        endpoint_path = self._find_endpoint_for_file(endpoint_file)
                        if endpoint_path:
                            endpoints.append(endpoint_path)
                except Exception:
                    continue

        except Exception:
            pass

        return endpoints

    def _find_endpoints_affected_by_config(self, config_file: str) -> list[str]:
        """Find endpoints affected by config changes."""
        # Config changes might affect all database-backed endpoints
        # For now, return empty list (conservative approach)
        return []

    def _find_all_endpoint_files(self) -> list[str]:
        """Find all endpoint/handler files in the codebase."""
        endpoint_files = []
        repo_root = Path(self.config.repo_root)

        for pattern in ["**/api/**/*.py", "**/routes/**/*.py", "**/handlers/**/*.py"]:
            for file_path in repo_root.glob(pattern):
                if not self._is_test_file(str(file_path)):
                    endpoint_files.append(str(file_path))

        return endpoint_files

    def _read_file(self, file_path: str) -> str:
        """Read file content."""
        return Path(file_path).read_text(errors='ignore')

    def _extract_imports(self, code: str) -> list[str]:
        """Extract import statements from code."""
        imports = []

        # Python imports
        for match in re.finditer(r'^(?:from|import)\s+([\w.]+)', code, re.MULTILINE):
            imports.append(match.group(1))

        # Also capture "from x import Y"
        for match in re.finditer(r'from\s+([\w.]+)\s+import\s+([\w,\s]+)', code, re.MULTILINE):
            module = match.group(1)
            names = match.group(2)
            imports.append(module)
            for name in names.split(','):
                imports.append(name.strip())

        return imports

    def prioritize_endpoints(self, impact_map: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """
        Prioritize endpoints based on impact scores.

        Args:
            impact_map: Map of endpoints to impact info.

        Returns:
            Dictionary with prioritized endpoints (sorted by priority).
        """
        priorities = {}

        for endpoint, impact_info in impact_map.items():
            change_type = impact_info.get("change_type", "unknown")
            files = impact_info.get("files", [])

            # Determine highest priority change type for this endpoint
            max_priority = 0
            final_type = change_type

            for file_path in files:
                file_change_type = self._determine_change_type(file_path)
                file_priority = self.PRIORITY_SCORES.get(file_change_type, 0)
                if file_priority > max_priority:
                    max_priority = file_priority
                    final_type = file_change_type

            # If no priority determined from files, use the original change_type
            if max_priority == 0:
                max_priority = self.PRIORITY_SCORES.get(change_type, 0)

            priorities[endpoint] = {
                "priority": max_priority,
                "reason": final_type,
            }

        # Sort by priority (highest first)
        sorted_priorities = dict(
            sorted(priorities.items(), key=lambda x: x[1]["priority"], reverse=True)
        )

        return sorted_priorities

    def select_regression_suite(self, priorities: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
        """
        Select regression test suite based on priorities.

        Args:
            priorities: Prioritized endpoints.

        Returns:
            Dictionary with must_test, should_test, and may_skip lists.
        """
        must_test = []
        should_test = []
        may_skip = []

        total_selected = 0
        max_endpoints = self.limits.max_endpoints_standard

        for endpoint, info in priorities.items():
            if total_selected >= max_endpoints:
                break

            priority = info["priority"]

            if priority >= self.must_test_threshold:
                must_test.append(endpoint)
                total_selected += 1
            elif priority >= self.should_test_threshold:
                should_test.append(endpoint)
                total_selected += 1
            else:
                may_skip.append(endpoint)

        return {
            "must_test": must_test,
            "should_test": should_test,
            "may_skip": may_skip,
        }
