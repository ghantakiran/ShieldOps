"""Incident Response Playbook Manager — manage playbooks, track usage, and analyze coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PlaybookType(StrEnum):
    AUTOMATED = "automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL = "manual"
    ESCALATION = "escalation"
    COMMUNICATION = "communication"


class PlaybookStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    UNDER_REVIEW = "under_review"
    ARCHIVED = "archived"


class PlaybookEffectiveness(StrEnum):
    HIGHLY_EFFECTIVE = "highly_effective"
    EFFECTIVE = "effective"
    NEEDS_IMPROVEMENT = "needs_improvement"
    INEFFECTIVE = "ineffective"
    UNTESTED = "untested"


# --- Models ---


class PlaybookRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    playbook_type: PlaybookType = PlaybookType.MANUAL
    playbook_status: PlaybookStatus = PlaybookStatus.DRAFT
    playbook_effectiveness: PlaybookEffectiveness = PlaybookEffectiveness.UNTESTED
    coverage_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PlaybookUsage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    usage_name: str = ""
    playbook_type: PlaybookType = PlaybookType.MANUAL
    execution_count: int = 0
    avg_resolution_time: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponsePlaybookReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_usages: int = 0
    low_coverage_playbooks: int = 0
    avg_coverage_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponsePlaybookManager:
    """Manage incident response playbooks, track usage, and analyze coverage."""

    def __init__(
        self,
        max_records: int = 200000,
        min_playbook_coverage_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_playbook_coverage_pct = min_playbook_coverage_pct
        self._records: list[PlaybookRecord] = []
        self._usages: list[PlaybookUsage] = []
        logger.info(
            "response_playbook.initialized",
            max_records=max_records,
            min_playbook_coverage_pct=min_playbook_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_playbook(
        self,
        playbook_name: str,
        playbook_type: PlaybookType = PlaybookType.MANUAL,
        playbook_status: PlaybookStatus = PlaybookStatus.DRAFT,
        playbook_effectiveness: PlaybookEffectiveness = PlaybookEffectiveness.UNTESTED,
        coverage_score: float = 0.0,
        team: str = "",
    ) -> PlaybookRecord:
        record = PlaybookRecord(
            playbook_name=playbook_name,
            playbook_type=playbook_type,
            playbook_status=playbook_status,
            playbook_effectiveness=playbook_effectiveness,
            coverage_score=coverage_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_playbook.recorded",
            record_id=record.id,
            playbook_name=playbook_name,
            playbook_type=playbook_type.value,
            playbook_status=playbook_status.value,
        )
        return record

    def get_playbook(self, record_id: str) -> PlaybookRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_playbooks(
        self,
        playbook_type: PlaybookType | None = None,
        status: PlaybookStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PlaybookRecord]:
        results = list(self._records)
        if playbook_type is not None:
            results = [r for r in results if r.playbook_type == playbook_type]
        if status is not None:
            results = [r for r in results if r.playbook_status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_usage(
        self,
        usage_name: str,
        playbook_type: PlaybookType = PlaybookType.MANUAL,
        execution_count: int = 0,
        avg_resolution_time: float = 0.0,
        description: str = "",
    ) -> PlaybookUsage:
        usage = PlaybookUsage(
            usage_name=usage_name,
            playbook_type=playbook_type,
            execution_count=execution_count,
            avg_resolution_time=avg_resolution_time,
            description=description,
        )
        self._usages.append(usage)
        if len(self._usages) > self._max_records:
            self._usages = self._usages[-self._max_records :]
        logger.info(
            "response_playbook.usage_added",
            usage_name=usage_name,
            playbook_type=playbook_type.value,
            execution_count=execution_count,
        )
        return usage

    # -- domain operations --------------------------------------------------

    def analyze_playbook_coverage(self) -> dict[str, Any]:
        """Group by type; return count and avg coverage score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.playbook_type.value
            type_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where effectiveness is INEFFECTIVE or UNTESTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.playbook_effectiveness in (
                PlaybookEffectiveness.INEFFECTIVE,
                PlaybookEffectiveness.UNTESTED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "playbook_name": r.playbook_name,
                        "playbook_effectiveness": r.playbook_effectiveness.value,
                        "coverage_score": r.coverage_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by team, avg coverage score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"], reverse=True)
        return results

    def detect_playbook_trends(self) -> dict[str, Any]:
        """Split-half on avg_resolution_time; delta threshold 5.0."""
        if len(self._usages) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [u.avg_resolution_time for u in self._usages]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ResponsePlaybookReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        for r in self._records:
            by_type[r.playbook_type.value] = by_type.get(r.playbook_type.value, 0) + 1
            by_status[r.playbook_status.value] = by_status.get(r.playbook_status.value, 0) + 1
            by_effectiveness[r.playbook_effectiveness.value] = (
                by_effectiveness.get(r.playbook_effectiveness.value, 0) + 1
            )
        low_count = sum(
            1
            for r in self._records
            if r.playbook_effectiveness
            in (PlaybookEffectiveness.INEFFECTIVE, PlaybookEffectiveness.UNTESTED)
        )
        avg_score = (
            round(sum(r.coverage_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_effectiveness()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if self._records and avg_score < self._min_playbook_coverage_pct:
            recs.append(
                f"Avg coverage {avg_score} below threshold ({self._min_playbook_coverage_pct})"
            )
        if low_count > 0:
            recs.append(f"{low_count} playbook(s) need improvement — review effectiveness")
        if not recs:
            recs.append("Playbook coverage is within acceptable limits")
        return ResponsePlaybookReport(
            total_records=len(self._records),
            total_usages=len(self._usages),
            low_coverage_playbooks=low_count,
            avg_coverage_score=avg_score,
            by_type=by_type,
            by_status=by_status,
            by_effectiveness=by_effectiveness,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._usages.clear()
        logger.info("response_playbook.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.playbook_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_usages": len(self._usages),
            "min_playbook_coverage_pct": self._min_playbook_coverage_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_playbooks": len({r.playbook_name for r in self._records}),
        }
