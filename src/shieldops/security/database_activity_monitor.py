"""Database Activity Monitor — monitor database activity for suspicious queries and operations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QueryType(StrEnum):
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"


class ActivityRisk(StrEnum):
    EXFILTRATION = "exfiltration"
    INJECTION = "injection"
    PRIVILEGE_ABUSE = "privilege_abuse"
    BULK_OPERATION = "bulk_operation"
    NORMAL = "normal"


class DatabaseEngine(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"


# --- Models ---


class DatabaseActivityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    activity_id: str = ""
    query_type: QueryType = QueryType.SELECT
    activity_risk: ActivityRisk = ActivityRisk.NORMAL
    database_engine: DatabaseEngine = DatabaseEngine.POSTGRESQL
    activity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DatabaseActivityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    activity_id: str = ""
    query_type: QueryType = QueryType.SELECT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DatabaseActivityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_activity_score: float = 0.0
    by_query_type: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_engine: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DatabaseActivityMonitor:
    """Monitor database activity for suspicious queries and risky operations."""

    def __init__(
        self,
        max_records: int = 200000,
        activity_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._activity_threshold = activity_threshold
        self._records: list[DatabaseActivityRecord] = []
        self._analyses: list[DatabaseActivityAnalysis] = []
        logger.info(
            "database_activity_monitor.initialized",
            max_records=max_records,
            activity_threshold=activity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_activity(
        self,
        activity_id: str,
        query_type: QueryType = QueryType.SELECT,
        activity_risk: ActivityRisk = ActivityRisk.NORMAL,
        database_engine: DatabaseEngine = DatabaseEngine.POSTGRESQL,
        activity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DatabaseActivityRecord:
        record = DatabaseActivityRecord(
            activity_id=activity_id,
            query_type=query_type,
            activity_risk=activity_risk,
            database_engine=database_engine,
            activity_score=activity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "database_activity_monitor.activity_recorded",
            record_id=record.id,
            activity_id=activity_id,
            query_type=query_type.value,
            activity_risk=activity_risk.value,
        )
        return record

    def get_activity(self, record_id: str) -> DatabaseActivityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_activities(
        self,
        query_type: QueryType | None = None,
        activity_risk: ActivityRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DatabaseActivityRecord]:
        results = list(self._records)
        if query_type is not None:
            results = [r for r in results if r.query_type == query_type]
        if activity_risk is not None:
            results = [r for r in results if r.activity_risk == activity_risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        activity_id: str,
        query_type: QueryType = QueryType.SELECT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DatabaseActivityAnalysis:
        analysis = DatabaseActivityAnalysis(
            activity_id=activity_id,
            query_type=query_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "database_activity_monitor.analysis_added",
            activity_id=activity_id,
            query_type=query_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_query_distribution(self) -> dict[str, Any]:
        query_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.query_type.value
            query_data.setdefault(key, []).append(r.activity_score)
        result: dict[str, Any] = {}
        for query, scores in query_data.items():
            result[query] = {
                "count": len(scores),
                "avg_activity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_activity_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.activity_score < self._activity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "activity_id": r.activity_id,
                        "query_type": r.query_type.value,
                        "activity_score": r.activity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["activity_score"])

    def rank_by_activity(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.activity_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_activity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_activity_score"])
        return results

    def detect_activity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DatabaseActivityReport:
        by_query_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_engine: dict[str, int] = {}
        for r in self._records:
            by_query_type[r.query_type.value] = by_query_type.get(r.query_type.value, 0) + 1
            by_risk[r.activity_risk.value] = by_risk.get(r.activity_risk.value, 0) + 1
            by_engine[r.database_engine.value] = by_engine.get(r.database_engine.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.activity_score < self._activity_threshold)
        scores = [r.activity_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_activity_gaps()
        top_gaps = [o["activity_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} activity(ies) below threshold ({self._activity_threshold})")
        if self._records and avg_score < self._activity_threshold:
            recs.append(
                f"Avg activity score {avg_score} below threshold ({self._activity_threshold})"
            )
        if not recs:
            recs.append("Database activity monitoring is healthy")
        return DatabaseActivityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_activity_score=avg_score,
            by_query_type=by_query_type,
            by_risk=by_risk,
            by_engine=by_engine,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("database_activity_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        query_dist: dict[str, int] = {}
        for r in self._records:
            key = r.query_type.value
            query_dist[key] = query_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "activity_threshold": self._activity_threshold,
            "query_distribution": query_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
