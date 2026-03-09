"""IacValidationEngine

Terraform/OpenTofu plan validation, policy compliance checking,
cost estimation, blast-radius prediction.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IacToolType(StrEnum):
    TERRAFORM = "terraform"
    OPENTOFU = "opentofu"
    PULUMI = "pulumi"
    CLOUDFORMATION = "cloudformation"
    CROSSPLANE = "crossplane"


class ValidationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class BlastRadiusLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class IacValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tool_type: IacToolType = IacToolType.TERRAFORM
    validation_result: ValidationResult = ValidationResult.PASSED
    blast_radius: BlastRadiusLevel = BlastRadiusLevel.MINIMAL
    resources_added: int = 0
    resources_changed: int = 0
    resources_destroyed: int = 0
    estimated_cost_delta: float = 0.0
    policy_violations: int = 0
    plan_file: str = ""
    workspace: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IacValidationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tool_type: IacToolType = IacToolType.TERRAFORM
    analysis_score: float = 0.0
    total_violations: int = 0
    estimated_monthly_cost: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IacValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    passed_count: int = 0
    failed_count: int = 0
    total_policy_violations: int = 0
    total_cost_delta: float = 0.0
    avg_blast_radius_score: float = 0.0
    by_tool_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_blast_radius: dict[str, int] = Field(default_factory=dict)
    top_violators: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IacValidationEngine:
    """Terraform/OpenTofu plan validation with policy compliance and cost estimation."""

    BLAST_RADIUS_WEIGHTS: dict[str, float] = {
        "critical": 100.0,
        "high": 75.0,
        "medium": 50.0,
        "low": 25.0,
        "minimal": 10.0,
    }

    def __init__(
        self,
        max_records: int = 200000,
        violation_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._violation_threshold = violation_threshold
        self._records: list[IacValidationRecord] = []
        self._analyses: list[IacValidationAnalysis] = []
        logger.info(
            "iac.validation.engine.initialized",
            max_records=max_records,
            violation_threshold=violation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        tool_type: IacToolType = IacToolType.TERRAFORM,
        validation_result: ValidationResult = ValidationResult.PASSED,
        blast_radius: BlastRadiusLevel = BlastRadiusLevel.MINIMAL,
        resources_added: int = 0,
        resources_changed: int = 0,
        resources_destroyed: int = 0,
        estimated_cost_delta: float = 0.0,
        policy_violations: int = 0,
        plan_file: str = "",
        workspace: str = "",
        service: str = "",
        team: str = "",
    ) -> IacValidationRecord:
        record = IacValidationRecord(
            name=name,
            tool_type=tool_type,
            validation_result=validation_result,
            blast_radius=blast_radius,
            resources_added=resources_added,
            resources_changed=resources_changed,
            resources_destroyed=resources_destroyed,
            estimated_cost_delta=estimated_cost_delta,
            policy_violations=policy_violations,
            plan_file=plan_file,
            workspace=workspace,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "iac.validation.engine.item_recorded",
            record_id=record.id,
            name=name,
            tool_type=tool_type.value,
            validation_result=validation_result.value,
        )
        return record

    def get_record(self, record_id: str) -> IacValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        tool_type: IacToolType | None = None,
        validation_result: ValidationResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IacValidationRecord]:
        results = list(self._records)
        if tool_type is not None:
            results = [r for r in results if r.tool_type == tool_type]
        if validation_result is not None:
            results = [r for r in results if r.validation_result == validation_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        tool_type: IacToolType = IacToolType.TERRAFORM,
        analysis_score: float = 0.0,
        total_violations: int = 0,
        estimated_monthly_cost: float = 0.0,
        description: str = "",
    ) -> IacValidationAnalysis:
        analysis = IacValidationAnalysis(
            name=name,
            tool_type=tool_type,
            analysis_score=analysis_score,
            total_violations=total_violations,
            estimated_monthly_cost=estimated_monthly_cost,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "iac.validation.engine.analysis_added",
            name=name,
            tool_type=tool_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def calculate_blast_radius(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            total_affected = r.resources_added + r.resources_changed + r.resources_destroyed
            weight = self.BLAST_RADIUS_WEIGHTS.get(r.blast_radius.value, 10.0)
            score = round(total_affected * weight / 100.0, 2)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "blast_radius": r.blast_radius.value,
                    "total_affected_resources": total_affected,
                    "destruction_ratio": round(r.resources_destroyed / total_affected, 2)
                    if total_affected > 0
                    else 0.0,
                    "blast_score": score,
                }
            )
        return sorted(results, key=lambda x: x["blast_score"], reverse=True)

    def estimate_cost_impact(self) -> dict[str, Any]:
        workspace_costs: dict[str, float] = {}
        for r in self._records:
            workspace_costs.setdefault(r.workspace, 0.0)
            workspace_costs[r.workspace] += r.estimated_cost_delta
        total_delta = sum(r.estimated_cost_delta for r in self._records)
        return {
            "total_cost_delta": round(total_delta, 2),
            "by_workspace": {k: round(v, 2) for k, v in workspace_costs.items()},
            "cost_increasing_plans": sum(1 for r in self._records if r.estimated_cost_delta > 0),
            "cost_decreasing_plans": sum(1 for r in self._records if r.estimated_cost_delta < 0),
        }

    def identify_policy_violations(self) -> list[dict[str, Any]]:
        violators: list[dict[str, Any]] = []
        for r in self._records:
            if r.policy_violations > 0:
                violators.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "tool_type": r.tool_type.value,
                        "policy_violations": r.policy_violations,
                        "workspace": r.workspace,
                        "team": r.team,
                    }
                )
        return sorted(violators, key=lambda x: x["policy_violations"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> IacValidationReport:
        by_tool: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_blast: dict[str, int] = {}
        total_violations = 0
        total_cost = 0.0
        blast_scores: list[float] = []
        for r in self._records:
            by_tool[r.tool_type.value] = by_tool.get(r.tool_type.value, 0) + 1
            by_result[r.validation_result.value] = by_result.get(r.validation_result.value, 0) + 1
            by_blast[r.blast_radius.value] = by_blast.get(r.blast_radius.value, 0) + 1
            total_violations += r.policy_violations
            total_cost += r.estimated_cost_delta
            blast_scores.append(self.BLAST_RADIUS_WEIGHTS.get(r.blast_radius.value, 10.0))
        passed = sum(1 for r in self._records if r.validation_result == ValidationResult.PASSED)
        failed = sum(1 for r in self._records if r.validation_result == ValidationResult.FAILED)
        avg_blast = round(sum(blast_scores) / len(blast_scores), 2) if blast_scores else 0.0
        violators = self.identify_policy_violations()
        top_violators = [v["name"] for v in violators[:5]]
        recs: list[str] = []
        if failed > 0:
            recs.append(f"{failed} plan(s) failed validation — review before apply")
        if total_violations > 0:
            recs.append(f"{total_violations} total policy violation(s) detected")
        if total_cost > 1000.0:
            recs.append(f"Estimated cost increase ${total_cost:.2f} — review resource sizing")
        if not recs:
            recs.append("IaC validation pipeline is healthy — all plans passing")
        return IacValidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            passed_count=passed,
            failed_count=failed,
            total_policy_violations=total_violations,
            total_cost_delta=round(total_cost, 2),
            avg_blast_radius_score=avg_blast,
            by_tool_type=by_tool,
            by_result=by_result,
            by_blast_radius=by_blast,
            top_violators=top_violators,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("iac.validation.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tool_dist: dict[str, int] = {}
        for r in self._records:
            tool_dist[r.tool_type.value] = tool_dist.get(r.tool_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "violation_threshold": self._violation_threshold,
            "tool_type_distribution": tool_dist,
            "unique_workspaces": len({r.workspace for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
