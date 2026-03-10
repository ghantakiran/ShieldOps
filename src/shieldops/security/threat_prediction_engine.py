"""Threat Prediction Engine
predict attack probability, identify precursor patterns,
compute threat velocity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatVector(StrEnum):
    NETWORK = "network"
    ENDPOINT = "endpoint"
    IDENTITY = "identity"
    SUPPLY_CHAIN = "supply_chain"


class PredictionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class ThreatHorizon(StrEnum):
    IMMINENT = "imminent"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


# --- Models ---


class ThreatPredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    threat_vector: ThreatVector = ThreatVector.NETWORK
    confidence: PredictionConfidence = PredictionConfidence.MEDIUM
    horizon: ThreatHorizon = ThreatHorizon.SHORT_TERM
    probability: float = 0.0
    velocity: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatPredictionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    threat_vector: ThreatVector = ThreatVector.NETWORK
    analysis_score: float = 0.0
    predicted_probability: float = 0.0
    precursor_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatPredictionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_probability: float = 0.0
    avg_velocity: float = 0.0
    by_vector: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_horizon: dict[str, int] = Field(default_factory=dict)
    high_risk_threats: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatPredictionEngine:
    """Predict attack probability, identify precursor
    patterns, and compute threat velocity."""

    def __init__(
        self,
        max_records: int = 200000,
        probability_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._probability_threshold = probability_threshold
        self._records: list[ThreatPredictionRecord] = []
        self._analyses: list[ThreatPredictionAnalysis] = []
        logger.info(
            "threat_prediction_engine.initialized",
            max_records=max_records,
            probability_threshold=probability_threshold,
        )

    def add_record(
        self,
        threat_id: str,
        threat_vector: ThreatVector = ThreatVector.NETWORK,
        confidence: PredictionConfidence = (PredictionConfidence.MEDIUM),
        horizon: ThreatHorizon = ThreatHorizon.SHORT_TERM,
        probability: float = 0.0,
        velocity: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ThreatPredictionRecord:
        record = ThreatPredictionRecord(
            threat_id=threat_id,
            threat_vector=threat_vector,
            confidence=confidence,
            horizon=horizon,
            probability=probability,
            velocity=velocity,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_prediction_engine.record_added",
            record_id=record.id,
            threat_id=threat_id,
            threat_vector=threat_vector.value,
        )
        return record

    def process(self, key: str) -> ThreatPredictionAnalysis | None:
        """Process a record by ID, producing an analysis."""
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = rec.probability * 100.0
        precursors = int(rec.velocity * 2)
        analysis = ThreatPredictionAnalysis(
            threat_id=rec.threat_id,
            threat_vector=rec.threat_vector,
            analysis_score=round(score, 2),
            predicted_probability=rec.probability,
            precursor_count=precursors,
            description=(f"Threat {rec.threat_id} analyzed with score {score:.1f}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> ThreatPredictionReport:
        by_vector: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_horizon: dict[str, int] = {}
        probs: list[float] = []
        vels: list[float] = []
        for r in self._records:
            v = r.threat_vector.value
            by_vector[v] = by_vector.get(v, 0) + 1
            c = r.confidence.value
            by_confidence[c] = by_confidence.get(c, 0) + 1
            h = r.horizon.value
            by_horizon[h] = by_horizon.get(h, 0) + 1
            probs.append(r.probability)
            vels.append(r.velocity)
        avg_p = round(sum(probs) / len(probs), 4) if probs else 0.0
        avg_v = round(sum(vels) / len(vels), 2) if vels else 0.0
        high_risk = [
            r.threat_id for r in self._records if r.probability >= self._probability_threshold
        ][:5]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} threats above probability threshold")
        if not recs:
            recs.append("Threat predictions within norms")
        return ThreatPredictionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_probability=avg_p,
            avg_velocity=avg_v,
            by_vector=by_vector,
            by_confidence=by_confidence,
            by_horizon=by_horizon,
            high_risk_threats=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        vec_dist: dict[str, int] = {}
        for r in self._records:
            k = r.threat_vector.value
            vec_dist[k] = vec_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "probability_threshold": (self._probability_threshold),
            "vector_distribution": vec_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_prediction_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def predict_attack_probability(
        self,
    ) -> list[dict[str, Any]]:
        """Predict attack probability per vector."""
        vector_data: dict[str, list[float]] = {}
        for r in self._records:
            k = r.threat_vector.value
            vector_data.setdefault(k, []).append(r.probability)
        results: list[dict[str, Any]] = []
        for vec, probs in vector_data.items():
            avg = round(sum(probs) / len(probs), 4)
            mx = round(max(probs), 4)
            results.append(
                {
                    "vector": vec,
                    "avg_probability": avg,
                    "max_probability": mx,
                    "sample_count": len(probs),
                    "high_risk": avg >= self._probability_threshold,
                }
            )
        results.sort(
            key=lambda x: x["avg_probability"],
            reverse=True,
        )
        return results

    def identify_precursor_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Find records that may be precursors
        based on low probability but high velocity."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.probability < self._probability_threshold and r.velocity > 0:
                score = round(
                    r.velocity * (1.0 - r.probability),
                    4,
                )
                results.append(
                    {
                        "threat_id": r.threat_id,
                        "vector": r.threat_vector.value,
                        "probability": r.probability,
                        "velocity": r.velocity,
                        "precursor_score": score,
                    }
                )
        results.sort(
            key=lambda x: x["precursor_score"],
            reverse=True,
        )
        return results

    def compute_threat_velocity(
        self,
    ) -> dict[str, Any]:
        """Compute velocity statistics per vector."""
        if not self._records:
            return {
                "avg_velocity": 0.0,
                "max_velocity": 0.0,
                "by_vector": {},
            }
        vec_vels: dict[str, list[float]] = {}
        for r in self._records:
            k = r.threat_vector.value
            vec_vels.setdefault(k, []).append(r.velocity)
        by_vec: dict[str, float] = {}
        for v, vals in vec_vels.items():
            by_vec[v] = round(sum(vals) / len(vals), 2)
        all_v = [r.velocity for r in self._records]
        return {
            "avg_velocity": round(sum(all_v) / len(all_v), 2),
            "max_velocity": round(max(all_v), 2),
            "by_vector": by_vec,
        }
