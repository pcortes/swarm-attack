"""TDD fix plan generation for actionable findings."""

from typing import Optional
import hashlib

from swarm_attack.commit_review.models import Finding, Severity, TDDPlan


class TDDPlanGenerator:
    """Generates TDD fix plans for actionable findings."""

    def generate_plan(self, finding: Finding) -> Optional[TDDPlan]:
        """Generate a TDD plan for a finding.

        Low severity findings don't get plans.
        Medium+ severity findings get full TDD plans.

        Args:
            finding: The finding to generate a plan for

        Returns:
            TDDPlan or None for low severity
        """
        if finding.severity == Severity.LOW:
            return None

        finding_id = self._generate_id(finding)
        red_phase = generate_red_phase(finding)
        green_phase = generate_green_phase(finding)
        refactor_phase = generate_refactor_phase(finding)

        return TDDPlan(
            finding_id=finding_id,
            red_phase=red_phase,
            green_phase=green_phase,
            refactor_phase=refactor_phase,
        )

    def _generate_id(self, finding: Finding) -> str:
        """Generate a unique ID for the finding."""
        content = f"{finding.commit_sha}:{finding.evidence}:{finding.description}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


def generate_red_phase(finding: Finding) -> str:
    """Generate failing test descriptions for issues.

    Args:
        finding: The finding to address

    Returns:
        Description of the failing test to write
    """
    # Extract file info from evidence
    file_info = finding.evidence.split(":")[0] if ":" in finding.evidence else "unknown"

    templates = {
        "production_reliability": f"""Write a test that verifies the fix handles the production scenario.

Test file: tests/unit/test_{file_info.replace('.py', '')}_fix.py

```python
def test_{_snake_case(finding.description[:30])}():
    # Arrange: Set up the conditions that caused the issue
    # Act: Trigger the code path that was fixed
    # Assert: Verify the fix handles the case correctly
    pass
```

The test should fail before the fix is applied.""",
        "test_coverage": f"""Write a test that verifies proper coverage for the change.

Test file: tests/unit/test_{file_info.replace('.py', '')}.py

```python
def test_coverage_for_{_snake_case(finding.description[:30])}():
    # Test the specific code path mentioned in the finding
    # Ensure mocks match production API signatures
    pass
```

Run with: pytest --cov={file_info} --cov-fail-under=80""",
        "code_quality": f"""Write a test that validates the implementation is complete.

Test file: tests/unit/test_{file_info.replace('.py', '')}.py

```python
def test_{_snake_case(finding.description[:30])}_complete():
    # Test all required functionality
    # Verify no partial implementation
    pass
```""",
        "documentation": f"""Write a test that validates documentation accuracy.

Test file: tests/unit/test_docs.py

```python
def test_documentation_for_{_snake_case(finding.description[:30])}():
    # Verify documented behavior matches actual behavior
    # Check cross-references are accurate
    pass
```""",
        "architecture": f"""Write a test that verifies API contract preservation.

Test file: tests/integration/test_{file_info.replace('.py', '')}_contract.py

```python
def test_api_contract_{_snake_case(finding.description[:30])}():
    # Verify the interface contract is maintained
    # Check for breaking changes
    pass
```""",
    }

    return templates.get(finding.category, templates["code_quality"])


def generate_green_phase(finding: Finding) -> str:
    """Generate minimal fix steps.

    Args:
        finding: The finding to address

    Returns:
        Steps to implement the minimal fix
    """
    file_info = finding.evidence.split(":")[0] if ":" in finding.evidence else "unknown"
    line_info = finding.evidence.split(":")[1] if ":" in finding.evidence else "0"

    return f"""Implement the minimal fix to make the test pass.

**Location:** `{file_info}:{line_info}`

**Steps:**
1. Open `{file_info}` and navigate to line {line_info}
2. Address the issue: {finding.description}
3. Run the failing test to verify it now passes
4. Run the full test suite to check for regressions

**Implementation guidance:**
- Make the smallest change that addresses the issue
- Don't add extra features or refactoring yet
- Focus only on making the test green"""


def generate_refactor_phase(finding: Finding) -> str:
    """Generate cleanup suggestions.

    Args:
        finding: The finding that was addressed

    Returns:
        Refactoring suggestions
    """
    return f"""After the fix is verified, consider these cleanup steps:

1. **Extract common patterns** - If the fix reveals duplication, extract to shared utilities
2. **Improve naming** - Ensure variable/function names clearly describe their purpose
3. **Add documentation** - Document any non-obvious behavior introduced by the fix
4. **Review related code** - Check if similar issues exist in related code paths

**Verification:**
- All existing tests still pass
- New test still passes
- No new warnings introduced
- Code coverage maintained or improved"""


def _snake_case(text: str) -> str:
    """Convert text to snake_case for function names."""
    import re
    # Remove non-alphanumeric chars and convert to lowercase
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    # Replace spaces with underscores
    text = re.sub(r"\s+", "_", text)
    return text[:40]  # Limit length
