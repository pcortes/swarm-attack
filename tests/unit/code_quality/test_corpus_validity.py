"""Tests to validate the code quality test corpus.

These tests ensure:
1. All samples in the manifest exist as files
2. The manifest follows the expected schema
3. All Python files in the corpus parse without syntax errors
4. Clean code samples have no expected findings
5. Non-clean samples have at least one expected finding
"""
import ast
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Path to the corpus directory
CORPUS_DIR = Path(__file__).parent.parent.parent / "fixtures" / "code_quality_corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


@pytest.fixture
def manifest() -> Dict[str, Any]:
    """Load the manifest.json file."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


@pytest.fixture
def manifest_samples(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get samples from manifest."""
    return manifest.get("samples", [])


class TestManifestExists:
    """Test that the manifest file exists and is valid JSON."""

    def test_manifest_file_exists(self):
        """Manifest file must exist."""
        assert MANIFEST_PATH.exists(), f"Manifest not found at {MANIFEST_PATH}"

    def test_manifest_is_valid_json(self):
        """Manifest must be valid JSON."""
        with open(MANIFEST_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestManifestSchema:
    """Test that the manifest matches the expected schema."""

    def test_manifest_has_required_fields(self, manifest: Dict[str, Any]):
        """Manifest must have required top-level fields."""
        required_fields = ["corpus_version", "samples"]
        for field in required_fields:
            assert field in manifest, f"Manifest missing required field: {field}"

    def test_manifest_version_format(self, manifest: Dict[str, Any]):
        """Corpus version must be semver format."""
        version = manifest.get("corpus_version", "")
        parts = version.split(".")
        assert len(parts) == 3, f"Version {version} is not semver format"
        for part in parts:
            assert part.isdigit(), f"Version part {part} is not numeric"

    def test_manifest_has_samples(self, manifest: Dict[str, Any]):
        """Manifest must have at least one sample."""
        samples = manifest.get("samples", [])
        assert len(samples) > 0, "Manifest has no samples"

    def test_manifest_total_samples_matches(self, manifest: Dict[str, Any]):
        """Total samples count must match actual samples."""
        declared_total = manifest.get("total_samples", 0)
        actual_total = len(manifest.get("samples", []))
        assert declared_total == actual_total, (
            f"Declared {declared_total} samples but found {actual_total}"
        )


class TestSampleSchema:
    """Test that each sample in the manifest has required fields."""

    def test_samples_have_required_fields(self, manifest_samples: List[Dict[str, Any]]):
        """Each sample must have required fields."""
        required_fields = ["file", "category", "expected_findings"]
        for sample in manifest_samples:
            for field in required_fields:
                assert field in sample, (
                    f"Sample {sample.get('file', 'unknown')} missing field: {field}"
                )

    def test_samples_have_valid_category(self, manifest_samples: List[Dict[str, Any]]):
        """Each sample must have a valid category."""
        valid_categories = {
            "hallucinations",
            "code_smells",
            "error_handling",
            "solid_violations",
            "clean_code",
        }
        for sample in manifest_samples:
            category = sample.get("category")
            assert category in valid_categories, (
                f"Sample {sample['file']} has invalid category: {category}"
            )

    def test_samples_expected_findings_is_list(self, manifest_samples: List[Dict[str, Any]]):
        """expected_findings must be a list."""
        for sample in manifest_samples:
            findings = sample.get("expected_findings")
            assert isinstance(findings, list), (
                f"Sample {sample['file']} expected_findings is not a list"
            )

    def test_clean_code_samples_have_no_findings(self, manifest_samples: List[Dict[str, Any]]):
        """Clean code samples must have empty expected_findings."""
        for sample in manifest_samples:
            if sample.get("category") == "clean_code":
                findings = sample.get("expected_findings", [])
                assert len(findings) == 0, (
                    f"Clean code sample {sample['file']} has findings: {findings}"
                )

    def test_non_clean_samples_have_findings(self, manifest_samples: List[Dict[str, Any]]):
        """Non-clean samples must have at least one expected finding."""
        for sample in manifest_samples:
            if sample.get("category") != "clean_code":
                findings = sample.get("expected_findings", [])
                assert len(findings) > 0, (
                    f"Sample {sample['file']} has no expected findings"
                )


class TestAllSamplesExist:
    """Test that all samples in manifest exist as files."""

    def test_all_samples_in_manifest_exist(self, manifest_samples: List[Dict[str, Any]]):
        """Every file listed in manifest must exist."""
        missing_files = []
        for sample in manifest_samples:
            file_path = CORPUS_DIR / sample["file"]
            if not file_path.exists():
                missing_files.append(sample["file"])

        assert len(missing_files) == 0, (
            f"Missing {len(missing_files)} files:\n" +
            "\n".join(f"  - {f}" for f in missing_files[:10]) +
            (f"\n  ... and {len(missing_files) - 10} more" if len(missing_files) > 10 else "")
        )


class TestAllFilesInManifest:
    """Test that all Python files in corpus are in manifest."""

    def test_all_python_files_in_manifest(self, manifest_samples: List[Dict[str, Any]]):
        """Every .py file in corpus directories should be in manifest."""
        manifest_files = {sample["file"] for sample in manifest_samples}

        # Find all .py files in corpus subdirectories
        corpus_files = set()
        for subdir in ["hallucinations", "code_smells", "error_handling",
                       "solid_violations", "clean_code"]:
            subdir_path = CORPUS_DIR / subdir
            if subdir_path.exists():
                for py_file in subdir_path.glob("*.py"):
                    relative_path = f"{subdir}/{py_file.name}"
                    corpus_files.add(relative_path)

        # Find files in corpus but not in manifest
        missing_from_manifest = corpus_files - manifest_files
        assert len(missing_from_manifest) == 0, (
            f"Files in corpus but not in manifest:\n" +
            "\n".join(f"  - {f}" for f in sorted(missing_from_manifest))
        )


class TestSamplesAreValidPython:
    """Test that all sample files are valid Python syntax."""

    def test_samples_are_valid_python(self, manifest_samples: List[Dict[str, Any]]):
        """All .py files must parse without syntax errors."""
        syntax_errors = []

        for sample in manifest_samples:
            file_path = CORPUS_DIR / sample["file"]
            if not file_path.exists():
                continue  # Handled by other test

            try:
                with open(file_path) as f:
                    source = f.read()
                ast.parse(source)
            except SyntaxError as e:
                syntax_errors.append(f"{sample['file']}: {e.msg} (line {e.lineno})")

        assert len(syntax_errors) == 0, (
            f"Syntax errors in {len(syntax_errors)} files:\n" +
            "\n".join(f"  - {e}" for e in syntax_errors)
        )


class TestCorpusDistribution:
    """Test the distribution of samples across categories."""

    def test_minimum_samples_per_category(self, manifest_samples: List[Dict[str, Any]]):
        """Each category should have a minimum number of samples."""
        category_counts: Dict[str, int] = {}
        for sample in manifest_samples:
            category = sample.get("category")
            category_counts[category] = category_counts.get(category, 0) + 1

        min_samples = 3  # At least 3 samples per category
        for category, count in category_counts.items():
            assert count >= min_samples, (
                f"Category {category} has only {count} samples (min: {min_samples})"
            )

    def test_clean_code_samples_exist(self, manifest_samples: List[Dict[str, Any]]):
        """Must have clean code samples for false positive testing."""
        clean_samples = [s for s in manifest_samples if s.get("category") == "clean_code"]
        assert len(clean_samples) >= 5, (
            f"Need at least 5 clean code samples, found {len(clean_samples)}"
        )

    def test_hallucination_samples_exist(self, manifest_samples: List[Dict[str, Any]]):
        """Must have hallucination samples for AC1 testing."""
        hallucination_samples = [
            s for s in manifest_samples if s.get("category") == "hallucinations"
        ]
        assert len(hallucination_samples) >= 10, (
            f"Need at least 10 hallucination samples for AC1, found {len(hallucination_samples)}"
        )


class TestFindingSchema:
    """Test that expected findings have proper schema."""

    def test_findings_have_required_fields(self, manifest_samples: List[Dict[str, Any]]):
        """Each finding must have required fields."""
        for sample in manifest_samples:
            for i, finding in enumerate(sample.get("expected_findings", [])):
                assert "type" in finding, (
                    f"Finding {i} in {sample['file']} missing 'type'"
                )
                assert "severity" in finding, (
                    f"Finding {i} in {sample['file']} missing 'severity'"
                )

    def test_findings_have_valid_severity(self, manifest_samples: List[Dict[str, Any]]):
        """Severity must be one of the valid values."""
        valid_severities = {"critical", "high", "medium", "low"}
        for sample in manifest_samples:
            for finding in sample.get("expected_findings", []):
                severity = finding.get("severity")
                assert severity in valid_severities, (
                    f"Finding in {sample['file']} has invalid severity: {severity}"
                )


class TestSubcategoryDistribution:
    """Test subcategory distribution within categories."""

    def test_hallucinations_subcategories(self, manifest_samples: List[Dict[str, Any]]):
        """Hallucinations should have multiple subcategories."""
        subcategories = set()
        for sample in manifest_samples:
            if sample.get("category") == "hallucinations":
                subcategories.add(sample.get("subcategory"))

        expected = {"hallucinated_import", "hallucinated_method", "wrong_signature"}
        missing = expected - subcategories
        assert len(missing) == 0, f"Missing hallucination subcategories: {missing}"

    def test_code_smells_subcategories(self, manifest_samples: List[Dict[str, Any]]):
        """Code smells should have multiple subcategories."""
        subcategories = set()
        for sample in manifest_samples:
            if sample.get("category") == "code_smells":
                subcategories.add(sample.get("subcategory"))

        expected = {"long_method", "large_class", "deep_nesting", "god_class",
                    "copy_paste", "primitive_obsession"}
        missing = expected - subcategories
        assert len(missing) == 0, f"Missing code smell subcategories: {missing}"
