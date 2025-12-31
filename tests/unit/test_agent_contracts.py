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
