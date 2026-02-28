"""Change Freeze Manager — manage change freeze windows and exceptions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreezeType(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    EMERGENCY_ONLY = "emergency_only"
    SCHEDULED = "scheduled"
    CUSTOM = "custom"


class FreezeScope(StrEnum):
    GLOBAL = "global"
    TEAM = "team"
    SERVICE = "service"
    ENVIRONMENT = "environment"
    REGION = "region"


class ExceptionStatus(StrEnum):
    APPROVED = "approved"
    PENDING = "pending"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


# --- Models ---


class FreezeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    freeze_name: str = ""
    freeze_type: FreezeType = FreezeType.FULL
    scope: FreezeScope = FreezeScope.GLOBAL
    exception_status: ExceptionStatus = ExceptionStatus.PENDING
    duration_hours: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FreezeException(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_name: str = ""
    freeze_type: FreezeType = FreezeType.FULL
    scope: FreezeScope = FreezeScope.GLOBAL
    reason: str = ""
    approved_by: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeFreezeReport(BaseModel):
    total_freezes: int = 0
    total_exceptions: int = 0
    compliance_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    exception_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeFreezeManager:
    """Manage change freeze windows and exceptions."""

    def __init__(
        self,
        max_records: int = 200000,
        max_exception_rate_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_exception_rate_pct = max_exception_rate_pct
        self._records: list[FreezeRecord] = []
        self._exceptions: list[FreezeException] = []
        logger.info(
            "change_freeze.initialized",
            max_records=max_records,
            max_exception_rate_pct=max_exception_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_freeze(
        self,
        freeze_name: str,
        freeze_type: FreezeType = FreezeType.FULL,
        scope: FreezeScope = FreezeScope.GLOBAL,
        exception_status: ExceptionStatus = ExceptionStatus.PENDING,
        duration_hours: float = 0.0,
        details: str = "",
    ) -> FreezeRecord:
        record = FreezeRecord(
            freeze_name=freeze_name,
            freeze_type=freeze_type,
            scope=scope,
            exception_status=exception_status,
            duration_hours=duration_hours,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_freeze.freeze_recorded",
            record_id=record.id,
            freeze_name=freeze_name,
            freeze_type=freeze_type.value,
            scope=scope.value,
        )
        return record

    def get_freeze(self, record_id: str) -> FreezeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freezes(
        self,
        freeze_name: str | None = None,
        freeze_type: FreezeType | None = None,
        limit: int = 50,
    ) -> list[FreezeRecord]:
        results = list(self._records)
        if freeze_name is not None:
            results = [r for r in results if r.freeze_name == freeze_name]
        if freeze_type is not None:
            results = [r for r in results if r.freeze_type == freeze_type]
        return results[-limit:]

    def add_exception(
        self,
        exception_name: str,
        freeze_type: FreezeType = FreezeType.FULL,
        scope: FreezeScope = FreezeScope.GLOBAL,
        reason: str = "",
        approved_by: str = "",
    ) -> FreezeException:
        exception = FreezeException(
            exception_name=exception_name,
            freeze_type=freeze_type,
            scope=scope,
            reason=reason,
            approved_by=approved_by,
        )
        self._exceptions.append(exception)
        if len(self._exceptions) > self._max_records:
            self._exceptions = self._exceptions[-self._max_records :]
        logger.info(
            "change_freeze.exception_added",
            exception_name=exception_name,
            freeze_type=freeze_type.value,
            scope=scope.value,
        )
        return exception

    # -- domain operations -----------------------------------------------

    def analyze_freeze_effectiveness(self, freeze_name: str) -> dict[str, Any]:
        """Analyze freeze effectiveness for a specific freeze name."""
        records = [r for r in self._records if r.freeze_name == freeze_name]
        if not records:
            return {"freeze_name": freeze_name, "status": "no_data"}
        avg_duration = round(sum(r.duration_hours for r in records) / len(records), 2)
        approved_count = sum(1 for r in records if r.exception_status == ExceptionStatus.APPROVED)
        exception_rate = round(approved_count / len(records) * 100, 2)
        return {
            "freeze_name": freeze_name,
            "avg_duration": avg_duration,
            "record_count": len(records),
            "exception_rate": exception_rate,
        }

    def identify_frequent_exceptions(self) -> list[dict[str, Any]]:
        """Find freeze names with >1 APPROVED exceptions."""
        approved_counts: dict[str, int] = {}
        for r in self._records:
            if r.exception_status == ExceptionStatus.APPROVED:
                approved_counts[r.freeze_name] = approved_counts.get(r.freeze_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in approved_counts.items():
            if count > 1:
                results.append(
                    {
                        "freeze_name": name,
                        "approved_count": count,
                    }
                )
        results.sort(key=lambda x: x["approved_count"], reverse=True)
        return results

    def rank_by_freeze_duration(self) -> list[dict[str, Any]]:
        """Rank freeze names by average duration_hours descending."""
        name_durations: dict[str, list[float]] = {}
        for r in self._records:
            name_durations.setdefault(r.freeze_name, []).append(r.duration_hours)
        results: list[dict[str, Any]] = []
        for name, durations in name_durations.items():
            results.append(
                {
                    "freeze_name": name,
                    "avg_duration_hours": round(sum(durations) / len(durations), 2),
                }
            )
        results.sort(key=lambda x: x["avg_duration_hours"], reverse=True)
        return results

    def detect_freeze_patterns(self) -> list[dict[str, Any]]:
        """Detect freeze names with >3 records for pattern analysis."""
        name_counts: dict[str, int] = {}
        for r in self._records:
            name_counts[r.freeze_name] = name_counts.get(r.freeze_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in name_counts.items():
            if count > 3:
                results.append(
                    {
                        "freeze_name": name,
                        "record_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ChangeFreezeReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.freeze_type.value] = by_type.get(r.freeze_type.value, 0) + 1
            by_status[r.exception_status.value] = by_status.get(r.exception_status.value, 0) + 1
        denied_or_pending = sum(
            1
            for r in self._records
            if r.exception_status in (ExceptionStatus.DENIED, ExceptionStatus.PENDING)
        )
        compliance_rate = (
            round(denied_or_pending / len(self._records) * 100, 2) if self._records else 0.0
        )
        exception_count = sum(
            1 for r in self._records if r.exception_status == ExceptionStatus.APPROVED
        )
        frequent = len(self.identify_frequent_exceptions())
        recs: list[str] = []
        if exception_count > 0:
            exc_rate = round(exception_count / len(self._records) * 100, 2)
            if exc_rate > self._max_exception_rate_pct:
                recs.append(
                    f"Exception rate {exc_rate}% exceeds {self._max_exception_rate_pct}% threshold"
                )
        if frequent > 0:
            recs.append(f"{frequent} freeze(s) with frequent exceptions")
        if exception_count > 0 and not recs:
            recs.append(f"{exception_count} approved exception(s) within limits")
        if not recs:
            recs.append("Change freeze compliance meets targets")
        return ChangeFreezeReport(
            total_freezes=len(self._records),
            total_exceptions=len(self._exceptions),
            compliance_rate_pct=compliance_rate,
            by_type=by_type,
            by_status=by_status,
            exception_count=exception_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._exceptions.clear()
        logger.info("change_freeze.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freeze_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_freezes": len(self._records),
            "total_exceptions": len(self._exceptions),
            "max_exception_rate_pct": self._max_exception_rate_pct,
            "type_distribution": type_dist,
            "unique_freeze_names": len({r.freeze_name for r in self._records}),
        }
