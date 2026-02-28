"""Vendor Lock-in Analyzer — analyze and track vendor lock-in risks across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LockinCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORKING = "networking"
    PROPRIETARY_SERVICE = "proprietary_service"


class LockinRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class MigrationComplexity(StrEnum):
    EXTREME = "extreme"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    TRIVIAL = "trivial"


# --- Models ---


class LockinRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    service_name: str = ""
    category: LockinCategory = LockinCategory.COMPUTE
    risk: LockinRisk = LockinRisk.MODERATE
    complexity: MigrationComplexity = MigrationComplexity.MODERATE
    risk_score: float = 0.0
    monthly_spend: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LockinAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    category: LockinCategory = LockinCategory.COMPUTE
    risk: LockinRisk = LockinRisk.MODERATE
    complexity: MigrationComplexity = MigrationComplexity.MODERATE
    estimated_exit_cost: float = 0.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorLockinReport(BaseModel):
    total_records: int = 0
    total_assessments: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    critical_lockin_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class VendorLockinAnalyzer:
    """Analyze and track vendor lock-in risks across services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._max_risk_score = max_risk_score
        self._records: list[LockinRecord] = []
        self._assessments: list[LockinAssessment] = []
        logger.info(
            "vendor_lockin.initialized",
            max_records=max_records,
            max_risk_score=max_risk_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_lockin(
        self,
        vendor_name: str,
        service_name: str,
        category: LockinCategory = LockinCategory.COMPUTE,
        risk: LockinRisk = LockinRisk.MODERATE,
        complexity: MigrationComplexity = MigrationComplexity.MODERATE,
        risk_score: float = 0.0,
        monthly_spend: float = 0.0,
        details: str = "",
    ) -> LockinRecord:
        record = LockinRecord(
            vendor_name=vendor_name,
            service_name=service_name,
            category=category,
            risk=risk,
            complexity=complexity,
            risk_score=risk_score,
            monthly_spend=monthly_spend,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "vendor_lockin.lockin_recorded",
            record_id=record.id,
            vendor_name=vendor_name,
            category=category.value,
            risk=risk.value,
        )
        return record

    def get_lockin(self, record_id: str) -> LockinRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lockins(
        self,
        vendor_name: str | None = None,
        category: LockinCategory | None = None,
        limit: int = 50,
    ) -> list[LockinRecord]:
        results = list(self._records)
        if vendor_name is not None:
            results = [r for r in results if r.vendor_name == vendor_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_assessment(
        self,
        vendor_name: str,
        category: LockinCategory = LockinCategory.COMPUTE,
        risk: LockinRisk = LockinRisk.MODERATE,
        complexity: MigrationComplexity = MigrationComplexity.MODERATE,
        estimated_exit_cost: float = 0.0,
        notes: str = "",
    ) -> LockinAssessment:
        assessment = LockinAssessment(
            vendor_name=vendor_name,
            category=category,
            risk=risk,
            complexity=complexity,
            estimated_exit_cost=estimated_exit_cost,
            notes=notes,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "vendor_lockin.assessment_added",
            vendor_name=vendor_name,
            risk=risk.value,
            complexity=complexity.value,
        )
        return assessment

    # -- domain operations -----------------------------------------------

    def analyze_lockin_by_vendor(self, vendor_name: str) -> dict[str, Any]:
        """Analyze lock-in profile for a specific vendor."""
        records = [r for r in self._records if r.vendor_name == vendor_name]
        if not records:
            return {"vendor_name": vendor_name, "status": "no_data"}
        avg_risk_score = round(sum(r.risk_score for r in records) / len(records), 2)
        total_spend = round(sum(r.monthly_spend for r in records), 2)
        category_counts: dict[str, int] = {}
        for r in records:
            category_counts[r.category.value] = category_counts.get(r.category.value, 0) + 1
        return {
            "vendor_name": vendor_name,
            "total_services": len(records),
            "avg_risk_score": avg_risk_score,
            "total_monthly_spend": total_spend,
            "exceeds_threshold": avg_risk_score >= self._max_risk_score,
            "by_category": category_counts,
        }

    def identify_critical_lockins(self) -> list[dict[str, Any]]:
        """Find records with CRITICAL or HIGH lock-in risk."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk in (LockinRisk.CRITICAL, LockinRisk.HIGH):
                results.append(
                    {
                        "record_id": r.id,
                        "vendor_name": r.vendor_name,
                        "service_name": r.service_name,
                        "category": r.category.value,
                        "risk": r.risk.value,
                        "risk_score": r.risk_score,
                        "monthly_spend": r.monthly_spend,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank all records by risk score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "vendor_name": r.vendor_name,
                    "service_name": r.service_name,
                    "risk_score": r.risk_score,
                    "risk": r.risk.value,
                    "complexity": r.complexity.value,
                }
            )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def detect_lockin_trends(self) -> list[dict[str, Any]]:
        """Detect vendors with increasing risk scores over time."""
        vendor_scores: dict[str, list[float]] = {}
        for r in self._records:
            vendor_scores.setdefault(r.vendor_name, []).append(r.risk_score)
        trends: list[dict[str, Any]] = []
        for vendor, scores in vendor_scores.items():
            if len(scores) >= 2:
                trend = scores[-1] - scores[0]
                trends.append(
                    {
                        "vendor_name": vendor,
                        "score_delta": round(trend, 2),
                        "trending_up": trend > 0,
                        "record_count": len(scores),
                        "latest_score": scores[-1],
                    }
                )
        trends.sort(key=lambda x: x["score_delta"], reverse=True)
        return trends

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> VendorLockinReport:
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_risk[r.risk.value] = by_risk.get(r.risk.value, 0) + 1
        avg_risk = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        critical_count = sum(
            1 for r in self._records if r.risk in (LockinRisk.CRITICAL, LockinRisk.HIGH)
        )
        recs: list[str] = []
        if avg_risk >= self._max_risk_score:
            recs.append(f"Average risk score {avg_risk} exceeds threshold {self._max_risk_score}")
        if critical_count > 0:
            recs.append(f"{critical_count} service(s) with critical or high lock-in risk")
        trending = [t for t in self.detect_lockin_trends() if t["trending_up"]]
        if trending:
            recs.append(f"{len(trending)} vendor(s) showing increasing lock-in risk")
        if not recs:
            recs.append("Vendor lock-in risk is within acceptable thresholds")
        return VendorLockinReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            avg_risk_score=avg_risk,
            by_category=by_category,
            by_risk=by_risk,
            critical_lockin_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("vendor_lockin.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_risk_score": self._max_risk_score,
            "category_distribution": category_dist,
            "unique_vendors": len({r.vendor_name for r in self._records}),
        }
