# Migration Guide

## v0.1.x to v0.2.0

### Class Renames (pytest Collection Fix)

Several classes were renamed to avoid pytest collecting them as test classes. All old names remain available as aliases for backward compatibility.

#### Config Classes

```python
# Old (still works via alias)
from swarm_attack.config import TestRunnerConfig

# New (recommended)
from swarm_attack.config import ExecutorConfig
```

#### Recovery Classes

```python
# Old (still works via alias)
from swarm_attack.recovery import TestRunResult
from swarm_attack.recovery import TestRunner

# New (recommended)
from swarm_attack.recovery import ExecutionResult
from swarm_attack.recovery import Executor
```

#### Edge Case Classes

```python
# Old (still works via alias)
from swarm_attack.edge_cases import TestFailureError
from swarm_attack.edge_cases import TestFailureHandler

# New (recommended)
from swarm_attack.edge_cases import ExecutionFailureError
from swarm_attack.edge_cases import FailureHandler
```

#### Bug Model Classes

```python
# Old (still works via alias)
from swarm_attack.bug_models import TestCase

# New (recommended)
from swarm_attack.bug_models import BugTestCase
```

#### Chief of Staff Classes

```python
# Old (still works via alias)
from swarm_attack.chief_of_staff.validation_gates import TestValidationGate
from swarm_attack.chief_of_staff.critics import TestCritic
from swarm_attack.chief_of_staff.backlog_discovery import TestFailureDiscoveryAgent

# New (recommended)
from swarm_attack.chief_of_staff.validation_gates import TestingValidationGate
from swarm_attack.chief_of_staff.critics import TestingCritic
# Note: FailureDiscoveryAgent must be imported from the submodule directly
from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import FailureDiscoveryAgent
```

### Complete Rename Table

| Module | Old Name | New Name |
|--------|----------|----------|
| `config` | `TestRunnerConfig` | `ExecutorConfig` |
| `recovery` | `TestRunResult` | `ExecutionResult` |
| `recovery` | `TestRunner` | `Executor` |
| `edge_cases` | `TestFailureError` | `ExecutionFailureError` |
| `edge_cases` | `TestFailureHandler` | `FailureHandler` |
| `bug_models` | `TestCase` | `BugTestCase` |
| `chief_of_staff.validation_gates` | `TestValidationGate` | `TestingValidationGate` |
| `chief_of_staff.critics` | `TestCritic` | `TestingCritic` |
| `chief_of_staff.backlog_discovery` | `TestFailureDiscoveryAgent` | `FailureDiscoveryAgent` |

### New Validation Module

A new validation module provides input validation utilities:

```python
from swarm_attack.validation.input_validator import InputValidator, ValidationError

# Validate feature ID - returns validated string or ValidationError
result = InputValidator.validate_feature_id("my-feature")
if isinstance(result, ValidationError):
    print(f"Error: {result.message}")
    print(f"Expected: {result.expected}")
    print(f"Got: {result.got}")
    print(f"Hint: {result.hint}")
else:
    print(f"Valid feature ID: {result}")

# Validate positive integer
result = InputValidator.validate_positive_int(42, "issue_number")

# Validate positive float
result = InputValidator.validate_positive_float(10.0, "budget")

# Validate path is within project
result = InputValidator.validate_path_in_project(Path("src/file.py"), project_root)
```

### New Code Extraction Function

The coder module now exports a utility function for extracting code from LLM responses:

```python
from swarm_attack.agents.coder import extract_code_from_response

# Extract code from markdown-formatted LLM response
response = '''
Here's the implementation:

```python
def hello():
    return "world"
```

This function returns "world".
'''

code = extract_code_from_response(response)
# Returns: 'def hello():\n    return "world"'
```

### Verifier Schema Drift Detection

The Verifier agent now supports schema drift detection. To use it, provide `module_registry` and `new_classes_defined` in the context:

```python
context = {
    "module_registry": {
        "models/user.py": ["User", "UserProfile"],
        "models/admin.py": ["Admin"],
    },
    "new_classes_defined": {
        "services/user.py": ["UserService"],
    },
}

result = verifier.run(context)
if result.schema_conflicts:
    print("Schema drift detected:", result.schema_conflicts)
```

### TaskRef Validation

`TaskRef` now validates that `issue_number` is >= 1:

```python
from swarm_attack.models import TaskRef

# This now raises ValueError
task = TaskRef(feature_id="my-feature", issue_number=0)  # ValueError!

# Valid usage
task = TaskRef(feature_id="my-feature", issue_number=1)  # OK
```

### Checkpoint Auto-Cleanup

Checkpoints older than 8 days are now automatically cleaned up when listing:

```bash
swarm-attack cos checkpoints list
# Automatically removes checkpoints older than 8 days
```

### pytest Configuration

If you have a custom `pytest.ini` or `pyproject.toml` pytest config, ensure it's compatible with:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

## Breaking Changes

None. All changes are backward compatible via aliases.

## Deprecation Timeline

The old class names (via aliases) will be supported indefinitely, but new code should use the new names.
