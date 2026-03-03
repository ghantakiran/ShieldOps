"""Crown Jewel Access Monitor — monitor access to critical crown jewel assets."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class JewelType(StrEnum):
    DATABASE = "database"
    SECRET_STORE = "secret_store"  # noqa: S105
    SOURCE_CODE = "source_code"
    CUSTOMER_DATA = "customer_data"
    FINANCIAL_SYSTEM = "financial_system"


class AccessType(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    EXPORT = "export"
    DELETE = "delete"


class AccessRisk(StrEnum):
    UNAUTHORIZED = "unauthorized"
    SUSPICIOUS = "suspicious"
    ELEVATED = "elevated"
    NORMAL = "normal"
    PRIVILEGED = "privileged"


# --- Models ---


class JewelAccessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_id: str = ""
    jewel_type: JewelType = JewelType.DATABASE
    access_type_val: AccessType = AccessType.READ
    access_risk: AccessRisk = AccessRisk.NORMAL
    access_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class JewelAccessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_id: str = ""
    jewel_type: JewelType = JewelType.DATABASE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class JewelAccessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_access_score: float = 0.0
    by_jewel: dict[str, int] = Field(default_factory=dict)
    by_access_type: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrownJewelAccessMonitor:
    """Monitor access to critical crown jewel assets and detect anomalous patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        access_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._access_threshold = access_threshold
        self._records: list[JewelAccessRecord] = []
        self._analyses: list[JewelAccessAnalysis] = []
        logger.info(
            "crown_jewel_access_monitor.initialized",
            max_records=max_records,
            access_threshold=access_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_access(
        self,
        access_id: str,
        jewel_type: JewelType = JewelType.DATABASE,
        access_type_val: AccessType = AccessType.READ,
        access_risk: AccessRisk = AccessRisk.NORMAL,
        access_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> JewelAccessRecord:
        record = JewelAccessRecord(
            access_id=access_id,
            jewel_type=jewel_type,
            access_type_val=access_type_val,
            access_risk=access_risk,
            access_score=access_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "crown_jewel_access_monitor.access_recorded",
            record_id=record.id,
            access_id=access_id,
            jewel_type=jewel_type.value,
            access_type_val=access_type_val.value,
        )
        return record

    def get_access(self, record_id: str) -> JewelAccessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_accesses(
        self,
        jewel_type: JewelType | None = None,
        access_type_val: AccessType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[JewelAccessRecord]:
        results = list(self._records)
        if jewel_type is not None:
            results = [r for r in results if r.jewel_type == jewel_type]
        if access_type_val is not None:
            results = [r for r in results if r.access_type_val == access_type_val]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        access_id: str,
        jewel_type: JewelType = JewelType.DATABASE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> JewelAccessAnalysis:
        analysis = JewelAccessAnalysis(
            access_id=access_id,
            jewel_type=jewel_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "crown_jewel_access_monitor.analysis_added",
            access_id=access_id,
            jewel_type=jewel_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_jewel_distribution(self) -> dict[str, Any]:
        jewel_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.jewel_type.value
            jewel_data.setdefault(key, []).append(r.access_score)
        result: dict[str, Any] = {}
        for jewel, scores in jewel_data.items():
            result[jewel] = {
                "count": len(scores),
                "avg_access_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_access_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.access_score < self._access_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "access_id": r.access_id,
                        "jewel_type": r.jewel_type.value,
                        "access_score": r.access_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["access_score"])

    def rank_by_access(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.access_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_access_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_access_score"])
        return results

    def detect_access_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> JewelAccessReport:
        by_jewel: dict[str, int] = {}
        by_access_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_jewel[r.jewel_type.value] = by_jewel.get(r.jewel_type.value, 0) + 1
            by_access_type[r.access_type_val.value] = (
                by_access_type.get(r.access_type_val.value, 0) + 1
            )
            by_risk[r.access_risk.value] = by_risk.get(r.access_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.access_score < self._access_threshold)
        scores = [r.access_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_access_gaps()
        top_gaps = [o["access_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} access(es) below threshold ({self._access_threshold})")
        if self._records and avg_score < self._access_threshold:
            recs.append(f"Avg access score {avg_score} below threshold ({self._access_threshold})")
        if not recs:
            recs.append("Crown jewel access monitoring is healthy")
        return JewelAccessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_access_score=avg_score,
            by_jewel=by_jewel,
            by_access_type=by_access_type,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("crown_jewel_access_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        jewel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.jewel_type.value
            jewel_dist[key] = jewel_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "access_threshold": self._access_threshold,
            "jewel_distribution": jewel_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
