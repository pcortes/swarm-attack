"""Documentation Generation Tests.

Verifies API documentation can be generated and is complete.
"""

import os
import subprocess
from pathlib import Path

import pytest


def _get_env_with_pythonpath():
    """Get environment dict with PYTHONPATH set."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    return env


class TestDocumentationGeneration:
    """Tests for documentation generation."""

    def test_pdoc_can_generate_docs(self, tmp_path):
        """pdoc should generate documentation without errors."""
        result = subprocess.run(
            ["python", "-m", "pdoc", "swarm_attack.qa", "-o", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )
        assert result.returncode == 0, f"pdoc failed: {result.stderr}"

    def test_all_public_modules_documented(self, tmp_path):
        """All public QA modules should have generated docs."""
        # Generate docs for individual modules (pdoc generates separate files this way)
        modules = [
            "swarm_attack.qa.models",
            "swarm_attack.qa.orchestrator",
            "swarm_attack.qa.context_builder",
            "swarm_attack.qa.depth_selector",
        ]
        subprocess.run(
            ["python", "-m", "pdoc", *modules, "-o", str(tmp_path)],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )

        expected_modules = [
            "models.html",
            "orchestrator.html",
            "context_builder.html",
            "depth_selector.html",
        ]

        for module in expected_modules:
            assert (tmp_path / "swarm_attack" / "qa" / module).exists(), \
                f"Missing docs for {module}"

    def test_orchestrator_methods_documented(self, tmp_path):
        """QAOrchestrator public methods should be in docs."""
        # Generate docs for orchestrator module specifically
        subprocess.run(
            ["python", "-m", "pdoc", "swarm_attack.qa.orchestrator", "-o", str(tmp_path)],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env=_get_env_with_pythonpath(),
        )

        orch_docs = (tmp_path / "swarm_attack" / "qa" / "orchestrator.html").read_text()

        required_methods = ["test", "validate_issue", "health_check", "dispatch_agents"]
        for method in required_methods:
            assert method in orch_docs, f"Method {method} not documented"


class TestDocstringCompleteness:
    """Tests for docstring completeness."""

    def test_orchestrator_has_docstrings(self):
        """QAOrchestrator should have docstrings on all public methods."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        public_methods = [
            name for name in dir(QAOrchestrator)
            if not name.startswith("_") and callable(getattr(QAOrchestrator, name))
        ]

        for method_name in public_methods:
            method = getattr(QAOrchestrator, method_name)
            assert method.__doc__, f"Method {method_name} missing docstring"

    def test_context_builder_has_docstrings(self):
        """QAContextBuilder should have docstrings on all public methods."""
        from swarm_attack.qa.context_builder import QAContextBuilder

        public_methods = [
            name for name in dir(QAContextBuilder)
            if not name.startswith("_") and callable(getattr(QAContextBuilder, name))
        ]

        for method_name in public_methods:
            method = getattr(QAContextBuilder, method_name)
            assert method.__doc__, f"Method {method_name} missing docstring"

    def test_models_have_docstrings(self):
        """QA model classes should have docstrings."""
        from swarm_attack.qa import models

        model_classes = [
            "QASession", "QAFinding", "QAResult", "QAContext",
            "QAEndpoint", "QALimits", "QABug"
        ]

        for class_name in model_classes:
            cls = getattr(models, class_name)
            assert cls.__doc__, f"Class {class_name} missing docstring"

    def test_depth_selector_has_docstrings(self):
        """DepthSelector should have docstrings on all public methods."""
        from swarm_attack.qa.depth_selector import DepthSelector

        public_methods = [
            name for name in dir(DepthSelector)
            if not name.startswith("_") and callable(getattr(DepthSelector, name))
        ]

        for method_name in public_methods:
            method = getattr(DepthSelector, method_name)
            assert method.__doc__, f"Method {method_name} missing docstring"


class TestDocumentationQuality:
    """Tests for documentation quality."""

    def test_orchestrator_docstring_has_args(self):
        """QAOrchestrator public methods should document their args."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        methods_with_args = ["test", "validate_issue", "dispatch_agents"]

        for method_name in methods_with_args:
            method = getattr(QAOrchestrator, method_name)
            docstring = method.__doc__ or ""
            assert "Args:" in docstring or "args:" in docstring.lower(), \
                f"Method {method_name} missing Args section"

    def test_orchestrator_docstring_has_returns(self):
        """QAOrchestrator public methods should document their returns."""
        from swarm_attack.qa.orchestrator import QAOrchestrator

        methods_with_returns = ["test", "validate_issue", "health_check", "get_session"]

        for method_name in methods_with_returns:
            method = getattr(QAOrchestrator, method_name)
            docstring = method.__doc__ or ""
            assert "Returns:" in docstring or "returns:" in docstring.lower(), \
                f"Method {method_name} missing Returns section"

    def test_context_builder_docstring_quality(self):
        """QAContextBuilder.build_context should have complete docstring."""
        from swarm_attack.qa.context_builder import QAContextBuilder

        docstring = QAContextBuilder.build_context.__doc__ or ""

        assert "Args:" in docstring, "build_context missing Args section"
        assert "Returns:" in docstring, "build_context missing Returns section"
        assert "QAContext" in docstring, "build_context should mention QAContext"
