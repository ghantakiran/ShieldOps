"""Entity Behavior Risk Engine
score behavioral risk, detect baseline deviations,
compute behavior risk velocity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BehaviorCategory(StrEnum):
    ACCESS_PATTERN = "access_pattern"
    DATA_MOVEMENT = "data_movement"
    PRIVILEGE_USE = "privilege_use"
    NETWORK_ACTIVITY = "network_activity"


class BehaviorBaseline(StrEnum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    ANOMALOUS = "anomalous"
    MALICIOUS = "malicious"


class RiskContribution(StrEnum):
    DOMINANT = "dominant"
    SIGNIFICANT = "significant"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


# --- Models ---


class BehaviorRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    category: BehaviorCategory = BehaviorCategory.ACCESS_PATTERN
    baseline: BehaviorBaseline = BehaviorBaseline.NORMAL
    contribution: RiskContribution = RiskContribution.MINOR
    risk_score: float = 0.0
    baseline_score: float = 0.0
    deviation: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BehaviorRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    category: BehaviorCategory = BehaviorCategory.ACCESS_PATTERN
    behavioral_score: float = 0.0
    deviation_pct: float = 0.0
    velocity: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BehaviorRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_baseline: dict[str, int] = Field(default_factory=dict)
    by_contribution: dict[str, int] = Field(default_factory=dict)
    anomalous_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EntityBehaviorRiskEngine:
    """Score behavioral risk, detect deviations,
    compute risk velocity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BehaviorRiskRecord] = []
        self._analyses: dict[str, BehaviorRiskAnalysis] = {}
        logger.info(
            "entity_behavior_risk_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        entity_id: str = "",
        category: BehaviorCategory = (BehaviorCategory.ACCESS_PATTERN),
        baseline: BehaviorBaseline = (BehaviorBaseline.NORMAL),
        contribution: RiskContribution = (RiskContribution.MINOR),
        risk_score: float = 0.0,
        baseline_score: float = 0.0,
        deviation: float = 0.0,
        description: str = "",
    ) -> BehaviorRiskRecord:
        record = BehaviorRiskRecord(
            entity_id=entity_id,
            category=category,
            baseline=baseline,
            contribution=contribution,
            risk_score=risk_score,
            baseline_score=baseline_score,
            deviation=deviation,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "entity_behavior_risk.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> BehaviorRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dev_pct = (
            round(
                rec.deviation / rec.baseline_score * 100,
                2,
            )
            if rec.baseline_score > 0
            else 0.0
        )
        entity_recs = [r for r in self._records if r.entity_id == rec.entity_id]
        velocity = (
            round(
                sum(r.deviation for r in entity_recs) / len(entity_recs),
                2,
            )
            if entity_recs
            else 0.0
        )
        analysis = BehaviorRiskAnalysis(
            entity_id=rec.entity_id,
            category=rec.category,
            behavioral_score=round(rec.risk_score, 2),
            deviation_pct=dev_pct,
            velocity=velocity,
            description=(f"Entity {rec.entity_id} deviation={dev_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BehaviorRiskReport:
        by_c: dict[str, int] = {}
        by_b: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.category.value
            by_c[k] = by_c.get(k, 0) + 1
            k2 = r.baseline.value
            by_b[k2] = by_b.get(k2, 0) + 1
            k3 = r.contribution.value
            by_ct[k3] = by_ct.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        anomalous = sorted(
            {
                r.entity_id
                for r in self._records
                if r.baseline
                in (
                    BehaviorBaseline.ANOMALOUS,
                    BehaviorBaseline.MALICIOUS,
                )
            }
        )[:10]
        recs: list[str] = []
        if anomalous:
            recs.append(f"{len(anomalous)} anomalous entities detected")
        if not recs:
            recs.append("Behavior baselines normal")
        return BehaviorRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_category=by_c,
            by_baseline=by_b,
            by_contribution=by_ct,
            anomalous_entities=anomalous,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "category_distribution": cat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("entity_behavior_risk_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def score_behavioral_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Score behavioral risk per entity."""
        entity_data: dict[str, list[float]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for eid, scores in entity_data.items():
            total = round(sum(scores), 2)
            avg = round(total / len(scores), 2)
            results.append(
                {
                    "entity_id": eid,
                    "total_risk": total,
                    "avg_risk": avg,
                    "event_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["total_risk"],
            reverse=True,
        )
        return results

    def detect_baseline_deviation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect entities deviating from baseline."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.deviation > 0 and r.baseline_score > 0:
                dev_pct = round(
                    r.deviation / r.baseline_score * 100,
                    2,
                )
                if dev_pct > 10.0:
                    results.append(
                        {
                            "entity_id": (r.entity_id),
                            "category": (r.category.value),
                            "deviation_pct": dev_pct,
                            "baseline": (r.baseline.value),
                        }
                    )
        results.sort(
            key=lambda x: x["deviation_pct"],
            reverse=True,
        )
        return results

    def compute_behavior_risk_velocity(
        self,
    ) -> list[dict[str, Any]]:
        """Compute risk velocity per entity."""
        entity_devs: dict[str, list[float]] = {}
        for r in self._records:
            entity_devs.setdefault(r.entity_id, []).append(r.deviation)
        results: list[dict[str, Any]] = []
        for eid, devs in entity_devs.items():
            velocity = round(sum(devs) / len(devs), 2)
            results.append(
                {
                    "entity_id": eid,
                    "velocity": velocity,
                    "sample_count": len(devs),
                    "is_accelerating": velocity > 5.0,
                }
            )
        results.sort(
            key=lambda x: x["velocity"],
            reverse=True,
        )
        return results
