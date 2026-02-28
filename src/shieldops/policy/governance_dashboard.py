"""Governance Dashboard — aggregate platform governance metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GovernanceArea(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    COST = "cost"
    RELIABILITY = "reliability"
    OPERATIONAL = "operational"


class GovernanceStatus(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_ATTENTION = "needs_attention"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


class GovernanceTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    area_name: str = ""
    area: GovernanceArea = GovernanceArea.SECURITY
    status: GovernanceStatus = GovernanceStatus.GOOD
    trend: GovernanceTrend = GovernanceTrend.STABLE
    score_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernancePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    area: GovernanceArea = GovernanceArea.SECURITY
    status: GovernanceStatus = GovernanceStatus.GOOD
    min_score_pct: float = 70.0
    review_cadence_days: float = 7.0
    created_at: float = Field(default_factory=time.time)


class GovernanceDashboardReport(BaseModel):
    total_assessments: int = 0
    total_policies: int = 0
    excellent_rate_pct: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformGovernanceDashboard:
    """Aggregate platform governance metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        min_governance_score_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_governance_score_pct = min_governance_score_pct
        self._records: list[GovernanceRecord] = []
        self._policies: list[GovernancePolicy] = []
        logger.info(
            "governance_dashboard.initialized",
            max_records=max_records,
            min_governance_score_pct=(min_governance_score_pct),
        )

    # -- record / get / list ----------------------------------------

    def record_assessment(
        self,
        area_name: str,
        area: GovernanceArea = (GovernanceArea.SECURITY),
        status: GovernanceStatus = (GovernanceStatus.GOOD),
        trend: GovernanceTrend = (GovernanceTrend.STABLE),
        score_pct: float = 0.0,
        details: str = "",
    ) -> GovernanceRecord:
        record = GovernanceRecord(
            area_name=area_name,
            area=area,
            status=status,
            trend=trend,
            score_pct=score_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "governance_dashboard.assessment_recorded",
            record_id=record.id,
            area_name=area_name,
            area=area.value,
            status=status.value,
        )
        return record

    def get_assessment(self, record_id: str) -> GovernanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        area_name: str | None = None,
        area: GovernanceArea | None = None,
        limit: int = 50,
    ) -> list[GovernanceRecord]:
        results = list(self._records)
        if area_name is not None:
            results = [r for r in results if r.area_name == area_name]
        if area is not None:
            results = [r for r in results if r.area == area]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        area: GovernanceArea = (GovernanceArea.SECURITY),
        status: GovernanceStatus = (GovernanceStatus.GOOD),
        min_score_pct: float = 70.0,
        review_cadence_days: float = 7.0,
    ) -> GovernancePolicy:
        policy = GovernancePolicy(
            policy_name=policy_name,
            area=area,
            status=status,
            min_score_pct=min_score_pct,
            review_cadence_days=review_cadence_days,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "governance_dashboard.policy_added",
            policy_name=policy_name,
            area=area.value,
            status=status.value,
        )
        return policy

    # -- domain operations ------------------------------------------

    def analyze_governance_health(self, area_name: str) -> dict[str, Any]:
        """Analyze governance health for an area."""
        records = [r for r in self._records if r.area_name == area_name]
        if not records:
            return {
                "area_name": area_name,
                "status": "no_data",
            }
        excellent_count = sum(
            1
            for r in records
            if r.status
            in (
                GovernanceStatus.EXCELLENT,
                GovernanceStatus.GOOD,
            )
        )
        excellent_rate = round(excellent_count / len(records) * 100, 2)
        avg_score = round(
            sum(r.score_pct for r in records) / len(records),
            2,
        )
        return {
            "area_name": area_name,
            "assessment_count": len(records),
            "excellent_count": excellent_count,
            "excellent_rate": excellent_rate,
            "avg_score": avg_score,
            "meets_threshold": (avg_score >= self._min_governance_score_pct),
        }

    def identify_at_risk_areas(
        self,
    ) -> list[dict[str, Any]]:
        """Find areas with repeated at-risk status."""
        risk_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                GovernanceStatus.AT_RISK,
                GovernanceStatus.CRITICAL,
            ):
                risk_counts[r.area_name] = risk_counts.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area, count in risk_counts.items():
            if count > 1:
                results.append(
                    {
                        "area_name": area,
                        "at_risk_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["at_risk_count"],
            reverse=True,
        )
        return results

    def rank_by_governance_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank areas by avg score descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.area_name] = totals.get(r.area_name, 0.0) + r.score_pct
            counts[r.area_name] = counts.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area in totals:
            avg = round(totals[area] / counts[area], 2)
            results.append(
                {
                    "area_name": area,
                    "avg_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_score"],
            reverse=True,
        )
        return results

    def detect_governance_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect areas with >3 non-EXCELLENT/GOOD."""
        non_good: dict[str, int] = {}
        for r in self._records:
            if r.status not in (
                GovernanceStatus.EXCELLENT,
                GovernanceStatus.GOOD,
            ):
                non_good[r.area_name] = non_good.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area, count in non_good.items():
            if count > 3:
                results.append(
                    {
                        "area_name": area,
                        "non_good_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_good_count"],
            reverse=True,
        )
        return results

    # -- report / stats ---------------------------------------------

    def generate_report(
        self,
    ) -> GovernanceDashboardReport:
        by_area: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_area[r.area.value] = by_area.get(r.area.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        excellent_count = sum(
            1
            for r in self._records
            if r.status
            in (
                GovernanceStatus.EXCELLENT,
                GovernanceStatus.GOOD,
            )
        )
        excellent_rate = (
            round(
                excellent_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        critical = sum(1 for d in self.identify_at_risk_areas())
        recs: list[str] = []
        if self._records and excellent_rate < 80.0:
            recs.append(f"Excellent rate {excellent_rate}% is below 80.0% threshold")
        if critical > 0:
            recs.append(f"{critical} area(s) with repeated at-risk status")
        gaps = len(self.detect_governance_gaps())
        if gaps > 0:
            recs.append(f"{gaps} area(s) detected with governance gaps")
        if not recs:
            recs.append("Platform governance is healthy and well-managed")
        return GovernanceDashboardReport(
            total_assessments=len(self._records),
            total_policies=len(self._policies),
            excellent_rate_pct=excellent_rate,
            by_area=by_area,
            by_status=by_status,
            critical_count=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("governance_dashboard.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_policies": len(self._policies),
            "min_governance_score_pct": (self._min_governance_score_pct),
            "area_distribution": area_dist,
            "unique_areas": len({r.area_name for r in self._records}),
        }
