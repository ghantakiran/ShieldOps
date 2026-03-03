"""Data Residency Enforcer — enforce data residency rules across regions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Region(StrEnum):
    US = "us"
    EU = "eu"
    APAC = "apac"
    LATAM = "latam"
    GLOBAL = "global"


class ResidencyStatus(StrEnum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    PENDING = "pending"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"


class EnforcementAction(StrEnum):
    BLOCK = "block"
    REDIRECT = "redirect"
    ENCRYPT = "encrypt"
    LOG = "log"
    ALERT = "alert"


# --- Models ---


class ResidencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    region: Region = Region.US
    residency_status: ResidencyStatus = ResidencyStatus.COMPLIANT
    enforcement_action: EnforcementAction = EnforcementAction.LOG
    compliance_score: float = 0.0
    tenant: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class ResidencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    region: Region = Region.US
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResidencyComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_region: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataResidencyEnforcer:
    """Enforce data residency rules; detect violations and trigger enforcement actions."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ResidencyRecord] = []
        self._analyses: list[ResidencyAnalysis] = []
        logger.info(
            "data_residency_enforcer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_residency(
        self,
        data_asset: str,
        region: Region = Region.US,
        residency_status: ResidencyStatus = ResidencyStatus.COMPLIANT,
        enforcement_action: EnforcementAction = EnforcementAction.LOG,
        compliance_score: float = 0.0,
        tenant: str = "",
        data_owner: str = "",
    ) -> ResidencyRecord:
        record = ResidencyRecord(
            data_asset=data_asset,
            region=region,
            residency_status=residency_status,
            enforcement_action=enforcement_action,
            compliance_score=compliance_score,
            tenant=tenant,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_residency_enforcer.residency_recorded",
            record_id=record.id,
            data_asset=data_asset,
            region=region.value,
            residency_status=residency_status.value,
        )
        return record

    def get_residency(self, record_id: str) -> ResidencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_residencies(
        self,
        region: Region | None = None,
        residency_status: ResidencyStatus | None = None,
        tenant: str | None = None,
        limit: int = 50,
    ) -> list[ResidencyRecord]:
        results = list(self._records)
        if region is not None:
            results = [r for r in results if r.region == region]
        if residency_status is not None:
            results = [r for r in results if r.residency_status == residency_status]
        if tenant is not None:
            results = [r for r in results if r.tenant == tenant]
        return results[-limit:]

    def add_analysis(
        self,
        data_asset: str,
        region: Region = Region.US,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResidencyAnalysis:
        analysis = ResidencyAnalysis(
            data_asset=data_asset,
            region=region,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_residency_enforcer.analysis_added",
            data_asset=data_asset,
            region=region.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_region_distribution(self) -> dict[str, Any]:
        """Group by region; return count and avg compliance_score."""
        region_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.region.value
            region_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for reg, scores in region_data.items():
            result[reg] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_residency_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "data_asset": r.data_asset,
                        "region": r.region.value,
                        "compliance_score": r.compliance_score,
                        "tenant": r.tenant,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by tenant, avg compliance_score, sort ascending."""
        tenant_scores: dict[str, list[float]] = {}
        for r in self._records:
            tenant_scores.setdefault(r.tenant, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for tenant, scores in tenant_scores.items():
            results.append(
                {
                    "tenant": tenant,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_residency_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ResidencyComplianceReport:
        by_region: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_region[r.region.value] = by_region.get(r.region.value, 0) + 1
            by_status[r.residency_status.value] = by_status.get(r.residency_status.value, 0) + 1
            by_action[r.enforcement_action.value] = by_action.get(r.enforcement_action.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.compliance_score < self._threshold)
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_residency_gaps()
        top_gaps = [o["data_asset"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} asset(s) below residency compliance threshold ({self._threshold})"
            )
        if self._records and avg_compliance_score < self._threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Data residency compliance is healthy")
        return ResidencyComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_region=by_region,
            by_status=by_status,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_residency_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        region_dist: dict[str, int] = {}
        for r in self._records:
            key = r.region.value
            region_dist[key] = region_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "region_distribution": region_dist,
            "unique_tenants": len({r.tenant for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }
