"""Security Control SLA Monitor — monitor SLA compliance of security controls."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlCategory(StrEnum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    DETERRENT = "deterrent"
    COMPENSATING = "compensating"


class SLAMetric(StrEnum):
    UPTIME = "uptime"
    RESPONSE_TIME = "response_time"
    COVERAGE = "coverage"
    EFFECTIVENESS = "effectiveness"
    COMPLIANCE = "compliance"


class SLAStatus(StrEnum):
    MET = "met"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    EXEMPT = "exempt"
    NOT_MEASURED = "not_measured"


# --- Models ---


class ControlSLARecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    control_category: ControlCategory = ControlCategory.PREVENTIVE
    sla_metric: SLAMetric = SLAMetric.UPTIME
    sla_status: SLAStatus = SLAStatus.MET
    sla_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlSLAAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str = ""
    control_category: ControlCategory = ControlCategory.PREVENTIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlSLAReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_sla_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityControlSLAMonitor:
    """Monitor SLA compliance of security controls across categories and metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        sla_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._sla_threshold = sla_threshold
        self._records: list[ControlSLARecord] = []
        self._analyses: list[ControlSLAAnalysis] = []
        logger.info(
            "security_control_sla_monitor.initialized",
            max_records=max_records,
            sla_threshold=sla_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_sla(
        self,
        sla_id: str,
        control_category: ControlCategory = ControlCategory.PREVENTIVE,
        sla_metric: SLAMetric = SLAMetric.UPTIME,
        sla_status: SLAStatus = SLAStatus.MET,
        sla_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ControlSLARecord:
        record = ControlSLARecord(
            sla_id=sla_id,
            control_category=control_category,
            sla_metric=sla_metric,
            sla_status=sla_status,
            sla_score=sla_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_control_sla_monitor.sla_recorded",
            record_id=record.id,
            sla_id=sla_id,
            control_category=control_category.value,
            sla_metric=sla_metric.value,
        )
        return record

    def get_sla(self, record_id: str) -> ControlSLARecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_slas(
        self,
        control_category: ControlCategory | None = None,
        sla_metric: SLAMetric | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlSLARecord]:
        results = list(self._records)
        if control_category is not None:
            results = [r for r in results if r.control_category == control_category]
        if sla_metric is not None:
            results = [r for r in results if r.sla_metric == sla_metric]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        sla_id: str,
        control_category: ControlCategory = ControlCategory.PREVENTIVE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ControlSLAAnalysis:
        analysis = ControlSLAAnalysis(
            sla_id=sla_id,
            control_category=control_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_control_sla_monitor.analysis_added",
            sla_id=sla_id,
            control_category=control_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_category.value
            category_data.setdefault(key, []).append(r.sla_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_sla_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_sla_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.sla_score < self._sla_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "sla_id": r.sla_id,
                        "control_category": r.control_category.value,
                        "sla_score": r.sla_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["sla_score"])

    def rank_by_sla(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.sla_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_sla_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_sla_score"])
        return results

    def detect_sla_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ControlSLAReport:
        by_category: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.control_category.value] = by_category.get(r.control_category.value, 0) + 1
            by_metric[r.sla_metric.value] = by_metric.get(r.sla_metric.value, 0) + 1
            by_status[r.sla_status.value] = by_status.get(r.sla_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.sla_score < self._sla_threshold)
        scores = [r.sla_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_sla_gaps()
        top_gaps = [o["sla_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} SLA(s) below threshold ({self._sla_threshold})")
        if self._records and avg_score < self._sla_threshold:
            recs.append(f"Avg SLA score {avg_score} below threshold ({self._sla_threshold})")
        if not recs:
            recs.append("Security control SLAs are healthy")
        return ControlSLAReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_sla_score=avg_score,
            by_category=by_category,
            by_metric=by_metric,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_control_sla_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "sla_threshold": self._sla_threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
