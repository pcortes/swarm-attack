"""
Implementation Agent (Coder) for Feature Swarm.

This is the thick-agent implementation that handles the full TDD workflow:
1. Reads context (issue, spec, integration points)
2. Writes tests first (RED phase)
3. Implements code (GREEN phase)
4. Iterates until all tests pass

Uses the coder skill via Claude CLI to generate both tests and implementation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class CoderAgent(BaseAgent):
    """
    Agent that implements code to make tests pass.

    Follows TDD principles: tests exist first, implementation comes second.
    """

    name = "coder"

    # Protected paths that should never be overwritten by generated code
    # These are the tool's own codebase directories
    PROTECTED_PATHS = [
        "swarm_attack/",
        ".claude/",
        ".swarm/",
        ".git/",
    ]

    # Internal features that ARE part of swarm-attack itself
    # These features CAN write to swarm_attack/ directory (bypassing protection)
    INTERNAL_FEATURES = frozenset([
        "chief-of-staff",
    ])

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Coder agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _is_protected_path(self, file_path: str, feature_id: str = "") -> bool:
        """
        Check if a file path is in a protected directory.

        Protected paths include the tool's own codebase (swarm_attack/),
        configuration directories (.claude/, .swarm/), and git internals.

        Internal features (those in INTERNAL_FEATURES) bypass protection for
        swarm_attack/ since they ARE part of the tool itself.

        Args:
            file_path: Relative file path to check.
            feature_id: The feature being implemented (used to check if internal).

        Returns:
            True if the path is protected and should not be written to.
        """
        # Normalize the path - only strip leading "./" not just "."
        normalized = file_path.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]

        # Internal features can write to swarm_attack/ (they ARE part of it)
        if feature_id in self.INTERNAL_FEATURES:
            # Still protect .git/ even for internal features
            return normalized.startswith(".git/")

        for protected in self.PROTECTED_PATHS:
            if normalized.startswith(protected):
                return True
        return False

    def _rewrite_protected_path(self, file_path: str, feature_id: str) -> str:
        """
        Rewrite a protected path to use the feature's output directory.

        If the LLM tries to write to swarm_attack/models/user.py,
        this rewrites it to <feature_id>/models/user.py instead.

        Internal features (those in INTERNAL_FEATURES) do NOT get rewritten
        since they ARE part of swarm_attack/ by design.

        Args:
            file_path: Original file path from LLM output.
            feature_id: The feature being implemented.

        Returns:
            Rewritten path in the feature output directory, or original path
            for internal features.
        """
        # Internal features: no rewriting needed (they write to swarm_attack/)
        if feature_id in self.INTERNAL_FEATURES:
            return file_path

        # Normalize the path - only strip leading "./" not just "."
        normalized = file_path.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]

        for protected in self.PROTECTED_PATHS:
            if normalized.startswith(protected):
                # Strip the protected prefix and prepend feature_id
                remainder = normalized[len(protected):]
                return f"{feature_id}/{remainder}"

        return file_path

    def _get_spec_path(self, feature_id: str) -> Path:
        """Get the path to the spec-final.md file."""
        return self.config.specs_path / feature_id / "spec-final.md"

    def _get_issues_path(self, feature_id: str) -> Path:
        """Get the path to the issues.json file."""
        return self.config.specs_path / feature_id / "issues.json"

    def _get_default_test_path(
        self,
        feature_id: str,
        issue_number: int,
        project_info: Optional[dict[str, str]] = None,
    ) -> Path:
        """
        Get the default path for generated tests.

        Uses project_info to determine the correct test directory and extension
        for the project type (Python, Flutter, Node.js, etc).

        Args:
            feature_id: The feature identifier
            issue_number: The issue order number
            project_info: Optional project type info dict from _detect_project_type()

        Returns:
            Path to the test file
        """
        if project_info:
            test_dir = project_info.get("test_dir", "tests/generated")
            test_ext = project_info.get("test_ext", ".py")
        else:
            # Default to Python/swarm standard
            test_dir = "tests/generated"
            test_ext = ".py"

        tests_dir = Path(self.config.repo_root) / test_dir / feature_id
        return tests_dir / f"test_issue_{issue_number}{test_ext}"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt, stripping YAML frontmatter.

        The skill file may contain YAML frontmatter with metadata like
        'allowed-tools: Read,Glob,Bash,Write,Edit'. Since we run with
        allowed_tools=[] (no tools), this frontmatter can confuse Claude
        into attempting tool use, burning through max_turns.

        We use load_skill_with_metadata() from BaseAgent to strip frontmatter.
        """
        if self._skill_prompt is None:
            content, _ = self.load_skill_with_metadata("coder")
            self._skill_prompt = content
        return self._skill_prompt

    def _load_issues(self, feature_id: str) -> dict[str, Any]:
        """Load the issues.json file for a feature."""
        issues_path = self._get_issues_path(feature_id)
        if not file_exists(issues_path):
            raise FileNotFoundError(f"Issues file not found at {issues_path}")

        content = read_file(issues_path)
        return json.loads(content)

    def _find_issue(
        self, issues_data: dict[str, Any], issue_number: int
    ) -> Optional[dict[str, Any]]:
        """Find a specific issue by its order number."""
        issues = issues_data.get("issues", [])
        for issue in issues:
            if issue.get("order") == issue_number:
                return issue
        return None

    def _extract_expected_modules(self, test_content: str) -> list[str]:
        """
        Extract module paths from import statements.

        Parses the test file to find what modules it imports,
        which tells us what files need to be created.

        Args:
            test_content: Content of the test file.

        Returns:
            List of module paths (e.g., ["src/auth/signup.py"]).
        """
        # Match: from src.auth.signup import signup
        import_pattern = r"from\s+([\w.]+)\s+import"
        matches = re.findall(import_pattern, test_content)

        modules = []
        for match in matches:
            # Skip standard library and pytest imports
            if match.startswith(("pytest", "unittest", "os", "sys", "typing")):
                continue
            # Convert module path to file path: src.auth.signup -> src/auth/signup.py
            module_path = match.replace(".", "/") + ".py"
            modules.append(module_path)

        return modules

    def _extract_expected_directories(self, test_content: str) -> list[str]:
        """
        Extract directory paths from is_dir() assertions in tests.

        Looks for patterns like:
        - models_path = Path.cwd() / "lib" / "models" followed by models_path.is_dir()
        - Path.cwd() / "lib" / "models" directly with is_dir()

        Args:
            test_content: Content of the test file.

        Returns:
            List of directory paths (e.g., ["lib/models", "lib/widgets"]).
        """
        directories = set()

        # Pattern 1: Find variable definitions like:
        # models_path = Path.cwd() / "lib" / "models"
        # These are typically followed by .is_dir() assertions elsewhere
        var_def_pattern = r'(\w+_path)\s*=\s*Path\.cwd\(\)\s*/\s*"lib"\s*/\s*"([^"]+)"'
        for match in re.finditer(var_def_pattern, test_content):
            var_name = match.group(1)
            dirname = match.group(2)
            # Only if it's used with is_dir() somewhere
            if f"{var_name}.is_dir()" in test_content and '.' not in dirname:
                directories.add(f"lib/{dirname}")

        # Pattern 2: Direct Path.cwd() / "lib" / "dirname" with is_dir() on same line
        direct_pattern = r'Path\.cwd\(\)\s*/\s*"lib"\s*/\s*"([^"]+)"[^.]*\.is_dir\(\)'
        for match in re.finditer(direct_pattern, test_content):
            dirname = match.group(1)
            if '.' not in dirname:
                directories.add(f"lib/{dirname}")

        # Pattern 3: Look for common Flutter directory patterns in test names
        flutter_dirs = ["screens", "controllers", "services", "models", "widgets"]
        for dir_name in flutter_dirs:
            # Look for explicit directory tests like test_lib_models_directory_exists
            if f"test_lib_{dir_name}_directory" in test_content.lower() or \
               f"test_{dir_name}_directory" in test_content.lower():
                directories.add(f"lib/{dir_name}")

        return sorted(directories)

    def _ensure_directories_exist(self, test_content: str) -> dict[str, str]:
        """
        Create .gitkeep files for directories expected by tests.

        Returns:
            Dictionary mapping file paths to content (empty for .gitkeep).
        """
        directories = self._extract_expected_directories(test_content)
        files = {}
        for dir_path in directories:
            gitkeep_path = f"{dir_path}/.gitkeep"
            files[gitkeep_path] = ""
        return files

    def _parse_file_outputs(self, llm_response: str) -> dict[str, str]:
        """
        Parse LLM response into file path -> content mapping.

        Supports multiple formats and languages (Python, Dart, TypeScript, etc.):
        - # FILE: path/to/file.ext followed by content (preferred)
        - #FILE: path/to/file.ext (no space)
        - Code fences with path comments: # path/to/file.py or // path/to/file.dart

        Args:
            llm_response: Raw response from LLM.

        Returns:
            Dictionary mapping file paths to their contents.
        """
        files: dict[str, str] = {}

        if not llm_response.strip():
            self._log("coder_parse_warning", {
                "warning": "Empty LLM response",
            }, level="warning")
            return files

        # Pattern 1: # FILE: path/to/file.ext followed by content until next FILE or end
        # Handles both "# FILE:" and "#FILE:" formats - works for ALL languages
        file_marker_pattern = r"#\s*FILE:\s*([^\n]+)\n([\s\S]*?)(?=#\s*FILE:|$)"
        matches = re.findall(file_marker_pattern, llm_response, re.IGNORECASE)

        if matches:
            for path, content in matches:
                path = path.strip()
                content = content.strip()
                if path and content:
                    files[path] = content
            return files

        # Pattern 2: Code fence with path comment at the start (multi-language)
        # Supports: ```dart\n// path.dart\n OR ```python\n# path.py\n
        # Comment markers: # (Python/Shell/Ruby) or // (Dart/JS/TS/C/Go/Rust)
        fence_pattern = r"```(?:\w+)?\s*\n(?:#|//)\s*([^\n]+\.\w+)\s*\n([\s\S]*?)```"
        fence_matches = re.findall(fence_pattern, llm_response)

        if fence_matches:
            for path, content in fence_matches:
                path = path.strip()
                content = content.strip()
                if path and content:
                    files[path] = content
            return files

        # Pattern 3: Plain code fence extraction (fallback)
        # Try to extract from standard code fences with any language
        code_fence_pattern = r"```(?:\w+)?\s*([\s\S]*?)\s*```"
        code_matches = re.findall(code_fence_pattern, llm_response)

        if code_matches:
            # Look for path comment in the first line of each block
            for content in code_matches:
                lines = content.strip().split("\n")
                if lines:
                    first_line = lines[0].strip()
                    # Check if first line looks like a path comment
                    # Supports # (Python) or // (Dart/JS/C) comment styles
                    # Matches any file extension (.py, .dart, .ts, .yaml, etc.)
                    path_match = re.match(r"(?:#|//)\s*(\S+\.\w+)\s*$", first_line)
                    if path_match:
                        path = path_match.group(1)
                        file_content = "\n".join(lines[1:]).strip()
                        if path and file_content:
                            files[path] = file_content

        # Log warning if no files were parsed
        if not files:
            preview = llm_response[:500] if len(llm_response) > 500 else llm_response
            self._log("coder_parse_warning", {
                "warning": "No files parsed from LLM response",
                "response_length": len(llm_response),
                "response_preview": preview,
            }, level="warning")

        return files

    def _detect_project_type(self, spec_content: str, test_content: str) -> dict[str, str]:
        """
        Detect project type from spec and test content.

        Returns dict with:
            - type: Project type name
            - source_dir: Source code directory
            - file_ext: Source file extension
            - structure: Directory structure hints
            - test_dir: Test directory for generated tests
            - test_ext: Test file extension
            - test_command: Command to run tests
            - code_fence: Code fence language for prompts
        """
        combined = spec_content.lower() + test_content.lower()

        if "flutter" in combined or ".dart" in combined or "pubspec.yaml" in combined:
            return {
                "type": "Flutter/Dart",
                "source_dir": "lib/",
                "file_ext": ".dart",
                "structure": "lib/screens/, lib/controllers/, lib/services/, lib/models/, lib/widgets/",
                "test_dir": "test",  # Flutter standard test directory
                "test_ext": ".dart",
                "test_command": "flutter test",
                "code_fence": "dart",
            }
        elif "package.json" in combined or "node" in combined or ".ts" in combined:
            return {
                "type": "Node.js/TypeScript",
                "source_dir": "src/",
                "file_ext": ".ts",
                "structure": "src/",
                "test_dir": "tests",
                "test_ext": ".ts",
                "test_command": "npm test",
                "code_fence": "typescript",
            }
        else:
            return {
                "type": "Python",
                "source_dir": "src/",
                "file_ext": ".py",
                "structure": "src/",
                "test_dir": "tests/generated",  # Swarm standard location
                "test_ext": ".py",
                "test_command": "pytest",
                "code_fence": "python",
            }

    def _format_test_failures(self, failures: list[dict[str, Any]]) -> str:
        """
        Format test failures for inclusion in the prompt.

        Args:
            failures: List of failure dictionaries from VerifierAgent.

        Returns:
            Formatted string describing the failures.
        """
        if not failures:
            return ""

        lines = ["## ⚠️ TEST FAILURES FROM PREVIOUS RUN", ""]
        lines.append(f"**{len(failures)} test(s) failed.** You must fix these specific issues:")
        lines.append("")

        for i, failure in enumerate(failures, 1):
            test_name = failure.get("test", "unknown")
            test_class = failure.get("class", "")
            file_path = failure.get("file", "unknown")
            line_num = failure.get("line", "?")
            error_msg = failure.get("error", "Unknown error")

            full_test_name = f"{test_class}::{test_name}" if test_class else test_name

            lines.append(f"### Failure {i}: `{full_test_name}`")
            lines.append(f"**File:** `{file_path}` line {line_num}")
            lines.append(f"**Error:** {error_msg}")
            lines.append("")

        lines.append("**IMPORTANT:** Focus on fixing THESE SPECIFIC failures. Do not rewrite working code.")
        lines.append("")

        return "\n".join(lines)

    def _format_existing_implementation(self, existing: dict[str, str]) -> str:
        """
        Format existing implementation files for inclusion in the prompt.

        Args:
            existing: Dictionary mapping file paths to their contents.

        Returns:
            Formatted string showing existing implementation.
        """
        if not existing:
            return ""

        lines = ["## 📁 YOUR PREVIOUS IMPLEMENTATION", ""]
        lines.append("You already wrote the following code. **Iterate on it, don't rewrite from scratch.**")
        lines.append("Only modify what's needed to fix the failing tests.")
        lines.append("")

        for path, content in existing.items():
            # Truncate very long files to avoid token limits
            truncated = content[:5000] if len(content) > 5000 else content
            was_truncated = len(content) > 5000

            lines.append(f"### `{path}`")
            lines.append("```")
            lines.append(truncated)
            if was_truncated:
                lines.append("... (truncated)")
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def _format_test_section(
        self,
        test_content: str,
        test_path: Optional[Path],
        code_fence_lang: str,
    ) -> str:
        """
        Format the test section for the prompt.

        Handles two cases:
        1. Test file exists: Show the test content
        2. Test file missing: Instruct coder to create tests (TDD mode)

        Args:
            test_content: Content of the test file (empty if not exists)
            test_path: Path where test file should be created
            code_fence_lang: Language for code fence (python, dart, typescript)

        Returns:
            Formatted string for test section in prompt.
        """
        if test_content:
            # Test file exists - show content
            return f"""**Existing Test Content (your implementation must make these tests pass):**

```{code_fence_lang}
{test_content}
```"""
        else:
            # No test file - instruct coder to create tests (TDD mode)
            test_path_str = str(test_path) if test_path else "tests/generated/<feature>/test_issue_<N>.py"
            return f"""**No Test File Found - TDD Mode Active**

You must CREATE tests as part of your implementation. This is TDD (Test-Driven Development):

1. **First, create the test file at:** `{test_path_str}`
2. Write tests that verify the acceptance criteria in the issue
3. Then implement code to make those tests pass

Your output MUST include the test file using:
```
# FILE: {test_path_str}
```

Test Requirements:
- Write tests that verify all acceptance criteria
- Tests should be comprehensive but focused
- Use appropriate test framework ({code_fence_lang} tests for this project)
- Include edge cases mentioned in the issue"""

    def _format_spec_context(self, spec_content: str) -> str:
        """
        Format spec context for prompt - truncate large specs.

        Large specs (>20k chars) blow up the prompt and cause max_turns errors.
        The issue body should be self-contained with all needed context.

        Args:
            spec_content: Full spec content.

        Returns:
            Formatted spec section or empty string for large specs.
        """
        # 20k chars ~= 5k tokens - leave room for issue, skill prompt, and output
        MAX_SPEC_CHARS = 20000

        if len(spec_content) <= MAX_SPEC_CHARS:
            return f"""**Engineering Spec Context:**

```markdown
{spec_content}
```"""
        else:
            # Large spec - issue body should have all context needed
            return """**Note:** Full spec is large ({:,} chars). Issue body contains relevant context.
Refer to spec sections mentioned in issue body if needed.""".format(len(spec_content))

    def _build_prompt(
        self,
        feature_id: str,
        issue: dict[str, Any],
        spec_content: str,
        test_content: str,
        expected_modules: list[str],
        retry_number: int = 0,
        test_failures: Optional[list[dict[str, Any]]] = None,
        existing_implementation: Optional[dict[str, str]] = None,
        test_path: Optional[Path] = None,
    ) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        modules_str = "\n".join(f"- {m}" for m in expected_modules) if expected_modules else "- (Infer from test imports)"

        # Detect project type for better context
        project_info = self._detect_project_type(spec_content, test_content)

        # Determine code fence language based on project type
        code_fence_lang = "python"
        if project_info["type"] == "Flutter/Dart":
            code_fence_lang = "dart"
        elif project_info["type"] == "Node.js/TypeScript":
            code_fence_lang = "typescript"

        # Build failure and existing implementation sections (for retries)
        failures_section = self._format_test_failures(test_failures or [])
        existing_section = self._format_existing_implementation(existing_implementation or {})

        # Retry context
        retry_context = ""
        if retry_number > 0:
            retry_context = f"""
**⚠️ RETRY ATTEMPT #{retry_number}**
This is NOT your first attempt. Your previous implementation had failing tests.
Review the failures below and make TARGETED fixes. DO NOT rewrite everything.
"""

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}
{retry_context}

**Project Type:** {project_info['type']}
**Source Directory:** {project_info['source_dir']}
**File Extension:** {project_info['file_ext']}
**Directory Structure:** {project_info['structure']}

{failures_section}

{existing_section}

**Issue to Implement:**

Title: {issue.get('title', 'Unknown')}

{issue.get('body', 'No description')}

**Labels:** {', '.join(issue.get('labels', []))}
**Estimated Size:** {issue.get('estimated_size', 'medium')}

**Test File:**
{self._format_test_section(test_content, test_path, code_fence_lang)}

**Expected Module Paths (based on test imports):**
{modules_str}

{self._format_spec_context(spec_content)}

---

## Your Task

Implement production code that makes ALL tests in the test file pass.

CRITICAL REQUIREMENTS:
1. Output files using `# FILE: path/to/file.ext` markers (use correct extension for project type)
2. DO NOT use Write or Edit tools - output code as text only
3. Create files in {project_info['source_dir']} directory structure
4. Analyze tests to understand what files and content they expect
5. If tests check Path.cwd() / "path", create files at that exact path

IMPORTANT - Read the tests carefully for ALL path assertions:
- Look for `Path.cwd() / "path" / "to" / "dir"` -> create corresponding directory with .gitkeep
- For EVERY directory existence test, create a .gitkeep file in that directory
- For EVERY file existence test, create that file with appropriate content

Requirements:
1. Analyze the test file to understand expected behavior
2. Create ALL files and directories that tests check for
3. For directory existence tests, create a .gitkeep file in that directory
4. Implement all functions/classes that tests expect
5. Handle all edge cases that tests check for
6. Follow existing code patterns in the spec

Output Format:
- Use `# FILE: path/to/file.ext` markers for each file
- Output ONLY implementation code, no explanations
- Create all necessary files to make tests pass
- For directories, output `# FILE: path/to/dir/.gitkeep` with empty content

CRITICAL: Your output MUST start with `# FILE:` markers. Examples:

Python Example:
# FILE: src/services/processor.py
class Processor:
    def process(self, data):
        return data.upper()

# FILE: src/models/__init__.py
from .user import User

Flutter/Dart Example:
# FILE: lib/services/my_service.dart
class MyService {{
  bool _active = false;
  bool get isActive => _active;
}}

DO NOT use code fences (```). DO NOT add explanatory text before the files.
Start your response IMMEDIATELY with `# FILE:` followed by the first file path.
"""

    def _extract_implementation_paths_from_tests(self, test_content: str) -> list[str]:
        """
        Extract expected file paths from test content.

        Looks for patterns like:
        - Path.cwd() / "lib" / "widgets" / "transcription_display.dart"
        - Path.cwd() / "lib" / "models" / "transcription_state.dart"

        Returns list of relative file paths.
        """
        paths = []

        # Pattern: Path.cwd() / "lib" / "..." / "filename.ext"
        # Capture all path segments after Path.cwd()
        pattern = r'Path\.cwd\(\)\s*/\s*"([^"]+)"(?:\s*/\s*"([^"]+)")*'

        # More specific pattern for file paths (ends with .dart, .py, etc.)
        file_pattern = r'Path\.cwd\(\)\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"\s*/\s*"([^"]+\.\w+)"'
        for match in re.finditer(file_pattern, test_content):
            path = "/".join(match.groups())
            if path not in paths:
                paths.append(path)

        # Also try 2-segment paths
        two_segment_pattern = r'Path\.cwd\(\)\s*/\s*"([^"]+)"\s*/\s*"([^"]+\.\w+)"'
        for match in re.finditer(two_segment_pattern, test_content):
            path = "/".join(match.groups())
            if path not in paths:
                paths.append(path)

        return paths

    def _read_existing_implementation(
        self, test_content: str, expected_modules: list[str]
    ) -> dict[str, str]:
        """
        Read existing implementation files that the coder previously created.

        Args:
            test_content: Test file content to extract expected paths.
            expected_modules: Module paths from test imports.

        Returns:
            Dictionary mapping file paths to their contents.
        """
        existing: dict[str, str] = {}

        # Collect all potential file paths
        paths_to_check = set()

        # From test imports (expected_modules)
        for module in expected_modules:
            paths_to_check.add(module)

        # From test assertions (Path.cwd() / "lib" / ... patterns)
        for path in self._extract_implementation_paths_from_tests(test_content):
            paths_to_check.add(path)

        # Read each file if it exists
        for rel_path in paths_to_check:
            full_path = Path(self.config.repo_root) / rel_path
            if file_exists(full_path):
                try:
                    content = read_file(full_path)
                    # Only include non-empty files that aren't .gitkeep
                    if content.strip() and not rel_path.endswith(".gitkeep"):
                        existing[rel_path] = content
                except Exception:
                    pass  # Skip files we can't read

        return existing

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Generate implementation code for a specific issue.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - issue_number: The issue order number (required)
                - test_path: Optional path to test file (defaults to standard location)
                - retry_number: Retry attempt number (0 = first attempt)
                - test_failures: List of failure details from previous verifier run

        Returns:
            AgentResult with:
                - success: True if implementation was generated
                - output: Dict with files_created, files_modified, etc.
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        issue_number = context.get("issue_number")
        if issue_number is None:
            return AgentResult.failure_result("Missing required context: issue_number")

        # NEW: Extract retry context
        retry_number = context.get("retry_number", 0)
        test_failures = context.get("test_failures", [])

        self._log("coder_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "retry_number": retry_number,
            "failure_count": len(test_failures),
        })
        self.checkpoint("started")

        # Determine test file path
        test_path_str = context.get("test_path")
        if test_path_str:
            test_path = Path(test_path_str)
        else:
            test_path = self._get_default_test_path(feature_id, issue_number)

        # Read test file content IF IT EXISTS (TDD: coder creates tests if missing)
        test_content = ""
        test_file_exists = file_exists(test_path)
        if test_file_exists:
            try:
                test_content = read_file(test_path)
            except Exception as e:
                # Log but don't fail - we can still generate tests
                self._log("coder_warning", {
                    "warning": f"Could not read existing test file: {e}",
                    "test_path": str(test_path),
                }, level="warning")
        else:
            self._log("coder_no_test_file", {
                "message": "Test file not found - coder will create tests (TDD mode)",
                "test_path": str(test_path),
            })

        # Extract expected modules from test imports
        expected_modules = self._extract_expected_modules(test_content)

        # Check if spec exists
        spec_path = self._get_spec_path(feature_id)
        if not file_exists(spec_path):
            error = f"Spec not found at {spec_path}"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read spec content
        try:
            spec_content = read_file(spec_path)
        except Exception as e:
            error = f"Failed to read spec: {e}"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load issues
        try:
            issues_data = self._load_issues(feature_id)
        except FileNotFoundError as e:
            error = str(e)
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except json.JSONDecodeError as e:
            error = f"Failed to parse issues.json: {e}"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Find the specific issue
        issue = self._find_issue(issues_data, issue_number)
        if not issue:
            error = f"Issue {issue_number} not found in issues.json"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Check if this is a manual task (cannot be automated)
        automation_type = issue.get("automation_type", "automated")
        if automation_type == "manual":
            self._log("coder_manual_task", {
                "issue_number": issue_number,
                "title": issue.get("title", ""),
                "message": "Task requires manual human verification - cannot be automated",
            })
            return AgentResult.failure_result(
                f"Issue #{issue_number} requires manual verification and cannot be automated. "
                f"Title: {issue.get('title', 'Unknown')}. "
                "Mark this task as MANUAL_REQUIRED or complete it manually."
            )

        self.checkpoint("context_loaded")

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("coder_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        # NEW: Read existing implementation on retry
        existing_implementation: dict[str, str] = {}
        if retry_number > 0:
            existing_implementation = self._read_existing_implementation(
                test_content, expected_modules
            )
            self._log("coder_existing_impl", {
                "retry_number": retry_number,
                "existing_files": list(existing_implementation.keys()),
            })

        # Build prompt and invoke Claude
        prompt = self._build_prompt(
            feature_id,
            issue,
            spec_content,
            test_content,
            expected_modules,
            retry_number=retry_number,
            test_failures=test_failures,
            existing_implementation=existing_implementation,
            test_path=test_path,
        )

        try:
            # No tools - all context is in prompt, just generate code with # FILE: markers
            # Using Write/Edit tools causes result.text to be empty, breaking file parsing
            # max_turns=10 allows for large code output generation
            result = self.llm.run(
                prompt,
                allowed_tools=[],
                max_turns=10,
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("coder_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse file outputs from response
        files = self._parse_file_outputs(result.text)

        # Ensure all directories expected by tests exist (creates .gitkeep files)
        directory_files = self._ensure_directories_exist(test_content)
        for dir_file, content in directory_files.items():
            if dir_file not in files:
                files[dir_file] = content

        # Write implementation files
        files_created: list[str] = []
        files_modified: list[str] = []
        paths_rewritten: list[tuple[str, str]] = []  # (original, rewritten) for logging

        for file_path, content in files.items():
            try:
                # Check if path is protected and rewrite if necessary
                # Internal features (like chief-of-staff) bypass protection for swarm_attack/
                original_path = file_path
                if self._is_protected_path(file_path, feature_id):
                    file_path = self._rewrite_protected_path(file_path, feature_id)
                    paths_rewritten.append((original_path, file_path))
                    self._log("coder_path_rewrite", {
                        "original": original_path,
                        "rewritten": file_path,
                        "reason": "Protected path - redirecting to feature output directory",
                    }, level="warning")

                full_path = Path(self.config.repo_root) / file_path
                is_new = not file_exists(full_path)

                ensure_dir(full_path.parent)
                safe_write(full_path, content)

                if is_new:
                    files_created.append(file_path)
                else:
                    files_modified.append(file_path)
            except Exception as e:
                error = f"Failed to write file {file_path}: {e}"
                self._log("coder_error", {"error": error}, level="error")
                return AgentResult.failure_result(error, cost_usd=cost)

        # Log summary of path rewrites if any occurred
        if paths_rewritten:
            self._log("coder_protected_paths", {
                "count": len(paths_rewritten),
                "rewrites": paths_rewritten,
                "message": f"Redirected {len(paths_rewritten)} file(s) from protected paths to feature directory",
            }, level="warning")

        self.checkpoint("files_written", cost_usd=0)

        # Generate summary
        implementation_summary = self._generate_summary(files_created, files_modified, issue)

        # Success
        self._log(
            "coder_complete",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "files_created": files_created,
                "files_modified": files_modified,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "feature_id": feature_id,
                "issue_number": issue_number,
                "files_created": files_created,
                "files_modified": files_modified,
                "implementation_summary": implementation_summary,
            },
            cost_usd=cost,
        )

    def _generate_summary(
        self,
        files_created: list[str],
        files_modified: list[str],
        issue: dict[str, Any],
    ) -> str:
        """Generate a summary of the implementation."""
        parts = []

        if files_created:
            parts.append(f"Created {len(files_created)} file(s): {', '.join(files_created)}")
        if files_modified:
            parts.append(f"Modified {len(files_modified)} file(s): {', '.join(files_modified)}")

        issue_title = issue.get("title", "Unknown issue")
        parts.append(f"Implementation for: {issue_title}")

        return ". ".join(parts)
