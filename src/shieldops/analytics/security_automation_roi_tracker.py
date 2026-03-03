"""Security Automation ROI Tracker — track return on investment for security automation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationType(StrEnum):
    PLAYBOOK = "playbook"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    ML_MODEL = "ml_model"
    CUSTOM = "custom"


class ROIMetric(StrEnum):
    TIME_SAVED = "time_saved"
    COST_REDUCED = "cost_reduced"
    INCIDENTS_PREVENTED = "incidents_prevented"
    ACCURACY_IMPROVED = "accuracy_improved"
    COVERAGE_EXPANDED = "coverage_expanded"


class InvestmentPhase(StrEnum):
    PILOT = "pilot"
    SCALING = "scaling"
    MATURE = "mature"
    OPTIMIZING = "optimizing"
    DEPRECATED = "deprecated"


# --- Models ---


class ROIRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    roi_id: str = ""
    automation_type: AutomationType = AutomationType.PLAYBOOK
    roi_metric: ROIMetric = ROIMetric.TIME_SAVED
    investment_phase: InvestmentPhase = InvestmentPhase.PILOT
    roi_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ROIAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    roi_id: str = ""
    automation_type: AutomationType = AutomationType.PLAYBOOK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ROIReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_roi_score: float = 0.0
    by_automation: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityAutomationROITracker:
    """Track return on investment for security automation initiatives."""

    def __init__(
        self,
        max_records: int = 200000,
        roi_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._roi_threshold = roi_threshold
        self._records: list[ROIRecord] = []
        self._analyses: list[ROIAnalysis] = []
        logger.info(
            "security_automation_roi_tracker.initialized",
            max_records=max_records,
            roi_threshold=roi_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_roi(
        self,
        roi_id: str,
        automation_type: AutomationType = AutomationType.PLAYBOOK,
        roi_metric: ROIMetric = ROIMetric.TIME_SAVED,
        investment_phase: InvestmentPhase = InvestmentPhase.PILOT,
        roi_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ROIRecord:
        record = ROIRecord(
            roi_id=roi_id,
            automation_type=automation_type,
            roi_metric=roi_metric,
            investment_phase=investment_phase,
            roi_score=roi_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_automation_roi_tracker.roi_recorded",
            record_id=record.id,
            roi_id=roi_id,
            automation_type=automation_type.value,
            roi_metric=roi_metric.value,
        )
        return record

    def get_roi(self, record_id: str) -> ROIRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rois(
        self,
        automation_type: AutomationType | None = None,
        roi_metric: ROIMetric | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ROIRecord]:
        results = list(self._records)
        if automation_type is not None:
            results = [r for r in results if r.automation_type == automation_type]
        if roi_metric is not None:
            results = [r for r in results if r.roi_metric == roi_metric]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        roi_id: str,
        automation_type: AutomationType = AutomationType.PLAYBOOK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ROIAnalysis:
        analysis = ROIAnalysis(
            roi_id=roi_id,
            automation_type=automation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_automation_roi_tracker.analysis_added",
            roi_id=roi_id,
            automation_type=automation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_automation_distribution(self) -> dict[str, Any]:
        automation_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.automation_type.value
            automation_data.setdefault(key, []).append(r.roi_score)
        result: dict[str, Any] = {}
        for automation, scores in automation_data.items():
            result[automation] = {
                "count": len(scores),
                "avg_roi_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_roi_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.roi_score < self._roi_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "roi_id": r.roi_id,
                        "automation_type": r.automation_type.value,
                        "roi_score": r.roi_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["roi_score"])

    def rank_by_roi(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.roi_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_roi_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_roi_score"])
        return results

    def detect_roi_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ROIReport:
        by_automation: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        for r in self._records:
            by_automation[r.automation_type.value] = (
                by_automation.get(r.automation_type.value, 0) + 1
            )
            by_metric[r.roi_metric.value] = by_metric.get(r.roi_metric.value, 0) + 1
            by_phase[r.investment_phase.value] = by_phase.get(r.investment_phase.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.roi_score < self._roi_threshold)
        scores = [r.roi_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_roi_gaps()
        top_gaps = [o["roi_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} automation(s) below ROI threshold ({self._roi_threshold})")
        if self._records and avg_score < self._roi_threshold:
            recs.append(f"Avg ROI score {avg_score} below threshold ({self._roi_threshold})")
        if not recs:
            recs.append("Security automation ROI is healthy")
        return ROIReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_roi_score=avg_score,
            by_automation=by_automation,
            by_metric=by_metric,
            by_phase=by_phase,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_automation_roi_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        automation_dist: dict[str, int] = {}
        for r in self._records:
            key = r.automation_type.value
            automation_dist[key] = automation_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "roi_threshold": self._roi_threshold,
            "automation_distribution": automation_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
