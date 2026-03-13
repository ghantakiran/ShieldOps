"""Recovery Verification Engine — verify recovery completeness,
detect partial recoveries, rank by effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecoveryStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    PENDING = "pending"


class VerificationMethod(StrEnum):
    SLI_COMPARISON = "sli_comparison"
    HEALTH_CHECK = "health_check"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"


class RecoveryScope(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    DEGRADED = "degraded"


# --- Models ---


class RecoveryVerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    recovery_status: RecoveryStatus = RecoveryStatus.PENDING
    verification_method: VerificationMethod = VerificationMethod.HEALTH_CHECK
    recovery_scope: RecoveryScope = RecoveryScope.FULL
    completeness_pct: float = 0.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryVerificationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    recovery_status: RecoveryStatus = RecoveryStatus.PENDING
    effectiveness_score: float = 0.0
    is_partial: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryVerificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_completeness: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecoveryVerificationEngine:
    """Verify recovery completeness, detect partial recoveries,
    rank recoveries by effectiveness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RecoveryVerificationRecord] = []
        self._analyses: dict[str, RecoveryVerificationAnalysis] = {}
        logger.info(
            "recovery_verification_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        recovery_status: RecoveryStatus = RecoveryStatus.PENDING,
        verification_method: VerificationMethod = VerificationMethod.HEALTH_CHECK,
        recovery_scope: RecoveryScope = RecoveryScope.FULL,
        completeness_pct: float = 0.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> RecoveryVerificationRecord:
        record = RecoveryVerificationRecord(
            incident_id=incident_id,
            recovery_status=recovery_status,
            verification_method=verification_method,
            recovery_scope=recovery_scope,
            completeness_pct=completeness_pct,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recovery_verification.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> RecoveryVerificationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_partial = rec.recovery_status == RecoveryStatus.PARTIAL or rec.completeness_pct < 100.0
        effectiveness = round(rec.completeness_pct / 100.0, 2)
        analysis = RecoveryVerificationAnalysis(
            incident_id=rec.incident_id,
            recovery_status=rec.recovery_status,
            effectiveness_score=effectiveness,
            is_partial=is_partial,
            description=f"Recovery {rec.incident_id} completeness {rec.completeness_pct}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RecoveryVerificationReport:
        by_status: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        pcts: list[float] = []
        for r in self._records:
            by_status[r.recovery_status.value] = by_status.get(r.recovery_status.value, 0) + 1
            by_method[r.verification_method.value] = (
                by_method.get(r.verification_method.value, 0) + 1
            )
            by_scope[r.recovery_scope.value] = by_scope.get(r.recovery_scope.value, 0) + 1
            pcts.append(r.completeness_pct)
        avg = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        recs: list[str] = []
        partial_count = by_status.get("partial", 0) + by_status.get("failed", 0)
        if partial_count > 0:
            recs.append(f"{partial_count} incomplete/failed recoveries need attention")
        if not recs:
            recs.append("All recoveries verified successfully")
        return RecoveryVerificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_completeness=avg,
            by_status=by_status,
            by_method=by_method,
            by_scope=by_scope,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.recovery_status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("recovery_verification_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def verify_recovery_completeness(self) -> list[dict[str, Any]]:
        """Verify recovery completeness per incident."""
        incident_records: dict[str, list[RecoveryVerificationRecord]] = {}
        for r in self._records:
            incident_records.setdefault(r.incident_id, []).append(r)
        results: list[dict[str, Any]] = []
        for iid, records in incident_records.items():
            avg_pct = round(sum(r.completeness_pct for r in records) / len(records), 2)
            complete = all(r.recovery_status == RecoveryStatus.COMPLETE for r in records)
            results.append(
                {
                    "incident_id": iid,
                    "avg_completeness_pct": avg_pct,
                    "fully_complete": complete,
                    "verification_count": len(records),
                }
            )
        results.sort(key=lambda x: x["avg_completeness_pct"], reverse=True)
        return results

    def detect_partial_recoveries(self) -> list[dict[str, Any]]:
        """Detect incidents with partial or failed recoveries."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            is_partial = r.recovery_status in (RecoveryStatus.PARTIAL, RecoveryStatus.FAILED)
            if is_partial and r.incident_id not in seen:
                seen.add(r.incident_id)
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "recovery_status": r.recovery_status.value,
                        "completeness_pct": r.completeness_pct,
                        "service": r.service,
                    }
                )
        results.sort(key=lambda x: x["completeness_pct"])
        return results

    def rank_recoveries_by_effectiveness(self) -> list[dict[str, Any]]:
        """Rank incidents by recovery effectiveness."""
        incident_pcts: dict[str, list[float]] = {}
        for r in self._records:
            incident_pcts.setdefault(r.incident_id, []).append(r.completeness_pct)
        results: list[dict[str, Any]] = []
        for iid, pcts in incident_pcts.items():
            avg = round(sum(pcts) / len(pcts), 2)
            results.append(
                {
                    "incident_id": iid,
                    "avg_effectiveness": avg,
                    "check_count": len(pcts),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
