"""Refactoring suggestion engine for code quality findings.

This module maps detected code quality issues to specific refactoring patterns,
generates step-by-step instructions, and estimates effort based on the
refactoring catalog from the Code Quality spec.

The refactoring catalog is based on Martin Fowler's Refactoring patterns
and the spec's refactor_strategist expert (Dr. Sarah Fowler).
"""

from dataclasses import replace
from typing import Optional

from .models import Finding


class RefactorSuggester:
    """Maps detected issues to specific refactoring suggestions.

    Uses a catalog of code smells mapped to refactoring patterns,
    with step-by-step instructions and effort estimates.

    Attributes:
        SMELL_TO_REFACTORING: Mapping of smell types to refactoring patterns.
        REFACTORING_STEPS: Mapping of refactoring patterns to step templates.
        REFACTORING_EFFORT: Mapping of refactoring patterns to effort estimates.
    """

    # Refactoring catalog from spec (refactor_strategist expert)
    SMELL_TO_REFACTORING: dict[str, str] = {
        "long_method": "Extract Method",
        "large_class": "Extract Class",
        "feature_envy": "Move Method",
        "primitive_obsession": "Replace with Value Object",
        "switch_on_type": "Replace Conditional with Polymorphism",
        "too_many_parameters": "Introduce Parameter Object",
        "data_clump": "Extract Class",
        "message_chain": "Hide Delegate",
        "god_class": "Extract Class (split by responsibility)",
        "deep_nesting": "Extract Method / Guard Clauses",
        "duplicate_code": "Extract Method or Base Class",
    }

    # Step templates for each refactoring pattern
    REFACTORING_STEPS: dict[str, list[str]] = {
        "Extract Method": [
            "Identify logical blocks or cohesive code sections within the method",
            "Create a new private method with a descriptive name for each block",
            "Extract the identified code into the new method",
            "Replace the original code with a call to the new method",
            "Run tests to ensure behavior is unchanged",
        ],
        "Extract Class": [
            "Identify groups of related fields and methods",
            "Create a new class with a name reflecting its responsibility",
            "Move related fields to the new class",
            "Move related methods to the new class",
            "Update the original class to use composition with the new class",
            "Run tests to ensure behavior is unchanged",
        ],
        "Move Method": [
            "Identify the class that uses the method's features most",
            "Copy the method to the target class",
            "Update the method to use target class's fields directly",
            "Replace the original method with a delegation call or remove it",
            "Update all callers to use the new location",
        ],
        "Replace with Value Object": [
            "Create a new class to represent the value concept",
            "Add fields for all primitive values being replaced",
            "Make the class immutable (no setters)",
            "Add relevant behavior methods to the new class",
            "Replace primitive usage with the new value object",
        ],
        "Replace Conditional with Polymorphism": [
            "Create an interface or abstract base class with the conditional behavior",
            "Create a concrete class for each branch of the conditional",
            "Implement the method in each concrete class with branch-specific logic",
            "Replace the conditional with polymorphic method call",
            "Update object creation to instantiate the correct subtype",
        ],
        "Introduce Parameter Object": [
            "Create a new dataclass to hold the related parameters",
            "Add the new class as a single parameter to the method",
            "Update the method body to access fields from the new object",
            "Update all call sites to pass the new parameter object",
            "Run tests to ensure behavior is unchanged",
        ],
        "Hide Delegate": [
            "Create a delegating method on the intermediate object",
            "Replace the chain of calls with the single delegating method",
            "Consider if other chains need similar treatment",
            "Run tests to ensure behavior is unchanged",
        ],
        "Extract Class (split by responsibility)": [
            "Identify distinct responsibilities in the god class",
            "Create a new class for each responsibility",
            "Move fields and methods for each responsibility to its class",
            "Use composition to connect the extracted classes",
            "Consider using facade pattern if clients need unified interface",
            "Run tests after each extraction to catch regressions",
        ],
        "Extract Method / Guard Clauses": [
            "Convert outer conditions to early returns (guard clauses)",
            "Identify deeply nested blocks that can be extracted",
            "Extract each nested block to a well-named method",
            "Flatten remaining conditionals using guard clauses",
            "Run tests to ensure behavior is unchanged",
        ],
        "Extract Method or Base Class": [
            "Identify the duplicated code blocks",
            "If duplication is within one class, extract to a private method",
            "If duplication is across classes, consider a shared base class",
            "Replace duplicate code with calls to the extracted method",
            "Run tests to ensure behavior is unchanged",
        ],
        "Inject Dependencies": [
            "Identify dependencies that are instantiated directly in __init__",
            "Add parameters to __init__ for each dependency",
            "Assign injected dependencies to instance attributes",
            "Update call sites to provide dependency instances",
            "Consider using a factory or DI container for complex cases",
        ],
    }

    # Effort estimates based on typical refactoring scope
    # small: <10 lines changed, medium: 10-50 lines, large: >50 lines
    REFACTORING_EFFORT: dict[str, str] = {
        "Extract Method": "medium",
        "Extract Class": "large",
        "Move Method": "medium",
        "Replace with Value Object": "medium",
        "Replace Conditional with Polymorphism": "medium",
        "Introduce Parameter Object": "small",
        "Hide Delegate": "small",
        "Extract Class (split by responsibility)": "large",
        "Extract Method / Guard Clauses": "medium",
        "Extract Method or Base Class": "medium",
        "Inject Dependencies": "small",
        "Manual Review Required": "medium",
    }

    # Keywords in titles that map to smell types
    TITLE_TO_SMELL: dict[str, str] = {
        "long method": "long_method",
        "large class": "large_class",
        "feature envy": "feature_envy",
        "primitive obsession": "primitive_obsession",
        "ocp violation": "switch_on_type",
        "type check": "switch_on_type",
        "too many parameters": "too_many_parameters",
        "data clump": "data_clump",
        "message chain": "message_chain",
        "god class": "god_class",
        "deep nesting": "deep_nesting",
        "duplicate": "duplicate_code",
        "srp violation": "large_class",  # SRP -> Extract Class
        "dip violation": "dip_violation",
    }

    def suggest_refactoring(self, finding: Finding) -> str:
        """Suggest appropriate refactoring for a finding.

        Analyzes the finding's title and description to determine the
        smell type, then maps it to the appropriate refactoring pattern.

        Args:
            finding: The code quality finding to analyze.

        Returns:
            The name of the suggested refactoring pattern.
        """
        # Normalize title for matching
        title_lower = finding.title.lower()
        description_lower = finding.description.lower()

        # Check for known smell patterns in title
        for keyword, smell in self.TITLE_TO_SMELL.items():
            if keyword in title_lower or keyword in description_lower:
                if smell == "dip_violation":
                    return "Inject Dependencies"
                return self.SMELL_TO_REFACTORING.get(smell, "Manual Review Required")

        # Check for SOLID violations by category
        if "srp" in title_lower:
            return "Extract Class"
        if "dip" in title_lower or "instantiat" in description_lower:
            return "Inject Dependencies"

        # Fallback to Manual Review for unrecognized issues
        return "Manual Review Required"

    def generate_steps(self, finding: Finding, refactoring: str) -> list[str]:
        """Generate step-by-step refactoring instructions.

        Creates specific, actionable steps based on the refactoring pattern
        and the context from the finding.

        Args:
            finding: The code quality finding providing context.
            refactoring: The name of the refactoring pattern to apply.

        Returns:
            List of step-by-step instructions for the refactoring.
        """
        # Get base steps for this refactoring pattern
        base_steps = self.REFACTORING_STEPS.get(refactoring, [])

        if not base_steps:
            # Default steps for unknown refactoring patterns
            return [
                f"Review the issue at {finding.file}:{finding.line}",
                "Analyze the code structure and identify the core problem",
                "Apply appropriate refactoring based on the specific context",
                "Write tests to verify the refactored code works correctly",
                "Run all existing tests to ensure no regressions",
            ]

        # Return a copy of the base steps
        return list(base_steps)

    def estimate_effort(self, finding: Finding, refactoring: str) -> str:
        """Estimate effort for a refactoring.

        Provides effort estimates based on typical scope:
        - 'small': <10 lines changed
        - 'medium': 10-50 lines changed
        - 'large': >50 lines changed

        Args:
            finding: The code quality finding (for context).
            refactoring: The name of the refactoring pattern.

        Returns:
            Effort estimate: 'small', 'medium', or 'large'.
        """
        return self.REFACTORING_EFFORT.get(refactoring, "medium")

    def enrich_finding(self, finding: Finding) -> Finding:
        """Add refactoring suggestion, steps, and effort to a finding.

        Creates a new Finding with the refactoring pattern, steps, and
        effort estimate populated. Does not mutate the original finding.

        Args:
            finding: The original code quality finding.

        Returns:
            A new Finding with refactoring information added.
        """
        # Determine the refactoring pattern
        refactoring = self.suggest_refactoring(finding)

        # Generate steps for this refactoring
        steps = self.generate_steps(finding, refactoring)

        # Estimate the effort
        effort = self.estimate_effort(finding, refactoring)

        # Create a new Finding with the enriched fields
        return replace(
            finding,
            refactoring_pattern=refactoring,
            refactoring_steps=steps,
            effort_estimate=effort,
        )
