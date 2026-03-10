"""Causal Inference Engine

Evaluates causal relationships between operational events
using counterfactual reasoning and evidence scoring.
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


class CausalRelation(StrEnum):
    CAUSES = "causes"
    CORRELATES = "correlates"
    PRECEDES = "precedes"
    INDEPENDENT = "independent"
    UNKNOWN = "unknown"


class EvidenceStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class InterventionType(StrEnum):
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    SCALING = "scaling"
    RESTART = "restart"
    EXTERNAL = "external"


# --- Models ---


class CausalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_event: str = ""
    target_event: str = ""
    relation: CausalRelation = CausalRelation.UNKNOWN
    evidence_strength: EvidenceStrength = EvidenceStrength.INSUFFICIENT
    intervention_type: InterventionType = InterventionType.DEPLOYMENT
    temporal_lag_sec: float = 0.0
    confidence_score: float = 0.0
    blast_radius_overlap: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CausalAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_event: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CausalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence: float = 0.0
    causal_link_count: int = 0
    by_relation: dict[str, int] = Field(default_factory=dict)
    by_evidence: dict[str, int] = Field(default_factory=dict)
    by_intervention: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CausalInferenceEngine:
    """Causal Inference Engine

    Evaluates causal relationships between operational
    events using counterfactual reasoning.
    """

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[CausalRecord] = []
        self._analyses: list[CausalAnalysis] = []
        logger.info(
            "causal_inference_engine.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    def add_record(
        self,
        source_event: str,
        target_event: str,
        relation: CausalRelation = (CausalRelation.UNKNOWN),
        evidence_strength: EvidenceStrength = (EvidenceStrength.INSUFFICIENT),
        intervention_type: InterventionType = (InterventionType.DEPLOYMENT),
        temporal_lag_sec: float = 0.0,
        confidence_score: float = 0.0,
        blast_radius_overlap: float = 0.0,
    ) -> CausalRecord:
        record = CausalRecord(
            source_event=source_event,
            target_event=target_event,
            relation=relation,
            evidence_strength=evidence_strength,
            intervention_type=intervention_type,
            temporal_lag_sec=temporal_lag_sec,
            confidence_score=confidence_score,
            blast_radius_overlap=blast_radius_overlap,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "causal_inference_engine.record_added",
            record_id=record.id,
            source_event=source_event,
            target_event=target_event,
        )
        return record

    def evaluate_causality(
        self,
        source_event: str,
        target_event: str,
    ) -> dict[str, Any]:
        matching = [
            r
            for r in self._records
            if r.source_event == source_event and r.target_event == target_event
        ]
        if not matching:
            return {
                "source": source_event,
                "target": target_event,
                "status": "no_data",
            }
        scores = [r.confidence_score for r in matching]
        avg = round(sum(scores) / len(scores), 4)
        causal = sum(1 for r in matching if r.relation == CausalRelation.CAUSES)
        return {
            "source": source_event,
            "target": target_event,
            "avg_confidence": avg,
            "causal_count": causal,
            "total_observations": len(matching),
        }

    def build_counterfactual(self, source_event: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.source_event == source_event]
        if not matching:
            return {
                "source": source_event,
                "status": "no_data",
            }
        targets: dict[str, list[float]] = {}
        for r in matching:
            if r.target_event not in targets:
                targets[r.target_event] = []
            targets[r.target_event].append(r.confidence_score)
        effects = []
        for tgt, scores in targets.items():
            avg = round(sum(scores) / len(scores), 4)
            effects.append(
                {
                    "target": tgt,
                    "avg_confidence": avg,
                    "observations": len(scores),
                }
            )
        return {
            "source": source_event,
            "potential_effects": sorted(
                effects,
                key=lambda x: x["avg_confidence"],
                reverse=True,
            ),
        }

    def rank_causal_factors(self, target_event: str, top_n: int = 5) -> list[dict[str, Any]]:
        matching = [
            r
            for r in self._records
            if r.target_event == target_event and r.relation == CausalRelation.CAUSES
        ]
        if not matching:
            return []
        factors: dict[str, list[float]] = {}
        for r in matching:
            if r.source_event not in factors:
                factors[r.source_event] = []
            factors[r.source_event].append(r.confidence_score)
        ranked = []
        for src, scores in factors.items():
            avg = round(sum(scores) / len(scores), 4)
            ranked.append(
                {
                    "source": src,
                    "avg_confidence": avg,
                    "observations": len(scores),
                }
            )
        return sorted(
            ranked,
            key=lambda x: x["avg_confidence"],  # type: ignore[arg-type,return-value]
            reverse=True,
        )[:top_n]

    def process(self, source_event: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.source_event == source_event]
        if not matching:
            return {
                "source_event": source_event,
                "status": "no_data",
            }
        scores = [r.confidence_score for r in matching]
        avg = round(sum(scores) / len(scores), 4)
        causal = sum(1 for r in matching if r.relation == CausalRelation.CAUSES)
        return {
            "source_event": source_event,
            "record_count": len(matching),
            "avg_confidence": avg,
            "causal_links": causal,
        }

    def generate_report(self) -> CausalReport:
        by_rel: dict[str, int] = {}
        by_ev: dict[str, int] = {}
        by_int: dict[str, int] = {}
        for r in self._records:
            rv = r.relation.value
            by_rel[rv] = by_rel.get(rv, 0) + 1
            ev = r.evidence_strength.value
            by_ev[ev] = by_ev.get(ev, 0) + 1
            iv = r.intervention_type.value
            by_int[iv] = by_int.get(iv, 0) + 1
        scores = [r.confidence_score for r in self._records]
        avg_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        causal = by_rel.get("causes", 0)
        recs: list[str] = []
        unknown = by_rel.get("unknown", 0)
        total = len(self._records)
        if total > 0 and unknown / total > 0.4:
            recs.append("Over 40% relations unknown — increase evidence collection")
        weak = by_ev.get("insufficient", 0)
        if total > 0 and weak / total > 0.3:
            recs.append("Over 30% insufficient evidence — add more signal sources")
        if not recs:
            recs.append("Causal inference quality is nominal")
        return CausalReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_confidence=avg_conf,
            causal_link_count=causal,
            by_relation=by_rel,
            by_evidence=by_ev,
            by_intervention=by_int,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rel_dist: dict[str, int] = {}
        for r in self._records:
            k = r.relation.value
            rel_dist[k] = rel_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "confidence_threshold": (self._confidence_threshold),
            "relation_distribution": rel_dist,
            "unique_sources": len({r.source_event for r in self._records}),
            "unique_targets": len({r.target_event for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("causal_inference_engine.cleared")
        return {"status": "cleared"}
