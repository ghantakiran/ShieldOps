"""Compliance Automation Scorer — score compliance automation coverage and ROI."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationScope(StrEnum):
    EVIDENCE_COLLECTION = "evidence_collection"
    CONTROL_TESTING = "control_testing"
    REPORTING = "reporting"
    MONITORING = "monitoring"
    REMEDIATION = "remediation"


class AutomationMaturity(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    MOSTLY_AUTOMATED = "mostly_automated"
    PARTIALLY_AUTOMATED = "partially_automated"
    MANUAL_WITH_TOOLS = "manual_with_tools"
    FULLY_MANUAL = "fully_manual"


class ROICategory(StrEnum):
    HIGH_ROI = "high_roi"
    MODERATE_ROI = "moderate_roi"
    LOW_ROI = "low_roi"
    BREAK_EVEN = "break_even"
    NEGATIVE_ROI = "negative_roi"


# --- Models ---


class AutomationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    process_name: str = ""
    automation_scope: AutomationScope = AutomationScope.EVIDENCE_COLLECTION
    automation_maturity: AutomationMaturity = AutomationMaturity.FULLY_AUTOMATED
    roi_category: ROICategory = ROICategory.HIGH_ROI
    automation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    process_name: str = ""
    automation_scope: AutomationScope = AutomationScope.EVIDENCE_COLLECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_automation_count: int = 0
    avg_automation_score: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    by_roi: dict[str, int] = Field(default_factory=dict)
    top_low_automation: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAutomationScorer:
    """Score compliance automation coverage and measure ROI across processes."""

    def __init__(
        self,
        max_records: int = 200000,
        automation_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._automation_threshold = automation_threshold
        self._records: list[AutomationRecord] = []
        self._analyses: list[AutomationAnalysis] = []
        logger.info(
            "compliance_automation_scorer.initialized",
            max_records=max_records,
            automation_threshold=automation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_automation(
        self,
        process_name: str,
        automation_scope: AutomationScope = AutomationScope.EVIDENCE_COLLECTION,
        automation_maturity: AutomationMaturity = AutomationMaturity.FULLY_AUTOMATED,
        roi_category: ROICategory = ROICategory.HIGH_ROI,
        automation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutomationRecord:
        record = AutomationRecord(
            process_name=process_name,
            automation_scope=automation_scope,
            automation_maturity=automation_maturity,
            roi_category=roi_category,
            automation_score=automation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_automation_scorer.automation_recorded",
            record_id=record.id,
            process_name=process_name,
            automation_scope=automation_scope.value,
            automation_maturity=automation_maturity.value,
        )
        return record

    def get_automation(self, record_id: str) -> AutomationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_automations(
        self,
        automation_scope: AutomationScope | None = None,
        automation_maturity: AutomationMaturity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AutomationRecord]:
        results = list(self._records)
        if automation_scope is not None:
            results = [r for r in results if r.automation_scope == automation_scope]
        if automation_maturity is not None:
            results = [r for r in results if r.automation_maturity == automation_maturity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        process_name: str,
        automation_scope: AutomationScope = AutomationScope.EVIDENCE_COLLECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AutomationAnalysis:
        analysis = AutomationAnalysis(
            process_name=process_name,
            automation_scope=automation_scope,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "compliance_automation_scorer.analysis_added",
            process_name=process_name,
            automation_scope=automation_scope.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_automation_distribution(self) -> dict[str, Any]:
        """Group by automation_scope; return count and avg automation_score."""
        scope_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.automation_scope.value
            scope_data.setdefault(key, []).append(r.automation_score)
        result: dict[str, Any] = {}
        for scope, scores in scope_data.items():
            result[scope] = {
                "count": len(scores),
                "avg_automation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_automation_processes(self) -> list[dict[str, Any]]:
        """Return records where automation_score < automation_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.automation_score < self._automation_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "process_name": r.process_name,
                        "automation_scope": r.automation_scope.value,
                        "automation_score": r.automation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["automation_score"])

    def rank_by_automation(self) -> list[dict[str, Any]]:
        """Group by service, avg automation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.automation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_automation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_automation_score"])
        return results

    def detect_automation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AutomationReport:
        by_scope: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        by_roi: dict[str, int] = {}
        for r in self._records:
            by_scope[r.automation_scope.value] = by_scope.get(r.automation_scope.value, 0) + 1
            by_maturity[r.automation_maturity.value] = (
                by_maturity.get(r.automation_maturity.value, 0) + 1
            )
            by_roi[r.roi_category.value] = by_roi.get(r.roi_category.value, 0) + 1
        low_automation_count = sum(
            1 for r in self._records if r.automation_score < self._automation_threshold
        )
        scores = [r.automation_score for r in self._records]
        avg_automation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_automation_processes()
        top_low_automation = [o["process_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_automation_count > 0:
            recs.append(
                f"{low_automation_count} process(es) below automation threshold "
                f"({self._automation_threshold})"
            )
        if self._records and avg_automation_score < self._automation_threshold:
            recs.append(
                f"Avg automation score {avg_automation_score} below threshold "
                f"({self._automation_threshold})"
            )
        if not recs:
            recs.append("Compliance automation coverage is healthy")
        return AutomationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_automation_count=low_automation_count,
            avg_automation_score=avg_automation_score,
            by_scope=by_scope,
            by_maturity=by_maturity,
            by_roi=by_roi,
            top_low_automation=top_low_automation,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("compliance_automation_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.automation_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "automation_threshold": self._automation_threshold,
            "scope_distribution": scope_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
