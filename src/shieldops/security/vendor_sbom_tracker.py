"""Vendor SBOM Tracker — track vendor-provided SBOM completeness and update cadence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VendorTier(StrEnum):
    STRATEGIC = "strategic"
    PREFERRED = "preferred"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class SBOMCompleteness(StrEnum):
    COMPLETE = "complete"
    SUBSTANTIAL = "substantial"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class UpdateFrequency(StrEnum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# --- Models ---


class VendorSBOMRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.APPROVED
    sbom_completeness: SBOMCompleteness = SBOMCompleteness.COMPLETE
    update_frequency: UpdateFrequency = UpdateFrequency.WEEKLY
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorSBOMAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_name: str = ""
    vendor_tier: VendorTier = VendorTier.APPROVED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorSBOMReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_completeness_score: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_completeness: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class VendorSBOMTracker:
    """Track vendor SBOM completeness, tier classification, and update cadence."""

    def __init__(
        self,
        max_records: int = 200000,
        completeness_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._completeness_gap_threshold = completeness_gap_threshold
        self._records: list[VendorSBOMRecord] = []
        self._analyses: list[VendorSBOMAnalysis] = []
        logger.info(
            "vendor_sbom_tracker.initialized",
            max_records=max_records,
            completeness_gap_threshold=completeness_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_vendor_sbom(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.APPROVED,
        sbom_completeness: SBOMCompleteness = SBOMCompleteness.COMPLETE,
        update_frequency: UpdateFrequency = UpdateFrequency.WEEKLY,
        completeness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VendorSBOMRecord:
        record = VendorSBOMRecord(
            vendor_name=vendor_name,
            vendor_tier=vendor_tier,
            sbom_completeness=sbom_completeness,
            update_frequency=update_frequency,
            completeness_score=completeness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "vendor_sbom_tracker.vendor_sbom_recorded",
            record_id=record.id,
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            sbom_completeness=sbom_completeness.value,
        )
        return record

    def get_vendor_sbom(self, record_id: str) -> VendorSBOMRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_vendor_sboms(
        self,
        vendor_tier: VendorTier | None = None,
        sbom_completeness: SBOMCompleteness | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VendorSBOMRecord]:
        results = list(self._records)
        if vendor_tier is not None:
            results = [r for r in results if r.vendor_tier == vendor_tier]
        if sbom_completeness is not None:
            results = [r for r in results if r.sbom_completeness == sbom_completeness]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        vendor_name: str,
        vendor_tier: VendorTier = VendorTier.APPROVED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VendorSBOMAnalysis:
        analysis = VendorSBOMAnalysis(
            vendor_name=vendor_name,
            vendor_tier=vendor_tier,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "vendor_sbom_tracker.analysis_added",
            vendor_name=vendor_name,
            vendor_tier=vendor_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_tier_distribution(self) -> dict[str, Any]:
        """Group by vendor_tier; return count and avg completeness_score."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for tier, scores in tier_data.items():
            result[tier] = {
                "count": len(scores),
                "avg_completeness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_completeness_gaps(self) -> list[dict[str, Any]]:
        """Return records where completeness_score < completeness_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completeness_score < self._completeness_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "vendor_name": r.vendor_name,
                        "vendor_tier": r.vendor_tier.value,
                        "completeness_score": r.completeness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["completeness_score"])

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by service, avg completeness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completeness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_completeness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"])
        return results

    def detect_completeness_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> VendorSBOMReport:
        by_tier: dict[str, int] = {}
        by_completeness: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_tier[r.vendor_tier.value] = by_tier.get(r.vendor_tier.value, 0) + 1
            by_completeness[r.sbom_completeness.value] = (
                by_completeness.get(r.sbom_completeness.value, 0) + 1
            )
            by_frequency[r.update_frequency.value] = (
                by_frequency.get(r.update_frequency.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.completeness_score < self._completeness_gap_threshold
        )
        scores = [r.completeness_score for r in self._records]
        avg_completeness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_completeness_gaps()
        top_gaps = [o["vendor_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} vendor(s) below SBOM completeness threshold "
                f"({self._completeness_gap_threshold})"
            )
        if self._records and avg_completeness_score < self._completeness_gap_threshold:
            recs.append(
                f"Avg completeness score {avg_completeness_score} below threshold "
                f"({self._completeness_gap_threshold})"
            )
        if not recs:
            recs.append("Vendor SBOM completeness is healthy")
        return VendorSBOMReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_completeness_score=avg_completeness_score,
            by_tier=by_tier,
            by_completeness=by_completeness,
            by_frequency=by_frequency,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("vendor_sbom_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.vendor_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "completeness_gap_threshold": self._completeness_gap_threshold,
            "tier_distribution": tier_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
