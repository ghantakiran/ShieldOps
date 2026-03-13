"""Postmortem Insight Extractor — extract actionable insights,
detect recurring themes, rank insights by prevention value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InsightType(StrEnum):
    ROOT_CAUSE = "root_cause"
    CONTRIBUTING_FACTOR = "contributing_factor"
    ACTION_ITEM = "action_item"
    PREVENTION = "prevention"


class ThemeCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    CODE = "code"
    PROCESS = "process"
    HUMAN = "human"


class InsightPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class PostmortemInsightRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    insight_type: InsightType = InsightType.ROOT_CAUSE
    theme_category: ThemeCategory = ThemeCategory.INFRASTRUCTURE
    insight_priority: InsightPriority = InsightPriority.MEDIUM
    prevention_score: float = 0.0
    insight_text: str = ""
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostmortemInsightAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    insight_type: InsightType = InsightType.ROOT_CAUSE
    prevention_value: float = 0.0
    is_recurring: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostmortemInsightReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_prevention_score: float = 0.0
    by_insight_type: dict[str, int] = Field(default_factory=dict)
    by_theme_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PostmortemInsightExtractor:
    """Extract actionable insights from postmortems, detect
    recurring themes, rank insights by prevention value."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PostmortemInsightRecord] = []
        self._analyses: dict[str, PostmortemInsightAnalysis] = {}
        logger.info(
            "postmortem_insight_extractor.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        insight_type: InsightType = InsightType.ROOT_CAUSE,
        theme_category: ThemeCategory = ThemeCategory.INFRASTRUCTURE,
        insight_priority: InsightPriority = InsightPriority.MEDIUM,
        prevention_score: float = 0.0,
        insight_text: str = "",
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> PostmortemInsightRecord:
        record = PostmortemInsightRecord(
            incident_id=incident_id,
            insight_type=insight_type,
            theme_category=theme_category,
            insight_priority=insight_priority,
            prevention_score=prevention_score,
            insight_text=insight_text,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "postmortem_insight.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> PostmortemInsightAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        theme_count = sum(1 for r in self._records if r.theme_category == rec.theme_category)
        is_recurring = theme_count > 1
        analysis = PostmortemInsightAnalysis(
            incident_id=rec.incident_id,
            insight_type=rec.insight_type,
            prevention_value=round(rec.prevention_score, 2),
            is_recurring=is_recurring,
            description=f"Insight for {rec.incident_id}: {rec.insight_text[:50]}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PostmortemInsightReport:
        by_it: dict[str, int] = {}
        by_tc: dict[str, int] = {}
        by_pr: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_it[r.insight_type.value] = by_it.get(r.insight_type.value, 0) + 1
            by_tc[r.theme_category.value] = by_tc.get(r.theme_category.value, 0) + 1
            by_pr[r.insight_priority.value] = by_pr.get(r.insight_priority.value, 0) + 1
            scores.append(r.prevention_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        critical = by_pr.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical-priority insights require immediate action")
        if not recs:
            recs.append("No critical postmortem insights detected")
        return PostmortemInsightReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_prevention_score=avg,
            by_insight_type=by_it,
            by_theme_category=by_tc,
            by_priority=by_pr,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.insight_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "insight_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("postmortem_insight_extractor.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def extract_actionable_insights(self) -> list[dict[str, Any]]:
        """Extract actionable insights grouped by type."""
        type_insights: dict[str, list[PostmortemInsightRecord]] = {}
        for r in self._records:
            type_insights.setdefault(r.insight_type.value, []).append(r)
        results: list[dict[str, Any]] = []
        for itype, records in type_insights.items():
            avg_score = round(sum(r.prevention_score for r in records) / len(records), 2)
            results.append(
                {
                    "insight_type": itype,
                    "count": len(records),
                    "avg_prevention_score": avg_score,
                    "top_insights": [r.insight_text for r in records[:5]],
                }
            )
        results.sort(key=lambda x: x["avg_prevention_score"], reverse=True)
        return results

    def detect_recurring_themes(self) -> list[dict[str, Any]]:
        """Detect recurring themes across postmortems."""
        theme_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.theme_category.value
            if k not in theme_data:
                theme_data[k] = {"count": 0, "incidents": set(), "scores": []}
            theme_data[k]["count"] += 1
            theme_data[k]["incidents"].add(r.incident_id)
            theme_data[k]["scores"].append(r.prevention_score)
        results: list[dict[str, Any]] = []
        for theme, data in theme_data.items():
            if data["count"] > 1:
                avg = round(sum(data["scores"]) / len(data["scores"]), 2)
                results.append(
                    {
                        "theme": theme,
                        "occurrence_count": data["count"],
                        "unique_incidents": len(data["incidents"]),
                        "avg_prevention_score": avg,
                    }
                )
        results.sort(key=lambda x: x["occurrence_count"], reverse=True)
        return results

    def rank_insights_by_prevention_value(self) -> list[dict[str, Any]]:
        """Rank all insights by prevention value."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "incident_id": r.incident_id,
                    "insight_type": r.insight_type.value,
                    "theme": r.theme_category.value,
                    "prevention_score": r.prevention_score,
                    "insight_text": r.insight_text,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["prevention_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
