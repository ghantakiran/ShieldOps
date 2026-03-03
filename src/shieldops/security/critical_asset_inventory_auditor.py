"""Critical Asset Inventory Auditor — audit critical asset inventories across tiers and."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AssetCriticality(StrEnum):
    TIER1_CRITICAL = "tier1_critical"
    TIER2_HIGH = "tier2_high"
    TIER3_MEDIUM = "tier3_medium"
    TIER4_LOW = "tier4_low"
    UNCLASSIFIED = "unclassified"


class AssetCategory(StrEnum):
    DATA_STORE = "data_store"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    IDENTITY = "identity"


class AuditStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    DISPUTED = "disputed"
    PENDING = "pending"


# --- Models ---


class AssetAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    asset_criticality: AssetCriticality = AssetCriticality.TIER1_CRITICAL
    asset_category: AssetCategory = AssetCategory.DATA_STORE
    audit_status: AuditStatus = AuditStatus.CURRENT
    audit_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AssetAuditAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    asset_criticality: AssetCriticality = AssetCriticality.TIER1_CRITICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AssetAuditReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_audit_score: float = 0.0
    by_criticality: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CriticalAssetInventoryAuditor:
    """Audit critical asset inventories across tiers, categories, and audit statuses."""

    def __init__(
        self,
        max_records: int = 200000,
        audit_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._audit_threshold = audit_threshold
        self._records: list[AssetAuditRecord] = []
        self._analyses: list[AssetAuditAnalysis] = []
        logger.info(
            "critical_asset_inventory_auditor.initialized",
            max_records=max_records,
            audit_threshold=audit_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_audit(
        self,
        audit_id: str,
        asset_criticality: AssetCriticality = AssetCriticality.TIER1_CRITICAL,
        asset_category: AssetCategory = AssetCategory.DATA_STORE,
        audit_status: AuditStatus = AuditStatus.CURRENT,
        audit_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AssetAuditRecord:
        record = AssetAuditRecord(
            audit_id=audit_id,
            asset_criticality=asset_criticality,
            asset_category=asset_category,
            audit_status=audit_status,
            audit_score=audit_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "critical_asset_inventory_auditor.audit_recorded",
            record_id=record.id,
            audit_id=audit_id,
            asset_criticality=asset_criticality.value,
            asset_category=asset_category.value,
        )
        return record

    def get_audit(self, record_id: str) -> AssetAuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_audits(
        self,
        asset_criticality: AssetCriticality | None = None,
        asset_category: AssetCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AssetAuditRecord]:
        results = list(self._records)
        if asset_criticality is not None:
            results = [r for r in results if r.asset_criticality == asset_criticality]
        if asset_category is not None:
            results = [r for r in results if r.asset_category == asset_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        audit_id: str,
        asset_criticality: AssetCriticality = AssetCriticality.TIER1_CRITICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AssetAuditAnalysis:
        analysis = AssetAuditAnalysis(
            audit_id=audit_id,
            asset_criticality=asset_criticality,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "critical_asset_inventory_auditor.analysis_added",
            audit_id=audit_id,
            asset_criticality=asset_criticality.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_criticality_distribution(self) -> dict[str, Any]:
        criticality_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.asset_criticality.value
            criticality_data.setdefault(key, []).append(r.audit_score)
        result: dict[str, Any] = {}
        for criticality, scores in criticality_data.items():
            result[criticality] = {
                "count": len(scores),
                "avg_audit_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_audit_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.audit_score < self._audit_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "audit_id": r.audit_id,
                        "asset_criticality": r.asset_criticality.value,
                        "audit_score": r.audit_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["audit_score"])

    def rank_by_audit(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.audit_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_audit_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_audit_score"])
        return results

    def detect_audit_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AssetAuditReport:
        by_criticality: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_criticality[r.asset_criticality.value] = (
                by_criticality.get(r.asset_criticality.value, 0) + 1
            )
            by_category[r.asset_category.value] = by_category.get(r.asset_category.value, 0) + 1
            by_status[r.audit_status.value] = by_status.get(r.audit_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.audit_score < self._audit_threshold)
        scores = [r.audit_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_audit_gaps()
        top_gaps = [o["audit_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} asset(s) below audit threshold ({self._audit_threshold})")
        if self._records and avg_score < self._audit_threshold:
            recs.append(f"Avg audit score {avg_score} below threshold ({self._audit_threshold})")
        if not recs:
            recs.append("Critical asset inventory is healthy")
        return AssetAuditReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_audit_score=avg_score,
            by_criticality=by_criticality,
            by_category=by_category,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("critical_asset_inventory_auditor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        criticality_dist: dict[str, int] = {}
        for r in self._records:
            key = r.asset_criticality.value
            criticality_dist[key] = criticality_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "audit_threshold": self._audit_threshold,
            "criticality_distribution": criticality_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
