"""Trace-Driven Testing — generate tests from production traces."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TraceStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


class TraceTestType(StrEnum):
    INTEGRATION = "integration"
    CONTRACT = "contract"
    LOAD = "load"
    REGRESSION = "regression"
    SMOKE = "smoke"


class CoverageLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class TraceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service: str = ""
    operation: str = ""
    status: TraceStatus = TraceStatus.SUCCESS
    duration_ms: float = 0.0
    span_count: int = 1
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class GeneratedTestCase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    test_type: TraceTestType = TraceTestType.INTEGRATION
    source_trace_id: str = ""
    service: str = ""
    operation: str = ""
    expected_status: TraceStatus = TraceStatus.SUCCESS
    expected_duration_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TraceCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_traces: int = 0
    total_tests: int = 0
    coverage_level: CoverageLevel = CoverageLevel.NONE
    coverage_pct: float = 0.0
    by_service: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    uncovered_operations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceDrivenTesting:
    """Generate tests from production traces."""

    def __init__(self, max_traces: int = 100000) -> None:
        self._max_traces = max_traces
        self._traces: list[TraceRecord] = []
        self._tests: list[GeneratedTestCase] = []
        logger.info("trace_driven_testing.initialized", max_traces=max_traces)

    def add_trace(
        self,
        trace_id: str,
        service: str,
        operation: str,
        status: TraceStatus = TraceStatus.SUCCESS,
        duration_ms: float = 0.0,
        span_count: int = 1,
        tags: dict[str, str] | None = None,
    ) -> TraceRecord:
        """Ingest a production trace."""
        record = TraceRecord(
            trace_id=trace_id,
            service=service,
            operation=operation,
            status=status,
            duration_ms=duration_ms,
            span_count=span_count,
            tags=tags or {},
        )
        self._traces.append(record)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces :]
        return record

    def extract_test_cases(
        self,
        service: str | None = None,
        test_type: TraceTestType = TraceTestType.INTEGRATION,
    ) -> list[GeneratedTestCase]:
        """Extract test cases from recorded traces."""
        targets = self._traces
        if service:
            targets = [t for t in targets if t.service == service]
        seen: set[str] = set()
        new_tests: list[GeneratedTestCase] = []
        for trace in targets:
            key = f"{trace.service}:{trace.operation}"
            if key in seen:
                continue
            seen.add(key)
            test = GeneratedTestCase(
                name=f"test_{trace.service}_{trace.operation}",
                test_type=test_type,
                source_trace_id=trace.trace_id,
                service=trace.service,
                operation=trace.operation,
                expected_status=trace.status,
                expected_duration_ms=trace.duration_ms,
            )
            new_tests.append(test)
            self._tests.append(test)
        logger.info(
            "trace_driven_testing.tests_extracted",
            count=len(new_tests),
        )
        return new_tests

    def generate_synthetic_traces(
        self,
        service: str,
        operation: str,
        count: int = 10,
    ) -> list[TraceRecord]:
        """Generate synthetic traces based on patterns."""
        existing = [t for t in self._traces if t.service == service and t.operation == operation]
        base_duration = sum(t.duration_ms for t in existing) / len(existing) if existing else 100.0
        synthetic: list[TraceRecord] = []
        for i in range(count):
            jitter = (i % 5 - 2) * 10
            record = TraceRecord(
                trace_id=f"synthetic-{uuid.uuid4().hex[:8]}",
                service=service,
                operation=operation,
                status=TraceStatus.SUCCESS,
                duration_ms=round(base_duration + jitter, 2),
            )
            synthetic.append(record)
            self._traces.append(record)
        return synthetic

    def validate_trace_coverage(self) -> dict[str, Any]:
        """Validate test coverage against traces."""
        trace_ops = {f"{t.service}:{t.operation}" for t in self._traces}
        test_ops = {f"{t.service}:{t.operation}" for t in self._tests}
        covered = trace_ops & test_ops
        uncovered = trace_ops - test_ops
        pct = round(len(covered) / len(trace_ops) * 100, 1) if trace_ops else 0
        if pct >= 80:
            level = CoverageLevel.FULL
        elif pct >= 50:
            level = CoverageLevel.PARTIAL
        elif pct > 0:
            level = CoverageLevel.MINIMAL
        else:
            level = CoverageLevel.NONE
        return {
            "coverage_pct": pct,
            "coverage_level": level.value,
            "covered_count": len(covered),
            "uncovered_count": len(uncovered),
            "uncovered": sorted(uncovered),
        }

    def compare_trace_patterns(
        self,
        service: str,
        operation: str,
    ) -> dict[str, Any]:
        """Compare trace patterns over time."""
        traces = [t for t in self._traces if t.service == service and t.operation == operation]
        if not traces:
            return {"service": service, "operation": operation, "samples": 0}
        durations = [t.duration_ms for t in traces]
        avg = sum(durations) / len(durations)
        error_rate = sum(1 for t in traces if t.status == TraceStatus.ERROR) / len(traces)
        return {
            "service": service,
            "operation": operation,
            "samples": len(traces),
            "avg_duration_ms": round(avg, 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "error_rate": round(error_rate, 4),
        }

    def get_coverage_report(self) -> TraceCoverageReport:
        """Generate a trace coverage report."""
        by_svc: dict[str, int] = {}
        by_st: dict[str, int] = {}
        for t in self._traces:
            by_svc[t.service] = by_svc.get(t.service, 0) + 1
            by_st[t.status.value] = by_st.get(t.status.value, 0) + 1
        cov = self.validate_trace_coverage()
        recs: list[str] = []
        if cov["coverage_pct"] < 50:
            recs.append("Coverage below 50% — generate more tests from traces")
        if cov["uncovered_count"] > 0:
            recs.append(f"{cov['uncovered_count']} operation(s) lack test coverage")
        if not recs:
            recs.append("Trace-driven testing coverage is healthy")
        return TraceCoverageReport(
            total_traces=len(self._traces),
            total_tests=len(self._tests),
            coverage_level=CoverageLevel(cov["coverage_level"]),
            coverage_pct=cov["coverage_pct"],
            by_service=by_svc,
            by_status=by_st,
            uncovered_operations=cov["uncovered"][:10],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all traces and tests."""
        self._traces.clear()
        self._tests.clear()
        logger.info("trace_driven_testing.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_traces": len(self._traces),
            "total_tests": len(self._tests),
            "unique_services": len({t.service for t in self._traces}),
            "unique_operations": len({f"{t.service}:{t.operation}" for t in self._traces}),
        }
