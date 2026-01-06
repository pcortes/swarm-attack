"""SemanticQAMetrics - Track semantic testing performance metrics."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SemanticTestMetric:
    """Single test run metric."""
    timestamp: str
    verdict: str
    execution_time_ms: float
    depth: str  # "unit", "integration", "semantic"
    was_true_positive: Optional[bool] = None  # Bug caught that was real
    was_false_positive: Optional[bool] = None  # FAIL verdict but code was correct
    scope: str = "changes_only"


@dataclass
class SemanticQAMetrics:
    """Aggregated metrics for semantic QA testing."""

    metrics_file: Path = field(default_factory=lambda: Path(".swarm/qa/metrics.json"))
    metrics: list[SemanticTestMetric] = field(default_factory=list)

    def __post_init__(self):
        self.metrics_file = Path(self.metrics_file)
        self._load()

    def _load(self) -> None:
        """Load metrics from disk."""
        if self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text())
                self.metrics = [SemanticTestMetric(**m) for m in data.get("metrics", [])]
            except (json.JSONDecodeError, KeyError):
                self.metrics = []

    def _save(self) -> None:
        """Save metrics to disk."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"metrics": [asdict(m) for m in self.metrics]}
        self.metrics_file.write_text(json.dumps(data, indent=2))

    def record_test(
        self,
        verdict: str,
        execution_time_ms: float,
        depth: str = "semantic",
        scope: str = "changes_only",
    ) -> None:
        """Record a test run."""
        metric = SemanticTestMetric(
            timestamp=datetime.now().isoformat(),
            verdict=verdict,
            execution_time_ms=execution_time_ms,
            depth=depth,
            scope=scope,
        )
        self.metrics.append(metric)
        self._save()

    def record_true_positive(self, timestamp: str) -> None:
        """Mark a FAIL verdict as a true positive (real bug found)."""
        for m in reversed(self.metrics):
            if m.timestamp == timestamp:
                m.was_true_positive = True
                m.was_false_positive = False
                break
        self._save()

    def record_false_positive(self, timestamp: str) -> None:
        """Mark a FAIL verdict as a false positive (code was actually correct)."""
        for m in reversed(self.metrics):
            if m.timestamp == timestamp:
                m.was_true_positive = False
                m.was_false_positive = True
                break
        self._save()

    def get_summary(self) -> dict:
        """Get aggregated metrics summary."""
        total = len(self.metrics)
        if total == 0:
            return {
                "total_tests": 0,
                "pass_rate": 0.0,
                "fail_rate": 0.0,
                "partial_rate": 0.0,
                "avg_execution_time_ms": 0.0,
                "true_positive_rate": 0.0,
                "false_positive_rate": 0.0,
                "coverage_by_depth": {},
            }

        passes = sum(1 for m in self.metrics if m.verdict == "PASS")
        fails = sum(1 for m in self.metrics if m.verdict == "FAIL")
        partials = sum(1 for m in self.metrics if m.verdict == "PARTIAL")

        # True/false positive rates (only for FAIL verdicts that have been classified)
        classified_fails = [m for m in self.metrics if m.verdict == "FAIL" and m.was_true_positive is not None]
        true_positives = sum(1 for m in classified_fails if m.was_true_positive)
        false_positives = sum(1 for m in classified_fails if m.was_false_positive)

        # Execution times
        exec_times = [m.execution_time_ms for m in self.metrics]
        avg_time = sum(exec_times) / len(exec_times) if exec_times else 0.0

        # Coverage by depth
        depth_counts: dict[str, int] = {}
        for m in self.metrics:
            depth_counts[m.depth] = depth_counts.get(m.depth, 0) + 1

        return {
            "total_tests": total,
            "pass_rate": passes / total,
            "fail_rate": fails / total,
            "partial_rate": partials / total,
            "avg_execution_time_ms": avg_time,
            "true_positive_rate": true_positives / len(classified_fails) if classified_fails else 0.0,
            "false_positive_rate": false_positives / len(classified_fails) if classified_fails else 0.0,
            "coverage_by_depth": depth_counts,
        }
