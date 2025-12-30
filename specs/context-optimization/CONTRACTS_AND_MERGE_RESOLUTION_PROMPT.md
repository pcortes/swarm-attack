# Agent Contracts + Merge Resolution Implementation Prompt

<mission>
You are orchestrating a **Team of Specialized Experts** to complete two sequential tasks:

1. **Task 1:** Implement Agent Contracts via strict TDD (create `swarm_attack/contracts.py`)
2. **Task 2:** Research and evaluate Merge Resolution Helpers, then design implementation if warranted

Both tasks follow TDD methodology where applicable.
</mission>

---

<team_structure>

| Expert | Role | Responsibility |
|--------|------|----------------|
| **Architect** | Design Lead | Review existing patterns, define interfaces, evaluate trade-offs |
| **TestWriter** | RED Phase | Write comprehensive failing tests FIRST |
| **Coder** | GREEN Phase | Implement minimal code to pass all tests |
| **Integrator** | Wiring | Update BaseAgent, ensure backward compatibility |
| **Researcher** | Analysis | Investigate merge conflicts, evaluate approaches |
| **Reviewer** | Validation | Run full test suite, verify no regressions |

</team_structure>

---

# TASK 1: Agent Contracts Implementation (TDD)

<task_1_overview>

Implement TypedDict-based validation for all agent input/output, catching contract violations early and improving debugging.

**Files to Create:**
- `swarm_attack/contracts.py` - Main implementation
- `tests/unit/test_agent_contracts.py` - Unit tests

</task_1_overview>

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
    issues_created: list[dict[str, Any]]
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
    score: float
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
        contract_type: str,
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
    def validate_input(cls, agent_name: str, data: dict, contract: type, strict: bool = False) -> None:
        """Validate input data against contract."""
        pass

    @classmethod
    def validate_output(cls, agent_name: str, data: dict, contract: type) -> None:
        """Validate output data against contract."""
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

<tdd_protocol_task_1>

<phase name="RED" description="Write Failing Tests">

Create `tests/unit/test_agent_contracts.py` with ALL tests from the spec:

```python
"""Unit tests for Agent Contracts.

TDD RED Phase - All tests should FAIL initially.
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
        hints = get_type_hints(CoderInput, include_extras=True)
        assert "feature_id" in hints
        assert "issue_number" in hints
        assert "issue_body" in hints
        assert "issue_title" in hints

    def test_coder_input_has_optional_keys(self):
        hints = get_type_hints(CoderInput, include_extras=True)
        assert "module_registry" in hints
        assert "completed_summaries" in hints
        assert "spec_content" in hints

    def test_coder_output_has_required_keys(self):
        hints = get_type_hints(CoderOutput, include_extras=True)
        assert "success" in hints
        assert "files_created" in hints
        assert "files_modified" in hints
        assert "classes_defined" in hints


class TestVerifierContracts:
    def test_verifier_input_has_required_keys(self):
        hints = get_type_hints(VerifierInput, include_extras=True)
        assert "feature_id" in hints
        assert "issue_number" in hints
        assert "test_file_path" in hints
        assert "files_created" in hints

    def test_verifier_output_has_required_keys(self):
        hints = get_type_hints(VerifierOutput, include_extras=True)
        assert "success" in hints
        assert "tests_passed" in hints


class TestContractValidatorInput:
    def test_valid_input_passes(self):
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
        }
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_missing_required_key_raises(self):
        data = {"feature_id": "test-feature"}
        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input("CoderAgent", data, CoderInput)
        assert "issue_number" in exc_info.value.missing_keys
        assert "issue_body" in exc_info.value.missing_keys

    def test_extra_keys_strict_mode_raises(self):
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
            "unexpected_key": "value",
        }
        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input("CoderAgent", data, CoderInput, strict=True)
        assert "unexpected_key" in exc_info.value.extra_keys

    def test_extra_keys_non_strict_mode_passes(self):
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
            "unexpected_key": "value",
        }
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_optional_keys_can_be_omitted(self):
        data = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "issue_body": "Test body",
            "issue_title": "Test title",
        }
        ContractValidator.validate_input("CoderAgent", data, CoderInput)

    def test_type_mismatch_detected(self):
        data = {
            "feature_id": "test-feature",
            "issue_number": "not-an-int",
            "issue_body": "Test body",
            "issue_title": "Test title",
        }
        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_input("CoderAgent", data, CoderInput)
        assert "issue_number" in exc_info.value.type_errors


class TestContractValidatorOutput:
    def test_valid_output_passes(self):
        data = {
            "success": True,
            "files_created": ["test.py"],
            "files_modified": [],
            "classes_defined": {"test.py": ["TestClass"]},
        }
        ContractValidator.validate_output("CoderAgent", data, CoderOutput)

    def test_missing_required_output_key_raises(self):
        data = {"success": True}
        with pytest.raises(ContractValidationError) as exc_info:
            ContractValidator.validate_output("CoderAgent", data, CoderOutput)
        assert "files_created" in exc_info.value.missing_keys


class TestContractValidationError:
    def test_error_includes_agent_name(self):
        error = ContractValidationError(
            agent_name="TestAgent",
            contract_type="input",
            missing_keys=["key1"],
            extra_keys=[],
            type_errors={},
        )
        assert "TestAgent" in str(error)

    def test_error_lists_missing_keys(self):
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
    def test_coder_agent_registered(self):
        assert "CoderAgent" in AGENT_CONTRACTS
        input_contract, output_contract = AGENT_CONTRACTS["CoderAgent"]
        assert input_contract == CoderInput
        assert output_contract == CoderOutput

    def test_verifier_agent_registered(self):
        assert "VerifierAgent" in AGENT_CONTRACTS

    def test_get_contract_returns_tuple(self):
        result = get_contract("CoderAgent")
        assert result is not None
        assert len(result) == 2
        assert result[0] == CoderInput
        assert result[1] == CoderOutput

    def test_get_contract_returns_none_for_unknown(self):
        result = get_contract("UnknownAgent")
        assert result is None

    def test_register_contract_adds_to_registry(self):
        from typing import TypedDict

        class TestInput(TypedDict):
            test_key: str

        class TestOutput(TypedDict):
            success: bool

        register_contract("TestAgent", TestInput, TestOutput)
        assert "TestAgent" in AGENT_CONTRACTS
        assert get_contract("TestAgent") == (TestInput, TestOutput)
        del AGENT_CONTRACTS["TestAgent"]


class TestHelperMethods:
    def test_get_required_keys_extracts_required(self):
        required = ContractValidator._get_required_keys(CoderInput)
        assert "feature_id" in required
        assert "issue_number" in required
        assert "issue_body" in required

    def test_get_optional_keys_extracts_optional(self):
        optional = ContractValidator._get_optional_keys(CoderInput)
        assert "module_registry" in optional
        assert "completed_summaries" in optional
        assert "spec_content" in optional

    def test_check_types_detects_mismatches(self):
        data = {
            "feature_id": 123,
            "issue_number": "not-int",
        }
        errors = ContractValidator._check_types(data, CoderInput)
        assert "feature_id" in errors
        assert "issue_number" in errors
```

**Verify RED phase:**
```bash
pytest tests/unit/test_agent_contracts.py -v
# Expected: ALL TESTS FAIL (contracts.py doesn't exist)
```

</phase>

<phase name="GREEN" description="Implement to Pass Tests">

Create `swarm_attack/contracts.py` implementing:

1. All TypedDict contract classes
2. `ContractValidationError` exception with all fields
3. `ContractValidator` class with all methods
4. `AGENT_CONTRACTS` registry
5. `get_contract()` and `register_contract()` functions

<implementation_notes>

- Use `typing.get_type_hints()` with `include_extras=True` to get NotRequired info
- Use `typing.get_origin()` and `typing.get_args()` for type checking
- For NotRequired detection: `get_origin(annotation) is NotRequired`

</implementation_notes>

**Verify GREEN phase:**
```bash
pytest tests/unit/test_agent_contracts.py -v
# Expected: ALL TESTS PASS
```

</phase>

<phase name="REFACTOR" description="Clean Up + Full Suite">

```bash
pytest tests/ -v --tb=short
# Expected: Full test suite passes, no regressions
```

</phase>

</tdd_protocol_task_1>

---

<task_1_success_criteria>

Task 1 complete when:

1. [ ] All unit tests in `test_agent_contracts.py` pass
2. [ ] All 5 agent contracts defined (Coder, Verifier, IssueCreator, SpecAuthor, SpecCritic)
3. [ ] `ContractValidator` validates required/optional keys
4. [ ] `ContractValidator` detects type mismatches
5. [ ] `ContractValidationError` provides helpful error messages
6. [ ] `AGENT_CONTRACTS` registry maps agents to contracts
7. [ ] Full test suite passes (no regressions)

</task_1_success_criteria>

---

# TASK 2: Merge Resolution Helpers Research & Design

<task_2_overview>

After Task 1 is complete, research whether Intelligent Merge Resolution is a good implementation for Swarm Attack.

**Reference:** `specs/context-optimization/IMPLEMENTATION_PROMPT.md` - Catalog Entry 3

**Goal:** Investigate, evaluate, and if warranted, design a TDD implementation spec.

</task_2_overview>

---

<research_protocol>

<phase name="RESEARCH" description="Understand the Problem Space">

**1. Investigate current merge conflict handling:**
```
Glob "swarm_attack/**/*.py"
Grep "merge|conflict|git" swarm_attack/
Read swarm_attack/agents/verifier.py
```

**2. Find where merge conflicts occur:**
- When do they happen in the current pipeline?
- How are they currently handled?
- What is the failure rate?

**3. Search for existing patterns:**
```
Grep "subprocess.*git" swarm_attack/
Grep "GitPython|dulwich" swarm_attack/
```

</phase>

<phase name="EVALUATE" description="Assess Whether Implementation is Warranted">

Answer these questions:

**1. Problem Frequency:**
- How often do merge conflicts occur in practice?
- Search `.swarm/` for conflict-related failures
- Check episode history for merge-related errors

**2. Current Cost:**
- What happens when a merge conflict occurs today?
- Does it fail the entire issue implementation?
- How much human intervention is required?

**3. Proposed Solution Value:**
- The spec suggests "~98% token savings" - is this realistic?
- Three-tier approach: auto-merge → conflict-only AI → full-file AI
- Is the complexity justified by the frequency of the problem?

**4. Implementation Complexity:**
- What git operations are needed?
- How do we detect conflict regions?
- How do we invoke AI for just the conflict parts?

</phase>

<phase name="DECISION" description="Recommend Go/No-Go">

Based on research, recommend ONE of:

**Option A: Implement Now**
- Problem is frequent and costly
- Solution is well-defined
- Proceed to TDD spec

**Option B: Defer**
- Problem is rare
- Current handling is acceptable
- Document for future consideration

**Option C: Simplify**
- Full solution is over-engineered
- Propose simpler alternative (e.g., just auto-retry with rebase)

</phase>

</research_protocol>

---

<merge_resolution_spec_template>

If DECISION is "Implement Now", create this spec:

```markdown
# Intelligent Merge Resolution Implementation (TDD)

<mission>
Implement AI-driven conflict resolution with tiered approach:
1. Auto-merge (no AI needed)
2. Conflict-only AI (send just conflict regions)
3. Full-file AI (fallback for complex cases)
</mission>

<interface_contract>

```python
# File: swarm_attack/merge_resolver.py

@dataclass
class ConflictRegion:
    """A single conflict region in a file."""
    file_path: str
    ours: str      # Our version (HEAD)
    theirs: str    # Their version (incoming)
    base: str      # Common ancestor
    start_line: int
    end_line: int


@dataclass
class MergeResult:
    """Result of a merge resolution attempt."""
    success: bool
    resolved_files: list[str]
    remaining_conflicts: list[ConflictRegion]
    strategy_used: str  # "auto", "conflict_only_ai", "full_file_ai"
    error: str | None


class MergeResolver:
    """Intelligent merge conflict resolver."""

    def __init__(self, repo_root: Path, llm_runner = None):
        pass

    def detect_conflicts(self) -> list[ConflictRegion]:
        """Detect all conflict regions in working tree."""
        pass

    def auto_merge(self, conflicts: list[ConflictRegion]) -> MergeResult:
        """Attempt automatic resolution without AI."""
        pass

    def resolve_conflict_only(self, conflict: ConflictRegion) -> str:
        """Use AI to resolve just this conflict region."""
        pass

    def resolve_full_file(self, file_path: str) -> str:
        """Use AI to resolve entire file (fallback)."""
        pass

    def resolve_all(self) -> MergeResult:
        """
        Tiered resolution:
        1. Try auto-merge for all
        2. For remaining, try conflict-only AI
        3. For still remaining, try full-file AI
        """
        pass
```

</interface_contract>

<acceptance_criteria>
- [ ] `detect_conflicts()` finds all conflict markers
- [ ] `auto_merge()` handles trivial conflicts (whitespace, etc.)
- [ ] `resolve_conflict_only()` sends minimal context to AI
- [ ] Token usage is ~98% lower than full-file for conflict-only
- [ ] Graceful fallback when conflict-only fails
</acceptance_criteria>

<test_file>tests/unit/test_merge_resolver.py</test_file>
```

</merge_resolution_spec_template>

---

<task_2_deliverables>

After Task 2 research, produce ONE of:

**If "Implement Now":**
- Create `specs/context-optimization/MERGE_RESOLUTION_TDD_PROMPT.md`
- Include full TDD spec with tests and interface contract

**If "Defer":**
- Update `specs/context-optimization/IMPLEMENTATION_PROMPT.md` with findings
- Add note explaining why deferred and when to revisit

**If "Simplify":**
- Propose simpler alternative
- Create mini-spec for simplified approach

</task_2_deliverables>

---

<execution_command>

```
Execute this prompt in two phases:

PHASE 1: Agent Contracts (TDD)
1. RED: Create tests/unit/test_agent_contracts.py - verify tests FAIL
2. GREEN: Create swarm_attack/contracts.py - verify tests PASS
3. REFACTOR: Run full test suite - verify no regressions

PHASE 2: Merge Resolution Research
1. RESEARCH: Investigate current merge handling
2. EVALUATE: Assess problem frequency and solution value
3. DECISION: Recommend Go/No-Go/Simplify
4. DELIVERABLE: Create appropriate spec or documentation

Report findings after each phase.
```

</execution_command>

---

<references>

- **Agent Contracts Spec:** `specs/context-optimization/AGENT_CONTRACTS_TDD_PROMPT.md`
- **Parent Spec:** `specs/context-optimization/IMPLEMENTATION_PROMPT.md`
- **Existing Agents:** `swarm_attack/agents/*.py`
- **State Store:** `swarm_attack/state_store.py`
- **Verifier Agent:** `swarm_attack/agents/verifier.py`
- **XML Guidelines:** `CLAUDE.md` section "XML Prompt Engineering Guidelines"

</references>
