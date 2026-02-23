"""Chaos Experiment Tracker — tracks chaos engineering experiments."""

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
    LATENCY_INJECTION = "latency_injection"
    FAULT_INJECTION = "fault_injection"
    RESOURCE_STRESS = "resource_stress"
    NETWORK_PARTITION = "network_partition"
    NODE_FAILURE = "node_failure"
    DEPENDENCY_FAILURE = "dependency_failure"


class ExperimentStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


# --- Models ---


class ChaosExperiment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    experiment_type: ExperimentType
    target_service: str
    hypothesis: str = ""
    blast_radius: str = "single-service"
    status: ExperimentStatus = ExperimentStatus.PLANNED
    started_at: float | None = None
    completed_at: float | None = None
    findings: list[str] = Field(default_factory=list)
    steady_state_met: bool | None = None
    rollback_triggered: bool = False
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ExperimentResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str
    metric_name: str
    baseline_value: float = 0.0
    observed_value: float = 0.0
    impact_pct: float = 0.0
    within_tolerance: bool = True
    recorded_at: float = Field(default_factory=time.time)


# --- Tracker ---


class ChaosExperimentTracker:
    """Tracks chaos engineering experiments and their impact on system reliability."""

    def __init__(self, max_experiments: int = 5000, max_results: int = 50000) -> None:
        self.max_experiments = max_experiments
        self.max_results = max_results
        self._experiments: dict[str, ChaosExperiment] = {}
        self._results: list[ExperimentResult] = []
        logger.info(
            "chaos_experiment_tracker.initialized",
            max_experiments=max_experiments,
            max_results=max_results,
        )

    def create_experiment(
        self, name: str, experiment_type: ExperimentType, target_service: str, **kw: Any
    ) -> ChaosExperiment:
        """Create a new chaos experiment."""
        if len(self._experiments) >= self.max_experiments:
            raise ValueError(f"Max experiments limit reached ({self.max_experiments})")
        experiment = ChaosExperiment(
            name=name,
            experiment_type=experiment_type,
            target_service=target_service,
            **kw,
        )
        self._experiments[experiment.id] = experiment
        logger.info(
            "chaos_experiment_tracker.experiment_created",
            experiment_id=experiment.id,
            name=name,
            experiment_type=experiment_type,
            target_service=target_service,
        )
        return experiment

    def start_experiment(self, experiment_id: str) -> ChaosExperiment | None:
        """Start a chaos experiment."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return None
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = time.time()
        logger.info(
            "chaos_experiment_tracker.experiment_started",
            experiment_id=experiment_id,
        )
        return experiment

    def complete_experiment(
        self,
        experiment_id: str,
        steady_state_met: bool,
        findings: list[str] | None = None,
    ) -> ChaosExperiment | None:
        """Complete a chaos experiment."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return None
        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = time.time()
        experiment.steady_state_met = steady_state_met
        if findings is not None:
            experiment.findings = findings
        logger.info(
            "chaos_experiment_tracker.experiment_completed",
            experiment_id=experiment_id,
            steady_state_met=steady_state_met,
        )
        return experiment

    def abort_experiment(self, experiment_id: str, reason: str = "") -> ChaosExperiment | None:
        """Abort a chaos experiment and trigger rollback."""
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            return None
        experiment.status = ExperimentStatus.ABORTED
        experiment.rollback_triggered = True
        experiment.completed_at = time.time()
        if reason:
            experiment.findings.append(reason)
        logger.warning(
            "chaos_experiment_tracker.experiment_aborted",
            experiment_id=experiment_id,
            reason=reason,
        )
        return experiment

    def record_result(
        self,
        experiment_id: str,
        metric_name: str,
        baseline_value: float,
        observed_value: float,
        tolerance_pct: float = 10.0,
    ) -> ExperimentResult:
        """Record a metric result for an experiment.

        Computes impact_pct as abs(observed - baseline) / baseline * 100 if baseline != 0.
        within_tolerance is True if impact_pct <= tolerance_pct.
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment not found: {experiment_id}")

        if baseline_value != 0:
            impact_pct = abs(observed_value - baseline_value) / abs(baseline_value) * 100.0
        else:
            impact_pct = 0.0

        within_tolerance = impact_pct <= tolerance_pct

        result = ExperimentResult(
            experiment_id=experiment_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            observed_value=observed_value,
            impact_pct=impact_pct,
            within_tolerance=within_tolerance,
        )
        self._results.append(result)
        if len(self._results) > self.max_results:
            self._results = self._results[-self.max_results :]

        logger.info(
            "chaos_experiment_tracker.result_recorded",
            result_id=result.id,
            experiment_id=experiment_id,
            metric_name=metric_name,
            impact_pct=impact_pct,
            within_tolerance=within_tolerance,
        )
        return result

    def get_experiment(self, experiment_id: str) -> ChaosExperiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        target_service: str | None = None,
    ) -> list[ChaosExperiment]:
        """List experiments with optional filters."""
        results = list(self._experiments.values())
        if status is not None:
            results = [e for e in results if e.status == status]
        if target_service is not None:
            results = [e for e in results if e.target_service == target_service]
        return results

    def get_results(self, experiment_id: str) -> list[ExperimentResult]:
        """Get results for a specific experiment."""
        return [r for r in self._results if r.experiment_id == experiment_id]

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment."""
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            logger.info(
                "chaos_experiment_tracker.experiment_deleted",
                experiment_id=experiment_id,
            )
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        experiments = list(self._experiments.values())
        by_status: dict[str, int] = {}
        for e in experiments:
            by_status[e.status] = by_status.get(e.status, 0) + 1

        completed = [e for e in experiments if e.status == ExperimentStatus.COMPLETED]
        steady_state_success = sum(1 for e in completed if e.steady_state_met)
        steady_state_rate = (steady_state_success / len(completed)) * 100.0 if completed else 0.0

        all_results = self._results
        avg_impact = (
            sum(r.impact_pct for r in all_results) / len(all_results) if all_results else 0.0
        )

        return {
            "total_experiments": len(experiments),
            "by_status": by_status,
            "steady_state_success_rate": steady_state_rate,
            "total_results": len(all_results),
            "avg_impact_pct": avg_impact,
        }
