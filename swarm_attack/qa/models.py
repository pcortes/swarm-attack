"""QA Agent data models for swarm-attack."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional


# =============================================================================
# ENUMS
# =============================================================================


class ServiceStartupResult(Enum):
    """Service startup result from Section 10.1."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    PORT_CONFLICT = "port_conflict"
    DOCKER_UNAVAILABLE = "docker_unavailable"
    STARTUP_CRASHED = "startup_crashed"
    NO_HEALTH_ENDPOINT = "no_health_endpoint"


class AuthStrategy(Enum):
    """Authentication strategy from Section 10.2."""
    BEARER_TOKEN = "bearer"
    API_KEY_HEADER = "api_key"
    API_KEY_QUERY = "api_key_query"
    BASIC_AUTH = "basic"
    COOKIE_SESSION = "cookie"
    NONE = "none"


class QATrigger(Enum):
    """What initiated the QA session."""
    POST_VERIFICATION = "post_verification"
    BUG_REPRODUCTION = "bug_reproduction"
    USER_COMMAND = "user_command"
    PRE_MERGE = "pre_merge"
    SCHEDULED_HEALTH = "scheduled_health"
    SPEC_COMPLIANCE = "spec_compliance"


class QADepth(Enum):
    """Testing depth level."""
    SHALLOW = "shallow"
    STANDARD = "standard"
    DEEP = "deep"
    REGRESSION = "regression"


class QAStatus(Enum):
    """Status of a QA session from Section 10.12."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class QARecommendation(Enum):
    """QA outcome recommendation."""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


# =============================================================================
# CONFIG DATACLASSES
# =============================================================================


@dataclass
class QADataConfig:
    """Configure how QA handles test data (BUG-13/14: renamed from TestDataConfig)."""
    mode: Literal["shared", "isolated", "readonly"] = "shared"
    prefix: str = "qa_test_"
    cleanup_on_success: bool = True
    cleanup_on_failure: bool = False


# BUG-13/14: Backward compatibility alias (not a class definition, so pytest won't collect)
TestDataConfig = QADataConfig


@dataclass
class ResilienceConfig:
    """Configure retry and timeout behavior from Section 10.7."""
    request_timeout_seconds: int = 30
    connect_timeout_seconds: int = 5
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    retry_on_status: list[int] = field(default_factory=lambda: [429, 502, 503, 504])
    requests_per_second: float = 10.0
    respect_retry_after: bool = True
    verify_ssl: bool = True


@dataclass
class QALimits:
    """Hard limits to prevent runaway execution from Section 10.10."""
    max_cost_usd: float = 5.0
    warn_cost_usd: float = 2.0
    max_endpoints_shallow: int = 100
    max_endpoints_standard: int = 50
    max_endpoints_deep: int = 20
    max_tests_per_endpoint: int = 20
    max_retries_per_test: int = 2
    session_timeout_minutes: int = 30
    request_timeout_seconds: int = 30
    max_files_for_contract_analysis: int = 50
    max_consumers_per_endpoint: int = 10


@dataclass
class QASafetyConfig:
    """Safety settings to prevent accidents from Section 10.11."""
    detect_production: bool = True
    production_url_patterns: list[str] = field(default_factory=lambda: [
        r".*\.prod\..*",
        r".*production.*",
        r"api\.(company)\.com",
    ])
    allow_mutations_in_prod: bool = False
    allow_deep_tests_in_prod: bool = False
    allow_security_probes_in_prod: bool = False
    redact_tokens_in_logs: bool = True
    redact_patterns: list[str] = field(default_factory=lambda: [
        r"Bearer [A-Za-z0-9\-_]+",
        r"api[_-]?key[=:]\s*\S+",
        r"password[=:]\s*\S+",
    ])
    require_confirmation_for_delete: bool = True
    readonly_mode: bool = False


# =============================================================================
# CORE DATACLASSES
# =============================================================================


@dataclass
class QAEndpoint:
    """An API endpoint being tested."""
    method: str
    path: str
    auth_required: bool = False
    schema: Optional[dict[str, Any]] = None


@dataclass
class QAFinding:
    """A single QA finding/issue."""
    finding_id: str
    severity: Literal["critical", "moderate", "minor"]
    category: str
    endpoint: str
    test_type: str
    title: str
    description: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    evidence: dict[str, str]
    recommendation: str
    confidence: float = 0.9

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "category": self.category,
            "endpoint": self.endpoint,
            "test_type": self.test_type,
            "title": self.title,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAFinding:
        return cls(**data)


@dataclass
class QAContext:
    """Context for a QA session."""
    feature_id: Optional[str] = None
    issue_number: Optional[int] = None
    bug_id: Optional[str] = None
    spec_path: Optional[str] = None
    target_files: list[str] = field(default_factory=list)
    target_endpoints: list[QAEndpoint] = field(default_factory=list)
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    environment: dict[str, str] = field(default_factory=dict)
    git_diff: Optional[str] = None
    spec_content: Optional[str] = None
    related_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
            "bug_id": self.bug_id,
            "spec_path": self.spec_path,
            "target_files": self.target_files,
            "target_endpoints": [
                {"method": e.method, "path": e.path, "auth_required": e.auth_required}
                for e in self.target_endpoints
            ],
            "base_url": self.base_url,
            "environment": self.environment,
            "git_diff": self.git_diff,
            "spec_content": self.spec_content,
            "related_tests": self.related_tests,
        }


@dataclass
class QAResult:
    """Aggregated results from a QA session."""
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    endpoints_tested: list[str] = field(default_factory=list)
    findings: list[QAFinding] = field(default_factory=list)
    critical_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    recommendation: QARecommendation = QARecommendation.PASS
    confidence: float = 0.9
    behavioral_results: Optional[dict[str, Any]] = None
    contract_results: Optional[dict[str, Any]] = None
    regression_results: Optional[dict[str, Any]] = None
    skipped_reasons: dict[str, str] = field(default_factory=dict)
    partial_completion_reason: Optional[str] = None
    # Coverage tracking fields (QA Session Extension)
    endpoints_discovered: int = 0
    coverage_percentage: float = 0.0
    coverage_delta: float = 0.0  # vs baseline

    def to_dict(self) -> dict[str, Any]:
        return {
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "endpoints_tested": self.endpoints_tested,
            "findings": [f.to_dict() for f in self.findings],
            "critical_count": self.critical_count,
            "moderate_count": self.moderate_count,
            "minor_count": self.minor_count,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "endpoints_discovered": self.endpoints_discovered,
            "coverage_percentage": self.coverage_percentage,
            "coverage_delta": self.coverage_delta,
        }


@dataclass
class QASession:
    """Complete state of a QA session."""
    session_id: str
    trigger: QATrigger
    depth: QADepth
    status: QAStatus
    context: QAContext
    result: Optional[QAResult] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cost_usd: float = 0.0
    error: Optional[str] = None
    # QA Session Extension fields
    coverage_report: Optional[dict[str, Any]] = None
    regression_report: Optional[dict[str, Any]] = None
    is_baseline: bool = False
    baseline_session_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trigger": self.trigger.value,
            "depth": self.depth.value,
            "status": self.status.value,
            "context": self.context.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "coverage_report": self.coverage_report,
            "regression_report": self.regression_report,
            "is_baseline": self.is_baseline,
            "baseline_session_id": self.baseline_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QASession:
        trigger = QATrigger(data["trigger"])
        depth = QADepth(data["depth"])
        status = QAStatus(data["status"])
        context_data = data.get("context", {})

        # Restore target_endpoints from serialized form
        target_endpoints = [
            QAEndpoint(
                method=e.get("method", "GET"),
                path=e.get("path", ""),
                auth_required=e.get("auth_required", False),
            )
            for e in context_data.get("target_endpoints", [])
        ]

        context = QAContext(
            feature_id=context_data.get("feature_id"),
            issue_number=context_data.get("issue_number"),
            bug_id=context_data.get("bug_id"),
            spec_path=context_data.get("spec_path"),
            target_files=context_data.get("target_files", []),
            target_endpoints=target_endpoints,
            base_url=context_data.get("base_url"),
            environment=context_data.get("environment", {}),
            git_diff=context_data.get("git_diff"),
            spec_content=context_data.get("spec_content"),
            related_tests=context_data.get("related_tests", []),
        )
        result = None
        if data.get("result"):
            result_data = data["result"]
            findings = [QAFinding.from_dict(f) for f in result_data.get("findings", [])]
            result = QAResult(
                tests_run=result_data.get("tests_run", 0),
                tests_passed=result_data.get("tests_passed", 0),
                tests_failed=result_data.get("tests_failed", 0),
                findings=findings,
                recommendation=QARecommendation(result_data.get("recommendation", "pass")),
            )
        return cls(
            session_id=data["session_id"],
            trigger=trigger,
            depth=depth,
            status=status,
            context=context,
            result=result,
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            cost_usd=data.get("cost_usd", 0.0),
            error=data.get("error"),
            coverage_report=data.get("coverage_report"),
            regression_report=data.get("regression_report"),
            is_baseline=data.get("is_baseline", False),
            baseline_session_id=data.get("baseline_session_id"),
        )


@dataclass
class QABug:
    """A bug discovered by QA, ready for Bug Bash pipeline."""
    bug_id: str
    source_finding: str
    qa_session: str
    title: str
    description: str
    severity: Literal["critical", "moderate", "minor"]
    endpoint: str
    reproduction_steps: list[str]
    expected_behavior: str
    actual_behavior: str
    evidence: dict[str, str]

    def to_bug_report(self) -> dict[str, Any]:
        return {
            "description": f"{self.title}\n\n{self.description}",
            "error_message": self.evidence.get("error_message"),
            "steps_to_reproduce": self.reproduction_steps,
        }
