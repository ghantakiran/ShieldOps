"""Behavioral Baseline Deviation Engine —
detect deviations from behavioral baselines,
classify deviation patterns, rank deviations by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeviationType(StrEnum):
    ACCESS_PATTERN = "access_pattern"
    DATA_VOLUME = "data_volume"
    TIME_ANOMALY = "time_anomaly"
    GEO_ANOMALY = "geo_anomaly"


class BaselineMethod(StrEnum):
    STATISTICAL = "statistical"
    ML_MODEL = "ml_model"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


class DeviationSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class BaselineDeviationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    deviation_type: DeviationType = DeviationType.ACCESS_PATTERN
    baseline_method: BaselineMethod = BaselineMethod.STATISTICAL
    severity: DeviationSeverity = DeviationSeverity.LOW
    deviation_score: float = 0.0
    baseline_value: float = 0.0
    observed_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineDeviationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    deviation_type: DeviationType = DeviationType.ACCESS_PATTERN
    risk_score: float = 0.0
    anomaly_confirmed: bool = False
    deviation_magnitude: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineDeviationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_deviation_score: float = 0.0
    by_deviation_type: dict[str, int] = Field(default_factory=dict)
    by_baseline_method: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_risk_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class BehavioralBaselineDeviationEngine:
    """Detect deviations from behavioral baselines,
    classify deviation patterns, rank deviations by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BaselineDeviationRecord] = []
        self._analyses: dict[str, BaselineDeviationAnalysis] = {}
        logger.info(
            "behavioral_baseline_deviation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        entity_id: str = "",
        deviation_type: DeviationType = DeviationType.ACCESS_PATTERN,
        baseline_method: BaselineMethod = BaselineMethod.STATISTICAL,
        severity: DeviationSeverity = DeviationSeverity.LOW,
        deviation_score: float = 0.0,
        baseline_value: float = 0.0,
        observed_value: float = 0.0,
        description: str = "",
    ) -> BaselineDeviationRecord:
        record = BaselineDeviationRecord(
            entity_id=entity_id,
            deviation_type=deviation_type,
            baseline_method=baseline_method,
            severity=severity,
            deviation_score=deviation_score,
            baseline_value=baseline_value,
            observed_value=observed_value,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "behavioral_baseline_deviation.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> BaselineDeviationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risk_score = round(
            sev_weights.get(rec.severity.value, 1) * rec.deviation_score,
            2,
        )
        magnitude = (
            round(abs(rec.observed_value - rec.baseline_value) / rec.baseline_value, 4)
            if rec.baseline_value != 0
            else 0.0
        )
        analysis = BaselineDeviationAnalysis(
            entity_id=rec.entity_id,
            deviation_type=rec.deviation_type,
            risk_score=risk_score,
            anomaly_confirmed=rec.severity in (DeviationSeverity.CRITICAL, DeviationSeverity.HIGH),
            deviation_magnitude=magnitude,
            description=(f"Entity {rec.entity_id} deviation score {rec.deviation_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BaselineDeviationReport:
        by_dt: dict[str, int] = {}
        by_bm: dict[str, int] = {}
        by_sv: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.deviation_type.value
            by_dt[k] = by_dt.get(k, 0) + 1
            k2 = r.baseline_method.value
            by_bm[k2] = by_bm.get(k2, 0) + 1
            k3 = r.severity.value
            by_sv[k3] = by_sv.get(k3, 0) + 1
            scores.append(r.deviation_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk = list(
            {
                r.entity_id
                for r in self._records
                if r.severity in (DeviationSeverity.CRITICAL, DeviationSeverity.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} entities with critical/high deviations")
        if not recs:
            recs.append("Behavioral baselines within normal ranges")
        return BaselineDeviationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_deviation_score=avg,
            by_deviation_type=by_dt,
            by_baseline_method=by_bm,
            by_severity=by_sv,
            high_risk_entities=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.deviation_type.value
            dt_dist[k] = dt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "deviation_type_distribution": dt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("behavioral_baseline_deviation_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_baseline_deviations(self) -> list[dict[str, Any]]:
        """Detect entities with significant baseline deviations."""
        entity_data: dict[str, list[BaselineDeviationRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, recs in entity_data.items():
            max_score = max(rec.deviation_score for rec in recs)
            worst_type = max(recs, key=lambda x: x.deviation_score).deviation_type.value
            results.append(
                {
                    "entity_id": eid,
                    "max_deviation_score": round(max_score, 2),
                    "worst_deviation_type": worst_type,
                    "deviation_count": len(recs),
                    "anomaly_confirmed": max_score > 0.7,
                }
            )
        results.sort(key=lambda x: x["max_deviation_score"], reverse=True)
        return results

    def classify_deviation_patterns(self) -> list[dict[str, Any]]:
        """Classify deviation patterns by type and method."""
        pattern_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            pat_key = f"{r.deviation_type.value}:{r.baseline_method.value}"
            if pat_key not in pattern_map:
                pattern_map[pat_key] = {
                    "deviation_type": r.deviation_type.value,
                    "baseline_method": r.baseline_method.value,
                    "count": 0,
                    "total_score": 0.0,
                    "severities": {},
                }
            entry = pattern_map[pat_key]
            entry["count"] += 1
            entry["total_score"] += r.deviation_score
            sv = r.severity.value
            entry["severities"][sv] = entry["severities"].get(sv, 0) + 1
        results: list[dict[str, Any]] = []
        for pat_key, data in pattern_map.items():
            cnt = data["count"]
            results.append(
                {
                    "pattern_key": pat_key,
                    "deviation_type": data["deviation_type"],
                    "baseline_method": data["baseline_method"],
                    "count": cnt,
                    "avg_score": round(data["total_score"] / cnt, 2),
                    "severity_breakdown": data["severities"],
                }
            )
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    def rank_deviations_by_risk(self) -> list[dict[str, Any]]:
        """Rank all deviation records by composite risk score."""
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = sev_weights.get(r.severity.value, 1)
            composite = round(w * r.deviation_score, 2)
            results.append(
                {
                    "record_id": r.id,
                    "entity_id": r.entity_id,
                    "deviation_type": r.deviation_type.value,
                    "severity": r.severity.value,
                    "deviation_score": r.deviation_score,
                    "composite_risk": composite,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
