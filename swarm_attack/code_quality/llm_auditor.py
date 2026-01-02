"""LLM-specific code issue detection.

Detects issues commonly introduced by LLM-generated code:
- Hallucinated imports (non-existent modules)
- Hallucinated APIs (non-existent method calls)
- Incomplete implementations (TODO/FIXME comments)
- Swallowed exceptions (empty except blocks)
- Placeholder returns (return None, {}, 0 as stubs)
"""

import ast
import importlib.util
import re
from pathlib import Path
from typing import Optional

from .models import Finding, Severity, Category, Priority


class LLMAuditor:
    """Detects LLM-specific code issues (hallucinations, incomplete implementations)."""

    # Counter for generating unique finding IDs
    _finding_counter: int = 0

    # Patterns for incomplete implementation detection
    INCOMPLETE_PATTERNS = [
        (r"#\s*TODO\b", "TODO comment found"),
        (r"#\s*FIXME\b", "FIXME comment found"),
        (r"#\s*XXX\b", "XXX comment found"),
        (r"#\s*HACK\b", "HACK comment found"),
    ]

    def __init__(self) -> None:
        """Initialize the LLM auditor."""
        self._finding_counter = 0

    def _next_finding_id(self) -> str:
        """Generate the next finding ID."""
        self._finding_counter += 1
        return f"LLM-{self._finding_counter:03d}"

    def analyze_file(self, file_path: Path) -> list[Finding]:
        """Analyze file for LLM-specific issues.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            List of Finding objects for detected issues.
        """
        findings: list[Finding] = []

        # Handle non-existent file
        if not file_path.exists():
            return findings

        try:
            source = file_path.read_text()
        except Exception:
            return findings

        # Handle empty file
        if not source.strip():
            return findings

        # Try to parse the AST
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # File has syntax errors - can't analyze
            return findings

        file_str = str(file_path)

        # Run all detectors
        findings.extend(self.detect_hallucinated_imports(tree, file_str))
        findings.extend(self.detect_hallucinated_apis(tree, file_str, source))
        findings.extend(self.detect_incomplete_implementations(source, file_str))
        findings.extend(self.detect_swallowed_exceptions(tree, file_str))

        return findings

    def detect_hallucinated_imports(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Find imports of non-existent modules.

        Uses importlib.util.find_spec() to verify module existence.
        Returns CRITICAL severity findings.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for hallucinated imports.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not self._verify_import_exists(module_name):
                        findings.append(Finding(
                            finding_id=self._next_finding_id(),
                            severity=Severity.CRITICAL,
                            category=Category.LLM_HALLUCINATION,
                            file=file_path,
                            line=node.lineno,
                            title=f"Hallucinated import: {module_name}",
                            description=f"Import of non-existent module '{module_name}'. This will cause an ImportError at runtime.",
                            code_snippet=f"import {module_name}",
                            expert="Dr. James Liu",
                            refactoring_pattern="Replace or Remove",
                            refactoring_steps=[
                                f"Verify if '{module_name}' is a typo",
                                "Find the correct module name or remove the import",
                                "If this is a custom module, ensure it exists in the codebase",
                            ],
                            priority=Priority.FIX_NOW,
                            effort_estimate="small",
                            confidence=0.95,
                        ))

            elif isinstance(node, ast.ImportFrom):
                # Handle "from X import Y" statements
                module_name = node.module

                # Handle relative imports
                if node.level > 0:
                    # Relative import - harder to verify
                    # For now, flag relative imports to non-existent siblings
                    # This is a simplification - in a real implementation,
                    # we'd resolve the relative import against the file's location
                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.CRITICAL,
                        category=Category.LLM_HALLUCINATION,
                        file=file_path,
                        line=node.lineno,
                        title="Potentially hallucinated relative import",
                        description=f"Relative import from '{module_name or ''}' with level {node.level}. Verify this module exists in the package.",
                        code_snippet=self._format_import_from(node),
                        expert="Dr. James Liu",
                        refactoring_pattern="Verify or Replace",
                        refactoring_steps=[
                            "Check if the relative module exists",
                            "Verify the package structure",
                            "Use absolute imports if uncertain",
                        ],
                        priority=Priority.FIX_NOW,
                        effort_estimate="small",
                        confidence=0.75,
                    ))
                elif module_name and not self._verify_import_exists(module_name):
                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.CRITICAL,
                        category=Category.LLM_HALLUCINATION,
                        file=file_path,
                        line=node.lineno,
                        title=f"Hallucinated import: {module_name}",
                        description=f"Import from non-existent module '{module_name}'. This will cause an ImportError at runtime.",
                        code_snippet=self._format_import_from(node),
                        expert="Dr. James Liu",
                        refactoring_pattern="Replace or Remove",
                        refactoring_steps=[
                            f"Verify if '{module_name}' is a typo",
                            "Find the correct module name or remove the import",
                            "If this is a custom module, ensure it exists in the codebase",
                        ],
                        priority=Priority.FIX_NOW,
                        effort_estimate="small",
                        confidence=0.95,
                    ))

        return findings

    def _format_import_from(self, node: ast.ImportFrom) -> str:
        """Format an ImportFrom node as a code snippet."""
        dots = "." * node.level
        module = node.module or ""
        names = ", ".join(alias.name for alias in node.names)
        return f"from {dots}{module} import {names}"

    def detect_hallucinated_apis(
        self, tree: ast.AST, file_path: str, source: str
    ) -> list[Finding]:
        """Find method calls on classes that don't have those methods.

        This focuses on self.method() calls within class definitions.
        It checks if the method exists on the same class.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.
            source: The source code as a string.

        Returns:
            List of findings for hallucinated API calls.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Collect all method names defined in this class
                defined_methods = set()
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                        defined_methods.add(item.name)

                # Also add common dunder methods and inherited methods
                # that are always available
                builtin_methods = {
                    "__init__", "__new__", "__del__", "__repr__", "__str__",
                    "__bytes__", "__format__", "__hash__", "__bool__",
                    "__getattr__", "__setattr__", "__delattr__", "__dir__",
                    "__get__", "__set__", "__delete__", "__call__",
                    "__len__", "__getitem__", "__setitem__", "__delitem__",
                    "__iter__", "__next__", "__contains__", "__enter__",
                    "__exit__", "__await__", "__aiter__", "__anext__",
                    "__aenter__", "__aexit__", "__eq__", "__ne__", "__lt__",
                    "__le__", "__gt__", "__ge__", "__add__", "__sub__",
                }
                defined_methods.update(builtin_methods)

                # Now look for self.method() calls
                for item in ast.walk(node):
                    if isinstance(item, ast.Call):
                        if isinstance(item.func, ast.Attribute):
                            if isinstance(item.func.value, ast.Name):
                                if item.func.value.id == "self":
                                    method_name = item.func.attr
                                    if method_name not in defined_methods:
                                        # Get the line of code for the snippet
                                        lines = source.split("\n")
                                        line_idx = item.lineno - 1
                                        code_line = lines[line_idx] if line_idx < len(lines) else ""

                                        findings.append(Finding(
                                            finding_id=self._next_finding_id(),
                                            severity=Severity.CRITICAL,
                                            category=Category.LLM_HALLUCINATION,
                                            file=file_path,
                                            line=item.lineno,
                                            title=f"Hallucinated API: self.{method_name}()",
                                            description=f"Method '{method_name}' is called on 'self' but is not defined in class '{node.name}'. This will cause an AttributeError at runtime.",
                                            code_snippet=code_line.strip(),
                                            expert="Dr. James Liu",
                                            refactoring_pattern="Implement or Remove",
                                            refactoring_steps=[
                                                f"Implement method '{method_name}' in class '{node.name}'",
                                                "Or replace with an existing method that provides the needed functionality",
                                                "Or remove the call if not needed",
                                            ],
                                            priority=Priority.FIX_NOW,
                                            effort_estimate="medium",
                                            confidence=0.90,
                                        ))

        return findings

    def detect_incomplete_implementations(
        self, source: str, file_path: str
    ) -> list[Finding]:
        """Find TODO, FIXME, XXX, HACK comments.

        Also detect placeholder returns: return None, return {}, return 0
        when they appear to be stub implementations.

        Args:
            source: The source code as a string.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for incomplete implementations.
        """
        findings: list[Finding] = []
        lines = source.split("\n")

        # Check for TODO, FIXME, XXX, HACK comments
        for line_num, line in enumerate(lines, start=1):
            for pattern, message in self.INCOMPLETE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.HIGH,
                        category=Category.INCOMPLETE,
                        file=file_path,
                        line=line_num,
                        title=message,
                        description=f"Incomplete implementation marker found: {line.strip()}",
                        code_snippet=line.strip(),
                        expert="Dr. James Liu",
                        refactoring_pattern="Complete Implementation",
                        refactoring_steps=[
                            "Review what the TODO/FIXME is asking for",
                            "Implement the missing functionality",
                            "Remove the marker comment once complete",
                        ],
                        priority=Priority.FIX_NOW,
                        effort_estimate="medium",
                        confidence=0.95,
                    ))

        # Check for placeholder returns
        # Only flag if the function body is very short (likely a stub)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Look for stub patterns:
                # 1. Single return None/{}/''/0/[] at end
                # 2. Only has comments and a placeholder return
                body = node.body
                if len(body) >= 1:
                    last_stmt = body[-1]
                    if isinstance(last_stmt, ast.Return):
                        if self._is_placeholder_return(last_stmt, body):
                            # Check if there's a comment suggesting this is intentional
                            func_lines = source.split("\n")[node.lineno - 1:node.end_lineno]
                            func_text = "\n".join(func_lines)

                            # Don't flag if there's a docstring explaining the None return
                            # or if the function has real logic before the return
                            has_real_logic = any(
                                isinstance(stmt, (ast.Assign, ast.AugAssign, ast.Call,
                                                 ast.If, ast.For, ast.While, ast.With,
                                                 ast.Try))
                                for stmt in body[:-1]
                            )

                            if not has_real_logic:
                                findings.append(Finding(
                                    finding_id=self._next_finding_id(),
                                    severity=Severity.HIGH,
                                    category=Category.INCOMPLETE,
                                    file=file_path,
                                    line=last_stmt.lineno,
                                    title=f"Placeholder return in {node.name}()",
                                    description=f"Function '{node.name}' appears to have a stub implementation with a placeholder return value.",
                                    code_snippet=lines[last_stmt.lineno - 1].strip() if last_stmt.lineno <= len(lines) else "",
                                    expert="Dr. James Liu",
                                    refactoring_pattern="Implement Function",
                                    refactoring_steps=[
                                        f"Review the expected behavior of '{node.name}'",
                                        "Implement the actual logic",
                                        "Return the appropriate value",
                                    ],
                                    priority=Priority.FIX_NOW,
                                    effort_estimate="medium",
                                    confidence=0.75,
                                ))

        return findings

    def _is_placeholder_return(self, return_node: ast.Return, body: list) -> bool:
        """Check if a return statement is a placeholder."""
        value = return_node.value

        if value is None:
            # "return" or "return None" - could be placeholder
            # Only flag if function body is very short
            return len(body) <= 2

        if isinstance(value, ast.Constant):
            # return None, return 0, return "", return False
            if value.value in (None, 0, "", False, []):
                return len(body) <= 2

        if isinstance(value, ast.Dict) and len(value.keys) == 0:
            # return {}
            return len(body) <= 2

        if isinstance(value, ast.List) and len(value.elts) == 0:
            # return []
            return len(body) <= 2

        return False

    def detect_swallowed_exceptions(
        self, tree: ast.AST, file_path: str
    ) -> list[Finding]:
        """Find empty except blocks or bare except clauses.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for swallowed exceptions.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    is_bare_except = handler.type is None
                    is_empty_handler = (
                        len(handler.body) == 1 and
                        isinstance(handler.body[0], ast.Pass)
                    )

                    if is_bare_except:
                        # Bare except clause - catches everything
                        findings.append(Finding(
                            finding_id=self._next_finding_id(),
                            severity=Severity.HIGH,
                            category=Category.ERROR_HANDLING,
                            file=file_path,
                            line=handler.lineno,
                            title="Bare except clause",
                            description="Bare 'except:' catches all exceptions including KeyboardInterrupt and SystemExit. This can hide bugs and make debugging difficult.",
                            code_snippet="except:",
                            expert="Dr. James Liu",
                            refactoring_pattern="Add Exception Type",
                            refactoring_steps=[
                                "Identify which specific exceptions should be caught",
                                "Replace bare except with specific exception types",
                                "Add proper error logging",
                            ],
                            priority=Priority.FIX_NOW,
                            effort_estimate="small",
                            confidence=0.95,
                        ))

                    if is_empty_handler:
                        # Empty except block - swallows errors
                        exception_type = "all exceptions" if is_bare_except else ast.unparse(handler.type)
                        findings.append(Finding(
                            finding_id=self._next_finding_id(),
                            severity=Severity.HIGH,
                            category=Category.ERROR_HANDLING,
                            file=file_path,
                            line=handler.lineno,
                            title="Swallowed exception",
                            description=f"Exception handler for {exception_type} contains only 'pass'. This silently swallows errors and makes debugging impossible.",
                            code_snippet=f"except {exception_type}:\n    pass" if not is_bare_except else "except:\n    pass",
                            expert="Dr. James Liu",
                            refactoring_pattern="Add Error Handling",
                            refactoring_steps=[
                                "Log the exception at minimum",
                                "Consider re-raising after logging",
                                "Return an error result if applicable",
                            ],
                            priority=Priority.FIX_NOW,
                            effort_estimate="small",
                            confidence=0.95,
                        ))

        return findings

    def _verify_import_exists(self, module_name: str) -> bool:
        """Check if a module can be imported.

        Args:
            module_name: The name of the module to check.

        Returns:
            True if the module exists, False otherwise.
        """
        try:
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ModuleNotFoundError, ValueError, AttributeError):
            return False
