"""
TDD Tests for Semantic QA v0.3.1 Polish

Issue 1: httpx dependency in pyproject.toml
Issue 2: Consistent SemanticTestHook usage in bug pipeline
Issue 3: Documentation line number accuracy
Issue 4: CLI auto-metrics recording

RED PHASE: All tests should FAIL initially
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# ISSUE 1: httpx dependency in pyproject.toml
# =============================================================================

class TestHttpxDependency:
    """Tests for httpx dependency being declared in pyproject.toml."""

    def test_pyproject_includes_httpx_dependency(self):
        """pyproject.toml should include httpx in dependencies."""
        import tomllib

        pyproject_path = Path(__file__).parent.parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        dependencies = pyproject.get("project", {}).get("dependencies", [])
        httpx_deps = [d for d in dependencies if d.startswith("httpx")]

        assert len(httpx_deps) > 0, "httpx should be listed in dependencies"
        # Check version pinning
        assert any(">=" in d or "^" in d or "~" in d for d in httpx_deps), \
            "httpx should have version pinning"

    def test_qa_probe_imports_without_error(self):
        """qa probe command should import httpx without ImportError."""
        # This tests the actual import chain used by probe command
        try:
            # The probe command does a lazy import of httpx
            import httpx
            assert httpx is not None
        except ImportError as e:
            pytest.fail(f"httpx import failed: {e}")

    def test_httpx_version_meets_minimum(self):
        """httpx version should be at least 0.27.0."""
        import httpx

        version_parts = httpx.__version__.split(".")
        major = int(version_parts[0])
        minor = int(version_parts[1])

        assert (major, minor) >= (0, 27), \
            f"httpx version {httpx.__version__} should be >= 0.27.0"


# =============================================================================
# ISSUE 2: SemanticTestHook consistency in bug pipeline
# =============================================================================

class TestBugPipelineSemanticHook:
    """Tests for bug pipeline using SemanticTestHook instead of direct agent."""

    def test_bug_pipeline_uses_semantic_hook(self):
        """bug_orchestrator.py should import SemanticTestHook, not SemanticTesterAgent."""
        from swarm_attack import bug_orchestrator

        # Check that SemanticTestHook is imported
        source_path = Path(bug_orchestrator.__file__)
        source_code = source_path.read_text()

        # Should import SemanticTestHook
        assert "from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook" in source_code, \
            "bug_orchestrator should import SemanticTestHook"

        # Should NOT directly import SemanticTesterAgent for running tests
        # (it's OK to have the agent imported, but hook should be used for invocation)
        assert "SemanticTestHook(" in source_code, \
            "bug_orchestrator should instantiate SemanticTestHook"

    def test_bug_pipeline_semantic_output_matches_feature_pipeline(self):
        """Bug pipeline semantic test result should have same structure as feature pipeline."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticHookResult

        # Both pipelines should use SemanticHookResult
        result = SemanticHookResult()

        # Verify all expected fields are present
        assert hasattr(result, "verdict")
        assert hasattr(result, "should_block")
        assert hasattr(result, "block_reason")
        assert hasattr(result, "created_bug_id")
        assert hasattr(result, "warning")
        assert hasattr(result, "recommendations")
        assert hasattr(result, "evidence")
        assert hasattr(result, "issues")

    def test_semantic_hook_configuration_consistent(self):
        """SemanticTestHook configuration should be same in bug and feature pipelines."""
        from swarm_attack import bug_orchestrator, orchestrator

        bug_source = Path(bug_orchestrator.__file__).read_text()
        feature_source = Path(orchestrator.__file__).read_text()

        # Both should use SemanticTestHook with same config pattern
        # Feature pipeline: SemanticTestHook(self.config, self._logger)
        assert "SemanticTestHook(self.config" in bug_source, \
            "Bug pipeline should use SemanticTestHook with config"
        assert "SemanticTestHook(self.config" in feature_source, \
            "Feature pipeline should use SemanticTestHook with config"

    def test_bug_pipeline_handles_partial_verdict(self):
        """Bug pipeline should handle PARTIAL verdict (not just PASS/FAIL)."""
        from swarm_attack import bug_orchestrator

        source_path = Path(bug_orchestrator.__file__)
        source_code = source_path.read_text()

        # Should handle PARTIAL verdict like feature pipeline does
        assert "PARTIAL" in source_code or "semantic_result.verdict" in source_code, \
            "Bug pipeline should handle semantic verdicts properly via hook"


# =============================================================================
# ISSUE 3: Documentation line number accuracy
# =============================================================================

class TestDocumentationLineNumbers:
    """Tests for documentation line number references being accurate."""

    def _find_function_or_class_line(self, file_path: Path, name: str) -> int:
        """Find the line number where a function or class is defined."""
        content = file_path.read_text()
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if f"def {name}(" in line or f"class {name}" in line:
                return i
        return -1

    def test_claude_md_line_references_accurate(self):
        """CLAUDE.md line number references should point to actual code locations."""
        repo_root = Path(__file__).parent.parent.parent.parent
        claude_md = repo_root / "CLAUDE.md"

        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        content = claude_md.read_text()

        # Check for common line number patterns and verify them
        # Pattern: filename.py:NNN or filename.py:function_name
        import re

        # Find references like "config.py:165" or "coder.py:1208"
        line_refs = re.findall(r'(\w+\.py):(\d+)', content)

        errors = []
        for filename, line_str in line_refs:
            line_num = int(line_str)
            # Find the file
            matches = list(repo_root.rglob(filename))
            if not matches:
                continue  # Skip if file not found

            # Check if line number is within reasonable range
            for match in matches:
                try:
                    file_lines = match.read_text().split("\n")
                    if line_num > len(file_lines) + 10:  # Allow 10 line drift
                        errors.append(f"{filename}:{line_num} - file only has {len(file_lines)} lines")
                except Exception:
                    continue

        assert len(errors) == 0, f"Invalid line references: {errors}"

    def test_skill_md_line_references_accurate(self):
        """SKILL.md line number references should be accurate."""
        repo_root = Path(__file__).parent.parent.parent.parent
        skill_md = repo_root / ".claude" / "skills" / "qa-semantic-tester" / "SKILL.md"

        if not skill_md.exists():
            pytest.skip("qa-semantic-tester SKILL.md not found")

        content = skill_md.read_text()
        import re

        # Find references like "config.py:411"
        line_refs = re.findall(r'(\w+\.py):(\d+)', content)

        errors = []
        for filename, line_str in line_refs:
            line_num = int(line_str)
            matches = list(repo_root.rglob(filename))
            if not matches:
                continue

            for match in matches:
                try:
                    file_lines = match.read_text().split("\n")
                    if line_num > len(file_lines) + 10:
                        errors.append(f"{filename}:{line_num} - file only has {len(file_lines)} lines")
                except Exception:
                    continue

        assert len(errors) == 0, f"Invalid line references in SKILL.md: {errors}"

    def test_issue_creator_skill_line_refs(self):
        """issue-creator SKILL.md line refs should be accurate (known drift: config.py:411 → 419)."""
        repo_root = Path(__file__).parent.parent.parent.parent
        skill_md = repo_root / "swarm_attack" / "skills" / "issue-creator" / "SKILL.md"

        if not skill_md.exists():
            pytest.skip("issue-creator SKILL.md not found")

        content = skill_md.read_text()

        # This specific reference is known to have drifted
        # config.py:411 should now be config.py:419
        config_py = repo_root / "swarm_attack" / "config.py"
        config_content = config_py.read_text()
        lines = config_content.split("\n")

        # Find _parse_chief_of_staff_config
        actual_line = -1
        for i, line in enumerate(lines, 1):
            if "def _parse_chief_of_staff_config" in line:
                actual_line = i
                break

        # If docs reference 411, it should actually be at 419 (or nearby)
        if "config.py:411" in content:
            assert abs(actual_line - 419) <= 5, \
                f"_parse_chief_of_staff_config at line {actual_line}, docs say 411, should be ~419"


# =============================================================================
# ISSUE 4: CLI auto-metrics recording
# =============================================================================

class TestCLIAutoMetrics:
    """Tests for semantic-test CLI auto-recording metrics."""

    def test_semantic_test_has_no_metrics_flag(self):
        """semantic-test command should have --no-metrics flag."""
        from swarm_attack.cli.qa import semantic_test_command
        import inspect

        sig = inspect.signature(semantic_test_command)
        param_names = list(sig.parameters.keys())

        assert "no_metrics" in param_names, \
            "semantic_test_command should have no_metrics parameter"

    def test_semantic_test_records_metrics_by_default(self):
        """semantic_test_command should record metrics by default."""
        from swarm_attack.cli import qa as qa_module

        source_code = Path(qa_module.__file__).read_text()

        # Should import and use SemanticQAMetrics
        assert "SemanticQAMetrics" in source_code, \
            "qa.py should import SemanticQAMetrics"
        assert "record_test(" in source_code, \
            "qa.py should call metrics.record_test()"

    def test_semantic_test_no_metrics_flag_skips_recording(self):
        """--no-metrics flag should skip metrics recording."""
        from swarm_attack.cli import qa as qa_module

        source_code = Path(qa_module.__file__).read_text()

        # Should check no_metrics flag before recording
        assert "no_metrics" in source_code, \
            "qa.py should check no_metrics flag"

    def test_metrics_file_created_if_missing(self):
        """Metrics file should be created if it doesn't exist."""
        from swarm_attack.qa.metrics import SemanticQAMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / ".swarm" / "qa" / "metrics.json"
            assert not metrics_path.exists()

            metrics = SemanticQAMetrics(metrics_file=metrics_path)
            metrics.record_test(verdict="PASS", execution_time_ms=100.0)

            assert metrics_path.exists(), "Metrics file should be created"
            data = json.loads(metrics_path.read_text())
            assert len(data) > 0, "Metrics should be recorded"

    def test_metrics_include_required_fields(self):
        """Recorded metrics should include verdict, duration, scope, timestamp."""
        from swarm_attack.qa.metrics import SemanticQAMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.json"
            metrics = SemanticQAMetrics(metrics_file=metrics_path)

            metrics.record_test(
                verdict="PASS",
                execution_time_ms=150.0,
                scope="changes_only",
            )

            data = json.loads(metrics_path.read_text())
            # Metrics are stored as {"metrics": [...]}
            assert "metrics" in data, "Missing metrics key in file"
            assert len(data["metrics"]) == 1

            record = data["metrics"][0]
            assert "verdict" in record, "Missing verdict field"
            assert "execution_time_ms" in record, "Missing execution_time_ms field"
            assert "scope" in record, "Missing scope field"
            assert "timestamp" in record, "Missing timestamp field"

            assert record["verdict"] == "PASS"
            assert record["execution_time_ms"] == 150.0
            assert record["scope"] == "changes_only"

    def test_cli_records_execution_time(self):
        """CLI should measure and record execution time."""
        from swarm_attack.cli import qa as qa_module

        source_code = Path(qa_module.__file__).read_text()

        # Should measure time
        time_patterns = ["time.time()", "time.perf_counter()", "elapsed", "duration", "execution_time"]
        has_timing = any(p in source_code for p in time_patterns)

        assert has_timing, \
            "CLI should measure execution time for metrics recording"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSemanticQAPolishIntegration:
    """Integration tests for the complete polish work."""

    def test_all_imports_work(self):
        """All relevant modules should import without error."""
        try:
            from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
            from swarm_attack.qa.agents.semantic_tester import SemanticTesterAgent
            from swarm_attack.qa.metrics import SemanticQAMetrics
            from swarm_attack.bug_orchestrator import BugOrchestrator
            from swarm_attack.orchestrator import Orchestrator
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_no_circular_imports(self):
        """There should be no circular import issues."""
        # This test catches import cycles
        import importlib
        import sys

        modules_to_test = [
            "swarm_attack.qa.hooks.semantic_hook",
            "swarm_attack.qa.agents.semantic_tester",
            "swarm_attack.qa.metrics",
            "swarm_attack.bug_orchestrator",
            "swarm_attack.cli.qa",
        ]

        for mod_name in modules_to_test:
            # Clear from cache
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        # Re-import fresh
        for mod_name in modules_to_test:
            try:
                importlib.import_module(mod_name)
            except ImportError as e:
                if "circular" in str(e).lower():
                    pytest.fail(f"Circular import in {mod_name}: {e}")
                raise
