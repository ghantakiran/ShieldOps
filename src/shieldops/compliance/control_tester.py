"""Compliance Control Tester — track and analyze compliance control test results."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlTestResult(StrEnum):
    PASS = "pass"  # noqa: S105
    PARTIAL_PASS = "partial_pass"  # noqa: S105
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


class ControlType(StrEnum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    COMPENSATING = "compensating"
    ADMINISTRATIVE = "administrative"


class ControlTestFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


# --- Models ---


class ControlTestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    result: ControlTestResult = ControlTestResult.PASS
    control_type: ControlType = ControlType.PREVENTIVE
    frequency: ControlTestFrequency = ControlTestFrequency.MONTHLY
    pass_rate_pct: float = 0.0
    framework: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlTestEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_record_id: str = ""
    evidence_type: str = ""
    description: str = ""
    verified: bool = False
    created_at: float = Field(default_factory=time.time)


class ComplianceControlReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_evidence: int = 0
    overall_pass_rate_pct: float = 0.0
    failing_controls: int = 0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_control_type: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    critical_failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceControlTester:
    """Track and analyze compliance control test results."""

    def __init__(
        self,
        max_records: int = 200000,
        min_pass_rate_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_pass_rate_pct = min_pass_rate_pct
        self._records: list[ControlTestRecord] = []
        self._evidence: list[ControlTestEvidence] = []
        logger.info(
            "control_tester.initialized",
            max_records=max_records,
            min_pass_rate_pct=min_pass_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_test(
        self,
        control_id: str,
        result: ControlTestResult = ControlTestResult.PASS,
        control_type: ControlType = ControlType.PREVENTIVE,
        frequency: ControlTestFrequency = ControlTestFrequency.MONTHLY,
        pass_rate_pct: float = 0.0,
        framework: str = "",
        details: str = "",
    ) -> ControlTestRecord:
        record = ControlTestRecord(
            control_id=control_id,
            result=result,
            control_type=control_type,
            frequency=frequency,
            pass_rate_pct=pass_rate_pct,
            framework=framework,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "control_tester.recorded",
            record_id=record.id,
            control_id=control_id,
            result=result.value,
        )
        return record

    def get_test(self, record_id: str) -> ControlTestRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_tests(
        self,
        result: ControlTestResult | None = None,
        control_type: ControlType | None = None,
        framework: str | None = None,
        limit: int = 50,
    ) -> list[ControlTestRecord]:
        results = list(self._records)
        if result is not None:
            results = [r for r in results if r.result == result]
        if control_type is not None:
            results = [r for r in results if r.control_type == control_type]
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        return results[-limit:]

    def add_evidence(
        self,
        test_record_id: str,
        evidence_type: str = "",
        description: str = "",
        verified: bool = False,
    ) -> ControlTestEvidence:
        evidence = ControlTestEvidence(
            test_record_id=test_record_id,
            evidence_type=evidence_type,
            description=description,
            verified=verified,
        )
        self._evidence.append(evidence)
        if len(self._evidence) > self._max_records:
            self._evidence = self._evidence[-self._max_records :]
        logger.info(
            "control_tester.evidence_added",
            evidence_id=evidence.id,
            test_record_id=test_record_id,
            verified=verified,
        )
        return evidence

    # -- domain operations -----------------------------------------------

    def analyze_test_results(self) -> dict[str, Any]:
        """Group by control_type, compute pass count/total and avg pass_rate_pct."""
        groups: dict[str, list[ControlTestRecord]] = {}
        for r in self._records:
            groups.setdefault(r.control_type.value, []).append(r)
        result: dict[str, Any] = {}
        for ct, records in groups.items():
            passes = sum(1 for r in records if r.result == ControlTestResult.PASS)
            avg_rate = round(sum(r.pass_rate_pct for r in records) / len(records), 2)
            result[ct] = {
                "count": len(records),
                "pass_count": passes,
                "avg_pass_rate_pct": avg_rate,
            }
        return result

    def identify_failing_controls(self) -> list[dict[str, Any]]:
        """Find controls with pass_rate_pct below min_pass_rate_pct."""
        failing = [r for r in self._records if r.pass_rate_pct < self._min_pass_rate_pct]
        return [
            {
                "record_id": r.id,
                "control_id": r.control_id,
                "pass_rate_pct": r.pass_rate_pct,
                "result": r.result.value,
                "framework": r.framework,
            }
            for r in failing
        ]

    def rank_by_pass_rate(self) -> list[dict[str, Any]]:
        """Group by framework, compute avg pass_rate_pct, sort ascending (worst first)."""
        framework_rates: dict[str, list[float]] = {}
        for r in self._records:
            framework_rates.setdefault(r.framework, []).append(r.pass_rate_pct)
        results: list[dict[str, Any]] = []
        for fw, rates in framework_rates.items():
            results.append(
                {"framework": fw, "avg_pass_rate_pct": round(sum(rates) / len(rates), 2)}
            )
        results.sort(key=lambda x: x["avg_pass_rate_pct"])
        return results

    def detect_test_trends(self) -> dict[str, Any]:
        """Split records in half and compute delta in avg pass_rate_pct; threshold 5.0."""
        if len(self._records) < 2:
            return {"status": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        avg_first = sum(r.pass_rate_pct for r in first_half) / len(first_half)
        avg_second = sum(r.pass_rate_pct for r in second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        trend = "improving" if delta > 5.0 else ("worsening" if delta < -5.0 else "stable")
        return {
            "avg_rate_first_half": round(avg_first, 2),
            "avg_rate_second_half": round(avg_second, 2),
            "delta": delta,
            "trend": trend,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ComplianceControlReport:
        by_result: dict[str, int] = {}
        by_control_type: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
            by_control_type[r.control_type.value] = by_control_type.get(r.control_type.value, 0) + 1
            by_frequency[r.frequency.value] = by_frequency.get(r.frequency.value, 0) + 1
        overall_rate = (
            round(
                sum(r.pass_rate_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        failing_controls = sum(
            1 for r in self._records if r.pass_rate_pct < self._min_pass_rate_pct
        )
        critical_failures = [
            r.control_id
            for r in self._records
            if r.result == ControlTestResult.FAIL and r.pass_rate_pct < self._min_pass_rate_pct
        ][:5]
        recs: list[str] = []
        if failing_controls > 0:
            recs.append(
                f"{failing_controls} control(s) below minimum pass rate "
                f"of {self._min_pass_rate_pct}%"
            )
        error_count = sum(1 for r in self._records if r.result == ControlTestResult.ERROR)
        if error_count > 0:
            recs.append(f"{error_count} control test(s) resulted in errors")
        if not recs:
            recs.append("All compliance controls within acceptable pass rate thresholds")
        return ComplianceControlReport(
            total_records=len(self._records),
            total_evidence=len(self._evidence),
            overall_pass_rate_pct=overall_rate,
            failing_controls=failing_controls,
            by_result=by_result,
            by_control_type=by_control_type,
            by_frequency=by_frequency,
            critical_failures=critical_failures,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._evidence.clear()
        logger.info("control_tester.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            key = r.result.value
            result_dist[key] = result_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_evidence": len(self._evidence),
            "min_pass_rate_pct": self._min_pass_rate_pct,
            "result_distribution": result_dist,
            "unique_frameworks": len({r.framework for r in self._records}),
        }
