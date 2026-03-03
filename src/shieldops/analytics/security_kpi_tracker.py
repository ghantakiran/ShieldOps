"""Security KPI Tracker — track security key performance indicators across categories."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KPICategory(StrEnum):
    DETECTION = "detection"
    RESPONSE = "response"
    PREVENTION = "prevention"
    COMPLIANCE = "compliance"
    RISK = "risk"


class MeasurementFrequency(StrEnum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class KPIStatus(StrEnum):
    ON_TARGET = "on_target"
    AT_RISK = "at_risk"
    MISSED = "missed"
    EXCEEDED = "exceeded"
    NOT_MEASURED = "not_measured"


# --- Models ---


class KPIRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kpi_id: str = ""
    kpi_category: KPICategory = KPICategory.DETECTION
    measurement_frequency: MeasurementFrequency = MeasurementFrequency.DAILY
    kpi_status: KPIStatus = KPIStatus.ON_TARGET
    kpi_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class KPIAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kpi_id: str = ""
    kpi_category: KPICategory = KPICategory.DETECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KPIReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_kpi_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityKPITracker:
    """Track security key performance indicators across categories and frequencies."""

    def __init__(
        self,
        max_records: int = 200000,
        kpi_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._kpi_threshold = kpi_threshold
        self._records: list[KPIRecord] = []
        self._analyses: list[KPIAnalysis] = []
        logger.info(
            "security_kpi_tracker.initialized",
            max_records=max_records,
            kpi_threshold=kpi_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_kpi(
        self,
        kpi_id: str,
        kpi_category: KPICategory = KPICategory.DETECTION,
        measurement_frequency: MeasurementFrequency = MeasurementFrequency.DAILY,
        kpi_status: KPIStatus = KPIStatus.ON_TARGET,
        kpi_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> KPIRecord:
        record = KPIRecord(
            kpi_id=kpi_id,
            kpi_category=kpi_category,
            measurement_frequency=measurement_frequency,
            kpi_status=kpi_status,
            kpi_score=kpi_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_kpi_tracker.kpi_recorded",
            record_id=record.id,
            kpi_id=kpi_id,
            kpi_category=kpi_category.value,
            measurement_frequency=measurement_frequency.value,
        )
        return record

    def get_kpi(self, record_id: str) -> KPIRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_kpis(
        self,
        kpi_category: KPICategory | None = None,
        measurement_frequency: MeasurementFrequency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[KPIRecord]:
        results = list(self._records)
        if kpi_category is not None:
            results = [r for r in results if r.kpi_category == kpi_category]
        if measurement_frequency is not None:
            results = [r for r in results if r.measurement_frequency == measurement_frequency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        kpi_id: str,
        kpi_category: KPICategory = KPICategory.DETECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> KPIAnalysis:
        analysis = KPIAnalysis(
            kpi_id=kpi_id,
            kpi_category=kpi_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_kpi_tracker.analysis_added",
            kpi_id=kpi_id,
            kpi_category=kpi_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.kpi_category.value
            category_data.setdefault(key, []).append(r.kpi_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_kpi_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_kpi_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.kpi_score < self._kpi_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "kpi_id": r.kpi_id,
                        "kpi_category": r.kpi_category.value,
                        "kpi_score": r.kpi_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["kpi_score"])

    def rank_by_kpi(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.kpi_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_kpi_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_kpi_score"])
        return results

    def detect_kpi_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> KPIReport:
        by_category: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.kpi_category.value] = by_category.get(r.kpi_category.value, 0) + 1
            by_frequency[r.measurement_frequency.value] = (
                by_frequency.get(r.measurement_frequency.value, 0) + 1
            )
            by_status[r.kpi_status.value] = by_status.get(r.kpi_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.kpi_score < self._kpi_threshold)
        scores = [r.kpi_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_kpi_gaps()
        top_gaps = [o["kpi_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} KPI(s) below threshold ({self._kpi_threshold})")
        if self._records and avg_score < self._kpi_threshold:
            recs.append(f"Avg KPI score {avg_score} below threshold ({self._kpi_threshold})")
        if not recs:
            recs.append("Security KPIs are healthy")
        return KPIReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_kpi_score=avg_score,
            by_category=by_category,
            by_frequency=by_frequency,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_kpi_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.kpi_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "kpi_threshold": self._kpi_threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
