"""QAContextBuilder for gathering QA testing context.

Implements spec section 7: QA Context Builder
- Parse spec/issue content to extract test requirements
- Discover API schemas (OpenAPI, type hints, docstrings)
- Analyze consumer code to find callers
- Extract git diff context for regression testing
- Build QAContext with all gathered information
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from swarm_attack.qa.models import (
    QAContext,
    QAEndpoint,
    QATrigger,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class EndpointDiscoveryError(Exception):
    """Raised when endpoint discovery fails and endpoints are required."""
    pass


class QAContextBuilder:
    """
    Builds QAContext by gathering information from various sources.

    Sources include:
    - Spec/issue content for test requirements
    - API schemas from OpenAPI, type hints, docstrings
    - Consumer code analysis to find callers
    - Git diff for regression context
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the QAContextBuilder.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger
        self.repo_root = Path(config.repo_root)

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "qa_context_builder"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def build_context(
        self,
        trigger: QATrigger,
        target: str,
        feature_id: Optional[str] = None,
        issue_number: Optional[int] = None,
        bug_id: Optional[str] = None,
        base_url: Optional[str] = None,
        explicit_endpoints: Optional[list[QAEndpoint]] = None,
    ) -> QAContext:
        """
        Build complete QA context from available sources.

        Args:
            trigger: What initiated this QA session.
            target: What to test (file path, endpoint, or description).
            feature_id: Optional feature identifier.
            issue_number: Optional issue number.
            bug_id: Optional bug identifier.
            base_url: Optional base URL for API requests.
            explicit_endpoints: Optional list of explicitly specified endpoints.

        Returns:
            QAContext with all gathered information.
        """
        self._log("build_context_start", {
            "trigger": trigger.value,
            "target": target,
            "feature_id": feature_id,
        })

        context = QAContext(
            feature_id=feature_id,
            issue_number=issue_number,
            bug_id=bug_id,
            base_url=base_url,
        )

        # Set target files
        target_path = Path(target)
        if target_path.is_absolute() and target_path.exists():
            context.target_files = [str(target_path)]
        elif (self.repo_root / target).exists():
            context.target_files = [str(self.repo_root / target)]

        # Use explicit endpoints if provided, otherwise discover
        if explicit_endpoints:
            context.target_endpoints = explicit_endpoints
        else:
            # Discover endpoints from target
            if context.target_files:
                context.target_endpoints = self.discover_endpoints(context.target_files[0])
            elif target.startswith("/"):
                # Target is an endpoint path
                context.target_endpoints = [QAEndpoint(method="GET", path=target)]

        # Load spec content for post-verification triggers
        if feature_id:
            context.spec_content = self._load_spec_content(feature_id)
            if issue_number:
                issue_content = self._load_issue_content(feature_id, issue_number)
                if issue_content:
                    if context.spec_content:
                        context.spec_content += f"\n\n## Issue #{issue_number}\n{issue_content}"
                    else:
                        context.spec_content = issue_content

        # Get git diff for pre-merge/regression triggers
        if trigger == QATrigger.PRE_MERGE:
            context.git_diff = self._get_git_diff()

        # Find related test files
        if context.target_files:
            context.related_tests = self._find_related_tests(context.target_files[0])

        self._log("build_context_complete", {
            "endpoints_found": len(context.target_endpoints),
            "files_found": len(context.target_files),
        })

        return context

    def discover_endpoints(self, target: str) -> list[QAEndpoint]:
        """
        Discover API endpoints from code/specs.

        Searches for endpoints in:
        1. OpenAPI/Swagger specs
        2. FastAPI/Flask route decorators
        3. Other common patterns

        Args:
            target: File path or description to search.

        Returns:
            List of discovered QAEndpoint objects.
        """
        endpoints: list[QAEndpoint] = []

        target_path = Path(target)
        if not target_path.exists():
            # Try relative to repo root
            target_path = self.repo_root / target
            if not target_path.exists():
                return endpoints

        # Check if it's an OpenAPI spec file
        if target_path.suffix in [".yaml", ".yml", ".json"]:
            endpoints.extend(self._discover_from_openapi(target_path))
        elif target_path.suffix == ".py":
            endpoints.extend(self._discover_from_python(target_path))
        elif target_path.suffix in [".ts", ".js"]:
            endpoints.extend(self._discover_from_typescript(target_path))

        return endpoints

    def discover_endpoints_required(self, target: str) -> list[QAEndpoint]:
        """
        Discover endpoints with error if none found.

        Args:
            target: File path to search.

        Returns:
            List of discovered endpoints.

        Raises:
            EndpointDiscoveryError: If no endpoints found.
        """
        endpoints = self.discover_endpoints(target)
        if not endpoints:
            raise EndpointDiscoveryError(
                f"No endpoints discovered from {target}. Either:\n"
                "1. Add openapi.yaml to your project\n"
                "2. Specify endpoints in config.yaml under qa.endpoints\n"
                "3. Check that API code follows standard patterns"
            )
        return endpoints

    def _discover_from_openapi(self, spec_path: Path) -> list[QAEndpoint]:
        """Discover endpoints from OpenAPI/Swagger spec."""
        endpoints: list[QAEndpoint] = []

        try:
            content = spec_path.read_text()

            if spec_path.suffix == ".json":
                spec = json.loads(content)
            else:
                # Simple YAML parsing for paths
                spec = self._parse_simple_yaml(content)

            paths = spec.get("paths", {})
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method in methods.keys():
                        if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                            endpoints.append(QAEndpoint(
                                method=method.upper(),
                                path=path,
                                auth_required=self._check_auth_in_openapi(methods.get(method, {})),
                            ))
        except Exception as e:
            self._log("openapi_parse_error", {"error": str(e)}, level="warning")

        return endpoints

    def _parse_simple_yaml(self, content: str) -> dict[str, Any]:
        """Simple YAML parser for OpenAPI specs."""
        result: dict[str, Any] = {"paths": {}}

        current_path = None
        lines = content.split('\n')

        for i, line in enumerate(lines):
            # Look for paths section
            if line.strip() == "paths:":
                # Parse paths
                indent_level = len(line) - len(line.lstrip())
                j = i + 1
                while j < len(lines):
                    path_line = lines[j]
                    if not path_line.strip() or path_line.strip().startswith('#'):
                        j += 1
                        continue

                    current_indent = len(path_line) - len(path_line.lstrip())
                    if current_indent <= indent_level and path_line.strip():
                        break

                    # Check if it's a path definition (starts with /)
                    stripped = path_line.strip()
                    if stripped.startswith('/') or stripped.startswith("'/") or stripped.startswith('"/'):
                        # Extract path
                        path_match = re.match(r"['\"]?(/[^'\":]+)['\"]?:", stripped)
                        if path_match:
                            current_path = path_match.group(1)
                            result["paths"][current_path] = {}
                    elif current_path and stripped.rstrip(':') in ["get", "post", "put", "delete", "patch"]:
                        method = stripped.rstrip(':')
                        result["paths"][current_path][method] = {}

                    j += 1

        return result

    def _check_auth_in_openapi(self, method_spec: dict[str, Any]) -> bool:
        """Check if OpenAPI method spec requires authentication."""
        if "security" in method_spec:
            return len(method_spec["security"]) > 0
        return False

    def _discover_from_python(self, file_path: Path) -> list[QAEndpoint]:
        """Discover endpoints from Python file (FastAPI, Flask, etc.)."""
        endpoints: list[QAEndpoint] = []

        try:
            content = file_path.read_text()

            # FastAPI patterns
            # @router.get("/path") or @app.get("/path")
            fastapi_patterns = [
                (r'@(?:router|app)\.get\s*\(\s*["\']([^"\']+)["\']', "GET"),
                (r'@(?:router|app)\.post\s*\(\s*["\']([^"\']+)["\']', "POST"),
                (r'@(?:router|app)\.put\s*\(\s*["\']([^"\']+)["\']', "PUT"),
                (r'@(?:router|app)\.delete\s*\(\s*["\']([^"\']+)["\']', "DELETE"),
                (r'@(?:router|app)\.patch\s*\(\s*["\']([^"\']+)["\']', "PATCH"),
            ]

            for pattern, method in fastapi_patterns:
                for match in re.finditer(pattern, content):
                    path = match.group(1)
                    # Check if auth is required (look for Depends in the line)
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_end = content.find('\n', match.end())
                    line = content[line_start:line_end if line_end > 0 else len(content)]
                    auth_required = "Depends" in line or "get_current_user" in line

                    endpoints.append(QAEndpoint(
                        method=method,
                        path=path,
                        auth_required=auth_required,
                    ))

            # Flask patterns
            # @app.route("/path", methods=["GET"])
            flask_pattern = r'@(?:app|blueprint)\.route\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?'
            for match in re.finditer(flask_pattern, content, re.DOTALL):
                path = match.group(1)
                methods_str = match.group(2)

                if methods_str:
                    methods = re.findall(r'["\'](\w+)["\']', methods_str)
                else:
                    methods = ["GET"]

                for method in methods:
                    endpoints.append(QAEndpoint(
                        method=method.upper(),
                        path=path,
                    ))

        except Exception as e:
            self._log("python_parse_error", {"error": str(e)}, level="warning")

        return endpoints

    def _discover_from_typescript(self, file_path: Path) -> list[QAEndpoint]:
        """Discover endpoints from TypeScript/JavaScript file."""
        endpoints: list[QAEndpoint] = []

        try:
            content = file_path.read_text()

            # Express patterns
            # app.get('/path', handler)
            express_patterns = [
                (r'\.get\s*\(\s*["\']([^"\']+)["\']', "GET"),
                (r'\.post\s*\(\s*["\']([^"\']+)["\']', "POST"),
                (r'\.put\s*\(\s*["\']([^"\']+)["\']', "PUT"),
                (r'\.delete\s*\(\s*["\']([^"\']+)["\']', "DELETE"),
            ]

            for pattern, method in express_patterns:
                for match in re.finditer(pattern, content):
                    path = match.group(1)
                    if path.startswith('/'):
                        endpoints.append(QAEndpoint(
                            method=method,
                            path=path,
                        ))

        except Exception as e:
            self._log("typescript_parse_error", {"error": str(e)}, level="warning")

        return endpoints

    def extract_schemas(self, endpoints: list[QAEndpoint]) -> dict[str, Any]:
        """
        Extract response schemas for endpoints.

        Searches for schemas in:
        1. OpenAPI spec components
        2. Pydantic model definitions
        3. TypedDict definitions

        Args:
            endpoints: List of endpoints to find schemas for.

        Returns:
            Dictionary mapping endpoint paths to their schemas.
        """
        schemas: dict[str, Any] = {}

        # Search for OpenAPI spec
        openapi_paths = list(self.repo_root.glob("**/openapi.yaml")) + \
                       list(self.repo_root.glob("**/openapi.json")) + \
                       list(self.repo_root.glob("**/swagger.yaml")) + \
                       list(self.repo_root.glob("**/swagger.json"))

        for spec_path in openapi_paths[:1]:  # Use first found
            try:
                content = spec_path.read_text()
                if spec_path.suffix == ".json":
                    spec = json.loads(content)
                else:
                    spec = self._parse_simple_yaml(content)

                # Extract schemas from components
                if "components" in spec and "schemas" in spec.get("components", {}):
                    schemas["_components"] = spec["components"]["schemas"]

            except Exception:
                pass

        return schemas

    def find_consumers(self, endpoints: list[QAEndpoint]) -> dict[str, list[str]]:
        """
        Find code that calls each endpoint.

        Searches for:
        1. Frontend fetch/axios calls
        2. Other service HTTP calls
        3. Integration tests

        Args:
            endpoints: List of endpoints to find consumers for.

        Returns:
            Dictionary mapping endpoint paths to list of consumer file paths.
        """
        consumers: dict[str, list[str]] = {}

        for endpoint in endpoints:
            consumers[endpoint.path] = []

        # Search patterns
        search_patterns = [
            # JavaScript/TypeScript fetch
            r'fetch\s*\(\s*["\'][^"\']*({path})',
            # Axios
            r'axios\.(get|post|put|delete)\s*\(\s*["\'][^"\']*({path})',
            # Python requests
            r'requests\.(get|post|put|delete)\s*\([^)]*({path})',
            # httpx
            r'client\.(get|post|put|delete)\s*\([^)]*({path})',
        ]

        # Search in common directories
        search_dirs = [
            self.repo_root / "frontend",
            self.repo_root / "src",
            self.repo_root / "clients",
            self.repo_root / "tests",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for ext in ["*.ts", "*.tsx", "*.js", "*.jsx", "*.py"]:
                for file_path in search_dir.rglob(ext):
                    try:
                        content = file_path.read_text()

                        for endpoint in endpoints:
                            # Escape special regex chars in path
                            escaped_path = re.escape(endpoint.path)
                            # Allow for path parameters
                            pattern_path = escaped_path.replace(r'\{', r'[^/]*').replace(r'\}', '')

                            for pattern in search_patterns:
                                full_pattern = pattern.format(path=pattern_path)
                                if re.search(full_pattern, content):
                                    consumers[endpoint.path].append(str(file_path))
                                    break

                            # Also check for literal path in file
                            if endpoint.path in content:
                                if str(file_path) not in consumers[endpoint.path]:
                                    consumers[endpoint.path].append(str(file_path))

                    except Exception:
                        pass

        return consumers

    def _get_git_diff(self) -> Optional[str]:
        """
        Get git diff for current changes.

        Returns:
            Git diff as string, or None if not in git repo.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Try just uncommitted changes
                result = subprocess.run(
                    ["git", "diff"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if result.returncode != 0:
                return None

            return result.stdout if result.stdout else None

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        except Exception:
            return None

    def _load_spec_content(self, feature_id: str) -> Optional[str]:
        """
        Load spec content for a feature.

        Tries in order:
        1. specs/{feature_id}/spec-final.md
        2. specs/{feature_id}/spec-draft.md

        Args:
            feature_id: Feature identifier.

        Returns:
            Spec content as string, or None if not found.
        """
        spec_dir = self.repo_root / "specs" / feature_id

        # Try spec-final first
        spec_final = spec_dir / "spec-final.md"
        if spec_final.exists():
            return spec_final.read_text()

        # Fall back to spec-draft
        spec_draft = spec_dir / "spec-draft.md"
        if spec_draft.exists():
            return spec_draft.read_text()

        return None

    def _load_issue_content(
        self, feature_id: str, issue_number: int
    ) -> Optional[str]:
        """
        Load issue content from issues.json.

        Args:
            feature_id: Feature identifier.
            issue_number: Issue number to find.

        Returns:
            Issue content as string, or None if not found.
        """
        issues_file = self.repo_root / "specs" / feature_id / "issues.json"

        if not issues_file.exists():
            return None

        try:
            issues = json.loads(issues_file.read_text())

            for issue in issues:
                if issue.get("number") == issue_number:
                    title = issue.get("title", "")
                    body = issue.get("body", "")
                    return f"**{title}**\n\n{body}"

            return None

        except Exception:
            return None

    def _find_related_tests(self, source_file: str) -> list[str]:
        """
        Find test files related to source file.

        Args:
            source_file: Path to source file.

        Returns:
            List of related test file paths.
        """
        related: list[str] = []
        source_path = Path(source_file)

        if not source_path.exists():
            return related

        # Get the base name without extension
        base_name = source_path.stem

        # Search for test files
        test_patterns = [
            f"**/test_{base_name}.py",
            f"**/{base_name}_test.py",
            f"**/tests/**/test_{base_name}.py",
        ]

        for pattern in test_patterns:
            for test_file in self.repo_root.glob(pattern):
                related.append(str(test_file))

        return related
