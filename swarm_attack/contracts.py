"""Agent Contracts - TypedDict-based validation for agent input/output.

This module provides typed contracts for all agents, enabling early detection
of contract violations and improved debugging.
"""
from typing import TypedDict, NotRequired, Any, get_type_hints, get_origin, get_args


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
    def validate_input(
        cls, agent_name: str, data: dict, contract: type, strict: bool = False
    ) -> None:
        """Validate input data against contract.

        Args:
            agent_name: Name of the agent being validated
            data: The input data dict to validate
            contract: The TypedDict contract class
            strict: If True, raise on extra keys not in contract
        """
        required_keys = cls._get_required_keys(contract)
        optional_keys = cls._get_optional_keys(contract)
        all_keys = required_keys | optional_keys

        # Check for missing required keys
        missing_keys = list(required_keys - set(data.keys()))

        # Check for extra keys (only in strict mode)
        extra_keys = []
        if strict:
            extra_keys = list(set(data.keys()) - all_keys)

        # Check types
        type_errors = cls._check_types(data, contract)

        if missing_keys or extra_keys or type_errors:
            raise ContractValidationError(
                agent_name=agent_name,
                contract_type="input",
                missing_keys=missing_keys,
                extra_keys=extra_keys,
                type_errors=type_errors,
            )

    @classmethod
    def validate_output(cls, agent_name: str, data: dict, contract: type) -> None:
        """Validate output data against contract.

        Args:
            agent_name: Name of the agent being validated
            data: The output data dict to validate
            contract: The TypedDict contract class
        """
        required_keys = cls._get_required_keys(contract)

        # Check for missing required keys
        missing_keys = list(required_keys - set(data.keys()))

        # Check types
        type_errors = cls._check_types(data, contract)

        if missing_keys or type_errors:
            raise ContractValidationError(
                agent_name=agent_name,
                contract_type="output",
                missing_keys=missing_keys,
                extra_keys=[],
                type_errors=type_errors,
            )

    @classmethod
    def _get_required_keys(cls, contract: type) -> set[str]:
        """Get required keys from TypedDict (those without NotRequired)."""
        hints = get_type_hints(contract, include_extras=True)
        required = set()

        for key, annotation in hints.items():
            # Check if the annotation is wrapped in NotRequired
            origin = get_origin(annotation)
            if origin is not NotRequired:
                required.add(key)

        return required

    @classmethod
    def _get_optional_keys(cls, contract: type) -> set[str]:
        """Get optional keys from TypedDict (those with NotRequired)."""
        hints = get_type_hints(contract, include_extras=True)
        optional = set()

        for key, annotation in hints.items():
            origin = get_origin(annotation)
            if origin is NotRequired:
                optional.add(key)

        return optional

    @classmethod
    def _check_types(cls, data: dict, contract: type) -> dict[str, str]:
        """Check types of values against contract annotations."""
        hints = get_type_hints(contract, include_extras=True)
        errors = {}

        for key, value in data.items():
            if key not in hints:
                continue

            annotation = hints[key]

            # Unwrap NotRequired if present
            origin = get_origin(annotation)
            if origin is NotRequired:
                args = get_args(annotation)
                if args:
                    annotation = args[0]

            # Get the actual type to check against
            expected_type = cls._get_base_type(annotation)

            if expected_type is not None and not isinstance(value, expected_type):
                errors[key] = f"expected {expected_type.__name__}, got {type(value).__name__}"

        return errors

    @classmethod
    def _get_base_type(cls, annotation: type) -> type | None:
        """Extract the base type from an annotation for isinstance checks."""
        origin = get_origin(annotation)

        # Handle generic types like list[str], dict[str, Any]
        if origin is list:
            return list
        if origin is dict:
            return dict
        if origin is set:
            return set
        if origin is tuple:
            return tuple

        # Handle union types - skip validation for complex unions
        if origin is not None:
            return None

        # Simple types
        if isinstance(annotation, type):
            return annotation

        return None


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


def register_contract(
    agent_name: str, input_contract: type, output_contract: type
) -> None:
    """Register a new agent contract."""
    AGENT_CONTRACTS[agent_name] = (input_contract, output_contract)
