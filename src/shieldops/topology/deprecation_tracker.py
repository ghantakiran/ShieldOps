"""Service Deprecation Tracker — track service deprecation stages, migration plans, and urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeprecationStage(StrEnum):
    ANNOUNCED = "announced"
    MIGRATION_PERIOD = "migration_period"
    SUNSET_WARNING = "sunset_warning"
    END_OF_LIFE = "end_of_life"
    DECOMMISSIONED = "decommissioned"


class DeprecationImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class MigrationStatus(StrEnum):
    NOT_STARTED = "not_started"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    NEARLY_COMPLETE = "nearly_complete"
    COMPLETED = "completed"


# --- Models ---


class DeprecationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    stage: DeprecationStage = DeprecationStage.ANNOUNCED
    impact: DeprecationImpact = DeprecationImpact.MODERATE
    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED
    eol_date: float = 0.0
    dependent_services: list[str] = Field(default_factory=list)
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MigrationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    target_service: str = ""
    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED
    planned_completion_date: float = 0.0
    owner_team: str = ""
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class DeprecationTrackerReport(BaseModel):
    total_deprecations: int = 0
    total_migration_plans: int = 0
    overdue_count: int = 0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_migration_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDeprecationTracker:
    """Track service deprecation stages, migration plans, and urgency."""

    def __init__(
        self,
        max_records: int = 200000,
        max_overdue_days: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._max_overdue_days = max_overdue_days
        self._records: list[DeprecationRecord] = []
        self._migration_plans: list[MigrationPlan] = []
        logger.info(
            "deprecation_tracker.initialized",
            max_records=max_records,
            max_overdue_days=max_overdue_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_deprecation(
        self,
        service_name: str,
        stage: DeprecationStage = DeprecationStage.ANNOUNCED,
        impact: DeprecationImpact = DeprecationImpact.MODERATE,
        migration_status: MigrationStatus = MigrationStatus.NOT_STARTED,
        eol_date: float = 0.0,
        dependent_services: list[str] | None = None,
        details: str = "",
    ) -> DeprecationRecord:
        record = DeprecationRecord(
            service_name=service_name,
            stage=stage,
            impact=impact,
            migration_status=migration_status,
            eol_date=eol_date,
            dependent_services=dependent_services or [],
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deprecation_tracker.deprecation_recorded",
            record_id=record.id,
            service_name=service_name,
            stage=stage.value,
            impact=impact.value,
        )
        return record

    def get_deprecation(self, record_id: str) -> DeprecationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_deprecations(
        self,
        service_name: str | None = None,
        stage: DeprecationStage | None = None,
        limit: int = 50,
    ) -> list[DeprecationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        return results[-limit:]

    def add_migration_plan(
        self,
        service_name: str,
        target_service: str = "",
        migration_status: MigrationStatus = MigrationStatus.NOT_STARTED,
        planned_completion_date: float = 0.0,
        owner_team: str = "",
        notes: str = "",
    ) -> MigrationPlan:
        plan = MigrationPlan(
            service_name=service_name,
            target_service=target_service,
            migration_status=migration_status,
            planned_completion_date=planned_completion_date,
            owner_team=owner_team,
            notes=notes,
        )
        self._migration_plans.append(plan)
        if len(self._migration_plans) > self._max_records:
            self._migration_plans = self._migration_plans[-self._max_records :]
        logger.info(
            "deprecation_tracker.migration_plan_added",
            service_name=service_name,
            target_service=target_service,
            migration_status=migration_status.value,
        )
        return plan

    # -- domain operations -----------------------------------------------

    def analyze_deprecation_by_stage(self) -> dict[str, Any]:
        """Analyze deprecation records grouped by stage."""
        stage_counts: dict[str, int] = {}
        stage_impact: dict[str, list[str]] = {}
        for r in self._records:
            key = r.stage.value
            stage_counts[key] = stage_counts.get(key, 0) + 1
            stage_impact.setdefault(key, []).append(r.impact.value)
        summary: dict[str, Any] = {}
        for stage, count in stage_counts.items():
            impacts = stage_impact.get(stage, [])
            critical_count = impacts.count("critical")
            summary[stage] = {
                "count": count,
                "critical_impact_count": critical_count,
            }
        return {"by_stage": summary, "total_deprecations": len(self._records)}

    def identify_overdue_migrations(self) -> list[dict[str, Any]]:
        """Find services whose EOL date has passed without completed migration."""
        now = time.time()
        overdue_threshold = self._max_overdue_days * 86400
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.eol_date > 0
                and r.eol_date < now
                and r.migration_status != MigrationStatus.COMPLETED
            ):
                overdue_seconds = now - r.eol_date
                overdue_days = round(overdue_seconds / 86400, 1)
                results.append(
                    {
                        "service_name": r.service_name,
                        "overdue_days": overdue_days,
                        "migration_status": r.migration_status.value,
                        "exceeds_threshold": overdue_seconds > overdue_threshold,
                    }
                )
        results.sort(key=lambda x: x["overdue_days"], reverse=True)
        return results

    def rank_by_urgency(self) -> list[dict[str, Any]]:
        """Rank deprecation records by urgency (stage + impact)."""
        stage_order = {
            DeprecationStage.DECOMMISSIONED: 5,
            DeprecationStage.END_OF_LIFE: 4,
            DeprecationStage.SUNSET_WARNING: 3,
            DeprecationStage.MIGRATION_PERIOD: 2,
            DeprecationStage.ANNOUNCED: 1,
        }
        impact_order = {
            DeprecationImpact.CRITICAL: 5,
            DeprecationImpact.HIGH: 4,
            DeprecationImpact.MODERATE: 3,
            DeprecationImpact.LOW: 2,
            DeprecationImpact.MINIMAL: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            urgency_score = stage_order.get(r.stage, 0) + impact_order.get(r.impact, 0)
            results.append(
                {
                    "service_name": r.service_name,
                    "stage": r.stage.value,
                    "impact": r.impact.value,
                    "urgency_score": urgency_score,
                    "migration_status": r.migration_status.value,
                }
            )
        results.sort(key=lambda x: x["urgency_score"], reverse=True)
        return results

    def detect_deprecation_risks(self) -> list[dict[str, Any]]:
        """Detect high-risk deprecations: critical impact with no migration progress."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            is_high_risk = (
                r.impact in (DeprecationImpact.CRITICAL, DeprecationImpact.HIGH)
                and r.migration_status in (MigrationStatus.NOT_STARTED, MigrationStatus.PLANNING)
                and r.stage
                in (
                    DeprecationStage.SUNSET_WARNING,
                    DeprecationStage.END_OF_LIFE,
                    DeprecationStage.DECOMMISSIONED,
                )
            )
            if is_high_risk:
                results.append(
                    {
                        "service_name": r.service_name,
                        "stage": r.stage.value,
                        "impact": r.impact.value,
                        "migration_status": r.migration_status.value,
                        "dependent_services_count": len(r.dependent_services),
                        "risk_reason": "high_impact_no_migration_progress",
                    }
                )
        results.sort(key=lambda x: x["dependent_services_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DeprecationTrackerReport:
        by_stage: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_migration: dict[str, int] = {}
        for r in self._records:
            by_stage[r.stage.value] = by_stage.get(r.stage.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
            by_migration[r.migration_status.value] = (
                by_migration.get(r.migration_status.value, 0) + 1
            )
        overdue = self.identify_overdue_migrations()
        risks = self.detect_deprecation_risks()
        recs: list[str] = []
        if overdue:
            recs.append(f"{len(overdue)} service(s) have overdue migrations past EOL date")
        if risks:
            recs.append(
                f"{len(risks)} high-risk deprecation(s) with no migration progress detected"
            )
        eol_count = by_stage.get("end_of_life", 0) + by_stage.get("decommissioned", 0)
        if eol_count > 0:
            recs.append(f"{eol_count} service(s) at end-of-life or decommissioned stage")
        if not recs:
            recs.append("All deprecation timelines and migrations are on track")
        return DeprecationTrackerReport(
            total_deprecations=len(self._records),
            total_migration_plans=len(self._migration_plans),
            overdue_count=len(overdue),
            by_stage=by_stage,
            by_impact=by_impact,
            by_migration_status=by_migration,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._migration_plans.clear()
        logger.info("deprecation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_deprecations": len(self._records),
            "total_migration_plans": len(self._migration_plans),
            "max_overdue_days": self._max_overdue_days,
            "stage_distribution": stage_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
