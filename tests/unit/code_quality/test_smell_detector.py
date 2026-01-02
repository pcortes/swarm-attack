"""Tests for SmellDetector code smell detection.

TDD RED Phase: These tests define the expected behavior of SmellDetector.
Tests cover:
- Long method detection (> 50 lines)
- Large class detection (> 300 lines)
- Deep nesting detection (> 4 levels)
- Too many parameters detection (> 3 parameters)
"""

import ast
import tempfile
from pathlib import Path

import pytest

from swarm_attack.code_quality.smell_detector import SmellDetector
from swarm_attack.code_quality.models import Finding, Severity, Category


class TestSmellDetectorInit:
    """Tests for SmellDetector initialization."""

    def test_default_thresholds(self):
        """SmellDetector should have sensible default thresholds from spec."""
        detector = SmellDetector()
        assert detector.MAX_METHOD_LINES == 50
        assert detector.MAX_CLASS_LINES == 300
        assert detector.MAX_NESTING_DEPTH == 4
        assert detector.MAX_PARAMETERS == 3


class TestLongMethodDetection:
    """Tests for detecting methods > 50 lines."""

    def test_detects_long_method(self, tmp_path):
        """A method with 60 lines should be flagged as long method."""
        # Create a file with a 60-line method
        code = '''
class MyClass:
    def long_method(self):
        """A long method with many lines."""
        x = 1
        x = 2
        x = 3
        x = 4
        x = 5
        x = 6
        x = 7
        x = 8
        x = 9
        x = 10
        x = 11
        x = 12
        x = 13
        x = 14
        x = 15
        x = 16
        x = 17
        x = 18
        x = 19
        x = 20
        x = 21
        x = 22
        x = 23
        x = 24
        x = 25
        x = 26
        x = 27
        x = 28
        x = 29
        x = 30
        x = 31
        x = 32
        x = 33
        x = 34
        x = 35
        x = 36
        x = 37
        x = 38
        x = 39
        x = 40
        x = 41
        x = 42
        x = 43
        x = 44
        x = 45
        x = 46
        x = 47
        x = 48
        x = 49
        x = 50
        x = 51
        x = 52
        x = 53
        x = 54
        x = 55
        x = 56
        x = 57
        x = 58
        x = 59
        x = 60
        return x
'''
        file_path = tmp_path / "test_long_method.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.CODE_SMELL
        assert "long_method" in finding.title.lower() or "Long Method" in finding.title
        assert "MyClass.long_method" in finding.description or "long_method" in finding.title

    def test_does_not_flag_short_method(self, tmp_path):
        """A method with 30 lines should NOT be flagged."""
        code = '''
class MyClass:
    def short_method(self):
        """A short method."""
        x = 1
        x = 2
        x = 3
        x = 4
        x = 5
        x = 6
        x = 7
        x = 8
        x = 9
        x = 10
        x = 11
        x = 12
        x = 13
        x = 14
        x = 15
        x = 16
        x = 17
        x = 18
        x = 19
        x = 20
        x = 21
        x = 22
        x = 23
        x = 24
        x = 25
        x = 26
        x = 27
        x = 28
        return x
'''
        file_path = tmp_path / "test_short_method.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        # Should not have any long method findings
        long_method_findings = [
            f for f in findings
            if "long" in f.title.lower() and "method" in f.title.lower()
        ]
        assert len(long_method_findings) == 0

    def test_method_exactly_at_threshold(self, tmp_path):
        """A method with exactly 50 lines should NOT be flagged."""
        # Method structure:
        # Line 1: def threshold_method(self):
        # Line 2: """Exactly 50 lines."""
        # Lines 3-49: 47 assignment statements
        # Line 50: return x
        # Total: 50 lines exactly
        lines = ["        x = {}".format(i) for i in range(1, 48)]  # 47 lines
        method_body = "\n".join(lines)
        code = f'''class MyClass:
    def threshold_method(self):
        """Exactly 50 lines."""
{method_body}
        return x
'''
        file_path = tmp_path / "test_threshold.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        long_method_findings = [
            f for f in findings
            if "long" in f.title.lower() and "method" in f.title.lower()
        ]
        assert len(long_method_findings) == 0


class TestLargeClassDetection:
    """Tests for detecting classes > 300 lines."""

    def test_detects_large_class(self, tmp_path):
        """A class with 350 lines should be flagged as large class."""
        # Generate a class with 350 lines
        methods = []
        for i in range(35):
            method = f'''
    def method_{i}(self):
        """Method {i}."""
        x = {i}
        y = {i} + 1
        z = {i} + 2
        w = {i} + 3
        return x + y + z + w
'''
            methods.append(method)

        class_body = "\n".join(methods)
        code = f'''
class LargeClass:
    """A large class that exceeds 300 lines."""
{class_body}
'''
        file_path = tmp_path / "test_large_class.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        large_class_findings = [
            f for f in findings
            if "large" in f.title.lower() and "class" in f.title.lower()
        ]
        assert len(large_class_findings) == 1
        finding = large_class_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.CODE_SMELL
        assert "LargeClass" in finding.description or "LargeClass" in finding.title

    def test_does_not_flag_small_class(self, tmp_path):
        """A class with 50 lines should NOT be flagged."""
        code = '''
class SmallClass:
    """A small class."""

    def __init__(self):
        self.x = 1
        self.y = 2

    def method_one(self):
        return self.x + self.y

    def method_two(self):
        return self.x * self.y

    def method_three(self):
        return self.x - self.y
'''
        file_path = tmp_path / "test_small_class.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        large_class_findings = [
            f for f in findings
            if "large" in f.title.lower() and "class" in f.title.lower()
        ]
        assert len(large_class_findings) == 0


class TestDeepNestingDetection:
    """Tests for detecting nesting > 4 levels."""

    def test_detects_deep_nesting(self, tmp_path):
        """Code with 5+ levels of nesting should be flagged."""
        code = '''
def deeply_nested_function(items):
    for item in items:  # Level 1
        if item:  # Level 2
            for sub in item:  # Level 3
                if sub:  # Level 4
                    for x in sub:  # Level 5 - should be flagged
                        print(x)
'''
        file_path = tmp_path / "test_deep_nesting.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        nesting_findings = [
            f for f in findings
            if "nest" in f.title.lower() or "nesting" in f.description.lower()
        ]
        assert len(nesting_findings) >= 1
        finding = nesting_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.CODE_SMELL

    def test_does_not_flag_shallow_nesting(self, tmp_path):
        """Code with <= 4 levels of nesting should NOT be flagged."""
        code = '''
def shallow_function(items):
    for item in items:  # Level 1
        if item:  # Level 2
            for sub in item:  # Level 3
                if sub:  # Level 4
                    print(sub)
'''
        file_path = tmp_path / "test_shallow_nesting.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        nesting_findings = [
            f for f in findings
            if "nest" in f.title.lower() or "nesting" in f.description.lower()
        ]
        assert len(nesting_findings) == 0


class TestTooManyParametersDetection:
    """Tests for detecting functions with > 3 parameters."""

    def test_detects_too_many_parameters(self, tmp_path):
        """Function with 5 parameters should be flagged."""
        code = '''
def too_many_params(a, b, c, d, e):
    """This function has too many parameters."""
    return a + b + c + d + e
'''
        file_path = tmp_path / "test_many_params.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        param_findings = [
            f for f in findings
            if "param" in f.title.lower() or "parameter" in f.title.lower()
        ]
        assert len(param_findings) == 1
        finding = param_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.CODE_SMELL
        assert "too_many_params" in finding.description or "too_many_params" in finding.title

    def test_does_not_flag_few_parameters(self, tmp_path):
        """Function with 3 parameters should NOT be flagged."""
        code = '''
def few_params(a, b, c):
    """This function has acceptable number of parameters."""
    return a + b + c
'''
        file_path = tmp_path / "test_few_params.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        param_findings = [
            f for f in findings
            if "param" in f.title.lower() or "parameter" in f.title.lower()
        ]
        assert len(param_findings) == 0

    def test_excludes_self_and_cls_from_count(self, tmp_path):
        """self and cls should not count towards parameter limit."""
        code = '''
class MyClass:
    def method_with_self(self, a, b, c):
        """self should not count."""
        return a + b + c

    @classmethod
    def method_with_cls(cls, a, b, c):
        """cls should not count."""
        return a + b + c
'''
        file_path = tmp_path / "test_self_cls.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        param_findings = [
            f for f in findings
            if "param" in f.title.lower() or "parameter" in f.title.lower()
        ]
        assert len(param_findings) == 0

    def test_flags_method_with_too_many_params_after_self(self, tmp_path):
        """Method with 4+ real parameters (excluding self) should be flagged."""
        code = '''
class MyClass:
    def method_with_many_params(self, a, b, c, d):
        """self + 4 params = flagged."""
        return a + b + c + d
'''
        file_path = tmp_path / "test_method_params.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        param_findings = [
            f for f in findings
            if "param" in f.title.lower() or "parameter" in f.title.lower()
        ]
        assert len(param_findings) == 1


class TestAnalyzeFile:
    """Tests for the main analyze_file method."""

    def test_returns_empty_list_for_clean_code(self, tmp_path):
        """Clean code should return no findings."""
        code = '''
def clean_function(a, b):
    """A clean, simple function."""
    return a + b


class CleanClass:
    """A clean, simple class."""

    def __init__(self):
        self.value = 0

    def get_value(self):
        return self.value
'''
        file_path = tmp_path / "test_clean.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        assert len(findings) == 0

    def test_handles_syntax_error_gracefully(self, tmp_path):
        """Invalid Python code should return empty list, not crash."""
        code = '''
def broken_function(
    # Missing closing paren and colon
'''
        file_path = tmp_path / "test_syntax_error.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        # Should not crash, should return empty list
        assert findings == []

    def test_handles_nonexistent_file_gracefully(self):
        """Non-existent file should return empty list, not crash."""
        detector = SmellDetector()
        findings = detector.analyze_file(Path("/nonexistent/path/file.py"))

        assert findings == []

    def test_finding_has_required_fields(self, tmp_path):
        """All findings should have required fields from spec."""
        code = '''
def too_many_params(a, b, c, d, e, f):
    """This function has too many parameters."""
    return a + b + c + d + e + f
'''
        file_path = tmp_path / "test_fields.py"
        file_path.write_text(code)

        detector = SmellDetector()
        findings = detector.analyze_file(file_path)

        assert len(findings) >= 1
        finding = findings[0]

        # Check required fields from spec
        assert finding.finding_id is not None
        assert finding.severity in Severity
        assert finding.category == Category.CODE_SMELL
        assert finding.file == str(file_path)
        assert finding.line > 0
        assert finding.title is not None
        assert finding.description is not None


class TestCountLines:
    """Tests for the _count_lines helper method."""

    def test_counts_lines_correctly(self):
        """Should correctly count lines in an AST node."""
        code = '''
def test_function():
    x = 1
    y = 2
    z = 3
    return x + y + z
'''
        tree = ast.parse(code)
        func = tree.body[0]

        detector = SmellDetector()
        line_count = detector._count_lines(func)

        # Function spans from line 2 to line 6 = 5 lines
        assert line_count == 5


class TestMeasureNestingDepth:
    """Tests for the _measure_nesting_depth helper method."""

    def test_measures_nesting_correctly(self):
        """Should correctly measure nesting depth."""
        code = '''
def test_function():
    for x in range(10):  # Level 1
        if x > 5:  # Level 2
            while x > 6:  # Level 3
                x -= 1
'''
        tree = ast.parse(code)
        func = tree.body[0]

        detector = SmellDetector()
        depth = detector._measure_nesting_depth(func)

        # Should be 3 levels of nesting
        assert depth == 3

    def test_no_nesting_returns_zero(self):
        """Flat code should return 0 nesting depth."""
        code = '''
def test_function():
    x = 1
    y = 2
    return x + y
'''
        tree = ast.parse(code)
        func = tree.body[0]

        detector = SmellDetector()
        depth = detector._measure_nesting_depth(func)

        assert depth == 0
