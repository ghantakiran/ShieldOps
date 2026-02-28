"""Change Freeze Validator — validate freeze windows and track violations."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreezeType(StrEnum):
    FULL_FREEZE = "full_freeze"
    PARTIAL_FREEZE = "partial_freeze"
    SOFT_FREEZE = "soft_freeze"
    EMERGENCY_ONLY = "emergency_only"
    MAINTENANCE_WINDOW = "maintenance_window"


class FreezeViolation(StrEnum):
    UNAUTHORIZED_DEPLOY = "unauthorized_deploy"
    SKIPPED_APPROVAL = "skipped_approval"
    BYPASS_POLICY = "bypass_policy"
    EMERGENCY_OVERRIDE = "emergency_override"
    SCHEDULED_CONFLICT = "scheduled_conflict"


class FreezeStatus(StrEnum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXTENDED = "extended"


# --- Models ---


class FreezeRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    freeze_name: str = ""
    freeze_type: FreezeType = FreezeType.FULL_FREEZE
    status: FreezeStatus = FreezeStatus.ACTIVE
    team: str = ""
    environment: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FreezeViolationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    freeze_id: str = ""
    violation_type: FreezeViolation = FreezeViolation.UNAUTHORIZED_DEPLOY
    deployer: str = ""
    service: str = ""
    severity_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FreezeValidatorReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_violations: int = 0
    violation_rate_pct: float = 0.0
    by_freeze_type: dict[str, int] = Field(default_factory=dict)
    by_violation_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_violators: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeFreezeValidator:
    """Validate change freeze windows and track violations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_violation_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_violation_rate_pct = max_violation_rate_pct
        self._records: list[FreezeRecord] = []
        self._violations: list[FreezeViolationRecord] = []
        logger.info(
            "freeze_validator.initialized",
            max_records=max_records,
            max_violation_rate_pct=max_violation_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_freeze(
        self,
        freeze_name: str,
        freeze_type: FreezeType = FreezeType.FULL_FREEZE,
        status: FreezeStatus = FreezeStatus.ACTIVE,
        team: str = "",
        environment: str = "",
        start_time: float = 0.0,
        end_time: float = 0.0,
        details: str = "",
    ) -> FreezeRecord:
        record = FreezeRecord(
            freeze_name=freeze_name,
            freeze_type=freeze_type,
            status=status,
            team=team,
            environment=environment,
            start_time=start_time,
            end_time=end_time,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "freeze_validator.freeze_recorded",
            record_id=record.id,
            freeze_name=freeze_name,
            freeze_type=freeze_type.value,
            status=status.value,
        )
        return record

    def get_freeze(self, record_id: str) -> FreezeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freezes(
        self,
        freeze_type: FreezeType | None = None,
        status: FreezeStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FreezeRecord]:
        results = list(self._records)
        if freeze_type is not None:
            results = [r for r in results if r.freeze_type == freeze_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_violation(
        self,
        freeze_id: str,
        violation_type: FreezeViolation = (FreezeViolation.UNAUTHORIZED_DEPLOY),
        deployer: str = "",
        service: str = "",
        severity_score: float = 0.0,
    ) -> FreezeViolationRecord:
        violation = FreezeViolationRecord(
            freeze_id=freeze_id,
            violation_type=violation_type,
            deployer=deployer,
            service=service,
            severity_score=severity_score,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_records:
            self._violations = self._violations[-self._max_records :]
        logger.info(
            "freeze_validator.violation_added",
            violation_id=violation.id,
            freeze_id=freeze_id,
            violation_type=violation_type.value,
        )
        return violation

    # -- domain operations -------------------------------------------

    def analyze_freeze_compliance(self) -> dict[str, Any]:
        """Analyze overall freeze compliance metrics."""
        total = len(self._records)
        violations = len(self._violations)
        if total == 0:
            return {"status": "no_data"}
        rate = round(violations / total * 100.0, 2)
        return {
            "total_freezes": total,
            "total_violations": violations,
            "violation_rate_pct": rate,
            "within_threshold": (rate <= self._max_violation_rate_pct),
        }

    def identify_frequent_violators(
        self,
    ) -> list[dict[str, Any]]:
        """Find deployers with >1 violation, sorted desc."""
        deployer_counts: dict[str, int] = {}
        for v in self._violations:
            deployer_counts[v.deployer] = deployer_counts.get(v.deployer, 0) + 1
        results: list[dict[str, Any]] = []
        for deployer, count in deployer_counts.items():
            if count > 1:
                results.append(
                    {
                        "deployer": deployer,
                        "violation_count": count,
                    }
                )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_by_severity_score(
        self,
    ) -> list[dict[str, Any]]:
        """Average severity per deployer, sorted desc."""
        deployer_scores: dict[str, list[float]] = {}
        for v in self._violations:
            deployer_scores.setdefault(v.deployer, []).append(v.severity_score)
        results: list[dict[str, Any]] = []
        for deployer, scores in deployer_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "deployer": deployer,
                    "avg_severity_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_severity_score"],
            reverse=True,
        )
        return results

    def detect_violation_trends(
        self,
    ) -> list[dict[str, Any]]:
        """Detect deployers with >3 violations (trending)."""
        deployer_counts: dict[str, int] = {}
        for v in self._violations:
            deployer_counts[v.deployer] = deployer_counts.get(v.deployer, 0) + 1
        results: list[dict[str, Any]] = []
        for deployer, count in deployer_counts.items():
            if count > 3:
                results.append(
                    {
                        "deployer": deployer,
                        "violation_count": count,
                    }
                )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> FreezeValidatorReport:
        by_freeze_type: dict[str, int] = {}
        by_violation_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            ft = r.freeze_type.value
            by_freeze_type[ft] = by_freeze_type.get(ft, 0) + 1
            st = r.status.value
            by_status[st] = by_status.get(st, 0) + 1
        for v in self._violations:
            vt = v.violation_type.value
            by_violation_type[vt] = by_violation_type.get(vt, 0) + 1
        total = len(self._records)
        violations = len(self._violations)
        rate = round(violations / total * 100.0, 2) if total else 0.0
        # top violators
        deployer_counts: dict[str, int] = {}
        for v in self._violations:
            deployer_counts[v.deployer] = deployer_counts.get(v.deployer, 0) + 1
        sorted_violators = sorted(
            deployer_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        top_violators = [d for d, _ in sorted_violators[:10]]
        recs: list[str] = []
        if rate > self._max_violation_rate_pct:
            recs.append(f"Violation rate {rate}% exceeds {self._max_violation_rate_pct}% threshold")
        high_sev = sum(1 for v in self._violations if v.severity_score > 8.0)
        if high_sev > 0:
            recs.append(f"{high_sev} high-severity violation(s) detected")
        if not recs:
            recs.append("Freeze compliance within acceptable limits")
        return FreezeValidatorReport(
            total_records=total,
            total_violations=violations,
            violation_rate_pct=rate,
            by_freeze_type=by_freeze_type,
            by_violation_type=by_violation_type,
            by_status=by_status,
            top_violators=top_violators,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._violations.clear()
        logger.info("freeze_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freeze_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_freezes": len(self._records),
            "total_violations": len(self._violations),
            "max_violation_rate_pct": (self._max_violation_rate_pct),
            "freeze_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
