"""Tests for coder.py stdlib import handling."""
import pytest


class TestStdlibModuleWhitelist:
    """Test that stdlib modules are properly whitelisted."""

    def test_importlib_in_stdlib_modules(self):
        """Verify importlib is in STDLIB_MODULES."""
        from swarm_attack.agents.coder import CoderAgent

        assert 'importlib' in CoderAgent.STDLIB_MODULES, \
            "importlib should be in STDLIB_MODULES whitelist"

    def test_importlib_util_skipped_in_validation(self):
        """Test that importlib.util imports are skipped during validation."""
        from swarm_attack.agents.coder import CoderAgent
        from unittest.mock import MagicMock

        # Create agent with mock config
        mock_config = MagicMock()
        mock_config.repo_root = "/tmp"
        mock_config.specs_path = "/tmp/specs"

        agent = CoderAgent(config=mock_config)

        # Test content that imports from importlib.util
        test_content = '''
from importlib.util import find_spec, module_from_spec
from importlib.metadata import version

def test_something():
    pass
'''

        # Extract imports - importlib should be skipped
        imports = agent._extract_imports_from_tests_ast(test_content)

        # importlib imports should NOT be in the list (they're stdlib)
        import_modules = [module for module, _, _ in imports]
        assert 'importlib.util' not in import_modules, \
            "importlib.util should be skipped as stdlib"
        assert 'importlib.metadata' not in import_modules, \
            "importlib.metadata should be skipped as stdlib"

    def test_project_imports_still_validated(self):
        """Test that non-stdlib imports are still validated."""
        from swarm_attack.agents.coder import CoderAgent
        from unittest.mock import MagicMock

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp"
        mock_config.specs_path = "/tmp/specs"

        agent = CoderAgent(config=mock_config)

        # Test content with project imports
        test_content = '''
from myproject.models import User
from myproject.utils import helper

def test_something():
    pass
'''

        imports = agent._extract_imports_from_tests_ast(test_content)
        import_modules = [module for module, _, _ in imports]

        # Project imports SHOULD be in the list
        assert 'myproject.models' in import_modules, \
            "Project imports should be validated"
        assert 'myproject.utils' in import_modules, \
            "Project imports should be validated"
