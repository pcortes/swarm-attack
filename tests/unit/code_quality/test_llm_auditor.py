"""Tests for LLMAuditor - LLM-specific code issue detection.

This tests the detection of:
- Hallucinated imports (non-existent modules)
- Hallucinated APIs (non-existent method calls)
- Incomplete implementations (TODO/FIXME comments)
- Swallowed exceptions (empty except blocks)
- Placeholder returns (return None, {}, 0 as stubs)
"""

import ast
import tempfile
from pathlib import Path

import pytest

from swarm_attack.code_quality.llm_auditor import LLMAuditor
from swarm_attack.code_quality.models import Severity, Category


class TestHallucinatedImports:
    """Tests for hallucinated import detection."""

    def test_detects_nonexistent_module_import(self, tmp_path: Path) -> None:
        """Detects import of a module that doesn't exist."""
        code = '''
from swarm_attack.utils.magic_helper import do_magic
from nonexistent_package.fake_module import FakeClass
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # Should detect at least 2 hallucinated imports
        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        assert len(hallucination_findings) >= 2

        # All should be CRITICAL severity
        for finding in hallucination_findings:
            assert finding.severity == Severity.CRITICAL
            assert "hallucinated" in finding.title.lower() or "non-existent" in finding.description.lower()

    def test_allows_valid_stdlib_imports(self, tmp_path: Path) -> None:
        """Does not flag valid standard library imports."""
        code = '''
import os
import sys
from pathlib import Path
from typing import Optional, List
from collections import defaultdict
import json
import re
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # Should have no hallucination findings for valid stdlib
        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        assert len(hallucination_findings) == 0

    def test_allows_valid_third_party_imports(self, tmp_path: Path) -> None:
        """Does not flag valid third-party imports (like pytest)."""
        code = '''
import pytest
from pathlib import Path
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        assert len(hallucination_findings) == 0

    def test_detects_hallucinated_relative_import(self, tmp_path: Path) -> None:
        """Detects relative imports of non-existent modules."""
        code = '''
from .nonexistent_sibling import helper_function
from ..parent.nonexistent_module import ParentClass
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # Relative imports to non-existent modules should be flagged
        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        assert len(hallucination_findings) >= 1

    def test_handles_import_alias(self, tmp_path: Path) -> None:
        """Correctly handles aliased imports."""
        code = '''
import numpy as np
from fake_module import FakeClass as FC
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # numpy is valid, fake_module is not
        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        # Should detect fake_module
        assert len(hallucination_findings) >= 1


class TestIncompleteImplementations:
    """Tests for incomplete implementation detection (TODO/FIXME)."""

    def test_detects_todo_comments(self, tmp_path: Path) -> None:
        """Detects TODO comments indicating incomplete work."""
        code = '''
def process_data(data):
    # TODO: implement validation
    # TODO: add error handling
    return data
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        incomplete_findings = [
            f for f in findings if f.category == Category.INCOMPLETE
        ]
        assert len(incomplete_findings) >= 2

        for finding in incomplete_findings:
            assert finding.severity == Severity.HIGH

    def test_detects_fixme_comments(self, tmp_path: Path) -> None:
        """Detects FIXME comments indicating bugs to fix."""
        code = '''
def calculate_total(items):
    # FIXME: this doesn't handle negative values
    total = sum(items)
    return total
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        incomplete_findings = [
            f for f in findings if f.category == Category.INCOMPLETE
        ]
        assert len(incomplete_findings) >= 1

    def test_detects_xxx_and_hack_comments(self, tmp_path: Path) -> None:
        """Detects XXX and HACK comments."""
        code = '''
def quick_fix():
    # XXX: this is a temporary workaround
    # HACK: bypassing validation for now
    return True
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        incomplete_findings = [
            f for f in findings if f.category == Category.INCOMPLETE
        ]
        assert len(incomplete_findings) >= 2

    def test_detects_placeholder_returns(self, tmp_path: Path) -> None:
        """Detects placeholder return values indicating stub code."""
        code = '''
def get_user_data(user_id):
    # This should fetch from database
    return None

def get_config():
    return {}

def count_items():
    return 0
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # Should detect placeholder returns but not overflag
        incomplete_findings = [
            f for f in findings if f.category == Category.INCOMPLETE
        ]
        # We expect at least some placeholder detections
        # Note: This can be tricky as sometimes return None is valid
        assert len(incomplete_findings) >= 1

    def test_allows_valid_none_returns(self, tmp_path: Path) -> None:
        """Does not flag legitimate None returns."""
        code = '''
def find_item(items, target):
    """Find an item in the list, return None if not found."""
    for item in items:
        if item == target:
            return item
    return None  # Legitimate - item not found
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # This is a legitimate None return with context
        # The auditor should be smart about this
        # Placeholder detection is inherently heuristic
        # We don't want false positives here
        incomplete_findings = [
            f for f in findings if f.category == Category.INCOMPLETE
        ]
        # Should not flag this as incomplete
        assert len(incomplete_findings) == 0


class TestSwallowedExceptions:
    """Tests for swallowed exception detection."""

    def test_detects_empty_except_block(self, tmp_path: Path) -> None:
        """Detects empty except blocks that swallow errors."""
        code = '''
def risky_operation():
    try:
        do_something()
    except:
        pass
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        error_findings = [
            f for f in findings if f.category == Category.ERROR_HANDLING
        ]
        assert len(error_findings) >= 1

        for finding in error_findings:
            assert finding.severity == Severity.HIGH

    def test_detects_bare_except(self, tmp_path: Path) -> None:
        """Detects bare except clauses (no exception type)."""
        code = '''
def another_risky_op():
    try:
        something_dangerous()
    except:
        log_error("something went wrong")
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        error_findings = [
            f for f in findings if f.category == Category.ERROR_HANDLING
        ]
        assert len(error_findings) >= 1

    def test_allows_specific_exception_handling(self, tmp_path: Path) -> None:
        """Does not flag properly typed exception handlers."""
        code = '''
def safe_operation():
    try:
        do_something()
    except ValueError as e:
        logger.error(f"Value error: {e}")
        raise
    except IOError as e:
        logger.error(f"IO error: {e}")
        return None
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # Should not flag proper exception handling
        error_findings = [
            f for f in findings if f.category == Category.ERROR_HANDLING
        ]
        assert len(error_findings) == 0

    def test_detects_except_with_pass_only(self, tmp_path: Path) -> None:
        """Detects except blocks that only contain pass."""
        code = '''
def suppressed_errors():
    try:
        operation()
    except Exception:
        pass
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        error_findings = [
            f for f in findings if f.category == Category.ERROR_HANDLING
        ]
        assert len(error_findings) >= 1


class TestHallucinatedAPIs:
    """Tests for hallucinated API call detection."""

    def test_detects_nonexistent_method_on_self(self, tmp_path: Path) -> None:
        """Detects calls to methods that don't exist on self."""
        code = '''
class MyClass:
    def __init__(self):
        self.value = 0

    def process(self):
        # This method doesn't exist on this class
        self.nonexistent_method()
        self.another_fake_method(arg1=True)
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        # This is harder to detect statically - we look for self.method() patterns
        # where the method isn't defined in the class
        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        assert len(hallucination_findings) >= 1

    def test_allows_existing_methods_on_self(self, tmp_path: Path) -> None:
        """Does not flag calls to methods that exist on self."""
        code = '''
class MyClass:
    def __init__(self):
        self.value = 0

    def helper(self):
        return self.value * 2

    def process(self):
        result = self.helper()
        return result
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        hallucination_findings = [
            f for f in findings if f.category == Category.LLM_HALLUCINATION
        ]
        # Should not flag helper() as it exists
        assert len(hallucination_findings) == 0


class TestAnalyzeFile:
    """Tests for the main analyze_file method."""

    def test_returns_list_of_findings(self, tmp_path: Path) -> None:
        """analyze_file returns a list of Finding objects."""
        code = '''
def simple_func():
    return 1
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        assert isinstance(findings, list)

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        """Handles files with syntax errors without crashing."""
        code = '''
def broken_function(
    # Missing closing paren
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        # Should not raise, should return empty or error finding
        findings = auditor.analyze_file(test_file)
        assert isinstance(findings, list)

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Handles empty files gracefully."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)
        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Handles non-existent files gracefully."""
        test_file = tmp_path / "does_not_exist.py"

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)
        assert isinstance(findings, list)

    def test_findings_have_required_fields(self, tmp_path: Path) -> None:
        """Each finding has all required fields."""
        code = '''
from nonexistent_module import fake
# TODO: implement this
'''
        test_file = tmp_path / "test_file.py"
        test_file.write_text(code)

        auditor = LLMAuditor()
        findings = auditor.analyze_file(test_file)

        for finding in findings:
            assert finding.finding_id
            assert finding.severity in Severity
            assert finding.category in Category
            assert finding.file
            assert finding.line > 0
            assert finding.title
            assert finding.description


class TestVerifyImportExists:
    """Tests for the _verify_import_exists helper method."""

    def test_verifies_stdlib_exists(self) -> None:
        """Verifies standard library modules exist."""
        auditor = LLMAuditor()
        assert auditor._verify_import_exists("os") is True
        assert auditor._verify_import_exists("sys") is True
        assert auditor._verify_import_exists("pathlib") is True
        assert auditor._verify_import_exists("json") is True

    def test_verifies_nonexistent_module(self) -> None:
        """Verifies non-existent modules don't exist."""
        auditor = LLMAuditor()
        assert auditor._verify_import_exists("nonexistent_module_xyz") is False
        assert auditor._verify_import_exists("fake_package.fake_module") is False

    def test_handles_submodule_imports(self) -> None:
        """Handles dotted module paths correctly."""
        auditor = LLMAuditor()
        assert auditor._verify_import_exists("os.path") is True
        assert auditor._verify_import_exists("collections.abc") is True
        assert auditor._verify_import_exists("os.nonexistent") is False
