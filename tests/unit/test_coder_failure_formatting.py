"""
Unit tests for coder agent failure formatting.

Tests that recovery_agent_plan entries are formatted prominently.
"""

import pytest
from swarm_attack.agents.coder import CoderAgent
from unittest.mock import MagicMock


class TestFormatTestFailures:
    """Tests for _format_test_failures method."""
    
    @pytest.fixture
    def coder(self):
        """Create a CoderAgent with mocked dependencies."""
        config = MagicMock()
        config.project_root = "/test"
        logger = MagicMock()
        return CoderAgent(config, logger)
    
    def test_empty_failures(self, coder):
        """Empty list returns empty string."""
        result = coder._format_test_failures([])
        assert result == ""
    
    def test_standard_test_failure(self, coder):
        """Standard test failures are formatted correctly."""
        failures = [{
            "test": "test_example",
            "class": "TestClass",
            "file": "tests/test_foo.py",
            "line": 42,
            "error": "AssertionError: expected True"
        }]
        result = coder._format_test_failures(failures)
        
        assert "TEST FAILURES FROM PREVIOUS RUN" in result
        assert "test_example" in result
        assert "TestClass" in result
        assert "tests/test_foo.py" in result
        assert "line 42" in result
        assert "AssertionError" in result
    
    def test_recovery_agent_plan_formatted_first(self, coder):
        """Recovery agent plans appear BEFORE test failures."""
        failures = [
            # Test failure first in list
            {
                "test": "test_import",
                "class": "TestImport",
                "file": "tests/test_cli.py",
                "line": 10,
                "error": "ImportError: No module"
            },
            # Recovery plan second in list
            {
                "type": "recovery_agent_plan",
                "message": "Add 'from typer.testing import CliRunner' at the top",
                "root_cause": "Missing import for CliRunner"
            }
        ]
        result = coder._format_test_failures(failures)
        
        # Recovery should appear first in output
        recovery_pos = result.find("RECOVERY INSTRUCTIONS")
        test_pos = result.find("TEST FAILURES")
        
        assert recovery_pos != -1, "Recovery section not found"
        assert test_pos != -1, "Test failures section not found"
        assert recovery_pos < test_pos, "Recovery should appear BEFORE test failures"
        
        # Recovery content should be present
        assert "from typer.testing import CliRunner" in result
        assert "Missing import for CliRunner" in result
    
    def test_recovery_plan_only(self, coder):
        """Recovery plan without test failures works."""
        failures = [{
            "type": "recovery_agent_plan",
            "message": "Fix the import statement",
            "root_cause": "Module not found"
        }]
        result = coder._format_test_failures(failures)
        
        assert "RECOVERY INSTRUCTIONS" in result
        assert "Fix the import statement" in result
        assert "Module not found" in result
        assert "TEST FAILURES" not in result  # No test failures section
    
    def test_multiple_recovery_plans(self, coder):
        """Multiple recovery plans are numbered."""
        failures = [
            {
                "type": "recovery_agent_plan",
                "message": "First fix",
                "root_cause": "Issue 1"
            },
            {
                "type": "recovery_agent_plan",
                "message": "Second fix",
                "root_cause": "Issue 2"
            }
        ]
        result = coder._format_test_failures(failures)
        
        assert "Recovery Plan 1" in result
        assert "Recovery Plan 2" in result
        assert "First fix" in result
        assert "Second fix" in result
    
    def test_suggested_actions_formatted(self, coder):
        """Suggested actions are formatted as bullet list."""
        failures = [{
            "type": "recovery_agent_plan",
            "message": "Fix imports",
            "root_cause": "Missing modules",
            "suggested_actions": ["Install typer", "Update requirements.txt"]
        }]
        result = coder._format_test_failures(failures)
        
        assert "- Install typer" in result
        assert "- Update requirements.txt" in result
    
    def test_unknown_failure_type(self, coder):
        """Unknown failure types are handled gracefully."""
        failures = [{
            "type": "some_future_type",
            "message": "Some error occurred"
        }]
        result = coder._format_test_failures(failures)
        
        assert "OTHER ERRORS" in result
        assert "some_future_type" in result
        assert "Some error occurred" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
