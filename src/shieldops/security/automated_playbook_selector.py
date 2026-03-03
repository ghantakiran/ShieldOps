"""Automated Playbook Selector — select optimal playbooks based on threat context."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PlaybookCategory(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    THREAT_HUNTING = "threat_hunting"
    REMEDIATION = "remediation"
    INVESTIGATION = "investigation"
    COMPLIANCE = "compliance"


class SelectionCriteria(StrEnum):
    THREAT_TYPE = "threat_type"
    SEVERITY = "severity"
    ASSET_TYPE = "asset_type"
    TEAM = "team"
    HISTORICAL = "historical"


class PlaybookConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL_OVERRIDE = "manual_override"
    UNKNOWN = "unknown"


# --- Models ---


class PlaybookSelectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    selection_id: str = ""
    playbook_category: PlaybookCategory = PlaybookCategory.INCIDENT_RESPONSE
    selection_criteria: SelectionCriteria = SelectionCriteria.THREAT_TYPE
    playbook_confidence: PlaybookConfidence = PlaybookConfidence.HIGH
    selection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PlaybookSelectionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    selection_id: str = ""
    playbook_category: PlaybookCategory = PlaybookCategory.INCIDENT_RESPONSE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PlaybookSelectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_selection_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_criteria: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedPlaybookSelector:
    """Select optimal playbooks based on threat context, severity, and historical outcomes."""

    def __init__(
        self,
        max_records: int = 200000,
        selection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._selection_threshold = selection_threshold
        self._records: list[PlaybookSelectionRecord] = []
        self._analyses: list[PlaybookSelectionAnalysis] = []
        logger.info(
            "automated_playbook_selector.initialized",
            max_records=max_records,
            selection_threshold=selection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_selection(
        self,
        selection_id: str,
        playbook_category: PlaybookCategory = PlaybookCategory.INCIDENT_RESPONSE,
        selection_criteria: SelectionCriteria = SelectionCriteria.THREAT_TYPE,
        playbook_confidence: PlaybookConfidence = PlaybookConfidence.HIGH,
        selection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PlaybookSelectionRecord:
        record = PlaybookSelectionRecord(
            selection_id=selection_id,
            playbook_category=playbook_category,
            selection_criteria=selection_criteria,
            playbook_confidence=playbook_confidence,
            selection_score=selection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_playbook_selector.selection_recorded",
            record_id=record.id,
            selection_id=selection_id,
            playbook_category=playbook_category.value,
            selection_criteria=selection_criteria.value,
        )
        return record

    def get_selection(self, record_id: str) -> PlaybookSelectionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_selections(
        self,
        playbook_category: PlaybookCategory | None = None,
        selection_criteria: SelectionCriteria | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PlaybookSelectionRecord]:
        results = list(self._records)
        if playbook_category is not None:
            results = [r for r in results if r.playbook_category == playbook_category]
        if selection_criteria is not None:
            results = [r for r in results if r.selection_criteria == selection_criteria]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        selection_id: str,
        playbook_category: PlaybookCategory = PlaybookCategory.INCIDENT_RESPONSE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PlaybookSelectionAnalysis:
        analysis = PlaybookSelectionAnalysis(
            selection_id=selection_id,
            playbook_category=playbook_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automated_playbook_selector.analysis_added",
            selection_id=selection_id,
            playbook_category=playbook_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.playbook_category.value
            category_data.setdefault(key, []).append(r.selection_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_selection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_selection_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.selection_score < self._selection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "selection_id": r.selection_id,
                        "playbook_category": r.playbook_category.value,
                        "selection_score": r.selection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["selection_score"])

    def rank_by_selection(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.selection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_selection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_selection_score"])
        return results

    def detect_selection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PlaybookSelectionReport:
        by_category: dict[str, int] = {}
        by_criteria: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_category[r.playbook_category.value] = (
                by_category.get(r.playbook_category.value, 0) + 1
            )
            by_criteria[r.selection_criteria.value] = (
                by_criteria.get(r.selection_criteria.value, 0) + 1
            )
            by_confidence[r.playbook_confidence.value] = (
                by_confidence.get(r.playbook_confidence.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.selection_score < self._selection_threshold)
        scores = [r.selection_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_selection_gaps()
        top_gaps = [o["selection_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} selection(s) below threshold ({self._selection_threshold})")
        if self._records and avg_score < self._selection_threshold:
            recs.append(
                f"Avg selection score {avg_score} below threshold ({self._selection_threshold})"
            )
        if not recs:
            recs.append("Playbook selection is healthy")
        return PlaybookSelectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_selection_score=avg_score,
            by_category=by_category,
            by_criteria=by_criteria,
            by_confidence=by_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_playbook_selector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.playbook_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "selection_threshold": self._selection_threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
