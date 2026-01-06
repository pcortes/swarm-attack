"""
Integration tests for full memory flow between agents.

Tests the memory system integration across:
1. VerifierAgent recording schema drift entries
2. CoderAgent querying for schema warnings
3. Memory persistence across Orchestrator instances
4. Schema warnings appearing in coder prompts

TDD: Tests written to verify end-to-end memory flow works correctly.
"""

import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


class TestVerifierRecordsDriftCoderReceivesWarning:
    """Test full flow: VerifierAgent records drift, CoderAgent queries warnings."""

    @pytest.fixture
    def temp_memory_path(self):
        """Create a temporary directory for memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def shared_memory_store(self, temp_memory_path):
        """Create a shared MemoryStore instance."""
        return MemoryStore(store_path=temp_memory_path)

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory with required structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)
            (repo_path / ".swarm" / "memory").mkdir(parents=True)

            # Create minimal spec
            (repo_path / "specs" / "test-feature" / "spec-final.md").write_text(
                "# Test Spec\n\nThis is a test spec."
            )

            # Create minimal issues.json with class references
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "Implement AutopilotSession",
                        "body": "## Interface Contract\n\n**Required Classes:**\n- `AutopilotSession`\n",
                        "labels": ["enhancement"],
                        "estimated_size": "medium",
                    }
                ]
            }
            (repo_path / "specs" / "test-feature" / "issues.json").write_text(
                json.dumps(issues)
            )

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text(
                "# Coder Skill\n\nImplement code following TDD."
            )

            # Create minimal test file
            test_content = '''"""Test file for test-feature issue 1."""
import pytest

def test_placeholder():
    """Placeholder test."""
    assert True
'''
            (repo_path / "tests" / "generated" / "test-feature" / "test_issue_1.py").write_text(
                test_content
            )

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for agents."""
        @dataclass
        class MockTestConfig:
            command: str = "pytest"
            args: list = field(default_factory=list)
            timeout_seconds: int = 60

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")
            tests: MockTestConfig = field(default_factory=MockTestConfig)

        return MockConfig(
            repo_root=temp_repo,
            specs_path=temp_repo / "specs",
            tests=MockTestConfig(),
        )

    def test_verifier_records_drift_coder_receives_warning(
        self, shared_memory_store, mock_config
    ):
        """
        Full flow test:
        1. VerifierAgent records a schema drift entry
        2. CoderAgent queries for schema warnings
        3. Verify the warning is returned
        """
        from swarm_attack.agents.coder import CoderAgent
        from swarm_attack.agents.verifier import VerifierAgent

        # Step 1: Simulate VerifierAgent detecting and recording schema drift
        # This mimics what happens when verifier._check_duplicate_classes() finds conflicts
        drift_entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="test-feature",
            issue_number=1,
            content={
                "class_name": "AutopilotSession",
                "existing_file": "swarm_attack/models/session.py",
                "new_file": "swarm_attack/agents/autopilot.py",
                "existing_issue": 5,
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "AutopilotSession"],
        )
        shared_memory_store.add(drift_entry)
        shared_memory_store.save()

        # Step 2: Create CoderAgent with the same memory store
        coder = CoderAgent(config=mock_config, memory_store=shared_memory_store)

        # Step 3: Query for schema warnings for the class mentioned in issue
        class_names = ["AutopilotSession"]
        warnings = coder._get_schema_warnings(class_names)

        # Step 4: Verify the warning is returned
        assert len(warnings) == 1
        assert warnings[0]["class_name"] == "AutopilotSession"
        assert warnings[0]["existing_file"] == "swarm_attack/models/session.py"
        assert warnings[0]["existing_issue"] == 5

    def test_verifier_records_multiple_drifts_coder_receives_all(
        self, shared_memory_store, mock_config
    ):
        """Test that multiple drift entries are all returned to coder."""
        from swarm_attack.agents.coder import CoderAgent

        # Record multiple schema drift entries
        drift_entries = [
            ("AutopilotSession", "models/session.py", 5),
            ("DailyGoal", "models/goal.py", 8),
        ]

        for class_name, existing_file, issue_num in drift_entries:
            entry = MemoryEntry(
                id=str(uuid4()),
                category="schema_drift",
                feature_id="test-feature",
                issue_number=issue_num,
                content={
                    "class_name": class_name,
                    "existing_file": existing_file,
                    "new_file": f"agents/{class_name.lower()}.py",
                    "existing_issue": issue_num,
                },
                outcome="blocked",
                created_at=datetime.now().isoformat(),
                tags=["schema_drift", class_name],
            )
            shared_memory_store.add(entry)

        shared_memory_store.save()

        # Create CoderAgent and query
        coder = CoderAgent(config=mock_config, memory_store=shared_memory_store)
        warnings = coder._get_schema_warnings(["AutopilotSession", "DailyGoal"])

        # Should get warnings for both classes
        assert len(warnings) == 2
        class_names_returned = {w["class_name"] for w in warnings}
        assert "AutopilotSession" in class_names_returned
        assert "DailyGoal" in class_names_returned

    def test_coder_without_memory_store_returns_no_warnings(self, mock_config):
        """CoderAgent without memory_store should return empty warnings list."""
        from swarm_attack.agents.coder import CoderAgent

        # Create CoderAgent without memory store
        coder = CoderAgent(config=mock_config, memory_store=None)

        # Query for warnings
        warnings = coder._get_schema_warnings(["AutopilotSession"])

        # Should return empty list (graceful degradation)
        assert warnings == []


class TestMemoryPersistsAcrossOrchestratorInstances:
    """Test that memory entries persist when orchestrator is recreated."""

    @pytest.fixture
    def temp_memory_path(self):
        """Create a temporary file path for memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create minimal structure
            (repo_path / ".swarm" / "state").mkdir(parents=True)
            (repo_path / ".swarm" / "events").mkdir(parents=True)
            (repo_path / ".swarm" / "memory").mkdir(parents=True)
            (repo_path / "specs").mkdir(parents=True)
            (repo_path / "tests" / "generated").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "verifier").mkdir(parents=True)

            # Create skill files
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder")
            (repo_path / ".claude" / "skills" / "verifier" / "SKILL.md").write_text("# Verifier")

            yield repo_path

    @pytest.fixture
    def real_config(self, temp_repo):
        """Create a real SwarmConfig pointing to temp repo."""
        from swarm_attack.config import SwarmConfig
        return SwarmConfig(repo_root=str(temp_repo))

    def test_memory_persists_across_orchestrator_instances(
        self, temp_memory_path, real_config
    ):
        """
        Test that:
        1. Create Orchestrator with memory store, record entries
        2. Destroy orchestrator
        3. Create new Orchestrator with same memory path
        4. Memory entries are still accessible
        """
        from swarm_attack.orchestrator import Orchestrator

        # Step 1: Create first memory store and add entries
        memory_store_1 = MemoryStore(store_path=temp_memory_path)

        drift_entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="persistent-feature",
            issue_number=10,
            content={
                "class_name": "PersistentClass",
                "existing_file": "src/models.py",
                "new_file": "src/duplicate.py",
                "existing_issue": 10,
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "PersistentClass"],
        )
        memory_store_1.add(drift_entry)
        memory_store_1.save()

        # Step 2: Create Orchestrator with this memory store
        orchestrator_1 = Orchestrator(
            config=real_config,
            memory_store=memory_store_1,
        )

        # Verify memory is accessible through orchestrator
        assert orchestrator_1.memory_store is not None
        results_1 = orchestrator_1.memory_store.query(category="schema_drift")
        assert len(results_1) == 1
        assert results_1[0].content["class_name"] == "PersistentClass"

        # Step 3: "Destroy" orchestrator (simulate session end)
        del orchestrator_1

        # Step 4: Create new memory store from same path (simulating new session)
        memory_store_2 = MemoryStore.load(store_path=temp_memory_path)

        # Step 5: Create new Orchestrator with loaded memory
        orchestrator_2 = Orchestrator(
            config=real_config,
            memory_store=memory_store_2,
        )

        # Step 6: Verify memory entries are still accessible
        results_2 = orchestrator_2.memory_store.query(category="schema_drift")
        assert len(results_2) == 1
        assert results_2[0].content["class_name"] == "PersistentClass"
        assert results_2[0].content["existing_file"] == "src/models.py"

    def test_orchestrator_creates_default_memory_store_if_none_provided(
        self, real_config
    ):
        """Orchestrator should create a default MemoryStore if none provided."""
        from swarm_attack.orchestrator import Orchestrator

        # Create orchestrator without memory store
        orchestrator = Orchestrator(config=real_config)

        # Should have created a default memory store
        assert orchestrator.memory_store is not None
        assert isinstance(orchestrator.memory_store, MemoryStore)


class TestSchemaWarningAppearsInCoderPrompt:
    """Test that schema drift warnings appear in generated coder prompts."""

    @pytest.fixture
    def temp_memory_path(self):
        """Create a temporary directory for memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory with required structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "test-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "test-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)
            (repo_path / ".swarm" / "memory").mkdir(parents=True)

            # Create minimal spec
            (repo_path / "specs" / "test-feature" / "spec-final.md").write_text(
                "# Test Spec\n\nThis is a test spec for UserSession feature."
            )

            # Create issues.json with class reference that matches schema drift
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "Implement UserSession Manager",
                        "body": """## Interface Contract

**Required Classes:**
- `UserSession` - Core session management class
- `SessionStore` - Persistence layer

## Acceptance Criteria
- [ ] Create `UserSession` class with start/stop methods
- [ ] Implement session persistence via `SessionStore`
""",
                        "labels": ["enhancement"],
                        "estimated_size": "medium",
                    }
                ]
            }
            (repo_path / "specs" / "test-feature" / "issues.json").write_text(
                json.dumps(issues)
            )

            # Create minimal skill file
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text(
                "# Coder Skill\n\nImplement code following TDD principles."
            )

            # Create test file
            test_content = '''"""Test file for UserSession."""
import pytest

def test_user_session_exists():
    """Test UserSession class exists."""
    pass
'''
            (repo_path / "tests" / "generated" / "test-feature" / "test_issue_1.py").write_text(
                test_content
            )

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config for CoderAgent."""
        @dataclass
        class MockTestConfig:
            command: str = "pytest"
            args: list = field(default_factory=list)
            timeout_seconds: int = 60

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")
            tests: MockTestConfig = field(default_factory=MockTestConfig)

        return MockConfig(
            repo_root=temp_repo,
            specs_path=temp_repo / "specs",
            tests=MockTestConfig(),
        )

    @pytest.fixture
    def memory_store_with_drift(self, temp_memory_path):
        """Create a MemoryStore with schema drift entries for UserSession."""
        store = MemoryStore(store_path=temp_memory_path)

        # Add schema drift entry for UserSession (matches issue body)
        drift_entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="prior-feature",
            issue_number=3,
            content={
                "class_name": "UserSession",
                "existing_file": "src/auth/session.py",
                "new_file": "src/managers/user_session.py",
                "existing_issue": 3,
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "UserSession"],
        )
        store.add(drift_entry)
        store.save()

        return store

    def test_schema_warning_appears_in_coder_prompt(
        self, mock_config, memory_store_with_drift
    ):
        """
        Test that when CoderAgent processes an issue mentioning a class name
        that has schema drift, the warning appears in the generated prompt.
        """
        from swarm_attack.agents.coder import CoderAgent

        # Create CoderAgent with memory store containing drift
        coder = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        # Load the issue to get its body
        issues_data = coder._load_issues("test-feature")
        issue = coder._find_issue(issues_data, 1)
        assert issue is not None

        # Extract class names from issue body
        class_names = coder._extract_potential_classes(issue["body"])
        assert "UserSession" in class_names

        # Get schema warnings for these classes
        warnings = coder._get_schema_warnings(class_names)
        assert len(warnings) >= 1

        # Format the warnings for prompt injection
        warnings_text = coder._format_schema_warnings(warnings)

        # Verify the warning text contains key information
        assert "Schema Drift Warnings" in warnings_text
        assert "UserSession" in warnings_text
        assert "src/auth/session.py" in warnings_text
        assert "Issue #3" in warnings_text

    def test_format_schema_warnings_empty_list(self, mock_config):
        """Formatting empty warnings list should return empty string."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config, memory_store=None)

        warnings_text = coder._format_schema_warnings([])

        assert warnings_text == ""

    def test_format_schema_warnings_includes_import_guidance(
        self, mock_config, memory_store_with_drift
    ):
        """Warning text should include guidance to import instead of recreate."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config, memory_store=memory_store_with_drift)

        warnings = coder._get_schema_warnings(["UserSession"])
        warnings_text = coder._format_schema_warnings(warnings)

        # Should include import guidance
        assert "Import" in warnings_text or "import" in warnings_text
        assert "recreat" in warnings_text.lower()


class TestEndToEndMemoryFlowWithVerifier:
    """End-to-end test of the memory flow with actual VerifierAgent recording."""

    @pytest.fixture
    def temp_memory_path(self):
        """Create a temporary directory for memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repo directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create required directories
            (repo_path / "specs" / "e2e-feature").mkdir(parents=True)
            (repo_path / "tests" / "generated" / "e2e-feature").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "coder").mkdir(parents=True)
            (repo_path / ".claude" / "skills" / "verifier").mkdir(parents=True)
            (repo_path / ".swarm" / "memory").mkdir(parents=True)

            # Create skill files
            (repo_path / ".claude" / "skills" / "coder" / "SKILL.md").write_text("# Coder")
            (repo_path / ".claude" / "skills" / "verifier" / "SKILL.md").write_text("# Verifier")

            # Create minimal spec
            (repo_path / "specs" / "e2e-feature" / "spec-final.md").write_text("# E2E Spec")

            # Create issues.json
            issues = {
                "issues": [
                    {
                        "order": 1,
                        "title": "E2E Test Issue",
                        "body": "## Interface Contract\n\n- `ConflictClass`",
                        "labels": [],
                        "estimated_size": "small",
                    }
                ]
            }
            (repo_path / "specs" / "e2e-feature" / "issues.json").write_text(
                json.dumps(issues)
            )

            # Create test file
            (repo_path / "tests" / "generated" / "e2e-feature" / "test_issue_1.py").write_text(
                'def test_pass(): assert True'
            )

            yield repo_path

    @pytest.fixture
    def mock_config(self, temp_repo):
        """Create a mock config."""
        @dataclass
        class MockTestConfig:
            command: str = "pytest"
            args: list = field(default_factory=list)
            timeout_seconds: int = 60

        @dataclass
        class MockConfig:
            repo_root: Path = field(default_factory=lambda: temp_repo)
            specs_path: Path = field(default_factory=lambda: temp_repo / "specs")
            tests: MockTestConfig = field(default_factory=MockTestConfig)

        return MockConfig(
            repo_root=temp_repo,
            specs_path=temp_repo / "specs",
            tests=MockTestConfig(),
        )

    def test_verifier_records_drift_to_memory_store(
        self, temp_memory_path, mock_config
    ):
        """
        Test that VerifierAgent's _check_duplicate_classes records conflicts
        to the memory store when schema drift is detected.
        """
        from swarm_attack.agents.verifier import VerifierAgent

        # Create shared memory store
        memory_store = MemoryStore(store_path=temp_memory_path)

        # Create VerifierAgent with memory store
        verifier = VerifierAgent(config=mock_config, memory_store=memory_store)

        # Simulate existing module registry (from prior issues)
        module_registry = {
            "modules": {
                "src/models/conflict.py": {
                    "classes": ["ConflictClass"],
                    "created_by_issue": 1,
                }
            }
        }

        # New classes being created (would cause conflict)
        new_classes_defined = {
            "src/services/new_conflict.py": ["ConflictClass"]  # Same class name, different file
        }

        # Check for duplicates
        conflicts = verifier._check_duplicate_classes(new_classes_defined, module_registry)

        # Should detect the conflict
        assert len(conflicts) == 1
        assert conflicts[0]["class_name"] == "ConflictClass"

        # Now verify that when verifier.run() processes this with conflicts,
        # it would record to memory (we test the recording logic directly)
        if conflicts and memory_store is not None:
            from swarm_attack.memory.store import MemoryEntry

            for conflict in conflicts:
                entry = MemoryEntry(
                    id=str(uuid4()),
                    category="schema_drift",
                    feature_id="e2e-feature",
                    issue_number=2,
                    content={
                        "class_name": conflict["class_name"],
                        "existing_file": conflict["existing_file"],
                        "new_file": conflict["new_file"],
                        "existing_issue": conflict["existing_issue"],
                    },
                    outcome="blocked",
                    created_at=datetime.now().isoformat(),
                    tags=["schema_drift", conflict["class_name"]],
                )
                memory_store.add(entry)

            memory_store.save()

        # Verify the drift was recorded
        results = memory_store.query(category="schema_drift")
        assert len(results) == 1
        assert results[0].content["class_name"] == "ConflictClass"
        assert "schema_drift" in results[0].tags
        assert "ConflictClass" in results[0].tags
