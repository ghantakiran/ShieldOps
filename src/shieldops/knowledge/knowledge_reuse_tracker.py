"""Knowledge Reuse Tracker — track knowledge content reuse, identify low-reuse content."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContentType(StrEnum):
    ARTICLE = "article"
    RUNBOOK = "runbook"
    PLAYBOOK = "playbook"
    POSTMORTEM = "postmortem"
    ARCHITECTURE_DOC = "architecture_doc"


class ReuseOutcome(StrEnum):
    RESOLVED_ISSUE = "resolved_issue"
    PARTIALLY_HELPFUL = "partially_helpful"
    OUTDATED_CONTENT = "outdated_content"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_UPDATE = "needs_update"


class ReuseContext(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    CHANGE_PLANNING = "change_planning"
    ONBOARDING = "onboarding"
    TROUBLESHOOTING = "troubleshooting"
    COMPLIANCE_AUDIT = "compliance_audit"


# --- Models ---


class ReuseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str = ""
    content_type: ContentType = ContentType.ARTICLE
    reuse_outcome: ReuseOutcome = ReuseOutcome.RESOLVED_ISSUE
    reuse_context: ReuseContext = ReuseContext.INCIDENT_RESPONSE
    reuse_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReuseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str = ""
    content_type: ContentType = ContentType.ARTICLE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeReuseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_reuse_count: int = 0
    avg_reuse_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_context: dict[str, int] = Field(default_factory=dict)
    top_low_reuse: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeReuseTracker:
    """Track knowledge content reuse, identify low-reuse content, measure reuse effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        min_reuse_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_reuse_score = min_reuse_score
        self._records: list[ReuseRecord] = []
        self._analyses: list[ReuseAnalysis] = []
        logger.info(
            "knowledge_reuse_tracker.initialized",
            max_records=max_records,
            min_reuse_score=min_reuse_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_reuse(
        self,
        content_id: str,
        content_type: ContentType = ContentType.ARTICLE,
        reuse_outcome: ReuseOutcome = ReuseOutcome.RESOLVED_ISSUE,
        reuse_context: ReuseContext = ReuseContext.INCIDENT_RESPONSE,
        reuse_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReuseRecord:
        record = ReuseRecord(
            content_id=content_id,
            content_type=content_type,
            reuse_outcome=reuse_outcome,
            reuse_context=reuse_context,
            reuse_score=reuse_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_reuse_tracker.reuse_recorded",
            record_id=record.id,
            content_id=content_id,
            content_type=content_type.value,
            reuse_outcome=reuse_outcome.value,
        )
        return record

    def get_reuse(self, record_id: str) -> ReuseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reuse_records(
        self,
        content_type: ContentType | None = None,
        reuse_outcome: ReuseOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReuseRecord]:
        results = list(self._records)
        if content_type is not None:
            results = [r for r in results if r.content_type == content_type]
        if reuse_outcome is not None:
            results = [r for r in results if r.reuse_outcome == reuse_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        content_id: str,
        content_type: ContentType = ContentType.ARTICLE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReuseAnalysis:
        analysis = ReuseAnalysis(
            content_id=content_id,
            content_type=content_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "knowledge_reuse_tracker.analysis_added",
            content_id=content_id,
            content_type=content_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_reuse_distribution(self) -> dict[str, Any]:
        """Group by content_type; return count and avg reuse_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.content_type.value
            type_data.setdefault(key, []).append(r.reuse_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_reuse_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_reuse_content(self) -> list[dict[str, Any]]:
        """Return records where reuse_score < min_reuse_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.reuse_score < self._min_reuse_score:
                results.append(
                    {
                        "record_id": r.id,
                        "content_id": r.content_id,
                        "content_type": r.content_type.value,
                        "reuse_score": r.reuse_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["reuse_score"])

    def rank_by_reuse(self) -> list[dict[str, Any]]:
        """Group by service, avg reuse_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.reuse_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_reuse_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_reuse_score"])
        return results

    def detect_reuse_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> KnowledgeReuseReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_context: dict[str, int] = {}
        for r in self._records:
            by_type[r.content_type.value] = by_type.get(r.content_type.value, 0) + 1
            by_outcome[r.reuse_outcome.value] = by_outcome.get(r.reuse_outcome.value, 0) + 1
            by_context[r.reuse_context.value] = by_context.get(r.reuse_context.value, 0) + 1
        low_reuse_count = sum(1 for r in self._records if r.reuse_score < self._min_reuse_score)
        scores = [r.reuse_score for r in self._records]
        avg_reuse_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_reuse_content()
        top_low_reuse = [o["content_id"] for o in low_list[:5]]
        recs: list[str] = []
        if low_reuse_count > 0:
            recs.append(f"{low_reuse_count} low-reuse content item(s) — review for improvement")
        if self._records and avg_reuse_score < self._min_reuse_score:
            recs.append(
                f"Avg reuse score {avg_reuse_score} below threshold ({self._min_reuse_score})"
            )
        if not recs:
            recs.append("Knowledge reuse levels are healthy")
        return KnowledgeReuseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_reuse_count=low_reuse_count,
            avg_reuse_score=avg_reuse_score,
            by_type=by_type,
            by_outcome=by_outcome,
            by_context=by_context,
            top_low_reuse=top_low_reuse,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("knowledge_reuse_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.content_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "min_reuse_score": self._min_reuse_score,
            "content_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
