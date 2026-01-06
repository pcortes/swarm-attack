"""Integration tests for CoderAgent schema drift warnings.

Phase 2C: Memory-Powered UX Implementation
Tests for pre-implementation schema warnings in CoderAgent.

TDD: Tests written BEFORE implementation (RED phase).
"""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


@pytest.mark.skip(reason="Feature not implemented: CoderAgent._extract_potential_classes() method not yet added")
class TestSchemaWarningsExtraction:
    """Tests for extracting potential class names from issue body."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)

            # Create minimal spec
            (repo_path / "specs" / "test-feature" / "spec-final.md").write_text("# Test Spec\n")

            # Create minimal issues.json
            import json
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "Test Issue",
                        "body": "## Interface Contract\n\n**Required Classes:**\n- `AutopilotSession`\n- `DailyGoal`\n",
                        "labels": ["enhancement"],
                        "estimated_size": "medium",
                    }
                ]
            }
            (repo_path / "specs" / "test-feature" / "issues.json").write_text(json.dumps(issues))

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder Skill\n")

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for CoderAgent."""
        from dataclasses import dataclass, field

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")

        return MockConfig(repo_root=temp_repo, specs_path=temp_repo / "specs")

    def test_extract_class_names_from_interface_contract(self, mock_config):
        """Should extract class names from ## Interface Contract section."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config)

        issue_body = """## Interface Contract

**Required Classes:**
- `AutopilotSession`
- `DailyGoal`
- `CheckpointStore`

**Methods:**
- `start()`
- `stop()`
"""

        classes = agent._extract_potential_classes(issue_body)

        assert "AutopilotSession" in classes
        assert "DailyGoal" in classes
        assert "CheckpointStore" in classes

    def test_extract_class_names_from_acceptance_criteria(self, mock_config):
        """Should extract class names from acceptance criteria."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config)

        issue_body = """## Acceptance Criteria

- [ ] Create `SessionManager` class with lifecycle methods
- [ ] `ErrorHandler` should catch all exceptions
- [ ] Implement `ResultParser.parse()` method
"""

        classes = agent._extract_potential_classes(issue_body)

        assert "SessionManager" in classes
        assert "ErrorHandler" in classes
        assert "ResultParser" in classes

    def test_no_classes_extracted_from_empty_body(self, mock_config):
        """Empty issue body should return empty list."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config)

        classes = agent._extract_potential_classes("")

        assert classes == []


@pytest.mark.skip(reason="Feature not implemented: CoderAgent memory_store parameter not yet added")
class TestSchemaWarningsQuery:
    """Tests for querying memory for schema drift warnings."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store_with_drift(self, temp_store_path):
        """Create a MemoryStore with schema drift entries."""
        store = MemoryStore(store_path=temp_store_path)

        # Add schema drift entries for known classes
        drift_entries = [
            ("AutopilotSession", "swarm_attack/chief_of_staff/autopilot_runner.py", 15),
            ("DailyGoal", "swarm_attack/chief_of_staff/goal_tracker.py", 8),
        ]

        for class_name, existing_file, issue_num in drift_entries:
            entry = MemoryEntry(
                id=str(uuid4()),
                category="schema_drift",
                feature_id="chief-of-staff-v3",
                issue_number=issue_num,
                content={
                    "class_name": class_name,
                    "existing_file": existing_file,
                    "new_file": f"swarm_attack/chief_of_staff/duplicate_{class_name.lower()}.py",
                    "existing_issue": issue_num,
                },
                outcome="blocked",
                created_at=datetime.now().isoformat(),
                tags=["schema_drift", class_name],
            )
            store.add(entry)

        store.save()
        return store

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)

            # Create minimal spec
            (repo_path / "specs" / "test-feature" / "spec-final.md").write_text("# Test Spec\n")

            # Create minimal issues.json
            import json
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "Test Issue",
                        "body": "Test body",
                        "labels": ["enhancement"],
                        "estimated_size": "medium",
                    }
                ]
            }
            (repo_path / "specs" / "test-feature" / "issues.json").write_text(json.dumps(issues))

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder Skill\n")

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for CoderAgent."""
        from dataclasses import dataclass, field

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")

        return MockConfig(repo_root=temp_repo, specs_path=temp_repo / "specs")

    def test_schema_warning_returned_for_known_drift(
        self, mock_config, memory_store_with_drift
    ):
        """Should return warning when class caused drift before."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["AutopilotSession"])

        assert len(warnings) >= 1
        assert any(w["class_name"] == "AutopilotSession" for w in warnings)

    def test_no_warning_when_no_past_drift(self, mock_config, memory_store_with_drift):
        """Should return empty when class has no drift history."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["NewUniqueClass"])

        # Should find no warnings for unknown class
        assert not any(w["class_name"] == "NewUniqueClass" for w in warnings)

    def test_warning_includes_existing_file_path(
        self, mock_config, memory_store_with_drift
    ):
        """Warning should include where the class already exists."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["AutopilotSession"])

        assert len(warnings) >= 1
        autopilot_warning = next(
            (w for w in warnings if w["class_name"] == "AutopilotSession"), None
        )
        assert autopilot_warning is not None
        assert "existing_file" in autopilot_warning
        assert "autopilot_runner.py" in autopilot_warning["existing_file"]

    def test_warning_includes_original_issue_number(
        self, mock_config, memory_store_with_drift
    ):
        """Warning should include which issue created the class."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["AutopilotSession"])

        assert len(warnings) >= 1
        autopilot_warning = next(
            (w for w in warnings if w["class_name"] == "AutopilotSession"), None
        )
        assert autopilot_warning is not None
        assert "existing_issue" in autopilot_warning
        assert autopilot_warning["existing_issue"] == 15


@pytest.mark.skip(reason="Feature not implemented: CoderAgent._get_schema_warnings() and _format_schema_warnings() methods not yet added")
class TestSchemaWarningsInjection:
    """Tests for injecting warnings into CoderAgent context."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store_with_drift(self, temp_store_path):
        """Create a MemoryStore with schema drift entries."""
        store = MemoryStore(store_path=temp_store_path)

        entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="test-feature",
            issue_number=5,
            content={
                "class_name": "TestClass",
                "existing_file": "src/models/test.py",
                "new_file": "src/duplicate.py",
                "existing_issue": 5,
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "TestClass"],
        )
        store.add(entry)
        store.save()

        return store

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)

            # Create minimal spec
            (repo_path / "specs" / "test-feature" / "spec-final.md").write_text("# Test Spec\n")

            # Create minimal issues.json
            import json
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "Test Issue",
                        "body": "Create `TestClass` for handling test data.",
                        "labels": ["enhancement"],
                        "estimated_size": "medium",
                    }
                ]
            }
            (repo_path / "specs" / "test-feature" / "issues.json").write_text(json.dumps(issues))

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder Skill\n")

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for CoderAgent."""
        from dataclasses import dataclass, field

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")

        return MockConfig(repo_root=temp_repo, specs_path=temp_repo / "specs")

    def test_warnings_injected_into_context(self, mock_config, memory_store_with_drift):
        """Schema warnings should appear in enhanced context."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["TestClass"])
        warning_text = agent._format_schema_warnings(warnings)

        assert "TestClass" in warning_text
        assert "src/models/test.py" in warning_text
        assert "import" in warning_text.lower()

    def test_no_warnings_section_when_no_drift(self, mock_config):
        """No warnings section when no schema drift history."""
        from swarm_attack.agents.coder import CoderAgent

        # No memory store at all
        agent = CoderAgent(config=mock_config)

        warnings = agent._get_schema_warnings(["SomeNewClass"])
        warning_text = agent._format_schema_warnings(warnings)

        # Should be empty or minimal
        assert warning_text == "" or "No" in warning_text

    def test_coder_works_without_memory_store(self, mock_config):
        """Existing behavior preserved when memory_store=None."""
        from swarm_attack.agents.coder import CoderAgent

        # No memory_store provided
        agent = CoderAgent(config=mock_config)

        # Should not raise
        warnings = agent._get_schema_warnings(["AnyClass"])
        assert warnings == []

    def test_warning_format_is_readable(self, mock_config, memory_store_with_drift):
        """Warning format should be simple and readable."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = agent._get_schema_warnings(["TestClass"])
        warning_text = agent._format_schema_warnings(warnings)

        # Should be simple one-line-per-warning format, not markdown table
        # Check for readable format
        assert "TestClass" in warning_text
        # Should mention importing instead of recreating
        assert "import" in warning_text.lower() or "recreat" in warning_text.lower()


@pytest.mark.skip(reason="Feature not implemented: CoderAgent memory_store parameter not yet added")
class TestCoderAgentMemoryStoreParameter:
    """Tests for CoderAgent accepting memory_store parameter."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, temp_store_path):
        """Create a MemoryStore instance."""
        return MemoryStore(store_path=temp_store_path)

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder Skill\n")

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for CoderAgent."""
        from dataclasses import dataclass, field

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")

        return MockConfig(repo_root=temp_repo, specs_path=temp_repo / "specs")

    def test_coder_agent_accepts_memory_store(self, mock_config, memory_store):
        """CoderAgent should accept memory_store parameter."""
        from swarm_attack.agents.coder import CoderAgent

        # Should not raise
        agent = CoderAgent(config=mock_config, memory_store=memory_store)
        assert agent is not None
        assert hasattr(agent, "_memory")

    def test_coder_agent_stores_memory_reference(self, mock_config, memory_store):
        """CoderAgent should store memory_store reference."""
        from swarm_attack.agents.coder import CoderAgent

        agent = CoderAgent(config=mock_config, memory_store=memory_store)

        assert agent._memory is memory_store
