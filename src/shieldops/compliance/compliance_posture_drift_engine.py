"""Compliance Posture Drift Engine
compute posture drift score, detect drift acceleration,
rank domains by drift severity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftDirection(StrEnum):
    DEGRADING = "degrading"
    STABLE = "stable"
    IMPROVING = "improving"
    UNKNOWN = "unknown"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PostureDomain(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    LOGGING = "logging"


# --- Models ---


class PostureDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = ""
    drift_direction: DriftDirection = DriftDirection.STABLE
    drift_severity: DriftSeverity = DriftSeverity.LOW
    posture_domain: PostureDomain = PostureDomain.ACCESS_CONTROL
    drift_score: float = 0.0
    baseline_score: float = 100.0
    current_score: float = 100.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureDriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = ""
    drift_direction: DriftDirection = DriftDirection.STABLE
    computed_drift: float = 0.0
    is_accelerating: bool = False
    severity_level: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_drift_score: float = 0.0
    by_drift_direction: dict[str, int] = Field(default_factory=dict)
    by_drift_severity: dict[str, int] = Field(default_factory=dict)
    by_posture_domain: dict[str, int] = Field(default_factory=dict)
    critical_domains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CompliancePostureDriftEngine:
    """Compute posture drift score, detect drift
    acceleration, rank domains by drift severity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PostureDriftRecord] = []
        self._analyses: dict[str, PostureDriftAnalysis] = {}
        logger.info(
            "compliance_posture_drift_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        domain_id: str = "",
        drift_direction: DriftDirection = DriftDirection.STABLE,
        drift_severity: DriftSeverity = DriftSeverity.LOW,
        posture_domain: PostureDomain = PostureDomain.ACCESS_CONTROL,
        drift_score: float = 0.0,
        baseline_score: float = 100.0,
        current_score: float = 100.0,
        description: str = "",
    ) -> PostureDriftRecord:
        record = PostureDriftRecord(
            domain_id=domain_id,
            drift_direction=drift_direction,
            drift_severity=drift_severity,
            posture_domain=posture_domain,
            drift_score=drift_score,
            baseline_score=baseline_score,
            current_score=current_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_posture_drift.record_added",
            record_id=record.id,
            domain_id=domain_id,
        )
        return record

    def process(self, key: str) -> PostureDriftAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        drift_vals = [r.drift_score for r in self._records if r.domain_id == rec.domain_id]
        is_accelerating = len(drift_vals) >= 2 and drift_vals[-1] > drift_vals[-2]
        analysis = PostureDriftAnalysis(
            domain_id=rec.domain_id,
            drift_direction=rec.drift_direction,
            computed_drift=round(rec.drift_score, 2),
            is_accelerating=is_accelerating,
            severity_level=rec.drift_severity.value,
            description=f"Domain {rec.domain_id} drift {rec.drift_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PostureDriftReport:
        by_dd: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_pd: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.drift_direction.value
            by_dd[k] = by_dd.get(k, 0) + 1
            k2 = r.drift_severity.value
            by_ds[k2] = by_ds.get(k2, 0) + 1
            k3 = r.posture_domain.value
            by_pd[k3] = by_pd.get(k3, 0) + 1
            scores.append(r.drift_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = list(
            {
                r.domain_id
                for r in self._records
                if r.drift_severity in (DriftSeverity.CRITICAL, DriftSeverity.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical drift domains detected")
        if not recs:
            recs.append("Compliance posture is stable")
        return PostureDriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_drift_score=avg,
            by_drift_direction=by_dd,
            by_drift_severity=by_ds,
            by_posture_domain=by_pd,
            critical_domains=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dd_dist: dict[str, int] = {}
        for r in self._records:
            k = r.drift_direction.value
            dd_dist[k] = dd_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_direction_distribution": dd_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("compliance_posture_drift_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_posture_drift_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute drift score per domain."""
        domain_scores: dict[str, list[float]] = {}
        domain_types: dict[str, str] = {}
        for r in self._records:
            domain_scores.setdefault(r.domain_id, []).append(r.drift_score)
            domain_types[r.domain_id] = r.posture_domain.value
        results: list[dict[str, Any]] = []
        for did, scores in domain_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "domain_id": did,
                    "posture_domain": domain_types[did],
                    "avg_drift_score": avg,
                    "measurement_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_drift_score"], reverse=True)
        return results

    def detect_drift_acceleration(
        self,
    ) -> list[dict[str, Any]]:
        """Detect domains where drift is accelerating."""
        domain_series: dict[str, list[float]] = {}
        for r in self._records:
            domain_series.setdefault(r.domain_id, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for did, series in domain_series.items():
            if len(series) >= 2 and series[-1] > series[-2]:
                results.append(
                    {
                        "domain_id": did,
                        "current_drift": series[-1],
                        "previous_drift": series[-2],
                        "acceleration": round(series[-1] - series[-2], 2),
                    }
                )
        results.sort(key=lambda x: x["acceleration"], reverse=True)
        return results

    def rank_domains_by_drift_severity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank domains by drift severity."""
        domain_drift: dict[str, float] = {}
        domain_types: dict[str, str] = {}
        for r in self._records:
            domain_drift[r.domain_id] = domain_drift.get(r.domain_id, 0.0) + r.drift_score
            domain_types[r.domain_id] = r.posture_domain.value
        results: list[dict[str, Any]] = []
        for did, total in domain_drift.items():
            results.append(
                {
                    "domain_id": did,
                    "posture_domain": domain_types[did],
                    "aggregate_drift": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["aggregate_drift"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
