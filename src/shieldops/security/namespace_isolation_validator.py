"""Namespace Isolation Validator — validate Kubernetes namespace isolation boundaries."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IsolationType(StrEnum):
    NETWORK = "network"
    RESOURCE = "resource"
    RBAC = "rbac"
    STORAGE = "storage"
    FULL = "full"


class IsolationStatus(StrEnum):
    ISOLATED = "isolated"
    PARTIAL = "partial"
    SHARED = "shared"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class TenantModel(StrEnum):
    SINGLE = "single"
    MULTI = "multi"
    HYBRID = "hybrid"
    HIERARCHICAL = "hierarchical"
    FLAT = "flat"


# --- Models ---


class IsolationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    isolation_id: str = ""
    isolation_type: IsolationType = IsolationType.NETWORK
    isolation_status: IsolationStatus = IsolationStatus.ISOLATED
    tenant_model: TenantModel = TenantModel.SINGLE
    isolation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IsolationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    isolation_id: str = ""
    isolation_type: IsolationType = IsolationType.NETWORK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NamespaceIsolationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_isolation_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_tenant_model: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class NamespaceIsolationValidator:
    """Validate Kubernetes namespace isolation boundaries, tenant models, and security."""

    def __init__(
        self,
        max_records: int = 200000,
        isolation_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._isolation_gap_threshold = isolation_gap_threshold
        self._records: list[IsolationRecord] = []
        self._analyses: list[IsolationAnalysis] = []
        logger.info(
            "namespace_isolation_validator.initialized",
            max_records=max_records,
            isolation_gap_threshold=isolation_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_isolation(
        self,
        isolation_id: str,
        isolation_type: IsolationType = IsolationType.NETWORK,
        isolation_status: IsolationStatus = IsolationStatus.ISOLATED,
        tenant_model: TenantModel = TenantModel.SINGLE,
        isolation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IsolationRecord:
        record = IsolationRecord(
            isolation_id=isolation_id,
            isolation_type=isolation_type,
            isolation_status=isolation_status,
            tenant_model=tenant_model,
            isolation_score=isolation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "namespace_isolation_validator.isolation_recorded",
            record_id=record.id,
            isolation_id=isolation_id,
            isolation_type=isolation_type.value,
            isolation_status=isolation_status.value,
        )
        return record

    def get_isolation(self, record_id: str) -> IsolationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_isolations(
        self,
        isolation_type: IsolationType | None = None,
        isolation_status: IsolationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IsolationRecord]:
        results = list(self._records)
        if isolation_type is not None:
            results = [r for r in results if r.isolation_type == isolation_type]
        if isolation_status is not None:
            results = [r for r in results if r.isolation_status == isolation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        isolation_id: str,
        isolation_type: IsolationType = IsolationType.NETWORK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IsolationAnalysis:
        analysis = IsolationAnalysis(
            isolation_id=isolation_id,
            isolation_type=isolation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "namespace_isolation_validator.analysis_added",
            isolation_id=isolation_id,
            isolation_type=isolation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by isolation_type; return count and avg isolation_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.isolation_type.value
            type_data.setdefault(key, []).append(r.isolation_score)
        result: dict[str, Any] = {}
        for iso_type, scores in type_data.items():
            result[iso_type] = {
                "count": len(scores),
                "avg_isolation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_isolation_gaps(self) -> list[dict[str, Any]]:
        """Return records where isolation_score < isolation_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.isolation_score < self._isolation_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "isolation_id": r.isolation_id,
                        "isolation_type": r.isolation_type.value,
                        "isolation_score": r.isolation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["isolation_score"])

    def rank_by_isolation(self) -> list[dict[str, Any]]:
        """Group by service, avg isolation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.isolation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_isolation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_isolation_score"])
        return results

    def detect_isolation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> NamespaceIsolationReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_tenant_model: dict[str, int] = {}
        for r in self._records:
            by_type[r.isolation_type.value] = by_type.get(r.isolation_type.value, 0) + 1
            by_status[r.isolation_status.value] = by_status.get(r.isolation_status.value, 0) + 1
            by_tenant_model[r.tenant_model.value] = by_tenant_model.get(r.tenant_model.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.isolation_score < self._isolation_gap_threshold
        )
        scores = [r.isolation_score for r in self._records]
        avg_isolation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_isolation_gaps()
        top_gaps = [o["isolation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} isolation(s) below threshold ({self._isolation_gap_threshold})"
            )
        if self._records and avg_isolation_score < self._isolation_gap_threshold:
            recs.append(
                f"Avg isolation score {avg_isolation_score} below threshold "
                f"({self._isolation_gap_threshold})"
            )
        if not recs:
            recs.append("Namespace isolation validation is healthy")
        return NamespaceIsolationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_isolation_score=avg_isolation_score,
            by_type=by_type,
            by_status=by_status,
            by_tenant_model=by_tenant_model,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("namespace_isolation_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.isolation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "isolation_gap_threshold": self._isolation_gap_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
