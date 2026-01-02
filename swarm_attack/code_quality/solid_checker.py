"""SOLID principle violation detection using AST analysis.

This module detects violations of SOLID principles:
- Single Responsibility Principle (SRP): Classes with multiple unrelated responsibilities
- Open/Closed Principle (OCP): Switch on type instead of polymorphism
- Dependency Inversion Principle (DIP): Direct instantiation of dependencies

Detection is based on AST analysis of Python source code.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .models import Finding, Severity, Category, Priority


class SOLIDChecker:
    """Detects SOLID principle violations using AST analysis."""

    # Common prefixes that indicate method clusters
    CLUSTER_PREFIXES = [
        "save", "load", "delete", "update", "create", "get", "set",
        "send", "receive", "process", "handle", "validate", "parse",
        "connect", "disconnect", "open", "close", "read", "write",
        "log", "export", "import", "convert", "transform", "filter",
        "email", "notify", "db", "database", "cache", "queue",
        "auth", "authenticate", "authorize", "encrypt", "decrypt",
    ]

    # Types that are considered value objects (not dependencies)
    VALUE_TYPES = {
        "dict", "list", "set", "tuple", "frozenset",
        "str", "int", "float", "bool", "bytes",
        "datetime", "date", "time", "timedelta",
        "Path", "UUID", "Decimal",
    }

    # Standard library instantiations that are OK
    STDLIB_CLASSES = {
        "datetime", "date", "time", "timedelta",
        "Path", "PurePath", "PosixPath", "WindowsPath",
        "UUID", "Decimal", "Fraction",
        "defaultdict", "Counter", "OrderedDict", "deque",
        "Thread", "Lock", "Event", "Semaphore",
    }

    def __init__(self):
        """Initialize the SOLID checker."""
        self._finding_counter = 0

    def _next_finding_id(self) -> str:
        """Generate the next finding ID."""
        self._finding_counter += 1
        return f"SOLID-{self._finding_counter:03d}"

    def analyze_file(self, file_path: Path) -> list[Finding]:
        """Analyze a Python file for SOLID violations.

        Args:
            file_path: Path to the Python file to analyze

        Returns:
            List of Finding objects for detected SOLID violations
        """
        try:
            if not file_path.exists():
                return []

            source = file_path.read_text()
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return []

        findings: list[Finding] = []
        file_str = str(file_path)

        # Detect each type of SOLID violation
        findings.extend(self.detect_srp_violations(tree, file_str))
        findings.extend(self.detect_ocp_violations(tree, file_str))
        findings.extend(self.detect_dip_violations(tree, file_str))

        return findings

    def detect_srp_violations(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Detect Single Responsibility Principle violations.

        A class violates SRP if it has methods from multiple unrelated domains.
        Uses method clustering - if methods form > 2 distinct clusters, flag SRP.

        Args:
            tree: AST of the Python source
            file_path: Path to the source file (for reporting)

        Returns:
            List of findings for SRP violations
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            clusters = self._cluster_methods_by_name(node)

            # If class has more than 2 distinct method clusters, it's an SRP violation
            if len(clusters) > 2:
                cluster_names = [
                    f"'{methods[0].split('_')[0]}*'" if methods else "unknown"
                    for methods in clusters
                ]

                findings.append(Finding(
                    finding_id=self._next_finding_id(),
                    severity=Severity.MEDIUM,
                    category=Category.SOLID,
                    file=file_path,
                    line=node.lineno,
                    title=f"SRP Violation: {node.name}",
                    description=(
                        f"Class '{node.name}' appears to have {len(clusters)} distinct "
                        f"responsibilities based on method clustering: {', '.join(cluster_names)}. "
                        f"Consider extracting separate classes for each responsibility."
                    ),
                    code_snippet=f"class {node.name}:",
                    expert="Alexandra Vance",
                    refactoring_pattern="Extract Class",
                    refactoring_steps=[
                        "Create a new class for each responsibility cluster",
                        "Move related methods to the new classes",
                        f"Compose the new classes into {node.name} or replace it",
                    ],
                    priority=Priority.FIX_LATER,
                    effort_estimate="large",
                    confidence=0.8,
                ))

        return findings

    def detect_ocp_violations(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Detect Open/Closed Principle violations.

        Look for switch/if-elif chains checking isinstance or type.
        These should be replaced with polymorphism.

        Args:
            tree: AST of the Python source
            file_path: Path to the source file (for reporting)

        Returns:
            List of findings for OCP violations
        """
        findings: list[Finding] = []

        type_checks = self._find_type_checks(tree)

        # Group type checks by their containing function/method
        checks_by_function: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for line, type_name in type_checks:
            # Use a rough grouping by line proximity
            func_key = line // 20  # Group checks within ~20 lines
            checks_by_function[func_key].append((line, type_name))

        # Only flag if there are 2+ isinstance/type checks in a chain
        for func_key, checks in checks_by_function.items():
            if len(checks) >= 2:
                first_line = min(line for line, _ in checks)
                types_checked = [type_name for _, type_name in checks]

                findings.append(Finding(
                    finding_id=self._next_finding_id(),
                    severity=Severity.MEDIUM,
                    category=Category.SOLID,
                    file=file_path,
                    line=first_line,
                    title="OCP Violation: Type Check Chain",
                    description=(
                        f"Found {len(checks)} type checks in an if/elif chain "
                        f"(types: {', '.join(types_checked[:5])}{'...' if len(types_checked) > 5 else ''}). "
                        f"Consider using polymorphism instead of checking types explicitly."
                    ),
                    code_snippet=f"if isinstance(obj, {types_checked[0]}): ...",
                    expert="Alexandra Vance",
                    refactoring_pattern="Replace Conditional with Polymorphism",
                    refactoring_steps=[
                        "Define a common interface/base class with an abstract method",
                        f"Implement the method in each type: {', '.join(types_checked[:3])}",
                        "Replace the if/elif chain with a single method call",
                    ],
                    priority=Priority.FIX_LATER,
                    effort_estimate="medium",
                    confidence=0.85,
                ))

        return findings

    def detect_dip_violations(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Detect Dependency Inversion Principle violations.

        Look for classes that instantiate their dependencies directly
        in __init__ instead of accepting them as parameters.

        Args:
            tree: AST of the Python source
            file_path: Path to the source file (for reporting)

        Returns:
            List of findings for DIP violations
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Find the __init__ method
            init_method: Optional[ast.FunctionDef] = None
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    init_method = item
                    break

            if init_method is None:
                continue

            # Look for direct instantiation of dependencies
            violations: list[tuple[int, str]] = []
            for stmt in ast.walk(init_method):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                            if target.value.id == "self":
                                # Check if the value is a class instantiation
                                if isinstance(stmt.value, ast.Call):
                                    func = stmt.value.func
                                    if isinstance(func, ast.Name):
                                        class_name = func.id
                                        # Skip value types and stdlib classes
                                        if class_name not in self.VALUE_TYPES and class_name not in self.STDLIB_CLASSES:
                                            violations.append((stmt.lineno, class_name))

            # Only report if there are actual violations
            if violations:
                instantiated_classes = [cls for _, cls in violations]
                first_line = min(line for line, _ in violations)

                findings.append(Finding(
                    finding_id=self._next_finding_id(),
                    severity=Severity.MEDIUM,
                    category=Category.SOLID,
                    file=file_path,
                    line=first_line,
                    title=f"DIP Violation: {node.name}",
                    description=(
                        f"Class '{node.name}' instantiates its dependencies directly in __init__: "
                        f"{', '.join(instantiated_classes[:5])}{'...' if len(instantiated_classes) > 5 else ''}. "
                        f"Consider accepting dependencies as constructor parameters (dependency injection)."
                    ),
                    code_snippet=f"self.{violations[0][1].lower()} = {violations[0][1]}()",
                    expert="Alexandra Vance",
                    refactoring_pattern="Inject Dependencies",
                    refactoring_steps=[
                        f"Add parameters to __init__ for each dependency: {', '.join(instantiated_classes[:3])}",
                        "Assign the injected dependencies to instance attributes",
                        "Create the concrete instances at the call site or use a factory/DI container",
                    ],
                    priority=Priority.FIX_NOW,
                    effort_estimate="small",
                    confidence=0.9,
                ))

        return findings

    # Domain keywords that indicate a specific responsibility
    DOMAIN_KEYWORDS = {
        "database": ["database", "db", "sql", "query", "table", "record"],
        "email": ["email", "mail", "smtp", "notification"],
        "log": ["log", "logging", "audit", "trace"],
        "cache": ["cache", "redis", "memcached"],
        "file": ["file", "path", "directory", "folder"],
        "http": ["http", "request", "response", "api", "endpoint"],
        "auth": ["auth", "login", "logout", "permission", "role"],
        "user": ["user", "account", "profile"],
        "payment": ["payment", "charge", "invoice", "billing"],
        "storage": ["storage", "bucket", "s3", "blob"],
    }

    def _cluster_methods_by_name(self, class_node: ast.ClassDef) -> list[list[str]]:
        """Group methods by common domain/purpose based on their names.

        Uses a two-phase approach:
        1. First, try to match methods to domain keywords (database, email, log, etc.)
        2. For methods without domain matches, group by action prefix

        e.g., ['save_to_database', 'load_from_database'] -> 'database' cluster
              ['send_email', 'send_welcome_email'] -> 'email' cluster

        Args:
            class_node: AST node for a class definition

        Returns:
            List of method name clusters, where each cluster is a list of method names
        """
        # Get all non-dunder method names
        method_names: list[str] = []
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef):
                name = item.name
                # Skip dunder methods
                if name.startswith("__") and name.endswith("__"):
                    continue
                method_names.append(name)

        if not method_names:
            return []

        # Phase 1: Cluster by domain keywords
        clusters: dict[str, list[str]] = defaultdict(list)
        unmatched: list[str] = []

        for method_name in method_names:
            method_lower = method_name.lower()
            matched_domain: Optional[str] = None

            # Check if method name contains any domain keyword
            for domain, keywords in self.DOMAIN_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in method_lower:
                        matched_domain = domain
                        break
                if matched_domain:
                    break

            if matched_domain:
                clusters[matched_domain].append(method_name)
            else:
                unmatched.append(method_name)

        # Phase 2: Group unmatched methods by action prefix
        for method_name in unmatched:
            matched_prefix: Optional[str] = None
            for prefix in self.CLUSTER_PREFIXES:
                if method_name.startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix:
                clusters[f"action_{matched_prefix}"].append(method_name)
            else:
                # Methods without recognized prefix go to "other" cluster
                parts = method_name.split("_")
                if len(parts) > 1:
                    clusters[f"other_{parts[0]}"].append(method_name)
                else:
                    clusters["_other_"].append(method_name)

        # Convert to list of lists, filtering out small clusters (< 2 methods)
        result: list[list[str]] = []
        for methods in clusters.values():
            if len(methods) >= 2:  # Only count clusters with 2+ methods
                result.append(methods)

        # If no significant clusters found, return a single cluster with all methods
        if not result and method_names:
            return [method_names]

        return result

    def _find_type_checks(self, node: ast.AST) -> list[tuple[int, str]]:
        """Find isinstance/type checks in if/elif chains.

        Args:
            node: AST node to search

        Returns:
            List of (line_number, type_being_checked) tuples
        """
        type_checks: list[tuple[int, str]] = []

        for child in ast.walk(node):
            if isinstance(child, (ast.If,)):
                # Check the condition
                self._extract_type_check(child.test, type_checks)

        return type_checks

    def _extract_type_check(
        self, node: ast.AST, type_checks: list[tuple[int, str]]
    ) -> None:
        """Extract type check from a condition node.

        Args:
            node: AST node representing a condition
            type_checks: List to append findings to
        """
        if isinstance(node, ast.Call):
            # Check for isinstance(obj, SomeType)
            if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                if len(node.args) >= 2:
                    type_arg = node.args[1]
                    if isinstance(type_arg, ast.Name):
                        type_checks.append((node.lineno, type_arg.id))
                    elif isinstance(type_arg, ast.Tuple):
                        # isinstance(obj, (TypeA, TypeB))
                        for elt in type_arg.elts:
                            if isinstance(elt, ast.Name):
                                type_checks.append((node.lineno, elt.id))

        elif isinstance(node, ast.Compare):
            # Check for type(obj) == SomeType
            if isinstance(node.left, ast.Call):
                if isinstance(node.left.func, ast.Name) and node.left.func.id == "type":
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Name):
                            type_checks.append((node.lineno, comparator.id))

        elif isinstance(node, ast.BoolOp):
            # Handle 'and' / 'or' combinations
            for value in node.values:
                self._extract_type_check(value, type_checks)
