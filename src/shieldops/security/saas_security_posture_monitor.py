"""SaaS Security Posture Monitor — monitor SaaS security posture."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SaaSCategory(StrEnum):
    COLLABORATION = "collaboration"
    CRM = "crm"
    DEVELOPMENT = "development"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"


class PostureArea(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_PROTECTION = "data_protection"
    LOGGING = "logging"
    INTEGRATION = "integration"


class PostureGrade(StrEnum):
    A_EXCELLENT = "a_excellent"
    B_GOOD = "b_good"
    C_FAIR = "c_fair"
    D_POOR = "d_poor"
    F_CRITICAL = "f_critical"


# --- Models ---


class SaaSPostureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    saas_category: SaaSCategory = SaaSCategory.COLLABORATION
    posture_area: PostureArea = PostureArea.AUTHENTICATION
    posture_grade: PostureGrade = PostureGrade.A_EXCELLENT
    posture_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SaaSPostureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    saas_category: SaaSCategory = SaaSCategory.COLLABORATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SaaSSecurityPostureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_posture_score: float = 0.0
    by_saas_category: dict[str, int] = Field(default_factory=dict)
    by_posture_area: dict[str, int] = Field(default_factory=dict)
    by_posture_grade: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SaaSSecurityPostureMonitor:
    """Monitor SaaS application security posture across categories."""

    def __init__(
        self,
        max_records: int = 200000,
        posture_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._posture_gap_threshold = posture_gap_threshold
        self._records: list[SaaSPostureRecord] = []
        self._analyses: list[SaaSPostureAnalysis] = []
        logger.info(
            "saas_security_posture_monitor.initialized",
            max_records=max_records,
            posture_gap_threshold=posture_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_posture(
        self,
        posture_id: str,
        saas_category: SaaSCategory = SaaSCategory.COLLABORATION,
        posture_area: PostureArea = PostureArea.AUTHENTICATION,
        posture_grade: PostureGrade = PostureGrade.A_EXCELLENT,
        posture_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SaaSPostureRecord:
        record = SaaSPostureRecord(
            posture_id=posture_id,
            saas_category=saas_category,
            posture_area=posture_area,
            posture_grade=posture_grade,
            posture_score=posture_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "saas_security_posture_monitor.recorded",
            record_id=record.id,
            posture_id=posture_id,
            saas_category=saas_category.value,
            posture_area=posture_area.value,
        )
        return record

    def get_posture(self, record_id: str) -> SaaSPostureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_postures(
        self,
        saas_category: SaaSCategory | None = None,
        posture_area: PostureArea | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SaaSPostureRecord]:
        results = list(self._records)
        if saas_category is not None:
            results = [r for r in results if r.saas_category == saas_category]
        if posture_area is not None:
            results = [r for r in results if r.posture_area == posture_area]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        posture_id: str,
        saas_category: SaaSCategory = SaaSCategory.COLLABORATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SaaSPostureAnalysis:
        analysis = SaaSPostureAnalysis(
            posture_id=posture_id,
            saas_category=saas_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "saas_security_posture_monitor.analysis_added",
            posture_id=posture_id,
            saas_category=saas_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_posture_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.saas_category.value
            data.setdefault(key, []).append(r.posture_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_posture_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_posture_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.posture_score < self._posture_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "posture_id": r.posture_id,
                        "saas_category": r.saas_category.value,
                        "posture_score": r.posture_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["posture_score"])

    def rank_by_posture(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.posture_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_posture_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_posture_score"])
        return results

    def detect_posture_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SaaSSecurityPostureReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.saas_category.value] = by_e1.get(r.saas_category.value, 0) + 1
            by_e2[r.posture_area.value] = by_e2.get(r.posture_area.value, 0) + 1
            by_e3[r.posture_grade.value] = by_e3.get(r.posture_grade.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.posture_score < self._posture_gap_threshold)
        scores = [r.posture_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_posture_gaps()
        top_gaps = [o["posture_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._posture_gap_threshold})")
        if self._records and avg_score < self._posture_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._posture_gap_threshold})")
        if not recs:
            recs.append("SaaSSecurityPostureMonitor metrics are healthy")
        return SaaSSecurityPostureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_posture_score=avg_score,
            by_saas_category=by_e1,
            by_posture_area=by_e2,
            by_posture_grade=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("saas_security_posture_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.saas_category.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "posture_gap_threshold": self._posture_gap_threshold,
            "saas_category_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
