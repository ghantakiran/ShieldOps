"""Risk Factor Aggregator
aggregate risk factors from multiple sources,
detect factor correlations, compute contributions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FactorSource(StrEnum):
    DETECTION_RULE = "detection_rule"
    THREAT_INTEL = "threat_intel"
    BEHAVIOR = "behavior"
    VULNERABILITY = "vulnerability"


class AggregationMethod(StrEnum):
    SUM = "sum"
    MAX = "max"
    WEIGHTED_AVG = "weighted_avg"
    EXPONENTIAL = "exponential"


class FactorWeight(StrEnum):
    CRITICAL_10 = "critical_10"
    HIGH_7 = "high_7"
    MEDIUM_4 = "medium_4"
    LOW_1 = "low_1"


# --- Models ---


class RiskFactorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    factor_id: str = ""
    source: FactorSource = FactorSource.DETECTION_RULE
    method: AggregationMethod = AggregationMethod.SUM
    weight: FactorWeight = FactorWeight.MEDIUM_4
    entity_id: str = ""
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskFactorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    factor_id: str = ""
    source: FactorSource = FactorSource.DETECTION_RULE
    aggregated_score: float = 0.0
    correlation_count: int = 0
    contribution_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskFactorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_weight: dict[str, int] = Field(default_factory=dict)
    top_factors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskFactorAggregator:
    """Aggregate risk factors, detect correlations,
    compute factor contributions."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskFactorRecord] = []
        self._analyses: dict[str, RiskFactorAnalysis] = {}
        logger.info(
            "risk_factor_aggregator.init",
            max_records=max_records,
        )

    def add_record(
        self,
        factor_id: str = "",
        source: FactorSource = (FactorSource.DETECTION_RULE),
        method: AggregationMethod = (AggregationMethod.SUM),
        weight: FactorWeight = FactorWeight.MEDIUM_4,
        entity_id: str = "",
        score: float = 0.0,
        description: str = "",
    ) -> RiskFactorRecord:
        record = RiskFactorRecord(
            factor_id=factor_id,
            source=source,
            method=method,
            weight=weight,
            entity_id=entity_id,
            score=score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_factor_aggregator.record_added",
            record_id=record.id,
            factor_id=factor_id,
        )
        return record

    def process(self, key: str) -> RiskFactorAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        corr = sum(1 for r in self._records if r.entity_id == rec.entity_id and r.id != rec.id)
        total = sum(r.score for r in self._records)
        contrib = round(rec.score / total * 100, 2) if total > 0 else 0.0
        analysis = RiskFactorAnalysis(
            factor_id=rec.factor_id,
            source=rec.source,
            aggregated_score=round(rec.score, 2),
            correlation_count=corr,
            contribution_pct=contrib,
            description=(f"Factor {rec.factor_id} contributes {contrib}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RiskFactorReport:
        by_src: dict[str, int] = {}
        by_mth: dict[str, int] = {}
        by_wt: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.source.value
            by_src[k] = by_src.get(k, 0) + 1
            k2 = r.method.value
            by_mth[k2] = by_mth.get(k2, 0) + 1
            k3 = r.weight.value
            by_wt[k3] = by_wt.get(k3, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        top = sorted(
            self._records,
            key=lambda x: x.score,
            reverse=True,
        )[:5]
        top_ids = [t.factor_id for t in top]
        recs: list[str] = []
        crit = by_wt.get("critical_10", 0)
        if crit > 0:
            recs.append(f"{crit} critical-weight factors")
        if not recs:
            recs.append("Risk factors within norms")
        return RiskFactorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_source=by_src,
            by_method=by_mth,
            by_weight=by_wt,
            top_factors=top_ids,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        src_dist: dict[str, int] = {}
        for r in self._records:
            k = r.source.value
            src_dist[k] = src_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "source_distribution": src_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_factor_aggregator.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def aggregate_risk_factors(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate factors per entity."""
        entity_data: dict[str, list[float]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r.score)
        results: list[dict[str, Any]] = []
        for eid, scores in entity_data.items():
            results.append(
                {
                    "entity_id": eid,
                    "total_score": round(sum(scores), 2),
                    "avg_score": round(sum(scores) / len(scores), 2),
                    "factor_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["total_score"],
            reverse=True,
        )
        return results

    def detect_factor_correlation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect correlated factors on same entity."""
        entity_sources: dict[str, set[str]] = {}
        for r in self._records:
            entity_sources.setdefault(r.entity_id, set()).add(r.source.value)
        results: list[dict[str, Any]] = []
        for eid, sources in entity_sources.items():
            if len(sources) > 1:
                results.append(
                    {
                        "entity_id": eid,
                        "correlated_sources": sorted(sources),
                        "source_count": len(sources),
                    }
                )
        results.sort(
            key=lambda x: x["source_count"],
            reverse=True,
        )
        return results

    def compute_factor_contribution(
        self,
    ) -> list[dict[str, Any]]:
        """Compute each source contribution pct."""
        src_totals: dict[str, float] = {}
        grand = 0.0
        for r in self._records:
            k = r.source.value
            src_totals[k] = src_totals.get(k, 0.0) + r.score
            grand += r.score
        results: list[dict[str, Any]] = []
        for src, total in src_totals.items():
            pct = round(total / grand * 100, 2) if grand > 0 else 0.0
            results.append(
                {
                    "source": src,
                    "total_score": round(total, 2),
                    "contribution_pct": pct,
                }
            )
        results.sort(
            key=lambda x: x["contribution_pct"],
            reverse=True,
        )
        return results
