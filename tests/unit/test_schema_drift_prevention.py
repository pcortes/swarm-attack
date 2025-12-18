"""
Unit tests for Schema Drift Prevention components.

Tests the following components:
1. DependencyGraph - transitive dependency computation
2. Compact Schema formatting in ContextBuilder
3. Subclass detection in VerifierAgent
4. IssueContextManager - GitHub context propagation
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass


# Test DependencyGraph
class TestDependencyGraph:
    """Tests for DependencyGraph transitive dependency computation."""

    def test_direct_dependencies(self):
        """Test getting direct dependencies."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
        ]
        graph = DependencyGraph(tasks)

        assert graph.get_direct_dependencies(1) == set()
        assert graph.get_direct_dependencies(2) == {1}

    def test_transitive_dependencies(self):
        """Test transitive dependency computation."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        # Chain: 1 <- 2 <- 3
        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[2]),
        ]
        graph = DependencyGraph(tasks)

        # Issue 3 should see both 1 and 2
        assert graph.get_transitive_dependencies(3) == {1, 2}
        assert graph.get_transitive_dependencies(2) == {1}
        assert graph.get_transitive_dependencies(1) == set()

    def test_diamond_dependencies(self):
        """Test diamond-shaped dependency graph."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        # Diamond: 1 <- 2, 1 <- 3, 2,3 <- 4
        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[1]),
            MockTask(issue_number=4, dependencies=[2, 3]),
        ]
        graph = DependencyGraph(tasks)

        # Issue 4 should see 1, 2, and 3
        assert graph.get_transitive_dependencies(4) == {1, 2, 3}

    def test_get_dependents(self):
        """Test getting issues that depend on a given issue."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[1]),
            MockTask(issue_number=4, dependencies=[2]),
        ]
        graph = DependencyGraph(tasks)

        # Issue 1 is depended on by 2 and 3
        assert graph.get_dependents(1) == {2, 3}
        assert graph.get_dependents(2) == {4}
        assert graph.get_dependents(4) == set()

    def test_get_transitive_dependents(self):
        """Test transitive dependent computation."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        # Chain: 1 <- 2 <- 3
        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[2]),
        ]
        graph = DependencyGraph(tasks)

        # When issue 1 completes, both 2 and 3 need context
        assert graph.get_transitive_dependents(1) == {2, 3}

    def test_topological_sort(self):
        """Test topological sorting of issues."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        tasks = [
            MockTask(issue_number=3, dependencies=[2]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=1, dependencies=[]),
        ]
        graph = DependencyGraph(tasks)

        order = graph.topological_sort()
        # 1 must come before 2, 2 must come before 3
        assert order.index(1) < order.index(2)
        assert order.index(2) < order.index(3)

    def test_cycle_detection(self):
        """Test detection of dependency cycles."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        # Create cycle: 1 <- 2 <- 3 <- 1
        tasks = [
            MockTask(issue_number=1, dependencies=[3]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[2]),
        ]
        graph = DependencyGraph(tasks)

        has_cycle, cycle_nodes = graph.has_cycle()
        assert has_cycle
        assert set(cycle_nodes) == {1, 2, 3}

    def test_no_cycle_in_dag(self):
        """Test that DAG reports no cycle."""
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[1]),
            MockTask(issue_number=3, dependencies=[1]),
        ]
        graph = DependencyGraph(tasks)

        has_cycle, cycle_nodes = graph.has_cycle()
        assert not has_cycle
        assert cycle_nodes == []


class TestCompactSchema:
    """Tests for compact schema formatting in ContextBuilder."""

    def test_format_module_registry_compact_empty(self):
        """Test formatting empty registry."""
        from swarm_attack.context_builder import ContextBuilder

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        builder = ContextBuilder(mock_config)
        result = builder.format_module_registry_compact({})

        assert "No prior modules" in result

    def test_format_module_registry_compact_filters_dependencies(self, tmp_path):
        """Test that compact schema filters to dependencies only."""
        from swarm_attack.context_builder import ContextBuilder

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path

        builder = ContextBuilder(mock_config)

        # Create actual files for the test
        models_file = tmp_path / "models.py"
        models_file.write_text("""
class SessionA:
    id: str
""")

        utils_file = tmp_path / "utils.py"
        utils_file.write_text("""
class HelperB:
    def help(self): pass
""")

        runner_file = tmp_path / "runner.py"
        runner_file.write_text("""
class RunnerC:
    def run(self): pass
""")

        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["SessionA"],
                },
                "utils.py": {
                    "created_by_issue": 2,
                    "classes": ["HelperB"],
                },
                "runner.py": {
                    "created_by_issue": 3,
                    "classes": ["RunnerC"],
                },
            }
        }

        # Only show classes from issue 1
        result = builder.format_module_registry_compact(registry, dependencies={1})

        # Should mention SessionA (from issue 1)
        assert "SessionA" in result
        # Should NOT mention HelperB or RunnerC (from issues 2 and 3)
        assert "HelperB" not in result
        assert "RunnerC" not in result


class TestSubclassDetection:
    """Tests for subclass detection in duplicate class checking."""

    def test_exact_duplicate_detected(self, tmp_path):
        """Test that exact duplicates are detected."""
        from swarm_attack.agents.verifier import VerifierAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path

        verifier = VerifierAgent(mock_config)

        # Create a new file with duplicate class
        new_file = tmp_path / "new_module.py"
        new_file.write_text("""
class AutopilotSession:
    id: str
    goals: list
""")

        new_classes = {
            "new_module.py": ["AutopilotSession"],
        }

        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession"],
                },
            }
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "AutopilotSession"
        assert "SCHEMA DRIFT" in conflicts[0]["message"]

    def test_subclass_allowed(self, tmp_path):
        """Test that subclassing existing classes is allowed."""
        from swarm_attack.agents.verifier import VerifierAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path

        verifier = VerifierAgent(mock_config)

        # Create a new file with subclass (not duplicate)
        new_file = tmp_path / "extended.py"
        new_file.write_text("""
from models import BaseSession

class BaseSession(BaseSession):
    extra_field: str
""")

        # Note: The class name matches but it inherits from BaseSession
        new_classes = {
            "extended.py": ["BaseSession"],
        }

        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["BaseSession"],
                },
            }
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        # Should be allowed because it's a subclass
        assert len(conflicts) == 0

    def test_same_name_same_file_allowed(self, tmp_path):
        """Test that same class in same file is not flagged."""
        from swarm_attack.agents.verifier import VerifierAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path

        verifier = VerifierAgent(mock_config)

        # Class in same file (modification, not duplication)
        new_classes = {
            "models.py": ["AutopilotSession"],
        }

        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["AutopilotSession"],
                },
            }
        }

        conflicts = verifier._check_duplicate_classes(new_classes, registry)

        # Same file = modification, not duplication
        assert len(conflicts) == 0


class TestIssueContextManager:
    """Tests for GitHub issue context propagation."""

    def test_format_summary_section(self):
        """Test that summary section is formatted with markers."""
        from swarm_attack.github.issue_context import IssueContextManager

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        manager = IssueContextManager(mock_config)

        # Test marker constants exist
        assert "SWARM:IMPLEMENTATION_SUMMARY:START" in manager.SUMMARY_MARKER_START
        assert "SWARM:IMPLEMENTATION_SUMMARY:END" in manager.SUMMARY_MARKER_END

    def test_insert_or_replace_section_new(self):
        """Test inserting new section into body."""
        from swarm_attack.github.issue_context import IssueContextManager

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        manager = IssueContextManager(mock_config)

        body = "Original issue body"
        section = "New summary content"

        result = manager._insert_or_replace_section(
            body,
            section,
            "<!-- START -->",
            "<!-- END -->",
        )

        assert "Original issue body" in result
        assert "New summary content" in result
        assert "<!-- START -->" in result
        assert "<!-- END -->" in result

    def test_insert_or_replace_section_update(self):
        """Test replacing existing section in body."""
        from swarm_attack.github.issue_context import IssueContextManager

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        manager = IssueContextManager(mock_config)

        body = """Original body

<!-- START -->
Old content
<!-- END -->

More content"""

        result = manager._insert_or_replace_section(
            body,
            "New content",
            "<!-- START -->",
            "<!-- END -->",
        )

        assert "New content" in result
        assert "Old content" not in result
        assert "More content" in result


class TestSummarizerAgent:
    """Tests for the summarizer agent."""

    def test_build_fallback_summary(self):
        """Test fallback summary generation without LLM."""
        from swarm_attack.agents.summarizer import SummarizerAgent

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        summarizer = SummarizerAgent(mock_config)

        files_created = ["models.py", "utils.py"]
        classes_defined = {
            "models.py": ["Session", "Goal"],
            "utils.py": ["Helper"],
        }

        summary = summarizer._build_fallback_summary(files_created, classes_defined)

        assert "files_summary" in summary
        assert len(summary["files_summary"]) == 2

        assert "classes_defined" in summary
        assert "models.py" in summary["classes_defined"]
        assert len(summary["classes_defined"]["models.py"]) == 2

        # Check import statements are generated
        session_cls = summary["classes_defined"]["models.py"][0]
        assert "import_statement" in session_cls
        assert "models" in session_cls["import_statement"]

    def test_format_summary_for_github(self):
        """Test formatting summary as GitHub markdown."""
        from swarm_attack.agents.summarizer import SummarizerAgent

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        summarizer = SummarizerAgent(mock_config)

        summary = {
            "files_summary": [
                {"path": "models.py", "purpose": "Core data models"},
            ],
            "classes_defined": {
                "models.py": [
                    {
                        "name": "Session",
                        "purpose": "Tracks user sessions",
                        "import_statement": "from models import Session",
                        "key_fields": ["id: str", "started_at: str"],
                        "key_methods": ["to_dict()", "from_dict()"],
                    }
                ]
            },
            "usage_patterns": ["Create via Session(id=...)", "Serialize with to_dict()"],
            "integration_notes": ["Use from_dict() for deserialization"],
        }

        markdown = summarizer._format_summary_for_github(summary)

        assert "### Files Created/Modified" in markdown
        assert "models.py" in markdown
        assert "### Classes Defined" in markdown
        assert "**Session**" in markdown
        assert "### Usage Patterns" in markdown

    def test_format_context_for_dependent(self):
        """Test formatting compact context for dependent issues."""
        from swarm_attack.agents.summarizer import SummarizerAgent

        mock_config = MagicMock()
        mock_config.repo_root = Path("/fake/repo")

        summarizer = SummarizerAgent(mock_config)

        summary = {
            "classes_defined": {
                "models.py": [
                    {
                        "name": "Session",
                        "purpose": "Tracks user sessions",
                        "import_statement": "from models import Session",
                        "key_fields": ["id: str"],
                        "key_methods": [],
                    }
                ]
            },
            "usage_patterns": ["Create via Session(id=...)"],
        }

        context = summarizer._format_context_for_dependent(
            source_issue=1,
            source_title="Core Models",
            summary=summary,
        )

        assert "### From Issue #1: Core Models" in context
        assert "from models import Session" in context
        assert "**Session**" in context


class TestIntegration:
    """Integration tests for schema drift prevention flow."""

    def test_dependency_filtering_in_context_builder(self, tmp_path):
        """Test end-to-end dependency filtering in context building."""
        from swarm_attack.context_builder import ContextBuilder
        from swarm_attack.planning.dependency_graph import DependencyGraph

        @dataclass
        class MockTask:
            issue_number: int
            dependencies: list[int]

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path

        builder = ContextBuilder(mock_config)

        # Create real files for schema extraction
        models_file = tmp_path / "models.py"
        models_file.write_text("""
from dataclasses import dataclass

@dataclass
class Session:
    id: str
    started_at: str
""")

        utils_file = tmp_path / "utils.py"
        utils_file.write_text("""
class Helper:
    def help(self): pass
""")

        registry = {
            "modules": {
                "models.py": {
                    "created_by_issue": 1,
                    "classes": ["Session"],
                },
                "utils.py": {
                    "created_by_issue": 2,
                    "classes": ["Helper"],
                },
            }
        }

        # Issue 3 only depends on issue 1
        tasks = [
            MockTask(issue_number=1, dependencies=[]),
            MockTask(issue_number=2, dependencies=[]),
            MockTask(issue_number=3, dependencies=[1]),
        ]

        result = builder.format_module_registry_for_issue(
            registry,
            issue_dependencies=[1],
            all_tasks=tasks,
        )

        # Should show Session (from issue 1)
        assert "Session" in result
        # Should NOT show Helper (from issue 2, not a dependency)
        assert "Helper" not in result
