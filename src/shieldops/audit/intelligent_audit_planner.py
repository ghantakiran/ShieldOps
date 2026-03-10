"""Intelligent Audit Planner — intelligent audit planning and optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditScope(StrEnum):
    FULL = "full"
    TARGETED = "targeted"
    CONTINUOUS = "continuous"
    SAMPLING = "sampling"


class AuditPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PlanningHorizon(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


# --- Models ---


class AuditPlanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    audit_scope: AuditScope = AuditScope.TARGETED
    audit_priority: AuditPriority = AuditPriority.MEDIUM
    planning_horizon: PlanningHorizon = PlanningHorizon.QUARTERLY
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditPlanAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    audit_scope: AuditScope = AuditScope.TARGETED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IntelligentAuditPlannerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_audit_scope: dict[str, int] = Field(default_factory=dict)
    by_audit_priority: dict[str, int] = Field(default_factory=dict)
    by_planning_horizon: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentAuditPlanner:
    """Intelligent Audit Planner
    for audit planning and optimization.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AuditPlanRecord] = []
        self._analyses: list[AuditPlanAnalysis] = []
        logger.info(
            "intelligent_audit_planner.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        audit_scope: AuditScope = AuditScope.TARGETED,
        audit_priority: AuditPriority = (AuditPriority.MEDIUM),
        planning_horizon: PlanningHorizon = (PlanningHorizon.QUARTERLY),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AuditPlanRecord:
        record = AuditPlanRecord(
            name=name,
            audit_scope=audit_scope,
            audit_priority=audit_priority,
            planning_horizon=planning_horizon,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intelligent_audit_planner.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> AuditPlanRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        audit_scope: AuditScope | None = None,
        audit_priority: AuditPriority | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AuditPlanRecord]:
        results = list(self._records)
        if audit_scope is not None:
            results = [r for r in results if r.audit_scope == audit_scope]
        if audit_priority is not None:
            results = [r for r in results if r.audit_priority == audit_priority]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        audit_scope: AuditScope = AuditScope.TARGETED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuditPlanAnalysis:
        analysis = AuditPlanAnalysis(
            name=name,
            audit_scope=audit_scope,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "intelligent_audit_planner.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def generate_audit_plan(
        self,
    ) -> list[dict[str, Any]]:
        """Generate prioritized audit plan."""
        priority_weight = {
            "critical": 4.0,
            "high": 3.0,
            "medium": 2.0,
            "low": 1.0,
        }
        plan: list[dict[str, Any]] = []
        for r in self._records:
            weight = priority_weight.get(r.audit_priority.value, 1.0)
            urgency = round(weight * (100 - r.score) / 100, 2)
            plan.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "scope": r.audit_scope.value,
                    "priority": r.audit_priority.value,
                    "horizon": r.planning_horizon.value,
                    "urgency_score": urgency,
                    "service": r.service,
                }
            )
        plan.sort(
            key=lambda x: x["urgency_score"],
            reverse=True,
        )
        return plan

    def optimize_audit_coverage(
        self,
    ) -> dict[str, Any]:
        """Optimize audit coverage across services."""
        svc_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.service not in svc_data:
                svc_data[r.service] = {
                    "scopes": set(),
                    "priorities": set(),
                    "scores": [],
                }
            svc_data[r.service]["scopes"].add(r.audit_scope.value)
            svc_data[r.service]["priorities"].add(r.audit_priority.value)
            svc_data[r.service]["scores"].append(r.score)
        all_scopes = {s.value for s in AuditScope}
        coverage: list[dict[str, Any]] = []
        for svc, data in svc_data.items():
            scope_cov = round(len(data["scopes"]) / len(all_scopes) * 100, 2)
            avg = round(sum(data["scores"]) / len(data["scores"]), 2)
            coverage.append(
                {
                    "service": svc,
                    "scope_coverage_pct": scope_cov,
                    "avg_score": avg,
                    "audit_count": len(data["scores"]),
                    "needs_expansion": scope_cov < 75,
                }
            )
        coverage.sort(key=lambda x: x["scope_coverage_pct"])
        return {
            "service_coverage": coverage,
            "total_services": len(svc_data),
        }

    def compute_audit_efficiency(
        self,
    ) -> dict[str, Any]:
        """Compute audit efficiency metrics."""
        scope_data: dict[str, list[float]] = {}
        horizon_data: dict[str, list[float]] = {}
        for r in self._records:
            scope_data.setdefault(r.audit_scope.value, []).append(r.score)
            horizon_data.setdefault(r.planning_horizon.value, []).append(r.score)
        by_scope: dict[str, Any] = {}
        for scope, scores in scope_data.items():
            avg = round(sum(scores) / len(scores), 2)
            by_scope[scope] = {
                "count": len(scores),
                "avg_score": avg,
                "efficient": avg >= self._threshold,
            }
        by_horizon: dict[str, Any] = {}
        for hz, scores in horizon_data.items():
            by_horizon[hz] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        all_scores = [r.score for r in self._records]
        overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        return {
            "overall_efficiency": overall,
            "by_scope": by_scope,
            "by_horizon": by_horizon,
            "total_audits": len(self._records),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(
        self,
    ) -> IntelligentAuditPlannerReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.audit_scope.value] = by_e1.get(r.audit_scope.value, 0) + 1
            by_e2[r.audit_priority.value] = by_e2.get(r.audit_priority.value, 0) + 1
            by_e3[r.planning_horizon.value] = by_e3.get(r.planning_horizon.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Intelligent Audit Planner is healthy")
        return IntelligentAuditPlannerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_audit_scope=by_e1,
            by_audit_priority=by_e2,
            by_planning_horizon=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intelligent_audit_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.audit_scope.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "audit_scope_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
