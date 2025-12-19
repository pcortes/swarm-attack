"""
Generated test cases for bug: test-writer-no-tests

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: coder must validate imports in GENERATED test files, not just pre-existing ones
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

# Coder validation passes when generated test imports are fully satisfied
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

# AST-based import parser correctly handles multi-line imports with parentheses
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

# AST-based import parser correctly handles aliased imports (as keyword)
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

# Integration test: CoderAgent.run() returns failure when TDD-generated tests have unsatisfied imports
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

# Verifier provides helpful error message for ImportError during test collection
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

