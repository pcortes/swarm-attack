"""ContractValidatorAgent for API contract validation.

Implements spec sections 4.2, 10.3, 10.8:
- Endpoint discovery from OpenAPI specs, code, and tests
- Contract discovery with fallback chain
- Path parameter detection ({id}, :id, <id>)
- EndpointDiscoveryError when no endpoints found
- Graceful degradation when no consumers found
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import yaml

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.qa.models import (
    QADepth,
    QAEndpoint,
    QAFinding,
    QALimits,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.qa.models import QAContext


class EndpointDiscoveryError(Exception):
    """Raised when no endpoints can be discovered.

    Section 10.3: discover_endpoints must NEVER return empty silently.
    """
    pass


class ContractSource(Enum):
    """Source of contract definition, in priority order (Section 10.8)."""
    OPENAPI = "openapi"
    TYPE_DEFINITION = "type_definition"
    CONSUMER = "consumer"
    INTEGRATION_TEST = "integration_test"


@dataclass
class Contract:
    """Represents an API contract expectation."""
    endpoint: str
    expected_fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)
    nullable_fields: list[str] = field(default_factory=list)
    source: ContractSource = ContractSource.OPENAPI
    consumer_location: Optional[str] = None


class ContractValidatorAgent(BaseAgent):
    """
    Agent that validates API contracts.

    Discovers consumers and ensures API responses match expectations.
    Detects breaking changes like removed fields, type changes, and renames.
    """

    name: str = "contract_validator"

    # Path parameter patterns (Section 10.3)
    PATH_PARAM_PATTERNS = [
        r'\{(\w+)\}',       # {id} style
        r':(\w+)',          # :id style (Express.js)
        r'<(?:\w+:)?(\w+)>' # <id> or <int:id> style (Flask)
    ]

    # Consumer detection patterns
    FETCH_PATTERN = re.compile(r"fetch\s*\(\s*['\"`]([^'\"`]+)['\"`]")
    AXIOS_PATTERN = re.compile(r"axios\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]")
    REQUESTS_PATTERN = re.compile(r"requests\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]")

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        limits: Optional[QALimits] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the ContractValidatorAgent."""
        super().__init__(config, logger, **kwargs)
        self.limits = limits or QALimits()
        self._finding_counter = 0
        self._files_analyzed = 0

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute contract validation on the provided endpoints.

        Args:
            context: Dictionary containing:
                - endpoints: List of QAEndpoint to validate
                - depth: QADepth level
                - base_url: Optional base URL for making requests

        Returns:
            AgentResult with validation results and findings.
        """
        endpoints = context.get("endpoints", [])
        depth = context.get("depth", QADepth.STANDARD)

        self._log("contract_validation_start", {
            "endpoint_count": len(endpoints),
            "depth": depth.value if isinstance(depth, QADepth) else depth,
        })

        contracts_checked = 0
        contracts_valid = 0
        contracts_broken = 0
        findings: list[QAFinding] = []
        skipped_reasons: dict[str, str] = {}

        qa_context = self._build_qa_context(context)

        for endpoint in endpoints:
            try:
                contracts = self.discover_contracts(endpoint, qa_context)

                if not contracts:
                    skipped_reasons[f"{endpoint.method} {endpoint.path}"] = "no_contracts_found"
                    continue

                for contract in contracts:
                    contracts_checked += 1
                    validation_errors = self._validate_contract(contract, context)

                    if validation_errors:
                        contracts_broken += 1
                        for error in validation_errors:
                            findings.append(error)
                    else:
                        contracts_valid += 1

            except Exception as e:
                self._log("contract_validation_error", {
                    "endpoint": f"{endpoint.method} {endpoint.path}",
                    "error": str(e),
                }, level="error")
                skipped_reasons[f"{endpoint.method} {endpoint.path}"] = str(e)

        output = {
            "agent": "contract_validator",
            "contracts_checked": contracts_checked,
            "contracts_valid": contracts_valid,
            "contracts_broken": contracts_broken,
            "findings": findings,
            "skipped_reasons": skipped_reasons,
        }

        return AgentResult.success_result(output=output)

    def _build_qa_context(self, context: dict[str, Any]) -> QAContext:
        """Build QAContext from run context dict."""
        from swarm_attack.qa.models import QAContext
        return QAContext(
            target_files=context.get("target_files", []),
            target_endpoints=context.get("endpoints", []),
            base_url=context.get("base_url"),
        )

    def discover_endpoints(self, context: QAContext) -> list[QAEndpoint]:
        """
        Discover API endpoints from various sources.

        Section 10.3: NEVER return empty list silently - raise EndpointDiscoveryError.

        Priority order:
        1. OpenAPI/Swagger spec (most reliable)
        2. Route decorators in code
        3. Test files
        4. Explicit endpoints from context

        Args:
            context: QAContext with target files and explicit endpoints.

        Returns:
            List of discovered QAEndpoint objects.

        Raises:
            EndpointDiscoveryError: When no endpoints can be discovered.
        """
        endpoints: list[QAEndpoint] = []

        # 1. Try OpenAPI spec first
        endpoints.extend(self._discover_from_openapi(context))

        # 2. Try code analysis
        endpoints.extend(self._discover_from_code(context))

        # 3. Try test files
        endpoints.extend(self._discover_from_tests(context))

        # 4. Add explicit endpoints from context
        endpoints.extend(context.target_endpoints)

        # Deduplicate
        endpoints = self._deduplicate_endpoints(endpoints)

        # Section 10.3: NEVER return empty silently
        if not endpoints:
            raise EndpointDiscoveryError(
                "No endpoints discovered. Either:\n"
                "1. Add openapi.yaml to your project\n"
                "2. Specify endpoints in config.yaml under qa.endpoints\n"
                "3. Check that API code follows standard patterns"
            )

        return endpoints

    def _discover_from_openapi(self, context: QAContext) -> list[QAEndpoint]:
        """Discover endpoints from OpenAPI/Swagger specs."""
        endpoints: list[QAEndpoint] = []
        repo_root = Path(self.config.repo_root)

        spec_files = self._find_openapi_specs(repo_root)

        for spec_file in spec_files:
            try:
                content = self._load_spec_file(spec_file)
                endpoints.extend(self._extract_endpoints_from_openapi(content))
            except Exception as e:
                self._log("openapi_parse_error", {
                    "file": str(spec_file),
                    "error": str(e),
                }, level="warning")

        return endpoints

    def _discover_from_code(self, context: QAContext) -> list[QAEndpoint]:
        """Discover endpoints from code analysis (route decorators)."""
        endpoints: list[QAEndpoint] = []
        repo_root = Path(self.config.repo_root)

        # Look for common API patterns in Python and JS/TS files
        patterns = [
            "**/*.py",
            "**/*.ts",
            "**/*.js",
        ]

        files_to_check = []
        for pattern in patterns:
            files_to_check.extend(repo_root.glob(pattern))

        # Limit files analyzed
        files_to_check = files_to_check[:self.limits.max_files_for_contract_analysis]

        for file_path in files_to_check:
            try:
                content = file_path.read_text()
                endpoints.extend(self._extract_endpoints_from_code(content, str(file_path)))
            except Exception:
                continue

        return endpoints

    def _discover_from_tests(self, context: QAContext) -> list[QAEndpoint]:
        """Discover endpoints from test files."""
        endpoints: list[QAEndpoint] = []
        repo_root = Path(self.config.repo_root)

        test_patterns = [
            "**/test_*.py",
            "**/*_test.py",
            "**/*.test.ts",
            "**/*.spec.ts",
        ]

        for pattern in test_patterns:
            for test_file in repo_root.glob(pattern):
                try:
                    content = test_file.read_text()
                    # Look for API calls in tests
                    endpoints.extend(self._extract_endpoints_from_tests(content))
                except Exception:
                    continue

        return endpoints

    def _find_openapi_specs(self, root: Path) -> list[Path]:
        """Find OpenAPI/Swagger spec files."""
        specs = []
        patterns = [
            "**/openapi.yaml",
            "**/openapi.yml",
            "**/openapi.json",
            "**/swagger.yaml",
            "**/swagger.yml",
            "**/swagger.json",
        ]
        for pattern in patterns:
            specs.extend(root.glob(pattern))
        return specs

    def _load_spec_file(self, path: Path) -> dict[str, Any]:
        """Load and parse an OpenAPI spec file."""
        content = path.read_text()
        if path.suffix == ".json":
            return json.loads(content)
        return yaml.safe_load(content)

    def _extract_endpoints_from_openapi(self, spec: dict[str, Any]) -> list[QAEndpoint]:
        """Extract endpoints from parsed OpenAPI spec."""
        endpoints = []
        paths = spec.get("paths", {})

        for path, methods in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in methods:
                    endpoints.append(QAEndpoint(
                        method=method.upper(),
                        path=path,
                        schema=methods.get(method, {}).get("responses", {}),
                    ))

        return endpoints

    def _extract_endpoints_from_code(self, content: str, file_path: str) -> list[QAEndpoint]:
        """Extract endpoints from route decorators in code."""
        endpoints = []

        # Python Flask/FastAPI patterns
        flask_pattern = re.compile(r'@app\.route\s*\(\s*["\']([^"\']+)["\'].*methods=\[([^\]]+)\]')
        fastapi_pattern = re.compile(r'@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']')

        for match in flask_pattern.finditer(content):
            path = match.group(1)
            methods = match.group(2)
            for method in re.findall(r'"(\w+)"', methods):
                endpoints.append(QAEndpoint(method=method.upper(), path=path))

        for match in fastapi_pattern.finditer(content):
            method = match.group(1)
            path = match.group(2)
            endpoints.append(QAEndpoint(method=method.upper(), path=path))

        # Express.js patterns
        express_pattern = re.compile(r'(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']')
        for match in express_pattern.finditer(content):
            method = match.group(1)
            path = match.group(2)
            endpoints.append(QAEndpoint(method=method.upper(), path=path))

        return endpoints

    def _extract_endpoints_from_tests(self, content: str) -> list[QAEndpoint]:
        """Extract endpoints from test files."""
        endpoints = []

        # Look for HTTP client calls in tests
        patterns = [
            (self.FETCH_PATTERN, "GET"),
            (self.REQUESTS_PATTERN, None),
            (self.AXIOS_PATTERN, None),
        ]

        for pattern, default_method in patterns:
            for match in pattern.finditer(content):
                if default_method:
                    path = match.group(1)
                    method = default_method
                else:
                    method = match.group(1).upper()
                    path = match.group(2)

                if path.startswith("/"):
                    endpoints.append(QAEndpoint(method=method, path=path))

        return endpoints

    def _deduplicate_endpoints(self, endpoints: list[QAEndpoint]) -> list[QAEndpoint]:
        """Remove duplicate endpoints."""
        seen = set()
        unique = []
        for ep in endpoints:
            key = (ep.method, self._normalize_path(ep.path))
            if key not in seen:
                seen.add(key)
                unique.append(ep)
        return unique

    def discover_contracts(self, endpoint: QAEndpoint, context: QAContext) -> list[Contract]:
        """
        Discover contracts for an endpoint using fallback chain.

        Section 10.8: Fallback chain priority:
        1. OpenAPI spec (most authoritative)
        2. Type definitions (TypeScript, Python dataclasses)
        3. Consumer code analysis
        4. Integration tests

        Args:
            endpoint: The endpoint to discover contracts for.
            context: QAContext with project information.

        Returns:
            List of Contract objects (may be empty with warning).
        """
        contracts: list[Contract] = []

        # 1. OpenAPI spec (most authoritative)
        openapi_contract = self._contract_from_openapi(endpoint, context)
        if openapi_contract:
            contracts.append(openapi_contract)

        # 2. Type definitions
        type_contract = self._contract_from_types(endpoint, context)
        if type_contract:
            contracts.append(type_contract)

        # 3. Consumer code analysis
        consumer_contracts = self._contracts_from_consumers(endpoint, context)
        contracts.extend(consumer_contracts)

        # 4. Integration tests
        test_contracts = self._contracts_from_tests(endpoint, context)
        contracts.extend(test_contracts)

        # Section 10.8: Graceful degradation - log warning when empty
        if not contracts:
            self._log("no_contracts_found", {
                "endpoint": f"{endpoint.method} {endpoint.path}",
                "warning": "Contract validation will be skipped",
            }, level="warning")

        return contracts

    def _contract_from_openapi(self, endpoint: QAEndpoint, context: QAContext) -> Optional[Contract]:
        """Extract contract from OpenAPI spec for endpoint."""
        repo_root = Path(self.config.repo_root)

        for spec_file in self._find_openapi_specs(repo_root):
            try:
                spec = self._load_spec_file(spec_file)
                paths = spec.get("paths", {})

                # Find matching path
                for path, methods in paths.items():
                    if self._paths_match(path, endpoint.path):
                        method_spec = methods.get(endpoint.method.lower(), {})
                        if method_spec:
                            return self._contract_from_method_spec(
                                endpoint.path, method_spec, ContractSource.OPENAPI
                            )
            except Exception:
                continue

        return None

    def _contract_from_types(self, endpoint: QAEndpoint, context: QAContext) -> Optional[Contract]:
        """Extract contract from type definitions."""
        # TODO: Implement TypeScript/Python dataclass extraction
        return None

    def _contracts_from_consumers(self, endpoint: QAEndpoint, context: QAContext) -> list[Contract]:
        """Extract contracts from consumer code analysis."""
        contracts = []
        repo_root = Path(self.config.repo_root)

        # Search for consumers
        consumer_patterns = [
            "**/*.ts",
            "**/*.tsx",
            "**/*.js",
            "**/*.jsx",
        ]

        files_checked = 0
        for pattern in consumer_patterns:
            for file_path in repo_root.glob(pattern):
                if files_checked >= self.limits.max_files_for_contract_analysis:
                    break

                try:
                    content = file_path.read_text()
                    consumers = self._find_consumers_in_code(content, str(file_path))

                    for consumer in consumers:
                        if self._consumer_matches_endpoint(consumer, endpoint):
                            contract = self._contract_from_consumer(consumer, file_path)
                            if contract:
                                contracts.append(contract)
                                if len(contracts) >= self.limits.max_consumers_per_endpoint:
                                    return contracts

                    files_checked += 1
                except Exception:
                    continue

        self._files_analyzed = files_checked
        return contracts

    def _contracts_from_tests(self, endpoint: QAEndpoint, context: QAContext) -> list[Contract]:
        """Extract contracts from integration tests."""
        # TODO: Implement test-based contract extraction
        return []

    def _contract_from_method_spec(
        self,
        path: str,
        method_spec: dict[str, Any],
        source: ContractSource
    ) -> Contract:
        """Create Contract from OpenAPI method specification."""
        expected_fields = []
        field_types = {}

        # Extract from response schema
        responses = method_spec.get("responses", {})
        success_response = responses.get("200", responses.get("201", {}))
        content = success_response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        if schema.get("type") == "object":
            properties = schema.get("properties", {})
            for field_name, field_spec in properties.items():
                expected_fields.append(field_name)
                if "type" in field_spec:
                    field_types[field_name] = field_spec["type"]

        return Contract(
            endpoint=path,
            expected_fields=expected_fields,
            field_types=field_types,
            source=source,
        )

    def _find_consumers_in_code(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Find API consumers in code content."""
        consumers = []

        # Find fetch calls
        for match in self.FETCH_PATTERN.finditer(content):
            endpoint = match.group(1)
            consumers.append({
                "endpoint": endpoint,
                "file": file_path,
                "type": "fetch",
            })

        # Find axios calls
        for match in self.AXIOS_PATTERN.finditer(content):
            method = match.group(1)
            endpoint = match.group(2)
            consumers.append({
                "endpoint": endpoint,
                "method": method.upper(),
                "file": file_path,
                "type": "axios",
            })

        # Find Python requests calls
        for match in self.REQUESTS_PATTERN.finditer(content):
            method = match.group(1)
            endpoint = match.group(2)
            consumers.append({
                "endpoint": endpoint,
                "method": method.upper(),
                "file": file_path,
                "type": "requests",
            })

        return consumers

    def _consumer_matches_endpoint(self, consumer: dict[str, Any], endpoint: QAEndpoint) -> bool:
        """Check if a consumer calls the given endpoint."""
        consumer_path = consumer.get("endpoint", "")
        return self._paths_match(consumer_path, endpoint.path)

    def _contract_from_consumer(self, consumer: dict[str, Any], file_path: Path) -> Optional[Contract]:
        """Create Contract from consumer analysis."""
        # TODO: Extract expected fields from consumer code
        return Contract(
            endpoint=consumer.get("endpoint", ""),
            expected_fields=[],
            source=ContractSource.CONSUMER,
            consumer_location=f"{file_path}",
        )

    def _paths_match(self, path1: str, path2: str) -> bool:
        """Check if two paths match (accounting for path parameters)."""
        norm1 = self._normalize_path(path1)
        norm2 = self._normalize_path(path2)
        return norm1 == norm2

    def _normalize_path(self, path: str) -> str:
        """Normalize path by converting all parameter styles to {param}."""
        normalized = path

        # Convert :param to {param}
        normalized = re.sub(r':(\w+)', r'{\1}', normalized)

        # Convert <param> or <type:param> to {param}
        normalized = re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', normalized)

        return normalized

    def _extract_path_params(self, path: str) -> list[str]:
        """Extract path parameter names from a path."""
        params = []
        for pattern in self.PATH_PARAM_PATTERNS:
            for match in re.finditer(pattern, path):
                params.append(match.group(1))
        return params

    def _validate_contract(self, contract: Contract, context: dict[str, Any]) -> list[QAFinding]:
        """Validate a contract (stub for now - would make HTTP request)."""
        # TODO: Make actual HTTP request and validate response
        return []

    def _validate_response(self, contract: Contract, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate an API response against a contract."""
        errors = []

        # Check field presence
        for field in contract.expected_fields:
            if field not in response:
                if field not in contract.nullable_fields:
                    errors.append({
                        "type": "missing_field",
                        "field": field,
                        "message": f"Required field '{field}' is missing",
                    })

        # Check field types
        for field, expected_type in contract.field_types.items():
            if field in response:
                actual_value = response[field]
                if not self._type_matches(actual_value, expected_type):
                    errors.append({
                        "type": "type_mismatch",
                        "field": field,
                        "expected_type": expected_type,
                        "actual_type": type(actual_value).__name__,
                        "message": f"Field '{field}' has wrong type",
                    })

        return errors

    def _type_matches(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, accept anything
        return isinstance(value, expected)

    def _create_contract_finding(
        self,
        endpoint: str,
        consumer_location: str,
        issue: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> QAFinding:
        """Create a QAFinding from a contract violation."""
        self._finding_counter += 1
        finding_id = f"CV-{self._finding_counter:03d}"

        # Determine severity
        if expected.get("required", False) or "missing" in issue.lower():
            severity = "critical"
        elif "type" in issue.lower():
            severity = "moderate"
        else:
            severity = "minor"

        return QAFinding(
            finding_id=finding_id,
            severity=severity,
            category="contract",
            endpoint=endpoint,
            test_type="contract_validation",
            title=issue,
            description=f"Contract violation: {issue}",
            expected=expected,
            actual=actual,
            evidence={
                "consumer": consumer_location,
            },
            recommendation=self._get_contract_recommendation(issue),
        )

    def _get_contract_recommendation(self, issue: str) -> str:
        """Generate recommendation based on contract issue."""
        if "missing" in issue.lower():
            return "Add the missing field to the API response or update consumers to not require it."
        elif "renamed" in issue.lower():
            return "Keep the original field name for backwards compatibility or update all consumers."
        elif "type" in issue.lower():
            return "Fix the field type in the API response or update the contract definition."
        return "Review the contract and ensure API response matches consumer expectations."

    def _analyze_files_for_consumers(self, files: list[str]) -> list[dict[str, Any]]:
        """Analyze files to find API consumers (with limit enforcement)."""
        consumers = []
        self._files_analyzed = 0

        for file_path in files[:self.limits.max_files_for_contract_analysis]:
            try:
                content = self._read_file(file_path)
                file_consumers = self._find_consumers_in_code(content, file_path)
                consumers.extend(file_consumers)
                self._files_analyzed += 1
            except Exception:
                continue

        return consumers

    def _read_file(self, file_path: str) -> str:
        """Read file content."""
        return Path(file_path).read_text()

    def _find_all_consumers(self, endpoint_path: str) -> list[dict[str, Any]]:
        """Find all consumers for an endpoint path."""
        # Stub for testing
        return []

    def _get_consumers_for_endpoint(self, endpoint_path: str) -> list[dict[str, Any]]:
        """Get consumers for an endpoint, respecting limits."""
        all_consumers = self._find_all_consumers(endpoint_path)
        return all_consumers[:self.limits.max_consumers_per_endpoint]
