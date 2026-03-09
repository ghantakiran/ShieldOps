"""Golden Signal Optimizer

Latency/traffic/errors/saturation optimization, SLI alignment, threshold
tuning, and coverage scoring for the four golden signals of monitoring.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GoldenSignal(StrEnum):
    LATENCY = "latency"
    TRAFFIC = "traffic"
    ERRORS = "errors"
    SATURATION = "saturation"


class SignalHealth(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNMEASURED = "unmeasured"


class ThresholdAction(StrEnum):
    TIGHTEN = "tighten"
    LOOSEN = "loosen"
    MAINTAIN = "maintain"
    CREATE = "create"
    REVIEW = "review"


# --- Models ---


class GoldenSignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    signal: GoldenSignal = GoldenSignal.LATENCY
    signal_health: SignalHealth = SignalHealth.UNMEASURED
    current_value: float = 0.0
    threshold_value: float = 0.0
    sli_target: float = 0.0
    sli_actual: float = 0.0
    coverage_pct: float = 0.0
    has_alert: bool = False
    has_dashboard: bool = False
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThresholdRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    signal: GoldenSignal = GoldenSignal.LATENCY
    action: ThresholdAction = ThresholdAction.MAINTAIN
    current_threshold: float = 0.0
    recommended_threshold: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class GoldenSignalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_recommendations: int = 0
    overall_coverage_pct: float = 0.0
    avg_sli_gap: float = 0.0
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_signal_health: dict[str, int] = Field(default_factory=dict)
    signal_coverage: dict[str, float] = Field(default_factory=dict)
    undermonitored_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class GoldenSignalOptimizer:
    """Golden Signal Optimizer

    Latency/traffic/errors/saturation optimization, SLI alignment,
    threshold tuning, and coverage scoring.
    """

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
        sli_gap_threshold: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._sli_gap_threshold = sli_gap_threshold
        self._records: list[GoldenSignalRecord] = []
        self._recommendations: list[ThresholdRecommendation] = []
        logger.info(
            "golden_signal_optimizer.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    def add_record(
        self,
        service: str,
        signal: GoldenSignal,
        current_value: float = 0.0,
        threshold_value: float = 0.0,
        sli_target: float = 0.0,
        sli_actual: float = 0.0,
        coverage_pct: float = 0.0,
        has_alert: bool = False,
        has_dashboard: bool = False,
        team: str = "",
    ) -> GoldenSignalRecord:
        if coverage_pct == 0 and not has_alert and not has_dashboard:
            health = SignalHealth.UNMEASURED
        elif threshold_value > 0 and current_value > threshold_value * 1.5:
            health = SignalHealth.CRITICAL
        elif threshold_value > 0 and current_value > threshold_value:
            health = SignalHealth.DEGRADED
        elif sli_target > 0 and sli_actual >= sli_target:
            health = SignalHealth.OPTIMAL
        else:
            health = SignalHealth.ACCEPTABLE
        record = GoldenSignalRecord(
            service=service,
            signal=signal,
            signal_health=health,
            current_value=current_value,
            threshold_value=threshold_value,
            sli_target=sli_target,
            sli_actual=sli_actual,
            coverage_pct=coverage_pct,
            has_alert=has_alert,
            has_dashboard=has_dashboard,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "golden_signal_optimizer.record_added",
            record_id=record.id,
            service=service,
            signal=signal.value,
            health=health.value,
        )
        return record

    def get_record(self, record_id: str) -> GoldenSignalRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        signal: GoldenSignal | None = None,
        signal_health: SignalHealth | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[GoldenSignalRecord]:
        results = list(self._records)
        if signal is not None:
            results = [r for r in results if r.signal == signal]
        if signal_health is not None:
            results = [r for r in results if r.signal_health == signal_health]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def compute_coverage(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {"service": service or "all", "status": "no_data"}
        signal_coverage: dict[str, float] = {}
        for sig in GoldenSignal:
            sig_records = [r for r in matching if r.signal == sig]
            if sig_records:
                avg_cov = sum(r.coverage_pct for r in sig_records) / len(sig_records)
                signal_coverage[sig.value] = round(avg_cov, 2)
            else:
                signal_coverage[sig.value] = 0.0
        overall = round(sum(signal_coverage.values()) / len(signal_coverage), 2)
        gaps = [s for s, c in signal_coverage.items() if c < self._min_coverage_pct]
        return {
            "service": service or "all",
            "overall_coverage_pct": overall,
            "signal_coverage": signal_coverage,
            "coverage_gaps": gaps,
            "meets_minimum": overall >= self._min_coverage_pct,
        }

    def recommend_thresholds(self, service: str) -> list[ThresholdRecommendation]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return []
        recs: list[ThresholdRecommendation] = []
        for sig in GoldenSignal:
            sig_records = [r for r in matching if r.signal == sig]
            if not sig_records:
                rec = ThresholdRecommendation(
                    service=service,
                    signal=sig,
                    action=ThresholdAction.CREATE,
                    confidence=0.5,
                    reason=f"No {sig.value} monitoring configured",
                )
                recs.append(rec)
                continue
            values = [r.current_value for r in sig_records]
            avg_val = sum(values) / len(values)
            max_val = max(values)
            current_thresh = sig_records[-1].threshold_value
            if current_thresh == 0:
                action = ThresholdAction.CREATE
                recommended = round(avg_val * 1.5, 2)
                reason = "No threshold set — recommend baseline + 50% buffer"
            elif max_val < current_thresh * 0.5:
                action = ThresholdAction.TIGHTEN
                recommended = round(max_val * 1.3, 2)
                reason = "Threshold too loose — values consistently below 50%"
            elif sum(1 for v in values if v > current_thresh) / len(values) > 0.2:
                action = ThresholdAction.LOOSEN
                recommended = round(max_val * 1.2, 2)
                reason = "Too many breaches (>20%) — threshold too tight"
            else:
                action = ThresholdAction.MAINTAIN
                recommended = current_thresh
                reason = "Threshold is well-calibrated"
            confidence = min(1.0, len(sig_records) / 20.0)
            rec = ThresholdRecommendation(
                service=service,
                signal=sig,
                action=action,
                current_threshold=current_thresh,
                recommended_threshold=recommended,
                confidence=round(confidence, 2),
                reason=reason,
            )
            recs.append(rec)
        self._recommendations.extend(recs)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        return recs

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        coverage = self.compute_coverage(service)
        sli_gaps = [abs(r.sli_target - r.sli_actual) for r in matching if r.sli_target > 0]
        avg_sli_gap = round(sum(sli_gaps) / len(sli_gaps), 4) if sli_gaps else 0.0
        health_counts: dict[str, int] = {}
        for r in matching:
            health_counts[r.signal_health.value] = health_counts.get(r.signal_health.value, 0) + 1
        return {
            "service": service,
            "signal_count": len(matching),
            "overall_coverage": coverage.get("overall_coverage_pct", 0.0),
            "avg_sli_gap": avg_sli_gap,
            "health_distribution": health_counts,
            "coverage_gaps": coverage.get("coverage_gaps", []),
        }

    def generate_report(self) -> GoldenSignalReport:
        by_sig: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_sig[r.signal.value] = by_sig.get(r.signal.value, 0) + 1
            by_health[r.signal_health.value] = by_health.get(r.signal_health.value, 0) + 1
        covs = [r.coverage_pct for r in self._records]
        overall_cov = round(sum(covs) / max(1, len(covs)), 2)
        sli_gaps = [abs(r.sli_target - r.sli_actual) for r in self._records if r.sli_target > 0]
        avg_gap = round(sum(sli_gaps) / max(1, len(sli_gaps)), 4)
        sig_cov: dict[str, float] = {}
        for sig in GoldenSignal:
            sig_recs = [r for r in self._records if r.signal == sig]
            if sig_recs:
                sig_cov[sig.value] = round(sum(r.coverage_pct for r in sig_recs) / len(sig_recs), 2)
        svc_services: dict[str, bool] = {}
        for r in self._records:
            svc_services[r.service] = True
        svc_cov: dict[str, float] = {}
        for svc in svc_services:
            svc_records = [r for r in self._records if r.service == svc]
            covered_signals = len({r.signal for r in svc_records if r.coverage_pct > 0})
            svc_cov[svc] = covered_signals / 4.0 * 100
        undermon = [s for s, c in svc_cov.items() if c < self._min_coverage_pct]
        recs: list[str] = []
        unmeasured = by_health.get("unmeasured", 0)
        if unmeasured > 0:
            recs.append(f"{unmeasured} signal(s) unmeasured — add instrumentation")
        if avg_gap > self._sli_gap_threshold:
            recs.append(f"Average SLI gap {avg_gap:.2f} exceeds threshold — tune targets")
        if undermon:
            recs.append(f"{len(undermon)} service(s) below {self._min_coverage_pct}% coverage")
        critical = by_health.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical signal(s) — immediate action required")
        if not recs:
            recs.append("Golden signals are well-optimized across all services")
        return GoldenSignalReport(
            total_records=len(self._records),
            total_recommendations=len(self._recommendations),
            overall_coverage_pct=overall_cov,
            avg_sli_gap=avg_gap,
            by_signal=by_sig,
            by_signal_health=by_health,
            signal_coverage=sig_cov,
            undermonitored_services=undermon[:10],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sig_dist: dict[str, int] = {}
        for r in self._records:
            sig_dist[r.signal.value] = sig_dist.get(r.signal.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_recommendations": len(self._recommendations),
            "min_coverage_pct": self._min_coverage_pct,
            "sli_gap_threshold": self._sli_gap_threshold,
            "signal_distribution": sig_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("golden_signal_optimizer.cleared")
        return {"status": "cleared"}
