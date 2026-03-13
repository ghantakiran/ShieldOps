"""Terraform Plan Impact Analyzer
analyze terraform plan impacts, detect destructive
changes, rank plans by risk score."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"


class ImpactLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResourceCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    SECURITY = "security"


# --- Models ---


class TerraformPlanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    resource_name: str = ""
    change_action: ChangeAction = ChangeAction.CREATE
    impact_level: ImpactLevel = ImpactLevel.LOW
    resource_category: ResourceCategory = ResourceCategory.COMPUTE
    affected_resources: int = 0
    risk_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TerraformPlanAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    blast_radius: int = 0
    destructive_count: int = 0
    computed_risk: float = 0.0
    impact_level: ImpactLevel = ImpactLevel.LOW
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TerraformPlanReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_change_action: dict[str, int] = Field(default_factory=dict)
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_resource_category: dict[str, int] = Field(default_factory=dict)
    high_risk_plans: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TerraformPlanImpactAnalyzer:
    """Analyze terraform plan impacts, detect
    destructive changes, rank plans by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TerraformPlanRecord] = []
        self._analyses: dict[str, TerraformPlanAnalysis] = {}
        logger.info(
            "terraform_plan_impact_analyzer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        plan_id: str = "",
        resource_name: str = "",
        change_action: ChangeAction = ChangeAction.CREATE,
        impact_level: ImpactLevel = ImpactLevel.LOW,
        resource_category: ResourceCategory = (ResourceCategory.COMPUTE),
        affected_resources: int = 0,
        risk_score: float = 0.0,
        description: str = "",
    ) -> TerraformPlanRecord:
        record = TerraformPlanRecord(
            plan_id=plan_id,
            resource_name=resource_name,
            change_action=change_action,
            impact_level=impact_level,
            resource_category=resource_category,
            affected_resources=affected_resources,
            risk_score=risk_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "terraform_plan_impact.record_added",
            record_id=record.id,
            plan_id=plan_id,
        )
        return record

    def process(self, key: str) -> TerraformPlanAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        destructive = sum(
            1
            for r in self._records
            if r.plan_id == rec.plan_id
            and r.change_action in (ChangeAction.DELETE, ChangeAction.REPLACE)
        )
        blast = sum(r.affected_resources for r in self._records if r.plan_id == rec.plan_id)
        analysis = TerraformPlanAnalysis(
            plan_id=rec.plan_id,
            blast_radius=blast,
            destructive_count=destructive,
            computed_risk=round(rec.risk_score, 2),
            impact_level=rec.impact_level,
            description=(f"Plan {rec.plan_id} risk {rec.risk_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TerraformPlanReport:
        by_ca: dict[str, int] = {}
        by_il: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.change_action.value
            by_ca[k] = by_ca.get(k, 0) + 1
            k2 = r.impact_level.value
            by_il[k2] = by_il.get(k2, 0) + 1
            k3 = r.resource_category.value
            by_rc[k3] = by_rc.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list(
            {
                r.plan_id
                for r in self._records
                if r.impact_level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk plans detected")
        if not recs:
            recs.append("No significant risks detected")
        return TerraformPlanReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_change_action=by_ca,
            by_impact_level=by_il,
            by_resource_category=by_rc,
            high_risk_plans=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ca_dist: dict[str, int] = {}
        for r in self._records:
            k = r.change_action.value
            ca_dist[k] = ca_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "change_action_distribution": ca_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("terraform_plan_impact_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_plan_blast_radius(
        self,
    ) -> list[dict[str, Any]]:
        """Compute blast radius per plan."""
        plan_resources: dict[str, int] = {}
        plan_actions: dict[str, list[str]] = {}
        for r in self._records:
            plan_resources[r.plan_id] = plan_resources.get(r.plan_id, 0) + r.affected_resources
            plan_actions.setdefault(r.plan_id, []).append(r.change_action.value)
        results: list[dict[str, Any]] = []
        for pid, total in plan_resources.items():
            results.append(
                {
                    "plan_id": pid,
                    "blast_radius": total,
                    "action_count": len(plan_actions[pid]),
                    "actions": list(set(plan_actions[pid])),
                }
            )
        results.sort(
            key=lambda x: x["blast_radius"],
            reverse=True,
        )
        return results

    def detect_destructive_changes(
        self,
    ) -> list[dict[str, Any]]:
        """Detect destructive changes in plans."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.change_action in (
                ChangeAction.DELETE,
                ChangeAction.REPLACE,
            ):
                results.append(
                    {
                        "plan_id": r.plan_id,
                        "resource_name": r.resource_name,
                        "action": r.change_action.value,
                        "impact_level": (r.impact_level.value),
                        "risk_score": r.risk_score,
                    }
                )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        return results

    def rank_plans_by_risk_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank plans by aggregate risk score."""
        plan_scores: dict[str, float] = {}
        for r in self._records:
            plan_scores[r.plan_id] = plan_scores.get(r.plan_id, 0.0) + r.risk_score
        results: list[dict[str, Any]] = []
        for pid, total in plan_scores.items():
            results.append(
                {
                    "plan_id": pid,
                    "aggregate_risk": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["aggregate_risk"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
