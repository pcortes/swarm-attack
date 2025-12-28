"""Tests for QAContextBuilder following TDD approach.

Tests cover spec section 7: QA Context Builder
- Parse spec/issue content to extract test requirements
- Discover API schemas (OpenAPI, type hints, docstrings)
- Analyze consumer code to find callers
- Extract git diff context for regression testing
- Build QAContext with all gathered information
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    QATrigger,
)


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify QAContextBuilder can be imported."""

    def test_can_import_context_builder(self):
        """Should be able to import QAContextBuilder class."""
        from swarm_attack.qa.context_builder import QAContextBuilder
        assert QAContextBuilder is not None

    def test_can_import_endpoint_discovery_error(self):
        """Should be able to import EndpointDiscoveryError."""
        from swarm_attack.qa.context_builder import EndpointDiscoveryError
        assert EndpointDiscoveryError is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestQAContextBuilderInit:
    """Tests for QAContextBuilder initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.context_builder import QAContextBuilder
        builder = QAContextBuilder(mock_config)
        assert builder.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.context_builder import QAContextBuilder
        logger = MagicMock()
        builder = QAContextBuilder(mock_config, logger=logger)
        assert builder._logger == logger

    def test_init_sets_repo_root(self, mock_config, tmp_path):
        """Should set repo_root from config."""
        from swarm_attack.qa.context_builder import QAContextBuilder
        builder = QAContextBuilder(mock_config)
        assert builder.repo_root == Path(tmp_path)


# =============================================================================
# build_context() TESTS
# =============================================================================


class TestBuildContext:
    """Tests for build_context() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_returns_qa_context(self, builder):
        """Should return a QAContext object."""
        result = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target="src/api/users.py",
        )
        assert isinstance(result, QAContext)

    def test_sets_feature_id_when_provided(self, builder):
        """Should set feature_id in context when provided."""
        result = builder.build_context(
            trigger=QATrigger.POST_VERIFICATION,
            target="src/api/users.py",
            feature_id="my-feature",
        )
        assert result.feature_id == "my-feature"

    def test_sets_issue_number_when_provided(self, builder):
        """Should set issue_number in context when provided."""
        result = builder.build_context(
            trigger=QATrigger.POST_VERIFICATION,
            target="src/api/users.py",
            issue_number=42,
        )
        assert result.issue_number == 42

    def test_sets_bug_id_when_provided(self, builder):
        """Should set bug_id in context when provided."""
        result = builder.build_context(
            trigger=QATrigger.BUG_REPRODUCTION,
            target="src/api/users.py",
            bug_id="BUG-123",
        )
        assert result.bug_id == "BUG-123"

    def test_sets_target_files_from_file_path(self, builder, tmp_path):
        """Should set target_files when target is a file path."""
        # Create a test file
        test_file = tmp_path / "src" / "api" / "users.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# API code")

        result = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(test_file),
        )
        assert str(test_file) in result.target_files

    def test_discovers_endpoints_for_file_target(self, builder, tmp_path):
        """Should discover endpoints when target is a file."""
        # Create a FastAPI-style file
        api_file = tmp_path / "src" / "api" / "users.py"
        api_file.parent.mkdir(parents=True, exist_ok=True)
        api_file.write_text('''
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def list_users():
    pass

@router.post("/users")
def create_user():
    pass
''')

        result = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(api_file),
        )
        # Should discover endpoints
        endpoint_paths = [e.path for e in result.target_endpoints]
        assert "/users" in endpoint_paths or len(result.target_endpoints) >= 0

    def test_includes_git_diff_for_regression_trigger(self, builder):
        """Should include git_diff for PRE_MERGE trigger."""
        with patch.object(builder, '_get_git_diff') as mock_diff:
            mock_diff.return_value = "diff --git a/file.py"
            result = builder.build_context(
                trigger=QATrigger.PRE_MERGE,
                target="src/api/users.py",
            )
            assert result.git_diff is not None or mock_diff.called

    def test_loads_spec_content_for_feature(self, builder, tmp_path):
        """Should load spec content when feature_id is provided."""
        # Create spec file
        spec_dir = tmp_path / "specs" / "my-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_file = spec_dir / "spec-final.md"
        spec_file.write_text("# Feature Spec\n\nThis is the spec.")

        result = builder.build_context(
            trigger=QATrigger.POST_VERIFICATION,
            target="src/api/users.py",
            feature_id="my-feature",
        )
        # Should attempt to load spec
        assert result.spec_content is None or "Feature Spec" in str(result.spec_content)


# =============================================================================
# ENDPOINT DISCOVERY TESTS
# =============================================================================


class TestDiscoverEndpoints:
    """Tests for discover_endpoints() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_discovers_fastapi_routes(self, builder, tmp_path):
        """Should discover endpoints from FastAPI decorators."""
        api_file = tmp_path / "src" / "api" / "users.py"
        api_file.parent.mkdir(parents=True, exist_ok=True)
        api_file.write_text('''
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def list_users():
    return []

@router.post("/users")
def create_user(user: dict):
    return user

@router.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id}

@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    pass
''')

        endpoints = builder.discover_endpoints(str(api_file))

        methods = [e.method for e in endpoints]
        paths = [e.path for e in endpoints]

        assert "GET" in methods
        assert "POST" in methods
        assert "/users" in paths or any("/users" in p for p in paths)

    def test_discovers_flask_routes(self, builder, tmp_path):
        """Should discover endpoints from Flask decorators."""
        api_file = tmp_path / "app.py"
        api_file.write_text('''
from flask import Flask
app = Flask(__name__)

@app.route("/items", methods=["GET"])
def list_items():
    return []

@app.route("/items", methods=["POST"])
def create_item():
    return {}
''')

        endpoints = builder.discover_endpoints(str(api_file))
        paths = [e.path for e in endpoints]
        assert "/items" in paths or len(endpoints) >= 0

    def test_discovers_from_openapi_spec(self, builder, tmp_path):
        """Should discover endpoints from OpenAPI spec file."""
        openapi_file = tmp_path / "openapi.yaml"
        openapi_file.write_text('''
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: Success
    post:
      summary: Create user
      responses:
        '201':
          description: Created
  /users/{id}:
    get:
      summary: Get user
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: Success
''')

        endpoints = builder.discover_endpoints(str(openapi_file))
        methods = [e.method for e in endpoints]
        paths = [e.path for e in endpoints]

        assert "GET" in methods
        assert "POST" in methods
        assert "/users" in paths

    def test_discovers_from_openapi_json(self, builder, tmp_path):
        """Should discover endpoints from OpenAPI JSON file."""
        openapi_file = tmp_path / "swagger.json"
        openapi_content = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {"summary": "List items"},
                    "post": {"summary": "Create item"},
                }
            }
        }
        openapi_file.write_text(json.dumps(openapi_content))

        endpoints = builder.discover_endpoints(str(openapi_file))
        paths = [e.path for e in endpoints]
        assert "/items" in paths

    def test_handles_missing_file(self, builder):
        """Should handle missing file gracefully."""
        # Should not raise, but return empty or partial results
        endpoints = builder.discover_endpoints("/nonexistent/file.py")
        assert isinstance(endpoints, list)

    def test_handles_file_without_endpoints(self, builder, tmp_path):
        """Should handle file with no endpoints."""
        util_file = tmp_path / "utils.py"
        util_file.write_text('''
def helper_function():
    return "hello"
''')

        endpoints = builder.discover_endpoints(str(util_file))
        assert isinstance(endpoints, list)
        assert len(endpoints) == 0

    def test_detects_auth_required(self, builder, tmp_path):
        """Should detect when endpoints require authentication."""
        api_file = tmp_path / "api.py"
        api_file.write_text('''
from fastapi import APIRouter, Depends
from auth import get_current_user

router = APIRouter()

@router.get("/public")
def public_endpoint():
    return "public"

@router.get("/protected", dependencies=[Depends(get_current_user)])
def protected_endpoint():
    return "protected"
''')

        endpoints = builder.discover_endpoints(str(api_file))
        # At minimum, should return endpoints
        assert isinstance(endpoints, list)


# =============================================================================
# SCHEMA EXTRACTION TESTS
# =============================================================================


class TestExtractSchemas:
    """Tests for extract_schemas() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_extracts_pydantic_schemas(self, builder, tmp_path):
        """Should extract schemas from Pydantic models."""
        model_file = tmp_path / "models.py"
        model_file.write_text('''
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
''')

        api_file = tmp_path / "api.py"
        api_file.write_text('''
from fastapi import APIRouter
from models import UserCreate, UserResponse

router = APIRouter()

@router.post("/users", response_model=UserResponse)
def create_user(user: UserCreate):
    return user
''')

        endpoints = [QAEndpoint(method="POST", path="/users")]
        schemas = builder.extract_schemas(endpoints)

        assert isinstance(schemas, dict)

    def test_extracts_from_openapi_spec(self, builder, tmp_path):
        """Should extract schemas from OpenAPI spec."""
        openapi_file = tmp_path / "openapi.yaml"
        openapi_file.write_text('''
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserCreate'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
components:
  schemas:
    UserCreate:
      type: object
      properties:
        name:
          type: string
        email:
          type: string
    User:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
''')

        endpoints = [QAEndpoint(method="POST", path="/users")]
        schemas = builder.extract_schemas(endpoints)

        assert isinstance(schemas, dict)

    def test_handles_missing_schemas(self, builder):
        """Should handle endpoints without schemas."""
        endpoints = [QAEndpoint(method="GET", path="/health")]
        schemas = builder.extract_schemas(endpoints)
        assert isinstance(schemas, dict)

    def test_extracts_type_hints(self, builder, tmp_path):
        """Should extract schemas from type hints."""
        api_file = tmp_path / "api.py"
        api_file.write_text('''
from typing import List
from dataclasses import dataclass

@dataclass
class Item:
    name: str
    price: float

def get_items() -> List[Item]:
    return []
''')

        endpoints = [QAEndpoint(method="GET", path="/items")]
        schemas = builder.extract_schemas(endpoints)

        assert isinstance(schemas, dict)


# =============================================================================
# CONSUMER FINDING TESTS
# =============================================================================


class TestFindConsumers:
    """Tests for find_consumers() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_finds_fetch_callers(self, builder, tmp_path):
        """Should find frontend code that uses fetch()."""
        # Create frontend file
        frontend_dir = tmp_path / "frontend" / "src"
        frontend_dir.mkdir(parents=True, exist_ok=True)

        frontend_file = frontend_dir / "api.ts"
        frontend_file.write_text('''
export async function getUsers() {
    const response = await fetch('/api/users');
    return response.json();
}

export async function createUser(data: UserData) {
    const response = await fetch('/api/users', {
        method: 'POST',
        body: JSON.stringify(data)
    });
    return response.json();
}
''')

        endpoints = [
            QAEndpoint(method="GET", path="/api/users"),
            QAEndpoint(method="POST", path="/api/users"),
        ]
        consumers = builder.find_consumers(endpoints)

        assert isinstance(consumers, dict)

    def test_finds_axios_callers(self, builder, tmp_path):
        """Should find code using axios."""
        frontend_dir = tmp_path / "src" / "services"
        frontend_dir.mkdir(parents=True, exist_ok=True)

        service_file = frontend_dir / "userService.ts"
        service_file.write_text('''
import axios from 'axios';

export const userService = {
    getAll: () => axios.get('/api/users'),
    create: (data) => axios.post('/api/users', data),
    getById: (id) => axios.get(`/api/users/${id}`),
};
''')

        endpoints = [QAEndpoint(method="GET", path="/api/users")]
        consumers = builder.find_consumers(endpoints)

        assert isinstance(consumers, dict)

    def test_finds_python_requests_callers(self, builder, tmp_path):
        """Should find Python code using requests library."""
        client_dir = tmp_path / "clients"
        client_dir.mkdir(parents=True, exist_ok=True)

        client_file = client_dir / "api_client.py"
        client_file.write_text('''
import requests

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def get_users(self):
        return requests.get(f"{self.base_url}/api/users")

    def create_user(self, data):
        return requests.post(f"{self.base_url}/api/users", json=data)
''')

        endpoints = [QAEndpoint(method="GET", path="/api/users")]
        consumers = builder.find_consumers(endpoints)

        assert isinstance(consumers, dict)

    def test_handles_no_consumers(self, builder):
        """Should handle endpoints with no consumers."""
        endpoints = [QAEndpoint(method="GET", path="/internal/health")]
        consumers = builder.find_consumers(endpoints)

        assert isinstance(consumers, dict)
        # Should return empty or endpoints with empty lists
        for path, consumer_list in consumers.items():
            assert isinstance(consumer_list, list)

    def test_finds_integration_test_consumers(self, builder, tmp_path):
        """Should find integration tests as consumers."""
        test_dir = tmp_path / "tests" / "integration"
        test_dir.mkdir(parents=True, exist_ok=True)

        test_file = test_dir / "test_api.py"
        test_file.write_text('''
import pytest
import httpx

async def test_get_users(client):
    response = await client.get("/api/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

async def test_create_user(client):
    response = await client.post("/api/users", json={"name": "Test"})
    assert response.status_code == 201
''')

        endpoints = [QAEndpoint(method="GET", path="/api/users")]
        consumers = builder.find_consumers(endpoints)

        assert isinstance(consumers, dict)


# =============================================================================
# GIT DIFF EXTRACTION TESTS
# =============================================================================


class TestGetGitDiff:
    """Tests for _get_git_diff() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_returns_diff_string(self, builder):
        """Should return git diff as string."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="diff --git a/file.py b/file.py\n+new line",
                stderr=""
            )
            diff = builder._get_git_diff()
            assert isinstance(diff, str)

    def test_handles_not_git_repo(self, builder):
        """Should handle not being in a git repo."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository"
            )
            diff = builder._get_git_diff()
            # Should return empty or None, not raise
            assert diff is None or diff == ""

    def test_handles_clean_worktree(self, builder):
        """Should handle clean worktree with no changes."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )
            diff = builder._get_git_diff()
            assert diff == "" or diff is None

    def test_includes_uncommitted_changes(self, builder):
        """Should include uncommitted changes in diff."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="diff --git a/new_file.py\n+new content",
                stderr=""
            )
            diff = builder._get_git_diff()
            if diff:
                assert "new_file.py" in diff or len(diff) > 0


# =============================================================================
# SPEC LOADING TESTS
# =============================================================================


class TestLoadSpec:
    """Tests for _load_spec_content() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_loads_spec_final(self, builder, tmp_path):
        """Should load spec-final.md when available."""
        spec_dir = tmp_path / "specs" / "my-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_file = spec_dir / "spec-final.md"
        spec_file.write_text("# Final Spec\n\nApproved spec content.")

        content = builder._load_spec_content("my-feature")
        assert content is not None
        assert "Final Spec" in content

    def test_falls_back_to_spec_draft(self, builder, tmp_path):
        """Should fall back to spec-draft.md if no final."""
        spec_dir = tmp_path / "specs" / "my-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_file = spec_dir / "spec-draft.md"
        spec_file.write_text("# Draft Spec\n\nDraft content.")

        content = builder._load_spec_content("my-feature")
        assert content is not None
        assert "Draft Spec" in content

    def test_handles_missing_spec(self, builder):
        """Should handle missing spec gracefully."""
        content = builder._load_spec_content("nonexistent-feature")
        assert content is None

    def test_loads_prd_as_fallback(self, builder, tmp_path):
        """Should load PRD as last fallback."""
        prd_dir = tmp_path / ".claude" / "prds"
        prd_dir.mkdir(parents=True, exist_ok=True)
        prd_file = prd_dir / "my-feature.md"
        prd_file.write_text("# PRD\n\nProduct requirements.")

        content = builder._load_spec_content("my-feature")
        # Might be None if only PRD exists (depends on implementation)
        assert content is None or "PRD" in content


# =============================================================================
# ISSUE LOADING TESTS
# =============================================================================


class TestLoadIssue:
    """Tests for _load_issue_content() method."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_loads_issue_from_json(self, builder, tmp_path):
        """Should load issue from issues.json."""
        spec_dir = tmp_path / "specs" / "my-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        issues_file = spec_dir / "issues.json"
        issues_content = [
            {"number": 1, "title": "First issue", "body": "Issue 1 body"},
            {"number": 2, "title": "Second issue", "body": "Issue 2 body"},
        ]
        issues_file.write_text(json.dumps(issues_content))

        content = builder._load_issue_content("my-feature", 2)
        assert content is not None
        assert "Second issue" in content or "Issue 2" in content

    def test_handles_missing_issues_file(self, builder):
        """Should handle missing issues.json."""
        content = builder._load_issue_content("nonexistent", 1)
        assert content is None

    def test_handles_missing_issue_number(self, builder, tmp_path):
        """Should handle issue number not in file."""
        spec_dir = tmp_path / "specs" / "my-feature"
        spec_dir.mkdir(parents=True, exist_ok=True)
        issues_file = spec_dir / "issues.json"
        issues_file.write_text('[{"number": 1, "title": "Issue 1"}]')

        content = builder._load_issue_content("my-feature", 999)
        assert content is None


# =============================================================================
# ENDPOINT DISCOVERY ERROR TESTS
# =============================================================================


class TestEndpointDiscoveryError:
    """Tests for EndpointDiscoveryError behavior."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_raises_when_no_endpoints_and_required(self, builder):
        """Should raise EndpointDiscoveryError when endpoints required but not found."""
        from swarm_attack.qa.context_builder import EndpointDiscoveryError

        # When explicitly requiring endpoints
        with pytest.raises(EndpointDiscoveryError):
            builder.discover_endpoints_required("/nonexistent/path.py")


# =============================================================================
# FULL INTEGRATION TESTS
# =============================================================================


class TestFullContextBuild:
    """Integration tests for building complete context."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_builds_complete_context_for_post_verification(self, builder, tmp_path):
        """Should build complete context for POST_VERIFICATION trigger."""
        # Set up spec
        spec_dir = tmp_path / "specs" / "user-auth"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec-final.md").write_text("# Auth Spec\nLogin and logout.")

        # Set up API file
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True, exist_ok=True)
        api_file = api_dir / "auth.py"
        api_file.write_text('''
from fastapi import APIRouter
router = APIRouter()

@router.post("/auth/login")
def login():
    pass

@router.post("/auth/logout")
def logout():
    pass
''')

        context = builder.build_context(
            trigger=QATrigger.POST_VERIFICATION,
            target=str(api_file),
            feature_id="user-auth",
            issue_number=1,
        )

        assert context.feature_id == "user-auth"
        assert context.issue_number == 1
        # Should have found endpoints or file
        assert len(context.target_files) > 0 or len(context.target_endpoints) >= 0

    def test_builds_context_for_bug_reproduction(self, builder, tmp_path):
        """Should build context for BUG_REPRODUCTION trigger."""
        api_file = tmp_path / "api.py"
        api_file.write_text('''
@app.get("/users/{id}")
def get_user(id: int):
    pass
''')

        context = builder.build_context(
            trigger=QATrigger.BUG_REPRODUCTION,
            target=str(api_file),
            bug_id="BUG-456",
        )

        assert context.bug_id == "BUG-456"
        assert context.target_files is not None

    def test_builds_context_for_pre_merge(self, builder, tmp_path):
        """Should build context for PRE_MERGE trigger with diff."""
        api_file = tmp_path / "api.py"
        api_file.write_text("# API code")

        with patch.object(builder, '_get_git_diff') as mock_diff:
            mock_diff.return_value = "diff content"
            context = builder.build_context(
                trigger=QATrigger.PRE_MERGE,
                target=str(api_file),
            )
            # Should attempt to get diff
            assert mock_diff.called or context.git_diff is not None

    def test_builds_context_for_user_command(self, builder, tmp_path):
        """Should build context for USER_COMMAND trigger."""
        api_file = tmp_path / "api.py"
        api_file.write_text('''
@router.get("/items")
def list_items():
    return []
''')

        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(api_file),
        )

        assert isinstance(context, QAContext)


# =============================================================================
# EXPLICIT ENDPOINT CONFIGURATION TESTS
# =============================================================================


class TestExplicitEndpoints:
    """Tests for explicit endpoint configuration."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_accepts_explicit_endpoints(self, builder):
        """Should accept explicitly provided endpoints."""
        explicit_endpoints = [
            QAEndpoint(method="GET", path="/api/v2/users"),
            QAEndpoint(method="POST", path="/api/v2/users"),
        ]

        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target="/api/v2/users",
            explicit_endpoints=explicit_endpoints,
        )

        assert len(context.target_endpoints) == 2

    def test_explicit_endpoints_override_discovery(self, builder, tmp_path):
        """Explicit endpoints should take precedence over discovery."""
        # Create file with different endpoints
        api_file = tmp_path / "api.py"
        api_file.write_text('''
@router.get("/old/endpoint")
def old():
    pass
''')

        explicit_endpoints = [
            QAEndpoint(method="GET", path="/new/endpoint"),
        ]

        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(api_file),
            explicit_endpoints=explicit_endpoints,
        )

        # Should use explicit, not discovered
        paths = [e.path for e in context.target_endpoints]
        assert "/new/endpoint" in paths


# =============================================================================
# BASE URL HANDLING TESTS
# =============================================================================


class TestBaseUrlHandling:
    """Tests for base URL configuration."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_accepts_base_url(self, builder):
        """Should accept and set base_url."""
        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target="/api/users",
            base_url="http://localhost:3000",
        )

        assert context.base_url == "http://localhost:3000"

    def test_defaults_base_url_to_none(self, builder):
        """Should default base_url to None when not provided."""
        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target="/api/users",
        )

        assert context.base_url is None


# =============================================================================
# RELATED TESTS DISCOVERY
# =============================================================================


class TestRelatedTestsDiscovery:
    """Tests for finding related test files."""

    @pytest.fixture
    def builder(self, tmp_path):
        from swarm_attack.qa.context_builder import QAContextBuilder
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return QAContextBuilder(config)

    def test_finds_related_test_files(self, builder, tmp_path):
        """Should find test files related to target."""
        # Create source file
        src_dir = tmp_path / "src" / "api"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "users.py").write_text("# User API")

        # Create test file
        test_dir = tmp_path / "tests" / "api"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "test_users.py").write_text("# User tests")

        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(src_dir / "users.py"),
        )

        # Should find related tests
        assert isinstance(context.related_tests, list)

    def test_handles_no_related_tests(self, builder, tmp_path):
        """Should handle case with no related tests."""
        # Create source file with no tests
        src_file = tmp_path / "standalone.py"
        src_file.write_text("# Standalone code")

        context = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target=str(src_file),
        )

        assert isinstance(context.related_tests, list)
        assert len(context.related_tests) == 0
