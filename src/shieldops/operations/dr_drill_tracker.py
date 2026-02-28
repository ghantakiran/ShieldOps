"""DR Drill Tracker — track disaster recovery drill execution, outcomes, and RTO/RPO validation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DrillType(StrEnum):
    FAILOVER = "failover"
    BACKUP_RESTORE = "backup_restore"
    NETWORK_PARTITION = "network_partition"
    DATA_CENTER_LOSS = "data_center_loss"
    CASCADING_FAILURE = "cascading_failure"


class DrillOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ABORTED = "aborted"


class DrillScope(StrEnum):
    SINGLE_SERVICE = "single_service"
    MULTI_SERVICE = "multi_service"
    REGIONAL = "regional"
    CROSS_REGION = "cross_region"
    FULL_PLATFORM = "full_platform"


# --- Models ---


class DrillRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    drill_type: DrillType = DrillType.FAILOVER
    outcome: DrillOutcome = DrillOutcome.SUCCESS
    scope: DrillScope = DrillScope.SINGLE_SERVICE
    recovery_time_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DrillFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_name: str = ""
    drill_type: DrillType = DrillType.FAILOVER
    outcome: DrillOutcome = DrillOutcome.SUCCESS
    severity_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DRDrillReport(BaseModel):
    total_drills: int = 0
    total_findings: int = 0
    avg_recovery_time_min: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    failed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DRDrillTracker:
    """Track disaster recovery drill execution, outcomes, and RTO/RPO validation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate_pct = min_success_rate_pct
        self._records: list[DrillRecord] = []
        self._findings: list[DrillFinding] = []
        logger.info(
            "dr_drill_tracker.initialized",
            max_records=max_records,
            min_success_rate_pct=min_success_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_drill(
        self,
        service_name: str,
        drill_type: DrillType = DrillType.FAILOVER,
        outcome: DrillOutcome = DrillOutcome.SUCCESS,
        scope: DrillScope = DrillScope.SINGLE_SERVICE,
        recovery_time_minutes: float = 0.0,
        details: str = "",
    ) -> DrillRecord:
        record = DrillRecord(
            service_name=service_name,
            drill_type=drill_type,
            outcome=outcome,
            scope=scope,
            recovery_time_minutes=recovery_time_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dr_drill_tracker.drill_recorded",
            record_id=record.id,
            service_name=service_name,
            outcome=outcome.value,
        )
        return record

    def get_drill(self, record_id: str) -> DrillRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drills(
        self,
        service_name: str | None = None,
        drill_type: DrillType | None = None,
        limit: int = 50,
    ) -> list[DrillRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if drill_type is not None:
            results = [r for r in results if r.drill_type == drill_type]
        return results[-limit:]

    def add_finding(
        self,
        finding_name: str,
        drill_type: DrillType = DrillType.FAILOVER,
        outcome: DrillOutcome = DrillOutcome.SUCCESS,
        severity_score: float = 0.0,
        description: str = "",
    ) -> DrillFinding:
        finding = DrillFinding(
            finding_name=finding_name,
            drill_type=drill_type,
            outcome=outcome,
            severity_score=severity_score,
            description=description,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_records:
            self._findings = self._findings[-self._max_records :]
        logger.info(
            "dr_drill_tracker.finding_added",
            finding_name=finding_name,
            outcome=outcome.value,
        )
        return finding

    # -- domain operations -----------------------------------------------

    def analyze_drill_effectiveness(self, service_name: str) -> dict[str, Any]:
        """Analyze success rate for a service and check threshold."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        success_count = sum(1 for r in svc_records if r.outcome == DrillOutcome.SUCCESS)
        success_rate = round((success_count / len(svc_records)) * 100, 2)
        meets_threshold = success_rate >= self._min_success_rate_pct
        return {
            "service_name": service_name,
            "success_rate": success_rate,
            "record_count": len(svc_records),
            "meets_threshold": meets_threshold,
            "min_success_rate_pct": self._min_success_rate_pct,
        }

    def identify_failed_drills(self) -> list[dict[str, Any]]:
        """Find services with more than one FAILED or TIMEOUT drill."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.outcome in (DrillOutcome.FAILED, DrillOutcome.TIMEOUT):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "failed_timeout_count": count})
        results.sort(key=lambda x: x["failed_timeout_count"], reverse=True)
        return results

    def rank_by_recovery_time(self) -> list[dict[str, Any]]:
        """Rank services by average recovery time descending."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service_name, []).append(r.recovery_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            avg = round(sum(times) / len(times), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_recovery_time_min": avg,
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_recovery_time_min"], reverse=True)
        return results

    def detect_drill_trends(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 drill records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DRDrillReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.drill_type.value] = by_type.get(r.drill_type.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        avg_time = (
            round(
                sum(r.recovery_time_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        failed_count = sum(1 for r in self._records if r.outcome == DrillOutcome.FAILED)
        recs: list[str] = []
        if failed_count > 0:
            recs.append(f"{failed_count} drill(s) failed")
        timeout_count = sum(1 for r in self._records if r.outcome == DrillOutcome.TIMEOUT)
        if timeout_count > 0:
            recs.append(f"{timeout_count} drill(s) timed out")
        if not recs:
            recs.append("DR drill outcomes are healthy")
        return DRDrillReport(
            total_drills=len(self._records),
            total_findings=len(self._findings),
            avg_recovery_time_min=avg_time,
            by_type=by_type,
            by_outcome=by_outcome,
            failed_count=failed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._findings.clear()
        logger.info("dr_drill_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drill_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_drills": len(self._records),
            "total_findings": len(self._findings),
            "min_success_rate_pct": self._min_success_rate_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
