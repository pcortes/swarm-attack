"""Skill Integration Tests.

Tests that QA skills work correctly with Claude Code.
- Skill file existence
- Required sections in skill definitions
- Valid markdown/YAML structure
- Skill configuration correctness
"""

import os
import re
from pathlib import Path

import pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def skills_base_path():
    """Get the base path to skills directory."""
    return Path("/Users/philipjcortes/Desktop/swarm-attack-qa-agent/.claude/skills")


@pytest.fixture
def qa_skill_names():
    """List of QA-related skill names."""
    return [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ]


def parse_skill_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from skill file content."""
    frontmatter = {}

    # Check if content starts with ---
    if not content.strip().startswith("---"):
        return frontmatter

    # Find the end of frontmatter
    lines = content.split("\n")
    in_frontmatter = False
    frontmatter_lines = []

    for line in lines:
        if line.strip() == "---":
            if in_frontmatter:
                break  # End of frontmatter
            else:
                in_frontmatter = True
                continue

        if in_frontmatter:
            frontmatter_lines.append(line)

    # Parse simple YAML-like frontmatter
    current_key = None
    current_value_lines = []

    for line in frontmatter_lines:
        # Handle multi-line values (description with >)
        if line.startswith("  ") and current_key:
            current_value_lines.append(line.strip())
            continue

        if current_key and current_value_lines:
            frontmatter[current_key] = " ".join(current_value_lines).strip()
            current_value_lines = []

        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""

            if value == ">" or value == "|":
                # Multi-line value coming
                current_key = key
                current_value_lines = []
            elif value.startswith("-"):
                # List value - store as is for now
                frontmatter[key] = value
                current_key = key
            else:
                frontmatter[key] = value
                current_key = None

    # Handle last multi-line value
    if current_key and current_value_lines:
        frontmatter[current_key] = " ".join(current_value_lines).strip()

    return frontmatter


def get_skill_content(skills_base_path: Path, skill_name: str) -> str:
    """Read the content of a skill file."""
    # Try both SKILL.md and skill.md
    skill_file = skills_base_path / skill_name / "SKILL.md"
    if not skill_file.exists():
        skill_file = skills_base_path / skill_name / "skill.md"

    if skill_file.exists():
        return skill_file.read_text()
    return ""


# =============================================================================
# QA ORCHESTRATOR SKILL TESTS
# =============================================================================


class TestQAOrchestratorSkill:
    """Tests for qa-orchestrator skill."""

    def test_skill_file_exists(self, skills_base_path):
        """Skill definition file should exist."""
        skill_path = skills_base_path / "qa-orchestrator"
        assert skill_path.exists(), "qa-orchestrator skill directory should exist"

        # Check for SKILL.md (case-insensitive)
        skill_files = list(skill_path.glob("[Ss][Kk][Ii][Ll][Ll].md"))
        assert len(skill_files) > 0, "qa-orchestrator should have SKILL.md file"

    def test_skill_has_required_sections(self, skills_base_path):
        """Skill should have all required sections."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")
        assert content, "Skill content should not be empty"

        # Check for frontmatter
        assert content.strip().startswith("---"), "Skill should have YAML frontmatter"

        # Parse frontmatter
        frontmatter = parse_skill_frontmatter(content)

        # Required frontmatter fields
        assert "name" in frontmatter, "Skill should have 'name' in frontmatter"
        assert "description" in frontmatter, "Skill should have 'description' in frontmatter"
        assert "allowed-tools" in frontmatter, "Skill should have 'allowed-tools' in frontmatter"

    def test_skill_prompt_is_valid(self, skills_base_path):
        """Skill prompt should be valid markdown."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")
        assert content, "Skill content should not be empty"

        # Check for markdown content after frontmatter
        lines = content.split("\n")
        frontmatter_ended = False
        dash_count = 0

        for line in lines:
            if line.strip() == "---":
                dash_count += 1
                if dash_count == 2:
                    frontmatter_ended = True
                    continue

            if frontmatter_ended and line.strip():
                # Should have some markdown content
                break

        assert frontmatter_ended, "Skill should have content after frontmatter"

        # Check for a title heading
        assert "# " in content, "Skill should have at least one markdown heading"

    def test_skill_has_correct_name(self, skills_base_path):
        """Skill should have correct name in frontmatter."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")
        frontmatter = parse_skill_frontmatter(content)

        assert frontmatter.get("name") == "qa-orchestrator"

    def test_skill_has_depth_selection(self, skills_base_path):
        """Skill should document depth selection logic."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")

        # Check for depth-related content
        assert "depth" in content.lower(), "Skill should mention testing depth"
        assert "shallow" in content.lower() or "deep" in content.lower(), (
            "Skill should mention depth levels"
        )

    def test_skill_has_output_format(self, skills_base_path):
        """Skill should document output format."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")

        # Check for output format section
        assert "output" in content.lower(), "Skill should document output format"
        assert "json" in content.lower(), "Skill should specify JSON output"


# =============================================================================
# QA AGENT SKILLS TESTS
# =============================================================================


class TestQAAgentSkills:
    """Tests for individual QA agent skills."""

    def test_behavioral_tester_skill_exists(self, skills_base_path):
        """Behavioral tester skill should exist."""
        skill_path = skills_base_path / "qa-behavioral-tester"
        assert skill_path.exists(), "qa-behavioral-tester skill directory should exist"

        skill_files = list(skill_path.glob("[Ss][Kk][Ii][Ll][Ll].md"))
        assert len(skill_files) > 0, "qa-behavioral-tester should have SKILL.md file"

    def test_contract_validator_skill_exists(self, skills_base_path):
        """Contract validator skill should exist."""
        skill_path = skills_base_path / "qa-contract-validator"
        assert skill_path.exists(), "qa-contract-validator skill directory should exist"

        skill_files = list(skill_path.glob("[Ss][Kk][Ii][Ll][Ll].md"))
        assert len(skill_files) > 0, "qa-contract-validator should have SKILL.md file"

    def test_regression_scanner_skill_exists(self, skills_base_path):
        """Regression scanner skill should exist."""
        skill_path = skills_base_path / "qa-regression-scanner"
        assert skill_path.exists(), "qa-regression-scanner skill directory should exist"

        skill_files = list(skill_path.glob("[Ss][Kk][Ii][Ll][Ll].md"))
        assert len(skill_files) > 0, "qa-regression-scanner should have SKILL.md file"


# =============================================================================
# SKILL STRUCTURE TESTS
# =============================================================================


class TestSkillStructure:
    """Tests for skill file structure consistency."""

    @pytest.mark.parametrize("skill_name", [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ])
    def test_skill_has_frontmatter(self, skills_base_path, skill_name):
        """Each skill should have valid YAML frontmatter."""
        content = get_skill_content(skills_base_path, skill_name)
        assert content, f"{skill_name} skill content should not be empty"

        frontmatter = parse_skill_frontmatter(content)
        assert frontmatter, f"{skill_name} should have parseable frontmatter"

    @pytest.mark.parametrize("skill_name", [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ])
    def test_skill_has_name(self, skills_base_path, skill_name):
        """Each skill should have name in frontmatter."""
        content = get_skill_content(skills_base_path, skill_name)
        frontmatter = parse_skill_frontmatter(content)

        assert "name" in frontmatter, f"{skill_name} should have 'name'"
        assert frontmatter["name"] == skill_name, f"{skill_name} name should match directory"

    @pytest.mark.parametrize("skill_name", [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ])
    def test_skill_has_description(self, skills_base_path, skill_name):
        """Each skill should have description in frontmatter."""
        content = get_skill_content(skills_base_path, skill_name)
        frontmatter = parse_skill_frontmatter(content)

        assert "description" in frontmatter, f"{skill_name} should have 'description'"
        assert len(frontmatter["description"]) > 10, f"{skill_name} description should be meaningful"

    @pytest.mark.parametrize("skill_name", [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ])
    def test_skill_has_allowed_tools(self, skills_base_path, skill_name):
        """Each skill should specify allowed tools."""
        content = get_skill_content(skills_base_path, skill_name)
        frontmatter = parse_skill_frontmatter(content)

        assert "allowed-tools" in frontmatter, f"{skill_name} should have 'allowed-tools'"

    @pytest.mark.parametrize("skill_name", [
        "qa-orchestrator",
        "qa-behavioral-tester",
        "qa-contract-validator",
        "qa-regression-scanner",
    ])
    def test_skill_has_markdown_content(self, skills_base_path, skill_name):
        """Each skill should have markdown content after frontmatter."""
        content = get_skill_content(skills_base_path, skill_name)

        # Check for heading after frontmatter
        assert "# " in content, f"{skill_name} should have markdown headings"


# =============================================================================
# SKILL CONTENT VALIDATION TESTS
# =============================================================================


class TestSkillContentValidation:
    """Tests for skill content quality."""

    def test_behavioral_tester_has_test_generation(self, skills_base_path):
        """Behavioral tester should document test generation."""
        content = get_skill_content(skills_base_path, "qa-behavioral-tester")

        assert "test" in content.lower(), "Should mention test generation"
        assert "curl" in content.lower() or "http" in content.lower(), (
            "Should mention HTTP requests"
        )

    def test_behavioral_tester_has_output_format(self, skills_base_path):
        """Behavioral tester should document output format."""
        content = get_skill_content(skills_base_path, "qa-behavioral-tester")

        assert "output" in content.lower(), "Should document output format"
        assert "json" in content.lower(), "Should specify JSON output"

    def test_contract_validator_has_consumer_discovery(self, skills_base_path):
        """Contract validator should document consumer discovery."""
        content = get_skill_content(skills_base_path, "qa-contract-validator")

        assert "consumer" in content.lower(), "Should mention consumer discovery"
        assert "contract" in content.lower(), "Should mention contracts"

    def test_contract_validator_has_validation_rules(self, skills_base_path):
        """Contract validator should document validation rules."""
        content = get_skill_content(skills_base_path, "qa-contract-validator")

        assert "validation" in content.lower() or "validate" in content.lower(), (
            "Should document validation"
        )

    def test_regression_scanner_has_diff_analysis(self, skills_base_path):
        """Regression scanner should document diff analysis."""
        content = get_skill_content(skills_base_path, "qa-regression-scanner")

        assert "diff" in content.lower(), "Should mention diff analysis"
        assert "git" in content.lower(), "Should mention git"

    def test_regression_scanner_has_priority_scoring(self, skills_base_path):
        """Regression scanner should document priority scoring."""
        content = get_skill_content(skills_base_path, "qa-regression-scanner")

        assert "priority" in content.lower(), "Should mention priority scoring"


# =============================================================================
# TOOL CONFIGURATION TESTS
# =============================================================================


class TestToolConfiguration:
    """Tests for skill tool configuration."""

    def test_orchestrator_has_all_tools(self, skills_base_path):
        """Orchestrator should have access to core tools."""
        content = get_skill_content(skills_base_path, "qa-orchestrator")
        frontmatter = parse_skill_frontmatter(content)

        allowed = frontmatter.get("allowed-tools", "")
        assert "Read" in allowed, "Should have Read tool"
        assert "Bash" in allowed, "Should have Bash tool"

    def test_behavioral_tester_has_bash(self, skills_base_path):
        """Behavioral tester needs Bash for curl commands."""
        content = get_skill_content(skills_base_path, "qa-behavioral-tester")
        frontmatter = parse_skill_frontmatter(content)

        allowed = frontmatter.get("allowed-tools", "")
        assert "Bash" in allowed, "Behavioral tester should have Bash for HTTP requests"

    def test_regression_scanner_has_bash(self, skills_base_path):
        """Regression scanner needs Bash for git commands."""
        content = get_skill_content(skills_base_path, "qa-regression-scanner")
        frontmatter = parse_skill_frontmatter(content)

        allowed = frontmatter.get("allowed-tools", "")
        assert "Bash" in allowed, "Regression scanner should have Bash for git"


# =============================================================================
# SKILL DIRECTORY STRUCTURE TESTS
# =============================================================================


class TestSkillDirectoryStructure:
    """Tests for skill directory structure."""

    def test_all_qa_skills_present(self, skills_base_path, qa_skill_names):
        """All expected QA skills should be present."""
        for skill_name in qa_skill_names:
            skill_path = skills_base_path / skill_name
            assert skill_path.exists(), f"Missing skill directory: {skill_name}"
            assert skill_path.is_dir(), f"Skill path should be a directory: {skill_name}"

    def test_skills_directory_exists(self, skills_base_path):
        """Skills base directory should exist."""
        assert skills_base_path.exists(), "Skills directory should exist"
        assert skills_base_path.is_dir(), "Skills path should be a directory"

    def test_no_empty_skill_directories(self, skills_base_path, qa_skill_names):
        """No skill directory should be empty."""
        for skill_name in qa_skill_names:
            skill_path = skills_base_path / skill_name
            if skill_path.exists():
                contents = list(skill_path.iterdir())
                assert len(contents) > 0, f"Skill directory should not be empty: {skill_name}"


# =============================================================================
# CONSISTENCY TESTS
# =============================================================================


class TestSkillConsistency:
    """Tests for consistency across skills."""

    def test_all_skills_use_same_frontmatter_format(self, skills_base_path, qa_skill_names):
        """All skills should use consistent frontmatter format."""
        for skill_name in qa_skill_names:
            content = get_skill_content(skills_base_path, skill_name)
            if content:
                # Should start with ---
                assert content.strip().startswith("---"), (
                    f"{skill_name} should start with YAML frontmatter delimiter"
                )

    def test_all_skills_have_output_section(self, skills_base_path, qa_skill_names):
        """All skills should document their output format."""
        for skill_name in qa_skill_names:
            content = get_skill_content(skills_base_path, skill_name)
            if content:
                # Each skill should have output documentation
                has_output = "output" in content.lower() or "format" in content.lower()
                assert has_output, f"{skill_name} should document output format"

    def test_all_skills_mention_json(self, skills_base_path, qa_skill_names):
        """All skills should use JSON for structured output."""
        for skill_name in qa_skill_names:
            content = get_skill_content(skills_base_path, skill_name)
            if content:
                assert "json" in content.lower(), (
                    f"{skill_name} should mention JSON for output"
                )
