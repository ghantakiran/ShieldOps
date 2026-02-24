"""Chaos Experiment Designer — design experiments with blast radius and rollback."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExperimentType(StrEnum):
    NETWORK_PARTITION = "network_partition"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SERVICE_KILL = "service_kill"
    LATENCY_INJECTION = "latency_injection"
    DEPENDENCY_FAILURE = "dependency_failure"


class BlastRadiusLevel(StrEnum):
    MINIMAL = "minimal"
    CONTAINED = "contained"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    CATASTROPHIC = "catastrophic"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"


# --- Models ---


class ExperimentDesign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    experiment_type: ExperimentType = ExperimentType.NETWORK_PARTITION
    target_service: str = ""
    blast_radius_level: BlastRadiusLevel = BlastRadiusLevel.MINIMAL
    status: ExperimentStatus = ExperimentStatus.DRAFT
    hypothesis: str = ""
    rollback_plan: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int = 30
    created_at: float = Field(default_factory=time.time)


class PrerequisiteCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    check_name: str = ""
    passed: bool = False
    details: str = ""
    checked_at: float = Field(default_factory=time.time)


class ChaosDesignReport(BaseModel):
    total_experiments: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    avg_blast_radius: float = 0.0
    coverage_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


_BLAST_RADIUS_ORDER = [
    BlastRadiusLevel.MINIMAL,
    BlastRadiusLevel.CONTAINED,
    BlastRadiusLevel.MODERATE,
    BlastRadiusLevel.SIGNIFICANT,
    BlastRadiusLevel.CATASTROPHIC,
]


class ChaosExperimentDesigner:
    """Design chaos experiments with blast radius estimation and rollback plans."""

    def __init__(
        self,
        max_experiments: int = 50000,
        max_blast_radius: int = 3,
    ) -> None:
        self._max_experiments = max_experiments
        self._max_blast_radius = max_blast_radius
        self._experiments: list[ExperimentDesign] = []
        self._prerequisite_checks: list[PrerequisiteCheck] = []
        logger.info(
            "chaos_designer.initialized",
            max_experiments=max_experiments,
            max_blast_radius=max_blast_radius,
        )

    def create_experiment(
        self,
        name: str,
        experiment_type: ExperimentType = ExperimentType.NETWORK_PARTITION,
        target_service: str = "",
        hypothesis: str = "",
        blast_radius_level: BlastRadiusLevel = BlastRadiusLevel.MINIMAL,
        rollback_plan: str = "",
        prerequisites: list[str] | None = None,
        affected_services: list[str] | None = None,
        estimated_duration_minutes: int = 30,
    ) -> ExperimentDesign:
        """Create and store a new chaos experiment design."""
        experiment = ExperimentDesign(
            name=name,
            experiment_type=experiment_type,
            target_service=target_service,
            hypothesis=hypothesis,
            blast_radius_level=blast_radius_level,
            rollback_plan=rollback_plan,
            prerequisites=prerequisites or [],
            affected_services=affected_services or [],
            estimated_duration_minutes=estimated_duration_minutes,
        )
        self._experiments.append(experiment)
        if len(self._experiments) > self._max_experiments:
            self._experiments = self._experiments[-self._max_experiments :]
        logger.info(
            "chaos_designer.experiment_created",
            exp_id=experiment.id,
            name=name,
            experiment_type=experiment_type,
            target_service=target_service,
        )
        return experiment

    def get_experiment(self, exp_id: str) -> ExperimentDesign | None:
        """Retrieve a single experiment by ID."""
        for e in self._experiments:
            if e.id == exp_id:
                return e
        return None

    def list_experiments(
        self,
        experiment_type: ExperimentType | None = None,
        status: ExperimentStatus | None = None,
        target_service: str | None = None,
        limit: int = 100,
    ) -> list[ExperimentDesign]:
        """List experiments with optional filtering."""
        results = list(self._experiments)
        if experiment_type is not None:
            results = [e for e in results if e.experiment_type == experiment_type]
        if status is not None:
            results = [e for e in results if e.status == status]
        if target_service is not None:
            results = [e for e in results if e.target_service == target_service]
        return results[-limit:]

    def estimate_blast_radius(self, exp_id: str) -> dict[str, Any]:
        """Estimate the blast radius of an experiment based on affected services count."""
        experiment = self.get_experiment(exp_id)
        if experiment is None:
            return {}
        affected_count = len(experiment.affected_services)
        if affected_count <= 1:
            level = BlastRadiusLevel.MINIMAL
        elif affected_count <= 3:
            level = BlastRadiusLevel.CONTAINED
        elif affected_count <= 6:
            level = BlastRadiusLevel.MODERATE
        elif affected_count <= 9:
            level = BlastRadiusLevel.SIGNIFICANT
        else:
            level = BlastRadiusLevel.CATASTROPHIC

        level_index = _BLAST_RADIUS_ORDER.index(level)
        exceeds_max = level_index > self._max_blast_radius

        logger.info(
            "chaos_designer.blast_radius_estimated",
            exp_id=exp_id,
            level=level.value,
            affected_count=affected_count,
            exceeds_max=exceeds_max,
        )
        return {
            "experiment_id": exp_id,
            "level": level.value,
            "affected_count": affected_count,
            "exceeds_max": exceeds_max,
        }

    def validate_prerequisites(self, exp_id: str) -> list[PrerequisiteCheck]:
        """Validate prerequisites for an experiment (simulated — all pass)."""
        experiment = self.get_experiment(exp_id)
        if experiment is None:
            return []
        checks: list[PrerequisiteCheck] = []
        for prereq in experiment.prerequisites:
            check = PrerequisiteCheck(
                experiment_id=exp_id,
                check_name=prereq,
                passed=True,
                details=f"Prerequisite '{prereq}' validated successfully",
            )
            checks.append(check)
            self._prerequisite_checks.append(check)
        logger.info(
            "chaos_designer.prerequisites_validated",
            exp_id=exp_id,
            check_count=len(checks),
        )
        return checks

    def generate_rollback_plan(self, exp_id: str) -> dict[str, Any]:
        """Generate a rollback plan for an experiment based on its type."""
        experiment = self.get_experiment(exp_id)
        if experiment is None:
            return {}

        rollback_steps: list[str] = []
        exp_type = experiment.experiment_type

        if exp_type == ExperimentType.NETWORK_PARTITION:
            rollback_steps = [
                "Remove network partition rules",
                "Verify connectivity restored",
                "Validate service health checks",
            ]
        elif exp_type == ExperimentType.RESOURCE_EXHAUSTION:
            rollback_steps = [
                "Kill resource exhaustion processes",
                "Release consumed resources",
                "Verify resource availability",
            ]
        elif exp_type == ExperimentType.SERVICE_KILL:
            rollback_steps = [
                "Restart killed service instances",
                "Verify service registration",
                "Confirm health check passing",
            ]
        elif exp_type == ExperimentType.LATENCY_INJECTION:
            rollback_steps = [
                "Remove latency injection rules",
                "Flush network queues",
                "Verify baseline latency restored",
            ]
        elif exp_type == ExperimentType.DEPENDENCY_FAILURE:
            rollback_steps = [
                "Restore dependency connections",
                "Clear circuit breaker states",
                "Verify dependency health",
            ]

        affected_count = len(experiment.affected_services) or 1
        estimated_rollback_minutes = 5 * affected_count

        logger.info(
            "chaos_designer.rollback_plan_generated",
            exp_id=exp_id,
            steps=len(rollback_steps),
            estimated_minutes=estimated_rollback_minutes,
        )
        return {
            "experiment_id": exp_id,
            "rollback_steps": rollback_steps,
            "estimated_rollback_minutes": estimated_rollback_minutes,
        }

    def approve_experiment(self, exp_id: str) -> ExperimentDesign | None:
        """Approve a DRAFT experiment, setting its status to APPROVED."""
        experiment = self.get_experiment(exp_id)
        if experiment is None or experiment.status != ExperimentStatus.DRAFT:
            return None
        experiment.status = ExperimentStatus.APPROVED
        logger.info(
            "chaos_designer.experiment_approved",
            exp_id=exp_id,
        )
        return experiment

    def analyze_experiment_coverage(self) -> dict[str, Any]:
        """Analyze coverage of experiment types."""
        all_types = set(ExperimentType)
        used_types = {e.experiment_type for e in self._experiments}
        types_covered = len(used_types)
        types_total = len(all_types)
        coverage_pct = round(types_covered / types_total * 100, 2) if types_total > 0 else 0.0
        uncovered_types = [t.value for t in all_types - used_types]

        logger.info(
            "chaos_designer.coverage_analyzed",
            types_covered=types_covered,
            types_total=types_total,
            coverage_pct=coverage_pct,
        )
        return {
            "types_covered": types_covered,
            "types_total": types_total,
            "coverage_pct": coverage_pct,
            "uncovered_types": sorted(uncovered_types),
        }

    def generate_design_report(self) -> ChaosDesignReport:
        """Generate a comprehensive chaos design report."""
        total = len(self._experiments)

        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        blast_radius_sum = 0.0

        for e in self._experiments:
            key_type = e.experiment_type.value
            by_type[key_type] = by_type.get(key_type, 0) + 1
            key_status = e.status.value
            by_status[key_status] = by_status.get(key_status, 0) + 1
            blast_radius_sum += _BLAST_RADIUS_ORDER.index(e.blast_radius_level)

        avg_blast_radius = round(blast_radius_sum / total, 2) if total > 0 else 0.0

        coverage = self.analyze_experiment_coverage()
        coverage_pct = coverage["coverage_pct"]

        recommendations: list[str] = []
        if coverage_pct < 100.0:
            recommendations.append(
                f"Only {coverage_pct}% experiment type coverage — "
                f"add experiments for: {', '.join(coverage['uncovered_types'])}"
            )
        draft_count = by_status.get(ExperimentStatus.DRAFT.value, 0)
        if draft_count > 0:
            recommendations.append(
                f"{draft_count} experiment(s) still in DRAFT — review and approve"
            )
        if avg_blast_radius > self._max_blast_radius:
            recommendations.append(
                "Average blast radius exceeds maximum threshold — review experiment scope"
            )

        report = ChaosDesignReport(
            total_experiments=total,
            by_type=by_type,
            by_status=by_status,
            avg_blast_radius=avg_blast_radius,
            coverage_pct=coverage_pct,
            recommendations=recommendations,
        )
        logger.info(
            "chaos_designer.report_generated",
            total_experiments=total,
            coverage_pct=coverage_pct,
            avg_blast_radius=avg_blast_radius,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored experiments and prerequisite checks."""
        self._experiments.clear()
        self._prerequisite_checks.clear()
        logger.info("chaos_designer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored experiments."""
        types: dict[str, int] = {}
        statuses: dict[str, int] = {}
        services: set[str] = set()
        for e in self._experiments:
            types[e.experiment_type.value] = types.get(e.experiment_type.value, 0) + 1
            statuses[e.status.value] = statuses.get(e.status.value, 0) + 1
            if e.target_service:
                services.add(e.target_service)
        return {
            "total_experiments": len(self._experiments),
            "total_prerequisite_checks": len(self._prerequisite_checks),
            "unique_target_services": len(services),
            "type_distribution": types,
            "status_distribution": statuses,
        }
