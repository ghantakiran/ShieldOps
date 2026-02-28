"""Chaos Experiment Automator — automated chaos experiment scheduling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChaosType(StrEnum):
    LATENCY_INJECTION = "latency_injection"
    SERVICE_KILL = "service_kill"
    CPU_STRESS = "cpu_stress"
    MEMORY_PRESSURE = "memory_pressure"
    NETWORK_PARTITION = "network_partition"


class ChaosOutcome(StrEnum):
    PASSED = "passed"
    DEGRADED = "degraded"
    FAILED = "failed"
    ABORTED = "aborted"
    INCONCLUSIVE = "inconclusive"


class BlastRadius(StrEnum):
    SINGLE_POD = "single_pod"
    SINGLE_SERVICE = "single_service"
    SERVICE_GROUP = "service_group"
    AVAILABILITY_ZONE = "availability_zone"
    REGION = "region"


# --- Models ---


class ChaosRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_name: str = ""
    chaos_type: ChaosType = ChaosType.LATENCY_INJECTION
    outcome: ChaosOutcome = ChaosOutcome.PASSED
    blast_radius: BlastRadius = BlastRadius.SINGLE_POD
    impact_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ChaosSchedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_name: str = ""
    chaos_type: ChaosType = ChaosType.LATENCY_INJECTION
    blast_radius: BlastRadius = BlastRadius.SINGLE_POD
    frequency_days: int = 7
    auto_rollback: bool = True
    created_at: float = Field(default_factory=time.time)


class ChaosAutomatorReport(BaseModel):
    total_experiments: int = 0
    total_schedules: int = 0
    pass_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    failed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChaosExperimentAutomator:
    """Automated chaos experiment scheduling."""

    def __init__(
        self,
        max_records: int = 200000,
        min_pass_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_pass_rate_pct = min_pass_rate_pct
        self._records: list[ChaosRecord] = []
        self._schedules: list[ChaosSchedule] = []
        logger.info(
            "chaos_automator.initialized",
            max_records=max_records,
            min_pass_rate_pct=min_pass_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_experiment(
        self,
        experiment_name: str,
        chaos_type: ChaosType = (ChaosType.LATENCY_INJECTION),
        outcome: ChaosOutcome = ChaosOutcome.PASSED,
        blast_radius: BlastRadius = (BlastRadius.SINGLE_POD),
        impact_score: float = 0.0,
        details: str = "",
    ) -> ChaosRecord:
        record = ChaosRecord(
            experiment_name=experiment_name,
            chaos_type=chaos_type,
            outcome=outcome,
            blast_radius=blast_radius,
            impact_score=impact_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "chaos_automator.experiment_recorded",
            record_id=record.id,
            experiment_name=experiment_name,
            chaos_type=chaos_type.value,
            outcome=outcome.value,
        )
        return record

    def get_experiment(self, record_id: str) -> ChaosRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_experiments(
        self,
        experiment_name: str | None = None,
        chaos_type: ChaosType | None = None,
        limit: int = 50,
    ) -> list[ChaosRecord]:
        results = list(self._records)
        if experiment_name is not None:
            results = [r for r in results if r.experiment_name == experiment_name]
        if chaos_type is not None:
            results = [r for r in results if r.chaos_type == chaos_type]
        return results[-limit:]

    def add_schedule(
        self,
        schedule_name: str,
        chaos_type: ChaosType = (ChaosType.LATENCY_INJECTION),
        blast_radius: BlastRadius = (BlastRadius.SINGLE_POD),
        frequency_days: int = 7,
        auto_rollback: bool = True,
    ) -> ChaosSchedule:
        schedule = ChaosSchedule(
            schedule_name=schedule_name,
            chaos_type=chaos_type,
            blast_radius=blast_radius,
            frequency_days=frequency_days,
            auto_rollback=auto_rollback,
        )
        self._schedules.append(schedule)
        if len(self._schedules) > self._max_records:
            self._schedules = self._schedules[-self._max_records :]
        logger.info(
            "chaos_automator.schedule_added",
            schedule_name=schedule_name,
            chaos_type=chaos_type.value,
            blast_radius=blast_radius.value,
        )
        return schedule

    # -- domain operations -------------------------------------------

    def analyze_experiment_results(self, experiment_name: str) -> dict[str, Any]:
        """Analyze results for a specific experiment."""
        records = [r for r in self._records if r.experiment_name == experiment_name]
        if not records:
            return {
                "experiment_name": experiment_name,
                "status": "no_data",
            }
        passed = sum(1 for r in records if r.outcome == ChaosOutcome.PASSED)
        pass_rate = round(passed / len(records) * 100, 2)
        avg_impact = round(
            sum(r.impact_score for r in records) / len(records),
            2,
        )
        return {
            "experiment_name": experiment_name,
            "experiment_count": len(records),
            "passed_count": passed,
            "pass_rate": pass_rate,
            "avg_impact": avg_impact,
            "meets_threshold": (pass_rate >= self._min_pass_rate_pct),
        }

    def identify_failed_experiments(
        self,
    ) -> list[dict[str, Any]]:
        """Find experiments with repeated failures."""
        fail_counts: dict[str, int] = {}
        for r in self._records:
            if r.outcome in (
                ChaosOutcome.FAILED,
                ChaosOutcome.ABORTED,
            ):
                fail_counts[r.experiment_name] = fail_counts.get(r.experiment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for exp, count in fail_counts.items():
            if count > 1:
                results.append(
                    {
                        "experiment_name": exp,
                        "failure_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["failure_count"],
            reverse=True,
        )
        return results

    def rank_by_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank experiments by avg impact desc."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.experiment_name, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for exp, scores in totals.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "experiment_name": exp,
                    "avg_impact": avg,
                    "experiment_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_impact"],
            reverse=True,
        )
        return results

    def detect_experiment_regressions(
        self,
    ) -> list[dict[str, Any]]:
        """Detect experiments with >3 non-PASSED."""
        exp_non: dict[str, int] = {}
        for r in self._records:
            if r.outcome != ChaosOutcome.PASSED:
                exp_non[r.experiment_name] = exp_non.get(r.experiment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for exp, count in exp_non.items():
            if count > 3:
                results.append(
                    {
                        "experiment_name": exp,
                        "non_passed_count": count,
                        "regression_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_passed_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> ChaosAutomatorReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.chaos_type.value] = by_type.get(r.chaos_type.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        passed = sum(1 for r in self._records if r.outcome == ChaosOutcome.PASSED)
        rate = round(passed / len(self._records) * 100, 2) if self._records else 0.0
        failed_count = sum(1 for d in self.identify_failed_experiments())
        recs: list[str] = []
        if rate < self._min_pass_rate_pct:
            recs.append(f"Pass rate {rate}% is below {self._min_pass_rate_pct}% threshold")
        if failed_count > 0:
            recs.append(f"{failed_count} experiment(s) with repeated failures")
        regs = len(self.detect_experiment_regressions())
        if regs > 0:
            recs.append(f"{regs} experiment(s) with regressions")
        if not recs:
            recs.append("Chaos experiment health meets targets")
        return ChaosAutomatorReport(
            total_experiments=len(self._records),
            total_schedules=len(self._schedules),
            pass_rate_pct=rate,
            by_type=by_type,
            by_outcome=by_outcome,
            failed_count=failed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._schedules.clear()
        logger.info("chaos_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.chaos_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_experiments": len(self._records),
            "total_schedules": len(self._schedules),
            "min_pass_rate_pct": (self._min_pass_rate_pct),
            "type_distribution": type_dist,
            "unique_experiments": len({r.experiment_name for r in self._records}),
        }
