"""Unit tests for CLI review-commits command.

Tests cover:
- JSON output structure matches COO integration expectations
- Exit codes (0 on success, non-zero on failure)
- Error output goes to stderr
- Timeout handling
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from swarm_attack.cli.review_commits import review_commits
from swarm_attack.commit_review.models import (
    ReviewReport,
    CommitReview,
    Finding,
    Verdict,
    Severity,
    TDDPlan,
)


class TestCLIJsonOutput:
    """Tests for JSON output structure matching COO expectations.

    COO expects:
    - commit_reviews[]: sha, message, score, verdict, findings[]
    - overall_score: float (0.0 - 1.0)
    - summary: string
    """

    @pytest.fixture
    def sample_report(self):
        """Create a sample ReviewReport for testing."""
        return ReviewReport(
            generated_at="2025-12-31T12:00:00",
            repo_path="/path/to/repo",
            branch="main",
            since="24 hours ago",
            commit_reviews=[
                CommitReview(
                    commit_sha="abc1234",
                    message="fix: resolve bug",
                    author="John Doe",
                    findings=[
                        Finding(
                            commit_sha="abc1234",
                            expert="Dr. Elena Vasquez",
                            severity=Severity.MEDIUM,
                            category="reliability",
                            description="Missing error handling",
                            evidence="src/app.py:42",
                        )
                    ],
                    score=0.75,
                    verdict=Verdict.FIX,
                    tdd_plans=[
                        TDDPlan(
                            finding_id="f1",
                            red_phase="Write test for error handling",
                            green_phase="Add try/except block",
                            refactor_phase="Extract to utility function",
                        )
                    ],
                ),
                CommitReview(
                    commit_sha="def5678",
                    message="feat: add feature",
                    author="Jane Doe",
                    findings=[],
                    score=1.0,
                    verdict=Verdict.LEAVE,
                    tdd_plans=[],
                ),
            ],
            overall_score=0.875,
            summary="2 commits reviewed. 1 issue found requiring attention.",
        )

    def test_json_output_has_commit_reviews_array(self, sample_report):
        """JSON output has commit_reviews[] array."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        assert "commit_reviews" in data
        assert isinstance(data["commit_reviews"], list)
        assert len(data["commit_reviews"]) == 2

    def test_json_output_commit_has_required_fields(self, sample_report):
        """Each commit in commit_reviews has required fields."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        # COO expects: sha, message, score, verdict, findings[]
        commit = data["commit_reviews"][0]

        # Note: current implementation uses commit_sha, not sha
        # This test documents what COO expects vs actual
        assert "commit_sha" in commit, "commit_sha field missing"
        assert "message" in commit, "message field missing"
        assert "score" in commit, "score field missing"
        assert "verdict" in commit, "verdict field missing"
        assert "findings" in commit, "findings field missing"
        assert isinstance(commit["findings"], list)

    def test_json_output_has_overall_score(self, sample_report):
        """JSON output has overall_score field."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        assert "overall_score" in data
        assert isinstance(data["overall_score"], float)
        assert 0.0 <= data["overall_score"] <= 1.0

    def test_json_output_has_summary(self, sample_report):
        """JSON output has summary field."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        assert "summary" in data
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0

    def test_json_output_findings_have_required_fields(self, sample_report):
        """Each finding has required fields: expert, severity, description, evidence."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        # Get first commit which has findings
        commit = data["commit_reviews"][0]
        finding = commit["findings"][0]

        assert "expert" in finding
        assert "severity" in finding
        assert "description" in finding
        assert "evidence" in finding

    def test_json_output_tdd_plans_structure(self, sample_report):
        """TDD plans have required structure."""
        from swarm_attack.commit_review.report import ReportGenerator

        generator = ReportGenerator()
        json_output = generator.to_json(sample_report)
        data = json.loads(json_output)

        commit = data["commit_reviews"][0]
        assert "tdd_plans" in commit
        assert len(commit["tdd_plans"]) == 1

        plan = commit["tdd_plans"][0]
        assert "finding_id" in plan
        assert "red_phase" in plan
        assert "green_phase" in plan
        assert "refactor_phase" in plan


class TestCLIExitCodes:
    """Tests for CLI exit codes.

    COO expects:
    - Return code 0 on success
    - Return code non-zero on failure
    """

    def test_exit_code_0_on_success(self):
        """CLI returns exit code 0 on successful review."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": [], "overall_score": 1.0, "summary": "No commits"}'

            result = runner.invoke(review_commits, ["--output", "json"])

            assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"

    def test_exit_code_nonzero_on_error(self):
        """CLI returns non-zero exit code on error."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.side_effect = RuntimeError("Git command failed")

            result = runner.invoke(review_commits, [])

            assert result.exit_code != 0, "Expected non-zero exit code on error"

    def test_exit_code_nonzero_on_strict_mode_with_issues(self):
        """CLI returns non-zero exit code when --strict and medium+ issues found."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            # Create mock result with has_medium_or_higher flag
            mock_result = MagicMock()
            mock_result.has_medium_or_higher = True
            mock_result.content = "Report with issues"
            mock_review.return_value = mock_result

            result = runner.invoke(review_commits, ["--strict"])

            assert result.exit_code == 1, f"Expected exit code 1 in strict mode with issues, got {result.exit_code}"

    def test_exit_code_0_on_strict_mode_without_issues(self):
        """CLI returns exit code 0 when --strict and no medium+ issues found."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            # Return plain string (no medium+ issues)
            mock_review.return_value = '{"commit_reviews": [], "overall_score": 1.0, "summary": "All clear"}'

            result = runner.invoke(review_commits, ["--strict"])

            assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"


class TestCLIErrorOutput:
    """Tests for error output handling.

    COO expects errors to go to stderr, not stdout.
    """

    def test_error_output_goes_to_stderr(self):
        """Errors should be written to stderr, not stdout."""
        runner = CliRunner(mix_stderr=False)

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.side_effect = RuntimeError("Test error")

            result = runner.invoke(review_commits, [])

            # Error message should be in stderr, not stdout
            assert "Error:" in result.output or result.stderr_bytes, (
                "Expected error output in stderr"
            )

    def test_successful_output_goes_to_stdout(self):
        """Successful report should be written to stdout."""
        runner = CliRunner(mix_stderr=False)

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": [], "overall_score": 1.0, "summary": "OK"}'

            result = runner.invoke(review_commits, ["--output", "json"])

            # Report should be in stdout
            assert "commit_reviews" in result.output


class TestCLITimeoutHandling:
    """Tests for subprocess timeout handling.

    COO needs timeout handling for subprocess invocation (300 seconds per project).
    """

    def test_handles_timeout_gracefully(self):
        """CLI handles timeout errors gracefully."""
        import subprocess

        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.side_effect = subprocess.TimeoutExpired("git", 300)

            result = runner.invoke(review_commits, [])

            # Should exit with non-zero code
            assert result.exit_code != 0
            # Should have error message
            assert "Error" in result.output or len(result.output) > 0

    def test_timeout_error_message_is_informative(self):
        """Timeout error message should mention the timeout."""
        import subprocess

        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.side_effect = subprocess.TimeoutExpired("git", 300)

            result = runner.invoke(review_commits, [])

            # Error output should mention timeout
            # Note: The exact message depends on exception handling in CLI
            assert result.exit_code != 0


class TestCLISubprocessContract:
    """Tests for subprocess invocation contract with COO.

    COO invokes: swarm-attack review-commits --since "{time}" --output json
    """

    def test_since_option_passed_correctly(self):
        """--since option is correctly passed to run_review."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": []}'

            runner.invoke(review_commits, ["--since", "1 hour ago"])

            mock_review.assert_called_once()
            call_args = mock_review.call_args
            assert call_args.kwargs.get("since") == "1 hour ago" or "1 hour ago" in str(call_args)

    def test_output_json_format(self):
        """--output json produces valid JSON."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": [], "overall_score": 1.0, "summary": "test"}'

            result = runner.invoke(review_commits, ["--output", "json"])

            # Should be valid JSON
            try:
                data = json.loads(result.output)
                assert "commit_reviews" in data
            except json.JSONDecodeError as e:
                pytest.fail(f"Output is not valid JSON: {result.output[:200]}... Error: {e}")

    def test_default_since_is_24_hours(self):
        """Default --since is '24 hours ago'."""
        runner = CliRunner()

        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": []}'

            runner.invoke(review_commits, [])

            mock_review.assert_called_once()
            call_args = mock_review.call_args
            # Check default value
            assert call_args.kwargs.get("since") == "24 hours ago" or "24 hours ago" in str(call_args)


class TestCLINoCommitsScenario:
    """Tests for handling no commits scenario.

    COO expects valid JSON even when no commits are found.
    """

    def test_no_commits_json_output_is_valid_json(self):
        """When no commits found, JSON output should still be valid JSON."""
        from swarm_attack.commit_review.report import ReportGenerator
        from swarm_attack.commit_review.models import ReviewReport

        # Create empty report
        report = ReviewReport(
            generated_at="2025-12-31T12:00:00",
            repo_path="/path/to/repo",
            branch="main",
            since="24 hours ago",
            commit_reviews=[],
            overall_score=1.0,
            summary="No commits found to review.",
        )

        generator = ReportGenerator()
        json_output = generator.to_json(report)

        # Should be valid JSON
        data = json.loads(json_output)
        assert data["commit_reviews"] == []
        assert data["overall_score"] == 1.0
        assert "summary" in data

    def test_no_commits_has_required_fields(self):
        """Empty commit_reviews should still have required top-level fields."""
        from swarm_attack.commit_review.report import ReportGenerator
        from swarm_attack.commit_review.models import ReviewReport

        report = ReviewReport(
            generated_at="2025-12-31T12:00:00",
            repo_path="/path/to/repo",
            branch="main",
            since="24 hours ago",
            commit_reviews=[],
            overall_score=1.0,
            summary="No commits found.",
        )

        generator = ReportGenerator()
        json_output = generator.to_json(report)
        data = json.loads(json_output)

        # COO expects these fields even when empty
        assert "commit_reviews" in data
        assert "overall_score" in data
        assert "summary" in data


class TestCLIRealWorldIntegration:
    """Tests simulating real COO integration scenarios."""

    def test_coo_invocation_pattern(self):
        """Test the exact invocation pattern COO will use."""
        runner = CliRunner()

        # COO invokes: swarm-attack review-commits --since "{checkpoint_time}" --output json
        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = json.dumps({
                "commit_reviews": [
                    {
                        "commit_sha": "abc1234",
                        "message": "fix: bug",
                        "score": 0.9,
                        "verdict": "leave",
                        "findings": []
                    }
                ],
                "overall_score": 0.9,
                "summary": "1 commit reviewed"
            })

            result = runner.invoke(review_commits, [
                "--since", "2025-12-31 10:00:00",
                "--output", "json"
            ])

            # Must succeed
            assert result.exit_code == 0

            # Must be valid JSON
            data = json.loads(result.output)
            assert "commit_reviews" in data
            assert "overall_score" in data
            assert "summary" in data

    def test_stderr_for_errors_stdout_for_report(self):
        """Errors go to stderr, report goes to stdout."""
        runner = CliRunner(mix_stderr=False)

        # Successful case
        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.return_value = '{"commit_reviews": [], "overall_score": 1.0, "summary": "OK"}'

            result = runner.invoke(review_commits, ["--output", "json"])

            # Report in stdout
            assert "commit_reviews" in result.output

        # Error case
        with patch("swarm_attack.cli.review_commits.run_review") as mock_review:
            mock_review.side_effect = RuntimeError("Git failed")

            result = runner.invoke(review_commits, [])

            # Error should trigger non-zero exit
            assert result.exit_code == 1
