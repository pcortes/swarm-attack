"""
Context Builder for Feature Swarm.

This module provides rich context injection for coder agents:
- Reads CLAUDE.md project instructions from repo root
- Builds comprehensive context from completed issue summaries
- Formats module registry for context handoff
- Extracts and injects actual class source code to prevent schema drift
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.state_store import StateStore


class ContextBuilder:
    """
    Builds rich context for coder agents.

    Reads project instructions from CLAUDE.md and aggregates context
    from completed issues to enable informed implementation.
    """

    # Candidate paths for project instructions (checked in order)
    CLAUDE_MD_CANDIDATES = [
        "CLAUDE.md",
        "claude.md",
        ".claude/CLAUDE.md",
    ]

    def __init__(
        self,
        config: SwarmConfig,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the context builder.

        Args:
            config: SwarmConfig with repo_root path.
            state_store: Optional StateStore for loading summaries.
        """
        self.config = config
        self._state_store = state_store
        self._cached_instructions: Optional[str] = None

    def get_project_instructions(self) -> str:
        """
        Read project instructions from CLAUDE.md.

        Searches for CLAUDE.md in multiple locations (repo root, .claude/).
        Results are cached for efficiency.

        Returns:
            Contents of CLAUDE.md if found, empty string otherwise.
        """
        if self._cached_instructions is not None:
            return self._cached_instructions

        for candidate in self.CLAUDE_MD_CANDIDATES:
            path = Path(self.config.repo_root) / candidate
            if path.exists():
                try:
                    self._cached_instructions = path.read_text()
                    return self._cached_instructions
                except (IOError, OSError):
                    continue

        self._cached_instructions = ""
        return self._cached_instructions

    def get_completed_summaries(self, feature_id: str) -> list[dict[str, Any]]:
        """
        Get summaries of completed issues for context handoff.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of dictionaries with issue summaries:
            [
                {
                    "issue_number": 1,
                    "title": "...",
                    "completion_summary": "...",
                    "files_created": [...],
                    "classes_defined": {...},
                },
                ...
            ]
        """
        if self._state_store is None:
            return []

        from swarm_attack.models import TaskStage

        state = self._state_store.load(feature_id)
        if state is None:
            return []

        summaries = []
        for task in state.tasks:
            if task.stage == TaskStage.DONE:
                summary_entry: dict[str, Any] = {
                    "issue_number": task.issue_number,
                    "title": task.title,
                }

                # Add completion summary if available
                if hasattr(task, "completion_summary") and task.completion_summary:
                    summary_entry["completion_summary"] = task.completion_summary

                # Add outputs if available
                if task.outputs:
                    summary_entry["files_created"] = task.outputs.files_created
                    summary_entry["classes_defined"] = task.outputs.classes_defined

                summaries.append(summary_entry)

        return summaries

    def build_coder_context(
        self,
        feature_id: str,
        issue_number: int,
        module_registry: dict[str, Any],
        issue_body: str,
        completed_summaries: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Build comprehensive context for coder agent.

        Aggregates all available context sources into a single dict
        that can be passed to the coder agent prompt.

        Args:
            feature_id: The feature identifier.
            issue_number: Current issue being implemented.
            module_registry: Registry of modules created by prior issues.
            issue_body: The issue description/body.
            completed_summaries: Optional pre-loaded summaries (avoids reload).

        Returns:
            Dictionary with all context:
            {
                "project_instructions": "...",  # From CLAUDE.md
                "module_registry": {...},
                "completed_summaries": [...],
                "feature_id": "...",
                "issue_number": N,
                "issue_body": "...",
            }
        """
        # Load summaries if not provided
        if completed_summaries is None:
            completed_summaries = self.get_completed_summaries(feature_id)

        return {
            "project_instructions": self.get_project_instructions(),
            "module_registry": module_registry,
            "completed_summaries": completed_summaries,
            "feature_id": feature_id,
            "issue_number": issue_number,
            "issue_body": issue_body,
        }

    def format_project_instructions_for_prompt(self) -> str:
        """
        Format project instructions for inclusion in coder prompt.

        Returns:
            Formatted markdown section with CLAUDE.md content,
            or empty string if no instructions found.
        """
        instructions = self.get_project_instructions()
        if not instructions:
            return ""

        # Truncate if too long (keep first 15k chars to leave room for other context)
        MAX_CHARS = 15000
        if len(instructions) > MAX_CHARS:
            instructions = instructions[:MAX_CHARS] + "\n\n... (truncated)"

        return f"""## Project Instructions (from CLAUDE.md)

{instructions}

---
"""

    def format_completed_summaries_for_prompt(
        self,
        feature_id: str,
    ) -> str:
        """
        Format completed issue summaries for inclusion in coder prompt.

        Args:
            feature_id: The feature identifier.

        Returns:
            Formatted markdown section with summaries,
            or message if no summaries available.
        """
        summaries = self.get_completed_summaries(feature_id)

        if not summaries:
            return "**No prior issues completed for this feature.**\n"

        lines = ["## Completed Issues Summary\n"]
        lines.append("The following issues have been implemented. Use this context for integration:\n")

        for summary in summaries:
            issue_num = summary.get("issue_number", "?")
            title = summary.get("title", "Unknown")
            completion = summary.get("completion_summary", "")

            lines.append(f"### Issue #{issue_num}: {title}")

            if completion:
                lines.append(f"**Summary:** {completion}")

            files = summary.get("files_created", [])
            if files:
                lines.append(f"**Files:** {', '.join(files)}")

            classes = summary.get("classes_defined", {})
            if classes:
                class_list = []
                for file_path, class_names in classes.items():
                    if class_names:
                        class_list.append(f"{file_path}: {', '.join(class_names)}")
                if class_list:
                    lines.append(f"**Classes:** {'; '.join(class_list)}")

            lines.append("")

        return "\n".join(lines)

    def _path_to_module(self, file_path: str) -> str:
        """
        Convert a file path to a Python module import path.

        Args:
            file_path: Relative file path (e.g., "swarm_attack/chief_of_staff/models.py")

        Returns:
            Module import path (e.g., "swarm_attack.chief_of_staff.models")
        """
        # Remove .py extension
        if file_path.endswith(".py"):
            file_path = file_path[:-3]
        # Convert slashes to dots
        return file_path.replace("/", ".").replace("\\", ".")

    def _extract_class_source(self, file_path: Path, class_name: str) -> str:
        """
        Extract source code for a specific class using AST.

        This is the key method for preventing schema drift - by showing the coder
        the ACTUAL class definition (not just the class name), we eliminate
        ambiguity about what fields and methods exist.

        Args:
            file_path: Full path to the Python file.
            class_name: Name of the class to extract.

        Returns:
            Source code of the class including decorators, or empty string if not found.
        """
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, FileNotFoundError, OSError):
            return ""

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Get line range (AST uses 1-based line numbers)
                # Include decorators by checking decorator_list
                if node.decorator_list:
                    # Start from the first decorator
                    start_line = node.decorator_list[0].lineno - 1
                else:
                    start_line = node.lineno - 1
                end_line = node.end_lineno if node.end_lineno else start_line + 1

                lines = content.split('\n')[start_line:end_line]
                return '\n'.join(lines)

        return ""

    def _extract_class_schema(self, file_path: Path, class_name: str) -> dict[str, Any]:
        """
        Extract structured schema for a class (fields, methods, decorators).

        This provides machine-readable schema information for validation,
        while _extract_class_source provides human-readable source for the coder.

        Args:
            file_path: Full path to the Python file.
            class_name: Name of the class to extract.

        Returns:
            Schema dictionary with fields, methods, and import_path.
        """
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, FileNotFoundError, OSError):
            return {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                fields = []
                methods = []
                is_dataclass = False

                # Check for @dataclass decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                        is_dataclass = True
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass":
                            is_dataclass = True

                for item in node.body:
                    # Extract annotated assignments (dataclass fields or class attributes)
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        field_name = item.target.id
                        try:
                            field_type = ast.unparse(item.annotation)
                        except Exception:
                            field_type = "Any"

                        default = None
                        if item.value:
                            try:
                                default = ast.unparse(item.value)
                            except Exception:
                                default = "..."

                        fields.append({
                            "name": field_name,
                            "type": field_type,
                            "default": default,
                        })

                    # Extract method definitions
                    elif isinstance(item, ast.FunctionDef):
                        methods.append(item.name)

                # Convert file path to import path
                rel_path = str(file_path)
                if str(self.config.repo_root) in rel_path:
                    rel_path = rel_path.replace(str(self.config.repo_root) + "/", "")
                import_path = self._path_to_module(rel_path)

                return {
                    "fields": fields,
                    "methods": methods,
                    "import_path": import_path,
                    "is_dataclass": is_dataclass,
                }

        return {}

    def format_module_registry_with_source(
        self,
        registry: dict[str, Any],
        max_chars_per_class: int = 3000,
    ) -> str:
        """
        Format module registry with actual source code for classes.

        This is the PRIMARY mechanism for preventing schema drift. By showing
        the coder the actual class source code (not just class names), we
        eliminate ambiguity about what fields and methods exist.

        The coder will see:
        1. Import statement to use
        2. Full class source code
        3. Explicit warning not to recreate

        Args:
            registry: Module registry from StateStore.get_module_registry()
            max_chars_per_class: Maximum characters per class before truncation.

        Returns:
            Formatted markdown section for inclusion in coder prompt.
        """
        if not registry or not registry.get("modules"):
            return "**No prior modules created for this feature.**"

        modules = registry.get("modules", {})
        if not modules:
            return "**No prior modules created for this feature.**"

        lines = [
            "## Existing Classes (MUST IMPORT - DO NOT RECREATE)",
            "",
            "**CRITICAL: The following classes already exist. You MUST import and use them.**",
            "**Creating a class with the same name WILL CAUSE SCHEMA CONFLICTS and break the system.**",
            "",
        ]

        classes_shown = 0
        for file_path, info in modules.items():
            full_path = Path(self.config.repo_root) / file_path
            if not full_path.exists():
                continue

            class_names = info.get("classes", [])
            if not class_names:
                continue

            import_path = self._path_to_module(file_path)
            issue_num = info.get("created_by_issue", "?")

            lines.append(f"### From `{file_path}` (Issue #{issue_num})")
            lines.append(f"**Import:** `from {import_path} import {', '.join(class_names)}`")
            lines.append("")

            for class_name in class_names:
                source = self._extract_class_source(full_path, class_name)
                if source:
                    # Truncate large classes to manage token usage
                    if len(source) > max_chars_per_class:
                        # Find a good truncation point (end of a method or field)
                        truncated = source[:max_chars_per_class]
                        last_newline = truncated.rfind('\n')
                        if last_newline > max_chars_per_class // 2:
                            truncated = truncated[:last_newline]
                        source = truncated + "\n    # ... (truncated - see full file for details)"

                    lines.append(f"**Class `{class_name}`:**")
                    lines.append("```python")
                    lines.append(source)
                    lines.append("```")
                    lines.append("")
                    classes_shown += 1

        if classes_shown == 0:
            return "**No prior modules created for this feature.**"

        # Add schema evolution guidance
        lines.append("---")
        lines.append("### Schema Evolution Rules")
        lines.append("")
        lines.append("If you need functionality not in an existing class:")
        lines.append("1. **EXTEND**: Create a subclass (e.g., `class ExtendedSession(AutopilotSession)`)")
        lines.append("2. **COMPOSE**: Create a new class that HAS-A the existing class")
        lines.append("3. **SEPARATE**: Create a distinctly-named class (e.g., `RunnerState` not `AutopilotSession`)")
        lines.append("")
        lines.append("**NEVER recreate a class with the same name but different fields.**")
        lines.append("")

        return "\n".join(lines)

    def get_existing_class_names(self, registry: dict[str, Any]) -> dict[str, str]:
        """
        Get a mapping of all existing class names to their file paths.

        Used for duplicate class detection in the verifier.

        Args:
            registry: Module registry from StateStore.get_module_registry()

        Returns:
            Dictionary mapping class names to file paths.
        """
        class_map: dict[str, str] = {}

        if not registry or not registry.get("modules"):
            return class_map

        for file_path, info in registry.get("modules", {}).items():
            for class_name in info.get("classes", []):
                class_map[class_name] = file_path

        return class_map

    def format_module_registry_compact(
        self,
        registry: dict[str, Any],
        dependencies: Optional[set[int]] = None,
        max_fields_per_class: int = 8,
        max_methods_per_class: int = 5,
    ) -> str:
        """
        Format module registry as compact schema (token-efficient alternative).

        This method is more token-efficient than format_module_registry_with_source.
        Instead of full source code (~300-800 tokens/class), it provides structured
        schema information (~50 tokens/class):
        - Import statement
        - Field names and types (truncated)
        - Method names (truncated)

        When dependencies are provided, only shows classes from those issues,
        further reducing token usage.

        Token budget: ~50 tokens per class x ~10 relevant classes = ~500 tokens

        Args:
            registry: Module registry from StateStore.get_module_registry()
            dependencies: Optional set of issue numbers to filter to.
                         Only shows classes from these issues.
                         If None, shows all classes.
            max_fields_per_class: Maximum fields to show per class.
            max_methods_per_class: Maximum methods to show per class.

        Returns:
            Formatted markdown section for inclusion in coder prompt.
        """
        if not registry or not registry.get("modules"):
            return "**No prior modules created for this feature.**"

        modules = registry.get("modules", {})
        if not modules:
            return "**No prior modules created for this feature.**"

        lines = [
            "## Existing Classes Reference (MUST IMPORT - DO NOT RECREATE)",
            "",
            "Classes from completed issues. Import and use them - do NOT recreate:",
            "",
        ]

        classes_shown = 0
        for file_path, info in modules.items():
            issue_num = info.get("created_by_issue")

            # Filter to dependencies if specified
            if dependencies is not None and issue_num not in dependencies:
                continue

            full_path = Path(self.config.repo_root) / file_path
            if not full_path.exists():
                continue

            class_names = info.get("classes", [])
            if not class_names:
                continue

            import_path = self._path_to_module(file_path)

            for class_name in class_names:
                schema = self._extract_class_schema(full_path, class_name)
                if not schema:
                    # Fallback if schema extraction fails
                    lines.append(f"**{class_name}** (`{file_path}`, Issue #{issue_num})")
                    lines.append(f"  Import: `from {import_path} import {class_name}`")
                    lines.append("")
                    classes_shown += 1
                    continue

                # Format fields (compact)
                fields = schema.get("fields", [])
                fields_str = ", ".join(
                    f"{f['name']}: {f['type']}"
                    for f in fields[:max_fields_per_class]
                )
                if len(fields) > max_fields_per_class:
                    fields_str += f" (+{len(fields) - max_fields_per_class} more)"

                # Format methods (compact)
                methods = schema.get("methods", [])
                # Filter out dunder methods
                public_methods = [m for m in methods if not m.startswith("_")]
                methods_str = ", ".join(
                    f"{m}()" for m in public_methods[:max_methods_per_class]
                )
                if len(public_methods) > max_methods_per_class:
                    methods_str += f" (+{len(public_methods) - max_methods_per_class} more)"

                # Output compact format
                lines.append(f"**{class_name}** (`{file_path}`, Issue #{issue_num})")
                lines.append(f"  Import: `from {import_path} import {class_name}`")
                if fields_str:
                    lines.append(f"  Fields: {fields_str}")
                if methods_str:
                    lines.append(f"  Methods: {methods_str}")
                lines.append("")
                classes_shown += 1

        if classes_shown == 0:
            if dependencies:
                return "**No classes from dependency issues found.**"
            return "**No prior modules created for this feature.**"

        # Add warning
        lines.append("---")
        lines.append("**DO NOT recreate these classes. Import and use them.**")
        lines.append("If you need additional functionality, create a subclass or new class.")
        lines.append("")

        return "\n".join(lines)

    def format_module_registry_for_issue(
        self,
        registry: dict[str, Any],
        issue_dependencies: list[int],
        all_tasks: Optional[list] = None,
    ) -> str:
        """
        Format module registry with transitive dependency filtering.

        This is the recommended method for building coder context. It:
        1. Computes transitive dependencies (not just direct deps)
        2. Uses compact schema format for token efficiency
        3. Only shows classes the coder actually needs

        Args:
            registry: Module registry from StateStore.get_module_registry()
            issue_dependencies: Direct dependencies from the issue being implemented.
            all_tasks: Optional list of all tasks for computing transitive deps.
                      If provided, computes transitive closure.

        Returns:
            Formatted compact schema for inclusion in coder prompt.
        """
        # Compute transitive dependencies if we have all tasks
        if all_tasks:
            from swarm_attack.planning.dependency_graph import DependencyGraph
            graph = DependencyGraph(all_tasks)

            # Get transitive deps by unioning transitive deps of each direct dep
            all_deps: set[int] = set(issue_dependencies)
            for dep in issue_dependencies:
                all_deps.update(graph.get_transitive_dependencies(dep))
        else:
            all_deps = set(issue_dependencies)

        # Use compact schema with dependency filtering
        return self.format_module_registry_compact(
            registry,
            dependencies=all_deps if all_deps else None,
        )
