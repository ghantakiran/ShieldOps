"""Automated Containment Engine — automated threat containment and isolation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContainmentType(StrEnum):
    NETWORK_ISOLATION = "network_isolation"
    PROCESS_KILL = "process_kill"
    ACCOUNT_DISABLE = "account_disable"
    DNS_SINKHOLE = "dns_sinkhole"
    FIREWALL_BLOCK = "firewall_block"


class ContainmentScope(StrEnum):
    HOST = "host"
    NETWORK = "network"
    ACCOUNT = "account"
    APPLICATION = "application"
    SERVICE = "service"


class ContainmentStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# --- Models ---


class ContainmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION
    containment_scope: ContainmentScope = ContainmentScope.HOST
    containment_status: ContainmentStatus = ContainmentStatus.PENDING
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedContainmentEngine:
    """Automated threat containment — network isolation, process kill, account disable."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._records: list[ContainmentRecord] = []
        self._analyses: list[ContainmentAnalysis] = []
        logger.info(
            "automated_containment_engine.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_containment(
        self,
        name: str,
        containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION,
        containment_scope: ContainmentScope = ContainmentScope.HOST,
        containment_status: ContainmentStatus = ContainmentStatus.PENDING,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContainmentRecord:
        record = ContainmentRecord(
            name=name,
            containment_type=containment_type,
            containment_scope=containment_scope,
            containment_status=containment_status,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_containment_engine.recorded",
            record_id=record.id,
            name=name,
            containment_type=containment_type.value,
            containment_scope=containment_scope.value,
        )
        return record

    def get_record(self, record_id: str) -> ContainmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        containment_type: ContainmentType | None = None,
        containment_scope: ContainmentScope | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ContainmentRecord]:
        results = list(self._records)
        if containment_type is not None:
            results = [r for r in results if r.containment_type == containment_type]
        if containment_scope is not None:
            results = [r for r in results if r.containment_scope == containment_scope]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ContainmentAnalysis:
        analysis = ContainmentAnalysis(
            name=name,
            containment_type=containment_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automated_containment_engine.analysis_added",
            name=name,
            containment_type=containment_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by containment_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.containment_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "containment_type": r.containment_type.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ContainmentReport:
        by_type: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.containment_type.value] = by_type.get(r.containment_type.value, 0) + 1
            by_scope[r.containment_scope.value] = by_scope.get(r.containment_scope.value, 0) + 1
            by_status[r.containment_status.value] = by_status.get(r.containment_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._score_threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} containment(s) below threshold ({self._score_threshold})")
        if self._records and avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Containment metrics within healthy range")
        return ContainmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_type=by_type,
            by_scope=by_scope,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_containment_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.containment_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "score_threshold": self._score_threshold,
            "type_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
