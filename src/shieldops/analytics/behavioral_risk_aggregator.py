"""Behavioral Risk Aggregator — aggregate risk signals from multiple sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskSource(StrEnum):
    UEBA = "ueba"
    DLP = "dlp"
    IAM = "iam"
    NETWORK = "network"
    ENDPOINT = "endpoint"


class AggregationMethod(StrEnum):
    WEIGHTED_AVERAGE = "weighted_average"
    MAXIMUM = "maximum"
    BAYESIAN = "bayesian"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


class RiskTier(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    ELEVATED = "elevated"
    NORMAL = "normal"
    LOW = "low"


# --- Models ---


class AggregatedRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    risk_source: RiskSource = RiskSource.UEBA
    aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE
    risk_tier: RiskTier = RiskTier.NORMAL
    aggregated_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AggregatedRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    risk_source: RiskSource = RiskSource.UEBA
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BehavioralRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_aggregated_score: float = 0.0
    by_risk_source: dict[str, int] = Field(default_factory=dict)
    by_aggregation_method: dict[str, int] = Field(default_factory=dict)
    by_risk_tier: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BehavioralRiskAggregator:
    """Aggregate risk signals from multiple sources using various aggregation methods."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AggregatedRiskRecord] = []
        self._analyses: list[AggregatedRiskAnalysis] = []
        logger.info(
            "behavioral_risk_aggregator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_risk(
        self,
        entity_name: str,
        risk_source: RiskSource = RiskSource.UEBA,
        aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE,
        risk_tier: RiskTier = RiskTier.NORMAL,
        aggregated_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AggregatedRiskRecord:
        record = AggregatedRiskRecord(
            entity_name=entity_name,
            risk_source=risk_source,
            aggregation_method=aggregation_method,
            risk_tier=risk_tier,
            aggregated_score=aggregated_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "behavioral_risk_aggregator.risk_recorded",
            record_id=record.id,
            entity_name=entity_name,
            risk_source=risk_source.value,
            aggregation_method=aggregation_method.value,
        )
        return record

    def get_record(self, record_id: str) -> AggregatedRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        risk_source: RiskSource | None = None,
        aggregation_method: AggregationMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AggregatedRiskRecord]:
        results = list(self._records)
        if risk_source is not None:
            results = [r for r in results if r.risk_source == risk_source]
        if aggregation_method is not None:
            results = [r for r in results if r.aggregation_method == aggregation_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        entity_name: str,
        risk_source: RiskSource = RiskSource.UEBA,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AggregatedRiskAnalysis:
        analysis = AggregatedRiskAnalysis(
            entity_name=entity_name,
            risk_source=risk_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "behavioral_risk_aggregator.analysis_added",
            entity_name=entity_name,
            risk_source=risk_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by risk_source; return count and avg aggregated_score."""
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.risk_source.value
            source_data.setdefault(key, []).append(r.aggregated_score)
        result: dict[str, Any] = {}
        for source, scores in source_data.items():
            result[source] = {
                "count": len(scores),
                "avg_aggregated_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where aggregated_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.aggregated_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "entity_name": r.entity_name,
                        "risk_source": r.risk_source.value,
                        "aggregated_score": r.aggregated_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["aggregated_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg aggregated_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.aggregated_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_aggregated_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_aggregated_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> BehavioralRiskReport:
        by_risk_source: dict[str, int] = {}
        by_aggregation_method: dict[str, int] = {}
        by_risk_tier: dict[str, int] = {}
        for r in self._records:
            by_risk_source[r.risk_source.value] = by_risk_source.get(r.risk_source.value, 0) + 1
            by_aggregation_method[r.aggregation_method.value] = (
                by_aggregation_method.get(r.aggregation_method.value, 0) + 1
            )
            by_risk_tier[r.risk_tier.value] = by_risk_tier.get(r.risk_tier.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.aggregated_score < self._threshold)
        scores = [r.aggregated_score for r in self._records]
        avg_aggregated_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["entity_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} entity(s) below aggregated risk threshold ({self._threshold})"
            )
        if self._records and avg_aggregated_score < self._threshold:
            recs.append(
                f"Avg aggregated score {avg_aggregated_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Behavioral risk aggregation is healthy")
        return BehavioralRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_aggregated_score=avg_aggregated_score,
            by_risk_source=by_risk_source,
            by_aggregation_method=by_aggregation_method,
            by_risk_tier=by_risk_tier,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("behavioral_risk_aggregator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_source.value
            risk_source_dist[key] = risk_source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "risk_source_distribution": risk_source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
