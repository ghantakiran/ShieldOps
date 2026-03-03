"""Microsegmentation Enforcer — enforce network microsegmentation policies and rules."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SegmentType(StrEnum):
    NETWORK = "network"
    APPLICATION = "application"
    DATA = "data"
    IDENTITY = "identity"
    WORKLOAD = "workload"


class EnforcementAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    RESTRICT = "restrict"
    MONITOR = "monitor"
    QUARANTINE = "quarantine"


class SegmentStatus(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    VIOLATED = "violated"
    EXEMPT = "exempt"
    DISABLED = "disabled"


# --- Models ---


class SegmentRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str = ""
    segment_type: SegmentType = SegmentType.NETWORK
    enforcement_action: EnforcementAction = EnforcementAction.ALLOW
    segment_status: SegmentStatus = SegmentStatus.ACTIVE
    enforcement_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SegmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str = ""
    segment_type: SegmentType = SegmentType.NETWORK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SegmentEnforcementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_enforcement_score: float = 0.0
    by_segment_type: dict[str, int] = Field(default_factory=dict)
    by_enforcement_action: dict[str, int] = Field(default_factory=dict)
    by_segment_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MicrosegmentationEnforcer:
    """Enforce microsegmentation policies, track rule violations, and analyze segment health."""

    def __init__(
        self,
        max_records: int = 200000,
        enforcement_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._enforcement_gap_threshold = enforcement_gap_threshold
        self._records: list[SegmentRule] = []
        self._analyses: list[SegmentAnalysis] = []
        logger.info(
            "microsegmentation_enforcer.initialized",
            max_records=max_records,
            enforcement_gap_threshold=enforcement_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_rule(
        self,
        segment_id: str,
        segment_type: SegmentType = SegmentType.NETWORK,
        enforcement_action: EnforcementAction = EnforcementAction.ALLOW,
        segment_status: SegmentStatus = SegmentStatus.ACTIVE,
        enforcement_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SegmentRule:
        record = SegmentRule(
            segment_id=segment_id,
            segment_type=segment_type,
            enforcement_action=enforcement_action,
            segment_status=segment_status,
            enforcement_score=enforcement_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "microsegmentation_enforcer.rule_recorded",
            record_id=record.id,
            segment_id=segment_id,
            segment_type=segment_type.value,
            enforcement_action=enforcement_action.value,
        )
        return record

    def get_rule(self, record_id: str) -> SegmentRule | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rules(
        self,
        segment_type: SegmentType | None = None,
        enforcement_action: EnforcementAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SegmentRule]:
        results = list(self._records)
        if segment_type is not None:
            results = [r for r in results if r.segment_type == segment_type]
        if enforcement_action is not None:
            results = [r for r in results if r.enforcement_action == enforcement_action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        segment_id: str,
        segment_type: SegmentType = SegmentType.NETWORK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SegmentAnalysis:
        analysis = SegmentAnalysis(
            segment_id=segment_id,
            segment_type=segment_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "microsegmentation_enforcer.analysis_added",
            segment_id=segment_id,
            segment_type=segment_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_segment_distribution(self) -> dict[str, Any]:
        """Group by segment_type; return count and avg enforcement_score."""
        segment_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.segment_type.value
            segment_data.setdefault(key, []).append(r.enforcement_score)
        result: dict[str, Any] = {}
        for segment, scores in segment_data.items():
            result[segment] = {
                "count": len(scores),
                "avg_enforcement_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_enforcement_gaps(self) -> list[dict[str, Any]]:
        """Return records where enforcement_score < enforcement_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.enforcement_score < self._enforcement_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "segment_id": r.segment_id,
                        "segment_type": r.segment_type.value,
                        "enforcement_score": r.enforcement_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["enforcement_score"])

    def rank_by_enforcement(self) -> list[dict[str, Any]]:
        """Group by service, avg enforcement_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.enforcement_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_enforcement_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_enforcement_score"])
        return results

    def detect_enforcement_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SegmentEnforcementReport:
        by_segment_type: dict[str, int] = {}
        by_enforcement_action: dict[str, int] = {}
        by_segment_status: dict[str, int] = {}
        for r in self._records:
            by_segment_type[r.segment_type.value] = by_segment_type.get(r.segment_type.value, 0) + 1
            by_enforcement_action[r.enforcement_action.value] = (
                by_enforcement_action.get(r.enforcement_action.value, 0) + 1
            )
            by_segment_status[r.segment_status.value] = (
                by_segment_status.get(r.segment_status.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.enforcement_score < self._enforcement_gap_threshold
        )
        scores = [r.enforcement_score for r in self._records]
        avg_enforcement_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_enforcement_gaps()
        top_gaps = [o["segment_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} segment(s) below enforcement threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if self._records and avg_enforcement_score < self._enforcement_gap_threshold:
            recs.append(
                f"Avg enforcement score {avg_enforcement_score} below threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if not recs:
            recs.append("Microsegmentation enforcement is healthy")
        return SegmentEnforcementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_enforcement_score=avg_enforcement_score,
            by_segment_type=by_segment_type,
            by_enforcement_action=by_enforcement_action,
            by_segment_status=by_segment_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("microsegmentation_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        segment_dist: dict[str, int] = {}
        for r in self._records:
            key = r.segment_type.value
            segment_dist[key] = segment_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "enforcement_gap_threshold": self._enforcement_gap_threshold,
            "segment_type_distribution": segment_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
