# Agent Contracts Implementation Prompt (TDD)

<mission>
You are orchestrating a **Team of Specialized Experts** to implement formalized Agent Contracts using strict **Test-Driven Development (TDD)** methodology.

This feature introduces TypedDict-based validation for all agent input/output, catching contract violations early and improving debugging.
</mission>

---

<team_structure>

| Expert | Role | Responsibility |
|--------|------|----------------|
| **Architect** | Design Lead | Review existing agents, define contract schemas, identify common patterns |
| **TestWriter** | RED Phase | Write comprehensive failing tests FIRST |
| **Coder** | GREEN Phase | Implement minimal code to pass all tests |
| **Integrator** | Wiring | Update BaseAgent to validate contracts, ensure backward compatibility |
| **Reviewer** | Validation | Run full test suite, verify no regressions |

</team_structure>

---

<background_context>

<existing_code>

**Current Agent Pattern** in `swarm_attack/agents/base.py`:

```python
class BaseAgent(ABC):
    """Base class for all agents."""

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        """Execute the agent with given context."""
        pass


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    text: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
```

</existing_code>

<limitations>

1. `context: dict` - No schema validation, any keys accepted
2. No type hints for expected context keys
3. Runtime errors when agents receive wrong context structure
4. Hard to debug which agent expects which fields
5. No documentation of agent contracts

</limitations>

<problem_example>

```python
# CoderAgent expects:
context = {
    "feature_id": str,
    "issue_number": int,
    "issue_body": str,
    "module_registry": dict,
    "completed_summaries": list,
}

# But caller passes:
context = {
    "feature": "my-feature",  # Wrong key!
    "issue": 1,                # Wrong key!
}
# Results in cryptic KeyError deep in agent code
```

</problem_example>

</background_context>

---

<interface_contract>

```python
# File: swarm_attack/contracts.py

from typing import TypedDict, Optional, Any, NotRequired
from dataclasses import dataclass


# ============================================================================
# Base Contract Types
# ============================================================================

class BaseAgentInput(TypedDict, total=False):
    """Base input contract all agents inherit from."""
    feature_id: str
    issue_number: int


class BaseAgentOutput(TypedDict):
    """Base output contract all agents produce."""
    success: bool
    error: NotRequired[str]


# ============================================================================
# CoderAgent Contracts
# ============================================================================

class CoderInput(TypedDict):
    """Input contract for CoderAgent."""
    feature_id: str
    issue_number: int
    issue_body: str
    issue_title: str
    spec_content: NotRequired[str]
    module_registry: NotRequired[dict[str, Any]]
    completed_summaries: NotRequired[list[dict[str, Any]]]
    test_file_path: NotRequired[str]
    max_turns: NotRequired[int]


class CoderOutput(TypedDict):
    """Output contract for CoderAgent."""
    success: bool
    files_created: list[str]
    files_modified: list[str]
    classes_defined: dict[str, list[str]]
    test_file: NotRequired[str]
    error: NotRequired[str]
    iterations: NotRequired[int]


# ============================================================================
# VerifierAgent Contracts
# ============================================================================

class VerifierInput(TypedDict):
    """Input contract for VerifierAgent."""
    feature_id: str
    issue_number: int
    issue_title: str
    test_file_path: str
    files_created: list[str]
    classes_defined: NotRequired[dict[str, list[str]]]
    module_registry: NotRequired[dict[str, Any]]


class VerifierOutput(TypedDict):
    """Output contract for VerifierAgent."""
    success: bool
    tests_passed: bool
    commit_sha: NotRequired[str]
    error: NotRequired[str]
    schema_conflicts: NotRequired[list[dict[str, str]]]


# ============================================================================
# IssueCreatorAgent Contracts
# ============================================================================

class IssueCreatorInput(TypedDict):
    """Input contract for IssueCreatorAgent."""
    feature_id: str
    spec_content: str
    max_issues: NotRequired[int]


class IssueCreatorOutput(TypedDict):
    """Output contract for IssueCreatorAgent."""
    success: bool
    issues_created: list[dict[str, Any]]  # [{number, title, body, labels}]
    error: NotRequired[str]


# ============================================================================
# SpecAuthorAgent Contracts
# ============================================================================

class SpecAuthorInput(TypedDict):
    """Input contract for SpecAuthorAgent."""
    feature_id: str
    prd_content: str


class SpecAuthorOutput(TypedDict):
    """Output contract for SpecAuthorAgent."""
    success: bool
    spec_content: str
    error: NotRequired[str]


# ============================================================================
# SpecCriticAgent Contracts
# ============================================================================

class SpecCriticInput(TypedDict):
    """Input contract for SpecCriticAgent."""
    feature_id: str
    spec_content: str
    prd_content: str
    round_number: NotRequired[int]


class SpecCriticOutput(TypedDict):
    """Output contract for SpecCriticAgent."""
    success: bool
    score: float  # 0.0 to 1.0
    feedback: str
    error: NotRequired[str]


# ============================================================================
# Contract Validation
# ============================================================================

class ContractValidationError(Exception):
    """Raised when agent input/output doesn't match contract."""

    def __init__(
        self,
        agent_name: str,
        contract_type: str,  # "input" or "output"
        missing_keys: list[str],
        extra_keys: list[str],
        type_errors: dict[str, str],
    ):
        self.agent_name = agent_name
        self.contract_type = contract_type
        self.missing_keys = missing_keys
        self.extra_keys = extra_keys
        self.type_errors = type_errors

        msg = f"{agent_name} {contract_type} contract violation:"
        if missing_keys:
            msg += f"\n  Missing required keys: {missing_keys}"
        if extra_keys:
            msg += f"\n  Unexpected keys: {extra_keys}"
        if type_errors:
            for key, err in type_errors.items():
                msg += f"\n  Type error for '{key}': {err}"

        super().__init__(msg)


class ContractValidator:
    """Validates agent input/output against TypedDict contracts."""

    @classmethod
    def validate_input(
        cls,
        agent_name: str,
        data: dict,
        contract: type,
        strict: bool = False,
    ) -> None:
        """
        Validate input data against contract.

        Args:
            agent_name: Name of the agent (for error messages).
            data: Input dict to validate.
            contract: TypedDict class defining the contract.
            strict: If True, raise on extra keys. If False, warn only.

        Raises:
            ContractValidationError: If validation fails.
        """
        pass

    @classmethod
    def validate_output(
        cls,
        agent_name: str,
        data: dict,
        contract: type,
    ) -> None:
        """
        Validate output data against contract.

        Args:
            agent_name: Name of the agent (for error messages).
            data: Output dict to validate.
            contract: TypedDict class defining the contract.

        Raises:
            ContractValidationError: If validation fails.
        """
        pass

    @classmethod
    def _get_required_keys(cls, contract: type) -> set[str]:
        """Get required keys from TypedDict (those without NotRequired)."""
        pass

    @classmethod
    def _get_optional_keys(cls, contract: type) -> set[str]:
        """Get optional keys from TypedDict (those with NotRequired)."""
        pass

    @classmethod
    def _check_types(cls, data: dict, contract: type) -> dict[str, str]:
        """Check types of values against contract annotations."""
        pass


# ============================================================================
# Contract Registry
# ============================================================================

AGENT_CONTRACTS: dict[str, tuple[type, type]] = {
    # agent_name: (InputContract, OutputContract)
    "CoderAgent": (CoderInput, CoderOutput),
    "VerifierAgent": (VerifierInput, VerifierOutput),
    "IssueCreatorAgent": (IssueCreatorInput, IssueCreatorOutput),
    "SpecAuthorAgent": (SpecAuthorInput, SpecAuthorOutput),
    "SpecCriticAgent": (SpecCriticInput, SpecCriticOutput),
}


def get_contract(agent_name: str) -> tuple[type, type] | None:
    """Get input/output contract for an agent."""
    return AGENT_CONTRACTS.get(agent_name)


def register_contract(agent_name: str, input_contract: type, output_contract: type) -> None:
    """Register a new agent contract."""
    AGENT_CONTRACTS[agent_name] = (input_contract, output_contract)
```

</interface_contract>

---

<acceptance_criteria>

<core_functionality>

- [ ] `CoderInput`, `CoderOutput` TypedDict contracts defined
- [ ] `VerifierInput`, `VerifierOutput` TypedDict contracts defined
- [ ] `IssueCreatorInput`, `IssueCreatorOutput` TypedDict contracts defined
- [ ] `SpecAuthorInput`, `SpecAuthorOutput` TypedDict contracts defined
- [ ] `SpecCriticInput`, `SpecCriticOutput` TypedDict contracts defined
- [ ] `ContractValidator.validate_input()` validates required keys
- [ ] `ContractValidator.validate_output()` validates required keys
- [ ] `AGENT_CONTRACTS` registry maps agent names to contracts

</core_functionality>

<validation_behavior>

- [ ] Missing required keys raises `ContractValidationError`
- [ ] Extra keys in strict mode raises error
- [ ] Extra keys in non-strict mode logs warning (doesn't raise)
- [ ] Type mismatches detected and reported
- [ ] `NotRequired` keys are truly optional

</validation_behavior>

<error_messages>

- [ ] `ContractValidationError` includes agent name
- [ ] Error lists all missing required keys
- [ ] Error lists unexpected keys (strict mode)
- [ ] Error includes type mismatch details

</error_messages>

<backward_compatibility>

- [ ] Existing agents continue to work without changes
- [ ] Validation is opt-in (not enforced by default initially)
- [ ] No breaking changes to `AgentResult` class

</backward_compatibility>

</acceptance_criteria>

---

<tdd_protocol>

<phase name="RED" description="Write Failing Tests">

Create `tests/unit/test_agent_contracts.py`:

```python
"""Unit tests for Agent Contracts.

Tests follow TDD RED phase - all tests should FAIL initially.
"""
import pytest
from typing import get_type_hints

from swarm_attack.contracts import (
    CoderInput,
    CoderOutput,
    VerifierInput,
    VerifierOutput,
    IssueCreatorInput,
    IssueCreatorOutput,
    SpecAuthorInput,
    SpecAuthorOutput,
    SpecCriticInput,
    SpecCriticOutput,
    ContractValidator,
    ContractValidationError,
    AGENT_CONTRACTS,
    get_contract,
    register_contract,
)


class TestCoderContracts:
    """Tests for CoderAgent input/output contracts."""

    def test_coder_input_has_required_keys(self):
        """CoderInput should require essential keys."""
        hints = get_type_hints(CoderInput, include_extras=True)

        assert "feature_id" in hints
        assert "issue_number" in hints
        assert "issue_body" in hints
        assert "issue_title" in hints

    def test_coder_input_has_optional_keys(self):
        """CoderInput should have optional context keys."""
        hints = get_type_hints(CoderInput, include_extras=True)

        # These should be NotRequired
        assert "module_registry" in hints
        assert "completed_summaries" in hints
        assert "spec_content" in hints

    def test_coder_output_has_required_keys(self):
        """CoderOutput should require success and file info."""
        hints = get_type_hints(CoderOutput, include_extras=True)

        assert "success" in hints
        assert "files_created" in hints
        assert "files_modified" in hints
        assert "classes_defined" in hints


class TestVerifierContracts:
    """Tests for VerifierAgent contracts."""

    def test_verifier_input_has_required_keys(self):
        """VerifierInput should require essential keys."""
        hints = get_type_hints(VerifierInput, include_extras=True)

        assert "feature_id" in hints
        assert "issue_number" in hints
        assert "test_file_path" in hints
        assert "files_created" in hints

    def test_verifier_output_has_required_keys(self):
        """VerifierOutput should include test results."""
        hints = get_type_hints(VerifierOutput, include_extras=True)

        assert "success" in hints
        assert "tests_passed" in hints


class TestContractValidatorInput:
    """Tests for ContractValidator.validate_input()."""

    def test_valid_input_passes(self):
        """Valid input matching contract should not raise."""
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
        }

        # Should not raise
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_missing_required_key_raises(self):
        """Missing required key should raise ContractValidationError."""
        data = {
            "feature_id": "test-feature",
            # Missing: issue_number, issue_body, issue_title
        }

        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input("CoderAgent", data, CoderInput)

        assert "issue_number" in exc_info.value.missing_keys
        assert "issue_body" in exc_info.value.missing_keys

    def test_extra_keys_strict_mode_raises(self):
        """Extra keys in strict mode should raise."""
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
            "unexpected_key": "value",
        }

        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input(
                "CoderAgent", data, CoderInput, strict=True
            )

        assert "unexpected_key" in exc_info.value.extra_keys

    def test_extra_keys_non_strict_mode_passes(self):
        """Extra keys in non-strict mode should not raise."""
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
            "unexpected_key": "value",
        }

        # Should not raise (default is non-strict)
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_optional_keys_can_be_omitted(self):
        """NotRequired keys should be truly optional."""
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
            # Omitting: module_registry, completed_summaries, spec_content
        }

        # Should not raise
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_type_mismatch_detected(self):
        """Wrong type for a key should be detected."""
        data = {
            "feature_id": "test-feature",
            "issue_number": "not-an-int",  # Should be int
            "issue_body": "Test body",
            "issue_title": "Test title",
        }

        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input("CoderAgent", data, CoderInput)

        assert "issue_number" in exc_info.value.type_errors


class TestContractValidatorOutput:
    """Tests for ContractValidator.validate_output()."""

    def test_valid_output_passes(self):
        """Valid output matching contract should not raise."""
        data = {
            "success": True,
            "files_created": ["test.py"],
            "files_modified": [],
            "classes_defined": {"test.py": ["TestClass"]},
        }

        # Should not raise
        ContractValidator.validate_output("CoderAgent", data, CoderOutput)

    def test_missing_required_output_key_raises(self):
        """Missing required output key should raise."""
        data = {
            "success": True,
            # Missing: files_created, files_modified, classes_defined
        }

        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_output("CoderAgent", data, CoderOutput)

        assert "files_created" in exc_info.value.missing_keys


class TestContractValidationError:
    """Tests for ContractValidationError exception."""

    def test_error_includes_agent_name(self):
        """Error message should include agent name."""
        error = ContractValidationError(
            agent_name="TestAgent",
            contract_type="input",
            missing_keys=["key1"],
            extra_keys=[],
            type_errors={},
        )

        assert "TestAgent" in str(error)

    def test_error_lists_missing_keys(self):
        """Error message should list missing keys."""
        error = ContractValidationError(
            agent_name="TestAgent",
            contract_type="input",
            missing_keys=["key1", "key2"],
            extra_keys=[],
            type_errors={},
        )

        assert "key1" in str(error)
        assert "key2" in str(error)

    def test_error_lists_extra_keys(self):
        """Error message should list extra keys."""
        error = ContractValidationError(
            agent_name="TestAgent",
            contract_type="input",
            missing_keys=[],
            extra_keys=["extra1", "extra2"],
            type_errors={},
        )

        assert "extra1" in str(error)
        assert "extra2" in str(error)

    def test_error_includes_type_errors(self):
        """Error message should include type mismatch details."""
        error = ContractValidationError(
            agent_name="TestAgent",
            contract_type="input",
            missing_keys=[],
            extra_keys=[],
            type_errors={"field1": "expected int, got str"},
        )

        assert "field1" in str(error)
        assert "expected int" in str(error)


class TestContractRegistry:
    """Tests for AGENT_CONTRACTS registry."""

    def test_coder_agent_registered(self):
        """CoderAgent should be in registry."""
        assert "CoderAgent" in AGENT_CONTRACTS

        input_contract, output_contract = AGENT_CONTRACTS["CoderAgent"]
        assert input_contract == CoderInput
        assert output_contract == CoderOutput

    def test_verifier_agent_registered(self):
        """VerifierAgent should be in registry."""
        assert "VerifierAgent" in AGENT_CONTRACTS

    def test_get_contract_returns_tuple(self):
        """get_contract should return (input, output) tuple."""
        result = get_contract("CoderAgent")

        assert result is not None
        assert len(result) == 2
        assert result[0] == CoderInput
        assert result[1] == CoderOutput

    def test_get_contract_returns_none_for_unknown(self):
        """get_contract should return None for unknown agent."""
        result = get_contract("UnknownAgent")

        assert result is None

    def test_register_contract_adds_to_registry(self):
        """register_contract should add new agent to registry."""
        from typing import TypedDict

        class TestInput(TypedDict):
            test_key: str

        class TestOutput(TypedDict):
            success: bool

        register_contract("TestAgent", TestInput, TestOutput)

        assert "TestAgent" in AGENT_CONTRACTS
        assert get_contract("TestAgent") == (TestInput, TestOutput)

        # Cleanup
        del AGENT_CONTRACTS["TestAgent"]


class TestHelperMethods:
    """Tests for ContractValidator helper methods."""

    def test_get_required_keys_extracts_required(self):
        """Should extract keys without NotRequired."""
        required = ContractValidator._get_required_keys(CoderInput)

        assert "feature_id" in required
        assert "issue_number" in required
        assert "issue_body" in required

    def test_get_optional_keys_extracts_optional(self):
        """Should extract keys with NotRequired."""
        optional = ContractValidator._get_optional_keys(CoderInput)

        assert "module_registry" in optional
        assert "completed_summaries" in optional
        assert "spec_content" in optional

    def test_check_types_detects_mismatches(self):
        """Should detect type mismatches."""
        data = {
            "feature_id": 123,  # Should be str
            "issue_number": "not-int",  # Should be int
        }

        errors = ContractValidator._check_types(data, CoderInput)

        assert "feature_id" in errors
        assert "issue_number" in errors
```

**Verify RED phase:**
```bash
pytest tests/unit/test_agent_contracts.py -v
# Expected: ALL TESTS FAIL (contracts.py doesn't exist yet)
```

</phase>

<phase name="GREEN" description="Implement to Pass Tests">

Create `swarm_attack/contracts.py`:

1. Implement all TypedDict contract classes
2. Implement `ContractValidationError` exception
3. Implement `ContractValidator` class with all methods
4. Implement `AGENT_CONTRACTS` registry
5. Implement `get_contract()` and `register_contract()` functions

<implementation_notes>

- Use `typing.get_type_hints()` with `include_extras=True` to get NotRequired info
- Use `typing.get_origin()` and `typing.get_args()` for type checking
- For NotRequired detection, check if `typing.NotRequired` is in the type annotation

</implementation_notes>

**Verify GREEN phase:**
```bash
pytest tests/unit/test_agent_contracts.py -v
# Expected: ALL TESTS PASS
```

</phase>

<phase name="REFACTOR" description="Clean Up + Integration">

<optional_integration>

Add validation to BaseAgent (opt-in for gradual rollout):

```python
# In swarm_attack/agents/base.py

class BaseAgent(ABC):
    _validate_contracts: bool = False  # Off by default

    def run(self, context: dict) -> AgentResult:
        if self._validate_contracts:
            contract = get_contract(self.__class__.__name__)
            if contract:
                ContractValidator.validate_input(
                    self.__class__.__name__, context, contract[0]
                )

        result = self._run_impl(context)

        if self._validate_contracts:
            contract = get_contract(self.__class__.__name__)
            if contract:
                ContractValidator.validate_output(
                    self.__class__.__name__, result, contract[1]
                )

        return result
```

</optional_integration>

**Verify REFACTOR phase:**
```bash
pytest tests/ -v --tb=short
# Expected: Full test suite passes, no regressions
```

</phase>

</tdd_protocol>

---

<pattern_references>

<existing_agent_result>

From `swarm_attack/agents/base.py`:

```python
@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    text: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
```

</existing_agent_result>

<typeddict_with_notrequired>

From Python 3.11+ typing:

```python
from typing import TypedDict, NotRequired

class MyTypedDict(TypedDict):
    required_key: str
    optional_key: NotRequired[int]
```

</typeddict_with_notrequired>

<runtime_type_checking>

```python
from typing import get_type_hints, get_origin, get_args, NotRequired

def is_notrequired(annotation):
    """Check if annotation is NotRequired."""
    origin = get_origin(annotation)
    return origin is NotRequired

def get_inner_type(annotation):
    """Get inner type from NotRequired[T]."""
    if is_notrequired(annotation):
        args = get_args(annotation)
        return args[0] if args else None
    return annotation
```

</runtime_type_checking>

</pattern_references>

---

<files_to_create>

| File | Purpose |
|------|---------|
| `swarm_attack/contracts.py` | Main implementation |
| `tests/unit/test_agent_contracts.py` | Unit tests (TDD) |

</files_to_create>

<files_to_modify>

| File | Change |
|------|--------|
| `swarm_attack/agents/base.py` | Add optional contract validation (optional) |
| `swarm_attack/__init__.py` | Export contracts module (optional) |

</files_to_modify>

---

<success_criteria>

Phase complete when:

1. [ ] All unit tests in `test_agent_contracts.py` pass
2. [ ] All 5 agent contracts defined (Coder, Verifier, IssueCreator, SpecAuthor, SpecCritic)
3. [ ] `ContractValidator` validates required/optional keys
4. [ ] `ContractValidator` detects type mismatches
5. [ ] `ContractValidationError` provides helpful error messages
6. [ ] `AGENT_CONTRACTS` registry maps agents to contracts
7. [ ] Full test suite passes (no regressions)
8. [ ] Code reviewed for patterns consistency

</success_criteria>

---

<execution_command>

To run this implementation:

```
Execute specs/context-optimization/AGENT_CONTRACTS_TDD_PROMPT.md using TDD methodology.

Phase 1 (RED): Create tests/unit/test_agent_contracts.py with all tests - verify they FAIL
Phase 2 (GREEN): Create swarm_attack/contracts.py - verify all tests PASS
Phase 3 (REFACTOR): Run full test suite, clean up code
```

</execution_command>

---

<future_enhancements>

These are NOT part of this implementation but could be added later:

1. **Pydantic Integration** - Use Pydantic models instead of TypedDict for richer validation
2. **Contract Documentation Generation** - Auto-generate docs from contracts
3. **Contract Versioning** - Support multiple versions of contracts
4. **Strict Mode by Default** - Enable strict validation in production
5. **JSON Schema Export** - Export contracts as JSON Schema for external tools

</future_enhancements>

---

<references>

- **Parent Spec:** `specs/context-optimization/IMPLEMENTATION_PROMPT.md` (Catalog Entry 2)
- **Existing Agents:** `swarm_attack/agents/*.py`
- **AgentResult:** `swarm_attack/agents/base.py:AgentResult`
- **XML Guidelines:** See `CLAUDE.md` section "XML Prompt Engineering Guidelines"

</references>
