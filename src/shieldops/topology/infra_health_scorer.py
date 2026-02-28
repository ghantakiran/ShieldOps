"""Infrastructure Health Scorer — score and track infrastructure health across dimensions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthDimension(StrEnum):
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    SECURITY = "security"
    CAPACITY = "capacity"


class HealthGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class InfraLayer(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    PLATFORM = "platform"


# --- Models ---


class HealthScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    resource_name: str = ""
    layer: InfraLayer = InfraLayer.COMPUTE
    grade: HealthGrade = HealthGrade.GOOD
    health_score: float = 0.0
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class HealthDimensionDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    detail_name: str = ""
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: HealthGrade = HealthGrade.GOOD
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InfraHealthScorerReport(BaseModel):
    total_health_records: int = 0
    total_dimension_details: int = 0
    avg_health_score_pct: float = 0.0
    by_layer: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    unhealthy_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureHealthScorer:
    """Score infrastructure health across dimensions and detect unhealthy resources."""

    def __init__(
        self,
        max_records: int = 200000,
        min_health_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_health_score = min_health_score
        self._records: list[HealthScoreRecord] = []
        self._dimension_details: list[HealthDimensionDetail] = []
        logger.info(
            "infra_health_scorer.initialized",
            max_records=max_records,
            min_health_score=min_health_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_health(
        self,
        resource_name: str,
        layer: InfraLayer = InfraLayer.COMPUTE,
        grade: HealthGrade = HealthGrade.GOOD,
        health_score: float = 0.0,
        dimension: HealthDimension = HealthDimension.AVAILABILITY,
        details: str = "",
    ) -> HealthScoreRecord:
        record = HealthScoreRecord(
            resource_name=resource_name,
            layer=layer,
            grade=grade,
            health_score=health_score,
            dimension=dimension,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "infra_health_scorer.recorded",
            record_id=record.id,
            resource_name=resource_name,
            layer=layer.value,
            grade=grade.value,
        )
        return record

    def get_health(self, record_id: str) -> HealthScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_health_records(
        self,
        layer: InfraLayer | None = None,
        grade: HealthGrade | None = None,
        limit: int = 50,
    ) -> list[HealthScoreRecord]:
        results = list(self._records)
        if layer is not None:
            results = [r for r in results if r.layer == layer]
        if grade is not None:
            results = [r for r in results if r.grade == grade]
        return results[-limit:]

    def add_dimension(
        self,
        detail_name: str,
        dimension: HealthDimension = HealthDimension.AVAILABILITY,
        grade: HealthGrade = HealthGrade.GOOD,
        score: float = 0.0,
        description: str = "",
    ) -> HealthDimensionDetail:
        detail = HealthDimensionDetail(
            detail_name=detail_name,
            dimension=dimension,
            grade=grade,
            score=score,
            description=description,
        )
        self._dimension_details.append(detail)
        if len(self._dimension_details) > self._max_records:
            self._dimension_details = self._dimension_details[-self._max_records :]
        logger.info(
            "infra_health_scorer.dimension_added",
            detail_name=detail_name,
            dimension=dimension.value,
            grade=grade.value,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_health_by_layer(self, layer: InfraLayer) -> dict[str, Any]:
        records = [r for r in self._records if r.layer == layer]
        if not records:
            return {"layer": layer.value, "status": "no_data"}
        avg_score = round(sum(r.health_score for r in records) / len(records), 2)
        unhealthy = sum(1 for r in records if r.grade in (HealthGrade.POOR, HealthGrade.CRITICAL))
        return {
            "layer": layer.value,
            "total_records": len(records),
            "avg_health_score": avg_score,
            "unhealthy_count": unhealthy,
            "below_threshold": avg_score < self._min_health_score,
        }

    def identify_unhealthy_infra(self) -> list[dict[str, Any]]:
        unhealthy_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (HealthGrade.POOR, HealthGrade.CRITICAL):
                unhealthy_counts[r.resource_name] = unhealthy_counts.get(r.resource_name, 0) + 1
        results: list[dict[str, Any]] = []
        for resource, count in unhealthy_counts.items():
            if count > 1:
                results.append({"resource_name": resource, "unhealthy_count": count})
        results.sort(key=lambda x: x["unhealthy_count"], reverse=True)
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        resource_scores: dict[str, list[float]] = {}
        for r in self._records:
            resource_scores.setdefault(r.resource_name, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for resource, scores in resource_scores.items():
            results.append(
                {
                    "resource_name": resource,
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"])
        return results

    def detect_health_trends(self) -> list[dict[str, Any]]:
        resource_counts: dict[str, int] = {}
        for r in self._records:
            resource_counts[r.resource_name] = resource_counts.get(r.resource_name, 0) + 1
        results: list[dict[str, Any]] = []
        for resource, count in resource_counts.items():
            if count > 3:
                results.append(
                    {
                        "resource_name": resource,
                        "health_record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["health_record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> InfraHealthScorerReport:
        by_layer: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_layer[r.layer.value] = by_layer.get(r.layer.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_score = (
            round(sum(r.health_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        unhealthy = sum(
            1 for r in self._records if r.grade in (HealthGrade.POOR, HealthGrade.CRITICAL)
        )
        recs: list[str] = []
        if self._records and avg_score < self._min_health_score:
            recs.append(
                f"Average health score {avg_score}% is below"
                f" {self._min_health_score}% minimum threshold"
            )
        trends = len(self.detect_health_trends())
        if trends > 0:
            recs.append(f"{trends} resource(s) with recurring health degradation trends")
        if not recs:
            recs.append("Infrastructure health scores are within acceptable thresholds")
        return InfraHealthScorerReport(
            total_health_records=len(self._records),
            total_dimension_details=len(self._dimension_details),
            avg_health_score_pct=avg_score,
            by_layer=by_layer,
            by_grade=by_grade,
            unhealthy_count=unhealthy,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._dimension_details.clear()
        logger.info("infra_health_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        layer_dist: dict[str, int] = {}
        for r in self._records:
            key = r.layer.value
            layer_dist[key] = layer_dist.get(key, 0) + 1
        return {
            "total_health_records": len(self._records),
            "total_dimension_details": len(self._dimension_details),
            "min_health_score": self._min_health_score,
            "layer_distribution": layer_dist,
            "unique_resources": len({r.resource_name for r in self._records}),
        }
