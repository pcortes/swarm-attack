# Continue QA Documentation & Coverage via TDD

## Current State

The Adaptive QA Agent implementation is **complete** with comprehensive test coverage.

### Test Summary (821 tests passing)

| Category | Tests | Status |
|----------|-------|--------|
| Unit Tests | ~531 | ✅ All passing |
| Integration Tests | ~290 | ✅ All passing |
| **Total** | **821** | ✅ **All passing** |

### Coverage Report

| Module | Coverage |
|--------|----------|
| models.py | 100% |
| orchestrator.py | 91% |
| context_builder.py | 83% |
| depth_selector.py | 99% |
| **TOTAL** | **80%** |

### Recently Completed (Priority 13-14)

| File | Tests | Description |
|------|-------|-------------|
| `test_documentation.py` | 10 | API doc generation |
| `test_coverage.py` | 8 | Coverage validation |
| `test_system_validation.py` | 23 | Full QA flow end-to-end |
| `test_api_surface.py` | 65 | Public API documentation |
| `test_performance.py` | 27 | Performance benchmarks |

---

## Working Directory

```
/Users/philipjcortes/Desktop/swarm-attack-qa-agent/
```

Use the same worktree. Do NOT create a new branch or worktree.

---

## Git Strategy

### When to Commit

Commit after completing each priority task:

1. **After Priority 13** (API Docs Generation) - commit with message describing docs tooling
2. **After Priority 14** (Coverage Report) - commit with message describing coverage setup
3. **After Priority 15** (Update prompt file) - commit the updated documentation

### Commit Command Pattern

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
git add -A
git commit -m "$(cat <<'EOF'
feat(qa): add API documentation generation

- Add sphinx/pdoc configuration for auto-generating API docs
- Add tests verifying documentation completeness
- Generate initial API reference documentation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### When to Push to Main

**Push to main/prod ONLY after:**

1. All 803+ tests still pass
2. New tests for the feature pass
3. No regressions in existing functionality
4. Coverage report shows no decrease (if applicable)

```bash
# Verify before push
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ -v

# If all pass, push
git push origin main
```

---

## Priority 13: API Documentation Generation

### Goal
Auto-generate API documentation from code docstrings and type hints.

### Task
1. Choose documentation tool (pdoc recommended for simplicity)
2. Write tests that verify documentation can be generated
3. Generate initial documentation
4. Store in `docs/api/` directory

### Test File Location
Create: `tests/integration/qa/test_documentation.py`

### Test Structure

```python
"""Documentation Generation Tests.

Verifies API documentation can be generated and is complete.
"""

import subprocess
from pathlib import Path

import pytest


class TestDocumentationGeneration:
    """Tests for documentation generation."""

    def test_pdoc_can_generate_docs(self, tmp_path):
        """pdoc should generate documentation without errors."""
        result = subprocess.run(
            ["python", "-m", "pdoc", "swarm_attack.qa", "-o", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"pdoc failed: {result.stderr}"

    def test_all_public_modules_documented(self, tmp_path):
        """All public QA modules should have generated docs."""
        subprocess.run(
            ["python", "-m", "pdoc", "swarm_attack.qa", "-o", str(tmp_path)],
            capture_output=True,
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
        subprocess.run(
            ["python", "-m", "pdoc", "swarm_attack.qa", "-o", str(tmp_path)],
            capture_output=True,
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
```

### Implementation Steps

1. Install pdoc: `pip install pdoc`
2. Write the tests above (TDD - they will fail initially if pdoc not installed)
3. Run pdoc to generate docs
4. Verify tests pass
5. Commit

### Generate Docs Command

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
python -m pdoc swarm_attack.qa -o docs/api --html
```

---

## Priority 14: Coverage Report

### Goal
Add test coverage tracking and establish baseline.

### Task
1. Configure pytest-cov
2. Write tests that verify coverage thresholds
3. Generate coverage report
4. Add coverage badge/config

### Test File Location
Create: `tests/integration/qa/test_coverage.py`

### Test Structure

```python
"""Coverage Validation Tests.

Verifies test coverage meets minimum thresholds.
"""

import subprocess
import json
from pathlib import Path

import pytest


class TestCoverageThresholds:
    """Tests for coverage thresholds."""

    @pytest.fixture
    def coverage_data(self, tmp_path):
        """Run coverage and return data."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/", "tests/integration/qa/",
                f"--cov=swarm_attack/qa",
                "--cov-report=json",
                f"--cov-report=json:{tmp_path}/coverage.json",
                "-q"
            ],
            capture_output=True,
            text=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env={"PYTHONPATH": "."},
        )

        coverage_file = tmp_path / "coverage.json"
        if coverage_file.exists():
            return json.loads(coverage_file.read_text())
        return None

    def test_overall_coverage_above_threshold(self, coverage_data):
        """Overall coverage should be above 80%."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        total = coverage_data.get("totals", {})
        percent = total.get("percent_covered", 0)

        assert percent >= 80, f"Coverage {percent}% below 80% threshold"

    def test_orchestrator_coverage(self, coverage_data):
        """Orchestrator should have high coverage."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        files = coverage_data.get("files", {})
        orch_key = [k for k in files.keys() if "orchestrator.py" in k]

        if orch_key:
            percent = files[orch_key[0]].get("summary", {}).get("percent_covered", 0)
            assert percent >= 85, f"Orchestrator coverage {percent}% below 85%"

    def test_models_coverage(self, coverage_data):
        """Models should have high coverage."""
        if coverage_data is None:
            pytest.skip("Coverage data not available")

        files = coverage_data.get("files", {})
        models_key = [k for k in files.keys() if "models.py" in k]

        if models_key:
            percent = files[models_key[0]].get("summary", {}).get("percent_covered", 0)
            assert percent >= 90, f"Models coverage {percent}% below 90%"


class TestCoverageReportGeneration:
    """Tests for coverage report generation."""

    def test_html_report_generates(self, tmp_path):
        """HTML coverage report should generate."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/test_models.py",  # Just one file for speed
                "--cov=swarm_attack/qa/models",
                f"--cov-report=html:{tmp_path}/htmlcov",
                "-q"
            ],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env={"PYTHONPATH": "."},
        )

        assert (tmp_path / "htmlcov" / "index.html").exists()

    def test_xml_report_generates(self, tmp_path):
        """XML coverage report should generate (for CI)."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "tests/unit/qa/test_models.py",
                "--cov=swarm_attack/qa/models",
                f"--cov-report=xml:{tmp_path}/coverage.xml",
                "-q"
            ],
            capture_output=True,
            cwd="/Users/philipjcortes/Desktop/swarm-attack-qa-agent",
            env={"PYTHONPATH": "."},
        )

        assert (tmp_path / "coverage.xml").exists()
```

### Coverage Configuration

Add to `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["swarm_attack/qa"]
branch = true
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80

[tool.coverage.html]
directory = "htmlcov"
```

### Generate Coverage Report

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ \
    --cov=swarm_attack/qa \
    --cov-report=html \
    --cov-report=term-missing
```

---

## Priority 15: Update Documentation

### Goal
Update the continuation prompt with final state.

### Task
After completing Priorities 13-14:
1. Update this file with actual test counts
2. Document any issues encountered
3. Add learnings for future teams

---

## Verification Commands

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent

# Run all tests (should be 803+)
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ -v

# Run with coverage
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ \
    --cov=swarm_attack/qa \
    --cov-report=term-missing

# Generate API docs
python -m pdoc swarm_attack.qa -o docs/api --html

# Count tests
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ --collect-only | tail -5
```

---

## TDD Workflow Reminder

1. **Write test first** - Test should fail
2. **Implement minimum code** - Make test pass
3. **Refactor if needed** - Keep tests passing
4. **Commit** - After each priority completes

---

## Dependencies to Install

```bash
pip install pdoc pytest-cov
```

---

## Notes for Team

1. **Always use PYTHONPATH=.** when running tests
2. **821 tests currently passing** - don't regress!
3. **Commit after each priority** - don't batch commits
4. **Push only when all tests pass** - verify before push
5. **Use the same worktree** - `/Users/philipjcortes/Desktop/swarm-attack-qa-agent/`

---

## Final State (Completed 2025-12-27)

| Metric | Before | After |
|--------|--------|-------|
| Tests | 803 | 821 |
| Coverage | Unknown | 80% |
| API Docs | None | Generated in `docs/api/` |
| Commits | 0 | 2 |

### Commits Made

1. `c440fa8` - feat(qa): add API documentation generation
2. `b16dd0b` - feat(qa): add test coverage tracking and reporting

---

## Commit Checklist

Before each commit:
- [ ] All existing tests pass (803+)
- [ ] New tests pass
- [ ] No linting errors
- [ ] Coverage not decreased

Before push to main:
- [ ] All above checks pass
- [ ] Documentation generates without errors
- [ ] Coverage report generates without errors
