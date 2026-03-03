"""Data Retention Enforcer — enforce data retention policies across data categories."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RetentionPolicy(StrEnum):
    LEGAL_HOLD = "legal_hold"
    REGULATORY = "regulatory"
    BUSINESS = "business"
    ARCHIVE = "archive"
    DELETE = "delete"


class DataCategory(StrEnum):
    PERSONAL = "personal"
    FINANCIAL = "financial"
    HEALTH = "health"
    BIOMETRIC = "biometric"
    BEHAVIORAL = "behavioral"


class EnforcementStatus(StrEnum):
    ENFORCED = "enforced"
    OVERDUE = "overdue"
    EXEMPT = "exempt"
    PENDING = "pending"
    FAILED = "failed"


# --- Models ---


class RetentionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    retention_policy: RetentionPolicy = RetentionPolicy.REGULATORY
    data_category: DataCategory = DataCategory.PERSONAL
    enforcement_status: EnforcementStatus = EnforcementStatus.ENFORCED
    compliance_score: float = 0.0
    storage_system: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    data_category: DataCategory = DataCategory.PERSONAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_policy: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataRetentionEnforcer:
    """Enforce data retention policies; track overdue and non-compliant assets."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RetentionRecord] = []
        self._analyses: list[RetentionAnalysis] = []
        logger.info(
            "data_retention_enforcer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_retention(
        self,
        data_asset: str,
        retention_policy: RetentionPolicy = RetentionPolicy.REGULATORY,
        data_category: DataCategory = DataCategory.PERSONAL,
        enforcement_status: EnforcementStatus = EnforcementStatus.ENFORCED,
        compliance_score: float = 0.0,
        storage_system: str = "",
        data_owner: str = "",
    ) -> RetentionRecord:
        record = RetentionRecord(
            data_asset=data_asset,
            retention_policy=retention_policy,
            data_category=data_category,
            enforcement_status=enforcement_status,
            compliance_score=compliance_score,
            storage_system=storage_system,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_retention_enforcer.retention_recorded",
            record_id=record.id,
            data_asset=data_asset,
            retention_policy=retention_policy.value,
            data_category=data_category.value,
        )
        return record

    def get_retention(self, record_id: str) -> RetentionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_retentions(
        self,
        retention_policy: RetentionPolicy | None = None,
        data_category: DataCategory | None = None,
        data_owner: str | None = None,
        limit: int = 50,
    ) -> list[RetentionRecord]:
        results = list(self._records)
        if retention_policy is not None:
            results = [r for r in results if r.retention_policy == retention_policy]
        if data_category is not None:
            results = [r for r in results if r.data_category == data_category]
        if data_owner is not None:
            results = [r for r in results if r.data_owner == data_owner]
        return results[-limit:]

    def add_analysis(
        self,
        data_asset: str,
        data_category: DataCategory = DataCategory.PERSONAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RetentionAnalysis:
        analysis = RetentionAnalysis(
            data_asset=data_asset,
            data_category=data_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_retention_enforcer.analysis_added",
            data_asset=data_asset,
            data_category=data_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        """Group by data_category; return count and avg compliance_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.data_category.value
            cat_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_retention_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "data_asset": r.data_asset,
                        "data_category": r.data_category.value,
                        "compliance_score": r.compliance_score,
                        "storage_system": r.storage_system,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by storage_system, avg compliance_score, sort ascending."""
        sys_scores: dict[str, list[float]] = {}
        for r in self._records:
            sys_scores.setdefault(r.storage_system, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for sys, scores in sys_scores.items():
            results.append(
                {
                    "storage_system": sys,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_retention_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RetentionComplianceReport:
        by_policy: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_policy[r.retention_policy.value] = by_policy.get(r.retention_policy.value, 0) + 1
            by_category[r.data_category.value] = by_category.get(r.data_category.value, 0) + 1
            by_status[r.enforcement_status.value] = by_status.get(r.enforcement_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.compliance_score < self._threshold)
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_retention_gaps()
        top_gaps = [o["data_asset"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} asset(s) below retention compliance threshold ({self._threshold})"
            )
        if self._records and avg_compliance_score < self._threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Data retention compliance is healthy")
        return RetentionComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_policy=by_policy,
            by_category=by_category,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_retention_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": cat_dist,
            "unique_systems": len({r.storage_system for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }
