"""Compliance Automation Gap Analyzer
compute automation potential, detect manual bottlenecks,
rank controls by automation ROI."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationLevel(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL = "manual"
    NOT_APPLICABLE = "not_applicable"


class GapType(StrEnum):
    TOOLING = "tooling"
    INTEGRATION = "integration"
    PROCESS = "process"
    SKILL = "skill"


class RoiCategory(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGATIVE = "negative"


# --- Models ---


class AutomationGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    automation_level: AutomationLevel = AutomationLevel.MANUAL
    gap_type: GapType = GapType.TOOLING
    roi_category: RoiCategory = RoiCategory.MEDIUM
    automation_potential: float = 0.0
    manual_hours: float = 0.0
    estimated_savings: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationGapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    automation_level: AutomationLevel = AutomationLevel.MANUAL
    computed_potential: float = 0.0
    is_bottleneck: bool = False
    roi_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_automation_potential: float = 0.0
    by_automation_level: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    by_roi_category: dict[str, int] = Field(default_factory=dict)
    manual_bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAutomationGapAnalyzer:
    """Compute automation potential, detect manual
    bottlenecks, rank controls by automation ROI."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AutomationGapRecord] = []
        self._analyses: dict[str, AutomationGapAnalysis] = {}
        logger.info(
            "compliance_automation_gap_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        control_id: str = "",
        automation_level: AutomationLevel = AutomationLevel.MANUAL,
        gap_type: GapType = GapType.TOOLING,
        roi_category: RoiCategory = RoiCategory.MEDIUM,
        automation_potential: float = 0.0,
        manual_hours: float = 0.0,
        estimated_savings: float = 0.0,
        description: str = "",
    ) -> AutomationGapRecord:
        record = AutomationGapRecord(
            control_id=control_id,
            automation_level=automation_level,
            gap_type=gap_type,
            roi_category=roi_category,
            automation_potential=automation_potential,
            manual_hours=manual_hours,
            estimated_savings=estimated_savings,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_automation_gap.record_added",
            record_id=record.id,
            control_id=control_id,
        )
        return record

    def process(self, key: str) -> AutomationGapAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_bottleneck = rec.automation_level == AutomationLevel.MANUAL and rec.manual_hours > 10
        roi = round(rec.estimated_savings / max(rec.manual_hours, 1.0), 2)
        analysis = AutomationGapAnalysis(
            control_id=rec.control_id,
            automation_level=rec.automation_level,
            computed_potential=round(rec.automation_potential, 2),
            is_bottleneck=is_bottleneck,
            roi_score=roi,
            description=f"Control {rec.control_id} potential {rec.automation_potential}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AutomationGapReport:
        by_al: dict[str, int] = {}
        by_gt: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.automation_level.value
            by_al[k] = by_al.get(k, 0) + 1
            k2 = r.gap_type.value
            by_gt[k2] = by_gt.get(k2, 0) + 1
            k3 = r.roi_category.value
            by_rc[k3] = by_rc.get(k3, 0) + 1
            scores.append(r.automation_potential)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        bottlenecks = list(
            {r.control_id for r in self._records if r.automation_level == AutomationLevel.MANUAL}
        )[:10]
        recs: list[str] = []
        if bottlenecks:
            recs.append(f"{len(bottlenecks)} manual bottlenecks detected")
        if not recs:
            recs.append("All controls have adequate automation")
        return AutomationGapReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_automation_potential=avg,
            by_automation_level=by_al,
            by_gap_type=by_gt,
            by_roi_category=by_rc,
            manual_bottlenecks=bottlenecks,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        al_dist: dict[str, int] = {}
        for r in self._records:
            k = r.automation_level.value
            al_dist[k] = al_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "automation_level_distribution": al_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("compliance_automation_gap_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_automation_potential(
        self,
    ) -> list[dict[str, Any]]:
        """Compute automation potential per control."""
        control_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.control_id not in control_data:
                control_data[r.control_id] = {
                    "potential": r.automation_potential,
                    "manual_hours": r.manual_hours,
                    "level": r.automation_level.value,
                }
        results: list[dict[str, Any]] = []
        for cid, data in control_data.items():
            results.append(
                {
                    "control_id": cid,
                    "automation_level": data["level"],
                    "automation_potential": data["potential"],
                    "manual_hours": data["manual_hours"],
                }
            )
        results.sort(key=lambda x: x["automation_potential"], reverse=True)
        return results

    def detect_manual_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect controls that are manual bottlenecks."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.automation_level == AutomationLevel.MANUAL
                and r.manual_hours > 0
                and r.control_id not in seen
            ):
                seen.add(r.control_id)
                results.append(
                    {
                        "control_id": r.control_id,
                        "gap_type": r.gap_type.value,
                        "manual_hours": r.manual_hours,
                        "automation_potential": r.automation_potential,
                    }
                )
        results.sort(key=lambda x: x["manual_hours"], reverse=True)
        return results

    def rank_controls_by_automation_roi(
        self,
    ) -> list[dict[str, Any]]:
        """Rank controls by automation ROI."""
        control_roi: dict[str, float] = {}
        control_levels: dict[str, str] = {}
        for r in self._records:
            roi = r.estimated_savings / max(r.manual_hours, 1.0)
            control_roi[r.control_id] = max(control_roi.get(r.control_id, 0.0), roi)
            control_levels[r.control_id] = r.automation_level.value
        results: list[dict[str, Any]] = []
        for cid, roi in control_roi.items():
            results.append(
                {
                    "control_id": cid,
                    "automation_level": control_levels[cid],
                    "roi_score": round(roi, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["roi_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
