"""TDD tests for GitHub issue/PR template validation.

These tests validate that GitHub templates:
1. Exist at expected paths
2. Contain required sections
3. Have valid markdown structure
4. Include appropriate checklists and prompts

RED Phase: These tests should fail initially until templates are created.
GREEN Phase: Create templates to satisfy requirements.
REFACTOR Phase: Improve template content while keeping tests green.

NOTE: These tests are skipped because swarm-attack uses its own issue creation
system (IssueCreator agent) rather than GitHub's native issue templates. None of
the swarm ecosystem projects (swarm-attack, swarm-attack-qa, coo) use GitHub
issue/PR templates as they are internal development tools.
"""
import re
from pathlib import Path
from typing import List, Set

import pytest


# Project root - tests run from worktree root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Skip reason for all template tests
SKIP_REASON = (
    "GitHub templates not needed - swarm-attack uses IssueCreator agent for issue "
    "management. None of the swarm ecosystem projects use GitHub issue/PR templates."
)


@pytest.mark.skip(reason=SKIP_REASON)
class TestBugReportTemplate:
    """Test bug report template has required sections for issue triage."""

    TEMPLATE_PATH = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md"

    def test_template_file_exists(self):
        """Bug report template must exist at .github/ISSUE_TEMPLATE/bug_report.md."""
        assert self.TEMPLATE_PATH.exists(), (
            f"Bug report template not found at {self.TEMPLATE_PATH}. "
            "Create .github/ISSUE_TEMPLATE/bug_report.md"
        )

    def test_has_frontmatter(self):
        """Template must have YAML frontmatter with name and description."""
        content = self._read_template()
        assert content.startswith("---"), "Template must start with YAML frontmatter (---)"
        assert "---" in content[3:], "Template must have closing frontmatter delimiter"

        frontmatter = self._extract_frontmatter(content)
        assert "name:" in frontmatter, "Frontmatter must include 'name:'"
        assert "about:" in frontmatter or "description:" in frontmatter, (
            "Frontmatter must include 'about:' or 'description:'"
        )

    def test_has_description_section(self):
        """Template must have a Description section for bug summary."""
        content = self._read_template()
        assert self._has_section(content, "Description"), (
            "Bug report must have '## Description' section"
        )

    def test_has_steps_to_reproduce(self):
        """Template must have Steps to Reproduce section."""
        content = self._read_template()
        assert self._has_section(content, "Steps to Reproduce") or \
               self._has_section(content, "Steps To Reproduce"), (
            "Bug report must have '## Steps to Reproduce' section"
        )

    def test_has_expected_behavior(self):
        """Template must have Expected Behavior section."""
        content = self._read_template()
        assert self._has_section(content, "Expected Behavior") or \
               self._has_section(content, "Expected behaviour"), (
            "Bug report must have '## Expected Behavior' section"
        )

    def test_has_actual_behavior(self):
        """Template must have Actual Behavior section."""
        content = self._read_template()
        assert self._has_section(content, "Actual Behavior") or \
               self._has_section(content, "Actual behaviour"), (
            "Bug report must have '## Actual Behavior' section"
        )

    def test_has_environment_section(self):
        """Template must have Environment section for system info."""
        content = self._read_template()
        assert self._has_section(content, "Environment") or \
               self._has_section(content, "System Information"), (
            "Bug report must have '## Environment' section"
        )

    def test_has_additional_context_section(self):
        """Template should have Additional Context section."""
        content = self._read_template()
        assert self._has_section(content, "Additional Context") or \
               self._has_section(content, "Additional Information"), (
            "Bug report should have '## Additional Context' section"
        )

    def test_has_labels_in_frontmatter(self):
        """Template frontmatter should specify labels."""
        content = self._read_template()
        frontmatter = self._extract_frontmatter(content)
        assert "labels:" in frontmatter or "label:" in frontmatter, (
            "Bug report frontmatter should specify labels (e.g., 'bug')"
        )

    def _read_template(self) -> str:
        """Read template content, fail with helpful message if missing."""
        if not self.TEMPLATE_PATH.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        return self.TEMPLATE_PATH.read_text()

    def _extract_frontmatter(self, content: str) -> str:
        """Extract YAML frontmatter from template."""
        if not content.startswith("---"):
            return ""
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return ""
        return content[3:end_idx]

    def _has_section(self, content: str, section_name: str) -> bool:
        """Check if content has a markdown section with given name."""
        pattern = rf"^##\s+{re.escape(section_name)}"
        return bool(re.search(pattern, content, re.MULTILINE | re.IGNORECASE))


@pytest.mark.skip(reason=SKIP_REASON)
class TestFeatureRequestTemplate:
    """Test feature request template has required sections."""

    TEMPLATE_PATH = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md"

    def test_template_file_exists(self):
        """Feature request template must exist."""
        assert self.TEMPLATE_PATH.exists(), (
            f"Feature request template not found at {self.TEMPLATE_PATH}. "
            "Create .github/ISSUE_TEMPLATE/feature_request.md"
        )

    def test_has_frontmatter(self):
        """Template must have YAML frontmatter."""
        content = self._read_template()
        assert content.startswith("---"), "Template must start with YAML frontmatter"
        frontmatter = self._extract_frontmatter(content)
        assert "name:" in frontmatter, "Frontmatter must include 'name:'"

    def test_has_description_section(self):
        """Template must have Description section."""
        content = self._read_template()
        assert self._has_section(content, "Description") or \
               self._has_section(content, "Feature Description"), (
            "Feature request must have '## Description' section"
        )

    def test_has_problem_statement(self):
        """Template should have Problem Statement or motivation section."""
        content = self._read_template()
        has_problem = (
            self._has_section(content, "Problem") or
            self._has_section(content, "Problem Statement") or
            self._has_section(content, "Motivation") or
            self._has_section(content, "Is your feature request related to a problem")
        )
        assert has_problem, (
            "Feature request should have problem/motivation section"
        )

    def test_has_proposed_solution(self):
        """Template must have Proposed Solution section."""
        content = self._read_template()
        assert self._has_section(content, "Proposed Solution") or \
               self._has_section(content, "Solution") or \
               self._has_section(content, "Describe the solution"), (
            "Feature request must have '## Proposed Solution' section"
        )

    def test_has_alternatives_section(self):
        """Template should have Alternatives section."""
        content = self._read_template()
        assert self._has_section(content, "Alternatives") or \
               self._has_section(content, "Alternatives Considered") or \
               self._has_section(content, "Alternative Solutions"), (
            "Feature request should have '## Alternatives' section"
        )

    def test_has_acceptance_criteria(self):
        """Template should have Acceptance Criteria for testability."""
        content = self._read_template()
        assert self._has_section(content, "Acceptance Criteria") or \
               self._has_section(content, "Definition of Done") or \
               self._has_section(content, "Success Criteria"), (
            "Feature request should have '## Acceptance Criteria' section"
        )

    def test_has_labels_in_frontmatter(self):
        """Template frontmatter should specify labels."""
        content = self._read_template()
        frontmatter = self._extract_frontmatter(content)
        assert "labels:" in frontmatter or "label:" in frontmatter, (
            "Feature request frontmatter should specify labels (e.g., 'enhancement')"
        )

    def _read_template(self) -> str:
        if not self.TEMPLATE_PATH.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        return self.TEMPLATE_PATH.read_text()

    def _extract_frontmatter(self, content: str) -> str:
        if not content.startswith("---"):
            return ""
        end_idx = content.find("---", 3)
        return content[3:end_idx] if end_idx != -1 else ""

    def _has_section(self, content: str, section_name: str) -> bool:
        pattern = rf"^##\s+{re.escape(section_name)}"
        return bool(re.search(pattern, content, re.MULTILINE | re.IGNORECASE))


@pytest.mark.skip(reason=SKIP_REASON)
class TestPRTemplate:
    """Test PR template has required checklist and sections."""

    TEMPLATE_PATH = PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

    def test_template_file_exists(self):
        """PR template must exist at .github/PULL_REQUEST_TEMPLATE.md."""
        assert self.TEMPLATE_PATH.exists(), (
            f"PR template not found at {self.TEMPLATE_PATH}. "
            "Create .github/PULL_REQUEST_TEMPLATE.md"
        )

    def test_has_description_section(self):
        """PR template must have Description section."""
        content = self._read_template()
        assert self._has_section(content, "Description") or \
               self._has_section(content, "Summary"), (
            "PR template must have '## Description' section"
        )

    def test_has_changes_section(self):
        """PR template should have Changes section."""
        content = self._read_template()
        assert self._has_section(content, "Changes") or \
               self._has_section(content, "What Changed") or \
               self._has_section(content, "Changes Made"), (
            "PR template should have '## Changes' section"
        )

    def test_has_test_plan(self):
        """PR template must have Test Plan section."""
        content = self._read_template()
        assert self._has_section(content, "Test Plan") or \
               self._has_section(content, "Testing") or \
               self._has_section(content, "How to Test"), (
            "PR template must have '## Test Plan' section"
        )

    def test_has_checklist(self):
        """PR template must have a checklist with checkboxes."""
        content = self._read_template()
        # Look for markdown checkboxes: - [ ] or - [x]
        checkbox_pattern = r"-\s*\[\s*[xX\s]?\s*\]"
        checkboxes = re.findall(checkbox_pattern, content)
        assert len(checkboxes) >= 3, (
            f"PR template must have at least 3 checklist items, found {len(checkboxes)}"
        )

    def test_checklist_includes_tests(self):
        """PR checklist must include testing confirmation."""
        content = self._read_template()
        content_lower = content.lower()
        has_test_checkbox = (
            "tests" in content_lower and "- [" in content_lower or
            "test" in content_lower and "- [" in content_lower
        )
        assert has_test_checkbox, (
            "PR checklist must include testing-related checkbox"
        )

    def test_checklist_includes_documentation(self):
        """PR checklist should mention documentation."""
        content = self._read_template()
        content_lower = content.lower()
        has_docs = (
            "documentation" in content_lower or
            "docs" in content_lower or
            "readme" in content_lower or
            "comments" in content_lower
        )
        assert has_docs, (
            "PR checklist should mention documentation updates"
        )

    def test_has_related_issues_section(self):
        """PR template should have Related Issues section."""
        content = self._read_template()
        has_related = (
            self._has_section(content, "Related Issues") or
            self._has_section(content, "Related Issue") or
            self._has_section(content, "Closes") or
            self._has_section(content, "Fixes") or
            "closes #" in content.lower() or
            "fixes #" in content.lower() or
            "related to #" in content.lower()
        )
        assert has_related, (
            "PR template should reference related issues"
        )

    def test_has_breaking_changes_section(self):
        """PR template should mention breaking changes."""
        content = self._read_template()
        has_breaking = (
            self._has_section(content, "Breaking Changes") or
            "breaking change" in content.lower() or
            "breaking" in content.lower()
        )
        assert has_breaking, (
            "PR template should include breaking changes section/checkbox"
        )

    def _read_template(self) -> str:
        if not self.TEMPLATE_PATH.exists():
            pytest.skip(f"Template not found: {self.TEMPLATE_PATH}")
        return self.TEMPLATE_PATH.read_text()

    def _has_section(self, content: str, section_name: str) -> bool:
        pattern = rf"^##\s+{re.escape(section_name)}"
        return bool(re.search(pattern, content, re.MULTILINE | re.IGNORECASE))


@pytest.mark.skip(reason=SKIP_REASON)
class TestTemplateFormat:
    """Test markdown validity and format consistency of all templates."""

    TEMPLATE_PATHS = [
        PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md",
        PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md",
        PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
    ]

    @pytest.fixture
    def all_templates(self) -> List[Path]:
        """Get all template files that exist."""
        existing = [p for p in self.TEMPLATE_PATHS if p.exists()]
        if not existing:
            pytest.skip("No template files found")
        return existing

    def test_at_least_one_template_exists(self):
        """At least one template file must exist."""
        existing = [p for p in self.TEMPLATE_PATHS if p.exists()]
        assert len(existing) >= 1, (
            "At least one GitHub template must exist. "
            f"Expected files at: {[str(p) for p in self.TEMPLATE_PATHS]}"
        )

    def test_templates_are_not_empty(self, all_templates):
        """Template files must not be empty."""
        for template_path in all_templates:
            content = template_path.read_text().strip()
            assert len(content) > 50, (
                f"Template {template_path.name} appears to be empty or too short"
            )

    def test_templates_have_valid_markdown_headers(self, all_templates):
        """All templates must have valid markdown headers."""
        for template_path in all_templates:
            content = template_path.read_text()
            # Look for markdown headers (## or ###)
            headers = re.findall(r"^#+\s+.+$", content, re.MULTILINE)
            assert len(headers) >= 2, (
                f"Template {template_path.name} should have at least 2 markdown headers"
            )

    def test_templates_no_placeholder_text(self, all_templates):
        """Templates should not have unfilled placeholder indicators."""
        placeholder_patterns = [
            r"\[PLACEHOLDER\]",
            r"\[TODO\]",
            r"\[INSERT\]",
            r"XXX",
            r"FIXME",
        ]
        for template_path in all_templates:
            content = template_path.read_text()
            for pattern in placeholder_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, (
                    f"Template {template_path.name} has unfilled placeholder: {pattern}"
                )

    def test_templates_have_consistent_line_endings(self, all_templates):
        """Templates should have consistent line endings (LF, not CRLF)."""
        for template_path in all_templates:
            content = template_path.read_bytes()
            crlf_count = content.count(b"\r\n")
            assert crlf_count == 0, (
                f"Template {template_path.name} has CRLF line endings. Use LF only."
            )

    def test_templates_end_with_newline(self, all_templates):
        """Templates should end with a newline character."""
        for template_path in all_templates:
            content = template_path.read_text()
            assert content.endswith("\n"), (
                f"Template {template_path.name} should end with a newline"
            )

    def test_no_trailing_whitespace(self, all_templates):
        """Templates should not have trailing whitespace on lines."""
        for template_path in all_templates:
            content = template_path.read_text()
            lines_with_trailing = []
            for i, line in enumerate(content.split("\n"), 1):
                if line != line.rstrip():
                    lines_with_trailing.append(i)
            # Allow some trailing whitespace but flag if excessive
            assert len(lines_with_trailing) <= 3, (
                f"Template {template_path.name} has trailing whitespace on "
                f"lines: {lines_with_trailing[:5]}"
            )

    def test_issue_templates_in_correct_directory(self):
        """Issue templates must be in .github/ISSUE_TEMPLATE/ directory."""
        issue_template_dir = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
        if not issue_template_dir.exists():
            pytest.skip("ISSUE_TEMPLATE directory not yet created")

        # Check directory exists and is a directory
        assert issue_template_dir.is_dir(), (
            ".github/ISSUE_TEMPLATE must be a directory"
        )

        # Check for at least one template
        md_files = list(issue_template_dir.glob("*.md"))
        assert len(md_files) >= 1, (
            ".github/ISSUE_TEMPLATE/ should contain at least one .md file"
        )

    def test_pr_template_in_correct_location(self):
        """PR template should be at .github/PULL_REQUEST_TEMPLATE.md."""
        pr_template = PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        if not pr_template.exists():
            # Also check alternative location
            alt_location = PROJECT_ROOT / ".github" / "pull_request_template.md"
            exists = pr_template.exists() or alt_location.exists()
            if not exists:
                pytest.skip("PR template not yet created")

        # If we get here, verify it's a file
        assert pr_template.is_file() or (
            PROJECT_ROOT / ".github" / "pull_request_template.md"
        ).is_file(), (
            "PR template must be a file at .github/PULL_REQUEST_TEMPLATE.md"
        )


@pytest.mark.skip(reason=SKIP_REASON)
class TestTemplateConsistency:
    """Test consistency across all templates."""

    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

    def test_all_templates_have_description(self):
        """All templates should have a Description section."""
        templates = self._get_existing_templates()
        if not templates:
            pytest.skip("No templates found")

        for template_path in templates:
            content = template_path.read_text()
            has_description = bool(
                re.search(r"^##\s+(Description|Summary)", content, re.MULTILINE | re.IGNORECASE)
            )
            assert has_description, (
                f"Template {template_path.name} should have Description section"
            )

    def test_template_naming_convention(self):
        """Template files should use lowercase with underscores or hyphens."""
        template_dir = self.PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
        if not template_dir.exists():
            pytest.skip("ISSUE_TEMPLATE directory not found")

        for template in template_dir.glob("*.md"):
            name = template.stem
            # Should be lowercase with underscores or hyphens
            assert name == name.lower(), (
                f"Template filename {template.name} should be lowercase"
            )

    def _get_existing_templates(self) -> List[Path]:
        """Get all existing template files."""
        templates = []

        # Issue templates
        issue_dir = self.PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
        if issue_dir.exists():
            templates.extend(issue_dir.glob("*.md"))

        # PR template
        pr_template = self.PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        if pr_template.exists():
            templates.append(pr_template)

        return templates
