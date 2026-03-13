"""Risk Observation Engine
consolidate risk observations, compute observation
density, detect observation patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ObservationType(StrEnum):
    NOTABLE_EVENT = "notable_event"
    ANOMALY = "anomaly"
    POLICY_VIOLATION = "policy_violation"
    THRESHOLD_BREACH = "threshold_breach"


class ObservationFidelity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    RAW = "raw"


class ConsolidationStrategy(StrEnum):
    TIME_WINDOW = "time_window"
    ENTITY = "entity"
    TECHNIQUE = "technique"
    CAMPAIGN = "campaign"


# --- Models ---


class RiskObservationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observation_id: str = ""
    obs_type: ObservationType = ObservationType.NOTABLE_EVENT
    fidelity: ObservationFidelity = ObservationFidelity.MEDIUM
    strategy: ConsolidationStrategy = ConsolidationStrategy.ENTITY
    entity_id: str = ""
    risk_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskObservationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observation_id: str = ""
    obs_type: ObservationType = ObservationType.NOTABLE_EVENT
    density_score: float = 0.0
    pattern_detected: bool = False
    consolidated_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskObservationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_fidelity: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    high_density_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskObservationEngine:
    """Consolidate observations, compute density,
    detect observation patterns."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskObservationRecord] = []
        self._analyses: dict[str, RiskObservationAnalysis] = {}
        logger.info(
            "risk_observation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        observation_id: str = "",
        obs_type: ObservationType = (ObservationType.NOTABLE_EVENT),
        fidelity: ObservationFidelity = (ObservationFidelity.MEDIUM),
        strategy: ConsolidationStrategy = (ConsolidationStrategy.ENTITY),
        entity_id: str = "",
        risk_score: float = 0.0,
        description: str = "",
    ) -> RiskObservationRecord:
        record = RiskObservationRecord(
            observation_id=observation_id,
            obs_type=obs_type,
            fidelity=fidelity,
            strategy=strategy,
            entity_id=entity_id,
            risk_score=risk_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_observation.record_added",
            record_id=record.id,
            observation_id=observation_id,
        )
        return record

    def process(self, key: str) -> RiskObservationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        entity_obs = [r for r in self._records if r.entity_id == rec.entity_id]
        density = round(len(entity_obs) * 1.0, 2)
        pattern = len(entity_obs) >= 3
        analysis = RiskObservationAnalysis(
            observation_id=rec.observation_id,
            obs_type=rec.obs_type,
            density_score=density,
            pattern_detected=pattern,
            consolidated_count=len(entity_obs),
            description=(f"Observation {rec.observation_id} density={density}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RiskObservationReport:
        by_t: dict[str, int] = {}
        by_f: dict[str, int] = {}
        by_s: dict[str, int] = {}
        scores: list[float] = []
        entity_counts: dict[str, int] = {}
        for r in self._records:
            k = r.obs_type.value
            by_t[k] = by_t.get(k, 0) + 1
            k2 = r.fidelity.value
            by_f[k2] = by_f.get(k2, 0) + 1
            k3 = r.strategy.value
            by_s[k3] = by_s.get(k3, 0) + 1
            scores.append(r.risk_score)
            entity_counts[r.entity_id] = entity_counts.get(r.entity_id, 0) + 1
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_density = [eid for eid, cnt in entity_counts.items() if cnt >= 3][:10]
        recs: list[str] = []
        if high_density:
            recs.append(f"{len(high_density)} high-density entities detected")
        if not recs:
            recs.append("Observation density normal")
        return RiskObservationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_type=by_t,
            by_fidelity=by_f,
            by_strategy=by_s,
            high_density_entities=high_density,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.obs_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_observation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def consolidate_observations(
        self,
    ) -> list[dict[str, Any]]:
        """Consolidate observations per entity."""
        entity_data: dict[str, list[RiskObservationRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, obs in entity_data.items():
            total_risk = round(sum(o.risk_score for o in obs), 2)
            results.append(
                {
                    "entity_id": eid,
                    "observation_count": len(obs),
                    "total_risk": total_risk,
                    "types": sorted({o.obs_type.value for o in obs}),
                }
            )
        results.sort(
            key=lambda x: x["total_risk"],
            reverse=True,
        )
        return results

    def compute_observation_density(
        self,
    ) -> list[dict[str, Any]]:
        """Compute observation density per entity."""
        entity_counts: dict[str, int] = {}
        for r in self._records:
            entity_counts[r.entity_id] = entity_counts.get(r.entity_id, 0) + 1
        results: list[dict[str, Any]] = []
        for eid, cnt in entity_counts.items():
            results.append(
                {
                    "entity_id": eid,
                    "density": cnt,
                    "is_high_density": cnt >= 3,
                }
            )
        results.sort(
            key=lambda x: x["density"],
            reverse=True,
        )
        return results

    def detect_observation_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect patterns in observations."""
        entity_types: dict[str, dict[str, int]] = {}
        for r in self._records:
            et = entity_types.setdefault(r.entity_id, {})
            k = r.obs_type.value
            et[k] = et.get(k, 0) + 1
        results: list[dict[str, Any]] = []
        for eid, types in entity_types.items():
            if len(types) > 1:
                results.append(
                    {
                        "entity_id": eid,
                        "pattern_types": types,
                        "diversity": len(types),
                    }
                )
        results.sort(
            key=lambda x: x["diversity"],
            reverse=True,
        )
        return results
