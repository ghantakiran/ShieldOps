"""Entity Risk Scoring Engine
score entities by cumulative risk, detect threshold
breaches, rank entities by risk exposure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EntityType(StrEnum):
    USER = "user"
    HOST = "host"
    SERVICE = "service"
    IP_ADDRESS = "ip_address"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScoringModel(StrEnum):
    CUMULATIVE = "cumulative"
    DECAY = "decay"
    WEIGHTED = "weighted"
    BAYESIAN = "bayesian"


# --- Models ---


class EntityRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.USER
    risk_level: RiskLevel = RiskLevel.LOW
    scoring_model: ScoringModel = ScoringModel.CUMULATIVE
    risk_score: float = 0.0
    threshold: float = 80.0
    source: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EntityRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    entity_type: EntityType = EntityType.USER
    computed_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    threshold_breached: bool = False
    contributing_factors: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EntityRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_scoring_model: dict[str, int] = Field(default_factory=dict)
    high_risk_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EntityRiskScoringEngine:
    """Score entities by cumulative risk, detect
    threshold breaches, rank by risk exposure."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EntityRiskRecord] = []
        self._analyses: dict[str, EntityRiskAnalysis] = {}
        logger.info(
            "entity_risk_scoring_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        entity_id: str = "",
        entity_type: EntityType = EntityType.USER,
        risk_level: RiskLevel = RiskLevel.LOW,
        scoring_model: ScoringModel = (ScoringModel.CUMULATIVE),
        risk_score: float = 0.0,
        threshold: float = 80.0,
        source: str = "",
        description: str = "",
    ) -> EntityRiskRecord:
        record = EntityRiskRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            risk_level=risk_level,
            scoring_model=scoring_model,
            risk_score=risk_score,
            threshold=threshold,
            source=source,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "entity_risk_scoring.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> EntityRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        factors = sum(1 for r in self._records if r.entity_id == rec.entity_id)
        breached = rec.risk_score >= rec.threshold
        analysis = EntityRiskAnalysis(
            entity_id=rec.entity_id,
            entity_type=rec.entity_type,
            computed_score=round(rec.risk_score, 2),
            risk_level=rec.risk_level,
            threshold_breached=breached,
            contributing_factors=factors,
            description=(f"Entity {rec.entity_id} score {rec.risk_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EntityRiskReport:
        by_et: dict[str, int] = {}
        by_rl: dict[str, int] = {}
        by_sm: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.entity_type.value
            by_et[k] = by_et.get(k, 0) + 1
            k2 = r.risk_level.value
            by_rl[k2] = by_rl.get(k2, 0) + 1
            k3 = r.scoring_model.value
            by_sm[k3] = by_sm.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list(
            {
                r.entity_id
                for r in self._records
                if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk entities detected")
        if not recs:
            recs.append("No significant risk detected")
        return EntityRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_entity_type=by_et,
            by_risk_level=by_rl,
            by_scoring_model=by_sm,
            high_risk_entities=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        et_dist: dict[str, int] = {}
        for r in self._records:
            k = r.entity_type.value
            et_dist[k] = et_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "entity_type_distribution": et_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("entity_risk_scoring_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_entity_risk_score(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate risk score per entity."""
        entity_scores: dict[str, list[float]] = {}
        entity_types: dict[str, str] = {}
        for r in self._records:
            entity_scores.setdefault(r.entity_id, []).append(r.risk_score)
            entity_types[r.entity_id] = r.entity_type.value
        results: list[dict[str, Any]] = []
        for eid, scores in entity_scores.items():
            total = round(sum(scores), 2)
            avg = round(total / len(scores), 2)
            results.append(
                {
                    "entity_id": eid,
                    "entity_type": entity_types[eid],
                    "total_score": total,
                    "avg_score": avg,
                    "event_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["total_score"],
            reverse=True,
        )
        return results

    def detect_risk_threshold_breach(
        self,
    ) -> list[dict[str, Any]]:
        """Detect entities that breached threshold."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.risk_score >= r.threshold and r.entity_id not in seen:
                seen.add(r.entity_id)
                results.append(
                    {
                        "entity_id": r.entity_id,
                        "entity_type": (r.entity_type.value),
                        "risk_score": r.risk_score,
                        "threshold": r.threshold,
                        "breach_amount": round(
                            r.risk_score - r.threshold,
                            2,
                        ),
                    }
                )
        results.sort(
            key=lambda x: x["breach_amount"],
            reverse=True,
        )
        return results

    def rank_entities_by_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all entities by aggregate risk."""
        entity_data: dict[str, float] = {}
        entity_types: dict[str, str] = {}
        for r in self._records:
            entity_data[r.entity_id] = entity_data.get(r.entity_id, 0.0) + r.risk_score
            entity_types[r.entity_id] = r.entity_type.value
        results: list[dict[str, Any]] = []
        for eid, total in entity_data.items():
            results.append(
                {
                    "entity_id": eid,
                    "entity_type": entity_types[eid],
                    "aggregate_risk": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["aggregate_risk"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
