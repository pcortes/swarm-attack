"""Testing module for quality gates and test validation.

This module provides:
- QualityGateRunner: Orchestrates quality gates for CI/validation pipeline
- AdversarialTestGenerator: Generates adversarial test cases from interface specs
- MutationTestGate (from mutation_test_gate): Validates test quality via actual mutation runs
- LLMMutationTestGate (from quality_gate_runner): LLM-based mutation analysis
"""

from swarm_attack.testing.mutation_test_gate import (
    MutationTestGate,
    MutationTestResult as MutmutTestResult,
    MutantInfo,
)

from swarm_attack.testing.quality_gate_runner import (
    QualityGateRunner,
    QualityGateResult,
    GateResult,
    GateType,
    AdversarialTestGenerator as LegacyAdversarialTestGenerator,
    MutationTestGate as LLMMutationTestGate,
)

# New interface-based adversarial test generator
from swarm_attack.testing.adversarial_test_generator import (
    AdversarialTestGenerator,
    InterfaceSpec,
    GeneratedTest,
    TestGenerationResult,
    TestCategory,
    MutationTestResult,
    TestGenerationError,
)

__all__ = [
    # Core mutation testing (actual mutmut runner)
    "MutationTestGate",
    "MutmutTestResult",
    "MutantInfo",
    # Quality gate runner (LLM-based analysis)
    "QualityGateRunner",
    "QualityGateResult",
    "GateResult",
    "GateType",
    "LegacyAdversarialTestGenerator",
    "LLMMutationTestGate",
    # New interface-based adversarial test generator
    "AdversarialTestGenerator",
    "InterfaceSpec",
    "GeneratedTest",
    "TestGenerationResult",
    "TestCategory",
    "MutationTestResult",
    "TestGenerationError",
]
