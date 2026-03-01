"""Deploy Gate Tracker — track deployment gate pass/fail rates and gate effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GateType(StrEnum):
    SECURITY_SCAN = "security_scan"
    TEST_COVERAGE = "test_coverage"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    APPROVAL = "approval"


class GateResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BYPASSED = "bypassed"
    PENDING = "pending"
    EXPIRED = "expired"


class GateImpact(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFORMATIONAL = "informational"
    ADVISORY = "advisory"
    NONE = "none"


# --- Models ---


class GateRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    gate_type: GateType = GateType.SECURITY_SCAN
    gate_result: GateResult = GateResult.PENDING
    gate_impact: GateImpact = GateImpact.BLOCKING
    failure_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GateMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    gate_type: GateType = GateType.SECURITY_SCAN
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployGateReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    failed_gates: int = 0
    avg_failure_rate: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    top_failing: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployGateTracker:
    """Track deployment gate pass/fail rates and gate effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        max_gate_failure_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_gate_failure_pct = max_gate_failure_pct
        self._records: list[GateRecord] = []
        self._metrics: list[GateMetric] = []
        logger.info(
            "deploy_gate.initialized",
            max_records=max_records,
            max_gate_failure_pct=max_gate_failure_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_gate(
        self,
        deployment_id: str,
        gate_type: GateType = GateType.SECURITY_SCAN,
        gate_result: GateResult = GateResult.PENDING,
        gate_impact: GateImpact = GateImpact.BLOCKING,
        failure_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GateRecord:
        record = GateRecord(
            deployment_id=deployment_id,
            gate_type=gate_type,
            gate_result=gate_result,
            gate_impact=gate_impact,
            failure_rate=failure_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_gate.gate_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            gate_type=gate_type.value,
            gate_result=gate_result.value,
        )
        return record

    def get_gate(self, record_id: str) -> GateRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gates(
        self,
        gate_type: GateType | None = None,
        result: GateResult | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GateRecord]:
        results = list(self._records)
        if gate_type is not None:
            results = [r for r in results if r.gate_type == gate_type]
        if result is not None:
            results = [r for r in results if r.gate_result == result]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        deployment_id: str,
        gate_type: GateType = GateType.SECURITY_SCAN,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GateMetric:
        metric = GateMetric(
            deployment_id=deployment_id,
            gate_type=gate_type,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "deploy_gate.metric_added",
            deployment_id=deployment_id,
            gate_type=gate_type.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_gate_distribution(self) -> dict[str, Any]:
        """Group by gate_type; return count and avg failure_rate."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gate_type.value
            type_data.setdefault(key, []).append(r.failure_rate)
        result: dict[str, Any] = {}
        for gtype, rates in type_data.items():
            result[gtype] = {
                "count": len(rates),
                "avg_failure_rate": round(sum(rates) / len(rates), 2),
            }
        return result

    def identify_failed_gates(self) -> list[dict[str, Any]]:
        """Return records where gate_result == FAILED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gate_result == GateResult.FAILED:
                results.append(
                    {
                        "record_id": r.id,
                        "deployment_id": r.deployment_id,
                        "gate_type": r.gate_type.value,
                        "failure_rate": r.failure_rate,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_failure_rate(self) -> list[dict[str, Any]]:
        """Group by service, avg failure_rate, sort descending."""
        svc_rates: dict[str, list[float]] = {}
        for r in self._records:
            svc_rates.setdefault(r.service, []).append(r.failure_rate)
        results: list[dict[str, Any]] = []
        for svc, rates in svc_rates.items():
            results.append(
                {
                    "service": svc,
                    "avg_failure_rate": round(sum(rates) / len(rates), 2),
                }
            )
        results.sort(key=lambda x: x["avg_failure_rate"], reverse=True)
        return results

    def detect_gate_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DeployGateReport:
        by_type: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_type[r.gate_type.value] = by_type.get(r.gate_type.value, 0) + 1
            by_result[r.gate_result.value] = by_result.get(r.gate_result.value, 0) + 1
            by_impact[r.gate_impact.value] = by_impact.get(r.gate_impact.value, 0) + 1
        failed_gates = sum(1 for r in self._records if r.gate_result == GateResult.FAILED)
        rates = [r.failure_rate for r in self._records]
        avg_failure_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
        rankings = self.rank_by_failure_rate()
        top_failing = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if failed_gates > 0:
            recs.append(
                f"{failed_gates} gate(s) failed"
                f" (max acceptable failure {self._max_gate_failure_pct}%)"
            )
        bypassed = sum(1 for r in self._records if r.gate_result == GateResult.BYPASSED)
        if bypassed > 0:
            recs.append(f"{bypassed} gate(s) bypassed — review bypass policies")
        if not recs:
            recs.append("Deployment gate health is acceptable")
        return DeployGateReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            failed_gates=failed_gates,
            avg_failure_rate=avg_failure_rate,
            by_type=by_type,
            by_result=by_result,
            by_impact=by_impact,
            top_failing=top_failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("deploy_gate.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gate_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_gate_failure_pct": self._max_gate_failure_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
