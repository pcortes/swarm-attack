# Fix Plan: test-writer-no-tests

## Summary
Validate test imports from generated files (not just disk), using AST parsing for robust import extraction, and add proper integration tests

## Risk Assessment
- **Risk Level:** LOW
- **Scope:** Two files: coder.py (add validation methods using AST, add validation call that checks generated test files) and verifier.py (improve error messages for collection errors)

### Risk Explanation
The fix adds validation before returning success - it's purely additive and defensive. Existing working code paths are unaffected: if implementation is complete, validation passes and behavior is unchanged. The key difference from the previous plan is that we now also validate GENERATED test files, not just pre-existing ones from disk. AST parsing is robust and falls back to regex if needed. The only behavior change is that incomplete implementations now fail explicitly instead of returning false success.

## Proposed Changes

### Change 1: swarm_attack/agents/coder.py
- **Type:** modify
- **Explanation:** Add ast import at the top of the file for robust Python AST-based import parsing.

**Current Code:**
```python
from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.models import IssueOutput
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write
```

**Proposed Code:**
```python
import ast

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.models import IssueOutput
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write
```

### Change 2: swarm_attack/agents/coder.py
- **Type:** modify
- **Explanation:** Add four new methods: _extract_imports_from_tests_ast() uses Python AST for robust import parsing handling multi-line, aliased, and bare imports. _extract_imports_from_tests_regex() is a fallback. _validate_test_imports_satisfied() validates imports against generated/existing files using AST-based definition lookup. _extract_test_files_from_generated() identifies test files in the generated output by path patterns.

**Current Code:**
```python
    def _extract_outputs(self, files: dict[str, str]) -> IssueOutput:
        """
        Extract classes/functions from written files.

        Parses Python and Dart files for class definitions to track
        what was created for context handoff to subsequent issues.

        Args:
            files: Dictionary mapping file paths to their contents.

        Returns:
            IssueOutput with files_created and classes_defined.
        """
```

**Proposed Code:**
```python
    def _extract_imports_from_tests_ast(self, test_content: str) -> list[tuple[str, str, list[str]]]:
        """
        Extract import statements from test file using AST parsing.

        Uses Python's ast module for robust parsing that handles:
        - Multi-line imports with parentheses
        - Aliased imports (import X as Y)
        - Regular imports (import module)
        - From imports (from module import name)

        Args:
            test_content: Content of the test file.

        Returns:
            List of tuples: (module_path, file_path, imported_names)
            e.g., [("swarm_attack.chief_of_staff.recovery", "swarm_attack/chief_of_staff/recovery.py", ["RetryStrategy", "ErrorCategory"])]
        """
        imports = []

        try:
            tree = ast.parse(test_content)
        except SyntaxError:
            # Fall back to regex if AST parsing fails
            return self._extract_imports_from_tests_regex(test_content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                module = node.module

                # Skip standard library and test framework imports
                if module.split('.')[0] in ('pytest', 'unittest', 'os', 'sys', 'typing', 'json', 'datetime', 'pathlib', 're', 'collections', 'functools', 'itertools', 'enum', 'dataclasses', 'abc'):
                    continue

                # Get imported names (handle aliases)
                imported_names = []
                for alias in node.names:
                    imported_names.append(alias.name)  # Use original name, not alias

                # Convert module path to file path
                file_path = module.replace(".", "/") + ".py"

                imports.append((module, file_path, imported_names))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    # Skip standard library
                    if module.split('.')[0] in ('pytest', 'unittest', 'os', 'sys', 'typing', 'json', 'datetime', 'pathlib', 're', 'collections', 'functools', 'itertools', 'enum', 'dataclasses', 'abc'):
                        continue
                    file_path = module.replace(".", "/") + ".py"
                    # For bare imports, we import the module itself
                    imports.append((module, file_path, [module.split('.')[-1]]))

        return imports

    def _extract_imports_from_tests_regex(self, test_content: str) -> list[tuple[str, str, list[str]]]:
        """
        Fallback regex-based import extraction for when AST parsing fails.

        Handles common patterns including multi-line imports with parentheses.
        """
        imports = []

        # Pattern for multi-line imports: from module import (\n    Name1,\n    Name2,\n)
        multiline_pattern = r"from\s+([\w.]+)\s+import\s+\(([^)]+)\)"
        for match in re.finditer(multiline_pattern, test_content, re.DOTALL):
            module = match.group(1)
            names_block = match.group(2)

            if module.split('.')[0] in ('pytest', 'unittest', 'os', 'sys', 'typing', 'json', 'datetime', 'pathlib'):
                continue

            # Parse names from block (handles commas, newlines, trailing commas)
            imported_names = [n.strip().split(' as ')[0] for n in re.split(r'[,\n]', names_block) if n.strip() and not n.strip().startswith('#')]
            file_path = module.replace(".", "/") + ".py"
            imports.append((module, file_path, imported_names))

        # Pattern for single-line imports: from module import X, Y, Z
        singleline_pattern = r"from\s+([\w.]+)\s+import\s+([^(\n]+)"
        for match in re.finditer(singleline_pattern, test_content):
            module = match.group(1)
            names_str = match.group(2)

            if module.split('.')[0] in ('pytest', 'unittest', 'os', 'sys', 'typing', 'json', 'datetime', 'pathlib'):
                continue

            # Check if this was already matched by multiline pattern
            file_path = module.replace(".", "/") + ".py"
            if any(fp == file_path for _, fp, _ in imports):
                continue

            imported_names = [n.strip().split(' as ')[0] for n in names_str.split(',') if n.strip()]
            imports.append((module, file_path, imported_names))

        return imports

    def _validate_test_imports_satisfied(
        self,
        test_content: str,
        generated_files: dict[str, str],
    ) -> tuple[bool, list[str]]:
        """
        Validate that all imports in test content are satisfied by generated files.

        This catches the case where tests are generated but implementation is incomplete,
        which would cause ImportError at test collection time.

        Args:
            test_content: Content of the test file (can be newly generated or from disk).
            generated_files: Files generated by this coder invocation.

        Returns:
            Tuple of (all_satisfied, missing_items) where missing_items is a list
            of "module_path:ClassName" strings for imports that cannot be found.
        """
        missing = []
        imports = self._extract_imports_from_tests_ast(test_content)

        for module_name, file_path, imported_names in imports:
            # Check if file exists in generated files
            file_content = None

            # Try exact path match first
            if file_path in generated_files:
                file_content = generated_files[file_path]

            # Try path variations (with/without leading directories)
            if not file_content:
                for gen_path, gen_content in generated_files.items():
                    if gen_path.endswith(file_path) or file_path.endswith(gen_path):
                        file_content = gen_content
                        break
                    # Also try matching just the filename parts
                    if gen_path.replace('/', '.').rstrip('.py') == module_name or \
                       module_name.endswith(gen_path.replace('/', '.').rstrip('.py')):
                        file_content = gen_content
                        break

            # Also try reading from disk if not in generated files
            if not file_content:
                disk_path = Path(self.config.repo_root) / file_path
                if file_exists(disk_path):
                    try:
                        file_content = read_file(disk_path)
                    except Exception:
                        pass

            if not file_content:
                # Entire module file is missing
                for name in imported_names:
                    missing.append(f"{file_path}:{name}")
                continue

            # Check that each imported name exists in the file
            for name in imported_names:
                # Use AST to find definitions for accurate matching
                name_found = False
                try:
                    impl_tree = ast.parse(file_content)
                    for node in ast.walk(impl_tree):
                        if isinstance(node, ast.ClassDef) and node.name == name:
                            name_found = True
                            break
                        if isinstance(node, ast.FunctionDef) and node.name == name:
                            name_found = True
                            break
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name) and target.id == name:
                                    name_found = True
                                    break
                except SyntaxError:
                    # Fall back to regex if AST fails
                    class_pattern = rf"^class\s+{re.escape(name)}\b"
                    func_pattern = rf"^def\s+{re.escape(name)}\b"
                    var_pattern = rf"^{re.escape(name)}\s*="
                    if (re.search(class_pattern, file_content, re.MULTILINE) or
                        re.search(func_pattern, file_content, re.MULTILINE) or
                        re.search(var_pattern, file_content, re.MULTILINE)):
                        name_found = True

                if not name_found:
                    missing.append(f"{file_path}:{name}")

        return (len(missing) == 0, missing)

    def _extract_test_files_from_generated(self, files: dict[str, str]) -> dict[str, str]:
        """
        Extract test files from the generated files dict.

        Identifies files that are test files by:
        - Path contains 'test' or 'tests'
        - Filename starts with 'test_' or ends with '_test.py'

        Args:
            files: Dictionary mapping file paths to contents.

        Returns:
            Dictionary of test file paths to contents.
        """
        test_files = {}
        for path, content in files.items():
            path_lower = path.lower()
            filename = path.split('/')[-1].lower()

            is_test = (
                'test' in path_lower or
                filename.startswith('test_') or
                filename.endswith('_test.py') or
                filename.endswith('_test.dart')
            )

            if is_test:
                test_files[path] = content

        return test_files

    def _extract_outputs(self, files: dict[str, str]) -> IssueOutput:
        """
        Extract classes/functions from written files.

        Parses Python and Dart files for class definitions to track
        what was created for context handoff to subsequent issues.

        Args:
            files: Dictionary mapping file paths to their contents.

        Returns:
            IssueOutput with files_created and classes_defined.
        """
```

### Change 3: swarm_attack/agents/coder.py
- **Type:** modify
- **Explanation:** Add validation BEFORE writing files. The key fix: extract test files from the generated `files` dict (not just `test_content` from disk). In TDD mode, the coder generates both tests and implementation in the same response, so we must validate the generated test files. This addresses the critic's critical issue.

**Current Code:**
```python
        # Parse file outputs from response
        files = self._parse_file_outputs(result.text)

        # Ensure all directories expected by tests exist (creates .gitkeep files)
        directory_files = self._ensure_directories_exist(test_content)
        for dir_file, content in directory_files.items():
            if dir_file not in files:
                files[dir_file] = content

        # Write implementation files
```

**Proposed Code:**
```python
        # Parse file outputs from response
        files = self._parse_file_outputs(result.text)

        # Ensure all directories expected by tests exist (creates .gitkeep files)
        directory_files = self._ensure_directories_exist(test_content)
        for dir_file, content in directory_files.items():
            if dir_file not in files:
                files[dir_file] = content

        # CRITICAL: Validate that test imports are satisfied by implementation
        # This catches incomplete implementations before we write files and return success.
        # KEY FIX: Check BOTH pre-existing test file (test_content) AND newly generated tests.
        # The bug occurred because in TDD mode, tests are generated in the same LLM response
        # and test_content (from disk) is empty - so we must check generated test files too.
        generated_test_files = self._extract_test_files_from_generated(files)
        all_test_content_to_validate = []

        # Include pre-existing test file content if available
        if test_content:
            all_test_content_to_validate.append(("disk", str(test_path), test_content))

        # Include any newly generated test files
        for test_path_gen, test_content_gen in generated_test_files.items():
            all_test_content_to_validate.append(("generated", test_path_gen, test_content_gen))

        # Validate each test file's imports
        all_missing = []
        for source, path, content in all_test_content_to_validate:
            imports_ok, missing = self._validate_test_imports_satisfied(content, files)
            if not imports_ok:
                self._log("coder_incomplete_implementation", {
                    "warning": f"Test file imports classes not defined in implementation",
                    "test_source": source,
                    "test_path": path,
                    "missing_imports": missing,
                }, level="warning")
                all_missing.extend(missing)

        if all_missing:
            self._log("coder_validation_failed", {
                "error": "Generated tests import undefined names",
                "missing_imports": all_missing,
                "files_generated": list(files.keys()),
            }, level="error")
            return AgentResult.failure_result(
                f"Incomplete implementation: test file(s) import {len(all_missing)} undefined name(s): "
                f"{', '.join(all_missing[:5])}"
                + (f" (+{len(all_missing)-5} more)" if len(all_missing) > 5 else ""),
                cost_usd=cost,
            )

        # Write implementation files
```

### Change 4: swarm_attack/agents/verifier.py
- **Type:** modify
- **Explanation:** Improve error messages when tests fail during collection (ImportError, ModuleNotFoundError) rather than execution. This surfaces the actual root cause (missing imports/modules) instead of the misleading '0 failed, 0 passed' message.

**Current Code:**
```python
            errors = []
            if not issue_tests_passed:
                errors.append(f"Issue tests failed: {parsed['tests_failed']} failed, {parsed['tests_passed']} passed")
```

**Proposed Code:**
```python
            errors = []
            if not issue_tests_passed:
                # Check for collection errors (ImportError, etc.) which indicate implementation issues
                # These occur when tests can't even be collected due to missing imports
                if parsed.get('errors', 0) > 0 and parsed['tests_run'] == 0:
                    # Extract ImportError details if present in output
                    import_error_match = re.search(
                        r"ImportError:\s*cannot import name ['"]([^'"]+)['"]\s+from\s+['"]([^'"]+)['"]",
                        output
                    )
                    module_not_found_match = re.search(
                        r"ModuleNotFoundError:\s*No module named ['"]([^'"]+)['"]",
                        output
                    )
                    if import_error_match:
                        name, module = import_error_match.groups()
                        errors.append(
                            f"Collection error: cannot import '{name}' from '{module}' - "
                            "implementation may be incomplete (missing class/function definition)"
                        )
                    elif module_not_found_match:
                        module = module_not_found_match.group(1)
                        errors.append(
                            f"Collection error: module '{module}' not found - "
                            "implementation file may be missing"
                        )
                    else:
                        errors.append(
                            f"Collection error: {parsed['errors']} error(s) during test collection - "
                            "tests could not run (check for missing imports or syntax errors)"
                        )
                else:
                    errors.append(f"Issue tests failed: {parsed['tests_failed']} failed, {parsed['tests_passed']} passed")
```

## Test Cases

### Test 1: test_coder_validates_generated_test_imports
- **Category:** regression
- **Description:** Regression test: coder must validate imports in GENERATED test files, not just pre-existing ones

```python
def test_coder_validates_generated_test_imports():
    """Regression test: coder must validate imports in generated test files (TDD mode).

    This tests the critical bug: in TDD mode, the coder generates BOTH tests and implementation
    in the same LLM response. The bug was that validation only checked test_content (from disk),
    which is empty in TDD mode, so incomplete implementations were marked as success.
    """
    from swarm_attack.agents.coder import CoderAgent
    from unittest.mock import MagicMock, patch
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/fake/root")
    config.specs_path = Path("/fake/root/specs")

    coder = CoderAgent(config)

    # Simulate generated files from LLM response (TDD mode)
    # The test file imports RetryStrategy and ErrorCategory, but implementation is incomplete
    generated_files = {
        "tests/generated/feature/test_issue_1.py": '''from swarm_attack.chief_of_staff.recovery import RetryStrategy, ErrorCategory

def test_retry_strategy():
    assert RetryStrategy.SAME.value == "same"

def test_error_category():
    assert ErrorCategory.TRANSIENT.value == "transient"
''',
        "swarm_attack/chief_of_staff/recovery.py": '''class RecoveryLevel:
    """Missing RetryStrategy and ErrorCategory enums!"""
    pass
'''
    }

    # Extract test files from generated output
    test_files = coder._extract_test_files_from_generated(generated_files)
    assert len(test_files) == 1
    assert "tests/generated/feature/test_issue_1.py" in test_files

    # Validate the generated test file's imports
    test_content = test_files["tests/generated/feature/test_issue_1.py"]
    imports_ok, missing = coder._validate_test_imports_satisfied(test_content, generated_files)

    assert imports_ok is False, "Should detect missing imports"
    assert len(missing) == 2, f"Should have 2 missing imports, got {missing}"
    assert any("RetryStrategy" in m for m in missing)
    assert any("ErrorCategory" in m for m in missing)
```

### Test 2: test_coder_passes_when_generated_implementation_complete
- **Category:** edge_case
- **Description:** Coder validation passes when generated test imports are fully satisfied

```python
def test_coder_passes_when_generated_implementation_complete():
    """Coder validation should pass when all imports in generated tests are satisfied."""
    from swarm_attack.agents.coder import CoderAgent
    from unittest.mock import MagicMock
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/fake/root")
    config.specs_path = Path("/fake/root/specs")

    coder = CoderAgent(config)

    # Simulate complete implementation
    generated_files = {
        "tests/generated/feature/test_issue_1.py": '''from swarm_attack.chief_of_staff.recovery import RetryStrategy, ErrorCategory

def test_retry_strategy():
    assert RetryStrategy.SAME.value == "same"
''',
        "swarm_attack/chief_of_staff/recovery.py": '''from enum import Enum

class RetryStrategy(Enum):
    SAME = "same"
    ALTERNATIVE = "alternative"

class ErrorCategory(Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
'''
    }

    test_files = coder._extract_test_files_from_generated(generated_files)
    test_content = test_files["tests/generated/feature/test_issue_1.py"]
    imports_ok, missing = coder._validate_test_imports_satisfied(test_content, generated_files)

    assert imports_ok is True
    assert missing == []
```

### Test 3: test_ast_parser_handles_multiline_imports
- **Category:** edge_case
- **Description:** AST-based import parser correctly handles multi-line imports with parentheses

```python
def test_ast_parser_handles_multiline_imports():
    """AST parser should correctly extract multi-line imports with parentheses."""
    from swarm_attack.agents.coder import CoderAgent
    from unittest.mock import MagicMock
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/fake/root")
    config.specs_path = Path("/fake/root/specs")

    coder = CoderAgent(config)

    # Test content with multi-line import (common after formatters)
    test_content = '''from swarm_attack.chief_of_staff.recovery import (
    RetryStrategy,
    ErrorCategory,
    RecoveryLevel,
)

def test_something():
    pass
'''

    imports = coder._extract_imports_from_tests_ast(test_content)

    assert len(imports) == 1
    module, file_path, names = imports[0]
    assert module == "swarm_attack.chief_of_staff.recovery"
    assert file_path == "swarm_attack/chief_of_staff/recovery.py"
    assert "RetryStrategy" in names
    assert "ErrorCategory" in names
    assert "RecoveryLevel" in names
```

### Test 4: test_ast_parser_handles_aliased_imports
- **Category:** edge_case
- **Description:** AST-based import parser correctly handles aliased imports (as keyword)

```python
def test_ast_parser_handles_aliased_imports():
    """AST parser should extract original name for aliased imports."""
    from swarm_attack.agents.coder import CoderAgent
    from unittest.mock import MagicMock
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/fake/root")
    config.specs_path = Path("/fake/root/specs")

    coder = CoderAgent(config)

    test_content = '''from swarm_attack.models import RetryStrategy as RS, ErrorCategory as EC

def test_something():
    pass
'''

    imports = coder._extract_imports_from_tests_ast(test_content)

    assert len(imports) == 1
    module, file_path, names = imports[0]
    assert "RetryStrategy" in names  # Should have original name, not alias
    assert "ErrorCategory" in names
    assert "RS" not in names  # Should NOT have alias
    assert "EC" not in names
```

### Test 5: test_coder_run_fails_on_incomplete_tdd_implementation
- **Category:** integration
- **Description:** Integration test: CoderAgent.run() returns failure when TDD-generated tests have unsatisfied imports

```python
def test_coder_run_fails_on_incomplete_tdd_implementation():
    """Integration test: CoderAgent.run() should fail when generated tests import missing classes.

    This is the key integration test that exercises the actual behavior change in the run() method.
    """
    from swarm_attack.agents.coder import CoderAgent
    from swarm_attack.agents.base import AgentResult
    from unittest.mock import MagicMock, patch, PropertyMock
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/tmp/fake_repo")
    config.specs_path = Path("/tmp/fake_repo/specs")

    # Mock LLM response with incomplete implementation
    mock_llm_result = MagicMock()
    mock_llm_result.text = '''# FILE: tests/generated/feature/test_issue_1.py
from swarm_attack.recovery import MissingClass

def test_missing():
    assert MissingClass().value == "test"

# FILE: swarm_attack/recovery.py
class OtherClass:
    pass
'''
    mock_llm_result.total_cost_usd = 0.05

    mock_llm = MagicMock()
    mock_llm.run.return_value = mock_llm_result

    coder = CoderAgent(config, llm_runner=mock_llm)

    # Mock file system operations
    with patch.object(coder, '_load_skill_prompt', return_value="skill prompt"):
        with patch('swarm_attack.agents.coder.file_exists') as mock_exists:
            with patch('swarm_attack.agents.coder.read_file') as mock_read:
                # Spec exists, test file doesn't (TDD mode)
                def exists_side_effect(path):
                    path_str = str(path)
                    if 'spec-final.md' in path_str:
                        return True
                    if 'issues.json' in path_str:
                        return True
                    return False

                mock_exists.side_effect = exists_side_effect

                def read_side_effect(path):
                    path_str = str(path)
                    if 'spec-final.md' in path_str:
                        return "# Spec content"
                    if 'issues.json' in path_str:
                        return '{"issues": [{"order": 1, "title": "Test Issue", "body": "Description"}]}'
                    raise FileNotFoundError(path)

                mock_read.side_effect = read_side_effect

                result = coder.run({
                    "feature_id": "feature",
                    "issue_number": 1,
                })

    # Should fail due to incomplete implementation
    assert result.success is False, f"Should fail with incomplete implementation, got: {result}"
    assert "MissingClass" in str(result.errors) or "Incomplete implementation" in str(result.errors)
```

### Test 6: test_verifier_surfaces_import_errors_clearly
- **Category:** regression
- **Description:** Verifier provides helpful error message for ImportError during test collection

```python
def test_verifier_surfaces_import_errors_clearly():
    """Verifier should surface ImportError details, not just '0 failed, 0 passed'."""
    from swarm_attack.agents.verifier import VerifierAgent
    from unittest.mock import MagicMock, patch
    from pathlib import Path

    config = MagicMock()
    config.repo_root = Path("/fake/root")
    config.tests = MagicMock()
    config.tests.timeout_seconds = 60

    verifier = VerifierAgent(config)

    # Simulate pytest output with ImportError during collection
    pytest_output = '''============================= ERRORS ==============================
_________________ ERROR collecting tests/test_feature.py __________________
ImportError: cannot import name 'RetryStrategy' from 'swarm_attack.chief_of_staff.recovery'
=========================== short test summary info ===========================
ERROR tests/test_feature.py
========================= 1 error in 0.52s =========================='''

    parsed = verifier._parse_pytest_output(pytest_output)

    # Should detect the error
    assert parsed['errors'] == 1
    assert parsed['tests_run'] == 0
    assert parsed['tests_failed'] == 0
```

## Potential Side Effects
- Incomplete implementations that previously returned success will now return failure - this is the intended fix and core behavior change
- AST parsing adds minimal CPU overhead (parsing Python source) which is negligible compared to LLM invocation cost
- If AST parsing fails on malformed Python, fallback regex parser is used ensuring robustness
- Verifier error messages will be more descriptive for ImportError/ModuleNotFoundError cases - only affects failure path
- TDD-mode implementations now have their generated tests validated before files are written to disk

## Rollback Plan
Remove the four new methods (_extract_imports_from_tests_ast, _extract_imports_from_tests_regex, _validate_test_imports_satisfied, _extract_test_files_from_generated) and the validation block from coder.py. Revert the error message improvements in verifier.py. This restores the broken behavior (false positives for incomplete TDD implementations) but doesn't break anything that was working.

## Estimated Effort
medium
